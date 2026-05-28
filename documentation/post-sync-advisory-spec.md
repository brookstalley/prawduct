# Post-Sync Advisory Infrastructure — Spec

**Status:** Draft v0.2 (2026-05-28)
**Changes from v0.1:** Q1-Q4 resolved per user feedback. Unified command renamed `/advisory` → `/prawduct-advisory` to reflect that advisories are framework infrastructure (the `prawduct-` prefix marks framework-level commands; user-project commands like `/backlog` and `/llm-strategy` do not carry it). Explicit separation of `project-state.yaml` (committed, shared) and `.advisories.json` (gitignored, per-clone). Probe versioning + supersession. Resolution-condition concept. Compact retention form for non-active entries.
**Scope:** Shared infrastructure used by the backlog and prompts features to surface migration signals to the user after a sync, without forcing setup or blocking work. This spec describes the storage, lifecycle, schema, session-briefing format, and dismissal mechanism.
**Out of scope:** Per-feature probe logic (lives in each feature's own build plan), build plan for this infrastructure (separate deliverable).
**Required-by:**
- `documentation/backlog-system-requirements.md` §8.1
- `documentation/prompt-management-requirements.md` §11.1
- `documentation/empirical-testing-plan.md` §4 (Cross-cutting — listed as a hand-waved prerequisite)

---

## 1. Problem & motivation

Two new features (backlog system, prompt management) need a way to notice "this project should probably do X, but we won't force it" — and then nudge the user at session start, persistently, until they act or explicitly dismiss.

The pattern is general:
- **Sync** runs migration probes that examine project state + codebase
- **Probes** detect signals (e.g., `anthropic` imported but no `uses_llm_inference: true`)
- **Advisories** are written to a shared store
- **Session briefing** at next session start surfaces them
- **User** runs the recommended command (`/llm-strategy detect`) or dismisses

Both features need this shape. Specifying it once, in shared infrastructure, prevents the two build plans from each inventing their own (incompatible) version.

---

## 2. Design principles

1. **Advisories are informational, not gates.** They surface, they don't block. The stop hook does not block on active advisories. Each feature *may* opt into gating later (e.g., the backlog feature could refuse `/backlog list` if a migration is pending), but the default is non-blocking.
2. **Idempotent across syncs.** Re-running sync without state change must not duplicate advisories. The same trigger → the same advisory `id` → no-op on re-write.
3. **Auto-clear when resolved.** Probes are re-run on each sync. If a previously-triggered probe no longer matches, the advisory is resolved automatically (no user action required).
4. **Dismissal is sticky.** A user-dismissed advisory does not re-surface even if the trigger condition persists. Re-surfaces only if (a) dismissal is explicitly cleared, or (b) a different probe fires for a related-but-distinct condition.
5. **Per-clone nag log, shared resolution truth.** Two stores with distinct purposes (formalized in §3.5):
   - `.prawduct/.advisories.json` (gitignored, per-clone) — the *nag log*. Holds active triggers and per-developer dismissal/resolution state. One developer dismissing does not affect a teammate.
   - `.prawduct/project-state.yaml` (committed, shared) — the *answer store*. Holds the resolved-state facts that probes consult to know whether to fire (e.g., `uses_llm_inference: true`). A team member who *resolves* a condition affects everyone, because the resolution is recorded in the shared file.
6. **Schema-versioned.** A `schema_version` field at the top of `.advisories.json` allows evolution without breaking existing stores.
7. **Feature-tagged.** Each advisory declares its source feature. Session briefing can group; per-feature dismissal commands can scope.
8. **Probe-versioned.** Each probe declares its version. The advisory `id` hashes the probe version with the evidence so a probe update produces a new id, and the old advisory is auto-resolved with `superseded_by` pointing at its replacement (avoids stale advisories surviving probe refinements).

---

## 3. Storage

### 3.1 File location

`.prawduct/.advisories.json` — per-clone, gitignored (added to `.gitignore` by sync).

### 3.2 Schema

```json
{
  "schema_version": 1,
  "advisories": [
    {
      "id": "prompts-llm-sdk-detected-v1-d3f9a2",
      "feature": "prompt-management",
      "type": "prompt-strategy-required",
      "probe_version": 1,
      "triggered_at": "2026-05-28T14:30:00Z",
      "triggered_by_sync_version": "v1.6.0",
      "trigger_summary": "Detected vendor SDK imports (anthropic, openai) and prompt-shaped content in source code, but `uses_llm_inference` is not set in project-state.yaml.",
      "evidence": [
        "api/src/clients/anthropic_client.py:1 — imports anthropic",
        "api/src/clients/openai_client.py:1 — imports openai",
        "config/models.yaml:3 — contains 'claude-haiku-4-5' substring"
      ],
      "recommended_action": "/llm-strategy detect",
      "alternative_actions": [
        "/llm-strategy init",
        "/llm-strategy dismiss-advisory prompts-llm-sdk-detected-v1-d3f9a2"
      ],
      "priority": "info",
      "state": "active",
      "superseded_by": null,
      "dismissed_at": null,
      "dismissed_reason": null,
      "resolved_at": null,
      "resolved_by": null
    },
    {
      "id": "prompts-llm-sdk-detected-v0-a1b2c3",
      "state": "resolved",
      "resolved_at": "2026-05-28T14:30:00Z",
      "resolved_by": "probe-update",
      "superseded_by": "prompts-llm-sdk-detected-v1-d3f9a2"
    }
  ]
}
```

The second entry illustrates the **compact form** used for non-active advisories (per §3.4 retention).

### 3.3 Field definitions

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | int | Always `1` for now. Increment on breaking schema changes. |
| `advisories` | array | All advisories — active, dismissed, resolved. Resolved/dismissed entries are kept for a TTL (see §3.4). |
| `id` | string | Stable across syncs *within a probe version*. Format: `<feature-prefix>-<probe-type>-v<probe-version>-<trigger-hash>`. The trigger hash is a 6-char digest of the evidence; the probe version is included so a probe refinement produces a new id (and the old advisory is auto-superseded — see Q1 resolution). Same evidence + same probe version → same id (idempotent). |
| `feature` | string | Source feature. Current values: `backlog`, `prompt-management`. Extensible. |
| `type` | string | Probe type within the feature. Current planned values: `legacy-backlog-format`, `backlog-overdue-migration`, `prompt-strategy-required`, `prompt-strategy-stale-review`, `prompt-strategy-overdue-role-review`, `runtime-instruction-detected`. Extensible. |
| `probe_version` | int | Monotonic, per `(feature, type)` tuple. Bumped by maintainers when the probe's trigger logic or evidence shape changes. Allows old advisories to be cleanly superseded. |
| `triggered_at` | ISO-8601 | When the probe first fired this id. Not updated on re-fires. |
| `triggered_by_sync_version` | string | The framework version of the sync that first triggered. |
| `trigger_summary` | string | Human-readable, one sentence, suitable for session briefing. |
| `evidence` | array of strings | File:line citations or other concrete signals. ≤5 entries to keep the briefing scannable; more available via `/prawduct-advisory show <id>`. |
| `recommended_action` | string | Single primary action (a slash command or short instruction). |
| `alternative_actions` | array of strings | Other actions the user might take (including dismissal). |
| `priority` | enum | `info` (default), `warn`, `urgent`. Affects session-briefing ordering and verbosity. `urgent` is rare and reserved for things like "model used in this project is past retirement date." |
| `state` | enum | `active`, `dismissed`, `resolved`. |
| `superseded_by` | string or null | When non-null, this advisory was replaced by another (id given) due to a probe-version bump. The replacement is the canonical current entry; this one is kept only to prevent re-trigger. |
| `dismissed_at` | ISO-8601 or null | Set when user dismisses. |
| `dismissed_reason` | string or null | Optional user-provided reason. |
| `resolved_at` | ISO-8601 or null | Set when probe re-runs and no longer matches (or supersession). |
| `resolved_by` | string or null | `sync` (auto-resolved — resolution condition met), `<action>` (resolved by user running a command), or `probe-update` (superseded by a probe-version bump). |

### 3.4 Retention

- **Active**: full payload, kept forever (until resolved or dismissed).
- **Resolved**: shrunken to compact form (only `id`, `state`, `resolved_at`, `resolved_by`, and `superseded_by` when applicable). Kept for 30 days for "resolved since last session" reporting, then removed by sync.
- **Dismissed**: shrunken to compact form (only `id`, `state`, `dismissed_at`, `dismissed_reason`). Kept forever — the dismissal is the load-bearing fact, not the original trigger evidence.

**Why compact?** The full payload (trigger_summary, evidence, recommended_action, alternative_actions) is only useful while an advisory is `active`. Once resolved or dismissed, the only thing the store needs to remember is "this id is no longer eligible to trigger." The compact form prevents `.advisories.json` from growing unbounded in long-running projects while preserving idempotency guarantees.

If a user needs to inspect a dismissed advisory in detail, the probe can be re-run to reconstruct the evidence (the trigger condition is deterministic on project state).

### 3.5 Where state lives — `.advisories.json` vs `project-state.yaml`

Two distinct stores, with sharply different semantics:

**`.prawduct/.advisories.json`** — gitignored, per-clone. The *nag log*. Holds:
- Active advisories (full payload)
- Dismissed advisories (compact)
- Resolved advisories (compact, 30-day TTL)

This file is local. A teammate doesn't see your dismissals, and vice versa. Probes re-run on every sync and recompute the active set against this file's existing entries.

**`.prawduct/project-state.yaml`** — committed, team-shared. The *answer store*. Holds settled facts that probes consult:
- `uses_llm_inference: true | false | null`
- `prompt_strategy_path: ".prawduct/artifacts/prompt-strategy.md"` (when set)
- Backlog format version
- (Other feature-specific resolved-condition fields)

These fields are populated by user actions (e.g., `/llm-strategy detect` writes `uses_llm_inference: true` on accept). Because `project-state.yaml` is committed, when one developer's action resolves a probe, *everyone* gets the resolution on next pull — `.advisories.json` re-syncs locally and the now-stale advisory auto-resolves.

**Decision rule for "where does this go?"**

- *"What's the answer? (project-level, shared)"* → `project-state.yaml`
- *"Have I already dealt with this nag? (developer-level, local)"* → `.advisories.json`

A team-wide *dismissal* mechanism (e.g., "the whole team agrees to not run `/llm-strategy detect` on this project — we know it uses LLMs but we're tracking that elsewhere") could be added later as a `dismissed_advisory_classes: []` array in `project-state.yaml`. Out of scope for v1 (per Q2 lean).

---

## 4. Lifecycle

```
┌─────────────────┐
│ Sync runs probes│
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐         ┌─────────────────────────────┐
│ For each probe: does it fire?│        │ For each existing advisory: │
└────────┬────────────────────┘         │ does its probe still match? │
         │ yes                          └────────┬────────────────────┘
         ▼                                       │ no
┌──────────────────────────────┐                ▼
│ Compute id from evidence hash│      ┌─────────────────────────────┐
│ id already in store?         │      │ Mark resolved (state +      │
│                              │      │ resolved_at + resolved_by)  │
│   yes → no-op                │      └─────────────────────────────┘
│   no  → write new advisory   │
└──────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ Next session start                   │
│ Session briefing reads advisories     │
│ Active + priority-ordered list shown │
└──────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────┐
│ User options:                                          │
│  - Run recommended_action → on success, sync re-runs   │
│    probe, advisory becomes resolved on next sync       │
│  - Dismiss → state=dismissed, dismissed_at set         │
│  - Ignore → advisory persists, surfaces next session   │
└────────────────────────────────────────────────────────┘
```

### 4.1 Probe execution

- Probes are registered by features at framework startup (e.g., in `tools/lib/probes/prompt_management.py`).
- Each probe is a function: `(project_state, codebase) → list[AdvisoryCandidate]`.
- Sync calls all registered probes. Returned candidates are matched against existing advisories by id.

### 4.2 Resolution detection

Resolution is the inverse of triggering. After running all probes, sync diffs:
- IDs in the previous advisory store but not in this run's probe output → mark resolved (with `resolved_by: sync`).
- IDs in this run's probe output but not in the store → write as new active advisory.
- IDs in both → no-op.

This requires probes to be **deterministic** given the same project state — the trigger hash must be stable.

### 4.3 Action-driven resolution

When the user runs a `recommended_action` (e.g., `/llm-strategy detect`), the action's success path can write `resolved_at` + `resolved_by: <action>` directly without waiting for the next sync. This gives immediate feedback: "Advisory resolved."

---

## 5. Session briefing integration

The existing `tools/product-hook session-start` (or equivalent) gains a new section after the current `Framework freshness` and `Place-once template advisories` blocks:

```
ADVISORIES (post-sync, 3 active):
  • [prompt-management] Detected vendor SDK imports but `uses_llm_inference` not set.
    → Run /llm-strategy detect (or /prawduct-advisory dismiss prompts-llm-sdk-detected-v1-d3f9a2)
  • [backlog] 43 legacy-format items in .prawduct/backlog.md.
    → Run /backlog migrate (or /prawduct-advisory dismiss backlog-legacy-format-v1-a1b2c3)
  • [prompt-management] Role `summarizer` overdue for review since 2026-04-15.
    → Run /llm-strategy review summarizer

  Dismissed since last session: 1 (run /prawduct-advisory list --dismissed to see)
  Resolved since last session: 0
```

### 5.1 Verbosity rules

- **Default**: show summary + recommended action per active advisory, capped at 5 most-recent + highest-priority.
- **Truncation**: if more than 5 active, show first 5 + "... and N more (run /prawduct-advisory list)."
- **Priority ordering**: urgent → warn → info, then by `triggered_at` descending within priority.
- **Suppression**: if all advisories are `info` priority and total count is unchanged from the last session, can be collapsed to one line: "ADVISORIES: 3 active (unchanged) — run /prawduct-advisory list."

### 5.2 Empty state

When no active advisories, omit the section entirely. Don't print "ADVISORIES: 0 active" — that's noise.

---

## 6. Dismissal and management CLI

### 6.1 Unified command: `/prawduct-advisory`

The advisory system is framework infrastructure. Per the project's naming convention, framework-level commands carry the `prawduct-` prefix to distinguish them from user-project commands (e.g., `/backlog`, `/llm-strategy`, which are about the user's project state). `/prawduct-advisory` is the canonical surface:

