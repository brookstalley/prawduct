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
| prawduct (own research + delivery-surface map) | ~15 | in `../mcp-knowledge-corpus-design.md` §8 |
| hallucinote (Python server) | 92 | two renderings; addressed twin in `hallucinote-server-structured.md`; **audited 2026-09-18 → `hallucinote-verification.md`** — 106 verdicts: 95 RESOLVED · 7 MOVED · 0 NOT-FOUND · 2 CONTRADICTED · 2 UNVERIFIABLE |

Every number in the middle column is the headline its own mining agent wrote and **none re-derives** —
see the next section. They are kept only because removing them would hide the discrepancy.

## The headline counts do not reproduce — do not quote them

**This section records the state of the COMPRESSED captures before the 2026-09-18 re-mine, and its
readings are historical.** They are kept because they are why the re-mine happened; do not read them
as describing the shipped tree, and do not re-run its receipt expecting them — the structured
captures that replaced those inputs carry a shared marker and a count that reproduces (see the last
section of this file).

As measured then: each row's count was the number its own mining agent wrote in its headline, and
none re-derived. The command §10.1 named for re-deriving them disagreed with every headline, and the
sums differed. hallucinote disagreed a third way: its structured twin's own summary said 78 while its
body carried 106 rule blocks.

So there is no count of this corpus that anything has verified. The discrepancy does not disturb the
packaging ruling (§10.1 — every reading is far above the one-file threshold), but the number stated
there is unsourced and the command cited as its receipt returns something else. A count that ships
needs a derivation that runs, over a rule marker the captures actually share — which they currently
did not. **Corrected 2026-09-18: the split was one file and four, not "two and three" as this
section originally said.** At that point only `hallucinote-server-structured.md` used `**RULE:**`
blocks and the compressed captures used `- **bold**` bullets exclusively. That is no longer the
shipped state — every structured capture now uses the shared marker — so run this over the tree
rather than trusting the sentence:

    for f in *-server.md *-structured.md; do
      printf '%-36s RULE-blocks:%-5s bold-bullets:%s\n' "$f" \
        "$(grep -c '^\*\*RULE:\*\*' "$f")" "$(grep -c '^- \*\*' "$f")"
    done

Unifying the marker is a precondition for counting, not a formatting preference — and because the
target marker is the structured schema, unifying it is the same act as paying the provenance debt.

`core.md`: *a spike that discards its code leaves its numbers unfalsifiable — cite the command,
never the digits*; *a number that disagrees with another number is a bug report.*

## No provenance at all in four of five captures — measured 2026-09-18

The note at the top of this file says each citation "must be re-checked against the source repo."
That framing was wrong about the compressed captures, in a way that matters: **there were no
citations to re-check.** The readings below are over the files this repository still ships.

    for f in cordyceps-server.md bankmachine-server.md \
             hallucinote-server.md hallucinote-server-structured.md; do
      printf '%-36s ^PROVENANCE:%-5s distinct-tree-paths:%s\n' "$f" \
        "$(grep -c '^PROVENANCE:' "$f")" \
        "$(grep -oE '`[A-Za-z0-9_./-]+\.(py|cs|ts|tsx|md|json|yaml|toml)`' "$f" | sort -u | wc -l | tr -d ' ')"
    done

Reading: `0 / 4`, `0 / 1`, `0 / 3` for the three compressed captures — against `106 / 52` for
`hallucinote-server-structured.md`, the one addressed file. Zero `PROVENANCE` lines each, and a
handful of distinct source paths across ~20KB of rules apiece, while those same rules carry hard
measured figures.

So the debt was not "re-anchor the line numbers on symbols." It was that for the compressed sources
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

The read-only agents dispatched that day, recorded here because they held no worktree and a dispatch
that lives only in a session's context evaporates at the next `/clear`. **One row is absent: the
consumer-side miner, whose capture is withheld** (`capture-quotation-verification.md` § *Scope*).

| Agent | Source repo | Owns exactly | Task |
|---|---|---|---|
| miner | `/Users/brookstalley/source/cordyceps` (`develop`) | `cordyceps-server-structured.md` | re-mine under the structured schema |
| miner | `/Users/brookstalley/source/bankmachine` (`feature/mcp-error-recovery-and-types`) | `bankmachine-server-structured.md` | re-mine; establish the answer-shape tool-boundary claim |
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

## PAID 2026-09-18: the quoted-evidence audit — and the recipe this section recorded was wrong

