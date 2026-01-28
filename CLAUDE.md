# frfr

High-confidence document Q&A using LLM fact extraction with source verification.

## Stack

- **Backend**: Go (REST API + SSE)
- **Frontend**: React + TypeScript + Vite
- **PDF extraction**: go-pdfium (WebAssembly, no Python)
- **LLM**: Claude API

## Quick Start

```bash
./run.sh              # Start backend + frontend
open http://localhost:3000
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
