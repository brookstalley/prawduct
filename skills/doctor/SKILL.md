---
description: Health-check, repair, and maintain an already-onboarded Prawduct repo (enable gates, verify, audit learnings)
argument-hint: "[no args — runs in the product repo]"
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash(prawduct-hook verify-operator-verification *), Bash(prawduct-hook audit-learnings *), Read, Glob
---

You are managing prawduct product-repo health under the **plugin** distribution model. Prawduct is installed as a Claude Code plugin (dev-time governance); a product commits only the install *reference* plus its own `.prawduct/` state — no framework files. Every flow operates on the consumer's own repo: there is no framework checkout to call back to.

This skill is for a repo that is **already onboarded**. To set up a new or existing repo, use **`/prawduct:onboard`** instead.

## Context Detection

1. If an explicit target path was provided → `doctor` runs in the *current* product repo, not on a target path. If they meant to **set up** that path, send them to **`/prawduct:onboard <path>`**; if they meant to **health-check a different** repo, have them `cd` there and re-run. Either way, stop here.
2. Else if the current directory has `.prawduct/` (is a product repo) → **Health Check**, and route to Enable-Gate / Verify / Audit-Learnings on explicit request.
3. Else → ask the user what they want to do.

| Request | Action |
|---|---|
| Set up a new or existing repo | **Use `/prawduct:onboard`** (not this skill) |
| Current dir is a product repo (has `.prawduct/`) | **Health Check**: see Health Check Flow |
| "enable coverage" / "turn on F4" / "enable operator verification" / "turn on F10" / similar | **Enable a gate**: see Enable-Gate Flow |
| "verify VRF-NN" / "drain operator verification" / "mark verified" | **Verify**: see Verify Flow |
| "audit learnings" / "retire structurally-enforced learnings" / "check lifecycle metadata" / similar | **Audit Learnings**: see Audit-Learnings Flow |

## Health Check Flow (current dir is a product repo)

Plugin-native — read the consumer's OWN `.prawduct/` and `.claude/` with Read / Glob; there is no framework path to resolve and nothing to sync. Check:

1. **Install reference** — `.claude/settings.json` has `enabledPlugins["prawduct@prawduct"]: true` and an `extraKnownMarketplaces.prawduct` source pinned `ref: "main"`. (Missing → contributors won't get governance on clone.)
2. **Distribution recorded** — `project-state.yaml` has `distribution: plugin`. (Absent → a legacy file-sync hook may still be governing; recommend `/prawduct:migrate`.)
3. **No stale file-sync residue** — no committed `tools/product-hook`, `tools/lib/`, framework `.claude/skills/critic/`, or `.prawduct/sync-manifest.json`. (Present → migration is incomplete; recommend `/prawduct:migrate`.)
4. **Static governance anchor** — `CLAUDE.md` contains the `PRAWDUCT:ANCHOR` marker (the thin governed-by-plugin anchor a migrated repo keeps).
5. **Core state present** — `.prawduct/` has `project-state.yaml`, `learnings.md`, `backlog.md`, `change-log.md`, and `artifacts/`.
6. **Discovery captured** — if the repo shows product-definition work (source code, or markdown under `docs/`), `project-state.yaml` should have `classification` and `product_definition` filled, not template-default (`domain: null` / `vision: null`). Template-default state alongside real product work means discovery was skipped — the docs-first / brownfield onboarding gap the **DISCOVERY NOT CAPTURED** session-briefing nudge also flags. Recommend **`/prawduct:discovery`** (reconciliation mode reads the existing docs/code and backfills `project-state.yaml`). A repo with no product work yet is fine — discovery comes when building starts.
7. **External backlog files** — if `TODO.md` / `BACKLOG.md` / `ROADMAP.md` / `IDEAS.md` exist in the repo root or `.github/` and aren't recorded in `backlog_external_imports`, report them and recommend **`/prawduct:backlog import <path>`** (don't auto-import — the user confirms). This is the explicit health-check surface for the same signal the `external-backlog-detected` session-start advisory raises ambiently; both resolve on `backlog_external_imports`.

Classify and report:
- **healthy**: install reference + `distribution: plugin` + no residue + core state present + discovery captured (or no product work yet) → "Your prawduct plugin setup is healthy."
- **degraded**: governance works but something is off (missing anchor, a missing non-critical file, or discovery uncaptured despite product work) — list each with its implication and the fix.
- **broken**: no install reference, or file-sync residue still committed — recommend `/prawduct:migrate` (or installing the plugin first).

## Enable-Gate Flow (coverage F4 / operator-verification F10)

