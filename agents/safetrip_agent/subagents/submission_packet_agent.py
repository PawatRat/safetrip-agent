from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib import request

from ..schemas import CaseState

DEFAULT_POLICE_SUBMISSION_ENDPOINT = (
    "https://safetripai-func-ejb8gjaffehxfmhn.southeastasia-01.azurewebsites.net"
    "/api/mockchat"
)

HttpPost = Callable[[str, dict], dict]


SUBMISSION_PACKET_AGENT_PROMPT = (
    "Submission Packet Agent: after explicit tourist confirmation, prepare a "
    "structured markdown packet and submit the confirmed case to the configured "
    "police handoff endpoint."
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


def submit_case_to_police_endpoint(
    state: CaseState,
    endpoint: str = DEFAULT_POLICE_SUBMISSION_ENDPOINT,
    http_post: HttpPost | None = None,
) -> tuple[CaseState, dict]:
    """Submit confirmed case payload to the configured police handoff endpoint."""
    payload = build_police_submission_payload(state)
    post = http_post or post_json
    response = post(endpoint, payload)
    updated = state.model_copy(deep=True)
    updated.submission_api_endpoint = endpoint
    updated.submission_api_response = response
    return updated, response


def build_police_submission_payload(state: CaseState) -> dict:
    return {
        "reply": state.draft_text or build_case_reply(state),
        "incident_type": incident_type_for_api(state),
        "severity": severity_for_case(state),
        "should_create_case": True,
        "required_info": ["location", "contact", "time", "evidence"],
    }


def post_json(endpoint: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8")
    if not body:
        return {}
    return json.loads(body)


def build_case_reply(state: CaseState) -> str:
    return (
        f"SafeTrip case {state.case_id}: {state.scam_type}. "
        f"Location: {state.location or 'not specified'}. "
        f"Time: {state.incident_time or 'not specified'}. "
        f"Amount: {state.amount_lost or 'not specified'}. "
        f"Evidence: {', '.join(state.known_evidence_names) or 'none listed'}."
    )


def incident_type_for_api(state: CaseState) -> str:
    if state.scam_type == "unknown":
        return "scam"
    return state.scam_type


def severity_for_case(state: CaseState) -> str:
    if state.scam_type in {"fake_police_or_government", "online_transfer_scam", "physical_assault"}:
        return "high"
    if state.amount_lost:
        return "medium"
    return "medium"


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
    legal_sources = "\n".join(
        f"- {source.get('title', source.get('id', 'source'))}: {source.get('url', '')}"
        for source in (state.reporting_guidance.sources if state.reporting_guidance else [])
    ) or "- None listed"
    recommended_actions = "\n".join(
        f"- {action}"
        for action in (
            state.reporting_guidance.recommended_actions
            if state.reporting_guidance
            else []
        )
    ) or "- None listed"

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
        "## Recommended Actions\n"
        f"{recommended_actions}\n\n"
        "## Legal / Tourist Assistance Sources\n"
        f"{legal_sources}\n\n"
        "## Confirmed Draft\n"
        f"{state.draft_text or 'No draft text stored.'}\n\n"
        "## Tourist Conversation\n"
        f"{transcript}\n\n"
        "## System Notes\n"
        "- This file is a prepared handoff packet. The confirmed case is also posted "
        "to the configured SafeTrip mock police handoff endpoint when submission "
        "confirmation is received.\n"
    )


SUBMISSION_PACKET_AGENT_TOOLS = []
