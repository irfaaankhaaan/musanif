"""
app.py

The Slack side of the bot. This file's whole job is:
  1. connect to Slack,
  2. notice when you send a direct message,
  3. work out what that message means given where we are in the session,
  4. hand the real work off to the other files.

Socket Mode means Slack opens a connection TO your laptop. You do not need a
website, a server, or a public URL. Close the terminal and the bot stops.

Run it with:  python app.py
"""

import sys

# Windows terminals default to a codepage that cannot print characters like the
# em dash, and printing one crashes the program. This makes output UTF-8 so a
# stray character in an error message can never take the bot down.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import blocks
import brain
import config
import history
import interview
import media
import rules
import session
import writer
import zernio
from slack_bolt import App

from slack_bolt.adapter.socket_mode import SocketModeHandler

# About "ConnectionResetError [WinError 10054]" in the window.
#
# Slack deliberately recycles the Socket Mode connection every so often. It
# hangs up on us, we reconnect, and Windows reports the hang-up as an error.
# It is noise, not a fault. The bot keeps working through it. You only have a
# real problem if messages stop appearing as "<- you" below.
CONNECTION = "built-in"

# token_verification_enabled=False stops Bolt from calling Slack the moment
# this file is imported. We check the token ourselves in main() instead, so we
# can give you a readable message, and so selftest.py can run with no internet.
app = App(token=config.SLACK_BOT_TOKEN, token_verification_enabled=False)


# ---------------------------------------------------------------------------
# Helper: send a message back into the DM
# ---------------------------------------------------------------------------
def say_to(client, channel: str, text: str) -> None:
    client.chat_postMessage(channel=channel, text=text)
    first_line = text.split("\n")[0]
    print(f"  -> bot: {first_line[:90]}", flush=True)


# You subscribed to the "file_shared" event as well as "message.im". Slack fires
# BOTH when you upload a file. We deliberately handle uploads through the message
# event instead, because that one also carries any caption you typed with the
# file. This empty handler exists only to tell Slack "seen it", so the log stays
# clean and nothing gets processed twice.
@app.event("file_shared")
def ignore_file_shared(event, logger):
    logger.debug("file_shared ignored; uploads are handled via the message event")


# ---------------------------------------------------------------------------
# The one message handler
# ---------------------------------------------------------------------------
# Slack sends us an event for every message in every channel the bot can see.
# We ignore everything that is not a direct message from a human.
@app.event("message")
def handle_message(event, client, logger):
    # Only direct messages. "im" is Slack's name for a one-to-one DM.
    if event.get("channel_type") != "im":
        return

    # Ignore the bot's own messages, and edits/deletes/joins.
    if event.get("bot_id") or event.get("subtype") not in (None, "file_share"):
        return

    user_id = event.get("user", "")
    channel_id = event.get("channel", "")
    text = (event.get("text") or "").strip()
    files = event.get("files") or []

    # Print every message we receive into the bot's window. If you send a DM
    # and nothing appears here, the message never reached the bot, which points
    # at the Slack app settings rather than at the code.
    attached = f" [+{len(files)} file(s)]" if files else ""
    print(f"  <- you: {text}{attached}", flush=True)

    try:
        route(client, user_id, channel_id, text, files)
    except Exception as error:
        # Never show a stack trace in Slack. Log it for me, show plain words to you.
        logger.exception("Unhandled error while handling a message")
        say_to(
            client,
            channel_id,
            "Something went wrong on my side and I had to stop.\n"
            f"The short version: {error}\n"
            "Your session is still here. Type *status* to see where we are, "
            "or *new* to start over.",
        )


