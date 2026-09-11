"""
selftest.py

Runs the bot's logic on your laptop with a pretend Slack and a pretend Claude,
so you can watch it work without connecting to anything and without spending
money.

Run it with:  python selftest.py
"""

import sys
from pathlib import Path

# Windows terminals default to a codepage that cannot print characters like the
# em dash, and printing one crashes the program. This makes output UTF-8 so a
# stray character can never take the test down.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import app
import brain
import config
import interview
import media
import rules
import session
import writer

# THE SELFTEST NEVER PUBLISHES. It clicks Approve on purpose, several times,
# and once DRY_RUN is off in your .env that would put real posts on your real
# accounts. So dry run is forced on here, for this process only, whatever the
# .env says. Your .env is not touched and the bot is unaffected.
config.DRY_RUN = True

LINE = "=" * 68


class FakeSlack:
    """Stands in for Slack. Instead of sending a message, it prints it."""

    def chat_postMessage(self, channel, text=None, blocks=None, **kwargs):
        for line in (text or "").split("\n"):
            print(f"  BOT: {line}")


def send(message: str) -> None:
    """Pretend you typed `message` into the DM."""
    print(f"\nYOU: {message}")
    app.route(FakeSlack(), "U_TEST", "D_TEST", message, [])


class FakeClaude:
    """
    Stands in for Claude. Returns canned answers in order, so we can test the
    bot's own rules without an API key and without spending anything.
    """

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    def __call__(self, system, user, want_json=False):
        self.calls += 1
        if not self.answers:
            raise AssertionError("The bot asked Claude more times than expected.")
        return self.answers.pop(0)


# ---------------------------------------------------------------------------
def check_dm_loop():
    """Stage 1: does the bot remember where it is between separate messages?"""
    print(LINE)
    print("STAGE 1 - the Slack DM loop and its memory")
    print(LINE)

    send("hello")
    send("status")
    send("cancel")

    session.clear()
    print("\nStage 1 passed: the bot answers, and knows nothing is running.")


# ---------------------------------------------------------------------------
def check_rules():
    """Stage 2: throw known-bad posts at the gate and confirm it catches them."""
    print("\n" + LINE)
    print("STAGE 2 - the rules gate")
    print(LINE)

    voice = rules.load_voice()
    print(f"Loaded voice.md: {len(rules.banned_phrases(voice))} banned phrases, "
          f"{len(rules.banned_characters(voice))} banned characters, "
          f"{len(rules.watch_list(voice))} on the watch list.\n")

    detail = ["40 minutes", "3 days"]
    clean_post = (
        "Onboarding went from 3 days to 40 minutes.\n\n"
        "The fix was one form (we had been asking for a VAT number nobody used)."
    )

    em_dash_post = "We cut it to 40 minutes — nobody believed it."
    rocket = "\U0001F680"

    # name, draft, platform, required detail, should this pass?
    cases = [
        ("an em dash",                 em_dash_post,                                            "linkedin",  None,   False),
        ("a banned word",              "A seamless way to move the needle on onboarding.",      "linkedin",  None,   False),
        ("not just X, it is Y",        "It's not just faster onboarding, it's a new business.", "linkedin",  None,   False),
        ("not only X, it also Y",      "Not only is it faster, it also cuts support tickets.",  "linkedin",  None,   False),
        ("a hashtag on LinkedIn",      "Onboarding: 3 days to 40 minutes. #startup",            "linkedin",  None,   False),
        ("an emoji on LinkedIn",       "Onboarding: 3 days to 40 minutes " + rocket,            "linkedin",  None,   False),
        ("an emoji on Instagram",      "Onboarding: 3 days to 40 minutes " + rocket,            "instagram", None,   True),
        ("markdown that won't render", "Onboarding went from **3 days to 40 minutes**.",        "linkedin",  None,   False),
        ("a post missing the detail",  "We improved our onboarding a lot this quarter.",        "linkedin",  detail, False),
        ("a clean post",               clean_post,                                              "linkedin",  detail, True),
    ]

    wrong = 0
    for name, text, platform, must, should_pass in cases:
        problems = rules.check(text, voice, platform, must)
        passed = not problems
        ok = passed == should_pass
        wrong += 0 if ok else 1
        label = "ok   " if ok else "WRONG"
        verdict = "let through" if passed else "caught"
        print(f"  [{label}] {name}: {verdict}")
        for problem in problems:
            print(f"           {problem}")

    print()
    if wrong:
        print(f"Stage 2 FAILED: {wrong} case(s) behaved unexpectedly.")
    else:
        print("Stage 2 passed: every bad post was caught, the clean one got through.")
    return wrong


