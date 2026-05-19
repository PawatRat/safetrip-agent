from __future__ import annotations

from typing import Any

from ..schemas import CaseState, DraftingResult

DRAFTING_AGENT_PROMPT = (
    "Drafting Agent: produce a neutral, structured police-ready report draft "
    "only after required fields are complete. Write enough detail for a tourist "
    "to review before submission. Use cautious wording like 'the tourist "
    "reports'. Do not claim anything has been submitted. End by asking the "
    "tourist to confirm or correct the draft."
)


def draft_report(state: CaseState) -> str:
    """Offline drafting node used only when the orchestrator is run without a model."""
    if not state.report_ready:
        return state.next_question or "Please provide the missing case details first."

    evidence = ", ".join(state.known_evidence_names) or "none listed"

    return (
        "Police-ready report draft for tourist confirmation\n\n"
        f"Case ID: {state.case_id}\n"
        f"Reported scam type: {state.scam_type}\n"
        f"Location: {state.location}\n"
        f"Incident time: {state.incident_time}\n"
        f"Amount lost: {state.amount_lost or 'not specified'}\n"
        f"Evidence noted: {evidence}\n\n"
        "Incident summary:\n"
        f"The tourist reports a {state.scam_type.replace('_', ' ')} incident "
        f"at {state.location} around {state.incident_time}.\n\n"
        "Statement for police review:\n"
        "The tourist states that the information above is true to the best of "
        "their knowledge. The tourist requests assistance reviewing the incident, "
        "preserving the listed evidence, and preparing the matter for the "
        "appropriate tourist police channel.\n\n"
        "Review note:\n"
        "Please read the draft carefully. If any location, time, amount, or "
        "evidence detail is wrong, tell me what to correct before submission.\n\n"
        "Please confirm whether this draft is accurate, or tell me exactly what "
        "to correct."
    )


def draft_report_with_model(model: Any, state: CaseState) -> str:
    """Drafting node: use the LLM to write a neutral tourist-confirmation draft."""
    if not state.report_ready:
        return state.next_question or "Please provide the missing case details first."

    structured_model = model.with_structured_output(DraftingResult)
    result = structured_model.invoke(
        [
            (
                "system",
                "You are the SafeTrip Drafting Agent. Produce a neutral, structured, "
                "police-ready report draft for tourist confirmation. The draft must "
                "be longer than a one-paragraph summary and must use this plain-text "
                "structure:\n\n"
                "Police-ready report draft for tourist confirmation\n\n"
                "Case ID: <case id>\n"
                "Reported scam type: <type>\n"
                "Location: <location>\n"
                "Incident time: <time>\n"
                "Amount lost: <amount or not specified>\n"
                "Evidence noted: <evidence list>\n\n"
                "Incident summary:\n"
                "<neutral paragraph using cautious wording such as 'the tourist "
                "reports' and 'the tourist states'>\n\n"
                "Statement for police review:\n"
                "<formal but readable paragraph describing what the tourist wants "
                "police/Tourist Police to review, without accusing as fact>\n\n"
                "Review note:\n"
                "<ask the tourist to check accuracy before submission>\n\n"
                "Do not state that anything has been submitted, sent, filed, or "
                "accepted by police. Do not guarantee any legal outcome. End by "
                "asking the tourist to confirm or correct the draft.",
            ),
            (
                "human",
                "Case state:\n"
                f"{state.model_dump(mode='json')}",
            ),
        ]
    )
    return result.response_text


DRAFTING_AGENT_TOOLS = []
