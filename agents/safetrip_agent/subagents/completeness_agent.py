from __future__ import annotations

from langchain.tools import tool

from ..evidence_rules import SCAM_EVIDENCE_RULES
from ..schemas import CaseState, IntakeState


COMPLETENESS_AGENT_PROMPT = (
    "Completeness Agent: determine whether the case has enough required fields "
    "and evidence to draft a report. If not ready, return only the next best "
    "missing item."
)


@tool
def completeness_check(state: dict) -> dict:
    """Check whether required fields and evidence are enough for draft generation."""
    if "case_id" in state:
        case = update_case_completeness(CaseState.model_validate(state))
        return {
            "report_ready": case.report_ready,
            "missing_evidence": case.missing_items,
            "next_question": case.next_question,
        }

    intake = IntakeState.model_validate(state)
    requirements = SCAM_EVIDENCE_RULES.get(intake.scam_type, [])
    required_names = {r.name for r in requirements if r.required_level == "required"}
    known = set(intake.known_evidence)
    missing = sorted(required_names - known)

    base_missing = []
    if not intake.location:
        base_missing.append("incident_location")
    if not intake.incident_time:
        base_missing.append("incident_time")

    all_missing = base_missing + missing
    return {
        "report_ready": not all_missing and intake.scam_type != "unknown",
        "missing_evidence": all_missing,
        "next_question": build_next_question(all_missing),
    }


def update_case_completeness(state: CaseState) -> CaseState:
    """Completeness node: deterministic report-readiness gate."""
    updated = state.model_copy(deep=True)
    requirements = SCAM_EVIDENCE_RULES.get(updated.scam_type, [])
    required_names = {r.name for r in requirements if r.required_level == "required"}
    known = set(updated.known_evidence_names)
    missing = sorted(required_names - known)

    base_missing = []
    if updated.scam_type == "unknown":
        base_missing.append("scam_type")
    if not updated.location:
        base_missing.append("incident_location")
    if not updated.incident_time:
        base_missing.append("incident_time")

    updated.missing_items = base_missing + missing
    updated.report_ready = not updated.missing_items and updated.scam_type != "unknown"
    updated.next_question = build_next_question(updated.missing_items)
    return updated


def build_next_question(missing: list[str]) -> str | None:
    if not missing:
        return None
    first = missing[0]
    question_map = {
        "scam_type": "What happened in one or two sentences? Include who contacted you and what they asked you to do.",
        "incident_location": "Where in Thailand did this happen? A landmark, shop name, hotel name, or map pin is enough.",
        "incident_time": "When did this happen? An approximate date and time is okay.",
        "transfer_slip_or_transaction_id": "Can you upload the transfer slip or provide the transaction ID?",
        "receiver_account_or_promptpay": "What bank account, PromptPay, wallet, or QR code received the money?",
        "chat_logs": "Can you upload screenshots of the chat, email, SMS, or page where the seller contacted you?",
        "pickup_and_dropoff": "Where did the ride start and end?",
        "fare_requested_and_paid": "How much did the driver ask for, and how much did you pay?",
        "venue_name_location": "What is the venue name and where is it located?",
        "bill_menu_or_receipt_photo": "Can you upload a photo of the bill, receipt, or menu?",
    }
    return question_map.get(first, f"Please provide evidence or details for: {first}.")


COMPLETENESS_AGENT_TOOLS = [completeness_check]
