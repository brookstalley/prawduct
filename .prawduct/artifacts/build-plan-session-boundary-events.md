---
artifact: build-plan
version: 1
scope: session-boundary-events
depends_on:
  - artifact: architecture
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms, and this plan STRENGTHENS it: the session-mutating half is what `resume` stops running, and the critic-active marker sweep is now BOUNDARY-only (review R-1/R-6 — the 'stale by construction' premise holds only for a session that ended; `compact` is in-process and `fork`'s parent is often still live, so sweeping there would disarm this very norm's enforcement plus the Stop hook's abandoned-review backstop)"
      - "authority fails closed; advice fails soft → conforms. Nothing here is a gate. The one place it bites: the session-end Critic gate's jurisdiction is derived from state this plan stops resetting, so the gate gets *wider* on resume, never narrower — a change in the fail-closed direction"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state → conforms; the only new write is one line inside an existing `.prawduct/` file"
      - "local-first governance coordination, zero-dependency limb → conforms; stdlib only, no manifest change. Network/daemon limb inapplicable — this plan adds no network surface"
  - artifact: api-contract
    dispositions:
      - "additive-first evolution; existing flag names and exit-code meanings never repurposed → conforms. `--brief-only` is a NEW flag; `clear --session-start` keeps its meaning and its behavior on `startup`/`clear` is unchanged (pinned by the pre-existing tests passing untouched). What changed is which SOURCES the hook routes down which path — a hooks.json wiring change, not a repurposed flag. Exit codes are untouched: 0 normally, 2 for the arg guard and the critic-active refusal"
      - "whole-surface semver; the internal CLI carries no per-subcommand version → conforms, nothing to version. The persisted-data limb is inapplicable — this plan changes no evidence-store schema"
      - "exit codes are the contract; errors attributed, never raised as stack traces across the boundary → conforms and extends: both new failure paths (`.session-reflected` unarchivable, absent base-tree anchor) print an attributed `NOTE:` and return 0 rather than raising, holding the never-block-session-start posture"
  - artifact: observability-strategy
    dispositions:
      - "severity-prefix vocabulary + stdout/stderr channel split → conforms. Both new signals use the `NOTE:` prefix and go to **stderr**, the user-and-diagnostics channel: each is operator-actionable (archive the file by hand; `/clear` in this worktree to anchor it) rather than something the agent acts on. This matches the sibling notice the boundary path already emits for the same narrowing"
      - "emitted text names no prawduct-internal identifier → conforms; both new messages carry the plain-language reason and no id (verified by grepping added lines for id-shaped tokens outside comments). The ids stay one line away in comments, tests and this plan. The pre-existing `(CRT-3X9D)` in the critic-refusal message is NOT touched by this changeset, so under the norm's interim rule it waits for OBS-7M4D rather than being swept here"
      - "single ledger writer → inapplicable; this plan appends no ledger event"
  - artifact: security-model
    dispositions:
      - "untrusted governance state — backlog, learnings, recalled memories, fetched references, PRIOR-SESSION HANDOFFS — is data, not instructions; malformed state fails soft (skip + attribute), never executes → conforms. This plan adds no new channel; it changes WHEN the existing one is consumed. The fail-soft posture is preserved and extended — the two new failure paths (`.session-reflected` unarchivable, absent base-tree anchor) print an attributed `NOTE:` and return 0, and the boundary/continuation split makes a resumed session destroy LESS untrusted state, never more. Recorded retroactively during the SCN-5B8Q Chunk 01 cumulative: the norm names this bundle's exact subject and applicability had been ASSUMED, not recorded. Probable cause worth noting so it does not recur — `work_model_index.jurisdiction_candidates` harvests headings, bold and declared vocabulary, and 'prior-session handoffs' appears as plain body prose, so the seeder could not surface this artifact."
last_validated: 2026-07-27
---

## Requirements Confidence

**Level:** High

**Why:** The defect is reproduced, not inferred — a scratch-repo run showed `claude --resume`
deleting `.handoff-notes.md` and `.session-reflected` mid-session and writing a handoff for a
session that had not ended. The fix shape was derived by enumerating what `cmd_clear` actually does
and asking which half a *continuation* needs; the owner independently rejected the cheaper
alternative on evidence (the session briefing has observed value, so the orientation half must keep
firing on every source).

**Open assumptions / unknowns:**

- ~~`[ASSUMPTION: `--resume`/`--continue` restore the conversation transcript, so a resumed session has
  NOT lost context | HIGH impact | verifiable in one session]`~~ **VERIFIED 2026-07-27.** Exercised
  end-to-end, not reasoned about: a headless session was given the codeword `QUILLFROST-8842`, then
  resumed by session id; the resumed session returned the codeword, which exists nowhere but the
  prior transcript. `--fork-session` returned it too. The premise holds and Chunk 01's shape is
  unchanged. The same probe logged the SessionStart payload and confirmed `source: "resume"` fires
  with the **same** session id, so the matcher split is mechanically viable.
- ~~`[ASSUMPTION: a `.critic-active` marker surviving into a resume is always stale | MED impact]`
  Reasoning: an in-flight review dies with the process that dispatched it, so a marker that outlives
  the session cannot correspond to a live reviewer. If false, sweeping on resume would clear a guard
  that is still doing its job.~~ **FALSIFIED by the Chunk 01 review** — and the assumption's own
  closing sentence named the consequence correctly. It holds for `resume`, but the matcher that
  carries `resume` also carries `compact` (which fires mid-session, *in-process*) and `fork` (whose
  parent session is frequently still running), so on those the marker is likely **live**. The sweep is
  now boundary-only; see the replacement DECISION in Chunk 01.
- `[ASSUMPTION: `compact` should receive the orientation half | MED impact | owner can veto]`
  It receives none today. Compaction is the one source where context genuinely *was* just lost, so a
  briefing is arguably most valuable there — but it also fires mid-session, potentially often, and
  the briefing is not free.
- `[ASSUMPTION: `fork` should receive the orientation half, on the same reasoning as `compact` | MED
  impact | owner can veto]`
  **Found during the verification above, and this plan was written without it.** There are **five**
  SessionStart sources, not four: `startup`, `resume`, `clear`, `compact`, **`fork`** (`--fork-session`
  with `--resume`/`--continue`, `/fork`'s background copy, `/branch`). Verified empirically — `fork`
  fires with a **new** session id and a **restored** transcript. It is therefore a continuation by the
  same test as `resume`, and the *most* dangerous source to hand a boundary reset to: the parent
  session may still be running, so resetting would destroy a **live** session's evidence rather than a
  finished one's. Today it gets nothing (the matcher is `startup|resume|clear`), so covering it is a
  gap closed, not a regression fixed.

## Status

<!-- views_enabled: true — these checkboxes are a DERIVED VIEW (lib/views.py). Do not hand-flip.
     Each chunk lands a change-log entry tagged `chunks=NN | scope=session-boundary-events` with
     NO `status=`; the release stamps `status=shipped` and regen-views flips the box. The
     `Context:` BLOCK below — from `Context:` to the end of this section — is author-curated and
     regen never touches it. -->

- [ ] Chunk 01: Orientation and boundary become separate acts
- [ ] Chunk 02: The handoff carries its vintage

Context: Plan written 2026-07-27 on the back of `session-handoff-continuity` Chunk 03, which fixed
the handoff's *content* and left its *trigger* wrong. Parent: **SCN-5B8Q**. Separate plan rather
than a chunk of the continuity plan because the subject is different — that plan is about what the
handoff says, this is about the session model underneath it — and folding it in would make that
plan's Success criteria retroactively wrong while blocking its chunks 04–05 on unrelated work.

**One correction already folded in, so nobody re-derives it.** SCN-5B8Q was first filed claiming the
base-tree reset "blinds the Critic gate." That was overstated: `gates.session_review_verdict`'s
docstring already documents the committed-but-unreviewed case as a deliberate degradation, and
`check_cumulative_critic` independently demands merge-base → HEAD coverage before any PR, so the
merge boundary catches what the session gate misses. Per-chunk review facts **compose over trees** —
which is exactly why the framework does not re-review the cumulative stack on every commit, and why
demanding session-base coverage no dispatchable review can produce would only train waivers. What
survives is smaller and is this plan's concern only in passing: the session-end gate *silently
narrows* its own jurisdiction on resume, and that narrowing is not among the degradations the
docstring enumerates. Chunk 01 removes the narrowing as a side effect of not resetting the anchor.

**Chunk 01 is DONE (2026-07-27).** Verification Strategy steps 1–4 were all exercised against the
real CLI, not simulated. Step 1 confirmed the load-bearing assumption *and* turned up `fork`, a fifth
source this plan was written without — the design changed as a result (see the assumption block and
Chunk 01's DECISION). Steps 2–4 ran in a scratch git repo wired to the real `hooks.json`: after a
genuine `claude --resume`, all six session-scoped files were byte-identical, the handoff was not
regenerated, the forward notes were not consumed, and a stale `.critic-active` was still swept; a
control run confirmed a genuine boundary still consumes notes, clears waivers and archives the
reflection. **(The sweep observation was true of the code as it stood that hour and is no longer what
ships** — the review made the sweep boundary-only, and the fixed build was re-verified end-to-end: a
real `claude --resume` now *preserves* a live marker. Recorded rather than deleted, because it is the
observation that made the reversal findable.)

**One finding worth carrying forward.** The first end-to-end attempt *failed* — and the cause was the
environment, not the code: the plugin is installed user-scoped from `~/source/prawduct` at `main`,
whose matcher is still `startup|resume|clear`, so the old hook fired alongside the new one. That run
is therefore the defect reproduced end-to-end on shipped code with the real CLI. The clean run needed
`CLAUDE_CONFIG_DIR` isolation. **This is not a fix that takes effect for this repo's own sessions
until the branch merges and the installed plugin updates** — until then, every `claude --resume` here
still destroys session evidence.

Chunk 02 is next, and its Governance Checkpoint (confirm with the owner that *reporting* handoff age
is enough) is unchanged.

## Problem, Success, Scope

**Problem.** `cmd_clear` does two categorically different jobs under one entry point, and its
SessionStart matcher (`startup|resume|clear`) cannot tell them apart:

| Orientation — what a live agent needs | Boundary reset — what ends a session |
|---|---|
| render the session briefing | generate `.session-handoff.md` |
| refresh advisories | consume + delete `.handoff-notes.md` |
| untrack accidentally-committed session files | archive + delete `.session-reflected` |
| the state-size and preferences checks | delete + recapture `.session-start`, `.session-git-baseline`, `.session-base-tree` |
| generate the subagent briefing | delete `.gates-waived` |
| | **sweep a stale `.critic-active` marker** |
| | **warn on the previous session's unmet gates** |

**This table's first draft put the last two rows in the LEFT column, and that was the chunk's central
error** (review R-1/R-4/R-6, found independently by two reviewers). They destroy nothing, so a sort by
"does it destroy evidence" files them under orientation — but both *interpret* session state as
belonging to a session that has **finished**, which only a boundary guarantees. The real taxonomy is
three-way, not two, and the middle category is invisible to the axis this table was built on:

1. **Destructive boundary acts** — the right column's original five rows.
2. **Boundary-dependent readers** — the two bolded rows. Read-only, and still boundary-only.
3. **Orientation** — the left column. Safe on every source.

~~The axis is **not** read-only vs. mutating — orientation refreshes caches and repairs stale markers.
It is *orientation* vs. *destruction of session-scoped evidence*.~~ **Both halves are pre-reversal.**
The "repairs stale markers" example is the behaviour that just moved columns, and the
destruction-based axis is the one the paragraph above calls the chunk's central error. The correct
statement is the three-way split, not a better two-way one.

`resume` is a **continuation**: the transcript is restored and nothing was lost. It needs the left
column and must not get the right one. Today it gets both. Reproduced end-to-end: after a simulated
resume, the forward notes were deleted (folded into a handoff for a session still running), the
reflection was archived away mid-session, and the session anchors were re-captured.

`compact` gets *neither* column — it is excluded from this hook entirely — which is backwards, since
compaction is the one source where context genuinely was just lost.

**Success.**
1. `claude --resume` destroys no session-scoped evidence: forward notes, reflection, and all three
   session anchors survive a continuation intact.
2. A resumed session still receives the full briefing, refreshed advisories, and the stale-marker
   sweep — the half whose value the owner confirmed from repeated observation.
3. `compact` receives orientation.
4. A handoff never presents itself as current when it is not (Chunk 02).
5. No gate semantics change except in the fail-closed direction; full suite green; `/clear` is never
   blocked or slowed by any of this.

**Out of scope** (named, not silently dropped):
- Whether the handoff *pair* is the right shape at all. The working hypothesis is that most of the
  discomfort with it is downstream of the trigger being wrong, so it is cheaper to fix this and
  re-ask than to redesign now. Re-ask at the governance checkpoint.
- The unbounded-unreadable-note survival path and the append-to-a-marked-handoff gap (SCN-2M6P) —
  both already named in `architecture.md` and neither is caused by the trigger.
- `git_derived`'s missing consumer (SCN-6V3D).

## Surfaces This Plan Touches

| Surface | Why | Guard |
|---|---|---|
| `plugin/hooks/hooks.json` | the matcher split — two entries where there is one | `test_plugin_methodology_digest.py::TestDigestWiring` + new |
| `plugin/bin/prawduct-hook` | `cmd_clear` gains `--brief-only`; the arg guard's allowed set | runtime tests |
| `plugin/lib/briefing.py` | Chunk 02's vintage line | unit tests |
| `plugin/methodology/building.md` | "Sessions and Work Cycles" says what a boundary is | **budget <4600, currently 4595 — 4 tokens of headroom** |
| `.prawduct/artifacts/architecture.md` | the session-boundary definition is architectural | — |

## Build Chunks

### Chunk 01: Orientation and boundary become separate acts
**Type:** code

Split by matcher, not by parsing the event payload — the matcher already carries the one fact needed,
and today's config throws it away by lumping `resume` in with `startup`:

```
matcher: "startup|clear"           → prawduct-hook clear --session-start
matcher: "resume|compact|fork"     → prawduct-hook clear --session-start --brief-only
```

Together these **exhaustively partition** all five documented sources — that property, not the
literal strings, is what the test pins (Done-when 4).

`[DECISION: `fork` joins the orientation matcher | because it restores the transcript (verified), so
it is a continuation by the same test as `resume` — and because a fork's parent session is often still
alive, making a boundary reset there destroy evidence belonging to a *running* session. The three
orientation-only entries (banner, digest, build-index) gain `fork` for the same reason: a forked
session that receives no governance context at all is the same defect one level down | user can ask
for fork to be left uncovered]`

`--brief-only` is orthogonal to `--session-start` rather than replacing it: `--session-start` keeps
meaning "a genuine hook invocation" — as opposed to a reviewer subagent's bare `clear`, which the
CRT-3X9D guard refuses — so the boundary is `--session-start` *without* `--brief-only`. (This
sentence originally ended "so sweep the critic-active marker, which both paths want"; the review
reversed that — see the struck DECISION below.)

~~`[DECISION: the critic-active marker sweep stays on the orientation path | because a review is
dispatched by a process, so an in-flight review dies with the session that died; a marker outliving a
session cannot correspond to a live reviewer, and resume is currently what rescues an operator from a
crashed Critic. Dropping the sweep would trade a loud bug for a 30-minute wedge | user can ask for the
sweep to be boundary-only]`~~

**REVERSED by the Chunk 01 review (R-1 + R-6, reached independently by two reviewers).** The premise
is true only for `resume`. `compact` fires **mid-session, in-process**, and `fork`'s parent is
frequently still running — a fact *this plan's own `fork` DECISION states three paragraphs up. The two
decisions contradicted each other and were written in the same sitting.* So a marker seen on those
sources is very likely **live**, and sweeping it disarms both the CRT-3X9D guard and the Stop hook's
abandoned-review backstop (which keys on the marker's presence) while a reviewer is genuinely working.
Compaction previously ran no `clear` hook at all, so the exposure was **new in this bundle**.

`[DECISION: the critic-active marker sweep is BOUNDARY-only | because the "stale by construction"
premise holds only for a session that ended, and the asymmetry is decisive: sweeping a live marker is a
silent governance failure, while leaving a dead one costs at most the 30-minute TTL with `--force` and
`rm` as loud documented overrides. A crashed Critic is now rescued by the next real boundary rather
than by a resume | user can ask for resume-only sweeping if the TTL wait proves painful]`

**The category this exposed.** The split's first cut sorted statements by *does it destroy evidence*.
That missed a third kind: statements that destroy nothing but **interpret session state as belonging to
a finished session**. Two qualify — the marker sweep, and `_check_previous_session_gates` (R-4), which
reads `.session-reflected`/`.gates-waived`/the change baseline and would report the *running* session
as a previous one with unmet gates, repeatedly under `compact`. Both are now boundary-only. However
read-only such a statement looks, it is not orientation.

Scope the change **by pattern, not line number**: enumerate every statement in `cmd_clear` and assign
it to a column before editing. The table in Problem is the inventory; verify it against the code
rather than trusting it — it was written by reading, not by executing.

**Inventory verified against the code 2026-07-27.** All 17 statement blocks in `cmd_clear` were
enumerated and assigned; the Problem table is accurate. Useful structural finding: the six boundary
blocks form exactly **two contiguous regions** (handoff → consume notes → archive reflection → delete
the five session files → rewrite `.session-start`; and later, `.session-git-baseline` →
`.session-base-tree`). So this is a **two-site** change, not six, and the orientation blocks between
them keep their current relative order — which matters, because the briefing reads the advisory store
the probes refresh, and the handoff must be generated before the reflection it consumes is archived.

`[DECISION: `--brief-only` never writes a session anchor, not even when one is absent | because
"create if missing" would stamp a *resume-time* clock onto a session that started earlier — narrowing
the Critic gate's jurisdiction, which is the very bug this chunk removes. The base-tree falls back to
HEAD's tree. **Correction (PR review, 2026-07-27): this DECISION originally also claimed "freshness
gates fail closed" on an absent anchor. That is false — `gates.py:156` returns `True` ("no session
marker to verify") with the tree-validity clause unreachable on that path, so the freshness gate fails
OPEN.** The decision stands on its first leg alone (do not stamp a resume-time clock); do NOT read it
as resting on a safe absent-anchor state, because that state is weaker than this plan assumed. Tracked
as STH-6D4Q. The edge is real but rare — it is the mid-cycle worktree entry `building.md` already
names | user can ask for create-if-absent]`

**Done when:**
1. A simulated resume leaves `.handoff-notes.md`, `.session-reflected`, `.session-start`,
   `.session-git-baseline` and `.session-base-tree` untouched, and writes no handoff. Regression test
   pins the case reproduced in SCN-5B8Q.
2. The same invocation still emits the briefing, refreshes advisories, untracks committed session
   files, and runs the size/preferences checks. It does **not** sweep `.critic-active` and does **not**
   run the previous-session gate check — those interpret session state as a finished session's and are
   boundary-only (review R-1/R-4/R-6). A boundary still does both.
3. `startup` and `clear` behave exactly as today — pinned by the existing tests passing unchanged.
4. `compact` and `fork` receive orientation. The test asserts the **partition property** over a
   pinned roster of all five documented sources — every source is covered by exactly one of the two
   entries — rather than spot-checking one string. A future source is then a *test failure* instead of
   a silent hole. (Honest limit, written into the test: the roster is a local pin of an external fact,
   so it cannot *discover* a sixth source Claude Code adds — it can only keep the five we know
   partitioned. The doc URL and verification date go in the pin.)
5. `--brief-only` is in the arg guard's allowed set, appears in the usage string, and is rejected
   nowhere it should be accepted.
6. `test_clear_matcher_excludes_compact` is **replaced, not relaxed**: the invariant it protects (no
   boundary reset on compaction) still holds, and the successor asserts it more precisely — the
   boundary entry must exclude `resume` and `fork` too, which the original never checked.
7. Full suite green; `/prawduct:critic` passes with no blocking findings.

### Chunk 02: The handoff carries its vintage
**Type:** code

`.session-handoff.md` carries no timestamp and is **never deleted** — only overwritten, and only when
the render is non-empty. So a session that produces nothing leaves the previous handoff in place while
the briefing still announces "Previous session context available", with nothing to distinguish a
handoff written minutes ago from one written last month.

Stamp the generated handoff with when and at what HEAD it was written, and have the briefing say so
when it is old. Both halves are needed: the stamp alone is invisible to an agent that only reads the
briefing line.

`[DECISION: age is reported, never acted on | because the handoff is advice and the ratified norm is
"advice fails soft" — a stale handoff must still be offered, with its age, not suppressed. Suppression
would turn a visible weak signal into an invisible absent one | user can ask for a staleness ceiling]`

**Requirement added 2026-07-27 (owner, post-Chunk-01): the pointer must know it is speaking to a
continuation.** `assemble_session_briefing` emits "Previous session context available" on **pure file
existence** — no source awareness, no vintage. Chunk 01 deliberately gave continuations the *full*
briefing (Success #2), which means a `resume`/`fork` session is now pointed at a handoff describing the
boundary *before* its own session — context it already holds in full, and which the parent has since
worked past. The pointer is boundary-scoped; the briefing that carries it is not.

The line splits three ways, not two:

| source | context state | the pointer is |
|---|---|---|
| `startup`, `clear` | fresh | correct — this is its job |
| `resume`, `fork` | fully restored | redundant, and points at superseded state |
| `compact` | genuinely lost | *wanted*, but this is the wrong artifact |

`fork` is the sharp case: the parent is often still running, so two live sessions read one pointer and
the drift is however long the parent has worked, not one boundary. `compact` is the interesting one —
the only continuation with real context loss, so it wants a bridge, but the pre-session handoff
describes the wrong side of the boundary and compaction can fire repeatedly in one session.

**This reframes the chunk.** Age was the planned signal; **applicability** is the stronger one —
"you are a continuation, this predates your session" beats "this is 6 days old", because age is a proxy
for the fact and source *is* the fact. Report both; lead with source. Suppression stays rejected
(advice fails soft): the handoff is still offered, the line just stops implying it is news.

`[ASSUMPTION: `compact` keeps the pointer, labelled, rather than gaining a new mid-session artifact |
MED impact | owner can veto]` Building the thing compaction actually wants — a bridge describing what
*this* session has done since its boundary — is a different feature, and the Out of Scope note about
re-asking whether the handoff *pair* is the right shape is where it belongs.

**Interface consequence — read this before starting Chunk 02.** `--brief-only` carries
*continuation vs. boundary* and nothing finer; `resume`, `compact` and `fork` all arrive through it
indistinguishably. Chunk 01 needs no more than that, but the three-way table above does. Two ways to
get the source, and they are not equivalent:

- **Split the orientation matcher** into `resume|fork` and `compact`, each passing its own flag. Keeps
  the "matcher carries the fact" design and stays free of payload parsing. Note this **breaks
  `test_exactly_one_boundary_and_one_orientation_entry` by design** — generalize it and the partition
  test to N entries rather than reading the failure as a regression.
- **Parse `source` from the hook's stdin JSON.** More precise and future-proof against a sixth source,
  but it is the payload parsing Chunk 01 deliberately avoided, and it puts a JSON read on the
  SessionStart hot path.

Recommendation: the matcher split, for consistency with Chunk 01 — unless Chunk 02 finds it needs the
source for something else too, at which point parsing earns its cost once.

Either way `assemble_session_briefing` must learn the distinction: today `cmd_clear` knows `brief_only`
and does not pass it, so threading it through is part of the chunk.

**Done when:**
1. A generated handoff records when it was written and the HEAD it was written at.
2. The briefing distinguishes a fresh handoff from a stale one in words an agent will act on.
3. **The pointer distinguishes a boundary from a continuation.** On `resume`/`fork` it says the handoff
   predates this session and the transcript already covers it; on `startup`/`clear` it reads as it does
   today. This is a *stronger* signal than age and the one to lead with.
4. An old handoff is still offered, never withheld — on every source, continuations included.
5. Full suite green; `/prawduct:critic` passes with no blocking findings.

## Verification Strategy

The subject is a cross-session behaviour that unit tests cannot reach, and the whole reason this
defect survived is that nobody exercised the real path:

1. **Verify the load-bearing assumption first** — start a session, do work, `--resume`, and confirm
   the transcript is restored. If it is not, stop and revisit Chunk 01's premise.
2. In a scratch clone: work, resume, and confirm notes/reflection/anchors survive and the briefing
   still renders.
3. Repeat with a stale `.critic-active` present and confirm resume **leaves it alone** — and that a
   real boundary (`startup`/`clear`) still clears it. ~~"confirm resume still clears it"~~ was the
   original step and is now **backwards**: running it as written would verify the regression as a
   success. The sweep became boundary-only in the Chunk 01 review, because `compact` fires in-process
   and `fork`'s parent is often still running, so a marker seen on a continuation is likely live.
4. Confirm `startup` and `clear` are unchanged by running a real chunk close through them.

## Governance Checkpoints

- **After Chunk 01** — re-ask the question that produced this plan: with the trigger correct, does the
  handoff *pair* still feel wrong? The hypothesis is that most of the discomfort was downstream of the
  trigger. If it survives the fix, that is evidence for a real redesign and the evidence will be
  better than it is today.
- **Before Chunk 02** — confirm with the owner that reporting age is enough, given that nothing
  currently deletes a handoff. If the answer is "it should also expire," that is a different chunk.
