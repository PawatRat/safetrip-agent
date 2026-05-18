from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .model_provider import build_agent_models
from .schemas import AgentTrace, CaseState
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
from .subagents.submission_packet_agent import (
    DEFAULT_POLICE_SUBMISSION_ENDPOINT,
    HttpPost,
    SUBMISSION_PACKET_AGENT_PROMPT,
    submit_case_to_police_endpoint,
    write_submission_packet,
)


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
    submission_output_root: Path = Path("police_submission_packets")
    police_submission_endpoint: str = DEFAULT_POLICE_SUBMISSION_ENDPOINT
    police_http_post: HttpPost | None = None
    case_state: CaseState = field(default_factory=CaseState, init=False)
    model: Any | None = field(default=None, init=False)
    agent_models: dict[str, Any] = field(default_factory=dict, init=False)
    last_traces: list[AgentTrace] = field(default_factory=list, init=False)
    workflow_prompts: tuple[str, ...] = field(
        default=(
            INTAKE_AGENT_PROMPT,
            EVIDENCE_AGENT_PROMPT,
            GUIDANCE_AGENT_PROMPT,
            COMPLETENESS_AGENT_PROMPT,
            DRAFTING_AGENT_PROMPT,
            SAFETY_AGENT_PROMPT,
            SUBMISSION_PACKET_AGENT_PROMPT,
        ),
        init=False,
    )

    _on_progress: Callable[[dict], None] | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.use_model:
            self.agent_models = build_agent_models()
        if self.verbose:
            print("SafeTrip workflow initialized with orchestrator-owned state routing.")

    def reset(self) -> None:
        self.case_state = CaseState()
        self.last_traces = []

    def process(
        self,
        message: str,
        on_progress: Callable[[dict], None] | None = None,
    ) -> AgentRunResult:
        workflow_steps: list[str] = []
        self.last_traces = []
        self._on_progress = on_progress
        state = self.case_state

        if self.verbose:
            print("\nPipeline>")

        route_to_submission = self._should_write_submission_packet(state, message)
        self._begin("Orchestrator", workflow_steps)
        self._record_trace(
            "Orchestrator",
            "Receive the tourist message and choose the top-level route before any subagent runs.",
            {
                "workflow_stage": state.workflow_stage,
                "is_confirmation_message": is_confirmation_message(message),
                "has_pending_draft": bool(state.draft_text),
            },
            "Route to police submission."
            if route_to_submission
            else "Route into the triage pipeline (Intake -> Evidence -> Completeness).",
        )
        if self.verbose:
            self._print_latest_trace("Orchestrator")

        if route_to_submission:
            state, response_text = self._run_submission_flow(state, message, workflow_steps)
            self.case_state = state
            return self._build_result(workflow_steps, response_text, state)

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
            "Completeness Agent",
            self._run_completeness_node,
            state,
            workflow_steps,
        )
        self._record_orchestrator_decision(state, workflow_steps)

        if state.report_ready:
            state.workflow_stage = "ready_to_draft"
            state = self._run_node(
                "Guidance Agent",
                lambda current: self._run_guidance_node(current, "report_route"),
                state,
                workflow_steps,
            )
            self._begin("Drafting Agent", workflow_steps)
            response_text = self._run_drafting_node(state)
            response_text = attach_guidance_to_response(response_text, state)
            state.draft_text = response_text
            state.workflow_stage = "awaiting_user_confirmation"
            self._record_trace(
                "Drafting Agent",
                "Case is complete, so draft a police-ready report for tourist confirmation.",
                {"draft_preview": summarize_text(response_text)},
                "Awaiting tourist confirmation before packet generation.",
            )
            if self.verbose:
                self._print_latest_trace("Drafting Agent")
        else:
            state.workflow_stage = "collecting_info"
            state = self._run_node(
                "Guidance Agent",
                lambda current: self._run_guidance_node(current, "intake_help"),
                state,
                workflow_steps,
            )
            response_text = build_intake_response(state)
            response_text = attach_guidance_to_response(response_text, state)
            self._record_trace(
                "Drafting Agent",
                "Case is not complete, so drafting is skipped.",
                {"missing_items": state.missing_items},
                "Ask the next focused question instead of drafting.",
            )
            if self.verbose:
                self._print_latest_trace("Drafting Agent")

        self._begin("Safety Agent", workflow_steps)
        state, response_text = self._run_safety_node(state, response_text)
        response_text = attach_guidance_to_response(response_text, state)
        self._record_trace(
            "Safety Agent",
            "Review tourist-facing response for unsafe claims and urgent danger signals.",
            {
                "flags": state.safety_review.flags,
                "notes": state.safety_review.notes,
            },
            "Response cleared for tourist.",
        )
        if self.verbose:
            self._print_latest_trace("Safety Agent")

        self.case_state = state
        return self._build_result(workflow_steps, response_text, state)

    def _build_result(
        self,
        workflow_steps: list[str],
        response_text: str,
        state: CaseState,
    ) -> AgentRunResult:
        self._on_progress = None
        return AgentRunResult(
            raw_result={
                "workflow_steps": workflow_steps,
                "agent_traces": [trace.model_dump(mode="json") for trace in self.last_traces],
                "case_state": state.model_dump(mode="json"),
            },
            final_text=response_text,
            case_state=state,
        )

    def _emit(self, event: dict) -> None:
        callback = self._on_progress
        if callback is None:
            return
        try:
            callback(event)
        except Exception:
            # Streaming consumer disconnected; keep the pipeline running.
            pass

    def _begin(self, name: str, workflow_steps: list[str]) -> None:
        workflow_steps.append(name)
        self._emit({"type": "agent_start", "agent_name": name})

    def _run_node(self, name: str, node, state: CaseState, workflow_steps: list[str]) -> CaseState:
        self._begin(name, workflow_steps)
        updated = node(state)
        if self.verbose:
            self._print_latest_trace(name)
        return updated

    def _run_intake_node(self, state: CaseState, message: str) -> CaseState:
        model = self._model_for("intake")
        if not model:
            updated = update_case_from_message(state, message)
            self._record_trace(
                "Intake Agent",
                "Extract incident facts from the latest tourist message.",
                intake_trace_data(updated),
                "Updated case facts and classification.",
            )
            return updated

        conversation = [*state.messages, message]
        extracted_facts = extract_case_facts_with_model(model, conversation, message)
        updated = update_case_from_message(state, message, extracted_facts)
        self._record_trace(
            "Intake Agent",
            extracted_facts.rationale or "Structured extraction completed from conversation.",
            intake_trace_data(updated),
            "Updated case facts and classification.",
        )
        return updated

    def _run_evidence_node(self, state: CaseState, message: str) -> CaseState:
        model = self._model_for("evidence")
        if not model:
            updated = update_case_evidence(state, message)
        else:
            updated = update_case_evidence_with_model(model, state, message)
        self._record_trace(
            "Evidence Agent",
            "Compare tourist-provided details against evidence requirements from the tool.",
            {
                "requirements": [item.model_dump() for item in updated.evidence_requirements],
                "known_evidence": updated.known_evidence_names,
            },
            "Updated evidence checklist and collected evidence.",
        )
        return updated

    def _run_guidance_node(self, state: CaseState, mode: str) -> CaseState:
        model = self._model_for("guidance")
        if not model:
            updated = update_case_guidance(state, mode)
        else:
            updated = update_case_guidance_with_model(model, state, mode)
        self._record_trace(
            "Guidance Agent",
            f"Prepare guidance in {mode} mode using current case data.",
            {
                "mode": mode,
                "route": updated.reporting_guidance.route if updated.reporting_guidance else None,
                "source_ids": updated.reporting_guidance.source_ids
                if updated.reporting_guidance
                else [],
            },
            "Attached guidance for the current workflow branch.",
        )
        return updated

    def _run_completeness_node(self, state: CaseState) -> CaseState:
        model = self._model_for("completeness")
        if not model:
            updated = update_case_completeness(state)
        else:
            updated = update_case_completeness_with_model(model, state)
        self._record_trace(
            "Completeness Agent",
            "Assess whether the case has enough facts and evidence to draft.",
            {
                "report_ready": updated.report_ready,
                "missing_items": updated.missing_items,
                "next_question": updated.next_question,
            },
            "Returned readiness assessment to the orchestrator.",
        )
        return updated

    def _run_drafting_node(self, state: CaseState) -> str:
        model = self._model_for("drafting")
        if not model:
            return draft_report(state)
        return draft_report_with_model(model, state)

    def _run_safety_node(self, state: CaseState, response_text: str) -> tuple[CaseState, str]:
        model = self._model_for("safety")
        if not model:
            return review_case_safety(state, response_text)
        return review_case_safety_with_model(model, state, response_text)

    def _model_for(self, agent_name: str):
        return self.agent_models.get(agent_name) or self.model

    def _run_submission_flow(
        self,
        state: CaseState,
        message: str,
        workflow_steps: list[str],
    ) -> tuple[CaseState, str]:
        updated = state.model_copy(deep=True)
        updated.messages.append(message)
        updated.user_confirmed_submission = True
        updated.workflow_stage = "confirmed_for_submission"
        self._begin("Orchestrator Decision", workflow_steps)
        self._record_trace(
            "Orchestrator Decision",
            "Tourist confirmed the draft, so move to packet generation.",
            {
                "previous_stage": state.workflow_stage,
                "confirmation_message": message,
            },
            "Route to Submission Packet Agent.",
        )
        self._begin("Submission Packet Agent", workflow_steps)
        packet_root = self._submission_root_path()
        updated, packet_path = write_submission_packet(updated, packet_root)
        api_error = None
        try:
            updated, api_response = submit_case_to_police_endpoint(
                updated,
                self.police_submission_endpoint,
                self.police_http_post,
            )
        except Exception as exc:
            api_response = {}
            api_error = f"{exc.__class__.__name__}: {exc}"
            updated.submission_api_endpoint = self.police_submission_endpoint
            updated.submission_api_response = {"error": api_error}
        self._record_trace(
            "Submission Packet Agent",
            "Create a structured markdown handoff packet and POST the confirmed case.",
            {
                "packet_path": str(packet_path),
                "endpoint": self.police_submission_endpoint,
                "api_response": api_response,
                "api_error": api_error,
            },
            "Police submission packet written locally; endpoint submission attempted.",
        )
        if api_error:
            response_text = (
                "Police submission packet prepared, but the online handoff endpoint "
                "returned an error.\n"
                f"Packet path: {packet_path}\n"
                f"Endpoint: {self.police_submission_endpoint}\n"
                f"Error: {api_error}\n"
                "The packet is saved locally and can still be handed to police or retried."
            )
        else:
            response_text = (
                "Police submission packet prepared and sent to SafeTrip mock endpoint.\n"
                f"Packet path: {packet_path}\n"
                f"Endpoint: {self.police_submission_endpoint}"
            )
        self._begin("Safety Agent", workflow_steps)
        updated, response_text = self._run_safety_node(updated, response_text)
        self._record_trace(
            "Safety Agent",
            "Check the packet-generation response does not overclaim submission.",
            {
                "flags": updated.safety_review.flags,
                "notes": updated.safety_review.notes,
            },
            "Response cleared for tourist.",
        )
        if self.verbose:
            self._print_all_traces()
        return updated, response_text

    def _record_orchestrator_decision(
        self,
        state: CaseState,
        workflow_steps: list[str],
    ) -> None:
        self._begin("Orchestrator Decision", workflow_steps)
        if state.report_ready:
            decision = "Evidence complete: route to Guidance Agent in report_route mode, then Drafting Agent."
        else:
            decision = "Evidence incomplete: route to Guidance Agent in intake_help mode, then ask one next question."
        self._record_trace(
            "Orchestrator Decision",
            "Use completeness assessment and case state to choose the next branch.",
            {
                "report_ready": state.report_ready,
                "missing_items": state.missing_items,
                "workflow_stage": state.workflow_stage,
            },
            decision,
        )
        if self.verbose:
            self._print_latest_trace("Orchestrator Decision")

    def _record_trace(
        self,
        agent_name: str,
        thought: str,
        collected_data: dict,
        decision: str,
    ) -> None:
        trace = AgentTrace(
            agent_name=agent_name,
            thought=thought,
            collected_data=collected_data,
            decision=decision,
        )
        self.last_traces.append(trace)
        self._emit({"type": "trace", "trace": trace.model_dump(mode="json")})

    def _print_latest_trace(self, agent_name: str) -> None:
        for trace in reversed(self.last_traces):
            if trace.agent_name == agent_name:
                print(format_trace(trace))
                return
        print(f"  - {agent_name} completed")

    def _print_all_traces(self) -> None:
        for trace in self.last_traces:
            print(format_trace(trace))

    def _should_write_submission_packet(self, state: CaseState, message: str) -> bool:
        return (
            state.workflow_stage == "awaiting_user_confirmation"
            and bool(state.draft_text)
            and is_confirmation_message(message)
        )

    def _submission_root_path(self) -> Path:
        if self.submission_output_root.is_absolute():
            return self.submission_output_root
        return Path.cwd() / self.submission_output_root


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


