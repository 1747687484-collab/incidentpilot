package app

import (
	"encoding/json"
	"time"
)

type Incident struct {
	ID        string    `json:"id"`
	Service   string    `json:"service"`
	Symptom   string    `json:"symptom"`
	Severity  string    `json:"severity"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

type Evidence struct {
	ID        string    `json:"id"`
	Source    string    `json:"source"`
	Query     string    `json:"query"`
	Content   string    `json:"content"`
	Score     float32   `json:"score"`
	Timestamp time.Time `json:"timestamp"`
}

type AgentStep struct {
	ID            string    `json:"id"`
	AgentName     string    `json:"agent_name"`
	ToolName      string    `json:"tool_name"`
	InputHash     string    `json:"input_hash"`
	OutputSummary string    `json:"output_summary"`
	LatencyMS     int       `json:"latency_ms"`
	Status        string    `json:"status"`
	CreatedAt     time.Time `json:"created_at"`
}

type RemediationAction struct {
	ID               string          `json:"id"`
	Type             string          `json:"type"`
	Params           json.RawMessage `json:"params"`
	RiskLevel        string          `json:"risk_level"`
	RequiresApproval bool            `json:"requires_approval"`
	Status           string          `json:"status"`
	IdempotencyKey   string          `json:"idempotency_key"`
	CreatedAt        time.Time       `json:"created_at"`
	UpdatedAt        time.Time       `json:"updated_at"`
}

type RootCauseReport struct {
	ID                 string    `json:"id"`
	RootCause          string    `json:"root_cause"`
	Confidence         float32   `json:"confidence"`
	EvidenceIDs        []string  `json:"evidence_ids"`
	RecommendedActions []string  `json:"recommended_actions"`
	Limitations        []string  `json:"limitations"`
	CreatedAt          time.Time `json:"created_at"`
}

type IncidentDetail struct {
	Incident Incident            `json:"incident"`
	Evidence []Evidence          `json:"evidence"`
	Steps    []AgentStep         `json:"steps"`
	Actions  []RemediationAction `json:"actions"`
	Report   *RootCauseReport    `json:"report,omitempty"`
}

type IncidentListResponse struct {
	Items []Incident `json:"items"`
	Limit int        `json:"limit"`
}

type KnowledgeDocumentSummary struct {
	ID         string    `json:"id"`
	Title      string    `json:"title"`
	Source     string    `json:"source"`
	ChunkCount int       `json:"chunk_count"`
	CreatedAt  time.Time `json:"created_at"`
}

type KnowledgeDocumentListResponse struct {
	Items []KnowledgeDocumentSummary `json:"items"`
	Limit int                        `json:"limit"`
}

type CreateIncidentRequest struct {
	Service  string `json:"service"`
	Symptom  string `json:"symptom"`
	Severity string `json:"severity"`
}

type KnowledgeDocumentRequest struct {
	Title   string `json:"title"`
	Source  string `json:"source"`
	Content string `json:"content"`
}

type FaultRequest struct {
	Service   string          `json:"service"`
	FaultType string          `json:"fault_type"`
	Intensity int             `json:"intensity"`
	Details   json.RawMessage `json:"details"`
}

type ApproveActionRequest struct {
	ActionID string `json:"action_id"`
	Operator string `json:"operator"`
}
