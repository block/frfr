#!/usr/bin/env python3
"""
Smart PDF text extraction - tries direct text extraction first, OCR as fallback
Usage: python extract_pdf_text.py <pdf_path> <start_page> <end_page> <output_dir>
"""

import sys
import os
from pathlib import Path

try:
    from PyPDF2 import PdfReader
    import pytesseract
    from PIL import Image
    import subprocess
except ImportError as e:
    print(f"Error: {e}")
    print("Run: pip install PyPDF2 pycryptodome pytesseract pillow")
    sys.exit(1)


def extract_text_pypdf(pdf_path, page_num):
    """Try direct text extraction from PDF"""
    try:
        reader = PdfReader(pdf_path)
        text = reader.pages[page_num].extract_text()
        # Check if we got meaningful text (not just whitespace/gibberish)
        if len(text.strip()) > 50:
            return text, "text"
        return None, None
    except Exception as e:
        print(f"    PyPDF2 failed: {e}")
        return None, None


def extract_text_ocr(pdf_path, page_num, output_dir):
    """Fallback to OCR"""
    try:
        img_path = output_dir / f"temp_page_{page_num + 1}.png"

        # Convert PDF to image
        subprocess.run([
            'convert', '-density', '300',
            f'{pdf_path}[{page_num}]',
            str(img_path)
        ], check=True, capture_output=True)

        # OCR
        img = Image.open(img_path)
        text = pytesseract.image_to_string(img, config='--oem 1 --psm 1')

        # Cleanup
        img_path.unlink()

        return text, "ocr"
    except Exception as e:
        print(f"    OCR failed: {e}")
        return None, None


def main():
    if len(sys.argv) != 5:
        print("Usage: python extract_pdf_text.py <pdf_path> <start_page> <end_page> <output_dir>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    start_page = int(sys.argv[2])
    end_page = int(sys.argv[3])
    output_dir = Path(sys.argv[4])

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing: {pdf_path.name}")
    print(f"Pages: {start_page + 1} to {end_page + 1}")
    print()

    for page_num in range(start_page, end_page + 1):
        page_label = f"{page_num + 1:03d}"
        print(f"Page {page_num + 1}...", end=" ")

        # Try direct text extraction first
        text, method = extract_text_pypdf(str(pdf_path), page_num)

        # Fallback to OCR if needed
        if text is None:
            print("(using OCR)...", end=" ")
            text, method = extract_text_ocr(str(pdf_path), page_num, output_dir)

        if text:
            output_file = output_dir / f"page_{page_label}.txt"
            output_file.write_text(text)
            print(f"✓ ({method}, {len(text)} chars)")
        else:
            print("✗ Failed")

    print()
    print(f"✅ Complete! Output: {output_dir}")


if __name__ == "__main__":
    main()
