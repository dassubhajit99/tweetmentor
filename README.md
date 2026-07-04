# tweetmentor

Scrape an X (Twitter) account's timeline and turn its posts into a personalized,
self-contained **study guide** — "how did this person grow their skills, and what
should *I* do to follow the same path?"

It works in three steps:

1. **scrape** — walk any public profile's timeline (resuming deeper on each run).
2. **analyze** — a map-reduce LLM pipeline extracts concrete patterns across your
   themes and synthesizes a study guide (patterns + a checkable action plan).
3. **export** — optionally flatten the scraped JSON into CSV.

The default themes describe *how someone became a developer* (learning, backend,
AI, freelancing), but you can point it at **any account** and supply **your own
themes** for any topic.

> ⚠️ **Use responsibly.** Scraping X may violate its Terms of Service and can get
> your account rate-limited or suspended. Only scrape public data, go slow, and
> use an account you're willing to risk. You are responsible for how you use this.

---

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/dassubhajit99/tweetmentor.git
cd tweetmentor
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

This installs the `tweetmentor` command.

## Configure

The **analyze** step talks to any OpenAI-compatible endpoint (NVIDIA, OpenAI,
Groq, …). Copy the example env file and fill in your key:

```bash
cp .env.example .env
# then edit .env: LLM_API_KEY (required), LLM_BASE_URL and LLM_MODEL (optional)
```

Secrets are read from the environment or `.env` — **never hardcode API keys**.

### X session cookies (for scraping)

Scraping authenticates as you, using your X session's `auth_token` cookie.

**1. Log into your account** at [x.com](https://x.com) in a browser.

**2. Get your `auth_token`:**

- Open DevTools (`F12`, or right-click → Inspect).
- Go to the **Application** tab (in Firefox: **Storage**).
- In the left sidebar, expand **Cookies** → click `https://x.com`.
- Find the row named **`auth_token`** and copy its **Value**.

**3. Put it in a `cookies.json` file** in the project root (Scweet format):

```json
[
  { "username": "your_handle", "cookies": { "auth_token": "PASTE_YOUR_TOKEN_HERE" } }
]
```

You can list multiple accounts to rotate between them (helps with rate limits):

```json
[
  { "username": "account_one", "cookies": { "auth_token": "..." } },
  { "username": "account_two", "cookies": { "auth_token": "..." } }
]
```

> 🔒 Your `auth_token` grants full access to your X account — treat it like a
> password. Never commit it or share it. If it leaks, log out of that X session
> (or change your password) to invalidate the token.

`cookies.json`, `.env`, `scweet_state.db` and `profile_cursors.json` are all
gitignored — keep them local.

## Usage

```bash
# 1. Scrape — run repeatedly to walk further back through the timeline.
#    Output accumulates (deduped) in outputs/<username>.json
tweetmentor scrape karpathy --limit 500

# 2. Analyze — produce study_guide.html (+ study_guide.json)
tweetmentor analyze outputs/karpathy.json -o study_guide.html

# 3. Export — flatten any JSON to CSV
tweetmentor export outputs/karpathy.json outputs/karpathy.csv
```

See all options with `tweetmentor <command> --help`.

### Custom themes

Pass a JSON file to analyze any account for any topics:

```json
[
  { "id": "growth",  "desc": "How they grew an audience", "title": "📈 Audience growth" },
  { "id": "writing", "desc": "How they write threads",    "title": "✍️ Writing style" }
]
```

```bash
tweetmentor analyze outputs/someone.json --themes my_themes.json --person "@someone"
```

## How the resume works

Scweet's built-in `resume=True` doesn't persist pagination for profile timelines
across separate runs, so plain runs keep re-fetching the newest tweets.
tweetmentor drives the runner directly, saves the returned `resume_cursors` to
`profile_cursors.json`, and feeds them back on the next run — so each run
continues where the last one stopped.

## Library use

```python
from tweetmentor import scrape_user, analyze_tweets, render_html
from tweetmentor.config import load_llm_config

scrape_user("karpathy", limit=500)
guide = analyze_tweets("outputs/karpathy.json", load_llm_config())
open("study_guide.html", "w").write(render_html(guide))
```

## License

MIT — see [LICENSE](LICENSE).
