"""
brain.py

Every conversation with Claude goes through this one file.

Two reasons it is separate. First, the model name, the effort level and the
error messages live in one place instead of being scattered. Second, when
something goes wrong with the API you get a sentence you can act on instead of
a wall of red text.
"""

import json
import re

import anthropic

import config

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


class BrainError(Exception):
    """A problem talking to Claude, already written in plain language."""


# ---------------------------------------------------------------------------
# The one call
# ---------------------------------------------------------------------------
def ask_claude(system: str, user: str, want_json: bool = False) -> str | dict:
    """
    Send one instruction to Claude and get the answer back.

    system : the standing instructions, loaded from a prompt file
    user   : the specific thing we want done this time
    want_json : if True, parse the reply as JSON and return a dictionary
    """
    try:
        response = client.messages.create(
            model=config.MODEL,
            max_tokens=config.MAX_TOKENS,
            output_config={"effort": config.EFFORT},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError:
        raise BrainError(
            "Anthropic would not accept the API key. Check ANTHROPIC_API_KEY in "
            "your .env file, then restart the bot."
        )
    except anthropic.RateLimitError:
        raise BrainError(
            "Anthropic is rate limiting us right now. Wait a minute, then send "
            "your message again."
        )
    except anthropic.NotFoundError:
        raise BrainError(
            f"Anthropic does not recognise the model '{config.MODEL}'. Open "
            "config.py and check the MODEL line near the top."
        )
    except anthropic.BadRequestError as error:
        raise BrainError(
            "Anthropic rejected the request. This usually means the model name "
            f"in config.py is out of date (it is currently '{config.MODEL}'). "
            f"The technical detail was: {error}"
        )
    except anthropic.APIConnectionError:
        raise BrainError(
            "Could not reach Anthropic at all. Check your internet connection "
            "and try again."
        )
    except anthropic.APIStatusError as error:
        raise BrainError(
            f"Anthropic had a problem on their side (error {error.status_code}). "
            "Wait a moment and try again."
        )

    # Claude can decline a request on safety grounds. It is very unlikely for
    # writing a LinkedIn post, but if it happens we say so rather than crash.
    if response.stop_reason == "refusal":
        raise BrainError(
            "Claude declined to answer that one. Try rewording the idea, or "
            "type *cancel* and start again."
        )

    # A reply is a list of blocks. We want the text ones.
    text = "".join(block.text for block in response.content if block.type == "text").strip()

    if not text:
        raise BrainError("Claude sent back an empty reply. Try that message again.")

    if not want_json:
        return text

    return _parse_json(text)


# ---------------------------------------------------------------------------
# Reading JSON back
# ---------------------------------------------------------------------------
def _parse_json(text: str) -> dict:
    """
    Claude sometimes wraps JSON in a code fence or adds a sentence before it.
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
            "Claude replied in a shape I could not read. Send your message "
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
