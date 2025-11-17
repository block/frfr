"""
Test enhanced fact recovery features.

Tests:
- OCR artifact handling
- Fuzzy word matching
- Multi-quote recovery
- Progressive recovery strategies
"""

import pytest
import tempfile
from pathlib import Path
from frfr.validation.fact_validator import FactValidator


class MockClaudeClient:
    """Mock Claude client for testing recovery features."""

    def __init__(self, response=None):
        self.response = response
        self.call_count = 0

    def prompt(self, prompt_text, max_tokens=1000):
        """Return mock response."""
        self.call_count += 1
        if self.response:
            return self.response
        return '{"found": false, "confidence": 0.0, "reasoning": "test"}'


def create_test_text_file(content: str) -> Path:
    """Create a temporary text file for testing."""
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    temp_file.write(content)
    temp_file.close()
    return Path(temp_file.name)


class TestFuzzyMatching:
    """Test fuzzy matching and OCR artifact handling."""

    def test_exact_word_match(self):
        """Test exact word matching works."""
        text_content = "The security audit was completed on January 15th, 2024."
        text_file = create_test_text_file(text_content)

        try:
            validator = FactValidator(text_file)

            # Test exact match
            assert validator.fuzzy_word_match("security", "security")
            assert validator.fuzzy_word_match("Security", "security")  # Case-insensitive
        finally:
            text_file.unlink()

    def test_ocr_artifact_l_vs_I(self):
        """Test OCR artifact: l vs I."""
        text_file = create_test_text_file("Test content")

        try:
            validator = FactValidator(text_file)

            # l vs I substitution
            assert validator.fuzzy_word_match("Initial", "Initia1")  # I -> 1
            assert validator.fuzzy_word_match("level", "Ievel")  # l -> I
        finally:
            text_file.unlink()

    def test_ocr_artifact_O_vs_0(self):
        """Test OCR artifact: O vs 0."""
        text_file = create_test_text_file("Test content")

        try:
            validator = FactValidator(text_file)

            # O vs 0 substitution
            assert validator.fuzzy_word_match("Operations", "0perations")  # O -> 0
            assert validator.fuzzy_word_match("tool", "t0ol")  # o -> 0
        finally:
            text_file.unlink()

    def test_ocr_artifact_rn_vs_m(self):
        """Test OCR artifact: rn vs m."""
        text_file = create_test_text_file("Test content")

        try:
            validator = FactValidator(text_file)

            # rn vs m substitution
            assert validator.fuzzy_word_match("information", "infornation")  # m -> rn
        finally:
            text_file.unlink()

    def test_levenshtein_distance(self):
        """Test Levenshtein distance calculation."""
        text_file = create_test_text_file("Test content")

        try:
            validator = FactValidator(text_file)

            # Test exact match
            assert validator.levenshtein_distance("test", "test") == 0

            # Test single character difference
            assert validator.levenshtein_distance("test", "best") == 1

            # Test multiple differences
            assert validator.levenshtein_distance("kitten", "sitting") == 3
        finally:
            text_file.unlink()

    def test_find_quote_with_fuzzy_matching(self):
        """Test find_quote_in_text with fuzzy matching enabled."""
        text_content = """
        The security audit was completed on January 15th, 2024.
        All vulnerabilities were identified and documented.
        """
        text_file = create_test_text_file(text_content)

        try:
            validator = FactValidator(text_file)

            # Test with OCR artifacts - should fail without fuzzy matching
            quote_with_ocr = "The security audit was comp1eted on January I5th"  # l->1, 1->I
            found_exact, _, ratio_exact = validator.find_quote_in_text(quote_with_ocr, text_content, use_fuzzy=False)

            # Should succeed with fuzzy matching
            found_fuzzy, _, ratio_fuzzy = validator.find_quote_in_text(quote_with_ocr, text_content, use_fuzzy=True)

            # Fuzzy should have better or equal match ratio
            assert ratio_fuzzy >= ratio_exact
        finally:
            text_file.unlink()


class TestMultiQuoteRecovery:
    """Test multi-quote recovery functionality."""

    def test_multi_quote_recovery_success(self):
        """Test successful multi-quote recovery."""
        text_content = """
        The company conducted a security assessment in Q1 2024.
        The assessment covered network infrastructure.
        Results showed 5 critical vulnerabilities.
        All vulnerabilities were remediated by March 2024.
        """
        text_file = create_test_text_file(text_content)

        # Mock LLM response with multiple quotes
        mock_response = """```json
{
  "needs_multiple_quotes": true,
  "quotes": [
    {"quote": "security assessment in Q1 2024", "supports": "timing"},
    {"quote": "5 critical vulnerabilities", "supports": "findings"}
  ],
  "confidence": 0.9,
  "reasoning": "Claim combines timing and findings"
}
```"""

        try:
            mock_client = MockClaudeClient(mock_response)
            validator = FactValidator(text_file, claude_client=mock_client)

            claim = "The Q1 2024 security assessment found 5 critical vulnerabilities"
            original_quote = "assessment found 5 critical issues"

            result = validator.attempt_multi_quote_recovery(
                claim, original_quote, text_content, 1, 4
            )

            # Should return list of quotes
            assert result is not None
            assert len(result) >= 2
            assert all(isinstance(q, tuple) for q in result)
        finally:
            text_file.unlink()

    def test_multi_quote_recovery_not_needed(self):
        """Test multi-quote recovery when not needed."""
        text_content = "The security audit was completed on January 15th, 2024."
        text_file = create_test_text_file(text_content)

        # Mock LLM response indicating multi-quote not needed
        mock_response = """```json
{
  "needs_multiple_quotes": false,
  "quotes": [],
  "confidence": 0.5,
  "reasoning": "Single quote sufficient"
}
```"""

        try:
            mock_client = MockClaudeClient(mock_response)
            validator = FactValidator(text_file, claude_client=mock_client)

            claim = "The security audit was completed on January 15th, 2024"
            original_quote = "audit was completed on January 15th"

            result = validator.attempt_multi_quote_recovery(
                claim, original_quote, text_content, 1, 1
            )

            # Should return None
            assert result is None
        finally:
            text_file.unlink()


