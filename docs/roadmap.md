# Roadmap

## MVP Completed

- Docker Compose stack.
- PostgreSQL + pgvector schema.
- Go API service.
- Python Agent worker.
- React dashboard.
- Synthetic fault injection.
- Runbook retrieval.
- Evidence-grounded RCA report.
- Human-approved remediation.
- Prometheus and Grafana provisioning.
- Unit tests and evaluation set.

## Phase 1: Team Hardening

- Add CI workflow for Go, Python, and web checks.
- Add API integration tests against Docker Compose.
- Add seed data reset script.
- Add environment variable reference.
- Add API examples with PowerShell and curl.

## Phase 2: Agent Capability

- Add optional OpenAI-compatible model provider interface.
- Add prompt templates for RCA and verifier stages.
- Add hallucination checks that require evidence IDs.
- Add richer evaluation cases and scoring report.
- Add model latency and token metrics.

## Phase 3: Backend Reliability

- Add JetStream dead-letter queue.
- Add retry policy configuration.
- Add rate limiting middleware.
- Add structured request logs.
- Add OpenTelemetry tracing across API, queue, worker, and tools.

## Phase 4: Product Polish

- Add incident list and filters.
- Add runbook management page.
- Add action risk review details.
- Add dashboard charts for SLI changes.
- Add demo video and screenshots.

## Phase 5: Deployment

- Add Kubernetes manifests.
- Add Helm chart.
- Add cloud deployment guide.
- Add production security checklist.

