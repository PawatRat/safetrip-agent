from __future__ import annotations

from ..schemas import CaseState

DRAFTING_AGENT_PROMPT = (
    "Drafting Agent: produce a neutral Thai/English police-ready report draft "
    "only after required fields are complete. Use wording like 'the tourist "
    "reports' and ask for tourist confirmation before submission."
)


def draft_report(state: CaseState) -> str:
    """Drafting node: only produce report text after deterministic readiness gate."""
    if not state.report_ready:
        return state.next_question or "Please provide the missing case details first."

    guidance = state.reporting_guidance.route if state.reporting_guidance else ""
    source_ids = (
        ", ".join(state.reporting_guidance.source_ids)
        if state.reporting_guidance
        else "none"
    )
    evidence = ", ".join(state.known_evidence_names) or "none listed"

    return (
        "Case draft for tourist confirmation\n\n"
        f"Case ID: {state.case_id}\n"
        f"Reported scam type: {state.scam_type}\n"
        f"Location: {state.location}\n"
        f"Incident time: {state.incident_time}\n"
        f"Amount lost: {state.amount_lost or 'not specified'}\n"
        f"Evidence noted: {evidence}\n\n"
        "Neutral incident summary:\n"
        f"The tourist reports a {state.scam_type.replace('_', ' ')} incident "
        f"at {state.location} around {state.incident_time}. "
        "The tourist should review this summary and confirm that it is accurate "
        "before any formal submission.\n\n"
        f"Suggested reporting route: {guidance}\n"
        f"Source IDs: {source_ids}\n\n"
        "Please confirm whether this draft is accurate or tell me what to correct."
    )


DRAFTING_AGENT_TOOLS = []
