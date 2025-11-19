#!/usr/bin/env python3
"""
Compare PDF extraction tools on test documents.

Tests multiple PDF extraction libraries to find the best performer:
- PyPDF2 (current)
- pdfplumber
- PyMuPDF (fitz)
- pdfminer.six

Metrics:
- Extraction quality (character spacing, word integrity)
- Speed (extraction time)
- Text readability
- Structure preservation
"""

import time
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def extract_with_pypdf2(pdf_path: Path) -> Dict[str, Any]:
    """Extract text using PyPDF2 (current implementation)."""
    try:
        from PyPDF2 import PdfReader

        start_time = time.time()
        reader = PdfReader(str(pdf_path))
        all_text = []

        for page in reader.pages:
            text = page.extract_text()
            all_text.append(text)

        full_text = "\n\n=== PAGE BREAK ===\n\n".join(all_text)
        extraction_time = time.time() - start_time

        return {
            "success": True,
            "library": "PyPDF2",
            "text": full_text,
            "pages": len(reader.pages),
            "chars": len(full_text),
            "time": extraction_time,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "library": "PyPDF2",
            "text": "",
            "pages": 0,
            "chars": 0,
            "time": 0,
            "error": str(e)
        }


def extract_with_pdfplumber(pdf_path: Path) -> Dict[str, Any]:
    """Extract text using pdfplumber."""
    try:
        import pdfplumber

        start_time = time.time()
        all_text = []
        page_count = 0

        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)
                else:
                    all_text.append("")

        full_text = "\n\n=== PAGE BREAK ===\n\n".join(all_text)
        extraction_time = time.time() - start_time

        return {
            "success": True,
            "library": "pdfplumber",
            "text": full_text,
            "pages": page_count,
            "chars": len(full_text),
            "time": extraction_time,
            "error": None
        }
    except ImportError:
        return {
            "success": False,
            "library": "pdfplumber",
            "text": "",
            "pages": 0,
            "chars": 0,
            "time": 0,
            "error": "pdfplumber not installed"
        }
    except Exception as e:
        return {
            "success": False,
            "library": "pdfplumber",
            "text": "",
            "pages": 0,
            "chars": 0,
            "time": 0,
            "error": str(e)
        }


