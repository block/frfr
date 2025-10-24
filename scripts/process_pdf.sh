#!/bin/bash
# Process PDF with OCR and save results to output directory
# Usage: ./process_pdf.sh <pdf_name> [start_page] [end_page]

set -e

PDF_NAME=${1:-test-doc.pdf}
START_PAGE=${2:-0}
END_PAGE=${3:-5}

PDF_PATH="/app/documents/$PDF_NAME"
OUTPUT_DIR="/app/output"

echo "=========================================="
echo "PDF OCR Processing"
echo "=========================================="
echo "PDF: $PDF_NAME"
echo "Pages: $START_PAGE to $END_PAGE"
echo ""

# Create output directories
mkdir -p $OUTPUT_DIR/images
mkdir -p $OUTPUT_DIR/text

# Process each page
for ((page=$START_PAGE; page<=$END_PAGE; page++)); do
    page_num=$(printf "%03d" $((page + 1)))
    echo "Processing page $((page + 1))..."

    # Convert PDF page to image
    convert -density 300 "${PDF_PATH}[${page}]" "$OUTPUT_DIR/images/page_${page_num}.png" 2>/dev/null || {
        echo "  ⚠ Could not convert page $((page + 1))"
        continue
    }

    # Run OCR
    python3 << PYEOF
from PIL import Image
import pytesseract

try:
    img = Image.open('$OUTPUT_DIR/images/page_${page_num}.png')
    text = pytesseract.image_to_string(img)

    with open('$OUTPUT_DIR/text/page_${page_num}.txt', 'w') as f:
        f.write(text)

    print(f"  ✓ Page $((page + 1)): {len(text)} characters")
except Exception as e:
    print(f"  ✗ Error: {e}")
PYEOF

done

echo ""
echo "=========================================="
echo "✅ Processing complete!"
echo "=========================================="
echo "Output location on host:"
echo "  Images: ~/Development/frfr/output/images/"
echo "  Text:   ~/Development/frfr/output/text/"
echo ""
echo "To view results:"
echo "  ls ~/Development/frfr/output/text/"
echo "  cat ~/Development/frfr/output/text/page_001.txt"
