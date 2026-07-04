"""Render a study-guide dict into a single self-contained HTML page."""

from __future__ import annotations

import html as _html
from datetime import datetime

from .themes import DEFAULT_THEMES, Theme


def _esc(x) -> str:
    return _html.escape(str(x or ""))


def _links_html(links) -> str:
    items = []
    for l in links or []:
        if l and str(l).startswith("http"):
            items.append(f'<a href="{_esc(l)}" target="_blank" rel="noopener">source</a>')
    return " · ".join(items)


def render_html(guide: dict, *, person: str | None = None, themes: list[Theme] | None = None) -> str:
    """Return a full HTML document string for the given study guide.

    Theme headings prefer the title the model produced; otherwise they fall back
    to the configured theme titles, then the raw id.
    """
    themes = themes or DEFAULT_THEMES
    person = person or guide.get("_person") or "this account"
    title_by_id = {t.id: t.title for t in themes}

    sections = []
    for theme in guide.get("themes", []):
        tid = theme.get("id")
        title = _esc(theme.get("title")) or _esc(title_by_id.get(tid, tid))
        patterns = []
        for p in theme.get("patterns", []):
            patterns.append(
                f'<div class="pattern"><h3>{_esc(p.get("point"))}</h3>'
                f'<p>{_esc(p.get("detail"))}</p>'
                f'<div class="links">{_links_html(p.get("examples"))}</div></div>'
            )
        sections.append(
            f'<section class="theme"><h2>{title}</h2>'
            f'{"".join(patterns) or "<p>No data.</p>"}</section>'
        )

    steps = []
    for s in guide.get("action_plan", []):
        steps.append(
            f'<li><label><input type="checkbox"> <strong>{_esc(s.get("step"))}</strong></label>'
            f'<p>{_esc(s.get("why"))}</p><div class="links">{_links_html(s.get("based_on"))}</div></li>'
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Study Guide — learning from {_esc(person)}</title>
<style>
  :root {{ --bg:#0f1117; --card:#1a1d28; --acc:#6ea8fe; --txt:#e7e9ee; --mut:#9aa1b1; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--txt); font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif; }}
  .wrap {{ max-width:880px; margin:0 auto; padding:40px 20px 80px; }}
  h1 {{ font-size:28px; margin:0 0 8px; }}
  .sub {{ color:var(--mut); margin-bottom:28px; }}
  .summary {{ background:var(--card); border-left:4px solid var(--acc); padding:16px 20px; border-radius:8px; margin-bottom:32px; }}
  .theme {{ margin-bottom:36px; }}
  .theme h2 {{ font-size:20px; border-bottom:1px solid #2a2e3c; padding-bottom:8px; }}
  .pattern {{ background:var(--card); border-radius:10px; padding:14px 18px; margin:12px 0; }}
  .pattern h3 {{ margin:0 0 6px; font-size:16px; color:var(--acc); }}
  .pattern p {{ margin:0 0 8px; }}
  .links a {{ color:var(--mut); font-size:13px; text-decoration:none; }}
  .links a:hover {{ color:var(--acc); }}
  ol.plan {{ list-style:none; padding:0; counter-reset:step; }}
  ol.plan li {{ background:var(--card); border-radius:10px; padding:14px 18px; margin:10px 0; }}
  ol.plan p {{ margin:6px 0; color:var(--mut); }}
  input[type=checkbox] {{ transform:scale(1.2); margin-right:8px; }}
  footer {{ color:var(--mut); font-size:13px; margin-top:40px; text-align:center; }}
</style></head>
<body><div class="wrap">
  <h1>Learning from {_esc(person)}</h1>
  <div class="sub">Patterns extracted from {_esc(person)}'s tweets · generated {datetime.now():%Y-%m-%d}</div>
  <div class="summary">{_esc(guide.get("summary"))}</div>
  {"".join(sections)}
  <section class="theme"><h2>✅ Your action plan</h2><ol class="plan">{"".join(steps) or "<li>No steps.</li>"}</ol></section>
  <footer>Tick the boxes as you go. Click &ldquo;source&rdquo; to read the original tweet.</footer>
</div></body></html>"""
