"""Tests for tweetmentor.render (pure string-building logic)."""

from __future__ import annotations

from tweetmentor.render import render_html
from tweetmentor.themes import Theme


def test_render_html_includes_person_name():
    html = render_html({}, person="karpathy")
    assert "karpathy" in html
    assert "<!doctype html>" in html


def test_render_html_falls_back_to_person_in_guide():
    html = render_html({"_person": "someone"})
    assert "someone" in html


def test_render_html_falls_back_to_default_person_text():
    html = render_html({})
    assert "this account" in html


def test_render_html_escapes_html_in_person_name():
    html = render_html({}, person="<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_html_escapes_summary():
    guide = {"summary": "<b>bold</b> & stuff"}
    html = render_html(guide)
    assert "<b>bold</b>" not in html
    assert "&lt;b&gt;bold&lt;/b&gt;" in html


def test_render_html_renders_theme_sections_with_patterns():
    guide = {
        "themes": [
            {
                "id": "learning",
                "patterns": [
                    {
                        "point": "Reads source code",
                        "detail": "Often links to GitHub repos",
                        "examples": ["https://x.com/example/status/1"],
                    }
                ],
            }
        ]
    }
    html = render_html(guide)
    assert "Reads source code" in html
    assert "Often links to GitHub repos" in html
    assert 'href="https://x.com/example/status/1"' in html
    assert "source</a>" in html


def test_render_html_theme_title_prefers_model_title_then_config_then_id():
    themes = [Theme(id="learning", desc="d", title="Configured Title")]

    guide_with_model_title = {"themes": [{"id": "learning", "title": "Model Title", "patterns": []}]}
    html = render_html(guide_with_model_title, themes=themes)
    assert "Model Title" in html

    guide_without_model_title = {"themes": [{"id": "learning", "patterns": []}]}
    html = render_html(guide_without_model_title, themes=themes)
    assert "Configured Title" in html

    guide_unknown_id = {"themes": [{"id": "unknown", "patterns": []}]}
    html = render_html(guide_unknown_id, themes=themes)
    assert ">unknown<" in html


def test_render_html_shows_no_data_when_theme_has_no_patterns():
    guide = {"themes": [{"id": "learning", "patterns": []}]}
    html = render_html(guide)
    assert "No data." in html


def test_render_html_renders_action_plan_steps():
    guide = {
        "action_plan": [
            {"step": "Build a project", "why": "It reinforces learning", "based_on": ["https://x.com/status/2"]}
        ]
    }
    html = render_html(guide)
    assert "Build a project" in html
    assert "It reinforces learning" in html
    assert 'href="https://x.com/status/2"' in html


def test_render_html_shows_no_steps_when_action_plan_empty():
    html = render_html({"action_plan": []})
    assert "No steps." in html


def test_links_html_ignores_non_http_and_empty_links():
    guide = {
        "themes": [
            {
                "id": "learning",
                "patterns": [
                    {
                        "point": "p",
                        "detail": "d",
                        "examples": ["not-a-url", "", None, "https://ok.example.com"],
                    }
                ],
            }
        ]
    }
    html = render_html(guide)
    assert 'href="not-a-url"' not in html
    assert 'href="https://ok.example.com"' in html
