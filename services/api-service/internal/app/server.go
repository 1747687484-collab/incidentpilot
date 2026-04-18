package app

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/nats-io/nats.go"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
)

var (
	httpRequests = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "incidentpilot_http_requests_total",
			Help: "Total API requests.",
		},
		[]string{"method", "route", "status"},
	)
	httpLatency = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "incidentpilot_http_request_duration_seconds",
			Help:    "API request duration.",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "route"},
	)
)

func init() {
	prometheus.MustRegister(httpRequests, httpLatency)
}

type Server struct {
	cfg    Config
	db     *pgxpool.Pool
	redis  *redis.Client
	nc     *nats.Conn
	js     nats.JetStreamContext
	server *http.Server
}

func New(ctx context.Context, cfg Config) (*Server, error) {
	db, err := pgxpool.New(ctx, cfg.DatabaseURL)
	if err != nil {
		return nil, fmt.Errorf("connect postgres: %w", err)
	}
	if err := db.Ping(ctx); err != nil {
		db.Close()
		return nil, fmt.Errorf("ping postgres: %w", err)
	}

	rdb := redis.NewClient(&redis.Options{Addr: cfg.RedisAddr})
	if err := rdb.Ping(ctx).Err(); err != nil {
		db.Close()
		return nil, fmt.Errorf("ping redis: %w", err)
	}

	nc, err := nats.Connect(cfg.NATSURL, nats.Name("incidentpilot-api"))
	if err != nil {
		db.Close()
		_ = rdb.Close()
		return nil, fmt.Errorf("connect nats: %w", err)
	}
	js, err := nc.JetStream()
	if err != nil {
		db.Close()
		_ = rdb.Close()
		nc.Close()
		return nil, fmt.Errorf("create jetstream context: %w", err)
	}
	if _, err := js.StreamInfo("INCIDENTS"); err != nil {
		if _, addErr := js.AddStream(&nats.StreamConfig{
			Name:     "INCIDENTS",
			Subjects: []string{"incident.*", "remediation.*", "simulation.*"},
			Storage:  nats.FileStorage,
		}); addErr != nil {
			db.Close()
			_ = rdb.Close()
			nc.Close()
			return nil, fmt.Errorf("ensure jetstream stream: %w", addErr)
		}
	}

	s := &Server{cfg: cfg, db: db, redis: rdb, nc: nc, js: js}
	mux := http.NewServeMux()
	mux.HandleFunc("/api/healthz", s.handleHealth)
	mux.Handle("/metrics", promhttp.Handler())
	mux.HandleFunc("/api/incidents", s.handleIncidents)
	mux.HandleFunc("/api/incidents/", s.handleIncidentByID)
	mux.HandleFunc("/api/knowledge/documents", s.handleKnowledgeDocuments)
	mux.HandleFunc("/api/simulations/faults", s.handleFaults)

	s.server = &http.Server{
		Addr:              cfg.Addr,
		Handler:           s.withMiddleware(mux),
		ReadHeaderTimeout: 5 * time.Second,
	}
	return s, nil
}

func (s *Server) Addr() string {
	return s.cfg.Addr
}

func (s *Server) ListenAndServe() error {
	return s.server.ListenAndServe()
}

func (s *Server) Shutdown(ctx context.Context) error {
	return s.server.Shutdown(ctx)
}

func (s *Server) Close() {
	if s.nc != nil {
		s.nc.Close()
	}
	if s.redis != nil {
		_ = s.redis.Close()
	}
	if s.db != nil {
		s.db.Close()
	}
}

func (s *Server) withMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Idempotency-Key")
		w.Header().Set("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		start := time.Now()
		next.ServeHTTP(rec, r)
		route := routeLabel(r.URL.Path)
		status := fmt.Sprintf("%d", rec.status)
		httpRequests.WithLabelValues(r.Method, route, status).Inc()
		httpLatency.WithLabelValues(r.Method, route).Observe(time.Since(start).Seconds())
	})
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(status int) {
	r.status = status
	r.ResponseWriter.WriteHeader(status)
}

