"""Scrape any X (Twitter) user's profile timeline incrementally.

Scweet's built-in ``resume=True`` does NOT persist progress for
``get_profile_tweets`` across separate runs: the high-level client throws away
the pagination cursor the engine returns, and the runner never reloads a saved
checkpoint. So every plain run starts from the top of the timeline and returns
the same newest tweets again.

This module fixes that by driving the runner directly so it can read the
``resume_cursors`` the engine returns, save them to a small JSON file, and feed
them back as ``initial_cursors`` on the next run. Each run therefore continues
where the previous one stopped (older tweets, deeper into the timeline).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from Scweet import Scweet, ScweetConfig
from Scweet.models import ProfileTimelineRequest
from Scweet.user_identity import normalize_user_targets

from .config import (
    DEFAULT_DAILY_REQUESTS_LIMIT,
    DEFAULT_DAILY_TWEETS_LIMIT,
    DEFAULT_LIMIT_PER_RUN,
    DEFAULT_MAX_EMPTY_PAGES,
)


@dataclass
class ScrapeResult:
    username: str
    fetched: int
    added: int
    total: int
    limit_reached: bool
    completed: bool
    has_resume_point: bool
    output_file: Path


def _slim(tweet: dict) -> dict:
    """Keep the post date, its text, its direct link, and any quoted post text.

    ``embedded_text`` is Scweet's field for the text of a quoted/retweeted post,
    i.e. when this post tags/quotes another tweet. It is None for normal posts.
    """
    return {
        "date": tweet.get("timestamp"),
        "content": tweet.get("text"),
        "link": tweet.get("tweet_url"),
        "quoted_content": tweet.get("embedded_text"),
    }


def _load_cursors(cursor_file: Path) -> dict:
    if cursor_file.exists():
        return json.loads(cursor_file.read_text(encoding="utf-8"))
    return {}


def _save_cursors(cursor_file: Path, cursors: dict) -> None:
    cursor_file.parent.mkdir(parents=True, exist_ok=True)
    cursor_file.write_text(json.dumps(cursors, indent=2), encoding="utf-8")


def _append_tweets(output_file: Path, tweets: list[dict]) -> int:
    """Merge new posts into the output file, skipping ones already saved."""
    existing: list[dict] = []
    if output_file.exists():
        existing = json.loads(output_file.read_text(encoding="utf-8"))

    seen = {(r.get("date"), r.get("content")) for r in existing}
    added: list[dict] = []
    for t in tweets:
        record = _slim(t)
        key = (record["date"], record["content"])
        if key not in seen:
            seen.add(key)
            added.append(record)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(existing + added, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(added)


async def _scrape_async(
    username: str,
    *,
    cookies_file: Path,
    output_file: Path,
    cursor_file: Path,
    limit: int,
    max_empty_pages: int,
    daily_requests_limit: int,
    daily_tweets_limit: int,
) -> ScrapeResult:
    config = ScweetConfig(
        daily_requests_limit=daily_requests_limit,
        daily_tweets_limit=daily_tweets_limit,
    )
    s = Scweet(cookies_file=str(cookies_file), config=config)

    initial_cursors = _load_cursors(cursor_file)
    targets = normalize_user_targets(users=[username]).get("targets", [])

    request = ProfileTimelineRequest(
        targets=targets,
        limit=limit,
        max_empty_pages=max_empty_pages,
        resume=True,
        initial_cursors=initial_cursors,  # resume point from last run
    )

    response = await s._runner.run_profile_tweets(request)

    result = response.get("result")
    tweets = [s._tweet_to_dict(t) for t in (getattr(result, "tweets", None) or [])]
    resume_cursors = response.get("resume_cursors", {})

    added = _append_tweets(output_file, tweets)
    # Merge (don't clobber) so cursors for other users in the same file survive.
    merged = _load_cursors(cursor_file)
    merged.update(resume_cursors or {})
    _save_cursors(cursor_file, merged)

    total = len(json.loads(output_file.read_text(encoding="utf-8")))
    return ScrapeResult(
        username=username,
        fetched=len(tweets),
        added=added,
        total=total,
        limit_reached=bool(response.get("limit_reached", False)),
        completed=bool(response.get("completed", False)),
        has_resume_point=bool(resume_cursors),
        output_file=output_file,
    )


def scrape_user(
    username: str,
    *,
    cookies_file: str | Path = "cookies.json",
    out_dir: str | Path = "outputs",
    cursor_file: str | Path = "profile_cursors.json",
    limit: int = DEFAULT_LIMIT_PER_RUN,
    max_empty_pages: int = DEFAULT_MAX_EMPTY_PAGES,
    daily_requests_limit: int = DEFAULT_DAILY_REQUESTS_LIMIT,
    daily_tweets_limit: int = DEFAULT_DAILY_TWEETS_LIMIT,
) -> ScrapeResult:
    """Scrape one run of ``username``'s timeline, resuming from the last stop.

    Tweets accumulate (deduped) in ``<out_dir>/<username>.json``. Call repeatedly
    to walk further back through the timeline.
    """
    username = username.lstrip("@").strip()
    if not username:
        raise ValueError("username must not be empty")

    output_file = Path(out_dir) / f"{username}.json"
    return asyncio.run(
        _scrape_async(
            username,
            cookies_file=Path(cookies_file),
            output_file=output_file,
            cursor_file=Path(cursor_file),
            limit=limit,
            max_empty_pages=max_empty_pages,
            daily_requests_limit=daily_requests_limit,
            daily_tweets_limit=daily_tweets_limit,
        )
    )
