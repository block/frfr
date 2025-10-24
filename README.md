# Frfr

High-confidence document Q&A system using LLM swarm consensus with hallucination detection and correction.

> **Quick Links**: [🚀 Quick Start](QUICKSTART.md) | [Docker Guide](README.docker.md) | [Design Doc](DESIGN.md) | [All Docs](DOCS_INDEX.md)

**Ready to extract your PDF?** See [QUICKSTART.md](QUICKSTART.md) for a 3-command guide.

## Overview

Frfr extracts structured, validated facts from complex documents (SOC2 reports, penetration test reports, design specs) with high precision.

**Current Implementation (V5 - Production Ready):**
1. ✅ PDF text extraction with OCR fallback
2. ✅ LLM-based fact extraction with enhanced metadata (8 fields)
3. ✅ Maximum depth extraction mode
4. ✅ Multiple evidence quotes support (V5)
5. ✅ Real-time validation against source text
6. ✅ Parallel processing with resume capability
7. ✅ Post-processing pipeline (QV tagging, filtering)

**Planned Features (Future Phases):**
- 🔮 Multiple LLM instances with swarm consensus
- 🔮 Semantic comparison and clustering
- 🔮 Contradiction detection and resolution
- 🔮 Judge model synthesis
- 🔮 Interactive Q&A over extracted facts

## Architecture

### Current Implementation (Phase 1: Extraction & Validation) ✅

```
┌─────────────────┐
│   CLI Interface │
│  (Rich Console) │
└────────┬────────┘
         │
         ▼
┌────────────────────────────────────────┐
│      Session Management (Local)        │
│  - Session tracking & resume           │
│  - Progress persistence                │
│  - Artifact storage                    │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│       Document Processing (Active)     │
│  - PDF OCR (ImageMagick + Tesseract)  │
│  - PyPDF2 for text-based PDFs         │
│  - Smart chunking (overlap + resume)  │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│   Enhanced Fact Extraction (V5) ✅     │
│  - Claude Sonnet via CLI               │
│  - Maximum depth extraction            │
│  - Multiple evidence quotes (V5)       │
│  - 8 metadata fields (specificity,     │
│    entities, QV, process details)      │
│  - Parallel processing (5-11 workers)  │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│    Real-Time Validation (Active) ✅    │
│  - Quote verification against source   │
│  - Line number validation              │
│  - Fuzzy matching (70% threshold)      │
│  - Fact recovery for medium confidence │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│   Post-Processing Pipeline (V5) ✅     │
│  - Retroactive QV tagging              │
│  - Quality scoring                     │
│  - Aggressive filtering (35% QV)       │
│  - Consolidated JSON output            │
└────────────────────────────────────────┘
```

### Planned Architecture (Phase 2: Consensus & Q&A) 🔮

Future enhancements will add:
- **Swarm Consensus**: Multiple LLM instances with voting
- **Semantic Clustering**: Group similar facts, detect outliers
- **Contradiction Resolution**: Judge model for conflicting facts
- **Interactive Q&A**: Natural language queries over extracted facts
- **Temporal Workflows**: Distributed orchestration

## Module Structure

```
frfr/
├── frfr/
│   ├── __init__.py
│   ├── cli.py                      # ✅ CLI interface (7 commands)
│   ├── config.py                   # ✅ Configuration management
│   ├── session.py                  # ✅ Session tracking & resume
│   ├── documents/
│   │   ├── __init__.py
│   │   └── pdf_extractor.py       # ✅ PDF OCR + PyPDF2 extraction
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── fact_extractor.py      # ✅ LLM-based extraction (V5)
│   │   ├── schemas.py              # ✅ Enhanced fact schemas (V5)
│   │   ├── claude_client.py        # ✅ Claude CLI wrapper
│   │   ├── extraction_patterns.py  # ✅ V3 regex patterns
│   │   └── v4_enhancements.py      # ✅ V4 filtering logic
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── fact_validator.py      # ✅ Real-time validation (V5)
│   │   └── quote_corrector.py      # ✅ LLM-based quote correction
│   │
│   ├── consensus/                  # 🔮 PLANNED (Phase 2)
│   │   └── __init__.py             # (empty - future swarm consensus)
│   ├── judge/                      # 🔮 PLANNED (Phase 2)
│   │   └── __init__.py             # (empty - future judge model)
│   ├── workflows/                  # 🔮 PLANNED (Phase 2)
│   │   └── __init__.py             # (empty - future Temporal)
│   └── reporting/                  # 🔮 PLANNED (Phase 2)
│       └── __init__.py             # (empty - future reporting)
│
├── scripts/
│   └── ...                         # Helper scripts
├── tests/
│   └── ...                         # Test files
├── pyproject.toml
├── requirements.txt
└── README.md
```

