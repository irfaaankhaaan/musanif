"""
zernio.py

Publishing, through the Zernio API.

Zernio is one API that posts to LinkedIn, Instagram and a dozen other places.
You connect your accounts once on their site, and this file just says "post
this text with this file to this account".

Each platform is published on its own, in its own call, with its own file.
That is deliberate: you approve LinkedIn and Instagram separately, so they go
out separately.

Nothing in here runs while DRY_RUN is on.
"""

import mimetypes
import time
from pathlib import Path

import requests

import config

BASE = "https://zernio.com/api/v1"

# How long to wait for a post to actually go live before we stop watching and
# just hand you the post id. Video takes longer than an image.
PUBLISH_WAIT_SECONDS = 90
POLL_EVERY_SECONDS = 5


# Platform names as they are actually written. Python's .title() turns
# "linkedin" into "Linkedin", which is wrong and looks careless in a tool that
# is all about writing well.
NAMES = {"linkedin": "LinkedIn", "instagram": "Instagram"}


def name_of(platform: str) -> str:
    return NAMES.get(platform, platform.title())


class ZernioError(Exception):
    """A publishing problem, already written in plain language."""


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.ZERNIO_API_KEY}"}


def _call(method: str, path: str, **kwargs) -> dict:
    """One request to Zernio, with the errors turned into plain sentences."""
    try:
        response = requests.request(
            method, f"{BASE}{path}", headers=_headers(), timeout=180, **kwargs
        )
    except requests.RequestException as error:
        raise ZernioError(
            f"Could not reach Zernio. Check your internet connection. ({error})"
        )

    if response.status_code == 401:
        raise ZernioError(
            "Zernio rejected the API key. Check ZERNIO_API_KEY in your .env "
            "file. It should start with 'sk_'."
        )
    if response.status_code == 402:
        raise ZernioError(
            "Zernio says this account is over its plan limit. Check your "
            "Zernio dashboard."
        )
    if response.status_code >= 400:
        detail = ""
        try:
            body = response.json()
            detail = body.get("error") or body.get("message") or ""
        except ValueError:
            detail = response.text[:200]
        raise ZernioError(
            f"Zernio refused the request (error {response.status_code}). {detail}"
        )

    try:
        return response.json()
    except ValueError:
        raise ZernioError("Zernio sent back something I could not read.")


# ---------------------------------------------------------------------------
# Which account to post to
# ---------------------------------------------------------------------------
_accounts_cache: list | None = None


def accounts(refresh: bool = False) -> list:
    """Every social account you have connected to Zernio."""
    global _accounts_cache
    if _accounts_cache is None or refresh:
        result = _call("GET", "/accounts")
        _accounts_cache = result.get("accounts") or []
    return _accounts_cache


def account_id_for(platform: str) -> str:
    """
    The Zernio account id for LinkedIn or Instagram.

    If you have not connected that platform yet, this says so rather than
    failing somewhere confusing later.
    """
    for account in accounts():
        if account.get("platform") == platform and account.get("isActive", True):
            account_id = account.get("_id") or account.get("id")
            if account_id:
                return account_id

    connected = sorted({a.get("platform", "?") for a in accounts()})
    raise ZernioError(
        f"You have no active {name_of(platform)} account connected to Zernio. "
        f"Connected right now: {', '.join(connected) or 'nothing'}. "
        "Connect it at zernio.com, then try again."
    )


# ---------------------------------------------------------------------------
# Getting your file to Zernio
# ---------------------------------------------------------------------------
# Zernio's upload endpoint runs on a serverless function, and those refuse any
# request body over about 4.5 MB. That is a limit on the road, not at Zernio's
# door: go over it and the request dies with a 413 before Zernio ever sees the
# file. We stay under it rather than finding out at publish time.
UPLOAD_LIMIT_BYTES = 4 * 1024 * 1024

# What an oversized image gets re-encoded to. JPEG quality 88 is high enough
# that the difference is not visible in a feed.
JPEG_QUALITY = 88
MIN_JPEG_QUALITY = 60


def _fallback_mime(item: dict) -> str:
    """A content type for a file saved before mime was recorded."""
    guessed, _ = mimetypes.guess_type(item.get("name") or "")
    if guessed:
        return guessed
    return "image/jpeg" if item.get("kind") == "image" else "video/mp4"


