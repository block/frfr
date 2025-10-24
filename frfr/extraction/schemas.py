"""Schemas for structured fact extraction."""

from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class EvidenceQuote(BaseModel):
    """A single piece of evidence supporting a fact (V5)."""

    quote: str = Field(
        ...,
        description="Exact text from document (must match exactly)",
    )
    source_location: str = Field(
        ...,
        description="Location of this quote (e.g., 'Lines 42-45', 'Page 3, Section 2.1')",
    )
    relevance: Optional[str] = Field(
        None,
        description="Why this quote supports the claim (optional context)",
    )


class ExtractedFact(BaseModel):
    """A single fact extracted from a document."""

    claim: str = Field(
        ...,
        description="The specific assertion or fact being claimed",
    )
    source_doc: str = Field(
        ...,
        description="The source document filename",
    )
    source_location: str = Field(
        ...,
        description="Location in source document (e.g., 'Page 42, Section 4.2.1')",
    )

    # V5: Support multiple evidence quotes (backward compatible with V4)
    evidence_quote: Optional[str] = Field(
        None,
        description="DEPRECATED in V5: Single evidence quote (for V4 compatibility). Use evidence_quotes instead.",
    )
    evidence_quotes: Optional[List[EvidenceQuote]] = Field(
        None,
        description="V5: Multiple evidence quotes supporting this fact (recommended format)",
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this fact (0.0-1.0)",
    )

    @model_validator(mode='after')
    def validate_evidence(self):
        """Ensure at least one evidence source is provided and normalize to evidence_quotes."""
        # If new format provided, we're good
        if self.evidence_quotes and len(self.evidence_quotes) > 0:
            return self

        # If legacy format provided, convert to new format
        if self.evidence_quote:
            self.evidence_quotes = [EvidenceQuote(
                quote=self.evidence_quote,
                source_location=self.source_location,
                relevance=None
            )]
            return self

        # Neither provided - error
        raise ValueError("Must provide either evidence_quote (V4) or evidence_quotes (V5)")

    def get_primary_quote(self) -> str:
        """Get the primary evidence quote for backward compatibility."""
        if self.evidence_quotes and len(self.evidence_quotes) > 0:
            return self.evidence_quotes[0].quote
        return self.evidence_quote or ""

    def get_all_quotes(self) -> List[str]:
        """Get all evidence quotes as a list of strings."""
        if self.evidence_quotes:
            return [eq.quote for eq in self.evidence_quotes]
        return [self.evidence_quote] if self.evidence_quote else []

    # Enhanced metadata fields
    fact_type: Optional[str] = Field(
        None,
        description="Type of fact: technical_control, organizational, process, metric, CUEC, test_result, architecture, compliance",
    )
    control_family: Optional[str] = Field(
        None,
        description="Control family: access_control, encryption, monitoring, backup_recovery, change_management, incident_response",
    )
    specificity_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Specificity score (0.0=generic, 1.0=highly specific with technical details)",
    )
    entities: Optional[List[str]] = Field(
        None,
        description="Named entities: tools, technologies, protocols, standards (e.g., AWS, TLS 1.2, NIST, Splunk)",
    )
    quantitative_values: Optional[List[str]] = Field(
        None,
        description="Quantitative values extracted: numbers, percentages, timeframes (e.g., 90 days, 256-bit, 99.9%)",
    )
    process_details: Optional[dict] = Field(
        None,
        description="Process details: {who: role, when: frequency, how: procedure}",
    )
    section_context: Optional[str] = Field(
        None,
        description="Section context: System Description, Control Testing, CUEC, Privacy, etc.",
    )
    related_control_ids: Optional[List[str]] = Field(
        None,
        description="Related control IDs (e.g., CC6.1, A.1.2)",
    )
    auto_generated: Optional[bool] = Field(
        False,
        description="Whether this fact was auto-generated (skips validation against source text)",
    )


class FactExtractionResult(BaseModel):
    """Result from a single LLM instance's fact extraction."""

    instance_id: str = Field(
        ...,
        description="Unique identifier for this swarm instance",
    )
    facts: List[ExtractedFact] = Field(
        default_factory=list,
        description="List of extracted facts",
    )
    model_used: str = Field(
        ...,
        description="Model identifier used for extraction",
    )
    seed: int = Field(
        ...,
        description="Random seed used for this instance",
    )


class FactCluster(BaseModel):
    """A cluster of semantically similar facts."""

    cluster_id: str = Field(
        ...,
        description="Unique identifier for this cluster",
    )
    facts: List[ExtractedFact] = Field(
        default_factory=list,
        description="Facts in this cluster",
    )
    centroid_embedding: Optional[List[float]] = Field(
        None,
        description="Centroid embedding for this cluster",
    )
    consensus_reached: bool = Field(
        False,
        description="Whether plurality consensus was reached",
    )
    has_contradiction: bool = Field(
        False,
        description="Whether contradictory facts were detected",
    )


class ConsensusFact(BaseModel):
    """A fact that reached consensus from the swarm."""

    claim: str = Field(
        ...,
        description="The consensus claim",
    )
    source_doc: str = Field(
        ...,
        description="Source document",
    )
    source_location: str = Field(
        ...,
        description="Location in source",
    )
    evidence_quote: str = Field(
        ...,
        description="Exact supporting text",
    )
    confidence: float = Field(
        ...,
        description="Consensus confidence score",
    )
    support_count: int = Field(
        ...,
        description="Number of instances that reported this fact",
    )
    total_instances: int = Field(
        ...,
        description="Total number of swarm instances",
    )


class Contradiction(BaseModel):
    """A detected contradiction between facts."""

    contradiction_id: str = Field(
        ...,
        description="Unique identifier for this contradiction",
    )
    conflicting_facts: List[ExtractedFact] = Field(
        ...,
        description="The facts that contradict each other",
    )
    resolution: Optional[str] = Field(
        None,
        description="Judge's resolution of the contradiction",
    )
    resolved_fact: Optional[ConsensusFact] = Field(
        None,
        description="The fact determined to be correct after resolution",
    )


class AnswerSynthesis(BaseModel):
    """Final synthesized answer to user's question."""

    question: str = Field(
        ...,
        description="The user's question",
    )
    answer: str = Field(
        ...,
        description="The synthesized answer",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the answer",
    )
    supporting_facts: List[ConsensusFact] = Field(
        default_factory=list,
        description="Consensus facts supporting this answer",
    )
    contradictions_resolved: List[Contradiction] = Field(
        default_factory=list,
        description="Contradictions that were resolved",
    )
    outliers_discarded: int = Field(
        0,
        description="Number of outlier facts discarded",
    )
