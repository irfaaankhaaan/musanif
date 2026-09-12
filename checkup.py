"""
checkup.py

Checks everything the bot needs, one item at a time, and tells you exactly
what to fix. Run this whenever something is not working.

Unlike app.py, this finishes and stops instead of running forever, so you can
read the result.

Run it with:  python checkup.py     (or double-click check-setup.bat)
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config

LINE = "-" * 66

# The Slack permissions this bot actually uses, and what each one is for.
NEEDED_SCOPES = {
    "chat:write": "send you messages",
    "im:history": "read the DMs you send it",
    "files:read": "download the images and videos you upload",
}

problems = []


def result(ok, label, detail=""):
    print(f"  [{'ok  ' if ok else 'FAIL'}] {label}")
    if detail:
        for line in detail.split("\n"):
            print(f"         {line}")
    if not ok:
        problems.append(label)


# ---------------------------------------------------------------------------
print(LINE)
print("CHECKUP")
print(LINE)

# 1. The .env file --------------------------------------------------------
print("\n1. Your .env file")
env_problems = config.check_secrets(need_zernio=not config.DRY_RUN)
if env_problems:
    for problem in env_problems:
        result(False, problem)
else:
    result(True, "all the keys the bot needs are filled in")

mode = "DRY RUN, nothing will be published" if config.DRY_RUN else "LIVE, posts go out for real"
print(f"         Mode: {mode}")


# 2. Slack ----------------------------------------------------------------
print("\n2. Slack")
if env_problems:
    print("         Skipped, fix the .env problems above first.")
else:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    slack = WebClient(token=config.SLACK_BOT_TOKEN)
    try:
        who = slack.auth_test()
        result(True, f"signed in as '{who['user']}' in '{who['team']}'")

        # Slack returns the granted permissions in a response header.
        granted = who.headers.get("x-oauth-scopes", "")
        have = {scope.strip() for scope in granted.split(",")}

        for scope, why in NEEDED_SCOPES.items():
            if scope in have:
                result(True, f"permission '{scope}' granted, needed to {why}")
            else:
                result(
                    False,
                    f"permission '{scope}' is MISSING, needed to {why}",
                    "Add it in your Slack app under OAuth & Permissions >\n"
                    "Bot Token Scopes, then click Reinstall to Workspace.\n"
                    "New scopes do nothing until you reinstall.",
                )
    except SlackApiError as error:
        result(
            False,
            f"Slack rejected the bot token: {error.response['error']}",
            "Copy the Bot User OAuth Token again from OAuth & Permissions.",
        )
    except Exception as error:
        result(False, f"could not reach Slack: {error}")


# 3. Grok -----------------------------------------------------------------
print("\n3. Grok")
if any("GROK" in p for p in env_problems):
    print("         Skipped, the key is not filled in yet.")
else:
    import openai

    import brain

    try:
        # A deliberately tiny request. This costs a fraction of a penny (nothing
        # at all on the free tier) and is the only way to know the key works.
        reply = brain.client.chat.completions.create(
            model=config.MODEL,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
        )
        said = (reply.choices[0].message.content or "").strip()
        result(True, f"the API key works and {config.MODEL} replied '{said}'")
    except openai.AuthenticationError:
        result(False, "Grok rejected the API key",
               "Check GROK_API_KEY in .env, from console.x.ai.")
    except openai.PermissionDeniedError:
        result(False, "Grok refused the request",
               "The key is real but the account has no credit, or no access to\n"
               f"'{config.MODEL}'. Check your xAI console.")
    except openai.NotFoundError:
        result(False, f"Grok does not know the model '{config.MODEL}'",
               "Open config.py and update the MODEL line near the top.")
    except Exception as error:
        result(False, f"could not reach Grok at {config.GROK_BASE_URL}: {error}")


# 4. Zernio, the thing that actually publishes ----------------------------
# This is checked even in dry run. It used to be skipped while DRY_RUN was on,
# which meant an unfilled key stayed invisible until the day you tried to
# publish for real. Better to know now.
print("\n4. Zernio, which does the publishing")
if config.DRY_RUN:
    print("         Dry run is on, so nothing here blocks the bot from starting.")

if "..." in config.ZERNIO_API_KEY or len(config.ZERNIO_API_KEY) < 20:
    message = "the Zernio key is not filled in, so publishing cannot work"
    detail = ("It is still the example value from .env.example.\n"
              "Get the real one from your Zernio dashboard, then run\n"
              "edit-secrets.bat and paste it in as ZERNIO_API_KEY.")
    if config.DRY_RUN:
        # Not a failure while nothing is being published, but say it loudly.
        print(f"  [note] {message}")
        for line in detail.split("\n"):
            print(f"         {line}")
    else:
        result(False, message, detail)
else:
    import zernio

    try:
        connected = zernio.accounts()
        if not connected:
            result(False, "the Zernio key works, but no accounts are connected",
                   "Connect LinkedIn and Instagram at zernio.com, then run this again.")
        else:
            for platform in ("linkedin", "instagram"):
                try:
                    zernio.account_id_for(platform)
                    result(True, f"{zernio.name_of(platform)} is connected and active")
                except zernio.ZernioError as error:
                    result(False, f"{zernio.name_of(platform)} is not ready", str(error))
    except zernio.ZernioError as error:
        result(False, "Zernio would not accept the key", str(error))


# 5. Your files -----------------------------------------------------------
print("\n5. Your editable files")
for path, label in [
    (config.VOICE_FILE, "voice.md, your writing rules"),
    (config.PROMPTS_DIR / "interview.md", "prompts/interview.md"),
    (config.PROMPTS_DIR / "brief.md", "prompts/brief.md"),
]:
    result(path.exists(), f"{label} {'found' if path.exists() else 'IS MISSING'}")


# ---------------------------------------------------------------------------
print("\n" + LINE)
if problems:
    print(f"{len(problems)} PROBLEM(S) FOUND. Fix the FAIL lines above.")
else:
    print("EVERYTHING IS READY.")
    print("")
    print("Start the bot with run-bot.bat, then open Slack and DM it the word:")
    print("    new")
    print("")
    print("The bot window will look like it is doing nothing. That is correct.")
    print("It is sitting there waiting for your message.")
print(LINE)