Plugin-native — enabling a gate is a `project-state.yaml` flag flip (no migrate subcommand, no sync). This skill **reads and guides**; it does not edit `project-state.yaml`. Read the current value first, confirm intent (surface the BLOCKING consequence), then present the exact one-line edit for the user (or the main session) to apply.

### Coverage (F4 — symbol-coverage enforcement)
Set `coverage_required: true` in `.prawduct/project-state.yaml`. **Consequence:** the Critic's Goal 1 then BLOCKS on any changed file missing from `.test-evidence.json`'s `changes_referenced`. (`/prawduct:building` "Coverage Evidence" explains the evidence shape; `bin/test-reference-verify` is the Python symbol floor — stronger language-native tools give `coverage_level: executed`.)

### Operator verification (F10 — pre-merge human-verification gate)
Set `operator_verification_required: true` in `.prawduct/project-state.yaml`; entries accumulate in `.prawduct/operator-verification.md` as visual / live-integration chunks enqueue them. **Consequence:** `/prawduct:pr create` then BLOCKS while any entry's status is `pending`; the per-PR override is `/prawduct:pr create --accept-pending-verification "rationale"` (rationale recorded back into each entry).

(There is no `--enable-settings-layout` in the plugin world — "settings layout" was a file-sync `.claude/settings.json` normalization; under the plugin the only settings concern is the committed install reference, which Health Check validates.)

## Verify Flow (drain operator-verification queue)

Drains a single pending entry in `.prawduct/operator-verification.md` after the human-verification step is genuinely complete. Plugin-native — operates only on the repo's own `.prawduct/`.

1. Confirm the user has actually performed the verification described in the entry's `**Verify:**` checklist — `verify` is a deliberate user action, not a session-time auto-flip.
2. Run: `prawduct-hook verify-operator-verification <VRF-id>`
3. Relay the `previous_status → status` line ("pending → verified") and the action line. If the entry was already verified, the command is a no-op and surfaces a note.

Refuses to verify an `accepted` entry — `accepted` means the gate was overridden via `--accept-pending-verification`; flipping to verified would erase the override rationale. Edit the file by hand if the verification is now genuine.

## Audit-Learnings Flow (lifecycle metadata triage)

Plugin-native — `prawduct-hook audit-learnings` walks the repo's own `.prawduct/learnings.md`, reads the optional per-entry metadata comment, and reports promotion candidates (advisory), retirement candidates (sentinel-protected), and stale single-confirmation entries (>90 days old).

The metadata comment is a single line placed immediately after each `## Title`:

```markdown
## My learning
<!-- prawduct-learning: confirmations=2; created=2026-02-22; sentinel=tests/test_critic.py::test_summaries_check -->

Body of the learning…
```

All three fields are optional. An entry without the comment is treated as "active, no lifecycle metadata" and stays untouched.

Use when the user asks to "audit learnings", "retire structurally-enforced learnings", "check lifecycle metadata", or similar.

1. Run: `prawduct-hook audit-learnings --json`
2. Relay each list — surface promotion candidates as advisory ("the rule has been confirmed twice — consider whether it belongs in `learnings.md` or can move to historical detail"), retirement candidates pending `--apply` ("the declared sentinel passes; running with `--apply` moves the entry to `learnings-detail.md`"), stale flags ("the entry is over 90 days old with no second confirmation — has the rule held up?"), and errors (failing sentinels, malformed dates).
3. If the user confirms intent to retire, re-run with `--apply`: `prawduct-hook audit-learnings --apply --json`. The `--apply` invocation mutates two files: `.prawduct/learnings.md` (entry removed) and `.prawduct/learnings-detail.md` (entry appended under the "Historical (structurally enforced)" section).

The audit is read-only by default. Promotion is always advisory — `learnings.md` doesn't have a sectioned active/promoted split; the count just surfaces in the report. Retirement is the only mutation, and only when `--apply` is passed AND the sentinel passes.

## Important Notes

- Onboarding lives in **`/prawduct:onboard`** (scaffold a new or existing repo via `prawduct-hook init-product`, or route a pre-2.0 file-sync repo to `/prawduct:migrate`). This skill (`doctor`) covers an already-onboarded repo: health-check, enable-gate, verify, audit-learnings.
- Health Check and Audit-Learnings decide from the consumer's OWN `.prawduct/` — no framework checkout, no sync.
- Enabling a gate is a `project-state.yaml` flag flip; the BLOCKING consequence is immediate on the next relevant gate (governance is modeled as CI — see `/prawduct:methodology`).
- Hooks and governance activate in the target's own Claude Code session, not the current one.
