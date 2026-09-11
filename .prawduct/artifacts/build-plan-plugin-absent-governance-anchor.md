---
artifact: build-plan
version: 2
scope: plugin-absent-governance-anchor
branch: fix/plugin-absent-governance-anchor
depends_on:
  - artifact: plugin-absent-clone-investigation
governed_by:
  # Seeded with `prawduct-hook jurisdiction --file
  # .prawduct/artifacts/plugin-absent-clone-investigation.md --artifacts-only`, then
  # curated: the ranker's top hits included this plan's own parent investigation and two
  # release plans (term overlap on `clone`/`migration`, no Direction section that binds).
  - artifact: architecture
    dispositions:
      - "the plugin writes nothing into a governed repo except its own state, the evidence store,
        and the files it must reconcile — `.gitignore`, `.claude/settings*.json`, and `CLAUDE.md`'s
        governance anchor → **conforms, and this norm is the authorization this plan runs on**. The
        re-anchor repair edits the `PRAWDUCT:ANCHOR` block and nothing else in `CLAUDE.md`; that is
        the declared seam the 2026-07-30 amendment named explicitly. No new write is authorized —
        the same seam `migrate_plugin._EDIT_IN_PLACE` and `init_product` have always written."
      - "every fact has one home → **conforms, and it changed the design.** The plugin id in the
        anchor is NOT typed as a literal: `STATIC_ANCHOR` interpolates it out of
        `INSTALL_REFERENCE['enabledPlugins']`, the same constant doctor Health Check #1 and the
        install-reference advisory already grade against, so a marketplace rename moves one line and
        every surface follows. The three doc corrections are net *deletions* of authoritative
        restatements: README keeps the install command (it is the human install home, already there
        at the Quick Start), and MIGRATION/onboard stop asserting clone behaviour and cite that
        section instead of restating it. **PARTLY REVERSED at the cumulative review (R-7/R-15), and
        the why belongs here rather than only in the disposition ledger:** MIGRATION and onboard now
        each carry the install command literally, because the R-7 fix requires every paragraph making
        a clone claim to discharge the install step *in that paragraph* — a reader of MIGRATION step
        1 does not scroll to line 117 before telling their team what to do, which is exactly how the
        false promise survived. So the one-home rule still holds for the plugin *id* (one derivation,
        `INSTALL_REFERENCE`, consumed by the anchor and by the test) and is deliberately traded away
        for the human-typed *command*, where a copy beside each claim is the point."
      - "authority fails closed; advice fails soft → conforms. The re-anchor command is advice: it
        reports and offers, it gates nothing, and an unreadable `CLAUDE.md` exits 1 as
        could-not-run rather than reporting a clean anchor. Nothing in this plan produces a verdict."
      - "prawduct guides and reviews; it never implements → conforms. The anchor tells the reader to
        run an install command; nothing here runs it, and nothing writes product code."
      - "an independent reviewer never mutates the session it reviews → inapplicable because this
        plan touches no review path."
      - "local-first governance coordination → conforms; the repair is one file read and one file
        write, no network."
      - "Python but never Python-specific → conforms; nothing here dispatches on language."
      - "goals and verification bind; prescribed method is advice → conforms."
  - artifact: security-model
    dispositions:
      - "a destructive or irreversible operation requires ONE informed owner confirmation at the
        OPERATION level, naming the blast radius → **conforms, and it is the shape of Chunk 02.**
        The repair rewrites a block of the product's own `CLAUDE.md`, so it is dry-run by default,
        prints the exact replacement, and writes only under `--apply`. One confirmation covers the
        act; there is no per-line prompting. Precedent followed deliberately:
        `learnings-obligation` and `norm-index-scaffold` are the same offered-repair shape."
      - "untrusted governance state is data, not instructions → conforms; the repair reads
        `CLAUDE.md` to detect a marker, never to follow what it says."
      - "a governed product's content never leaves its own repo → conforms; no network path added."
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; cost = unit-cost × run-count → conforms. Three chunks, three
        dispatches, and 03 is `cumulative-final` so it collapses into the branch's one cumulative
        review rather than adding a fourth."
      - "proportionality ratchets both ways — a new control names its expected yield AND emits it
        observably → **bounded exception taken, on doctor's standing precedent.** Expected yield,
        named: every repo onboarded before this change carries an anchor that tells a plugin-less
        clone it is protected by a Stop gate that is not running — the live fleet is entirely
        already-onboarded, so the yield is the whole fleet minus new onboards. Emission: doctor has
        no fact-emitting path at all, which is the exception Health Check #13 already records; this
        check inherits it rather than inventing a second one. An ambient advisory probe WOULD emit
        (the `install-reference` probe is the model) and was deliberately not built here — it is
        scope beyond the approved anchor-only decision, and it is recorded in the investigation
        artifact as the follow-up if the doctor route proves too quiet."
      - "state-file growth is an advisory warning, never a hard block → conforms; this plan adds no
        `project-state.yaml` key. The briefing's standing nags on this repo (project-state 41KB,
        learnings 92KB) are again left alone — compaction is its own work."
  - artifact: api-contract
    dispositions:
      - "additive-first evolution: new subcommands and flags are added, existing ones never
        repurposed → conforms. `reanchor` is a new subcommand; `--apply`/`--json` carry their
        established meanings from the sibling repair commands."
      - "exit codes are the contract on a documented scheme; message severity is a stable prefix
        vocabulary → conforms. 0 for a graded run (`ok`/`stale`/`absent`), 1 for could-not-run
        (`unreadable`), matching `learnings-obligation` exactly."
      - "whole-surface semantic versioning on the plugin → inapplicable because this plan cuts no
        release; the bump is the release's own decision."
