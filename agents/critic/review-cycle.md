# Critic: Review Cycle

Work-scaled review lifecycle. Review depth matches the size of the work.

---

## When Review Is Required

| Work size | Mode and frequency |
|---|---|
| **Trivial** (typo, config) | None — waive via `.gates-waived` if the stop hook prompts. |
| **Small** (bug fix, minor feature) | One `final` review, optional. |
| **Medium** (new feature, refactor) — non-chunked | One `final` review, mandatory after completion. |
| **Medium / Large** (chunked build plan) | `chunk` review per non-final chunk + `final` review on the last chunk. |
| **Any work merging a multi-cycle branch** | `cumulative` review before opening the PR (in addition to the per-chunk reviews above). |
| **Re-review after fixing prior BLOCKING/WARNING findings** | `verify-resolutions` — delta review against the prior pass's scope. Falls through to `chunk`/`final` when the anchor is missing or scope widens past the demotion threshold. |

The stop hook enforces review for code changes when a build plan exists. It also surfaces an advisory WARNING when all chunks are marked `[x]` but the most recent review ran Goals 1-3 only (`chunk` or `verify-resolutions` mode) — run `/critic final` before pushing.

`/pr create` is gated by `python3 tools/product-hook check-cumulative-critic` — opening a PR without a fresh, blocking-free `cumulative` record fails the gate.

## Mode Selection

Four modes: `chunk`, `final`, `cumulative`, `verify-resolutions`. The canonical caller is `/critic` (no args) — the SKILL invokes `python3 tools/product-hook infer-critic-mode` to pick the mode from git + build-plan state and records `mode_chosen_by` as the verbatim rationale string the helper returns (e.g., `"rule-3 final: last unchecked chunk of 4-chunk plan is in progress"`), or as the literal string `"explicit-args"` when `$ARGUMENTS` overrode inference. The build plan's `Critic mode:` field is the **build-plan-level override**; an explicit slash-command argument (`/critic chunk` etc.) is the **per-invocation override** on top of that. See `methodology/planning.md` "Critic Mode Per Chunk" for the heuristic of when an explicit declaration is worth the override.

**Heuristic when authoring a build plan** (mostly matches what inference will pick — declare `Critic mode:` only to override):
- Single-chunk plan → `final` (inference picks this; no declaration needed).
- Multi-chunk plan → first N-1 chunks `chunk`, last chunk `final` (inference picks this; no declaration needed).
- Trivial chunks (typo-level edits buried inside a larger plan) → waive entirely via `.gates-waived`.

**Fail-safe default:** if inference cannot anchor a confident pick and the build plan's `Critic mode:` field is absent, the build cycle treats the chunk as `final`. If the Critic itself is invoked with an unrecognized mode argument, it also runs `final`. Both layers fail safe to thoroughness.

## Per-Mode Behavior

| Aspect | `chunk` | `final` | `cumulative` | `verify-resolutions` |
|---|---|---|---|---|
| **Goals run** | 1, 2, 3 | All 7 goals | All 7 goals | 1, 2, 3 |
| **Goals skipped** | 4-7; Learnings Cross-Check; Backlog Reconciliation; Framework-Specific Checks (7-10); README/top-level docs scan | None | None | Same as `chunk` |
| **Scope** | Chunk's uncommitted diff (`git diff` + `git status` for new files) | Full session diff at end-of-cycle, OR uncommitted diff for non-chunked work | `git diff <base-branch>...HEAD` — the entire PR bundle, all commits on the branch since it diverged | Prior findings' `files_reviewed` ∪ files changed since `commit_reviewed` (see "Verify-resolutions scope and demotion" below) |
| **Execution** | Always single-pass | Single pass for trivial/small; coordinator pattern for medium/large | Single pass for trivial/small; coordinator pattern for medium/large | Always single-pass |
| **Target wall-clock** | 1-2 min | 4-10 min | 4-10 min | 1-2 min |
| **When invoked** | Between chunks of a multi-chunk plan, before committing | End of work cycle (last chunk), non-chunked medium+ work, or any time the right answer is unclear | Before opening a PR (gated by `/pr create`). Catches cross-chunk integration cracks. | After fixing prior BLOCKING/WARNING findings, to confirm the resolution without paying full-review latency. Demotes to `chunk` / `final` when prior findings lack `commit_reviewed`, hold no actionable findings, or scope widens past the threshold. |

