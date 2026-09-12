# Content Engine

A Slack bot you send a rough post to. It asks about the parts that need it,
then writes a finished LinkedIn post, plus an Instagram hook for your image and
a caption that answers it, and publishes both.

You talk to it in a direct message. It runs on your laptop.

---

## One-time setup

### 1. Run the installer

Double-click **`setup.bat`**.

It finds Python, installs everything into a `.venv` folder inside this one
(nothing is installed into the rest of your computer), creates your `.env`
secrets file, opens it for you, and then checks the whole setup and tells you
what is still missing.

If it says Python is not installed, get it from
<https://python.org/downloads> and **tick "Add python.exe to PATH"** on the
first screen of the installer. That box is easy to miss and nothing works
without it. Then run `setup.bat` again.

> Prefer to do it by hand? `pip install -r requirements.txt` still works, and
> the other `.bat` files fall back to your system Python if there is no
> `.venv` folder.

### 2. Create the Slack app

Go to <https://api.slack.com/apps> and click **Create New App** > **From scratch**.
Name it whatever you like. Pick your workspace.

Then, in the left sidebar:

**Socket Mode**
- Turn **Enable Socket Mode** on.
- It will ask you to make an app-level token. Name it `socket`, give it the
  `connections:write` scope, and click Generate.
- Copy the token that starts with `xapp-`. That is your `SLACK_APP_TOKEN`.

**OAuth & Permissions** > *Bot Token Scopes*, add these five:

| Scope | Why it is needed |
|---|---|
| `chat:write` | to send you messages |
| `im:history` | to read your DMs to it |
| `im:read` | to see the DM channel |
| `im:write` | to open the DM |
| `files:read` | to download the images and videos you upload |

**Event Subscriptions**
- Turn events on.
- Under *Subscribe to bot events*, add **`message.im`**. That is the one that
  makes DMs arrive.

**App Home**
- Scroll to *Show Tabs* and tick **Allow users to send Slash commands and
  messages from the messages tab**. Without this the message box in the DM is
  greyed out.

**Install App**
- Click **Install to Workspace** and approve.
- Copy the **Bot User OAuth Token** that starts with `xoxb-`. That is your
  `SLACK_BOT_TOKEN`.

> If you change scopes later, you must reinstall the app for them to take effect.

### 3. Fill in your secrets

