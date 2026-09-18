# Capture quotation audit — cordyceps, bankmachine, discodon

**Read 2026-09-18.** The half of the verification debt that `hallucinote-verification.md` paid for
one capture and the other three had never had: their **addresses** were verified as they were
written, their **quotations** not at all.

Every number below is produced by a committed instrument. Cite the command, never the digits:

    tools/verify-capture-quotations.py --self-test    # the controls
    tools/verify-capture-quotations.py --counts       # what each extraction reads
    tools/verify-capture-quotations.py cordyceps bankmachine discodon

Each capture is searched against **the SHA its own provenance header declares**, read through
`git archive` — read-only in the sibling repos: no checkout, no branch, no working-tree touch.
discodon is searched at both ends of the five-commit window its header records; cordyceps also
against the working tree, because its header flags two gitignored files it cites — that fallback
lists `--cached --others`, so it genuinely sees ignored files, and a control proves it (defect 5).

---

## The headline: the recorded recipe could not have paid this debt

`README.md` § *The next debt* recorded the instrument as extracting the `*"…"*` runs. **Four
defects were found in that recipe and in the first implementations of its replacement**, and all
four are the same species — *the query is itself a mechanism and can carry the defect it hunts*
(`core.md`). They are listed in the order they were found, with what each was costing.

| # | Defect | What it cost | Found by |
|---|---|---|---|
| 1 | Reads only the **italic** form | every plain-quoted fragment unaudited — 368 in bankmachine, 392 in discodon | comparing forms per capture |
| 2 | `grep -oE` is **line-based** | a quotation that wraps is invisible; **136 of cordyceps' 200** italic quotations | `--counts`, which reproduces the grep figure and checks it equals the non-wrapping subset |
| 3 | Naive `"([^"]+)"` is **not escape-aware** | the captures embed JSON (`{\"accountId\": 1}`); fragments truncate at the escaped quote and miss on their last character | 39 "tail-rewrite drift" candidates that were all artifacts |
| 4 | Splitting on the bare `**RULE:**` marker | the captures' headers *discuss* the marker, so every rule id shifted past the header — citations unresolvable | a chased finding landing on a rule whose text did not contain it |
| 5 | The working-tree fallback used `git ls-files` | that lists **tracked** files only, so the fallback added for cordyceps' two gitignored citations could never see them — they landed in "not in the tree at all" and read like drift | the Critic; confirmed by `git ls-files` returning 0 for `.prawduct/reflections.md` where `--cached --others` returns 1 |

Defects 1 and 2 were in the recorded recipe. Defects 3, 4 and 5 were mine, in the replacement, and
**4 is the dangerous one**: it produced a report that was wrong in exactly the way a report cannot
afford, since a reader resolves a citation by its id. It is now a permanent control — the
instrument's rule-block count must equal `grep -c '^\*\*RULE:\*\*'` (95 / 147 / 87), the corpus's
own canonical command, so the two cannot disagree.

**The measurement that justified this work was itself wrong, and in the direction that understated
the debt.** It was recorded as 64 / 10 / 4 italic fragments. That is the *single-line* subset. The
real totals are **200 / 17 / 4**.

## Controls — why any of this is evidence

`--self-test` runs them, and they are code rather than prose because a scan nobody has falsified has
measured nothing:

- the corpus is a **non-empty set** (a green scan over nothing is not green);
- a **nonsense string returns zero** — the search is not matching everything;
- a **large known-good set returns hits** — it is not dead;
- a **corrupted real fragment must miss** — the control the recorded recipe never had, and the only
  one that shows the search *discriminates* rather than merely runs;
- **rule ids reconcile** with the corpus's own counting command (defect 4);
- the **working-tree fallback sees gitignored files** — a real sentence from
  `.prawduct/reflections.md` is found there and, as it must be, *absent* at the SHA (defect 5).

**Every corpus is asserted non-empty, not just the first.** That was the class behind defect 5: a
silently-empty *secondary* corpus — cordyceps' working tree, discodon's end SHA — degrades a verdict
without ever failing, because "nothing matched there" and "nothing was there to match" are the same
output.

Falsified against three mutants — empty corpus, always-match, collapsing `normalize()`. All three go
red. Worth recording: under always-match the *known-good* control reports a false **120/120 green**,
and only the nonsense and corruption controls catch it. A "large known-good set returns hits" control
alone would have passed a search that matched everything.

## What the audit found

    ALL                     1,034 prose fragments   755 resolved   279 miss   73%

| source | form | fragments | resolved | miss | resolve rate |
|---|---|---|---|---|---|
| cordyceps | italic-quote | 192 | 154 | 38 | 80% |
| cordyceps | plain-quote | 66 | 45 | 21 | 68% |
| bankmachine | italic-quote | 14 | 13 | 1 | 92% |
| bankmachine | plain-quote | 368 | 274 | 94 | 74% |
| discodon | italic-quote | 2 | 0 | 2 | 0% |
| discodon | plain-quote | 392 | 269 | 123 | 68% |

**A miss is not drift.** Misses are bucketed by how far the fragment's longest prefix reaches before
diverging, because the depth is what separates the classes:

| bucket | prefix reach | count | what it means |
|---|---|---|---|
| **A** | 90–100% | **4** | the drift signature — the source is there and the *tail* was rewritten |
| B | 70–89% | 27 | partial; usually a stitched quotation or a mid-sentence paraphrase |
| C | 40–69% | 72 | loosely related wording |
| D | <40% | 176 | the text is not in the tree at all |

### The structural finding: two of three captures cannot be audited at the fragment level

