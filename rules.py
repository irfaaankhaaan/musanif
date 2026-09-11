"""
rules.py

The hard gate. Every draft passes through here before you see it.

The prompts tell Claude the rules. This file assumes Claude will sometimes
break them anyway, and checks. If a draft fails, the bot rewrites it and checks
again. You are not shown a post that breaks a rule.

The rules themselves live in voice.md, not in here. This file only reads them.
"""

import re

import config

# ---------------------------------------------------------------------------
# Reading voice.md
# ---------------------------------------------------------------------------

def load_voice() -> str:
    """The whole of voice.md, as text, to hand to Claude."""
    if not config.VOICE_FILE.exists():
        raise FileNotFoundError(
            "voice.md is missing from the project folder. That file holds your "
            "writing rules and the bot will not write without it."
        )
    return config.VOICE_FILE.read_text(encoding="utf-8")


def _bullets_under(heading: str, text: str) -> list[str]:
    """
    Pull the bullet list that sits under a '## heading' in voice.md.
    Stops at the next '##'. Strips backticks and surrounding quotes.
    """
    pattern = rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        return []

    items = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if line.startswith("- "):
            item = line[2:].strip().strip("`").strip('"').strip("'")
            if item:
                items.append(item)
    return items


def banned_characters(voice: str) -> list[str]:
    return _bullets_under("Banned characters", voice)


def banned_phrases(voice: str) -> list[str]:
    return _bullets_under("Banned words and phrases", voice)


def watch_list(voice: str) -> list[str]:
    return _bullets_under("Watch list", voice)


# ---------------------------------------------------------------------------
# The "not just X, it's Y" shape
# ---------------------------------------------------------------------------
# Your content rules call this the contrast crunch. It is a sentence shape, not
# a word, so it needs patterns rather than a list. Each one is a real variant.
CONTRAST_CRUNCH = [
    r"\b(?:is|it's|its|isn't|is not|was|are|aren't)\s+not\s+just\b[^.!?\n]{0,80}?,\s*(?:it'?s|it is|they'?re|but)\b",
    r"\bnot\s+just\s+(?:a|an|the)\b[^.!?\n]{0,80}?,\s*(?:it'?s|it is|but)\b",
    r"\bnot\s+about\b[^.!?\n]{0,80}?,\s*it'?s\s+about\b",
    r"\bnot\s+only\b[^.!?\n]{0,90}?\b(?:but\s+also|it\s+also)\b",
]

# LinkedIn and Instagram both show plain text. Markdown does not render, so
# these characters would appear literally in the published post.
MARKDOWN_LEAKS = {
    "**": "bold stars, which show up as literal asterisks",
    "~~": "strikethrough tildes, which show up as literal tildes",
}


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------

def check(post: str, voice: str, platform: str, must_contain: list[str] | None = None) -> list[str]:
    """
    Returns a list of plain-language problems with a draft.
    An empty list means the draft is clean and can be shown.
    """
    problems: list[str] = []
    lowered = post.lower()

    # 1. Banned characters, the em dash above all.
    for character in banned_characters(voice):
        if character and character in post:
            name = "em dash" if character == "—" else f"the character {character!r}"
            problems.append(f"Contains {name}. Rewrite the sentence without it.")

    # 2. Banned words and phrases, whole words only.
    for phrase in banned_phrases(voice):
        pattern = r"\b" + re.escape(phrase.lower()).replace(r"\ ", r"\s+") + r"\b"
        if re.search(pattern, lowered):
            problems.append(f'Contains the banned phrase "{phrase}". Remove it and say the specific thing.')

    # 3. The contrast crunch.
    for pattern in CONTRAST_CRUNCH:
        if re.search(pattern, lowered):
            problems.append(
                'Uses the "not just X, it\'s Y" construction. '
                "Delete it and name the specific thing instead."
            )
            break

    # 4. Markdown that would show up as raw characters.
    for marker, explanation in MARKDOWN_LEAKS.items():
        if marker in post:
            problems.append(f"Contains {explanation}. This platform shows plain text only.")

    # 5. Platform rules.
    if platform == "linkedin":
        if "#" in post:
            problems.append("Contains a hashtag. LinkedIn posts here carry none.")
        if _has_emoji(post):
            problems.append("Contains an emoji. LinkedIn posts here carry none.")

    # 6. The specific detail from the interview has to survive into the post.
    if must_contain:
        found = any(keyword.lower() in lowered for keyword in must_contain if keyword)
        if not found:
            listed = ", ".join(f'"{k}"' for k in must_contain)
            problems.append(
                f"Does not contain the specific detail from the interview ({listed}). "
                "The post has to carry the real thing, not a general version of it."
            )

    return problems


def _has_emoji(text: str) -> bool:
    """True if the text contains a pictographic character."""
    for character in text:
        code = ord(character)
        if (
            0x1F300 <= code <= 0x1FAFF   # emoji, symbols, pictographs
            or 0x2600 <= code <= 0x27BF  # misc symbols and dingbats
            or code in (0x2B50, 0x2B55, 0xFE0F)
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# Last resort
# ---------------------------------------------------------------------------

def scrub_characters(post: str, voice: str) -> str:
    """
    A mechanical fix for banned characters only, used after Claude has failed
    to remove them on its own. An em dash becomes a period or a comma depending
    on what follows it. Words are never touched, only punctuation.
    """
    cleaned = post
    for character in banned_characters(voice):
        if character not in cleaned:
            continue
        # "word — Word" reads as a sentence break. "word — word" reads as a comma.
        cleaned = re.sub(rf"\s*{re.escape(character)}\s*(?=[A-Z])", ". ", cleaned)
        cleaned = re.sub(rf"\s*{re.escape(character)}\s*", ", ", cleaned)
    return cleaned
