"""Tests for tweetmentor.config (pure logic, no network)."""

from __future__ import annotations

import pytest

from tweetmentor.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    ConfigError,
    load_llm_config,
)


def test_load_llm_config_uses_explicit_args(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    cfg = load_llm_config(api_key="explicit-key", base_url="https://example.com/v1", model="my-model")

    assert cfg.api_key == "explicit-key"
    assert cfg.base_url == "https://example.com/v1"
    assert cfg.model == "my-model"


def test_load_llm_config_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "env-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://env.example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "env-model")

    cfg = load_llm_config()

    assert cfg.api_key == "env-key"
    assert cfg.base_url == "https://env.example.com/v1"
    assert cfg.model == "env-model"


def test_load_llm_config_explicit_args_override_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "env-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://env.example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "env-model")

    cfg = load_llm_config(api_key="explicit-key", base_url="https://explicit.example.com/v1", model="explicit-model")

    assert cfg.api_key == "explicit-key"
    assert cfg.base_url == "https://explicit.example.com/v1"
    assert cfg.model == "explicit-model"


def test_load_llm_config_defaults_when_only_key_given(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    cfg = load_llm_config(api_key="explicit-key")

    assert cfg.base_url == DEFAULT_BASE_URL
    assert cfg.model == DEFAULT_MODEL


def test_load_llm_config_raises_without_any_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with pytest.raises(ConfigError):
        load_llm_config()


def test_config_error_message_mentions_llm_api_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with pytest.raises(ConfigError, match="LLM_API_KEY"):
        load_llm_config()
