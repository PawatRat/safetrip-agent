import {
  ArrowUp,
  Bot,
  Check,
  ChevronDown,
  CircleDashed,
  ClipboardList,
  FileText,
  FileUp,
  ListChecks,
  Minus,
  RefreshCcw,
  Route,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { FormEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

type RuntimeMode = "live" | "offline";

type AgentTrace = {
  agent_name?: string;
  thought?: string;
  collected_data?: Record<string, unknown>;
  decision?: string;
};

type EvidenceItem = {
  name?: string;
  description?: string;
};

type GuidanceSource = {
  title?: string;
  url?: string;
};

type ReportingGuidance = {
  route?: string;
  recommended_actions?: string[];
  sources?: GuidanceSource[];
};

type EvidenceRequirement = {
  name?: string;
  required_level?: string;
  reason?: string;
};

type CaseState = {
  workflow_stage?: string;
  scam_type?: string;
  classification_confidence?: number;
  location?: string | null;
  incident_time?: string | null;
  amount_lost?: string | null;
  evidence?: EvidenceItem[];
  evidence_requirements?: EvidenceRequirement[];
  missing_items?: string[];
  next_question?: string | null;
  report_ready?: boolean;
  reporting_guidance?: ReportingGuidance | null;
};

type ChatPayload = {
  final_text: string;
  workflow_steps: string[];
  agent_traces: AgentTrace[];
  case_state: CaseState;
};

type StatusPayload = {
  provider: string;
  live_model_available: boolean;
  default_mode: RuntimeMode;
  model_hint?: string;
};

type ChatTurn = {
  id: string;
  userText: string;
  assistantText?: string;
  pipeline?: AgentTrace[];
  workflowSteps?: string[];
  caseState?: CaseState;
  error?: string;
  streaming?: boolean;
  currentAgent?: string | null;
};

type StreamEvent =
  | { type: "agent_start"; agent_name: string }
  | { type: "trace"; trace: AgentTrace }
  | ({ type: "final" } & ChatPayload)
  | { type: "error"; error?: string; hint?: string };

const examples = [
  "A taxi driver charged me 2500 THB and refused the meter near JJ Mall today.",
  "I booked a Phuket villa from Facebook and transferred 12000 THB, but the hotel has no booking.",
  "Someone stole my passport and wallet at a night market in Chiang Mai.",
];

function createId() {
  return globalThis.crypto?.randomUUID?.() ?? `id_${Date.now()}_${Math.random()}`;
}

export default function App() {
  const [sessionId, setSessionId] = useState(createId);
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [mode, setMode] = useState<RuntimeMode>("live");
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [isSending, setIsSending] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const latestCase = useMemo(
    () => [...turns].reverse().find((turn) => turn.caseState)?.caseState,
    [turns],
  );

  useEffect(() => {
    fetch("/api/status")
      .then((response) => response.json())
      .then((payload: StatusPayload) => {
        setStatus(payload);
        setMode(payload.default_mode);
      })
      .catch(() => {
        setStatus({
          provider: "unknown",
          live_model_available: false,
          default_mode: "live",
          model_hint: "Web server status is unavailable.",
        });
      });
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns, isSending]);

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = "auto";

    const maxHeight = Number.parseFloat(getComputedStyle(textarea).maxHeight);
    const nextHeight = Number.isFinite(maxHeight)
      ? Math.min(textarea.scrollHeight, maxHeight)
      : textarea.scrollHeight;

    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > nextHeight ? "auto" : "hidden";
  }, [input]);

  async function sendMessage(message: string) {
    const trimmed = message.trim();
    if (!trimmed || isSending) return;

    const turnId = createId();
    setInput("");
    setIsSending(true);
    setTurns((current) => [
      ...current,
      { id: turnId, userText: trimmed, streaming: true, pipeline: [], workflowSteps: [] },
    ]);

    const patch = (mutate: (turn: ChatTurn) => ChatTurn) =>
      setTurns((current) =>
        current.map((turn) => (turn.id === turnId ? mutate(turn) : turn)),
      );

    const applyEvent = (event: StreamEvent) => {
      if (event.type === "agent_start") {
        patch((turn) => ({
          ...turn,
          currentAgent: event.agent_name,
          workflowSteps: turn.workflowSteps?.includes(event.agent_name)
            ? turn.workflowSteps
            : [...(turn.workflowSteps ?? []), event.agent_name],
        }));
      } else if (event.type === "trace") {
        patch((turn) => ({
          ...turn,
          pipeline: [...(turn.pipeline ?? []), event.trace],
          currentAgent: null,
        }));
      } else if (event.type === "final") {
        patch((turn) => ({
          ...turn,
          assistantText: event.final_text,
          pipeline: event.agent_traces ?? turn.pipeline,
          workflowSteps: event.workflow_steps ?? turn.workflowSteps,
          caseState: event.case_state,
          streaming: false,
          currentAgent: null,
        }));
      } else if (event.type === "error") {
        patch((turn) => ({
          ...turn,
          error: event.hint || event.error || "The request failed unexpectedly.",
          streaming: false,
          currentAgent: null,
        }));
      }
    };

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message: trimmed,
          offline: mode === "offline",
        }),
      });

      if (!response.ok || !response.body) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.hint || payload.error || "Request failed");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";
        for (const chunk of chunks) {
          const dataLine = chunk
            .split("\n")
            .find((line) => line.startsWith("data:"));
          if (!dataLine) continue;
          try {
            applyEvent(JSON.parse(dataLine.slice(5).trim()) as StreamEvent);
          } catch {
            // Ignore malformed/keepalive lines.
          }
        }
      }
    } catch (error) {
      patch((turn) => ({
        ...turn,
        error:
          error instanceof Error
            ? error.message
            : "The request failed unexpectedly.",
        streaming: false,
        currentAgent: null,
      }));
    } finally {
      patch((turn) => (turn.streaming ? { ...turn, streaming: false } : turn));
      setIsSending(false);
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    await sendMessage(input);
  }

  async function resetCase() {
    await fetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
    setSessionId(createId());
    setTurns([]);
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <h1>SafeTrip AI</h1>
        </div>

        <section className="panel runtime-panel" aria-label="Runtime">
          <div className="runtime-card">
            <div className="status-dot-row">
              <Sparkles size={14} />
              <span
                className={
                  status?.live_model_available ? "status-dot live" : "status-dot muted"
                }
              />
              <strong>
                {runtimeLabel(status)}
              </strong>
            </div>
          </div>
        </section>

        <CasePanel caseState={latestCase} />

        <EvidenceChecklist caseState={latestCase} />

      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h2>Tourist Support Chat</h2>
            <p>Every response includes the agent pipeline used to reach it.</p>
          </div>
          <button className="topbar-reset" type="button" onClick={resetCase}>
            <RefreshCcw size={15} />
            Reset case
          </button>
        </header>

        <div className="conversation" ref={listRef}>
          {turns.length === 0 ? (
            <EmptyState onExample={sendMessage} />
          ) : (
            turns.map((turn) => <ChatTurnView key={turn.id} turn={turn} />)
          )}
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void sendMessage(input);
              }
            }}
            placeholder="Message SafeTrip AI about a tourist incident..."
            rows={1}
          />
          <button disabled={isSending || !input.trim()} type="submit">
            <ArrowUp size={18} />
          </button>
        </form>
      </section>
    </main>
  );
}

