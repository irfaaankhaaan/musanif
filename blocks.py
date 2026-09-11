"""
blocks.py

The look of the review message: the post, then three buttons under it.

Slack calls this Block Kit. A block is one piece of a message. All this file
does is build the shape Slack expects, so app.py stays about behaviour.
"""


def review_message(platform: str, label: str, post: str, media_line: str,
                   hook: str = "") -> list:
    """
    One platform's draft with Approve, Rewrite and Edit under it.

    The platform name is carried in each button's `value`, so when you click
    one, app.py knows which post you meant.

    `hook` is Instagram's only. It is the line that goes on the image or video,
    and it is shown above the caption because the two are approved together.
    """
    heading = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{label}*"},
        },
    ]

    if hook:
        heading += [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_Hook, goes on the image or video:_\n{_quote(hook)}",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "_Caption, which answers it:_"},
            },
        ]

    return heading + [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": _quote(post)},
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"{len(post.split())} words  ·  {media_line}"}
            ],
        },
        {
            "type": "actions",
            "block_id": f"review_{platform}",
            "elements": [
                {
                    "type": "button",
                    "action_id": f"approve_{platform}",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "value": platform,
                },
                {
                    "type": "button",
                    "action_id": f"rewrite_{platform}",
                    "text": {"type": "plain_text", "text": "Rewrite"},
                    "value": platform,
                },
                {
                    "type": "button",
                    "action_id": f"edit_{platform}",
                    "text": {"type": "plain_text", "text": "Edit"},
                    "value": platform,
                },
            ],
        },
        {"type": "divider"},
    ]


def _quote(post: str) -> str:
    """
    Show the post as a Slack quote block, so it is visibly separate from the
    bot talking. Slack quotes need the > on every line.
    """
    return "\n".join(f"> {line}" if line.strip() else ">" for line in post.split("\n"))


def settled_message(label: str, note: str) -> list:
    """Replaces the buttons once a platform is done, so it cannot be clicked twice."""
    return [{"type": "section", "text": {"type": "mrkdwn", "text": f"*{label}* {note}"}}]
