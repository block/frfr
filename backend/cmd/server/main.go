package main

import (
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/nesposito/frfr/internal/api"
	"github.com/nesposito/frfr/internal/config"
)

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// Create and start server
	server := api.NewServer(cfg)

	// Handle graceful shutdown
	done := make(chan os.Signal, 1)
	signal.Notify(done, os.Interrupt, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		log.Printf("Starting frfr server on port %s", cfg.Port)
		log.Printf("Session storage: %s", cfg.SessionStorageDir)
		if cfg.AnthropicAPIKey != "" {
			log.Printf("Claude API: using explicit API key")
		} else {
			log.Printf("Claude API: using native credentials (claude CLI)")
		}
		if err := server.ListenAndServe(); err != nil {
			log.Fatalf("Server error: %v", err)
		}
	}()

	fmt.Printf("\nfrfr backend server running on http://localhost:%s\n", cfg.Port)
	fmt.Println("Press Ctrl+C to stop")

	<-done
	log.Println("Server stopped")
}