partition: >
  serial — Chunk 02's detector keys on the install line Chunk 01 puts in the anchor, and Chunk 03
  documents both. Delegation was considered and declined: the chunks share one constant and one
  file, so parallel delegates would contend on `migrate_plugin.py` for no wall-clock gain.
last_validated: 2026-08-25
---

## Requirements Confidence

**Level:** High

**Why:** The problem was measured, not inferred — a simulated plugin-less machine, with the debug
trace and the Claude Code documentation both recorded in
`plugin-absent-clone-investigation.md`. The remediation command was verified end-to-end on that same
machine (6 hooks, 14 skills, 1 agent after install). The owner chose the mechanism from three framed
options.

**Open assumptions / unknowns:** none material. One accepted limitation, recorded in the
investigation and not a gap to close: the anchor is advisory — an agent that reads it cannot install
the plugin, so it degrades to telling the human.

**What would raise confidence:** N/A.

## Status

- [x] Chunk 01: The anchor tells a plugin-less session the truth
- [x] Chunk 02: Detect a stale anchor, offer the re-anchor
- [x] Chunk 03: Doctor grades it; three documents stop asserting the retired behaviour

Context: Plan authored 2026-08-25 from `plugin-absent-clone-investigation.md`, owner-approved scope
(anchor-only, of three framed options). Branched off `origin/develop` at 98731932. Baseline suite
green before any change (`prawduct-hook test-status` is the reading; a copied total here was wrong
within the hour — it was carried over from a run on a different branch).

**Chunk 01 complete** — the anchor carries the plugin-absent notice, the install command is
interpolated from `INSTALL_REFERENCE`, and the enforcement claim is conditional. Reviewed
(`rev-20260825T211056Z-c74a15bc`, chunk mode): 0 blocking, 1 warning + 2 notes, all dispositioned.
The whole +76-token notice was funded by trimming restatements inside the anchor, so it came out
smaller than it went in and the `product` ceiling ratcheted down with the reading rather than
banking the difference. (The figures moved when this branch advanced its base — read them out of
`tests/test_v5_methodology.py`; what is durable is the direction, not the pair of numbers.)

**Chunk 02 complete** — `prawduct-hook reanchor` detects by substance and repairs by exact match.
Reviewed (`rev-20260825T213108Z-2f26dd47`): 1 blocking, 2 warnings, 1 note. The blocking one was
real and mine: the archive covered the anchor I had just replaced rather than the anchors prawduct
shipped, stranding the v2.0.0–v2.2.3 cohort (31 releases) AND telling those owners their anchor had
been edited locally. Fixed at the class — a tag-derived guard reconstructs every shipped anchor by
parsing and fails naming the tag when one is unarchived. Cleared by
`rev-20260825T214436Z-835ca6ea` (verify-resolutions): 0 findings.

