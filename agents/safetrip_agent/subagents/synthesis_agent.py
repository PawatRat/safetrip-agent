from __future__ import annotations

from typing import Any

from ..schemas import CaseState, SynthesisResult


SYNTHESIS_AGENT_PROMPT = (
    "Synthesis Agent: you write the single tourist-facing reply. Turn everything "
    "the other agents gathered into a warm, reassuring, scannable message a "
    "stressed traveller can read fast. Use this exact layout in plain text (no "
    "markdown symbols like # or *, no internal field names):\n\n"
    "1. Open with a sincere apology and empathy - tell the tourist you are sorry "
    "this happened and that you are here to help them through it (1-2 sentences, "
    "genuine, not robotic).\n"
    "2. A line `What to do now:` followed by 1-3 short `- ` bullet points "
    "(the recommended actions and the official channel, in plain language).\n"
    "3. A line `Evidence to prepare:` followed by `- ` bullet points, one per "
    "still-needed item, each as 'Item - short reason why it helps'. Skip this "
    "section only if nothing is missing.\n"
    "4. A closing that commits to the next step: tell the tourist that once they "
    "share the remaining evidence you will put together their police-ready "
    "report and help them submit it to the Tourist Police. Phrase it as a "
    "forward-looking promise conditional on their evidence - NEVER say a report "
    "has already been submitted, sent, or filed, and do not guarantee a legal "
    "outcome.\n"
    "5. End by clearly asking the ONE next question, e.g. "
    "`To continue, please tell me: <question>`. Skip only if there is no next "
    "question.\n\n"
    "Separate each section with a blank line. Keep bullets short. Do not invent "
    "details."
)


def _missing_evidence_lines(state: CaseState) -> list[str]:
    """Human-readable 'name - reason' lines for still-needed evidence."""
    known = set(state.known_evidence_names)
    lines: list[str] = []
    for requirement in state.evidence_requirements:
        if requirement.name in known:
            continue
        readable = requirement.name.replace("_", " ")
        lines.append(f"{readable} - {requirement.reason}")
    return lines


def compose_response(state: CaseState, base_text: str) -> str:
    """Offline fallback: keep the existing deterministic text unchanged."""
    return base_text


def compose_response_with_model(
    model: Any,
    state: CaseState,
    base_text: str,
) -> str:
    """LLM synthesis: rewrite the gathered data into one structured reply."""
    guidance = state.reporting_guidance
    structured_model = model.with_structured_output(SynthesisResult)
    result = structured_model.invoke(
        [
            ("system", SYNTHESIS_AGENT_PROMPT),
            (
                "human",
                "Case so far:\n"
                f"incident_type={state.scam_type}, location={state.location}, "
                f"time={state.incident_time}, amount_lost={state.amount_lost}\n"
                f"already_provided_evidence={state.known_evidence_names}\n"
                f"next_question={state.next_question}\n"
                f"reporting_route={guidance.route if guidance else None}\n"
                "recommended_actions="
                f"{guidance.recommended_actions if guidance else []}\n"
                "evidence_still_needed (name - reason):\n"
                + (
                    "\n".join(f"- {line}" for line in _missing_evidence_lines(state))
                    or "- (none)"
                )
                + "\n\nReference draft (use its facts; rewrite into the required "
                "structured layout, do not copy verbatim):\n"
                f"{base_text}",
            ),
        ]
    )
    return result.response_text or base_text


def compose_submission_response(
    state: CaseState,
    packet_path: str,
    endpoint_succeeded: bool,
) -> str:
    """Offline fallback for the post-confirmation submission result."""
    if endpoint_succeeded:
        return (
            "Your police-ready packet has been prepared and the online handoff "
            "was completed.\n\n"
            f"Saved packet: {packet_path}\n\n"
            "I kept the local packet available so it can be reviewed or shared "
            "again if needed."
        )
    return (
        "Your police-ready packet has been prepared and saved locally.\n\n"
        f"Saved packet: {packet_path}\n\n"
        "The online handoff could not be completed right now, but your case "
        "details are not lost. You can use the saved packet with Tourist Police "
        "support or retry the online handoff later."
    )


def compose_submission_response_with_model(
    model: Any,
    state: CaseState,
    packet_path: str,
    endpoint: str,
    endpoint_succeeded: bool,
    error_summary: str | None = None,
) -> str:
    """LLM synthesis for the final post-confirmation message."""
    structured_model = model.with_structured_output(SynthesisResult)
    result = structured_model.invoke(
        [
            (
                "system",
                "You are the SafeTrip Synthesis Agent writing the final message "
                "after the tourist confirmed a police-ready packet. Write a calm, "
                "plain-language user-facing response. Do not expose raw exception "
                "names, HTTP codes, stack traces, JSON, or internal endpoint debug "
                "details. Do not claim police accepted or filed the report unless "
                "the online handoff succeeded. If the handoff failed, say the "
                "packet was prepared and saved locally, explain that the online "
                "handoff could not be completed right now, and give the next safe "
                "step. Keep it short and reassuring.",
            ),
            (
                "human",
                "Submission result:\n"
                f"case_id={state.case_id}\n"
                f"incident_type={state.scam_type}\n"
                f"packet_path={packet_path}\n"
                f"endpoint={endpoint}\n"
                f"endpoint_succeeded={endpoint_succeeded}\n"
                f"error_summary={error_summary or 'none'}\n",
            ),
        ]
    )
    return result.response_text or compose_submission_response(
        state, packet_path, endpoint_succeeded
    )


SYNTHESIS_AGENT_TOOLS: list = []
