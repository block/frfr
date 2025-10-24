"""
Test script for quote corrector.

Demonstrates correction of paraphrased quotes.
"""

import json
import logging
from pathlib import Path
from frfr.validation.quote_corrector import QuoteCorrector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)


def test_quote_correction():
    """Test the quote corrector with sample rejected facts."""

    text_file = Path("output/soc2_full_extraction.txt")

    if not text_file.exists():
        logger.error(f"Text file not found: {text_file}")
        return

    # Sample rejected facts from the extraction (based on stderr output)
    rejected_facts = [
        {
            "claim": "Remote user VPN connections utilize multi-factor authentication",
            "evidence_quote": "Remote user VPN connections utilize multi-factor authentication for access",
            "source_location": "Lines 4800-4850",
            "match_percentage": 0.70,  # 70% match - candidate for correction
        },
        {
            "claim": "A third party application is used to monitor network devices",
            "evidence_quote": "A third party application is used to monitor network devices and servers",
            "source_location": "Lines 2200-2250",
            "match_percentage": 0.67,  # 67% match
        },
        {
            "claim": "LNRS has a Security Incident Response Policy and Procedures in place",
            "evidence_quote": "LNRS has a Security Incident Response Policy and Procedures",
            "source_location": "Lines 2800-2850",
            "match_percentage": 0.64,  # 64% match
        },
    ]

    logger.info("=" * 80)
    logger.info("QUOTE CORRECTION TEST")
    logger.info("=" * 80)
    logger.info(f"\nTesting correction of {len(rejected_facts)} rejected facts\n")

    # Initialize corrector
    corrector = QuoteCorrector(text_file)

    # Correct each fact
    results = []
    for i, fact in enumerate(rejected_facts, 1):
        logger.info(f"\n{'=' * 80}")
        logger.info(f"FACT {i}/{len(rejected_facts)}")
        logger.info(f"{'=' * 80}")
        logger.info(f"\nClaim: {fact['claim']}")
        logger.info(f"Original Quote: {fact['evidence_quote'][:100]}...")
        logger.info(f"Location: {fact['source_location']}")
        logger.info(f"Match: {fact['match_percentage']:.0%}")

        result = corrector.correct_paraphrased_quote(
            claim=fact["claim"],
            paraphrased_quote=fact["evidence_quote"],
            original_location=fact["source_location"],
        )

        results.append(result)

        if result.was_corrected:
            logger.info(f"\n✅ CORRECTED!")
            logger.info(f"Corrected Quote: {result.corrected_quote[:150]}...")
            logger.info(f"Corrected Location: {result.corrected_location}")
            logger.info(f"Confidence: {result.match_confidence:.0%}")
            logger.info(f"Validation Score: {result.validation_score:.0%}")
        else:
            logger.info(f"\n❌ FAILED")
            logger.info(f"Reason: {result.reasoning}")

    # Summary
    logger.info(f"\n{'=' * 80}")
    logger.info("SUMMARY")
    logger.info(f"{'=' * 80}")
    corrected = sum(1 for r in results if r.was_corrected)
    failed = len(results) - corrected

    logger.info(f"\nTotal facts: {len(results)}")
    logger.info(f"Corrected: {corrected} ({corrected/len(results)*100:.1f}%)")
    logger.info(f"Failed: {failed} ({failed/len(results)*100:.1f}%)")

    # Save results
    output_file = Path("output/quote_correction_test_results.json")
    output_data = {
        "test_facts": rejected_facts,
        "results": [
            {
                "claim": r.original_claim,
                "was_corrected": r.was_corrected,
                "corrected_quote": r.corrected_quote,
                "confidence": r.match_confidence,
                "reasoning": r.reasoning,
            }
            for r in results
        ],
        "summary": {
            "total": len(results),
            "corrected": corrected,
            "failed": failed,
            "success_rate": corrected / len(results) if results else 0,
        }
    }

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    test_quote_correction()
