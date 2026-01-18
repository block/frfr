#!/usr/bin/env python3
"""
Standalone PDF text extractor with JSON output.

Called by Go backend via subprocess:
    python -m frfr_pdf.extractor <pdf_path> --output <text_path> --json

Outputs JSON to stdout:
    {"status":"success","method":"pdfplumber","pages":155,"total_chars":400000,"output_file":"/path/to/output.txt"}
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Optional imports with availability flags
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False


def clean_extracted_text(text: str) -> str:
    """
    Clean extracted PDF text to remove problematic unicode characters.

    Removes/replaces characters that can cause JSON parsing issues:
    - Private Use Area characters (U+E000 to U+F8FF)
    - Replaces smart quotes with standard quotes
    - Removes zero-width characters
    - Normalizes whitespace
    """
    # Replace smart quotes with standard quotes
    text = text.replace('\u201c', '"')  # "
    text = text.replace('\u201d', '"')  # "
    text = text.replace('\u2018', "'")  # '
    text = text.replace('\u2019', "'")  # '

    # Remove Private Use Area characters (U+E000 to U+F8FF)
    text = re.sub(r'[\ue000-\uf8ff]', '', text)

    # Remove zero-width characters
    text = text.replace('\u200b', '')  # Zero-width space
    text = text.replace('\u200c', '')  # Zero-width non-joiner
    text = text.replace('\u200d', '')  # Zero-width joiner
    text = text.replace('\ufeff', '')  # Zero-width no-break space (BOM)

    # Remove other problematic control characters but keep newlines/tabs
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    return text


def extract_with_pdfplumber(pdf_path: Path, min_text_threshold: int = 50) -> tuple[list[str], str]:
    """Extract text using pdfplumber (best layout preservation)."""
    all_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            all_text.append(text)
    return all_text, "pdfplumber"


def extract_with_pymupdf(pdf_path: Path, min_text_threshold: int = 50) -> tuple[list[str], str]:
    """Extract text using PyMuPDF (fast)."""
    doc = fitz.open(pdf_path)
    all_text = []
    for page in doc:
        text = page.get_text()
        all_text.append(text)
    doc.close()
    return all_text, "pymupdf"


def extract_with_pypdf2(pdf_path: Path, min_text_threshold: int = 50) -> tuple[list[str], str]:
    """Extract text using PyPDF2 (fallback)."""
    reader = PdfReader(str(pdf_path))
    all_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        all_text.append(text)
    return all_text, "pypdf2"


def extract_pdf_to_text(
    pdf_path: Path,
    output_path: Path,
    min_text_threshold: int = 50
) -> dict:
    """
    Extract text from a PDF and save to a text file.

    Returns dict with extraction metadata.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    all_text = None
    method = None
    errors = []

    # Try extractors in order of preference
    extractors = []
    if PDFPLUMBER_AVAILABLE:
        extractors.append(("pdfplumber", extract_with_pdfplumber))
    if PYMUPDF_AVAILABLE:
        extractors.append(("pymupdf", extract_with_pymupdf))
    if PYPDF2_AVAILABLE:
        extractors.append(("pypdf2", extract_with_pypdf2))

    if not extractors:
        raise RuntimeError(
            "No PDF extraction library available. Install one of: "
            "pdfplumber, PyMuPDF (fitz), PyPDF2"
        )

    for name, extractor in extractors:
        try:
            all_text, method = extractor(pdf_path, min_text_threshold)
            break
        except Exception as e:
            errors.append(f"{name}: {e}")
            continue

    if all_text is None:
        raise RuntimeError(
            f"All extraction methods failed: {'; '.join(errors)}"
        )

    # Join all pages with page break markers
    full_text = "\n\n=== PAGE BREAK ===\n\n".join(all_text)

    # Clean problematic unicode characters
    full_text = clean_extracted_text(full_text)

    # Save to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_text, encoding='utf-8')

    return {
        "status": "success",
        "method": method,
        "pages": len(all_text),
        "total_chars": len(full_text),
        "output_file": str(output_path.absolute()),
        "source_pdf": str(pdf_path.name),
        "source_pdf_path": str(pdf_path.absolute()),
    }


def get_pdf_info(pdf_path: Path) -> dict:
    """Get metadata about a PDF file."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                return {
                    "pages": len(pdf.pages),
                    "is_encrypted": getattr(pdf.stream, 'is_encrypted', False),
                    "file_size": pdf_path.stat().st_size,
                }
        except Exception:
            pass

    if PYMUPDF_AVAILABLE:
        try:
            doc = fitz.open(pdf_path)
            info = {
                "pages": len(doc),
                "is_encrypted": doc.is_encrypted,
                "file_size": pdf_path.stat().st_size,
            }
            doc.close()
            return info
        except Exception:
            pass

    if PYPDF2_AVAILABLE:
        try:
            reader = PdfReader(str(pdf_path))
            return {
                "pages": len(reader.pages),
                "is_encrypted": reader.is_encrypted,
                "file_size": pdf_path.stat().st_size,
            }
        except Exception:
            pass

    raise RuntimeError("No PDF library available to read file info")


def main():
    parser = argparse.ArgumentParser(
        description="Extract text from PDF files with JSON output"
    )
    parser.add_argument(
        "pdf_path",
        help="Path to input PDF file"
    )
    parser.add_argument(
        "--output", "-o",
        help="Path to save extracted text (default: <pdf_name>_text.txt)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON to stdout"
    )
    parser.add_argument(
        "--info-only",
        action="store_true",
        help="Only return PDF info, don't extract text"
    )
    parser.add_argument(
        "--min-text-threshold",
        type=int,
        default=50,
        help="Minimum characters per page to consider extraction successful"
    )

    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)

    try:
        if args.info_only:
            result = get_pdf_info(pdf_path)
            result["status"] = "success"
        else:
            # Determine output path
            if args.output:
                output_path = Path(args.output)
            else:
                output_path = Path(f"{pdf_path.stem}_text.txt")

            result = extract_pdf_to_text(
                pdf_path,
                output_path,
                min_text_threshold=args.min_text_threshold
            )

        if args.json:
            print(json.dumps(result))
        else:
            if args.info_only:
                print(f"PDF: {pdf_path.name}")
                print(f"Pages: {result['pages']}")
                print(f"Encrypted: {result.get('is_encrypted', False)}")
                print(f"Size: {result['file_size']:,} bytes")
            else:
                print(f"Extracted {result['total_chars']:,} characters "
                      f"from {result['pages']} pages using {result['method']}")
                print(f"Output: {result['output_file']}")

        sys.exit(0)

    except FileNotFoundError as e:
        error_result = {"status": "error", "error": str(e), "error_type": "file_not_found"}
        if args.json:
            print(json.dumps(error_result))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        error_result = {"status": "error", "error": str(e), "error_type": "extraction_failed"}
        if args.json:
            print(json.dumps(error_result))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
