package app

import (
	"os"
	"time"
)

const DefaultShutdownTimeout = 10 * time.Second

type Config struct {
	Addr        string
	DatabaseURL string
	RedisAddr   string
	NATSURL     string
}

func LoadConfig() Config {
	return Config{
		Addr:        env("API_ADDR", ":8080"),
		DatabaseURL: env("DATABASE_URL", "postgres://incidentpilot:incidentpilot@localhost:5432/incidentpilot?sslmode=disable"),
		RedisAddr:   env("REDIS_ADDR", "localhost:6379"),
		NATSURL:     env("NATS_URL", "nats://localhost:4222"),
	}
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

