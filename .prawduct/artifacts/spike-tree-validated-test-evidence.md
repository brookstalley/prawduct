# Spike: Tree-Validated Test Evidence Freshness

**Status:** design spike (pre-build) · **Date:** 2026-07-14 · **Author:** framework session
**Advances:** kernel-v3-evidence-design.md §4 (deferred "Test evidence on the store"), COV-3R9K suggested-fix-1 (previously rejected — see §3), the governance-metadata false-re-run bug (`backlog.md:13`), and the restart false-stale surfaced in the v3.0.2 session.
**Requirements Confidence:** High on the problem and the failure history; **Medium** on the recommended design — the risk is a *false-fresh* semantic shift (§7), and two prior patches wrongly believed they'd solved the adjacent problem, so this spike gates on a validation matrix (§9) before any schema lands.

---

## 1. Problem (observable)

Test-evidence freshness (`test-status`, `lib/gates.py:74` `_test_evidence_is_current`) is **session-timestamp-anchored**: fresh iff `record.timestamp >= .session-start` and `failed == 0`. That produces three distinct frictions, all with the same root cause (freshness keys on *when the run happened*, not *what tree it ran against*):

1. **False-stale on restart.** Run a review, quit, restart, change nothing, go to PR → `test-status` reads `stale` (new session, old timestamp) even though the tree is identical. The cumulative-Critic **gate** passes (it's tree-anchored — `gates.py:818`), but the PR/Critic **reviewer** keys off `test-status` and raises a WARNING (`skills/pr/review-protocol.md:46`, `skills/critic/review-protocol.md:41`). A false-stale nag that trains needless re-runs.
2. **Metadata/doc edits force a full re-run.** Editing `.prawduct/*.yaml` or a `.md` in a later session re-stales evidence though no test-relevant file changed (the governance-metadata bug, `backlog.md:13`).
3. **Chronic per-session re-run.** Every code-touching session re-runs the full suite to re-stamp, even when the tested content is unchanged from a prior session's run.

The acute case — a declared `test_command` forcing a double-run — was fixed in **v3.0.2** (ingest on-ramps). This spike targets the chronic root cause underneath it.

## 2. Why this is *not* already solved by v3

v3.0.0 tree-anchored **review** evidence (`session_review_verdict`, `gates.py:490` — "Replaces the mtime-vs-`.session-start` freshness check"). **Test** evidence is the one remaining mtime-vs-session-start holdout — `kernel-v3-evidence-design.md §4` deferred it to "a later constituent plan." This spike is that plan.

## 3. Scar tissue — what was tried and rejected, and exactly why

Two prior mechanisms used a hash/SHA as an **expiry** signal and were removed for **chronic false-stales**:

| Mechanism | Lifespan | Why it failed (false *positive* = false stale) |
|---|---|---|
| **Content-hash "fingerprint"** (`compute_test_fingerprint`: HEAD SHA + sha256 of every dirty file) | intro v1.3.4 (`c132373`) → removed v1.3.8 (`7fb5e08`) | (a) HEAD SHA baked in → **any commit, even metadata-only, invalidated evidence**; (b) hashed **churny session/framework metadata** (`.critic-findings.json`, `backlog.md`, `build-plan.md`) that changes *between Verify and Critic* → chronic spurious stales across 8+ sessions; (c) the v1.3.5/v1.3.6 metadata-filter **patch failed** and put the hook itself in the skip-set (inverse false-fresh); (d) fragile `git status --porcelain` parsing. |
| **`git_sha`** (HEAD-at-record decoration) | → retired v2.1.8 (`1d8a7d1`, TST-4K2P) | Stamped HEAD but tested the **working tree**; the natural edit→run→record→commit flow stamped the *pre-commit* SHA, lagging HEAD after commit → reviewers eyeballed a false "stale." |

**These rejections are explicit and standing.** `backlog.md:1194` (COV-3R9K): *"content-/tree-hash freshness … deliberately rejected … freshness stays session-scoped."* `kernel-v3-evidence-design.md:319` (R10): *"Content-hash freshness stays dead: nothing … hashes file contents to decide staleness; trees compose, they don't expire."* And the standing rule in `coverage_algebra.py:66`: *"paths classify, contents don't (do-not-reintroduce: content-hash freshness)."*

## 4. The distinction that makes a new attempt viable

Every rejected mechanism used a hash **as an expiry signal that makes evidence go stale**. All their failures are false-*stale* failures. The v3 insight is that trees are safe as a **validity/composition key** (they compose, they don't expire) — which is why tree-anchoring *worked* for reviews.

So the design must be a **validity clause, not an expiry signal** — and it must classify **paths**, never **content** (git's tree-diff tells us *which paths changed*; `is_judgeable_path` classifies them; no file bytes are ever hashed by us).

## 5. Recommended design — an additive tree-validity clause

Do **not** replace the timestamp check. **Add** a second "still-valid" path to it:

> `test-status` is **current** iff **(session-fresh, as today)** **OR** **(the judgeable-scoped working tree is byte-identical to the tree the recorded run ran against)**, with `failed == 0` either way.

Because the clause is a disjunction that only ever moves evidence **stale → fresh**, it is **structurally incapable of producing a false stale** — the exact failure class that killed the fingerprint. It can only *remove* false-stales.

Mechanics (all primitives already exist in `develop`):

1. At `record`, capture the working-tree SHA via `evidence.capture_tree()` (`lib/evidence.py:367`) — temp index, never touches the session (R1). Store `tree` (and `head_tree`) in `.test-evidence.json`.
2. At `test-status`, capture the current tree, then `evidence.tree_diff(recorded_tree, current_tree)` (`lib/evidence.py:413`). Filter with `coverage_algebra.judgeable_files` (`lib/coverage_algebra.py:59`). **Empty judgeable diff ⇒ tree-valid ⇒ current.**

Each historical failure mode maps to a primitive that neutralizes it:

| Historical failure | Neutralized by |
|---|---|
| Commit (even metadata-only) invalidated evidence | Tree SHA is commit-position-independent — `capture_tree.clean = (tree == HEAD^{tree})`; a **verbatim commit preserves the tree SHA** |
| Churny metadata between Verify and Critic caused chronic false-stales | `is_judgeable_path` filters `.prawduct/`, `.claude/`, session files out of the staleness diff |
| Old metadata-filter patch skipped the hook itself (false-fresh) | Judgeability is the **vetted** path predicate: `bin/prawduct-hook` *is* judgeable → editing it correctly invalidates |
| Fragile porcelain parsing | `git diff --name-only <treeA> <treeB>` — git-native, already trusted by the review gates |
| `git_sha` lagged HEAD post-commit | Tree captures the actual working tree (incl. uncommitted edits); no HEAD reference participates |

**What it fixes:** restart-no-change → tree-valid → current (§1.1 ✓); metadata/doc-only edit → judgeable diff empty → current (§1.2 ✓, closes `backlog.md:13`); genuine code/test edit → judgeable diff non-empty → correctly stale → re-run (correct, not friction).

## 6. Schema change (lock-in — enumerated per planning.md)

Additive fields on `.prawduct/.test-evidence.json`: `evidence_tree` (str, the captured working-tree SHA) and `head_tree` (str|null). **Questions the field must answer** (its only consumers): *"Is the current judgeable tree identical to the one this run covered?"* and *"Was that tree a clean commit of HEAD?"* Nothing time- or commit-position-derived is stored (that's what failed). **Back-compat:** a record without `evidence_tree` (pre-upgrade, or `--from-counts` where no tree is meaningful) falls through to **today's timestamp-only** behavior — the clause is purely additive, so old records behave exactly as now.

## 7. The one real decision — env-drift tradeoff (user's call)

The timestamp model *incidentally* forces a re-run every session, which catches **environment drift** (a dependency upgraded without a tracked-file change; a flaky test; external state) even when code is unchanged. The tree-validity clause trades that away: same tree across sessions ⇒ "current" ⇒ no re-run ⇒ an env change that a re-run would catch is missed. This is:
- **Bounded:** lockfiles (`uv.lock`, etc.) are tracked, judgeable files, so dependency changes recorded in them *do* invalidate. The gap is env changes with **no** file footprint, plus flakes — both of which the current model also fails to catch on its own (it doesn't compare results, only timing).
- **Consistent** with how v3 review evidence already vouches across sessions/worktrees for an unchanged tree.
- **Escapable:** a builder who suspects env drift can always `record` fresh.

Recommendation: accept the tradeoff (the incidental per-session re-run is an expensive, undesigned safety net), but this is the decision to confirm — not to make silently.

## 8. Surface cascade

- `lib/gates.py` `_test_evidence_is_current` / `tests_are_current` — the disjunction.
- `bin/prawduct-hook` `cmd_test_evidence` — capture + store the tree; `test-status` reader.
- **Review protocols** (`skills/critic/review-protocol.md:41`, `skills/pr/review-protocol.md:46`) — already key off the `test-status` **exit code**, so they inherit the fix with **no prose change** (GOV-7T2M made the exit code the sole signal — this spike leans on that).
- `methodology/building.md:79` Verify bullet; `templates/` evidence schema doc if any.
- Tests: `tests/test_plugin_runtime.py` (TestTestEvidenceRecord / freshness), plus the §9 matrix.

## 9. Validation-first exit criterion (mandatory before schema lands)

Two prior patches *believed* they'd killed the false-stales and hadn't. So the spike's build gate is a **scenario matrix** proving the clause only ever relaxes, with no false-stale and characterized false-fresh:

| Scenario | Expected |
|---|---|
| Record → restart → no change → `test-status` | **current** (fixes §1.1) |
| Record → edit `.prawduct/*.yaml` only | **current** (fixes §1.2) |
| Record → edit a non-protected `.md` only | **current** |
| Record → edit a `src/*` or `tests/*` file | **stale** |
| Record → `git commit` verbatim (no content change) | **current** (tree preserved) |
| Record → edit `uv.lock` | **stale** (dependency footprint) |
| Record → edit `bin/prawduct-hook` | **stale** (hook is judgeable) |
| Record → add an untracked test file | **stale**; add an untracked note under `incoming-bugs/` | **current** |

## 10. Non-goals

- **Not** migrating test evidence onto the shared `evidence.jsonl` store — this is a local additive field, not a store move (that's a larger, separate step).
- **Not** catching env/dependency/flake/external-state drift (pre-existing gap in the timestamp model; §7).
- **Not** touching review-evidence composition (already tree-anchored).
- **Not** reintroducing content hashing — paths classify, contents don't.

## 11. Open questions / assumptions

- `[ASSUMPTION: the additive "OR tree-valid" framing was never specifically evaluated in the prior rejections | MED impact | the history shows the *replace-timestamp* direction was rejected for false-stale modes; user with full context can confirm/veto]`
- Cost: `test-status` would run `capture_tree` (a `git add -A` + `write-tree`) each call. The review gates already pay this per invocation, so it's a known, accepted cost — but confirm on the largest target repo.
- Should the clause require the recorded tree to be an **ancestor-reachable** tree (composition), or is **exact judgeable-scope identity** sufficient? Exact identity is simpler and sufficient for the three frictions; composition is a later refinement if cross-tree validity is ever wanted.
