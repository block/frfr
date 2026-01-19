# Quick Start: Process and Query Your Documents

Process PDFs and query them interactively using the web interface.

## Prerequisites

- Go 1.21+
- Node.js 18+
- Python 3.10+
- Claude API access (via `ANTHROPIC_API_KEY` or `claude` CLI authentication)

## Start the Application

```bash
# Start the backend and frontend
./run.sh

# Open in browser
open http://localhost:3000
```

## Process a Document

1. **Create a session** - Click "New Session" on the home page
2. **Add a document** - Click "Add Document" and enter the path to your PDF
   - Supports `~/Downloads/file.pdf` paths
3. **Start processing** - Click "Process" to begin extraction
4. **Watch progress** - See real-time chunk progress as facts are extracted

## Query Your Facts

1. Navigate to your session
2. Click **Query** in the header
3. Ask natural language questions:
   - "Does the system implement 2-factor authentication?"
   - "What are the data retention policies?"
   - "What security controls are described?"
4. View answers with clickable source citations
5. Click citations to see the source context with highlighted quotes

## Browse Facts

1. Navigate to your session
2. Click **Browse Facts** in the header
3. Search and filter through extracted facts
4. Click any fact to see its source context

## What You Get

- **PDF extraction** - Handles text-based and scanned PDFs
- **Structured facts** - 8 metadata fields per fact
- **Source verification** - Every fact linked to source text
- **Parallel processing** - Fast extraction with progress visualization
- **Natural language Q&A** - Query your facts conversationally

## Session Structure

Each session stores:

```
sessions/{session_id}/
├── metadata.json      # Session metadata & document registry
├── text/              # Extracted PDF text
├── chunks/            # Source text chunks (for context panel)
├── facts/             # Extracted facts per chunk
└── summaries/         # Document summaries
```

## Troubleshooting

**Issue:** Document shows "PDF not found"
**Solution:** Use absolute paths or `~/` for home directory

**Issue:** No API key found
**Solution:** Set `ANTHROPIC_API_KEY` or run `claude login`

**Issue:** Processing seems stuck
**Solution:** Check the backend logs in the terminal running `./run.sh`

## API Usage

You can also interact with the API directly:

```bash
# List sessions
curl http://localhost:8080/api/sessions

# Create session
curl -X POST http://localhost:8080/api/sessions

# Add document
curl -X POST http://localhost:8080/api/sessions/{id}/documents \
  -H "Content-Type: application/json" \
  -d '{"path": "~/Downloads/report.pdf"}'

# Start processing
curl -X POST http://localhost:8080/api/sessions/{id}/process

# Query facts
curl -X POST http://localhost:8080/api/sessions/{id}/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What security controls are implemented?"}'
```