# ---------------------------------------------------------------------------
# The router: decides what your message means
# ---------------------------------------------------------------------------
def route(client, user_id: str, channel_id: str, text: str, files: list) -> None:
    lowered = text.lower()
    live = session.current()

    # --- Commands that work at any time -----------------------------------
    if lowered == "new":
        # Your writing rules are read fresh here, at the start of every session.
        # Edit voice.md, type "new", and the output changes. No restart needed.
        live = session.start(user_id, channel_id, voice=rules.load_voice())

        # Record the opening question straight away, so your next message has
        # a question to attach itself to.
        live.interview.append({
            "question": interview.OPENING_QUESTION,
            "answer": "",
            "kind": interview.OPENING,
        })

        say_to(client, channel_id, f"New session started.\n\n{interview.OPENING_QUESTION}")
        return

    if lowered == "cancel":
        session.clear()
        say_to(client, channel_id, "Cancelled. Nothing was saved. Type *new* when you want to go again.")
        return

    if lowered == "status":
        say_to(client, channel_id, describe_status(live))
        return

    if lowered == "brief":
        if live is None:
            say_to(client, channel_id, "No session running. Type *new* to start one.")
        else:
            say_to(client, channel_id, interview.readable_brief(live.brief))
        return

    if lowered in ("help", "?"):
        say_to(client, channel_id, HELP_TEXT)
        return

    # --- Everything else needs a live session ------------------------------
    if live is None:
        say_to(
            client,
            channel_id,
            "No session running right now. Type *new* to start one.",
        )
        return

    if live.phase == session.INTERVIEW:
        # There is no fixed number of questions, so you get a way to end them.
        # It only works during the interview, and only once you have given it
        # something to write from.
        if lowered in ("write", "go", "write it", "just write it", "enough"):
            if not interview.rough_post(live):
                say_to(client, channel_id, "Give me the rough post first, then I can write it.")
                return
            say_to(client, channel_id, "Right, no more questions. Writing both posts now.")
            try:
                live.brief = interview.build_brief(live)
            except brain.BrainError as error:
                say_to(client, channel_id, str(error))
                return
            finish_interview(client, channel_id, live)
            return

        handle_interview_answer(client, channel_id, live, text)
        return

    if live.phase in (session.MEDIA_LINKEDIN, session.MEDIA_INSTAGRAM):
        handle_media(client, channel_id, live, text, files)
        return

    if live.phase == session.REWRITE_NOTE:
        handle_rewrite_note(client, channel_id, live, text)
        return

    if live.phase == session.EDIT_TEXT:
        handle_edit_text(client, channel_id, live, text)
        return

    if live.phase == session.REVIEW:
        say_to(
            client,
            channel_id,
            "Use the buttons under each post: Approve, Rewrite or Edit.",
        )
        return

    if live.phase == session.DONE:
        say_to(client, channel_id, "That session is finished. Type *new* to start another.")
        return

    say_to(client, channel_id, f"I am in the *{live.phase}* phase and not wired up for it yet.")


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------
# Each platform is asked for separately and gets its own files. That is the
# whole point: the LinkedIn image and the Instagram video are different things,
# so they are never shared between the two.
MEDIA_PROMPTS = {
    session.MEDIA_LINKEDIN: (
        "linkedin",
        "Now the *LinkedIn* media. Upload the image or video for the LinkedIn "
        "post, or type *skip* if there is none this time.",
    ),
    session.MEDIA_INSTAGRAM: (
        "instagram",
        "Now the *Instagram* video. Upload it, or type *skip* if there is none "
        "this time.\n_(This is a separate file from the LinkedIn one. The hook "
        "above goes on it, and the caption answers it.)_",
    ),
}


def ask_for_media(client, channel_id: str, live, phase: str) -> None:
    """Move into a media phase and ask for that platform's files."""
    live.phase = phase
    say_to(client, channel_id, MEDIA_PROMPTS[phase][1])


def handle_media(client, channel_id: str, live, text: str, files: list) -> None:
    """Take the upload for whichever platform we are currently asking about."""
    platform, _ = MEDIA_PROMPTS[live.phase]
    label = PLATFORM_LABELS[platform]
    draft = live.draft(platform)

    if text.lower() == "skip":
        draft.media = []
        draft.media_skipped = True
        if platform == "instagram" and not config.DRY_RUN:
            say_to(
                client,
                channel_id,
                "No media for Instagram. Worth knowing: Instagram will not "
                "publish a post without a file, so this one will not go out.",
            )
        else:
            say_to(client, channel_id, f"No media for {label}.")
        next_after_media(client, channel_id, live)
        return

    if not files:
        say_to(
            client,
            channel_id,
            f"I need a file for {label}, or the word *skip*. "
            "Drag the file into this chat and send it.",
        )
        return

    try:
        saved = media.download_all(files, platform)
    except media.MediaError as error:
        say_to(client, channel_id, f"{error}\n\nTry again, or type *skip*.")
        return

    draft.media = saved
    draft.media_skipped = False
    say_to(client, channel_id, f"Got the {label} media: {media.describe(saved)}")
    next_after_media(client, channel_id, live)


