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

        # Verify result metadata
        assert result["method"] == "pypdf2"
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


def test_extract_pdf_page_to_text():
    """Test extracting a single page from PDF."""
    pdf_path = Path("/app/documents/test-doc.pdf")

    if not pdf_path.exists():
        pytest.skip("Test PDF not found")

    # Extract page 1 (index 1, which is page 2 in the document)
    text, method = extract_pdf_page_to_text(pdf_path, page_num=1)

    assert method == "pypdf2"
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
