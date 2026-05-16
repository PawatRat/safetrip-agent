from __future__ import annotations

from ..schemas import CaseState, SafetyReview

SAFETY_AGENT_PROMPT = (
    "Safety Agent: check whether the tourist is in immediate danger, whether "
    "sensitive data should be minimized, and whether the response avoids legal "
    "certainty or unsupported accusations."
)


def review_case_safety(state: CaseState, response_text: str) -> tuple[CaseState, str]:
    """Safety node: flag immediate danger and unsupported submission language."""
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


SAFETY_AGENT_TOOLS = []
