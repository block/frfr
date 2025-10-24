# Quick Start: Extract Your SOC2 Report

Extract text from PDFs using a single command. Works from your terminal on the host machine.

## Prerequisites

- Docker services running: `make up` (or `docker compose up -d`)
- Your PDF in the `documents/` directory

## Extract a PDF (Portable CLI)

### Method 1: Simple wrapper script

```bash
cd ~/Development/frfr

# Extract the SOC2 report (all 155 pages)
./extract-pdf test-doc.pdf soc2_report.txt
```

That's it! The output appears in `output/soc2_report.txt` on your host machine.

### Method 2: Direct CLI command

```bash
cd ~/Development/frfr

docker compose exec frfr frfr extract \
    /app/documents/test-doc.pdf \
    /app/output/soc2_full_text.txt
```

Output: `~/Development/frfr/output/soc2_full_text.txt`

### Method 3: Your own PDF

```bash
cd ~/Development/frfr

# Copy your PDF to documents/
cp /path/to/your-file.pdf documents/

# Extract it
./extract-pdf your-file.pdf your-output.txt

# Or use the full CLI command
docker compose exec frfr frfr extract \
    /app/documents/your-file.pdf \
    /app/output/your-output.txt
```

## View the Results

```bash
# View the extracted text
cat output/soc2_report.txt | head -100

# Or with pagination
less output/soc2_report.txt

# Search for specific content
grep -i "authentication" output/soc2_report.txt

# Count words
wc -w output/soc2_report.txt
```

## What You Get

✅ **All 155 pages** - Complete document (~476K characters)  
✅ **Clean text** - No OCR artifacts (`ccccccc`, `ssshhshshs`)  
✅ **Fast** - PyPDF2 direct extraction (not OCR)  
✅ **Encrypted PDFs** - Handles them automatically  
✅ **Host accessible** - Output in `~/Development/frfr/output/`

## Additional CLI Commands

### Get PDF info

```bash
docker compose exec frfr frfr info /app/documents/test-doc.pdf
```

### CLI help

```bash
docker compose exec frfr frfr --help
docker compose exec frfr frfr extract --help
```

## Next Steps

Use the extracted text for:
- LLM question answering
- Swarm consensus analysis  
- Semantic search
- Compliance checking

## Troubleshooting

**Issue:** `FileNotFoundError: PDF not found`  
**Solution:** Ensure your PDF is in `~/Development/frfr/documents/`

```bash
ls ~/Development/frfr/documents/
# Should show: test-doc.pdf
```

**Issue:** Docker services not running  
**Solution:**

```bash
cd ~/Development/frfr
make up
# or
docker compose up -d
```

**Issue:** CLI command not found  
**Solution:** Reinstall the package:

```bash
docker compose exec frfr pip install -e /app
```

## Architecture

The extraction uses:
- **PyPDF2** - Fast, clean text extraction for text-based PDFs
- **pycryptodome** - Handles encrypted PDFs automatically
- **Tesseract OCR** - Fallback for scanned/image PDFs (rarely needed)

The CLI intelligently chooses the best method for your PDF.