| Subcommand | Behavior |
|---|---|
| `/prawduct-advisory list [--state=active\|dismissed\|resolved\|all] [--feature=<name>]` | List advisories. Defaults: state=active, all features. |
| `/prawduct-advisory show <id>` | Full detail on one advisory (evidence, history, full text). If the advisory is in compact form (resolved/dismissed), re-runs the probe to reconstruct evidence. |
| `/prawduct-advisory dismiss <id> [--reason "..."]` | Mark dismissed. Reason optional but encouraged. |
| `/prawduct-advisory undismiss <id>` | Clear dismissal — advisory returns to active state if the probe still fires. |
| `/prawduct-advisory resolve <id>` | Manually mark resolved (rare — usually probes do this via §4.2 or actions via §4.3). |

### 6.2 Per-feature aliases

User-project commands keep their own dismissal subcommands for discoverability and flow continuity. When a user is in the middle of `/llm-strategy detect` or `/backlog migrate`, dismissing a related advisory from within that feature's command surface is the natural reach:

- `/llm-strategy dismiss-advisory <id>` → equivalent to `/prawduct-advisory dismiss <id>` but errors if the id isn't a `prompt-management` advisory.
- `/backlog dismiss-advisory <id>` → equivalent but scoped to `backlog`.

These aliases are user-project conveniences. The unified `/prawduct-advisory` command is the framework's surface and is the authoritative API; the aliases delegate to it.

