"""
Document processing module.

Provides utilities for extracting and processing text from various document formats.
"""

from .pdf_extractor import (
    extract_pdf_to_text,
    extract_pdf_page_to_text,
    get_pdf_info,
    PDFExtractionError,
)

__all__ = [
    "extract_pdf_to_text",
    "extract_pdf_page_to_text",
    "get_pdf_info",
    "PDFExtractionError",
]
