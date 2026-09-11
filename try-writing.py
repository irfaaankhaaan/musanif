"""
try-writing.py

Writes both posts from a brief, in this window, with the real Claude. Use it to
tune the four prompt files without touching Slack.

    python try-writing.py

It shows you what the critique step actually changed, which is the part you
would normally never see. If the critique is finding nothing, the prompts in
prompts/*_critique.md are too soft.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import brain
import rules
import writer

LINE = "=" * 70

# The brief that came out of the interview demo. Change it to try your own.
BRIEF = {
    # Their own rough post. Both write prompts are told this is the spine, so
    # if the finished posts contain none of these words, the prompts are
    # overwriting the person instead of sharpening them.
    "rough_post": (
        "Want to post about our onboarding. It used to take six days from "
        "signed contract to first design review and we always blamed clients "
        "for being slow. It was us. The brief had to go through three people "
        "before a designer could touch it. We replaced the Notion form and "
        "Zapier mess with one form that writes straight into the project "
        "tracker and it is under two days now. Count your own handoffs before "
        "you blame the client."
    ),
    "core_claim": "Our onboarding took six days because three people had to touch a brief before a designer could start, not because clients were slow to respond.",
    "proof": "On Notion forms plus Zapier, signed contract to first design review ran about six days. The waiting was internal: the brief passed through three people before it reached a designer. After replacing that with one custom form that writes straight into the project tracker, the same journey now runs under two days.",
    "sharpest_detail": "The bottleneck was never client response time. It was a brief that three people had to touch before any design work could begin.",
    "detail_keywords": ["six days", "under two days", "three people", "project tracker"],
    "takeaway": "If onboarding drags, count your internal handoffs before you blame the client.",
    "call_to_action": "Map the path from signed contract to first brief and count how many people touch it.",
}


def show(platform: str, voice: str) -> None:
    print("\n" + LINE)
    print(f"{platform.upper()}")
    print(LINE)

    result = writer.make_post(platform, BRIEF, voice)

    print("\n--- what the critique found (you never see this in Slack) ---")
    if result["critique"]:
        for note in result["critique"]:
            print(f"  * {note}")
    else:
        print("  Nothing. If this stays empty, the critique prompt is too soft.")

    if result["repairs"]:
        print("\n--- rules broken, and repaired ---")
        for note in result["repairs"]:
            print(f"  ! {note}")

    if result["unresolved"]:
        print("\n--- STILL BROKEN after every attempt ---")
        for note in result["unresolved"]:
            print(f"  X {note}")

    if result.get("hook"):
        print("\n--- the hook, which goes on the image or video ---\n")
        print(f"  {result['hook']}")
        print(f"  [{len(result['hook'].split())} words]")
        print("\n--- the caption, which has to answer it ---\n")
    else:
        print("\n--- the post you would see ---\n")
    for line in result["post"].split("\n"):
        print(f"  {line}")

    words = len(result["post"].split())
    chars = len(result["post"])
    first_line = result["post"].split("\n")[0]
    print(f"\n  [{words} words, {chars} characters]")
    print(f"  [first line, {len(first_line)} chars: {first_line[:80]}]")

    # The detail may live in either half on Instagram, so check both together.
    both = (result["post"] + " " + result.get("hook", "")).lower()
    kept = [k for k in BRIEF["detail_keywords"] if k.lower() in both]
    print(f"  [detail kept: {kept or 'NONE, this is a failure'}]")


def main() -> None:
    voice = rules.load_voice()
    print(LINE)
    print("WRITING BOTH POSTS  (real Claude, costs a few pennies)")
    print(LINE)
    print("Same brief, two separate prompts, two separate sets of API calls.")
    print("Neither post can see the other one.")

    try:
        show("linkedin", voice)
        show("instagram", voice)
    except brain.BrainError as error:
        print(f"\nProblem: {error}")
        return

    print("\n" + LINE)
    print("Both written. Compare them: they should share the idea and share")
    print("almost no wording.")
    print(LINE)


if __name__ == "__main__":
    main()
