"""
interview.py

The part that asks you questions.

Your first message is not a topic. It is the post, roughly. Everything the
interview does after that is refinement: finding what is missing, what is
vague, and what you meant, so the writing stage has the real thing to work
from rather than a summary of it.

There is no list of questions in this file, no list of post types, and no
target number of questions. What to ask is worked out from your draft, fresh,
every turn. What this file guarantees is the shape of the conversation, not its
content:

  - one question at a time, never two
  - it asks what the draft is saying before it starts refining, if that is
    genuinely unclear
  - it stops when the draft is ready, however many questions that took, and
    you can stop it yourself at any point by typing "write"
  - when you say the questions are wrong, that is never filed as an answer,
    the question that earned it is thrown away, and the replacement is never
    the same question again

Instructions are a request. Code is a guarantee.
"""

import difflib
import re
from dataclasses import dataclass

import brain

# The bot always opens with this. Everything after it is worked out live.
OPENING_QUESTION = (
    "What is the post? Give it to me rough, as long or as messy as you like. "
    "I will ask about the parts that need it."
)

# There is no target number of questions, and no floor. A draft that arrives
# nearly finished should get one or two questions. A thin one should get more.
# This is only a runaway guard: it stops an interview that has stopped making
# progress, and should never be reached in a normal session.
SAFETY_CAP = 15

# Questions asked only to work out what the draft is actually saying. They do
# not count towards the guard, because they are not refining yet. The cap stops
# the bot circling if it never feels certain.
MAX_CLARIFIERS = 2

# The three kinds of turn.
OPENING = "opening"
CLARIFY = "clarify"
PROBE = "probe"

# Used when Grok owes us a question about the subject and did not send one.
TOPIC_QUESTION = "What is the main thing you want this post to say?"


@dataclass
class Step:
    """What the bot should do about the message you just sent."""

    kind: str                 # "question", "correction" or "done"
    question: str = ""
    acknowledge: str = ""     # corrections only, one line back to you
    note: str = ""            # corrections only, what you want asked instead
    turn_kind: str = PROBE


# ---------------------------------------------------------------------------
# Reading where we are
# ---------------------------------------------------------------------------
def questions_asked(live) -> int:
    """Refining questions asked so far. The opening and clarifiers are free."""
    return sum(1 for turn in live.interview if turn.get("kind") == PROBE)


def clarifiers_asked(live) -> int:
    """Questions asked only to work out what the draft is saying."""
    return sum(1 for turn in live.interview if turn.get("kind") == CLARIFY)


def rough_post(live) -> str:
    """Your first message. The rough post everything else is refining."""
    return live.interview[0]["answer"] if live.interview else ""


# ---------------------------------------------------------------------------
# The one decision
# ---------------------------------------------------------------------------
def respond(live, reply: str) -> Step:
    """
    Work out what your last message meant and what to do about it.

    Called with your raw message, BEFORE it is filed as an answer, because
    deciding whether it is an answer at all is half of this function's job.
    """
    pending = live.interview[-1]["question"] if live.interview else OPENING_QUESTION
    asked = questions_asked(live)

    decision = _ask_grok(live, pending, reply, asked)

    # Whatever else happens, hold on to what it now thinks the post is saying.
    topic = str(decision.get("topic") or "").strip()
    if topic:
        live.topic = topic

    is_correction = str(decision.get("reply_type") or "").strip().lower() == "correction"
    topic_clear = bool(decision.get("topic_clear", True))
    enough = bool(decision.get("enough"))
    question = _single_question(str(decision.get("question") or "").strip())

    # --- You told it the question was wrong -------------------------------
    if is_correction:
        note = str(decision.get("note") or "").strip() or reply.strip()

        # Kept for the rest of the session. Every later question is built with
        # these sitting in front of it, which is what makes a correction stick
        # rather than getting obeyed once and then forgotten.
        live.steers.append({
            "said": reply.strip(),
            "note": note,
            "rejected": pending,
        })

        # There is no material in a correction, so it can never be the thing
        # that finishes the interview, whatever Grok says.
        if not question or _too_similar(question, pending):
            question = _handover_question(live)

        return Step(
            kind="correction",
            question=question,
            acknowledge=str(decision.get("acknowledge") or "").strip() or "Understood.",
            note=note,
            turn_kind=PROBE if topic_clear else CLARIFY,
        )

    # --- It was an answer -------------------------------------------------
    # The runaway guard. Not a target, and not a shape for the interview. If
    # this ever fires, the questions had stopped getting anywhere.
    if asked >= SAFETY_CAP:
        return Step(kind="done")

    # It cannot say what the draft is saying. Settle that before refining.
    # These questions are free, up to the cap.
    if not topic_clear and clarifiers_asked(live) < MAX_CLARIFIERS:
        return Step(
            kind="question",
            question=question or TOPIC_QUESTION,
            turn_kind=CLARIFY,
        )

    if enough or not question:
        return Step(kind="done")

    return Step(kind="question", question=question, turn_kind=PROBE)


