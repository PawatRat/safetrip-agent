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
