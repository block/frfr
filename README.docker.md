# Frfr - Docker Setup Guide

## Quick Start

### 1. Prerequisites
- Docker Desktop or Docker Engine with docker-compose
- Anthropic API key

### 2. Initial Setup

```bash
# Create necessary directories and .env file
make init

# Edit .env with your API key
nano .env  # or use your preferred editor

# Build images
make build

# Start all services
make up
```

### 3. Usage

```bash
# Open a shell in the frfr container
make shell

# Inside the container, run frfr
frfr start-session --docs /app/documents/report.pdf

# Or run Python scripts directly
python scripts/start_temporal.py
```

## Architecture

The Docker setup includes:

1. **frfr** - Main application container
   - Python 3.11
   - ImageMagick & Tesseract OCR
   - All Python dependencies
   - Mounted volumes for code and documents

2. **temporal** - Temporal workflow engine
   - Auto-setup with PostgreSQL backend
   - Web UI on port 8233
   - gRPC on port 7233

3. **postgres** - Database for Temporal
   - Persistent data volume
   - Isolated on internal network

4. **temporal-admin-tools** - CLI tools for Temporal
   - Optional, for advanced Temporal operations

## Directory Structure

```
frfr/
├── documents/              # Place your PDF/MD files here
├── sessions/               # Session data (auto-created)
├── temporal-dynamicconfig/ # Temporal config (optional)
└── .env                    # Your environment variables
```

## Common Commands

### Service Management
```bash
make up             # Start all services
make down           # Stop all services
make logs           # View logs
make test-components # Test all Docker components
```

### Development
```bash
make dev         # Start with hot reload
make shell       # Interactive shell
make install     # Reinstall package
make test        # Run tests
```

### Temporal
```bash
make temporal-ui    # Open Web UI (http://localhost:8233)
make temporal-shell # Shell in admin tools container
```

### Cleanup
```bash
make clean       # Stop and remove volumes
make reset       # Full rebuild
```

## Environment Variables

Edit `.env` to configure:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional - Override defaults
TEMPORAL_ADDRESS=temporal:7233
SWARM_SIZE=5
CONSENSUS_THRESHOLD=0.8
SIMILARITY_THRESHOLD=0.85
SWARM_MODEL=claude-sonnet-4
JUDGE_MODEL=claude-opus-4
```

## Development Workflow

### Hot Reload Development
```bash
# Start in dev mode (code changes reflected immediately)
make dev

# In another terminal
make shell
```

### Adding Documents
```bash
# Copy documents to the mounted directory
cp ~/Downloads/report.pdf documents/

# Access from container at /app/documents/report.pdf
```

### Viewing Temporal Workflows
```bash
# Open Web UI
make temporal-ui

# Or use CLI
make temporal-shell
temporal workflow list
```

## Troubleshooting

### Services won't start
```bash
# Check logs
make logs

# Test components independently
make test-components

# Verify Docker resources (needs ~4GB RAM)
docker stats

# Full reset
make reset
```

### Verify installation
```bash
# Test all components
make test-components

# Should see: "All tests passed!"
# See scripts/README_TESTS.md for details
```

### Can't connect to Temporal
```bash
# Check Temporal is running
docker-compose ps

# Check network
docker network ls | grep frfr

# Restart Temporal
docker-compose restart temporal
```

### API key issues
```bash
# Verify .env file exists and has correct key
cat .env | grep ANTHROPIC_API_KEY

# Restart container to pick up changes
docker-compose restart frfr
```

### Permission issues with volumes
```bash
# Fix ownership (Linux/macOS)
sudo chown -R $USER:$USER sessions/

# Or run container as root
docker-compose exec -u root frfr bash
```

## Advanced Usage

### Custom Temporal Configuration
```bash
# Create custom dynamic config
mkdir -p temporal-dynamicconfig
cat > temporal-dynamicconfig/development-sql.yaml <<EOF
frontend.enableClientVersionCheck:
  - value: false
EOF

# Restart Temporal
docker-compose restart temporal
```

### Running Workers
```bash
# Start Temporal worker (when implemented)
make shell
python -m frfr.workflows.worker
```

### Multi-Container Development
```bash
# Run frfr CLI in one container
docker-compose run frfr bash

# Monitor Temporal in another
docker-compose exec temporal-admin-tools bash
temporal workflow list --namespace frfr
```

## Production Considerations

For production deployment:

1. Use proper secrets management (not .env files)
2. Configure Temporal with external PostgreSQL
3. Set up proper logging and monitoring
4. Use multi-stage Dockerfile for smaller images
5. Configure resource limits
6. Set up health checks
7. Use Docker secrets for API keys

Example production override:
```yaml
# docker-compose.prod.yml
services:
  frfr:
    restart: always
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

## Ports

- **8233** - Temporal Web UI
- **7233** - Temporal gRPC (internal)
- **5432** - PostgreSQL (internal)

## Network

All services communicate on the `frfr-network` bridge network. The app connects to Temporal at `temporal:7233`.

## Volumes

- **postgres-data** - Persistent Temporal database
- **./sessions** - Session storage (mounted)
- **./documents** - Document input (mounted)
- **./frfr** - Code (mounted for development)

## Next Steps

1. Start services: `make up`
2. Open shell: `make shell`
3. Place documents in `documents/`
4. Run: `frfr start-session --docs /app/documents/your-file.pdf`
5. Monitor workflows: `make temporal-ui`

For more details, see the main [README.md](README.md).