def next_after_media(client, channel_id: str, live) -> None:
    """LinkedIn media leads to Instagram media, then to the review."""
    if live.phase == session.MEDIA_LINKEDIN:
        ask_for_media(client, channel_id, live, session.MEDIA_INSTAGRAM)
        return

    show_review(client, channel_id, live)


PLATFORM_LABELS = {"linkedin": "LinkedIn", "instagram": "Instagram"}


def show_review(client, channel_id: str, live, only: str | None = None) -> None:
    """
    Show each post with Approve, Rewrite and Edit under it.

    `only` re-shows a single platform, used after a rewrite or an edit so the
    other post is left alone.
    """
    live.phase = session.REVIEW

    if only is None:
        mode = ("*DRY RUN.* Approving will show you what would be sent, and "
                "publish nothing." if config.DRY_RUN else
                "*LIVE.* Approving publishes for real.")
        say_to(client, channel_id, f"Both posts are ready. {mode}")

    for platform, label in PLATFORM_LABELS.items():
        if only and platform != only:
            continue

        draft = live.draft(platform)
        if not draft.text or draft.approved:
            continue

        media_line = "no media" if draft.media_skipped else media.describe(draft.media)
        client.chat_postMessage(
            channel=channel_id,
            text=f"{label} draft ready for review",   # fallback for notifications
            blocks=blocks.review_message(
                platform, label, draft.text, media_line, draft.hook
            ),
        )
        print(f"  -> bot: [{label} draft with buttons]", flush=True)


# ---------------------------------------------------------------------------
# The three buttons
# ---------------------------------------------------------------------------
def _button(action_id_prefix: str):
    """Register the same handler for both platforms' version of a button."""
    def register(handler):
        for platform in PLATFORM_LABELS:
            app.action(f"{action_id_prefix}_{platform}")(handler)
        return handler
    return register


@_button("approve")
def on_approve(ack, body, client, logger):
    ack()   # Slack needs an answer within 3 seconds or it shows an error
    platform = body["actions"][0]["value"]
    channel_id = body["channel"]["id"]
    live = session.current()

    print(f"  <- you: [Approve {platform}]", flush=True)

    if live is None:
        _retire_dead_buttons(client, body, platform)
        return

    _replace_buttons(client, body, platform, "approved.")

    try:
        publish_one(client, channel_id, live, platform)
    except Exception as error:
        logger.exception("Publishing failed")
        say_to(client, channel_id, f"Publishing {platform} failed. {error}")


@_button("rewrite")
def on_rewrite(ack, body, client):
    ack()
    platform = body["actions"][0]["value"]
    channel_id = body["channel"]["id"]
    live = session.current()

    print(f"  <- you: [Rewrite {platform}]", flush=True)

    if live is None:
        _retire_dead_buttons(client, body, platform)
        return

    _replace_buttons(client, body, platform, "being rewritten.")

    live.phase = session.REWRITE_NOTE
    live.pending_platform = platform
    say_to(
        client,
        channel_id,
        f"What was wrong with the {PLATFORM_LABELS[platform]} one?\n"
        "Say it plainly (\"too long\", \"hook is weak\", \"sounds like AI\"), "
        "or type *go* to just try again.",
    )


@_button("edit")
def on_edit(ack, body, client):
    ack()
    platform = body["actions"][0]["value"]
    channel_id = body["channel"]["id"]
    live = session.current()

    print(f"  <- you: [Edit {platform}]", flush=True)

    if live is None:
        _retire_dead_buttons(client, body, platform)
        return

    _replace_buttons(client, body, platform, "waiting for your version.")

    live.phase = session.EDIT_TEXT
    live.pending_platform = platform
    say_to(
        client,
        channel_id,
        f"Send me the {PLATFORM_LABELS[platform]} "
        + ("caption" if platform == "instagram" else "post")
        + " exactly as you want it. I will use your words as they are and not "
        "rewrite anything."
        + (" The hook stays as it is." if live.draft(platform).hook else ""),
    )


