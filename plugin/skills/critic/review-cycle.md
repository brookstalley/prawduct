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

The stop hook enforces review for code changes when a build plan exists: it asks whether composed review coverage spans the session's base tree → the current working tree with zero unresolved blocking findings (facts in the shared evidence store; see "Evidence and Composition" below). It also surfaces an advisory WARNING when all chunks are `[x]` but the most recent review ran Goals 1-3 only — run `/prawduct:critic final` before pushing.

`/prawduct:pr create` is gated by `prawduct-hook check-cumulative-critic` — composed review coverage must span `merge-base...HEAD` by tree, with zero unresolved blocking findings on the path. No single run needs to carry any particular mode label: chunk, final, cumulative, and verify-resolutions facts compose identically.

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
| **Protocol read** (SKILL step 2 — exactly one, and nothing else) | `goals-1-3.md` | `review-protocol.md` | `review-protocol.md` | `goals-1-3.md` |
| **Goals run** | 1, 2, 3 | All 7 goals | All 7 goals | 1, 2, 3 |
| **Goals skipped** | 4-7; Learnings Cross-Check; Backlog Reconciliation; Framework-Specific Checks (7-10); README/top-level docs scan | None | None | Same as `chunk` |
| **Review interval** (derived by `critic-begin`, recorded in the manifest) | HEAD's tree → captured working tree (the uncommitted diff) | Same as `chunk` | Merge-base tree → HEAD's tree (base branch from `prawduct-hook resolve-base`) — the committed PR bundle | Prior review fact's tree → captured working tree (see "Verify-resolutions anchoring and demotion") |
| **Execution** (roster derived by `critic-begin`) | Always single-pass | Single-pass under 5 changed files; coordinator at 5+ | Single-pass under 5 changed files; coordinator at 5+ | Always single-pass |
| **Target wall-clock** | 1-2 min | 4-10 min | 4-10 min | 1-2 min |
| **When invoked** | Between chunks of a multi-chunk plan, before committing | End of work cycle (last chunk), non-chunked medium+ work, or any time the right answer is unclear | Before opening a PR (gated by `/prawduct:pr create`). Catches cross-chunk integration cracks. | After fixing prior BLOCKING/WARNING findings — its resolution facts unblock the same evidence, and its review fact extends coverage over the fix delta. Demotes to `chunk`/`final` when no usable prior fact exists or scope widens past the threshold. |

**Two-form rule for the `mode` value:**
- **Caller-side** (in `$ARGUMENTS`, build plan field `Critic mode:`, slash-command argument, `critic-begin --mode`): the short token — `chunk`, `final`, `cumulative`, or `verify-resolutions`.
- **Persisted-side** (the manifest, review facts, `.prawduct/.critic-findings.json`, session briefings, gate WARNINGs): the verbose string — exactly `"chunk (lighter pass, not ready for push)"`, `"final (full review, ready for push)"`, `"cumulative (bundle review, ready for merge)"`, or `"verify-resolutions (delta review, prior findings only)"`.

Read short, write verbose — the persisted JSON stays self-documenting in briefings. The conversion happens in code (`critic-begin`); the manifest validator rejects bare short tokens.

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

### Evidence and Composition

Every consolidated review appends a **fact** to the shared evidence store (`<git-common-dir>/prawduct/evidence.jsonl` — shared by all worktrees of a clone, inspectable via `prawduct-hook evidence status|list`). A fact records the trees it actually saw: `base_tree → head_tree`, plus `files_reviewed` and the findings. Gates answer by **composition**: coverage of A → B exists when review facts (and free edges over intervals touching only non-judgeable files) form a path from tree(A) to tree(B), and the verdict passes when no blocking finding on the path lacks a resolution fact. Consequences worth knowing:

