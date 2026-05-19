# Working on SafeTrip AI

Guide for contributors (and Claude) working in this repo.

## One service, one port

The whole app is the Python web demo on **http://127.0.0.1:8765**. It serves the
**built** React bundle (`frontend/dist`) *and* the agent backend. There is no
separate dev server / port 5173 — the frontend is produced with
`npm run build` and served by Python.

```bash
.venv/bin/python -m safetrip_agent.web_demo --port 8765 --env-file .env   # run
.venv/bin/python -m pytest tests/ -q                                       # test
cd frontend && npm run build && cd ..                                      # rebuild UI
```

To see frontend changes: `npm run build`, then refresh the browser.

## Layout

```
agents/safetrip_agent/
  orchestrator.py            # the pipeline: process(), node wiring, traces, streaming
  retrieval.py               # in-process vector index (Case&Evidence DB, Legal DB)
  evidence_rules.py          # SCAM_EVIDENCE_RULES (evidence requirements per scam type)
  legal_knowledge_base.py    # legal sources / guidance entries
  model_provider.py          # per-agent model map (DEFAULT_AGENT_MODELS)
  schemas.py                 # pydantic models (CaseState, *Extraction, *Plan, ...)
  web_demo.py                # HTTP server: /api/chat, /api/chat/stream (SSE), static
  cli.py                     # terminal entrypoint
  subagents/
    orchestrator_agent.py    # the supervisor: plan_turn (intent + carries_case_data)
    perception_agent.py      # merged classify + fact/evidence extraction (incremental)
    completeness_agent.py    # deterministic readiness (required - collected)
    guidance_agent.py        # legal guidance retrieval
    drafting_agent.py        # police-ready report (LLM path)
    synthesis_agent.py       # composes the final natural tourist reply
    safety_agent.py          # deterministic gate; LLM rewrite only when flagged
frontend/src/App.tsx         # the entire UI (chat + streamed pipeline panel)
tests/                       # pytest; assert workflow_steps and final_text
```

## How the pipeline works

`SafeTripOrchestrator.process(message)` runs each turn:

1. **Orchestrator** (1 LLM call) → `OrchestratorPlan {intent, carries_case_data}`.
2. `confirm_submission` + a pending draft → **Submission Packet** → police endpoint.
3. else: if `carries_case_data` → **Perception** (1 LLM call, incremental).
4. **Completeness** (deterministic).
5. ready → **Drafting** (LLM) → **Guidance**; else **Guidance** → **Synthesis** (LLM).
6. **Safety** gate (deterministic; LLM rewrite only if a flag fires).

Each step emits an `agent_start` + `trace` event (SSE) → the UI pipeline panel.

## Rules / conventions (do not break these)

- **Every agent has a deterministic offline fallback.** `use_model=False` (and
  the tests) must work with no API key. Keep behaviour identical offline.
- **Tests assert exact `workflow_steps` lists and `final_text` substrings.** If
  you add/rename/reorder a pipeline step, update `tests/` accordingly and run
  `pytest` until green.
- **LLM only where judgment is needed.** Routing decisions, completeness, and
  guidance retrieval are deterministic. Don't add LLM calls casually — per-turn
  cost matters.
- **Hard guards stay:** can't `submit` without a pending draft; can't `draft` an
  unclassified case; default-to-extract when intent is ambiguous.
- **Retrieval is additive.** `retrieval.py` adds provenance; authoritative
  evidence/guidance still come from the existing functions — keep outputs
  identical so features/tests are unaffected.
- The pipeline UI renders steps generically, so new step names "just work"
  visually, but their names appear in tests.

## Models

`model_provider.DEFAULT_AGENT_MODELS` maps agent → Gemini model. Override per
agent with env vars like `SAFETRIP_ORCHESTRATOR_MODEL`. `_model_for(name)` in
the orchestrator resolves `agent_models` → `self.model`; if `None`, the
deterministic path runs.

## Git workflow

`main` on GitHub is the source of truth. Run/open this project folder only. When
changes land they are committed and pushed to `main`; keep the working tree
clean (let git be the channel). Don't hand-edit tracked files in two places.
