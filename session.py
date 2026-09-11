"""
session.py

The bot's short-term memory.

Slack has no memory of its own. Every message you send arrives as a separate
event with no idea what came before it. This file holds the one thing that
makes the bot feel like a conversation: a Session object that remembers what
phase we are in, what you have already told it, and what it has written.

There is one session at a time, on purpose. Typing "new" throws the old one
away and starts fresh.
"""

from dataclasses import dataclass, field
from datetime import datetime


# The phases of a session, in the order they happen.
# The bot looks at session.phase to decide what your next message means.
IDLE = "idle"                       # nothing running, waiting for "new"
INTERVIEW = "interview"             # asking you questions, one at a time
MEDIA_LINKEDIN = "media_linkedin"   # waiting for a LinkedIn file, or "skip"
MEDIA_INSTAGRAM = "media_instagram" # waiting for an Instagram video, or "skip"
REVIEW = "review"                   # both drafts shown, waiting on buttons
REWRITE_NOTE = "rewrite_note"       # waiting for "what was wrong with it?"
EDIT_TEXT = "edit_text"             # waiting for your corrected text
DONE = "done"                       # everything approved or skipped


@dataclass
class Draft:
    """One platform's post: the text, its media file, and where it ended up."""

    text: str = ""

    # Instagram only. The hook is the line that goes ON the image or video, and
    # `text` is then the caption that pays it off. LinkedIn leaves this empty:
    # its post carries its own hook in the first line, as it always did.
    hook: str = ""

    # The files you uploaded for THIS platform, downloaded to media_cache.
    # A list because LinkedIn takes several images. Each entry is
    # {path, name, kind, bytes}. Empty means you typed "skip".
    media: list = field(default_factory=list)
    media_skipped: bool = False

    published_url: str | None = None
    approved: bool = False

    # What the self-critique found, and any rules it had to repair.
    # Saved to the session history so you can see how the writing improved.
    critique: list = field(default_factory=list)
    repairs: list = field(default_factory=list)


@dataclass
class Session:
    """Everything the bot knows about the post currently being made."""

    user_id: str
    channel_id: str
    phase: str = IDLE
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    # voice.md is read once, when the session starts, and held for the whole
    # session. That way editing the file mid-session cannot change the rules
    # halfway through a post. Restart a session to pick up your edits.
    voice: str = ""

    # The interview, stored as a list of (question, answer) pairs.
    interview: list[dict] = field(default_factory=list)

    # The internal content brief built after the interview. You never see this
    # unless you ask for it with "brief".
    brief: dict = field(default_factory=dict)

    # The two posts.
    linkedin: Draft = field(default_factory=Draft)
    instagram: Draft = field(default_factory=Draft)

    # When you press Rewrite or Edit, we need to remember which platform you
    # pressed it on, because your next message is the answer to that button.
    pending_platform: str | None = None

    # What the bot currently believes the post is about, in one line. It is
    # rewritten every turn of the interview. This is what keeps the questions
    # anchored to your subject instead of drifting onto a template.
    topic: str = ""

    # Every time you told it the questions were wrong. Each entry is
    # {said, note, rejected}. These are handed back to Claude on every later
    # question, which is what makes a correction stick for the rest of the
    # session rather than being obeyed once and forgotten.
    steers: list[dict] = field(default_factory=list)

    def draft(self, platform: str) -> Draft:
        """Get the LinkedIn or Instagram draft by name."""
        return self.linkedin if platform == "linkedin" else self.instagram

    def last_answer(self) -> str:
        """The most recent thing you said in the interview."""
        return self.interview[-1]["answer"] if self.interview else ""

    def transcript(self) -> str:
        """
        The interview as readable text, for feeding to Claude.

        A question you have not answered yet is left out. Showing it with an
        empty answer invites Claude to fill the gap in for you, and an answer
        you never gave has no business ending up in the post.
        """
        lines = []
        for turn in self.interview:
            if not turn.get("answer"):
                continue
            lines.append(f"Q: {turn['question']}")
            lines.append(f"A: {turn['answer']}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# The single live session
# ---------------------------------------------------------------------------
_current: Session | None = None


def start(user_id: str, channel_id: str, voice: str = "") -> Session:
    """Throw away any old session and begin a new one."""
    global _current
    _current = Session(
        user_id=user_id,
        channel_id=channel_id,
        phase=INTERVIEW,
        voice=voice,
    )
    return _current


def current() -> Session | None:
    """The session in progress, or None if nothing is running."""
    return _current


def clear() -> None:
    """End the session without saving."""
    global _current
    _current = None