- A review of the dirty working tree **vouches for the subsequent commit** when the commit is made verbatim — the commit carries the reviewed tree. Any worktree or later session can then compose over it; nothing expires by time or session.
- A rebase or amend changes the tree → coverage gap → fresh review. A squash-merge preserves the tree, so squashed PRs stay covered.
- A **selective commit** (committing only part of the reviewed state) produces a tree that was never reviewed — a coverage gap. `/prawduct:critic verify-resolutions` reviews that delta and closes it.
- Blocking findings don't die with re-runs: they stay on the path until a `verify-resolutions` pass appends resolution facts for them.

### Cumulative mode and the PR gate

`cumulative` is the only mode whose head is committed state, not the working tree: `critic-begin` resolves the base branch via `prawduct-hook resolve-base` (it honors a configured `base_branch:`, falling back to `origin/main`/`main` — the **single source of truth** the PR gate uses too, so reviewer and gate never diff different ranges) and derives the interval merge-base tree → HEAD's tree — deliberately spanning every commit on the branch, so cross-chunk integration cracks surface even when every per-chunk review was clean.

`/prawduct:pr create` calls `prawduct-hook check-cumulative-critic` and refuses to open the PR if the gate fails. The gate composes coverage of merge-base tree → HEAD tree over the store and requires zero unresolved BLOCKING findings on the path. Its stderr names the remedy: `uncovered` → run `/prawduct:critic cumulative` (or `verify-resolutions` for a selective-commit delta); `blocking` → fix, then `/prawduct:critic verify-resolutions` records the resolution facts and the same evidence passes — no full re-review. WARNING and NOTE are advisory at the PR gate — they do not block, matching the PR reviewer's severity contract.

**Prep work before invoking cumulative.** A cumulative review takes ~4-10 minutes. Before invoking it, complete prep that doesn't depend on its findings — `/prawduct:learnings` for next topics, draft the PR description, audit the backlog, capture deferred reflections — so you integrate findings the moment it returns. This prep is also what keeps the wait cheap: a session that idles silently while reviewers run lets its prompt cache expire and re-reads its whole context when they land. If the prep runs out before the review does, emit a one-line progress note at least every 4 minutes rather than going quiet.

### Verify-resolutions anchoring and demotion

`verify-resolutions` is the only mode anchored to a *prior* review fact rather than HEAD. It exists to cut re-review latency after a round flags 1-2 BLOCKING findings and the builder fixes them — a full `chunk`/`final` re-run walks the whole diff again for a localized change. Its consolidation is also the only path that may append **resolution facts** (the judgment that unblocks a prior blocking finding); a `resolutions` payload in any other mode fails consolidation closed.

**Anchoring.** `critic-begin --mode verify-resolutions` locates the prior review fact via the findings cache's `fact_id` pointer and derives the interval: prior fact's `head_tree` → the captured working tree. Scope = the prior `files_reviewed` plus the delta — all computed in code and recorded in the manifest. Tree keying makes a dirty-tree verify sound: no commit needs to precede the pass, and the resulting fact extends coverage to whatever tree it saw.

**Demotion** (all detected by `critic-begin`, fail-closed — it refuses to anchor rather than silently shrinking the review):

| Trigger (exit code) | Why it demotes |
|---|---|
| No readable findings cache, no `fact_id` in it, or the fact is gone from the store (1) | Nothing to anchor against — fall back to `chunk`/`final`, record `mode_chosen_by: "fallback-no-prior-findings"`. |
| The prior tree can't be diffed against the current tree (1) | Rewritten history — anchor unreliable; same fallback. |
| Prior review has no BLOCKING/WARNING findings and nothing changed since (1) | Nothing to verify and no delta to review. |
| Delta files > 2 × prior `files_reviewed` + 5 (2) | Scope widened beyond the prior surface — a partial review would mislead; fall back to `final`, record `mode_chosen_by: "fallback-scope-widened"`. |

**When NOT to use verify-resolutions.** Not as a chunk's first review (it's a re-review mode). Not after long drift unrelated to the original findings — the scope-widening threshold exists for exactly that.

## Per-Chunk Cycle

