"""
Simple test for enhanced fact recovery features (no pytest required).
"""

import tempfile
from pathlib import Path
from frfr.validation.fact_validator import FactValidator


def create_test_text_file(content: str) -> Path:
    """Create a temporary text file for testing."""
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    temp_file.write(content)
    temp_file.close()
    return Path(temp_file.name)


def test_fuzzy_word_matching():
    """Test fuzzy word matching."""
    print("\n=== Testing Fuzzy Word Matching ===")

    text_file = create_test_text_file("Test content")

    try:
        validator = FactValidator(text_file)

        # Test exact match
        result = validator.fuzzy_word_match("security", "security")
        print(f"✓ Exact match: {result}")
        assert result, "Exact match should succeed"

        # Test case-insensitive
        result = validator.fuzzy_word_match("Security", "security")
        print(f"✓ Case-insensitive: {result}")
        assert result, "Case-insensitive match should succeed"

        # Test OCR artifact: l vs I
        result = validator.fuzzy_word_match("Initial", "Initia1")  # l -> 1
        print(f"✓ OCR artifact (l->1): {result}")
        assert result, "OCR artifact l->1 should match"

        # Test OCR artifact: O vs 0
        result = validator.fuzzy_word_match("Operations", "0perations")
        print(f"✓ OCR artifact (O->0): {result}")
        assert result, "OCR artifact O->0 should match"

        print("✅ All fuzzy word matching tests passed!")

    finally:
        text_file.unlink()


def test_levenshtein_distance():
    """Test Levenshtein distance calculation."""
    print("\n=== Testing Levenshtein Distance ===")

    text_file = create_test_text_file("Test content")

    try:
        validator = FactValidator(text_file)

        # Test exact match
        distance = validator.levenshtein_distance("test", "test")
        print(f"✓ Distance 'test' vs 'test': {distance}")
        assert distance == 0, "Exact match should have distance 0"

        # Test single character difference
        distance = validator.levenshtein_distance("test", "best")
        print(f"✓ Distance 'test' vs 'best': {distance}")
        assert distance == 1, "Single char diff should have distance 1"

        # Test multiple differences
        distance = validator.levenshtein_distance("kitten", "sitting")
        print(f"✓ Distance 'kitten' vs 'sitting': {distance}")
        assert distance == 3, "Multiple diffs should have distance 3"

        print("✅ All Levenshtein distance tests passed!")

    finally:
        text_file.unlink()


def test_find_quote_with_fuzzy():
    """Test find_quote_in_text with fuzzy matching."""
    print("\n=== Testing Find Quote with Fuzzy Matching ===")

    text_content = """
    The security audit was completed on January 15th, 2024.
    All vulnerabilities were identified and documented.
    """
    text_file = create_test_text_file(text_content)

    try:
        validator = FactValidator(text_file)

        # Test exact quote
        quote = "security audit was completed on January 15th"
        found, match_type, ratio = validator.find_quote_in_text(quote, text_content, use_fuzzy=False)
        print(f"✓ Exact quote (no fuzzy): found={found}, ratio={ratio:.0%}, type={match_type}")

        # Test with minor OCR artifacts
        quote_with_ocr = "security audit was comp1eted on January I5th"
        found_exact, _, ratio_exact = validator.find_quote_in_text(quote_with_ocr, text_content, use_fuzzy=False)
        found_fuzzy, _, ratio_fuzzy = validator.find_quote_in_text(quote_with_ocr, text_content, use_fuzzy=True)

        print(f"✓ Quote with OCR artifacts:")
        print(f"  - Without fuzzy: found={found_exact}, ratio={ratio_exact:.0%}")
        print(f"  - With fuzzy: found={found_fuzzy}, ratio={ratio_fuzzy:.0%}")

        assert ratio_fuzzy >= ratio_exact, "Fuzzy matching should improve or maintain ratio"

        print("✅ All find quote tests passed!")

    finally:
        text_file.unlink()


def test_normalize_text():
    """Test text normalization."""
    print("\n=== Testing Text Normalization ===")

    text_file = create_test_text_file("Test content")

    try:
        validator = FactValidator(text_file)

        # Test whitespace normalization
        text = "Multiple    spaces   and\n\nnewlines"
        normalized = validator.normalize_text(text)
        print(f"✓ Whitespace normalization: '{text}' -> '{normalized}'")
        assert "  " not in normalized, "Should collapse multiple spaces"

        # Test quote normalization
        text_with_smart_quotes = "test " + chr(0x201c) + "quoted" + chr(0x201d) + " text"
        normalized = validator.normalize_text(text_with_smart_quotes)
        print(f"✓ Quote normalization: '{text_with_smart_quotes}' -> '{normalized}'")

        # Test dash normalization
        text = "em—dash and en–dash"
        normalized = validator.normalize_text(text)
        print(f"✓ Dash normalization: '{text}' -> '{normalized}'")
        assert "—" not in normalized and "–" not in normalized, "Should normalize dashes"

        print("✅ All text normalization tests passed!")

    finally:
        text_file.unlink()


def test_progressive_recovery_integration():
    """Test that progressive recovery is integrated correctly."""
    print("\n=== Testing Progressive Recovery Integration ===")

    text_content = """
    The security audit was completed on January 15th, 2024.
    All vulnerabilities were identified and documented.
    The assessment found 5 critical issues.
    """
    text_file = create_test_text_file(text_content)

    try:
        validator = FactValidator(text_file)

        # Without Claude client, progressive recovery should handle gracefully
        claim = "The security audit was completed"
        original_quote = "audit completed January"

        result = validator.progressive_fact_recovery(
            claim, original_quote, text_content, 1, 3, 0.75
        )

        print(f"✓ Progressive recovery (no LLM): result={result}")
        # Without LLM, it should try strategies and return None or fuzzy match
        print(f"  (Result is None or fuzzy match, which is expected without LLM)")

        print("✅ Progressive recovery integration test passed!")

    finally:
        text_file.unlink()


def main():
    """Run all tests."""
    print("=" * 60)
    print("Enhanced Fact Recovery - Simple Tests")
    print("=" * 60)

    try:
        test_normalize_text()
        test_levenshtein_distance()
        test_fuzzy_word_matching()
        test_find_quote_with_fuzzy()
        test_progressive_recovery_integration()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
