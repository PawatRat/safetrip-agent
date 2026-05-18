from __future__ import annotations

from typing import Any

from ..schemas import CaseState, PerceptionExtraction
from .evidence_agent import add_evidence_once, get_requirements, infer_evidence_names
from .intake_agent import (
    add_fact_once,
    classify_message,
    extract_amount,
    extract_incident_time,
    extract_location,
)


PERCEPTION_AGENT_PROMPT = (
    "Perception Agent: in a single pass, read the latest tourist message in the "
    "context of the conversation and extract everything new: incident "
    "classification, key facts (location, time, amount), and which evidence "
    "items the tourist has now provided or clearly described. Capture only what "
    "the tourist actually said; never invent details. This runs incrementally "
    "and must not re-derive facts that are already known unless the tourist "
    "corrects them."
)


def _apply_requirements(state: CaseState) -> None:
    state.evidence_requirements = get_requirements(state.scam_type)


def update_case_perception(state: CaseState, message: str) -> CaseState:
    """Offline perception: classify + extract facts + collect evidence in one step.

    The orchestrator has already appended ``message`` to ``state.messages``.
    """
    updated = state.model_copy(deep=True)

    classification = classify_message("\n".join(updated.messages))
    if classification.confidence >= updated.classification_confidence:
        updated.scam_type = classification.scam_type
        updated.classification_confidence = classification.confidence
        updated.classification_rationale = classification.rationale

    location = extract_location(message)
    if location and not updated.location:
        updated.location = location
        add_fact_once(updated, "location", location)

    incident_time = extract_incident_time(message)
    if incident_time and not updated.incident_time:
        updated.incident_time = incident_time
        add_fact_once(updated, "incident_time", incident_time)

    amount = extract_amount(message)
    if amount and not updated.amount_lost:
        updated.amount_lost = amount
        add_fact_once(updated, "amount_lost", amount)

    _apply_requirements(updated)
    for evidence_name in infer_evidence_names(message, updated.scam_type):
        add_evidence_once(
            updated,
            evidence_name,
            f"Tourist mentioned {evidence_name.replace('_', ' ')}.",
        )

    return updated


def update_case_perception_with_model(
    model: Any,
    state: CaseState,
    message: str,
) -> CaseState:
    """LLM perception: one structured extraction for facts + evidence."""
    updated = state.model_copy(deep=True)
    transcript = "\n".join(f"Tourist: {item}" for item in updated.messages)

    structured_model = model.with_structured_output(PerceptionExtraction)
    extraction = structured_model.invoke(
        [
            (
                "system",
                PERCEPTION_AGENT_PROMPT
                + " Return strict structured output. Preserve the tourist's own "
                "wording for location and time.",
            ),
            (
                "human",
                "Already known case state:\n"
                f"scam_type={updated.scam_type}, location={updated.location}, "
                f"incident_time={updated.incident_time}, amount_lost={updated.amount_lost}, "
                f"known_evidence={updated.known_evidence_names}\n\n"
                "Conversation so far:\n"
                f"{transcript}\n\n"
                f"Latest tourist message:\n{message}",
            ),
        ]
    )

    if extraction.scam_type_confidence >= updated.classification_confidence:
        updated.scam_type = extraction.scam_type
        updated.classification_confidence = extraction.scam_type_confidence
        updated.classification_rationale = extraction.rationale

    if extraction.location and not updated.location:
        updated.location = extraction.location
        add_fact_once(updated, "location", extraction.location)

    if extraction.incident_time and not updated.incident_time:
        updated.incident_time = extraction.incident_time
        add_fact_once(updated, "incident_time", extraction.incident_time)

    if extraction.amount_lost and not updated.amount_lost:
        updated.amount_lost = extraction.amount_lost
        add_fact_once(updated, "amount_lost", extraction.amount_lost)

    _apply_requirements(updated)
    allowed = {requirement.name for requirement in updated.evidence_requirements}
    for evidence_name in extraction.evidence_names:
        if evidence_name in allowed:
            add_evidence_once(updated, evidence_name, "Tourist described this evidence.")

    return updated


PERCEPTION_AGENT_TOOLS: list = []
