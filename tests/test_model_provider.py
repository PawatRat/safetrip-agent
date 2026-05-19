from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def mp(monkeypatch):
    """Reload model_provider so module-level reads of env vars are fresh."""
    for key in (
        "SAFETRIP_MODEL_PROVIDER",
        "SAFETRIP_MODEL",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_API_VERSION",
        "SAFETRIP_AZURE_LOW_DEPLOYMENT",
        "SAFETRIP_AZURE_HIGH_DEPLOYMENT",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "SAFETRIP_DRAFTING_MODEL",
        "SAFETRIP_ORCHESTRATOR_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    import agents.safetrip_agent.model_provider as m

    return importlib.reload(m)


def test_tier_resolution_gemini(mp, monkeypatch):
    monkeypatch.setenv("SAFETRIP_MODEL_PROVIDER", "gemini")
    assert mp.resolve_agent_model_name("orchestrator") == "gemini-2.5-flash"
    assert mp.resolve_agent_model_name("drafting") == "gemini-2.5-pro"


def test_tier_resolution_azure_defaults(mp, monkeypatch):
    monkeypatch.setenv("SAFETRIP_MODEL_PROVIDER", "azure")
    assert mp.resolve_agent_model_name("orchestrator") == "gpt-5-mini"
    assert mp.resolve_agent_model_name("drafting") == "gpt-5"


def test_tier_resolution_azure_custom_deployments(mp, monkeypatch):
    monkeypatch.setenv("SAFETRIP_MODEL_PROVIDER", "azure")
    monkeypatch.setenv("SAFETRIP_AZURE_LOW_DEPLOYMENT", "my-low")
    monkeypatch.setenv("SAFETRIP_AZURE_HIGH_DEPLOYMENT", "my-high")
    assert mp.resolve_agent_model_name("perception") == "my-low"
    assert mp.resolve_agent_model_name("safety") == "my-high"


def test_per_agent_override_wins(mp, monkeypatch):
    monkeypatch.setenv("SAFETRIP_MODEL_PROVIDER", "azure")
    monkeypatch.setenv("SAFETRIP_DRAFTING_MODEL", "custom-draft-deployment")
    assert mp.resolve_agent_model_name("drafting") == "custom-draft-deployment"
    # Other agents still resolve via tier.
    assert mp.resolve_agent_model_name("orchestrator") == "gpt-5-mini"


def test_azure_build_model_returns_azure_chat_openai(mp, monkeypatch):
    monkeypatch.setenv("SAFETRIP_MODEL_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    from langchain_openai import AzureChatOpenAI

    model = mp.build_model(mp.resolve_agent_model_name("drafting"))
    assert isinstance(model, AzureChatOpenAI)
    assert model.deployment_name == "gpt-5"


def test_azure_missing_env_raises(mp, monkeypatch):
    monkeypatch.setenv("SAFETRIP_MODEL_PROVIDER", "azure")
    with pytest.raises(RuntimeError, match="AZURE_OPENAI"):
        mp.build_model("gpt-5")


def test_unsupported_provider_raises(mp, monkeypatch):
    monkeypatch.setenv("SAFETRIP_MODEL_PROVIDER", "bogus")
    with pytest.raises(ValueError):
        mp.build_model("anything")
