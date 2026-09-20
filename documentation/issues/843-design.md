# Issue #843 — Governance: Nothing Detects a Finished Branch That Was Never PR'd: Design

`status: draft · stage: design · area: governance · added: 2026-09-20 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/843`

Related: #712 (the inverse — merged work whose backlog item is still open — already designed and
the nearest structural precedent, cited throughout below); #640 (a closed item whose own fix is
half-built on one of the branches this issue's own survey lists — a live cost of the exact gap this
item closes, not something this design re-opens); #624 (`ephemeral-worktrees` sync-refusal area,
adjacent but distinct — that item is about a worktree's own refusal messages, not branch discovery).

**No separate requirements doc exists for #843, and none is needed.** The issue's own body already
carries the problem statement, a live measurement (seven branches, ~22,700 insertions, the
`fix/767-test-status-clause` cost example), a stated detection algorithm ("cheap and mechanical"),
an explicit non-blocking ruling, and three named open design questions. That is what a requirements
pass would otherwise produce; this document resolves the three open questions, corrects one stale
citation, and turns the result into a concrete build. (Same convention #712's design doc states for
itself, and the pattern several `kind:bug` items in this backlog already follow — `167-design.md`,
`669-design.md`, `712-design.md`, `755-design.md` and others carry no separate requirements
companion.)

## Grounding facts

Re-verified against the current tree (`develop`, 2026-09-20):

- **The issue's "`core.md`" citation does not resolve to a file of that name.** No `core.md` exists
  anywhere in this repo (`find . -iname core.md` — empty). The quoted sentence — *"Archiving an
  unmerged branch as 'intent captured in the backlog' must verify the IMPLEMENTATION landed…
  Nine branches were tagged in one pass…"* — lives at `.prawduct/learnings.md:637`. A citation
  correction to carry into the build chunk's commit message, not a reason to re-derive the lesson.