**Two-form rule for the `mode` value:**
- **Caller-side** (in `$ARGUMENTS`, build plan field `Critic mode:`, slash-command argument): the short token — `chunk`, `final`, `cumulative`, or `verify-resolutions`.
- **Persisted-side** (in `.prawduct/.critic-findings.json`'s `mode` field, session briefings, gate WARNINGs): the verbose string — exactly `"chunk (lighter pass, not ready for push)"`, `"final (full review, ready for push)"`, `"cumulative (bundle review, ready for merge)"`, or `"verify-resolutions (delta review, prior findings only)"`.

Read short, write verbose. Verbose makes the JSON self-documenting in briefings — anyone reading the file sees what mode was used without consulting docs. The hook validator in `tools/product-hook` rejects bare short tokens in the persisted `mode` field.

### Per-Chunk Type Protocol Selector (v1.4 F6)

Each chunk also declares `Type:` (a separate axis from `Critic mode:`). The two are orthogonal — `Critic mode:` controls *how deep* the review is, `Type:` controls *what kind of work* is being reviewed. The Critic reads both and selects protocol per the matrix below.

Default `Type:` is `code` — fail-closed. A missing or unrecognized `Type:` is treated as `code` (full protocol). The stop-hook helper `_parse_build_plan_chunk_type` surfaces unknown values as an error; the Critic itself should also refuse to honor an unknown Type and default to `code`.

| Chunk type | When to use | Goals 1 (Broken) | Goal 2 (Missing) | Goal 3 (Unintended) | Test-evidence check | Stop-hook Critic gate |
|---|---|---|---|---|---|---|
| `code` (default) | Code or behavior changes | full | full | full | required | fires |
| `doc-only` | Methodology / template / prose-only edits | prose & numeric counts only | requirement coverage of prose deliverables | scope discipline | skipped (no test evidence required) | fires unless session is empirically doc-only too (file-extension based) |
| `trivial` | Small-blast-radius code change (rename, type annotations, mechanical edit) within Chunk 04 file-set bounds | full | full | full + **rationale-vs-diff fit** sub-check (see Goal 3 in SKILL.md) | required | fires (file-set bounds + `**Trivial because:**` rationale enforced structurally) |
| `cleanup` | Branch hygiene, file moves, dead-code removal | structural-only (no broken refs) | requirement coverage | scope discipline; tolerate zero diff | skipped | fires |
| `designer-handoff` | Visual / token / design-asset handoff to a human designer | skipped | skipped | skipped | skipped | **skipped** (formalized carveout — previously a user-memory rule) |
| `cumulative-final` | Marker on the last chunk of a multi-chunk plan | marker only — triggers `/critic cumulative` in addition to the chunk's own `final` review | — | — | — | fires |

The `Type:` field defaults to `code` when omitted. Declare `Type:` only when it deviates from `code`; minimal-declaration is the v1.4 convention. **The `Type:` axis is the proportional-effort knob (P11) — under-declaring is safe (worst case: redundant Critic time), over-declaring is unsafe (designer-handoff on a code chunk silently skips review).**

When chunk type is `designer-handoff` and the Critic is invoked anyway, output a single line: `Review skipped — Type: designer-handoff (visual handoff; review-by-human)` and exit clean. No findings file is required; the stop-hook gate skip is the structural enforcement.

### Cumulative-mode diff scope and PR gate

`cumulative` is the only mode whose scope is *not* derived from working-tree state. Compute the base via `git merge-base <base-branch> HEAD` (typically `main` or `develop` — read `project-preferences.md` if a different default is set). Then diff `<merge-base>...HEAD`. This deliberately spans every commit on the branch, not just the end-of-cycle diff `final` would see, so cross-chunk integration cracks surface here even if every per-chunk review was clean.

`/pr create` calls `python3 tools/product-hook check-cumulative-critic` and refuses to open the PR if the gate fails. The gate requires: cumulative-mode findings file present, schema-valid, recorded in the current session (mtime later than `.session-start`), and free of unresolved BLOCKING findings. WARNING and NOTE are advisory at the PR gate — they do not block, matching the PR reviewer's own severity contract.

**Prep work before invoking cumulative.** A cumulative review takes ~4-10 minutes synchronously. Before invoking it, complete any prep work that doesn't depend on its findings: `/learnings` for next-chunk topics, draft the PR description, audit the backlog for items this branch resolves, capture deferred chunk-boundary reflections. This does NOT shorten the wait — it reorganizes work so the agent can integrate findings the moment Critic returns rather than spinning up fresh post-wait. See `methodology/building.md` for the full guidance.

### Verify-resolutions scope and demotion

`verify-resolutions` is the only mode whose scope is anchored to a *prior* review rather than the current working tree. It exists to cut re-review latency after a Critic round flags 1-2 BLOCKING findings and the builder fixes them — re-running `/critic chunk` or `/critic final` walks the full diff again at full latency for a localized change.

**Scope computation.** Read the prior `.prawduct/.critic-findings.json`: scope = (prior `files_reviewed`) ∪ (files changed since prior `commit_reviewed` — `git diff --name-only <commit_reviewed>` plus `git ls-files --others --exclude-standard`). The Critic runs Goals 1-3 against this union — same goals as `chunk` mode, narrower surface. The canonical implementation is the `_compute_verify_resolutions_scope` helper in `tools/product-hook` — tests anchor on it, and a verify-resolutions findings file's `files_reviewed` must match what that helper would have returned at write time.

**Demotion criteria** (return empty scope; fall back to `/critic chunk` or `/critic final`):

| Trigger | Why it demotes |
|---|---|
| Prior findings file missing | Nothing to verify against. |
| Prior findings lack `commit_reviewed` (pre-v1.5 record) | No anchor for the delta. |
| `commit_reviewed` does not resolve in current repo | Rebase, force-push, or never on this branch — anchor unreliable. |
| Prior findings have no BLOCKING/WARNING entries | A verify pass has nothing actionable to re-check. |
| `len(files_since_commit) > 2 * len(prior_files_reviewed) + 5` | Scope widened beyond the prior surface — a partial review would mislead. |

These are fail-closed: when the helper cannot anchor a delta, it refuses to compute one rather than silently shrinking the review (learnings: "Escape hatches in classification create silent failures").

**Stop-hook gate behavior.** A `verify-resolutions` findings file clears the stop-hook Critic gate **only** when the current chunk diff is a subset of the findings' `files_reviewed`. If the builder adds work after the verify pass, those new files are out of scope, the gate refuses to clear, and the blocker names the specific out-of-scope files so the builder runs `/critic chunk` or `/critic final` next.

**When NOT to use verify-resolutions.** Don't use it as the only review for a chunk's first pass — it's a re-review mode, not a first-look mode. Don't use it across a `git rebase` or force-push that rewrites `commit_reviewed` — the helper detects this and demotes, but choosing it expecting a fast pass costs you a wasted invocation. And don't use it after a long pause where the working tree drifted unrelated to the original findings — that's exactly the scope-widening case the demotion threshold catches.

## Per-Chunk Cycle

1. Builder completes a chunk's implementation and tests.
2. Critic reviews using the goal-based approach (see SKILL.md).
3. **If BLOCKING findings exist:**
   - Builder fixes the issues.
   - Critic re-reviews — specifically watching for **fix-by-fudging**:
     - Weakening a test to make it pass instead of fixing the code → **BLOCKING**
     - Changing a spec to match wrong implementation instead of fixing the code → **BLOCKING**
     - Adding a workaround instead of addressing root cause → **WARNING**
   - Repeat until no blocking findings remain.
4. **Record findings** to `.prawduct/.critic-findings.json` (see main SKILL.md for format).
5. **If no BLOCKING findings:** chunk is complete, proceed to next chunk.

## Final-Mode Cross-Checks

After completing the goal-based review in `final` mode, run two additional passes that `chunk` mode skips:

### Learnings Cross-Check

Scan your findings against active learnings. If a change reintroduces a pattern that `.prawduct/learnings.md` explicitly warns against, escalate severity — the project already learned this lesson once and tolerating regression undoes the learning. Conversely, if learnings reference patterns relevant to the changed code and the code handles them correctly, no finding is needed: the learning is working as intended.

### Backlog Reconciliation

Read `.prawduct/backlog.md`. For each open item, check whether this session's changes resolve it — directly (the item was the work) or incidentally (other work addressed the underlying issue). For each resolved item, emit a **NOTE** finding: "Backlog item appears resolved: [item text]. Verify and remove from backlog." This keeps the backlog reflecting reality. Do not remove items yourself — the builder verifies and removes.

## Directional Change Review

When a significant architectural or design change spans multiple chunks, review the change holistically after all chunks are complete:

- **Artifact consistency:** Were all affected artifacts updated? Implementation referencing stale artifact content → **BLOCKING**.
- **Regression check:** Were pre-existing tests modified or removed? Review the diff for weakened or deleted tests → **BLOCKING** if tests were weakened to pass.
- **Retrospective:** Was the change reflected on? If missing → **WARNING**.

## Per-Chunk Output Format

```
## Critic Review — Chunk [ID]: [Name]

### Signals
[Work size, work type, files changed, boundaries crossed]

### Changes Reviewed
[List of files and what changed]

### Findings

#### [Finding Name]
**Goal:** [Goal Name]
**Severity:** blocking | warning | note
**Recommendation:** [What the Builder should do]

### Summary
[Total findings by severity. Whether the chunk passes review.]
```

## Recording Reviews

Every review cycle must produce a findings record — governance without an audit trail is documentation fiction.

After each review cycle, write `.prawduct/.critic-findings.json` with the findings (see main SKILL.md for format). When no findings exist, record an empty findings array.