def attach_guidance_to_response(response_text: str, state: CaseState) -> str:
    if not state.reporting_guidance:
        return response_text

    parts = [response_text.rstrip()]
    if state.reporting_guidance.route and state.reporting_guidance.route not in response_text:
        parts.append("\nRecommendation:")
        parts.append(state.reporting_guidance.route)

    actions = [
        action
        for action in state.reporting_guidance.recommended_actions[:3]
        if action not in response_text
    ]
    if actions:
        parts.append("\nSuggested next steps:")
        parts.extend(f"- {action}" for action in actions)

    source_labels = [
        source.get("title") or source.get("id")
        for source in state.reporting_guidance.sources[:3]
        if source.get("title") or source.get("id")
    ]
    if source_labels and "Source basis:" not in response_text:
        parts.append("\nSource basis: " + ", ".join(source_labels))

    return "\n".join(parts)


def intake_trace_data(state: CaseState) -> dict:
    return {
        "scam_type": state.scam_type,
        "classification_confidence": state.classification_confidence,
        "location": state.location,
        "incident_time": state.incident_time,
        "amount_lost": state.amount_lost,
        "facts": [fact.model_dump() for fact in state.facts],
    }


def is_confirmation_message(message: str) -> bool:
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


def format_trace(trace: AgentTrace) -> str:
    lines = [
        f"  - {trace.agent_name}",
        f"    thinks: {trace.thought}",
        f"    collected: {summarize_mapping(trace.collected_data)}",
        f"    decision: {trace.decision}",
    ]
    return "\n".join(lines)


def summarize_mapping(data: dict) -> str:
    if not data:
        return "none"
    parts = []
    for key, value in data.items():
        parts.append(f"{key}={summarize_value(value)}")
    return "; ".join(parts)


def summarize_value(value) -> str:
    text = str(value)
    if len(text) > 240:
        return text[:237] + "..."
    return text


def summarize_text(text: str) -> str:
    text = " ".join(text.split())
    if len(text) > 180:
        return text[:177] + "..."
    return text


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
