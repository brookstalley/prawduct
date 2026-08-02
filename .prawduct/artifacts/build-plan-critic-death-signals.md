---
artifact: build-plan
version: 2
# Namespaces this plan's chunk numbering; matches the change-log entry's `scope=`.
scope: critic-death-signals
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** The problem is field-observed and root-caused (2026-08-02 consumer report on
plugin 3.2.3, verified line-by-line against this tree), success is statable in one
sentence, and the fix set was chosen by the owner ("we have to fix this now").

**Open assumptions / unknowns:**
- `[ASSUMPTION: reviewer-written started markers are reliable enough | MED impact | the marker is written by the model as its first action, not by code — a reviewer that crashes before its first tool call writes nothing, which the message renders as "no start marker", the same state as today]`
- `[ASSUMPTION: archiving (not refusing) is the right clobber behavior | MED impact | leftover manifests are a documented normal state (waived/stale reviews), so refusal would block routine reviews; archiving preserves the forensic trace at zero flow cost. A hard concurrent-dispatch guard stays filed as issue #171.]`
- `[ASSUMPTION: keeping the newest 3 archives is enough | LOW impact | one knob]`

**What would raise confidence:** N/A (High).

## Problem / Success / Scope

- **Problem:** During a healthy coordinator review, every observable signal falsely says
  the review is dead: (a) `.critic-active` embeds the PID of the already-exited
  `critic-begin` hook process — `ps -p` says "dead" within milliseconds of dispatch, on
  every review, and nothing ever reads the field back; (b) between "manifest written" and
  "partial complete" (typically 4–10 min per reviewer) there is no on-disk trace that any
  reviewer started, so "no partials yet" is indistinguishable from "reviewers never
  started"; (c) a re-dispatch after a premature death verdict silently clobbers the first
  manifest, erasing the evidence that the first review ever ran. Field consequence
  (2026-08-02, plugin 3.2.3): an agent concluded death at ~9 min — inside the grace
  window — re-dispatched, doubled review cost, and the first review left no trace.
- **Success:** No signal a waiting caller can reach affirmatively fakes death: the marker
  carries no PID; `critic-consolidate`'s waiting message reports per-role started ages
  from reviewer-written `<role>.started` markers ("design started 3.4 min ago" vs "no
  start marker"); the death verdict keys on each role's own started age when a marker
  exists, so late-started reviewers aren't declared dead by dispatch age; and
  `critic-begin` archives an unconsolidated predecessor manifest instead of deleting it.
- **Out of scope:** The SendMessage channel gap the same report noted (filed separately);
  a hard concurrent-dispatch refusal (issue #171 — archiving narrows the damage, the
  guard question stays open); the await-in-fork dispatch-model change (CRT-3F7M's
  research question, unchanged by this fix); single-pass-roster started markers (the
  single-pass reviewer is the dispatching fork itself — there is no waiting caller who
  can observe a marker before the fork returns, and the fork consolidates itself).

## Status

- [ ] Chunk 1: Kill the false death signals (marker PID, per-role liveness, archive-not-clobber)

**Context:** Branch `fix/critic-death-signals` off `origin/develop` (b1d6667). Single-chunk
plan. `active_build_plan` repointed here on this branch (precedent:
`build-plan-critic-session-guard.md`); the golive plan continues on its own branch.
No PR unless the user asks.

---

### Chunk 1: Kill the false death signals

- **Type:** code (bugfix)
- **Critic mode:** final
- **Delivers:**
  - `plugin/lib/critic_marker.py` — drop the `pid` field from the `.critic-active`
    payload (write-only, records the exited hook process, structurally a false "died"
    signal). Comment states the constraint so it doesn't come back.
  - `plugin/lib/critic_consolidate.py` — per-role started markers:
    `started_path(prawduct_dir, role)` (`.critic-partials/<role>.started`);
    `_incomplete_noop_message` gains per-role started ages (marker mtime) and a
    per-role effective-age death verdict: a missing role with a started marker is judged
    by the marker's age, one without by dispatch age; the past-grace advice fires only
    when every missing role is past grace on its own effective age. `remove_partials`
    already clears markers (it unlinks all children — verify with a test, don't assume).
  - `plugin/lib/critic_consolidate.py` (`begin_review`) — an existing manifest is
    archived to `.prawduct/.critic-partials-archive/<old-id>/` (newest 3 kept) instead
    of deleted; stdout/notes name what was archived and where. Partials without a
    readable manifest archive under a timestamp-derived name.
  - `plugin/lib/core.py` — `.prawduct/.critic-partials-archive/` joins
    `GITIGNORE_ENTRIES`.
  - `plugin/agents/critic-reviewer.md` + `plugin/skills/critic/review-protocol.md`
    (Coordinator Pattern prompt template) — the reviewer's FIRST action is writing its
    `<role>.started` marker (content: the role; the mtime is the signal — reviewers
    have no clock tool).
  - Tests: marker payload carries no `pid`; started-marker rendering + effective-age
    verdict (fresh marker past dispatch grace → wait; stale marker → dead; no marker →
    dispatch-age behavior unchanged); archive-not-clobber (old manifest recoverable,
    prune to 3); prose-binding test pinning the `.started` convention in both dispatch
    surfaces to the code's constant.
- **Done when:** acceptance above passes, full suite green, `/prawduct:critic` run and
  blocking findings resolved.
