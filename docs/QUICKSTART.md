# Quick Start: Process and Query Your Documents

Process PDFs and query them interactively using a single command.

## Prerequisites

- Python 3.10+ installed
- Claude CLI authenticated: `claude login`
- Your PDF in a local directory

## Fastest Way: Process Command (PDF → Interactive Querying)

Process a PDF from start to finish and enter interactive query mode:

```bash
# Process a document (extracts, analyzes, validates, and queries)
frfr process documents/soc2_report.pdf

# Or with custom settings
frfr process documents/report.pdf \
  --max-workers 11 \
  --multipass \
  --show-facts
```

This single command:
1. ✅ Extracts PDF to text
2. ✅ Extracts facts using LLM
3. ✅ Validates facts against source
4. ✅ Launches interactive query mode

Then ask questions like:
- "Does the system implement 2-factor authentication?"
- "What are the data retention policies?"
- "What security controls are described?"

Type `exit` to quit interactive mode.

## Alternative: Step-by-Step Extraction

### Extract a PDF

```bash
# Extract the PDF to text
frfr extract documents/report.pdf output/report_text.txt
```

### Extract Facts

```bash
# Extract structured facts from the text
frfr extract-facts output/report_text.txt \
  --document-name my_report \
  --max-workers 11
```

### Validate Facts

```bash
# Validate extracted facts against source
frfr validate-facts output/my_report_facts.json output/report_text.txt
```

### Query Interactively

```bash
# Launch interactive query mode
frfr interactive output/my_report_facts.json --show-facts
```

## View the Results

```bash
# View the extracted text
cat output/report_text.txt | head -100

# Or with pagination
less output/report_text.txt

# Search for specific content
grep -i "authentication" output/report_text.txt

# Count words
wc -w output/report_text.txt
```

## What You Get

✅ **Complete extraction** - All pages processed
✅ **Clean text** - No OCR artifacts
✅ **Fast** - PyPDF2 direct extraction (OCR fallback when needed)
✅ **Encrypted PDFs** - Handles them automatically
✅ **Validated facts** - 100% verification against source

## Additional CLI Commands

### Get PDF info

```bash
frfr info documents/report.pdf
```

### CLI help

```bash
frfr --help
frfr extract --help
frfr process --help
```

## Next Steps

Use the extracted facts for:
- Natural language Q&A
- Compliance checking
- Security analysis
- Cross-document queries

## Troubleshooting

**Issue:** `FileNotFoundError: PDF not found`
**Solution:** Ensure your PDF path is correct

```bash
ls documents/
# Should show your PDF file
```

**Issue:** `No Anthropic API key found`
**Solution:** Authenticate with Claude CLI:

```bash
claude login
```

**Issue:** CLI command not found
**Solution:** Reinstall the package:

```bash
pip install -e .
```

## Architecture

The extraction uses:
- **PyPDF2** - Fast, clean text extraction for text-based PDFs
- **pycryptodome** - Handles encrypted PDFs automatically
- **Tesseract OCR** - Fallback for scanned/image PDFs (rarely needed)
- **Claude CLI** - LLM-based fact extraction and validation

The CLI intelligently chooses the best method for your PDF.
