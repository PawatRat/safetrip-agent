from __future__ import annotations

import os

from langchain_openai import AzureChatOpenAI, ChatOpenAI


AGENT_TIERS: dict[str, str] = {
    "orchestrator": "low",
    "perception": "low",
    "intake": "low",
    "evidence": "low",
    "completeness": "high",
    "guidance": "low",
    "drafting": "high",
    "synthesis": "low",
    "safety": "high",
}


def _provider() -> str:
    return os.getenv("SAFETRIP_MODEL_PROVIDER", "gemini").lower()


def _tier_models() -> dict[str, str]:
    provider = _provider()
    if provider == "gemini":
        return {"low": "gemini-2.5-flash", "high": "gemini-2.5-pro"}
    if provider == "azure":
        return {
            "low": os.getenv("SAFETRIP_AZURE_LOW_DEPLOYMENT", "gpt-5-mini"),
            "high": os.getenv("SAFETRIP_AZURE_HIGH_DEPLOYMENT", "gpt-5"),
        }
    if provider == "openai":
        return {"low": "gpt-4o-mini", "high": "gpt-4o"}
    raise ValueError(
        "Unsupported SAFETRIP_MODEL_PROVIDER. Use 'gemini', 'azure', or 'openai'."
    )


# Kept as a derived dict for backward compatibility with callers/tests that
# read it. Resolves to the active provider's per-tier model.
DEFAULT_AGENT_MODELS: dict[str, str] = {
    agent: _tier_models()[tier] for agent, tier in AGENT_TIERS.items()
}


def resolve_agent_model_name(agent_name: str) -> str:
    env_name = f"SAFETRIP_{agent_name.upper()}_MODEL"
    override = os.getenv(env_name)
    if override:
        return override
    tier = AGENT_TIERS[agent_name]
    return _tier_models()[tier]


def build_model(model_name: str | None = None):
    provider = _provider()
    resolved = model_name or os.getenv("SAFETRIP_MODEL")

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_api_key:
            raise RuntimeError(
                "Missing GEMINI_API_KEY. Add it to .env or export it before running."
            )
        return ChatGoogleGenerativeAI(
            model=resolved or _tier_models()["low"],
            temperature=0.1,
            google_api_key=gemini_api_key,
        )

    if provider == "azure":
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        if not endpoint or not api_key:
            raise RuntimeError(
                "Missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY. "
                "Set them in .env (or as Container App secrets) before running."
            )
        return AzureChatOpenAI(
            azure_deployment=resolved or _tier_models()["low"],
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            temperature=0.1,
        )

    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "Missing OPENAI_API_KEY. Add it to .env or export it before running."
            )
        return ChatOpenAI(
            model=resolved or _tier_models()["low"],
            temperature=0.1,
        )

    raise ValueError(
        "Unsupported SAFETRIP_MODEL_PROVIDER. Use 'gemini', 'azure', or 'openai'."
    )


def build_agent_models() -> dict[str, object]:
    """Build per-agent chat models using tier defaults plus environment overrides."""
    return {
        agent_name: build_model(resolve_agent_model_name(agent_name))
        for agent_name in AGENT_TIERS
    }
