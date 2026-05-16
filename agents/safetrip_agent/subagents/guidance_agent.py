from __future__ import annotations

from typing import Any

from langchain.tools import tool

from ..schemas import CaseState, GuidanceSelection, ReportingGuidance, ScamType


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


def update_case_guidance(state: CaseState, mode: str = "intake_help") -> CaseState:
    """Offline guidance node used only when the orchestrator is run without a model."""
    updated = state.model_copy(deep=True)
    guidance = retrieve_reporting_guidance.invoke({"scam_type": updated.scam_type})
    route = guidance["route"]
    if mode == "intake_help" and updated.next_question:
        route = f"{route} Next, collect: {updated.next_question}"
    updated.reporting_guidance = ReportingGuidance(
        route=route,
        source_ids=guidance["source_ids"],
    )
    return updated


def update_case_guidance_with_model(
    model: Any,
    state: CaseState,
    mode: str = "intake_help",
) -> CaseState:
    """Guidance node: use the LLM to select tourist-facing guidance from tool context."""
    updated = state.model_copy(deep=True)
    seed_guidance = retrieve_reporting_guidance.invoke({"scam_type": updated.scam_type})
    structured_model = model.with_structured_output(GuidanceSelection)
    guidance = structured_model.invoke(
        [
            (
                "system",
                "You are the SafeTrip Guidance Agent. Use the retrieved guidance as "
                "source context, then produce a concise reporting route for the "
                "tourist. In intake_help mode, focus on what to collect next. In "
                "report_route mode, use all information to prepare reporting route "
                "guidance. Do not claim that any report was submitted.",
            ),
            (
                "human",
                f"Guidance mode: {mode}\n\n"
                "Retrieved guidance tool result:\n"
                f"{seed_guidance}\n\n"
                "Case state:\n"
                f"{updated.model_dump(mode='json')}",
            ),
        ]
    )
    updated.reporting_guidance = ReportingGuidance(
        route=guidance.route,
        source_ids=guidance.source_ids or seed_guidance.get("source_ids", []),
    )
    return updated


GUIDANCE_AGENT_TOOLS = [retrieve_reporting_guidance]
