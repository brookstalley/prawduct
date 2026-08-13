# Tactical Efficiency Analysis — Consumer Review-Tax Evidence and Fix Selection

**Date:** 2026-08-13
**Author:** Fable session (analysis + planning only; build executes on Opus)
**Status:** Parent requirement document for `build-plan-tactical-efficiency.md`
**Relationship to #181 (GOV-6D4Q):** This is the *tactical* track the owner requested while the
big-picture work (the four-cycle program, the deletion-only pass) proceeds separately. Everything
here is least-work/highest-ROI; foundational findings are recorded in "Deferred captures" below
and routed to the backlog, not built here.

## Method and evidence base

Four consumer repos mined by independent read-only subagents (session state, governance ledgers,
review evidence, recent transcripts), plus a mechanism read of the framework code and protocols
(`plugin/lib/coverage_algebra.py`, `plugin/lib/gates.py`, `plugin/lib/coverage.py`,
`plugin/lib/critic_consolidate.py`, the Critic and PR skill files):

- **discodon** (+ its worktrees, notably `wt-discodon-kairo`) — fully governed, heavy multi-worktree
  traffic against `develop`. Primary evidence source.
- **samsung-frame-art-loader** — fully governed, single-checkout. Corroborating.
- **3tears** — *half-governed* (no persisted `.prawduct/` state; owner confirms not fully
  onboarded). Used as directional corroboration only, mainly for comment-archaeology patterns.

Windows: 2026-08-10 → 2026-08-13 (3–4 days per repo).

## Cost baseline (measured)

| Repo | Review dispatches | Reviewer wall-clock | Blocking share of findings |
|---|---|---|---|
| discodon (ledger, 4 days) | 92 (23 cumulative / 55 verify / 11 PR / 3 chunk) | 12.4 h | 40 / 516 = **7.8%** |
| wt-discodon-kairo (ledger, 3 days, overlaps above) | 72 rounds (~77 reviewer *agents*: cumulative = 3 agents) | 9.8 h | 25 / 462 = **5.4%** |
| samsung-frame-art-loader (4 days) | 76 | 9.6 h | (dominated by verify rounds: 44) |

Directional conclusions that hold in every governed repo:

- **>90% of findings gate nothing**, and non-blocking findings drive nearly all round count.
- **55 verify-resolutions runs produced 21 findings** (0.38/run at ~5.8 min/run) in discodon —
  most verify rounds verify nothing.
- Owner, unprompted, mid-session: *"Round 7 is a lot. Are these meaningful fixes or minutae and
  pedantry?"*

## Findings and selected fixes

### F1 — A base advance voids all coverage, even when the branch's own diff is byte-identical

**Evidence.** discodon merges `develop` ~20×/day. On `fix/testing-infra-sweep`, 2 of 3 cumulative
rounds (3 reviewer agents × ~13 min each) existed *only* because `develop` moved; round 9
re-raised 6 of round 7's findings verbatim. One in-flight cumulative was abandoned 86 s after
dispatch because develop moved during dispatch (3 reviewer agents discarded). Consumer's own
handoff: *"each `develop` merge forces a fresh cumulative … Two merges, two rounds"* — ~30 of 60
review minutes on a 6-fix branch were base tax. In both observed forced merges, **the only
conflicts were prawduct's own `.prawduct/` files** (change-log top-append, `project-state.yaml`
`test_count`) — non-judgeable paths.

**Mechanism.** `check_cumulative_critic` composes review facts tree-to-tree over
`merge-base(base, HEAD)` → `HEAD`. A base sync moves the span's start node; no fact starts there;
verdict `uncovered`; remedy = full cumulative. The existing free-edge allowance
(`coverage_algebra`) only covers intervals whose diff is entirely non-judgeable.

**Fix (build plan Chunk 01) — base-advance transfer.** When the gate would report `uncovered`,
attempt a computed **transfer verdict**: a prior covered span (base' → head', 0 unresolved
blocking) transfers to the required span (base → HEAD) iff

1. the judgeable changed-file sets of the two spans are identical, and
2. for every such file `f`: `blob(HEAD, f) == blob(head', f)` **and** `blob(base, f) == blob(base', f)`
   — i.e. the branch's own diff is *byte-identical* in the new context, and the base advance
   touched none of the branch's files, and