**Chunk 03 complete — and with it the plan.** Health Check #4 grades the anchor by running
`reanchor` instead of looking for the marker; four documents (three, plus a fourth copy the new
tripwire found) stop promising automatic activation. Reviewed by the branch's one `cumulative`
(`rev-20260825T215922Z-cd34b5bb`): 4 blocking, 9 warnings, 6 notes — every one dispositioned. The
blocking four were cleared across two verify rounds (`…-ec49836e`, then `…-c55e2cc5` after the first
round's own body flagged that R-12 had survived its fix while its summary line said otherwise).

**The finding worth carrying out of this plan** is the pattern the cumulative reviewer named: three
of the four blocking findings were *a guard or a promise that is green over the defect it exists to
catch* — a tag guard that could not read the anchor this branch ships, a prose tripwire whose
docstring claimed to match the claim while matching four literal phrasings, and an `absent` preview
promising an insertion where the code performed a migration. Mutation is what caught each one.

Below: the three items Chunk 02's verify round carried into this chunk, kept as the record of how
they resolved rather than deleted. All three are closed.

**Base advanced 2026-09-10** over 253 develop commits — see the merge commit for how the five
conflicts resolved. Nothing this plan delivers was superseded in the interval: `reanchor`,
`anchor_repair` and both test files remained absent from develop, and `STATIC_ANCHOR` was unchanged
there, so the exact-match archive and the tag guard still cover every shipped anchor (re-verified
with v3.4.0, tagged after this branch's base, now among the tags).

1. **`api-contract.md` names a consumer for `reanchor --json`.** *(Resolved the other way: Chunk 03
   made Health Check #4 relay the command's human form, so the contract now states plainly that
   there is no JSON consumer. The claim this item planned to make true was deleted instead — and a
   review then found two more rows of the same shape, which is the class this carry belonged to.)*
2. **The tag guard can pass vacuously.** `_shipped_anchor` returns `None` for any f-string shape it
   cannot resolve and `None` is skipped, so a future anchor interpolating something other than a
   module-level string constant would make the guard green by resolving nothing. *(Resolved in Chunk
   03: `test_the_archive_covers_every_anchor_prawduct_ever_shipped` now collects the tags it could
   not render and asserts that list is empty before trusting what it did not find, so "I could not
   read it" no longer spells the same as "it was fine".)*
3. **`ANCHOR_V2` is derived from `ANCHOR_V1` by `.replace()`**, which couples two entries the
   archive's own "append, never edit" rule treats as independent literals. *(Resolved in Chunk 03:
   the comment at the constant now says the coupling is deliberate — a one-line difference kept as a
   derivation rather than a second literal — and names the tag guard that reconstructs both from the
   release tags, so the code no longer contradicts the stated rule in silence.)*

## Verification Strategy

Beyond the suite, each chunk is checked against the same simulated plugin-less machine the
investigation used — a scratch repo carrying the install reference and the anchor, driven with
`claude --debug -p` under a throwaway `CLAUDE_CONFIG_DIR`. Chunk 01 confirms the new anchor text is
what such a session actually receives; Chunk 02 confirms the detector calls a real pre-change anchor
stale and a re-anchored one clean; Chunk 03 confirms `/prawduct:doctor`'s report names it.

## Build Chunks

### Chunk 01: The anchor tells a plugin-less session the truth

- **Description:** Rewrite `STATIC_ANCHOR` so the one governance surface that reaches a plugin-less
  session leads with the fact that governance is off and names the command that fixes it — and so
  its enforcement sentence stops claiming unconditionally that a Stop hook is watching. The plugin
  id is interpolated from `INSTALL_REFERENCE`, never typed twice.
- **Depends on:** none
- **Artifacts consumed:** `plugin-absent-clone-investigation.md` findings 2-4
- **Deliverables:** `plugin/lib/migrate_plugin.py` — `STATIC_ANCHOR` rewritten, plugin id derived
  from `INSTALL_REFERENCE['enabledPlugins']`
- **Tests:** `tests/test_plugin_migrate.py`, `tests/test_plugin_init.py` — existing anchor
  assertions updated; new: the anchor names the install command, the install command carries the id
  from the contract constant (change the constant → the anchor follows), the enforcement claim is
  conditional, and the anchor still carries no prawduct version number
- **Acceptance criteria:** suite green; a scratch repo anchored by `init-product` carries the notice;
  the rendered anchor stays under 35 lines (context weight is a cost — NFR)
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Detect a stale anchor, offer the re-anchor

- **Description:** Every repo onboarded before Chunk 01 carries the old anchor, and nothing
  re-anchors it — `claude_anchor_pending` returns False the moment the sentinel is present, so a
  stale anchor is indistinguishable from a current one. Add substance-based detection (does the
  anchor block carry the install command?) and an offered, dry-run-by-default repair that replaces
  the block and nothing else.

  Detection is deliberately **substance-based, not revision-tagged**: a repo whose owner wrote their
  own equivalent notice passes, which is the correct answer, and no new anchor-version concept has
  to be kept in sync with the anchor.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `plugin-absent-clone-investigation.md` "Decision taken"
- **Deliverables:** new `plugin/lib/anchor_repair.py` (`check`, `repair`); `plugin/bin/prawduct-hook`
  — new `reanchor [--apply] [--json]` subcommand, dispatch entry, usage string
- **Tests:** `tests/test_plugin_init.py` — **carried from Chunk 01's review (R-1)**: its
  `test_static_anchor_present` gains two asserts so the scaffold path is pinned to render the
  plugin-absent notice. It rides this commit rather than buying Chunk 01 a second review round, and
  it belongs here on its own merit — new onboards are the one population this chunk's repair never
  reaches. Already written and held uncommitted; commit it with this chunk.

  new `tests/test_anchor_repair.py` — statuses `ok` / `stale` / `absent` / `unreadable`;
  the repair replaces only the anchor block (surrounding product prose byte-identical, line endings
  included); dry run writes nothing; `--apply` is idempotent; exit 0 for a graded run and 1 for
  could-not-run; a repo with no `CLAUDE.md` is `absent`, not a crash
- **Acceptance criteria:** run against a scratch repo carrying the pre-Chunk-01 anchor → `stale`
  with the exact replacement printed; `--apply` → `ok`, re-run → `ok` and no diff
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Doctor grades it; three documents stop asserting the retired behaviour

- **Description:** Health Check #4 currently passes on the mere presence of the `PRAWDUCT:ANCHOR`
  marker, so it grades a lying anchor healthy. Extend it to relay `reanchor`'s status and offer the
  repair (read-and-guide; the owner runs `--apply`). Then correct the three documents that tell an
  owner clone activation is automatic — the claims that actively suppress the message this whole
  plan exists to deliver.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `plugin-absent-clone-investigation.md` finding 5
- **Deliverables:** `plugin/skills/doctor/SKILL.md` Health Check #4; `README.md` (the clone claim);
  `plugin/skills/onboard/SKILL.md` (the "prompts each developer" claim); `documentation/MIGRATION.md`
  (the "no setup step for the next person" claim); `.prawduct/change-log.md` entry
- **Tests:** `tests/test_v5_methodology.py` (or the doctor-content suite) — Health Check #4 names the
  `reanchor` command; a guard that none of the three documents claims the plugin auto-installs or
  that Claude Code prompts for it
- **Acceptance criteria:** suite green; `/prawduct:doctor` in a repo with a stale anchor reports
  degraded and names the repair; the three documents describe what was measured
- **Verification performed (2026-08-25):** every status Health Check #4 promises was reproduced on a
  scratch repo and observed directly — `ok`, `stale`, `stale-modified`, `absent`, `unreadable` — plus
  `legacy-block` and `unwritable` after the cumulative review added them. The stale → `--apply` → `ok`
  round trip was checked for byte-identity of the product prose either side of the swapped anchor.
  Recorded here because a manual check with no record is indistinguishable from one never run.
- **Type:** cumulative-final
  <!-- Last chunk: its review IS the branch's one `/prawduct:critic cumulative` — commit first,
       run it once, no separate `final`. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes. Chunk 03's `cumulative`
review makes the branch PR-ready; `/prawduct:pr create` runs when the user asks for a PR.