func routeLabel(path string) string {
	switch {
	case path == "/api/incidents":
		return "/api/incidents"
	case strings.HasPrefix(path, "/api/incidents/") && strings.HasSuffix(path, "/events"):
		return "/api/incidents/{id}/events"
	case strings.HasPrefix(path, "/api/incidents/") && strings.HasSuffix(path, "/approve-action"):
		return "/api/incidents/{id}/approve-action"
	case strings.HasPrefix(path, "/api/incidents/"):
		return "/api/incidents/{id}"
	default:
		return path
	}
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *Server) handleIncidents(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	var req CreateIncidentRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	req.Service = strings.TrimSpace(req.Service)
	req.Symptom = strings.TrimSpace(req.Symptom)
	if req.Severity == "" {
		req.Severity = "SEV2"
	}
	if !validService(req.Service) {
		writeError(w, http.StatusBadRequest, "service must be order, payment, or inventory")
		return
	}
	if len(req.Symptom) < 8 {
		writeError(w, http.StatusBadRequest, "symptom must be at least 8 characters")
		return
	}

	if key := strings.TrimSpace(r.Header.Get("Idempotency-Key")); key != "" {
		cacheKey := "incident:create:" + key
		if existing, err := s.redis.Get(r.Context(), cacheKey).Result(); err == nil && existing != "" {
			detail, err := s.getIncidentDetail(r.Context(), existing)
			if err == nil {
				writeJSON(w, http.StatusOK, detail)
				return
			}
		}
	}

	var id string
	err := s.db.QueryRow(r.Context(), `
		INSERT INTO incidents (service, symptom, severity, status)
		VALUES ($1, $2, $3, 'queued')
		RETURNING id::text
	`, req.Service, req.Symptom, strings.ToUpper(req.Severity)).Scan(&id)
	if err != nil {
		slog.Error("insert incident failed", "error", err)
		writeError(w, http.StatusInternalServerError, "failed to create incident")
		return
	}

	if key := strings.TrimSpace(r.Header.Get("Idempotency-Key")); key != "" {
		_ = s.redis.Set(r.Context(), "incident:create:"+key, id, 24*time.Hour).Err()
	}

	_ = s.recordEvent(r.Context(), id, "incident.created", map[string]any{
		"service":  req.Service,
		"symptom":  req.Symptom,
		"severity": strings.ToUpper(req.Severity),
	})
	_ = s.publishJSON("incident.created", map[string]any{"incident_id": id})

	detail, err := s.getIncidentDetail(r.Context(), id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to load incident")
		return
	}
	writeJSON(w, http.StatusCreated, detail)
}

func (s *Server) handleIncidentByID(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/api/incidents/")
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) == 0 || parts[0] == "" {
		writeError(w, http.StatusNotFound, "incident not found")
		return
	}
	incidentID := parts[0]
	if _, err := uuid.Parse(incidentID); err != nil {
		writeError(w, http.StatusBadRequest, "invalid incident id")
		return
	}

	if len(parts) == 2 && parts[1] == "events" {
		s.handleIncidentEvents(w, r, incidentID)
		return
	}
	if len(parts) == 2 && parts[1] == "approve-action" {
		s.handleApproveAction(w, r, incidentID)
		return
	}
	if len(parts) > 1 {
		writeError(w, http.StatusNotFound, "route not found")
		return
	}
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}
	detail, err := s.getIncidentDetail(r.Context(), incidentID)
	if errors.Is(err, pgx.ErrNoRows) {
		writeError(w, http.StatusNotFound, "incident not found")
		return
	}
	if err != nil {
		slog.Error("load incident failed", "error", err)
		writeError(w, http.StatusInternalServerError, "failed to load incident")
		return
	}
	writeJSON(w, http.StatusOK, detail)
}

