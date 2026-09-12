"""
package.py

Builds the zip file you hand to the next person.

It copies the project into a zip, leaving out your secrets, your saved
sessions, the downloaded media and the installed packages. Before it writes
anything it checks the files for anything that looks like a real key, so you
cannot email your Slack token to someone by accident.

Double-click make-package.bat to run this.
"""

import re
import sys
import zipfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / f"musanif-{date.today():%Y-%m-%d}.zip"

# Folders and files that must never travel to the next person.
SKIP_DIRS = {".venv", ".git", "__pycache__", "sessions", "media_cache"}
SKIP_FILES = {".env"}
SKIP_SUFFIXES = {".pyc", ".zip"}

# What a real key looks like. The .env.example placeholders all end in "...",
# so they never match: a real key has actual characters after the prefix.
KEY_SHAPES = [
    ("Slack bot token", re.compile(r"xoxb-[A-Za-z0-9-]{10,}")),
    ("Slack app token", re.compile(r"xapp-[A-Za-z0-9-]{10,}")),
    ("xAI key", re.compile(r"xai-[A-Za-z0-9]{10,}")),
    ("OpenRouter key", re.compile(r"sk-or-[A-Za-z0-9-]{10,}")),
    ("Zernio key", re.compile(r"sk_[A-Za-z0-9]{20,}")),
]

TEXT_SUFFIXES = {".py", ".md", ".txt", ".bat", ".example", ".json", ".yml", ".yaml",
                 ".toml", ".service", ".cfg", ".ini"}

# Files with no extension that are still worth scanning. fly.toml and the
# deployment files are the risky ones: they are committed to git, and it is
# tempting to paste a key straight into them rather than into secrets.
TEXT_NAMES = {"Dockerfile", ".dockerignore", "Procfile", "Makefile"}


def wanted(path: Path) -> bool:
    """True if this file belongs in the handover zip."""
    if any(part in SKIP_DIRS for part in path.relative_to(HERE).parts):
        return False
    if path.name in SKIP_FILES:
        return False
    if path.suffix in SKIP_SUFFIXES:
        return False
    return True


def leaked_keys(files: list[Path]) -> list[str]:
    """Anything in these files that looks like a real, live key."""
    found = []
    for path in files:
        if path.suffix not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, shape in KEY_SHAPES:
            for hit in shape.findall(body):
                found.append(f"{path.name} looks like it holds a real {label}: {hit[:14]}...")
    return found


def main() -> int:
    files = sorted(p for p in HERE.rglob("*") if p.is_file() and wanted(p))

    if not files:
        print("Found nothing to package. Is package.py in the project folder?")
        return 1

    # The safety check. This is the whole reason this script exists rather
    # than you right-clicking the folder and choosing "Send to > Zip".
    leaks = leaked_keys(files)
    if leaks:
        print("STOPPED. Something in the project looks like a real key:\n")
        for leak in leaks:
            print(f"  * {leak}")
        print(
            "\nKeys belong in .env, which is never packaged. Take the key out "
            "of the file above,\nput it in .env instead, then run this again."
        )
        return 1

    if OUT.exists():
        OUT.unlink()

    # Everything sits inside a "musanif" folder so it unzips tidily instead of
    # spraying files across whatever folder they extracted it into.
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, Path("musanif") / path.relative_to(HERE))

    size = OUT.stat().st_size / 1024
    print(f"Built {OUT.name}  ({size:.0f} KB, {len(files)} files)\n")
    print("Left out, on purpose:")
    print("  .env             your keys")
    print("  .venv            the installed packages, rebuilt by setup.bat")
    print("  sessions/        your saved posts")
    print("  media_cache/     downloaded images\n")
    print("Send that one zip file. Tell them to unzip it and double-click")
    print("setup.bat inside. Nothing else.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
