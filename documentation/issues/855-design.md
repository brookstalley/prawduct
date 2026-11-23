# Issue #855 — Nothing Detects a Build Plan That Was Never Persisted: Design

`status: draft · stage: design · area: gates · added: 2026-09-22 · reworked: 2026-11-22 ·
issue: https://github.com/brookstalley/prawduct/issues/855`

**Reworked 2026-11-22 as an advisory.** The owner ruled: "#855 is reworked as an advisory, not a
blocking Stop gate, to fit the 2026-09-19 tax ruling" (`.prawduct/owner-rulings.md`, 2026-11-22
entry, ask 6). The earlier design was a blocking Stop gate. It is deleted here, not kept beside
this one. The note under "Superseded" says why it was dropped.

**The ruling this design has to fit.** On 2026-09-19 the owner turned down a freshness-gate change
with these words: "We default to adding tax everywhere and it's become a problem … 1 helps, 2
hinders both us and our consumers to fix a rare edge case." The ruling is recorded where it landed:
`.prawduct/artifacts/build-plan-audit-guidance.md:55` ("No new gate"), and the #843 design's
Decision 5. On #843, the same day, the owner asked for "a visible, dismissible signal, not a
refusal" (`documentation/issues/843-design.md:212`; `plugin/lib/stranded_branch_probes.py:10-11`).
The standing norm behind both: "proportionality ratchets both ways" (`nonfunctional-requirements.md`
§ Direction). It says a new control names its expected yield and emits that yield where it can be
seen. #855 is a rare failure. The issue reports one incident: a 7-chunk plan lost and re-pasted
from scrollback. So the ruling's shape applies directly. Every governed repo would pay a blocking
check at every session end to catch a rare loss. An advisory costs nothing to anyone the
predicate does not fire for.

Related: #661 (#855 was split from it); #843 (the advisory precedent for "nothing detects X");
#1050 (the work-unit binding, which replaced the resolver the earlier design was built on).

## Grounding facts

Re-verified against `develop` at `8b1847e2` on 2026-11-22. Much of what the 2026-09-22 design
cited no longer exists.

- **The resolver and the adjacent notice the old design reused are gone.**
  `core.resolve_build_plan_path` was removed when #1050 shipped. `plugin/CHANGELOG.md:374` says the
  shims "are removed, not kept for a release", and `tests/test_build_plan_resolution.py:590` pins
  that they are absent. "Which plan governs this checkout" is now `work_unit.resolve(project_dir)`
  (`plugin/lib/work_unit.py:200`). It returns a `Binding` whose `state` is `bound`, `unbound` or
  `broken`, and a legacy-window case (pointer or conventional path) still counts as `bound`.
  `buildplan_refs.unticked_committed_chunk_notice` was also retired, and its successor is
  `plan_status.built_not_done_notice` (`plugin/CHANGELOG.md:250`;
  `plugin/lib/plan_status.py:1783`). That successor returns `None` on any checkout that is not
  `bound` (`:1798-1800`). So the line between the two controls is still exact, but it moved: from
  "a plan file exists" to `binding.state == "bound"`. Built-not-done speaks only on a bound
  checkout, and this advisory never speaks on one.
- **The commit-subject primitives moved to `plan_status`, and they have one home there.**
  `_CHUNK_COMMIT_RE` and `_COMMIT_SCOPE_RE` (`plugin/lib/plan_status.py:1424-1431`), `_named_ids`
  (`:1444`, the unscoped reading), and `_log_commits` (`:1471`). `_log_commits` is "the one reader
  every chunk-to-commit answer here takes its commits from". One `git log --name-only` call gives
  each commit's subject and the paths it touched. The comment above `_CHUNK_COMMIT_RE` calls
  `_subject_chunks` "the rules' one home". The detector therefore lives in `plan_status` and
  exports its answer (learnings `hook-surface`: "Export the ANSWER, not the walker").
- **`build_scope_to_plan_map(..., include_archived=True)` still exists, and it is not allowed on
  this path.** It is at `plugin/lib/plan_index.py:652`. Its walker's docstring
  (`iter_scoped_plan_candidates`, `:382-422`) says the archive is pruned at directory level because
  "the walk runs at every session start and every session end". It also says to pass
  `include_archived=True` "only from a cold path". #1050's NF1 says the same for every hot path,
  session start included: "no network, and no cost that grows with the archive"
  (`documentation/issues/1050-requirements.md:306-307`). An advisory probe runs at every session
  start, so it is on a hot path. Measured on this repo (194 scopes, 186 archived files), the
  archive-inclusive map took 46 ms (best of 5) against 13.5 ms for the live map. That cost grows
  with every plan the repo ever finishes. The old design's clause D is replaced (Decision 2,
  clauses D1-D3).