func (s *Server) handleIncidentEvents(w http.ResponseWriter, r *http.Request, incidentID string) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}
	flusher, ok := w.(http.Flusher)
	if !ok {
		writeError(w, http.StatusInternalServerError, "streaming unsupported")
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	var lastID int64
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()
	for {
		rows, err := s.db.Query(r.Context(), `
			SELECT id, event_type, payload
			FROM incident_events
			WHERE incident_id = $1 AND id > $2
			ORDER BY id ASC
		`, incidentID, lastID)
		if err != nil {
			fmt.Fprintf(w, "event: error\ndata: %q\n\n", "failed to read events")
			flusher.Flush()
			return
		}
		for rows.Next() {
			var id int64
			var eventType string
			var payload []byte
			if err := rows.Scan(&id, &eventType, &payload); err == nil {
				lastID = id
				fmt.Fprintf(w, "id: %d\nevent: %s\ndata: %s\n\n", id, eventType, payload)
			}
		}
		rows.Close()
		flusher.Flush()

		select {
		case <-r.Context().Done():
			return
		case <-ticker.C:
		}
	}
}

func (s *Server) handleApproveAction(w http.ResponseWriter, r *http.Request, incidentID string) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}
	var req ApproveActionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	if _, err := uuid.Parse(req.ActionID); err != nil {
		writeError(w, http.StatusBadRequest, "invalid action_id")
		return
	}
	if req.Operator == "" {
		req.Operator = "local-demo"
	}

	var action RemediationAction
	var params []byte
	err := s.db.QueryRow(r.Context(), `
		UPDATE remediation_actions
		SET status = 'approved'
		WHERE incident_id = $1 AND id = $2 AND status = 'pending_approval'
		RETURNING id::text, type, params, risk_level, requires_approval, status, idempotency_key, created_at, updated_at
	`, incidentID, req.ActionID).Scan(
		&action.ID, &action.Type, &params, &action.RiskLevel, &action.RequiresApproval,
		&action.Status, &action.IdempotencyKey, &action.CreatedAt, &action.UpdatedAt,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		existing, loadErr := s.getAction(r.Context(), incidentID, req.ActionID)
		if loadErr != nil {
			writeError(w, http.StatusNotFound, "pending action not found")
			return
		}
		writeJSON(w, http.StatusOK, existing)
		return
	}
	if err != nil {
		slog.Error("approve action failed", "error", err)
		writeError(w, http.StatusInternalServerError, "failed to approve action")
		return
	}
	action.Params = json.RawMessage(params)

	_ = s.recordEvent(r.Context(), incidentID, "action.approved", map[string]any{
		"action_id": req.ActionID,
		"operator":  req.Operator,
	})
	_ = s.publishJSON("remediation.approved", map[string]any{
		"incident_id": incidentID,
		"action_id":   req.ActionID,
		"operator":    req.Operator,
	})
	writeJSON(w, http.StatusOK, action)
}

func (s *Server) handleKnowledgeDocuments(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}
	var req KnowledgeDocumentRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	req.Title = strings.TrimSpace(req.Title)
	req.Content = strings.TrimSpace(req.Content)
	if req.Source == "" {
		req.Source = "manual"
	}
	if req.Title == "" || len(req.Content) < 40 {
		writeError(w, http.StatusBadRequest, "title and content are required")
		return
	}

	tx, err := s.db.Begin(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to start transaction")
		return
	}
	defer tx.Rollback(r.Context())

	var docID string
	if err := tx.QueryRow(r.Context(), `
		INSERT INTO knowledge_documents (title, source, content)
		VALUES ($1, $2, $3)
		RETURNING id::text
	`, req.Title, req.Source, req.Content).Scan(&docID); err != nil {
		writeError(w, http.StatusInternalServerError, "failed to insert document")
		return
	}

	chunks := splitContent(req.Content, 120)
	for i, chunk := range chunks {
		_, err := tx.Exec(r.Context(), `
			INSERT INTO knowledge_chunks (document_id, chunk_index, content, embedding)
			VALUES ($1, $2, $3, $4::vector)
		`, docID, i, chunk, embeddingLiteral(chunk))
		if err != nil {
			writeError(w, http.StatusInternalServerError, "failed to insert chunks")
			return
		}
	}

	if err := tx.Commit(r.Context()); err != nil {
		writeError(w, http.StatusInternalServerError, "failed to commit document")
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{
		"id":      docID,
		"title":   req.Title,
		"chunks":  len(chunks),
		"message": "document indexed",
	})
}

