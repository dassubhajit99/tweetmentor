"""Tests for tweetmentor.themes (pure logic, no network)."""

from __future__ import annotations

import json

import pytest

from tweetmentor.themes import DEFAULT_THEMES, Theme, ThemesError, load_themes


def test_load_themes_returns_defaults_when_path_is_none():
    assert load_themes(None) == DEFAULT_THEMES


def test_load_themes_returns_defaults_when_path_is_empty_string():
    assert load_themes("") == DEFAULT_THEMES


def test_load_themes_raises_when_file_missing(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises(ThemesError, match="not found"):
        load_themes(missing)


def test_load_themes_raises_on_invalid_json(tmp_path):
    bad = tmp_path / "themes.json"
    bad.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ThemesError, match="not valid JSON"):
        load_themes(bad)


@pytest.mark.parametrize("payload", ["{}", '"just a string"', "[]", "42"])
def test_load_themes_raises_when_not_a_nonempty_array(tmp_path, payload):
    path = tmp_path / "themes.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ThemesError, match="non-empty JSON array"):
        load_themes(path)


def test_load_themes_raises_when_item_missing_required_keys(tmp_path):
    path = tmp_path / "themes.json"
    path.write_text(json.dumps([{"id": "x"}]), encoding="utf-8")
    with pytest.raises(ThemesError, match="must be an object"):
        load_themes(path)


def test_load_themes_raises_when_item_is_not_an_object(tmp_path):
    path = tmp_path / "themes.json"
    path.write_text(json.dumps(["not-an-object"]), encoding="utf-8")
    with pytest.raises(ThemesError, match="must be an object"):
        load_themes(path)


def test_load_themes_raises_on_duplicate_ids(tmp_path):
    path = tmp_path / "themes.json"
    path.write_text(
        json.dumps(
            [
                {"id": "dup", "desc": "one"},
                {"id": "dup", "desc": "two"},
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ThemesError, match="unique"):
        load_themes(path)


def test_load_themes_title_falls_back_to_id(tmp_path):
    path = tmp_path / "themes.json"
    path.write_text(json.dumps([{"id": "myid", "desc": "some desc"}]), encoding="utf-8")

    themes = load_themes(path)

    assert themes == [Theme(id="myid", desc="some desc", title="myid")]


def test_load_themes_strips_whitespace_and_uses_given_title(tmp_path):
    path = tmp_path / "themes.json"
    path.write_text(
        json.dumps([{"id": "  myid  ", "desc": "  desc  ", "title": "  My Title  "}]),
        encoding="utf-8",
    )

    themes = load_themes(path)

    assert themes == [Theme(id="myid", desc="desc", title="My Title")]


def test_load_themes_accepts_path_as_string(tmp_path):
    path = tmp_path / "themes.json"
    path.write_text(json.dumps([{"id": "a", "desc": "b"}]), encoding="utf-8")

    themes = load_themes(str(path))

    assert themes[0].id == "a"


def test_default_themes_have_unique_ids():
    ids = [t.id for t in DEFAULT_THEMES]
    assert len(ids) == len(set(ids))


def test_default_themes_all_have_nonempty_fields():
    for theme in DEFAULT_THEMES:
        assert theme.id
        assert theme.desc
        assert theme.title
