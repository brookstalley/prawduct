# MCP mining — raw captures

Per-repo rule captures from the 2026-09-17 mining pass. **These are agent-reported, not
verified.** Every `file:line`, symbol and number below is a claim made by a mining agent reading
that repo; none has been re-derived here.

`core.md`: *a `file:line` you did not resolve yourself is a claim, not a citation — its precision
reads as evidence of having been read.* Before any of this reaches a shipped corpus, each cited
number and path must be re-checked against the source repo, and each rule anchored on a symbol or
heading rather than a line number.

Kept per-repo rather than pre-merged so provenance stays attached to its source. Synthesis by
layer happens after all five miners report.

| Source | Rules (headline) | Status |
|---|---|---|
| cordyceps (C# server, wide production use) | 60 | captured |
| bankmachine (Python server, measured evidence trail) | 84 | captured |
| discodon (client/bridge — consumer's view of arbitrary servers) | 48 | captured |
| prawduct (own research + delivery-surface map) | ~15 | in `../mcp-knowledge-corpus-design.md` §8 |
| hallucinote (Python server) | 92 | captured; full-fidelity twin in `hallucinote-server-structured.md` |

## The headline counts do not reproduce — do not quote them

Each row's count is the number its mining agent wrote in its own headline. None re-derives. The
command `../mcp-knowledge-corpus-design.md` §10.1 names for re-deriving them
(`grep -c '^- \*\*\|^\*\*RULE' *.md`) returns 68 / 97 / 53 / 99 against headlines of 60 / 84 / 48 / 92 —
every row disagrees, and the sums differ by 33 (284 vs 317). hallucinote disagrees a third way: its
structured twin's own summary says 78 while its body carries 106 rule blocks.

So there is no count of this corpus that anything has verified. The discrepancy does not disturb the
packaging ruling (§10.1 — every reading is far above the one-file threshold), but the number stated
there is unsourced and the command cited as its receipt returns something else. A count that ships
needs a derivation that runs, over a rule marker the captures actually share — which they currently
do not: two files use `**RULE:**` blocks and three use `- **bold**` bullets. Unifying the marker is
a precondition for counting, not a formatting preference.

`core.md`: *a spike that discards its code leaves its numbers unfalsifiable — cite the command,
never the digits*; *a number that disagrees with another number is a bug report.*
