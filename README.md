# SafeTrip AI

SafeTrip AI is a tourist scam intake assistant for Thailand. It uses a
**supervisor (orchestrator) agent** that decides, every turn, which workers to
run, then composes one natural reply. The app runs as a single local service on
**http://127.0.0.1:8765** — the Python web demo serves the built React UI **and**
the agent backend together.

## Run (the only workflow)

Everything runs from this project folder. One service, one port.

```bash
# 1. Python env (first time only)
python3.11 -m venv .venv
.venv/bin/python -m pip install -e . pytest

# 2. Build the frontend bundle (Python serves this; no dev server)
cd frontend && npm install && npm run build && cd ..

# 3. Run the app
.venv/bin/python -m safetrip_agent.web_demo --port 8765 --env-file .env
```

Open **http://127.0.0.1:8765**.

- **Live mode** (default): needs `GEMINI_API_KEY` in `.env`. The orchestrator
  and workers use Gemini.
- **Offline mode**: add `--offline` to use the deterministic fallback with no
  API key (used by the tests).

> Note: there is **no `npm run dev` / port 5173** anymore. The frontend is built
> with `npm run build` and served by the Python service on 8765. To see UI
> changes, rebuild (`npm run build`) and refresh.

### CLI (optional)

```bash
.venv/bin/python -m safetrip_agent.cli --message "Taxi driver overcharged me in Bangkok today."
```

`--interactive` for a chat loop, `--verbose` to print the pipeline, `--offline`
for the no-key path.

## Test

```bash
.venv/bin/python -m pytest tests/ -q
```

## Architecture

A single LLM **Orchestrator** is the router. Workers are deterministic unless
judgment is genuinely required.

```text
user message
  -> ORCHESTRATOR (1 LLM call): intent + does the message carry case data?
       - confirm_submission (+pending draft) -> Submission Packet -> police endpoint
       - otherwise:
           [carries data] -> PERCEPTION (1 LLM call: classify + extract + evidence)
           -> COMPLETENESS (deterministic: required - collected)
           -> if ready: DRAFTING (LLM) -> GUIDANCE -> await confirmation
              else:     GUIDANCE -> SYNTHESIS (LLM: one natural reply)
       -> SAFETY (deterministic gate; LLM rewrite only if flagged)
  -> response
```

- **Perception** retrieves required evidence from the **Case & Evidence DB**
  (in-process vector index over `evidence_rules.py`).
- **Guidance** retrieves from the **Legal DB** (vector index over
  `legal_knowledge_base.py`).
- Retrieval is in `retrieval.py` — dependency-free, deterministic; authoritative
  outputs are unchanged, retrieval adds traceable provenance.

Per-turn LLM cost: recommendation/confirm ≈ 1 call, add info ≈ 2, draft ≈ 3
(down from ~6–7 in the earlier pipeline). Offline mode keeps every step
deterministic.

See `CLAUDE.md` for how the codebase is laid out and how to work in it.
