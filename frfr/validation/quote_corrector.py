"""
Paraphrased quote correction tool.

Recovers rejected facts by finding the exact quotes in source text.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from frfr.extraction.claude_client import ClaudeClient
from frfr.validation.fact_validator import FactValidator

logger = logging.getLogger(__name__)


@dataclass
class CorrectionResult:
    """Result of attempting to correct a paraphrased quote."""
    original_claim: str
    original_quote: str
    original_location: str
    was_corrected: bool
    corrected_quote: Optional[str] = None
    corrected_location: Optional[str] = None
    match_confidence: float = 0.0
    validation_score: float = 0.0  # How well corrected quote validates
    reasoning: str = ""


class QuoteCorrector:
    """Corrects paraphrased quotes by finding exact text in source."""

    def __init__(self, text_file: Path, claude_client: ClaudeClient = None):
        """
        Initialize quote corrector.

        Args:
            text_file: Path to the source text file
            claude_client: Claude client for LLM-assisted correction
        """
        self.text_file = Path(text_file)
        with open(self.text_file, "r") as f:
            self.lines = f.readlines()

        self.claude_client = claude_client or ClaudeClient()
        self.validator = FactValidator(text_file, claude_client=self.claude_client)

        logger.info(f"Initialized QuoteCorrector with {len(self.lines)} lines")

    def get_expanded_context(
        self, start_line: int, end_line: int, expansion: int = 30
    ) -> Tuple[str, int, int]:
        """
        Get expanded context around the original location.

        Args:
            start_line: Original start line (1-indexed)
            end_line: Original end line (1-indexed)
            expansion: Lines to expand on each side

        Returns:
            Tuple of (context_text, new_start_line, new_end_line)
        """
        expanded_start = max(1, start_line - expansion)
        expanded_end = min(len(self.lines), end_line + expansion)

        context = self.validator.get_line_text(expanded_start, expanded_end)
        return context, expanded_start, expanded_end

    def correct_paraphrased_quote(
        self, claim: str, paraphrased_quote: str, original_location: str
    ) -> CorrectionResult:
        """
        Attempt to find the exact quote for a paraphrased fact.

        Args:
            claim: The factual claim
            paraphrased_quote: The paraphrased quote that didn't validate
            original_location: Original location string (e.g., "Lines 100-110")

        Returns:
            CorrectionResult with correction details
        """
        # Parse original location
        try:
            start_line, end_line = self.validator.parse_line_range(original_location)
        except Exception as e:
            logger.error(f"Failed to parse location '{original_location}': {e}")
            return CorrectionResult(
                original_claim=claim,
                original_quote=paraphrased_quote,
                original_location=original_location,
                was_corrected=False,
                reasoning=f"Invalid location format: {e}",
            )

        # Get expanded context
        context, context_start, context_end = self.get_expanded_context(
            start_line, end_line, expansion=30
        )

        logger.info(f"Correcting quote for claim: {claim[:60]}...")
        logger.info(f"Original location: {original_location}, Expanded: Lines {context_start}-{context_end}")

        # Use LLM to find exact quote
        prompt = f"""You are helping to find the EXACT quote from a source document that supports a factual claim.

**Context**: The claim below was extracted from a document, but the evidence quote was paraphrased instead of being an exact quote. Your task is to find the EXACT text from the source that supports this claim.

**Claim**: {claim}

**Paraphrased Quote** (NOT exact): {paraphrased_quote}

**Source Context** (Lines {context_start}-{context_end}):
{context}

---

**Your Task**:
1. Search the context above for text that DIRECTLY supports the claim
2. Extract the EXACT quote (word-for-word, verbatim) from the context
3. DO NOT paraphrase, summarize, or rephrase - copy the exact text
4. Include enough context to make the quote self-contained but stay focused

**Requirements**:
- The quote MUST be verbatim text from the context above
- The quote should be as specific and complete as possible
- Include surrounding context if it helps clarify the fact
- If multiple sentences support the claim, include all of them

**Output Format** (JSON only):
{{
  "found": true/false,
  "exact_quote": "word-for-word text from context (if found)",
  "confidence": 0.0-1.0,
  "line_hint": "approximate line numbers where quote appears (e.g., 'around lines 105-107')",
  "reasoning": "brief explanation of why this quote supports the claim"
}}

If you cannot find supporting text in the context, set found to false.

