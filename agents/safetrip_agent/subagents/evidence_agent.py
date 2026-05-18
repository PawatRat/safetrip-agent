from __future__ import annotations

import re
from typing import Any

from langchain.tools import tool

from ..evidence_rules import SCAM_EVIDENCE_RULES
from ..schemas import CaseState, EvidenceExtraction, EvidenceItem, EvidenceRequirement, ScamType


EVIDENCE_AGENT_PROMPT = (
    "Evidence Agent: return the required and recommended evidence checklist for "
    "the detected scam type. Keep evidence requests relevant to the case."
)


@tool
def get_evidence_requirements(scam_type: ScamType) -> list[dict]:
    """Return evidence requirements for a SafeTrip scam type."""
    return [item.model_dump() for item in SCAM_EVIDENCE_RULES.get(scam_type, [])]


def get_requirements(scam_type: ScamType) -> list[EvidenceRequirement]:
    return SCAM_EVIDENCE_RULES.get(scam_type, [])


def update_case_evidence(state: CaseState, message: str) -> CaseState:
    """Offline evidence node used only when the orchestrator is run without a model."""
    updated = state.model_copy(deep=True)
    updated.evidence_requirements = [
        EvidenceRequirement.model_validate(item)
        for item in get_evidence_requirements.invoke({"scam_type": updated.scam_type})
    ]

    for evidence_name in infer_evidence_names(message, updated.scam_type):
        if evidence_name not in updated.known_evidence_names:
            updated.evidence.append(
                EvidenceItem(
                    name=evidence_name,
                    description=f"Tourist mentioned {evidence_name.replace('_', ' ')}.",
                )
            )

    return updated


def update_case_evidence_with_model(model: Any, state: CaseState, message: str) -> CaseState:
    """Evidence node: use the LLM to identify evidence, with rule data only as tool context."""
    updated = state.model_copy(deep=True)
    requirements = [
        EvidenceRequirement.model_validate(item)
        for item in get_evidence_requirements.invoke({"scam_type": updated.scam_type})
    ]
    updated.evidence_requirements = requirements

    allowed_names = [requirement.name for requirement in requirements]
    structured_model = model.with_structured_output(EvidenceExtraction)
    extraction = structured_model.invoke(
        [
            (
                "system",
                "You are the SafeTrip Evidence Agent. Decide which required or "
                "recommended evidence items the tourist has already provided or "
                "clearly described. Use only evidence_names from the allowed list. "
                "Do not require exact wording; infer from natural language.",
            ),
            (
                "human",
                "Allowed evidence requirements:\n"
                f"{[item.model_dump() for item in requirements]}\n\n"
                "Known evidence already attached:\n"
                f"{updated.known_evidence_names}\n\n"
                "Conversation:\n"
                f"{format_transcript(updated.messages)}\n\n"
                f"Latest tourist message:\n{message}",
            ),
        ]
    )

    allowed = set(allowed_names)
    for evidence_name in extraction.evidence_names:
        if evidence_name not in allowed:
            continue
        add_evidence_once(updated, evidence_name, "Tourist described this evidence.")

    return updated


def infer_evidence_names(message: str, scam_type: ScamType) -> list[str]:
    text = message.lower()
    aliases: dict[str, list[str]] = {
        "property_listing_url": ["listing", "url", "facebook page", "page"],
        "payment_record": ["payment", "paid", "transfer", "receipt", "slip"],
        "seller_chat_or_email": ["chat", "email", "messages", "conversation"],
        "booking_reference": ["booking reference", "reservation", "booking id"],
        "transfer_slip_or_transaction_id": ["transfer slip", "transaction", "slip"],
        "receiver_account_or_promptpay": ["account", "promptpay", "qr", "wallet"],
        "chat_logs": ["chat", "screenshots", "messages", "conversation"],
        "pickup_and_dropoff": ["pickup", "dropoff", "from", "to"],
        "fare_requested_and_paid": ["fare", "charged", "paid"],
        "vehicle_plate_or_taxi_id": ["plate", "taxi id", "license"],
        "receipt_payment_or_trip_record": ["receipt", "grab", "trip record"],
        "rental_shop_name_location": ["rental shop", "shop name"],
        "rental_agreement_or_deposit_record": ["agreement", "deposit"],
        "before_and_after_photos": ["before photo", "after photo", "photos"],
        "claimed_damage_and_amount": ["damage", "scratch", "repair"],
        "operator_or_guide_contact": ["guide contact", "phone", "line id"],
        "receipt_itinerary_or_listing": ["itinerary", "listing", "receipt"],
        "photos_of_guide_vehicle_shop_or_badge": ["badge", "vehicle", "shop photo"],
        "caller_or_chat_identifier": ["caller", "phone", "line id", "profile"],
        "fake_document_link_or_qr": ["document", "qr", "warrant", "link"],
        "transfer_record": ["transfer", "bank", "slip"],
        "remote_app_or_otp_details": ["otp", "remote app", "anydesk", "teamviewer"],
        "venue_name_location": ["venue", "restaurant", "bar", "club"],
        "bill_menu_or_receipt_photo": ["bill", "menu", "receipt"],
        "expected_vs_demanded_amount": ["expected", "demanded", "charged"],
        "item_description_and_value": ["phone", "wallet", "bag", "passport", "camera", "laptop", "value"],
        "theft_location_and_time": ["stolen", "theft", "pickpocket", "robbed", "snatched", "today", "yesterday"],
        "suspect_or_witness_details": ["suspect", "witness", "saw", "cctv", "camera"],
        "photos_receipts_or_tracking_info": ["photo", "receipt", "tracking", "find my", "imei", "serial"],
        "assault_location_and_time": ["assault", "attacked", "hit", "punched", "kicked", "today", "yesterday"],
        "injury_description_or_medical_record": ["injury", "hurt", "bleeding", "hospital", "medical", "doctor"],
        "suspect_description_or_identity": ["suspect", "attacker", "identity", "description", "shirt", "name"],
        "witnesses_photos_or_video": ["witness", "photo", "video", "cctv", "camera"],
    }
    allowed = {requirement.name for requirement in SCAM_EVIDENCE_RULES.get(scam_type, [])}
    matches = []
    for evidence_name, keywords in aliases.items():
        if allowed and evidence_name not in allowed:
            continue
        if any(contains_keyword(text, keyword) for keyword in keywords):
            matches.append(evidence_name)
    return matches


def contains_keyword(text: str, keyword: str) -> bool:
    escaped = re.escape(keyword)
    if " " in keyword:
        return re.search(rf"(?<!\w){escaped}(?!\w)", text) is not None
    return re.search(rf"\b{escaped}\b", text) is not None


def add_evidence_once(state: CaseState, evidence_name: str, description: str) -> None:
    if evidence_name in state.known_evidence_names:
        return
    state.evidence.append(EvidenceItem(name=evidence_name, description=description))


def format_transcript(messages: list[str]) -> str:
    return "\n".join(f"Tourist: {message}" for message in messages)


EVIDENCE_AGENT_TOOLS = [get_evidence_requirements]