3. saved test evidence is current for the merged tree (`tests_are_current`) — the suite, not the
   transferred review, is what vouches for semantic interaction with the advanced context.

Computed, never stored (same philosophy as free edges). Printed loudly as
`satisfied (transferred across base advance …)`.

**Soundness vs. the 2026-07-29 ruling (COV-3M8Q / #367).** That ruling bans *content-equivalence*
(AST-normalized) relaxations because a comment-level edit (`prawduct:allow` pragma) can change
behavior. Transfer uses **byte equality** of the branch's own diff — any edit at all, comments
included, breaks condition 2 and denies transfer. Nothing is normalized; no unreviewed authored
content can ride a transfer. The one genuinely new exposure — the reviewed diff interacting with
advanced context in disjoint files — is exactly what condition 3 prices, and is an exposure the
current process also carries whenever a re-review skims an unchanged diff.

**Riders in the same chunk:** #565's ordering fix (`/prawduct:pr create` Step 1 syncs base
*before* Step 2 reviews), and an explicit PR-reviewer rule that a base-sync merge with no
judgeable authored content does not re-run the reviewer.

**ROI.** Removes the largest single structural tax (~half the cumulative rounds in the busiest
repo), and removes the incentive to race "develop-quiet windows."

### F2 — The coverage gate itself costs up to 120 s and times out

**Evidence.** 9 invocations in one kairo session: 29–120 s each, two hit the 2-minute Bash
ceiling (one `Exit code 143`), agent resorted to `timeout 200 …`. ≈10 min of one session spent
asking whether a review is needed. Latency tracks the 784 KB ledger/store it composes over —
discodon's is 7.3 MB.

**Fix (Chunk 02).** Cache the composed verdict keyed on (base tree, head tree, evidence-store
fingerprint); invalidate on store append. Also keeps Chunk 01's extra git lookups cheap, since
the gate is polled repeatedly per session.

### F3 — Accepted findings are re-litigated; three reviewers file the same defect three times

**Evidence.** kairo round 9 re-raised 6 findings from round 7, several already `--accept`ed as
disposition facts. Round 1 shipped three separate warnings (R-1/R-5/R-11) that were one defect
found by all three coordinator reviewers; `likely_duplicate_groups` reported `[]` (its candidate
rule requires overlapping file attributions and title-word similarity, which missed).

**Mechanism.** Dispositions are facts in the store, but `critic-begin` manifests carry no
disposition context, so a fresh cumulative's reviewers cannot know a finding was already accepted.
Dedup is advisory-only (correctly — fuzzy merges could drop real findings) but its grouping is too
weak to even *report* the triplicate.

**Fix (Chunk 03).** `critic-begin` adds a `prior_dispositions` block to the manifest (accepted /
filed findings joined from the store, with reasons); protocols instruct reviewers: do not re-raise
a dispositioned finding absent material change in the cited files — restate it as one line under a
`priors` acknowledgment instead. Strengthen `likely_duplicate_groups` matching; keep it advisory
but have consolidation present a group as ONE finding with N attributions.

### F4 — Comment/doc wording litigation is ~40% of finding volume; archaeology is rewarded

**Evidence.** 218 of 516 discodon findings (42%) touch comment/doc wording; 15 blocking. The
"~75s vs 71s" saga: one wall-time figure, 9 findings across 5 rounds on 3 branches — *"one
number, ten edits"*, and the tenth edit missed, buying the next round's finding. Reviewers
repeatedly wrote *"record prose, not a defect … no edit is required"* — and the next round's
reviewer re-found it. 70 of 462 kairo findings (15%) use retrospective-narration language;
review pressure teaches agents to *narrate* fixes into comments (3tears' `# Critic-caught:`
convention; a finding-ID `R-1` cited in a committed test docstring, dangling — a class that repo
hit three times; a test-count anecdote written out verbatim in four places including a test
docstring). Owner pushback is on record: *"The numbers were archaeology, not a relationship."*