# ---------------------------------------------------------------------------
# Talking to Grok
# ---------------------------------------------------------------------------
def _ask_grok(live, pending: str, reply: str, asked: int) -> dict:
    system = (
        brain.load_prompt("interview")
        + "\n\n---\n\n# The person's voice and rules\n\n"
        + live.voice
    )

    parts = [
        "Their rough post, exactly as they sent it. This is the material the "
        "finished posts are built from, not a topic to go and research:",
        "",
        rough_post(live) or "(nothing yet)",
        "",
        "What you currently understand the post to be saying:",
        live.topic or "(not established yet)",
        "",
        "The conversation so far:",
        "",
        live.transcript() or "(nothing yet)",
        "",
        "The question you just asked:",
        pending,
        "",
        "What they just replied:",
        reply,
    ]

    if live.steers:
        corrections = "\n".join(f"- {steer['note']}" for steer in live.steers)
        parts += [
            "",
            "They have ALREADY corrected your questioning. These still apply to "
            "every question you ask from here, including this one:",
            corrections,
        ]

    parts += [
        "",
        f"You have asked {asked} refining question(s). There is no target "
        "number, no minimum and no maximum. Ask for what the draft still "
        "genuinely needs, and stop the moment it does not need any more.",
        "",
        "Decide what their reply was, then decide what to do next.",
    ]

    return brain.ask_grok(system, "\n".join(parts), want_json=True)


# ---------------------------------------------------------------------------
# The guarantees
# ---------------------------------------------------------------------------
def _single_question(question: str) -> str:
    """
    Guarantee one question, not two.

    If Grok bolted a second question on, keep the first and drop the rest.
    """
    first_mark = question.find("?")
    if first_mark != -1 and "?" in question[first_mark + 1:]:
        question = question[:first_mark + 1]
    return question.strip()


def _normalise(text: str) -> str:
    """Lowercase, punctuation stripped, spaces collapsed. For comparing only."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def _too_similar(new: str, old: str) -> bool:
    """
    True if the replacement question is really the rejected one again.

    This is the check that stops "you are asking the wrong questions" being
    answered with the same question wearing a different coat.
    """
    a, b = _normalise(new), _normalise(old)
    if not a or not b:
        return False
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() > 0.85


def _handover_question(live) -> str:
    """
    The fallback, used when Grok owes us a question and has not produced a
    usable one. It hands the choice to you rather than guessing again, which is
    the right move at the exact moment the guessing has been going wrong.
    """
    if live.topic:
        return f"What should I be asking you about {live.topic}?"
    return "What should I be asking you about this post?"


# ---------------------------------------------------------------------------
# The brief
# ---------------------------------------------------------------------------
def build_brief(live) -> dict:
    """
    Turn the rough post and everything that refined it into the internal
    content brief. You never see this unless you ask for it with "brief".
    """
    system = (
        brain.load_prompt("brief")
        + "\n\n---\n\n# The person's voice and rules\n\n"
        + live.voice
    )

    parts = [
        "Their rough post, exactly as they sent it:",
        "",
        rough_post(live),
        "",
        "What it is saying, as understood by the interview:",
        live.topic or "(not established)",
        "",
        "What the questions afterwards added:",
        "",
        live.transcript(),
    ]

    if live.steers:
        corrections = "\n".join(f"- {steer['note']}" for steer in live.steers)
        parts += [
            "",
            "During the interview they corrected what the questions were about. "
            "The brief, and both posts built from it, must respect these:",
            corrections,
        ]

    brief = brain.ask_grok(system, "\n".join(parts), want_json=True)

    # The keywords are what rules.py later uses to prove the specific detail
    # survived into the finished post, so they have to be usable strings.
    keywords = brief.get("detail_keywords") or []
    brief["detail_keywords"] = [
        str(word).strip() for word in keywords if str(word).strip()
    ][:4]

    # The writing stage gets the rough post itself, not only the brief's
    # reading of it. Their own words are the spine of both posts, so they are
    # carried through rather than being summarised away here.
    brief["rough_post"] = rough_post(live)

    return brief


def readable_brief(brief: dict) -> str:
    """The brief, formatted for Slack, for when you type 'brief'."""
    if not brief:
        return "No brief yet. It gets written once the questions are finished."

    keywords = ", ".join(brief.get("detail_keywords", [])) or "none"
    return (
        "*Content brief*\n"
        f"*Claim:* {brief.get('core_claim', '')}\n"
        f"*Proof:* {brief.get('proof', '')}\n"
        f"*Sharpest detail:* {brief.get('sharpest_detail', '')}\n"
        f"*Must appear in both posts:* {keywords}\n"
        f"*Takeaway:* {brief.get('takeaway', '')}\n"
        f"*Call to action:* {brief.get('call_to_action', '') or 'none'}"
    )