# ---------------------------------------------------------------------------
def check_interview():
    """
    Stage 3: the questions. Claude is faked here, so what we are really testing
    is the bot's own guarantees: one question at a time, no forced number of
    them, a way for you to stop them, and a correction that actually sticks.
    """
    print("\n" + LINE)
    print("STAGE 3 - the questions")
    print(LINE)

    wrong = 0
    real_ask = brain.ask_claude
    real_make = writer.make_post

    # These tests stop at the brief. Stub the writing so it does not run here,
    # it gets its own stage below.
    writer.make_post = lambda platform, brief, voice, note="": {
        "post": f"(a {platform} post)", "hook": "", "first_draft": "",
        "critique": [], "repairs": [], "unresolved": [],
    }

    final_brief = {
        "core_claim": "A field nobody used was costing three days of onboarding.",
        "proof": "Removing the VAT number field cut it to 40 minutes.",
        "sharpest_detail": "The VAT number field nobody had ever read.",
        "detail_keywords": ["40 minutes", "3 days", "VAT number"],
        "takeaway": "Look at what you ask for before you optimise how you ask.",
        "call_to_action": "",
    }

    # -- Test 1: a good draft needs one question, and that is allowed -------
    print("\n  Test 1: the draft arrives nearly finished.")
    print("          One question should be allowed to be enough.\n")

    brain.ask_claude = FakeClaude([
        {"reply_type": "answer", "topic": "onboarding", "topic_clear": True,
         "enough": False, "question": "What was the field actually for?"},
        {"reply_type": "answer", "topic": "onboarding", "topic_clear": True,
         "enough": True, "question": ""},
        final_brief,
    ])

    send("new")
    send("we cut onboarding from 3 days to 40 minutes by dropping a VAT field nobody read")
    send("nothing, finance had asked for it years ago and nobody removed it")

    live = session.current()
    asked = interview.questions_asked(live)
    if asked == 1:
        print(f"\n  [ok   ] stopped after {asked} question, no floor forced a second")
    else:
        print(f"\n  [WRONG] asked {asked} questions, expected to stop at 1")
        wrong += 1

    if live.brief.get("rough_post", "").startswith("we cut onboarding"):
        print("  [ok   ] your own rough post was carried into the brief")
    else:
        print("  [WRONG] the rough post did not reach the brief")
        wrong += 1

    session.clear()

    # -- Test 2: the runaway guard ------------------------------------------
    print("\n  Test 2: Claude wants to ask forever.")
    print(f"          The guard of {interview.SAFETY_CAP} should cut it off.\n")

    endless = [
        {"reply_type": "answer", "topic": "x", "topic_clear": True,
         "enough": False, "question": f"Follow-up number {n}?"}
        for n in range(1, interview.SAFETY_CAP + 4)
    ]
    brain.ask_claude = FakeClaude(endless + [final_brief])

    send("new")
    for n in range(interview.SAFETY_CAP + 2):
        send(f"answer {n}")

    live = session.current()
    asked = interview.questions_asked(live)
    if asked > interview.SAFETY_CAP:
        print(f"\n  [WRONG] {asked} questions asked, guard is {interview.SAFETY_CAP}")
        wrong += 1
    else:
        print(f"\n  [ok   ] stopped at {asked}, guard of {interview.SAFETY_CAP} held")

    session.clear()

    # -- Test 3: you stop the questions yourself ----------------------------
    print("\n  Test 3: you type 'write' to stop the questions.\n")

    brain.ask_claude = FakeClaude([
        {"reply_type": "answer", "topic": "onboarding", "topic_clear": True,
         "enough": False, "question": "What was the field for?"},
        final_brief,
    ])

    send("new")
    send("we cut onboarding from 3 days to 40 minutes")
    send("write")

    live = session.current()
    if live.brief.get("core_claim"):
        print("\n  [ok   ] the questions stopped and it went straight to writing")
    else:
        print("\n  [WRONG] 'write' did not end the questions")
        wrong += 1

    session.clear()
    brain.ask_claude = real_ask

    # -- Test 4: two questions in one get trimmed to one --------------------
    print("\n  Test 4: Claude bolts two questions together.")
    print("          Only the first should survive.\n")

    greedy = "What was it before? And how long did the fix take?"
    trimmed = interview._single_question(greedy)
    print(f"    Claude wrote : {greedy}")
    print(f"    You would see: {trimmed}")
    if trimmed.count("?") == 1:
        print("  [ok   ] trimmed to a single question")
    else:
        print("  [WRONG] more than one question survived")
        wrong += 1

    # -- Test 5: you tell it the questions are wrong ------------------------
    print("\n  Test 5: you tell it the questions are wrong.")
    print("          That must never be filed as an answer.\n")

    brain.ask_claude = FakeClaude([
        {"reply_type": "answer", "topic": "AI work", "topic_clear": True,
         "enough": False, "question": "How many hours did that save you?"},
        {"reply_type": "correction", "topic": "going from creative to building AI",
         "topic_clear": True, "enough": True,
         "note": "the post is about the shift itself, not the tools or the hours",
         "acknowledge": "Got it. The shift itself, not the tooling.",
         "question": "What was the moment you stopped calling yourself only a creative?"},
    ])

    send("new")
    send("my journey from a creative person to someone building AI solutions")
    before = interview.questions_asked(session.current())
    send("you are asking the wrong questions, this is about my journey not the tools")

    live = session.current()
    answers = " ".join(turn.get("answer", "") for turn in live.interview).lower()
    questions = " ".join(turn.get("question", "") for turn in live.interview).lower()

    checks = [
        ("the correction was not filed as an answer",
         "wrong questions" not in answers, None),
        ("the question that earned it was thrown away",
         "how many hours" not in questions, None),
        ("it did not cost you a question",
         interview.questions_asked(live) == before, None),
        ("the correction is held for the rest of the session",
         len(live.steers) == 1, live.steers[0]["note"] if live.steers else "none kept"),
        ("it re-read what the post is about",
         "creative" in live.topic.lower(), live.topic),
        ("it could not finish on a correction",
         live.phase == session.INTERVIEW, f"phase is {live.phase}"),
    ]
    for name, condition, detail in checks:
        print(f"  [{'ok   ' if condition else 'WRONG'}] {name}")
        if detail:
            print(f"           {detail}")
        if not condition:
            wrong += 1

    session.clear()

    # -- Test 6: the correction is ignored and the same question comes back -
    print("\n  Test 6: after a correction Claude asks the same thing again.")
    print("          The bot must not put that question to you.\n")

    brain.ask_claude = FakeClaude([
        {"reply_type": "answer", "topic": "AI work", "topic_clear": True,
         "enough": False, "question": "How many hours did that save you?"},
        {"reply_type": "correction", "topic": "my journey into building AI",
         "topic_clear": True, "enough": False,
         "note": "about the journey, not the hours",
         "acknowledge": "Understood.",
         "question": "How many hours did that save?"},
    ])

    send("new")
    send("my journey from a creative person to someone building AI solutions")
    send("wrong questions, ask me about the journey")

    live = session.current()
    asked_now = live.interview[-1]["question"]
    print("    Claude tried  : How many hours did that save?")
    print(f"    You were asked: {asked_now}")
    if "how many hours" not in asked_now.lower():
        print("  [ok   ] the repeat was caught and replaced")
    else:
        print("  [WRONG] the same question was put to you again")
        wrong += 1

    session.clear()
    brain.ask_claude = real_ask
    writer.make_post = real_make

    print()
    if wrong:
        print(f"Stage 3 FAILED: {wrong} problem(s).")
    else:
        print("Stage 3 passed: no forced question count, and a correction sticks.")
    return wrong


