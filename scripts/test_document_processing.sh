#!/bin/bash
# Test document processing dependencies

set -e

SUCCESS=0
FAILURE=1

echo "Testing Document Processing..."
echo "=============================="

# Test 1: PyPDF2
echo -n "  Checking PyPDF2... "
if python -c "import PyPDF2" 2>/dev/null; then
    VERSION=$(python -c "import PyPDF2; print(PyPDF2.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 2: PyPDF2 functionality (create a simple PDF)
echo -n "  Testing PyPDF2 read capability... "
python << 'EOF'
import PyPDF2
from io import BytesIO

# Create a minimal valid PDF
pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources 4 0 R /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000229 00000 n
0000000328 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
420
%%EOF"""

pdf_file = BytesIO(pdf_content)
reader = PyPDF2.PdfReader(pdf_file)
assert len(reader.pages) == 1
print("✓ Can read PDFs", end="")
EOF
echo ""

# Test 3: pytesseract
echo -n "  Checking pytesseract... "
if python -c "import pytesseract" 2>/dev/null; then
    echo "✓ Installed"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 4: pytesseract can find tesseract
echo -n "  Testing pytesseract integration... "
if python -c "import pytesseract; pytesseract.get_tesseract_version()" 2>/dev/null; then
    echo "✓ Can communicate with Tesseract"
else
    echo "✗ Cannot find Tesseract binary"
    exit $FAILURE
fi

# Test 5: python-magic
echo -n "  Checking python-magic... "
if python -c "import magic" 2>/dev/null; then
    echo "✓ Installed"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 6: python-magic functionality
echo -n "  Testing python-magic file detection... "
python << 'EOF'
import magic
import tempfile

# Test text file detection
with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
    f.write("Test content")
    temp_path = f.name

mime = magic.from_file(temp_path, mime=True)
assert 'text' in mime.lower()

import os
os.unlink(temp_path)
print("✓ Can detect file types", end="")
EOF
echo ""

# Test 7: markdown
echo -n "  Checking markdown... "
if python -c "import markdown" 2>/dev/null; then
    VERSION=$(python -c "import markdown; print(markdown.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 8: markdown functionality
echo -n "  Testing markdown parsing... "
if python -c "
import markdown
md = markdown.Markdown()
html = md.convert('# Test Header\n\nTest paragraph.')
assert '<h1>' in html
assert 'Test Header' in html
" 2>/dev/null; then
    echo "✓ Can parse markdown"
else
    echo "✗ Markdown parsing failed"
    exit $FAILURE
fi

echo ""
echo "Document processing tests passed!"
exit $SUCCESS
