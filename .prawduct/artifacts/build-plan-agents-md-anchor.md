---
artifact: build-plan
version: 2
scope: agents-md-anchor
branch: feature/942-agents-md-anchor
depends_on:
  - artifact: architecture
  - artifact: security-model
governed_by:
  - artifact: architecture
    dispositions:
      - "the plugin writes nothing into a governed repo except .prawduct/, the evidence store and the reconciled files (.gitignore, .claude/settings*.json, CLAUDE.md's anchor) → amendment proposed: AGENTS.md's anchor block joins the enumeration, recorded as a [DECISION] beneath the norm in Chunk 01, citing the owner's #942 ruling as the authority. The statement itself is not edited to match the code"
      - "every fact has one home → conforms: the neutral anchor text, the Claude shim text and the install id each keep one definition in migrate_plugin.py; anchor_repair imports them"
  - artifact: security-model
    dispositions:
      - "an edit to a product-owned file is offered with the exact bytes and applied under one informed confirmation → conforms: doctor offers the layout repair as a dry run, and --apply writes it (Chunk 03)"
partition: serial — 02 reads the constants and file layout 01 defines, and 03's repair composes 01's writers with 02's readers
last_validated: 2026-09-30
---

# Build plan: the governance anchor lives in AGENTS.md (#942)

## Requirements Confidence

**Level:** High