**Mechanism.** `review-protocol.md` Goal 4 rates any comment/code contradiction WARNING
("Documentation drift"); the NOTE ceiling for record prose (`goals-1-3.md` Severity) covers
change-logs and plans but **not code comments**; no protocol constrains the *remedy*, so "update
the narration" is a valid recommendation and produces the next round's stale narration.

**Fix (Chunk 04 — protocol + policy prose).**
- Severity ceiling: comment/docstring/doc wording, counts, and phrasing are **NOTE** unless the
  prose is *load-bearing* — referenced by a test or a gate, or would mislead a maintainer into a
  concrete wrong action (that consequence must be named, per the existing WARNING bar).
- Remedy constraint: for stale prose the permitted recommendations are **delete the claim, make
  it relational, or pin it with a test** — never "reword/renarrate," and never "add a comment
  explaining the history."
- Provenance ban: review/finding IDs, chunk numbers, and review history never belong in shipped
  comments (extends the existing `building.md` ephemeral-id rule); a comment narrating history is
  a deletion finding.
- Builder-side (`building.md`): sharpen the comment policy — a comment states a present-tense
  constraint ("added because callers kept passing null" qualifies); history lives in commits and
  the change-log, which are the one home for it.

### F5 — Verify-resolutions loops are mostly self-inflicted at a known decision point

**Evidence.** Five consecutive 0/0/0 verify passes on one branch (1,270 s), each followed by the
agent electing to fix that pass's *demoted observations*, each fix buying the next round. Agent
post-mortem: *"Each round surfaced new demoted observations, and I elected to fix them, which
bought the next round … The gap is that neither blocks, and both arrive after I've decided."*
Samsung: 8 verify rounds on one bundle; a PR reviewer re-ran 520 s over a 2-commit delta that was
a CI workflow comment plus `.prawduct` records. Also observed: fixes committed *after* a clean
pass ("safe to /clear" then two docstring numbers went unreviewed), and pre-fixing during a
running review creating tree mismatch findings.

