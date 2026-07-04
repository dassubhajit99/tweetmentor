"""Themes drive what the analysis looks for and how the study guide is titled.

A theme has:
    id     -- short machine key the model must tag observations with
    desc   -- what the model should look for under this theme
    title  -- human-facing heading used in the rendered HTML (may include an emoji)

The defaults below describe "how someone grew as a developer", but you can pass
your own themes file (JSON) via ``--themes`` to analyze any account for any set
of topics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Theme:
    id: str
    desc: str
    title: str


DEFAULT_THEMES: list[Theme] = [
    Theme(
        id="learning",
        desc="How they learn coding concepts (resources, habits, study methods, what they read/build to learn)",
        title="🧠 How they learn coding concepts",
    ),
    Theme(
        id="backend",
        desc="How they became a strong backend developer (tech stack, projects, systems concepts, practice)",
        title="⚙️ Becoming a strong backend developer",
    ),
    Theme(
        id="ai",
        desc="How they became an AI application engineer (models, tools, projects, what they studied)",
        title="🤖 Becoming an AI application engineer",
    ),
    Theme(
        id="freelancing",
        desc="How they get freelance clients & contracts (outreach, positioning, portfolio, networking, pricing)",
        title="💼 Getting freelance clients & contracts",
    ),
]


class ThemesError(ValueError):
    """Raised when a themes file is malformed."""


def load_themes(path: str | Path | None) -> list[Theme]:
    """Return the default themes, or load a JSON override from ``path``.

    Expected JSON shape (a list of objects)::

        [
          {"id": "learning", "desc": "what to look for", "title": "🧠 Heading"},
          ...
        ]

    ``title`` is optional and falls back to the id.
    """
    if not path:
        return DEFAULT_THEMES

    p = Path(path)
    if not p.exists():
        raise ThemesError(f"Themes file not found: {p}")

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ThemesError(f"Themes file is not valid JSON: {exc}") from exc

    if not isinstance(raw, list) or not raw:
        raise ThemesError("Themes file must be a non-empty JSON array of objects.")

    themes: list[Theme] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or "id" not in item or "desc" not in item:
            raise ThemesError(
                f"Theme #{i} must be an object with at least 'id' and 'desc'."
            )
        tid = str(item["id"]).strip()
        themes.append(
            Theme(
                id=tid,
                desc=str(item["desc"]).strip(),
                title=str(item.get("title") or tid).strip(),
            )
        )

    ids = [t.id for t in themes]
    if len(set(ids)) != len(ids):
        raise ThemesError("Theme ids must be unique.")
    return themes
