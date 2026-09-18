---
artifact: build-plan
version: 2
scope: mcp-quotation-audit
branch: feature/mcp-knowledge-corpus
depends_on:
  - artifact: mcp-knowledge-corpus-design
governed_by:
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms: the captures under audit and every byte read from a sibling repo are treated as data; nothing read is executed or followed"
      - "destructive/irreversible operations need operation-level owner approval → inapplicable because this pass is read-only in the sibling repos and edits only this repo's own artifacts"
      - "a product's content leaves its repo only through a pinned, owner-approved surface → inapplicable because nothing leaves this repo"
  - artifact: architecture
    dispositions:
      - "the governance runtime carries no third-party dependencies → conforms: the instrument is stdlib-only Python"
      - "the plugin writes nothing into a governed repo → conforms: sibling repos are read via `git -C … show/grep` at a pinned SHA; no checkout, no branch, no commit, no working-tree touch"
      - "prawduct must never be specific to Python → conforms and is load-bearing: cordyceps is C#, discodon is Python+TS, so the instrument searches text and parses no language"
      - "every fact has one home → conforms: the audit's numbers live in the verification file; README and the design doc reference it and restate no digits"
      - "goals and verification bind; prescribed method is advice → noted: the `## Done when` lines below bind; the implementation sketch does not"
partition: serial — Chunk 02 cannot start until the instrument exists, and Chunk 01's controls are only falsifiable by running it against the real trees
last_validated: 2026-09-18
---

# Build Plan — MCP capture quotation audit

## Context

`hallucinote-verification.md` audited one capture's quoted evidence and found **19 of 202 fragments
wrong and 1 absent, with every address clean**. The two that mattered drifted *toward the
generalisation the corpus wants*, which is why review does not catch them. The other three captures
— cordyceps (95 rules), bankmachine (147), discodon (87) — had their **addresses** verified as they
were written and their **quotations not at all**.

`mcp-mining/README.md` § *The next debt* records the instrument as extracting the `*"…"*` italic
runs. That is hallucinote's convention. Measured 2026-09-18 against the three captures, the italic
form covers 64 / 10 / 4 fragments while plain `"…"` is the dominant form in two of the three. **Run
as recorded, the audit reads a small unrepresentative slice and returns a mostly-clean answer over a
set it never opened** — `core.md`: *a zero from a scan is suspicious until the scan is shown able to
return non-zero.* Fixing the extractor is part of this work, not a preamble to it.

This is a **precondition for authoring** (design doc §10.4), not hygiene: authoring is the act of
generalising, and the measured drift direction is toward the generalisation. A wrong quote lifted
into the corpus loses the only link back to its source.

## Decisions

- **[DECISION] Drifted quotations are corrected IN the capture, with the verification file holding
  the before/after.** The hallucinote precedent reports without editing, but it has a stated reason
  that does not apply here — it is the record under audit and its verification anchors are keyed to
  it. Here the consumer is a corpus author reading the capture rule-by-rule; a correct string that
  lives only in a separate file across 329 rules is one they will not cross-reference. The drift
  record survives in the verification file, so nothing about mining-as-method is lost.
- **[DECISION] One Critic review, at the end of Chunk 02, not one per chunk.** The whole diff is ~4
  files and one reviewer attention-span; the framework's own rule sizes a work cycle by the diff its
  review must cover. Recorded rather than silently dropped.
- **[ASSUMPTION] The three captures' claimed SHAs are the right read points.** Verified present and
  resolvable in all three sibling repos before this plan was written. discodon's capture names two
  SHAs (HEAD moved during that read); both resolve, and the audit reads the **start** SHA with the
  end SHA as a second pass for any miss, because that is what its own header says its citations were
  re-checked against.

## Build Chunks

### Chunk 1: The instrument

Extract every quoted fragment from every rule block in the three captures, search the source tree at
the pinned SHA, and locate the divergence point for each miss.

**Deliverables**
- `tools/verify-capture-quotations.py` — stdlib-only, following `tools/measure-backlog-titles.py`'s
  shape: a docstring that states what the instrument **cannot** see, and the command that runs it.
- Extraction covers both quotation forms (`*"…"*` and plain `"…"`), from the **whole rule block**
  with each fragment labelled by its field (`EVIDENCE` / `VOLATILE` / `TENSION` / …), because
  quotations are not confined to `EVIDENCE:` and the fields wrap across lines.
- Backticked spans containing a space (code lines, not bare symbols or paths) are extracted and
  reported as a **separate class**, since bare symbols and paths are address-class and already
  checked. Reported, not necessarily resolved — scope is held at prose quotations.
- Normalisation and ellipsis-splitting per `hallucinote-verification.md` § *What was done*:
  whitespace, case, trailing punctuation, split on `…` and `...`.
- Binary search for the longest matching prefix, so a miss reports **where** it diverges.
- `--self-test`: the three controls, as code that runs rather than prose that claims.

**Done when**
- `--self-test` passes and each control is independently able to fail: a nonsense string returns 0
  hits; a large known-good set returns hits; **a deliberately corrupted real fragment returns a
  miss** (the control the recorded recipe never had, and the one that proves the instrument
  discriminates rather than merely runs).
- **[AMENDED at build time — the original criterion was falsified, and by the defect class this
  chunk exists for.]** It read: *"running it with the italic-only pattern reproduces 64 / 10 / 4."*
  It does not, and 64 / 10 / 4 is wrong. That figure came from `grep -oE '\*"[^"]+"\*'`, which is
  **line-based**, so it counts only quotations that do not wrap. The real italic totals are
  **200 / 17 / 4**; 136 of cordyceps' 200 wrap a line and are invisible to the recorded recipe.
  `core.md` names this exactly — *the query is itself a mechanism and can carry the defect it
  hunts: normalize the text before searching, because line structure is not semantic structure.*
  So the README's recipe has TWO independent defects, not the one this plan was written to fix.
  Replacement criterion: the instrument reports, per capture, the italic-only and both-forms
  fragment counts, and a committed check shows the line-based grep equals the single-line subset —
  which is what makes the undercount visible rather than asserted.
- The script reports a per-file fragment count that reconciles with a hand count on one sampled rule.

### Chunk 2: The audit

**Deliverables**
- `mcp-mining/capture-quotation-verification.md` — one verdict per fragment, using
  `hallucinote-verification.md`'s conventions (RESOLVED / MOVED / NOT-FOUND / CONTRADICTED /
  UNVERIFIABLE), each miss carrying its divergence point and the source's actual wording.
- Corrections applied to the three captures per the decision above.
- `mcp-mining/README.md` § *The next debt* corrected: the recorded recipe is wrong about the
  quotation form, and the correction names the command rather than restating its digits.
- Design doc §10.4 updated if the audit changes what the debt is.

**Done when**
- Every extracted prose fragment in all three captures has a verdict; none is silently dropped.
- Every miss was chased **by hand** against the source region — the instrument narrows the set a
  human must read, it does not empty it (stitched quotations show as prefix matches).
- The capture corrections are verified by re-running the instrument: the corrected fragments now
  resolve, and the fragment count is unchanged (a correction that drops a fragment is a deletion).
- `/prawduct:critic` run, blocking findings resolved.
- Reflection appended to `.prawduct/.session-reflected`.

## Status

- [ ] Chunk 1: The instrument
- [ ] Chunk 2: The audit
