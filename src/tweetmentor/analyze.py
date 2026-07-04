"""Map-reduce LLM analysis of a user's tweets into a structured study guide.

Pipeline (map-reduce, because hundreds of tweets are too big for one prompt):
  1. Load the slimmed tweets (date, content, link, quoted_content).
  2. MAP    : scan the tweets in batches; for each batch the LLM pulls out
             concrete observations tied to the configured themes.
  3. REDUCE : feed all observations back to the LLM to synthesize a structured
             study guide (patterns + an action plan) as JSON.

The rendering step lives in ``render.py``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from openai import OpenAI

from .config import LLMConfig
from .themes import DEFAULT_THEMES, Theme

Logger = Callable[[str], None]


class AnalysisError(RuntimeError):
    """Raised when the model output can't be parsed into a study guide."""


def _default_logger(msg: str) -> None:
    print(msg, flush=True)


def load_tweets(tweets_file: str | Path) -> list[dict]:
    path = Path(tweets_file)
    if not path.exists():
        raise FileNotFoundError(f"Tweet file not found: {path}")
    tweets = json.loads(path.read_text(encoding="utf-8"))

    def sort_key(t: dict):
        try:
            return datetime.strptime(t.get("date", ""), "%a %b %d %H:%M:%S %z %Y")
        except Exception:
            return datetime.min.replace(tzinfo=None)

    # Oldest first so the model sees the journey in order.
    return sorted(tweets, key=lambda t: str(sort_key(t)))


def _format_tweet(t: dict) -> str:
    line = f"[{t.get('date', '?')}] {(t.get('content') or '').strip()}"
    if t.get("quoted_content"):
        line += f"\n   ↳ (quoting) {t['quoted_content'].strip()}"
    if t.get("link"):
        line += f"\n   link: {t['link']}"
    return line


def _extract_json(text: str):
    """Pull the first JSON object/array out of a model reply (tolerates fences)."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


class _LLM:
    def __init__(self, cfg: LLMConfig):
        self._cfg = cfg
        self._client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)

    def call(self, system: str, user: str, max_tokens: int = 8192) -> str:
        resp = self._client.chat.completions.create(
            model=self._cfg.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
            top_p=0.9,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""


def _map_batch(
    llm: _LLM,
    themes: list[Theme],
    person: str,
    batch: list[dict],
    idx: int,
    total: int,
    log: Logger,
) -> list[dict]:
    theme_ids = [t.id for t in themes]
    theme_list = "\n".join(f"- {t.id}: {t.desc}" for t in themes)
    id_options = "|".join(theme_ids)
    system = (
        "You analyze a person's tweets to extract how they grew their skills and career. "
        "You only report observations that are actually supported by the tweets. Be concrete."
    )
    user = (
        f"Here are tweets from {person} (oldest first). Extract concrete observations that fit "
        f"these themes:\n{theme_list}\n\n"
        "Return ONLY a JSON array. Each item: "
        f'{{"theme": "<one of: {id_options}>", '
        '"insight": "<specific thing they did/said/learned>", '
        '"link": "<the tweet link it came from, or null>"}. '
        "Skip tweets that say nothing relevant. No prose outside the JSON.\n\n"
        "TWEETS:\n" + "\n\n".join(_format_tweet(t) for t in batch)
    )
    log(f"  MAP batch {idx}/{total} ({len(batch)} tweets)...")
    data = _extract_json(llm.call(system, user))
    if not isinstance(data, list):
        return []
    valid = set(theme_ids)
    out = []
    for item in data:
        if isinstance(item, dict) and item.get("theme") in valid and item.get("insight"):
            out.append(item)
    return out


def _reduce_observations(
    llm: _LLM,
    themes: list[Theme],
    person: str,
    observations: list[dict],
    log: Logger,
) -> dict:
    id_options = "|".join(t.id for t in themes)
    system = (
        "You are a mentor turning raw observations about a person into a focused study guide "
        "for someone who wants to follow the same path. Be specific and actionable."
    )
    user = (
        f"These observations were extracted from {person}'s tweets:\n\n"
        + json.dumps(observations, ensure_ascii=False)
        + "\n\nSynthesize them into a study guide. Return ONLY this JSON shape:\n"
        "{\n"
        '  "summary": "2-3 sentence overview of their journey and what made them effective",\n'
        '  "themes": [\n'
        f'    {{"id": "{id_options}", "title": "...",\n'
        '     "patterns": [{"point": "short pattern title", "detail": "what they did and why it works", "examples": ["tweet link", "..."]}]}\n'
        "  ],\n"
        '  "action_plan": [{"step": "concrete thing YOU should do", "why": "...", "based_on": ["tweet link"]}]\n'
        "}\n"
        "Cover every theme that has evidence. Merge duplicate observations. "
        "Use real tweet links from the observations as examples. No prose outside the JSON."
    )
    log("  REDUCE: synthesizing study guide...")
    data = _extract_json(llm.call(system, user, max_tokens=12000))
    if not isinstance(data, dict):
        raise AnalysisError(
            "Could not parse the synthesis step as JSON. Re-run, or lower batch_size."
        )
    return data


def analyze_tweets(
    tweets_file: str | Path,
    cfg: LLMConfig,
    *,
    person: str | None = None,
    themes: list[Theme] | None = None,
    batch_size: int = 60,
    log: Logger | None = None,
) -> dict:
    """Run the full map-reduce analysis and return the study-guide dict.

    ``person`` labels the subject in prompts/headings (defaults to the tweets
    file stem, e.g. ``@karpathy``). ``themes`` defaults to the built-in dev
    themes.
    """
    log = log or _default_logger
    themes = themes or DEFAULT_THEMES
    if person is None:
        person = "@" + Path(tweets_file).stem

    tweets = load_tweets(tweets_file)
    log(f"Loaded {len(tweets)} tweets from {tweets_file}")

    llm = _LLM(cfg)
    batches = [tweets[i : i + batch_size] for i in range(0, len(tweets), batch_size)]
    observations: list[dict] = []
    for i, batch in enumerate(batches, 1):
        observations.extend(_map_batch(llm, themes, person, batch, i, len(batches), log))
    log(f"Collected {len(observations)} observations.")

    if not observations:
        raise AnalysisError(
            "No relevant observations found. Check the model id / API key / themes."
        )

    guide = _reduce_observations(llm, themes, person, observations, log)
    guide.setdefault("_person", person)
    return guide
