# Critic: Review Cycle

Work-scaled review lifecycle. Review depth matches the size of the work.

---

## When Review Is Required

| Work size | Mode and frequency |
|---|---|
| **Trivial** (typo, config) | None — waive via `.gates-waived` if the stop hook prompts. |
| **Small** (bug fix, minor feature) | One inner-stage review, optional — inference answers `chunk`; `final` only by declaration. |
| **Medium** (new feature, refactor) — non-chunked | One `final` review, mandatory after completion. |
| **Medium / Large** (chunked build plan) | `chunk` review per non-final chunk + `final` review on the last chunk — except when the last chunk is `Type: cumulative-final`: then ONE `cumulative` IS the last chunk's review (no separate `final`). **A short plan** — at most 3 chunks, no `Critic mode:` declared on any chunk, nothing the branch changed a risk surface — owes no per-chunk review at all: the one `cumulative` at its last chunk is every chunk's review. Inference answers `deferred` mid-chunk (dispatch nothing), and the Stop gate WARNS instead of blocking on a non-final chunk, naming that boundary review; on the last chunk it blocks as ever. |
| **Any work merging a multi-cycle branch** | `cumulative` review before opening the PR (on a `cumulative-final` plan it doubles as the last chunk's review, not a second pass). |
| **Re-review after fixing prior BLOCKING/WARNING findings** | `verify-resolutions` — delta review against the prior pass's scope. Falls through to `chunk`/`final` when the anchor is missing or scope widens past the demotion threshold. |

The stop hook enforces review for code changes when a build plan exists: it asks whether composed review coverage spans the session's base tree → the current working tree with zero unresolved blocking findings (facts in the shared evidence store; see "Evidence and Composition" below). It also surfaces an advisory WARNING when all chunks are `[x]` but the most recent review ran Goals 1-3 only — run `/prawduct:critic final` before pushing.

`/prawduct:pr create` is gated by `prawduct-hook check-cumulative-critic` — composed review coverage must span `merge-base...HEAD` by tree, with zero unresolved blocking findings on the path. No single run needs to carry any particular mode label: chunk, final, cumulative, and verify-resolutions facts compose identically.

## Mode Selection

Four modes: `chunk`, `final`, `cumulative`, `verify-resolutions`. The canonical caller is `/prawduct:critic` (no args) — the SKILL forwards any invocation arguments verbatim to `prawduct-hook infer-critic-mode`, which owns the full precedence and records `mode_chosen_by` as its verbatim rationale string. Three precedence layers, highest first, all implemented inside the helper:

1. **Per-invocation override** — an explicit mode argument (`/prawduct:critic chunk` etc.). Rationale: `"explicit-args"` — except a named `chunk`/`final` on a clean tree, whose interval is provably empty: the helper answers `cumulative`, rationale `explicit-args <token> redirected: …` — the operator's word survives into `mode_chosen_by`. Not mid-plan (below): there the token stands.
2. **Plan-level override** — the active build plan's current chunk's `Critic mode:` field (the current chunk is the first unticked `## Status` box). A valid value wins over inference with rationale `plan-override: <mode>`; an absent, blank, or unrecognized value is ignored.
3. **Inference** — the four rules (`verify-resolutions > cumulative > final > chunk`), with the short-plan deferral between the second and third: an eligible plan with code in flight answers `deferred` (rationale `short-plan deferral: …`), which dispatches nothing; a fix-in-progress still gets rule 1's review, and a committed bundle rule 2's at the boundary. **Mid-plan** (2+ unticked chunks of the branch's own plan), a clean tree answers `chunk` over the unreviewed interval, or `deferred` (nothing unreviewed, or a short plan).

Authoring heuristic (what inference picks per plan shape, when an explicit declaration earns the override): `methodology/planning.md` "Critic Mode Per Chunk".

**Default when unsure (canonical statement):** If the mode is missing, unrecognized, or no inference rule fires, run the inner-stage review of whatever interval exists — `chunk` on a dirty tree, `cumulative` on a clean tree with a committed bundle at the boundary. `final` is never a default: it is inferred on a signal or declared. The boundary is never inferred away, and neither direction of error is safe ("Severity is stage-keyed", below).

## Per-Mode Behavior

| Aspect | `chunk` | `final` | `cumulative` | `verify-resolutions` |
|---|---|---|---|---|
| **Protocol read** (SKILL step 2; `final`/`cumulative` also load `cross-checks.md` and `framework-checks.md`) | `goals-1-3.md` | `review-protocol.md` | `review-protocol.md` | `goals-1-3.md` |
| **Stage** (derived by `critic-begin` from the mode's interval, recorded in the manifest as `stage`) | `inner` | `inner` | `boundary` | `inner` |
| **Goals run** | 1, 2, 3 | All 7 goals | All 7 goals | 1, 2, 3 |
| **Goals skipped** | 4-7; Learnings Cross-Check; Backlog Reconciliation; Records Pass; Framework-Specific Checks (7-10); README/top-level docs scan | None | None | Same as `chunk` |
| **New findings rated** | The inner BLOCKING set only — every other rated item is an OBSERVATION (see "Severity is stage-keyed") | Same as `chunk`, Goals 4–7 included | Every severity | **BLOCKING only**, and only from the inner set — anything lesser is an OBSERVATION in the reviewer's report, never a `findings` entry (see "A re-review does not manufacture work") |
| **Review interval** (derived by `critic-begin`, recorded in the manifest) | Last blocker-free reviewed tree (else the merge-base if nothing judgeable is uncommitted, else HEAD's) → captured working tree | Same as `chunk` | Merge-base tree → HEAD's tree (base branch from `prawduct-hook resolve-base`) — the committed PR bundle | Prior review fact's tree → captured working tree (see "Verify-resolutions anchoring and demotion") |
| **Execution** (roster derived by `critic-begin`) | Always single-pass | Coordinator when a risk surface is touched or 12+ judgeable files change; else single-pass | Coordinator when a risk surface is touched or 12+ judgeable files change; else single-pass | Always single-pass |
| **Target wall-clock** | 1-2 min | 4-10 min | 4-10 min | 1-2 min |
| **When invoked** | Between chunks of a multi-chunk plan, before committing | End of work cycle (last chunk), non-chunked medium+ work | Before opening a PR (gated by `/prawduct:pr create`). Catches cross-chunk integration cracks. | After fixing prior BLOCKING/WARNING findings — its resolution facts unblock the same evidence, and its review fact extends coverage over the fix delta. Demotes to `chunk`/`final` when no usable prior fact exists or scope widens past the threshold. |

**Risk surface** = a changed path matching this repo's `risk_surfaces:` in `project-state.yaml` — the
same predicate `prawduct-hook classify-diff-risk` reports as the review tier (`lib/risk.py`). A repo that declares none runs
the same two escalators — the framework-shaped derived defaults (`skills/`, `lib/gates*`,
`bin/*hook*`, plus contract paths in `boundary-patterns.md`) and volume at 12 judgeable files — and
no file-count fallback beneath them (the roster config block in `lib/critic_consolidate.py` carries
the measurement that retired it). What declaring buys is the paths it names.

**Two-form rule for the `mode` value:**
- **Caller-side** (in `$ARGUMENTS`, build plan field `Critic mode:`, slash-command argument, `critic-begin --mode`): the short token — `chunk`, `final`, `cumulative`, or `verify-resolutions`.
- **Persisted-side** (the manifest, review facts, `.prawduct/.critic-findings.json`, session briefings, gate WARNINGs): the verbose string — exactly `"chunk (lighter pass, not ready for push)"`, `"final (full review, ready for push)"`, `"cumulative (bundle review, ready for merge)"`, or `"verify-resolutions (delta review, prior findings only)"`.

Read short, write verbose — the persisted JSON stays self-documenting in briefings. The conversion happens in code (`critic-begin`); the manifest validator rejects bare short tokens.

### Severity is stage-keyed

The norm is `nonfunctional-requirements.md` § Direction, *Review rigor is stage-keyed*. The **inner
stage** is any review of an uncommitted or delta interval (`chunk`, `final`, `verify-resolutions`);
the **boundary stage** is the committed bundle (`cumulative`) and the PR review. At the inner stage a
finding is one of the **inner BLOCKING set** — a test failure in the evidence; a test deleted or weakened; changed behavior with no test at all; a silently dropped requirement; exploitable security in changed code; a cross-component contract break; a norm departure without a recorded decision; an unlisted dependency — and every other verdict the tables rate is an
observation: reported, recorded in the partial's `observations` array, answerable on the record,
never a `findings` entry. At the boundary the tables stand as written and consolidation refuses an
`observations` array. `critic-begin` derives `stage` from the mode (one home: `critic_consolidate.stage_of`), writes it
on the manifest with `judgeable_files`, `chunk_type` and the code-rendered `signals` line every
reviewer is handed, and it rides the review fact, the findings cache and the
`review.critic` ledger event — `review-stats` groups on it (`by_stage`), which is the yield query the
ratchet norm asks of every control. The failure direction is symmetric: an inner review run at
boundary rigor manufactures rounds; a boundary review run at inner rigor is priced in what ships.

The chunk `Type:` selector (which goals and checks each `Type:` value runs) is in `cross-checks.md`.

### Evidence and Composition

Every consolidated review appends a **fact** to the shared evidence store (`<git-common-dir>/prawduct/evidence.jsonl` — shared by all worktrees of a clone, inspectable via `prawduct-hook evidence status|list`). A fact records the trees it actually saw: `base_tree → head_tree`, plus `files_reviewed` (the findings-eligible **subject** set — everything but the records *about* the work), `files_oracle` (what the round read and did not rate), the findings, its `stage`, and any `observations` an inner-stage pass demoted. Gates answer by **composition**: coverage of A → B exists when review facts (and free edges over intervals touching only non-judgeable files) form a path from tree(A) to tree(B), and the verdict passes when no blocking finding on the path lacks a resolution fact. Consequences worth knowing:

- A review of the dirty working tree **vouches for the subsequent commit** when the commit is made verbatim — the commit carries the reviewed tree. Any worktree or later session can then compose over it; nothing expires by time or session.
- A rebase or amend changes the tree → a gap composition cannot close (the transfer below closes one case). A squash-merge preserves the tree, so squashed PRs stay covered.
- A **selective commit** (only part of the reviewed state) produces a tree nobody reviewed — a gap. `/prawduct:critic verify-resolutions` reviews that delta and closes it.
- Blocking findings don't die with re-runs: they stay on the path until a `verify-resolutions` pass appends resolution facts for them.

### Cumulative mode and the PR gate

`cumulative` is the only mode whose head is committed state, not the working tree: `critic-begin` resolves the base branch via `prawduct-hook resolve-base` (it honors a configured `base_branch:`, falling back to `origin/main`/`main` — the **single source of truth** the PR gate uses too, so reviewer and gate never diff different ranges) and derives the interval merge-base tree → HEAD's tree — deliberately spanning every commit on the branch, so cross-chunk integration cracks surface even when every per-chunk review was clean.

`/prawduct:pr create` calls `prawduct-hook check-cumulative-critic` and refuses to open the PR if the gate fails. Its stderr names the remedy: `uncovered` → run `/prawduct:critic cumulative`; `blocking` → fix, then `/prawduct:critic verify-resolutions` — no full re-review. A blocker marked `Superseded:` is the exception — a verify pass anchors only to the most recent review, so it clears only through a spanning `cumulative`. WARNING and NOTE are advisory at the PR gate — they do not block, matching the PR reviewer's severity contract.

`uncovered` caused only by the **base advancing** transfers instead of buying a round, at BOTH gates: `coverage.diagnose_base_advance_transfer` grants it when the branch's own diff is byte-identical across both spans and a suite run has met the tree that gate vouches for. A denial on that condition alone says so: the remedy is a run, not a review.

**Prep work before invoking cumulative.** A cumulative review takes ~4-10 minutes. Before invoking it, complete prep that doesn't depend on its findings — `.claude/rules/learnings/` for next topics, draft the PR description, audit the backlog, capture deferred reflections — so you integrate findings the moment it returns. This prep is also what keeps the wait cheap: a session that idles silently while reviewers run lets its prompt cache expire and re-reads its whole context when they land. If the prep runs out before the review lands, tell the user what you are waiting on.

### Verify-resolutions anchoring and demotion

`verify-resolutions` is the only mode anchored to a *prior* review fact rather than HEAD. It exists to cut re-review latency after a round flags 1-2 BLOCKING findings and the builder fixes them — a full `chunk`/`final` re-run walks the whole diff again for a localized change. Its consolidation is also the only path that may append **resolution facts** (the judgment that unblocks a prior blocking finding); a `resolutions` payload in any other mode fails consolidation closed.

**Anchoring.** `critic-begin --mode verify-resolutions` locates the prior review fact via the findings cache's `fact_id` pointer and derives the interval: prior fact's `head_tree` → the captured working tree. Scope = the prior `files_reviewed` plus the delta, split into subject and oracle — all computed in code and recorded in the manifest. Tree keying makes a dirty-tree verify sound: no commit needs to precede the pass, and the resulting fact extends coverage to whatever tree it saw.

The head end moves to **committed HEAD** instead when committed content differs from the reviewed tree — that is the PR gate's target, and anchoring there keeps a stray uncommitted file from leaving the gate `uncovered` after a successful pass (the WIP is noted and excluded). "Differs" is a **tree** comparison, and two readings of it are wrong in opposite directions: the vouching commit above materializes the reviewed tree verbatim, so it changes no content and is not a change of intent; and a prior review of a **dirty** tree (its fact records `head_commit: null`) leaves the anchor *ahead* of committed HEAD, which read as a committed delta inverts the edge and anchors the resolution facts to a tree the fixes are absent from. So the head end moves only when the trees differ **and** a commit actually landed — HEAD no longer standing where the prior review dispatched. (Both exclusions are code; `critic_consolidate.begin_review` carries the derivation.)

The anchor must also be an **ancestor of HEAD**. The findings cache is single-slot and survives a branch switch, and worktrees of one clone share an object store, so a sibling branch's anchor still resolves — resolving is not evidence it belongs to this lineage, and a cross-branch anchor yields phantom findings. Not-an-ancestor and any git failure both demote.

**Demotion** (all detected by `critic-begin`, fail-closed — it refuses to anchor rather than silently shrinking the review):

**Every row is governed by the demotion property** (`SKILL.md` step 4) — a demotion must name a mode whose interval can SEE the work. Rows flagged **Committed** are by construction the case `chunk`/`final` cannot cover.

| Trigger (exit code) | Why it demotes |
|---|---|
| No readable findings cache, no `fact_id` in it, or the fact is gone from the store (1) | Nothing to anchor against — fall back per the property above, record `mode_chosen_by: "fallback-no-prior-findings"`. |
| The prior tree can't be diffed against the current tree (1) | Rewritten history — anchor unreliable; same fallback. **Committed.** |
| The prior fact's anchor commit is not an ancestor of HEAD (1) | Another lineage — a branch switch, or rewritten history; the delta would span the divergence. Same fallback. **Committed.** |
| Delta > 2 × the prior count + 5 (2) | Scope widened beyond the prior surface — a partial review would mislead. Both counts are coverage-priced (the judgeable subset of each subject set, not the subject set), so prose riding along on a fix cannot demote the pass. Re-dispatch in the mode the refusal names, recording `mode_chosen_by: "fallback-scope-widened"`. |

**Not a demotion.** Prior review has no BLOCKING/WARNING findings and the anchored tree is the one it
reviewed: **exit 3, no review needed — stop.** There is no wider mode to fall back to, and
re-dispatching one spends a full round on a bundle the gate already passes.

**When NOT to use verify-resolutions.** Not as a chunk's first review (it's a re-review mode). Not after long drift unrelated to the original findings — the scope-widening threshold exists for exactly that.

## Per-Chunk Cycle

1. Builder completes a chunk's implementation and tests.
2. Critic reviews using the goal-based approach (see SKILL.md).
3. **If BLOCKING findings exist:** builder fixes; Critic re-reviews (`verify-resolutions`), specifically watching for **fix-by-fudging** — weakening a test to make it pass, changing a spec to match wrong implementation, a workaround where the finding named the root cause. Each is a **BLOCKING** finding in its own right *and* grounds to withhold the resolution: the finding was not fixed, so leaving it out of `resolutions` keeps it blocking, which is the answer that fails closed. Repeat until no blocking findings remain. Only the resolution facts a verify pass records unblock a blocking finding — the gate keeps blocking until then.
4. Every review persists through `critic-consolidate` — a review fact in the store plus the regenerated `.prawduct/.critic-findings.json`. A clean pass records an empty findings array; there is no review without a record.
5. **If no BLOCKING findings:** chunk complete; proceed.

### The review loop terminates — and the builder is what terminates it

**Once a pass returns zero BLOCKING, the review is over.** That is the exit condition, not a judgment
call, and it is what keeps step 3's "repeat until" from being unbounded.

**But "the review is over" is not "add it to the backlog."** Every remaining WARNING/NOTE gets exactly
one of three dispositions, and **FILE is the narrowest, never the default**:

- **ACCEPT** — won't fix. Record the disposition and its reason as a *fact* (`prawduct-hook
  disposition … --accept`, below) and render it into the change-log entry for the work or the PR body;
  no backlog item. This is the **default** for anything that gates nothing and that no
  one will realistically action. Principle 2 already licenses it: *implemented or explicitly
  descoped*. An accept is the explicit descope — visible, dated, and attached to the work it came
  from, where the next reader of that change meets it.
- **FIX** — take it now. Correct for anything cheap, and for anything touching a gate, a contract, or
  an operator-facing surface regardless of cost. Closing coverage afterwards costs **one**
  `verify-resolutions` pass — bounded, and not another full round. A fix confined to non-judgeable
  surfaces costs nothing at all, and records as `--fixed <paths>` (below).
- **FILE** — only genuinely deferred work that someone will actually do, and the item says what
  triggers it. No trigger means it is an ACCEPT wearing a backlog id. **Two tests, and it must pass
  both:** the work is **large** — a chunk's worth or more, not an hour's — **and** you cannot
  responsibly do it inside the current work, because it needs its own design, its own review, or it is
  orthogonal to what you are building. Filing something small that you have the context to fix *right
  now* is the worst option available: you pay the filing cost, the reader pays the triage cost, the next
  agent pays the re-derivation cost, and the item then sits unactioned because whoever picks it up has
  none of what you currently have in your head. **Deep context on a small problem is a FIX signal, not
  a filing signal — for a BLOCKER.** Below BLOCKING, the same deep context argues for a recorded
  ACCEPT, which costs no round, rather than a fix that buys one.

### A re-review does not manufacture work

Everything above is the **demand** side — what the builder does with findings that already exist. This
is the **supply** side, and without it the demand-side rules are asked to absorb an inflow the
framework itself creates.

**In `verify-resolutions`, a new finding is BLOCKING or it is not a finding.** Anything lesser the
reviewer notices is reported as an **OBSERVATION** in prose and never enters `findings`. (The stage
norm above generalizes the demotion to every inner-stage mode; this section keeps the reasoning that
first earned it.)

*Why this mode and not the others.* A verify pass exists to answer one question — were the named
findings resolved? Walking the fix delta at full severity on top of that turns round N's fix into
round N+1's findings: the builder fixes a WARNING, the fix moves the tree, the moved tree reopens
coverage, and the next pass reviews the prose the last fix wrote. Measured at ten rounds on one
consumer branch, where rounds five onward were entirely non-gating findings the previous round's
fixing had created. `chunk`, `final` and `cumulative` review work the builder *chose* to do; only
`verify-resolutions` reviews a delta the framework asked for.

*What it does not cost.* Unresolved BLOCKING findings are the only severity any gate reads, so nothing
that gated stops gating. The narrowing binds on **membership in the inner BLOCKING set** ("Severity
is stage-keyed"), which the dispatch directive (`critic_consolidate.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE`)
states in the norm's own sentence, so a class the set names
cannot be swept up by a table that rates it lower.

*The set is exact, and two of its members are escalations.* The directive names the shapes a fix
delta gets wrong (a weakened or deleted test, a dropped requirement, changed behavior with no test,
exploitable security in changed code including missing auth/authz and known-vulnerable
dependencies, and fix-by-fudging) and rates each BLOCKING, including the two `goals-1-3.md` prints
lower.

*What it does cost, stated plainly.* The fix delta's own content is rated at BLOCKING only. The
bound is narrower than it first reads, and the weaker reading is the honest one: `verify-resolutions`
is never a first review (`critic-begin` demotes when no usable prior fact exists), so the tree
*beneath* the fix was fully reviewed — but the fix delta's own content was not, and post-cumulative
fixes route here too. What holds is that the builder meets every observation twice: in the report,
under an `### Observations` section with a stated count, and on the review fact under an `O-n` id —
which makes it **answerable** (`disposition <review-id> O-1 --accept "<reason>"`). Declining one
stops costing the reasoning, which is what made fixing it the only answer that left a trace.

*Yield is emitted on both arms.* `review-stats` shows under-firing as B/W/N and over-firing — real
work suppressed — as the `observations` count beside it, derived from the items riding the review
event rather than a number the reviewer asserted about its own output.

### Record the disposition; render the census

**A disposition is a fact, not a sentence you write.** A FIX that bought a round already left a
machine-readable trace — the resolution fact a `verify-resolutions` pass records. ACCEPT, FILE, and
a FIX that bought no round record theirs with:

```
prawduct-hook disposition <review-id> <fid|oid> --accept "<reason>"      # won't fix, reason recorded
prawduct-hook disposition <review-id> <fid|oid> --file <backlog-id>      # deferred, item carries the work
prawduct-hook disposition <review-id> <fid|oid> --fixed <path>[,<path>…] # fixed for free, no round bought
```

**`--fixed` exists because the cheapest correct action was the only one the record could not see.** A
free fix buys no round, so no verify pass runs, no resolution fact is written, and the census reads
`undispositioned` forever — leaving "don't fix it" and "spend ten minutes" as the visible answers.
The paths you name are checked against the predicate that prices the edit: **a set
holding anything judgeable is refused**, so nothing launders a judgeable fix past a gate. BLOCKING is refused too: it clears only through a resolution fact.

The command validates that the finding exists before it records anything, and refuses to accept a
BLOCKING finding without `--owner-ruling "<text>"` — the severity rule below, enforced in code rather
than remembered. Re-dispositioning appends a newer fact; the older one stays as history, and an
identical re-run is a reported no-op. **A disposition never satisfies a gate**: a BLOCKING finding
stays blocking until a verify pass records a real resolution, so recording one costs you nothing and
protects nothing you shouldn't want protected.

**Then render the census — never author it:**

```
prawduct-hook render-dispositions [--review <id>|--scope <s>] [--json]
```

Paste the rendered table into the change-log entry or PR body. It reports each finding's state
(`fixed`, `waived`, `accepted`, `filed`, `fixed-unreviewed`) and how many findings are still
**undispositioned**. `fixed-unreviewed` is not `fixed`: both say the defect is gone, only one says a reviewer looked.

Hand-written censuses drift, and correcting one is a commit that buys a review round, so counting is
the machine's job and deciding is yours.

FILE is the narrowest disposition because a backlog that receives every non-blocking finding stops
being a work queue.

**"Pre-existing" is not a disposition, and neither is "already filed."** Both are the reflex wearing
a respectable coat: the finding leaves the review dispositioned by nobody. A defect the diff did not
introduce still gets FIX or ACCEPT — and "ACCEPT: predates this branch, out of its scope, tracked at
`ID`" is a perfectly good ACCEPT *because it is written down where the next reader meets it*. What is
not allowed is the silent write-off, or pointing at an open item as though the pointing were the
work. **If you fix something that has an open item, close the item in the same commit; if you accept
something that has one, say so on the item.** An existing id is a reason to reconcile, never a reason
to skip.

**The count is the smell.** A review that ends with a double-digit filing is not thorough, it is
undisposed. If you are filing more than two or three, you are using the backlog to avoid deciding —
go back and sort them into ACCEPT and FIX.

**Severity does not exempt.** BLOCKING, WARNING and NOTE all take a disposition; only the bar for
ACCEPT differs (a NOTE is often a one-clause accept; a BLOCKING cannot be accepted at all without an
explicit owner decision, since gates compose on it). Exempting NOTE just moves the pump, because
NOTE is the most common severity.

Reviewers are told never to name the backlog as a finding's destination (`cross-checks.md`).

Why it has to be a rule. WARNING and NOTE **gate nothing** — the PR gate and the Stop gate both
require only *coverage* plus *zero unresolved BLOCKING*. An agent that fixes them anyway commits
each fix; the commit extends HEAD; coverage no longer reaches HEAD; another pass runs; that pass reviews the records
just written and finds something true about them.

**Before running another pass to "close coverage," re-run the gate and let it answer.** Never infer
that coverage is needed from gate output printed *before* your fix commits — that stale line is the
most reliable way an agent talks itself into a round nothing asked for:

```
prawduct-hook check-cumulative-critic   # PR path
```

If it passes, you are done — stop; if it does not, the span is not free and the round is real.

**Batch the fixes: make them in the working tree, run one `verify-resolutions` over them, then land them in one commit** (after a `cumulative`, a fix committed first still infers the pass: rule 1b) — and there, don't judge whether the
pass is warranted: ask. `critic-begin` exits 3 (`no review needed`, no session state written) when
the post-fix delta is free, applying the same predicate the gate charges by.
Fix-commit-verify per finding multiplies rounds and hands each new round the prose the last fix
wrote. `critic-consolidate`'s close directive states the same order whenever a review lands
findings, so the builder meets it holding the findings rather than remembering it from here.

**Which writes are free while a review is in flight** — the question the builder actually has
mid-review, answered by `coverage_algebra.is_judgeable_path`. Free: **everything under
`.prawduct/`** (change-log, backlog, `project-state.yaml`, plan prose including its
`## Status` boxes, and the gitignored session files), `.claude/settings.json`, and `.md` outside the protected
set — README, `docs/**`, product prose. These are **non-judgeable**: a commit touching only those
composes as a free edge, so it never needs new coverage and a fix confined to them cannot mandate
another review. Two traps, both in the direction of *more* review than the extension suggests: a
**comment-only edit to a `.py` file still counts as judgeable**, which is how a pure-prose fix
commit gets pulled back into a full round; and a `.md` file under `skills/`, `methodology/` or
`templates/`, or a root `CLAUDE.md`, is **governance-protected and therefore judgeable** —
fork-skill prose is behavioural logic here. When in doubt assume judgeable and let the gate say
otherwise; it is the gate's answer that binds.

**The reviewer's half of the same rule is a separate pass, not a severity floor.** A record is not a
per-round subject at all — the bars that decide when one is worth a finding, and the pass that
applies them, are `cross-checks.md`'s **Records Pass**.

**Yield does not decay — do not wait for it to.** Findings per full round *rise* — 13.5, 15.4, 15.5, 18.4 — 99% of them new. There is **no natural fixed point**: "stop when the yield drops" never fires.
Later rounds do increasingly find defects in the *record of the previous round* — a signal to disposition what you have, never a bound. The
bounds are zero BLOCKING above, and the budget below. Stopping is not filing: most of that round's
findings are ACCEPTs, and saying so takes a clause each.

**The round budget is the backstop, and it is on.** `review_round_budget`
(`.prawduct/project-state.yaml`, 6 by default, `null` disables) caps the **full** rounds one body of
work may buy. At the ceiling `critic-begin` exits 4, auto-ACCEPTs the outstanding non-blocking
findings with the budget as their reason, and renders the census. It never counts or refuses a
`verify-resolutions` pass, and never sweeps a BLOCKING finding — so **it can end a review loop and
can never open a gate**. `--force` buys one anyway; needing that every time means the number is wrong.

**Last chunk of a `Type: cumulative-final` plan — one review, not two.** Commit the chunk, then run `/prawduct:critic cumulative` ONCE: that single review serves as both the chunk's review and the PR-gate evidence. Don't run a separate `final` first — cumulative runs the same 7 goals plus cross-checks over `merge-base...HEAD`, a scope that already contains the chunk's diff, so a preceding `final` re-pays 4-10 minutes for assurance the cumulative re-derives. Mode inference implements the sequencing: with the last chunk's work still uncommitted, `/prawduct:critic` infers `final` (the right mid-chunk look); once committed and clean, it infers `cumulative` — the at-commit review. Post-cumulative fixes take a `verify-resolutions` pass, not a second full one — its fact extends coverage over the fix delta. **A short plan gets this sequencing without the declaration**, on every chunk: mid-chunk `/prawduct:critic` answers `deferred` rather than `final`, and the boundary review that follows the last commit is the plan's whole review record. The eligibility is re-asked at every inference and every Stop against the branch's actual paths, so a later chunk that lands on a risk surface owes its review like any other.

## Reviewer Cross-Checks

The Final-Mode Cross-Checks (Learnings Cross-Check, Backlog Reconciliation, Records Pass,
Record-Lint and Governing-Artifact Reconciliation) are in `cross-checks.md`, the file every
`final`/`cumulative` reviewer loads.

## Recording Reviews

Every review cycle must produce a record — governance without an audit trail is documentation fiction. Every mode records the same way: `critic-begin` writes the dispatch manifest (code), the reviewer(s) write partials, and `prawduct-hook critic-consolidate` appends the review fact to the evidence store and regenerates `.prawduct/.critic-findings.json` from it. No model writes the manifest, the findings file, the store, or the ledger — a clean pass persists an empty findings array through the same path (see `review-protocol.md` "Review Execution").

**Dispatch manifest** (`.prawduct/.critic-partials/manifest.json`, written by `critic-begin`; schema/validators in `lib/critic_consolidate.py`). Keys: review `id`, `mode` (verbose string), `mode_chosen_by` (the `infer-critic-mode` rationale, relayed via `--chosen-by`), `roster` + `roster_chosen_by`, `rendezvous` (each role's resolved partial + started paths, derived from `partial_path`/`started_path`, which own the shape — recorded here so no instruction surface spells a filename), `commit_reviewed` (HEAD at dispatch), the review interval (`base_tree`/`head_tree` + commits), `files_changed` plus its subject/oracle split (`files_reviewed`/`files_oracle`), all derived from the interval, the review `stage` with `judgeable_files`, `chunk_type` and the rendered `signals` line ("Severity is stage-keyed"), and the relayed telemetry `tier`, `scope`, `chunk`, `base_reviewed`. `critic-consolidate` refuses to persist unless every roster role reported a valid partial at the manifest's `commit_reviewed`, carrying the manifest's `id` as its `dispatch_id` — the binding that stops a straggler from a displaced review consolidating as this one.

**The findings cache is a derived view.** `.prawduct/.critic-findings.json` is regenerated from the newest review fact and carries its `fact_id`; builders and briefings read it for *content*, and no gate reads it — gates compose over the store.

### The Governance-Event Ledger

The ledger (`.prawduct/.governance-ledger.jsonl`, gitignored) is the append-only telemetry history: `critic-consolidate` appends one `review.critic` event per consolidated review (the PR skill appends `review.pr` the same way). `lib.ledger` is the **single writer** (`ledger-append` for reviews, in-process for `learning.*`) — it validates the record and computes the envelope; agents never hand-author JSONL. No gate reads it; `review-stats` aggregates it.

Its `scope` comes from the dispatch manifest, where `critic-begin` recorded it — **derived in code** from the branch name matched against the scopes build plans declare, or passed explicitly as an override. `active_build_plan` is only the last fallback. Do not derive scope yourself and pass it: an agent reading that pointer is what attributed manifests, review facts and ledger events to unrelated plans.

Each line is one event with an envelope/payload split:

```json
{"schema_version": 1, "event": "review.critic", "ts": "...Z",
 "duration_seconds": 180, "project": "my-product", "scope": "my-feature",
 "chunk": "02", "actor": {"role": "critic", "model": "opus"},
 "git": {"head": "<sha>", "base": "origin/develop"},
 "review": { ...the findings record verbatim... }}
```

The envelope is shared by every event kind; the kind-specific payload nests under a family-named key (`review` for `review.critic` and `review.pr`). Consumers key on the envelope and **skip unknown event kinds and fields** — later kinds join without schema change. `duration_seconds` and `actor.model` are nullable, never invented; `scope` is the build-plan feature key (see above). Every line is self-contained; a long-lived repo can truncate oldest lines.

## Extending This Skill

Prefer strengthening existing goals over adding new ones. The 7 goals cover correctness (1-3), coherence and design (4, 7), and sustainability (5-6). When a new concern surfaces, first ask whether an existing goal can absorb it.

This guidance is addressed to whoever maintains the Critic, not to a reviewer mid-review, which is why it lives here rather than in `review-protocol.md` — that file is a payload every `final`/`cumulative` review loads under a token ceiling, and a reviewer never extends the skill while reviewing.
