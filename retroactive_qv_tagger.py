#!/usr/bin/env python3
"""
Retroactively tag quantitative values in existing facts.

This script scans fact claims for quantitative patterns and adds them to the
quantitative_values metadata field if not already present.
"""

import json
import sys
from pathlib import Path
from frfr.extraction.extraction_patterns import ExtractionPatterns


def retroactive_tag_qv(facts_file: Path, output_file: Path = None):
    """
    Retroactively tag quantitative values in facts.

    Args:
        facts_file: Path to facts JSON file
        output_file: Optional output path (defaults to same file with _qv_tagged suffix)
    """
    print(f"Loading facts from: {facts_file}")
    with open(facts_file, 'r') as f:
        data = json.load(f)

    # Extract document name and facts
    doc_name = list(data['documents'].keys())[0]
    facts = data['documents'][doc_name]['facts']

    print(f"Loaded {len(facts)} facts from document '{doc_name}'")

    # Count current QV coverage
    initial_qv_count = sum(1 for f in facts if f.get('quantitative_values') and len(f['quantitative_values']) > 0)
    initial_coverage = (initial_qv_count / len(facts) * 100) if len(facts) > 0 else 0

    print(f"\nInitial QV coverage: {initial_coverage:.1f}% ({initial_qv_count}/{len(facts)})")
    print(f"Target: 35.0%")
    print(f"Gap: {35.0 - initial_coverage:.1f}%\n")

    # Process each fact
    tagged_count = 0
    qv_added_count = 0

    for i, fact in enumerate(facts):
        claim = fact.get('claim', '')
        existing_qv = set(fact.get('quantitative_values', []))

        # Extract quantitative values from claim text
        extracted_qv = ExtractionPatterns.extract_all_quantitative(claim)

        # Add new QV that aren't already present
        new_qv = []
        for qv in extracted_qv:
            if qv.value not in existing_qv:
                new_qv.append(qv.value)
                qv_added_count += 1

        if new_qv:
            # Update the fact's quantitative_values
            all_qv = list(existing_qv) + new_qv
            fact['quantitative_values'] = all_qv
            tagged_count += 1

            if i < 10:  # Show first 10 examples
                print(f"  [{i}] Tagged: {claim[:80]}...")
                print(f"       Added: {', '.join(new_qv)}")

    # Calculate new coverage
    final_qv_count = sum(1 for f in facts if f.get('quantitative_values') and len(f['quantitative_values']) > 0)
    final_coverage = (final_qv_count / len(facts) * 100) if len(facts) > 0 else 0

    print(f"\n{'='*60}")
    print(f"RETROACTIVE QV TAGGING RESULTS")
    print(f"{'='*60}")
    print(f"Facts updated: {tagged_count}")
    print(f"QV values added: {qv_added_count}")
    print(f"\nInitial coverage: {initial_coverage:.1f}% ({initial_qv_count}/{len(facts)})")
    print(f"Final coverage:   {final_coverage:.1f}% ({final_qv_count}/{len(facts)})")
    print(f"Improvement:      +{final_coverage - initial_coverage:.1f}%")
    print(f"\nTarget: 35.0%")

    if final_coverage >= 35.0:
        print(f"Status: ✅ TARGET MET! (+{final_coverage - 35.0:.1f}%)")
    else:
        print(f"Status: ❌ MISSED by {35.0 - final_coverage:.1f}%")

    print(f"{'='*60}\n")

    # Save updated facts
    if output_file is None:
        output_file = facts_file.parent / f"{facts_file.stem}_qv_tagged.json"

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Saved updated facts to: {output_file}")

    return {
        'initial_coverage': initial_coverage,
        'final_coverage': final_coverage,
        'facts_updated': tagged_count,
        'qv_added': qv_added_count,
        'output_file': str(output_file),
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python retroactive_qv_tagger.py <facts_file.json> [output_file.json]")
        sys.exit(1)

    facts_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    if not facts_file.exists():
        print(f"Error: File not found: {facts_file}")
        sys.exit(1)

    results = retroactive_tag_qv(facts_file, output_file)

    # Exit with success if target met
    sys.exit(0 if results['final_coverage'] >= 35.0 else 1)