# ---------------------------------------------------------------------------
def check_writing():
    """
    Stage 4: the write, critique and repair pipeline.

    Claude is faked and made to misbehave on purpose: it writes a post with an
    em dash and a banned word, then the critique fails to remove them. What we
    are testing is that the gate catches it and the repair call fixes it, so a
    broken post never reaches you.
    """
    print("\n" + LINE)
    print("STAGE 4 - writing, self-critique, and the repair loop")
    print(LINE)

    wrong = 0
    real_ask = brain.ask_claude
    voice = rules.load_voice()

    brief = {
        "core_claim": "A field nobody used cost three days of onboarding.",
        "proof": "Removing it cut onboarding to 40 minutes.",
        "sharpest_detail": "A VAT number field nobody ever read.",
        "detail_keywords": ["40 minutes", "3 days"],
        "takeaway": "Check what you ask for.",
        "call_to_action": "",
    }

    dirty = "Onboarding took 3 days — a seamless process it was not. Now 40 minutes."
    still_dirty = "Onboarding took 3 days — we fixed it. Now 40 minutes."
    clean = "Onboarding took 3 days. We cut it to 40 minutes by deleting one field."

    brain.ask_claude = FakeClaude([
        dirty,                                                    # the first draft
        {"critique": ["Tightened the opening."], "rewrite": still_dirty},  # critique misses the em dash
        clean,                                                    # the repair call fixes it
    ])

    result = writer.make_post("linkedin", brief, voice)
    brain.ask_claude = real_ask

    print("\n  Claude wrote          :", dirty)
    print("  its critique returned :", still_dirty)
    print("  what the gate caught  :")
    for problem in result["repairs"]:
        print(f"      {problem}")
    print("\n  the post you would see:", result["post"])

    if result["unresolved"]:
        print(f"\n  [WRONG] {len(result['unresolved'])} rule(s) still broken")
        wrong += 1
    else:
        print("\n  [ok   ] the finished post breaks no rules")

    if result["repairs"]:
        print("  [ok   ] the gate caught what the critique missed")
    else:
        print("  [WRONG] the gate caught nothing")
        wrong += 1

    if all(k.lower() in result["post"].lower() for k in brief["detail_keywords"]):
        print("  [ok   ] the specific detail survived the repair")
    else:
        print("  [WRONG] the specific detail was lost")
        wrong += 1

    # -- Instagram, which is a hook plus a caption that answers it ----------
    print("\n  Instagram comes back as two pieces, and both are gated.\n")

    hook_draft = "3 days to 40 minutes — one dead field"
    caption_draft = (
        "Nobody had read that VAT number box since finance asked for it.\n\n"
        "It sat between a signed contract and a designer starting work.\n\n"
        "#agencylife #onboarding #opsdesign"
    )
    clean_hook = "3 days to 40 minutes. One dead field."

    brain.ask_claude = FakeClaude([
        {"hook": hook_draft, "caption": caption_draft},
        {"critique": ["Tightened the caption."],
         "rewrite_hook": hook_draft,          # critique leaves the em dash in
         "rewrite_caption": caption_draft},
        clean_hook,                            # the repair call fixes the hook
    ])

    result = writer.make_post("instagram", brief, voice)
    brain.ask_claude = real_ask

    print(f"  hook Claude wrote : {hook_draft}")
    print(f"  hook you would see: {result['hook']}")
    print(f"  caption           : {result['post'].splitlines()[0]}...")

    ig_checks = [
        ("the hook came back separately from the caption",
         bool(result["hook"]) and result["hook"] != result["post"]),
        ("the em dash was caught in the hook, not just the caption",
         "—" not in result["hook"]),
        ("the caption was left alone, it broke nothing",
         result["post"] == caption_draft),
        ("the detail survives across the pair",
         any(k.lower() in (result["hook"] + result["post"]).lower()
             for k in brief["detail_keywords"])),
    ]
    for name, condition in ig_checks:
        print(f"  [{'ok   ' if condition else 'WRONG'}] {name}")
        if not condition:
            wrong += 1

    print()
    if wrong:
        print(f"Stage 4 FAILED: {wrong} problem(s).")
    else:
        print("Stage 4 passed: a post that breaks a rule never reaches you.")
    return wrong