**Why:** The owner ruled on each fork on 2026-09-30 (issue #942, comment 5921278341). The
platform facts come from Claude Code's memory docs, read 2026-09-30: Claude Code reads
`AGENTS.md` natively only when no `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` exists
up the path, and a `CLAUDE.md` holding `@AGENTS.md` imports it in every Claude session,
including versions without native support.

**Open assumptions / unknowns:**
- [ASSUMPTION: a `CLAUDE.md` that is a symlink to `AGENTS.md` has no Claude-only place for the shim, so the writers refuse that layout with a named reason and doctor reports it, rather than writing a self-import | MED impact | user can override]
- [ASSUMPTION: the `@AGENTS.md` import goes where the old anchor sat in an existing `CLAUDE.md` (the repair swaps in place). A new `CLAUDE.md` opens with it | LOW impact | user can override]
- [ASSUMPTION: this repo's own `CLAUDE.md` is the framework's contract, not a product anchor, and has no `PRAWDUCT:ANCHOR`, so it is out of scope | LOW impact | user can override]

**What would raise confidence:** the live check in Chunk 03, a fresh `claude -p` session in a
scratch repo that shows the imported anchor text is in context.

## Problem

The anchor tells an agent the repo is governed, the hardest rules, and that governance is off
when the plugin isn't loaded. Today it lives only in `CLAUDE.md`, so a second host (Codex, #928)
never reads it. Its text is also Claude-specific ("a Claude Code plugin", `/prawduct:*`,
`claude plugin install`), so moving it verbatim would give another host wrong instructions.

## Success

- New onboards and migrations write the host-neutral anchor as a sentinel block in `AGENTS.md`
  (appended when the file already exists). `CLAUDE.md` carries an `@AGENTS.md` import plus a
  short Claude-only shim: the `/prawduct:*` check, `claude plugin install prawduct@prawduct`, and
  `/prawduct:methodology building`.
- Every reader that treats `CLAUDE.md` as the anchor or the contract also reads root `AGENTS.md`:
  the protected-path classifier, the onboarding markers, the briefing's size check and
  critical-rules read, and the jurisdiction corpus.
- `/prawduct:doctor` detects the old layout (the anchor in `CLAUDE.md`) and offers an exact-match
  repair to the new one. Nothing applies it without `--apply`.
- A plugin-absent Claude session still reads the notice (through the import), and a live check
  shows it.

## Out of scope

- Moving a product's own `CLAUDE.md` content to `AGENTS.md`. That is the product's call.
- `.claude/rules/learnings/` portability, and any Codex-specific install text (#928's adapter).
- An automatic rewrite at session start, or a nudging advisory.
- This repo's own `CLAUDE.md`.

## Status

- [ ] Chunk 01 — Split the anchor; writers and anchor_repair move together
- [ ] Chunk 02 — Readers and the protected-path classifier know AGENTS.md
- [ ] Chunk 03 — Doctor text, release notes, live check

Context: Plan drafted 2026-09-30 from the owner's #942 ruling. No code yet. Re-cut before any
code: `anchor_repair.py` imports `STATIC_ANCHOR` as its "current" anchor, and
`tests/test_anchor_repair.py` renders `STATIC_ANCHOR` out of every release tag's
`migrate_plugin.py` to prove each shipped anchor is repairable. Changing the anchor's shape
without moving the repair and that reader in the same chunk would ship a `check()` that grades
every new-layout repo as broken, and blind the tag reader for the first tag cut after it. So the
repair's core moved from Chunk 03 into Chunk 01.

## Chunk 01 — Split the anchor; writers and anchor_repair move together

**Type:** code

**Description:** In `plugin/lib/migrate_plugin.py`, replace the single `STATIC_ANCHOR` with two
texts that each have one home: `NEUTRAL_ANCHOR` (the `PRAWDUCT:ANCHOR` sentinel block for
`AGENTS.md`: governed by Prawduct; if your agent's Prawduct integration isn't loaded, governance
is OFF, so tell the user and don't proceed as if governed; read the build cycle before code; the
hardest rules; enforcement while loaded) and `CLAUDE_SHIM` (a separate sentinel, one that
doesn't contain `PRAWDUCT:ANCHOR` as a substring, then `@AGENTS.md`, then the Claude-only
lines). The writers:
- **`AGENTS.md`:** create it with the neutral block, or append the block to an existing file.
  If the sentinel is already present, it's a no-op.
- **`CLAUDE.md`:** create it as the shim, or add the shim to an existing file. If the shim
  sentinel is present, it's a no-op. If the file already imports `AGENTS.md`, add only the
  Claude-only lines.
- **Symlink:** a `CLAUDE.md` that is a symlink to `AGENTS.md` is refused with a named reason.
- **Line endings:** CRLF files stay CRLF.

`init_product.py` and `migrate_plugin.py` call the writers and report both files in
created/edited. Amend `architecture.md` § Direction by recording a `[DECISION]` beneath the
reconciled-files norm: `AGENTS.md`'s anchor block joins the enumeration, authority is the #942
ruling. `security-model.md` gets the same if its enumeration names `CLAUDE.md`.

In the same chunk, `plugin/lib/anchor_repair.py` learns the new layout. The pre-change
`STATIC_ANCHOR` is frozen into `SUPERSEDED_ANCHORS`. `check()` grades the pair of files, and the
two probes are read across both: the install notice lives in the shim, the stage-keyed rule in
the neutral block. A new status, `legacy-layout`, covers an anchor in `CLAUDE.md` with no
`AGENTS.md` block. `repair()` converts an exact match of any shipped `CLAUDE.md` anchor into the
shim and writes the neutral block. `tests/test_anchor_repair.py`'s shipped-anchor reader learns
the new constant names, so a tag cut after this change still yields its anchor and never reads
as blind.

**Acceptance criteria:**
- Fresh onboard of an empty repo: `AGENTS.md` holds the neutral block, and `CLAUDE.md` holds
  `@AGENTS.md` and the shim.
- Existing `AGENTS.md` with product text: the text is byte-identical above the appended block.
- Existing product `CLAUDE.md` with no anchor: the product text is untouched and the shim is
  added.
- Running either writer twice changes nothing.
- A symlinked `CLAUDE.md` is refused, and nothing is written through it.
- The neutral text contains no `claude`, `/prawduct:` or `Claude Code` token. A test pins this.
- `anchor_repair.check()` reports `ok` for a freshly written new-layout repo and `legacy-layout`
  for each shipped `CLAUDE.md` anchor. `repair(apply=True)` converts each one, and a second run
  reports `ok`. An edited anchor still reports `stale-modified` and is left alone.
- The shipped-anchor reader renders the anchor for the current tree under the new names. A test
  proves it isn't blind.
- `tests/test_plugin_init.py`, the migrate tests and `tests/test_anchor_repair.py` cover each
  case above.

**Done when:** tests pass, and `/prawduct:critic` has run on the chunk.

## Chunk 02 — Readers and the protected-path classifier know AGENTS.md

**Type:** code

**Description:** Enumerate by query (`grep -rn '"CLAUDE\.md"\|/ "CLAUDE\.md"' plugin`) and
bring each reader along:
- `buildplan_refs._TRIVIAL_PROTECTED_PATHS` gains root `AGENTS.md` (exact match,
  `agents-md-edited`). Its consumers `gitstate.py`, `coverage_algebra.py` and `coverage.py`
  inherit it; confirm each by test rather than by reading.
- `onboarding_probes._claude_md_text` reads both files for markers.
- `briefing.py`'s size check and critical-rules read.
- `prawduct-hook`'s jurisdiction corpus.
- `plugin_activation.py`'s wording.

Then sweep the prose that describes the anchor: `plugin/skills/onboard/SKILL.md`,
`plugin/docs/doctor-vs-janitor.md`, `documentation/project-structure.md`, the session digest if
it names the anchor file, and the `Type: trivial` bullet in `methodology/planning.md`. Search for
the claim ("anchor", "CLAUDE.md"), not just the tokens edited.

**Acceptance criteria:**
- A root `AGENTS.md` edit reopens the Critic gate and fails the `Type: trivial` bound, exactly
  as root `CLAUDE.md` does. A nested `foo/AGENTS.md` does not.
- The onboarding-marker probe finds a marker in `AGENTS.md` alone.
- The jurisdiction corpus includes a root `AGENTS.md`.
- The claim sweep's grep returns only sentences that are true of the new layout.

**Done when:** tests pass, and `/prawduct:critic` has run on the chunk.

## Chunk 03 — Doctor text, release notes, live check

**Type:** code

**Description:** Doctor Check #4's text says what `legacy-layout` means and what the offered
repair writes, and the `/prawduct:doctor` skill describes the repair as offered, never applied. Add a `plugin/CHANGELOG.md` rolling-notes
entry and a `.prawduct/change-log.md` entry (`scope=agents-md-anchor`).

Live check: in a scratch repo onboarded by the new writer, run `claude -p` in a fresh process
with the plugin disabled. Ask what the repo's governance instructions say, and confirm the
neutral notice and the shim both reach context. A same-session re-invocation proves nothing,
because the harness caches what it loaded.

**Acceptance criteria:**
- `/prawduct:doctor` on a legacy-layout repo prints the exact bytes the repair would write, and
  applies nothing without `--apply`.
- The live check's transcript excerpt is recorded in the chunk's reflection.

**Done when:** tests pass; the boundary `/prawduct:critic` (final) has run; the suite is recorded
green.
