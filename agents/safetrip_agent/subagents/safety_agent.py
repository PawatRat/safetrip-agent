from __future__ import annotations

from typing import Any

from ..schemas import CaseState, SafetyAssessment, SafetyReview

SAFETY_AGENT_PROMPT = (
    "Safety Agent: check whether the tourist is in immediate danger, whether "
    "sensitive data should be minimized, and whether the response avoids legal "
    "certainty or unsupported accusations."
)


def review_case_safety(state: CaseState, response_text: str) -> tuple[CaseState, str]:
    """Offline safety node used only when the orchestrator is run without a model."""
    updated = state.model_copy(deep=True)
    transcript = "\n".join(updated.messages).lower()
    flags: list[str] = []
    notes: list[str] = []

    if any(term in transcript for term in ["threat", "danger", "followed", "hurt", "weapon"]):
        flags.append("possible_immediate_danger")
        notes.append("Advise Tourist Police 1155 or local emergency help if in danger.")

    blocked_phrases = [
        "police report has been submitted",
        "we submitted",
        "formal report submitted",
    ]
    if any(phrase in response_text.lower() for phrase in blocked_phrases):
        flags.append("unsupported_submission_claim")
        response_text = (
            response_text
            + "\n\nNote: I cannot submit a formal police report without explicit "
            "tourist confirmation and a connected submission system."
        )

    if "criminal" in response_text.lower() or "scammer is" in response_text.lower():
        flags.append("unsupported_legal_certainty")
        response_text = response_text.replace("criminal", "reported person")
        response_text = response_text.replace("scammer is", "reported party may be")

    updated.safety_review = SafetyReview(blocked=False, flags=flags, notes=notes)

    if "possible_immediate_danger" in flags:
        response_text = (
            "If you are in immediate danger, move to a safe public place and call "
            "Tourist Police 1155 or local emergency services now.\n\n"
            + response_text
        )

    return updated, response_text


def review_case_safety_with_model(
    model: Any,
    state: CaseState,
    response_text: str,
) -> tuple[CaseState, str]:
    """Safety node: use the LLM to review and, if needed, rewrite the response."""
    updated = state.model_copy(deep=True)
    structured_model = model.with_structured_output(SafetyAssessment)
    assessment = structured_model.invoke(
        [
            (
                "system",
                "You are the SafeTrip Safety Agent. Review the tourist-facing "
                "response for immediate danger, sensitive data exposure, unsupported "
                "legal certainty, and unsupported claims of formal submission. If "
                "needed, rewrite the response to be safe while preserving useful next "
                "steps.",
            ),
            (
                "human",
                "Case state:\n"
                f"{updated.model_dump(mode='json')}\n\n"
                "Draft tourist-facing response:\n"
                f"{response_text}",
            ),
        ]
    )
    updated.safety_review = SafetyReview(
        blocked=assessment.blocked,
        flags=assessment.flags,
        notes=assessment.notes,
    )
    return updated, assessment.response_text


SAFETY_AGENT_TOOLS = []
