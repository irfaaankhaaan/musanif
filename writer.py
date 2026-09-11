"""
writer.py

Where the posts get written.

Three things happen here, in order, for each platform:

  1. WRITE      one Claude call, using that platform's own prompt file.
  2. CRITIQUE   a second Claude call that reads the draft hard, lists what is
                wrong with it, and rewrites it once. You only see the result.
  3. GATE       rules.py checks the finished text. If a rule is broken, a third
                targeted call fixes exactly that, and we check again.

The two platforms never see each other's text. Both are written from the same
brief, separately, with separate prompts. That is what makes them share an idea
without sharing wording.
"""

import brain
import config
import rules


def _brief_for_prompt(brief: dict) -> str:
    """The content brief, laid out for Claude to write from."""
    keywords = brief.get("detail_keywords", [])
    must_appear = "\n".join(f'  - "{word}"' for word in keywords) or "  (none given)"

    rough = (brief.get("rough_post") or "").strip()
    draft_section = ""
    if rough:
        draft_section = (
            "# Their own rough post\n\n"
            "This is what they actually wrote, before any of it was tidied. It "
            "is the spine of the post you are about to write. Keep their good "
            "lines and their phrasing where it works, and do not replace their "
            "voice with a smoother one. The brief below is a reading of this, "
            "not a replacement for it.\n\n"
            f"{rough}\n\n---\n\n"
        )

    return (
        draft_section
        + "# The brief\n\n"
        f"**The claim:** {brief.get('core_claim', '')}\n\n"
        f"**The proof:** {brief.get('proof', '')}\n\n"
        f"**The sharpest detail:** {brief.get('sharpest_detail', '')}\n\n"
        f"**The takeaway:** {brief.get('takeaway', '')}\n\n"
        f"**Call to action:** {brief.get('call_to_action', '') or '(none, do not invent one)'}\n\n"
        "**These strings must appear in the post, word for word:**\n"
        f"{must_appear}\n"
    )


def _rules_for_prompt(voice: str) -> str:
    return "\n\n---\n\n# The writing rules, which are absolute\n\n" + voice


# ---------------------------------------------------------------------------
# Step 1: write
# ---------------------------------------------------------------------------
def write_post(platform: str, brief: dict, voice: str, note: str = "") -> str:
    """
    One Claude call, using prompts/<platform>_write.md.

    `note` is your feedback when you press Rewrite ("too long", "hook is
    weak"). It goes in as an instruction, not as a suggestion.
    """
    system = brain.load_prompt(f"{platform}_write") + _rules_for_prompt(voice)

    user = _brief_for_prompt(brief)
    if note:
        user += (
            "\n---\n\n# What was wrong with the last attempt\n\n"
            f"{note}\n\n"
            "This came from the person you are writing for. Treat it as a "
            "requirement, not a suggestion. Fix it."
        )

    return _clean(brain.ask_claude(system, user))


# ---------------------------------------------------------------------------
# Step 2: critique and rewrite
# ---------------------------------------------------------------------------
def critique_post(platform: str, draft: str, brief: dict, voice: str) -> tuple[str, list[str]]:
    """
    A second call that reads the draft hard and rewrites it once.

    Returns the improved post and the list of problems it found. The problems
    are saved to the session history. You never see them in Slack.
    """
    system = brain.load_prompt(f"{platform}_critique") + _rules_for_prompt(voice)
    user = (
        f"{_brief_for_prompt(brief)}\n---\n\n# The draft to critique\n\n{draft}"
    )

    reply = brain.ask_claude(system, user, want_json=True)
    improved = _clean(str(reply.get("rewrite") or ""))
    found = [str(item) for item in (reply.get("critique") or [])]

    # If the critique came back with no usable rewrite, keep the original
    # rather than showing you an empty post.
    if not improved:
        return draft, found + ["The critique step returned nothing, kept the original draft."]

    return improved, found


# ---------------------------------------------------------------------------
# Step 3: the gate, and targeted repair
# ---------------------------------------------------------------------------
def fix_problems(platform: str, post: str, problems: list[str], brief: dict, voice: str) -> str:
    """
    A narrow repair call. Not a rewrite. It is given the exact broken rules and
    told to change as little as possible.
    """
    listed = "\n".join(f"  - {problem}" for problem in problems)
    keywords = ", ".join(f'"{word}"' for word in brief.get("detail_keywords", []))

    system = (
        "You repair posts that break a hard rule. You change as little as "
        "possible. You do not improve, restructure, or reword anything that is "
        "not listed as a problem. You return the repaired post and nothing "
        "else, with no preamble and no quote marks."
        + _rules_for_prompt(voice)
    )
    user = (
        f"# The post\n\n{post}\n\n"
        f"---\n\n# The rules it breaks\n\n{listed}\n\n"
        f"---\n\nFix exactly these and nothing else. "
        f"These strings must still appear word for word: {keywords or '(none)'}."
    )

    return _clean(brain.ask_claude(system, user))


# ---------------------------------------------------------------------------
# Instagram, which is two pieces rather than one
# ---------------------------------------------------------------------------
# The hook goes ON the image or video. The caption is the answer to it. They
# are written together, in one call, because a caption that pays off a hook has
# to be designed with that hook, not fitted to it afterwards.