1. Builder completes a chunk's implementation and tests.
2. Critic reviews using the goal-based approach (see SKILL.md).
3. **If BLOCKING findings exist:** builder fixes; Critic re-reviews (`verify-resolutions`), specifically watching for **fix-by-fudging** — weakening a test to make it pass (**BLOCKING**), changing a spec to match wrong implementation (**BLOCKING**), a workaround instead of root cause (**WARNING**). Repeat until no blocking findings remain. Only the resolution facts a verify pass records unblock a blocking finding — the gate keeps blocking until then.
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
  surfaces costs nothing at all.
- **FILE** — only genuinely deferred work that someone will actually do, and the item says what
  triggers it. No trigger means it is an ACCEPT wearing a backlog id. **Two tests, and it must pass
  both:** the work is **large** — a chunk's worth or more, not an hour's — **and** you cannot
  responsibly do it inside the current work, because it needs its own design, its own review, or it is
  orthogonal to what you are building. Filing something small that you have the context to fix *right
  now* is the worst option available: you pay the filing cost, the reader pays the triage cost, the next
  agent pays the re-derivation cost, and the item then sits unactioned because whoever picks it up has
  none of what you currently have in your head. **Deep context on a small problem is a FIX signal, not
  a filing signal.** (Owner-requested rule, 2026-07-29.)

### Record the disposition; render the census

**A disposition is a fact, not a sentence you write.** FIX already left a machine-readable trace — the
resolution fact a `verify-resolutions` pass records. ACCEPT and FILE now do too:

```
prawduct-hook disposition <review-id> <fid> --accept "<reason>"      # won't fix, reason recorded
prawduct-hook disposition <review-id> <fid> --file <backlog-id>      # deferred, item carries the work
```

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
(`fixed`, `waived`, `accepted`, `filed`) and — the number nothing measured before — how many findings
are still **undispositioned**.

**Why this stopped being prose.** Hand-written censuses drift, and their corrections re-enter review.
Measured on this framework's own repo in a single day: one census asserted a count of accepted notes
and then contradicted itself in its own closing sentence, another asserted every blocking and warning
finding was *fixed* when the store recorded one of them as *waived*, and a third was corrected three
times — each correction a commit, and commits extend HEAD, which is how a record defect buys a review
round. Arithmetic over facts the store already holds does not need a reviewer to check it. Counting
is the machine's job; deciding is yours.

**Why the default moved.** The old rule said file the rest, full stop. It bounded the review loop —
which was the real problem it solved — but it made the backlog the disposal route for every finding a
thorough reviewer produces, and thorough reviewers produce many. Measured on this framework's own
repo: **open items went 50 → 180 in 26 days; 67 were Critic-sourced and 53 of those had never been
touched since filing** — faster than anyone could action them, which turns the backlog from a work
queue into a guilt pile and buries the items that mattered. The sharpest tell was compounding: one
gate accumulated **six** open items, each a facet found by a later review of the same still-unfixed
mechanism. A framework that does this to itself does it to every
repo that adopts it, once per build plan.

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
explicit owner decision, since gates compose on it). Exempting NOTE just moves the pump — NOTE was
the majority of findings in the review that prompted this rule.

**Reviewers: never name the backlog as a finding's destination, at any severity.** The severity
contract (`review-protocol.md`) no longer says "recommend backlog" anywhere, and reviewers must not
reintroduce it in prose. Disposition is the builder's call, made once with the whole diff in view;
a reviewer-suggested destination pre-empts it and reads as a licence to file without deciding. State
the defect and its consequence, say what a fix would take when that isn't obvious, and stop.

Why it has to be a rule. WARNING and NOTE **gate nothing** — the PR gate and the Stop gate both
require only *coverage* plus *zero unresolved BLOCKING*. But `methodology/building.md` says warnings
"should be addressed," which reads as must-fix, so an agent fixes them. Each fix is a commit; the
commit extends HEAD; coverage no longer reaches HEAD; another pass runs; that pass reviews the records
just written and finds something true about them. Observed live: **four rounds and ~40 minutes of
review on a ~40-line code change** — every finding correct, none blocking, and the last round required
by no gate at all.

