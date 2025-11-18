# Conversation Enhancements: Smart Context & Multi-Hop Reasoning

## Overview

This implementation adds intelligent chunk-aware conversation capabilities to frfr, enabling smarter responses with full source context display and multi-hop reasoning across documents.

## What's New

### 1. **ChunkManager** - Intelligent Context Retrieval
Location: `frfr/conversation/chunk_manager.py`

A new system that:
- Loads text chunks from session storage
- Maps facts to their source chunks
- Scores and filters chunks by query relevance
- Highlights evidence text within chunks
- Manages token budgets for chunk context

**Key Features:**
- Smart chunk selection based on fact references and query keywords
- Fuzzy text matching for evidence highlighting
- Token budget management (default: 10,000 tokens for chunks)
- Caching for performance

### 2. **Enhanced Query Interface**
Location: `frfr/tui/screens/query.py`

**Major Changes:**
- Added `ChunkManager` integration
- New context panel showing source excerpts
- Enhanced prompts with full chunk context
- Multi-hop reasoning instructions for Claude

**UI Enhancements:**
- **Conversation Panel** (top): Shows Q&A with fact citations
- **Source Context Panel** (bottom): Displays relevant chunks with:
  - Document name and line numbers
  - Referenced fact IDs
  - Highlighted evidence text (yellow on blue)
  - Metadata for source location

### 3. **Smart Prompt Construction**

**Token Budget Split:**
- Conversation history: 50% of budget (10k tokens default)
- Chunk context: 50% of budget (10k tokens default)
- Total: 20k tokens (with fallback to 10k, 5k, 0k)

**Prompt Structure:**
```
1. Facts Context (numbered list of all facts)
2. Chunk Context (full text excerpts with metadata)
3. Conversation History (previous Q&A pairs)
4. Multi-hop reasoning instructions
5. Current query
```

**Multi-Hop Reasoning Instructions:**
The prompt now explicitly tells Claude to:
- Use chunk context to find connections between facts
- Draw insights from multiple sources
- Include details from chunks not captured in extracted facts
- Cite specific fact numbers

## How It Works

### Query Flow

1. **User submits query** → Stored in query history
2. **Load facts** → All facts from session loaded
3. **Build chunk context** (NEW):
   - Get chunks for facts (based on source_location)
   - Filter by query relevance (keyword matching)
   - Build formatted context with token budget
4. **Build conversation context** → Recent Q&A pairs
5. **Construct prompt** → Facts + Chunks + History + Instructions
6. **Query Claude** → With enhanced context
7. **Display results**:
   - Answer in conversation panel
   - Source chunks in context panel (NEW)
   - Evidence highlighting (NEW)

### Chunk Selection Algorithm

```python
For each fact:
  1. Parse line numbers from source_location
  2. Estimate chunk_id (line_number // 50)
  3. Load chunk file from session/chunks/
  4. Extract evidence quotes (V4 or V5 format)

For each chunk:
  1. Calculate relevance score:
     - Base: fact confidence (50%)
     - Query keywords: keyword overlap (50%)
  2. Deduplicate by chunk_id
  3. Sort by relevance
  4. Apply token budget
  5. Return top N chunks
```

### Evidence Highlighting

**Two Modes:**

1. **Standard Mode** (for query results with multiple chunks):
   - Exact match: Highlight evidence quote with markers
   - Fuzzy match: Highlight entire line containing normalized text
   - Visual markers: `>>> highlighted text <<<`
   - Color: Bold black on yellow background

2. **Focused Mode** (for viewing specific facts):
   - Shows only relevant lines plus 5 lines of context before/after
   - Evidence lines: Bold black on yellow with >>> markers <<<
   - Context lines: Dimmed for easy scanning
   - Multiple evidence sections separated by `...`

**Why These Colors:**
- **Black on Yellow** - Highest contrast, universally accessible
- **Dimmed context** - Reduces visual noise, helps eyes focus on evidence
- **Visual markers** (>>>) - Provides clear left-edge alignment for scanning

## Usage

### Running the TUI

