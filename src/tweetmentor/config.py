"""Runtime configuration for the LLM (OpenAI-compatible) and scraping defaults.

All secrets come from the environment (or a local ``.env`` file, which is loaded
automatically). Nothing sensitive is ever hardcoded here.

Environment variables:
    LLM_API_KEY   -- API key for your OpenAI-compatible endpoint (required to analyze)
    LLM_BASE_URL  -- base URL of the endpoint (default: NVIDIA integrate API)
    LLM_MODEL     -- model id to use (default below; make sure it's valid for your key)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load a local .env if present. Real environment variables take precedence.
load_dotenv(override=False)

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "z-ai/glm-5.1"

# Conservative scraping defaults. Scweet caps how much each account may scrape
# per day to avoid X flagging it. Raising these increases the risk of your
# account being rate-limited or suspended. Limits reset daily (tracked in the
# Scweet state DB).
DEFAULT_DAILY_REQUESTS_LIMIT = 150
DEFAULT_DAILY_TWEETS_LIMIT = 4000
DEFAULT_LIMIT_PER_RUN = 500
DEFAULT_MAX_EMPTY_PAGES = 2


class ConfigError(RuntimeError):
    """Raised when required configuration (e.g. the API key) is missing."""


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str


def load_llm_config(
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> LLMConfig:
    """Build the LLM config, preferring explicit args over environment values.

    Raises ConfigError if no API key can be found, with actionable guidance.
    """
    resolved_key = api_key or os.getenv("LLM_API_KEY")
    if not resolved_key:
        raise ConfigError(
            "No LLM API key found. Set LLM_API_KEY in your environment or a .env "
            "file (see .env.example), or pass --api-key. Never hardcode keys."
        )
    return LLMConfig(
        api_key=resolved_key,
        base_url=base_url or os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL,
        model=model or os.getenv("LLM_MODEL") or DEFAULT_MODEL,
    )