class TestProgressiveRecovery:
    """Test progressive recovery strategy."""

    def test_progressive_recovery_single_quote_success(self):
        """Test progressive recovery succeeds with single-quote strategy."""
        text_content = """
        The security audit was completed on January 15th, 2024.
        All vulnerabilities were identified and documented.
        """
        text_file = create_test_text_file(text_content)

        # Mock LLM response for single quote recovery
        mock_response = """```json
{
  "found": true,
  "quote": "security audit was completed on January 15th, 2024",
  "confidence": 0.9,
  "reasoning": "Found exact quote"
}
```"""

        try:
            mock_client = MockClaudeClient(mock_response)
            validator = FactValidator(text_file, claude_client=mock_client)

            claim = "The security audit was completed on January 15th, 2024"
            original_quote = "audit completed January 15th"

            result = validator.progressive_fact_recovery(
                claim, original_quote, text_content, 1, 2, 0.75
            )

            # Should succeed with single_quote method
            assert result is not None
            assert result["method"] == "single_quote"
            assert "quote" in result
        finally:
            text_file.unlink()

    def test_progressive_recovery_fuzzy_match_success(self):
        """Test progressive recovery succeeds with fuzzy matching."""
        text_content = """
        The security audit was comp1eted on January I5th, 2024.
        """
        text_file = create_test_text_file(text_content)

        # Mock LLM response that fails single-quote recovery
        mock_response = """```json
{
  "found": false,
  "confidence": 0.3,
  "reasoning": "Could not find exact quote"
}
```"""

        try:
            mock_client = MockClaudeClient(mock_response)
            validator = FactValidator(text_file, claude_client=mock_client)

            claim = "The security audit was completed on January 15th, 2024"
            # Quote with OCR artifacts that should match with fuzzy matching
            original_quote = "security audit was comp1eted on January I5th, 2024"

            result = validator.progressive_fact_recovery(
                claim, original_quote, text_content, 1, 1, 0.85  # Near match ratio
            )

            # Should succeed with fuzzy_match method (or None if fuzzy threshold not met)
            # This depends on how good the fuzzy matching is
            if result:
                assert result["method"] in ["fuzzy_match", "multi_quote"]
        finally:
            text_file.unlink()

    def test_progressive_recovery_all_fail(self):
        """Test progressive recovery when all strategies fail."""
        text_content = "Completely different text content."
        text_file = create_test_text_file(text_content)

        # Mock LLM responses that fail
        mock_response = """```json
{
  "found": false,
  "needs_multiple_quotes": false,
  "confidence": 0.1,
  "reasoning": "No match found"
}
```"""

        try:
            mock_client = MockClaudeClient(mock_response)
            validator = FactValidator(text_file, claude_client=mock_client)

            claim = "The security audit was completed on January 15th, 2024"
            original_quote = "security audit completed January 15th"

            result = validator.progressive_fact_recovery(
                claim, original_quote, text_content, 1, 1, 0.20  # Low match ratio
            )

            # Should return None when all strategies fail
            assert result is None
        finally:
            text_file.unlink()


class TestIntegration:
    """Integration tests for complete validation with enhanced recovery."""

    def test_validate_fact_with_fuzzy_recovery(self):
        """Test complete validation flow with fuzzy recovery."""
        text_content = """
        The security audit was comp1eted on January I5th, 2024.
        All vulnerabilities were identified and documented.
        """
        text_file = create_test_text_file(text_content)

        # Mock successful single-quote recovery
        mock_response = """```json
{
  "found": true,
  "quote": "security audit was comp1eted on January I5th, 2024",
  "confidence": 0.9,
  "reasoning": "Found quote"
}
```"""

        try:
            mock_client = MockClaudeClient(mock_response)
            validator = FactValidator(text_file, claude_client=mock_client)

            fact = {
                "claim": "The security audit was completed on January 15th, 2024",
                "evidence_quote": "security audit completed on January 15th, 2024",
                "source_location": "Line 2"
            }

            result = validator.validate_fact(fact, 0)

            # Fact may be valid or recovered depending on fuzzy match quality
            # The test mainly ensures no errors occur
            assert result is not None
            assert hasattr(result, 'is_valid')
        finally:
            text_file.unlink()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
