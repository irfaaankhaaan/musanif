# The bot as a container, so it can live somewhere that is always on.
#
# Socket Mode means the bot dials OUT to Slack and holds the connection open.
# Nothing ever connects in, so this image opens no ports, needs no public
# address, no domain and no certificate.

FROM python:3.12-slim

# Python that behaves itself in a container: no stray .pyc files, and output
# that appears in "docker logs" as it happens rather than in silent bursts.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Requirements first and on their own, so editing a .py file does not make
# Docker reinstall every package on the next build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as somebody other than root. The two folders the bot writes to are
# created here and handed over, so it can still save your sessions.
RUN useradd --create-home --uid 10001 musanif \
    && mkdir -p /app/sessions /app/media_cache \
    && chown -R musanif:musanif /app
USER musanif

# Python installs a handler for SIGINT but not for SIGTERM, and a process
# running as PID 1 ignores any signal it has no handler for. Without this line
# "docker stop" would wait ten seconds and then kill the bot. With it, the bot
# gets a KeyboardInterrupt and stops immediately.
STOPSIGNAL SIGINT

CMD ["python", "-u", "app.py"]
