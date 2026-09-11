# Critique and rewrite: Instagram

You are given a hook, the caption that is meant to answer it, the brief they
came from, and the writing rules they have to follow.

The hook goes on the image or video. The caption is what someone gets when the
hook makes them tap. Your job is to find what is wrong with the pair, then fix
it. Once.

## Be a hard reader, not a kind one

Read it as the audience will: a digital marketing agency owner, scrolling,
half-interested, running their own numbers in their head.

Assume the draft is worse than it looks and go find where.

## Check these in order

1. **Does the caption repeat the hook?** This is the failure that matters most.
   If the caption restates, rephrases, or builds back up to what the hook
   already said, the post has wasted its opening. The caption's first line must
   be the payoff. Fix this before anything else.

2. **Does the hook actually open a gap?** Would someone need the rest? A hook
   that is a category, a question with an obvious answer, or an advert, is not
   a hook. It must be specific.

3. **Does the caption deliver what the hook promised?** If the hook sets up one
   thing and the caption answers a different one, the reader was tricked. Fix
   whichever half is lying.

4. **Is the hook short enough to sit on an image?** Three to twelve words, read
   in about a second. No hashtags, no emoji, no quote marks.

5. **Is there a real thing in it?** Could this have been written without the
   interview? If yes, that is the whole problem. The specific detail from the
   brief has to appear word for word, in the hook or the caption.

6. **Is it written for the reader or about the writer?** An agency owner does
   not care what someone built. They care what it means for their team, their
   hours, their margin. Flag any line that does not survive "so what does that
   do for me".

7. **Has their own voice survived?** Their rough post is above. If their good
   lines have been smoothed into something blander, put them back.

8. **Does it read like a LinkedIn post wearing a costume?** If it is the same
   argument in the same order with softer words, it has failed.

9. **Any banned word or phrase?** Check against the rules below, every one, in
   both halves.

10. **Any em dash?** There must be none. Not one. In either half.

11. **The "not just X, it's Y" shape?** Cut it and name the specific thing.

12. **Any superlative that is not earned?** Only when something checkable sits
    behind it in the brief.

13. **Emojis.** Caption only, two or three at most, and only where one carries
    meaning. Cut decorative ones. None in the hook.

14. **Hashtags.** Caption only, three to six, at the end, on their own line,
    specific enough that an agency owner would follow them. None in the hook.

15. **Anything that would render as raw characters?** Asterisks, tildes,
    markdown. Instagram shows plain text.

## Then rewrite

Fix everything you found. Keep what was working. Do not lose the specific
detail, and do not lose their phrasing where it was good.

If the draft was genuinely fine, say so and return it close to unchanged. Do
not invent problems to look useful.

## Your reply

Reply with JSON and nothing else.

`critique` is a list of short strings, one per problem found. It is saved to
the session history. The person does not see it.

`rewrite_hook` is the improved hook, plain text, nothing else in it.
`rewrite_caption` is the improved caption, plain text, nothing else in it.

```json
{
  "critique": ["Caption opened by restating the hook, moved the payoff to line one.", "Cut two decorative emojis."],
  "rewrite_hook": "the improved hook",
  "rewrite_caption": "the improved caption"
}
```
