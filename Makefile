.PHONY: up down logs api-test agent-test web-build

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api-service agent-worker web

api-test:
	cd services/api-service && go test ./...

agent-test:
	cd services/agent-worker && python -m pytest

web-build:
	cd services/web && npm run build

