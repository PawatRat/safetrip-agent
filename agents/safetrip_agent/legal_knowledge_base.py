from __future__ import annotations

from pydantic import BaseModel, Field

from .schemas import ScamType


class LegalSource(BaseModel):
    id: str
    title: str
    url: str
    publisher: str
    notes: str


class LegalKnowledgeEntry(BaseModel):
    id: str
    title: str
    case_types: list[ScamType]
    guidance_modes: list[str] = Field(default_factory=lambda: ["intake_help", "report_route"])
    summary: str
    recommended_actions: list[str]
    source_ids: list[str]
    tags: list[str] = Field(default_factory=list)


LEGAL_SOURCES: dict[str, LegalSource] = {
    "tourist-police-main": LegalSource(
        id="tourist-police-main",
        title="Tourist Police Thailand",
        url="https://www.touristpolice.go.th/main",
        publisher="Tourist Police Bureau",
        notes="Official Tourist Police site listing hotline 1155 and tourist assistance application.",
    ),
    "tourist-police-i-lert-u": LegalSource(
        id="tourist-police-i-lert-u",
        title='Tourist Police "I Lert U" app',
        url="https://www.thailand.go.th/public/visit-thailand-detail/001_02_085",
        publisher="Thailand.go.th",
        notes="Explains that the app can send assistance requests, GPS location, photos, and notify Emergency Notification Center 1155.",
    ),
    "thailand-emergency-numbers": LegalSource(
        id="thailand-emergency-numbers",
        title="Emergency contact numbers",
        url="https://www.thailand.go.th/issue-focus-detail/009-017?hl=en",
        publisher="Thailand.go.th",
        notes="Lists emergency hotline 191, Tourist Police 1155, and emergency medical services 1669.",
    ),
    "tourist-police-trust": LegalSource(
        id="tourist-police-trust",
        title="Tourist Police Trust Portal",
        url="https://trust.touristpolice.go.th/en",
        publisher="Tourist Police Trust Portal",
        notes="Official portal for verified accommodation providers, suspicious URL checks, scam reports, and emergency 1155 contact.",
    ),
    "thai-police-online-reporting": LegalSource(
        id="thai-police-online-reporting",
        title="Royal Thai Police Online Reporting System",
        url="https://thaipoliceonline.go.th/",
        publisher="Royal Thai Police",
        notes="Online reporting channel referenced by Royal Thai Police e-service pages for online complaints.",
    ),
}


LEGAL_KNOWLEDGE_ENTRIES: list[LegalKnowledgeEntry] = [
    LegalKnowledgeEntry(
        id="tourist-police-general-help",
        title="Tourist Police assistance for tourist-related incidents",
        case_types=[
            "taxi_overcharge",
            "rental_damage_claim",
            "tour_package_or_illegal_guide",
            "restaurant_or_venue_overcharge",
            "theft",
        ],
        summary=(
            "Tourist-facing incidents should generally be routed through Tourist Police "
            "1155/app for immediate tourist assistance, language support, and preparation "
            "of a local incident packet."
        ),
        recommended_actions=[
            "Use Tourist Police 1155 or the Tourist Police app for tourist-specific assistance.",
            "Prepare a local incident packet with location, time, contact information, and evidence.",
            "If there is urgent danger, call emergency police 191 instead of waiting for document preparation.",
        ],
        source_ids=["tourist-police-main", "tourist-police-i-lert-u", "thailand-emergency-numbers"],
        tags=["tourist_police", "local_report", "1155", "191"],
    ),
    LegalKnowledgeEntry(
        id="accommodation-scam-trust-portal",
        title="Accommodation scam and suspicious booking guidance",
        case_types=["fake_accommodation"],
        summary=(
            "Suspicious accommodation bookings should be checked or reported through the "
            "Tourist Police Trust Portal and Tourist Police support channels."
        ),
        recommended_actions=[
            "Check the accommodation provider or suspicious URL through the Tourist Police Trust Portal.",
            "Collect listing URL, payment proof, booking reference, and seller chat evidence.",
            "Use Tourist Police support if the tourist needs help preparing a report packet.",
        ],
        source_ids=["tourist-police-trust", "tourist-police-main"],
        tags=["accommodation", "booking", "trust_portal", "scam_report"],
    ),
    LegalKnowledgeEntry(
        id="online-transfer-cybercrime",
        title="Online transfer scam and cybercrime reporting guidance",
        case_types=["online_transfer_scam", "fake_police_or_government"],
        summary=(
            "Online transfer scams, fake police/government contact, and credential-pressure "
            "cases should prioritize bank contact when money or credentials are involved, "
            "then prepare evidence for cybercrime or police reporting."
        ),
        recommended_actions=[
            "Contact the bank or payment provider immediately if money, credentials, OTP, or account access is involved.",
            "Keep transfer slips, transaction IDs, receiver account/PromptPay details, chat logs, caller IDs, and fake document links.",
            "Prepare the case for Royal Thai Police online reporting or local police follow-up.",
        ],
        source_ids=["thai-police-online-reporting", "thailand-emergency-numbers"],
        tags=["cybercrime", "transfer", "otp", "fake_police", "online_report"],
    ),
    LegalKnowledgeEntry(
        id="physical-assault-emergency",
        title="Physical assault and immediate safety guidance",
        case_types=["physical_assault"],
        summary=(
            "Physical assault cases should prioritize immediate safety, medical care, "
            "and emergency police/tourist police contact before document preparation."
        ),
        recommended_actions=[
            "Move to a safe public place if there is immediate danger.",
            "Call emergency police 191, Tourist Police 1155, or emergency medical services 1669 if injured.",
            "Collect location, time, injury or medical records, suspect description, witnesses, photos, video, or CCTV details.",
        ],
        source_ids=["thailand-emergency-numbers", "tourist-police-main", "tourist-police-i-lert-u"],
        tags=["assault", "injury", "emergency", "191", "1669", "1155"],
    ),
]


def search_legal_knowledge(
    scam_type: ScamType,
    mode: str = "intake_help",
    query: str = "",
) -> list[LegalKnowledgeEntry]:
    """Return tourist-focused legal guidance entries relevant to the case."""
    scored: list[tuple[int, LegalKnowledgeEntry]] = []
    query_terms = set(query.lower().replace("_", " ").split())
    for entry in LEGAL_KNOWLEDGE_ENTRIES:
        if mode not in entry.guidance_modes:
            continue
        score = 0
        if scam_type in entry.case_types:
            score += 10
        score += len(query_terms.intersection(set(entry.tags)))
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in scored]


def build_guidance_from_knowledge(
    scam_type: ScamType,
    mode: str = "intake_help",
    query: str = "",
) -> dict:
    entries = search_legal_knowledge(scam_type, mode, query)
    if not entries:
        entries = search_legal_knowledge("taxi_overcharge", mode, query)
    route_parts = []
    source_ids: list[str] = []
    recommended_actions: list[str] = []
    source_details = []

    for entry in entries:
        route_parts.append(entry.summary)
        recommended_actions.extend(entry.recommended_actions)
        for source_id in entry.source_ids:
            if source_id not in source_ids:
                source_ids.append(source_id)
                source = LEGAL_SOURCES[source_id]
                source_details.append(source.model_dump())

    return {
        "route": " ".join(route_parts),
        "source_ids": source_ids,
        "recommended_actions": dedupe(recommended_actions),
        "sources": source_details,
    }


def dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