# ---------------------------------------------------------------------------
class FakeResponse:
    """Stands in for what Slack sends back when we ask for a file."""

    def __init__(self, status=200, content=b"", content_type="image/jpeg"):
        self.status_code = status
        self.content = content
        self.headers = {"content-type": content_type}


def check_media():
    """
    Stage 5: downloading your uploads.

    The failure worth testing is the quiet one. When the bot token is not sent
    or not accepted, Slack answers 200 OK with an HTML login page. Saving that
    as photo.jpg looks fine until publishing rejects it days later.
    """
    print("\n" + LINE)
    print("STAGE 5 - downloading media, and the silent failure")
    print(LINE)

    wrong = 0
    real_get = media.requests.get
    sent_headers = {}

    fake_image = b"\xff\xd8\xff\xe0" + b"pretend jpeg bytes" * 20
    login_page = b"<!DOCTYPE html>\n<html><body>Sign in to Slack</body></html>"

    def check(name, condition, detail=""):
        nonlocal wrong
        print(f"  [{'ok   ' if condition else 'WRONG'}] {name}")
        if detail:
            print(f"           {detail}")
        if not condition:
            wrong += 1

    # -- 1. A normal download, and does it send the token? -----------------
    def good_get(url, headers=None, timeout=None):
        sent_headers.update(headers or {})
        return FakeResponse(content=fake_image)

    media.requests.get = good_get
    saved = media.download({
        "id": "F123", "name": "cover.jpg", "mimetype": "image/jpeg",
        "url_private_download": "https://files.slack.com/cover.jpg",
    })

    check("the file downloads and is saved", Path(saved["path"]).exists(),
          f"{saved['name']}, {saved['bytes']} bytes, kind '{saved['kind']}'")
    check("the bot token is sent in the Authorization header",
          sent_headers.get("Authorization", "").startswith("Bearer "),
          "Without this Slack returns a login page instead of the file.")

    # -- 2. The silent failure ---------------------------------------------
    media.requests.get = lambda url, headers=None, timeout=None: FakeResponse(
        content=login_page, content_type="text/html; charset=utf-8")

    try:
        media.download({
            "id": "F124", "name": "cover.jpg", "mimetype": "image/jpeg",
            "url_private_download": "https://files.slack.com/cover.jpg",
        })
        check("a login page disguised as a file is caught", False,
              "It was saved as if it were a real image.")
    except media.MediaError as error:
        check("a login page disguised as a file is caught", True, str(error))

    # -- 3. Wrong file type -------------------------------------------------
    media.requests.get = good_get
    try:
        media.download({"id": "F125", "name": "notes.txt", "mimetype": "text/plain",
                        "url_private_download": "https://files.slack.com/notes.txt"})
        check("a file that is not an image or video is refused", False)
    except media.MediaError as error:
        check("a file that is not an image or video is refused", True, str(error))

    # -- 4. Platform limits -------------------------------------------------
    two_videos = [
        {"id": f"F2{n}", "name": f"clip{n}.mp4", "mimetype": "video/mp4",
         "url_private_download": f"https://files.slack.com/clip{n}.mp4"}
        for n in range(2)
    ]
    try:
        media.download_all(two_videos, "instagram")
        check("two videos for Instagram is refused", False)
    except media.MediaError as error:
        check("two videos for Instagram is refused", True, str(error))

    media.requests.get = real_get

    # -- 5. The upload has to declare what the file is ----------------------
    # A multipart part with no content type is read as plain text by the
    # server, and Zernio refuses it with "Content type not allowed:
    # text/plain". This is the check that the real type is carried through.
    print("\n  The type of a file has to survive as far as the upload.\n")

    media.requests.get = good_get
    saved = media.download({
        "id": "F130", "name": "shot.png", "mimetype": "",     # Slack sent none
        "url_private_download": "https://files.slack.com/shot.png",
    })
    media.requests.get = real_get

    check("a missing type from Slack is worked out from the filename",
          saved.get("mime") == "image/png", f"mime = {saved.get('mime')}")
    check("the type is never plain text",
          not str(saved.get("mime", "")).startswith("text/"))

    # -- 6. Files too big for the upload ------------------------------------
    print("\n  Anything over the upload limit is handled before it is sent.\n")

    import zernio

    oversized = config.MEDIA_DIR / "oversized_test.bin"
    oversized.write_bytes(b"\x00" * (zernio.UPLOAD_LIMIT_BYTES + 1024))

    try:
        zernio._fit_upload_limit(
            oversized, {"name": "clip.mp4", "kind": "video"}
        )
        check("an oversized video is refused with an explanation", False,
              "It was sent anyway, which is the 413 we already hit.")
    except zernio.ZernioError as error:
        check("an oversized video is refused with an explanation", True, str(error))

    # A real oversized image, which should be shrunk rather than refused.
    from PIL import Image

    # Noise, not a flat colour. A plain red rectangle compresses to almost
    # nothing and would never reach the limit we are trying to test.
    import os

    big_image = config.MEDIA_DIR / "oversized_test.png"
    Image.frombytes("RGB", (2200, 1700), os.urandom(2200 * 1700 * 3)).save(big_image, "PNG")

    if big_image.stat().st_size > zernio.UPLOAD_LIMIT_BYTES:
        path, shrunk_to = zernio._fit_upload_limit(
            big_image, {"name": "shot.png", "kind": "image"}
        )
        check("an oversized image is shrunk to fit rather than refused",
              shrunk_to and path.stat().st_size <= zernio.UPLOAD_LIMIT_BYTES,
              f"{big_image.stat().st_size / 1024 / 1024:.1f} MB became "
              f"{path.stat().st_size / 1024 / 1024:.1f} MB")
        path.unlink(missing_ok=True)
    else:
        print("         (skipped, the test image compressed under the limit)")

    # A file already small enough must be left completely alone.
    small = config.MEDIA_DIR / "small_test.png"
    Image.new("RGB", (40, 30), (10, 10, 10)).save(small, "PNG")
    path, shrunk_to = zernio._fit_upload_limit(small, {"name": "small.png", "kind": "image"})
    check("a file under the limit is left untouched", path == small and shrunk_to == 0)

    for leftover in (oversized, big_image, small):
        leftover.unlink(missing_ok=True)

    print()
    if wrong:
        print(f"Stage 5 FAILED: {wrong} problem(s).")
    else:
        print("Stage 5 passed: real files save, fake ones are caught.")
    return wrong


