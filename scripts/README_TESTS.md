# Docker Component Test Suite

Comprehensive test suite to verify all Docker components and dependencies are working correctly.

## Overview

The test suite validates:
1. **System Dependencies** - ImageMagick, Tesseract OCR, Git
2. **Python Environment** - Python 3.10+, core packages
3. **Document Processing** - PDF parsing, OCR, file detection
4. **ML Components** - Sentence transformers, embeddings, clustering
5. **Temporal Integration** - Workflow engine connectivity
6. **CLI Components** - Interactive terminal tools

## Quick Start

```bash
# From host machine, with Docker running
make up                  # Start services
make test-components     # Run all tests

# Or manually inside container
make shell
bash /app/scripts/test_components.sh
```

## Test Structure

```
scripts/
├── test_components.sh           # Parent orchestrator
├── test_system_deps.sh          # System dependencies
├── test_python_env.sh           # Python environment
├── test_document_processing.sh  # Document tools
├── test_ml_components.sh        # ML/embeddings
├── test_temporal.sh             # Temporal integration
└── test_cli_components.sh       # CLI framework
```

## Individual Test Scripts

### 1. System Dependencies (`test_system_deps.sh`)

Tests system-level tools installed via apt-get.

**Tests:**
- ✓ ImageMagick installation and version
- ✓ ImageMagick image creation
- ✓ Tesseract installation and version
- ✓ Tesseract English language data
- ✓ Tesseract OCR functionality
- ✓ Git installation and version

**Success Criteria:**
- All commands available in PATH
- Can create and process images
- Can perform OCR on test image
- English language pack present

**Run individually:**
```bash
bash scripts/test_system_deps.sh
```

### 2. Python Environment (`test_python_env.sh`)

Tests Python version and core packages.

**Tests:**
- ✓ Python version >= 3.10
- ✓ anthropic package installed
- ✓ temporalio package installed
- ✓ pydantic package installed
- ✓ Pydantic model creation
- ✓ Environment variables (PYTHONUNBUFFERED, TEMPORAL_ADDRESS)

**Success Criteria:**
- Python 3.10+ present
- All core packages importable
- Pydantic models can be created and validated
- Environment configured

**Run individually:**
```bash
bash scripts/test_python_env.sh
```

### 3. Document Processing (`test_document_processing.sh`)

Tests document parsing and OCR libraries.

**Tests:**
- ✓ PyPDF2 installation
- ✓ PDF reading capability
- ✓ pytesseract installation
- ✓ pytesseract-Tesseract integration
- ✓ python-magic installation
- ✓ File type detection
- ✓ markdown library
- ✓ Markdown parsing

**Success Criteria:**
- Can read PDF files
- Can perform OCR via Python
- Can detect file MIME types
- Can parse markdown to HTML

**Run individually:**
```bash
bash scripts/test_document_processing.sh
```

### 4. ML Components (`test_ml_components.sh`)

Tests machine learning libraries for consensus layer.

**Tests:**
- ✓ numpy installation and operations
- ✓ scikit-learn installation
- ✓ KMeans clustering
- ✓ Cosine similarity calculation
- ✓ sentence-transformers installation
- ✓ Model loading (all-MiniLM-L6-v2)
- ✓ Embedding generation
- ✓ Semantic similarity

**Success Criteria:**
- Numpy arrays and operations work
- Clustering algorithms functional
- Sentence transformer model loads (may download on first run)
- Embeddings have correct dimensions (384 for MiniLM-L6)
- Similar sentences have higher similarity scores

**Run individually:**
```bash
bash scripts/test_ml_components.sh
```

**Note:** First run will download the sentence-transformers model (~90MB), which may take 1-2 minutes.

### 5. Temporal Integration (`test_temporal.sh`)

Tests Temporal workflow engine integration.

**Tests:**
- ✓ temporalio package
- ✓ Temporal client creation
- ✓ Workflow decorator
- ✓ Activity decorator
- ✓ TEMPORAL_ADDRESS environment
- ✓ Server connection (if running)
- ✓ Namespace accessibility

**Success Criteria:**
- Temporal client can be instantiated
- Decorators work correctly
- Can connect to Temporal server (warns if not running)
- Namespace "frfr" is accessible

**Run individually:**
```bash
bash scripts/test_temporal.sh
```

**Note:** Connection tests require Temporal server running (`make up`).

### 6. CLI Components (`test_cli_components.sh`)

Tests CLI framework and interactive tools.