def extract_with_pymupdf(pdf_path: Path) -> Dict[str, Any]:
    """Extract text using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF

        start_time = time.time()
        all_text = []

        doc = fitz.open(pdf_path)
        page_count = len(doc)

        for page in doc:
            text = page.get_text()
            all_text.append(text)

        doc.close()

        full_text = "\n\n=== PAGE BREAK ===\n\n".join(all_text)
        extraction_time = time.time() - start_time

        return {
            "success": True,
            "library": "PyMuPDF",
            "text": full_text,
            "pages": page_count,
            "chars": len(full_text),
            "time": extraction_time,
            "error": None
        }
    except ImportError:
        return {
            "success": False,
            "library": "PyMuPDF",
            "text": "",
            "pages": 0,
            "chars": 0,
            "time": 0,
            "error": "PyMuPDF not installed"
        }
    except Exception as e:
        return {
            "success": False,
            "library": "PyMuPDF",
            "text": "",
            "pages": 0,
            "chars": 0,
            "time": 0,
            "error": str(e)
        }


def extract_with_pdfminer(pdf_path: Path) -> Dict[str, Any]:
    """Extract text using pdfminer.six."""
    try:
        from pdfminer.high_level import extract_text, extract_pages
        from pdfminer.layout import LAParams

        start_time = time.time()

        # Use LAParams for better layout analysis
        laparams = LAParams()
        full_text = extract_text(pdf_path, laparams=laparams)

        # Count pages
        page_count = sum(1 for _ in extract_pages(pdf_path))

        extraction_time = time.time() - start_time

        return {
            "success": True,
            "library": "pdfminer.six",
            "text": full_text,
            "pages": page_count,
            "chars": len(full_text),
            "time": extraction_time,
            "error": None
        }
    except ImportError:
        return {
            "success": False,
            "library": "pdfminer.six",
            "text": "",
            "pages": 0,
            "chars": 0,
            "time": 0,
            "error": "pdfminer.six not installed"
        }
    except Exception as e:
        return {
            "success": False,
            "library": "pdfminer.six",
            "text": "",
            "pages": 0,
            "chars": 0,
            "time": 0,
            "error": str(e)
        }


def check_quality(text: str) -> Dict[str, Any]:
    """
    Analyze text quality for common PDF extraction issues.

    Returns metrics about text quality:
    - spaced_chars_ratio: ratio of lines with excessive character spacing
    - avg_word_length: average word length (should be ~4-6 for English)
    - short_lines_ratio: ratio of very short lines (< 10 chars)
    """
    if not text:
        return {
            "spaced_chars_ratio": 1.0,
            "avg_word_length": 0.0,
            "short_lines_ratio": 1.0,
            "quality_score": 0.0
        }

    lines = text.split('\n')
    non_empty_lines = [line for line in lines if line.strip()]

    # Check for spaced-out characters (e.g., "S c o p e :")
    # Pattern: single char followed by space, repeated
    spaced_pattern = re.compile(r'(\b\w\s){3,}')
    spaced_lines = sum(1 for line in non_empty_lines if spaced_pattern.search(line))
    spaced_chars_ratio = spaced_lines / len(non_empty_lines) if non_empty_lines else 1.0

    # Calculate average word length
    words = text.split()
    avg_word_length = sum(len(word) for word in words) / len(words) if words else 0.0

    # Check for very short lines (possible fragmentation)
    short_lines = sum(1 for line in non_empty_lines if len(line.strip()) < 10)
    short_lines_ratio = short_lines / len(non_empty_lines) if non_empty_lines else 1.0

    # Overall quality score (0-100, higher is better)
    # Penalize: high spaced_chars_ratio, abnormal word length, high short_lines_ratio
    quality_score = 100.0
    quality_score -= spaced_chars_ratio * 50  # Spaced chars are very bad

    # Word length penalty (optimal is 4-6 chars for English)
    if avg_word_length < 2 or avg_word_length > 10:
        quality_score -= 20

    # Short lines penalty
    if short_lines_ratio > 0.5:
        quality_score -= 20

    quality_score = max(0, quality_score)

    return {
        "spaced_chars_ratio": round(spaced_chars_ratio, 3),
        "avg_word_length": round(avg_word_length, 2),
        "short_lines_ratio": round(short_lines_ratio, 3),
        "quality_score": round(quality_score, 1)
    }


def save_sample(text: str, output_path: Path, lines: int = 100):
    """Save first N lines of text for manual inspection."""
    sample_lines = text.split('\n')[:lines]
    output_path.write_text('\n'.join(sample_lines), encoding='utf-8')


def compare_tools(pdf_path: Path, output_dir: Optional[Path] = None):
    """
    Compare all PDF extraction tools on a single PDF.

    Args:
        pdf_path: Path to PDF file to test
        output_dir: Optional directory to save sample outputs
    """
    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"Testing: {pdf_path.name}")
    print(f"{'='*80}\n")

    # Run all extractors
    extractors = [
        extract_with_pypdf2,
        extract_with_pdfplumber,
        extract_with_pymupdf,
        extract_with_pdfminer,
    ]

    results = []
    for extractor in extractors:
        print(f"Testing {extractor.__name__.replace('extract_with_', '')}...", end=" ")
        result = extractor(pdf_path)

        if result["success"]:
            quality = check_quality(result["text"])
            result["quality"] = quality
            print(f"✓ {result['chars']} chars in {result['time']:.2f}s (quality: {quality['quality_score']:.1f}/100)")

            # Save sample for manual inspection
            if output_dir:
                sample_file = output_dir / f"{pdf_path.stem}_{result['library']}_sample.txt"
                save_sample(result["text"], sample_file)
        else:
            print(f"❌ {result['error']}")
            result["quality"] = None

        results.append(result)

    # Print comparison table
    print(f"\n{'='*80}")
    print(f"{'Library':<15} {'Status':<10} {'Pages':<8} {'Chars':<12} {'Time':<10} {'Quality':<10}")
    print(f"{'='*80}")

    for result in results:
        status = "✓" if result["success"] else "❌"
        quality_str = f"{result['quality']['quality_score']:.1f}/100" if result["quality"] else "N/A"
        print(
            f"{result['library']:<15} {status:<10} {result['pages']:<8} "
            f"{result['chars']:<12} {result['time']:<10.2f} {quality_str:<10}"
        )

    # Determine winner
    successful_results = [r for r in results if r["success"]]
    if successful_results:
        # Sort by quality score (descending)
        winner = max(successful_results, key=lambda r: r["quality"]["quality_score"])
        print(f"\n🏆 Winner: {winner['library']} (Quality: {winner['quality']['quality_score']:.1f}/100)")

        # Show quality details for winner
        print(f"\nQuality metrics for {winner['library']}:")
        print(f"  - Spaced characters: {winner['quality']['spaced_chars_ratio']*100:.1f}%")
        print(f"  - Avg word length: {winner['quality']['avg_word_length']:.1f} chars")
        print(f"  - Short lines: {winner['quality']['short_lines_ratio']*100:.1f}%")


def main():
    """Run comparison on both test PDFs."""
    # Set up paths
    project_root = Path(__file__).parent.parent
    inputs_dir = project_root / "inputs"
    outputs_dir = project_root / "comparison_outputs"

    # Test PDFs
    test_pdfs = [
        inputs_dir / "test-doc.pdf",  # SOC2 report
        inputs_dir / "[ADR - #0085] - Declaring Ownership of Datasets at Block.pdf",  # Google Docs ADR
    ]

    # Check which PDFs exist
    available_pdfs = [pdf for pdf in test_pdfs if pdf.exists()]

    if not available_pdfs:
        print("❌ No test PDFs found. Expected files:")
        for pdf in test_pdfs:
            print(f"  - {pdf}")
        return 1

    print("PDF Extraction Library Comparison")
    print("=" * 80)
    print("\nTesting libraries:")
    print("  1. PyPDF2 (current)")
    print("  2. pdfplumber")
    print("  3. PyMuPDF (fitz)")
    print("  4. pdfminer.six")
    print("\n" + "=" * 80)

    # Run comparison on each PDF
    for pdf_path in available_pdfs:
        compare_tools(pdf_path, outputs_dir)

    print(f"\n{'='*80}")
    print(f"Sample outputs saved to: {outputs_dir}")
    print(f"{'='*80}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