---

## 7. Probe registration

Each feature provides probes via a registration point:

```python
# tools/lib/probes/__init__.py
from typing import Callable, Iterable
from .types import AdvisoryCandidate, ProjectState

ProbeFn = Callable[[ProjectState, "Codebase"], Iterable[AdvisoryCandidate]]

_REGISTRY: dict[str, ProbeFn] = {}

def register_probe(feature: str, probe_type: str, fn: ProbeFn) -> None:
    """Called at framework init by each feature's probes module."""
    _REGISTRY[f"{feature}:{probe_type}"] = fn

def run_all_probes(state: ProjectState, codebase: "Codebase") -> list[AdvisoryCandidate]:
    """Called by sync."""
    candidates = []
    for key, fn in _REGISTRY.items():
        candidates.extend(fn(state, codebase))
    return candidates
```

Each feature's `tools/lib/probes/<feature>.py` calls `register_probe(...)` at import time. Sync imports both modules to ensure registration happens before `run_all_probes` is called.

### 7.1 Probe authoring guidelines

- **Deterministic**: same inputs → same `AdvisoryCandidate` list (including evidence hash).
- **Cheap**: probes run on every sync. Read-only file scans; no expensive operations. Cache where possible.
- **Specific**: prefer many narrow probes over one omnibus probe. Each probe maps to one `type`.
- **Versioned**: declare `probe_version: int`. Bump when trigger logic or evidence shape changes; the framework supersedes old advisories automatically.
- **Two conditions, not one**: each probe declares both a **trigger condition** (when to fire) and a **resolution condition** (when to clear). These are distinct:
  - The **trigger condition** is "we should ask about this" — e.g., vendor SDK imports present.
  - The **resolution condition** is "the user has answered" — e.g., `uses_llm_inference: true` in `project-state.yaml`.
  - The resolution condition reads from `project-state.yaml` (the shared answer store, §3.5), not from local code state. This decouples "the codebase still has SDK imports" (which is correct and unchanged) from "the project has been characterized" (the actual question we wanted answered).
