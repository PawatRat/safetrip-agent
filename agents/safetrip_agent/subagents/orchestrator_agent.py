from __future__ import annotations

from typing import Any

from ..schemas import CaseState, OrchestratorPlan


ORCHESTRATOR_AGENT_PROMPT = (
    "Orchestrator: you are the routing brain of SafeTrip and the only agent that "
    "makes judgment calls about the workflow. Read the latest tourist message "
    "together with the known case state and decide two independent things: "
    "(1) the tourist's intent, and (2) whether this message carries new or "
    "corrected case data (a new fact, new evidence, or a correction). Workers "
    "around you are deterministic; you select the pathway."
)


_RECOMMENDATION_PHRASES = (
    "what should i do",
    "what do i do",
    "what to do",
    "what now",
    "what next",
    "next step",
    "recommend",
    "recommendation",
    "advice",
    "advise",
    "help me",
    "guide me",
)


def is_confirmation_message(message: str) -> bool:
    """Deterministic confirmation detector used by the offline fallback."""
    normalized = message.strip().lower()
    confirmations = {
        "yes",
        "yes confirm",
        "confirm",
        "confirmed",
        "submit",
        "send",
        "send it",
        "looks good",
        "correct",
        "that is correct",
        "ok",
        "okay",
    }
    if normalized in confirmations or normalized.startswith(("yes ", "yes,")):
        return True
    return any(phrase in normalized for phrase in ["please submit", "please send", "i confirm"])


def _has_pending_draft(state: CaseState) -> bool:
    return state.workflow_stage == "awaiting_user_confirmation" and bool(state.draft_text)


def plan_turn(state: CaseState, message: str) -> OrchestratorPlan:
    """Offline orchestrator: rule-based intent + carries_case_data plan."""
    if _has_pending_draft(state) and is_confirmation_message(message):
        return OrchestratorPlan(
            intent="confirm_submission",
            carries_case_data=False,
            rationale="A draft is awaiting confirmation and the tourist confirmed it.",
        )

    normalized = message.strip().lower()
    classified = state.scam_type != "unknown"
    looks_like_recommendation = any(
        phrase in normalized for phrase in _RECOMMENDATION_PHRASES
    )
    short_message = len(normalized.split()) <= 8

    if looks_like_recommendation and classified and short_message:
        return OrchestratorPlan(
            intent="want_recommendation",
            carries_case_data=False,
            rationale="The tourist is asking for a recommendation and gave no new case data.",
        )

    return OrchestratorPlan(
        intent="provide_info",
        carries_case_data=True,
        rationale="Treat the message as carrying case data (default-to-extract).",
    )


def plan_turn_with_model(model: Any, state: CaseState, message: str) -> OrchestratorPlan:
    """LLM orchestrator: classify intent and whether the message carries data."""
    structured_model = model.with_structured_output(OrchestratorPlan)
    plan = structured_model.invoke(
        [
            (
                "system",
                ORCHESTRATOR_AGENT_PROMPT
                + " carries_case_data must be true if the message contains any new "
                "fact, any new or described evidence, or a correction. Set it false "
                "only for pure intent messages (asking for advice, confirming, "
                "thanking, or a question with no new details). When unsure, prefer "
                "carries_case_data=true.",
            ),
            (
                "human",
                "Known case state:\n"
                f"scam_type={state.scam_type}, location={state.location}, "
                f"incident_time={state.incident_time}, amount_lost={state.amount_lost}, "
                f"known_evidence={state.known_evidence_names}, "
                f"report_ready={state.report_ready}, "
                f"workflow_stage={state.workflow_stage}, "
                f"has_pending_draft={_has_pending_draft(state)}\n\n"
                f"Latest tourist message:\n{message}",
            ),
        ]
    )

    # Hard guard: cannot confirm a submission unless a draft is actually pending.
    if plan.intent == "confirm_submission" and not _has_pending_draft(state):
        return OrchestratorPlan(
            intent="provide_info",
            carries_case_data=True,
            rationale="No draft is awaiting confirmation, so process the case instead.",
        )
    return plan


ORCHESTRATOR_AGENT_TOOLS: list = []