def _retire_dead_buttons(client, body, platform: str) -> None:
    """
    A button from a session that no longer exists.

    This happens whenever the bot is restarted: its memory of the session goes
    with it, but the message is still sitting in your Slack history with live
    looking buttons on it. Pressing one used to just say "that session has
    gone", which is easy to miss when the failure message from the old run is
    right above it. So the buttons are taken away as well, and the message says
    which run it was from.
    """
    say_to(
        client,
        channel_id_of(body),
        "That draft is from an earlier run of the bot, so its buttons no "
        "longer do anything. I have taken them off it.\n\n"
        "Type *new* down here to start a fresh one.",
    )
    _replace_buttons(
        client, body, platform,
        "draft expired. The bot was restarted after this was written.",
    )


def channel_id_of(body) -> str:
    return body["channel"]["id"]


def _replace_buttons(client, body, platform: str, note: str) -> None:
    """
    Swap the buttons for a line of text once you have pressed one, so the same
    post cannot be approved twice by clicking again.
    """
    try:
        client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text=f"{PLATFORM_LABELS[platform]} {note}",
            blocks=blocks.settled_message(PLATFORM_LABELS[platform], note),
        )
    except Exception:
        pass   # Losing the button swap is cosmetic, never worth an error


# ---------------------------------------------------------------------------
# Rewrite and edit replies
# ---------------------------------------------------------------------------
def handle_rewrite_note(client, channel_id: str, live, text: str) -> None:
    """Your note about what was wrong. Rewrites that ONE post."""
    platform = live.pending_platform
    label = PLATFORM_LABELS[platform]
    note = "" if text.lower() in ("go", "skip", "just try again") else text

    say_to(client, channel_id, f"Rewriting the {label} post...")

    try:
        result = writer.make_post(platform, live.brief, live.voice, note=note)
    except brain.BrainError as error:
        say_to(client, channel_id, f"The rewrite failed. {error}")
        show_review(client, channel_id, live, only=platform)
        return

    draft = live.draft(platform)
    draft.text = result["post"]
    draft.hook = result.get("hook", "")
    draft.critique = result["critique"]
    draft.repairs = result["repairs"]

    live.pending_platform = None
    show_review(client, channel_id, live, only=platform)


def handle_edit_text(client, channel_id: str, live, text: str) -> None:
    """
    Your corrected text. Used exactly as sent.

    We still run it past the rules, but only to tell you. Your words are not
    changed, because you asked for exactly this text.
    """
    platform = live.pending_platform
    label = PLATFORM_LABELS[platform]

    if not text:
        say_to(client, channel_id, f"Send me the {label} text you want to use.")
        return

    draft = live.draft(platform)
    draft.text = text
    draft.critique = ["You supplied this text yourself. Nothing was rewritten."]
    draft.repairs = []

    problems = rules.check(text, live.voice, platform, live.brief.get("detail_keywords"))
    if problems:
        listed = "\n".join(f"  - {p}" for p in problems)
        say_to(
            client,
            channel_id,
            f"Using your {label} text exactly as sent. Worth knowing:\n{listed}\n"
            "I have not changed anything.",
        )
    else:
        say_to(client, channel_id, f"Using your {label} text exactly as sent.")

    live.pending_platform = None
    show_review(client, channel_id, live, only=platform)


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------
def publish_one(client, channel_id: str, live, platform: str) -> None:
    """Publish one platform with its own media, or show what would go out."""
    label = PLATFORM_LABELS[platform]
    draft = live.draft(platform)
    draft.approved = True

    if config.DRY_RUN:
        attached = "no media" if draft.media_skipped else media.describe(draft.media)
        say_to(
            client,
            channel_id,
            f"*DRY RUN, nothing was published.*\nThis is what would have gone "
            f"to {label}, with {attached}:\n\n"
            + (f"_Hook, on the media:_ {draft.hook}\n\n" if draft.hook else "")
            + draft.text,
        )
        finish_if_done(client, channel_id, live)
        return

    # Instagram will not accept a post with no media, and now that the hook
    # lives on the image there would be nothing to read without one. Catch it
    # here, in plain words, rather than letting it fail inside the API.
    if platform == "instagram" and not draft.media:
        draft.approved = False
        say_to(
            client,
            channel_id,
            "Instagram will not take a post with no media, and the hook is "
            "meant to go on the image or video.\n\n"
            "Approve LinkedIn on its own if you want that one out, then type "
            "*new* and give it a file at the Instagram step.",
        )
        show_review(client, channel_id, live, only=platform)
        return

    say_to(client, channel_id, f"Publishing to {label}...")

    try:
        result = zernio.publish(platform, draft.text, draft.media)
    except zernio.ZernioError as error:
        draft.approved = False
        say_to(
            client,
            channel_id,
            f"{label} did not publish.\n{error}\n\n"
            "The post is still here. Fix the problem and press Approve again.",
        )
        show_review(client, channel_id, live, only=platform)
        return

    draft.published_url = result.get("url")

    # If a file had to be changed to get it uploaded, say so. You should never
    # find out that your image went out as a smaller JPEG by noticing later.
    for note in result.get("notes", []):
        say_to(client, channel_id, note)

    say_to(client, channel_id, zernio.describe_result(platform, result))
    finish_if_done(client, channel_id, live)


