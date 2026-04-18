# Demo Script

## 2-3 minute walkthrough

1. Start the stack with `docker compose up --build`.
2. Open `http://localhost:5173`.
3. Inject `order / cache_stampede` with intensity `82`.
4. Create an incident with the default checkout latency symptom.
5. Explain that the Go API writes the incident, emits `incident.created` to NATS JetStream, and streams SSE events to the UI.
6. Watch `triage_agent`, `evidence_agent`, `rca_agent`, `verifier_agent`, and `action_agent` appear.
7. Open the evidence chain and point out logs, metrics, topology, and Runbook retrieval.
8. Approve the proposed action.
9. Show the status moving to `resolved`.
10. Open Grafana or Prometheus and mention API/Agent metrics.

## Interview talking points

- The core backend challenge is not the UI; it is durable task orchestration, idempotent writes, state recovery, and evidence traceability.
- Every tool call is audited with latency and status.
- Write actions are separated from reasoning and require explicit approval.
- The project can be extended with real OpenTelemetry traces, real log backends, and OpenAI-compatible model calls.

