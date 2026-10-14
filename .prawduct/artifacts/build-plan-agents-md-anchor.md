---
artifact: build-plan
version: 3
scope: agents-md-anchor
branch: feature/942-agents-md-anchor
depends_on:
  - artifact: architecture
  - artifact: security-model
governed_by:
  - artifact: architecture
    dispositions:
      - "the plugin writes nothing into a governed repo except .prawduct/, the evidence store and the reconciled files (.gitignore, .claude/settings*.json, CLAUDE.md's anchor) → amendment proposed: AGENTS.md's anchor block and CLAUDE.md's `@AGENTS.md` import replace 'CLAUDE.md's anchor' in the enumeration, recorded as a [DECISION] beneath the norm in Chunk 01 citing the owner's rulings on #942 (2026-09-30) and #928 D-8 (2026-10-10) as the authority. The statement itself is not edited to match the code"
      - "every fact has one home → conforms: the anchor text, the import line and the install id each keep one definition in migrate_plugin.py; anchor_repair and onboarding_probes import them"
      - "an independent reviewer never mutates the session it reviews → inapplicable because no reviewer or review path is touched"
      - "authority fails closed; advice fails soft → conforms: root AGENTS.md joins the protected set (Chunk 02), so an edit to it reopens the Critic gate rather than riding a doc-only path; the doctor grade stays advice"
      - "local-first, no network, no third-party runtime dependencies → conforms: the writers and the repair are stdlib file edits"
      - "Prawduct is written in Python and must never be specific to Python → inapplicable because the anchor layout is language-independent instruction text"
      - "Prawduct guides and reviews; it never implements → conforms: the anchor and its import are governance text at the reconciled-files seam, not product code or tooling"
      - "goals and verification bind; prescribed method is advice → conforms: chunks state acceptance criteria; mid-build departures from the described method are recorded under Goals"
  - artifact: security-model
    dispositions:
      - "an edit to a product-owned file is offered with the exact bytes and applied under one informed confirmation → conforms: doctor offers the layout repair as a dry run printing both files' bytes, and --apply writes them (the repair lands in Chunk 01; doctor surfaces it in Chunk 03)"
      - "untrusted governance state is data, not instructions → conforms: the anchor is static text from the plugin; nothing read from a product file is executed or promoted to authority"
      - "a governed product's content leaves its repo only through a pinned surface with owner-approved bytes → inapplicable because nothing in this plan sends content outside the repo"
partition: serial — 02 reads the constants and layout 01 defines, and 03 moves this repo onto the layout 01 and 02 make every reader understand
last_validated: 2026-10-14
---

# Build plan: the governance anchor lives in AGENTS.md (#942)

## Goals

**Response taken:** Proceed citing a backlog item and owner rulings. #942's 2026-09-30 decisions,
amended by #928 D-8 on 2026-10-10 (`CLAUDE.md` is the one line `@AGENTS.md`, no Claude-only shim).
The two forks D-8 left open were answered by the owner on 2026-10-14, in session:
1. **Claude-only lines** (the `/prawduct:*` check, `claude plugin install`) live inside the
   `AGENTS.md` anchor block as one host-labelled line. A later Codex adapter adds its own line the
   same way.
2. **An existing product `CLAUDE.md`** keeps its own text. The shipped anchor in it is replaced in
   place by `@AGENTS.md`. A `CLAUDE.md` that prawduct creates is exactly `@AGENTS.md`.

