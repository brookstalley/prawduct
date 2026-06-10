# Critic: Review Cycle

Work-scaled review lifecycle. Review depth matches the size of the work.

---

## When Review Is Required

| Work size | Mode and frequency |
|---|---|
| **Trivial** (typo, config) | None — waive via `.gates-waived` if the stop hook prompts. |
| **Small** (bug fix, minor feature) | One `final` review, optional. |
| **Medium** (new feature, refactor) — non-chunked | One `final` review, mandatory after completion. |
| **Medium / Large** (chunked build plan) | `chunk` review per non-final chunk + `final` review on the last chunk — except when the last chunk is `Type: cumulative-final`: then ONE `cumulative` IS the last chunk's review (no separate `final`). |
| **Any work merging a multi-cycle branch** | `cumulative` review before opening the PR (in addition to the per-chunk reviews above — but on a `cumulative-final` plan it doubles as the last chunk's review, not a second pass). |
| **Re-review after fixing prior BLOCKING/WARNING findings** | `verify-resolutions` — delta review against the prior pass's scope. Falls through to `chunk`/`final` when the anchor is missing or scope widens past the demotion threshold. |

The stop hook enforces review for code changes when a build plan exists. It also surfaces an advisory WARNING when all chunks are marked `[x]` but the most recent review ran Goals 1-3 only (`chunk` or `verify-resolutions` mode) — run `/prawduct:critic final` before pushing.

`/prawduct:pr create` is gated by `prawduct-hook check-cumulative-critic` — opening a PR without a blocking-free, HEAD-covering `cumulative` record fails the gate. A `verify-resolutions` **chain record** that extends such a cumulative also satisfies it (CRT-4J8W — see "The chain" below).

## Mode Selection

Four modes: `chunk`, `final`, `cumulative`, `verify-resolutions`. The canonical caller is `/prawduct:critic` (no args) — the SKILL invokes `prawduct-hook infer-critic-mode` to pick the mode from git + build-plan state and records `mode_chosen_by` as the verbatim rationale string the helper returns (e.g., `"rule-3 final: last unchecked chunk of 4-chunk plan is in progress"`), or as the literal string `"explicit-args"` when `$ARGUMENTS` overrode inference.

Three precedence layers, highest first:

1. **Per-invocation override** — an explicit slash-command argument (`/prawduct:critic chunk` etc.). Recorded as `mode_chosen_by: "explicit-args"`.
2. **Plan-level override** — the active build plan's CURRENT chunk (normally the first unchecked `- [ ]` item in the Status section; on a `views_enabled` feature branch, git-derived since the checkboxes don't flip until release — CRT-7B4M) `Critic mode:` field. **As of CRT-3M8Q this override is honored by inference itself**: `infer-critic-mode` reads the current chunk's `**Critic mode:**` field and, when it names a valid mode, returns that mode with rationale `plan-override: <mode>` — *before* walking the inference rules. Previously this field was inert (the Skill-tool args never threaded to the forked skill's `$ARGUMENTS`, and the skill didn't read the plan), so a plan-mandated `final` silently ran as the inferred `chunk`. Now a plan-mandated mode wins over inference. An absent, blank, or unrecognized `Critic mode:` value is ignored and inference proceeds normally.
3. **Inference** — the four rules (`verify-resolutions > cumulative > final > chunk`), used only when neither override applies.

See `methodology/planning.md` "Critic Mode Per Chunk" for the heuristic of when an explicit declaration is worth the override.

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
| **Scope** | Chunk's uncommitted diff (`git diff` + `git status` for new files) | Full session diff at end-of-cycle, OR uncommitted diff for non-chunked work | `git diff <merge-base>...HEAD` (base from `prawduct-hook resolve-base`) — the entire PR bundle, all commits on the branch since it diverged | Prior findings' `files_reviewed` ∪ files changed since `commit_reviewed` (see "Verify-resolutions scope and demotion" below) |
| **Execution** | Always single-pass | Single pass for trivial/small; coordinator pattern for medium/large | Single pass for trivial/small; coordinator pattern for medium/large | Always single-pass |
| **Target wall-clock** | 1-2 min | 4-10 min | 4-10 min | 1-2 min |
| **When invoked** | Between chunks of a multi-chunk plan, before committing | End of work cycle (last chunk), non-chunked medium+ work, or any time the right answer is unclear | Before opening a PR (gated by `/prawduct:pr create`). Catches cross-chunk integration cracks. | After fixing prior BLOCKING/WARNING findings, to confirm the resolution without paying full-review latency — or after a *committed* post-cumulative fix, where the resulting chain record satisfies the PR gate (CRT-4J8W). Demotes to `chunk` / `final` when prior findings lack `commit_reviewed`, hold no actionable findings (and no chain-extendable delta), or scope widens past the threshold. |

