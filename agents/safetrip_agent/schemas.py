from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from typing import Literal

from pydantic import BaseModel, Field


ScamType = Literal[
    "taxi_overcharge",
    "rental_damage_claim",
    "fake_accommodation",
    "tour_package_or_illegal_guide",
    "online_transfer_scam",
    "fake_police_or_government",
    "restaurant_or_venue_overcharge",
    "unknown",
]


class EvidenceRequirement(BaseModel):
    name: str
    required_level: Literal["required", "strongly_recommended", "conditional", "optional"]
    reason: str


class ClassificationResult(BaseModel):
    scam_type: ScamType = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""
    matched_signals: list[str] = Field(default_factory=list)


class CaseFactExtraction(BaseModel):
    scam_type: ScamType = "unknown"
    scam_type_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""
    location: str | None = None
    incident_time: str | None = None
    amount_lost: str | None = None
    evidence_names: list[str] = Field(default_factory=list)


class EvidenceExtraction(BaseModel):
    evidence_names: list[str] = Field(default_factory=list)
    notes: str = ""


class CompletenessAssessment(BaseModel):
    report_ready: bool = False
    missing_items: list[str] = Field(default_factory=list)
    next_question: str | None = None
    rationale: str = ""


class GuidanceSelection(BaseModel):
    route: str
    source_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class DraftingResult(BaseModel):
    response_text: str


class SafetyAssessment(BaseModel):
    blocked: bool = False
    flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    response_text: str


class CaseFact(BaseModel):
    name: str
    value: str
    source: Literal["user_message", "system", "officer"] = "user_message"


class EvidenceItem(BaseModel):
    id: str = Field(default_factory=lambda: f"ev_{uuid4().hex[:12]}")
    name: str
    description: str | None = None
    source: Literal["user_message", "upload", "system"] = "user_message"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SafetyReview(BaseModel):
    blocked: bool = False
    flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ReportingGuidance(BaseModel):
    route: str
    source_ids: list[str] = Field(default_factory=list)


class CaseState(BaseModel):
    case_id: str = Field(default_factory=lambda: f"case_{uuid4().hex[:12]}")
    language: str | None = None
    scam_type: ScamType = "unknown"
    classification_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    classification_rationale: str | None = None
    location: str | None = None
    incident_time: str | None = None
    amount_lost: str | None = None
    facts: list[CaseFact] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    next_question: str | None = None
    report_ready: bool = False
    reporting_guidance: ReportingGuidance | None = None
    safety_review: SafetyReview = Field(default_factory=SafetyReview)
    user_confirmed_submission: bool = False
    messages: list[str] = Field(default_factory=list)

    @property
    def known_evidence_names(self) -> list[str]:
        return sorted({item.name for item in self.evidence})


class IntakeState(BaseModel):
    tourist_message: str
    language: str | None = None
    location: str | None = None
    incident_time: str | None = None
    scam_type: ScamType = "unknown"
    amount_lost: str | None = None
    known_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    next_question: str | None = None
    report_ready: bool = False