**Legend:**
- ✅ = Implemented and production-ready
- 🔮 = Planned for future phases

## Prerequisites

### Docker Setup (Recommended)
- Docker Desktop or Docker Engine with docker-compose
- Anthropic API key

### Manual Setup
- Python 3.10+
- Claude API access (assumes pre-configured via environment)
- ImageMagick
- Tesseract OCR
- Temporal (dev server script provided)

## Installation

### Docker Setup (Recommended)

The easiest way to get started is with Docker. See [README.docker.md](README.docker.md) for full details.

```bash
# Clone repository
git clone <repo-url>
cd frfr

# Create .env file with your API key
make init
nano .env  # Edit with your ANTHROPIC_API_KEY

# Build and start all services
make build
make up

# Open a shell in the container
make shell

# Inside container: place documents and run
frfr start-session --docs /app/documents/report.pdf
```

**Docker setup includes:**
- Temporal server with Web UI (http://localhost:8233)
- PostgreSQL database
- All system dependencies (ImageMagick, Tesseract)
- Isolated network and persistent storage

### Manual Setup

```bash
# Clone repository
git clone <repo-url>
cd frfr

# Install system dependencies (macOS)
brew install imagemagick tesseract temporal

# Install Python dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```

## Setup

### Docker
All services start automatically with `make up`. See [README.docker.md](README.docker.md).

### Manual
The system requires Temporal for workflow orchestration. A convenience script is provided:

```bash
# Start Temporal dev server (runs in background)
python scripts/start_temporal.py
```

This script will:
- Check if Temporal is already running
- Start a dev server if not running
- Create the `frfr` namespace if it doesn't exist

## PDF Text Extraction API

The primary entrypoint for document processing is the PDF extraction API. It provides a clean Python interface for converting PDFs to text.

### Quick Start: Extract a PDF

From your terminal on the host machine:

```bash
cd ~/Development/frfr

# Extract the SOC2 report (all 155 pages)
./extract-pdf test-doc.pdf soc2_report.txt

# View the output
cat output/soc2_report.txt | head -50
```

That's it! The output appears in `~/Development/frfr/output/` on your host machine.

**For your own PDFs:**

```bash
# Copy your PDF to documents/
cp /path/to/your-file.pdf documents/

# Extract it
./extract-pdf your-file.pdf output.txt
```

### Full Document Extraction

To extract an entire PDF (all pages):

```bash
# From your host terminal
cd ~/Development/frfr
docker compose exec frfr python3 << 'EOF'
from frfr.documents import extract_pdf_to_text

result = extract_pdf_to_text(
    pdf_path='/app/documents/your-file.pdf',
    output_path='/app/output/full_document.txt'
)

print(f"✓ Extracted {result['pages']} pages")
print(f"  Method: {result['method']}")
print(f"  Characters: {result['total_chars']:,}")
EOF

# View the output on your host
cat output/full_document.txt
```

### Python API (Inside Container)

```python
from frfr.documents import extract_pdf_to_text, get_pdf_info

# Get PDF metadata
info = get_pdf_info('/app/documents/your-file.pdf')
print(f"Pages: {info['pages']}")
print(f"Encrypted: {info['is_encrypted']}")

# Extract full PDF to text file
result = extract_pdf_to_text(
    pdf_path='/app/documents/your-file.pdf',
    output_path='/app/output/extracted_text.txt'
)

print(f"Method: {result['method']}")      # 'pypdf2' (fast, clean)
print(f"Pages: {result['pages']}")         # 155
print(f"Characters: {result['total_chars']:,}")  # 476,143
```

### Example Script

Run the included example to test extraction:

```bash
# From host terminal
docker compose exec frfr python3 /app/scripts/example_pdf_extraction.py

# Output appears in ~/Development/frfr/output/example_extraction.txt
```

### Extraction Strategy

The system automatically chooses the best method:

1. **PyPDF2 (default)**: For text-based PDFs
   - Fast, clean extraction
   - Handles encrypted PDFs (with pycryptodome)
   - Preserves formatting
   - Zero OCR artifacts

2. **OCR (fallback)**: For scanned/image PDFs
   - Tesseract with LSTM neural network
   - 400 DPI quality
   - Smart artifact cleaning

### API Reference

**`extract_pdf_to_text(pdf_path, output_path)`**

Extract text from entire PDF and save to file.

Returns:
```python
{
    "method": "pypdf2",
    "pages": 155,
    "total_chars": 476143,
    "output_file": "/path/to/output.txt"
}
```

**`extract_pdf_page_to_text(pdf_path, page_num)`**

Extract text from a single page (0-indexed).

Returns: `tuple[str, str]` - (text, method)

**`get_pdf_info(pdf_path)`**

Get PDF metadata.

Returns:
```python
{
    "pages": 155,
    "is_encrypted": True,
    "file_size": 1858673
}
```

## Usage

### Current Workflow (V5 Production)

```bash
# 1. Extract PDF to text
frfr extract documents/soc2_report.pdf output/soc2_text.txt

# 2. Extract facts with V5 features
frfr extract-facts output/soc2_text.txt \
  --document-name my_soc2 \
  --chunk-size 500 \
  --overlap 100 \
  --max-workers 11

# Output:
# ✅ Session: sess_abc123
# ✅ Processing chunks... [170/170] (28 minutes)
# ✅ Extracted 2,487 facts
# ✅ Consolidated: output/my_soc2_facts.json

# 3. Validate facts against source
frfr validate-facts output/my_soc2_facts.json output/soc2_text.txt

# Output:
# ✅ Total: 2,487 facts
# ✅ Valid: 2,487 (100%)
# ✅ Validation rate: 100%

# 4. Check session progress (for resume)
frfr session-info sess_abc123

# 5. Resume if interrupted
frfr extract-facts output/soc2_text.txt \
  --document-name my_soc2 \
  --session-id sess_abc123 \
  --start-chunk 85
```

### Interactive Q&A (Future Phase 2) 🔮

```bash
# Planned future capability:
frfr query sess_abc123 --interactive

> does the system implement 2-factor authentication?

[Querying 2,487 extracted facts...]
[Finding relevant facts with semantic search...]

Answer: Yes, 2FA implemented with SMS and TOTP.
Supporting Facts: 3 facts found (lines 1245, 1389, 2103)
Confidence: High (multiple sources)

> exit
```

### CLI Options

```bash
# Extract facts with parallel processing
frfr extract-facts text.txt \
  --document-name doc_name \
  --max-workers 11            # Parallel Claude processes (default: 5)
  --chunk-size 500            # Lines per chunk (default: 1000)
  --overlap 100               # Overlap between chunks (default: 200)

# Enable multi-pass extraction (CUECs, tests, quantitative, technical)
frfr extract-facts text.txt \
  --document-name doc_name \
  --multipass

# Resume interrupted extraction
frfr extract-facts text.txt \
  --document-name doc_name \
  --session-id sess_abc123 \
  --start-chunk 85

# Validate with custom output
frfr validate-facts facts.json text.txt \
  --show-invalid-only \
  --output validation_report.json
```

## Fact Schema

Extracted facts follow this structure:

```json
{
  "claim": "System implements 2FA via SMS and TOTP",
  "source_doc": "soc2_report.pdf",
  "source_location": "Page 42, Section 4.2.1",
  "evidence_quote": "Multi-factor authentication is enforced for all user accounts, supporting both SMS-based codes and TOTP authenticator applications.",
  "confidence": 0.92
}
```

## Report Format

Generated reports include:

1. **Executive Summary**: Direct answer to question
2. **Confidence Score**: Overall confidence (0-100%)
3. **Supporting Facts**: All consensus facts with citations
4. **Methodology**: Swarm size, consensus reached, outliers discarded
5. **Appendix**:
   - Corrected hallucinations (facts that didn't reach consensus)
   - Resolved contradictions (conflicting facts and judge's resolution)
   - Low-confidence facts (flagged but not included)

## How It Works (Current Implementation)

### 1. Document Processing ✅
- PDFs converted via PyPDF2 (fast, clean) or OCR fallback (Tesseract)
- Encrypted PDFs handled automatically (pycryptodome)
- Documents chunked with sliding window (configurable size + overlap)
- Smart resume capability for interrupted extractions

### 2. Enhanced Fact Extraction (V5) ✅
- Claude Sonnet via CLI (headless mode)
- Maximum depth extraction (5-10 facts per paragraph)
- Enhanced schema with 8 metadata fields:
  - `fact_type`, `control_family`, `specificity_score`
  - `entities`, `quantitative_values`, `process_details`
  - `section_context`, `related_control_ids`
- **V5 Feature**: Multiple evidence quotes per fact
- Parallel processing (5-11 workers)
- Section-aware prompting (Control Testing, System Description, CUEC)

### 3. Real-Time Validation ✅
- Every fact validated against source text immediately
- Line-number-based quote verification
- Fuzzy matching (70% threshold) for OCR artifacts
- Fact recovery for medium-confidence matches (40-79%)
- 100% validation rate achieved in production

### 4. Post-Processing Pipeline ✅
- Retroactive QV tagging (scans claims for missed quantitative values)
- Quality scoring (specificity + entities + process details)
- Aggressive filtering to achieve target QV coverage (35%)
- Consolidated JSON output with session metadata

### 5. Future: Consensus & Q&A 🔮
- **Planned**: Swarm extraction with multiple instances
- **Planned**: Semantic clustering and consensus voting
- **Planned**: Contradiction detection and judge resolution
- **Planned**: Interactive Q&A over extracted facts

## Development Status

**Current Phase**: ✅ **Phase 1 Complete - Production Ready**

### Implemented Features (V5)
- ✅ PDF text extraction (PyPDF2 + OCR fallback)
- ✅ Enhanced fact extraction with 8 metadata fields
- ✅ Maximum depth extraction mode
- ✅ Multiple evidence quotes support (V5)
- ✅ Real-time validation (100% rate achieved)
- ✅ Parallel processing (5-11 workers)
- ✅ Session management with resume capability
- ✅ Post-processing pipeline (QV tagging, filtering)
- ✅ Comprehensive CLI (7 commands)

### Production Metrics (V5)
- **1,011 validated facts** from 155-page SOC2 report
- **35.0% quantitative value coverage** (target achieved)
- **0.878 average specificity** (high quality)
- **28 minutes** extraction time (170 chunks, 11 workers)
- **100% validation rate** (all facts verified against source)

### Planned Features (Phase 2)
- 🔮 Multi-instance swarm extraction with consensus voting
- 🔮 Semantic clustering and outlier detection
- 🔮 Contradiction detection and judge resolution
- 🔮 Interactive Q&A over extracted facts
- 🔮 Temporal workflow orchestration
- 🔮 Web UI wrapper around CLI

## Contributing

This project is open source. Contributions welcome for:
- Additional document format support
- Improved consensus algorithms
- Better chunking strategies
- UI/UX enhancements

## License

TBD

## Use Cases

- **Security Audits**: "Does this pentest report identify any critical vulnerabilities?"
- **Compliance**: "Does this SOC2 report implement the controls in this reference spec?"
- **Design Review**: "Does this architecture doc address the scaling requirements from this spec?"
- **Governance**: "What data retention policies are described in this document?"

The system is designed for high-stakes questions where accuracy matters more than speed.
