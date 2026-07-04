"""Tests for tweetmentor.analyze with the OpenAI client mocked out."""

from __future__ import annotations

import json

import pytest

from tweetmentor import analyze as analyze_mod
from tweetmentor.analyze import (
    AnalysisError,
    _extract_json,
    _format_tweet,
    analyze_tweets,
    load_tweets,
)
from tweetmentor.config import LLMConfig
from tweetmentor.themes import Theme


# -- pure helpers -------------------------------------------------------------


def test_load_tweets_raises_when_file_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_tweets(tmp_path / "nope.json")


def test_load_tweets_sorts_oldest_first(tmp_path):
    path = tmp_path / "tweets.json"
    path.write_text(
        json.dumps(
            [
                {"date": "Wed Jan 03 10:00:00 +0000 2024", "content": "newer"},
                {"date": "Mon Jan 01 10:00:00 +0000 2024", "content": "oldest"},
                {"date": "Tue Jan 02 10:00:00 +0000 2024", "content": "middle"},
            ]
        ),
        encoding="utf-8",
    )
    tweets = load_tweets(path)
    assert [t["content"] for t in tweets] == ["oldest", "middle", "newer"]


def test_load_tweets_tolerates_unparseable_dates(tmp_path):
    path = tmp_path / "tweets.json"
    path.write_text(
        json.dumps([{"date": "not-a-date", "content": "x"}]),
        encoding="utf-8",
    )
    # Should not raise; unparseable dates just sort as the minimum.
    tweets = load_tweets(path)
    assert len(tweets) == 1


def test_format_tweet_includes_date_and_content():
    line = _format_tweet({"date": "d1", "content": " hello "})
    assert line == "[d1] hello"


def test_format_tweet_includes_quoted_content_and_link():
    line = _format_tweet(
        {"date": "d1", "content": "c1", "quoted_content": " quoted ", "link": "https://x.com/1"}
    )
    assert "↳ (quoting) quoted" in line
    assert "link: https://x.com/1" in line


def test_format_tweet_handles_missing_date_and_content():
    assert _format_tweet({}) == "[?] "


def test_extract_json_plain_array():
    assert _extract_json('[{"a": 1}]') == [{"a": 1}]


def test_extract_json_strips_markdown_fences():
    text = "```json\n[{\"a\": 1}]\n```"
    assert _extract_json(text) == [{"a": 1}]


def test_extract_json_object():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_returns_none_when_no_json_present():
    assert _extract_json("just some prose, no json here") is None


def test_extract_json_returns_none_on_malformed_json():
    assert _extract_json("[1, 2,") is None


# -- analyze_tweets pipeline (OpenAI client mocked) ---------------------------


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeChatCompletions:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def create(self, **kwargs):
        content = self._responses.pop(0)
        return _FakeCompletion(content)


class _FakeChat:
    def __init__(self, responses: list[str]):
        self.completions = _FakeChatCompletions(responses)


class _FakeOpenAIClient:
    def __init__(self, responses: list[str]):
        self.chat = _FakeChat(responses)


def _install_fake_openai(monkeypatch, responses: list[str]):
    client = _FakeOpenAIClient(responses)
    monkeypatch.setattr(analyze_mod, "OpenAI", lambda base_url, api_key: client)
    return client


def _write_tweets(tmp_path, n=3):
    path = tmp_path / "karpathy.json"
    path.write_text(
        json.dumps(
            [
                {
                    "date": f"Mon Jan 0{i+1} 10:00:00 +0000 2024",
                    "content": f"tweet {i}",
                    "link": f"https://x.com/status/{i}",
                    "quoted_content": None,
                }
                for i in range(n)
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_analyze_tweets_full_pipeline(tmp_path, monkeypatch):
    tweets_path = _write_tweets(tmp_path, n=2)
    map_response = json.dumps(
        [{"theme": "learning", "insight": "reads a lot", "link": "https://x.com/status/0"}]
    )
    reduce_response = json.dumps(
        {
            "summary": "A great learner.",
            "themes": [{"id": "learning", "title": "Learning", "patterns": []}],
            "action_plan": [],
        }
    )
    _install_fake_openai(monkeypatch, [map_response, reduce_response])

    cfg = LLMConfig(api_key="k", base_url="https://example.com/v1", model="m")
    themes = [Theme(id="learning", desc="desc", title="Learning")]
    logs = []

    guide = analyze_tweets(
        tweets_path,
        cfg,
        person="@karpathy",
        themes=themes,
        batch_size=10,
        log=logs.append,
    )

    assert guide["summary"] == "A great learner."
    assert guide["_person"] == "@karpathy"
    assert any("Loaded 2 tweets" in line for line in logs)
    assert any("MAP batch" in line for line in logs)
    assert any("REDUCE" in line for line in logs)


def test_analyze_tweets_raises_when_no_observations(tmp_path, monkeypatch):
    tweets_path = _write_tweets(tmp_path, n=1)
    _install_fake_openai(monkeypatch, [json.dumps([])])

    cfg = LLMConfig(api_key="k", base_url="https://example.com/v1", model="m")

    with pytest.raises(AnalysisError, match="No relevant observations"):
        analyze_tweets(tweets_path, cfg, batch_size=10)


def test_analyze_tweets_raises_when_reduce_step_unparseable(tmp_path, monkeypatch):
    tweets_path = _write_tweets(tmp_path, n=1)
    map_response = json.dumps(
        [{"theme": "learning", "insight": "x", "link": None}]
    )
    _install_fake_openai(monkeypatch, [map_response, "not json at all"])

    cfg = LLMConfig(api_key="k", base_url="https://example.com/v1", model="m")
    themes = [Theme(id="learning", desc="desc", title="Learning")]

    with pytest.raises(AnalysisError, match="Could not parse"):
        analyze_tweets(tweets_path, cfg, themes=themes, batch_size=10)


def test_analyze_tweets_defaults_person_to_file_stem(tmp_path, monkeypatch):
    tweets_path = _write_tweets(tmp_path, n=1)
    map_response = json.dumps([{"theme": "learning", "insight": "x", "link": None}])
    reduce_response = json.dumps({"summary": "s", "themes": [], "action_plan": []})
    _install_fake_openai(monkeypatch, [map_response, reduce_response])

    cfg = LLMConfig(api_key="k", base_url="https://example.com/v1", model="m")
    themes = [Theme(id="learning", desc="desc", title="Learning")]

    guide = analyze_tweets(tweets_path, cfg, themes=themes, batch_size=10)

    assert guide["_person"] == "@karpathy"


def test_analyze_tweets_batches_according_to_batch_size(tmp_path, monkeypatch):
    tweets_path = _write_tweets(tmp_path, n=5)
    # 5 tweets, batch_size=2 -> 3 MAP calls + 1 REDUCE call = 4 responses.
    map_response = json.dumps([{"theme": "learning", "insight": "x", "link": None}])
    reduce_response = json.dumps({"summary": "s", "themes": [], "action_plan": []})
    client = _install_fake_openai(
        monkeypatch, [map_response, map_response, map_response, reduce_response]
    )

    cfg = LLMConfig(api_key="k", base_url="https://example.com/v1", model="m")
    themes = [Theme(id="learning", desc="desc", title="Learning")]

    analyze_tweets(tweets_path, cfg, themes=themes, batch_size=2)

    assert client.chat.completions._responses == []
