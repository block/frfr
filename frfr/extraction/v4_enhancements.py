"""
V4 enhancements for fact extraction based on judge feedback.

Key improvements:
1. Better quantitative value tagging with semantic matching
2. Test-result-only fact filtering
3. Generic term detection and rejection
4. Enhanced prompt to prevent generic extractions
"""

import re
from typing import List, Dict
from frfr.extraction.schemas import ExtractedFact
from frfr.extraction.extraction_patterns import QuantitativeValue


def is_test_result_only(fact_claim: str) -> bool:
    """
    Detect if a fact is ONLY a test result with no control substance.

    Test-only facts like "No exceptions noted" provide minimal value.
    We want to filter these out to reduce noise.

    CONSERVATIVE APPROACH: Only filter facts that are PURELY test results
    with no control information whatsoever.

    Args:
        fact_claim: The fact claim text

    Returns:
        True if this is a test-only fact (should be filtered)
    """
    claim_lower = fact_claim.lower()

    # VERY SPECIFIC test-only patterns (no control substance)
    # These are pure test results that add no control information
    test_only_patterns = [
        r"^no exceptions? (were |was )?(noted|found|identified)\.?$",  # Only "no exceptions noted"
        r"^auditor (inspected|tested|examined|observed) .* and found no exceptions?\.?$",  # Pure test with no control
        r"^(inspection|testing|examination) (found|revealed|showed) no (exceptions?|issues?|problems?)\.?$",
    ]

    # Check if claim matches PURE test-only patterns
    is_pure_test = any(re.search(p, claim_lower) for p in test_only_patterns)

    if not is_pure_test:
        return False

    # Double-check: Does it have ANY control substance?
    # If it mentions specific controls, keep it even if it's a test result
    control_substance_patterns = [
        r"(requires?|require|required|requiring)",
        r"(performs?|perform|performed|performing)",
        r"(maintains?|maintain|maintained|maintaining)",
        r"(reviews?|review|reviewed|reviewing)",
        r"(monitors?|monitor|monitored|monitoring)",
        r"(encrypts?|encrypt|encrypted|encrypting)",
        r"(restricts?|restrict|restricted|restricting)",
        r"(configures?|configure|configured|configuring)",
        r"(implements?|implement|implemented|implementing)",
        r"(enforces?|enforce|enforced|enforcing)",
        r"\b(password|encryption|firewall|access|authentication|backup)\b",  # Control topics
        r"\b(policy|procedure|requirement|standard|control)\b",  # Control documents
        r"\b(daily|weekly|monthly|quarterly|annually)\b",  # Frequency in control
        r"\b(at least|minimum|maximum|threshold)\b.*\d+",  # Quantitative requirement
        r"\b(user|access|security|system|application|network|database)\b",  # Control objects
    ]

    has_control_detail = any(re.search(p, claim_lower) for p in control_substance_patterns)

    # Only filter if it's pure test AND has no control detail
    return is_pure_test and not has_control_detail


def contains_generic_terms(fact_claim: str) -> bool:
    """
    Detect if a fact uses generic terms without specifics.

    Generic terms like "encryption" (vs "TLS 1.3"), "monitoring" (vs "SIEM"),
    "IT staff" (vs "security team") indicate insufficient specificity.

    Args:
        fact_claim: The fact claim text

    Returns:
        True if fact contains generic terms without specifics
    """
    claim_lower = fact_claim.lower()

    # Generic terms that should have specifics
    generic_patterns = [
        # Generic tech terms (should have specific protocol/version)
        (r"\bencryption\b(?!\s+(using|with|via|through|by)\s+\w+)", "encryption without specifying protocol (TLS, AES, etc.)"),
        (r"\bmonitoring\b(?!\s+(using|with|via|through|by|tool|system|software)\s+\w+)", "monitoring without specifying tool/system"),
        (r"\bauthentication\b(?!\s+(using|with|via|requires?|method|system)\s+\w+)", "authentication without specifying method"),

        # Generic roles (should have specific team/title)
        (r"\b(IT|it) (staff|personnel|team)\b(?!.*\b(security|operations|infrastructure|development)\b)", "generic 'IT staff' without specific team"),
        (r"\bmanagement\b(?!.*\b(security|risk|compliance|IT|senior)\b)", "generic 'management' without specific role"),
        (r"\bpersonnel\b(?!.*\b(authorized|security|IT)\b)", "generic 'personnel' without specific role"),
        (r"\badministrator\b(?!.*\b(system|database|network|security)\b)", "generic 'administrator' without specific type"),

        # Generic frequencies (should be specific)
        (r"\b(periodic|periodically)\b(?!.*\b(daily|weekly|monthly|quarterly|annually)\b)", "vague 'periodic' without specific frequency"),
        (r"\b(regular|regularly)\b(?!.*\b(daily|weekly|monthly|quarterly|annually)\b)", "vague 'regular' without specific frequency"),
        (r"\bongoing\b(?!.*\b(continuous|real-time|daily)\b)", "vague 'ongoing' without specific frequency"),

        # Generic policies (should have name)
        (r"\bpolicies and procedures\b(?!\s+(for|regarding|governing|named|titled|including))", "generic 'policies' without names"),
        (r"\bsecurity program\b(?!\s+(includes|implements|requires|enforces))", "generic 'security program' without details"),
    ]

    # Check each pattern
    for pattern, description in generic_patterns:
        if re.search(pattern, claim_lower):
            return True

    return False


