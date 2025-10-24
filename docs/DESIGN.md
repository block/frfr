# Frfr Design Document

## Problem

LLMs can miss details or introduce inaccuracies when analyzing complex compliance documents. High-stakes use cases (security audits, compliance verification, technical design review) require exhaustive, validated fact extraction.

## Solution

### Current Implementation (Phase 1) ✅

Extract structured facts from documents using:
1. **Maximum depth extraction** - Extract 5-10 facts per paragraph with enhanced metadata
2. **Real-time validation** - Verify every fact against source text immediately
3. **Multiple evidence quotes** - Support facts synthesized from multiple locations (V5)
4. **Quality post-processing** - Filter and score facts for optimal quality/density

### Future Vision (Phase 2) 🔮

Add consensus layer:
1. Run multiple LLM instances in parallel with different random seeds
2. Use non-LLM semantic comparison to identify consensus
3. Discard outliers and resolve contradictions with judge model
4. Result: high-confidence answers with exact citations

## Architecture

### Current Implementation (Phase 1) ✅

```
Documents (PDF/Markdown)
    ↓
PyPDF2/OCR → Chunk (sliding window + resume)
    ↓
Enhanced Extract (Claude Sonnet via CLI)
  - Maximum depth (5-10 facts/paragraph)
  - 8 metadata fields
  - Multiple evidence quotes (V5)
  - Section-aware prompting
  - Parallel workers (5-11)
    ↓
Real-Time Validation
  - Quote verification
  - Line number validation
  - Fuzzy matching (70%)
  - Fact recovery (40-79%)
    ↓
Post-Processing Pipeline
  - Retroactive QV tagging
  - Quality scoring
  - Aggressive filtering (35% QV target)
    ↓
Structured Facts (JSON) → Validated 100%
```

### Future Architecture (Phase 2) 🔮

```
Validated Facts (from Phase 1)
    ↓
Embed Facts (sentence transformers)
    ↓
Cluster by Semantic Similarity
    ↓
Swarm Extraction (N instances, different seeds)
    ↓
Detect Consensus (plurality threshold)
    ↓
Detect Contradictions
    ↓
Judge Resolution (Claude Opus) ← only for contradictions
    ↓
Interactive Q&A + Report Generation
```

## Core Components

### Current Implementation (Phase 1) ✅

#### 1. Document Processing
- **Input**: PDFs via PyPDF2 (fast) or Tesseract OCR (fallback)
- **Encrypted PDFs**: Handled automatically (pycryptodome)
- **Chunking**: Configurable (default: 500 lines, 100 overlap)
- **Resume**: Smart session tracking for interrupted extractions
- **Target**: SOC2 reports (50-150 pages), pentest reports (20-100 pages)

#### 2. Enhanced Fact Extraction (V5)
- **Model**: Claude Sonnet via CLI (headless mode)
- **Extraction Mode**: Maximum depth (5-10 facts per paragraph)
- **Schema**: Enhanced with 8 metadata fields
  - `fact_type`, `control_family`, `specificity_score`
  - `entities`, `quantitative_values`, `process_details`
  - `section_context`, `related_control_ids`
- **V5 Feature**: Multiple evidence quotes per fact
- **Parallel Processing**: 5-11 workers (ThreadPoolExecutor)
- **Output**: Structured facts (JSON schema)

#### 3. Enhanced Fact Schema (V5)
```json
{
  "claim": "specific assertion",
  "source_doc": "filename.pdf",
  "source_location": "Lines 42-45",
  "evidence_quotes": [                    // V5: Multiple quotes
    {
      "quote": "exact text from source",
      "source_location": "Lines 42-45",
      "relevance": "why this supports claim"
    }
  ],
  "confidence": 0.95,
  // Enhanced metadata (8 fields)
  "fact_type": "technical_control",
  "control_family": "access_control",
  "specificity_score": 0.85,
  "entities": ["AWS", "TLS 1.2"],
  "quantitative_values": ["daily", "90 days"],
  "process_details": {"who": "IT team", "when": "quarterly", "how": "automated"},
  "section_context": "Control Testing",
  "related_control_ids": ["CC6.1"]
}
```

