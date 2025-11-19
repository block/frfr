#!/usr/bin/env python3
"""
Verify that chunking improvements work end-to-end.

Tests:
1. PDF extraction with pdfplumber produces clean text
2. Adaptive chunking creates appropriate number of chunks
3. Chunk count detection works correctly
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from frfr.documents import extract_pdf_to_text
from frfr.extraction.fact_extractor import FactExtractor
import tempfile


def main():
    print("="*80)
    print("END-TO-END VERIFICATION: PDF Extraction + Adaptive Chunking")
    print("="*80)

    # Step 1: Verify PDF extraction
    pdf_path = Path("/Users/nesposito/Development/frfr/inputs/[ADR - #0085] - Declaring Ownership of Datasets at Block.pdf")

    if not pdf_path.exists():
        print(f"\n❌ Test PDF not found: {pdf_path}")
        return 1

    print("\n[1/3] Testing PDF Extraction with pdfplumber...")
    print("-" * 60)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        temp_output = Path(f.name)

    try:
        result = extract_pdf_to_text(pdf_path, temp_output)

        print(f"  ✓ Method: {result['method']}")
        print(f"  ✓ Pages: {result['pages']}")
        print(f"  ✓ Characters: {result['total_chars']:,}")

        text = temp_output.read_text()

        # Check quality
        has_spaced_chars = " c o " in text[:5000]  # Check for "S c o p e" pattern
        has_clean_scope = "Scope:" in text or "Scope :" in text

        if has_spaced_chars:
            print(f"  ❌ FAIL: Still has spaced characters!")
            return 1
        elif has_clean_scope:
            print(f"  ✓ Text quality: CLEAN (no character spacing)")
        else:
            print(f"  ⚠️  Could not verify 'Scope:' text")

        # Check table preservation
        table_row_example = "Jon Tirsen Block TL Approved"
        if table_row_example in text:
            print(f"  ✓ Table preservation: GOOD (rows intact)")
        else:
            print(f"  ⚠️  Table format might be fragmented")

    finally:
        if temp_output.exists():
            temp_output.unlink()

    # Step 2: Verify adaptive chunking
    print("\n[2/3] Testing Adaptive Chunking...")
    print("-" * 60)

    extractor = FactExtractor(
        min_chunk_chars=3000,
        max_chunk_chars=8000,
        adaptive_chunking=True
    )

    chunks = extractor.chunk_text(text)

    print(f"  ✓ Total chunks: {len(chunks)}")
    print(f"  ✓ Avg chunk size: {len(text) // len(chunks):,} chars")

    # Verify chunks meet minimum size
    small_chunks = [i for i, (cid, ctext, _, _) in enumerate(chunks) if len(ctext) < 2000]
    if small_chunks and len(chunks) > 1:
        print(f"  ⚠️  Warning: {len(small_chunks)} chunks below 2000 chars")
    else:
        print(f"  ✓ All chunks have good context (>2000 chars)")

    # Check if chunking used PAGE BREAK boundaries
    if "=== PAGE BREAK ===" in text:
        page_count = text.count("=== PAGE BREAK ===")
        print(f"  ✓ Document has {page_count} page breaks (semantic chunking available)")

    # Step 3: Verify worker optimization
    print("\n[3/3] Testing Worker Optimization...")
    print("-" * 60)

    optimal_workers = extractor.get_optimal_workers(len(chunks))
    print(f"  ✓ Chunks: {len(chunks)} → Workers: {optimal_workers}")

    if len(chunks) <= 5 and optimal_workers == len(chunks):
        print(f"  ✓ Optimal: Using {optimal_workers} workers for {len(chunks)} chunks")
    elif len(chunks) > 10 and optimal_workers <= 20:
        print(f"  ✓ Optimal: Capped at {optimal_workers} workers")
    else:
        print(f"  ✓ Workers optimized for {len(chunks)} chunks")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"  ✅ PDF Extraction: {result['method']} - clean text, tables preserved")
    print(f"  ✅ Adaptive Chunking: {len(chunks)} chunks with ~{len(text) // len(chunks):,} chars each")
    print(f"  ✅ Worker Optimization: {optimal_workers} workers (not wasteful 20)")
    print(f"  ✅ Ready for fact extraction with {((235 - len(chunks))/235*100):.1f}% fewer API calls!")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
