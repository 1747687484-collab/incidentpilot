# Contributing Guide

## Working Agreement

IncidentPilot is structured as a team project. Keep changes small, documented, and testable. Prefer behavior-level issues and pull requests over broad rewrites.

## Branches

Use short descriptive branch names:

```text
feature/incident-list
fix/action-idempotency
docs/architecture-update
test/agent-eval-cases
```

## Commits

Use conventional-style commit prefixes:

```text
feat(api): add incident list endpoint
fix(worker): avoid duplicate action execution
docs: add product requirements
test(agent): add payment timeout cases
chore: update compose config
```

## Pull Requests

Every PR should include:

- What changed.
- Why it changed.
- How it was tested.
- Screenshots or API examples for UI/API changes.
- Follow-up work, if any.

## Code Ownership

- `services/api-service`: backend/API owner.
- `services/agent-worker`: Agent/workflow owner.
- `services/web`: frontend owner.
- `db/init`: data model owner.
- `configs`: infrastructure/observability owner.
- `tests`: QA/evaluation owner.
- `docs`: product and architecture owner.

## Local Checks

Run the checks that match your change:

```bash
docker compose config --quiet
docker run --rm -v ${PWD}/services/api-service:/src -w /src golang:1.23-alpine go test ./...
docker run --rm -v ${PWD}/services/agent-worker:/app -w /app incidentpilot-agent-worker python -m pytest
cd services/web && npm install && npm run build
python tests/agent_eval/run_eval.py
```

## Review Checklist

- Does the change preserve public API compatibility?
- Are write actions still approval-gated?
- Are tool calls auditable?
- Is the README or docs updated when behavior changes?
- Can another teammate run the project without private credentials?