```bash
# Start the TUI
python -m frfr.cli tui

# Or using the CLI alias
frfr tui
```

### Using the Enhanced Query Interface

1. Navigate to an existing session
2. Click "Query Facts" or press the appropriate key
3. Type your question
4. Press `Ctrl+Enter` to submit
5. Observe:
   - **Top panel**: Conversation with Q&A
   - **Bottom panel**: Source context with highlighted evidence

### Keyboard Shortcuts

- `Ctrl+Enter`: Submit query
- `↑/↓`: Navigate query history
- `fact N`: View context for specific fact (e.g., "fact 3")
- `Esc`: Go back
- `q`: Quit
- `?`: Help

### Interactive Fact Viewing

After submitting a query, you can view the source context for any specific fact by typing:

```
fact 3
```

or

```
show fact 15
```

Then press `Ctrl+Enter`. The system will:
1. Display the fact's claim in the conversation panel
2. Find the source chunk containing that fact
3. Show **focused context** - only the relevant lines with surrounding context
4. Show **line numbers** for exact source location
5. Use **bold black on yellow** highlighting for maximum visibility
6. Dim the context lines for easier scanning

**Visual Example:**
```
 507 │ Context line before...                [dimmed]
 508 │ This line contains the key evidence   [HIGHLIGHTED YELLOW]
 509 │ Context line after...                 [dimmed]
```

This is useful when you want to:
- Dive deeper into a specific fact mentioned in an answer
- See more context around a particular claim
- Verify the source of a specific fact
- Quickly spot the exact evidence without reading entire chunks

## Testing

### Unit Tests

```bash
# Test ChunkManager functionality
python test_chunk_manager.py
```

### Integration Tests

```bash
# Test full integration
./venv/bin/python test_integration.py
```

### Expected Results

✓ ChunkManager loads chunks from session
✓ Facts map to correct chunks
✓ Evidence highlighting works
✓ Context panel displays chunks
✓ Token budget management works
✓ Multi-hop reasoning enabled

## Architecture Decisions

### 1. **Token Budget Split (50/50)**
**Rationale**: Balances conversation history with rich source context. Allows for multi-turn conversations while still providing deep context.

### 2. **Keyword-Based Relevance Scoring**
**Rationale**: Simple, fast, and effective for initial implementation. Can be enhanced with embeddings later.

### 3. **Line-Based Chunk Estimation**
**Rationale**: Chunks are created with consistent size (50 lines, 10 overlap). Estimation works well for most cases. Could be enhanced with metadata in future.

### 4. **Separate Context Panel**
**Rationale**: User preference from requirements. Keeps conversation clean while providing easy access to source context.

### 5. **Fuzzy Highlighting**
**Rationale**: Handles OCR artifacts, whitespace variations, and near-matches. More robust than exact matching.

## Performance Characteristics

- **Chunk Loading**: O(1) with caching
- **Chunk Selection**: O(n) where n = number of facts
- **Highlighting**: O(m*c) where m = evidence texts, c = chunk size
- **Token Budget**: Linear scan, stops when budget reached

## Future Enhancements

### Phase 1 (Current) ✅
- ✅ ChunkManager class
- ✅ Context panel UI
- ✅ Evidence highlighting
- ✅ Multi-hop reasoning prompts
- ✅ Token budget management
- ✅ Interactive fact viewing (type "fact N" to see context)

### Phase 2 (Potential)
- [ ] Semantic search with embeddings
- [ ] Clickable fact links in rich text (currently command-based)
- [ ] Export conversation with sources
- [ ] Configurable token budgets in UI
- [ ] Page number mapping (not just lines)
- [ ] PDF preview integration

### Phase 3 (Advanced)
- [ ] Graph-based fact relationships
- [ ] Automatic fact connection discovery
- [ ] Smart context windowing (not just token budget)
- [ ] Multi-document cross-referencing
- [ ] Citation chain visualization

## Technical Details

### File Structure

