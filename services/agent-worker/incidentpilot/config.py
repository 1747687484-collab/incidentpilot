from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_addr: str
    nats_url: str
    metrics_port: int
    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: float
    llm_max_tokens: int
    llm_temperature: float


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgres://incidentpilot:incidentpilot@localhost:5432/incidentpilot?sslmode=disable",
        ),
        redis_addr=os.getenv("REDIS_ADDR", "localhost:6379"),
        nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
        metrics_port=int(os.getenv("AGENT_METRICS_PORT", "9100")),
        llm_provider=os.getenv("LLM_PROVIDER", "disabled").strip().lower(),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "12")),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "700")),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
    )