func (s *Server) handleFaults(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}
	var req FaultRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	req.Service = strings.TrimSpace(req.Service)
	req.FaultType = strings.TrimSpace(req.FaultType)
	if !validService(req.Service) {
		writeError(w, http.StatusBadRequest, "service must be order, payment, or inventory")
		return
	}
	if req.FaultType == "" {
		writeError(w, http.StatusBadRequest, "fault_type is required")
		return
	}
	if req.Intensity == 0 {
		req.Intensity = 70
	}
	if req.Intensity < 1 || req.Intensity > 100 {
		writeError(w, http.StatusBadRequest, "intensity must be 1..100")
		return
	}
	if len(req.Details) == 0 {
		req.Details = json.RawMessage(`{}`)
	}

	var id string
	err := s.db.QueryRow(r.Context(), `
		INSERT INTO faults (service, fault_type, intensity, details)
		VALUES ($1, $2, $3, $4::jsonb)
		RETURNING id::text
	`, req.Service, req.FaultType, req.Intensity, string(req.Details)).Scan(&id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to inject fault")
		return
	}
	_ = s.publishJSON("simulation.fault.injected", map[string]any{
		"fault_id":   id,
		"service":    req.Service,
		"fault_type": req.FaultType,
		"intensity":  req.Intensity,
	})
	writeJSON(w, http.StatusCreated, map[string]any{
		"id":         id,
		"service":    req.Service,
		"fault_type": req.FaultType,
		"intensity":  req.Intensity,
		"active":     true,
	})
}

func (s *Server) getIncidentDetail(ctx context.Context, incidentID string) (IncidentDetail, error) {
	var detail IncidentDetail
	err := s.db.QueryRow(ctx, `
		SELECT id::text, service, symptom, severity, status, created_at, updated_at
		FROM incidents
		WHERE id = $1
	`, incidentID).Scan(
		&detail.Incident.ID, &detail.Incident.Service, &detail.Incident.Symptom,
		&detail.Incident.Severity, &detail.Incident.Status, &detail.Incident.CreatedAt,
		&detail.Incident.UpdatedAt,
	)
	if err != nil {
		return detail, err
	}

	evidenceRows, err := s.db.Query(ctx, `
		SELECT id::text, source, query, content, score, timestamp
		FROM evidence
		WHERE incident_id = $1
		ORDER BY timestamp ASC
	`, incidentID)
	if err != nil {
		return detail, err
	}
	defer evidenceRows.Close()
	for evidenceRows.Next() {
		var item Evidence
		if err := evidenceRows.Scan(&item.ID, &item.Source, &item.Query, &item.Content, &item.Score, &item.Timestamp); err != nil {
			return detail, err
		}
		detail.Evidence = append(detail.Evidence, item)
	}

	stepRows, err := s.db.Query(ctx, `
		SELECT id::text, agent_name, tool_name, input_hash, output_summary, latency_ms, status, created_at
		FROM agent_steps
		WHERE incident_id = $1
		ORDER BY created_at ASC
	`, incidentID)
	if err != nil {
		return detail, err
	}
	defer stepRows.Close()
	for stepRows.Next() {
		var item AgentStep
		if err := stepRows.Scan(&item.ID, &item.AgentName, &item.ToolName, &item.InputHash, &item.OutputSummary, &item.LatencyMS, &item.Status, &item.CreatedAt); err != nil {
			return detail, err
		}
		detail.Steps = append(detail.Steps, item)
	}

	actionRows, err := s.db.Query(ctx, `
		SELECT id::text, type, params, risk_level, requires_approval, status, idempotency_key, created_at, updated_at
		FROM remediation_actions
		WHERE incident_id = $1
		ORDER BY created_at ASC
	`, incidentID)
	if err != nil {
		return detail, err
	}
	defer actionRows.Close()
	for actionRows.Next() {
		var item RemediationAction
		var params []byte
		if err := actionRows.Scan(&item.ID, &item.Type, &params, &item.RiskLevel, &item.RequiresApproval, &item.Status, &item.IdempotencyKey, &item.CreatedAt, &item.UpdatedAt); err != nil {
			return detail, err
		}
		item.Params = json.RawMessage(params)
		detail.Actions = append(detail.Actions, item)
	}

	report, err := s.getReport(ctx, incidentID)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return detail, err
	}
	if err == nil {
		detail.Report = &report
	}
	return detail, nil
}

