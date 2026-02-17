"""
LLM client configuration via OpenRouter.
OpenRouter provides a unified API compatible with OpenAI's interface.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """Get configured LLM instance via OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is required")

    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=0.3,
        max_tokens=4096,
    )