- **Both conditions must be deterministic** so re-runs are idempotent.

Example probe shape:

```python
@register_probe(feature="prompt-management", probe_type="prompt-strategy-required", probe_version=1)
def prompt_strategy_required(state: ProjectState, codebase: Codebase) -> list[AdvisoryCandidate]:
    # Resolution condition: project has explicitly characterized its LLM usage
    if state.get("uses_llm_inference") is not None:
        return []  # resolved (either true or explicit false)

    # Trigger condition: Category A or Category B signals present
    evidence = []
    if codebase.has_imports(["anthropic", "openai", "google.generativeai", "langchain", "litellm"]):
        evidence.append("Vendor SDK imports detected in source")
    if codebase.has_files_matching(".claude/skills/*/SKILL.md", "agents/*/SKILL.md", ".cursorrules"):
        evidence.append("Runtime-instruction artifact locations detected")

    if not evidence:
        return []  # neither triggered nor resolved — nothing to say

    return [AdvisoryCandidate(
        type="prompt-strategy-required",
        evidence=evidence,
        trigger_summary="LLM-usage signals detected but `uses_llm_inference` is not set.",
        recommended_action="/llm-strategy detect",
    )]
```

---

## 8. Initial probe roster (referenced by the two feature specs)

These are the probes the two features expect this infrastructure to support. The actual probe implementations are deferred to each feature's build plan.

