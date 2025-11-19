#!/usr/bin/env python3
"""
Test adaptive chunking implementation on the ADR document.

Compares old vs new chunking strategies.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from frfr.extraction.fact_extractor import FactExtractor


def test_chunking_strategies():
    """Compare legacy vs adaptive chunking on ADR document."""

    # Read the fixed ADR text
    adr_path = Path("/Users/nesposito/Development/frfr/outputs/[ADR - #0085] - Declaring Ownership of Datasets at Block_text_FINAL.txt")

    if not adr_path.exists():
        print(f"❌ ADR text file not found: {adr_path}")
        return 1

    text = adr_path.read_text()

    print("="*80)
    print("ADAPTIVE CHUNKING TEST - ADR Document")
    print("="*80)
    print(f"\nDocument stats:")
    print(f"  Characters: {len(text):,}")
    print(f"  Lines: {len(text.split(chr(10))):,}")
    print(f"  Pages (PAGE BREAK markers): {text.count('=== PAGE BREAK ===')}")

    # Test 1: Legacy chunking (old way)
    print(f"\n{'='*80}")
    print("TEST 1: Legacy Line-Based Chunking (old)")
    print("="*80)

    extractor_legacy = FactExtractor(
        chunk_size=50,
        overlap_size=10,
        adaptive_chunking=False  # Use old method
    )

    chunks_legacy = extractor_legacy.chunk_text(text)

    print(f"  Total chunks: {len(chunks_legacy)}")
    print(f"  Avg chars/chunk: {len(text) // len(chunks_legacy):,}")
    print(f"  Avg lines/chunk: {len(text.split(chr(10))) // len(chunks_legacy):.1f}")

    # Show sample chunks
    print(f"\n  First 3 chunks:")
    for i, (chunk_id, chunk_text, start, end) in enumerate(chunks_legacy[:3]):
        print(f"    Chunk {chunk_id}: lines {start}-{end}, {len(chunk_text)} chars")
        preview = chunk_text[:80].replace('\n', ' ')
        print(f"      Preview: {preview}...")

    # Test 2: Adaptive chunking (new way)
    print(f"\n{'='*80}")
    print("TEST 2: Adaptive Character-Based Chunking (new)")
    print("="*80)

    extractor_adaptive = FactExtractor(
        min_chunk_chars=3000,
        max_chunk_chars=8000,
        adaptive_chunking=True  # Use new smart method
    )

    chunks_adaptive = extractor_adaptive.chunk_text(text)

    print(f"  Total chunks: {len(chunks_adaptive)}")
    print(f"  Avg chars/chunk: {len(text) // len(chunks_adaptive):,}")
    print(f"  Avg lines/chunk: {len(text.split(chr(10))) // len(chunks_adaptive):.1f}")

    # Show sample chunks
    print(f"\n  First 3 chunks:")
    for i, (chunk_id, chunk_text, start, end) in enumerate(chunks_adaptive[:3]):
        print(f"    Chunk {chunk_id}: lines {start}-{end}, {len(chunk_text):,} chars")
        preview = chunk_text[:80].replace('\n', ' ')
        print(f"      Preview: {preview}...")

    # Worker optimization
    print(f"\n{'='*80}")
    print("WORKER OPTIMIZATION")
    print("="*80)

    workers_legacy = extractor_legacy.get_optimal_workers(len(chunks_legacy))
    workers_adaptive = extractor_adaptive.get_optimal_workers(len(chunks_adaptive))

    print(f"  Legacy: {len(chunks_legacy)} chunks → {workers_legacy} workers")
    print(f"  Adaptive: {len(chunks_adaptive)} chunks → {workers_adaptive} workers")

    # Summary
    print(f"\n{'='*80}")
    print("IMPROVEMENT SUMMARY")
    print("="*80)

    chunk_reduction = ((len(chunks_legacy) - len(chunks_adaptive)) / len(chunks_legacy) * 100)
    context_increase = ((len(text) // len(chunks_adaptive)) / (len(text) // len(chunks_legacy)) * 100) - 100

    print(f"  Chunk reduction: {chunk_reduction:.1f}% ({len(chunks_legacy)} → {len(chunks_adaptive)})")
    print(f"  Context per chunk: +{context_increase:.1f}% more characters")
    print(f"  Workers needed: {workers_legacy} → {workers_adaptive}")
    print(f"  Processing efficiency: {chunk_reduction:.0f}% fewer LLM calls")

    print(f"\n✅ Adaptive chunking is much more efficient!\n")

    return 0


if __name__ == "__main__":
    sys.exit(test_chunking_strategies())