```
frfr/
├── conversation/
│   ├── __init__.py           # Module exports
│   └── chunk_manager.py      # ChunkManager class
└── tui/
    └── screens/
        └── query.py           # Enhanced QueryScreen

.frfr_sessions/
└── {session_id}/
    ├── chunks/                # Source text chunks
    │   └── {doc}_chunk_{id}.txt
    ├── facts/                 # Extracted facts per chunk
    │   └── {doc}_chunk_{id}.json
    └── metadata.json          # Session metadata
```

### Data Models

**ChunkInfo:**
```python
@dataclass
class ChunkInfo:
    chunk_id: str              # e.g., "chunk_0005"
    document: str              # Document filename
    text: str                  # Full chunk text
    line_start: int            # Starting line number
    line_end: int              # Ending line number
    source_path: Path          # Path to chunk file
```

**ChunkWithEvidence:**
```python
@dataclass
class ChunkWithEvidence:
    chunk_info: ChunkInfo
    evidence_texts: List[str]  # Evidence quotes to highlight
    relevance_score: float     # 0.0-1.0
    fact_ids: List[int]        # Which facts reference this chunk
```

### API

**ChunkManager Methods:**

```python
# Load a specific chunk
load_chunk(document: str, chunk_id: str) -> Optional[ChunkInfo]

# Find chunk containing a fact
find_chunk_for_fact(fact: Dict, document: str) -> Optional[ChunkInfo]

# Get all chunks for facts
get_chunks_for_facts(facts: List[Dict]) -> List[ChunkWithEvidence]

# Filter chunks by query relevance
filter_chunks_by_query(chunks: List[ChunkWithEvidence], query: str, max_chunks: int = 10) -> List[ChunkWithEvidence]

# Highlight evidence in text (NEW: with optional markers)
highlight_evidence_in_text(text: str, evidence_texts: List[str], add_markers: bool = False) -> str

# Get focused context around evidence (NEW)
get_focused_context(text: str, evidence_texts: List[str], context_lines: int = 5) -> str

# Build chunk context for prompt
build_chunk_context(facts: List[Dict], query: str, token_budget: int = 10000) -> Tuple[str, List[ChunkWithEvidence]]
```

**QueryScreen Methods:**

```python
# Show context for a specific fact number (NEW)
show_fact_context(fact_num: int) -> None
```

## Compatibility

- **Python**: 3.8+
- **Dependencies**:
  - textual (TUI framework)
  - rich (text formatting)
- **Session Format**: Compatible with existing .frfr_sessions structure
- **Fact Format**: Supports both V4 (single evidence_quote) and V5 (multiple evidence_quotes)

## Known Limitations

1. **Line Number Estimation**: Chunks use estimated line numbers based on chunk ID. Could be enhanced with metadata.

2. **Token Estimation**: Uses rough approximation (1 token ≈ 4 chars). Could use tiktoken for accuracy.

3. **Keyword Matching**: Simple keyword-based relevance. Could benefit from semantic search.

4. **No Pagination**: Context panel shows all chunks at once. Could add scrolling/pagination for many chunks.

5. **Highlighting Limitations**: Fuzzy matching may miss some evidence if text differs significantly.

## Troubleshooting

### Chunks not displaying
- Verify chunks exist: `ls .frfr_sessions/{session}/chunks/`
- Check session has processed documents
- Ensure facts have source_location field

### Evidence not highlighted
- Check evidence quotes aren't too different from chunk text
- Try exact phrase from chunk
- Verify Rich markup is enabled in RichLog

### Context panel empty
- Verify facts reference actual chunks
- Check token budget isn't too restrictive
- Ensure query has keyword overlap with chunks

### Performance issues
- Reduce token budget (default 10k)
- Limit max_chunks parameter
- Enable chunk caching (already on by default)

## Credits

Implementation based on requirements for:
- Smart conversations with chunk awareness
- Multi-hop reasoning across documents
- Source context display with highlighting
- Metadata preservation for traceability

Integrated with existing frfr architecture:
- Session management
- Fact extraction (V4/V5 formats)
- TUI framework (Textual)
- Conversation history system
