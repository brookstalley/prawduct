<!-- Build Plan — register the missing legacy-backlog-format advisory probe. -->
---
artifact: build-plan
version: 2
scope: legacy-backlog-format-probe
depends_on: []
last_validated: null
lifecycle: completed
archived: 2026-08-10
released_in: v2.0.17
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** Root cause is known and verified against the code. The post-sync
advisory roster is supposed to nudge a repo to run `/prawduct:backlog migrate`
when it carries a legacy-format backlog — the `legacy-backlog-format` probe
(`documentation/backlog-system-requirements.md` §8.2 / `post-sync-advisory-spec.md`
§8.2): *trigger* = `.prawduct/backlog.md` exists with **>5 items, none carrying
`[PFX-XXXX]` ids*; *resolution* = `backlog_format_version: 2`; *action* =
`/prawduct:backlog migrate`. That probe was the single **production** probe
shipped in framework v1.7.0 (`tools/lib/backlog_probes.py::legacy_backlog_format_probe`).
M4 (v2.0.3) deleted the file-sync `tools/lib/backlog_probes.py` along with the
engine. The v0.3 backlog rework (v2.0.15) built a **new** plugin-native
`lib/backlog_probes.py` — but it implemented the three previously-*deferred*
probes (`external-backlog-detected`, `legacy-section-schema`,
`backlog-overdue-grooming`) and **never re-ported the primary one**.
`register()` registers those three and not `legacy-backlog-format`, and
`grep register_probe` confirms it is registered nowhere.

Net effect (the user's report): a repo that adopts a new prawduct version with an
unmigrated backlog gets **no advisory** nudging `/prawduct:backlog migrate`. The
roster itself is alive (the grooming probe fires in real session briefings), so
the gap is the missing probe, not the infrastructure.

Two stale artifacts corroborate the gap is known-but-unfixed:
- `lib/advisory_store.py` `run_sync_advisories` comment: "The probe roster is
  empty: the sole legacy probe (legacy-backlog-format) was retired with the
  file-sync engine (M4)." — now wrong: the roster holds three probes.
- `skills/backlog/SKILL.md`: "re-adding it as a plugin-native probe is tracked in
  the backlog."

**Decision:** Re-port the proven `legacy-backlog-format` probe into the
plugin-native `lib/backlog_probes.py`, register it, and reconcile the stale
comments/docs. Faithful to the original (same trigger floor, partial-migration
guard, stable count-independent evidence, `priority="info"`), adapted to the
current `parse_backlog` API and the plugin-namespaced action string.

**Open assumptions / unknowns:**
- `[ASSUMPTION: the trigger stays ">5 items, none carrying a [PFX-XXXX] id" and resolution stays backlog_format_version==2, per spec §8.2 — unchanged from the v1.7.0 production probe | HIGH | user can veto]`
- `[ASSUMPTION: priority stays "info" (matches the original probe and the three sibling probes; the briefing surfaces info advisories) | HIGH]`
- `[ASSUMPTION: a legacy backlog may legitimately trigger BOTH legacy-backlog-format (id-less items) and legacy-section-schema (old headings); they are distinct spec'd probe types and both resolve on backlog_format_version==2 | HIGH]`

**What would raise confidence:** N/A (High).

## Status

- [x] Chunk 01: Register the legacy-backlog-format probe (probe + register + doc reconcile + regression tests)

## Build Chunks

### Chunk 01: Register the legacy-backlog-format probe

- **Description:** Add the missing `legacy-backlog-format` probe to the
  plugin-native roster so a legacy-format backlog surfaces a
  `/prawduct:backlog migrate` nudge at session start. Reconcile the two stale
  artifacts that document the probe as absent.
- **Deliverables:**
  - `lib/backlog_probes.py`: add `probe_legacy_backlog_format(state, codebase)`
    — short-circuit when `backlog_format_version == 2`; read `.prawduct/backlog.md`
    (empty → no fire); count `parse_backlog(text).items` (the parser already
    skips HTML-comment and code-fence bullets); fire only when `len(items) > 5`
    **and** no item carries an `item_id` (partial migration → don't fire,
    `backlog_format_version` is the authoritative done-signal). Stable,
    count-independent `evidence`; live count in `trigger_summary`; action
    `/prawduct:backlog migrate`; `priority="info"`. Add `LEGACY_FORMAT_MIN_ITEMS = 5`.
    Register it in `register()`; update the module docstring ("three" → "four").
  - `lib/advisory_store.py`: correct the stale `run_sync_advisories` comment that
    claims the roster is empty / the legacy probe is retired.
  - `skills/backlog/SKILL.md`: update the two stale notes (the migrate-section
    parenthetical that says the probe "is tracked in the backlog", and step 5's
    "a *future* plugin-native probe would consult") to reflect that the probe now
    exists and is registered.
  - `tests/test_backlog_probes.py`: add `TestLegacyBacklogFormatProbe` (fires on
    >5 id-less items; resolved by `backlog_format_version: 2`; partial-migration
    no-fire; small-backlog no-fire; no-file no-fire; comment-bullet exclusion);
    update `TestRegistration` to expect **four** registered probes (add the
    `backlog:legacy-backlog-format` key).
- **Tests:** the new `TestLegacyBacklogFormatProbe`; the updated registration
  assertion; full suite green.
- **Acceptance criteria:** `lib.backlog_probes.register()` registers
  `backlog:legacy-backlog-format`; `run_all_probes` returns a
  `legacy-backlog-format` candidate (action `/prawduct:backlog migrate`) for a
  `>5` id-less-item backlog with no `backlog_format_version: 2`, and returns none
  once that fact is set or any item carries an id. No active code/skill file still
  documents the probe as absent. Full suite green.
- **Critic mode:** final
- **Type:** code
- **Done when:** 1. Acceptance + tests pass · 2. `/prawduct:critic final` blocking resolved · 3. committed + Status updated (views: change-log + regen-views happen at release) · 4. `/prawduct:critic cumulative` (the `/prawduct:pr` gate).