- **The advisory channel already exists, has one composition root, and runs on every
  SessionStart source.** Probes register through `advisory_store.register_probe` from a module's
  `register()`. They are listed once, in `plugin/lib/probe_families.py:register_all`. The roster
  runs inside `cmd_clear` (`plugin/bin/prawduct-hook:2134-2141`). That block is orientation, kind
  (3) in `cmd_clear`'s docstring, so it also runs on a continuation. The hook matchers
  (`plugin/hooks/hooks.json`) send `startup|clear` to `clear --session-start`, and
  `resume|compact|fork` to `clear --session-start --brief-only`. Both forms reach the probe
  roster. A plan lost to a compaction therefore triggers the advisory in the same conversation,
  right after the compact.
- **How an advisory reaches its readers.** `AdvisoryCandidate` (`plugin/lib/advisory_store.py:95-
  139`) carries `evidence`, which hashes to a stable id; `trigger_summary`; `owner_action`, a
  person's decision in prose with no command; `recommended_action`, exactly one command; and
  `priority`. When a probe stops producing an advisory, the next sync marks it `resolved`.
  `advisory dismiss` is sticky per clone (`plugin/skills/advisory/SKILL.md`). A probe returns `None`
  when it could not look, so an open advisory is not resolved by a check that never ran
  (`advisory_store.run_probes`, `:343-393`; #917). `tests/test_advisory_actionability.py` reads
  every construction site and enforces the two-audience rules. It allows only `prawduct-hook` and
  `git` as the first word of a `recommended_action` (`:59`, `:304-325`).
- **The nearest existing probe is in the same family.** `work_unit_probes.probe_plan_unbound_legacy`
  (`plugin/lib/work_unit_probes.py`, feature `work-unit`) is the binding's own advisory. It asks
  "this checkout's plan governs through a route being retired". #855 asks the step before that:
  "this branch's chunk work has no plan at all". Both questions are about the work unit, so both
  advisories belong to that one module.
- **A one-command remedy exists.** `prawduct-hook plan new [<scope>]` (`plugin/bin/prawduct-
  hook:8372`; `plugin/lib/plan_mint.py:175`) writes `build-plan-<scope>.md` claiming the checked-out
  branch, and writes its change-fragment stub. Once it runs, the checkout is `bound`, so the
  advisory resolves on the next sync. It refuses on the base branch itself (`branch-is-base`),
  a harness scratch branch, a branch another live plan already claims, or a scope that a live or archived plan already holds. The scope check walks the
  archive, which is fine there because `plan new` is a cold path someone chose to run.
- **Transcript-based detection is still ruled out.** The constraint the old design cited still
  applies. `prawduct-hook` reads and writes only the governed repo's `.prawduct/`.
  `transcript_path` would be the first read outside that boundary. See Scope-out.
- **The `active_build_plan` dangling-pointer notice is a different channel.** It is a `⚠` line
  that `briefing.render_briefing` prints (`plugin/lib/briefing.py:1015-1050`) every session while
  a set pointer names no file on an unbound checkout. It cannot be dismissed, it is not in the
  advisory store, and it fires on a configuration fault (a scalar naming a missing path) whose fix
  is to unset or bind. It never fires on #855's case, where the pointer is unset
  (`active_build_plan: null` is the shipped default). For whether the two should share one owner,
  see Decision 6.

## Decisions

**1. Surface: the session-start advisory roster, as a second probe in `work_unit_probes`.**
Type `plan-not-persisted`, feature `work-unit`, registered by that module's existing `register()`.
`probe_families` needs no change, because it already calls `register_work_unit()`. There is no
`gates.json` entry, no `_WAIVER_KEY_BY_GATE` key and nothing in `cmd_stop`. Choosing this channel
over the other two:

- The Stop hook is a refusal (the tax ruling).
- A briefing line cannot be dismissed. A deliberately planless branch would show the same `⚠`
  in every session, and the ruling objects to exactly that cost.

The roster is the one surface built for "visible, dismissible, self-resolving, checked on every
sync" (#843 Decision 5).

**2. The detector is `plan_status.unpersisted_plan_evidence(project_dir)`.** It returns an
`UnpersistedPlan` (branch, chunk ids, the first subject carrying each id, and a suggested scope),
or `None` for "nothing to report", or a cause string for "could not look". Each clause suppresses
one named false positive. They run cheapest first, so the common case stops before any new git
call:

```
branch = gitstate.current_branch(root)
if branch is None or gitstate.ephemeral_kind_of(root, branch) is not None:
    return None                                   # clause S: detached, or a harness scratch tree
if branch in plan_mint.integration_branches(root):
    return None                                   # clause I: a branch that is never a unit's
binding = work_unit.resolve(root, branch=branch)
if binding.state != "unbound":
    return None                                   # clause A: a plan governs (claim or legacy window),
                                                  #   or the binding is broken (the briefing reports it)
base, _ = coverage.repo_base_branch(root)         # an unbound checkout's base IS the repo's
if base is None:
    return "no base branch resolves"              # could not look
commits = _log_commits(root, f"{base}..HEAD")     # ONE git call: subjects + touched paths
if isinstance(commits, str):
    return commits                                # could not look
ids = _named_ids(c.subject for c in commits)      # clause B is implied: no commits, no ids
if len(ids) < MIN_UNPLANNED_CHUNK_IDS:            # = 2
    return None                                   # clause C
scopes = {conventional scope of each id-carrying subject}
if scopes & build_scope_to_plan_map(artifacts).keys():          # LIVE only
    return None                                   # clause D1
if any touched path under .prawduct/artifacts/ is a file now with has_build_plan_shape:
    return None                                   # clause D2
if any (artifacts / "archive" / f"build-plan-{s}.md").is_file() for s in scopes:
    return None                                   # clause D3
return UnpersistedPlan(...)
```

- **S and I** keep the probe silent where a plan would be wrong or impossible. A scratch tree's
  coordinator governs it (`work_unit.resolve`, step 1). `integration_branches` is the `main` family
  plus the repo's own integration branch, which are "branches that are never a unit's"
  (`plan_mint.py:131-134`). `plan new` refuses to claim the base (`branch-is-base`), so on the base
  the probe would recommend a command that cannot run.
- **A** is the dividing line with `built_not_done_notice` (Grounding facts). A `broken` binding
  stays silent, because whether a plan claims the branch is unknown, and the briefing already
  prints the breakage.
- **C** keeps the probe from nagging planless small work (acceptance criterion 2), the same bound
  the old design used. Two or more distinct chunk ids on one branch with no plan is what a plan
  executed chunk by chunk and never written down looks like. One `(Chunk 1)` commit could be
  casual wording. The limitation is stated: a real one-chunk plan that was never written is
  invisible to this check.
- **D1** handles a plan that exists and binds nothing to this branch. For example, a plan claims
  `feature/x`, and this checkout is an undeclared side branch whose commits carry `x`. The scope
  map is the live one, with the archive pruned. That walk is already paid on every session-start
  path.
- **D2** replaces the old clause D's archive walk with a fact about the branch. If any commit in
  `base..HEAD` added, edited, or archived a file that is a build plan now, the plan was persisted
  (learnings `hook-surface`: "Observable beats stored"). Only files the range touched are read,
  so the cost grows with the branch, not the archive. A plan that was written and then archived on
  this branch is covered because the archive move is in the range. Renames show the new path under
  git's default rename detection, and the shape test (`buildplan_refs.has_build_plan_shape`,
  `:167`) needs positive evidence, so a design note in `artifacts/` does not count as a plan.