**Before running another pass to "close coverage," re-run the gate and let it answer.** Never infer
that coverage is needed from gate output printed *before* your fix commits — that stale line is the
most reliable way an agent talks itself into a round nothing asked for:

```
prawduct-hook check-cumulative-critic   # PR path
```

If it passes, you are done — stop. Record-only surfaces (`change-log.md`, `learnings.md`,
`.prawduct/artifacts/**` plan prose, product docs) are **non-judgeable**: a commit touching only those
never needs new coverage, so a fix confined to them cannot mandate another review. Two traps, both
in the direction of *more* review than the extension suggests: a **comment-only edit to a `.py` file
still counts as judgeable**, which is how a pure-prose fix commit gets pulled back into a full
round; and a `.md` file under `skills/`, `methodology/` or `templates/`, or a root `CLAUDE.md`, is
**governance-protected and therefore judgeable** — fork-skill prose is behavioural logic here. When
in doubt assume judgeable and let the gate say otherwise; it is the gate's answer that binds.

**The reviewer's half of the same rule** (severity contract: `review-protocol.md`). A finding whose
only subject is a non-judgeable record is a **NOTE** unless it clears one of two bars:

- **It ships** — the inaccuracy reaches consumers as a false claim (release note, `CHANGELOG.md`, a
  published doc). *A change-log entry asserting a guard that was never built → WARNING: a reader
  relies on a check that does not exist.*
- **It misleads into action** — an operator or agent following the record would do the wrong thing.
  *A measurement table assigning a probe a question it cannot answer → WARNING: the next operator
  runs it and records a fact it cannot produce.*

Everything else about a record — an imprecise count, a narration that stopped one revision short, a
phrasing that could be truer — is a NOTE. These findings are **correct**; the bar governs *severity*,
never *suppression*. Raise it and name the surface; the builder dispositions it.

**Diminishing-returns signal.** Round 1 finds defects in the *work*. By round 3 a pass is typically
finding defects in the *record of round 2* — true, confidently rated, and worth less than the round
costs. When every finding is about prose written to close the previous pass's findings, that is the
signal to **stop reviewing** — disposition what you have and end the loop, rather than writing a
better paragraph for the next pass to find. Stopping is not filing: most of that round's findings
are ACCEPTs, and saying so takes a clause each.

**Last chunk of a `Type: cumulative-final` plan — one review, not two.** Commit the chunk, then run `/prawduct:critic cumulative` ONCE: that single review serves as both the chunk's review and the PR-gate evidence. Don't run a separate `final` first — cumulative runs the same 7 goals plus cross-checks over `merge-base...HEAD`, a scope that already contains the chunk's diff, so a preceding `final` re-pays 4-10 minutes for assurance the cumulative re-derives. Mode inference implements the sequencing: with the last chunk's work still uncommitted, `/prawduct:critic` infers `final` (the right mid-chunk look); once committed and clean, it infers `cumulative` — the at-commit review. Post-cumulative fixes take a `verify-resolutions` pass, not a second full one — its fact extends coverage over the fix delta.

## Final-Mode Cross-Checks

After the goal-based review in `final` mode, run two additional passes that `chunk` mode skips. **`final`/`cumulative` is the owner of both cross-checks** — the PR reviewer does not re-run them (see `skills/pr/review-protocol.md`), so each runs once per PR:

### Learnings Cross-Check

Scan your findings against active learnings. If a change reintroduces a pattern `.prawduct/learnings.md` explicitly warns against, escalate severity — tolerating regression undoes the learning. Conversely, if learnings reference patterns the changed code handles correctly, no finding is needed.

### Backlog Reconciliation

