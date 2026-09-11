# Content brief

Turn the material below into a short internal brief. This brief is the shared
source for both posts, so that the LinkedIn post and the Instagram caption
carry the same idea without sharing any wording.

**The first thing below is their own rough post.** That is not a topic they
handed you to go and develop. It is the post, already written badly, and it is
the spine of everything after it. The questions that follow it only filled in
what it was missing.

So the brief describes **their** post, not a better one you would rather write.
Where they said something well, that is the phrasing to carry forward. The
claim is the claim they were already making.

The person does not normally see this. Write it for the writer, not for them.

If they corrected the questioning during the interview, those corrections are
listed underneath it. They are the strongest signal you have about what this
post is for, stronger than anything you infer from the answers. Obey them.

Refer to the person as **they**, never "he" and never "she". Nobody has told
you which is right. The posts themselves are written in the first person, so
this only affects the brief, but get it right anyway.

## Fields

- **core_claim**: the one thing this post says. One sentence, specific enough
  that only this person could have said it. It can be an argument ("onboarding
  was slow because of a field nobody used") or the turn in a story ("I stopped
  waiting to be handed the brief and started building the thing myself"). What
  it cannot be is a category with a verb attached. "We improved onboarding" is
  not a claim.
- **proof**: what makes the claim land, taken from the interview. A number when
  the interview gave you one. When it did not, the specific moment, the before
  and after, or the thing they used to do and no longer do. **Never invent a
  number and never reach for one that was not offered.** A post about a person
  changing is proved by a moment, not a metric.
- **sharpest_detail**: the single most specific thing they said. The fact that
  could only have come from this conversation.
- **detail_keywords**: 2 to 4 short literal strings that MUST appear word for
  word in both posts. Each under 25 characters, written exactly as a writer
  would type them. A number if the interview contained one ("40 minutes").
  Otherwise the concrete nouns, names and phrases they actually used ("VAT
  number", "colour grade", "the third rewrite"). Never a number the interview
  did not contain. Do not include a keyword you would not expect to survive a
  rewrite.
- **takeaway**: what the reader should be left holding.
- **call_to_action**: what the reader should do. If nothing genuine fits, use
  an empty string rather than inventing one.

## Your reply

Reply with JSON and nothing else.

```json
{
  "core_claim": "",
  "proof": "",
  "sharpest_detail": "",
  "detail_keywords": [],
  "takeaway": "",
  "call_to_action": ""
}
```
