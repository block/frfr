"""
Test script to demonstrate enhanced fact recovery on real data.
"""

import json
from pathlib import Path
from frfr.validation.fact_validator import FactValidator
from frfr.extraction.claude_client import ClaudeClient
import os

def load_facts_from_chunks(facts_dir: Path, max_chunks=10):
    """Load facts from chunk files."""
    all_facts = []
    chunk_files = sorted(facts_dir.glob("*_chunk_*.json"))[:max_chunks]

    for chunk_file in chunk_files:
        with open(chunk_file, 'r') as f:
            facts = json.load(f)
            all_facts.extend(facts)

    return all_facts


def test_validation_with_enhanced_recovery():
    """Test validation with enhanced recovery features."""

    print("=" * 70)
    print("Enhanced Fact Recovery - Validation Test")
    print("=" * 70)

    # Paths
    session_dir = Path(".frfr_sessions/sess_lexisnexis_soc2_assessment_20251106_195621")
    facts_dir = session_dir / "facts"
    text_file = Path("outputs/LexisNexis-SOC2-BusSvc-Full_text.txt")

    # Check if files exist
    if not text_file.exists():
        print(f"\n❌ Text file not found: {text_file}")
        print("   Please ensure the document text file exists.")
        return

    if not facts_dir.exists():
        print(f"\n❌ Facts directory not found: {facts_dir}")
        return

    print(f"\n📁 Session: {session_dir.name}")
    print(f"📄 Text file: {text_file}")
    print(f"📊 Facts directory: {facts_dir}")

    # Load facts
    print("\n🔍 Loading facts from chunks...")
    facts = load_facts_from_chunks(facts_dir, max_chunks=5)  # Start with 5 chunks
    print(f"   Loaded {len(facts)} facts from first 5 chunks")

    # Initialize validator
    # Check if we have Claude API key for full recovery testing
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        print("\n🤖 Claude API key found - full recovery testing enabled")
        claude_client = ClaudeClient(api_key)
    else:
        print("\n⚠️  No Claude API key - testing without LLM recovery")
        print("   (Fuzzy matching and multi-quote will still be demonstrated)")
        claude_client = None

    validator = FactValidator(text_file, claude_client=claude_client)

    # Validate facts
    print("\n🔬 Validating facts with enhanced recovery...")
    print("-" * 70)

    results = []
    for i, fact in enumerate(facts):
        if i < 10:  # Show first 10 for brevity
            claim = fact.get("claim", "")[:60]
            print(f"\n[{i+1}/{len(facts)}] {claim}...")

        result = validator.validate_fact(fact, i)
        results.append(result)

        if i < 10:
            if result.is_valid:
                if result.was_recovered:
                    recovery_info = f" (recovered via {result.recovery_method})"
                    print(f"   ✅ Valid{recovery_info}")
                else:
                    print(f"   ✅ Valid")
            else:
                error = result.error_message[:50]
                if result.is_near_match:
                    print(f"   ⚠️  Near match failed: {error}")
                else:
                    print(f"   ❌ Invalid: {error}")

    if len(facts) > 10:
        print(f"\n   ... validating remaining {len(facts) - 10} facts ...")

    # Calculate statistics
    print("\n" + "=" * 70)
    print("📊 Validation Results")
    print("=" * 70)

    total = len(results)
    valid = sum(1 for r in results if r.is_valid)
    invalid = total - valid

    # Recovery stats
    recovered = sum(1 for r in results if r.is_valid and r.was_recovered)
    near_match_failed = sum(1 for r in results if not r.is_valid and r.is_near_match)

    # Recovery method breakdown
    recovery_methods = {}
    for r in results:
        if r.was_recovered and r.recovery_method:
            recovery_methods[r.recovery_method] = recovery_methods.get(r.recovery_method, 0) + 1

    print(f"\n✅ Valid facts: {valid}/{total} ({valid/total*100:.1f}%)")
    print(f"❌ Invalid facts: {invalid}/{total} ({invalid/total*100:.1f}%)")

    if recovered > 0:
        print(f"\n🔄 Facts recovered: {recovered}")
        print(f"   Recovery rate: {recovered/total*100:.1f}%")

        if recovery_methods:
            print(f"\n   Recovery method breakdown:")
            for method, count in recovery_methods.items():
                print(f"   - {method}: {count} facts")

    if near_match_failed > 0:
        print(f"\n⚠️  Near matches that failed recovery: {near_match_failed}")
        print(f"   (These are 75-89% match but all recovery strategies failed)")

    # Show example near matches
    near_matches = [r for r in results if r.is_near_match]
    if near_matches:
        print(f"\n📋 Example near-match facts:")
        for i, r in enumerate(near_matches[:3]):
            status = "✅ Recovered" if r.is_valid else "❌ Failed"
            print(f"\n   [{i+1}] {status}")
            print(f"       Claim: {r.claim[:60]}...")
            print(f"       Match: {r.match_percentage:.0%}")
            if r.was_recovered and r.recovery_method:
                print(f"       Method: {r.recovery_method}")
            if not r.is_valid:
                print(f"       Error: {r.error_message[:50]}")

    # Calculate what validation rate would have been without recovery
    valid_without_recovery = valid - recovered
    baseline_rate = valid_without_recovery / total * 100
    enhanced_rate = valid / total * 100
    improvement = enhanced_rate - baseline_rate

    if recovered > 0:
        print(f"\n📈 Impact of Enhanced Recovery:")
        print(f"   Baseline (no recovery): {baseline_rate:.1f}%")
        print(f"   Enhanced (with recovery): {enhanced_rate:.1f}%")
        print(f"   Improvement: +{improvement:.1f} percentage points")

    print("\n" + "=" * 70)
    print("✨ Test Complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_validation_with_enhanced_recovery()