function EmptyState({ onExample }: { onExample: (message: string) => Promise<void> }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Bot size={28} />
      </div>
      <h2>Start a tourist incident case</h2>
      <p>
        SafeTrip will classify the case, collect evidence, retrieve guidance, and
        draft a police-ready report when the information is complete.
      </p>
      <div className="example-grid">
        {examples.map((example) => (
          <button key={example} type="button" onClick={() => onExample(example)}>
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}

function ChatTurnView({ turn }: { turn: ChatTurn }) {
  return (
    <article className="turn">
      <div className="message user">
        <div className="avatar">
          <UserRound size={17} />
        </div>
        <div className="bubble">{turn.userText}</div>
      </div>

      {turn.pipeline?.length || turn.streaming ? (
        <PipelinePanel
          traces={turn.pipeline ?? []}
          steps={turn.workflowSteps ?? []}
          streaming={turn.streaming ?? false}
          currentAgent={turn.currentAgent}
        />
      ) : null}

      {turn.assistantText ? (
        <div className="message assistant">
          <div className="avatar">
            <Bot size={17} />
          </div>
          <div className="bubble">
            <FormattedText text={turn.assistantText} />
          </div>
        </div>
      ) : null}

      {turn.error ? (
        <div className="message assistant">
          <div className="avatar error">
            <CircleDashed size={17} />
          </div>
          <div className="bubble error">
            <strong>SafeTrip could not complete the request.</strong>
            <span>{turn.error}</span>
          </div>
        </div>
      ) : null}
    </article>
  );
}

function PipelinePanel({
  traces,
  steps,
  streaming,
  currentAgent,
}: {
  traces: AgentTrace[];
  steps: string[];
  streaming: boolean;
  currentAgent?: string | null;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const open = streaming || !collapsed;

  const liveAgent = streaming
    ? currentAgent ?? (traces.length === 0 ? "Starting pipeline" : null)
    : null;

  return (
    <section className="pipeline">
      <button
        className="pipeline-summary"
        type="button"
        onClick={() => setCollapsed((value) => !value)}
      >
        <div>
          <span className={streaming ? "thinking-pulse live" : "thinking-pulse"} />
          <strong>{streaming ? "Thinking…" : "Thinking process"}</strong>
          <small>{steps.join(" -> ")}</small>
        </div>
        <ChevronDown className={open ? "rotated" : ""} size={18} />
      </button>
      {open ? (
        <div className="trace-stack">
          {traces.map((trace, index) => (
            <div className="trace-row" key={`${trace.agent_name ?? "step"}-${index}`}>
              <div className="trace-marker">
                <TraceStepIcon stepName={trace.agent_name} />
              </div>
              <div className="trace-content">
                <div className="trace-heading">
                  <strong>{displayStepName(trace.agent_name)}</strong>
                  <span>{trace.decision ?? "Completed"}</span>
                </div>
                <p>{trace.thought ?? "Completed this workflow step."}</p>
                <TraceDetails data={trace.collected_data} />
              </div>
            </div>
          ))}
          {liveAgent ? (
            <div className="trace-row active" key="live-agent">
              <div className="trace-marker">
                <span className="trace-spinner" />
              </div>
              <div className="trace-content">
                <span className="trace-live-label">
                  {pretty(liveAgent)} is working…
                </span>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function CasePanel({ caseState }: { caseState?: CaseState }) {
  const evidence = caseState?.evidence ?? [];

  const hasCase = Boolean(caseState?.workflow_stage);
  const scamType = caseState?.scam_type;
  const typeKnown = Boolean(scamType && scamType !== "unknown");
  const location = caseState?.location;
  const incidentTime = caseState?.incident_time;
  const hasEvidence = evidence.length > 0;

  return (
    <section className="panel">
      <div className="panel-title">
        <FileText size={16} />
        Active case
      </div>
      <div className="case-grid">
        <Field
          label="Stage"
          value={hasCase ? pretty(caseState?.workflow_stage) : "No active case"}
          collected={hasCase}
        />
        <Field
          label="Type"
          value={typeKnown ? pretty(scamType) : "Not identified yet"}
          collected={typeKnown}
        />
        <Field
          label="Location"
          value={location || "Not collected yet"}
          collected={Boolean(location)}
        />
        <Field
          label="Time"
          value={incidentTime || "Not collected yet"}
          collected={Boolean(incidentTime)}
        />
        <Field
          label="Evidence"
          value={
            hasEvidence
              ? evidence.map((item) => pretty(item.name)).join(", ")
              : "Not collected yet"
          }
          collected={hasEvidence}
        />
      </div>
    </section>
  );
}

function EvidenceChecklist({ caseState }: { caseState?: CaseState }) {
  const requirements = caseState?.evidence_requirements ?? [];
  const collected = new Set(
    (caseState?.evidence ?? [])
      .map((item) => item.name)
      .filter((name): name is string => Boolean(name)),
  );

  return (
    <section className="panel">
      <div className="panel-title">
        <ClipboardList size={16} />
        Evidence for this case
      </div>
      {requirements.length === 0 ? (
        <p className="checklist-empty">
          Once the case is classified, the evidence this specific case needs
          will appear here.
        </p>
      ) : (
        <ul className="checklist">
          {requirements.map((req, index) => {
            const have = req.name ? collected.has(req.name) : false;
            return (
              <li className="checklist-item" key={`${req.name ?? "req"}-${index}`}>
                <StatusMark collected={have} />
                <div className="checklist-body">
                  <div className="checklist-head">
                    <span className="checklist-level">
                      {pretty(req.required_level) || "optional"}
                    </span>
                    <strong className={have ? "" : "muted"}>
                      {pretty(req.name) || "Evidence item"}
                    </strong>
                  </div>
                  {req.reason ? <p>{req.reason}</p> : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function StatusMark({ collected }: { collected: boolean }) {
  return (
    <span className={collected ? "status-mark on" : "status-mark"}>
      {collected ? <Check size={13} strokeWidth={2.5} /> : <Minus size={13} />}
    </span>
  );
}

function Field({
  label,
  value,
  collected,
}: {
  label: string;
  value: string;
  collected: boolean;
}) {
  return (
    <div className="field">
      <StatusMark collected={collected} />
      <div className="field-text">
        <span className="field-label">{label}</span>
        <strong className={collected ? "" : "muted"}>{value}</strong>
      </div>
    </div>
  );
}

function FormattedText({ text }: { text: string }) {
  const [visibleText, setVisibleText] = useState("");

  useEffect(() => {
    setVisibleText("");
    let index = 0;
    const timer = window.setInterval(() => {
      index = Math.min(index + 3, text.length);
      setVisibleText(text.slice(0, index));
      document.querySelector(".conversation")?.scrollTo({
        top: document.querySelector(".conversation")?.scrollHeight ?? 0,
      });
      if (index >= text.length) {
        window.clearInterval(timer);
      }
    }, 14);
    return () => window.clearInterval(timer);
  }, [text]);

  return (
    <>
      {visibleText.split("\n").map((line, index) => (
        <span className="text-line" key={`${line}-${index}`}>
          {line || "\u00a0"}
        </span>
      ))}
      {visibleText.length < text.length ? <span className="typing-cursor" /> : null}
    </>
  );
}

function runtimeLabel(status: StatusPayload | null) {
  if (!status) return "Checking API";
  return status.live_model_available ? "API Detected" : "API Not Detected";
}

function displayStepName(stepName?: string) {
  switch (stepName) {
    case "Completeness Agent":
      return "Completeness check";
    case "Guidance Agent":
      return "Guidance retrieval";
    case "Safety Agent":
      return "Safety check";
    case "Submission Packet Agent":
      return "Submission packet";
    default:
      return stepName ?? "Workflow step";
  }
}

function TraceStepIcon({ stepName }: { stepName?: string }) {
  const className = isLlmStep(stepName) ? "trace-step-icon llm" : "trace-step-icon rule";

  switch (stepName) {
    case "Completeness Agent":
      return <ListChecks className={className} size={14} strokeWidth={2.3} />;
    case "Guidance Agent":
      return <Route className={className} size={14} strokeWidth={2.3} />;
    case "Safety Agent":
      return <ShieldCheck className={className} size={14} strokeWidth={2.3} />;
    case "Submission Packet Agent":
      return <FileUp className={className} size={14} strokeWidth={2.3} />;
    default:
      return <Bot className={className} size={14} strokeWidth={2.3} />;
  }
}

function isLlmStep(stepName?: string) {
  return [
    "Orchestrator",
    "Perception Agent",
    "Drafting Agent",
    "Synthesis Agent",
  ].includes(stepName ?? "");
}

function pretty(value?: string | null) {
  return value ? value.replaceAll("_", " ") : "";
}

function TraceDetails({ data }: { data?: Record<string, unknown> }) {
  const lines = formatTraceDetails(data);
  if (lines.length === 0) {
    return <p className="trace-detail-empty">No extra details reported.</p>;
  }
  return (
    <dl className="trace-detail-list">
      {lines.map((line) => (
        <div className="trace-detail-item" key={`${line.label}-${line.value}`}>
          <dt>{line.label}</dt>
          <dd>{line.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function formatTraceDetails(data?: Record<string, unknown>) {
  if (!data || Object.keys(data).length === 0) return [];

  const lines: Array<{ label: string; value: string }> = [];
  const used = new Set<string>();
  const add = (key: string, label: string, value?: unknown) => {
    if (value === undefined || value === null || value === "" || value === false) return;
    used.add(key);
    lines.push({ label, value: formatTraceValue(value) });
  };

  add("intent", "Route", explainIntent(data.intent));
  add("carries_case_data", "New case details", data.carries_case_data === true ? "Yes" : "No");
  add("decided_by", "Uses AI", data.decided_by === "model" ? "Yes" : "No, rule-based");
  add("workflow_stage", "Case stage", data.workflow_stage);
  add("has_pending_draft", "Draft waiting for confirmation", data.has_pending_draft === true ? "Yes" : "No");

  add("scam_type", "Case type", data.scam_type);
  add("classification_confidence", "Confidence", formatConfidence(data.classification_confidence));
  add("location", "Location", data.location);
  add("incident_time", "Time", data.incident_time);
  add("amount_lost", "Amount", data.amount_lost);
  add("known_evidence", "Evidence found", data.known_evidence);

  add("report_ready", "Ready to draft", data.report_ready === true ? "Yes" : "No");
  add("missing_items", "Still needed", data.missing_items);
  add("next_question", "Next question", data.next_question);

  add("mode", "Guidance mode", explainGuidanceMode(data.mode));
  add("route", "Reporting route", data.route);
  add("source_ids", "Sources", data.source_ids);

  add("draft_preview", "Draft preview", data.draft_preview);
  add("preview", "Response preview", data.preview);
  add("flags", "Safety flags", data.flags);
  add("notes", "Safety notes", data.notes);
  add("packet_path", "Packet file", data.packet_path);
  add("endpoint", "Endpoint", data.endpoint);
  add("api_error", "API issue", data.api_error);

  for (const [key, value] of Object.entries(data)) {
    if (used.has(key)) continue;
    add(key, titleCase(pretty(key)), value);
  }

  return lines;
}

function explainIntent(value: unknown) {
  if (value === "provide_info") return "Collect or update case details";
  if (value === "confirm_submission") return "Confirm submission";
  if (value === "ask_advice") return "Answer a guidance question";
  if (value === "other") return "General support";
  return value;
}

function explainGuidanceMode(value: unknown) {
  if (value === "intake_help") return "Help collect missing details";
  if (value === "report_route") return "Prepare reporting instructions";
  return value;
}

function formatConfidence(value: unknown) {
  if (typeof value !== "number") return value;
  return `${Math.round(value * 100)}%`;
}

function formatTraceValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "None";
  if (Array.isArray(value)) {
    if (value.length === 0) return "None";
    return value.map(formatTraceValue).join(", ");
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return String(value);
  if (typeof value === "object") return summarizeObject(value);
  return pretty(String(value));
}

function summarizeObject(value: object) {
  const entries = Object.entries(value);
  if (entries.length === 0) return "None";
  return entries
    .slice(0, 4)
    .map(([key, item]) => `${pretty(key)}: ${formatTraceValue(item)}`)
    .join(", ");
}

function titleCase(value: string) {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}
