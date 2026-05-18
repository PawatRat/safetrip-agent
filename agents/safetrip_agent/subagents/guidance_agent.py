from __future__ import annotations

from typing import Any

from langchain.tools import tool

from ..legal_knowledge_base import build_guidance_from_knowledge
from ..schemas import CaseState, GuidanceSelection, ReportingGuidance, ScamType


GUIDANCE_AGENT_PROMPT = (
    "Guidance Agent: retrieve the appropriate reporting route and source IDs. "
    "Do not claim a formal police report has been submitted."
)


@tool
def retrieve_reporting_guidance(scam_type: ScamType) -> dict:
    """Retrieve tourist-focused legal guidance from the local knowledge base."""
    return build_guidance_from_knowledge(scam_type)


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
        recommended_actions=guidance.get("recommended_actions", []),
        sources=guidance.get("sources", []),
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
                "Retrieved legal knowledge base result:\n"
                f"{seed_guidance}\n\n"
                "Case state:\n"
                f"{updated.model_dump(mode='json')}",
            ),
        ]
    )
    updated.reporting_guidance = ReportingGuidance(
        route=guidance.route,
        source_ids=guidance.source_ids or seed_guidance.get("source_ids", []),
        recommended_actions=seed_guidance.get("recommended_actions", []),
        sources=seed_guidance.get("sources", []),
    )
    return updated


GUIDANCE_AGENT_TOOLS = [retrieve_reporting_guidance]
