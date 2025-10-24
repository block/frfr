"""
Extraction patterns and rules for high-fidelity fact extraction.

This module provides regex patterns, parsing logic, and structured templates
for extracting quantitative data, technical specifications, and structured
control information from SOC 2 reports and similar compliance documents.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class QuantitativeValue:
    """Structured representation of a quantitative value."""
    value: str
    type: str  # frequency, duration, sample_size, percentage, count, threshold
    normalized: Optional[str] = None  # Normalized representation


@dataclass
class ControlTableRow:
    """Parsed control table row (3-column SOC 2 format)."""
    control_description: str
    test_performed: str
    test_results: str
    control_id: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None


class ExtractionPatterns:
    """
    Patterns for extracting structured information from compliance documents.
    """

    # Frequency patterns
    FREQUENCY_PATTERNS = [
        # Specific frequencies
        r'\b(daily|weekly|monthly|quarterly|semi-annually|annually|yearly)\b',
        r'\bevery\s+\d+\s+(day|days|week|weeks|month|months|quarter|quarters|year|years)\b',
        r'\b\d+\s+times?\s+per\s+(day|week|month|quarter|year)\b',
        r'\b(real-time|continuous|continuously|ongoing)\b',
        r'\bupon\s+(occurrence|detection|notification|request)\b',
        r'\bwithin\s+\d+\s+(hour|hours|day|days|business\s+days?)\b',
        r'\b(at\s+least|no\s+less\s+than|minimum\s+of)\s+\d+\s+times?\s+(per|each)\s+(day|week|month|quarter|year)\b',
        r'\bon\s+a\s+(daily|weekly|monthly|quarterly|yearly|regular)\s+basis\b',
    ]

    # Duration patterns
    DURATION_PATTERNS = [
        r'\b\d+\s+(day|days|week|weeks|month|months|quarter|quarters|year|years)\b',
        r'\b\d+\s+(hour|hours|minute|minutes|second|seconds)\b',
        r'\b\d+-(?:day|week|month|year)\s+(?:period|retention|window)\b',
    ]

    # Sample size patterns
    SAMPLE_SIZE_PATTERNS = [
        r'\bsampled?\s+\d+\s+(?:of\s+\d+)?\s*(?:items?|users?|employees?|tickets?|controls?|instances?|requests?|reviews?|reports?)?\b',
        r'\bsample\s+of\s+\d+\b',
        r'\binspected\s+(?:all\s+)?\d+\s+(?:items?|users?|employees?|tickets?|controls?|instances?|requests?|reviews?|reports?)\b',
        r'\btested\s+\d+\s+(?:items?|users?|employees?|tickets?|controls?|instances?)\b',
        r'\b(?:reviewed|examined|analyzed)\s+\d+\s+(?:out\s+of\s+)?\d*\s*(?:items?|samples?)\b',
    ]

    # Percentage/threshold patterns
    PERCENTAGE_PATTERNS = [
        r'\b\d+(?:\.\d+)?%\b',
        r'\b\d+\s+percent\b',
        r'\b(?:greater|less|more|fewer)\s+than\s+\d+%?\b',
        r'\b(?:at|above|below|exceeds|falls\s+below)\s+\d+%?\b',
        r'\buptime\s+of\s+\d+(?:\.\d+)?%\b',
    ]

    # Count patterns
    COUNT_PATTERNS = [
        r'\b\d+\s+(?:employees?|users?|offices?|countries|locations?|servers?|systems?|controls?|policies|procedures?)\b',
        r'\b\d+\+?\s+(?:employees?|users?|offices?)\b',
        r'\b(?:over|more\s+than|approximately)\s+\d+(?:,\d+)?\s+(?:employees?|users?|offices?|countries)\b',
    ]

    # Technical specification patterns
    ENCRYPTION_PATTERNS = [
        r'\b(?:TLS|SSL)\s+(?:v?(?:1\.0|1\.1|1\.2|1\.3))?\b',
        r'\b(?:AES|RSA|SHA|MD5)-?\d+\b',
        r'\b\d+-bit\s+(?:encryption|key|algorithm)\b',
        r'\b(?:AES|RSA|SHA|DES|3DES|Blowfish|bcrypt)\b',
    ]

    AUTHENTICATION_PATTERNS = [
        r'\b(?:two|2|multi)[-\s]?factor\s+authentication\b',
        r'\b(?:MFA|2FA|SSO|SAML|OAuth|LDAP|AD|Kerberos)\b',
        r'\bpassword\s+(?:complexity|length|history|age)\b',
        r'\b(?:minimum|maximum)\s+password\s+(?:length|age)\s+of\s+\d+\b',
    ]

    NETWORK_PATTERNS = [
        r'\b(?:firewall|IDS|IPS|DMZ|VPN|VLAN)\b',
        r'\b(?:port|ports)\s+\d+(?:\s+and\s+\d+)?\b',
        r'\b(?:stateful|stateless)\s+(?:packet\s+)?inspection\b',
        r'\b(?:inbound|outbound)\s+(?:traffic|connections?|rules?)\b',
    ]

    # Role/WHO patterns
    ROLE_PATTERNS = [
        r'\b(?:Chief|Senior|VP\s+of|Vice\s+President\s+of|Director\s+of|Manager\s+of|Head\s+of)\s+[A-Z][a-zA-Z\s]+\b',
        r'\b(?:Security|IT|Privacy|Compliance|Risk|Audit|Operations?|Engineering)\s+(?:Team|Officer|Administrator|Manager|Personnel|Staff|Department)\b',
        r'\b(?:CISO|CIO|CTO|CPO|DPO|CSO)\b',
        r'\b(?:authorized|designated|responsible)\s+personnel\b',
    ]

    @classmethod
    def extract_frequencies(cls, text: str) -> List[QuantitativeValue]:
        """Extract all frequency mentions from text."""
        frequencies = []
        for pattern in cls.FREQUENCY_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                frequencies.append(QuantitativeValue(
                    value=match.group(0),
                    type="frequency",
                    normalized=cls._normalize_frequency(match.group(0))
                ))
        return frequencies

    @classmethod
    def extract_durations(cls, text: str) -> List[QuantitativeValue]:
        """Extract all duration mentions from text."""
        durations = []
        for pattern in cls.DURATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                durations.append(QuantitativeValue(
                    value=match.group(0),
                    type="duration"
                ))
        return durations

    @classmethod
    def extract_sample_sizes(cls, text: str) -> List[QuantitativeValue]:
        """Extract all sample size mentions from text."""
        samples = []
        for pattern in cls.SAMPLE_SIZE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                samples.append(QuantitativeValue(
                    value=match.group(0),
                    type="sample_size"
                ))
        return samples

    @classmethod
    def extract_percentages(cls, text: str) -> List[QuantitativeValue]:
        """Extract all percentage/threshold mentions from text."""
        percentages = []
        for pattern in cls.PERCENTAGE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                percentages.append(QuantitativeValue(
                    value=match.group(0),
                    type="percentage"
                ))
        return percentages

    @classmethod
    def extract_counts(cls, text: str) -> List[QuantitativeValue]:
        """Extract all count mentions from text."""
        counts = []
        for pattern in cls.COUNT_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                counts.append(QuantitativeValue(
                    value=match.group(0),
                    type="count"
                ))
        return counts

    @classmethod
    def extract_all_quantitative(cls, text: str) -> List[QuantitativeValue]:
        """Extract all quantitative values from text."""
        return (
            cls.extract_frequencies(text) +
            cls.extract_durations(text) +
            cls.extract_sample_sizes(text) +
            cls.extract_percentages(text) +
            cls.extract_counts(text)
        )

    @classmethod
    def extract_encryption_specs(cls, text: str) -> List[str]:
        """Extract encryption specifications."""
        specs = []
        for pattern in cls.ENCRYPTION_PATTERNS:
            specs.extend(re.findall(pattern, text, re.IGNORECASE))
        return list(set(specs))

    @classmethod
    def extract_authentication_specs(cls, text: str) -> List[str]:
        """Extract authentication specifications."""
        specs = []
        for pattern in cls.AUTHENTICATION_PATTERNS:
            specs.extend(re.findall(pattern, text, re.IGNORECASE))
        return list(set(specs))

    @classmethod
    def extract_network_specs(cls, text: str) -> List[str]:
        """Extract network specifications."""
        specs = []
        for pattern in cls.NETWORK_PATTERNS:
            specs.extend(re.findall(pattern, text, re.IGNORECASE))
        return list(set(specs))

    @classmethod
    def extract_roles(cls, text: str) -> List[str]:
        """Extract role/WHO mentions."""
        roles = []
        for pattern in cls.ROLE_PATTERNS:
            roles.extend(re.findall(pattern, text, re.IGNORECASE))
        return list(set(roles))

    @classmethod
    def _normalize_frequency(cls, freq_text: str) -> str:
        """Normalize frequency to standard form."""
        freq_lower = freq_text.lower()
        if "daily" in freq_lower or "every day" in freq_lower:
            return "daily"
        elif "weekly" in freq_lower or "every week" in freq_lower:
            return "weekly"
        elif "monthly" in freq_lower or "every month" in freq_lower:
            return "monthly"
        elif "quarterly" in freq_lower or "every quarter" in freq_lower:
            return "quarterly"
        elif "annually" in freq_lower or "yearly" in freq_lower or "every year" in freq_lower:
            return "annually"
        elif "real-time" in freq_lower or "continuous" in freq_lower:
            return "continuous"
        else:
            return freq_text


class ControlTableParser:
    """
    Parser for SOC 2 three-column control tables.

    Handles the collapsed table format produced by PDF extraction where
    control description, test performed, and test results appear as
    running text separated by specific patterns.
    """

    # Patterns for identifying table sections
    CONTROL_START_PATTERN = r'^[A-Z]{2,3}\d+\.\d+\s+'  # e.g., "CC6.1 ", "PI1.2 "
    TEST_INTRO_PATTERNS = [
        r'Inspected\s+',
        r'Observed\s+',
        r'Performed\s+',
        r'Conducted\s+',
        r'Reviewed\s+',
        r'Examined\s+',
        r'Validated\s+',
        r'Tested\s+',
    ]
    RESULT_PATTERN = r'\bNo\s+Exceptions?\s+Noted\b'

    @classmethod
    def parse_control_rows(cls, text: str, start_line: int = 0) -> List[ControlTableRow]:
        """
        Parse control table rows from text.

        Args:
            text: Text containing control table rows
            start_line: Starting line number for line tracking

        Returns:
            List of parsed ControlTableRow objects
        """
        rows = []
        lines = text.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Check if this is a control description
            control_id_match = re.match(cls.CONTROL_START_PATTERN, line)
            if control_id_match:
                control_id = control_id_match.group(0).strip()

                # Accumulate control description until we hit test performed
                control_lines = []
                j = i
                while j < len(lines):
                    current_line = lines[j].strip()

                    # Check if we hit a test intro pattern
                    is_test = any(re.search(pattern, current_line, re.IGNORECASE)
                                for pattern in cls.TEST_INTRO_PATTERNS)
                    if is_test and j > i:
                        break

                    control_lines.append(current_line)
                    j += 1

                control_desc = ' '.join(control_lines)

                # Now accumulate test performed until we hit results
                test_lines = []
                while j < len(lines):
                    current_line = lines[j].strip()

                    # Check if we hit the results pattern
                    if re.search(cls.RESULT_PATTERN, current_line, re.IGNORECASE):
                        test_lines.append(current_line)
                        j += 1
                        break

                    test_lines.append(current_line)
                    j += 1

                test_performed = ' '.join(test_lines)

                # Extract results (usually just "No Exceptions Noted")
                test_results = "No Exceptions Noted" if "No Exception" in test_performed else "Unknown"

                if control_desc and test_performed:
                    rows.append(ControlTableRow(
                        control_description=control_desc,
                        test_performed=test_performed,
                        test_results=test_results,
                        control_id=control_id,
                        start_line=start_line + i,
                        end_line=start_line + j
                    ))

                i = j
            else:
                # Try to identify control rows by test pattern markers
                # This catches controls without explicit control IDs
                is_test_intro = any(re.search(pattern, line, re.IGNORECASE)
                                   for pattern in cls.TEST_INTRO_PATTERNS)

                if is_test_intro:
                    # Backtrack to find control description
                    control_lines = []
                    k = i - 1
                    while k >= 0 and not re.search(cls.RESULT_PATTERN, lines[k], re.IGNORECASE):
                        if lines[k].strip():
                            control_lines.insert(0, lines[k].strip())
                        k -= 1
                        if len(control_lines) > 5:  # Reasonable limit
                            break

                    control_desc = ' '.join(control_lines) if control_lines else ""

                    # Accumulate test and results
                    test_lines = []
                    j = i
                    while j < len(lines):
                        current_line = lines[j].strip()
                        test_lines.append(current_line)

                        if re.search(cls.RESULT_PATTERN, current_line, re.IGNORECASE):
                            j += 1
                            break
                        j += 1

                    test_performed = ' '.join(test_lines)
                    test_results = "No Exceptions Noted" if "No Exception" in test_performed else "Unknown"

                    if control_desc:
                        rows.append(ControlTableRow(
                            control_description=control_desc,
                            test_performed=test_performed,
                            test_results=test_results,
                            control_id=None,
                            start_line=start_line + k + 1,
                            end_line=start_line + j
                        ))

                    i = j
                else:
                    i += 1

        return rows

    @classmethod
    def extract_control_facts(cls, row: ControlTableRow) -> List[Dict]:
        """
        Extract multiple atomic facts from a single control table row.

        This implements the critical "fact density" improvement by extracting:
        - The control existence fact
        - WHO performs the control
        - WHEN the control is performed (frequency)
        - HOW the control is performed (tools, methods)
        - WHAT is controlled (specific systems/data/processes)
        - Test methodology
        - Test sample size
        - Test results (if exceptions exist)

        Args:
            row: Parsed control table row

        Returns:
            List of fact dictionaries
        """
        facts = []

        # Extract from control description
        control_text = row.control_description

        # Fact 1: Main control statement (existence)
        facts.append({
            "claim": control_text,
            "fact_type": "technical_control",
            "source_location": f"Lines {row.start_line}-{row.end_line}",
            "evidence_quote": control_text,
        })

        # Fact 2-N: Extract quantitative values
        quantitative_values = ExtractionPatterns.extract_all_quantitative(control_text)
        for qv in quantitative_values:
            if qv.type == "frequency":
                facts.append({
                    "claim": f"Control performed {qv.value}",
                    "fact_type": "process",
                    "quantitative_values": [qv.value],
                    "source_location": f"Lines {row.start_line}-{row.end_line}",
                    "evidence_quote": control_text,
                })

        # Fact N+1: Roles mentioned
        roles = ExtractionPatterns.extract_roles(control_text)
        for role in roles:
            facts.append({
                "claim": f"{role} is responsible for control execution",
                "fact_type": "organizational",
                "process_details": {"who": role},
                "source_location": f"Lines {row.start_line}-{row.end_line}",
                "evidence_quote": control_text,
            })

        # Fact N+2: Technical specifications
        encryption_specs = ExtractionPatterns.extract_encryption_specs(control_text)
        auth_specs = ExtractionPatterns.extract_authentication_specs(control_text)
        network_specs = ExtractionPatterns.extract_network_specs(control_text)

        all_specs = encryption_specs + auth_specs + network_specs
        for spec in all_specs:
            facts.append({
                "claim": f"System uses {spec}",
                "fact_type": "technical_control",
                "entities": [spec],
                "source_location": f"Lines {row.start_line}-{row.end_line}",
                "evidence_quote": control_text,
            })

        # Extract from test performed
        test_text = row.test_performed
        sample_sizes = ExtractionPatterns.extract_sample_sizes(test_text)

        for sample in sample_sizes:
            facts.append({
                "claim": f"Auditor tested {sample.value}",
                "fact_type": "test_result",
                "quantitative_values": [sample.value],
                "source_location": f"Lines {row.start_line}-{row.end_line}",
                "evidence_quote": test_text,
            })

        return facts


def calculate_specificity_score(fact_dict: Dict) -> float:
    """
    Calculate specificity score based on presence of concrete details.

    Scoring criteria:
    - Base score: 0.3
    - Has quantitative values: +0.2
    - Has named entities (tools/technologies): +0.2
    - Has specific roles (not generic "management"): +0.2
    - Has process details (WHO/WHEN/HOW): +0.1 each
    - Contains vague terms ("periodically", "as needed"): -0.2

    Args:
        fact_dict: Dictionary containing fact data

    Returns:
        Specificity score from 0.0 to 1.0
    """
    score = 0.3  # Base score

    # Check for quantitative values
    if fact_dict.get("quantitative_values") and len(fact_dict["quantitative_values"]) > 0:
        score += 0.2

    # Check for named entities
    if fact_dict.get("entities") and len(fact_dict["entities"]) > 0:
        score += 0.2

    # Check for specific roles
    process_details = fact_dict.get("process_details") or {}
    who = process_details.get("who", "") if isinstance(process_details, dict) else ""
    if who and who.lower() not in ["management", "personnel", "staff", "it personnel"]:
        score += 0.2

    # Check for process details
    if isinstance(process_details, dict):
        if process_details.get("who"):
            score += 0.1
        if process_details.get("when"):
            score += 0.1
        if process_details.get("how"):
            score += 0.1

    # Penalize vague terms
    claim = fact_dict.get("claim", "").lower()
    vague_terms = ["periodically", "regularly", "as needed", "as appropriate", "certain", "various"]
    if any(term in claim for term in vague_terms):
        score -= 0.2

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, score))
