# Frfr Makefile

# Use docker compose (v2) instead of docker-compose
DOCKER_COMPOSE := docker compose

.PHONY: help build up down logs shell temporal-ui clean test install dev

# Default target
help:
	@echo "Frfr - Docker Management Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make build          Build Docker images"
	@echo "  make up             Start all services"
	@echo "  make down           Stop all services"
	@echo ""
	@echo "Development:"
	@echo "  make dev            Start in development mode with hot reload"
	@echo "  make shell          Open shell in frfr container"
	@echo "  make logs           Follow logs from all services"
	@echo "  make install        Install package in development mode"
	@echo ""
	@echo "Temporal:"
	@echo "  make temporal-ui    Open Temporal Web UI in browser"
	@echo "  make temporal-shell Open shell in Temporal admin tools"
	@echo ""
	@echo "Utilities:"
	@echo "  make test           Run tests"
	@echo "  make test-components Test Docker components independently"
	@echo "  make clean          Clean up containers and volumes"
	@echo "  make reset          Full reset (clean + rebuild)"

# Build images
build:
	$(DOCKER_COMPOSE) build

# Start services
up:
	$(DOCKER_COMPOSE) up -d
	@echo "Services started. Temporal UI: http://localhost:8233"
	@echo "Run 'make shell' to access frfr container"

# Start in development mode
dev:
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up

# Stop services
down:
	$(DOCKER_COMPOSE) down

# View logs
logs:
	$(DOCKER_COMPOSE) logs -f

# Open shell in frfr container
shell:
	$(DOCKER_COMPOSE) exec frfr bash

# Open Temporal Web UI
temporal-ui:
	@echo "Opening Temporal UI at http://localhost:8233"
	@open http://localhost:8233 2>/dev/null || xdg-open http://localhost:8233 2>/dev/null || echo "Please open http://localhost:8233 in your browser"

# Open shell in Temporal admin tools
temporal-shell:
	$(DOCKER_COMPOSE) exec temporal-admin-tools bash

# Install package in development mode (inside container)
install:
	$(DOCKER_COMPOSE) exec frfr pip install -e .

# Run tests (when implemented)
test:
	$(DOCKER_COMPOSE) exec frfr pytest tests/

# Test Docker components independently
test-components:
	@echo "Testing Docker components..."
	$(DOCKER_COMPOSE) exec frfr bash /app/scripts/test_components.sh

# Clean up
clean:
	$(DOCKER_COMPOSE) down -v
	rm -rf .frfr_sessions/
	rm -rf sessions/

# Full reset
reset: clean
	$(DOCKER_COMPOSE) build --no-cache
	$(DOCKER_COMPOSE) up -d

# Create necessary directories
init:
	mkdir -p documents sessions temporal-dynamicconfig
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env file - please edit with your API key"; fi
