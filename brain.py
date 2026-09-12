"""
brain.py

Every conversation with Grok goes through this one file.

Two reasons it is separate. First, the model name, the effort level and the
error messages live in one place instead of being scattered. Second, when
something goes wrong with the API you get a sentence you can act on instead of
a wall of red text.

Grok speaks the same HTTP dialect as OpenAI, so we use the `openai` client
library and just point it at xAI (or at any other host that serves Grok, such
as OpenRouter's free tier). Which host is used is one line in config.py.
"""

import json
import re

import openai

import config

# The client refuses to be built with a blank key, which would crash the bot on
# startup before it could tell you what is wrong. The placeholder lets it start;
# config.check_secrets() then says the key is missing in plain language, and the
# selftest can run with no key at all.
client = openai.OpenAI(
    api_key=config.GROK_API_KEY or "no-key-set",
    base_url=config.GROK_BASE_URL,
)


class BrainError(Exception):
    """A problem talking to Grok, already written in plain language."""


# ---------------------------------------------------------------------------
# The one call
# ---------------------------------------------------------------------------
def ask_grok(system: str, user: str, want_json: bool = False) -> str | dict:
    """
    Send one instruction to Grok and get the answer back.

    system : the standing instructions, loaded from a prompt file
    user   : the specific thing we want done this time
    want_json : if True, parse the reply as JSON and return a dictionary
    """
    # Only reasoning models accept an effort level, so it is left out unless
    # config.EFFORT is filled in.
    extra = {"reasoning_effort": config.EFFORT} if config.EFFORT else {}

    try:
        response = client.chat.completions.create(
            model=config.MODEL,
            max_tokens=config.MAX_TOKENS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **extra,
        )
    except openai.AuthenticationError:
        raise BrainError(
            "Grok would not accept the API key. Check GROK_API_KEY in your .env "
            "file, then restart the bot."
        )
    except openai.PermissionDeniedError:
        raise BrainError(
            "Grok accepted the key but refused the request. The account behind "
            "that key probably has no credit left, or is not allowed to use "
            f"'{config.MODEL}'. Check your xAI console."
        )
    except openai.RateLimitError:
        raise BrainError(
            "Grok is rate limiting us right now. Wait a minute, then send your "
            "message again."
        )
    except openai.NotFoundError:
        raise BrainError(
            f"Grok does not recognise the model '{config.MODEL}'. Open config.py "
            "and check the MODEL line near the top."
        )
    except openai.BadRequestError as error:
        raise BrainError(
            "Grok rejected the request. This usually means the model name in "
            f"config.py is out of date (it is currently '{config.MODEL}'). "
            f"The technical detail was: {error}"
        )
    except openai.APIConnectionError:
        raise BrainError(
            f"Could not reach Grok at all ({config.GROK_BASE_URL}). Check your "
            "internet connection and try again."
        )
    except openai.APIStatusError as error:
        raise BrainError(
            f"Grok had a problem on their side (error {error.status_code}). "
            "Wait a moment and try again."
        )

    if not response.choices:
        raise BrainError("Grok sent back an empty reply. Try that message again.")

    choice = response.choices[0]

    # Grok can decline a request on safety grounds. It is very unlikely for
    # writing a LinkedIn post, but if it happens we say so rather than crash.
    if getattr(choice.message, "refusal", None) or choice.finish_reason == "content_filter":
        raise BrainError(
            "Grok declined to answer that one. Try rewording the idea, or type "
            "*cancel* and start again."
        )

    text = (choice.message.content or "").strip()

    if not text:
        raise BrainError("Grok sent back an empty reply. Try that message again.")

    if not want_json:
        return text

    return _parse_json(text)


# ---------------------------------------------------------------------------
# Reading JSON back
# ---------------------------------------------------------------------------
def _parse_json(text: str) -> dict:
    """
    Grok sometimes wraps JSON in a code fence or adds a sentence before it.
    This digs the actual object out rather than giving up.
    """
    # Strip a ```json ... ``` fence if there is one.
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    # Otherwise take everything between the first { and the last }.
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start:end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise BrainError(
            "Grok replied in a shape I could not read. Send your message "
            "again, it usually works the second time."
        )


# ---------------------------------------------------------------------------
# Loading prompt files
# ---------------------------------------------------------------------------
def load_prompt(name: str) -> str:
    """Read one of the editable instruction files out of the prompts folder."""
    path = config.PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise BrainError(
            f"The prompt file prompts/{name}.md is missing. That file holds the "
            "instructions for this step and the bot cannot run without it."
        )
    return path.read_text(encoding="utf-8")
