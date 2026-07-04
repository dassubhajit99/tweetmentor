"""Tests for tweetmentor.cli: argument parsing and command orchestration,
with the scrape/analyze/export engines mocked out.
"""

from __future__ import annotations

import json

import pytest

from tweetmentor import cli as cli_mod
from tweetmentor.analyze import AnalysisError
from tweetmentor.config import ConfigError, LLMConfig
from tweetmentor.scrape import ScrapeResult
from tweetmentor.themes import ThemesError


# -- argument parsing ---------------------------------------------------------


def test_build_parser_requires_a_subcommand(capsys):
    parser = cli_mod.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_build_parser_version(capsys):
    parser = cli_mod.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--version"])


def test_build_parser_scrape_defaults():
    parser = cli_mod.build_parser()
    args = parser.parse_args(["scrape", "karpathy"])
    assert args.username == "karpathy"
    assert args.cookies == "cookies.json"
    assert args.out_dir == "outputs"
    assert args.func is cli_mod._cmd_scrape


def test_build_parser_analyze_defaults():
    parser = cli_mod.build_parser()
    args = parser.parse_args(["analyze", "outputs/karpathy.json"])
    assert args.tweets == "outputs/karpathy.json"
    assert args.out == "study_guide.html"
    assert args.batch_size == 60
    assert args.func is cli_mod._cmd_analyze


def test_build_parser_export_defaults():
    parser = cli_mod.build_parser()
    args = parser.parse_args(["export", "data.json"])
    assert args.input == "data.json"
    assert args.output is None
    assert args.func is cli_mod._cmd_export


# -- _cmd_scrape ---------------------------------------------------------------


def test_cmd_scrape_returns_error_when_cookies_missing(tmp_path, capsys):
    parser = cli_mod.build_parser()
    args = parser.parse_args(
        ["scrape", "karpathy", "--cookies", str(tmp_path / "missing.json")]
    )
    rc = cli_mod._cmd_scrape(args)
    assert rc == 2
    assert "cookies file not found" in capsys.readouterr().err


def test_cmd_scrape_success_path(tmp_path, monkeypatch, capsys):
    cookies = tmp_path / "cookies.json"
    cookies.write_text("{}", encoding="utf-8")

    result = ScrapeResult(
        username="karpathy",
        fetched=5,
        added=5,
        total=10,
        limit_reached=False,
        completed=True,
        has_resume_point=True,
        output_file=tmp_path / "outputs" / "karpathy.json",
    )
    monkeypatch.setattr(cli_mod, "scrape_user", lambda *a, **kw: result)

    parser = cli_mod.build_parser()
    args = parser.parse_args(["scrape", "karpathy", "--cookies", str(cookies)])
    rc = cli_mod._cmd_scrape(args)

    out = capsys.readouterr().out
    assert rc == 0
    assert "Fetched 5 tweets this run (5 new)." in out
    assert "Total saved: 10" in out
    assert "Saved resume point" in out


def test_cmd_scrape_reports_bottom_of_timeline_when_no_resume_and_some_fetched(
    tmp_path, monkeypatch, capsys
):
    cookies = tmp_path / "cookies.json"
    cookies.write_text("{}", encoding="utf-8")

    result = ScrapeResult(
        username="karpathy",
        fetched=3,
        added=1,
        total=10,
        limit_reached=False,
        completed=True,
        has_resume_point=False,
        output_file=tmp_path / "karpathy.json",
    )
    monkeypatch.setattr(cli_mod, "scrape_user", lambda *a, **kw: result)

    parser = cli_mod.build_parser()
    args = parser.parse_args(["scrape", "karpathy", "--cookies", str(cookies)])
    rc = cli_mod._cmd_scrape(args)

    out = capsys.readouterr().out
    assert rc == 0
    assert "reached the bottom of the timeline" in out


def test_cmd_scrape_reports_quota_hit_when_nothing_fetched(tmp_path, monkeypatch, capsys):
    cookies = tmp_path / "cookies.json"
    cookies.write_text("{}", encoding="utf-8")

    result = ScrapeResult(
        username="karpathy",
        fetched=0,
        added=0,
        total=10,
        limit_reached=False,
        completed=False,
        has_resume_point=False,
        output_file=tmp_path / "karpathy.json",
    )
    monkeypatch.setattr(cli_mod, "scrape_user", lambda *a, **kw: result)

    parser = cli_mod.build_parser()
    args = parser.parse_args(["scrape", "karpathy", "--cookies", str(cookies)])
    rc = cli_mod._cmd_scrape(args)

    out = capsys.readouterr().out
    assert rc == 0
    assert "daily account quota hit" in out


# -- _cmd_analyze ---------------------------------------------------------------