#### 4. Real-Time Validation
- **Quote Verification**: Check every quote exists in source text
- **Line Number Validation**: Verify quotes in specified ranges
- **Fuzzy Matching**: 70% threshold for OCR artifacts
- **Fact Recovery**: LLM-assisted recovery for 40-79% matches
- **Philosophy**: 100% validation rate before saving

#### 5. Post-Processing Pipeline
- **Retroactive QV Tagging**: Scan claims for missed quantitative values
- **Quality Scoring**: Specificity + entities + process details
- **Aggressive Filtering**: Achieve target QV coverage (35%)
- **Output**: High-quality, high-density fact set

#### 6. Session Management
- **Storage**: Local session directories
- **Resume**: Track processed chunks, resume from interruption
- **Progress**: Real-time progress tracking
- **Consolidation**: Auto-consolidate facts per session

### Future Components (Phase 2) 🔮

#### Consensus Detection (Planned)
- **Embedding**: Sentence transformers (local, fast, no API costs)
- **Clustering**: Cosine similarity (threshold: 0.85)
- **Plurality**: Configurable threshold (default: 0.8 or "all but one")
- **Outliers**: Facts below threshold are discarded as errors
- **Philosophy**: Precision over recall

#### Contradiction Handling (Planned)
- **Detection**: Semantically similar facts with conflicting claims
- **Resolution**: Judge model (Claude Opus) examines source docs
- **Output**: Resolved fact + reasoning documented in report appendix

#### Judge Synthesis (Planned)
- **Model**: Claude Opus or latest Sonnet (highest quality)
- **Input**: Consensus facts + resolved contradictions
- **Output**: Final answer with confidence score and citations

#### Interactive Q&A (Planned)
- **Query**: Natural language questions over extracted facts
- **Search**: Semantic search for relevant facts
- **Synthesis**: Generate answers with citations

## Data Flow Example

**User Question**: "Does the system implement 2FA?"

**Swarm Extraction** (5 instances):
- Instance 1: Extracts 3 facts about 2FA
- Instance 2: Extracts 3 facts (2 match Instance 1)
- Instance 3: Extracts 2 facts (both match previous)
- Instance 4: Extracts 4 facts (3 match, 1 is hallucination)
- Instance 5: Extracts 3 facts (all match consensus)

**Consensus**:
- Cluster 1: "System uses 2FA" (5/5 instances) → Consensus ✓
- Cluster 2: "2FA via SMS and TOTP" (4/5 instances) → Consensus ✓
- Cluster 3: "Hardware tokens required" (1/5 instances) → Outlier ✗

**Judge Synthesis**:
- Combines consensus facts
- Confidence: 95% (strong consensus)
- Answer: "Yes, 2FA is implemented via SMS and TOTP"

**Report**:
- Direct answer with confidence
- Supporting facts with exact page/section citations
- Appendix: 1 hallucination corrected (hardware tokens)

## Key Design Decisions

### Non-LLM Consensus
Using embeddings instead of LLM-based comparison:
- **Fast**: Local computation, no API latency
- **Cheap**: No API costs for comparison
- **Deterministic**: Reproducible clustering
- Judge LLM only invoked for contradictions

### High Confidence Default
- Low-occurrence facts (1-2 instances) are assumed errors
- Saves human time by not flagging low-confidence findings
- Trade-off: May miss rare but true facts

### Exact Citations
- All facts must link to exact text in source
- No paraphrasing in evidence quotes
- Enables verification and trust

### Temporal Orchestration
- Session state persists across workflow steps
- Parallel swarm execution with retries
- Future: Resume sessions across CLI invocations

## Configuration

