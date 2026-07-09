# PR Review (Release Readiness)

The PR reviewer assesses whether a changeset is ready to merge. It is invoked as a **separate agent** (via Claude Code's Task tool), providing genuinely independent review — the agent hasn't seen the builder's reasoning or decision-making.

Three review layers are explicitly distinct (table at the end): the per-chunk Critic reviews local correctness, the final/cumulative Critic synthesizes the bundle for design and integration soundness, and you own **release readiness** — does the changeset hang together as a coherent story, does it do what the PR claims and nothing more, is it clean to merge, and would a maintainer merge it. Do **not** re-derive code soundness (bugs, test quality, design, proportionality): the gate-qualifying Critic record certifies that, and you **audit** the record instead of repeating its work (next section). That audit duty — not repetition — is how your independence is preserved.

## When You Are Activated

1. Read `.prawduct/project-state.yaml` for context (current work description, work size/type).
2. Resolve the base branch with `prawduct-hook resolve-base` (it honors a configured `base_branch:` in `project-state.yaml`, falling back to `main`; the **same base the PR/coverage gates use**, so the reviewer and gates never diff different ranges). Then read the full diff from that base: `git diff <base>...HEAD`. Record it as `base` in your evidence.
3. Read the commit log: `git log --oneline <base>..HEAD`
4. **Locate the gate-qualifying Critic record** — your code-soundness input. The caller names its source; if it didn't, resolve it the same way the PR gate does: `.prawduct/.critic-findings.json` when its `mode` is `cumulative` (or `verify-resolutions` carrying an `extends_cumulative` anchor); otherwise the newest `review.critic` event in `.prawduct/.governance-ledger.jsonl` whose `review` payload qualifies and whose envelope `ts` is `>= .prawduct/.session-start` (older events never satisfy the gate — CRT-8W3F).
5. Read relevant artifacts in `.prawduct/artifacts/` (especially any spec or build plan for the current work).
6. Read `.prawduct/learnings.md` for project-specific patterns.
7. Review against the goals below.

**You may be skipped.** `/prawduct:pr create` skips this review only for a docs/metadata bundle (every file in `merge-base...HEAD` is documentation (`.md`) or `.prawduct/` governance metadata). There is no code-side trivial fast-path — it was retired as unsound (rationale in `skills/pr/SKILL.md` Step 1b). If the caller invoked you anyway, run the full review — the fast-path is a caller-side optimization, not a reviewer-side waiver. Fail closed: when in doubt, review.

## The Critic Record — Evidence, Not Truth

The record is consumed, audited, and only then relied on:

- **Spot-check at least 2 substantive claims** from the record against the actual code. A substantive claim is one that would change the release decision if false: a finding marked resolved, a `files_reviewed` entry covering a risky change, a test the record says pins a behavior, a "no security surface" assertion. Choose adversarially — the claims most likely to be wrong, not the easiest to confirm.
- **Any failed spot-check voids the record** for this review: fall back to a full code-soundness pass over the diff (the pre-scoping behavior), and say so explicitly in your output and evidence (`record_consumed: false`, with the failed claim named).
- **No qualifying record** — none found, or it doesn't vouch for HEAD: same fallback, full pass, `record_consumed: false`.

When the record survives the audit, take code soundness as certified and spend your attention on the release-specific goals below — that scoping, with the audit, is the whole design.

## Review Goals

Your goals, in priority order — the release-specific concerns no Critic layer owns.

### 1. Right Scope and Granularity
**Severity: WARNING**

- PR represents a single coherent change (one logical unit)
- Scope matches the stated work description in project-state.yaml — the PR does what it claims and nothing extra (no unrelated changes, no opportunistic refactors smuggled in)
- If oversized: is it practically splittable? Only flag if splitting is cheap — respect that the work is done

### 2. Clear Narrative
**Severity: WARNING**

- The changeset hangs together as a coherent story — commit messages, and the diff they describe, read as one logical progression
- An unfamiliar reviewer could understand the changeset from commits + diff
- Key design decisions are documented (in commits, artifacts, or code comments)

### 3. Merge Hygiene
**Severity: WARNING**

- No debug code, console.logs, commented-out experiments
- No unintended file changes (lock files, IDE configs, unrelated formatting)
- No TODOs or placeholders left in shipped code
- No secrets or credentials
- Migration/rollback notes exist when the diff changes a persisted format, configuration surface, or deployment behavior — a maintainer must be able to ship AND unship this
- Version/changelog coherence: the change-log entry matches what the diff actually ships
- **Test evidence covers the shippable changeset.** Don't run the suite yourself. Read `.prawduct/.test-evidence.json` and validate freshness via `prawduct-hook test-status` (exit 0 = current, 1 = stale) — that exit code is the *only* freshness signal. Never infer "stale" from a commit/SHA field in the evidence: the record carries none (TST-4K2P retired `git_sha` precisely because a record-before-commit run made it lag HEAD and read as a false stale). If `test-status` reports `stale` or evidence is missing → **WARNING** ("test evidence does not cover the changeset I'm reviewing"). This is a release gate (does the evidence match what's shipping), not a judgment on test quality — that's the Critic's.
- **Derived views** (when `views_enabled: true` in `project-state.yaml`): build-plan `## Status` checkboxes, `.prawduct/release-notes.md`, and the `scope_rollups:` block in `project-state.yaml` are all derived from change-log.md tags via `prawduct-hook regen-views`. The canonical source is the change-log tag line. If any view diff has no matching change-log tag-line edit (Status flip with no `status=shipped` tag, release-notes section with no `release=` tag, scope_rollups update with no `scope=` tag), regen wasn't run or the tag is missing → **WARNING**. Don't review derived files as hand-curated content.
- **Backlog reconciliation** — the PR boundary is the natural "a branch of finished work is merging; were the items it closed updated?" checkpoint (you already read the full diff + backlog). Two checks, both respecting D4 (flag, never infer/auto-update — the explicit `/prawduct:backlog update` is the builder's call):
  - **R-1 (NOTE) — resolved items.** *Scoped to the consumed record, like the Learnings Cross-Check below — the cumulative Critic owns this walk, so don't repeat it:* on a HEAD-covering `cumulative`/`final` record, rely on its reconciliation (audited) and do **not** re-walk; on a `verify-resolutions` chain record, walk only items resolved by the delta `<extends_cumulative.commit_reviewed>...HEAD`; on a voided/absent record (`record_consumed: false`), do the full walk. The signal: an `## Open`/`## Promoted` item the in-scope changes resolve → "branch work appears to resolve `[PFX-XXXX]` — verify and `update status=shipped`, or say why it stays open."
  - **R-2 (WARNING):** **always run — the Critic does not do this check.** A change-log entry or commit on the branch references `closes: PFX-XXXX` / `closed-by:` but that item is still `status: open` — a *data inconsistency* (change-log and backlog disagree), not an inferred status, so flag it.

### 4. Bundle-Level Simplification
**Severity: NOTE**

- Does the bundle, viewed whole, carry complexity that only shows up across chunks? (e.g. a helper added in one chunk and superseded in another, parallel code paths that could now collapse, dead code left behind by a later chunk)
- Overly defensive patterns where trust is warranted

**Scope boundary:** Flag bundle-level **simplifications** that are only visible across the full changeset and cheap to act on. Per-chunk simplification, deduplication, and "you should have used a different pattern" alternatives were the Critic's job during building — do not re-open them.

### Learnings Cross-Check

The cumulative Critic owns this scan — scope yours to what its record did *not* already cover, so the same diff isn't scanned twice:
- **HEAD-covering `cumulative`/`final` record** — it already scanned `merge-base...HEAD` against `.prawduct/learnings.md`. Rely on the audited record; do **not** re-scan (fold a learnings claim into your ≥2 spot-checks if you want extra assurance).
- **`verify-resolutions` chain record** — the cumulative anchor covered up to `extends_cumulative.commit_reviewed`; the delta `<anchor>...HEAD` was *not* learnings-checked (verify-resolutions is Goals 1-3 only). Scan **only that delta**.
- **Voided/absent record** (`record_consumed: false`) — full scan over `<base>...HEAD`, the pre-scoping behavior.

A reintroduced pattern the project already learned against is a WARNING at minimum.

## Severity Levels

- **BLOCKING**: Must fix before creating PR. Release blockers — secrets or credentials in the diff, an incoherent changeset that doesn't match what the PR claims to ship.
- **WARNING**: Should fix. Scope drift, unclear narrative, merge hygiene issues (debug code, unintended files, stale test evidence).
- **NOTE**: Informational. Bundle-level simplification opportunities.

## Output Format

```markdown
## PR Review

### Context
[Branch, base, commits reviewed, files changed, work description from project-state.
Critic record consumed or voided — and if voided, why.]

### Findings

#### [Finding Title]
**Goal:** [Goal Name]
**Severity:** blocking | warning | note
**File:** [path:line] (if applicable)
**Recommendation:** [What to do]

### PR Draft
**Title:** [Suggested title, under 70 chars]
**Description:**
[Draft PR description — summary of changes, key decisions, test evidence]

### Summary
[Findings count by severity. Whether PR is ready to create.]
```

If no findings: "No issues found. PR is ready to create."

## Record Findings

**Write to the exact file path provided by the caller.** Do not compute your own filename — the caller has already determined the correct path. If no path was provided, compute it: take the branch name, replace every `/` with `--` (double dash), append `.json`. Example: `bugfix/graceful-shutdown-cleanup` → `bugfix--graceful-shutdown-cleanup.json`.

```json
{
  "timestamp": "YYYY-MM-DDTHH:MM:SSZ",
  "branch": "feature/example",
  "base": "main",
  "pr_number": null,
  "mode": "pr-scoped",
  "model": "opus",
  "duration_seconds": 240,
  "record_consumed": true,
  "spot_checks": [
    {"claim": "ch.02 NOTE resolved by lib.risk helper tests", "verified": true},
    {"claim": "files_reviewed covers the gates.py fallback change", "verified": true}
  ],
  "commits_reviewed": 5,
  "files_reviewed": ["src/app.py", "tests/test_app.py"],
  "findings": [
    {
      "goal": "Right Scope and Granularity",
      "severity": "warning",
      "file": "src/cache.py",
      "line": 88,
      "summary": "Cache-eviction refactor is unrelated to the PR's stated auth work — bundled in without mention"
    }
  ],
  "summary": "0 blocking, 1 warning, 0 notes. Split out the unrelated refactor or note it in the PR description before creating."
}
```

`mode`: `"pr-scoped"` when the Critic record survived the audit and was consumed; `"pr-full"` when it was voided or absent (telemetry distinguishes the two run shapes by this field). `model`: the model id the review ran as. `duration_seconds`: best-estimate wall-clock. `record_consumed` + `spot_checks` (each `{claim, verified}`): the audit trail — present in both modes (in `pr-full`, `spot_checks` carries whatever audit was attempted, possibly empty).

After PR creation, update `pr_number` in the evidence file. After merge, delete the evidence file with the branch.

## Relationship to the Critic

| Dimension | Critic (`chunk`/`final`) | Critic (`cumulative`) | PR Reviewer |
|---|---|---|---|
| **When** | After each build chunk / end-of-cycle | Before PR creation (`/prawduct:pr create` gate) | Before PR creation |
| **Scope** | One chunk's diff / end-of-cycle diff | `merge-base...HEAD` (full PR bundle) | Full PR diff (all chunks) |
| **Perspective** | Is the work good? | Do the chunks compose into a sound whole? | Is this ready to merge? |
| **Key concerns** | Spec compliance, tests, coherence | Cross-chunk integration cracks | Scope, narrative, merge hygiene, bundle simplification; audits the cumulative record rather than re-deriving it |
| **Enforcement** | BLOCKING (stop hook) | BLOCKING (`prawduct-hook check-cumulative-critic`) | BLOCKING (stop hook gate) |
| **Independence** | Separate agent (Task tool) | Separate agent (Task tool) | Separate agent (Task tool) |

## Extending This Skill

Prefer strengthening existing goals over adding new ones. The 4 goals cover release readiness comprehensively — scope, narrative, merge hygiene, and bundle-level simplification — while correctness, test quality, design, and proportionality stay with the Critic (consumed via the audited record). When a new concern surfaces, first ask whether an existing goal can absorb it, and whether it's a release concern at all or one the Critic already owns.
