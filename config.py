"""
config.py

Every setting and secret in one place. If you want to change how the bot
behaves without touching real code, this is the file to open.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load the .env file that sits next to this file.
HERE = Path(__file__).parent
load_dotenv(HERE / ".env")


# ---------------------------------------------------------------------------
# The Grok model
# ---------------------------------------------------------------------------
# One constant, used by every Grok call in the project. If a newer model comes
# out, change this single line and the whole bot upgrades.
MODEL = os.getenv("GROK_MODEL", "grok-4-fast-reasoning")

# Where the Grok API lives. The default is xAI's own API, which is what the
# GROK_API_KEY from console.x.ai talks to.
#
# To use a free Grok instead, put these two lines in your .env:
#   GROK_BASE_URL=https://openrouter.ai/api/v1
#   GROK_MODEL=x-ai/grok-4-fast:free
# and use an OpenRouter key (it starts with "sk-or-") as your GROK_API_KEY.
GROK_BASE_URL = os.getenv("GROK_BASE_URL", "https://api.x.ai/v1").strip()

# How hard Grok thinks before answering, sent only if you fill it in.
# Blank is the right answer for the grok-4 models: they decide for themselves
# and reject the setting. The smaller grok-3-mini accepts "low" or "high".
EFFORT = os.getenv("GROK_EFFORT", "").strip()

# Safety ceiling on how long a single Grok reply can be. Posts are short,
# so this is generous.
MAX_TOKENS = 8000


# ---------------------------------------------------------------------------
# Secrets, read from .env
# ---------------------------------------------------------------------------
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
GROK_API_KEY = os.getenv("GROK_API_KEY", "")
ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY", "")


# ---------------------------------------------------------------------------
# Behaviour switches
# ---------------------------------------------------------------------------
# DRY_RUN on means: do all the work, show you the posts, publish nothing.
# It is ON unless your .env says exactly "false".
DRY_RUN = os.getenv("DRY_RUN", "true").strip().lower() != "false"

# How many times the bot is allowed to rewrite a post that broke a hard rule
# (an em dash, a banned word) before it gives up and tells you.
MAX_RULE_RETRIES = 3


# ---------------------------------------------------------------------------
# Where things live on disk
# ---------------------------------------------------------------------------
VOICE_FILE = HERE / "voice.md"
PROMPTS_DIR = HERE / "prompts"
SESSIONS_DIR = HERE / "sessions"       # finished sessions get saved here
MEDIA_DIR = HERE / "media_cache"       # files you upload get downloaded here

# The session you are in the middle of, written to disk after every message so
# that restarting the bot does not lose the conversation. It sits in
# SESSIONS_DIR because that is the folder already kept on a volume when the bot
# is hosted, so persistence needs no extra setup.
#
# Finished sessions in there are named after their date and time, and come as a
# .md and a .json pair, so this fixed name never clashes with one. It is
# deleted the moment a session is cancelled.
STATE_FILE = SESSIONS_DIR / "in-progress.json"

for folder in (SESSIONS_DIR, MEDIA_DIR):
    folder.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Startup check
# ---------------------------------------------------------------------------
def _is_unfilled(value: str) -> bool:
    """
    True if this is still the example value out of .env.example rather than a
    real key. The examples all end in '...', and every real key is long.
    """
    return (not value) or ("..." in value) or (len(value) < 20)


def check_secrets(need_zernio: bool = False) -> list[str]:
    """
    Returns a list of plain-language problems with your .env file.
    An empty list means everything needed is present.
    """
    problems = []

    # Each row is (value, name, accepted prefix or prefixes, where to get it,
    # whether it is required).
    keys = [
        (SLACK_BOT_TOKEN, "SLACK_BOT_TOKEN", "xoxb-",
         "Slack app > OAuth & Permissions > Bot User OAuth Token", True),
        (SLACK_APP_TOKEN, "SLACK_APP_TOKEN", "xapp-",
         "Slack app > Basic Information > App-Level Tokens", True),
        (GROK_API_KEY, "GROK_API_KEY", ("xai-", "sk-or-"),
         "console.x.ai > API keys, or openrouter.ai/keys for the free tier", True),
        (ZERNIO_API_KEY, "ZERNIO_API_KEY", "sk_",
         "your Zernio dashboard", need_zernio),
    ]

    for value, name, prefix, where, required in keys:
        if not required:
            continue
        if _is_unfilled(value):
            problems.append(
                f"{name} has not been filled in yet. It is still the example "
                f"value from .env.example. Get the real one from {where}, then "
                "paste it into the .env file."
            )
        elif not value.startswith(prefix):
            wanted = prefix if isinstance(prefix, str) else " or ".join(prefix)
            problems.append(
                f"{name} does not look right. It should start with '{wanted}'. "
                f"Get it from {where}."
            )

    if problems:
        problems.append(
            "Tip: double-click edit-secrets.bat to open the .env file in Notepad."
        )

    return problems
