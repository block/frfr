# frfr

High-confidence document Q&A using LLM fact extraction with source verification.

## Stack

- **Backend**: Go (REST API + SSE)
- **Frontend**: React + TypeScript + Vite
- **Desktop**: Electron (macOS)
- **PDF extraction**: go-pdfium (WebAssembly, no Python)
- **LLM**: Claude API

## Quick Start

```bash
./run.sh              # Start backend + frontend (web)
open http://localhost:3000

# Or build desktop app
./scripts/build-electron.sh --arch arm64
open electron/release/mac-arm64/frfr.app
```

## Structure

```
backend/
  cmd/server/         # Entrypoint
  internal/
    api/handlers/     # REST endpoints
    services/
      pdf/            # PDF text extraction (pdfium)
      extraction/     # Fact extraction
      query/          # Query processing
      claude/         # Claude API client
frontend/
  src/components/     # React components
electron/
  main/               # Main process (backend lifecycle, IPC)
  preload/            # Secure IPC bridge
scripts/
  dev-electron.sh     # Electron dev mode
  build-electron.sh   # Electron production build
docs/                 # Design docs
```

## Key Files

- `backend/internal/services/pdf/extractor.go` - PDF text extraction
- `backend/internal/api/handlers/processing.go` - Document processing endpoints
- `backend/internal/services/query/query.go` - Query with citations
- `frontend/src/components/query/QueryInterface.tsx` - Query UI

## Current Work

See [TODO.md](TODO.md) for active tasks and roadmap.

## Docs

- [docs/DESIGN.md](docs/DESIGN.md) - Architecture and design
- [docs/QUICKSTART.md](docs/QUICKSTART.md) - Getting started guide
- [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md) - All documentation
