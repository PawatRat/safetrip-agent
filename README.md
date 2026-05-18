# SafeTrip AI

SafeTrip AI is a tourist scam intake workflow prototype for Thailand. The current
implementation uses explicit workflow nodes for intake, evidence mapping,
reporting guidance, completeness gating, drafting, and safety review.

## Run

```bash
.venv/bin/python agents/safetrip_langchain_workflow.py --message "Taxi driver overcharged me in Bangkok today."
```

Use `--interactive` for a local chat loop and `--verbose` to show workflow steps.

## Test

```bash
.venv/bin/python -m unittest discover -s tests
```

## Web Demo

Build the React frontend, then run the web demo locally:

```bash
cd frontend
npm install
npm run build
cd ..
PYTHONPATH=agents .venv/bin/python -m safetrip_agent.web_demo --port 8765
```

Then open:

```text
http://127.0.0.1:8765
```

The web demo is additive. It uses the same `SafeTripOrchestrator` and shows each
agent pipeline trace beside the chat response. By default the web demo uses the
same live model path as the terminal. Start it with `--offline` only when you
want deterministic fallback behavior without Gemini/OpenAI credentials.

## Architecture Direction

The Phase 3 implementation keeps the system deterministic and auditable:

```text
tourist message
-> Intake Agent updates CaseState
-> Evidence Agent maps evidence requirements
-> Guidance Agent attaches source-linked route
-> Completeness Agent gates report readiness
-> Drafting Agent drafts only when ready
-> Safety Agent reviews final text
```

LLM/provider configuration remains available for future drafting or extraction
enhancement, but the core case workflow no longer requires an API key.
