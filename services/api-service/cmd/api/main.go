package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"incidentpilot/api-service/internal/app"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	server, err := app.New(ctx, app.LoadConfig())
	if err != nil {
		slog.Error("failed to initialize api service", "error", err)
		os.Exit(1)
	}
	defer server.Close()

	errCh := make(chan error, 1)
	go func() {
		slog.Info("api service listening", "addr", server.Addr())
		errCh <- server.ListenAndServe()
	}()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), app.DefaultShutdownTimeout)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			slog.Error("graceful shutdown failed", "error", err)
			os.Exit(1)
		}
	case err := <-errCh:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("api service stopped unexpectedly", "error", err)
			os.Exit(1)
		}
	}
}

