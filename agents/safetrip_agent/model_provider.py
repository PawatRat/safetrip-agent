from __future__ import annotations

import os

from langchain_openai import ChatOpenAI


DEFAULT_AGENT_MODELS = {
    "orchestrator": "gemini-2.5-flash",
    "intake": "gemini-2.5-flash",
    "evidence": "gemini-2.5-flash",
    "completeness": "gemini-2.5-pro",
    "guidance": "gemini-2.5-flash",
    "drafting": "gemini-2.5-pro",
    "safety": "gemini-2.5-pro",
}


def build_model(model_name: str | None = None):
    provider = os.getenv("SAFETRIP_MODEL_PROVIDER", "gemini").lower()
    resolved_model_name = model_name or os.getenv("SAFETRIP_MODEL")

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_api_key:
            raise RuntimeError(
                "Missing GEMINI_API_KEY. Add it to .env or export it before running."
            )
        return ChatGoogleGenerativeAI(
            model=resolved_model_name or DEFAULT_AGENT_MODELS["intake"],
            temperature=0.1,
            google_api_key=gemini_api_key,
        )

    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "Missing OPENAI_API_KEY. Add it to .env or export it before running."
            )
        return ChatOpenAI(
            model=resolved_model_name or "gpt-4.1-mini",
            temperature=0.1,
        )

    raise ValueError("Unsupported SAFETRIP_MODEL_PROVIDER. Use 'openai' or 'gemini'.")


def build_agent_models() -> dict[str, object]:
    """Build per-agent chat models using defaults plus environment overrides."""
    return {
        agent_name: build_model(resolve_agent_model_name(agent_name))
        for agent_name in DEFAULT_AGENT_MODELS
    }


def resolve_agent_model_name(agent_name: str) -> str:
    env_name = f"SAFETRIP_{agent_name.upper()}_MODEL"
    return os.getenv(env_name) or DEFAULT_AGENT_MODELS[agent_name]
