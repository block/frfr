#!/usr/bin/env python3
"""Minimal test of fact extraction pipeline."""

import sys
import os
import json
from pathlib import Path

# Add frfr to path
sys.path.insert(0, os.path.dirname(__file__))

from frfr.extraction.fact_extractor import FactExtractor
from frfr.session import Session

def test_fact_extraction():
    """Test the full fact extraction pipeline."""
    print("🔍 Testing Fact Extraction Pipeline\n")

    # Use test file
    text_file = Path("output/test_sample_100lines.txt")
    if not text_file.exists():
        print(f"✗ Test file not found: {text_file}")
        return False

    print(f"✓ Test file found: {text_file}")
    print(f"  Size: {text_file.stat().st_size:,} bytes\n")

    # Create session
    session = Session(base_dir=".frfr_sessions")
    print(f"✓ Session created: {session.session_id}")
    print(f"  Directory: {session.session_dir}\n")

    # Create extractor with small chunks for testing
    print("✓ Initializing FactExtractor")
    print("  Chunk size: 50 lines")
    print("  Overlap: 10 lines\n")

    extractor = FactExtractor(
        chunk_size=50,
        overlap_size=10,
    )

    # Run extraction
    try:
        print("🚀 Running extraction...\n")

        result = extractor.extract_from_document(
            text_file=text_file,
            document_name="test_sample",
            session=session,
        )

        # Display results
        print("\n✅ Extraction complete!\n")
        print(f"Total facts extracted: {len(result.facts)}")
        print(f"Model used: {result.model_used}\n")

        # Show first few facts
        if result.facts:
            print("Sample Facts (first 3):\n")
            for i, fact in enumerate(result.facts[:3], 1):
                print(f"{i}. {fact.claim}")
                print(f"   Location: {fact.source_location}")
                print(f"   Confidence: {fact.confidence:.2f}")
                print(f"   Evidence: \"{fact.evidence_quote[:80]}...\"")
                print()

        # Show session stats
        stats = session.get_stats()
        print(f"Session directory: {stats['session_dir']}")
        print(f"Total chunks processed: {stats['total_chunks']}")
        print(f"Total fact files: {stats['total_fact_files']}")

        return True

    except Exception as e:
        print(f"\n✗ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_fact_extraction()
    sys.exit(0 if success else 1)
