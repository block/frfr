#!/usr/bin/env python3
"""
Analyze V4.2 results and compare to V3 baseline.
"""

import json
from pathlib import Path

def count_lines(text_file: Path) -> int:
    """Count lines in source text file."""
    with open(text_file, 'r') as f:
        return len(f.readlines())

def analyze_facts(facts_file: Path) -> dict:
    """Analyze facts from JSON file."""
    with open(facts_file, 'r') as f:
        data = json.load(f)

    # Get all facts
    all_facts = []
    for doc_name, doc_data in data.get('documents', {}).items():
        facts = doc_data.get('facts', [])
        all_facts.extend(facts)

    # Count facts with quantitative values
    qv_facts = [f for f in all_facts if f.get('quantitative_values') and len(f['quantitative_values']) > 0]

    # Count specificity levels
    high_specificity = [f for f in all_facts if f.get('specificity_score', 0) >= 0.7]
    medium_specificity = [f for f in all_facts if 0.5 <= f.get('specificity_score', 0) < 0.7]
    low_specificity = [f for f in all_facts if f.get('specificity_score', 0) < 0.5]

    # Count facts with entity metadata
    entity_facts = [f for f in all_facts if f.get('entities') and len(f['entities']) > 0]

    # Count facts with process details
    process_facts = [f for f in all_facts if f.get('process_details') and len(f['process_details']) > 0]

    # Average specificity
    avg_specificity = sum(f.get('specificity_score', 0) for f in all_facts) / len(all_facts) if all_facts else 0

    return {
        'total_facts': len(all_facts),
        'qv_facts': len(qv_facts),
        'qv_coverage': len(qv_facts) / len(all_facts) if all_facts else 0,
        'high_specificity': len(high_specificity),
        'medium_specificity': len(medium_specificity),
        'low_specificity': len(low_specificity),
        'avg_specificity': avg_specificity,
        'entity_facts': len(entity_facts),
        'entity_coverage': len(entity_facts) / len(all_facts) if all_facts else 0,
        'process_facts': len(process_facts),
        'process_coverage': len(process_facts) / len(all_facts) if all_facts else 0,
    }

def main():
    # File paths
    v3_file = Path('output/lexisnexis_soc2_v3_facts.json')
    v4_2_file = Path('output/lexisnexis_soc2_v4_2_facts.json')
    source_file = Path('output/soc2_full_extraction.txt')

    # Count lines
    total_lines = count_lines(source_file)

    # Analyze V3
    print("=== Analyzing V3 Baseline ===")
    v3_stats = analyze_facts(v3_file)
    v3_density = (v3_stats['total_facts'] / total_lines) * 100

    print(f"Total facts: {v3_stats['total_facts']}")
    print(f"Facts per 100 lines: {v3_density:.2f}")
    print(f"QV coverage: {v3_stats['qv_coverage']:.1%} ({v3_stats['qv_facts']} facts)")
    print(f"Avg specificity: {v3_stats['avg_specificity']:.3f}")
    print(f"Entity coverage: {v3_stats['entity_coverage']:.1%}")
    print(f"Process coverage: {v3_stats['process_coverage']:.1%}")
    print()

    # Analyze V4.2
    print("=== Analyzing V4.2 ===")
    v4_2_stats = analyze_facts(v4_2_file)
    v4_2_density = (v4_2_stats['total_facts'] / total_lines) * 100

    print(f"Total facts: {v4_2_stats['total_facts']}")
    print(f"Facts per 100 lines: {v4_2_density:.2f}")
    print(f"QV coverage: {v4_2_stats['qv_coverage']:.1%} ({v4_2_stats['qv_facts']} facts)")
    print(f"Avg specificity: {v4_2_stats['avg_specificity']:.3f}")
    print(f"Entity coverage: {v4_2_stats['entity_coverage']:.1%}")
    print(f"Process coverage: {v4_2_stats['process_coverage']:.1%}")
    print()

    # Compare
    print("=== V4.2 vs V3 Comparison ===")
    fact_change = v4_2_stats['total_facts'] - v3_stats['total_facts']
    fact_change_pct = (fact_change / v3_stats['total_facts']) * 100 if v3_stats['total_facts'] else 0
    print(f"Facts: {fact_change:+d} ({fact_change_pct:+.1f}%)")

    density_change = v4_2_density - v3_density
    print(f"Density: {density_change:+.2f} per 100 lines")

    qv_change = v4_2_stats['qv_coverage'] - v3_stats['qv_coverage']
    qv_fact_change = v4_2_stats['qv_facts'] - v3_stats['qv_facts']
    print(f"QV coverage: {qv_change:+.1%} ({qv_fact_change:+d} facts)")

    spec_change = v4_2_stats['avg_specificity'] - v3_stats['avg_specificity']
    print(f"Specificity: {spec_change:+.3f}")

    print()
    print("=== Target Assessment ===")
    print(f"✅ = met target, ❌ = below target, ⚠️ = close")
    print()

    # Fact density target: 8-12 per 100 lines
    density_status = "✅" if 8 <= v4_2_density <= 12 else "❌"
    print(f"{density_status} Fact density: {v4_2_density:.2f} per 100 lines (target: 8-12)")

    # QV coverage target: 35%+
    qv_status = "✅" if v4_2_stats['qv_coverage'] >= 0.35 else "⚠️" if v4_2_stats['qv_coverage'] >= 0.30 else "❌"
    qv_gap = 0.35 - v4_2_stats['qv_coverage']
    print(f"{qv_status} QV coverage: {v4_2_stats['qv_coverage']:.1%} (target: 35%+, gap: {qv_gap:.1%})")

    # Specificity target: 0.70+
    spec_status = "✅" if v4_2_stats['avg_specificity'] >= 0.70 else "⚠️" if v4_2_stats['avg_specificity'] >= 0.65 else "❌"
    print(f"{spec_status} Avg specificity: {v4_2_stats['avg_specificity']:.3f} (target: 0.70+)")

    # Entity coverage target: 40%+
    entity_status = "✅" if v4_2_stats['entity_coverage'] >= 0.40 else "⚠️" if v4_2_stats['entity_coverage'] >= 0.35 else "❌"
    print(f"{entity_status} Entity coverage: {v4_2_stats['entity_coverage']:.1%} (target: 40%+)")

    # Process coverage target: 40%+
    process_status = "✅" if v4_2_stats['process_coverage'] >= 0.40 else "⚠️" if v4_2_stats['process_coverage'] >= 0.35 else "❌"
    print(f"{process_status} Process coverage: {v4_2_stats['process_coverage']:.1%} (target: 40%+)")

if __name__ == '__main__':
    main()