def finish_if_done(client, channel_id: str, live) -> None:
    """When both platforms are settled, save the session and close it."""
    if not all(live.draft(p).approved for p in PLATFORM_LABELS):
        return

    live.phase = session.DONE

    try:
        path = history.save(live)
        say_to(
            client,
            channel_id,
            f"Done. Saved to `{path}`.\n\nType *new* when you want to go again.",
        )
    except Exception as error:
        say_to(
            client,
            channel_id,
            f"Done. I could not write the history file though: {error}\n\n"
            "Type *new* when you want to go again.",
        )


# ---------------------------------------------------------------------------
# The interview
# ---------------------------------------------------------------------------
def handle_interview_answer(client, channel_id: str, live, text: str) -> None:
    """
    Work out what your message was, then either ask the next question or move
    on to the writing.

    Your message is not assumed to be an answer. It might be you telling the
    bot that the questions are wrong, and that is handled completely
    differently: it is never filed as material for the post.
    """
    if not text:
        say_to(client, channel_id, "I did not catch that. Say it again?")
        return

    try:
        step = interview.respond(live, text)
    except brain.BrainError as error:
        say_to(client, channel_id, str(error))
        return

    # --- You told it the question was wrong -------------------------------
    if step.kind == "correction":
        # The rejected question is thrown away rather than answered. It leaves
        # nothing behind in the interview, so it cannot end up in the post, and
        # it costs you nothing out of the question budget.
        pending = live.interview[-1]
        if pending.get("kind") == interview.OPENING:
            live.interview.append(
                {"question": step.question, "answer": "", "kind": step.turn_kind}
            )
        else:
            pending["question"] = step.question
            pending["answer"] = ""
            pending["kind"] = step.turn_kind

        say_to(client, channel_id, f"{step.acknowledge}\n\n{step.question}")
        return

    # --- It was an answer, so file it against the question we asked --------
    live.interview[-1]["answer"] = text

    if step.kind == "question":
        live.interview.append(
            {"question": step.question, "answer": "", "kind": step.turn_kind}
        )
        say_to(client, channel_id, step.question)
        return

    # The interview is over. Build the brief, then hand off to the writing.
    say_to(client, channel_id, "That is what I needed. Writing both posts now.")

    try:
        live.brief = interview.build_brief(live)
    except brain.BrainError as error:
        say_to(client, channel_id, str(error))
        return

    finish_interview(client, channel_id, live)