def write_instagram(brief: dict, voice: str, note: str = "") -> tuple[str, str]:
    """Returns (hook, caption). The hook is for the media, not the caption."""
    system = brain.load_prompt("instagram_write") + _rules_for_prompt(voice)

    user = _brief_for_prompt(brief)
    if note:
        user += (
            "\n---\n\n# What was wrong with the last attempt\n\n"
            f"{note}\n\n"
            "This came from the person you are writing for. Treat it as a "
            "requirement, not a suggestion. Fix it."
        )

    reply = brain.ask_claude(system, user, want_json=True)
    return _clean(str(reply.get("hook") or "")), _clean(str(reply.get("caption") or ""))


def critique_instagram(hook: str, caption: str, brief: dict, voice: str) -> tuple[str, str, list[str]]:
    """Reads both halves hard and rewrites them once. Returns (hook, caption, notes)."""
    system = brain.load_prompt("instagram_critique") + _rules_for_prompt(voice)
    user = (
        f"{_brief_for_prompt(brief)}\n---\n\n"
        f"# The hook, which goes on the image or video\n\n{hook}\n\n"
        f"---\n\n# The caption, which has to answer it\n\n{caption}"
    )

    reply = brain.ask_claude(system, user, want_json=True)
    found = [str(item) for item in (reply.get("critique") or [])]
    new_hook = _clean(str(reply.get("rewrite_hook") or ""))
    new_caption = _clean(str(reply.get("rewrite_caption") or ""))

    # If the critique came back with nothing usable, keep what we had rather
    # than showing you an empty post.
    if not new_caption:
        return hook, caption, found + ["The critique step returned nothing, kept the original."]

    return new_hook or hook, new_caption, found


def _gate(platform: str, text: str, brief: dict, voice: str, keywords: list) -> tuple[str, list, list]:
    """
    Run one piece of text past rules.py and repair it until it is clean.
    Returns (text, repairs, unresolved).
    """
    problems = rules.check(text, voice, platform, keywords)
    attempts = 0
    repairs: list[str] = []

    while problems and attempts < config.MAX_RULE_RETRIES:
        attempts += 1
        repairs.extend(problems)
        text = fix_problems(platform, text, problems, brief, voice)
        problems = rules.check(text, voice, platform, keywords)

    # Last resort for punctuation only. If an em dash has survived three repair
    # attempts, replace it mechanically rather than show you a post that breaks
    # your hardest rule.
    if problems:
        scrubbed = rules.scrub_characters(text, voice)
        if scrubbed != text:
            text = scrubbed
            repairs.append("An em dash survived the rewrites, so it was replaced mechanically.")
            problems = rules.check(text, voice, platform, keywords)

    return text, repairs, problems


def make_instagram(brief: dict, voice: str, note: str = "") -> dict:
    """The whole Instagram pipeline: hook for the media, caption that answers it."""
    keywords = brief.get("detail_keywords", [])

    draft_hook, draft_caption = write_instagram(brief, voice, note)
    hook, caption, critique_notes = critique_instagram(draft_hook, draft_caption, brief, voice)

    # The must-appear detail is checked across the pair, because the hook and
    # the caption are read together. Requiring it in both would force the
    # caption to repeat the hook, which is the one thing it must not do.
    caption, caption_repairs, caption_left = _gate(
        "instagram", caption, brief, voice, keywords if not _has_any(hook, keywords) else []
    )
    hook, hook_repairs, hook_left = _gate("instagram", hook, brief, voice, [])

    return {
        "post": caption,
        "hook": hook,
        "first_draft": draft_caption,
        "critique": critique_notes,
        "repairs": caption_repairs + [f"(hook) {note}" for note in hook_repairs],
        "unresolved": caption_left + hook_left,
    }


def _has_any(text: str, keywords: list) -> bool:
    """True if any of the must-appear strings is already in this text."""
    lowered = text.lower()
    return any(word.lower() in lowered for word in keywords if word)


def make_post(platform: str, brief: dict, voice: str, note: str = "") -> dict:
    """
    The whole pipeline for one platform.

    Returns a dictionary holding the finished post, what the critique found,
    and any rule problems that survived. app.py shows you the post; the rest
    goes into the session history.
    """
    if platform == "instagram":
        return make_instagram(brief, voice, note)

    keywords = brief.get("detail_keywords", [])

    draft = write_post(platform, brief, voice, note)
    post, critique_notes = critique_post(platform, draft, brief, voice)

    problems = rules.check(post, voice, platform, keywords)
    attempts = 0
    repairs: list[str] = []

    # Keep repairing until the post is clean or we run out of patience.
    while problems and attempts < config.MAX_RULE_RETRIES:
        attempts += 1
        repairs.extend(problems)
        post = fix_problems(platform, post, problems, brief, voice)
        problems = rules.check(post, voice, platform, keywords)

    # Last resort for punctuation only. If an em dash has survived three
    # repair attempts, we replace it mechanically rather than show you a post
    # that breaks your hardest rule.
    if problems:
        scrubbed = rules.scrub_characters(post, voice)
        if scrubbed != post:
            post = scrubbed
            repairs.append("An em dash survived the rewrites, so it was replaced mechanically.")
            problems = rules.check(post, voice, platform, keywords)

    return {
        "post": post,
        "hook": "",
        "first_draft": draft,
        "critique": critique_notes,
        "repairs": repairs,
        "unresolved": problems,
    }


# ---------------------------------------------------------------------------
def _clean(text: str) -> str:
    """
    Strip the wrapping Claude sometimes adds despite being told not to:
    a code fence, or quote marks around the whole post.
    """
    text = text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        if lines[-1].strip().startswith("```"):
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        text = "\n".join(lines).strip()

    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()

    return text
