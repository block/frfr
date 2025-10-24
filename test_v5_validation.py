#!/usr/bin/env python3
"""
Test V5 validation logic with multiple evidence quotes.

Tests:
1. V4 format (single evidence_quote) - should work
2. V5 format with single quote - should work
3. V5 format with multiple quotes (all valid) - should work
4. V5 format with multiple quotes (some invalid) - should fail
"""

import sys
from pathlib import Path
from frfr.validation.fact_validator import FactValidator

# Create a simple test text file
test_text = """Line 1: Introduction to the system
Line 2: The backup system performs daily backups at 2 AM.
Line 3: All backups are encrypted using AES-256 encryption.
Line 4: Backup retention is set to 90 days.
Line 5: The system administrator reviews logs weekly.
Line 6: Vulnerability scans are performed quarterly by Acme Security.
Line 7: All findings are remediated within 30 days.
Line 8: The incident response team is available 24/7.
"""

test_file = Path("/tmp/test_validation_source.txt")
with open(test_file, "w") as f:
    f.write(test_text)

# Create validator
validator = FactValidator(test_file)

print("=" * 70)
print("V5 VALIDATION TESTS")
print("=" * 70)

# Test 1: V4 format (single evidence_quote)
print("\n[TEST 1] V4 Format (single evidence_quote)")
fact_v4 = {
    "claim": "Backups performed daily at 2 AM",
    "evidence_quote": "The backup system performs daily backups at 2 AM.",
    "source_location": "Lines 2-2",
    "confidence": 0.95
}

result = validator.validate_fact(fact_v4, 0)
print(f"  Result: {'✅ PASS' if result.is_valid else '❌ FAIL'}")
print(f"  Valid: {result.is_valid}")
print(f"  Quote: {result.quote_snippet}")
if not result.is_valid:
    print(f"  Error: {result.error_message}")

# Test 2: V5 format with single quote
print("\n[TEST 2] V5 Format (single quote in evidence_quotes array)")
fact_v5_single = {
    "claim": "Backups encrypted with AES-256",
    "evidence_quotes": [
        {
            "quote": "All backups are encrypted using AES-256 encryption.",
            "source_location": "Lines 3-3",
            "relevance": "Encryption standard"
        }
    ],
    "source_location": "Lines 3-3",
    "confidence": 0.95
}

result = validator.validate_fact(fact_v5_single, 1)
print(f"  Result: {'✅ PASS' if result.is_valid else '❌ FAIL'}")
print(f"  Valid: {result.is_valid}")
print(f"  Quote: {result.quote_snippet}")
if not result.is_valid:
    print(f"  Error: {result.error_message}")

# Test 3: V5 format with multiple quotes (all valid)
print("\n[TEST 3] V5 Format (multiple quotes - all valid)")
fact_v5_multi_valid = {
    "claim": "Vulnerability scans performed quarterly with 30-day remediation SLA",
    "evidence_quotes": [
        {
            "quote": "Vulnerability scans are performed quarterly by Acme Security.",
            "source_location": "Lines 6-6",
            "relevance": "Frequency and vendor"
        },
        {
            "quote": "All findings are remediated within 30 days.",
            "source_location": "Lines 7-7",
            "relevance": "Remediation SLA"
        }
    ],
    "source_location": "Lines 6-7",
    "confidence": 0.95
}

result = validator.validate_fact(fact_v5_multi_valid, 2)
print(f"  Result: {'✅ PASS' if result.is_valid else '❌ FAIL'}")
print(f"  Valid: {result.is_valid}")
print(f"  Quote: {result.quote_snippet}")
if not result.is_valid:
    print(f"  Error: {result.error_message}")

# Test 4: V5 format with multiple quotes (some invalid)
print("\n[TEST 4] V5 Format (multiple quotes - some invalid)")
fact_v5_multi_invalid = {
    "claim": "System has 24/7 support and automatic failover",
    "evidence_quotes": [
        {
            "quote": "The incident response team is available 24/7.",
            "source_location": "Lines 8-8",
            "relevance": "24/7 availability"
        },
        {
            "quote": "Automatic failover is configured for all critical systems.",
            "source_location": "Lines 9-9",
            "relevance": "Failover capability"
        }
    ],
    "source_location": "Lines 8-9",
    "confidence": 0.90
}

result = validator.validate_fact(fact_v5_multi_invalid, 3)
print(f"  Result: {'✅ PASS' if result.is_valid else '❌ FAIL'}")
print(f"  Valid: {result.is_valid}")
print(f"  Quote: {result.quote_snippet}")
if not result.is_valid:
    print(f"  Error: {result.error_message}")

# Test 5: Chunk-based validation with V5 format
print("\n[TEST 5] V5 Format with chunk_text validation (multiple quotes)")
chunk_text = """Vulnerability scans are performed quarterly by Acme Security.
All findings are remediated within 30 days.
The incident response team is available 24/7."""

result = validator.validate_fact(fact_v5_multi_valid, 4, chunk_text=chunk_text)
print(f"  Result: {'✅ PASS' if result.is_valid else '❌ FAIL'}")
print(f"  Valid: {result.is_valid}")
print(f"  Quote: {result.quote_snippet}")
if not result.is_valid:
    print(f"  Error: {result.error_message}")

print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print("All tests completed! Check results above.")
print("\nExpected results:")
print("  Test 1: ✅ PASS (V4 format should work)")
print("  Test 2: ✅ PASS (V5 single quote should work)")
print("  Test 3: ✅ PASS (V5 multiple valid quotes should work)")
print("  Test 4: ❌ FAIL (V5 with invalid quote should fail)")
print("  Test 5: ✅ PASS (chunk validation with multiple quotes should work)")
print("=" * 70)