func (s *Server) getReport(ctx context.Context, incidentID string) (RootCauseReport, error) {
	var report RootCauseReport
	var evidenceJSON, actionsJSON, limitationsJSON string
	err := s.db.QueryRow(ctx, `
		SELECT id::text, root_cause, confidence,
		       array_to_json(evidence_ids)::text,
		       array_to_json(recommended_actions)::text,
		       array_to_json(limitations)::text,
		       created_at
		FROM root_cause_reports
		WHERE incident_id = $1
	`, incidentID).Scan(
		&report.ID, &report.RootCause, &report.Confidence,
		&evidenceJSON, &actionsJSON, &limitationsJSON, &report.CreatedAt,
	)
	if err != nil {
		return report, err
	}
	_ = json.Unmarshal([]byte(evidenceJSON), &report.EvidenceIDs)
	_ = json.Unmarshal([]byte(actionsJSON), &report.RecommendedActions)
	_ = json.Unmarshal([]byte(limitationsJSON), &report.Limitations)
	return report, nil
}

func (s *Server) getAction(ctx context.Context, incidentID, actionID string) (RemediationAction, error) {
	var action RemediationAction
	var params []byte
	err := s.db.QueryRow(ctx, `
		SELECT id::text, type, params, risk_level, requires_approval, status, idempotency_key, created_at, updated_at
		FROM remediation_actions
		WHERE incident_id = $1 AND id = $2
	`, incidentID, actionID).Scan(
		&action.ID, &action.Type, &params, &action.RiskLevel, &action.RequiresApproval,
		&action.Status, &action.IdempotencyKey, &action.CreatedAt, &action.UpdatedAt,
	)
	action.Params = json.RawMessage(params)
	return action, err
}

func (s *Server) recordEvent(ctx context.Context, incidentID, eventType string, payload any) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	_, err = s.db.Exec(ctx, `
		INSERT INTO incident_events (incident_id, event_type, payload)
		VALUES ($1, $2, $3)
	`, incidentID, eventType, body)
	return err
}

func (s *Server) publishJSON(subject string, payload any) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	_, err = s.js.Publish(subject, body)
	return err
}

func validService(service string) bool {
	switch service {
	case "order", "payment", "inventory":
		return true
	default:
		return false
	}
}

var wordRE = regexp.MustCompile(`\s+`)

func splitContent(content string, wordsPerChunk int) []string {
	words := wordRE.Split(strings.TrimSpace(content), -1)
	if len(words) == 0 {
		return []string{content}
	}
	var chunks []string
	for start := 0; start < len(words); start += wordsPerChunk {
		end := start + wordsPerChunk
		if end > len(words) {
			end = len(words)
		}
		chunks = append(chunks, strings.Join(words[start:end], " "))
	}
	return chunks
}

func embeddingLiteral(text string) string {
	keywords := []string{"order", "payment", "inventory", "timeout", "cache", "database", "error", "latency"}
	lower := strings.ToLower(text)
	values := make([]string, 0, len(keywords))
	for _, keyword := range keywords {
		count := float64(strings.Count(lower, keyword))
		values = append(values, fmt.Sprintf("%.4f", (count+1)/10))
	}
	return "[" + strings.Join(values, ",") + "]"
}

func hashString(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])[:16]
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]any{"error": message})
}