Found by the hallucinote citation audit, and it is a finding about **mining as a method**, not about
one file: a capture's quoted evidence drifts, and it drifts *toward the generalisation the corpus
wants*. Of 202 quoted fragments there, 170 matched the tree exactly, **19 do not and 1 appears
nowhere** — with every address resolving, so no path check can see it. The two that matter rewrote
*"its quality directly determines"* to *"its **structure** decides"*, and substituted *"the host"*
for the tree's *"Live"*. Both read *better* as corpus material than the source does, which is why
nobody re-checks them. **So a quotation in an `EVIDENCE:` field is a claim, exactly like a
`file:line`** — the schema's `PROVENANCE:` line invites a reader to believe the quote was checked
because the address was.

**cordyceps and bankmachine have now been audited. Results, method, what was corrected and what is
still owed: `capture-quotation-verification.md`.** The numbers have one home, which is that file and
the instrument it cites; they are not restated here. A third source mined in the same pass is
deliberately not published in this repository — that file's § *Scope* says why, and the reason is
not a quality judgement about the capture.

**This section previously recorded the instrument as "extract the `*"…"*` runs" and said it did not
need an agent. The second half was right and the first was wrong twice**, which is why the
instrument is now committed as `tools/verify-capture-quotations.py` with its controls rather than
described in prose:

- it read only the **italic** form — but only cordyceps uses that convention; bankmachine quotes
  with plain `"…"` almost exclusively, so nearly every fragment in that capture went unaudited;
- and as a `grep -oE` it is **line-based**, so any quotation that *wraps* is invisible — and these
  captures wrap prose at ~95 chars. Run `tools/verify-capture-quotations.py --counts`: it reproduces
  the grep figure and checks that it equals exactly the non-wrapping subset.

That second defect is the same species as the thing being hunted — `core.md`: *the query is itself a
mechanism and can carry the defect it hunts; normalize the text before searching, because line
structure is not semantic structure.*

**Two controls make a scan evidence rather than reassurance, and a third makes it discriminate:** a
nonsense string must return zero, a large known-good set must return hits, and — the one the recipe
here never had — **a deliberately corrupted real fragment must miss.** Under a search that matches
everything, the known-good control reports a false 120/120 green and only the other two catch it.

Note what no instrument can see: a quotation *stitched* from two non-adjacent sentences with no
ellipsis marked shows up as a prefix match and has to be read. The script narrows the set a human
must read; it does not empty it.

## The marker is now uniform; the FIELD LAYOUT is not — measured 2026-09-18

All four addressed captures are reaped. **One marker, one command, and for the first time a count of
this corpus that reproduces:**

    grep -c '^\*\*RULE:\*\*' *-structured.md      # per capture; run it rather than quoting it
    cat *-structured.md | wc -cw                  # bytes / words — run it, do not quote it

**One marker, one command, and for the first time a count of this corpus that reproduces.** Run the
commands above rather than quoting a total here: the corpus lost a source after these lines were
written (see `capture-quotation-verification.md` § *Scope*), and every transcribed total in this
directory went stale the moment it did — which is the defect this whole section exists to describe.
Two marker variants were normalized at integration — bankmachine's
newness flag (moved to `FIRST-SEEN:`) and a second capture's provisional flag (moved to `STATUS:`) — because
each put its payload *inside* the `RULE:` token, which is invisible to the count that reads it.

**The remaining non-uniformity is the field layout, and it bites the same way.** Three captures put
one field per line; `hallucinote-server-structured.md` combines `LAYER · KIND · EVIDENCE` on one line
and `VOLATILE · TENSION` on another. Per-file field counts are unaffected (`grep -c '^LAYER:'` is 106
there, correctly), but **a corpus-wide layer tally silently matches a different set per file** —
`grep -h '^LAYER: L' | sort | uniq -c` returns one row per rule — garbage — because each combined line is
unique. Use the layout-agnostic form, which anchors and stops:

    grep -ohE '^LAYER: L[0-4]' *-structured.md | sort | uniq -c

**hallucinote's layout was deliberately left alone**: it is the record under audit, and
`hallucinote-verification.md`'s per-rule anchors are keyed to it. Normalize it when it is lifted into
the corpus, not before, and never by a script that has not been run against the verification file's
rule ids.

This is the same lesson as the marker, one layer down: **a shared field NAME is not a shared
format**, and the command that appears to read every capture is the one that reads none of them.
