# Capture quotation audit — cordyceps and bankmachine

**Read 2026-09-18.** The half of the verification debt that `hallucinote-verification.md` paid for
one capture and the others had never had: their **addresses** were verified as they were written,
their **quotations** not at all.

Every number below is produced by a committed instrument. Cite the command, never the digits:

    tools/verify-capture-quotations.py --self-test    # the controls
    tools/verify-capture-quotations.py --counts       # what each extraction reads
    tools/verify-capture-quotations.py cordyceps bankmachine

Each capture is searched against **the SHA its own provenance header declares**, read through
`git archive` — read-only in the sibling repos: no checkout, no branch, no working-tree touch.
cordyceps is also searched against the working tree, because its header flags two gitignored files
it cites; that fallback lists `--cached --others`, so it genuinely sees ignored files, and a control
proves it.

## Scope — a third source was mined and is deliberately not published here

A fourth capture — a client/bridge consumer, the only consumer-side source in the corpus — was
produced in the same pass and audited by the same instrument. It is not in this repository and its
numbers are not in the tables below.

**Why.** This repository is public. That source is a **private repository owned by a different
account**, and the capture was a verbatim record of its internals. Publishing it here would have
disclosed a third party's private code through a governance artifact. The specifics stay out of this
file too: a public note explaining *which* private repo was withheld, and *what* was wrong with it,
is itself a disclosure — naming the target is most of the work. The full reasoning, with no more
detail than this, is in the design notes' § *One mined source is withdrawn from this repository*.

Recorded rather than silently dropped, because the *absence* is the thing a later reader would
otherwise try to fix. The work exists; it is simply not publishable from here, which is not a
quality judgement about it. Anything this file says about "the captures" means the two it covers.

---

## The headline: the recorded recipe could not have paid this debt

`README.md` § *The next debt* recorded the instrument as extracting the `*"…"*` runs. **Six defects
were found in that recipe and in the implementations of its replacement**, and they are the same
species — *the query is itself a mechanism and can carry the defect it hunts* (`core.md`). Listed in
the order found, with what each was costing.

| # | Defect | What it cost | Found by |
|---|---|---|---|
| 1 | Reads only the **italic** form | every plain-quoted fragment unaudited — the large majority of bankmachine's | comparing forms per capture |
| 2 | `grep -oE` is **line-based** | a quotation that wraps is invisible; most of cordyceps' italic quotations | `--counts`, which reproduces the grep figure and checks it equals the non-wrapping subset |
| 3 | Naive `"([^"]+)"` is **not escape-aware** | the captures embed JSON; fragments truncate at the escaped quote and miss on their last character | a batch of "tail-rewrite drift" candidates that were all artifacts |
| 4 | Splitting on the bare `**RULE:**` marker | the captures' headers *discuss* the marker, so every rule id shifted past the header — citations unresolvable | a chased finding landing on a rule whose text did not contain it |
| 5 | The working-tree fallback used `git ls-files` | that lists **tracked** files only, so the fallback added for cordyceps' gitignored citations could never see them — they landed in "not in the tree at all" and read like drift | the Critic |
| 6 | **The controls only covered the search** | three of defects 1–5 live in *extraction*; reverting the escape-aware regex left the whole self-test green | the Critic, by walking each control against a defect it should have caught |

Defects 1 and 2 were in the recorded recipe. The rest were in the replacement, and **6 is the one
worth carrying forward**: a guard with no control is one a later edit deletes silently, and the
guards written to close findings were themselves the unpinned ones.

## Controls — why any of this is evidence

`--self-test` runs them, and they are code rather than prose because a scan nobody has falsified has
measured nothing. **Do not state their count here** — it has grown three times and a number in this
sentence would be the first thing to go stale; run the command. They cover: a non-empty corpus (a
green scan over nothing is not green) and *every* corpus non-empty rather than only the first; a
nonsense string returning zero; a large known-good set returning hits; **a corrupted real fragment
that must miss**; rule ids reconciling with the corpus's own `grep -c '^\*\*RULE:\*\*'`; the
working-tree fallback seeing gitignored files; an emptied corpus refusing the run; `die`'s exit-2
contract; every emitted form being selectable; and **extraction itself**, pinned against an inline
fixture carrying a wrapped quotation, embedded escaped-quote JSON, and the rule marker discussed in
prose.

The corrupted-fragment control is the one the recorded recipe never had, and it is not optional.
Falsified against a mutant that matches everything, the *known-good* control reports a false
**120/120 green** while only the nonsense and corruption controls go red: a control that passes more
easily the more broken the instrument is measures nothing. The extraction control was falsified the
same way, against all three extraction defects, each going red with its own diagnostic.

## What the audit found

    ALL   640 prose fragments   486 resolved   154 miss   75%

| source | form | fragments | resolved | miss | resolve rate |
|---|---|---|---|---|---|
| cordyceps | italic-quote | 192 | 154 | 38 | 80% |
| cordyceps | plain-quote | 66 | 45 | 21 | 68% |
| bankmachine | italic-quote | 14 | 13 | 1 | 92% |
| bankmachine | plain-quote | 368 | 274 | 94 | 74% |

**A miss is not drift.** Misses are bucketed by how far the fragment's longest prefix reaches before
diverging, because the depth is what separates the classes:

| bucket | prefix reach | count | what it means |
|---|---|---|---|
| **A** | 90–100% | **2** | the drift signature — the source is there and the *tail* was rewritten |
| B | 70–89% | 14 | partial; usually a stitched quotation or a mid-sentence paraphrase |
| C | 40–69% | 38 | loosely related wording |
| D | <40% | 100 | the text is not in the tree at all |

