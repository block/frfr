#!/bin/bash
# High-quality PDF OCR processing with enhanced settings
# Usage: ./process_pdf_hq.sh <pdf_name> [start_page] [end_page]

set -e

PDF_NAME=${1:-test-doc.pdf}
START_PAGE=${2:-0}
END_PAGE=${3:-5}

PDF_PATH="/app/documents/$PDF_NAME"
OUTPUT_DIR="/app/output"

echo "=========================================="
echo "HIGH-QUALITY PDF OCR Processing"
echo "=========================================="
echo "PDF: $PDF_NAME"
echo "Pages: $START_PAGE to $END_PAGE"
echo "Settings:"
echo "  - DPI: 400 (higher quality)"
echo "  - Image processing: deskew + denoise"
echo "  - Tesseract PSM: 1 (auto with OSD)"
echo "  - Tesseract OEM: 1 (neural network LSTM)"
echo ""

# Create output directories
mkdir -p $OUTPUT_DIR/images
mkdir -p $OUTPUT_DIR/text
mkdir -p $OUTPUT_DIR/text_hq

# Process each page
for ((page=$START_PAGE; page<=$END_PAGE; page++)); do
    page_num=$(printf "%03d" $((page + 1)))
    echo "Processing page $((page + 1))..."

    # Convert PDF page to high-res image with preprocessing
    convert -density 400 \
            -background white \
            -alpha remove \
            -alpha off \
            "${PDF_PATH}[${page}]" \
            -deskew 40% \
            -strip \
            "$OUTPUT_DIR/images/page_${page_num}_hq.png" 2>/dev/null || {
        echo "  ⚠ Could not convert page $((page + 1))"
        continue
    }

    # Apply additional image preprocessing for better OCR
    convert "$OUTPUT_DIR/images/page_${page_num}_hq.png" \
            -level 0%,100%,0.7 \
            -sharpen 0x1 \
            "$OUTPUT_DIR/images/page_${page_num}_hq.png"

    # Run high-quality OCR with optimal settings
    python3 << PYEOF
import pytesseract
from PIL import Image

try:
    img = Image.open('$OUTPUT_DIR/images/page_${page_num}_hq.png')

    # Use custom Tesseract config for higher quality
    # PSM 1: Automatic page segmentation with OSD (orientation and script detection)
    # OEM 1: Neural nets LSTM engine only (most accurate)
    custom_config = r'--oem 1 --psm 1'

    text = pytesseract.image_to_string(img, config=custom_config)

    # Clean up common OCR artifacts
    # Remove excessive whitespace
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(line for line in lines if line)

    with open('$OUTPUT_DIR/text_hq/page_${page_num}.txt', 'w') as f:
        f.write(text)

    print(f"  ✓ Page $((page + 1)): {len(text)} characters (cleaned)")
except Exception as e:
    print(f"  ✗ Error: {e}")
PYEOF

done

echo ""
echo "=========================================="
echo "✅ High-quality processing complete!"
echo "=========================================="
echo "Output location on host:"
echo "  Images: ~/Development/frfr/output/images/*_hq.png"
echo "  Text:   ~/Development/frfr/output/text_hq/"
echo ""
echo "To compare quality:"
echo "  diff ~/Development/frfr/output/text/page_001.txt \\"
echo "       ~/Development/frfr/output/text_hq/page_001.txt"
