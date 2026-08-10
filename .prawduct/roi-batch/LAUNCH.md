# ROI batch — launch runbook (post-/clear)

> **HISTORICAL — do not execute.** This work shipped in v2.0.5 and its plan is archived. The
> document is kept as a record of how the batch was launched, not as a procedure. In particular,
> **do not follow the `active_build_plan` step below**: it now names a path under
> `artifacts/archive/`, and a pointer at an archived plan reads to every gate as "no active build
> plan" — they go quiet rather than fail, which is the exact state this repo's own governance docs
> warn about. That line is a mechanical consequence of the archive move, left visible rather than
> silently rewritten, because rewriting it would make a dead runbook look live.

Nine pre-triaged backlog ROI items, built by **two parallel background workflows**, then
governed and shipped by this (launching) session. Plan: `.prawduct/artifacts/archive/build-plan-roi-batch.md`.

Items: **CRT-3M8Q, BLD-4Q9X, TST-2R7H, MIG-8C3V** (code lane) · **MET-4K8Z, MET-1T5W,
MET-8N2C, MET-2D9K, DOC-2W9P** (docs lane).

The workflows do the **build half only** (fix + regression test + scoped pytest; no commit, no
Critic). This session does the **governance half** (full suite → Critic → commit → PR → archive).

---

## Step 0 — branch + activate governance (do this BEFORE launching)

```bash
git checkout develop && git pull --ff-only          # ensure fresh base
git checkout -b fix/roi-batch
```

Then point the stop-hook gate at the plan (so the Critic gate enforces correctly this session):
set `active_build_plan: artifacts/archive/build-plan-roi-batch.md` in `.prawduct/project-state.yaml`
(the `active_build_plan:` key near the bottom — currently empty).

## Step 1 — launch BOTH workflows in parallel (one message, two tool calls)

The two lanes touch disjoint files, so they run safely against the one `fix/roi-batch` working tree:

- `Workflow({ scriptPath: ".prawduct/roi-batch/wf-code.js" })`
- `Workflow({ scriptPath: ".prawduct/roi-batch/wf-docs.js" })`

Both run in the background and return task IDs immediately; a `<task-notification>` arrives when
each completes. Watch live progress with `/workflows`. Do NOT start editing these files yourself
in the meantime — let the agents own them.

## Step 2 — when BOTH workflows have completed

1. **Full suite:** `python3 -m pytest -q` — must be fully green. (Each lane only ran scoped
   tests; this is the first all-together run.) Fix any cross-lane interaction here.
2. **Review the diff:** `git diff --stat` — confirm the file sets match the plan and nothing
   strayed into `.prawduct/` bookkeeping.
3. **Cumulative Critic:** `/prawduct:critic` (it will infer `cumulative` on a clean-tree,
   ahead-of-base branch — or pass `cumulative`). Resolve every BLOCKING finding; reflect on
   WARNINGs. This is the single review for the whole batch (proportional — small, independent fixes).
4. **Commit per concern** on `fix/roi-batch` (suggested):
   - `fix(critic): honor build-plan per-chunk Critic mode override [CRT-3M8Q]`
   - `fix(views): scope:null suppresses change-log inference [BLD-4Q9X]`
   - `test(gate): pin non-handoff Types fall through to Critic gate [TST-2R7H]`
   - `fix(migrate): drop leading double blank line in migrated CLAUDE.md [MIG-8C3V]`
   - `docs: methodology + design-spec coherence batch [MET-4K8Z/1T5W/8N2C/2D9K, DOC-2W9P]`
5. **PR:** `/prawduct:pr` (independent reviewer → create → merge to `develop` when clean).
6. **Reconcile bookkeeping** (the part the workflows deliberately left alone):
   - Archive all 9 items in `.prawduct/backlog.md` (Open → Archive, `status: shipped`, `closed-by:`).
   - Add `.prawduct/change-log.md` entries tagged `scope=roi-batch · status=shipped` per chunk,
     then `prawduct-hook regen-views` to flip the Status checkboxes.
   - Clear `active_build_plan:` back to empty in `.prawduct/project-state.yaml`.
7. **Reflect** (`/prawduct:reflection`) before `/clear`.

## Safety notes (why this is parallel-safe)

- **Disjoint file sets.** Code lane owns `lib/` `bin/` `skills/critic/` `tests/{critic_mode_inference,views,plugin_migrate, +new gate test}`; docs lane owns `methodology/` `documentation/`. No same-file race.
- **No commits inside workflows.** Both lanes leave changes uncommitted on the one branch; this session does all git.
- **Scoped tests only inside workflows.** Avoids one lane's in-flight edit breaking the other's test run. The full suite runs once here (Step 2.1).
- **Bookkeeping files are off-limits to the agents** — prevents the only cross-lane conflict (everyone wanting to edit backlog/changelog/state).

## Kick it off

Paste to the fresh session:

> Read `.prawduct/roi-batch/LAUNCH.md` and execute it: do Step 0, then launch both workflows in parallel (Step 1), and when they finish run the Step 2 governance wrap-up.
