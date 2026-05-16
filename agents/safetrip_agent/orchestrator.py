from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model_provider import build_model
from .schemas import CaseState
from .subagents.completeness_agent import (
    COMPLETENESS_AGENT_PROMPT,
    update_case_completeness,
    update_case_completeness_with_model,
)
from .subagents.drafting_agent import DRAFTING_AGENT_PROMPT
from .subagents.drafting_agent import draft_report, draft_report_with_model
from .subagents.evidence_agent import (
    EVIDENCE_AGENT_PROMPT,
    update_case_evidence,
    update_case_evidence_with_model,
)
from .subagents.guidance_agent import (
    GUIDANCE_AGENT_PROMPT,
    update_case_guidance,
    update_case_guidance_with_model,
)
from .subagents.intake_agent import (
    INTAKE_AGENT_PROMPT,
    extract_case_facts_with_model,
    update_case_from_message,
)
from .subagents.safety_agent import SAFETY_AGENT_PROMPT
from .subagents.safety_agent import review_case_safety, review_case_safety_with_model


@dataclass
class AgentRunResult:
    raw_result: dict
    final_text: str
    case_state: CaseState


@dataclass
class SafeTripOrchestrator:
    """Coordinates explicit SafeTrip workflow nodes and preserves case state."""

    verbose: bool = False
    use_model: bool = True
    case_state: CaseState = field(default_factory=CaseState, init=False)
    model: Any | None = field(default=None, init=False)
    workflow_prompts: tuple[str, ...] = field(
        default=(
            INTAKE_AGENT_PROMPT,
            EVIDENCE_AGENT_PROMPT,
            GUIDANCE_AGENT_PROMPT,
            COMPLETENESS_AGENT_PROMPT,
            DRAFTING_AGENT_PROMPT,
            SAFETY_AGENT_PROMPT,
        ),
        init=False,
    )

    def __post_init__(self) -> None:
        if self.use_model:
            self.model = build_model()
        if self.verbose:
            print("SafeTrip workflow initialized with explicit Phase 3 nodes.")

    def reset(self) -> None:
        self.case_state = CaseState()

    def process(self, message: str) -> AgentRunResult:
        workflow_steps: list[str] = []
        state = self.case_state

        if self.verbose:
            print("\nPipeline>")

        state = self._run_node(
            "Intake Agent",
            lambda current: self._run_intake_node(current, message),
            state,
            workflow_steps,
        )
        state = self._run_node(
            "Evidence Agent",
            lambda current: self._run_evidence_node(current, message),
            state,
            workflow_steps,
        )
        state = self._run_node(
            "Guidance Agent",
            self._run_guidance_node,
            state,
            workflow_steps,
        )
        state = self._run_node(
            "Completeness Agent",
            self._run_completeness_node,
            state,
            workflow_steps,
        )

        if state.report_ready:
            workflow_steps.append("Drafting Agent")
            response_text = self._run_drafting_node(state)
            if self.verbose:
                print("  - Drafting Agent produced confirmation draft")
        else:
            response_text = build_intake_response(state)
            if self.verbose:
                print("  - Drafting Agent skipped until required fields are complete")

        workflow_steps.append("Safety Agent")
        state, response_text = self._run_safety_node(state, response_text)
        if self.verbose:
            print("  - Safety Agent reviewed tourist-facing response")

        self.case_state = state
        return AgentRunResult(
            raw_result={
                "workflow_steps": workflow_steps,
                "case_state": state.model_dump(mode="json"),
            },
            final_text=response_text,
            case_state=state,
        )

    def _run_node(self, name: str, node, state: CaseState, workflow_steps: list[str]) -> CaseState:
        workflow_steps.append(name)
        updated = node(state)
        if self.verbose:
            print(f"  - {name} updated case state")
        return updated

    def _run_intake_node(self, state: CaseState, message: str) -> CaseState:
        if not self.model:
            return update_case_from_message(state, message)

        conversation = [*state.messages, message]
        extracted_facts = extract_case_facts_with_model(self.model, conversation, message)
        return update_case_from_message(state, message, extracted_facts)

    def _run_evidence_node(self, state: CaseState, message: str) -> CaseState:
        if not self.model:
            return update_case_evidence(state, message)
        return update_case_evidence_with_model(self.model, state, message)

    def _run_guidance_node(self, state: CaseState) -> CaseState:
        if not self.model:
            return update_case_guidance(state)
        return update_case_guidance_with_model(self.model, state)

    def _run_completeness_node(self, state: CaseState) -> CaseState:
        if not self.model:
            return update_case_completeness(state)
        return update_case_completeness_with_model(self.model, state)

    def _run_drafting_node(self, state: CaseState) -> str:
        if not self.model:
            return draft_report(state)
        return draft_report_with_model(self.model, state)

    def _run_safety_node(self, state: CaseState, response_text: str) -> tuple[CaseState, str]:
        if not self.model:
            return review_case_safety(state, response_text)
        return review_case_safety_with_model(self.model, state, response_text)


def build_intake_response(state: CaseState) -> str:
    scam_label = state.scam_type.replace("_", " ")
    confidence = round(state.classification_confidence, 2)
    known_evidence = ", ".join(state.known_evidence_names) or "none yet"
    missing = ", ".join(state.missing_items) or "none"

    lines = [
        f"Current case: {scam_label} (confidence {confidence}).",
        f"Known evidence: {known_evidence}.",
        f"Missing before report draft: {missing}.",
    ]
    if state.reporting_guidance:
        lines.append(f"Guidance route: {state.reporting_guidance.route}")
    if state.next_question:
        lines.append(f"Next question: {state.next_question}")
    return "\n".join(lines)


def get_final_text(result: dict) -> str:
    messages = result.get("messages", [])
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text_parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            text = "\n".join(part for part in text_parts if part.strip())
            if text:
                return text
    return "No final assistant response was returned."


def message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(part for part in parts if part.strip()).strip()
    return ""


def print_agent_progress(event: dict) -> None:
    messages = event.get("messages", [])
    if not messages:
        return

    latest = messages[-1]
    message_type = latest.__class__.__name__

    if message_type == "AIMessage":
        tool_calls = getattr(latest, "tool_calls", None) or []
        if tool_calls:
            for tool_call in tool_calls:
                tool_name = tool_call.get("name", "unknown_tool")
                args = tool_call.get("args", {})
                print(f"  - Orchestrator selected tool: {tool_name}")
                if args:
                    print(f"    args: {summarize_tool_args(args)}")
            return

        text = message_text(latest)
        if text:
            print("  - Drafted final tourist-facing response")
        return

    if message_type == "ToolMessage":
        tool_name = getattr(latest, "name", "tool")
        content = message_text(latest)
        print(f"  - {tool_name} returned: {summarize_tool_result(content)}")


def summarize_tool_args(args: dict) -> str:
    safe_args = {}
    for key, value in args.items():
        if key == "message" and isinstance(value, str) and len(value) > 100:
            safe_args[key] = value[:100] + "..."
        else:
            safe_args[key] = value
    return str(safe_args)


def summarize_tool_result(content: str) -> str:
    content = " ".join(content.split())
    if len(content) > 260:
        return content[:260] + "..."
    return content
