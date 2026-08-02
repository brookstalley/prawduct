---
artifact: build-plan
version: 2
scope: backlog-block-field-writes
depends_on:
  - artifact: data-model
  - artifact: api-contract
governed_by:
  - artifact: api-contract
    dispositions:
      - "additive-first evolution; flag names/exit codes/--json keys never repurposed → conforms (four new flags on `update`, one on `file`; nothing existing changes meaning)"
      - "exit codes are the contract; errors attributed, never stack traces → conforms (new rejections reuse the existing `validation` class)"
      - "whole-surface semver, no per-subcommand version; only `print-install-reference`/`version` are the `stable` tier → inapplicable because `backlog` is internal/unstable"
  - artifact: data-model
    dispositions:
      - "governance verdicts computed from the append-only fact ledger, no model in a fact's write path → inapplicable because this plan touches the backlog adapter, not the Critic data plane"
      - "facts immutable and append-only; a state change is a new fact, never an edit in place → inapplicable, same reason; a backlog item is mutable state by design, not a fact"
      - "derived views are disposable and never authoritative → inapplicable, same reason"
      - "a fact written by a newer schema than the reader is a loud block → inapplicable, same reason; the block's own version rule is §7 additive-only-forever, which this plan conforms to by adding keys and repurposing none"
      - "two stores, two lifetimes — committed answers distinct from per-clone caches → inapplicable because this plan adds no store; it writes fields into the existing issue body"
      - "`backlog_service_repo` selects the authoritative store; writes never bypass the skill on either backend → conforms, and is the norm this plan serves: the writes the skill already instructs were unreachable through the sanctioned path, which is what made reaching around it tempting"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is a P0 constraint; the two PR-boundary reviews run in parallel → inapplicable because this plan changes no gate, mode, or chunk structure"
      - "proportionality ratchets both ways; adding a control names the yield it expects and emits it observably → conforms; Chunk 02's guard names its yield (the four drifted instructions it would have caught) and fails with the specific field and op, not a bare assert"
      - "state-file growth past its threshold is an advisory, never a hard block → inapplicable because this plan writes no state file"
last_validated: 2026-08-02
---

## Requirements Confidence

**Level:** High

**Why:** The defect is measured, not inferred (398 issues counted by field). Both design forks — what `reviewed:` means, and which fields gain write paths — were put to the user and answered. The remaining choices are mechanical and follow existing precedent in the same module.

**Open assumptions / unknowns:**

