# Keeping the bot always on

By default the bot runs on your laptop and stops when you close the window.
This file is about moving it somewhere that stays on, so you can message it
from your phone at midnight and get an answer.

## What makes this easy

The bot uses Slack **Socket Mode**, which means it dials out to Slack and
holds the connection open. Nothing ever connects in.

So there is no public web address to buy, no domain, no HTTPS certificate, no
firewall rule and no open port. It works from behind a home router untouched.
Anything that can run Python and reach the internet can host this.

## Which route

| You have | Use | Cost |
|---|---|---|
| An old laptop, a Pi, a home server | **Docker Compose**, below | nothing |
| Nothing spare, want it hosted | **Fly.io**, below | a few dollars a month |
| A Linux VPS already | **systemd**, below | whatever the VPS costs |

All three run the same code. None needs a change to the bot.

---

## Route A: a machine you own, with Docker

The simplest option if you have any computer that stays on. Install Docker
Desktop (Windows, Mac) or Docker Engine (Linux), then, in the project folder:

```
docker compose up -d --build
```

That is it. The bot starts, and `restart: unless-stopped` in
`docker-compose.yml` brings it back if it crashes or the machine reboots.

```
docker compose logs -f      watch what it is doing
docker compose restart      restart, after editing voice.md
docker compose down         stop it for good
```

Your keys come from the `.env` file next to `docker-compose.yml`. That file is
listed in `.dockerignore`, so it is never baked into the image; it is handed to
the container when it starts.

Your saved sessions live in a Docker volume so they survive rebuilds. To copy
them out where you can read them:

```
docker compose cp musanif:/app/sessions ./sessions
```

## Route B: Fly.io

For when you have no machine of your own that stays on. `fly.toml` is already
written and deliberately has no `[http_service]` section, because the bot needs
no public address. That also stops Fly from auto-sleeping the machine between
messages, which would defeat the point.

Install `flyctl`, then:

```
fly launch --no-deploy --copy-config --name musanif
fly volumes create musanif_sessions --size 1
fly secrets set SLACK_BOT_TOKEN=xoxb-... SLACK_APP_TOKEN=xapp-... \
                GROK_API_KEY=xai-... ZERNIO_API_KEY=sk_...
fly deploy
```

Keys go in `fly secrets`, never in `fly.toml` — that file is committed to git.

```
fly logs         watch it
fly status       is it up
fly deploy       push a change
```

Change `primary_region` in `fly.toml` to somewhere near you: `iad`, `sjc`,
`fra`, `sin`, `syd`.

## Route C: a Linux VPS, no Docker

`musanif.service` is a systemd unit, ready to use. It assumes the project is at
`/opt/musanif`, owned by a user called `musanif`, with its virtualenv built:

```
sudo useradd --system --home /opt/musanif musanif
sudo git clone https://github.com/irfaaankhaaan/musanif /opt/musanif
sudo chown -R musanif:musanif /opt/musanif
sudo -u musanif python3 -m venv /opt/musanif/.venv
sudo -u musanif /opt/musanif/.venv/bin/pip install -r /opt/musanif/requirements.txt
```

Put your keys in `/opt/musanif/.env`, then:

```
sudo cp /opt/musanif/musanif.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now musanif
journalctl -u musanif -f
```

`Restart=always` handles crashes; `enable` handles reboots.

---

## Things to know once it is hosted

**Turn publishing on deliberately.** Every route ships with `DRY_RUN=true`, so
the bot writes posts and publishes nothing. Change it only when you trust it:
edit `.env` and restart (Routes A and C), or `fly secrets set DRY_RUN=false`
(Route B).

**A restart loses the session you are in the middle of.** The interview lives
in memory, not on disk. If the bot restarts while you are halfway through
answering questions, your next message gets *"No session running"* and you
start again with `new`. Finished sessions are already saved and are not
affected. In practice this only happens when you deploy an update.

**Editing `voice.md` needs a restart.** The file is read when a session starts,
but the container holds its own copy of it. Change it, then
`docker compose up -d --build` or `fly deploy`.

**Watch the logs the first time.** Every message you send appears as `<- you`.
If it does not appear there, the message never reached the bot, and the problem
is the Slack app rather than the code.

**Nobody else can talk to it.** The bot only answers direct messages, and only
in the workspace its tokens belong to. Hosting it does not put it on the
internet for strangers — there is no address to reach it on.

**Cost.** Grok is the only thing you pay per use, and OpenRouter's free tier
covers light use. Route A costs nothing but electricity. Route B is a few
dollars a month for the smallest machine and a 1 GB volume.