- **D3** is one `stat` per distinct commit scope. It covers the case D2 cannot see: a plan
  archived on the base after this branch was cut, with the branch then rebased. Archiving happens
  at release, so that case is rare. The check is keyed on the name `plan new` writes
  (`build-plan-<scope>.md`), not on frontmatter. A plan archived under some other name falls
  through to a firing, which a dismissal answers (Decision 5). This is the deliberate trade for
  never walking the archive.
- **The bias, carried over from the old design and now cheaper.** When scopes disagree (a commit
  scope that drifted from the frontmatter `scope:`; `_carries_scope`'s comment calls scope tags
  "a convention, and drift"), D1 to D3 can fail to suppress. The probe then fires on a plan that
  exists. They never suppress when nothing exists. As a gate, a false fire cost a blocked session
  end. As an advisory it costs one dismissal.

**3. Lines, shaped like `stranded-branch` and `plan-unbound-legacy`.**

- `evidence`: `(f"branch {branch}",)`, the branch alone. Following `finished-branch-unlanded`'s "the
  id must survive new plans and the clock", the id stays stable while more chunk commits land.
  One dismissal then covers the branch, and a new `Chunk 03` commit does not bring it back.
- `trigger_summary`: `f"branch {branch} carries commits for {n} chunks ({ids}) and no build plan
  covers them — not live, not committed on this branch, not archived; a plan that lives only in a
  conversation is lost when that conversation ends"`. The first carrying subject per id goes in
  the `advisory show` detail, capped at `EVIDENCE_CAP`, so the person can check the claim without
  re-deriving it.
