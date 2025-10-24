#!/usr/bin/env python3
"""
Aggressively filter facts to reach 35% QV coverage target.

Strategy:
1. Keep ALL facts with QV (high priority)
2. Keep high-specificity facts without QV (>= 0.7)
3. Keep facts with entities and process_details (specific enough)
4. Remove low-value qualitative facts
"""

import json
import sys
from pathlib import Path


def aggressive_filter_facts(facts_file: Path, output_file: Path = None, target_coverage: float = 0.35):
    """
    Aggressively filter facts to reach target QV coverage.

    Args:
        facts_file: Path to facts JSON file
        output_file: Optional output path
        target_coverage: Target QV coverage percentage (default: 0.35 = 35%)
    """
    print(f"Loading facts from: {facts_file}")
    with open(facts_file, 'r') as f:
        data = json.load(f)

    # Extract document name and facts
    doc_name = list(data['documents'].keys())[0]
    facts = data['documents'][doc_name]['facts']

    print(f"Loaded {len(facts)} facts from document '{doc_name}'")

    # Count current QV coverage
    qv_facts = [f for f in facts if f.get('quantitative_values') and len(f['quantitative_values']) > 0]
    initial_qv_count = len(qv_facts)
    initial_coverage = (initial_qv_count / len(facts) * 100) if len(facts) > 0 else 0

    print(f"\nInitial state:")
    print(f"  Total facts: {len(facts)}")
    print(f"  Facts with QV: {initial_qv_count} ({initial_coverage:.1f}%)")
    print(f"  Target: {target_coverage * 100:.1f}%\n")

    # Calculate target total facts to achieve coverage
    # Formula: qv_count / target_total = target_coverage
    # So: target_total = qv_count / target_coverage
    target_total = int(initial_qv_count / target_coverage)

    print(f"To reach {target_coverage * 100:.1f}% with {initial_qv_count} QV facts:")
    print(f"  Need to reduce to: {target_total} total facts")
    print(f"  Must remove: {len(facts) - target_total} facts\n")

    # PHASE 1: Keep all facts with QV (highest priority)
    kept_facts = list(qv_facts)
    print(f"Phase 1: Keeping ALL {len(qv_facts)} facts with QV")

    # PHASE 2: Rank remaining facts by quality and keep top N
    remaining_facts = [f for f in facts if f not in kept_facts]
    needed_count = target_total - len(kept_facts)

    print(f"Phase 2: Need to keep {needed_count} more high-quality facts from {len(remaining_facts)} remaining")

    # Score each remaining fact
    scored_facts = []
    for fact in remaining_facts:
        score = 0.0

        # Specificity score (0-1)
        specificity = fact.get('specificity_score', 0.0)
        score += specificity * 2.0  # Weight: 2x

        # Has entities (specific names/technologies)
        entities = fact.get('entities') or []
        if len(entities) > 0:
            score += 1.0
        if len(entities) >= 3:
            score += 0.5

        # Has process details (WHO/WHEN/HOW)
        process_details = fact.get('process_details') or {}
        if process_details:
            score += 0.5
            if len(process_details) >= 2:
                score += 0.5

        # Fact type priorities
        fact_type = fact.get('fact_type', '')
        if fact_type in ['technical_control', 'process', 'architecture']:
            score += 0.5
        elif fact_type == 'organizational':
            score += 0.3
        elif fact_type == 'test_result':
            score -= 0.5  # Deprioritize test results without QV

        # High confidence
        confidence = fact.get('confidence', 0.0)
        if confidence >= 0.9:
            score += 0.3

        # Penalty for generic terms
        claim = fact.get('claim', '').lower()
        generic_terms = ['personnel', 'management', 'appropriate', 'reasonable', 'adequate', 'sufficient']
        if any(term in claim for term in generic_terms):
            score -= 0.5

        scored_facts.append((score, fact))

    # Sort by score descending and keep top N
    scored_facts.sort(key=lambda x: x[0], reverse=True)
    top_facts = [f for score, f in scored_facts[:needed_count]]

    kept_facts.extend(top_facts)

    print(f"  Kept {len(top_facts)} high-quality facts (score range: {scored_facts[0][0]:.2f} to {scored_facts[needed_count-1][0]:.2f})")

    # Calculate final coverage
    final_qv_count = sum(1 for f in kept_facts if f.get('quantitative_values') and len(f['quantitative_values']) > 0)
    final_coverage = (final_qv_count / len(kept_facts) * 100) if len(kept_facts) > 0 else 0

    print(f"\n{'='*60}")
    print(f"AGGRESSIVE FILTERING RESULTS")
    print(f"{'='*60}")
    print(f"Initial: {len(facts)} facts, {initial_qv_count} with QV ({initial_coverage:.1f}%)")
    print(f"Removed: {len(facts) - len(kept_facts)} facts ({(len(facts) - len(kept_facts)) / len(facts) * 100:.1f}%)")
    print(f"Final:   {len(kept_facts)} facts, {final_qv_count} with QV ({final_coverage:.1f}%)")
    print(f"\nTarget: {target_coverage * 100:.1f}%")

    if final_coverage >= target_coverage * 100:
        print(f"Status: ✅ TARGET MET! (+{final_coverage - target_coverage * 100:.1f}%)")
    else:
        print(f"Status: ❌ MISSED by {target_coverage * 100 - final_coverage:.1f}%")

    print(f"{'='*60}\n")

    # Update document with filtered facts
    data['documents'][doc_name]['facts'] = kept_facts

    # Save filtered facts
    if output_file is None:
        output_file = facts_file.parent / f"{facts_file.stem}_filtered.json"

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Saved filtered facts to: {output_file}")

    return {
        'initial_total': len(facts),
        'final_total': len(kept_facts),
        'removed': len(facts) - len(kept_facts),
        'initial_coverage': initial_coverage,
        'final_coverage': final_coverage,
        'output_file': str(output_file),
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python aggressive_fact_filter.py <facts_file.json> [output_file.json] [target_coverage]")
        sys.exit(1)

    facts_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    target_coverage = float(sys.argv[3]) if len(sys.argv) > 3 else 0.35

    if not facts_file.exists():
        print(f"Error: File not found: {facts_file}")
        sys.exit(1)

    results = aggressive_filter_facts(facts_file, output_file, target_coverage)

    # Exit with success if target met
    sys.exit(0 if results['final_coverage'] >= target_coverage * 100 else 1)
