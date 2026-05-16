from __future__ import annotations

import re

from langchain.tools import tool

from ..evidence_rules import SCAM_EVIDENCE_RULES
from ..schemas import CaseState, EvidenceItem, EvidenceRequirement, ScamType


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
    """Evidence node: attach requirements and infer evidence mentioned by user."""
    updated = state.model_copy(deep=True)
    updated.evidence_requirements = get_requirements(updated.scam_type)

    for evidence_name in infer_evidence_names(message, updated.scam_type):
        if evidence_name not in updated.known_evidence_names:
            updated.evidence.append(
                EvidenceItem(
                    name=evidence_name,
                    description=f"Tourist mentioned {evidence_name.replace('_', ' ')}.",
                )
            )

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


EVIDENCE_AGENT_TOOLS = [get_evidence_requirements]
