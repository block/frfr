#!/usr/bin/env python3
"""Test multi-quote extraction improvements."""

import sys
import os
from pathlib import Path

# Add frfr to path
sys.path.insert(0, os.path.dirname(__file__))

from frfr.extraction.fact_extractor import FactExtractor
from frfr.session import Session

def test_multiquote_extraction():
    """Test that facts now use multiple quotes more frequently."""
    print("🔍 Testing Multi-Quote Extraction Improvements\n")

    # Use test file with multi-quote opportunities
    text_file = Path("output/test_multiquote.txt")
    if not text_file.exists():
        print(f"✗ Test file not found: {text_file}")
        return False

    print(f"✓ Test file found: {text_file}")
    print(f"  Size: {text_file.stat().st_size:,} bytes\n")

    # Create session
    session = Session(base_dir=".frfr_sessions")
    print(f"✓ Session created: {session.session_id}\n")

    # Create extractor
    extractor = FactExtractor(
        chunk_size=50,
        overlap_size=10,
    )

    # Run extraction
    try:
        print("🚀 Running extraction...\n")

        result = extractor.extract_from_document(
            text_file=text_file,
            document_name="test_multiquote",
            session=session,
        )

        # Analyze results
        print("✅ Extraction complete!\n")
        print(f"Total facts extracted: {len(result.facts)}\n")

        # Count single vs multi-quote facts
        single_quote_facts = []
        multi_quote_facts = []

        for fact in result.facts:
            # Check if fact uses V5 multi-quote format
            if fact.evidence_quotes and len(fact.evidence_quotes) > 1:
                multi_quote_facts.append(fact)
            else:
                single_quote_facts.append(fact)

        total = len(result.facts)
        multi_count = len(multi_quote_facts)
        single_count = len(single_quote_facts)
        multi_percentage = (multi_count / total * 100) if total > 0 else 0

        print("📊 RESULTS:")
        print(f"   Single-quote facts: {single_count} ({single_count/total*100:.1f}%)")
        print(f"   Multi-quote facts:  {multi_count} ({multi_percentage:.1f}%)")
        print()

        # Show multi-quote examples
        if multi_quote_facts:
            print(f"✨ Multi-Quote Examples ({min(3, len(multi_quote_facts))} of {len(multi_quote_facts)}):\n")
            for i, fact in enumerate(multi_quote_facts[:3], 1):
                print(f"{i}. CLAIM: {fact.claim}")
                print(f"   QUOTES ({len(fact.evidence_quotes)}):")
                for j, quote in enumerate(fact.evidence_quotes, 1):
                    preview = quote.quote[:100] + "..." if len(quote.quote) > 100 else quote.quote
                    relevance = f" [{quote.relevance}]" if quote.relevance else ""
                    print(f"     {j}. \"{preview}\"{relevance}")
                print()
        else:
            print("⚠️  No multi-quote facts found - prompt changes may not be effective\n")

        # Show single-quote examples for comparison
        if single_quote_facts:
            print(f"📝 Single-Quote Examples ({min(2, len(single_quote_facts))} of {len(single_quote_facts)}):\n")
            for i, fact in enumerate(single_quote_facts[:2], 1):
                print(f"{i}. CLAIM: {fact.claim}")
                evidence = fact.evidence_quotes[0].quote if fact.evidence_quotes else fact.evidence_quote
                preview = evidence[:100] + "..." if len(evidence) > 100 else evidence
                print(f"   QUOTE: \"{preview}\"")
                print()

        # Success criteria
        if multi_percentage >= 15:
            print(f"✅ SUCCESS: {multi_percentage:.1f}% of facts use multiple quotes (target: 15%+)")
            return True
        elif multi_percentage > 0:
            print(f"⚠️  PARTIAL: {multi_percentage:.1f}% of facts use multiple quotes (target: 15%+)")
            print("    Prompt changes are working but could be more aggressive")
            return True
        else:
            print("❌ FAILURE: No facts use multiple quotes")
            print("    Prompt changes appear ineffective")
            return False

    except Exception as e:
        print(f"\n✗ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_multiquote_extraction()
    sys.exit(0 if success else 1)