Open the `.env` file in this folder and paste in your four keys.

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
GROK_API_KEY=xai-...
ZERNIO_API_KEY=sk_...
DRY_RUN=true
```

The writing is done by **Grok**, xAI's model. Get the key from
**console.x.ai > API keys**; it starts with `xai-`.

If you would rather not pay at all, OpenRouter serves a free Grok. Get a key
from **openrouter.ai/keys** (it starts with `sk-or-`), paste it in as
`GROK_API_KEY`, and add these two lines to `.env` as well:

```
GROK_BASE_URL=https://openrouter.ai/api/v1
GROK_MODEL=x-ai/grok-4-fast:free
```

The free tier is rate limited, so the bot may occasionally ask you to wait a
minute and send your message again. Nothing else changes.

`DRY_RUN=true` means the bot does all the work and shows you the posts but
publishes nothing. Leave it on until you trust it.

---

## Running it

**Do not double-click the `.py` files.** Windows runs them, then closes the
window instantly, so you never get to read what happened. Use these instead.
Double-clicking them is fine, they keep the window open.

| Double-click this | What it does |
|---|---|
| `setup.bat` | **first time only.** Installs everything and sets up your keys |
| `edit-secrets.bat` | opens your `.env` in Notepad so you can paste your keys in |
| `check-setup.bat` | checks every part of the setup and says what to fix |
| `run-selftest.bat` | runs the offline checks. Connects to nothing, spends nothing |
| `run-bot.bat` | starts the bot for real |
| `make-package.bat` | builds the zip you hand to the next person |

> **A running bot looks like it is doing nothing.** After it prints
> `Bolt app is running!` the window sits still and stays blank. That is correct.
> It is waiting for you to message it in Slack. Nothing else will appear in that
> window until you do.

Once `run-bot.bat` is running, leave that black window open. Open Slack, find
the app under **Apps** in the sidebar, and DM it.

To stop the bot, close the window or press `Ctrl+C` in it.

If you prefer a terminal, the same three are `python app.py` and
`python selftest.py`.

---

## If the message box in the bot DM is greyed out

Slack disables the message box on a bot DM by default. It is one checkbox.

1. <https://api.slack.com/apps> and open your app
2. Left sidebar > **App Home**
3. Scroll to **Show Tabs**
4. Under **Messages Tab**, tick **Allow users to send Slash commands and
   messages from the messages tab**
5. **Fully quit Slack and reopen it.** Right-click the Slack icon in the system
   tray and Quit. Closing the window is not enough, the box stays greyed out
   until the app reloads.

No reinstall is needed for this one.

## Talking to it

| You type | What happens |
|---|---|
| `new` | starts a session, then asks you for the rough post |
| `write` | stops the questions and writes both posts now |
| `status` | tells you which phase we are in |
| `brief` | shows the internal content brief it wrote |
| `copy` | re-sends each post on its own, ready to copy on a phone |
| `skip` | no media for the platform it is currently asking about |
| `cancel` | throws the session away |
| `help` | the command list |

### Your first message is the post, not a topic

Send it rough. As long, as messy, as unstructured as you like. That is the
material both posts are built from, and your own lines and phrasing are carried
through rather than replaced with something smoother.

Everything it asks after that is only refining what you already wrote: the gap
a reader would fall into, the claim with nothing behind it, the vague phrase
with a specific one hiding in it.

### There is no set number of questions

A draft that arrives nearly finished might get one question. A thin one gets
more. It stops when more questions would stop improving the post.

If you have had enough, type **`write`** and it goes straight to writing.

### If it asks you a bad question, say so

Mid-interview, in your own words:

> you are asking the wrong questions, this is about my journey, not the tools

That is not filed as an answer, so it never ends up in the post. The question
that earned it is thrown away. It changes tack, and every question after that
one still respects what you said.

It does not need a number. If nothing you said contained one, neither post will
invent one.

### Instagram comes back as two pieces

- **The hook** goes on your image or video, set in type. Short, three to twelve
  words, and it opens a gap.
- **The caption** is the answer to that hook. It never repeats it. Someone
  reads the hook on the image, taps for the rest, and the caption pays it off.

Both are shown to you together, and Approve covers the pair. LinkedIn is
unchanged: one post, with its hook in the first line as always.

---

## Using it from your phone

There is nothing to install. The bot lives inside Slack, so it is already on
the Slack app on your iPhone or Android: open Slack, find the app under **Apps**
in the sidebar, and DM it exactly as you would on a laptop. Same conversation,
same buttons, same session. Start on your laptop and finish on your phone if
you like.

Uploading a photo works too. Tap the **+** next to the message box, pick the
image, and send it at the step where the bot asks for media.

**Copying the finished post out.** On a phone you copy a message by
long-pressing it and tapping *Copy Text*, which takes the whole message. So
every finished post is sent on its own, with no heading above it and no word
count below, and pasting it into LinkedIn gives you exactly the post with
nothing to tidy up. Type **`copy`** at any time to have them re-sent that way.

**By default the bot only runs while your laptop is running it.**
`run-bot.bat` has to be open, and the laptop awake and online. If it is asleep
in a bag, messages you send from your phone sit in Slack unanswered until you
open the laptop again, and then they all arrive at once.

To fix that, move the bot somewhere that stays on. **[DEPLOY.md](DEPLOY.md)**
covers three routes, all using the code as it is: Docker Compose on a machine
you own, Fly.io if you have none, or systemd on a Linux VPS.

Socket Mode makes this unusually painless. The bot dials out to Slack and
nothing dials in, so there is no public address to buy, no domain, no
certificate and no open port.

---

## Giving it to someone else

Double-click **`make-package.bat`**. It builds a dated zip file, for example
`musanif-2026-09-12.zip`, that holds everything the next person needs and
nothing they should not have.

Left out of the zip: your `.env` keys, your saved `sessions/`, the downloaded
`media_cache/`, and the installed `.venv` packages (they get rebuilt by
`setup.bat` on the other machine).

Before it writes the zip it scans every file for anything shaped like a real
Slack, xAI, OpenRouter or Zernio key, and refuses to build if it finds one.
That is the reason to use it instead of right-clicking the folder and choosing
*Send to > Compressed folder*, which would package your `.env` along with
everything else.

Send them the one zip file. They unzip it, read `START-HERE.txt`, and
double-click `setup.bat`. They will need their own four keys: the Slack app
has to be created in their own workspace, and keys are per-person.

---

## The files

| File | What it is |
|---|---|
| `START-HERE.txt` | the short version of this file, for whoever you hand it to |
| `DEPLOY.md` | how to keep the bot running always, so your phone gets answers |
| `Dockerfile`, `docker-compose.yml` | run it in a container on an always-on machine |
| `fly.toml`, `musanif.service` | the Fly.io and systemd versions of the same thing |
| `setup.bat` | **run this first.** Installs everything, sets up your keys |
| `make-package.bat` | builds the zip you hand to the next person, minus your keys |
| `app.py` | the Slack connection and the router that reads your messages |
| `config.py` | **every setting and secret.** The Grok model name lives here |
| `session.py` | the bot's memory of where you are in the conversation |
| `rules.py` | the gate. Checks every draft against `voice.md` before you see it |
| `selftest.py` | runs the logic offline so you can watch it work |
| `content-rules.md` | your original rules doc, kept as reference. The bot reads `voice.md` |
| `voice.md` | **your writing rules.** Edit this to change the output |
| `prompts/` | **the four instruction files** for writing and self-critique |
| `sessions/` | every finished session, saved so you can look back |
| `.env` | your secret keys. Never share this file |

The two files you will actually edit are `voice.md` and the four files in
`prompts/`. Neither is code. Change them, restart the bot, and the writing
changes.