**Tests:**
- ✓ click installation and commands
- ✓ rich installation
- ✓ Rich console output
- ✓ Rich tables
- ✓ Rich progress bars
- ✓ prompt-toolkit installation
- ✓ Prompt session components
- ✓ python-dotenv installation
- ✓ .env file loading
- ✓ aiofiles installation
- ✓ Async file operations

**Success Criteria:**
- Click commands can be created
- Rich console can format output
- Tables and progress bars render
- Prompt toolkit can create interactive sessions
- Environment files can be loaded
- Async file I/O works

**Run individually:**
```bash
bash scripts/test_cli_components.sh
```

## Parent Orchestrator (`test_components.sh`)

Runs all test scripts in sequence and provides a summary.

**Features:**
- Color-coded output (green = pass, red = fail, yellow = running)
- Tracks pass/fail counts
- Lists all failed tests at end
- Exits with error code if any test fails

**Output Format:**
```
========================================
Frfr Docker Component Test Suite
========================================

Running: System Dependencies
✓ PASS: System Dependencies

Running: Python Environment
✓ PASS: Python Environment

...

========================================
Test Summary
========================================
Total Tests: 6
Passed: 6
Failed: 0

All tests passed!
```

## Running Tests

### From Host Machine (Recommended)

```bash
# Start Docker services first
make up

# Run all component tests
make test-components
```

### Inside Container

```bash
# Enter container
make shell

# Run all tests
bash /app/scripts/test_components.sh

# Run individual test
bash /app/scripts/test_ml_components.sh
```

### Manual Testing

You can also run Python tests directly:

```bash
make shell

# Test specific component
python -c "import sentence_transformers; print('OK')"

# Test with more detail
python << 'EOF'
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(["test sentence"])
print(f"Embedding dimension: {embeddings.shape}")
EOF
```

## Troubleshooting

### Tests Fail on First Run

**Issue:** ML component test fails with model download error.

**Solution:** The sentence-transformers model downloads on first use (~90MB). Wait for download to complete, then re-run.

```bash
make shell
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
# Wait for download
bash /app/scripts/test_ml_components.sh
```

### Temporal Connection Tests Fail

**Issue:** Temporal integration tests show warnings about server not reachable.

**Solution:** This is expected if Temporal isn't running. Start services:

```bash
make up
# Wait 10 seconds for Temporal to start
make test-components
```

### Permission Errors

**Issue:** Scripts not executable.

**Solution:**
```bash
chmod +x scripts/test_*.sh
```

### Container Not Running

**Issue:** `make test-components` fails with "container not found".

**Solution:**
```bash
make up
make test-components
```

## Success Criteria Summary

| Component | Critical Tests | Expected Result |
|-----------|----------------|-----------------|
| System Deps | ImageMagick, Tesseract, Git | All installed and functional |
| Python Env | Python 3.10+, core packages | All importable |
| Document Processing | PDF, OCR, markdown | Can process documents |
| ML Components | Embeddings, clustering | Model loads, generates embeddings |
| Temporal | Client, workflows, activities | Decorators work, server connects |
| CLI | Click, rich, prompts | All UI components functional |

## Integration with CI/CD

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Build Docker
  run: docker-compose build

- name: Start Services
  run: docker-compose up -d

- name: Wait for Services
  run: sleep 10

- name: Run Component Tests
  run: docker-compose exec -T frfr bash /app/scripts/test_components.sh
```

## Adding New Tests

To add a new component test:

1. Create `scripts/test_new_component.sh`
2. Follow the structure of existing tests
3. Add to `test_components.sh`:
   ```bash
   run_test "New Component" "$SCRIPT_DIR/test_new_component.sh"
   ```
4. Make executable: `chmod +x scripts/test_new_component.sh`
5. Update this README

## Test Output

Tests produce colored output:
- 🔵 **Blue** - Section headers
- 🟡 **Yellow** - Test running
- 🟢 **Green** - Test passed
- 🔴 **Red** - Test failed
- ⚠️ **Warning** - Non-critical issue

## Expected Runtime

| Test Suite | Runtime | Notes |
|------------|---------|-------|
| System Dependencies | ~5s | Fast |
| Python Environment | ~2s | Very fast |
| Document Processing | ~3s | Creates temp files |
| ML Components | ~30s first run, ~10s subsequent | Model download on first run |
| Temporal | ~5s | Waits for connection |
| CLI Components | ~3s | Fast |
| **Total** | ~50s first run, ~30s subsequent | |

## Questions?

- Check logs: `make logs`
- Inspect container: `make shell`
- Review individual test scripts for detailed test logic
- See main [README.md](../README.md) for project documentation

---

**All tests passing?** You're ready to start implementing Frfr core modules! 🚀
