---
artifact: build-plan
version: 1
scope: session-boundary-events
depends_on:
  - artifact: architecture
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms, and this plan STRENGTHENS it: the critic-active marker sweep is deliberately kept on the orientation path (a session that died took any in-flight review with it, so a marker surviving a resume is stale by construction), while the session-mutating half is what `resume` stops running"
      - "authority fails closed; advice fails soft → conforms. Nothing here is a gate. The one place it bites: the session-end Critic gate's jurisdiction is derived from state this plan stops resetting, so the gate gets *wider* on resume, never narrower — a change in the fail-closed direction"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state → conforms; the only new write is one line inside an existing `.prawduct/` file"
      - "local-first governance coordination, zero-dependency limb → conforms; stdlib only, no manifest change. Network/daemon limb inapplicable — this plan adds no network surface"
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
- `[ASSUMPTION: a `.critic-active` marker surviving into a resume is always stale | MED impact]`
  Reasoning: an in-flight review dies with the process that dispatched it, so a marker that outlives
  the session cannot correspond to a live reviewer. If false, sweeping on resume would clear a guard
  that is still doing its job.
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
reflection.

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
| sweep a stale `.critic-active` marker | archive + delete `.session-reflected` |
| untrack accidentally-committed session files | delete + recapture `.session-start`, `.session-git-baseline`, `.session-base-tree` |
| warn on the previous session's unmet gates | delete `.gates-waived` |

The axis is **not** read-only vs. mutating — orientation refreshes caches and repairs stale markers.
It is *orientation* vs. *destruction of session-scoped evidence*.

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
meaning "a genuine hook invocation, so sweep the critic-active marker", which both paths want.

`[DECISION: the critic-active marker sweep stays on the orientation path | because a review is
dispatched by a process, so an in-flight review dies with the session that died; a marker outliving a
session cannot correspond to a live reviewer, and resume is currently what rescues an operator from a
crashed Critic. Dropping the sweep would trade a loud bug for a 30-minute wedge | user can ask for the
sweep to be boundary-only]`

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
the Critic gate's jurisdiction, which is the very bug this chunk removes. An absent anchor already has
a documented degradation (freshness gates fail closed; the base-tree falls back to HEAD's tree), and
failing closed is the direction this plan committed to. The edge is real but rare — it is the
mid-cycle worktree entry `building.md` already names | user can ask for create-if-absent]`

**Done when:**
1. A simulated resume leaves `.handoff-notes.md`, `.session-reflected`, `.session-start`,
   `.session-git-baseline` and `.session-base-tree` untouched, and writes no handoff. Regression test
   pins the case reproduced in SCN-5B8Q.
2. The same invocation still emits the briefing, refreshes advisories, and sweeps a stale
   `.critic-active`.
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

**Done when:**
1. A generated handoff records when it was written and the HEAD it was written at.
2. The briefing distinguishes a fresh handoff from a stale one in words an agent will act on.
3. An old handoff is still offered, never withheld.
4. Full suite green; `/prawduct:critic` passes with no blocking findings.

## Verification Strategy

The subject is a cross-session behaviour that unit tests cannot reach, and the whole reason this
defect survived is that nobody exercised the real path:

1. **Verify the load-bearing assumption first** — start a session, do work, `--resume`, and confirm
   the transcript is restored. If it is not, stop and revisit Chunk 01's premise.
2. In a scratch clone: work, resume, and confirm notes/reflection/anchors survive and the briefing
   still renders.
3. Repeat with a stale `.critic-active` present and confirm resume still clears it.
4. Confirm `startup` and `clear` are unchanged by running a real chunk close through them.

## Governance Checkpoints

- **After Chunk 01** — re-ask the question that produced this plan: with the trigger correct, does the
  handoff *pair* still feel wrong? The hypothesis is that most of the discomfort was downstream of the
  trigger. If it survives the fix, that is evidence for a real redesign and the evidence will be
  better than it is today.
- **Before Chunk 02** — confirm with the owner that reporting age is enough, given that nothing
  currently deletes a handoff. If the answer is "it should also expire," that is a different chunk.