### The structural finding: bankmachine cannot be audited at the fragment level

`italic-quote` resolves at **80% / 92%**; `plain-quote` at **68% / 74%**. cordyceps uses `*"…"*` as
a deliberate verbatim-quotation convention (192 of its 258 fragments); bankmachine essentially does
not (14 of 382) and uses plain double quotes for **both** source quotations and the author's own
scare-quotes, emphasis and named concepts.

So for bankmachine **there is no syntactic marker distinguishing a claim of verbatim source text
from the author's own words** — which is what bucket D mostly is. Its quoted evidence is therefore
not auditable at the fragment level *by any instrument*, only rule by rule with a human reading each
one. That is a finding about the mining schema, not about this pass: §3's schema specifies the
`EVIDENCE:` field but not how a quotation inside it declares itself.

**Strength of this finding, stated honestly.** It rests on two captures here. The unpublished third
source showed the same split — plain-quote resolving in the same band, with almost no italic use —
which is why the pattern reads as a property of the schema rather than of one author. A reader of
this repository cannot check that third data point, so the claim to rely on is the two-capture one.

### Bucket A, chased by hand — all of it

Each was resolved against its source tree at the declared SHA. Three items are recorded because one
of them is the correction this audit made, and deleting it would erase the record of why.

1. **cordyceps rule 90** — *"…needs the `mcp-remote` bridge. Requires Node.js."*
   Source `README.md` reads `Requires [Node.js](https://nodejs.org/).` The capture silently dropped
   markdown link syntax. **Faithful in substance; not verbatim.**
2. **cordyceps rule 91** — *"…`xattr -dr com.apple.quarantine <path>`"*
   Source `README.md` reads `<path-to-Cordyceps.gha>`. The capture **shortened a placeholder inside
   a quoted shell command**, so a reader copying it gets a different command. **CORRECTED in the
   capture** to match the source verbatim — which is why it no longer appears in bucket A.
3. **bankmachine rule 142** — *"never makes outbound calls except to X"*
   **Not a quotation — a false positive.** The rule's own sentence is *a README saying "never makes
   outbound calls except to X" is a claim, not a fact*; the `X` is the rule's template. The EVIDENCE
   field one line below quotes the source correctly and in full. The capture is right; the extractor
   cannot tell a rule's illustrative template from a source quotation.

**No fabrication was found.** One genuine alteration of a quoted command (corrected), one markup
normalisation, one extractor false positive. That is a materially better result than hallucinote's —
where 19 of 202 were wrong and one appeared nowhere — and the difference is worth stating rather
than assumed: these were re-mined under the structured schema with addresses verified as they were
written, and hallucinote's compressed twin was not.

---

## What is NOT done, stated plainly

- **Buckets B, C and D are not chased by hand.** Bucket A was chased in full. The triage makes the
  rest tractable (the instrument reports each miss's divergence point), but reading them is a work
  cycle of its own, and most of D is expected to be the author's own words rather than drift.
  **Do not read "75% resolved" as "25% drift."**
- **`code-span` fragments are extracted and counted but not audited** — 143 in cordyceps, 74 in
  bankmachine. Bare symbols and paths are address-class and were checked when these captures were
  written; the multi-token code lines are a claim of the same kind as a prose quotation and are owed
  the same pass.
- **Fragments under 25 normalised characters are skipped, not searched** — 300 and 230. They are
  counted, never silently dropped. Short strings match everywhere and a verdict on them would be
  meaningless.
- **hallucinote's capture still carries its 19 known-wrong quotations.** That audit reported without
  editing, deliberately — it is the record under audit and its anchors are keyed to it. The
  consequence is that an author lifting from `hallucinote-server-structured.md` at stage 1 has no
  in-place signal, and must read `hallucinote-verification.md` alongside it.

## What this instrument cannot see

Stated here rather than glossed, and repeated in the script's own docstring:

- A quotation **stitched** from two non-adjacent sentences with no ellipsis marked shows as a long
  prefix match. The script narrows the set a human must read; it does not empty it.
- It answers *does this string appear in the tree*, **not** *does it appear at the address the
  `PROVENANCE:` line names*. A quote matching elsewhere in the repo reads as RESOLVED.
- Line-leading comment markers (`///`, `#`, `>`, `--`) are stripped from both sides, so text that is
  only adjacent *because* a marker was removed can be matched as continuous.
- Markdown emphasis is stripped, so a quotation differing from its source **only** in emphasis reads
  as matching. Deliberate: `**bold**` added around a true sentence is not a false claim.
- **cordyceps' working-tree corpus includes untracked build output**, because the fallback lists
  `--cached --others` to reach gitignored files and cannot distinguish "gitignored because it is a
  local record" from "gitignored because it is generated". Since RESOLVED means "matched anywhere",
  generated output could supply a match — the **false-clean** direction. Effect on this run is zero
  and measurably so, so it is harmless by coincidence rather than by construction.
- **Two extraction mechanisms are not pinned by any control**, and one is on the verdict path: the
  ellipsis split. Break it and a quotation carrying the capture's own `…` stops being split into
  searchable pieces and misses whole. The other is the multi-token backtick filter, which only
  affects the separately-reported `code-span` class. The next commit that touches this file should
  close it.
- **Only the extensions in `TEXT_SUFFIXES` are searched.** A quotation whose source file has an
  extension missing from that allowlist is reported as a miss and reads exactly like drift, so the
  allowlist is a limit on this audit rather than an implementation detail.