**Check the backend first.** Read the top-level `backlog_service_repo` scalar from
`.prawduct/project-state.yaml`. If it is **set**, this project's live backlog is GitHub Issues and
`.prawduct/backlog.md` is frozen history — **skip this walk and all of C-B1–C-B4**, and emit one
NOTE: "Backlog reconciliation unavailable — this project is on the GitHub Issues backend and these
checks have no Issues-mode path yet; they return when the backlog read-through cache lands." Do **not** open
`.prawduct/backlog.md` for live state in that mode: every item archived at cutover still parses as
open, so the walk would emit confident findings about items closed months ago while missing every
live Issue. A stated gap is recoverable; a confident wrong answer is not.

If it is **unset** (the markdown backend), run the walk as written below.

Read `.prawduct/backlog.md`. For each open item, check whether this session's changes resolve it — directly or incidentally. For each resolved item, emit a **NOTE**: "Backlog item appears resolved: [item text]. Verify and archive it now, on this branch — `/prawduct:backlog update <id> status=shipped closed-by=<scope>` — so it ships in this PR." Do not change status yourself — the framework never infers status; the builder makes the explicit call.

**Backlog hygiene checks (C-B1–C-B4 — all NOTE-level, never BLOCKING)** — four soft signals (`/prawduct:backlog` is the fix path for each):
- **C-B1 — missing metadata:** a new backlog item in the diff with no metadata bar → NOTE the structured format.
- **C-B2 — no dedup evidence:** a new item whose `area:` already has ≥3 items → NOTE "check [the existing IDs] for overlap (`/prawduct:backlog dedup`)."
- **C-B3 — missing hygiene step:** the diff touches an area with open items but no chunk reviewed/updated them → NOTE "open items in area X — assess and update status."
- **C-B4 — dangling ID:** a build plan / change-log / chunk body references `PFX-XXXX` with no such item → NOTE (typo or not-yet-filed forward reference).

