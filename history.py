"""
history.py

Saves every finished session to a file you can read.

Two files per session, in the sessions folder:

  2026-09-05_2140.md    for reading. The interview, both posts, what changed.
  2026-09-05_2140.json  for machines, in case you ever want to search them.

The markdown one is the point. It keeps the interview next to the post it
produced, and it includes what the self-critique caught, which you never see
in Slack. That is the record worth looking back at.
"""

import json
from datetime import datetime

import config


def _free_stamp() -> str:
    """
    A name no saved session is already using.

    Session files are named by the minute, which reads well. Two sessions
    finished inside the same minute would land on the same name, and the first
    one would be overwritten without a word. The second gets a suffix instead.
    """
    base = datetime.now().strftime("%Y-%m-%d_%H%M")
    stamp, attempt = base, 2
    while (
        (config.SESSIONS_DIR / f"{stamp}.md").exists()
        or (config.SESSIONS_DIR / f"{stamp}.json").exists()
    ):
        stamp = f"{base}-{attempt}"
        attempt += 1
    return stamp


def save(live) -> str:
    """Write the session to disk. Returns the path of the readable file."""
    stamp = _free_stamp()
    md_path = config.SESSIONS_DIR / f"{stamp}.md"
    json_path = config.SESSIONS_DIR / f"{stamp}.json"

    md_path.write_text(_as_markdown(live, stamp), encoding="utf-8")
    json_path.write_text(_as_json(live, stamp), encoding="utf-8")

    return str(md_path)


def _as_markdown(live, stamp: str) -> str:
    lines = [f"# Session {stamp}", ""]

    mode = "DRY RUN, nothing was published" if config.DRY_RUN else "Live"
    lines += [f"Started: {live.started_at}", f"Mode: {mode}", ""]

    # ---- the interview ----------------------------------------------------
    lines += ["## The interview", ""]
    if live.topic:
        lines += [f"_What it understood the post to be about: {live.topic}_", ""]
    for turn in live.interview:
        if not turn.get("answer"):
            continue
        lines += [f"**Q:** {turn['question']}", "", f"{turn['answer']}", ""]

    # ---- questions you rejected -------------------------------------------
    # Worth keeping. If the bot keeps earning corrections in the same place,
    # this is the record that shows you where, so you can fix the prompt.
    if live.steers:
        lines += ["## Where you corrected it", ""]
        for steer in live.steers:
            lines += [
                f"**It asked:** {steer.get('rejected', '')}",
                "",
                f"**You said:** {steer.get('said', '')}",
                "",
                f"**It took that as:** {steer.get('note', '')}",
                "",
            ]

    # ---- the brief --------------------------------------------------------
    brief = live.brief or {}
    lines += ["## The brief", ""]
    for field, label in [
        ("core_claim", "Claim"),
        ("proof", "Proof"),
        ("sharpest_detail", "Sharpest detail"),
        ("takeaway", "Takeaway"),
        ("call_to_action", "Call to action"),
    ]:
        if brief.get(field):
            lines.append(f"- **{label}:** {brief[field]}")
    if brief.get("detail_keywords"):
        keywords = ", ".join(f"`{k}`" for k in brief["detail_keywords"])
        lines.append(f"- **Had to appear in both posts:** {keywords}")
    lines.append("")

    # ---- the posts --------------------------------------------------------
    for platform, label in (("linkedin", "LinkedIn"), ("instagram", "Instagram")):
        draft = live.draft(platform)
        lines += [f"## {label}", ""]

        if not draft.text:
            lines += ["_Not written._", ""]
            continue

        if draft.hook:
            lines += ["Hook, which goes on the media:", "",
                      "```", draft.hook, "```", "",
                      "Caption, which answers it:", ""]

        lines += ["```", draft.text, "```", ""]

        if draft.media:
            for item in draft.media:
                size_mb = item["bytes"] / (1024 * 1024)
                lines.append(f"- Media: `{item['name']}` ({item['kind']}, {size_mb:.1f} MB)")
        else:
            lines.append("- Media: none")

        if draft.published_url:
            lines.append(f"- Published: {draft.published_url}")
        elif draft.approved:
            lines.append("- Approved" + (" (dry run, not published)" if config.DRY_RUN else ""))
        else:
            lines.append("- Not approved")
        lines.append("")

        if draft.critique:
            lines += ["What the self-critique changed:", ""]
            lines += [f"- {note}" for note in draft.critique]
            lines.append("")

        if draft.repairs:
            lines += ["Rules it broke and had to fix:", ""]
            lines += [f"- {note}" for note in draft.repairs]
            lines.append("")

    return "\n".join(lines)


def _as_json(live, stamp: str) -> str:
    data = {
        "session": stamp,
        "started_at": live.started_at,
        "dry_run": config.DRY_RUN,
        "topic": live.topic,
        "interview": live.interview,
        "corrections": live.steers,
        "brief": live.brief,
        "posts": {},
    }

    for platform in ("linkedin", "instagram"):
        draft = live.draft(platform)
        data["posts"][platform] = {
            "text": draft.text,
            "hook": draft.hook,
            "media": draft.media,
            "approved": draft.approved,
            "published_url": draft.published_url,
            "critique": draft.critique,
            "repairs": draft.repairs,
        }

    return json.dumps(data, indent=2, ensure_ascii=False)
