from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .model_provider import build_agent_models
from .schemas import AgentTrace, CaseState
from .subagents.completeness_agent import (
    COMPLETENESS_AGENT_PROMPT,
    update_case_completeness,
)
from .subagents.drafting_agent import DRAFTING_AGENT_PROMPT
from .subagents.drafting_agent import draft_report, draft_report_with_model
from .subagents.guidance_agent import (
    GUIDANCE_AGENT_PROMPT,
    update_case_guidance,
)
from .subagents.intake_agent import detect_language
from .subagents.orchestrator_agent import (
    ORCHESTRATOR_AGENT_PROMPT,
    is_confirmation_message,
    plan_turn,
    plan_turn_with_model,
)
from .retrieval import retrieve_evidence_requirements, retrieve_legal_doc_ids
from .subagents.perception_agent import (
    PERCEPTION_AGENT_PROMPT,
    update_case_perception,
    update_case_perception_with_model,
)
from .subagents.safety_agent import SAFETY_AGENT_PROMPT
from .subagents.safety_agent import review_case_safety, review_case_safety_with_model
from .subagents.synthesis_agent import (
    SYNTHESIS_AGENT_PROMPT,
    compose_response,
    compose_response_with_model,
)
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
            ORCHESTRATOR_AGENT_PROMPT,
            PERCEPTION_AGENT_PROMPT,
            COMPLETENESS_AGENT_PROMPT,
            GUIDANCE_AGENT_PROMPT,
            DRAFTING_AGENT_PROMPT,
            SYNTHESIS_AGENT_PROMPT,
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

        plan = self._run_orchestrator(state, message, workflow_steps)
        has_pending_draft = (
            state.workflow_stage == "awaiting_user_confirmation"
            and bool(state.draft_text)
        )

        # Confirmation -> police submission (hard-guarded by a pending draft).
        if plan.intent == "confirm_submission" and has_pending_draft:
            state, response_text = self._run_submission_flow(state, message, workflow_steps)
            self.case_state = state
            return self._build_result(workflow_steps, response_text, state)

        # The orchestrator owns appending the message exactly once; workers
        # operate on the already-updated transcript.
        state = state.model_copy(deep=True)
        state.messages.append(message)
        state.language = state.language or detect_language(message)

        # Perception is conditional and incremental: only when the orchestrator
        # judged that the message carries new or corrected case data.
        if plan.carries_case_data:
            state = self._run_node(
                "Perception Agent",
                lambda current: self._run_perception_node(current, message),
                state,
                workflow_steps,
            )

        # Completeness is a cheap deterministic readiness check.
        state = self._run_node(
            "Completeness Agent",
            self._run_completeness_node,
            state,
            workflow_steps,
        )

        ready = state.report_ready and state.scam_type != "unknown"

        if ready and not has_pending_draft:
            state.workflow_stage = "ready_to_draft"
            self._begin("Drafting Agent", workflow_steps)
            draft_text = self._run_drafting_node(state)
            self._record_trace(
                "Drafting Agent",
                "Orchestrator routed to draft, so produce a police-ready report.",
                {"draft_preview": summarize_text(draft_text)},
                "Draft prepared; attach reporting guidance next.",
            )
            if self.verbose:
                self._print_latest_trace("Drafting Agent")
            state = self._run_node(
                "Guidance Agent",
                lambda current: self._run_guidance_node(current, "report_route"),
                state,
                workflow_steps,
            )
            response_text = attach_guidance_to_response(draft_text, state)
            state.draft_text = response_text
            state.workflow_stage = "awaiting_user_confirmation"
            synthesized = False
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
            response_text = self._run_synthesis_node(
                state, response_text, workflow_steps
            )
            synthesized = True

        self._begin("Safety Agent", workflow_steps)
        state, response_text = self._run_safety_node(state, response_text)
        if not synthesized:
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

    def _run_orchestrator(self, state: CaseState, message: str, workflow_steps: list[str]):
        """The supervisor: one LLM (or rule) call deciding intent + data."""
        self._begin("Orchestrator", workflow_steps)
        model = self._model_for("orchestrator")
        if model:
            plan = plan_turn_with_model(model, state, message)
        else:
            plan = plan_turn(state, message)
        self._record_trace(
            "Orchestrator",
            plan.rationale or "Select the workflow pathway before any worker runs.",
            {
                "intent": plan.intent,
                "carries_case_data": plan.carries_case_data,
                "decided_by": "model" if model else "offline_rule",
                "workflow_stage": state.workflow_stage,
                "has_pending_draft": bool(state.draft_text),
            },
            "Route to police submission."
            if plan.intent == "confirm_submission"
            else (
                "Run Perception (incremental), then assess and respond."
                if plan.carries_case_data
                else "No new case data; reuse known state and respond."
            ),
        )
        if self.verbose:
            self._print_latest_trace("Orchestrator")
        return plan

    def _run_perception_node(self, state: CaseState, message: str) -> CaseState:
        model = self._model_for("perception")
        if model:
            updated = update_case_perception_with_model(model, state, message)
        else:
            updated = update_case_perception(state, message)
        _requirements, retrieved_docs = retrieve_evidence_requirements(
            updated.scam_type, message
        )
        self._record_trace(
            "Perception Agent",
            "Incrementally extract incident facts and retrieve required "
            "evidence from the Case & Evidence DB in one pass.",
            {
                "scam_type": updated.scam_type,
                "classification_confidence": updated.classification_confidence,
                "location": updated.location,
                "incident_time": updated.incident_time,
                "amount_lost": updated.amount_lost,
                "known_evidence": updated.known_evidence_names,
                "retrieval": "case_evidence_db",
                "retrieved_docs": retrieved_docs,
            },
            "Updated case facts, classification, and collected evidence.",
        )
        return updated

    def _run_completeness_node(self, state: CaseState) -> CaseState:
        updated = update_case_completeness(state)
        self._record_trace(
            "Completeness Agent",
            "Deterministically check whether required fields and evidence are present.",
            {
                "report_ready": updated.report_ready,
                "missing_items": updated.missing_items,
                "next_question": updated.next_question,
            },
            "Returned readiness assessment to the orchestrator.",
        )
        return updated

    def _run_guidance_node(self, state: CaseState, mode: str) -> CaseState:
        updated = update_case_guidance(state, mode)
        retrieved_docs = retrieve_legal_doc_ids(updated.scam_type, mode)
        self._record_trace(
            "Guidance Agent",
            f"Retrieve tourist-facing guidance from the Legal DB ({mode}).",
            {
                "mode": mode,
                "route": updated.reporting_guidance.route if updated.reporting_guidance else None,
                "source_ids": updated.reporting_guidance.source_ids
                if updated.reporting_guidance
                else [],
                "retrieval": "legal_db",
                "retrieved_docs": retrieved_docs,
            },
            "Attached guidance for the current workflow branch.",
        )
        return updated

    def _run_synthesis_node(
        self,
        state: CaseState,
        response_text: str,
        workflow_steps: list[str],
    ) -> str:
        """Compose one natural tourist-facing reply from gathered outputs."""
        self._begin("Synthesis Agent", workflow_steps)
        model = self._model_for("synthesis")
        if model:
            composed = compose_response_with_model(model, state, response_text)
        else:
            composed = compose_response(state, response_text)
        self._record_trace(
            "Synthesis Agent",
            "Synthesize all gathered agent outputs into one natural reply.",
            {
                "decided_by": "model" if model else "offline_passthrough",
                "preview": summarize_text(composed),
            },
            "Final tourist-facing message composed.",
        )
        if self.verbose:
            self._print_latest_trace("Synthesis Agent")
        return composed

    def _run_drafting_node(self, state: CaseState) -> str:
        model = self._model_for("drafting")
        if not model:
            return draft_report(state)
        return draft_report_with_model(model, state)

    def _run_safety_node(self, state: CaseState, response_text: str) -> tuple[CaseState, str]:
        """Deterministic safety gate every turn; LLM rewrite only if flagged."""
        checked_state, checked_text = review_case_safety(state, response_text)
        model = self._model_for("safety")
        if model and checked_state.safety_review.flags:
            return review_case_safety_with_model(model, state, response_text)
        return checked_state, checked_text

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
