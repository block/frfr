"""
Tests for PDF extraction functionality.
"""

import pytest
from pathlib import Path
import tempfile

from frfr.documents import (
    extract_pdf_to_text,
    extract_pdf_page_to_text,
    get_pdf_info,
    PDFExtractionError,
)


def test_extract_pdf_to_text_with_real_pdf():
    """Test extracting text from the test SOC2 PDF."""
    pdf_path = Path("/app/documents/test-doc.pdf")

    # Skip if test PDF doesn't exist
    if not pdf_path.exists():
        pytest.skip("Test PDF not found")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        output_path = Path(f.name)

    try:
        result = extract_pdf_to_text(pdf_path, output_path)

        # Verify result metadata (method should be pdfplumber, pymupdf, or pypdf2)
        assert result["method"] in ["pdfplumber", "pymupdf", "pypdf2"]
        assert result["pages"] == 155
        assert result["total_chars"] > 400000  # Should have substantial text
        assert result["output_file"] == str(output_path)

        # Verify output file was created
        assert output_path.exists()

        # Verify content is readable
        content = output_path.read_text()
        assert len(content) > 400000
        assert "LexisNexis" in content
        assert "SOC 2" in content

    finally:
        if output_path.exists():
            output_path.unlink()


def test_extract_google_docs_pdf():
    """Test extracting text from Google Docs generated PDF (ADR #0085)."""
    # Try both potential locations
    pdf_paths = [
        Path("/app/documents/[ADR - #0085] - Declaring Ownership of Datasets at Block.pdf"),
        Path("/Users/nesposito/Development/frfr/inputs/[ADR - #0085] - Declaring Ownership of Datasets at Block.pdf"),
    ]

    pdf_path = None
    for path in pdf_paths:
        if path.exists():
            pdf_path = path
            break

    if pdf_path is None:
        pytest.skip("ADR test PDF not found")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        output_path = Path(f.name)

    try:
        result = extract_pdf_to_text(pdf_path, output_path)

        # Verify result metadata
        assert result["method"] in ["pdfplumber", "pymupdf", "pypdf2"]
        assert result["pages"] == 32
        assert result["total_chars"] > 20000

        # Verify output file was created
        assert output_path.exists()

        # Verify content is readable and NOT spaced out
        content = output_path.read_text()
        assert len(content) > 20000

        # Check that text is properly formatted (not "S c o p e :")
        # Should contain "Scope:" not "S c o p e :"
        assert "Scope:" in content or "Scope :" in content
        assert "Block" in content
        assert "Cameron Hotchkies" in content

        # Ensure we DON'T have the spaced-out garbage
        # If we see 3+ consecutive single-char words with spaces, that's bad
        import re
        spaced_pattern = re.compile(r'(\b\w\s){5,}')  # 5+ single chars in a row
        spaced_matches = spaced_pattern.findall(content[:5000])  # Check first 5000 chars
        assert len(spaced_matches) == 0, f"Found spaced-out text: {spaced_matches[:3]}"

    finally:
        if output_path.exists():
            output_path.unlink()


def test_extract_pdf_page_to_text():
    """Test extracting a single page from PDF."""
    pdf_path = Path("/app/documents/test-doc.pdf")

    if not pdf_path.exists():
        pytest.skip("Test PDF not found")

    # Extract page 1 (index 1, which is page 2 in the document)
    text, method = extract_pdf_page_to_text(pdf_path, page_num=1)

    assert method in ["pdfplumber", "pymupdf", "pypdf2"]
    assert len(text) > 1000
    assert "LexisNexis" in text
    assert "TABLE OF CONTENTS" in text


def test_get_pdf_info():
    """Test getting PDF metadata."""
    pdf_path = Path("/app/documents/test-doc.pdf")

    if not pdf_path.exists():
        pytest.skip("Test PDF not found")

    info = get_pdf_info(pdf_path)

    assert info["pages"] == 155
    assert info["is_encrypted"] is True
    assert info["file_size"] > 1000000  # Should be > 1MB


def test_extract_nonexistent_pdf():
    """Test that extracting a nonexistent PDF raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        extract_pdf_to_text("/nonexistent/file.pdf", "/tmp/output.txt")


def test_extract_invalid_page():
    """Test that extracting an invalid page number raises an error."""
    pdf_path = Path("/app/documents/test-doc.pdf")

    if not pdf_path.exists():
        pytest.skip("Test PDF not found")

    with pytest.raises(PDFExtractionError, match="out of range"):
        extract_pdf_page_to_text(pdf_path, page_num=999)


def test_pdf_info_nonexistent():
    """Test that getting info for nonexistent PDF raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        get_pdf_info("/nonexistent/file.pdf")


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