def get_generic_term_feedback(fact_claim: str) -> str:
    """
    Get specific feedback on what generic terms should be replaced.

    Args:
        fact_claim: The fact claim

    Returns:
        Feedback string explaining what's generic
    """
    claim_lower = fact_claim.lower()
    feedback_parts = []

    if re.search(r"\bencryption\b(?!\s+(using|with))", claim_lower):
        feedback_parts.append("'encryption' → specify protocol (TLS 1.3, AES-256, etc.)")

    if re.search(r"\bmonitoring\b(?!\s+(using|with|tool))", claim_lower):
        feedback_parts.append("'monitoring' → specify tool (SIEM, Splunk, Datadog, etc.)")

    if re.search(r"\b(IT|it) (staff|personnel)\b", claim_lower):
        feedback_parts.append("'IT staff' → specify team (Security team, Operations team, etc.)")

    if re.search(r"\bmanagement\b(?!.*\b(security|senior)\b)", claim_lower):
        feedback_parts.append("'management' → specify role (Security Manager, CISO, etc.)")

    if re.search(r"\b(periodic|periodically|regular|regularly|ongoing)\b", claim_lower):
        feedback_parts.append("'periodic/regular/ongoing' → specify frequency (daily, weekly, monthly, etc.)")

    return "; ".join(feedback_parts) if feedback_parts else "Unspecified generic terms"


def semantic_quantitative_match(qv: QuantitativeValue, fact_claim: str) -> bool:
    """
    Check if a quantitative value is present in a fact claim using semantic matching.

    This improves on simple substring matching by catching variations:
    - "quarterly" matches "every quarter", "each quarter", "every 3 months"
    - "90 days" matches "ninety days", "three months", "90-day period"

    Args:
        qv: Quantitative value to match
        fact_claim: Fact claim text

    Returns:
        True if the quantitative concept is present in the claim
    """
    claim_lower = fact_claim.lower()
    value_lower = qv.value.lower()

    # Direct substring match (original logic)
    if value_lower in claim_lower:
        return True

    # Semantic variations by type
    if qv.type == "frequency":
        # Map common frequency terms to variations
        frequency_mappings = {
            "daily": ["every day", "each day", "per day", "day-to-day"],
            "weekly": ["every week", "each week", "per week", "week-to-week", "7 days"],
            "monthly": ["every month", "each month", "per month", "month-to-month", "30 days"],
            "quarterly": ["every quarter", "each quarter", "per quarter", "3 months", "three months", "every 3 months"],
            "annually": ["every year", "each year", "per year", "yearly", "annual", "12 months", "365 days"],
            "semi-annually": ["twice a year", "every 6 months", "6-month", "biannual"],
        }

        for freq, variations in frequency_mappings.items():
            if freq in value_lower:
                if any(var in claim_lower for var in variations):
                    return True

    elif qv.type == "duration":
        # Handle numeric durations with unit variations
        # "90 days" → "ninety days", "3 months", "90-day"
        match = re.search(r"(\d+)\s*(day|days|month|months|year|years|hour|hours|minute|minutes)", value_lower)
        if match:
            num, unit = match.groups()

            # Check for number as word
            number_words = {
                "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
                "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten",
                "30": "thirty", "60": "sixty", "90": "ninety", "365": "three hundred sixty-five"
            }

            if num in number_words:
                word_form = number_words[num]
                if f"{word_form} {unit}" in claim_lower or f"{word_form}-{unit}" in claim_lower:
                    return True

            # Check for hyphenated form
            if f"{num}-{unit}" in claim_lower:
                return True

            # Check for month/day conversions
            if unit in ["day", "days"]:
                days = int(num)
                if days == 30 and any(term in claim_lower for term in ["1 month", "one month", "monthly"]):
                    return True
                elif days == 90 and any(term in claim_lower for term in ["3 month", "three month", "quarterly"]):
                    return True
                elif days == 365 and any(term in claim_lower for term in ["1 year", "one year", "annual"]):
                    return True

    elif qv.type in ["percentage", "count"]:
        # Handle numeric values with slight variations
        # "90%" → "90 percent", "90.0%"
        match = re.search(r"(\d+\.?\d*)\s*%?", value_lower)
        if match:
            num = match.group(1)
            # Check for variations
            if any(pattern in claim_lower for pattern in [
                f"{num}%",
                f"{num} percent",
                f"{num} per cent",
                f"{float(num):.1f}%",
            ]):
                return True

    return False


