from __future__ import annotations

from langchain.tools import tool

from ..schemas import CaseState, ReportingGuidance, ScamType


GUIDANCE_AGENT_PROMPT = (
    "Guidance Agent: retrieve the appropriate reporting route and source IDs. "
    "Do not claim a formal police report has been submitted."
)


@tool
def retrieve_reporting_guidance(scam_type: ScamType) -> dict:
    """Retrieve seed reporting guidance. Replace with vector search in production."""
    if scam_type in {"online_transfer_scam", "fake_police_or_government"}:
        return {
            "route": "Contact bank immediately if money/credentials are involved, then prepare cybercrime or police report evidence.",
            "source_ids": ["seed:royal-thai-police-online-reporting", "seed:dsi-fake-report-warning"],
        }
    if scam_type == "fake_accommodation":
        return {
            "route": "Check/report suspicious accommodation through Tourist Police trust/report flow; use Tourist Police support for tourist assistance.",
            "source_ids": ["seed:tourist-police-trust-portal", "seed:tourist-police-1155-app"],
        }
    return {
        "route": "Use Tourist Police 1155/app for immediate tourist help and prepare a local incident packet for the responsible area.",
        "source_ids": ["seed:tourist-police-1155-app"],
    }


def update_case_guidance(state: CaseState) -> CaseState:
    """Guidance node: attach source-linked reporting route."""
    updated = state.model_copy(deep=True)
    guidance = retrieve_reporting_guidance.invoke({"scam_type": updated.scam_type})
    updated.reporting_guidance = ReportingGuidance.model_validate(guidance)
    return updated


GUIDANCE_AGENT_TOOLS = [retrieve_reporting_guidance]
