from __future__ import annotations

import os

from langchain_openai import ChatOpenAI


def build_model():
    provider = os.getenv("SAFETRIP_MODEL_PROVIDER", "gemini").lower()
    model_name = os.getenv("SAFETRIP_MODEL")

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_api_key:
            raise RuntimeError(
                "Missing GEMINI_API_KEY. Add it to .env or export it before running."
            )
        return ChatGoogleGenerativeAI(
            model=model_name or "gemini-3-flash-preview",
            temperature=0.1,
            google_api_key=gemini_api_key,
        )

    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "Missing OPENAI_API_KEY. Add it to .env or export it before running."
            )
        return ChatOpenAI(
            model=model_name or "gpt-4.1-mini",
            temperature=0.1,
        )

    raise ValueError("Unsupported SAFETRIP_MODEL_PROVIDER. Use 'openai' or 'gemini'.")
