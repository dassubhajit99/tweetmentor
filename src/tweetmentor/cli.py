"""Command-line interface for tweetmentor.

Subcommands:
    scrape    Scrape an X user's timeline (resumes deeper on each run).
    analyze   Turn scraped tweets into a study-guide HTML with an LLM.
    export    Flatten any JSON file into CSV.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .analyze import AnalysisError, analyze_tweets
from .config import (
    DEFAULT_DAILY_REQUESTS_LIMIT,
    DEFAULT_DAILY_TWEETS_LIMIT,
    DEFAULT_LIMIT_PER_RUN,
    DEFAULT_MAX_EMPTY_PAGES,
    ConfigError,
    load_llm_config,
)
from .export import json_to_csv
from .render import render_html
from .scrape import scrape_user
from .themes import ThemesError, load_themes


def _cmd_scrape(args: argparse.Namespace) -> int:
    if not Path(args.cookies).exists():
        print(
            f"error: cookies file not found: {args.cookies}\n"
            "Export your X session cookies to this file first (see the README).",
            file=sys.stderr,
        )
        return 2
    res = scrape_user(
        args.username,
        cookies_file=args.cookies,
        out_dir=args.out_dir,
        cursor_file=args.cursor_file,
        limit=args.limit,
        max_empty_pages=args.max_empty_pages,
        daily_requests_limit=args.daily_requests_limit,
        daily_tweets_limit=args.daily_tweets_limit,
    )
    print(f"Fetched {res.fetched} tweets this run ({res.added} new).")
    print(f"Total saved: {res.total} -> {res.output_file}")
    print(f"limit_reached={res.limit_reached} completed={res.completed}")
    if res.has_resume_point:
        print(f"Saved resume point -> next run continues deeper ({args.cursor_file}).")
    elif res.fetched:
        print("No resume cursor returned: reached the bottom of the timeline.")
    else:
        print(
            "Got 0 tweets and no cursor. Likely causes: daily account quota hit "
            "(raise --daily-* limits or wait for the daily reset), expired cookies, "
            "or the timeline is genuinely exhausted."
        )
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    try:
        cfg = load_llm_config(model=args.model, base_url=args.base_url, api_key=args.api_key)
        themes = load_themes(args.themes)
    except (ConfigError, ThemesError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    person = args.person or ("@" + Path(args.tweets).stem)
    try:
        guide = analyze_tweets(
            args.tweets,
            cfg,
            person=person,
            themes=themes,
            batch_size=args.batch_size,
        )
    except (AnalysisError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    html_out = Path(args.out)
    json_out = html_out.with_suffix(".json")
    html_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(guide, ensure_ascii=False, indent=2), encoding="utf-8")
    html_out.write_text(render_html(guide, person=person, themes=themes), encoding="utf-8")
    print(f"\nDone. Study guide: {html_out.resolve()}")
    print(f"Structured data:   {json_out.resolve()}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    try:
        out = json_to_csv(args.input, args.output)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tweetmentor",
        description="Scrape an X (Twitter) account and turn its posts into a study guide.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    # scrape
    sp = sub.add_parser("scrape", help="Scrape an X user's timeline (resumes on each run).")
    sp.add_argument("username", help="X handle to scrape, e.g. karpathy (@ optional).")
    sp.add_argument("--cookies", default="cookies.json", help="Path to X session cookies JSON.")
    sp.add_argument("--out-dir", default="outputs", help="Directory for <username>.json output.")
    sp.add_argument("--cursor-file", default="profile_cursors.json", help="Resume-cursor store.")
    sp.add_argument("--limit", type=int, default=DEFAULT_LIMIT_PER_RUN, help="Tweets to fetch per run.")
    sp.add_argument("--max-empty-pages", type=int, default=DEFAULT_MAX_EMPTY_PAGES)
    sp.add_argument("--daily-requests-limit", type=int, default=DEFAULT_DAILY_REQUESTS_LIMIT)
    sp.add_argument("--daily-tweets-limit", type=int, default=DEFAULT_DAILY_TWEETS_LIMIT)
    sp.set_defaults(func=_cmd_scrape)

    # analyze
    ap = sub.add_parser("analyze", help="Turn scraped tweets into a study-guide HTML.")
    ap.add_argument("tweets", help="Path to a scraped tweets JSON file.")
    ap.add_argument("-o", "--out", default="study_guide.html", help="Output HTML path.")
    ap.add_argument("--person", help="Label for the subject (default: @<filename>).")
    ap.add_argument("--themes", help="Path to a JSON themes file (default: built-in dev themes).")
    ap.add_argument("--model", help="Model id (default: $LLM_MODEL or built-in default).")
    ap.add_argument("--base-url", help="OpenAI-compatible base URL (default: $LLM_BASE_URL).")
    ap.add_argument("--api-key", help="API key (default: $LLM_API_KEY). Avoid on shared machines.")
    ap.add_argument("--batch-size", type=int, default=60, help="Tweets per MAP call.")
    ap.set_defaults(func=_cmd_analyze)

    # export
    ep = sub.add_parser("export", help="Flatten a JSON file into CSV.")
    ep.add_argument("input", help="Input JSON file.")
    ep.add_argument("output", nargs="?", help="Output CSV file (default: input with .csv).")
    ep.set_defaults(func=_cmd_export)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
