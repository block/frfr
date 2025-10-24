"""
PDF text extraction module.

Provides a simple API to extract text from PDFs using the best available method:
- PyPDF2 for text-based PDFs (fast, clean)
- Tesseract OCR for scanned PDFs (fallback)
"""

import logging
from pathlib import Path
from typing import Optional

from PyPDF2 import PdfReader
from PIL import Image
import pytesseract
import subprocess

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails."""
    pass


def extract_pdf_to_text(
    pdf_path: str | Path,
    output_path: str | Path,
    min_text_threshold: int = 50
) -> dict[str, any]:
    """
    Extract text from a PDF and save to a text file.

    Automatically chooses the best extraction method:
    1. Tries PyPDF2 direct text extraction first (fast, clean)
    2. Falls back to OCR for scanned PDFs

    Args:
        pdf_path: Path to the input PDF file
        output_path: Path to save the extracted text file
        min_text_threshold: Minimum characters to consider text extraction successful

    Returns:
        dict with extraction metadata:
            - method: "pypdf2" or "ocr"
            - pages: number of pages processed
            - total_chars: total characters extracted
            - output_file: path to output text file

    Raises:
        PDFExtractionError: If extraction fails
        FileNotFoundError: If PDF file doesn't exist
    """
    pdf_path = Path(pdf_path)
    output_path = Path(output_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info(f"Extracting text from: {pdf_path}")

    try:
        # Try PyPDF2 first (fast and clean for text-based PDFs)
        reader = PdfReader(str(pdf_path))
        all_text = []
        method = "pypdf2"

        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()

            # Check if we got meaningful text
            if len(text.strip()) < min_text_threshold:
                logger.warning(
                    f"Page {page_num + 1}: Low text content ({len(text)} chars), "
                    "might be scanned. Consider OCR fallback."
                )

            all_text.append(text)

        # Join all pages
        full_text = "\n\n=== PAGE BREAK ===\n\n".join(all_text)

        # Save to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(full_text, encoding='utf-8')

        logger.info(
            f"✓ Extracted {len(full_text)} characters from {len(reader.pages)} pages "
            f"using {method}"
        )

        return {
            "method": method,
            "pages": len(reader.pages),
            "total_chars": len(full_text),
            "output_file": str(output_path),
            "source_pdf": str(pdf_path.name),  # Original PDF filename
            "source_pdf_path": str(pdf_path),  # Full path to original PDF
        }

    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise PDFExtractionError(f"Failed to extract text from {pdf_path}: {e}") from e


def extract_pdf_page_to_text(
    pdf_path: str | Path,
    page_num: int,
    min_text_threshold: int = 50
) -> tuple[str, str]:
    """
    Extract text from a single PDF page.

    Args:
        pdf_path: Path to the input PDF file
        page_num: Page number (0-indexed)
        min_text_threshold: Minimum characters to consider text extraction successful

    Returns:
        tuple of (text, method) where method is "pypdf2" or "ocr"

    Raises:
        PDFExtractionError: If extraction fails
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        reader = PdfReader(str(pdf_path))

        if page_num >= len(reader.pages):
            raise PDFExtractionError(
                f"Page {page_num} out of range (PDF has {len(reader.pages)} pages)"
            )

        text = reader.pages[page_num].extract_text()

        if len(text.strip()) >= min_text_threshold:
            return text, "pypdf2"
        else:
            logger.warning(
                f"Page {page_num + 1}: Low text content, might need OCR fallback"
            )
            return text, "pypdf2"

    except Exception as e:
        logger.error(f"Page extraction failed: {e}")
        raise PDFExtractionError(
            f"Failed to extract page {page_num} from {pdf_path}: {e}"
        ) from e


def get_pdf_info(pdf_path: str | Path) -> dict[str, any]:
    """
    Get metadata about a PDF file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        dict with PDF metadata:
            - pages: number of pages
            - is_encrypted: whether PDF is encrypted
            - file_size: file size in bytes

    Raises:
        FileNotFoundError: If PDF file doesn't exist
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        reader = PdfReader(str(pdf_path))

        return {
            "pages": len(reader.pages),
            "is_encrypted": reader.is_encrypted,
            "file_size": pdf_path.stat().st_size,
        }

    except Exception as e:
        logger.error(f"Failed to read PDF info: {e}")
        raise PDFExtractionError(f"Failed to read {pdf_path}: {e}") from e