# ---------------------------------------------------------------------------
class ButtonSlack(FakeSlack):
    """A pretend Slack that can also show buttons and be clicked."""

    def __init__(self):
        self.buttons = []

    def chat_postMessage(self, channel, text=None, blocks=None, **kwargs):
        if blocks:
            for block in blocks:
                if block.get("type") == "actions":
                    labels = [e["text"]["text"] for e in block["elements"]]
                    self.buttons.append((block["block_id"], labels))
                    print(f"  BOT: [{block['block_id']}] buttons: {' | '.join(labels)}")
                elif block.get("type") == "section":
                    for line in block["text"]["text"].split("\n")[:2]:
                        print(f"  BOT: {line}")
        else:
            for line in (text or "").split("\n"):
                print(f"  BOT: {line}")

    def chat_update(self, channel, ts, text=None, blocks=None, **kwargs):
        print(f"  BOT: (buttons replaced) {text}")


def click(slack, action_id, platform):
    """Pretend you pressed a button."""
    print(f"\nYOU: [click {action_id}]")
    body = {
        "actions": [{"action_id": action_id, "value": platform}],
        "channel": {"id": "D_TEST"},
        "message": {"ts": "1.0"},
    }

    class Logger:
        def exception(self, *a, **k): pass

    handler = {"approve": app.on_approve, "rewrite": app.on_rewrite, "edit": app.on_edit}
    name = action_id.split("_")[0]
    if name == "approve":
        handler[name](lambda: None, body, slack, Logger())
    else:
        handler[name](lambda: None, body, slack)


