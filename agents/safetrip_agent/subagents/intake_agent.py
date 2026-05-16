from __future__ import annotations

import re

from langchain.tools import tool

from ..schemas import CaseFact, CaseState, ClassificationResult, ScamType


INTAKE_AGENT_PROMPT = (
    "Intake Agent: classify the tourist's incident and extract the first known "
    "facts from the full conversation. Do not ask again for details already "
    "provided."
)


@tool
def classify_scam_type(message: str) -> ScamType:
    """Classify a tourist scam report into the nearest SafeTrip case type."""
    return classify_message(message).scam_type


def classify_message(message: str) -> ClassificationResult:
    """Classify a tourist scam report with deterministic, auditable signals."""
    text = message.lower()

    signal_groups: list[tuple[ScamType, list[str], str]] = [
        (
            "fake_police_or_government",
            ["police", "immigration", "dsi", "otp", "remote", "warrant", "government"],
            "Government impersonation and credential-pressure signals take priority.",
        ),
        (
            "fake_accommodation",
            ["hotel", "hostel", "villa", "booking", "accommodation", "airbnb"],
            "Accommodation or booking terms matched.",
        ),
        (
            "taxi_overcharge",
            ["taxi", "tuk", "meter", "grab", "driver", "ride"],
            "Ride or driver terms matched.",
        ),
        (
            "rental_damage_claim",
            ["motorbike", "jet ski", "rental", "damage", "deposit"],
            "Rental, deposit, or damage-claim terms matched.",
        ),
        (
            "tour_package_or_illegal_guide",
            ["tour", "guide", "gem", "souvenir", "itinerary"],
            "Tour package, guide, or itinerary terms matched.",
        ),
        (
            "restaurant_or_venue_overcharge",
            ["restaurant", "bar", "bill", "menu", "venue", "club"],
            "Venue bill or menu terms matched.",
        ),
        (
            "online_transfer_scam",
            ["transfer", "promptpay", "bank", "seller", "online", "facebook", "qr"],
            "Online seller or transfer terms matched.",
        ),
    ]

    for scam_type, signals, rationale in signal_groups:
        matched = [signal for signal in signals if signal in text]
        if matched:
            confidence = min(0.95, 0.65 + (0.08 * len(matched)))
            return ClassificationResult(
                scam_type=scam_type,
                confidence=confidence,
                rationale=rationale,
                matched_signals=matched,
            )

    return ClassificationResult(
        scam_type="unknown",
        confidence=0.0,
        rationale="No known SafeTrip scam signals matched.",
    )


def update_case_from_message(state: CaseState, message: str) -> CaseState:
    """Intake node: append message and extract stable first-pass case facts."""
    updated = state.model_copy(deep=True)
    updated.messages.append(message)
    updated.language = updated.language or detect_language(message)

    classification = classify_message("\n".join(updated.messages))
    if classification.confidence >= updated.classification_confidence:
        updated.scam_type = classification.scam_type
        updated.classification_confidence = classification.confidence
        updated.classification_rationale = classification.rationale

    amount = extract_amount(message)
    if amount and not updated.amount_lost:
        updated.amount_lost = amount
        add_fact_once(updated, "amount_lost", amount)

    location = extract_location(message)
    if location and not updated.location:
        updated.location = location
        add_fact_once(updated, "location", location)

    incident_time = extract_incident_time(message)
    if incident_time and not updated.incident_time:
        updated.incident_time = incident_time
        add_fact_once(updated, "incident_time", incident_time)

    return updated


def detect_language(message: str) -> str:
    if re.search(r"[\u0e00-\u0e7f]", message):
        return "th"
    return "en"


def extract_amount(message: str) -> str | None:
    patterns = [
        r"\b(?:thb|baht)\s*([0-9][0-9,]*(?:\.\d+)?)\b",
        r"\b([0-9][0-9,]*(?:\.\d+)?)\s*(?:thb|baht)\b",
        r"\btransferred\s+([0-9][0-9,]*(?:\.\d+)?)\b",
        r"\bpaid\s+([0-9][0-9,]*(?:\.\d+)?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return match.group(1).replace(",", "") + " THB"
    return None


def extract_location(message: str) -> str | None:
    pattern = r"\b(?:in|at|near)\s+([A-Z][A-Za-z0-9 .'-]{2,60})"
    match = re.search(pattern, message)
    if not match:
        return None
    location = match.group(1).strip(" .")
    stop_words = [
        " and ",
        " but ",
        " when ",
        " after ",
        " before ",
        " today",
        " yesterday",
        " last night",
    ]
    for stop_word in stop_words:
        if stop_word in location.lower():
            location = location[: location.lower().index(stop_word)].strip()
    return location


def extract_incident_time(message: str) -> str | None:
    text = message.lower()
    for phrase in ["today", "yesterday", "last night", "this morning", "this afternoon"]:
        if phrase in text:
            return phrase
    date_match = re.search(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b", message)
    if date_match:
        return date_match.group(0)
    return None


def add_fact_once(state: CaseState, name: str, value: str) -> None:
    if any(fact.name == name and fact.value == value for fact in state.facts):
        return
    state.facts.append(CaseFact(name=name, value=value))


INTAKE_AGENT_TOOLS = [classify_scam_type]