def test_cmd_analyze_returns_error_when_config_invalid(tmp_path, monkeypatch, capsys):
    def raise_config_error(**kwargs):
        raise ConfigError("no key")

    monkeypatch.setattr(cli_mod, "load_llm_config", raise_config_error)

    parser = cli_mod.build_parser()
    args = parser.parse_args(["analyze", str(tmp_path / "tweets.json")])
    rc = cli_mod._cmd_analyze(args)

    assert rc == 2
    assert "no key" in capsys.readouterr().err


def test_cmd_analyze_returns_error_when_themes_invalid(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cli_mod, "load_llm_config", lambda **kw: LLMConfig(api_key="k", base_url="b", model="m")
    )

    def raise_themes_error(path):
        raise ThemesError("bad themes")

    monkeypatch.setattr(cli_mod, "load_themes", raise_themes_error)

    parser = cli_mod.build_parser()
    args = parser.parse_args(["analyze", str(tmp_path / "tweets.json")])
    rc = cli_mod._cmd_analyze(args)

    assert rc == 2
    assert "bad themes" in capsys.readouterr().err


def test_cmd_analyze_returns_error_when_analysis_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cli_mod, "load_llm_config", lambda **kw: LLMConfig(api_key="k", base_url="b", model="m")
    )
    monkeypatch.setattr(cli_mod, "load_themes", lambda path: [])

    def raise_analysis_error(*a, **kw):
        raise AnalysisError("no observations")

    monkeypatch.setattr(cli_mod, "analyze_tweets", raise_analysis_error)

    parser = cli_mod.build_parser()
    args = parser.parse_args(["analyze", str(tmp_path / "tweets.json")])
    rc = cli_mod._cmd_analyze(args)

    assert rc == 1
    assert "no observations" in capsys.readouterr().err


def test_cmd_analyze_writes_html_and_json_on_success(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cli_mod, "load_llm_config", lambda **kw: LLMConfig(api_key="k", base_url="b", model="m")
    )
    monkeypatch.setattr(cli_mod, "load_themes", lambda path: [])
    monkeypatch.setattr(
        cli_mod,
        "analyze_tweets",
        lambda *a, **kw: {"summary": "s", "themes": [], "action_plan": []},
    )

    out_html = tmp_path / "guide.html"
    parser = cli_mod.build_parser()
    args = parser.parse_args(
        ["analyze", str(tmp_path / "karpathy.json"), "-o", str(out_html)]
    )
    rc = cli_mod._cmd_analyze(args)

    assert rc == 0
    assert out_html.exists()
    json_out = out_html.with_suffix(".json")
    assert json_out.exists()
    assert json.loads(json_out.read_text(encoding="utf-8"))["summary"] == "s"
    assert "Done. Study guide" in capsys.readouterr().out


def test_cmd_analyze_defaults_person_from_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(
        cli_mod, "load_llm_config", lambda **kw: LLMConfig(api_key="k", base_url="b", model="m")
    )
    monkeypatch.setattr(cli_mod, "load_themes", lambda path: [])

    captured = {}

    def fake_analyze(tweets_file, cfg, *, person, themes, batch_size, log):
        captured["person"] = person
        return {"summary": "s", "themes": [], "action_plan": []}

    monkeypatch.setattr(cli_mod, "analyze_tweets", fake_analyze)

    parser = cli_mod.build_parser()
    args = parser.parse_args(
        ["analyze", str(tmp_path / "karpathy.json"), "-o", str(tmp_path / "g.html")]
    )
    cli_mod._cmd_analyze(args)

    assert captured["person"] == "@karpathy"


# -- _cmd_export ---------------------------------------------------------------


def test_cmd_export_success(tmp_path, monkeypatch, capsys):
    out_path = tmp_path / "out.csv"
    monkeypatch.setattr(cli_mod, "json_to_csv", lambda inp, outp: out_path)

    parser = cli_mod.build_parser()
    args = parser.parse_args(["export", str(tmp_path / "in.json")])
    rc = cli_mod._cmd_export(args)

    assert rc == 0
    assert f"Wrote {out_path}" in capsys.readouterr().out


def test_cmd_export_returns_error_on_failure(tmp_path, monkeypatch, capsys):
    def raise_error(inp, outp):
        raise FileNotFoundError("nope")

    monkeypatch.setattr(cli_mod, "json_to_csv", raise_error)

    parser = cli_mod.build_parser()
    args = parser.parse_args(["export", str(tmp_path / "in.json")])
    rc = cli_mod._cmd_export(args)

    assert rc == 1
    assert "nope" in capsys.readouterr().err


# -- main() dispatch ------------------------------------------------------------


def test_main_dispatches_to_export(tmp_path, monkeypatch, capsys):
    out_path = tmp_path / "out.csv"
    monkeypatch.setattr(cli_mod, "json_to_csv", lambda inp, outp: out_path)

    rc = cli_mod.main(["export", str(tmp_path / "in.json")])

    assert rc == 0