def enhance_quantitative_tagging(
    facts: List[ExtractedFact],
    pre_parsed_qv: List[QuantitativeValue],
    chunk_text: str
) -> List[ExtractedFact]:
    """
    Enhanced quantitative tagging using semantic matching.

    This is the V4 improvement to address the judge's #1 critical issue:
    only 7% of facts had quantitative metadata in V3.

    Args:
        facts: List of extracted facts
        pre_parsed_qv: Pre-parsed quantitative values
        chunk_text: Original chunk text

    Returns:
        Facts with enhanced quantitative_values metadata
    """
    enhanced_facts = []

    for fact in facts:
        # Check each pre-parsed quantitative value
        matched_values = []

        for qv in pre_parsed_qv:
            if semantic_quantitative_match(qv, fact.claim):
                matched_values.append(qv.value)

        if matched_values:
            # Merge with existing quantitative_values
            existing_qv = fact.quantitative_values or []
            all_qv = list(set(existing_qv + matched_values))
            fact.quantitative_values = all_qv

        enhanced_facts.append(fact)

    return enhanced_facts


def build_v4_enhanced_prompt_additions() -> str:
    """
    Build additional prompt instructions for V4 to prevent generic extractions.

    This addresses judge's feedback about technical specifications being too generic.

    Returns:
        Additional prompt text to inject
    """
    return """
🚫 **CRITICAL: NEVER USE GENERIC TERMS**

The following are FORBIDDEN in extracted facts (you MUST be specific):

❌ **Generic Technology Terms** (FORBIDDEN):
- "encryption" → ✅ USE: "TLS 1.3", "AES-256-GCM", "RSA-4096"
- "monitoring" → ✅ USE: "SIEM monitoring", "Splunk Enterprise", "Datadog alerts"
- "authentication" → ✅ USE: "multi-factor authentication", "OAuth 2.0", "SAML 2.0"
- "firewall" → ✅ USE: "Palo Alto firewall", "firewall rules restricting ports 80/443"
- "backup system" → ✅ USE: "Veeam backup", "daily incremental backups"

❌ **Generic Roles** (FORBIDDEN):
- "IT staff" or "IT personnel" → ✅ USE: "IT Security team", "Infrastructure team", "Security Operations Center"
- "management" → ✅ USE: "Security Manager", "CISO", "VP of Engineering", "senior management"
- "administrator" → ✅ USE: "system administrator", "database administrator", "network administrator"
- "personnel" → ✅ USE: "authorized personnel", "security personnel", "development team"

❌ **Generic Frequencies** (FORBIDDEN):
- "periodic" or "periodically" → ✅ USE: "daily", "weekly", "monthly", "quarterly", "annually"
- "regular" or "regularly" → ✅ USE: "every 90 days", "twice monthly", "each quarter"
- "ongoing" → ✅ USE: "continuous", "real-time", "daily monitoring"

❌ **Generic Policies** (FORBIDDEN):
- "policies and procedures" → ✅ USE: "Information Security Policy", "Access Control Procedures", "Incident Response Policy"
- "security program" → ✅ USE: "security program includes vulnerability scanning, penetration testing, and incident response"

**EXAMPLES OF GOOD VS BAD EXTRACTIONS:**

❌ BAD (generic): "System uses encryption for data protection"
✅ GOOD (specific): "Data in motion is encrypted using TLS 1.3"

❌ BAD (generic): "IT staff monitors systems"
✅ GOOD (specific): "Security Operations Center monitors system logs using Splunk Enterprise with real-time alerts"

❌ BAD (generic): "Access reviews performed periodically"
✅ GOOD (specific): "IT Security team reviews user access quarterly using automated reporting tool"

❌ BAD (generic): "Password policies are enforced"
✅ GOOD (specific): "Password policy requires minimum 12 characters with complexity requirements enforced via Active Directory GPO"

**IF YOU ENCOUNTER GENERIC TEXT**: Extract multiple specific facts from the surrounding context rather than one generic fact.

**PRIORITY ORDER FOR EXTRACTION**:
1. Specific technical details (protocols, versions, tools, configurations)
2. Exact roles/teams (never "IT staff", always "Security team" or "Operations team")
3. Precise frequencies (never "periodic", always "daily", "weekly", "monthly", etc.)
4. Named policies/procedures (never generic "policies", always "Information Security Policy")
5. Quantitative thresholds (numbers with units: "12 characters", "90 days", "99.95%")

**REMEMBER**: You are replacing human analysts. They would capture specific details, not generic statements. Extract with maximum technical precision.
"""