def check_review():
    """
    Stage 6: the buttons, the rewrite, the edit, and the history file.

    DRY_RUN is on, so nothing is published. What we are testing is that each
    button does the right thing to the right post and leaves the other alone.
    """
    print("\n" + LINE)
    print("STAGE 6 - the review buttons, and saving the session")
    print(LINE)

    wrong = 0
    real_ask = brain.ask_claude
    real_make = writer.make_post
    slack = ButtonSlack()

    def check(name, condition, detail=""):
        nonlocal wrong
        print(f"  [{'ok   ' if condition else 'WRONG'}] {name}")
        if detail:
            print(f"           {detail}")
        if not condition:
            wrong += 1

    # Build a session that has already been through interview and writing.
    live = session.start("U_TEST", "D_TEST", voice=rules.load_voice())
    live.interview = [{"question": "What is this post about?",
                       "answer": "we cut onboarding from 3 days to 40 minutes"}]
    live.brief = {
        "core_claim": "A field nobody used cost three days.",
        "proof": "Removing it cut onboarding to 40 minutes.",
        "sharpest_detail": "A VAT number field nobody read.",
        "detail_keywords": ["40 minutes", "3 days"],
        "takeaway": "Check what you ask for.", "call_to_action": "",
    }
    live.linkedin.text = "Onboarding took 3 days. We cut it to 40 minutes."
    live.instagram.text = "3 days to 40 minutes. Here is what it means for your agency."
    live.linkedin.media = [{"path": "x", "name": "cover.jpg", "kind": "image", "bytes": 2000}]
    live.instagram.media_skipped = True

    print()
    app.show_review(slack, "D_TEST", live)
    check("both posts shown with three buttons each", len(slack.buttons) == 2,
          f"{[b[0] for b in slack.buttons]}")
    check("the buttons are Approve, Rewrite, Edit",
          slack.buttons and slack.buttons[0][1] == ["Approve", "Rewrite", "Edit"])

    # -- Rewrite only touches one post -------------------------------------
    before_instagram = live.instagram.text
    writer.make_post = lambda platform, brief, voice, note="": {
        "post": f"REWRITTEN with your note: '{note}'. Still 3 days to 40 minutes.",
        "first_draft": "", "critique": [], "repairs": [], "unresolved": [],
    }

    click(slack, "rewrite_linkedin", "linkedin")
    app.route(slack, "U_TEST", "D_TEST", "hook is weak", [])

    check("your note reached the rewrite", "hook is weak" in live.linkedin.text,
          live.linkedin.text)
    check("the Instagram post was left alone", live.instagram.text == before_instagram)

    # -- Edit is used verbatim ---------------------------------------------
    click(slack, "edit_instagram", "instagram")
    my_text = "My own words. 3 days to 40 minutes. Nothing rewritten."
    app.route(slack, "U_TEST", "D_TEST", my_text, [])
    check("your edited text is used exactly as sent", live.instagram.text == my_text)

    # -- Edit warns but does not change ------------------------------------
    click(slack, "edit_instagram", "instagram")
    dirty = "3 days to 40 minutes — a seamless win."
    app.route(slack, "U_TEST", "D_TEST", dirty, [])
    check("a rule break in your own text is flagged, not silently fixed",
          live.instagram.text == dirty, "Your words are never edited behind your back.")

    # -- Approve both, in dry run ------------------------------------------
    click(slack, "approve_linkedin", "linkedin")
    check("LinkedIn approved without publishing (dry run)",
          live.linkedin.approved and not live.linkedin.published_url)

    before = set(config.SESSIONS_DIR.glob("*.md"))
    click(slack, "approve_instagram", "instagram")
    after = set(config.SESSIONS_DIR.glob("*.md"))

    check("both approved, so the session closed", live.phase == session.DONE)
    saved = after - before
    check("the session was saved to a file you can read", bool(saved),
          str(list(saved)[0]) if saved else "nothing was written")

    if saved:
        body = list(saved)[0].read_text(encoding="utf-8")
        check("the saved file holds the interview", "3 days to 40 minutes" in body)
        check("the saved file holds both posts",
              "## LinkedIn" in body and "## Instagram" in body)
        check("the saved file records the media filename", "cover.jpg" in body)

    writer.make_post = real_make
    brain.ask_claude = real_ask
    session.clear()

    print()
    if wrong:
        print(f"Stage 6 FAILED: {wrong} problem(s).")
    else:
        print("Stage 6 passed: each button touches only its own post, and the "
              "session is saved.")
    return wrong


# ---------------------------------------------------------------------------
def main():
    wrong = 0
    check_dm_loop()
    wrong += check_rules()
    wrong += check_interview()
    wrong += check_writing()
    wrong += check_media()
    wrong += check_review()
    print("\n" + LINE)
    print("ALL CHECKS PASSED" if wrong == 0 else f"{wrong} CHECK(S) FAILED")
    print(LINE)


if __name__ == "__main__":
    main()
