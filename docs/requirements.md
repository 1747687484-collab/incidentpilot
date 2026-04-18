# Product Requirements

## Background

IncidentPilot is designed as a portfolio-grade team project for backend engineering and Agent application interviews. The product simulates common production incidents, gathers evidence through tools, produces a traceable root cause report, and executes remediation only after human approval.

## Goals

- Provide a runnable local AIOps incident response platform.
- Demonstrate distributed backend skills: API design, queueing, idempotency, persistence, observability, and container orchestration.
- Demonstrate Agent application skills: tool use, evidence collection, runbook retrieval, multi-step reasoning, verification, and guarded execution.
- Support team collaboration with clear module ownership, issue templates, tests, and documentation.

## Non-Goals

- Do not connect to real company logs, metrics, or production systems.
- Do not execute destructive remediation.
- Do not require a paid LLM API key for the default demo.
- Do not model every AIOps edge case in the first MVP.

## Personas

- Backend intern candidate: wants to show production-style service design and reliability thinking.
- Agent application intern candidate: wants to show tool-calling workflow and evidence-grounded RCA.
- Reviewer/interviewer: wants to run the project quickly and understand the engineering tradeoffs.
- Teammate contributor: wants clear tasks, interfaces, and acceptance criteria.

## Core User Stories

- As an operator, I can inject a synthetic fault for `order`, `payment`, or `inventory`.
- As an operator, I can create an incident with service, symptom, and severity.
- As an operator, I can watch the Agent workflow through live SSE events.
- As an operator, I can inspect evidence gathered from logs, metrics, topology, and runbooks.
- As an operator, I can review a root cause report with confidence and limitations.
- As an operator, I can approve a recommended action and see the incident become resolved.
- As a contributor, I can run tests and understand which subsystem I own.

## Functional Requirements

- Incident API supports create, read, and SSE event streaming.
- Knowledge API supports uploading Markdown-style runbook documents.
- Simulation API supports fault injection for cache stampede, payment timeout, and database slow query.
- Agent worker consumes incident messages from NATS JetStream.
- Agent workflow writes evidence, steps, action proposals, reports, and audit records.
- Remediation actions require approval and are idempotent.
- Dashboard supports fault injection, incident creation, evidence view, timeline view, report view, and approval.
- Metrics are exposed for API requests and Agent tool calls.

## Non-Functional Requirements

- The project must start with one Docker Compose command.
- The public API must be stable enough for frontend and worker teams to develop independently.
- Tool calls must have timeout, input validation, and audit records.
- The default demo must run without external SaaS dependencies.
- Sensitive configuration must not be passed into Agent prompts or logs.
- Documentation must explain architecture, ownership, and test expectations.

## Acceptance Criteria

- `docker compose up --build` starts the stack.
- `GET /api/healthz` returns `ok`.
- A cache stampede incident produces at least four evidence records.
- A completed RCA report cites evidence IDs.
- A proposed action starts as `pending_approval`.
- Approval changes the action to `executed` and the incident to `resolved`.
- Repeating the same approval does not execute the action again.
- Go and Python unit tests pass.

