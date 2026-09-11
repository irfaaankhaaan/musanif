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
# The Claude model
# ---------------------------------------------------------------------------
# One constant, used by every Claude call in the project. If a newer model
# comes out, change this single line and the whole bot upgrades.
MODEL = "claude-opus-5"

# How hard Claude thinks before answering.
# "low" is fast and cheap, "high" is the default, "max" is slowest and best.
# Writing is worth thinking about, so we use "high".
EFFORT = "high"

# Safety ceiling on how long a single Claude reply can be. Posts are short,
# so this is generous.
MAX_TOKENS = 8000


# ---------------------------------------------------------------------------
# Secrets, read from .env
# ---------------------------------------------------------------------------
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
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

    keys = [
        (SLACK_BOT_TOKEN, "SLACK_BOT_TOKEN", "xoxb-",
         "Slack app > OAuth & Permissions > Bot User OAuth Token", True),
        (SLACK_APP_TOKEN, "SLACK_APP_TOKEN", "xapp-",
         "Slack app > Basic Information > App-Level Tokens", True),
        (ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY", "sk-ant-",
         "console.anthropic.com > API keys", True),
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
            problems.append(
                f"{name} does not look right. It should start with '{prefix}'. "
                f"Get it from {where}."
            )

    if problems:
        problems.append(
            "Tip: double-click edit-secrets.bat to open the .env file in Notepad."
        )

    return problems