def finish_interview(client, channel_id: str, live) -> None:
    """
    The writing stage. Each platform gets its own prompt, its own Claude call,
    and its own self-critique. Neither post can see the other one.
    """
    # Move off the interview phase, otherwise your next message would be read
    # as another interview answer and the brief would be built all over again.
    live.phase = session.DONE

    for platform, label in (("linkedin", "LinkedIn"), ("instagram", "Instagram")):
        say_to(client, channel_id, f"Writing the {label} post...")

        try:
            result = writer.make_post(platform, live.brief, live.voice)
        except brain.BrainError as error:
            say_to(client, channel_id, f"The {label} post failed. {error}")
            continue

        draft = live.draft(platform)
        draft.text = result["post"]
        draft.hook = result.get("hook", "")

        # The critique and any repairs are kept for the session history. You
        # see the finished post only.
        draft.critique = result["critique"]
        draft.repairs = result["repairs"]

        if draft.hook:
            say_to(
                client,
                channel_id,
                f"*{label}*\n\n_Hook, goes on the image or video:_\n{draft.hook}"
                f"\n\n_Caption, which answers it:_\n{result['post']}",
            )
        else:
            say_to(client, channel_id, f"*{label}*\n\n{result['post']}")

        # If a rule survived every repair attempt, say so rather than quietly
        # hand you a post that breaks it.
        if result["unresolved"]:
            problems = "\n".join(f"  - {p}" for p in result["unresolved"])
            say_to(
                client,
                channel_id,
                f"Heads up on the {label} post, I could not fix these:\n{problems}\n"
                "Everything else passed.",
            )

    # Both posts written. Now ask for each platform's media, one at a time.
    ask_for_media(client, channel_id, live, session.MEDIA_LINKEDIN)


# ---------------------------------------------------------------------------
# Small text helpers
# ---------------------------------------------------------------------------
HELP_TEXT = (
    "*What I do*\n"
    "You send me the post, roughly, however messy. I ask about the parts that "
    "need it, then write a LinkedIn post and an Instagram hook and caption from "
    "it, and publish both.\n\n"
    "The Instagram hook goes on your image or video. The caption is the answer "
    "to it.\n\n"
    "*Commands*\n"
    "• *new* - start a session\n"
    "• *write* - stop the questions, write it now\n"
    "• *status* - where are we\n"
    "• *brief* - show the internal content brief\n"
    "• *cancel* - throw this session away\n"
    "• *skip* - no media for this platform\n\n"
    "There is no set number of questions. If one is off, just say so: "
    "_\"wrong question, this is about X\"_.\n"
)


def describe_status(live) -> str:
    if live is None:
        return "Nothing running. Type *new* to start."

    readable = {
        session.INTERVIEW: "interviewing you",
        session.MEDIA_LINKEDIN: "waiting for LinkedIn media",
        session.MEDIA_INSTAGRAM: "waiting for the Instagram video",
        session.REVIEW: "waiting for you to approve, rewrite or edit",
        session.REWRITE_NOTE: "waiting for your note on what was wrong",
        session.EDIT_TEXT: "waiting for your corrected text",
        session.DONE: "finished",
    }.get(live.phase, live.phase)

    mode = "DRY RUN (nothing gets published)" if config.DRY_RUN else "LIVE (posts go out for real)"
    return (
        f"Currently: {readable}\n"
        f"Started: {live.started_at}\n"
        f"Interview answers so far: {len(live.interview)}\n"
        f"Mode: {mode}"
    )


# ---------------------------------------------------------------------------
# Start up
# ---------------------------------------------------------------------------
def main() -> None:
    problems = config.check_secrets(need_zernio=not config.DRY_RUN)
    if problems:
        print("I cannot start. Here is what needs fixing in your .env file:\n")
        for problem in problems:
            print(f"  - {problem}")
        raise SystemExit(1)

    # Ask Slack who we are. This is the real proof the token works.
    try:
        me = app.client.auth_test()
        print(f"Signed in to Slack as '{me['user']}' in workspace '{me['team']}'.")
    except Exception as error:
        print("Slack would not accept the bot token.")
        print(f"  Slack said: {error}")
        print("  Check SLACK_BOT_TOKEN in your .env, then reinstall the app to your workspace.")
        raise SystemExit(1)

    mode = "DRY RUN - nothing will be published" if config.DRY_RUN else "LIVE - posts will really go out"
    print(f"Content agent starting. Mode: {mode}")
    print(f"Model: {config.MODEL}")
    print(f"Connection: {CONNECTION}")
    print("Connecting to Slack... (press Ctrl+C to stop)")
    print("")
    print("Once you see 'Bolt app is running!', DM the bot the word: new")
    print("Every message you send will show below as '<- you'.")
    print("If nothing shows there, the message never reached the bot.")
    print("-" * 60)

    SocketModeHandler(app, config.SLACK_APP_TOKEN).start()


if __name__ == "__main__":
    main()
