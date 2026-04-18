from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_addr: str
    nats_url: str
    metrics_port: int


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgres://incidentpilot:incidentpilot@localhost:5432/incidentpilot?sslmode=disable",
        ),
        redis_addr=os.getenv("REDIS_ADDR", "localhost:6379"),
        nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
        metrics_port=int(os.getenv("AGENT_METRICS_PORT", "9100")),
    )

