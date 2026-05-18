import {
  ArrowUp,
  Bot,
  ChevronDown,
  CircleDashed,
  FileText,
  RefreshCcw,
  Sparkles,
  UserRound,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

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

type CaseState = {
  workflow_stage?: string;
  scam_type?: string;
  classification_confidence?: number;
  location?: string | null;
  incident_time?: string | null;
  amount_lost?: string | null;
  evidence?: EvidenceItem[];
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
          <div className="brand-mark">ST</div>
          <div>
            <h1>SafeTrip AI</h1>
            <p>Incident intelligence console</p>
          </div>
        </div>

        <section className="panel">
          <div className="panel-title">
            <Sparkles size={16} />
            Runtime
          </div>
          <div className="runtime-card">
            <div className="status-dot-row">
              <span
                className={
                  status?.live_model_available ? "status-dot live" : "status-dot muted"
                }
              />
              <strong>
                {mode === "live" ? "Live LLM mode" : "Deterministic fallback"}
              </strong>
            </div>
            <p>{statusText(status, mode)}</p>
          </div>
          <div className="segmented-control" aria-label="Runtime mode">
            <button
              className={mode === "live" ? "active" : ""}
              type="button"
              onClick={() => setMode("live")}
            >
              Live
            </button>
            <button
              className={mode === "offline" ? "active" : ""}
              type="button"
              onClick={() => setMode("offline")}
            >
              Offline
            </button>
          </div>
        </section>

        <CasePanel caseState={latestCase} />

        <button className="ghost-button" type="button" onClick={resetCase}>
          <RefreshCcw size={16} />
          Reset case
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h2>Tourist Support Chat</h2>
            <p>Every response includes the agent pipeline used to reach it.</p>
          </div>
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
            <div className="trace-row" key={`${trace.agent_name ?? "agent"}-${index}`}>
              <div className="trace-marker">
                <span className="trace-node" />
              </div>
              <div className="trace-content">
                <div className="trace-heading">
                  <strong>{trace.agent_name ?? "Agent"}</strong>
                  <span>{trace.decision ?? "Completed"}</span>
                </div>
                <p>{trace.thought ?? "Completed this workflow step."}</p>
                <code>{formatCollectedData(trace.collected_data)}</code>
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
  const missing = caseState?.missing_items ?? [];

  const hasCase = Boolean(caseState?.workflow_stage);
  const scamType = caseState?.scam_type;
  const typeKnown = Boolean(scamType && scamType !== "unknown");
  const location = caseState?.location;
  const incidentTime = caseState?.incident_time;
  const hasEvidence = evidence.length > 0;
  const hasMissing = missing.length > 0;

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
          tone={hasCase ? "ok" : "pending"}
        />
        <Field
          label="Type"
          value={typeKnown ? pretty(scamType) : "Not identified yet"}
          tone={typeKnown ? "ok" : "pending"}
        />
        <Field
          label="Location"
          value={location || "Not collected yet"}
          tone={location ? "ok" : "pending"}
        />
        <Field
          label="Time"
          value={incidentTime || "Not collected yet"}
          tone={incidentTime ? "ok" : "pending"}
        />
        <Field
          label="Evidence"
          value={
            hasEvidence
              ? evidence.map((item) => pretty(item.name)).join(", ")
              : "Not collected yet"
          }
          tone={hasEvidence ? "ok" : "pending"}
        />
        <Field
          label="Still needed"
          value={hasMissing ? missing.map(pretty).join(", ") : "All required info collected"}
          tone={hasMissing ? "attention" : "ok"}
        />
      </div>
    </section>
  );
}

type FieldTone = "ok" | "pending" | "attention";

function Field({
  label,
  value,
  tone = "ok",
}: {
  label: string;
  value: string;
  tone?: FieldTone;
}) {
  return (
    <div className={`field field-${tone}`}>
      <span className="field-label">
        <span className="field-dot" />
        {label}
      </span>
      <strong>{value}</strong>
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

function statusText(status: StatusPayload | null, mode: RuntimeMode) {
  if (!status) return "Checking model configuration...";
  if (mode === "offline") return "Uses deterministic local rules for stable demos.";
  if (status.live_model_available) {
    return `${status.provider.toUpperCase()} credentials detected. Web chat will call the same LLM path as the terminal.`;
  }
  return status.model_hint || "Live model credentials are missing.";
}

function pretty(value?: string | null) {
  return value ? value.replaceAll("_", " ") : "";
}

function formatCollectedData(data?: Record<string, unknown>) {
  if (!data || Object.keys(data).length === 0) return "No structured data reported.";
  return Object.entries(data)
    .map(([key, value]) => `${pretty(key)}: ${stringifyValue(value)}`)
    .join(" | ");
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) return "none";
  if (Array.isArray(value)) {
    if (value.length === 0) return "none";
    return value.map(stringifyValue).join(", ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}