**Mechanism.** The countermeasures exist (`cost-of-commit`, the fix-churn NOTE, verify-mode
blocking-only rating, consolidate's batch directive) but the **PR gate's `blocking:` stderr — the
text agents act on — still prescribes only "Fix them, then run verify-resolutions"** with no
batching instruction, and verify-pass observations arrive with no price on them. (The
owner-floated `--im-really-done` flag was analyzed in-session by the consumer agent and rejected:
sincerity flags can't catch an error that isn't insincerity. A refuse-to-dispatch guard is
unsound: the tempting fixes are in judgeable files, so refusing the verify would strand the gate
uncovered.)

**Fix (Chunk 05 — point-of-action text, all mechanized surfaces).**
- `blocking_remedy_lines`: prescribe the golden path — fix **all** named findings in the working
  tree, do **not** commit between fixes, run **one** `verify-resolutions` (dirty-tree verify is
  sound), then commit the verified tree verbatim.
- Verify-mode observation reporting (`goals-1-3.md`): every observation is delivered pre-priced —
  "ACCEPT is the default disposition; fixing any of these re-opens the gate and costs a round;
  batch survivors into an already-planned commit."
- `/prawduct:pr` Update flow: define "substantive" — a delta that is only non-judgeable paths
  and/or a base sync does not re-run the PR reviewer.

### F6 — Prawduct's own record files are the merge-conflict surface

**Evidence.** On both forced develop merges in kairo, 100% of conflicts were
`.prawduct/change-log.md` (top-append: both sides add at the top) and `project-state.yaml`
(`test_count`), plus an `active_build_plan` judgment call. Each conflict costs manual resolution
plus reconcile commits (4 `chore: reconcile test_count` commits on one branch).

**Fix (Chunk 07, small).** Recommend `merge=union` for `.prawduct/change-log.md` via
`.gitattributes`. Union-merge is safe for an append-only entry log and eliminates the dominant
conflict class. Delivery surface is a **post-sync advisory probe** (fires in every session
briefing — owner feedback 2026-08-13: doctor is very rarely run, so a doctor-only check would
almost never fire); doctor lists it too, as the secondary surface. Advisory-only either way —
the architecture write-set norm keeps the plugin from writing `.gitattributes` itself.
`test_count` churn is #633's scope — linked, not built here.

### F7 — `active_build_plan` is branch state stored in a product-level scalar

**Evidence.** Both forced develop merges in kairo required a judgment call on the
`active_build_plan` line of `project-state.yaml`; #283 (BLD-7W2J, 2026-06-10) records the class:
two concurrent branches each set the one pointer, guaranteeing a same-line conflict on develop,
after which one plan is invisible to every pointer-resolved governance surface until repointed.
Owner, 2026-08-13: *"the active build plan is a property of the branch, not the product."* The
current RETAIN-on-develop convention even has to instruct sessions to ignore an advisory because
the pointer keeps naming a merged-but-unreleased plan.

**Mechanism.** One parity-tested resolver pair (`core.resolve_build_plan_path` + the
`bin/prawduct-hook` inline mirror) serves every reader (stop hook, briefing,
`infer-critic-mode`, `record_lint`, `verify-chunk-refs`, archive/backfill) — so the resolution
rule can change in one place.

**Why not a literal git branch decoration.** `branch.<name>.description`, per-branch config, and
notes refs are per-clone and non-propagating: a fresh clone, a second collaborator, or CI loses
them silently, and the gates then fail *open* (no plan → no Critic trigger). The only
branch-scoped state git shares reliably is content committed on the branch.

**Fix (Chunk 06) — the plan declares its branch.** Build plans gain optional frontmatter
`branch: <name>`; the resolver prefers the live (non-archived) plan whose `branch:` matches
`git branch --show-current`, falling back to the `active_build_plan` scalar, then the
conventional default — so existing repos behave unchanged until a plan opts in. Two live plans
claiming one branch is a loud error, never a silent pick. Merge semantics come free: each plan
file is its own file (no shared-line conflicts); archiving moves the plan out of the live
directory, ending its claim; a plan merged to develop carries a `branch:` that no longer matches,
so it reads live-but-inactive — which is exactly what RETAIN wants, with no advisory to ignore.
Closes #283's in-flight half (the release-side half was already solved by scope enumeration).

## Deferred captures (foundational — backlog, not this pass)

1. **Subagent briefing weight.** `.prawduct/.subagent-briefing.md` is ~203 KB (~51k tokens) and
   is read by every dispatched reviewer — ~77 dispatches in 3 days ≈ 4M tokens of prefill before
   any diff is read. Needs role-scoped sharding/capping — a design question adjacent to #181's
   surface-reduction, not a quick fix. → filed as a new backlog item.
2. **Single-slot test evidence.** `.test-evidence.json` is one record per worktree; branch/session
   switches force ~7-min full-suite re-runs of trees whose judgeable content is unchanged
   (one `/clear` invalidated evidence for four branches). A per-tree evidence cache (keep last N
   records keyed by `evidence_tree`) fixes it; touches the evidence schema → deliberate design,
   not tactical. → filed as a new backlog item.
3. **`test_count` as a tracked field** — churn + conflicts; #633 already covers derivation; this
   analysis adds evidence there.
4. **Duplicate same-timestamp verify dispatches** observed in discodon's ledger (a double-spend).
   #171 (concurrent-dispatch guard) is shipped; the consumer was likely on an older plugin.
   Verify plugin-version before filing anything — noted here only.
5. **The framework's own narrative house style** (long historical docstrings) is the exemplar
   consumers imitate; pruning it is exactly #181's deletion-pass territory. Noted for that pass.
6. **Backlog-reconciliation runs on every cumulative** (34% of discodon reviews carried
   reconciliation findings). Mostly a symptom of F1's repeated cumulatives; F1's fix removes most
   of it. Re-measure after this pass before building anything.

## What was deliberately not proposed

- **Any relaxation of what counts as judgeable** — ruled out 2026-07-29 (#367); Chunk 01's
  transfer is byte-identity across contexts, not content equivalence within one.
- **A `--im-really-done` sincerity flag** and **a verify-dispatch refusal when the delta is
  "only fixes"** — both analyzed and rejected (see F5).
- **Sharding the subagent briefing** and **per-tree test evidence** — right ideas, wrong pass
  (design decisions with schema/ecosystem lock-in).