def filter_low_value_facts(facts: List[ExtractedFact]) -> tuple[List[ExtractedFact], List[ExtractedFact]]:
    """
    Filter out low-value facts (test-only and overly generic).

    This addresses judge's feedback:
    - 40-50% of V3 facts were test-only ("No exceptions noted")
    - Many facts were too generic to be useful

    V4.1 CRITICAL FIX: NEVER filter facts with quantitative values.
    These are high-priority facts needed to meet the 35%+ QV coverage target.

    Args:
        facts: List of all extracted facts

    Returns:
        (high_value_facts, filtered_facts) tuple
    """
    high_value = []
    filtered = []

    for fact in facts:
        # V4.1 PRIORITY: If fact has quantitative values, ALWAYS keep it
        # This is the #1 priority to address judge's critical feedback
        if fact.quantitative_values and len(fact.quantitative_values) > 0:
            high_value.append(fact)
            continue

        # Check if test-only
        if is_test_result_only(fact.claim):
            filtered.append(fact)
            continue

        # Check if overly generic
        if contains_generic_terms(fact.claim):
            # Log the issue for potential recovery
            feedback = get_generic_term_feedback(fact.claim)
            fact.confidence = max(0.3, fact.confidence - 0.3)  # Reduce confidence
            # Still include it but mark as lower quality
            high_value.append(fact)
            continue

        # High-value fact
        high_value.append(fact)

    return high_value, filtered


def get_v4_enhancement_stats(facts: List[ExtractedFact]) -> Dict:
    """
    Calculate V4-specific statistics to track improvements.

    Args:
        facts: List of extracted facts

    Returns:
        Dictionary with V4 enhancement statistics
    """
    total = len(facts)
    if total == 0:
        return {
            "total_facts": 0,
            "facts_with_qv": 0,
            "qv_percentage": 0.0,
            "test_only_facts": 0,
            "test_only_percentage": 0.0,
            "generic_facts": 0,
            "generic_percentage": 0.0,
            "high_specificity_facts": 0,
            "avg_specificity": 0.0,
        }

    qv_count = sum(1 for f in facts if f.quantitative_values and len(f.quantitative_values) > 0)
    test_only_count = sum(1 for f in facts if is_test_result_only(f.claim))
    generic_count = sum(1 for f in facts if contains_generic_terms(f.claim))
    high_spec_count = sum(1 for f in facts if f.specificity_score and f.specificity_score >= 0.7)

    specificity_scores = [f.specificity_score for f in facts if f.specificity_score is not None]
    avg_spec = sum(specificity_scores) / len(specificity_scores) if specificity_scores else 0.0

    return {
        "total_facts": total,
        "facts_with_qv": qv_count,
        "qv_percentage": qv_count / total * 100,
        "test_only_facts": test_only_count,
        "test_only_percentage": test_only_count / total * 100,
        "generic_facts": generic_count,
        "generic_percentage": generic_count / total * 100,
        "high_specificity_facts": high_spec_count,
        "high_specificity_percentage": high_spec_count / total * 100,
        "avg_specificity": avg_spec,
    }
