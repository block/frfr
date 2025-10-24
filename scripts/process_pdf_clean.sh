#!/bin/bash
# Production OCR with smart cleaning
# Usage: ./process_pdf_clean.sh <pdf_name> [start_page] [end_page]

set -e

PDF_NAME=${1:-test-doc.pdf}
START_PAGE=${2:-0}
END_PAGE=${3:-5}

PDF_PATH="/app/documents/$PDF_NAME"
OUTPUT_DIR="/app/output"

echo "=========================================="
echo "PRODUCTION PDF OCR (Smart Clean)"
echo "=========================================="
echo "PDF: $PDF_NAME"
echo "Pages: $START_PAGE to $END_PAGE"
echo ""

mkdir -p $OUTPUT_DIR/images_clean
mkdir -p $OUTPUT_DIR/text_clean

for ((page=$START_PAGE; page<=$END_PAGE; page++)); do
    page_num=$(printf "%03d" $((page + 1)))
    echo "Processing page $((page + 1))..."

    # High quality conversion
    convert -density 400 \
            -background white \
            -alpha remove \
            -alpha off \
            "${PDF_PATH}[${page}]" \
            -deskew 40% \
            "$OUTPUT_DIR/images_clean/page_${page_num}.png" 2>/dev/null || continue

    # Run OCR with cleaning
    python3 << PYEOF
import pytesseract
from PIL import Image
import re

try:
    img = Image.open('$OUTPUT_DIR/images_clean/page_${page_num}.png')

    # Best settings for business documents
    config = r'--oem 1 --psm 1'
    text = pytesseract.image_to_string(img, config=config)

    # Smart cleaning
    lines = []
    for line in text.split('\n'):
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Remove lines that are mostly dots (TOC leaders)
        # But keep lines with actual content
        if line.count('.') > 20 and len(line.replace('.', '').strip()) < 10:
            continue

        # Clean up repeated characters (OCR artifacts)
        line = re.sub(r'([.:]){10,}', ' ... ', line)
        line = re.sub(r'([=-]){5,}', '---', line)

        # Remove weird symbols that are clearly artifacts
        line = re.sub(r'[@#$%^&*]{1}(?=\s|$)', '', line)

        lines.append(line)

    # Join with newlines, removing excessive blank lines
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)

    with open('$OUTPUT_DIR/text_clean/page_${page_num}.txt', 'w') as f:
        f.write(text)

    print(f"  ✓ Page $((page + 1)): {len(text)} characters")
except Exception as e:
    print(f"  ✗ Error: {e}")
PYEOF

done

echo ""
echo "=========================================="
echo "✅ Production processing complete!"
echo "=========================================="
echo "Output: ~/Development/frfr/output/text_clean/"
echo ""
echo "Quality improvements:"
echo "  - 400 DPI resolution"
echo "  - LSTM neural network OCR"
echo "  - Smart artifact removal"
echo "  - TOC leader dots cleaned"
echo "  - Excessive whitespace removed"
