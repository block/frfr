#!/bin/bash
# Test system dependencies (ImageMagick, Tesseract, Git)

set -e

SUCCESS=0
FAILURE=1

echo "Testing System Dependencies..."
echo "=============================="

# Test 1: ImageMagick installed
echo -n "  Checking ImageMagick installation... "
if command -v convert &> /dev/null; then
    VERSION=$(convert -version | head -n1)
    echo "✓ Found: $VERSION"
else
    echo "✗ ImageMagick not found"
    exit $FAILURE
fi

# Test 2: ImageMagick can process images
echo -n "  Testing ImageMagick functionality... "
TEMP_IMG=$(mktemp --suffix=.png)
if convert -size 100x100 xc:white "$TEMP_IMG" 2>/dev/null; then
    if [ -f "$TEMP_IMG" ]; then
        rm "$TEMP_IMG"
        echo "✓ Can create images"
    else
        echo "✗ Image creation failed"
        exit $FAILURE
    fi
else
    echo "✗ Convert command failed"
    exit $FAILURE
fi

# Test 3: Tesseract installed
echo -n "  Checking Tesseract installation... "
if command -v tesseract &> /dev/null; then
    VERSION=$(tesseract --version 2>&1 | head -n1)
    echo "✓ Found: $VERSION"
else
    echo "✗ Tesseract not found"
    exit $FAILURE
fi

# Test 4: Tesseract English language data
echo -n "  Checking Tesseract English data... "
if tesseract --list-langs 2>&1 | grep -q "eng"; then
    echo "✓ English language pack installed"
else
    echo "✗ English language pack missing"
    exit $FAILURE
fi

# Test 5: Tesseract OCR functionality
echo -n "  Testing Tesseract OCR... "
TEMP_TXT=$(mktemp)
# Create a simple text image
convert -size 400x100 xc:white -pointsize 24 -fill black \
    -draw "text 10,50 'Test OCR Text'" -quality 100 /tmp/test_ocr.png 2>/dev/null

if tesseract /tmp/test_ocr.png "$TEMP_TXT" 2>/dev/null; then
    if grep -q "Test" "${TEMP_TXT}.txt" 2>/dev/null; then
        rm -f /tmp/test_ocr.png "${TEMP_TXT}.txt"
        echo "✓ OCR working"
    else
        echo "✗ OCR failed to extract text"
        rm -f /tmp/test_ocr.png "${TEMP_TXT}.txt"
        exit $FAILURE
    fi
else
    echo "✗ Tesseract command failed"
    rm -f /tmp/test_ocr.png
    exit $FAILURE
fi

# Test 6: Git installed
echo -n "  Checking Git installation... "
if command -v git &> /dev/null; then
    VERSION=$(git --version)
    echo "✓ Found: $VERSION"
else
    echo "✗ Git not found"
    exit $FAILURE
fi

echo ""
echo "All system dependency tests passed!"
exit $SUCCESS
