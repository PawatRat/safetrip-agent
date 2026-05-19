from __future__ import annotations

from typing import Any

from ..schemas import CaseState, SynthesisResult


SYNTHESIS_AGENT_PROMPT = (
    "Synthesis Agent: you write the single tourist-facing reply. Take everything "
    "the other agents gathered (case classification, what is still missing, the "
    "next question to ask, and the retrieved guidance and next steps) and turn it "
    "into one warm, clear, human message - not a form dump. If information is "
    "still being collected, ask exactly the one next question naturally and "
    "briefly explain why it helps. Weave in the recommended next steps and the "
    "official channel without bullet-point boilerplate. Never claim a police "
    "report has been submitted. Keep it concise and reassuring."
)


def compose_response(state: CaseState, base_text: str) -> str:
    """Offline fallback: keep the existing deterministic text unchanged."""
    return base_text


def compose_response_with_model(
    model: Any,
    state: CaseState,
    base_text: str,
) -> str:
    """LLM synthesis: rewrite the gathered data into one natural reply."""
    guidance = state.reporting_guidance
    structured_model = model.with_structured_output(SynthesisResult)
    result = structured_model.invoke(
        [
            ("system", SYNTHESIS_AGENT_PROMPT),
            (
                "human",
                "Case so far:\n"
                f"scam_type={state.scam_type}, location={state.location}, "
                f"incident_time={state.incident_time}, amount_lost={state.amount_lost}\n"
                f"known_evidence={state.known_evidence_names}\n"
                f"missing_items={state.missing_items}\n"
                f"next_question={state.next_question}\n"
                f"reporting_route={guidance.route if guidance else None}\n"
                f"recommended_actions={guidance.recommended_actions if guidance else []}\n\n"
                "Draft system-assembled text (rewrite this into one natural "
                "message, preserving the next question and the guidance):\n"
                f"{base_text}",
            ),
        ]
    )
    return result.response_text or base_text


SYNTHESIS_AGENT_TOOLS: list = []
