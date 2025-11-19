"""
PDF text extraction module.

Provides a simple API to extract text from PDFs using the best available method:
- pdfplumber for text-based PDFs (best layout/table preservation for Google Docs PDFs)
- PyMuPDF (fitz) as fast fallback
- PyPDF2 as final fallback
- Tesseract OCR for scanned PDFs (future enhancement)
"""

import logging
from pathlib import Path
from typing import Optional

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

from PIL import Image
import pytesseract
import subprocess

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails."""
    pass


def clean_extracted_text(text: str) -> str:
    """
    Clean extracted PDF text to remove problematic unicode characters.

    Removes/replaces characters that can cause JSON parsing issues:
    - Private Use Area characters (U+E000 to U+F8FF)
    - Replaces smart quotes with standard quotes
    - Removes zero-width characters
    - Normalizes whitespace

    Args:
        text: Raw extracted text from PDF

    Returns:
        Cleaned text safe for JSON processing
    """
    import re

    # Replace smart quotes with standard quotes
    text = text.replace('\u201c', '"')  # "
    text = text.replace('\u201d', '"')  # "
    text = text.replace('\u2018', "'")  # '
    text = text.replace('\u2019', "'")  # '

    # Remove Private Use Area characters (U+E000 to U+F8FF)
    # These are often formatting/hyperlink markers from PDFs
    text = re.sub(r'[\ue000-\uf8ff]', '', text)

    # Remove zero-width characters
    text = text.replace('\u200b', '')  # Zero-width space
    text = text.replace('\u200c', '')  # Zero-width non-joiner
    text = text.replace('\u200d', '')  # Zero-width joiner
    text = text.replace('\ufeff', '')  # Zero-width no-break space (BOM)

    # Remove other problematic control characters but keep newlines/tabs
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    return text


def extract_pdf_to_text(
    pdf_path: str | Path,
    output_path: str | Path,
    min_text_threshold: int = 50
) -> dict[str, any]:
    """
    Extract text from a PDF and save to a text file.

    Automatically chooses the best extraction method:
    1. Tries PyMuPDF (fitz) first - fast, accurate, handles Google Docs PDFs
    2. Falls back to PyPDF2 if PyMuPDF fails
    3. Future: OCR fallback for scanned PDFs

    Args:
        pdf_path: Path to the input PDF file
        output_path: Path to save the extracted text file
        min_text_threshold: Minimum characters to consider text extraction successful

    Returns:
        dict with extraction metadata:
            - method: "pymupdf", "pypdf2", or "ocr"
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

    # Try pdfplumber first (best layout/table preservation)
    if PDFPLUMBER_AVAILABLE:
        try:
            all_text = []
            method = "pdfplumber"

            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()

                    if text:
                        # Check if we got meaningful text
                        if len(text.strip()) < min_text_threshold:
                            logger.warning(
                                f"Page {page_num + 1}: Low text content ({len(text)} chars), "
                                "might be scanned. Consider OCR fallback."
                            )
                        all_text.append(text)
                    else:
                        all_text.append("")

            # Join all pages
            full_text = "\n\n=== PAGE BREAK ===\n\n".join(all_text)

            # Clean problematic unicode characters
            full_text = clean_extracted_text(full_text)

            # Save to file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(full_text, encoding='utf-8')

            logger.info(
                f"✓ Extracted {len(full_text)} characters from {page_count} pages "
                f"using {method}"
            )

            return {
                "method": method,
                "pages": page_count,
                "total_chars": len(full_text),
                "output_file": str(output_path),
                "source_pdf": str(pdf_path.name),
                "source_pdf_path": str(pdf_path),
            }

        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}. Trying PyMuPDF fallback...")

    # Try PyMuPDF second (fast fallback)
    if PYMUPDF_AVAILABLE:
        try:
            doc = fitz.open(pdf_path)
            all_text = []
            method = "pymupdf"

            for page_num, page in enumerate(doc):
                text = page.get_text()

                # Check if we got meaningful text
                if len(text.strip()) < min_text_threshold:
                    logger.warning(
                        f"Page {page_num + 1}: Low text content ({len(text)} chars), "
                        "might be scanned. Consider OCR fallback."
                    )

                all_text.append(text)

            doc.close()

            # Join all pages
            full_text = "\n\n=== PAGE BREAK ===\n\n".join(all_text)

            # Clean problematic unicode characters
            full_text = clean_extracted_text(full_text)

            # Save to file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(full_text, encoding='utf-8')

            logger.info(
                f"✓ Extracted {len(full_text)} characters from {len(all_text)} pages "
                f"using {method}"
            )

            return {
                "method": method,
                "pages": len(all_text),
                "total_chars": len(full_text),
                "output_file": str(output_path),
                "source_pdf": str(pdf_path.name),
                "source_pdf_path": str(pdf_path),
            }

        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {e}. Trying PyPDF2 fallback...")

    # Fallback to PyPDF2
    if PYPDF2_AVAILABLE:
        try:
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

            # Clean problematic unicode characters
            full_text = clean_extracted_text(full_text)

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
                "source_pdf": str(pdf_path.name),
                "source_pdf_path": str(pdf_path),
            }

        except Exception as e:
            logger.error(f"PyPDF2 extraction failed: {e}")
            raise PDFExtractionError(
                f"Failed to extract text from {pdf_path}: {e}"
            ) from e

    # No extraction library available
    raise PDFExtractionError(
        "No PDF extraction library available. Install PyMuPDF or PyPDF2."
    )


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
        tuple of (text, method) where method is "pymupdf", "pypdf2", or "ocr"

    Raises:
        PDFExtractionError: If extraction fails
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Try pdfplumber first (best layout preservation)
    if PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if page_num >= len(pdf.pages):
                    raise PDFExtractionError(
                        f"Page {page_num} out of range (PDF has {len(pdf.pages)} pages)"
                    )

                text = pdf.pages[page_num].extract_text()

                if text:
                    text = clean_extracted_text(text)

                if text and len(text.strip()) >= min_text_threshold:
                    return text, "pdfplumber"
                elif text:
                    logger.warning(
                        f"Page {page_num + 1}: Low text content, might need OCR fallback"
                    )
                    return text, "pdfplumber"
                else:
                    logger.warning(f"Page {page_num + 1}: No text extracted, trying fallback...")

        except Exception as e:
            logger.warning(f"pdfplumber page extraction failed: {e}. Trying PyMuPDF...")

    # Try PyMuPDF second
    if PYMUPDF_AVAILABLE:
        try:
            doc = fitz.open(pdf_path)

            if page_num >= len(doc):
                doc.close()
                raise PDFExtractionError(
                    f"Page {page_num} out of range (PDF has {len(doc)} pages)"
                )

            text = doc[page_num].get_text()
            doc.close()

            # Clean problematic unicode
            text = clean_extracted_text(text)

            if len(text.strip()) >= min_text_threshold:
                return text, "pymupdf"
            else:
                logger.warning(
                    f"Page {page_num + 1}: Low text content, might need OCR fallback"
                )
                return text, "pymupdf"

        except Exception as e:
            logger.warning(f"PyMuPDF page extraction failed: {e}. Trying PyPDF2...")

    # Fallback to PyPDF2
    if PYPDF2_AVAILABLE:
        try:
            reader = PdfReader(str(pdf_path))

            if page_num >= len(reader.pages):
                raise PDFExtractionError(
                    f"Page {page_num} out of range (PDF has {len(reader.pages)} pages)"
                )

            text = reader.pages[page_num].extract_text()

            # Clean problematic unicode
            text = clean_extracted_text(text)

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

    raise PDFExtractionError(
        "No PDF extraction library available. Install PyMuPDF or PyPDF2."
    )


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

    # Try pdfplumber first
    if PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                info = {
                    "pages": len(pdf.pages),
                    "is_encrypted": pdf.stream.is_encrypted if hasattr(pdf.stream, 'is_encrypted') else False,
                    "file_size": pdf_path.stat().st_size,
                }
                return info

        except Exception as e:
            logger.warning(f"pdfplumber info extraction failed: {e}. Trying PyMuPDF...")

    # Try PyMuPDF second
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

        except Exception as e:
            logger.warning(f"PyMuPDF info extraction failed: {e}. Trying PyPDF2...")

    # Fallback to PyPDF2
    if PYPDF2_AVAILABLE:
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

    raise PDFExtractionError(
        "No PDF extraction library available. Install PyMuPDF or PyPDF2."
    )