- `owner_action`: "Approve writing down the plan this branch is being built against, now, while
  this session or your terminal scrollback still holds it. If the branch is deliberately
  planless, dismiss this with that reason." This contains no command.
- `recommended_action`: `prawduct-hook plan new <scope>`. `<scope>` is the conventional scope most
  of the chunk-carrying subjects share. With no such scope the argument is left out, and `plan new`
  suggests one from the branch and prints it. The value is shell-quoted, the same treatment
  `stranded_branch_probes` gives a branch name. The agent then fills the minted plan's chunks from
  its context. The probe never writes the plan's contents. The old design's ruling still holds:
  only a session with the work in context can say what the plan was.
- `priority`: `warn`, the same as `stranded-branch`, because the failure is lost work. It is not
  `urgent`, because nothing is irreversible yet.

**4. How it clears.** The probe stops producing the advisory, and the next sync marks it
`resolved`, when any of these happens:

- the recommended `plan new` runs (clause A);
- a plan whose `scope:` the commits carry is written live (D1) or committed on the branch (D2);
- that plan is archived on the branch (D2) or on the base under its minted name (D3);
- the branch merges or is reset onto its base, so no ids are left ahead of it.

Each path gets a test that applies the action to a fixture and watches the advisory resolve
(learnings `tests`: test an advisory's effect, not its object). A sync that could not look
(Decision 2's cause strings) holds the open advisory where it is instead of resolving it.

**5. Dismissal.** `advisory dismiss <id> --reason "..."` is per clone and sticky, keyed on the
branch through the evidence hash. This is the answer for a deliberately planless branch, and for
D3's archived-under-another-name residual. Undismiss restores it if the probe still fires. There is
no committed "this branch is planless" fact. The tax ruling argues against adding new declared
vocabulary for a rare case, and #843 made the same choice.

**6. One owner with the pointer notice? No. They are one family, not one function.** The
dangling-pointer line and this probe answer different questions:

- The pointer line: a scalar names a missing file, so the binding route is misconfigured.
- This probe: chunk work exists and no plan does, so the work itself is at risk.

They have different remedies (unset the pointer or bind; versus mint and fill) and different
channels (an undismissible briefing line versus a dismissible advisory). The pointer is also part
of the legacy window #1050 is retiring, and building a new control on a retiring route would tie
the two together. When both fire, a set pointer at a missing file on a branch with unplanned
chunk work, both lines are true and their remedies agree. The owner #855 adds is
`work_unit_probes`, the binding's advisory module, so both plan-binding advisories have one home.
Moving the pointer line into the advisory store would make it dismissible. That is a separate
question, not part of this item.

## Cost

The probe runs at every SessionStart, on all five sources, and also inside `advisory show`.
Measured on this repo on 2026-11-22 with `develop` at `8b1847e2` (best of 5, warm cache):

| Path | What it reads | Cost |
|---|---|---|
| Detached, scratch tree (S) | the branch name, which the briefing already reads | no new git call |
| Integration branch (I) | `plan_mint.default_base`: one `project-state.yaml` read when `base_branch:` is set, which onboarding writes; otherwise `repo_base_branch`'s ref lookups | a file read, or the 16.2 ms lookup the later clauses need anyway (computed once) |
| Bound or broken checkout (A) | `work_unit.resolve`: one walk of live plans, archive pruned | the same walk the briefing and the base resolver already make each session; the live scope map, a comparable walk, measured 13.5 ms |
| Unbound feature branch, fewer than 2 ids (C) | + `repo_base_branch` (16.2 ms) + one `git log base..HEAD --name-only` | 34.5 ms for a 59-commit range, 79.3 ms for 940 commits. It grows with the branch, not with history or the archive |
| About to fire (D1-D3) | + live scope map (13.5 ms) + reads of plan-shaped paths the range touched (2.8-11.5 ms) + one `stat` per commit scope | under 105 ms at the 940-commit extreme. It is paid only while the condition holds, dismissed or not |

There are no network calls and no archive walk on any path. The archive-inclusive map the old
design used measured 46.2 ms here, which is why D2 and D3 replace it. The precedent is that
`stranded_branch_probes` already makes local git calls on every session start. The yield is
observable: each firing is a stored advisory with an id, so `advisory list --state=all` counts
firings, resolutions and dismissals. A probe that only ever ends dismissed is a retirement
candidate under the proportionality norm.

## What the advisory gives up versus the blocking gate

A session can end with the plan still unpersisted. The advisory speaks at the **next**
SessionStart, not before the current session ends:

- After a compaction it fires in the same conversation, while the compact summary may still hold
  the plan.
- After a `/clear` or a fresh start it fires when the conversation that held the plan is gone, so
  recovery depends on the operator's scrollback.
- It can be dismissed and then ignored.

The gate would have refused the session end while the plan was still in context. That was its one
real advantage, and the ruling trades it for zero cost to every session the predicate never fires
on, and for one dismissal instead of a blocked session end on a false fire. Acceptance criterion 1
("detected before the session ends") is therefore **not met as written**. See the Owner fork.

## Acceptance criteria: how each is met

- **"A build plan that exists only in context is detected before the session ends."** It is
  detected at the next SessionStart of any source, including a compact, once two or more chunk ids
  are committed. It is not detected before session end (see above). It is never detected for a
  plan lost before any chunk was committed (Scope-out).
- **"A repo doing planless small work is not nagged."** Clause A (a resolvable plan silences it),
  clause C (one incidental chunk tag is not a plan), clause I (integration branches), and a
  sticky dismissal for deliberate planless chunk work.
- **"The trigger is named and its false-positive shape stated."** Decision 2 names the trigger and
  the suppression clauses, and states the residual false fires: scope drift, a plan archived under
  a non-minted name, and a plan that lives only uncommitted in a sibling non-scratch worktree. Each
  is answered by one dismissal.

## Owner fork

**Acceptance criterion 1 needs rewording to match the ruling.** The ruling chose an advisory, and
an advisory cannot detect "before the session ends". Recommendation: reword it to *"a build plan
that exists only in context is surfaced at the next session start, including after a compaction,
once its chunks are committed"*. Also edit the issue body's "Expected" paragraph, which still
describes the blocking gate. This document cannot make either edit (owner/issue text).

## What ships

One chunk. The detector and the probe are small and are tested together through the probe.

1. `plugin/lib/plan_status.py`: `MIN_UNPLANNED_CHUNK_IDS = 2`, an `UnpersistedPlan` dataclass, and
   `unpersisted_plan_evidence(project_dir) -> UnpersistedPlan | str | None` (Decision 2). Its
   docstring states the stated ceiling and the cost table's claim (no archive walk, one git call).
2. `plugin/lib/work_unit_probes.py`: `probe_plan_not_persisted`, which renders Decision 3's lines
   from the evidence, returns `None` with a stderr `NOTE` on a cause string (the #917 convention),
   and is registered in `register()`. The module docstring gains the second probe.
3. Tests (below).
4. A change fragment for the work unit. Consumer note: a new `warn` advisory, which speaks only on
   an unplanned branch carrying two or more chunk-tagged commits, and can be dismissed.

Not shipped: any `gates.json`, `cmd_stop`, `_WAIVER_KEY_BY_GATE` or briefing change.

## Test plan

These go in `tests/test_work_unit_probes.py`, using its existing `_repo`/`_plan` git fixtures, and
port its case structure (learnings `tests`: copy the precedent's test file first). Every case is
written and seen **red** before the code exists. Each suppression clause is then mutation-checked:
delete that clause, watch its test go red, and restore it by inverting that exact edit.

1. **Fires**: an unbound `feat/work` branch with `feat(lost): Chunk 01 …` and `feat(lost): Chunk
   02 …` commits and no plan. One candidate: type `plan-not-persisted`, evidence exactly `("branch
   feat/work",)`, priority `warn`, and a summary naming both ids.
2. **Silent and its control, per clause.** Each is the fire fixture plus one change, so the only
   difference is the clause:
   - S: a detached HEAD, and an `agent-*` scratch worktree.
   - I: the same commits on the integration branch.
   - A: a plan claiming the branch; the legacy conventional `build-plan.md`; and a `broken`
     binding (two claimants).
   - C: one chunk id; and zero commits ahead.
   - D1: a live plan with `scope: lost` claiming another branch.
   - D2: a commit in range adding a plan-shaped file; that file then `git mv`'d to `archive/`; and
     a non-plan design note in range, which must **not** suppress.
   - D3: `archive/build-plan-lost.md` present but outside the range; and the same plan archived
     under another name, which must still fire (the stated residual).
3. **Could not look**: a configured `base_branch:` that resolves no ref returns `None` and prints
   a `NOTE`. An already-active advisory stays active through that sync and is not resolved.
4. **Effect of the remedy**: sync, take `recommended_action` from the store, run it through
   `plugin/bin/prawduct-hook`, then sync again. The advisory is `resolved` and the binding is
   `bound`. An unapplied sibling repo stays `active` as the control. The second case is a subject
   with no conventional scope, giving `plan new` with no argument and a branch-suggested scope.
5. **Clearing without the command**: commit a hand-written plan with `scope: lost`. It resolves.
6. **Dismissal is sticky across new chunk commits**: dismiss, commit `Chunk 03`, sync. The
   advisory is still dismissed and the id is unchanged.
7. **Cost asserts the costly operation, not a proxy.** Monkeypatch `plan_index._archive_roots`
   to raise, and run the firing and every D-clause case: none of them touch it. Wrap
   `plan_status._log_commits` with a counter: zero calls for S, I and A, and exactly one for C and
   for the firing case.
8. **Roster and lint**: `probe_families.register_all()` registers `("work-unit",
   "plan-not-persisted")`. `test_advisory_actionability` already picks up the new construction
   site, so assert it is counted among the sites it read. Its `recommended_action` must be
   statically readable or join the counted-skip set deliberately.
9. **Real-corpus check**: run `_named_ids` over a captured sample of this repo's real chunk-carrying
   subjects, as a fixture file. Clause C's id count must match a hand count, so the threshold is
   checked against the subjects products actually write, not only fixtures written to match it.

Verification ceiling for the builder: the two touched test files plus
`tests/test_advisory_actionability.py` and `tests/test_advisory_store.py`. The full suite runs
at the PR boundary.

## Superseded: blocking gate

The 2026-09-22 design wired this detector as a blocking Stop-hook gate, `plan-not-persisted`,
with a `.gates-waived` key, a `gates.json` row and a `cmd_stop` blocker. The argument was that
only the Stop hook can act "before the session ends". The owner dropped it on 2026-11-22 to fit
the 2026-09-19 tax ruling, for three reasons:

- It would have charged every session end in every governed repo for a failure reported once.
- A false fire would have cost a blocked session end instead of a dismissal.
- Its precision clause walked the plan archive on the hot path, which NF1 and `plan_index`'s own
  contract forbid.

The backlog-ROI wave of 2026-11-18 had already excluded #855 as "blocking tax against the
2026-09-19 ruling" (`.prawduct/artifacts/build-plan-backlog-roi-2026-11-18.md:62`).

## Scope-out

- **Transcript-based detection of a plan drafted but never committed at all.** This would be the
  complete answer. It needs a read outside the governed repo's `.prawduct/` (Grounding facts), and
  that is an owner-level decision to widen the invariant, not part of this item.
- **A one-chunk plan that was never persisted.** Clause C excludes it, for the reason given there.
- **Auto-writing the plan's contents.** The probe recommends minting an empty plan claiming the
  branch. Only the session holding the work can fill it.
- **A configurable threshold, or a committed "planless branch" fact.** Neither is added. The
  constant and the per-clone dismissal are enough, and the tax ruling argues against new
  vocabulary for a rare case.
- **Moving the `active_build_plan` pointer line into the advisory store** (Decision 6). This is a
  separate question.
