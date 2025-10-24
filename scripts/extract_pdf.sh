#!/bin/bash
# Production PDF text extraction - tries PyPDF2 first, OCR as fallback
# Usage: ./extract_pdf.sh <pdf_name> [start_page] [end_page]

set -e

PDF_NAME=${1:-test-doc.pdf}
START_PAGE=${2:-0}
END_PAGE=${3:-5}

PDF_PATH="/app/documents/$PDF_NAME"
OUTPUT_DIR="/app/output"

echo "=========================================="
echo "SMART PDF TEXT EXTRACTION"
echo "=========================================="
echo "PDF: $PDF_NAME"
echo "Pages: $START_PAGE to $END_PAGE"
echo ""
echo "Strategy: Try PyPDF2 first, OCR as fallback"
echo ""

docker compose exec frfr python3 /app/scripts/extract_pdf_text.py \
    "$PDF_PATH" \
    "$START_PAGE" \
    "$END_PAGE" \
    "$OUTPUT_DIR/extracted_text"

echo ""
echo "=========================================="
echo "✅ Extraction complete!"
echo "=========================================="
echo "Output: ~/Development/frfr/output/extracted_text/"
echo ""
echo "To view results:"
echo "  ls ~/Development/frfr/output/extracted_text/"
echo "  cat ~/Development/frfr/output/extracted_text/page_001.txt"
