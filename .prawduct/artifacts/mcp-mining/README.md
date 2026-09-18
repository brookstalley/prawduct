# MCP mining — raw captures

Per-repo rule captures from the 2026-09-17 mining pass. **These are agent-reported, not
verified.** Every `file:line`, symbol and number below is a claim made by a mining agent reading
that repo; none has been re-derived here.

`core.md`: *a `file:line` you did not resolve yourself is a claim, not a citation — its precision
reads as evidence of having been read.* Before any of this reaches a shipped corpus, each cited
number and path must be re-checked against the source repo, and each rule anchored on a symbol or
heading rather than a line number.

**That framing is too generous to four of these five files** — see *No provenance at all in four of
five captures* below. There is nothing to re-check in them, because nothing was ever addressed.

Kept per-repo rather than pre-merged so provenance stays attached to its source. Synthesis by
layer happens after all five miners report.

| Source | Rules (headline) | Status |
|---|---|---|
| cordyceps (C# server, wide production use) | 60 | **re-mined 2026-09-18 → `cordyceps-server-structured.md`, 95 rules, all addressed** (verified: 0 UNADDRESSED, 0 bare line-number citations, all 7 schema fields on all 95) |
| bankmachine (Python server, measured evidence trail) | 84 | **re-mined 2026-09-18 → `bankmachine-server-structured.md`, 147 rules, all addressed** (verified: 0 UNADDRESSED, all 7 fields on all 147; marker normalized at integration) |
| discodon (client/bridge — consumer's view of arbitrary servers) | 48 | compressed capture, unaddressed; **re-mine dispatched 2026-09-18** |
| prawduct (own research + delivery-surface map) | ~15 | in `../mcp-knowledge-corpus-design.md` §8 |
| hallucinote (Python server) | 92 | two renderings; addressed twin in `hallucinote-server-structured.md`; **audited 2026-09-18 → `hallucinote-verification.md`** — 106 verdicts: 95 RESOLVED · 7 MOVED · 0 NOT-FOUND · 2 CONTRADICTED · 2 UNVERIFIABLE |

Every number in the middle column is the headline its own mining agent wrote and **none re-derives** —
see the next section. They are kept only because removing them would hide the discrepancy.

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
do not. **Corrected 2026-09-18: the split is one file and four, not "two and three" as this section
originally said.** Only `hallucinote-server-structured.md` uses `**RULE:**` blocks (106 of them);
all four others use `- **bold**` bullets exclusively, and carry zero `**RULE:**` blocks. Re-derive:

    for f in *-server.md *-consumer.md *-structured.md; do
      printf '%-36s RULE-blocks:%-5s bold-bullets:%s\n' "$f" \
        "$(grep -c '^\*\*RULE:\*\*' "$f")" "$(grep -c '^- \*\*' "$f")"
    done

Unifying the marker is a precondition for counting, not a formatting preference — and because the
target marker is the structured schema, unifying it is the same act as paying the provenance debt.

`core.md`: *a spike that discards its code leaves its numbers unfalsifiable — cite the command,
never the digits*; *a number that disagrees with another number is a bug report.*

## No provenance at all in four of five captures — measured 2026-09-18

The note at the top of this file says each citation "must be re-checked against the source repo."
That framing was wrong about four of the five files, in a way that matters: **there are no citations
to re-check.**

    for f in cordyceps-server.md bankmachine-server.md discodon-consumer.md \
             hallucinote-server.md hallucinote-server-structured.md; do
      printf '%-36s ^PROVENANCE:%-5s distinct-tree-paths:%s\n' "$f" \
        "$(grep -c '^PROVENANCE:' "$f")" \
        "$(grep -oE '`[A-Za-z0-9_./-]+\.(py|cs|ts|tsx|md|json|yaml|toml)`' "$f" | sort -u | wc -l | tr -d ' ')"
    done

Reading: `0 / 4`, `0 / 1`, `0 / 0`, `0 / 3` — against `106 / 52` for
`hallucinote-server-structured.md`. Four files, zero `PROVENANCE` lines, and between zero and four
distinct source paths named across ~20KB of rules each. Meanwhile those rules carry hard measured
figures — a 49% docs-token reduction, ~32 minutes of observed silence, 37 and 43 parameters in one
schema, ten tools becoming eight.

So the debt is not "re-anchor the line numbers on symbols." It is that for four of five sources
**nothing was ever addressed**, while the rules read as though they had been.

**Why this is a precondition and not hygiene.** Desirable 3 in the design notes is periodic
revalidation. You cannot revalidate a claim you cannot locate, so an unaddressed corpus forecloses
the one absolute that keeps it true over time. It also collapses the marker-unification blocker into
the same act: the target marker *is* the structured schema, so unifying the marker for the
bullet-style captures and addressing them are one pass, not two.

hallucinote is the only source where the cost of compression is measurable, because it is the only
one with both renderings. The measurement there is ~8 rules and 100% of the addresses lost. That is
evidence about the other four, not only about hallucinote.

## Re-mining in flight — dispatched 2026-09-18

Four read-only agents, recorded here because they hold no worktree and a dispatch that lives only in
a session's context evaporates at the next `/clear`.

| Agent | Source repo | Owns exactly | Task |
|---|---|---|---|
| miner | `/Users/brookstalley/source/cordyceps` (`develop`) | `cordyceps-server-structured.md` | re-mine under the structured schema |
| miner | `/Users/brookstalley/source/bankmachine` (`feature/mcp-error-recovery-and-types`) | `bankmachine-server-structured.md` | re-mine; establish the answer-shape tool-boundary claim |
| miner | `/Users/brookstalley/source/discodon` (`feat/eval-candidate-kind-seam`) | `discodon-consumer-structured.md` | re-mine; establish the tool cap, the clamp policy, the frozen-schema observation |
| verifier | `/Users/brookstalley/source/hallucinote` (detached HEAD) | `hallucinote-verification.md` | resolve all 106 `PROVENANCE:` lines against the tree |

Each was briefed to: anchor on a symbol or heading and never a bare line number; carry no digit
without the thing that produces it, or mark it `UNSOURCED`; mark anything it cannot address
`UNADDRESSED` with the reason rather than inventing a path; treat its existing compressed capture as
an inventory so the output is a **superset** and no rule silently disappears; record the source
repo's HEAD SHA, since every citation is relative to it; and write the corpus **into its file, not
into its report** — the failure mode of the previous pass was a report and a disk copy that silently
disagreed.

Read-only in the source repos: no commits, no branches, no test runs, and no touching the sibling
checkouts, which belong to other sessions. The source branches are active non-MCP work carrying the
same core learnings (owner, 2026-09-18), so a branch tip is a sound thing to cite against.

**Integration is not delegated.** Folding these into the corpus, and reconciling them against the
compressed captures, is the coordinating session's debt.

## The two hallucinote files — direction of use

Corrected 2026-09-18. They are **not** two renderings of one rule set:
`hallucinote-server-structured.md` holds ~8 rules the compressed file lacks, and the compressed file
re-files 3 rules to better layers. **Author from the structured one for content; read the compressed
one for phrasing and layer assignment.** Each file's header carries the gap list and its probe
command. The compressed file's own per-layer counts were also wrong against its body — every row but
L0 — which is recorded in its header rather than here.

## The next debt: a capture's QUOTED EVIDENCE drifts, and it drifts toward the generalization

Found 2026-09-18 by the hallucinote citation audit, and it is a finding about **mining as a method**,
not about one file.

The audit extracted every `*"..."*` fragment from every `EVIDENCE:` field — 202 of them after
splitting on the capture's own ellipses — normalised them and searched the whole tree. **170 of 202
matched exactly. Nineteen quotations are not what the tree says, and one appears nowhere in it.**
Every address resolved (0 NOT-FOUND); the defects were of *wording*, which no path check can see.

**The direction is the finding.** The two edits that matter both drift **toward the generalisation
the corpus wants**:

- one rewrote an error-model rationale from *"its quality directly determines"* to *"its **structure**
  decides"*;
- one substituted *"the host"* for the tree's *"Live"* — in a corpus whose subject is the host/server
  boundary.

Both read *better* as corpus material than the source does. That is exactly why nobody re-checks
them: a paraphrase that sharpens a rule is invisible to a reader looking for errors, and it
launders a specific observation into a general claim the source never made. `core.md`'s
transcription rule names the mechanism (*its identifiers are the part that silently degrades — a
paraphrase reads exactly like a faithful copy*); this adds the direction, and the direction is what
makes it undetectable.

**So a quotation in an `EVIDENCE:` field is a claim, exactly like a `file:line`.** The schema's
PROVENANCE line invites a reader to believe the quote was checked because the address was.

### What is owed, and the cheap way to pay it

`cordyceps-server-structured.md` (95 rules) and `bankmachine-server-structured.md` (147) have had
their **addresses** verified as they were written, and their **quotations not at all**.
`discodon-consumer-structured.md` inherits the same debt.

This does not need an agent. The audit's instrument is mechanical and is described in
`hallucinote-verification.md` § *What was done*: extract the `*"..."*` runs, normalise whitespace,
case and trailing punctuation, split on ellipses, search the tree, and binary-search the longest
matching prefix so a divergence **point** is located rather than an absence merely reported. Two
controls make it evidence rather than reassurance, and both are worth copying: **a nonsense string
must return zero** (the search is not matching everything) and **a large known-good set must return
hits** (it is not dead).

Note what the instrument still cannot see, stated in that file rather than glossed: a quotation
*stitched* from two non-adjacent sentences with no ellipsis marked shows up as a prefix match and has
to be read. So the script narrows the set a human must read; it does not empty it.
