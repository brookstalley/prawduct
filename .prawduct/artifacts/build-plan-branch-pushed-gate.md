---
artifact: build-plan
version: 2
scope: branch-pushed-gate
branch: fix/branch-pushed-gate
depends_on:
  - artifact: api-contract
  - artifact: architecture
governed_by:
  # Seeded with `prawduct-hook jurisdiction "check-branch-pushed fail-closed gate …"
  # --artifacts-only`, then curated: the ranker's hits included three release plans and
  # two sibling build plans (term overlap on `gate`/`upstream`, no Direction section
  # that binds). `nonfunctional-requirements` is added by hand — the ranker missed it,
  # and its proportionality norm is the one this plan has to answer for.
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract, on a documented and consistent scheme → LOAD-BEARING,
        and it is what partitions the gate's answers: 0/1 for a readable push state, 3 for
        an unreadable one, derived from the standing third-outcome rule rather than chosen.
        See § The Exit Codes This Gate Takes."
      - "additive-first evolution: flag names, exit-code meanings and `--json` keys are never
        repurposed → conforms; a new subcommand is added, no existing meaning moves, and the
        gate emits no `--json` payload because it has no programmatic consumer."
      - "whole-surface semver; the internal CLI subcommand surface carries no per-subcommand
        version → conforms; `check-branch-pushed` is internal/unstable, not a § Operations
        published surface, so it owes no stability tier."
      - "errors are attributed, never raised as stack traces across the boundary → conforms;
        every failure path prints a named reason and returns an int."
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → LOAD-BEARING. This gate produces a
        verdict a merge depends on, so every state it cannot read is non-zero. There is no
        fail-soft branch anywhere in it."
      - "local-first: governance coordination is process-spawn + files + the git object
        database, no network; no gate verdict crosses the network → LOAD-BEARING, and it
        is what bounds the gate's question. See § The Question This Gate Answers."
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state
        → conforms; the gate is read-only and writes nothing at all."
      - "goals and verification bind; prescribed method is advice → conforms, and exercised
        once: #248 prescribes `git rev-parse origin/<branch>`, and the build takes the
        branch's configured upstream instead (§ The Question This Gate Answers)."
      - "an independent reviewer never mutates the session it reviews → inapplicable because
        this plan touches no review machinery and no marker path."
      - "prawduct is written in Python and must never be specific to Python → inapplicable
        because the gate reads git state and classifies no product file by language."
      - "prawduct guides and reviews; it never implements → inapplicable because the change
        is to prawduct's own runtime, not to a governed product's code."
      - "every fact has one home; every other mention is a reference to it → LOAD-BEARING twice.
        The question the gate answers has ONE home (the probe's docstring) and the gate cites it
        rather than restating it. And Create Step 5's prose comparison is REPLACED by the gate
        rather than joined by it — two carriers of one mechanical check is the shape this norm
        forbids. The two merge-side checks are not a second instance: they have different
        subjects, and the file says which."
  - artifact: nonfunctional-requirements
    dispositions:
      - "adding a control names the yield it expects AND emits that yield observably →
        BOUNDED EXCEPTION on the emission arm, on the recorded doctor-#13 precedent, with
        the expected yield named now so the future query has something to answer. See
        § The Yield This Gate Cannot Emit."
      - "review wall-clock is P0; cost = unit-cost × run-count → conforms, and it set the
        plan shape: one chunk, one cumulative review that serves as both the chunk review
        and the PR gate. Splitting the lib from its wiring would buy a second round and
        review neither half completely."
      - "proportionality ratchets both ways — a control that never produces a finding is
        removed by default → conforms; the yield statement below is what a future removal
        argument gets to be tested against."
      - "state-file growth is an advisory, never a hard block → inapplicable because this
        plan writes no state file."
  - artifact: project-preferences
    dispositions:
      - "internal `lib/` functions return dicts with status/reason rather than raising →
        conforms; the probe returns a state dict and the gate turns it into an exit code."
      - "stdlib-only governance runtime, Python 3.10+ → conforms; no new imports beyond
        `subprocess`, already imported in the module the probe lands in."
partition: serial, single chunk — the probe, the gate, the CLI wiring and the two skill call
  sites are one contract with four surfaces; a delegate could not prove any one of them
  without the others, and splitting them buys review rounds rather than parallelism
last_validated: 2026-09-12
---

## Requirements Confidence

**Level:** High

**Why:** The defect is not inferred — it fired in production on 2026-09-12 (PR #803 merged one
commit short) in exactly the repro #248 recorded on 2026-07-09, and the recovery cost a second PR
against a protected branch. The item carries a designed fix, six written tests on tag
`archive/gate-friction-batch`, and three port caveats that this session re-verified against the
current tree. The one open design question — which ref is the authority — is settled below against
a ratified norm rather than left to preference.

**Open assumptions / unknowns:** none outstanding. The two judgment calls are recorded as
`[DECISION: …]` blocks below, both stated to the owner before the build started.

**What would raise confidence:** N/A

## The Question This Gate Answers

**[DECISION: the gate answers from the local object database — HEAD against the branch's
configured upstream ref — and never from the network.]**

#248's fix-shape prescribes `git rev-parse --verify origin/<branch>^{commit}`. Two departures, one
of them load-bearing:

- **No network call, and therefore a bounded question.** The authoritative answer to *"is the
  commit that will be merged the commit I validated?"* lives on the remote, and reaching it
  (`git ls-remote`, `gh pr view`) would make a governance verdict depend on the network —
  `architecture.md`'s local-first norm forbids exactly that ("no gate, evidence fact, or review
  verdict crosses the network"). It would also owe an `egress_boundary` row. So the gate answers
  the narrower question it can answer locally and **says which one**: *every commit on this branch
  is on its upstream ref as far as this clone knows.* That is precisely the shape of the defect
  that bit #803 — a local commit made after the last push — because a push updates the tracking
  ref, so local-ahead is never invisible to this check.
- **The upstream ref, not a hardcoded `origin/<branch>`.** `@{u}` is what `git push` with no
  arguments targets and what Create Step 5 already compares against, so it is the ref whose
  disagreement with HEAD means "you have not pushed". Hardcoding a remote name would answer about
  a different ref than the one the flow pushes to on any repo whose remote is not `origin`.
  A branch with no upstream is **not** silently excused: it exits 1 with `no-upstream`, whose
  remedy (`git push -u origin <branch>`) is what the flow wants regardless. A branch pushed
  without `-u` is therefore blocked once, on one command — accepted deliberately over a
  `refs/remotes/origin/<branch>` fallback, which would answer confidently about a ref nothing in
  the flow pushes to.

**What this gate does NOT replace, and the file must keep saying so.** Merge Flow step 3's
`gh pr view --json headRefOid` check covers the direction this gate structurally cannot see: the
remote moved and this clone does not know it (a suggestion committed on GitHub, a push from
another worktree, a stale tracking ref). The two checks have different subjects — local
completeness versus the PR's actual head — and a future editor reading them as duplicates and
deleting one would reintroduce half the defect. Stated in the skill beside both, and pinned.

## The Exit Codes This Gate Takes

`api-contract.md` § Error Model's standing rule: *a gate whose SUBJECT could not be read takes a
third outcome — exit 3 — rather than folding into 0 or 1*, and the test is concrete — what would
each folding have said?

| Exit | Reasons | Why this code |
|---|---|---|
| 0 | `pushed` | The upstream ref resolves to exactly HEAD. |
| 1 | `unpushed-commits`, `local-behind-remote`, `diverged`, `no-upstream` | The subject was read and the answer is "not satisfied". 1's standing remedy — push, or integrate and push — is the fix in all four, so the number carries no meaning it cannot honour. |
| 3 | `detached-head`, `git-failed` | The subject does not exist or could not be read. Folded into 0, the gate reports "safe to merge" off a check that never ran — the defect it exists to close. Folded into 1, it hands the caller "push before merging", and there is nothing to push from a detached HEAD and no git to push it with. |

All three non-zero outcomes fail closed: the item's own instruction ("fail CLOSED on every
uncertainty — a merge that silently drops commits is worse than a false block") is satisfied by 1
and 3 alike, since the skill treats any non-zero as a stop. The split buys the *caller* an
accurate remedy, not a different blocking decision.

This owes the registry a row in the same commit (`learnings.md` L463): `api-contract.md` gains
`check-branch-pushed` in its § Operations gate list and a third-outcome bullet beside its three
siblings.

## The Yield This Gate Cannot Emit

`nonfunctional-requirements.md` binds every control added after 2026-07-29 to **emit its yield
observably**. This one cannot, and the exception is recorded rather than the norm amended.

**[DECISION: record a bounded exception on the emission arm, naming the expected yield now, rather
than teaching the governance ledger a `gate.*` event kind | the ledger is a review-event store
whose module documents that non-review kinds are *deliberately not built*, and it is
schema-versioned — so a new event kind is a persisted-format lock-in decision taken for one gate,
which is the accumulation this norm exists to stop (the doctor #13/#13a exception is the recorded
precedent for exactly this shape). Amending the emission arm to admit a control that cannot
satisfy it is the laundering tell `docs/norms.md` names | user can veto/override]`

**Expected yield, stated now so a future query has something to answer:** the gate blocks a merge
whose upstream ref is not HEAD. Base rate on this repo is one known occurrence (2026-09-12, PR
#803) across its PR history, and #805's prose checks now cover the same ground *when an agent runs
them*. So: **a single firing is evidence the gate was needed** (the prose was skipped and the gate
caught it), and **a year of zero firings alongside no recurrence of a short merge is evidence for
retiring it** in favour of the prose. Clock: the trigger is the ledger gaining a non-review event
kind, or the janitor's Norm Health yield query existing — at which point this gate is a first case
alongside doctor #13.

## Status

- [ ] Chunk 01: `check-branch-pushed` — the fail-closed push-completeness gate, wired into both PR flows
Context: Plan written 2026-09-12 from #248 (filed 2026-07-09, fired in production 2026-09-12).
Nothing built yet.

## Verification Strategy

Beyond the suite: run the gate against **this** repo on this branch at three real states — before
the first push (`no-upstream`), after `git push -u` (`pushed`), and after one further local commit
(`unpushed-commits`) — because the fixture repos prove the logic and only the live repo proves the
probe reads the state a working branch actually has. Then prove each guard can go red by mutating
it (L555): flip the comparison to `!=` and confirm the pass test fails, and drop the exit-3 branch
and confirm the detached-HEAD test fails. A gate whose test suite stays green through a mutation of
the thing it names is not pinned.

## Build Chunks

### Chunk 01: `check-branch-pushed` — the fail-closed push-completeness gate, wired into both PR flows

- **Description:** The PR gates validate local HEAD; the merge merges what is on the remote. #805
  shipped two instruction-level checks for this, and prose an agent can skip is strictly weaker
  than a gate that fails closed — which is the distinction #248 was filed on and why it stayed
  open. This chunk builds the gate.

  The four surfaces are one contract: a probe that reads git state, a gate that turns that state
  into an exit code and a remedy, the CLI wiring that makes it callable, and the two skill steps
  that call it. The design decisions it implements are § The Question This Gate Answers and
  § The Exit Codes This Gate Takes; neither is restated here.

- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/api-contract.md` § Error Model (the exit-code scheme
  and its third-outcome rule), `.prawduct/artifacts/architecture.md` § Direction (local-first,
  authority-fails-closed)
- **Deliverables:**
  - `plugin/lib/gitstate.py` — `branch_push_state(project_dir)`: the read-only probe, returning a
    state dict (`state`, plus the refs, shas and counts the message needs). Homed here rather than
    in `gates.py` because this module owns git plumbing and already imports `subprocess`, which
    `gates.py` deliberately does not.
  - `plugin/lib/gates.py` — `check_branch_pushed(project_dir)`: the gate. Maps state → exit code
    and prints the named reason with its remedy. Holds no git calls of its own.
  - `plugin/bin/prawduct-hook` — `cmd_check_branch_pushed` thin wrapper, the `_USAGE` entry, the
    dispatch branch, and a `_NO_ARGUMENT_COMMANDS` row (the guard refuses arguments on the
    caller's behalf; every sibling `check-*` gate is in that set).
  - `plugin/skills/pr/SKILL.md` — the `allowed-tools` grant, the call in Create Step 5 (after the
    push, before `gh pr create`), and the call in Merge Flow **step 3**, joining the existing
    `headRefOid` check inside that step rather than becoming a new numbered step. Deliberate: this
    branch's own predecessor shipped a stale cross-reference by renumbering that flow, and the two
    checks belong together anyway — one answers local completeness, the other the PR's head.
  - `.prawduct/artifacts/api-contract.md` — the § Operations gate-list row and the third-outcome
    bullet (the registry obligation § The Exit Codes This Gate Takes names).
  - new `tests/test_check_branch_pushed.py` — the gate's own tests, against a real bare-origin
    remote.
  - `tests/test_hook_argument_shape.py` — the new command in both lists (the documented
    invocations, and the dispatch-parity set that makes the first list evidence).
  - `tests/test_pr_reviewer.py` — the skill-side pins: the gate is called in Create Step 5 and in
    Merge Flow, and the reason the two merge-side checks are not duplicates survives.
  - `.prawduct/change-log.md` — entry tagged `scope=branch-pushed-gate`.

- **Design constraints (these are the fix, not decoration):**
  1. **One probe, one classifier.** The direction (`unpushed-commits` / `local-behind-remote` /
     `diverged`) is decided once, in the probe, from ancestry — `merge-base --is-ancestor` in both
     directions — and never re-derived from the counts at the message site. Counts are for the
     human sentence only, and a count that fails to resolve must not change a verdict.
  2. **No network, no writes.** The gate opens no socket and touches no file. Both are contract,
     not habit: the first is the local-first norm, the second is what lets the gate run twice in a
     row during a flow with no side effect to reason about.
  3. **The pass line states the bound.** Exit 0 prints which ref answered and that it is this
     clone's view, so the honest scope of the answer travels with the answer rather than living
     only in a docstring.
  4. **Every message names the remedy that actually works for that shape.** `local-behind-remote`
     and `diverged` are not answered with "push" — a force-push there rewrites the tree the PR
     review's `commit_reviewed` ancestor check pinned, voiding the evidence. Integrate, re-run the
     gates, push that.
  5. **Messages name no prawduct-internal identifier** (`observability-strategy.md` § Direction),
     and the human diagnostics go to stderr.

- **Tests:**
  - integration (real bare-origin fixture) — the six states: `pushed` exits 0; a commit made after
    the push exits 1 `unpushed-commits`; the remote ahead of local exits 1 `local-behind-remote`;
    both sides carrying a commit exits 1 `diverged`; a branch with no upstream exits 1
    `no-upstream`; a detached HEAD exits **3** `detached-head`.
  - integration — the pass path names the upstream ref and its clone-scoped bound, so constraint 3
    is asserted rather than trusted.
  - unit — `branch_push_state` returns a `git-failed` state when git cannot answer (exercised by
    pointing the probe at a directory that is not a work tree), and the gate maps it to 3.
  - dispatch — `check-branch-pushed` with an argument exits 2 and runs nothing (the
    `_NO_ARGUMENT_COMMANDS` contract), and the command appears in usage.
  - skill pins — Create Step 5 and Merge Flow each invoke the gate; the `allowed-tools` grant
    exists in the house form; the "not duplicates" reason is still in the file.
  - mutation-proof each new guard per the Verification Strategy above; a green suite through a
    flipped comparison is not a pin.

- **Acceptance criteria:**
  - On this repo, on this branch: the gate reports `no-upstream` before the first push, `pushed`
    after it, and `unpushed-commits` after one further local commit — verified by running it, not
    by reasoning about it.
  - `check-branch-pushed` is reachable through `/prawduct:pr`'s granted tools (the grant test
    passes), and both flows call it.
  - Full suite passes.

- **Critic mode:** cumulative
- **Type:** bugfix
- **Foreign API:** none
- **Exposed API:** one new CLI subcommand, `check-branch-pushed`, with exit codes 0/1/3 and no
  `--json`. Additive — no existing command, flag or exit-code meaning changes.
- **Visual change:** no

- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status