These flag; they never adjudicate whether an item "really" closed (the builder's call) and never block.

### Record-Lint — the checks the machine already ran

`prawduct-hook critic-begin` runs a deterministic pass over the changed **records** (markdown; the
archive excluded) and writes the result into the dispatch manifest as `record_lint`. Read it. Do not
re-derive any of it, and do not recount anything it counted — re-deriving a machine-checked number
is how a record defect buys a review round, which is the cost this exists to remove.

The suite-total tripwire reads only the lines a change **added**, so a change-log with years of
history in it reports on the entry just written and nothing else. Severity per check:

| `check` | Means | Severity |
|---|---|---|
| `chunk-ref-missing` | A deliverable the reviewed chunk *declares* does not exist | **BLOCKING** |
| `governed-by-gap` | A plan disposes of fewer norms than the cited artifact's `## Direction` carries, or cites an artifact that does not exist | **WARNING** (Goal 2 — the paperwork arm below) |
| `suite-total-claim` | A suite-total test claim in durable prose — the store already records pass/fail per tree | **NOTE** |

**Under the coordinator pattern, whoever holds Goal 2 raises every one of these** — including the
`suite-total-claim` NOTE, which would otherwise sit in Goal 4. The manifest is named in Goal 2 and
only that reviewer reads it, so splitting the findings by their natural goal loses them.

**`unchecked` is not a pass, and one entry is BLOCKING.** Each entry names a check that could **not
run** and why. A `chunk-ref-missing unchecked` line is the old `verify-chunk-refs` `cannot-verify:`
exit and keeps its severity — **BLOCKING**, because a deliverable check that could not run is
indistinguishable from one that passed, and habituation to that silence is what BLD-5J8N cost.
Every other `unchecked` entry is a **NOTE** you must still state in your summary. Two entries name
an *assumption* rather than a failure: record-lint graded a chunk inferred from build-plan Status
(Status names the first UNCHECKED chunk, so it may be the next one), or the whole pass crashed and
the review proceeded without it. Both mean **no answer**, not a clean one.

**`chunk_graded`** names whose deliverables were checked. A zero count is an answer about that
chunk; if it is `null`, nothing was checked at all.

Record-lint is **advice**: it reports to the builder and gates nothing. Its findings are yours to
raise at the severities above, and its per-check counts ride into the review fact so the control's
own yield stays measurable — which is also how a check that never catches anything gets retired.
Two checks (`dangling-ref`, `unknown-backlog-id`) were built, measured at zero true positives, and
removed before this shipped.

### Governing-Artifact Reconciliation

When the plan declares `governed_by:`, verify each listed artifact carries a recorded disposition
**for each of its Direction norms** (`conforms` | `ruling needed` | `exception` | `amendment
proposed` | `inapplicable because X`). A governing norm with no disposition line means
applicability was **assumed, not recorded** (`/prawduct:methodology norms`, "Applicability is recorded, not
assumed") → **WARNING** (Goal 2). This arm grades only the missing planning *paperwork*: an actual
departure, amendment, or `## Direction` edit without a recorded decision is the Authority Rule's
territory and stays **BLOCKING** via Goal 3 — never downgraded to this WARNING. A plan with no
`governed_by:` field in a product that already carries `## Direction` sections is itself the gap →
**NOTE** recommending the `prawduct-hook jurisdiction` seed.

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

Every review cycle must produce a record — governance without an audit trail is documentation fiction. Every mode records the same way: `critic-begin` writes the dispatch manifest (code), the reviewer(s) write partials, and `prawduct-hook critic-consolidate` appends the review fact to the evidence store and regenerates `.prawduct/.critic-findings.json` from it. No model writes the manifest, the findings file, the store, or the ledger — a clean pass persists an empty findings array through the same path (see `review-protocol.md` "Review Execution").

**Dispatch manifest** (`.prawduct/.critic-partials/manifest.json`, written by `critic-begin`; schema/validators in `lib/critic_consolidate.py`). Keys: review `id`, `mode` (verbose string), `mode_chosen_by` (the `infer-critic-mode` rationale, relayed via `--chosen-by`), `roster` + `roster_chosen_by`, `commit_reviewed` (HEAD at dispatch), the review interval (`base_tree`/`head_tree` + commits), `files_changed`/`files_reviewed` (derived from the interval), and the relayed telemetry `tier`, `scope`, `chunk`, `base_reviewed`. `critic-consolidate` refuses to persist unless every roster role reported a valid partial at the manifest's `commit_reviewed`.

**The findings cache is a derived view.** `.prawduct/.critic-findings.json` is regenerated from the newest review fact and carries its `fact_id`; builders and briefings read it for *content*, and no gate reads it — gates compose over the store.

### The Governance-Event Ledger

The ledger (`.prawduct/.governance-ledger.jsonl`, gitignored) is the append-only telemetry history: `critic-consolidate` appends one `review.critic` event per consolidated review (the PR skill appends `review.pr` the same way). `prawduct-hook ledger-append` is the **single writer** — it validates the record and computes the envelope; agents never hand-author JSONL. No gate reads the ledger; `prawduct-hook review-stats` aggregates it.

Each line is one event with an envelope/payload split:

```json
{"schema_version": 1, "event": "review.critic", "ts": "...Z",
 "duration_seconds": 180, "project": "my-product", "scope": "my-feature",
 "chunk": "02", "actor": {"role": "critic", "model": "opus"},
 "git": {"head": "<sha>", "base": "origin/develop"},
 "review": { ...the findings record verbatim... }}
```

The envelope is shared by every event kind; the kind-specific payload nests under a family-named key (`review` for `review.critic` and `review.pr`). Consumers key on the envelope and **skip unknown event kinds and fields** — later kinds join without schema change. `duration_seconds` and `actor.model` are nullable, never invented; `scope` is the build-plan feature key (passed explicitly; `active_build_plan` is only the fallback). Every line is self-contained; a long-lived repo can truncate oldest lines.