def _fit_upload_limit(path: Path, item: dict) -> tuple[Path, int]:
    """
    Make sure this file can actually be uploaded.

    An image that is too big is re-encoded smaller and the shrunk copy is used.
    A video that is too big cannot be fixed here, so it is refused with an
    explanation instead of a 413 from somewhere in the middle of the internet.

    Returns (path to upload, size it was shrunk to, or 0 if untouched).
    """
    size = path.stat().st_size
    if size <= UPLOAD_LIMIT_BYTES:
        return path, 0

    over = size / (1024 * 1024)

    if item.get("kind") != "image":
        raise ZernioError(
            f"'{item['name']}' is {over:.1f} MB, and the upload limit is "
            f"{UPLOAD_LIMIT_BYTES / (1024 * 1024):.0f} MB. I can shrink an "
            "image on the way through, but not a video. Compress or trim the "
            "clip and start a new session with the smaller file."
        )

    try:
        from PIL import Image
    except ImportError:
        raise ZernioError(
            f"'{item['name']}' is {over:.1f} MB, over the "
            f"{UPLOAD_LIMIT_BYTES / (1024 * 1024):.0f} MB upload limit, and I "
            "cannot shrink it because Pillow is not installed. Run "
            "'pip install -r requirements.txt', then try again."
        )

    shrunk = path.with_name(path.stem + "_smaller.jpg")

    try:
        with Image.open(path) as picture:
            # Transparency has to go: JPEG has no alpha channel, and a PNG
            # screenshot with one would otherwise come out with a black
            # background instead of a white one.
            if picture.mode in ("RGBA", "LA", "P"):
                picture = picture.convert("RGBA")
                flat = Image.new("RGB", picture.size, (255, 255, 255))
                flat.paste(picture, mask=picture.split()[-1])
                picture = flat
            else:
                picture = picture.convert("RGB")

            # Quality first, then dimensions. Most oversized files are large
            # PNG screenshots that become small JPEGs without losing a pixel.
            for width_cap in (None, 2560, 1920, 1440):
                working = picture
                if width_cap and picture.width > width_cap:
                    height = round(picture.height * width_cap / picture.width)
                    working = picture.resize((width_cap, height), Image.LANCZOS)

                for quality in range(JPEG_QUALITY, MIN_JPEG_QUALITY - 1, -7):
                    working.save(shrunk, "JPEG", quality=quality, optimize=True)
                    if shrunk.stat().st_size <= UPLOAD_LIMIT_BYTES:
                        return shrunk, shrunk.stat().st_size
    except ZernioError:
        raise
    except Exception as error:
        raise ZernioError(
            f"'{item['name']}' is {over:.1f} MB, over the upload limit, and I "
            f"could not shrink it. ({error}) Save it smaller and try again."
        )

    raise ZernioError(
        f"'{item['name']}' is {over:.1f} MB and would not come down under the "
        f"{UPLOAD_LIMIT_BYTES / (1024 * 1024):.0f} MB upload limit even after "
        "resizing. Save it smaller and start a new session."
    )


def upload(item: dict, notes: list | None = None) -> dict:
    """
    Upload one file and get back a URL Zernio can post from.

    Zernio has two upload routes. The presigned one only accepts images, so a
    video would fail there. This one takes anything, so we use it for both and
    keep a single path through the code.

    Two things here are not optional, and both were learned the hard way:

    1. The content type is declared explicitly. A multipart part with no type
       is treated as text/plain by the receiving server, and Zernio then
       refuses it with "Content type not allowed: text/plain".
    2. The file has to fit inside the upload limit. Zernio's API runs on
       serverless functions with a hard cap on request size, and going over it
       fails with a 413 before Zernio sees the file at all.
    """
    path = Path(item["path"])
    if not path.exists():
        raise ZernioError(
            f"The file '{item['name']}' is no longer on disk. Upload it again "
            "and start a new session."
        )

    original_size = path.stat().st_size
    path, shrunk_to = _fit_upload_limit(path, item)
    mime = "image/jpeg" if shrunk_to else item.get("mime") or _fallback_mime(item)

    if shrunk_to and notes is not None:
        notes.append(
            f"'{item['name']}' was {original_size / 1024 / 1024:.1f} MB, over the "
            f"upload limit, so it went up as a {shrunk_to / 1024 / 1024:.1f} MB "
            "JPEG."
        )

    with path.open("rb") as handle:
        result = _call(
            "POST",
            "/media/upload-direct",
            files={"file": (path.name, handle, mime)},
        )

    url = result.get("url")
    if not url:
        raise ZernioError(f"Zernio accepted '{item['name']}' but sent back no URL.")

    return {
        "type": item["kind"],          # "image" or "video"
        "url": url,
        "filename": result.get("filename") or item["name"],
        "mimeType": result.get("contentType"),
        "size": result.get("size") or item.get("bytes"),
    }


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------
def publish(platform: str, text: str, media_items: list) -> dict:
    """
    Publish one post to one platform, right now.

    Returns {"url": live link or None, "status": ..., "post_id": ...}
    """
    account_id = account_id_for(platform)

    notes: list[str] = []
    uploaded = [upload(item, notes) for item in media_items]

    payload = {
        "content": text,
        "platforms": [{"platform": platform, "accountId": account_id}],
        "publishNow": True,
    }
    if uploaded:
        payload["mediaItems"] = uploaded

    result = _call("POST", "/posts", json=payload)
    post = result.get("post") or {}
    post_id = post.get("_id")

    if not post_id:
        raise ZernioError("Zernio accepted the post but did not give it an id.")

    result = _wait_for_live(post_id, platform)
    result["notes"] = notes
    return result


def _wait_for_live(post_id: str, platform: str) -> dict:
    """
    Watch the post until it is actually published, so we can hand you the real
    link rather than just saying "sent".
    """
    deadline = time.time() + PUBLISH_WAIT_SECONDS
    status = "publishing"

    while time.time() < deadline:
        result = _call("GET", f"/posts/{post_id}")
        post = result.get("post") or result
        status = post.get("status", "")

        for entry in post.get("platforms") or []:
            if entry.get("platform") == platform and entry.get("platformPostUrl"):
                return {
                    "url": entry["platformPostUrl"],
                    "status": status,
                    "post_id": post_id,
                }

        if status == "published":
            # Published, but the link has not appeared yet.
            return {"url": None, "status": status, "post_id": post_id}

        if status in ("failed", "error"):
            raise ZernioError(
                f"Zernio could not publish to {name_of(platform)}. Check the "
                "post in your Zernio dashboard for the reason."
            )

        time.sleep(POLL_EVERY_SECONDS)

    # Still going. Not a failure, just slower than we waited.
    return {"url": None, "status": status or "publishing", "post_id": post_id}


def describe_result(platform: str, result: dict) -> str:
    """A sentence for the chat about where the post ended up."""
    label = name_of(platform)

    if result.get("url"):
        return f"*{label} published.*\n{result['url']}"

    return (
        f"*{label} sent.* Zernio has it and is still publishing "
        f"(status: {result.get('status')}). The link will appear in your "
        f"Zernio dashboard shortly. Post id: `{result.get('post_id')}`"
    )
