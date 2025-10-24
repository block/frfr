#!/usr/bin/env python3
"""
Example: PDF Text Extraction

This example demonstrates how to use the frfr PDF extraction API
to convert PDFs to clean text files.
"""

from pathlib import Path
from frfr.documents import extract_pdf_to_text, get_pdf_info


def main():
    # Example PDF path (adjust to your file)
    pdf_path = Path("/app/documents/test-doc.pdf")
    output_path = Path("/app/output/example_extraction.txt")

    print("=" * 60)
    print("PDF Text Extraction Example")
    print("=" * 60)
    print()

    # Step 1: Get PDF information
    print("Step 1: Getting PDF metadata...")
    try:
        info = get_pdf_info(pdf_path)
        print(f"  ✓ PDF found")
        print(f"    Pages: {info['pages']}")
        print(f"    Encrypted: {info['is_encrypted']}")
        print(f"    Size: {info['file_size']:,} bytes")
        print()
    except FileNotFoundError:
        print(f"  ✗ PDF not found: {pdf_path}")
        print("  Place a PDF in the documents/ directory first.")
        return

    # Step 2: Extract text
    print("Step 2: Extracting text...")
    result = extract_pdf_to_text(
        pdf_path=pdf_path,
        output_path=output_path
    )

    print(f"  ✓ Extraction complete!")
    print(f"    Method: {result['method']}")
    print(f"    Pages processed: {result['pages']}")
    print(f"    Total characters: {result['total_chars']:,}")
    print(f"    Output file: {result['output_file']}")
    print()

    # Step 3: Preview extracted text
    print("Step 3: Preview (first 500 characters)...")
    with open(output_path, 'r') as f:
        preview = f.read(500)
        print("-" * 60)
        print(preview)
        print("-" * 60)
        print()

    # Success
    print("=" * 60)
    print("✅ Example complete!")
    print("=" * 60)
    print()
    print(f"Full text available at: {output_path}")
    print()
    print("Next steps:")
    print("  - Use this text as input for LLM processing")
    print("  - Feed into the swarm consensus pipeline")
    print("  - Process with semantic embeddings")


if __name__ == "__main__":
    main()
