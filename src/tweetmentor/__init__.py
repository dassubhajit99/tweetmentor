"""tweetmentor — scrape an X account and turn its posts into a study guide.

Public API:
    scrape_user       -- incrementally scrape a user's timeline
    analyze_tweets    -- run the map-reduce LLM analysis over scraped tweets
    render_html       -- render a study-guide dict to a self-contained HTML page
    json_to_csv       -- flatten a JSON file into CSV
"""

from .analyze import analyze_tweets
from .export import json_to_csv
from .render import render_html
from .scrape import scrape_user

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "scrape_user",
    "analyze_tweets",
    "render_html",
    "json_to_csv",
]