### 8.1 Prompt-management probes

| Probe `type` | Triggers when | Recommended action |
|---|---|---|
| `prompt-strategy-required` | Category A signals (SDK imports, hostnames, message shapes, DB prompt columns) present AND `uses_llm_inference` is not `true` | `/llm-strategy detect` |
| `runtime-instruction-detected` | Category B signals (skill markdown locations) present AND `uses_llm_inference` is not `true` | `/llm-strategy detect` |
| `prompt-strategy-stale-review` | `prompt-strategy.md` exists AND `last_reviewed > 180 days ago` | `/llm-strategy review` |
| `prompt-strategy-overdue-role-review` | Any role's `next_review` is in the past | `/llm-strategy review <role>` |
| `model-near-retirement` | Any role's declared model has a retirement date within 60 days (uses the model-tier registry) | `/llm-strategy update <role> model=...` |

### 8.2 Backlog probes

| Probe `type` | Triggers when | Recommended action |
|---|---|---|
| `legacy-backlog-format` | `.prawduct/backlog.md` exists with >5 items lacking `[PFX-XXXX]` ids | `/backlog migrate` |
| `external-backlog-detected` | A `TODO.md`, `BACKLOG.md`, `ROADMAP.md`, or `IDEAS.md` detected at repo root or `.github/` | `/backlog import <path>` |
| `legacy-section-schema` | `## Active — next up` / `## Queue` headings present in `.prawduct/backlog.md` (older section schema) | `/backlog migrate --sections` |
| `backlog-overdue-grooming` | No `/backlog` command run in >90 days AND backlog has >20 open items | `/backlog list` |