CLI flags:
- `--swarm-size`: Number of LLM instances (default: 5)
- `--consensus-threshold`: Plurality threshold (default: 0.8)
- `--similarity-threshold`: Semantic clustering (default: 0.85)
- `--swarm-model`: Model for swarm (default: claude-sonnet-4)
- `--judge-model`: Model for judge (default: claude-opus-4)

## Interface

```bash
$ frfr start-session --docs report.pdf spec.md

Loading documents...
Session started: sess_abc123

> does the system implement 2FA?

[Processing with 5 instances...]

Answer: Yes, 2FA is implemented via SMS and TOTP.
Confidence: 95%

Type 'report' to view full details.

> report

# Full markdown report displayed #

> what TOTP apps are supported?

[Querying extracted facts...]

Answer: Google Authenticator and Authy.
Confidence: 88%

> exit

Session ended.
```

## Output Format

Markdown report:
1. **Executive Summary**: Direct answer
2. **Confidence Score**: 0-100%
3. **Supporting Facts**: All consensus facts with citations
4. **Methodology**: Swarm size, consensus stats, outliers
5. **Appendix**:
   - Corrected hallucinations
   - Resolved contradictions
   - Low-confidence facts (informational)

## Implementation

**Language**: Python 3.10+

**Dependencies**:
- `anthropic`: Claude API
- `temporalio`: Workflow orchestration
- `sentence-transformers`: Embeddings
- `pypdf2`, `pytesseract`: Document processing
- `click`, `rich`: CLI

**Module Structure**:
```
frfr/
├── documents/      # Parsing, chunking, storage
├── extraction/     # LLM fact extraction, swarm coordination
├── consensus/      # Embeddings, clustering, comparison
├── judge/          # Contradiction resolution, synthesis
├── workflows/      # Temporal workflows and activities
├── reporting/      # Markdown generation, formatting
└── cli.py          # Interactive CLI
```

## Use Cases

- **Security Audits**: "Does this pentest report identify critical vulnerabilities?"
- **Compliance**: "Does this SOC2 report implement controls in reference spec?"
- **Design Review**: "Does this architecture doc address scaling requirements?"
- **Governance**: "What data retention policies are described?"

## Limitations

- **Speed**: Multiple LLM calls are slower than single instance
- **Cost**: N instances = N × API cost (mitigated by smaller swarm model)
- **Rare Facts**: Low-occurrence truths may be discarded as outliers
- **Context Windows**: Very large documents require chunking

## Future Enhancements

- Multi-model swarm (different models for diversity)
- Dynamic prompt generation (meta-LLM creates variations)
- Session persistence across CLI invocations
- Incremental fact extraction for multi-document sessions
- Web UI wrapper
- Advanced comparison modes (compliance checking, feature verification)

## Philosophy

**Precision over recall**: Better to say "I don't know" than hallucinate.

**Transparency**: Show all work in appendix.

**Exact citations**: Never paraphrase evidence.

**Observability**: Temporal provides full execution history.

---

## Implementation Status

**Phase 1 (Extraction & Validation)**: ✅ **COMPLETE - Production Ready**
- Document processing: ✅ Complete (PyPDF2 + OCR)
- Enhanced extraction: ✅ Complete (V5 with 8 metadata fields)
- Real-time validation: ✅ Complete (100% rate achieved)
- Post-processing: ✅ Complete (QV tagging + filtering)
- CLI: ✅ Complete (7 commands)
- Session management: ✅ Complete (resume capability)

**Phase 2 (Consensus & Q&A)**: 🔮 **Planned**
- Swarm consensus: 🔮 Planned
- Semantic clustering: 🔮 Planned
- Contradiction resolution: 🔮 Planned
- Interactive Q&A: 🔮 Planned
- Temporal workflows: 🔮 Planned

**Production Metrics (V5)**:
- 1,011 validated facts from 155-page SOC2 report
- 35.0% quantitative value coverage (target achieved)
- 0.878 average specificity (high quality)
- 28 minutes extraction time (170 chunks, 11 workers)
- 100% validation rate

**License**: TBD (intended for open source release)