`italic-quote` resolves at **80% / 92%**; `plain-quote` at a flat **68% / 74% / 68%** across three
independently-written captures. That consistency is the signal. cordyceps uses `*"…"*` as a
deliberate verbatim-quotation convention (192 of its 258 fragments); bankmachine and discodon
essentially do not (14 of 382, 2 of 394) and use plain double quotes for **both** source quotations
and the author's own scare-quotes, emphasis and named concepts.

So for those two captures **there is no syntactic marker distinguishing a claim of verbatim source
text from the author's own words** — which is what bucket D's 176 mostly are. Their quoted evidence
is therefore not auditable at the fragment level *by any instrument*, only rule by rule with a human
reading each one. That is a finding about the mining schema, not about this pass: §3's schema
specifies the `EVIDENCE:` field but not how a quotation inside it declares itself.

### Bucket A, chased by hand — all five as first measured

(Bucket A reads **4** against the corrected captures, because item 2 below now resolves. All five
are kept here: the fifth is the one correction this audit made, and deleting it would erase the
record of why.)

Each was resolved against its source tree at the declared SHA.

1. **cordyceps rule 90** — *"…needs the `mcp-remote` bridge. Requires Node.js."*
   Source `README.md:56` reads `Requires [Node.js](https://nodejs.org/).` The capture silently
   dropped markdown link syntax. **Faithful in substance; not verbatim.**
2. **cordyceps rule 91** — *"…`xattr -dr com.apple.quarantine <path>`"*
   Source `README.md:39` reads `<path-to-Cordyceps.gha>`. The capture **shortened a placeholder
   inside a quoted shell command**, so a reader copying it gets a different command.
   **CORRECTED in the capture** to match the source verbatim.
3. **bankmachine rule 142** — *"never makes outbound calls except to X"*
   **Not a quotation — a false positive.** The rule's own sentence is *a README saying "never makes
   outbound calls except to X" is a claim, not a fact*; the `X` is the rule's template. The EVIDENCE
   field one line below quotes the source correctly and in full (*"The server never makes outbound
   calls except to Plaid's API."*). The capture is right; the extractor cannot tell a rule's
   illustrative template from a source quotation.
4. **discodon rule 32** — *"No perceptions — MCP servers are pull-only via `act`."*
   Source `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool` docstring reads ``:meth:`act` ``. The
   capture normalised Sphinx role markup. **Faithful in substance; not verbatim.**
5. **discodon rule 52** — *"…the only signal was 'timed out after 120s'"*
   Source `.prawduct/artifacts/project-preferences.md:100` reads *"the operator's **only signal was
   `timed out after 120s`**"*. The capture dropped `operator's` and re-quoted the literal.
   **Faithful in substance; not verbatim.**

**No fabrication was found in bucket A.** Three of five are markup normalisation, one is a genuine
alteration of a quoted command (corrected), and one is the instrument's own false positive. This is
a materially better result than hallucinote's — where 19 of 202 were wrong and one appeared nowhere
— and the difference is worth stating rather than assumed: these three were re-mined under the
structured schema with addresses verified as they were written, and hallucinote's compressed twin
was not.

---

## What is NOT done, stated plainly

- **Buckets B, C and D — 275 fragments — have not been chased by hand.** Bucket A was chased in
  full. The triage above makes the rest tractable (the instrument reports each one's divergence
  point), but reading them is a work cycle of its own, and most of D is expected to be the
  author's own words rather than drift. **Do not read "73% resolved" as "27% drift."**
- **`code-span` fragments are extracted and counted but not audited.** 148 / 86 / 231 of them. Bare
  symbols and paths are address-class and were checked when these captures were written; the
  multi-token code lines are a claim of the same kind as a prose quotation and are owed the same
  pass.
- **Fragments under 25 normalised characters are skipped, not searched** — 300 / 230 / 408. They are
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
- **cordyceps' working-tree corpus includes untracked build output**, because the fallback lists
  `--cached --others` to reach gitignored files and cannot distinguish "gitignored because it is a
  local record" from "gitignored because it is generated". The text-suffix corpus grows, and the
  large majority of what it gains is compiler output under `bin/` and `obj/` — re-derive with
  `git -C ~/source/cordyceps ls-files --cached --others` against a plain `ls-files`, rather than
  trusting a count here (this review and the audit disagreed by one on it, and nothing branches on
  the figure). Since RESOLVED means
  "matched anywhere", generated output could in principle supply a match — the **false-clean**
  direction. Effect on this run is zero and measurably so (cordyceps' plain-quote column is
  unchanged at 45/66, and the single italic gain is the tracked `README.md` correction below), so
  it is harmless **by coincidence rather than by construction** and is recorded as a standing limit.
- **Two extraction mechanisms are not pinned by any control**, and one is on the verdict path: the
  ellipsis split (`_ELLIPSIS_SPLIT_RE`). Break it and a quotation carrying the capture's own `…`
  stops being split into searchable pieces and misses whole, which is the shape of the
  escape-awareness defect above. The other is `_BACKTICK_RE`'s multi-token filter, which only
  affects the separately-reported `code-span` class. Control 9's fixture has no ellipsis and no
  multi-token backtick span, so neither is reached. Recorded rather than fixed: at a PR boundary a
  fix here buys a full review round for a gap nothing currently exercises, and the next commit that
  touches this file should close it.
- **Only the extensions in `TEXT_SUFFIXES` are searched.** A quotation whose source file has an
  extension missing from that allowlist is reported as a miss and reads exactly like drift, so the
  allowlist is a limit on this audit rather than an implementation detail.
- Markdown emphasis is stripped, so a quotation differing from its source **only** in emphasis reads
  as matching. Deliberate: `**bold**` added around a true sentence is not a false claim.
