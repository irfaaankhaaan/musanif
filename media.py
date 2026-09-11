"""
media.py

Downloads the files you upload to Slack.

The trap this file exists to avoid: a file you upload to Slack is NOT public.
Fetching its URL without the bot token does not fail. Slack answers with
"200 OK" and hands back an HTML login page. If you save that to disk you get a
file called photo.jpg that is actually a web page, and the failure only shows
up later when publishing rejects it.

So every download here does two things: sends the token, and then checks that
what came back is actually a file rather than a login page.
"""

import mimetypes
import re
from pathlib import Path

import requests

import config


class MediaError(Exception):
    """A problem getting your file, already written in plain language."""


# Platform names as they are actually written. Python's .title() turns
# "linkedin" into "Linkedin", which is wrong and looks careless in a tool that
# is all about writing well.
NAMES = {"linkedin": "LinkedIn", "instagram": "Instagram"}


def name_of(platform: str) -> str:
    return NAMES.get(platform, platform.title())


# What each platform can take. From Zernio's per-platform rules.
LIMITS = {
    "linkedin": {"images": 20, "videos": 1},
    "instagram": {"images": 10, "videos": 1},
}


def kind_of(mimetype: str, filename: str) -> str:
    """Is this an image or a video? Anything else we refuse."""
    mimetype = (mimetype or "").lower()
    if mimetype.startswith("image/"):
        return "image"
    if mimetype.startswith("video/"):
        return "video"

    # Slack does not always send a mimetype, so fall back to the extension.
    suffix = Path(filename or "").suffix.lower()
    if suffix in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"):
        return "image"
    if suffix in (".mp4", ".mov", ".m4v", ".webm", ".avi"):
        return "video"

    raise MediaError(
        f"'{filename}' is not an image or a video, so I cannot post it. "
        "Send a jpg, png, mp4 or mov."
    )


def _safe_name(name: str) -> str:
    """Turn a filename into something safe to write to disk."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name or "upload")
    return cleaned[:80] or "upload"


def download(file_info: dict) -> dict:
    """
    Download one file that you uploaded to Slack.

    `file_info` is the entry Slack puts in the message event's "files" list.
    Returns a dictionary describing the saved file.
    """
    name = file_info.get("name") or "upload"
    mimetype = file_info.get("mimetype", "")
    kind = kind_of(mimetype, name)

    # url_private_download is the one that gives us the raw bytes.
    url = file_info.get("url_private_download") or file_info.get("url_private")
    if not url:
        raise MediaError(
            f"Slack did not give me a download link for '{name}'. Try "
            "uploading it again."
        )

    # THE IMPORTANT LINE. Without this header Slack returns a login page
    # instead of your file, and does not report it as an error.
    headers = {"Authorization": f"Bearer {config.SLACK_BOT_TOKEN}"}

    try:
        response = requests.get(url, headers=headers, timeout=120)
    except requests.RequestException as error:
        raise MediaError(
            f"Could not reach Slack to download '{name}'. Check your internet "
            f"connection. ({error})"
        )

    if response.status_code != 200:
        raise MediaError(
            f"Slack refused to give me '{name}' (error {response.status_code}). "
            "The bot may be missing the files:read permission. Check "
            "OAuth & Permissions in your Slack app, then reinstall it."
        )

    body = response.content

    # The silent failure check. A login page is HTML and arrives as 200 OK.
    content_type = response.headers.get("content-type", "").lower()
    looks_like_html = body[:200].lstrip().lower().startswith((b"<!doctype", b"<html"))

    if "text/html" in content_type or looks_like_html:
        raise MediaError(
            f"Slack sent me a login page instead of '{name}'. That means the "
            "bot token was not accepted. Check SLACK_BOT_TOKEN in your .env "
            "and that the bot has the files:read permission."
        )

    if not body:
        raise MediaError(f"'{name}' came back empty. Try uploading it again.")

    path = config.MEDIA_DIR / f"{file_info.get('id', 'file')}_{_safe_name(name)}"
    path.write_bytes(body)

    return {
        "path": str(path),
        "name": name,
        "kind": kind,
        "bytes": len(body),
        # The exact type, kept because the upload has to declare it. A part in
        # a multipart upload with no type declared is treated as plain text by
        # the receiving server, and publishing then rejects the file.
        "mime": mime_of(mimetype, name, kind),
    }


def mime_of(mimetype: str, filename: str, kind: str) -> str:
    """
    The exact content type for a file, doing real work rather than trusting
    Slack, which does not always send one.
    """
    mimetype = (mimetype or "").strip().lower()
    if "/" in mimetype and not mimetype.startswith("text/"):
        return mimetype

    guessed, _ = mimetypes.guess_type(filename or "")
    if guessed:
        return guessed

    return "image/jpeg" if kind == "image" else "video/mp4"


def download_all(files: list, platform: str) -> list[dict]:
    """
    Download every file from one message, and check the platform can take them.
    """
    if not files:
        return []

    saved = [download(one) for one in files]

    images = [item for item in saved if item["kind"] == "image"]
    videos = [item for item in saved if item["kind"] == "video"]
    limits = LIMITS.get(platform, {"images": 10, "videos": 1})

    if videos and images:
        raise MediaError(
            f"You sent both a video and an image for {name_of(platform)}. "
            "Send one or the other, not a mix."
        )
    if len(videos) > limits["videos"]:
        raise MediaError(
            f"{name_of(platform)} takes {limits['videos']} video, you sent "
            f"{len(videos)}."
        )
    if len(images) > limits["images"]:
        raise MediaError(
            f"{name_of(platform)} takes up to {limits['images']} images, you "
            f"sent {len(images)}."
        )

    return saved


def describe(saved: list[dict]) -> str:
    """A readable one-liner about what was attached, for the chat."""
    if not saved:
        return "no media"

    total_mb = sum(item["bytes"] for item in saved) / (1024 * 1024)
    if len(saved) == 1:
        item = saved[0]
        return f"{item['kind']} `{item['name']}` ({total_mb:.1f} MB)"

    kinds = saved[0]["kind"] + "s"
    names = ", ".join(f"`{item['name']}`" for item in saved)
    return f"{len(saved)} {kinds} ({total_mb:.1f} MB): {names}"