- [ASSUMPTION: the block key stays hyphenated `closed-by`, not the data-model's prose spelling `closed_by` | HIGH impact | reversible] 149 live items spell it `closed-by` and zero spell it `closed_by`. Writing the underscore form would create two spellings of one field and orphan every existing value. The data-model doc is what gets corrected, not the data.
- [ASSUMPTION: `--reviewed` is a boolean that stamps *today*, never an arbitrary date | MED impact | user can override] A backdated "I re-confirmed this" is unfalsifiable and pure forgery surface; the only honest assertion is "now". This also keeps the flag off the valued-flag path.

**What would raise confidence:** N/A — the baseline suite was green at the branch point and the affected functions have direct test coverage already. (Suite totals are deliberately not restated here: a count copied into prose is stale the next time a test lands. `prawduct-hook test-status` is the live answer.)

## Status

- [ ] Chunk 01: Block-field write path through `update` and `file`
- [ ] Chunk 02: Instruction/spec coherence + the phantom-capability class guard
Context: Plan authored 2026-08-02 from #550, itself found while triaging `incoming-bugs/`. `active_build_plan` repointed here from `artifacts/build-plan-v3.2.0-golive.md` — **the golive plan is still in flight** (its Chunks 01, 05, 07, 08, 09 unchecked), so repoint back when this merges.

**Both chunks are complete and the branch is PR-ready.** Cumulative gate satisfied at `c9f2bb8` (4 review facts, 0 unresolved blocking); the final `verify-resolutions` returned 0 blocking / 0 warning / 0 note. Suite green and record-lint clean — `prawduct-hook test-status` is the live answer; a count copied into prose is stale the next time a test lands.

Review history, since the count is the interesting part: Chunk 01 took two resolution passes (a key allowlist that never constrained values, then a value guard narrower than the parser it protected). The cumulative returned 0 blocking / 8 warning, of which two were live defects — `--body` injection through an unterminated fence, and `--reviewed <date>` silently stamping today. Two further passes closed the residue, most of it in the test scaffolding rather than the shipped path. The recurring shape — a guard narrower than the mechanism it guards, three times, twice after the learning was written — is recorded in `learnings.md` and `.session-reflected`.

Chunk 02's open question is answered: `reviewed:` and `verified` are one concept at two fidelities (TF2 asks for "re-checked by `<actor>` on `<date>`"; TF3 counts `reviewed:` stamps), `reviewed:` is the live encoding, and the actor half comes from the API identity rather than a forgeable block field.

The checkboxes above stay `[ ]` on purpose: they are a derived view and only `status=shipped` flips them, so the two statusless tagged change-log entries riding in the feature PR are the correct release-pending state, not a missed step. **On merge, repoint `active_build_plan` back to the golive plan** — it is still in flight.

## Verification Strategy

Beyond tests, each chunk is verified against the **live backlog**, because the defect is precisely that the code path reports success while changing nothing — a mock cannot distinguish the bug from the fix. Chunk 01 closes by setting `refs:` on the real item this work already needs it on (#207, the coordinator-dispatch item whose linkage is currently carried only as a comment), then re-reading the block to confirm the value landed and no sibling field moved.

### Verification record — Chunk 01, 2026-08-02

Run against `brookstalley/prawduct#207` on the real GitHub backend (not `FakeGitHub`), via the working-tree `prawduct-hook` (`which` resolves to this checkout's `plugin/bin/`, and the backlog CLI is imported lazily from `plugin/lib/`, so there is no bundled copy that could have served stale code).

`prawduct-hook backlog update brookstalley/prawduct#207 --refs "<existing value>, incoming-bugs/archive/…"` → envelope ok. Re-read and diffed the parsed block before/after:

- key set identical (9 keys, same order); `refs` the **only** changed line
- the prior `refs` value preserved verbatim inside the new one (append, not replace)
- `original_body` — 10,611 chars, JSON-string-encoded, the single riskiest value in the block — byte-identical
- exactly one `prawduct` fence; human prose above it unchanged
- **`reviewed:` did not move**, confirming on a real write that no other edit implies a re-confirmation stamp

This is the check the plan argues a mock cannot perform: the original defect returns `status: ok` while writing nothing, so only a before/after read of the live body distinguishes "wrote correctly" from "wrote nothing".

## Build Chunks

### Chunk 01: Block-field write path through `update` and `file`

- **Description:** Give the four block fields a sanctioned write path. `update` gains `--refs`, `--revisit`, `--closed-by` (valued) and `--reviewed` (boolean, stamps today); `file` gains `--refs` so a natively-filed item can carry one from birth. The SEC-2 mass-assignment guard is *extended, not loosened* — provenance and identity fields (`original_title`, `original_body`, `id_aliases`, `v`, `automated`, `worker`, `provenance`) and fields owned by another op (`claimed_at`, `related`, `superseded_by`, `verified`, `attachments`) all stay rejected.
- **Depends on:** none
- **Artifacts consumed:** `documentation/backlog-service-data-model.md` §1.2/§2, `documentation/backlog-service-api-contract.md`
- **Deliverables:** `plugin/lib/backlog/core.py` (`_UPDATE_BLOCK` allowlist, block composition in `update_item`, `mark_reviewed` + injected `now` clock seam following `claim`'s precedent, `refs` param on `file_item`), `plugin/lib/backlog/cli.py` (`_run_update` valued/boolean flag sets, `_run_file`, `_HELP` usage text), `plugin/lib/backlog/encode.py` (`check_block_value`, the value-level guard; the four editorial fields projected in `decode_item`)

  <!-- `encode.py` was added to this chunk mid-build, not planned into it. Two
       findings drove it and both are recorded rather than absorbed silently:
       the value-level injection guard (R-1) has to live beside the parser whose
       behaviour defines it, and the `decode_item` projection closes the gap
       where a write could not be confirmed from the response that performed it
       — the same blindness that hid this defect for the whole cutover. -->

- **Decision — the projection reuses the field names, which collides with §1.1:** the data model already defines an item field `reviewed`/verification as `{by, on}`, homed as block `verified` plus a cache `reviewed` column for the TF2 stale-verification query. The block field this chunk makes writable is a bare **date** on 300 live items meaning *"someone re-read this and it still holds"*. Those are adjacent but not identical, and this chunk deliberately does **not** settle which — it ships the write path and hands the modelling question to Chunk 02, whose data-model deliverable is widened below to cover §1.1. Recorded here so the ambiguity is visible rather than resolved by accident in whichever file gets edited first.
- **Tests:** unit — each field round-trips through `upsert_block_field` with every sibling key intact; empty value clears; `--reviewed` stamps the injected `now` and is *not* set by any other update; rejection list still rejects each provenance/identity/other-op field by name. Integration — `--body` plus a block flag in one call compose correctly (body edit must not clobber the block write, and vice versa); a no-op update issues no body PATCH.
- **Acceptance criteria:** `backlog update <id> --refs "x.md"` changes `refs:` and nothing else; `--reviewed` stamps today; `backlog file --refs "x.md"` creates an item whose block carries it; every currently-rejected field is still rejected.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Live verification: set `refs:` on #207 against the real backend, re-read, confirm the value landed and no sibling field moved
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 02: Instruction/spec coherence + the phantom-capability class guard

- **Description:** Make the documentation true, then stop the class of drift that hid this for the whole cutover. Three `SKILL.md` instructions currently name writes the adapter could not perform; the data-model's block schema never listed these four fields at all. The structural half is the guard: `test_backlog_instruction_surface.py` today catches phantom **safety mechanisms** (its own docstring scopes it to "the mutation-safety family") and is blind to phantom **capabilities** — a skill telling the model to set a field no op can write. Extending it to that sibling class is the Principle 16 fix; the four flags alone are just the symptom.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `plugin/skills/backlog/SKILL.md`, `documentation/backlog-service-data-model.md`, `documentation/backlog-service-api-contract.md`
- **Deliverables:** `plugin/skills/backlog/SKILL.md` (the `update` line's "always set `reviewed:` on any touch" becomes explicit re-confirmation; triage step 2's `refs:` instruction and the ship workflow's `closed-by=` gain their real flag spellings; **`accepted-by=`** — a fourth phantom capability found while reading — is redirected to `claim`/`unclaim`, which *is* the claim mechanism on this backend, rather than implemented), `documentation/backlog-service-data-model.md` (§2 block schema gains the four fields under §7 additive-only-forever; §1.2 records which are writable and which stay import-only; **§1.1** resolves the `reviewed`-vs-`verified` collision Chunk 01 deliberately left open), `documentation/backlog-service-api-contract.md` (the `update` field list), `tests/test_backlog_instruction_surface.py` (the new check)
- **Open question this chunk must answer, not assume:** is the block's `reviewed:` date the same concept as §1.1's `verified` `{by, on}` verification, or a distinct triage re-confirmation? Read the TF2 requirement before deciding — the answer determines whether §1.1 gains a second row or the two are unified, and picking by convenience would leave one field defined twice.
- **Tests:** the guard asserts every block field a scanned skill instructs the model to *set* is writable by some exposed op — and carries a **discrimination self-test** proving it fails on a synthetic skill file claiming an unwritable field, so it cannot silently pass by matching nothing (the failure mode `#200` names).
- **Acceptance criteria:** the guard passes on the fixed tree; the same guard fails when pointed at a fixture claiming `added:` is settable; no instruction in `SKILL.md` names a field write with no backing op.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and full suite passes
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its review passes. Chunk 02's `cumulative` makes the branch PR-ready; `/prawduct:pr create` runs when the user asks.

- After Chunk 01: confirm the block composition order against a real item before widening to docs — the live check is the one that can distinguish "wrote nothing" from "wrote correctly".
- After Chunk 02 (cumulative): verify the new guard actually discriminates rather than matching an empty set.