**Product:** One governance anchor that every host reads. Claude Code reads it through the
import, and Codex (#928) reads `AGENTS.md` natively. The anchor tells a session the repo is
governed, gives the hardest rules, and says that governance is OFF when the host integration
isn't loaded.

**Architecture:** One home per fact: the anchor text, the import line and the install id are
defined once in `migrate_plugin.py`. Detection stays by substance and replacement stays
exact-match against shipped anchors (`anchor_repair.py`'s module docstring says why). The
protected-prose set stays core-owned (#928 D-6), and this plan adds root `AGENTS.md` to it.
Must stay possible: a second host's labelled line in the same block, without a new layout.

**Constraints:** Nothing rewrites a product's instruction files without `--apply` (owner,
2026-09-30, decision 4). Moving a product's own `CLAUDE.md` content is the product's call
(decision 2). Every shipped anchor must stay repairable: `tests/test_anchor_repair.py` renders
the anchor out of every release tag.

**Tradeoffs accepted:** The anchor grows by one host-labelled line, and every governed session
pays for it. `tests/test_v5_methodology.py` pins the anchor's token budget, so the growth is paid
in place by tightening the anchor's own prose, not by raising the ceiling.

**Decisions made mid-build:**
- Chunk 01 — the anchor constant keeps its name `STATIC_ANCHOR` rather than being renamed. The
  tag reader in `tests/test_anchor_repair.py` renders that name out of every release tag, so
  keeping it means no reader change and no blind spot at the next tag. Settled by "one home per
  fact".
- Chunk 01 — *Not settled by the goals; inferred:* when `AGENTS.md` and `CLAUDE.md` are one file
  through a symlink (either direction), the anchor stays in that file and no import is written,
  because the import would be the file importing itself. A symlink pointing outside the pair is
  never written through or replaced. Surfaced while writing the writer; the owner can override.
- Chunk 01 — a shipped anchor and the current one are swapped preserving the old one's trailing
  newline, because the archive holds both shapes (v1–v3 without, v4–v5 with), and a swap that
  added or ate it would move the product's next line.
- Chunk 01 — doctor Health Check #4's status descriptions moved into this chunk from Chunk 03,
  because a test derives the status list from the code. A chunk boundary defers a deletion, not
  a correction.
- Chunk 02 — the Critic's "CLAUDE.md size" rule in `review-protocol.md` is left as it is. The
  session briefing now measures `CLAUDE.md` plus an imported `AGENTS.md`, so the warning reaches
  the owner without a second copy. Adding the clause would also have raised every reviewer's
  per-mode load past its ceiling. Settled by "every fact has one home" and the payload budget.
- Chunk 02 — `building.md`'s "CLAUDE.md is instructions" sentence is left as it is, for the same
  reason: it stays true with an imported `AGENTS.md`, and the file sits at its ceiling.
- Chunk 02 — migrate reports "the governance anchor was not placed" when `AGENTS.md` links
  outside the pair. This was a Chunk 01 review observation, carried by Chunk 02's commit;
  outside the chunk's described scope, so recorded here.
- Chunk 01 — the reanchor JSON gains a `writes` list (path, how, exact text) beside
  `replacement`, which stays the anchor text, so the preview shows both files' bytes without
  changing an existing key's type.

**Level:** High. The owner ruled every fork. The platform fact (Claude Code reads `AGENTS.md`
natively only when no `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` exists up the
path, and a `CLAUDE.md` holding `@AGENTS.md` imports it in every session) comes from Claude Code's
memory docs as recorded in #942 and D-8. Chunk 03's live check re-verifies it, because this is
fast-moving.

**Inferred** (owner can override):
- When a product `CLAUDE.md` has no shipped anchor and no import, the `@AGENTS.md` line goes at
  the top, so a reader sees it first. Claude loads an import wherever it sits.
- A `CLAUDE.md` that is a symlink to `AGENTS.md` already gives Claude the anchor. Writers never
  write through a symlink. Repair reports this layout as `ok`, and the writers leave it alone.
- An existing `AGENTS.md` gets the anchor block appended, and its own text is byte-identical
  above it.

## Problem

The anchor lives only in `CLAUDE.md`, so a second host never reads it. D-8 rules out a
Claude-only shim in `CLAUDE.md`, so everything the anchor says moves to `AGENTS.md`, and
`CLAUDE.md` keeps only the import that makes Claude load it.

## Success

- New onboards and migrations write the anchor as a sentinel block in `AGENTS.md`, appended when
  the file exists. `CLAUDE.md` is created as exactly `@AGENTS.md`. When a product `CLAUDE.md`
  already exists, the shipped anchor is swapped in place for `@AGENTS.md`, and only the import is
  added when the file has no anchor.
- Every reader that treats `CLAUDE.md` as the anchor or the contract also reads root `AGENTS.md`.
- `/prawduct:doctor` detects the old layout and offers an exact-match repair to the new one.
  Nothing applies it without `--apply`.
- This repo's own `CLAUDE.md` is the single line `@AGENTS.md`, and its content lives in
  `AGENTS.md`.
- A plugin-absent Claude session still reads the notice through the import, and a live check
  shows it.

## Out of scope

- Moving a product's own `CLAUDE.md` content to `AGENTS.md`.
- `.claude/rules/learnings/` portability (D-7) and any Codex install text (#928's adapter).
- An automatic rewrite at session start, or a nudging advisory.

## Status

- [x] Chunk 01 — The anchor moves to AGENTS.md; writers and anchor_repair move together
- [ ] Chunk 02 — Readers and the protected-path classifier know AGENTS.md
- [ ] Chunk 03 — This repo onto the layout, doctor text, release notes, live check

Context: Re-cut 2026-10-14 from the 2026-09-30 draft. D-8 removed the Claude shim, so the split
into a neutral and a Claude text is gone. This repo's own `CLAUDE.md` moved into scope (#942
acceptance). The re-cut kept the earlier lesson: `anchor_repair.py` imports the current anchor,
and `tests/test_anchor_repair.py` renders it out of every release tag, so the anchor's shape and
the repair change in one chunk.

## Chunk 01 — The anchor moves to AGENTS.md; writers and anchor_repair move together

**Type:** code

**Description:** In `plugin/lib/migrate_plugin.py`, the anchor stays one text under its existing
`ANCHOR_SENTINEL` marker. It is re-worded host-neutral, with one host-labelled line for Claude
Code (the `/prawduct:*` check and `claude plugin install {PLUGIN_ID}`). Add `CLAUDE_IMPORT =
"@AGENTS.md"`. The pre-change anchor is frozen into `anchor_repair.SUPERSEDED_ANCHORS`, generated
from the bytes HEAD renders and not retyped. The writers:
- **`AGENTS.md`:** create it with the block, or append the block to an existing file. If the
  sentinel is present, it's a no-op.
- **`CLAUDE.md`:** create it as exactly `@AGENTS.md`. On an existing file, swap a shipped anchor
  in place for the import, strip a pre-2.0 BEGIN/END block exactly as today, or add the import at
  the top when neither is present. If the file already imports `AGENTS.md`, it's a no-op.
- **Symlink:** a `CLAUDE.md` that links to `AGENTS.md` is left alone, and nothing is written
  through it.
- **Line endings:** CRLF files stay CRLF.

`init_product.py` and `migrate_plugin.py` call the writers and report both files as created or
edited. Record the `architecture.md` § Direction `[DECISION]` beneath the reconciled-files norm,
and the same in `security-model.md` if its enumeration names `CLAUDE.md`.

`plugin/lib/anchor_repair.py` grades the pair. Substance probes read `AGENTS.md`'s block. A new
status, `legacy-layout`, covers a shipped anchor still in `CLAUDE.md`. `repair()` writes the
`AGENTS.md` block and swaps the `CLAUDE.md` anchor for the import, and the dry run shows both
files' bytes. An edited anchor in `CLAUDE.md` is still `stale-modified` and left to the owner.
`tests/test_anchor_repair.py`'s shipped-anchor reader learns the new names, so a tag cut after
this still renders its anchor.

**Acceptance criteria:**
- Fresh onboard of an empty repo: `AGENTS.md` holds the block, and `CLAUDE.md` is exactly
  `@AGENTS.md` plus a newline.
- Existing `AGENTS.md` with product text: that text is byte-identical above the appended block.
- Existing product `CLAUDE.md` with a shipped anchor: the anchor becomes `@AGENTS.md` in place,
  and the text around it is byte-identical. With no anchor: only the import line is added.
- Running either writer twice changes nothing. A symlinked `CLAUDE.md` is not written through.
- `check()` reports `ok` for a freshly written repo and `legacy-layout` for every shipped
  `CLAUDE.md` anchor. `repair(apply=True)` converts each one, and a second run reports `ok`.
- The shipped-anchor reader renders the current tree's anchor under the new names, and a test
  proves it isn't blind.
- The anchor's token budget test passes without raising its ceiling.

**Done when:** tests pass, and `/prawduct:critic` has run on the chunk.

## Chunk 02 — Readers and the protected-path classifier know AGENTS.md

**Type:** code

**Description:** Enumerate by query (`grep -rn 'CLAUDE\.md\|claude_md' plugin/lib plugin/bin
plugin/hooks`), and bring each reader along:
- `buildplan_refs._TRIVIAL_PROTECTED_PATHS` gains root `AGENTS.md` (exact match,
  `agents-md-edited`). Confirm by test that its consumers `gates.py`, `coverage_algebra.py` and
  `coverage.py` inherit it.
- `onboarding_probes` finds the anchor marker in `AGENTS.md`.
- `briefing.py`'s size check measures what Claude loads (`CLAUDE.md` plus an imported
  `AGENTS.md`), and its critical-rules read covers both files.
- The jurisdiction corpus in `prawduct-hook` includes root `AGENTS.md`.
- The wording in `plugin_activation.py` and `critic_consolidate.py`.

Then sweep the prose that describes the anchor or the protected set: skills, methodology, docs,
templates, agents and `documentation/` (28 files mention `CLAUDE.md` today). Search for the claim
("anchor", "protected", "CLAUDE.md"), not just the tokens edited, and delete superseded sentences
rather than adding beside them.

**Acceptance criteria:**
- A root `AGENTS.md` edit reopens the Critic gate and fails the trivial bound, exactly as root
  `CLAUDE.md` does. A nested AGENTS.md, one in a subdirectory, does not.
- The onboarding-marker probe finds a marker in `AGENTS.md` alone.
- The jurisdiction corpus includes a root `AGENTS.md`.
- The claim sweep's grep returns only sentences true of the new layout.

**Done when:** tests pass, and `/prawduct:critic` has run on the chunk.

## Chunk 03 — This repo onto the layout, doctor text, release notes, live check

**Type:** cumulative-final

**Description:** Move this repo's `CLAUDE.md` content verbatim into a new root `AGENTS.md`, and
make `CLAUDE.md` the single line `@AGENTS.md`. Repoint every test that reads this repo's
`CLAUDE.md` as the contract to `AGENTS.md`, found by query (`grep -rln '"CLAUDE.md"' tests`), and
check each one for whether it means "the file Claude reads" or "the contract text". Doctor
Check #4's text says what `legacy-layout` means and what the repair writes, and the
`/prawduct:doctor` skill describes the repair as offered, never applied. Fix the stale status
line and intro in `documentation/issues/928-requirements.md`, which still say "D-1, D-2, D-4
ruled" and "does not decide the open questions", and record row 29/30 progress there. Add a
`plugin/CHANGELOG.md` rolling-notes entry and a `.prawduct/change-log.md` entry
(`scope=agents-md-anchor`).

Live check: in a scratch repo onboarded by the new writer, run `claude -p` in a fresh process
with the plugin disabled. Ask what the repo's governance instructions say, and confirm the
anchor's plugin-absent notice reaches context through the import. A same-session re-invocation
proves nothing, because the harness caches what it loaded.

**Acceptance criteria:**
- This repo's `CLAUDE.md` is exactly `@AGENTS.md`, and the session digest and briefing still
  find the rules they read.
- `/prawduct:doctor` on a legacy-layout repo prints the exact bytes the repair would write, and
  applies nothing without `--apply`.
- The live check's transcript excerpt is recorded in the chunk's reflection.

**Done when:** tests pass, the boundary `/prawduct:critic cumulative` has run, and the suite is
recorded green.

## Verification Strategy

Beyond the unit tests: onboard a scratch repo with each starting layout (empty, product
`CLAUDE.md` only, product `AGENTS.md` only, both, a symlinked `CLAUDE.md`, a pre-2.0 block), and
diff the files the writers and the repair produce against the acceptance criteria. Run doctor on
a repo pinned to a shipped anchor. Do the Chunk 03 live check in a fresh process.
