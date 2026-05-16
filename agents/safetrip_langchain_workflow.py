"""Compatibility entrypoint for the SafeTrip AI agent CLI.

The implementation now lives in the `safetrip_agent` package:

- `safetrip_agent/orchestrator.py` coordinates the agent workflow.
- `safetrip_agent/subagents/` contains task-focused subagent modules.
- `safetrip_agent/tools.py` re-exports callable LangChain tools for compatibility.
- `safetrip_agent/evidence_rules.py` contains scam evidence rules.
- `safetrip_agent/model_provider.py` configures Gemini/OpenAI models.
- `safetrip_agent/cli.py` handles terminal usage.
"""

from __future__ import annotations

from safetrip_agent.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
