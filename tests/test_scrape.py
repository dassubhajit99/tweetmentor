"""Tests for tweetmentor.scrape's pure-logic helpers and the orchestration
of scrape_user with Scweet mocked out (no network / no real cookies file).
"""

from __future__ import annotations

import json

import pytest

from tweetmentor import scrape as scrape_mod
from tweetmentor.scrape import (
    ScrapeResult,
    _append_tweets,
    _date_range,
    _load_cursors,
    _parse_tweet_date,
    _save_cursors,
    _slim,
    scrape_user,
)


def test_slim_maps_expected_fields():
    tweet = {
        "timestamp": "2024-01-01",
        "text": "hello world",
        "tweet_url": "https://x.com/status/1",
        "embedded_text": "quoted stuff",
    }
    assert _slim(tweet) == {
        "date": "2024-01-01",
        "content": "hello world",
        "link": "https://x.com/status/1",
        "quoted_content": "quoted stuff",
    }


def test_slim_handles_missing_fields():
    assert _slim({}) == {
        "date": None,
        "content": None,
        "link": None,
        "quoted_content": None,
    }


def test_load_cursors_returns_empty_dict_when_missing(tmp_path):
    assert _load_cursors(tmp_path / "nope.json") == {}


def test_save_and_load_cursors_roundtrip(tmp_path):
    cursor_file = tmp_path / "sub" / "cursors.json"
    _save_cursors(cursor_file, {"a": "1"})
    assert cursor_file.exists()
    assert _load_cursors(cursor_file) == {"a": "1"}


def test_append_tweets_writes_new_file(tmp_path):
    output_file = tmp_path / "out" / "user.json"
    tweets = [
        {"timestamp": "t1", "text": "c1", "tweet_url": "l1", "embedded_text": None},
        {"timestamp": "t2", "text": "c2", "tweet_url": "l2", "embedded_text": None},
    ]
    added = _append_tweets(output_file, tweets)
    assert added == 2
    saved = json.loads(output_file.read_text(encoding="utf-8"))
    assert len(saved) == 2


def test_append_tweets_dedupes_against_existing(tmp_path):
    output_file = tmp_path / "user.json"
    output_file.write_text(
        json.dumps([{"date": "t1", "content": "c1", "link": "l1", "quoted_content": None}]),
        encoding="utf-8",
    )
    tweets = [
        {"timestamp": "t1", "text": "c1", "tweet_url": "l1", "embedded_text": None},  # dup
        {"timestamp": "t2", "text": "c2", "tweet_url": "l2", "embedded_text": None},  # new
    ]
    added = _append_tweets(output_file, tweets)
    assert added == 1
    saved = json.loads(output_file.read_text(encoding="utf-8"))
    assert len(saved) == 2


def test_scrape_user_rejects_empty_username():
    with pytest.raises(ValueError, match="empty"):
        scrape_user("   ")


def test_scrape_user_strips_at_symbol(tmp_path, monkeypatch):
    """scrape_user should strip a leading '@' and drive Scweet's runner directly,
    persisting results via _append_tweets / _save_cursors."""

    captured = {}

    class FakeResult:
        tweets = ["raw-tweet-1"]

    class FakeRunner:
        async def run_profile_tweets(self, request):
            captured["request"] = request
            return {
                "result": FakeResult(),
                "resume_cursors": {"cursor": "abc"},
                "limit_reached": False,
                "completed": True,
            }

    class FakeScweet:
        def __init__(self, cookies_file, config):
            captured["cookies_file"] = cookies_file
            captured["config"] = config
            self._runner = FakeRunner()

        def _tweet_to_dict(self, t):
            return {"timestamp": "d", "text": t, "tweet_url": "u", "embedded_text": None}

    monkeypatch.setattr(scrape_mod, "Scweet", FakeScweet)
    monkeypatch.setattr(scrape_mod, "ScweetConfig", lambda **kw: kw)
    monkeypatch.setattr(
        scrape_mod,
        "normalize_user_targets",
        lambda users: {"targets": users},
    )
    monkeypatch.setattr(
        scrape_mod,
        "ProfileTimelineRequest",
        lambda **kw: kw,
    )

    out_dir = tmp_path / "outputs"
    cursor_file = tmp_path / "cursors.json"

    result = scrape_user(
        "@karpathy",
        cookies_file=tmp_path / "cookies.json",
        out_dir=out_dir,
        cursor_file=cursor_file,
    )

    assert isinstance(result, ScrapeResult)
    assert result.username == "karpathy"
    assert result.fetched == 1
    assert result.added == 1
    assert result.total == 1
    assert result.completed is True
    assert result.has_resume_point is True
    assert result.output_file == out_dir / "karpathy.json"
    assert captured["request"]["targets"] == ["karpathy"]
    assert json.loads(cursor_file.read_text(encoding="utf-8")) == {"cursor": "abc"}


# -- date range reporting -------------------------------------------------------


def test_parse_tweet_date_parses_twitter_classic_format():
    dt = _parse_tweet_date("Wed Oct 10 20:19:24 +0000 2018")
    assert dt is not None
    assert (dt.year, dt.month, dt.day) == (2018, 10, 10)


def test_parse_tweet_date_returns_none_for_missing_or_bad_input():
    assert _parse_tweet_date(None) is None
    assert _parse_tweet_date("") is None
    assert _parse_tweet_date("not-a-date") is None


def test_date_range_returns_oldest_and_newest():
    records = [
        {"date": "Wed Jan 03 10:00:00 +0000 2024"},
        {"date": "Mon Jan 01 10:00:00 +0000 2024"},
        {"date": "Tue Jan 02 10:00:00 +0000 2024"},
        {"date": "not-a-date"},
        {"date": None},
    ]
    assert _date_range(records) == ("2024-01-01", "2024-01-03")


def test_date_range_returns_none_none_when_nothing_parses():
    assert _date_range([{"date": "garbage"}, {"date": None}]) == (None, None)
    assert _date_range([]) == (None, None)


def test_scrape_user_reports_date_range(tmp_path, monkeypatch):
    """scrape_user should surface the oldest/newest date across everything
    saved so far, so repeated runs can show the user how far back they've
    walked."""

    class FakeResult:
        tweets = ["raw-1", "raw-2"]

    class FakeRunner:
        async def run_profile_tweets(self, request):
            return {
                "result": FakeResult(),
                "resume_cursors": {"cursor": "abc"},
                "limit_reached": False,
                "completed": False,
            }

    dates = iter(
        ["Wed Jan 03 10:00:00 +0000 2024", "Mon Jan 01 10:00:00 +0000 2024"]
    )

    class FakeScweet:
        def __init__(self, cookies_file, config):
            self._runner = FakeRunner()

        def _tweet_to_dict(self, t):
            return {
                "timestamp": next(dates),
                "text": t,
                "tweet_url": "u",
                "embedded_text": None,
            }

    monkeypatch.setattr(scrape_mod, "Scweet", FakeScweet)
    monkeypatch.setattr(scrape_mod, "ScweetConfig", lambda **kw: kw)
    monkeypatch.setattr(scrape_mod, "normalize_user_targets", lambda users: {"targets": users})
    monkeypatch.setattr(scrape_mod, "ProfileTimelineRequest", lambda **kw: kw)

    out_dir = tmp_path / "outputs"
    result = scrape_user(
        "karpathy",
        cookies_file=tmp_path / "cookies.json",
        out_dir=out_dir,
        cursor_file=tmp_path / "cursors.json",
    )

    assert result.oldest_date == "2024-01-01"
    assert result.newest_date == "2024-01-03"
