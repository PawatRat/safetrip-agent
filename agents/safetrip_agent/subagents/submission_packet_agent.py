from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..schemas import CaseState


SUBMISSION_PACKET_AGENT_PROMPT = (
    "Submission Packet Agent: after explicit tourist confirmation, prepare a "
    "structured markdown packet for police handoff. Do not claim API submission."
)


def write_submission_packet(state: CaseState, output_root: Path) -> tuple[CaseState, Path]:
    """Write a police handoff packet after tourist confirmation."""
    updated = state.model_copy(deep=True)
    case_dir = output_root / updated.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    packet_path = case_dir / "police_submission.md"
    packet_path.write_text(build_submission_packet_markdown(updated), encoding="utf-8")
    updated.submission_packet_path = str(packet_path)
    updated.workflow_stage = "submission_packet_written"
    return updated, packet_path


def build_submission_packet_markdown(state: CaseState) -> str:
    created_at = datetime.now(timezone.utc).isoformat()
    evidence_rows = "\n".join(
        f"- `{item.name}`: {item.description or 'described by tourist'}"
        for item in state.evidence
    ) or "- None listed"
    requirement_rows = "\n".join(
        f"- `{item.name}` ({item.required_level}): {item.reason}"
        for item in state.evidence_requirements
    ) or "- None listed"
    facts = "\n".join(f"- `{fact.name}`: {fact.value}" for fact in state.facts) or "- None listed"
    transcript = "\n".join(f"- Tourist: {message}" for message in state.messages) or "- None"
    source_ids = (
        ", ".join(state.reporting_guidance.source_ids)
        if state.reporting_guidance
        else "none"
    )

    return (
        "# SafeTrip Police Submission Packet\n\n"
        "## Case Metadata\n"
        f"- Case ID: `{state.case_id}`\n"
        f"- Created at: {created_at}\n"
        f"- Workflow stage: {state.workflow_stage}\n"
        f"- Tourist confirmed submission: {state.user_confirmed_submission}\n\n"
        "## Classification\n"
        f"- Scam type: `{state.scam_type}`\n"
        f"- Confidence: {state.classification_confidence:.2f}\n"
        f"- Rationale: {state.classification_rationale or 'not provided'}\n\n"
        "## Incident Facts\n"
        f"- Location: {state.location or 'not specified'}\n"
        f"- Incident time: {state.incident_time or 'not specified'}\n"
        f"- Amount lost: {state.amount_lost or 'not specified'}\n\n"
        "## Extracted Facts\n"
        f"{facts}\n\n"
        "## Evidence Requirements\n"
        f"{requirement_rows}\n\n"
        "## Evidence Collected\n"
        f"{evidence_rows}\n\n"
        "## Reporting Guidance\n"
        f"- Route: {state.reporting_guidance.route if state.reporting_guidance else 'not provided'}\n"
        f"- Source IDs: {source_ids}\n\n"
        "## Confirmed Draft\n"
        f"{state.draft_text or 'No draft text stored.'}\n\n"
        "## Tourist Conversation\n"
        f"{transcript}\n\n"
        "## System Notes\n"
        "- This file is a prepared handoff packet. It is not proof that a formal "
        "police report was submitted through an external system.\n"
    )


SUBMISSION_PACKET_AGENT_TOOLS = []