See `documentation/backlog-system-requirements.md` §8.2 for resolution conditions and threshold rationale.

---

## 9. Stop-hook integration

The stop hook does **not** block on active advisories. Advisories are informational, not gates.

A feature MAY add its own stop-hook gate that consults the advisory store (e.g., the backlog feature could refuse a stop with unresolved migration if the backlog has only legacy items). Each such gate must be a separate feature decision, justified in its own spec; this infrastructure does not impose one.

---

## 10. Open questions

### Q1: Probe versioning when feature ships an update — RESOLVED v0.2

**Decision:** Probes declare a `probe_version` (monotonic per `(feature, type)`). The version is included in the advisory `id` hash so a probe refinement produces a new id. On sync after a probe-version bump:
- Old advisory is auto-resolved with `state: "resolved"`, `resolved_by: "probe-update"`, `superseded_by: "<new-id>"`.
- New advisory is created with the new evidence shape and updated trigger summary.

The user sees one current advisory at a time per `(feature, type, project-state)` tuple. Old advisories are kept in compact form for idempotency (so the next sync doesn't re-trigger them) and then garbage-collected per §3.4 retention rules.

### Q2: Cross-clone state — RESOLVED v0.2

**Decision:** Two stores with sharply distinct semantics, formalized in §3.5:
- `project-state.yaml` (committed, shared) holds *answers* — the resolution-condition facts probes consult.
- `.advisories.json` (gitignored, per-clone) holds the *nag log* — active triggers and per-developer dismissals.

A team-wide dismissal mechanism (`dismissed_advisory_classes: []` in `project-state.yaml`) is left out of v1 but can be added later without schema churn — the `.advisories.json` schema doesn't change; the probes' resolution conditions gain a new check.

### Q3: Action-resolved vs sync-resolved race — RESOLVED v0.2

**Decision:** Probes declare both a **trigger condition** and a **resolution condition** (formalized in §7.1). The resolution condition reads from `project-state.yaml`, not from local code signals. This decouples "the codebase still has SDK imports" (correct and unchanged) from "the project has answered the question" (the actual issue). When a user action writes the resolution-condition fact to `project-state.yaml`, the probe stops firing on the next sync and the advisory auto-resolves.

Action-driven resolution (§4.3) is still supported for immediate feedback within a session — actions can write `resolved_at` directly without waiting for sync — but the authoritative resolution path is "project-state.yaml fact + probe re-run."

### Q4: Maximum advisory store size — RESOLVED v0.2

**Decision:** Non-active entries (resolved, dismissed) are stored in **compact form** (per §3.4) — only the fields needed to prevent re-trigger:
- Resolved compact: `id`, `state`, `resolved_at`, `resolved_by`, `superseded_by` (when applicable).
- Dismissed compact: `id`, `state`, `dismissed_at`, `dismissed_reason`.

Dismissals are kept forever (the dismissal is the load-bearing fact). Resolved entries have a 30-day TTL for "resolved since last session" reporting, then are removed. Soft cap stays at 100 active + 50 resolved-within-30-days + 200 dismissed. The compact form makes the 200-dismissed cap roughly 30KB of JSON max — well within any reasonable bound.

Full evidence is reconstructible on demand via `/prawduct-advisory show <id>` (the probe re-runs to recover the citation list).

### Q5: User-readable evidence cap — STILL OPEN

Some probes might find dozens of file:line citations (e.g., "hard-coded model ID in 12 files"). Five-item cap in §3.3 is a tradeoff between briefing brevity and forensics value.

**Lean:** keep the 5-cap for the in-store evidence array, but `/prawduct-advisory show <id>` can re-run the probe to surface the full evidence list. The store doesn't need to retain all 30 file:line citations forever. Confirm during build plan.

---

## 11. Success criteria

| # | Criterion | How measured |
|---|---|---|
| A1 | Advisories from both features surface in the same session briefing without conflict | Onboard a project that triggers both backlog and prompt-management probes; verify both appear |
| A2 | Re-running sync without state change does not duplicate advisories | Run sync twice; verify advisory list unchanged |
| A3 | User action that addresses the trigger condition results in advisory clearance on next sync (or immediately, if action-resolved) | Trigger advisory, run recommended action, observe clearance |
| A4 | Dismissed advisory does not re-surface on subsequent syncs even if trigger persists | Trigger, dismiss, re-sync, verify suppressed |
| A5 | Session briefing remains under 10 lines for typical projects (≤5 active advisories) | Audit briefing output on 3 onboarded projects |
| A6 | `/prawduct-advisory list` works correctly with `--state` and `--feature` filters | Manual test |
| A8 | Probe-version bump produces clean supersession (old advisory marked `resolved_by: probe-update` with `superseded_by` set; new advisory created cleanly) | Author probe v1, trigger, bump to v2, sync, verify supersession |
| A9 | Resolution condition reading from `project-state.yaml` correctly auto-clears advisories when a teammate's commit lands | Setup: dev A triggers advisory; dev B writes resolution fact to project-state.yaml and pushes; dev A pulls + syncs; advisory auto-resolves |
| A7 | Schema-version bump allows old stores to be read and migrated forward | Author a v0 store, sync should migrate to v1 or warn cleanly |

---

## 12. Dependencies

- **Sync subsystem** (`tools/lib/sync_cmd.py`) — must gain the probe-execution step and the diff-with-existing-store logic.
- **Session-briefing hook** (`tools/product-hook session-start` or equivalent) — must gain the advisories section.
- **CLI surface** — `/prawduct-advisory` skill + per-feature dismissal aliases (`/backlog dismiss-advisory`, `/llm-strategy dismiss-advisory`).
- **Feature build plans** — each feature implements its probes against this infrastructure's registration API.

---

## 13. Build order

This spec is a *precondition* for both feature build plans. The recommended build order:

1. **Phase 1**: Build this advisory infrastructure (schema, storage, lifecycle, CLI, sync integration, session-briefing integration). Ship as a framework version bump (e.g., v1.6.0) with no user-visible advisories yet (probe roster is empty).
2. **Phase 2**: Build the backlog feature (which adds backlog probes against §8.2). User-visible advisories begin surfacing.
3. **Phase 3**: Build the prompt-management feature (which adds prompt-management probes against §8.1). Adds the prompt-strategy and related advisories.

This staging ensures each feature's build plan can assume the advisory mechanism exists, while keeping the first ship as a no-op infrastructure release that's easy to roll back if issues surface.

---

## 14. Out of scope

- **Team-wide advisory state** (per-developer is sufficient for v1)
- **Time-based auto-dismissal** (e.g., "dismiss after 30 days of being shown") — keep user-action-only for v1
- **Cross-product advisory aggregation** ("what advisories do all my Prawduct products have?") — could be a future addition for users with many products, but out of scope here
- **Web UI / dashboard** — advisories are CLI-surfaced only
