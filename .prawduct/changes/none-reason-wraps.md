---
schema: 1
type: fix
scope: none-reason-wraps
date: 2026-11-22
title: a `none:` consumer note wrapped onto a second line is still read as none
---
`none: <reason>` in a fragment's consumer note was matched against one line only. Fragment prose
wraps at the file's width, so a reason wrapped onto a second line read as consumer text, and the
release cut published "none: …" into the changelog as if it were a note for consumers. Three of
this release's own fragments hit it, found in the cut's preview. The match now spans lines, and the
reason is printed with its line breaks collapsed. A real note that merely contains "none:" further
down is unaffected. A `none:` note followed by a separate paragraph is now refused
(`none-with-note`): the cut would otherwise drop that paragraph without a word.

## Consumer note
A `none:` consumer note in a change fragment may now wrap onto more than one line; the release cut
still reads it as none and publishes nothing for it. A `none:` note followed by a blank line and
more text is refused as `none-with-note`: write the note for consumers, or keep only the reason.