**Two-form rule for the `mode` value:**
- **Caller-side** (in `$ARGUMENTS`, build plan field `Critic mode:`, slash-command argument): the short token — `chunk`, `final`, `cumulative`, or `verify-resolutions`.
- **Persisted-side** (in `.prawduct/.critic-findings.json`'s `mode` field, session briefings, gate WARNINGs): the verbose string — exactly `"chunk (lighter pass, not ready for push)"`, `"final (full review, ready for push)"`, `"cumulative (bundle review, ready for merge)"`, or `"verify-resolutions (delta review, prior findings only)"`.

Read short, write verbose. Verbose makes the JSON self-documenting in briefings — anyone reading the file sees what mode was used without consulting docs. The hook validator in `prawduct-hook` rejects bare short tokens in the persisted `mode` field.

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
| `cumulative-final` | Marker on the last chunk of a multi-chunk plan | marker only — the chunk's review IS the one `/prawduct:critic cumulative`: commit the chunk first, then run it once; no separate `final` (cumulative is a strict superset — all 7 goals + cross-checks over `merge-base...HEAD` ⊇ the chunk diff) | — | — | — | fires |

The `Type:` field defaults to `code` when omitted. Declare `Type:` only when it deviates from `code`; minimal-declaration is the v1.4 convention. **The `Type:` axis is the proportional-effort knob (P11) — under-declaring is safe (worst case: redundant Critic time), over-declaring is unsafe (designer-handoff on a code chunk silently skips review).**

When chunk type is `designer-handoff` and the Critic is invoked anyway, output a single line: `Review skipped — Type: designer-handoff (visual handoff; review-by-human)` and exit clean. No findings file is required; the stop-hook gate skip is the structural enforcement.

### Cumulative-mode diff scope and PR gate

`cumulative` is the only mode whose scope is *not* derived from working-tree state. Resolve the base branch with `prawduct-hook resolve-base` (run it as a discrete step) — it honors a configured `base_branch:` in `project-state.yaml` (gitflow `develop`), falling back to `origin/main`/`main` for trunk repos. This is the **single source of truth** the PR/coverage gates use too, so the reviewer and the gates never diff different ranges — don't guess the base from prose. Then compute `git merge-base <base> HEAD` and diff `<merge-base>...HEAD`. This deliberately spans every commit on the branch, not just the end-of-cycle diff `final` would see, so cross-chunk integration cracks surface here even if every per-chunk review was clean. (Why this matters: on a gitflow repo, a `main`-anchored base diffs the whole `develop..main` promotion range — a 2-commit feature branch reviewed as dozens of commits.)

`/prawduct:pr create` calls `prawduct-hook check-cumulative-critic` and refuses to open the PR if the gate fails. The gate requires: cumulative-mode findings file present, schema-valid, **covering current HEAD** (CRT-7M2D — the recorded `commit_reviewed` is HEAD, or the only files changed since are docs `.md`), and free of unresolved BLOCKING findings. Coverage, not recency, is the test: a code change since the review fails the gate (re-run needed), but a doc-only change does not — so an inert post-review fix doesn't force a needless re-run. WARNING and NOTE are advisory at the PR gate — they do not block, matching the PR reviewer's own severity contract.

**The chain (CRT-4J8W).** A code fix *after* the cumulative no longer forces a full bundle re-review. The gate equally accepts a `verify-resolutions` record that **extends** the cumulative: `extends_cumulative.commit_reviewed` = the cumulative's anchor X (resolvable), 0 BLOCKING findings, the record's own `commit_reviewed` covers HEAD (same `==HEAD`-or-doc-only-since rule), and every non-`.md`, non-metadata file changed in `X..HEAD` is in the record's `files_reviewed` — fail closed on any gap. Soundness: cumulative@X vouches for the bundle; a clean delta review whose scope covers `X..HEAD` extends that vouching to HEAD. Sequencing matters: **commit the fix first, then run `/prawduct:critic verify-resolutions`** — a verify record anchored pre-commit can never cover HEAD (`chain-stale`). Chains may stack (a chain record propagates its original anchor); the scope-widening demotion bounds their length.

**Prep work before invoking cumulative.** A cumulative review takes ~4-10 minutes synchronously. Before invoking it, complete any prep work that doesn't depend on its findings: `/prawduct:learnings` for next-chunk topics, draft the PR description, audit the backlog for items this branch resolves, capture deferred chunk-boundary reflections. This does NOT shorten the wait — it reorganizes work so the agent can integrate findings the moment Critic returns rather than spinning up fresh post-wait. See `methodology/building.md` for the full guidance.

### Verify-resolutions scope and demotion

`verify-resolutions` is the only mode whose scope is anchored to a *prior* review rather than the current working tree. It exists to cut re-review latency after a Critic round flags 1-2 BLOCKING findings and the builder fixes them — re-running `/prawduct:critic chunk` or `/prawduct:critic final` walks the full diff again at full latency for a localized change.

**Scope computation.** Don't reimplement — call `prawduct-hook compute-verify-resolutions-scope` (v1.5.1 Chunk 03). The subcommand wraps the canonical `_compute_verify_resolutions_scope` helper so the agent and the stop-hook gate compute identical scopes by construction. **stdout** = newline-separated file paths (the scope union); **stderr** = one reason line; **exit codes**: 0 = scope computed (use the files); 1 = cannot compute (missing prior findings, no `commit_reviewed`, unresolved commit, no actionable findings, git failure, etc.) — fall back to `/prawduct:critic chunk` or `/prawduct:critic final` and record `mode_chosen_by: "fallback-no-prior-findings"`; 2 = scope widened past `len(delta) > 2 * len(prior) + 5` — fall back to `/prawduct:critic final` and record `mode_chosen_by: "fallback-scope-widened"`. Underlying scope formula: (prior `files_reviewed`) ∪ (files changed since prior `commit_reviewed` — `git diff --name-only <commit_reviewed>` plus `git ls-files --others --exclude-standard`, metadata-paths excluded).

**Demotion criteria** (return empty scope; fall back to `/prawduct:critic chunk` or `/prawduct:critic final`):

| Trigger | Why it demotes |
|---|---|
| Prior findings file missing | Nothing to verify against. |
| Prior findings lack `commit_reviewed` (pre-v1.5 record) | No anchor for the delta. |
| `commit_reviewed` does not resolve in current repo | Rebase, force-push, or never on this branch — anchor unreliable. |
| Prior findings have no BLOCKING/WARNING entries — *unless* the prior is chain-extendable (cumulative, or a chain record) AND something changed since `commit_reviewed` (CRT-4J8W) | A verify pass has nothing actionable to re-check; with a chain-extendable prior + delta, the delta itself is the work — the pass extends the cumulative to HEAD. |
| `len(files_since_commit) > 2 * len(prior_files_reviewed) + 5` | Scope widened beyond the prior surface — a partial review would mislead. |

These are fail-closed: when the helper cannot anchor a delta, it refuses to compute one rather than silently shrinking the review (learnings: "Escape hatches in classification create silent failures").

**Chain anchor emission (CRT-4J8W).** When the prior record is chain-extendable, the subcommand's `ok:` reason line ends with `extends-cumulative=<sha>` — the cumulative anchor this verify pass extends (propagated unchanged through stacked chain records). Record it in the findings file as `extends_cumulative: {"commit_reviewed": "<sha>"}` (SKILL.md step 7); the PR gate's chain acceptance depends on it. No suffix → no anchor to embed.

**Stop-hook gate behavior.** A `verify-resolutions` findings file clears the stop-hook Critic gate **only** when the current chunk diff is a subset of the findings' `files_reviewed`. If the builder adds work after the verify pass, those new files are out of scope, the gate refuses to clear, and the blocker names the specific out-of-scope files so the builder runs `/prawduct:critic chunk` or `/prawduct:critic final` next.

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

**Last chunk of a `Type: cumulative-final` plan — one review, not two.** Commit the chunk, then run `/prawduct:critic cumulative` ONCE: that review is simultaneously the chunk's review and the PR-gate record. Don't run a separate `final` first — cumulative is a strict superset (all 7 goals + Framework checks + cross-checks, over `merge-base...HEAD`, which contains the chunk's diff), so a preceding `final` re-pays 4-10 minutes for assurance the cumulative re-derives anyway. Mode inference already implements the sequencing: with the last chunk's work still uncommitted, `/prawduct:critic` infers `final` (rule-3 — the right call for a MID-chunk look); once the chunk is committed and the tree is clean, it infers `cumulative` (rule-2) — the AT-COMMIT review. Post-cumulative fixes ride the verify-resolutions chain (CRT-4J8W), not a second full pass.

## Final-Mode Cross-Checks

After completing the goal-based review in `final` mode, run two additional passes that `chunk` mode skips:

### Learnings Cross-Check

Scan your findings against active learnings. If a change reintroduces a pattern that `.prawduct/learnings.md` explicitly warns against, escalate severity — the project already learned this lesson once and tolerating regression undoes the learning. Conversely, if learnings reference patterns relevant to the changed code and the code handles them correctly, no finding is needed: the learning is working as intended.

### Backlog Reconciliation

Read `.prawduct/backlog.md`. For each open item, check whether this session's changes resolve it — directly (the item was the work) or incidentally (other work addressed the underlying issue). For each resolved item, emit a **NOTE** finding: "Backlog item appears resolved: [item text]. Verify and `/prawduct:backlog update <id> status=shipped`." This keeps the backlog reflecting reality. Do not change status yourself — the framework never infers status (D4); the builder makes the explicit call.

**Backlog hygiene checks (C-B1–C-B4 — all NOTE-level, never BLOCKING)** — inspect the diff + backlog for four soft signals (`/prawduct:backlog` is the fix path for each):
- **C-B1 — missing metadata:** a new backlog item in the diff with no metadata bar → NOTE the structured format.
- **C-B2 — no dedup evidence:** a new item whose `area:` already has ≥3 items → NOTE "check [the existing IDs] for overlap (`/prawduct:backlog dedup`)."
- **C-B3 — missing hygiene step:** the cycle's diff touches an area with open items but no chunk reviewed/updated them → NOTE "open items in area X — assess whether any are affected and update status."
- **C-B4 — dangling ID:** a build plan / change-log / chunk body references `PFX-XXXX` with no such item → NOTE (could be a typo or a not-yet-filed forward reference).

These flag; they never adjudicate whether an item "really" closed (the builder's call, D4) and never block.

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