RESPOND WITH ONLY THE JSON OBJECT:"""

        try:
            response = self.claude_client.prompt(prompt, max_tokens=1500)

            # Parse JSON response
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()

            result = json.loads(response)

            if not result.get("found"):
                logger.info(f"No exact quote found: {result.get('reasoning', 'unknown')}")
                return CorrectionResult(
                    original_claim=claim,
                    original_quote=paraphrased_quote,
                    original_location=original_location,
                    was_corrected=False,
                    match_confidence=0.0,
                    reasoning=result.get("reasoning", "Quote not found in context"),
                )

            corrected_quote = result["exact_quote"]
            confidence = result.get("confidence", 0.0)

            # Verify the corrected quote actually exists in context
            found, match_type = self.validator.find_quote_in_text(
                corrected_quote, context
            )

            if not found:
                logger.warning(f"LLM returned quote that doesn't exist in context: {corrected_quote[:60]}...")
                return CorrectionResult(
                    original_claim=claim,
                    original_quote=paraphrased_quote,
                    original_location=original_location,
                    was_corrected=False,
                    match_confidence=confidence,
                    reasoning="LLM returned invalid quote (not found in context)",
                )

            # Extract validation score from match_type
            validation_score = 1.0 if "exact" in match_type else 0.8

            logger.info(f"✓ Successfully corrected quote ({match_type}, confidence: {confidence:.0%})")

            return CorrectionResult(
                original_claim=claim,
                original_quote=paraphrased_quote,
                original_location=original_location,
                was_corrected=True,
                corrected_quote=corrected_quote,
                corrected_location=f"Lines {context_start}-{context_end}",
                match_confidence=confidence,
                validation_score=validation_score,
                reasoning=result.get("reasoning", "Quote corrected successfully"),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response[:200]}")
            return CorrectionResult(
                original_claim=claim,
                original_quote=paraphrased_quote,
                original_location=original_location,
                was_corrected=False,
                reasoning=f"JSON parse error: {e}",
            )
        except Exception as e:
            logger.error(f"Quote correction failed: {e}")
            return CorrectionResult(
                original_claim=claim,
                original_quote=paraphrased_quote,
                original_location=original_location,
                was_corrected=False,
                reasoning=f"Error: {e}",
            )

    def correct_rejected_facts(
        self, rejected_facts: List[Dict], min_match_threshold: float = 0.3
    ) -> Tuple[List[Dict], List[CorrectionResult]]:
        """
        Attempt to correct all rejected facts.

        Args:
            rejected_facts: List of fact dicts that failed validation
            min_match_threshold: Minimum match percentage to attempt correction (e.g., 0.3 = 30%)

        Returns:
            Tuple of (corrected_facts_list, correction_results)
        """
        corrected_facts = []
        all_results = []

        logger.info(f"Attempting to correct {len(rejected_facts)} rejected facts...")

        for i, fact in enumerate(rejected_facts):
            claim = fact.get("claim", "")
            quote = fact.get("evidence_quote", "")
            location = fact.get("source_location", "")
            match_percentage = fact.get("match_percentage", 0.0)

            # Skip facts with very low match (likely not in this context at all)
            if match_percentage < min_match_threshold:
                logger.debug(f"Skipping fact {i+1} (match: {match_percentage:.0%} < threshold)")
                continue

            logger.info(f"[{i+1}/{len(rejected_facts)}] Correcting: {claim[:60]}... (match: {match_percentage:.0%})")

            result = self.correct_paraphrased_quote(claim, quote, location)
            all_results.append(result)

            if result.was_corrected:
                # Create corrected fact
                corrected_fact = fact.copy()
                corrected_fact["evidence_quote"] = result.corrected_quote
                corrected_fact["source_location"] = result.corrected_location
                corrected_fact["was_corrected"] = True
                corrected_fact["original_quote"] = result.original_quote
                corrected_fact["correction_confidence"] = result.match_confidence
                corrected_fact["validation_score"] = result.validation_score

                corrected_facts.append(corrected_fact)

        success_rate = len(corrected_facts) / len(rejected_facts) if rejected_facts else 0
        logger.info(
            f"Correction complete: {len(corrected_facts)}/{len(rejected_facts)} facts corrected ({success_rate:.1%})"
        )

        return corrected_facts, all_results

    def process_session_rejected_facts(
        self,
        session_dir: Path,
        document_name: str,
        min_match_threshold: float = 0.3,
        output_file: Optional[Path] = None,
    ) -> Dict:
        """
        Process all rejected facts from a session and attempt correction.

        Args:
            session_dir: Path to session directory
            document_name: Name of the document
            min_match_threshold: Minimum match percentage to attempt correction
            output_file: Optional path to save corrected facts

        Returns:
            Summary statistics dictionary
        """
        # This would need access to rejected facts during extraction
        # For now, this is a placeholder showing the intended API
        raise NotImplementedError(
            "Session processing requires integration with extraction pipeline"
        )


def correct_facts_from_file(
    facts_file: Path,
    text_file: Path,
    output_file: Path,
    min_match_threshold: float = 0.3,
) -> Dict:
    """
    Correct paraphrased quotes in a facts file.

    Args:
        facts_file: Path to JSON file with facts (must include match_percentage)
        text_file: Path to source text file
        output_file: Path to save corrected facts
        min_match_threshold: Minimum match percentage to attempt correction

    Returns:
        Summary statistics dictionary
    """
    with open(facts_file, "r") as f:
        data = json.load(f)

    # Extract rejected facts (facts with low match percentage)
    rejected_facts = []
    for doc_name, doc_data in data.get("documents", {}).items():
        facts = doc_data.get("facts", [])
        for fact in facts:
            if fact.get("match_percentage", 1.0) < 0.8:  # Consider <80% match as potentially paraphrased
                rejected_facts.append(fact)

    if not rejected_facts:
        logger.info("No rejected facts found in file")
        return {
            "total_facts": 0,
            "corrected": 0,
            "failed": 0,
            "correction_rate": 0.0,
        }

    # Correct them
    corrector = QuoteCorrector(text_file)
    corrected_facts, results = corrector.correct_rejected_facts(
        rejected_facts, min_match_threshold
    )

    # Save results
    output_data = {
        "source_file": str(facts_file),
        "text_file": str(text_file),
        "total_rejected": len(rejected_facts),
        "corrected": len(corrected_facts),
        "failed": len(rejected_facts) - len(corrected_facts),
        "correction_rate": len(corrected_facts) / len(rejected_facts) if rejected_facts else 0,
        "corrected_facts": [f for f in corrected_facts],
        "correction_results": [
            {
                "claim": r.original_claim[:100],
                "was_corrected": r.was_corrected,
                "confidence": r.match_confidence,
                "reasoning": r.reasoning,
            }
            for r in results
        ],
    }

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info(f"Correction results saved to {output_file}")

    return {
        "total_facts": len(rejected_facts),
        "corrected": len(corrected_facts),
        "failed": len(rejected_facts) - len(corrected_facts),
        "correction_rate": output_data["correction_rate"],
    }