- **The "all boxes ticked" signal the issue's algorithm calls for already exists as a function,
  built for a different caller.** `buildplan_refs._has_unfinished_chunk(plan_path)`
  (`plugin/lib/buildplan_refs.py:703-740`) returns `True` while any `- [ ]` item remains under a
  plan's `## Status` section (parsed by `_iter_status_section_items`, `:147-153`) and — load-bearing
  for this design — returns `True` (unfinished) for a plan with **no** Status items at all, so an
  unparseable plan never misreads as finished. Its docstring states plainly that it now "decides
  which plan GOVERNS" (`core.resolve_branch_claim`'s tie-break) and lists its other two consumers;
  this design adds a third rather than writing a second, differently-tuned "is it finished" test —
  exactly the "fourth classifier" anti-pattern this codebase's own comments repeatedly warn against
  (`plugin/lib/coverage.py:1072-1085`, on `check-change-log-entry`'s own such near-miss).
- **The "which plan governs this branch" signal also already exists, one level down from where
  #843 needs it.** `plan_index.branch_claiming_plans(artifacts_dir)` (`plugin/lib/plan_index.py:
  224-246`) returns `(path, branch)` for every live plan declaring `branch:` in its frontmatter,
  archive-pruned, and deliberately returns **every** claim rather than resolving one — because,
  per its own docstring, "several plans may claim one branch." `core.resolve_branch_claim`
  (`plugin/lib/core.py:625-714`) consumes it to pick the *governing* plan for the checked-out
  branch; #843 needs the opposite direction (all branches, each against all its claiming plans,
  none pre-resolved to a winner) and reuses the same raw index rather than the resolver, because a
  branch with several claiming plans is "finished" only when **all** of them are, not when a
  precedence rule happens to pick a finished one over an open sibling.
- **A branch with no claiming plan is not a hole in the algorithm — it is `branch_claiming_plans`
  returning nothing for it, by construction.** No plan means no entry in the index means the branch
  never enters the candidate set. This resolves the issue's own open question ("does it fire on
  branches with no build plan") without new code: "finished" has no reading without a plan's Status
  boxes, so silence is the correct answer, not a special case to write.
- **A near-identical worktree-exclusion probe already ships, and its shape is directly reusable.**
  `adhoc_delegate_probes.py` fires exactly once per worktree holding evidence of unintegrated work,
  is "self-resolving both ways" (merge or delete either ends it), and states the rule #843's own
  body asks for verbatim in its own docstring: *"The worktree boundary is respected: this probe
  stats, it never reads"* (`:21-25`). Its `_worktree_records(root)` (`:63-101`) parses
  `git worktree list --porcelain` into `{worktree, HEAD, branch, …}` dicts, degrading to `[]` with a
  stderr NOTE (not silent) on any git failure that is not "this isn't a repo" (`:76-86`). This is
  the exact primitive #843's "must not nag about a branch another worktree is actively holding"
  requirement needs, and it is a **private** function today (`_worktree_records`) with one caller —
  duplicating its 38 lines into a second probe module would be the same anti-pattern flagged above,
  one module over.
- **A `gh pr list` call against the branch under discussion already exists, already justified, and
  already answers a narrower version of #843's own question.** `cmd_stop` (`plugin/bin/
  prawduct-hook:2308`) runs `gh pr list --head <branch> --json number --limit 1` at session end
  (`:2900-2905`) — but only for the **current** branch, only when there are changes, and it asks
  "does an **open** PR exist" (the default `gh pr list` state), which is a different question from
  #843's "has a PR **ever** existed" (`--state all`). The surrounding comment is explicit about why
  this call is deliberately rare: *"a network call (300-800ms typical, 15s timeout worst case) that
  used to fire on EVERY turn-end… doing this cheaply matters"* (`:2881-2886`), and a second guard
  (`STH-3W7F`, `:2890-2892`) skips it entirely while a Stop is already deferred. Any design that adds
  a second, unbounded `gh pr list` caller inherits the same cost obligation this comment already
  states — it does not get to re-learn it.
- **`.prawduct/project-state.yaml` already enumerates every network egress site in the framework by
  name, and the `cmd_stop` call above is one of exactly three.** `egress_boundary`
  (`.prawduct/project-state.yaml:229`) names `lib/backlog/transport.py` (two callers, both gated on
  an opt-in), `lib/release_verification.py` (operator/CI-invoked), and *"a `gh pr list` in `cmd_stop`
  in `bin/prawduct-hook`, which DOES run on the Stop hook path"* — named individually because it is
  the one call that runs unconditionally rather than behind an opt-in scalar. A fourth, independent
  `gh pr list` call site would need a fourth bullet; reusing the third site's call (Decision 4)
  keeps the declared count at three and only needs that one bullet's prose widened to name its
  second caller, the same incremental amendment the `lib/backlog/transport.py` bullet already
  records for its own second caller ("so it is reachable with `backlog_service_repo` unset, which is
  why the site is no longer describable as just the backlog backend").
- **`GhTransport` (`plugin/lib/backlog/transport.py`) is the wrong reuse target, not the obvious
  right one.** It is repo-agnostic in its method signatures (`owner`, `repo` are always explicit
  parameters — confirmed against `list_merged_pull_requests(owner, repo, *, since)` in #712's
  design), but every existing call site constructs it against `backlog_service_repo` — a scalar that
  is **unset** in a markdown-backend repo. Routing #843's check through it would make the advisory
  silently unavailable in exactly the backend that has no other safety net for this gap (the Issues
  backend at least has `/prawduct:backlog`'s own item-tracking; a markdown-backend repo's branches
  are otherwise invisible to any governance surface). `cmd_stop`'s bare `subprocess.run(["gh", …])`
  already proves the unconditional, backend-agnostic call is both possible and already accepted —
  this design extends that call, not the backlog-scoped one.
- **The advisory infrastructure this design targets already runs a same-shaped probe roster at
  session-start sync, unconditionally and for free in the steady state.**
  `probe_families.register_all()` (`plugin/lib/probe_families.py:33-67`) registers thirteen probe
  families, every one of them local-only (git/filesystem) today — `advisory_store.py`'s own
  `_SCAN_SKIP_DIRS` comment states the invariant plainly: "cheap read-only scans only (spec §7.1:
  probes run on every sync)" (`:82-84`). This design is the first probe to touch the network at all,
  which is exactly why Decision 4 below keeps that cost conditional rather than accepting it as a
  new per-sync tax for every governed repo.
- **Day-granularity, not hour-granularity, is this codebase's only staleness-threshold precedent.**
  `advisory_store.RESOLVED_TTL_DAYS = 30` (`:66`) and `cachequery.py:520`'s `older_than_days` are the
  two existing constants of this shape; no hour-granularity constant exists anywhere in `plugin/lib`.
  The issue's own illustrative phrase ("a branch finished an hour ago is not a problem") names a
  lower bound, not a target value.

## Decisions

Three open questions the issue names explicitly ("Design questions, not settled here") plus the
egress question Grounding facts raises. Each resolves by extending an existing primitive rather than
adding a parallel one — the same posture #712's design states for itself ("this design does not
invent GraphQL as a new call style — it finishes a call style the sibling spec already committed to").

**1. Detection composes three existing reads; it adds no new "is this finished" logic.** A branch is
a **candidate** iff: (a) `plan_index.branch_claiming_plans` names at least one live plan claiming
it, AND (b) every one of that branch's claiming plans is finished per
`buildplan_refs._has_unfinished_chunk() is False`, AND (c) the branch's own commit-graph state
(Decision 2/3) clears the staleness and worktree checks. A branch failing (a) is silent by
construction (Grounding facts); a branch failing (b) — one open claimant among several — is
correctly excluded, matching `resolve_branch_claim`'s own reasoning that an open claimant is the
one governance is about.

**2. Staleness threshold: 24 hours since the branch's own tip commit, hardcoded — not a new
preferences row.** Read via one `git for-each-ref refs/heads/ --format='%(refname:short)|
%(objectname)|%(committerdate:iso-strict)'` call (a single process, no per-branch spawn), giving
name, tip SHA and last-commit instant together. Twenty-four hours sits above "an hour ago is not a
problem" (the issue's own floor) and well below the `fix/767-test-status-clause` cost example (two
days unmerged, two red CI runs) — the threshold exists to suppress same-session noise, not to give
real staleness a grace period. **Not a new configurable row**, for two reasons: it keeps this item's
blast radius to one hardcoded constant rather than a new piece of declared vocabulary, and #820's own
live triage thread (issue #820, 2026-09-17/18 comments) already flags this repo's `Delegate
verification`/`Inner-loop verification` rows as sitting against an explicit owner ruling that
"prawduct does not know this project's test regime and will not invent a vocabulary for it" — a
caution this item has no standing to relitigate for an unrelated setting. If a real repo's usage
shows 24h wrong, that is a follow-on item with its own evidence, not a guess made here.

**3. Worktree exclusion: skip a branch checked out by any *other* worktree; do not exempt the
current worktree's own branch.** Reuse the promoted `worktree_records` (Decision 4's module move)
to build the set of branches held elsewhere, and drop those from the candidate set — the literal ask
("must not nag about a branch another worktree is actively holding"). The branch checked out in
*this* worktree is not given a pass: the `fix/767-test-status-clause` cost example is precisely a
finished branch its own session had moved away from, and excluding "wherever I am standing" would
blind the probe to the exact case that motivated it.

**4. Network check: extend `cmd_stop`'s existing egress site through a shared `gitstate` helper,
gated behind a non-empty local candidate set, capped, never a fourth site.** Two extractions, both
into `plugin/lib/gitstate.py` (already the shared home for worktree/branch primitives — Grounding
facts):

   - `worktree_records(project_dir) -> list[dict]`, moved verbatim from
     `adhoc_delegate_probes._worktree_records` (same porcelain parse, same not-a-repo-vs-real-failure
     distinction on stderr); `adhoc_delegate_probes.py` is refactored to import and call it, so the
     parser has one home instead of two.
   - `pr_exists_for_branch(project_dir, branch, *, state="open") -> bool | None`, extracted from
     `cmd_stop`'s inline block (`:2902-2912`) with its exact subprocess shape, JSON-decode-on-failure
     tolerance, and 15s timeout preserved; returns `None` (not `False`) on any git/gh failure — a
     query that could not run is never read as "no PR", matching the fail-closed-on-uncertainty
     posture this codebase applies everywhere else a probe's own failure could be mistaken for its
     negative answer. `cmd_stop` is rewired to call this helper with `state="open"` (unchanged
     behavior, same query, same 15s timeout) rather than keep its own inline copy.

   The new probe calls the same helper with `state="all"` — the one line of actual behavior
   difference this item needs — **only when the free local-only filter (Decisions 1-3) already
   produced at least one candidate**, preserving every existing steady-state repo's zero-network-cost
   sync. Calls are capped at `_MAX_GH_CHECKS = 8` per sync (oldest-finished-first ordering), each on
   its own subprocess exactly as `cmd_stop`'s does today — no batching, because a bulk `gh pr list
   --state all --json headRefName --limit N` trades one network call for a size-bounded window that
   can silently miss an old branch's PR, which is a worse failure mode than a few small, individually
   correct calls for what the issue's own survey shows is a short list (seven branches, this repo,
   worst case observed). A sync that hits the cap reports how many candidates went unchecked on
   stderr — never silently truncated — and re-runs pick up where staleness ordering left off.

**5. Surface: the session-start advisory roster (`probe_families`/`advisory_store`), not `/prawduct:
doctor` and not Janitor.** `doctor` is on-demand only, so it would have missed the two days
`fix/767-test-status-clause` sat unmerged unless someone happened to run it. Janitor is a periodic,
human-invoked deep audit ("Version Control Hygiene" already names "dead branches" as a theme,
confirming the concern is in-scope there too, but as a survey item investigated when Janitor runs,
not a standing per-session check). The advisory roster is the one surface already built for
"visible, dismissible, self-resolving, checked on every sync" — precisely the owner's own framing
("a visible, dismissible signal, not a refusal") and structurally identical to
`adhoc_delegate_probes`'s existing worktree-abandonment advisory. It does not preclude Janitor's
"dead branches" theme from also looking here by eye; the two are not exclusive.

## What ships

1. `plugin/lib/gitstate.py`: `list_local_branches` (new — one `git for-each-ref` call, name/tip-sha/
   commit-instant per local branch), `worktree_records` (moved from `adhoc_delegate_probes.py`,
   Decision 4), `pr_exists_for_branch` (extracted from `cmd_stop`, Decision 4).
2. `plugin/lib/adhoc_delegate_probes.py`: `_worktree_records` calls removed in favor of
   `gitstate.worktree_records`; behavior unchanged (parity-tested).
3. `plugin/bin/prawduct-hook`: `cmd_stop`'s inline `gh pr list` block (`:2894-2912`) replaced with a
   call to `gitstate.pr_exists_for_branch(project_dir, current_branch, state="open")`; same query,
   same timeout, same JSON handling, now shared rather than sole.
4. New module `plugin/lib/unlanded_branch_probes.py`: `_finished_unheld_candidates` (Decisions 1-3,
   local-only), `probe_unlanded_finished_branch` (adds Decision 4's bounded network step and builds
   `AdvisoryCandidate`s), `register`. Mirrors `adhoc_delegate_probes.py`'s shape throughout —
   `FEATURE = "branch-landing"`, probe type `finished-branch-unlanded`, `PROBE_VERSION = 1`.
5. `plugin/lib/probe_families.py`: `register_all()` gains the new import and call, fourteenth in the
   roster.
6. `.prawduct/project-state.yaml`: `egress_boundary`'s `cmd_stop` bullet widened to name its second
   caller — the declared count of egress sites stays three (Decision 4).

Each `AdvisoryCandidate` (mirroring `adhoc_delegate_probes.py:201-234`'s exact field shape):
`evidence` names the branch, its claiming plan(s), and how long it has sat since its last commit;
`trigger_summary` states the plan is fully ticked and no PR has ever existed for it; `owner_action`
asks whether the work is still wanted (ship it via `/prawduct:pr`, or say why not — the same two-call
framing #712's Decision 6 and `adhoc_delegate_probes` both already use for "this is the operator's
call, not something automated on their behalf"); `recommended_action` is `git log --oneline
<base>..<branch>` (inspect what is actually on it — the same non-mutating, always-safe default
`adhoc_delegate_probes` picks, `:230`) rather than any command that would create, push, or delete
anything.

## Acceptance criteria — how each is met

- **Detects a branch whose claiming build plan(s) are all ticked and which has never had a
  PR** — Decisions 1-4, `probe_unlanded_finished_branch`.
- **Never a blocking gate** — by construction: the probe only ever produces `AdvisoryCandidate`
  values through the existing advisory roster; no exit code, no gate, and no new code path checks it
  anywhere the way `check-cumulative-critic` or `check-releasability` are checked. Matches the
  owner's explicit 2026-09-19 ruling verbatim.
- **Respects a staleness threshold** — Decision 2; a branch finished within 24h produces no
  candidate.
- **Silent on a branch with no claiming plan** — true by construction of reusing
  `branch_claiming_plans` rather than inventing a plan-less "finished" reading (Grounding facts,
  Decision 1).
- **Silent on a branch another worktree is actively holding** — Decision 3, reusing the promoted
  `gitstate.worktree_records`.
- **Self-resolving** — inherited for free from the existing advisory sync-diff mechanism every other
  probe already uses: once a PR exists for the branch, or the branch is deleted, the candidate stops
  being produced and the stored advisory reconciles to resolved on the next sync, with no
  branch-specific resolution logic to write.
- **Bounded, opt-in network cost** — Decision 4: zero `gh` calls in the steady state (no local
  candidates), capped per-sync when candidates exist, and the cap's overflow is reported rather than
  silently dropped.

## Scope-out (this item)

- **Remote-only branches with no local ref.** The issue's own detection recipe is stated as "for
  each local branch"; a purely-remote branch is a different signal (and a different cost model —
  it would require listing remote refs across however many clones exist) and is not this item's to
  solve.
- **A configurable staleness-threshold preferences row.** Ships hardcoded at 24h (Decision 2);
  configurability is a follow-on only if a real repo's usage shows the default wrong, with that
  repo's evidence attached — not guessed here.
- **Overflow handling beyond the per-sync `gh` check cap** (`_MAX_GH_CHECKS = 8`). Bounded and
  reported (Decision 4); a persistent-cursor or priority-carryover scheme is a real optimization but
  is deferred the same way #712's Decision "incremental cursor" note defers its own analogous
  optimization — not assumed needed until a repo's real branch count shows the cap binding.
- **Auto-opening a PR, auto-deleting a branch, or auto-archiving the plan.** Advisory only, per the
  owner's ruling; the action stays the operator's, mirroring #712's Decision 6 ("nothing acts
  automatically") for the same reason — a write path here would be exactly the kind of gate the
  owner's ruling rejects.
- **The seven branches the issue's own survey names**, and the two it already verified as safe to
  delete. Their disposition is this session's operational cleanup, not something this design
  performs or blocks on.
- **Reconciling #640's own half-shipped state** (flagged in the issue's own follow-up comment as a
  concrete cost of this gap). That is #640's item to reopen or re-verify, not folded into this
  design.

## Evidence / references

- `plugin/lib/buildplan_refs.py:703-740` (`_has_unfinished_chunk`) and `:147-153`
  (`_iter_status_section_items`) — the finished/unfinished predicate this design reuses verbatim
  (Decision 1).
- `plugin/lib/plan_index.py:224-246` (`branch_claiming_plans`) and `plugin/lib/core.py:625-714`
  (`resolve_branch_claim`) — the claiming-plan index this design reuses, and the resolver it
  deliberately does NOT reuse (Grounding facts, Decision 1).
- `plugin/lib/adhoc_delegate_probes.py:1-43` (module docstring, worktree-boundary rule stated
  verbatim), `:63-101` (`_worktree_records`), `:156-235`
  (`probe_unintegrated_delegate_worktree`, the `AdvisoryCandidate` field shape this design mirrors),
  `:238-245` (`register`) — the structural precedent for the whole new probe module.
- `plugin/bin/prawduct-hook:2308` (`cmd_stop`), `:2879-2912` (the existing `gh pr list` call, its
  cost comment, and the `STH-3W7F` defer guard) — the egress site Decision 4 extends rather than
  duplicates.
- `.prawduct/project-state.yaml:229` (`egress_boundary`) — the three declared egress sites; the
  bullet this design's Decision 4 amends rather than adds a fourth to.
- `plugin/lib/advisory_store.py:66` (`RESOLVED_TTL_DAYS`), `:82-84` (`_SCAN_SKIP_DIRS` comment,
  "cheap read-only scans only"), `:93-157` (`AdvisoryCandidate`), `:253-271` (`register_probe`,
  `run_all_probes`) — the roster contract this design's probe conforms to, and the day-granularity
  precedent Decision 2 follows.
- `plugin/lib/probe_families.py:33-67` (`register_all`) — the composition root this design's
  probe is added to, fourteenth in the list.
- `.prawduct/learnings.md:637` — the correctly-located citation for the "Archiving an unmerged
  branch…" lesson the issue attributes to a non-existent `core.md` (Grounding facts).
- Issue #712's design document (`documentation/issues/712-design.md`) — the nearest structural
  precedent throughout: "no separate requirements doc" framing, the `GhTransport` reuse-vs-avoid
  reasoning this document arrives at oppositely (and explains why), and Decision 6's "nothing acts
  automatically" posture, restated here as this item's own equivalent scope-out line.
- Issue #843's own body (2026-09-19) — the seven-branch survey, the `fix/767-test-status-clause`
  cost example, the owner's non-blocking ruling, and the three open design questions this document
  resolves; and its 2026-09-19 follow-up comment — the #640 cost example, cited in Scope-out rather
  than re-opened here.
