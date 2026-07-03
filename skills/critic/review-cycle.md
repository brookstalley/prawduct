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
| **Any work merging a multi-cycle branch** | `cumulative` review before opening the PR (on a `cumulative-final` plan it doubles as the last chunk's review, not a second pass). |
| **Re-review after fixing prior BLOCKING/WARNING findings** | `verify-resolutions` — delta review against the prior pass's scope. Falls through to `chunk`/`final` when the anchor is missing or scope widens past the demotion threshold. |

The stop hook enforces review for code changes when a build plan exists, and surfaces an advisory WARNING when all chunks are `[x]` but the most recent review ran Goals 1-3 only — run `/prawduct:critic final` before pushing.

`/prawduct:pr create` is gated by `prawduct-hook check-cumulative-critic` — a blocking-free, HEAD-covering `cumulative` record is required. A `verify-resolutions` **chain record** extending such a cumulative also satisfies it (see "The chain" below).

## Mode Selection

Four modes: `chunk`, `final`, `cumulative`, `verify-resolutions`. The canonical caller is `/prawduct:critic` (no args) — the SKILL forwards any invocation arguments verbatim to `prawduct-hook infer-critic-mode`, which owns the full precedence and records `mode_chosen_by` as its verbatim rationale string. Three precedence layers, highest first, all implemented inside the helper:

1. **Per-invocation override** — an explicit mode argument (`/prawduct:critic chunk` etc.). Rationale: `"explicit-args"`. The skill must forward, never parse (Skill-tool invocation of a fork-context skill does not substitute `$ARGUMENTS`; SKILL step 1 collects arguments from whichever delivery path carried them).
2. **Plan-level override** — the active build plan's current chunk's `Critic mode:` field (on a `views_enabled` feature branch the current chunk is git-derived, since checkboxes only flip at release). A valid value wins over inference with rationale `plan-override: <mode>`; an absent, blank, or unrecognized value is ignored.
3. **Inference** — the four rules (`verify-resolutions > cumulative > final > chunk`).

See `methodology/planning.md` "Critic Mode Per Chunk" for the authoring heuristic — what inference will pick per plan shape, and when an explicit declaration is worth the override.

**Fail-safe default (canonical statement):** If the mode is missing, unrecognized, or inference cannot make a confident call, run `final`. Every layer — the build cycle, the inference helper, and the Critic itself — fails safe to thoroughness.

## Per-Mode Behavior

| Aspect | `chunk` | `final` | `cumulative` | `verify-resolutions` |
|---|---|---|---|---|
| **Goals run** | 1, 2, 3 | All 7 goals | All 7 goals | 1, 2, 3 |
| **Goals skipped** | 4-7; Learnings Cross-Check; Backlog Reconciliation; Framework-Specific Checks (7-10); README/top-level docs scan | None | None | Same as `chunk` |
| **Scope** | Chunk's uncommitted diff (`git diff` + `git status` for new files) | Full session diff at end-of-cycle, OR uncommitted diff for non-chunked work | `git diff <merge-base>...HEAD` (base from `prawduct-hook resolve-base`) — the entire PR bundle | Prior findings' `files_reviewed` plus files changed since `commit_reviewed` (see "Verify-resolutions scope and demotion") |
| **Execution** | Always single-pass | Single pass for trivial/small; coordinator pattern for medium/large | Single pass for trivial/small; coordinator pattern for medium/large | Always single-pass |
| **Target wall-clock** | 1-2 min | 4-10 min | 4-10 min | 1-2 min |
| **When invoked** | Between chunks of a multi-chunk plan, before committing | End of work cycle (last chunk), non-chunked medium+ work, or any time the right answer is unclear | Before opening a PR (gated by `/prawduct:pr create`). Catches cross-chunk integration cracks. | After fixing prior BLOCKING/WARNING findings — or after a *committed* post-cumulative fix, where the resulting chain record satisfies the PR gate. Demotes to `chunk`/`final` when prior findings lack `commit_reviewed`, hold nothing actionable (and no chain-extendable delta), or scope widens past the threshold. |

**Two-form rule for the `mode` value:**
- **Caller-side** (in `$ARGUMENTS`, build plan field `Critic mode:`, slash-command argument): the short token — `chunk`, `final`, `cumulative`, or `verify-resolutions`.
- **Persisted-side** (in `.prawduct/.critic-findings.json`'s `mode` field, session briefings, gate WARNINGs): the verbose string — exactly `"chunk (lighter pass, not ready for push)"`, `"final (full review, ready for push)"`, `"cumulative (bundle review, ready for merge)"`, or `"verify-resolutions (delta review, prior findings only)"`.

Read short, write verbose — the JSON stays self-documenting in briefings. The hook validator rejects bare short tokens in the persisted `mode` field.

### Per-Chunk Type Protocol Selector

Each chunk also declares `Type:` — a separate axis from `Critic mode:`; definitions and when to declare each value live in `methodology/planning.md` "Choosing a Chunk Type". The Critic reads both fields and selects protocol per the matrix below. A missing or unrecognized `Type:` is treated as `code` (full protocol, fail-closed) — the Critic refuses to honor an unknown Type.

| Chunk type | When to use | Goals 1 (Broken) | Goal 2 (Missing) | Goal 3 (Unintended) | Test-evidence check | Stop-hook Critic gate |
|---|---|---|---|---|---|---|
| `code` (default) | Code or behavior changes | full | full | full | required | fires |
| `doc-only` | Methodology / template / prose-only edits | prose & numeric counts only | requirement coverage of prose deliverables | scope discipline | skipped | fires unless session is empirically doc-only too (file-extension based) |
| `trivial` | Small-blast-radius code change within the file-set bounds | full | full | full + **rationale-vs-diff fit** sub-check (Goal 3) | required | fires (file-set bounds + `**Trivial because:**` rationale enforced structurally) |
| `cleanup` | Branch hygiene, file moves, dead-code removal | structural-only (no broken refs) | requirement coverage | scope discipline; tolerate zero diff | skipped | fires |
| `designer-handoff` | Visual / token / design-asset handoff to a human designer | skipped | skipped | skipped | skipped | **skipped** |
| `cumulative-final` | Marker on the last chunk of a multi-chunk plan | marker only — the chunk's review is the one `/prawduct:critic cumulative` (commit first, then run it once; no separate `final`) | — | — | — | fires |

When chunk type is `designer-handoff` and the Critic is invoked anyway, output a single line: `Review skipped — Type: designer-handoff (visual handoff; review-by-human)` and exit clean — BEFORE `prawduct-hook critic-begin` (SKILL step 1), so no critic-active marker is left to block `clear`. No findings file is required; the stop-hook gate skip is the structural enforcement.

### Cumulative-mode diff scope and PR gate

`cumulative` is the only mode whose scope is *not* derived from working-tree state. Resolve the base branch with `prawduct-hook resolve-base` (a discrete step) — it honors a configured `base_branch:` in `project-state.yaml` (gitflow `develop`), falling back to `origin/main`/`main`. This is the **single source of truth** the PR/coverage gates use too, so reviewer and gates never diff different ranges — don't guess the base from prose (on a gitflow repo, a `main`-anchored base would diff the whole promotion range — a 2-commit feature branch reviewed as dozens of commits). Then compute `git merge-base <base> HEAD` and diff `<merge-base>...HEAD`. This deliberately spans every commit on the branch, so cross-chunk integration cracks surface even when every per-chunk review was clean.

`/prawduct:pr create` calls `prawduct-hook check-cumulative-critic` and refuses to open the PR if the gate fails. The gate requires: cumulative-mode findings file present, schema-valid, **covering current HEAD** (the recorded `commit_reviewed` is HEAD, or the only files changed since are docs `.md`), and free of unresolved BLOCKING findings. Coverage, not recency, is the test: a code change since the review fails the gate (re-run needed); a doc-only change does not. WARNING and NOTE are advisory at the PR gate — they do not block, matching the PR reviewer's severity contract.

**The chain (CRT-4J8W).** A code fix *after* the cumulative doesn't force a full bundle re-review. The gate equally accepts a `verify-resolutions` record that **extends** the cumulative: `extends_cumulative.commit_reviewed` = the cumulative's anchor X (resolvable), 0 BLOCKING findings, the record's own `commit_reviewed` covers HEAD (same ==HEAD-or-doc-only-since rule), and every non-`.md`, non-metadata file changed in `X..HEAD` is in the record's `files_reviewed` — fail closed on any gap. Soundness: cumulative@X vouches for the bundle; a clean delta review covering `X..HEAD` extends that vouching to HEAD. Sequencing matters: **commit the fix first, then run `/prawduct:critic verify-resolutions`** — a verify record anchored pre-commit can never cover HEAD (`chain-stale`). Chains may stack (a chain record propagates its original anchor); the scope-widening demotion bounds their length.

**Prep work before invoking cumulative.** A cumulative review takes ~4-10 minutes. Before invoking it, complete prep that doesn't depend on its findings — `/prawduct:learnings` for next topics, draft the PR description, audit the backlog, capture deferred reflections — so you integrate findings the moment it returns.

### Verify-resolutions scope and demotion

`verify-resolutions` is the only mode anchored to a *prior* review rather than the working tree. It exists to cut re-review latency after a round flags 1-2 BLOCKING findings and the builder fixes them — a full `chunk`/`final` re-run walks the whole diff again for a localized change.

**Scope computation.** Don't reimplement — call `prawduct-hook compute-verify-resolutions-scope` (the same canonical helper the stop-hook gate uses, so both compute identical scopes by construction). **stdout** = newline-separated file paths (the scope union: prior `files_reviewed` plus files changed since prior `commit_reviewed`, metadata-paths excluded); **stderr** = one reason line; **exit codes**: 0 = scope computed; 1 = cannot compute — fall back to `/prawduct:critic chunk` or `final`, record `mode_chosen_by: "fallback-no-prior-findings"`; 2 = scope widened past `len(delta) > 2 * len(prior) + 5` — fall back to `final`, record `mode_chosen_by: "fallback-scope-widened"`.

**Demotion criteria** (fall back to `chunk`/`final`):

| Trigger | Why it demotes |
|---|---|
| Prior findings file missing | Nothing to verify against. |
| Prior findings lack `commit_reviewed` | No anchor for the delta. |
| `commit_reviewed` does not resolve in current repo | Rebase, force-push, or never on this branch — anchor unreliable. |
| Prior findings have no BLOCKING/WARNING entries — *unless* the prior is chain-extendable (cumulative, or a chain record) AND something changed since `commit_reviewed` | Nothing actionable to re-check; with a chain-extendable prior + delta, the delta itself is the work — the pass extends the cumulative to HEAD. |
| `len(files_since_commit) > 2 * len(prior_files_reviewed) + 5` | Scope widened beyond the prior surface — a partial review would mislead. |

These are fail-closed: when the helper cannot anchor a delta, it refuses to compute one rather than silently shrinking the review.

**Chain anchor emission.** When the prior record is chain-extendable, the subcommand's `ok:` reason line ends with `extends-cumulative=<sha>` — the cumulative anchor this pass extends (propagated unchanged through stacked chain records). Record it in the findings file as `extends_cumulative: {"commit_reviewed": "<sha>"}` (SKILL step 7); the PR gate's chain acceptance depends on it. No suffix → no anchor to embed.

**Stop-hook gate behavior.** A `verify-resolutions` findings file clears the stop-hook Critic gate **only** when the current chunk diff is a subset of the findings' `files_reviewed`. Work added after the verify pass is out of scope; the gate refuses to clear and names the out-of-scope files.

**When NOT to use verify-resolutions.** Not as a chunk's first review (it's a re-review mode). Not across a rebase/force-push that rewrites `commit_reviewed` (the helper demotes, but you waste an invocation). Not after long drift unrelated to the original findings — the scope-widening threshold exists for exactly that.

## Per-Chunk Cycle

1. Builder completes a chunk's implementation and tests.
2. Critic reviews using the goal-based approach (see SKILL.md).
3. **If BLOCKING findings exist:** builder fixes; Critic re-reviews, specifically watching for **fix-by-fudging** — weakening a test to make it pass (**BLOCKING**), changing a spec to match wrong implementation (**BLOCKING**), a workaround instead of root cause (**WARNING**). Repeat until no blocking findings remain.
4. **Record findings** to `.prawduct/.critic-findings.json` (format: main SKILL.md). When no findings exist, record an empty findings array.
5. **If no BLOCKING findings:** chunk complete; proceed.

**Last chunk of a `Type: cumulative-final` plan — one review, not two.** Commit the chunk, then run `/prawduct:critic cumulative` ONCE: that single review serves as both the chunk's review and the PR-gate record. Don't run a separate `final` first — cumulative runs the same 7 goals plus cross-checks over `merge-base...HEAD`, a scope that already contains the chunk's diff, so a preceding `final` re-pays 4-10 minutes for assurance the cumulative re-derives. Mode inference implements the sequencing: with the last chunk's work still uncommitted, `/prawduct:critic` infers `final` (the right mid-chunk look); once committed and clean, it infers `cumulative` — the at-commit review. Post-cumulative fixes ride the verify-resolutions chain, not a second full pass.

## Final-Mode Cross-Checks

After the goal-based review in `final` mode, run two additional passes that `chunk` mode skips. **`final`/`cumulative` is the owner of both cross-checks** — the PR reviewer consumes their result from the cumulative record rather than re-running them (it re-scans only a chain-delta or a voided record; see `skills/pr/review-protocol.md`), so each runs once per PR:

### Learnings Cross-Check

Scan your findings against active learnings. If a change reintroduces a pattern `.prawduct/learnings.md` explicitly warns against, escalate severity — tolerating regression undoes the learning. Conversely, if learnings reference patterns the changed code handles correctly, no finding is needed.

### Backlog Reconciliation

Read `.prawduct/backlog.md`. For each open item, check whether this session's changes resolve it — directly or incidentally. For each resolved item, emit a **NOTE**: "Backlog item appears resolved: [item text]. Verify and archive it now, on this branch — `/prawduct:backlog update <id> status=shipped closed-by=<scope>` — so it ships in this PR." Do not change status yourself — the framework never infers status; the builder makes the explicit call.

**Backlog hygiene checks (C-B1–C-B4 — all NOTE-level, never BLOCKING)** — four soft signals (`/prawduct:backlog` is the fix path for each):
- **C-B1 — missing metadata:** a new backlog item in the diff with no metadata bar → NOTE the structured format.
- **C-B2 — no dedup evidence:** a new item whose `area:` already has ≥3 items → NOTE "check [the existing IDs] for overlap (`/prawduct:backlog dedup`)."
- **C-B3 — missing hygiene step:** the diff touches an area with open items but no chunk reviewed/updated them → NOTE "open items in area X — assess and update status."
- **C-B4 — dangling ID:** a build plan / change-log / chunk body references `PFX-XXXX` with no such item → NOTE (typo or not-yet-filed forward reference).

These flag; they never adjudicate whether an item "really" closed (the builder's call) and never block.

## Directional Change Review

When a significant architectural or design change spans multiple chunks, review holistically after all chunks complete:

- **Artifact consistency:** all affected artifacts updated? Implementation referencing stale artifact content → **BLOCKING**.
- **Regression check:** pre-existing tests modified or removed? → **BLOCKING** if weakened to pass.
- **Retrospective:** was the change reflected on? Missing → **WARNING**.

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

Every review cycle must produce a findings record — governance without an audit trail is documentation fiction. After each review, write `.prawduct/.critic-findings.json` (see main SKILL.md for format); when no findings exist, record an empty findings array.

### The Governance-Event Ledger

The findings file is single-slot — each review overwrites the last. The ledger (`.prawduct/.governance-ledger.jsonl`, gitignored) is the append-only history: after writing the findings file, run `prawduct-hook ledger-append --event review.critic --scope <plan-scope> [--chunk <id>] [--model <id>]` (SKILL step 7). The helper is the **single writer** — it validates the record and computes the envelope; agents never hand-author JSONL.

Each line is one event with an envelope/payload split:

```json
{"schema_version": 1, "event": "review.critic", "ts": "...Z",
 "duration_seconds": 180, "project": "my-product", "scope": "my-feature",
 "chunk": "02", "actor": {"role": "critic", "model": "opus"},
 "git": {"head": "<sha>", "base": "origin/develop"},
 "review": { ...the findings record verbatim... }}
```

The envelope is shared by every event kind; the kind-specific payload nests under a family-named key (`review` for `review.critic` and `review.pr`). Consumers key on the envelope and **skip unknown event kinds and fields** — later kinds join without schema change. `duration_seconds` and `actor.model` are nullable, never invented; `scope` is the build-plan feature key (passed explicitly; `active_build_plan` is only the fallback).

One gate consumes it today: `check-cumulative-critic` falls back to the newest qualifying `review.critic` event **from this session** (envelope `ts >= .session-start`; fail closed without the marker) when the latest findings file is the wrong kind for the PR gate — so a chunk review after the cumulative doesn't destroy the gate's evidence, while a days-old cumulative can't sneak through. The history also exists to be aggregated (reviewer efficiency per role, findings density per path, wall clock per feature). One line per event; if a long-lived repo ever needs pruning, truncate oldest lines — every line is self-contained.
