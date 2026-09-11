"""
try-interview.py

Runs just the interview, in this window, with the real Claude. Use it to tune
prompts/interview.md without touching Slack or restarting the bot.

Edit prompts/interview.md, run this, see the difference. That loop takes
seconds instead of minutes.

    python try-interview.py           you answer the questions
    python try-interview.py --demo    a canned journey post, for a quick look
    python try-interview.py --push    canned, and it pushes back mid-interview

While you are answering, you can tell it the questions are wrong exactly as you
would in Slack ("you are asking the wrong questions, this is about X"). It
should take the correction, throw away the question that earned it, and aim
somewhere new. That is worth testing here, where it costs pennies.

At the end it shows every correction you made, so you can see whether the
questions after one actually respected it.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import brain
import interview
import rules
import session

LINE = "-" * 70

# The first entry is the ROUGH POST, not a topic. That is the whole point: the
# questions after it are only refining what is already there. Nothing in it was
# measured and there is no number anywhere, so a bot that asks "how many hours
# did that save" has stopped reading.
DEMO_ANSWERS = [
    "I want to post about going from being a creative to someone who builds "
    "AI solutions. For eight years I was the person who made the thing look "
    "right. Decks, brand work, edits. Always downstream of whoever decided "
    "what we were making. Then I realised I could just build the thing I kept "
    "asking someone else to build for me. It was bad at first but it existed. "
    "I still think like a creative, I just stopped needing permission. Most "
    "creatives think builders are a different species of person and they are "
    "not.",
    "Permission from whoever owned the roadmap, mostly. There was always a "
    "person between me and the thing existing.",
    "The first one was a little tool that renamed and sorted export files. "
    "Ugly, but it saved me opening the same folder forty times a day.",
    "That builders are a different species. They are not, they just started.",
]

# The same rough post, but the second message is a push-back rather than an
# answer. Use this to watch a correction land without typing it yourself.
PUSH_ANSWERS = [
    DEMO_ANSWERS[0],
    "You are asking the wrong questions. This is not about what I built or how "
    "long it took, it is about the shift in how I see myself.",
    "The moment was when I stopped opening a brief and started opening an "
    "editor instead.",
    "Other creatives who assume building is a different species of person.",
]


def run(interactive: bool, answers: list) -> None:
    live = session.start("U_LOCAL", "D_LOCAL", voice=rules.load_voice())

    print(LINE)
    print("INTERVIEW  (real Claude, costs a few pennies)")
    print(LINE)
    if interactive:
        print("Answer normally. To test a push-back, type something like:")
        print('  "you are asking the wrong questions, this is about X"')
        print("Type quit to stop.")

    first = interview.OPENING_QUESTION
    live.interview.append(
        {"question": first, "answer": "", "kind": interview.OPENING}
    )
    print(f"\nQ: {first}")

    canned = iter(answers)

    while True:
        if interactive:
            reply = input("A: ").strip()
            if reply.lower() in ("quit", "exit", ""):
                print("\nStopped.")
                return
        else:
            try:
                reply = next(canned)
            except StopIteration:
                print("\nRan out of canned answers before the interview finished.")
                break
            print(f"A: {reply}")

        try:
            step = interview.respond(live, reply)
        except brain.BrainError as error:
            print(f"\nProblem: {error}")
            return

        # A correction: the question that earned it is replaced, not answered.
        if step.kind == "correction":
            pending = live.interview[-1]
            if pending.get("kind") == interview.OPENING:
                live.interview.append(
                    {"question": step.question, "answer": "", "kind": step.turn_kind}
                )
            else:
                pending.update(
                    question=step.question, answer="", kind=step.turn_kind
                )
            print(f"\n  [correction taken: {step.note}]")
            print(f"\n{step.acknowledge}")
            print(f"Q: {step.question}")
            continue

        live.interview[-1]["answer"] = reply

        if step.kind == "done":
            break

        live.interview.append(
            {"question": step.question, "answer": "", "kind": step.turn_kind}
        )
        label = "Q (working out the subject)" if step.turn_kind == interview.CLARIFY else "Q"
        print(f"\n{label}: {step.question}")

    # ----------------------------------------------------------------------
    print("\n" + LINE)
    print("WHAT IT THOUGHT THE POST WAS ABOUT")
    print(LINE)
    print(f"  {live.topic or '(never established)'}")
    print(f"\n  refining questions   : {interview.questions_asked(live)}")
    print(f"  subject questions    : {interview.clarifiers_asked(live)}")

    if live.steers:
        print("\n" + LINE)
        print("WHERE YOU PUSHED BACK")
        print(LINE)
        for steer in live.steers:
            print(f"\n  it asked   : {steer['rejected']}")
            print(f"  you said   : {steer['said']}")
            print(f"  it took as : {steer['note']}")
        print("\n  Check every question after this respected it.")

    # ----------------------------------------------------------------------
    print("\n" + LINE)
    print("BRIEF")
    print(LINE)
    try:
        live.brief = interview.build_brief(live)
    except brain.BrainError as error:
        print(f"Problem building the brief: {error}")
        return

    for field in ("core_claim", "proof", "sharpest_detail", "takeaway", "call_to_action"):
        print(f"  {field:18} {live.brief.get(field, '')}")
    print(f"  {'must appear':18} {live.brief.get('detail_keywords', [])}")

    session.clear()


if __name__ == "__main__":
    if "--push" in sys.argv:
        run(interactive=False, answers=PUSH_ANSWERS)
    elif "--demo" in sys.argv:
        run(interactive=False, answers=DEMO_ANSWERS)
    else:
        run(interactive=True, answers=[])
