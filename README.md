# Frfr

High-confidence document Q&A system using LLM fact extraction with source verification.

> **Quick Links**: [Design Doc](docs/DESIGN.md) | [All Docs](docs/DOCS_INDEX.md)

## Quick Start

```bash
# Start the application
./run.sh

# Open in browser
open http://localhost:3000
```

The web UI provides:
- **Session Browser**: View and manage all sessions with document counts and fact statistics
- **Document Processing**: Upload PDFs and extract facts with real-time progress visualization
- **Facts Browser**: Filter and search through extracted facts
- **Query Interface**: Ask natural language questions with parallel batch processing and source citations

## Architecture

Frfr uses a Go backend with a React frontend:

```
┌─────────────────────────────────────────┐
│         Web Interface (React)           │
│  - Session management                   │
│  - Document upload & processing         │
│  - Facts browser with search            │
│  - Query UI with source context panel   │
└────────────────┬────────────────────────┘
                 │ REST API + SSE
                 ▼
┌─────────────────────────────────────────┐
│         Go Backend Server               │
│  - Session & document management        │
│  - PDF text extraction (pdfium/wasm)    │
│  - Claude API integration               │
│  - Parallel fact extraction             │
│  - Query processing with citations      │
└─────────────────────────────────────────┘
```

## Features

### Document Processing
- PDF text extraction via go-pdfium (WebAssembly, no external dependencies)
- Adaptive chunking with semantic boundaries
- Parallel fact extraction (up to 20 concurrent workers)
- Real-time progress visualization with chunk grid
- Automatic session management

### Fact Extraction
- Claude-powered extraction with structured output
- 8 metadata fields per fact (type, control family, entities, etc.)
- Multiple evidence quotes per fact
- Specificity scoring and quality filtering

### Query System
- Natural language questions over extracted facts
- Parallel batch processing (150 facts per batch)
- Live progress streaming via SSE
- Clickable source citations
- Source context panel with quote highlighting

## Project Structure

```
frfr/
├── backend/                    # Go backend server
│   ├── cmd/server/            # Server entrypoint
│   └── internal/
│       ├── api/               # REST API handlers
│       ├── config/            # Configuration
│       ├── domain/models/     # Data models
│       └── services/          # Business logic
│           ├── claude/        # Claude API client
│           ├── extraction/    # Fact extraction
│           ├── pdf/           # PDF extraction (pdfium)
│           ├── query/         # Query processing
│           ├── session/       # Session management
│           └── validation/    # Fact validation
├── frontend/                   # React + TypeScript frontend
│   └── src/
│       ├── api/               # API client
│       ├── components/        # React components
│       └── pages/             # Page components
├── electron/                   # Electron desktop app
│   ├── main/                  # Main process (backend lifecycle, IPC)
│   ├── preload/               # Secure IPC bridge
│   └── resources/             # Build resources
├── scripts/                    # Build scripts
│   ├── dev-electron.sh        # Development mode
│   └── build-electron.sh      # Production build
├── run.sh                      # Start web app
└── docs/                       # Documentation
```

## Prerequisites

- Go 1.21+
- Node.js 18+
- Claude API access (via `ANTHROPIC_API_KEY` or `claude` CLI authentication)

## Installation

```bash
# Clone repository
git clone <repo-url>
cd frfr

# Start everything (installs dependencies automatically)
./run.sh
```

The `run.sh` script will:
1. Check dependencies (Go, Node)
2. Install frontend dependencies
3. Build and start the Go backend
4. Start the frontend dev server

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `FRFR_PORT` | `8080` | Backend server port |
| `FRFR_DATA_DIR` | `~/Documents/frfr/sessions` | Session storage directory |
| `FRFR_MAX_WORKERS` | `20` | Max parallel extraction workers |
| `ANTHROPIC_API_KEY` | - | Claude API key (optional if using CLI auth) |

## Session Structure

Each session stores:

```
sessions/{session_id}/
├── metadata.json      # Session metadata & document registry
├── text/              # Extracted PDF text
│   └── {doc}.txt
├── chunks/            # Source text chunks (for context panel)
│   └── {doc}_chunk_{id}.txt
├── facts/             # Extracted facts per chunk
│   └── {doc}_chunk_{id}.json
└── summaries/         # Document summaries
    └── {doc}.json
```

## API Endpoints

### Sessions
- `GET /api/sessions` - List all sessions
- `POST /api/sessions` - Create new session
- `GET /api/sessions/{id}` - Get session details
- `DELETE /api/sessions/{id}` - Delete session

### Documents
- `GET /api/sessions/{id}/documents` - List documents
- `POST /api/sessions/{id}/documents` - Add document
- `POST /api/sessions/{id}/documents/{doc}/reprocess` - Reprocess document

### Processing
- `POST /api/sessions/{id}/process` - Start processing
- `GET /api/sessions/{id}/process/events` - SSE event stream

### Facts
- `GET /api/sessions/{id}/facts` - List facts (paginated)
- `GET /api/sessions/{id}/facts/{index}/context` - Get fact with source context

### Query
- `POST /api/sessions/{id}/query` - Query facts
- `GET /api/sessions/{id}/query/stream` - SSE query stream with batch progress

## Development

```bash
# Backend only
cd backend && go run ./cmd/server

# Frontend only (with backend running)
cd frontend && npm run dev

# Build frontend for production
cd frontend && npm run build
```

## Desktop App (Electron)

Build frfr as a standalone macOS application.

### Development Mode

```bash
./scripts/dev-electron.sh
```

This starts the Go backend, Vite dev server, and Electron with hot reload.

### Production Build

```bash
# Build for current architecture (arm64 on Apple Silicon, x64 on Intel)
./scripts/build-electron.sh

# Build for specific architecture
./scripts/build-electron.sh --arch arm64   # Apple Silicon
./scripts/build-electron.sh --arch x64     # Intel
```

Output in `electron/release/`:
- `frfr-1.0.0-arm64.dmg` - Apple Silicon installer
- `frfr-1.0.0.dmg` - Intel installer
- `mac-arm64/frfr.app` - Apple Silicon app bundle
- `mac/frfr.app` - Intel app bundle

### Prerequisites

- Node.js 18+
- Go 1.21+

The build script handles:
1. Compiling Go backend for target architecture
2. Building React frontend with Vite
3. Compiling Electron TypeScript
4. Packaging with electron-builder

### Note on Code Signing

The app is not code-signed by default. On first launch, right-click → Open to bypass Gatekeeper.

## Use Cases

- **Security Audits**: "Does this pentest report identify any critical vulnerabilities?"
- **Compliance**: "Does this SOC2 report implement the controls in this reference spec?"
- **Design Review**: "Does this architecture doc address the scaling requirements?"
- **Governance**: "What data retention policies are described in this document?"

The system is designed for high-stakes questions where accuracy matters more than speed.

## License

TBD
