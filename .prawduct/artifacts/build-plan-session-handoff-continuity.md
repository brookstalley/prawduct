---
artifact: build-plan
version: 1
scope: session-handoff-continuity
depends_on:
  - artifact: architecture
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms (the new notes file is written by the builder, never by a review agent; `clear` already refuses while `critic-active` is set, and that guard is untouched)"
      - "authority fails closed; advice fails soft → conforms, and this norm DECIDES a design question: the handoff is advice (no gate reads it), so neither generation nor the new false-success check may ever block `/clear` — both degrade to a note. See the [DECISION] in Chunk 03."
      - "local-first governance coordination, network/daemon limb → inapplicable because this plan adds no network surface"
      - "local-first governance coordination, zero-dependency limb → conforms; this plan DOES add code to the governance runtime, and it is stdlib-only (`subprocess`, `typing.NamedTuple`) plus internal lib siblings — no manifest change. Applicability is recorded, not assumed: disposing of a two-limbed norm wholesale on the limb that happens not to apply is how the applicable limb goes unchecked."
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state → conforms (the new file is `.prawduct/` session state, gitignored like its siblings)"
last_validated: 2026-07-26
---

## Requirements Confidence

**Level:** Medium

**Why:** The defects are measured, not inferred — every one was reproduced by running the
shipped parser against this repo's own live build plan (see Problem). What is *not* settled is
the shape of the forward channel: one new file vs. reusing `.session-handoff.md` as a
model-owned surface, and what the framework should do when substantive work happened and the
agent left no note.

**Open assumptions / unknowns:**

- `[ASSUMPTION: the forward channel should be a NEW model-owned file consumed into the generated
  handoff, rather than making `.session-handoff.md` itself model-owned | HIGH impact | user can
  override]`
  Reasoning: the generated handoff must exist even when the agent never writes (a user who
  `/clear`s without warning still gets continuity), so something must always generate it. Two
  owners for one file is the bug we are fixing. Cost of this choice: a second filename the model
  must learn, mitigated by Chunk 01's preservation net.
- `[ASSUMPTION: notes are consumed at `/clear`, not carried forward indefinitely
  | MED impact | user can correct]`
  A note written three sessions ago and never cleared would resurface as current intent.
  *Resolved in Chunk 01, and narrowed:* consumed yes, **archived no** — the note's text is already
  carried verbatim into `.session-handoff.md`, so a second growing file mirroring
  `.session-reflected` → `reflections.md` would have no reader. Consumption is transactional and
  keys on delivery, so a note that never reached the handoff is kept rather than cleared.
- `[ASSUMPTION: the "no forward note despite substantive work" signal is advisory, never blocking
  | MED impact | user can override]`
  Forced by the architecture's "advice fails soft" norm, not by preference — see the Chunk 03
  DECISION.
- `[ASSUMPTION: SCN-7K4B is not buildable in this plan and gets a design chunk instead | MED
  impact | user can veto and demand it be built]`
  It is `stage: design` with two sibling items (MET-8J5R, DOC-3V7T) that partition the same
  problem. The framework's own rule routes an early-stage item to discovery, not to code.

**What would raise confidence:** the owner ruling on the channel shape (one file vs two) — that
is the single decision the rest of the plan hangs from.

## Status

<!-- views_enabled: true — these checkboxes are a DERIVED VIEW (lib/views.py). Do not hand-flip.
     Each chunk lands a change-log entry tagged `chunks=NN | scope=session-handoff-continuity`
     with NO `status=`; the release stamps `status=shipped` and regen-views flips the box. The
     `Context:` line below is author-curated and regen never touches it. -->

- [ ] Chunk 01: The forward channel — a model-owned notes file, and a generator that stops destroying
- [ ] Chunk 02: Parser correctness — done-predicate, views_enabled, missing H1, truncated Context
- [ ] Chunk 03: Proactive close — write-at-chunk-close, the documentation surfaces, the soft signal
- [ ] Chunk 04: CRT-7P5J — the handoff's Critic summary composes resolution facts
- [ ] Chunk 05: SCN-7K4B — design only: program-level continuity, advance the item or defer it

Context: **Chunk 01 complete** (2026-07-26; `5e5b178` + `76f165c`, Critic-clean — 6 warnings
resolved across two passes, 0 blocking) — `.prawduct/.handoff-notes.md` is the model-owned forward
channel; the generator emits it first, carries a machine marker, and folds an unmarked
(hand-authored) handoff in rather than overwriting it. Consumption keys on **delivery**, not on "a
handoff was written" (the Critic's central catch — the proxy deleted an unreadable note whose text
reached nothing). Degraded paths split by audience: continuity facts to stdout where the incoming
agent reads them, housekeeping to stderr. The pair's
contract is recorded in `architecture.md` § "The one model-owned session file" — that is the
persisted-format enumeration Chunk 01 called for, and the answers are: nothing but the generator
reads the notes; per-worktree; unconsumed notes survive to the next `/clear`.

**Chunk 02 complete** (2026-07-27) — the read path feeding the handoff is correct at every
consumer. The git-derived "which chunk is current" derivation moved from `critic_mode` into
`buildplan_refs._parse_build_plan_status`, so the handoff, `verify-chunk-refs` (**closes
BLD-7K3Q**) and mode inference share one implementation; four functions took `project_dir` instead
of `prawduct_dir` because resolving "current" reads git and the call sites should say so. The
done-predicate is the named `build_plan_is_complete`, shared by `staleness_scan` and
`_get_active_work`. `description` falls back to frontmatter `scope:` then filename, so the work
section cannot vanish. Context is a block to the end of the Status section, which dissolves the
first-wins/last-wins question instead of answering it. **BRF-6K2D landed** with it (merge-aware
delete nudge). Live re-reproduction on this repo's own plan: description
`session-handoff-continuity`, current `Chunk 02`, context 2283 chars (was 85), `verify-chunk-refs`
and `infer-critic-mode` both resolving Chunk 02. Chunk 03 is next.

Two things the Chunk 02 Critic corrected, both recorded rather than absorbed:

**`views_enabled` completion is `[x]` OR committed, never commits alone.** The first cut counted
only commit subjects since base, so a plan whose earlier chunks shipped in a *prior* release — boxes
flipped, commits behind the base — resolved "current" back to an already-shipped Chunk 01: strictly
worse than the checkbox fallback the derivation promises never to be worse than. The union fixes it
and also stops a branch whose commits only *partly* follow the convention from treating a
half-populated set as authoritative. The residual fragility is narrower than first filed: with the
union, a branch that omits the convention entirely degrades to the checkbox reading (fail-soft), and
a partial one is corrected by the `[x]` half rather than trusted.

**`[DECISION: the governance-gate trigger keeps the CHECKBOX reading, and does not follow the git
derivation | because the two answer different questions — git answers "which chunk is in flight",
which is right for reporting and for `verify-chunk-refs`, while the gate asks "is there still
governed work", and a chunk's last commit lands BEFORE its Critic pass and its reflection. Routing
the gate through git switched the blocking reflection and Critic gates off for the whole
complete-but-unmerged window, which is exactly when the PR-fix and finding-resolution sessions
happen — a silent loosening against this plan's own Success #6 ("no gate semantics change"). Under
`views_enabled` a flipped box means *shipped*, so "unflipped" is the right reading of "still
governed" | user can ask for the gate to track in-flight chunks instead]` Pinned by
`TestGateSemanticsUnchanged`.

Plan written 2026-07-26 on `feature/session-handoff-continuity` (off develop). Parents:
**SCN-4H9T** (the upstream triage of discodon's STH-9FYI — five defects, all reproduced against
this repo's own live plan), plus **CRT-7P5J** and **SCN-7K4B**. All three touch
`generate_session_handoff`, which is why they are one plan and not three patches to one function.
Filing SCN-4H9T surfaced two more that belong here: **BLD-7K3Q** (same `views_enabled` root cause
at `verify-chunk-refs`) and **BRF-6K2D** (the adjacent half of the done-predicate work) — Chunk 02
closes the first and should land the second with it. **CRT-7B4M** is already shipped and is where
the correct derivation lives.

Four independent wrong-output defects in one generator is the argument for scoping it as one body
of work rather than four picks.

`active_build_plan` now points here. The plan previously claimed it "deliberately still points at
`build-plan-governance-prose-diet.md` (Chunk 04 pending)" — false on both halves, caught by the
Chunk 01 Critic: the pointer was `null` (cleared at the v2.1.8 release) and no artifact by that name
exists; `build-plan-prose-diet.md` does, and it is 3/3 complete. A null pointer with no
`artifacts/build-plan.md` fallback is exactly why this repo's own handoff carries no work section —
the defect class this plan fixes, reproduced by the plan's own stale prose.

## Problem, Success, Scope

**Problem.** Cross-session continuity is destroyed silently while the agent reports success. Five
defects, each reproduced against this repo's live plan:

1. `/clear` **unconditionally overwrites** `.session-handoff.md` (`briefing.py:921`, bare
   `atomic_write_text`). The only guard, `if len(sections) > 2`, preserves a model-authored
   handoff **only when the machine has nothing to say** — so it survives when it matters least
   and is clobbered in every session with real work. Intermittent, therefore unlearnable.
2. **No forward channel exists.** All five sources are backward-looking machine state.
   `reflection.md:63` tells the agent to "Complete handoff" — which reads as an action on the
   file — while the sole sentence documenting machine ownership is `building.md:120`. The
   learnings already carry the rule ("Session-end signals must come AFTER handoff",
   `learnings-detail.md:852`); what is missing is any place to put the handoff.
3. **No done-predicate.** `staleness_scan` (`briefing.py:150-157`) concludes "all chunks complete
   — delete the plan"; `_get_active_work` (`briefing.py:354-359`) reads the *identical* parse,
   applies no predicate, and stamps a finished plan as the next session's `**Task**`.
4. **`views_enabled` repos are systematically wrong — and the fix already exists, unswept.**
   `current_chunk` is "first `- [ ]`" (`buildplan_refs.py:188`), but where Status is a derived
   view that only flips at release, that reports the *first* chunk forever. Verified live: this
   repo returned `Chunk 01` with three chunks complete and committed. **CRT-7B4M already shipped
   the correct derivation** — `critic_mode._git_aware_progress` (`critic_mode.py:520`) — for the
   `infer-critic-mode` consumer only, and `buildplan_refs.py:126` even carries a comment pointing
   at it. `verify-chunk-refs` has the same bug (BLD-7K3Q, `stage: ready`). So this is one root
   cause at three consumers, fixed at one. A third local patch would be the wrong move.
5. **The work section silently vanishes, and Context is truncated.** `description` requires a
   `# Build Plan` H1; a frontmatter-style plan has none, so `_get_active_work` returned `{}` on a
   live four-chunk plan and the handoff omits the section entirely. Separately `context` is a
   `removeprefix` on one physical line, truncating the multi-paragraph block that `building.md`
   itself calls "the cross-session handoff" — and the loop has no `break`, so multiple `Context:`
   lines silently last-wins.

**Success.**
1. An agent can write forward-looking context that reliably reaches the next session.
2. A user who `/clear`s with no warning still gets a correct, useful handoff.
3. The handoff never labels completed work as active, never silently omits the work section, and
   carries the whole Context block.
4. At chunk close the agent writes notes proactively, so "anything to tell the next agent?" is
   answered from disk, not by a fresh synthesis run.
5. Resolved Critic findings no longer appear as outstanding (CRT-7P5J).
6. Full suite green; no gate semantics change; `/clear` is never blocked by any of this.

**Out of scope** (named, not silently dropped):
- Building SCN-7K4B's `active_program` machinery — Chunk 05 designs it and stops (see its
  DECISION). Its siblings MET-8J5R and DOC-3V7T stay untouched.
- Any change to what the *session briefing* renders beyond consuming the corrected handoff.
- The backlog-service/Issues backend path — this plan touches no backlog storage.

## Surfaces This Plan Touches

<!-- planning.md: enumerate up front — this introduces a project-wide concept (a model-writable
     state file), and several surfaces carry token-budget guardrail tests. -->

| Surface | Why | Guard |
|---|---|---|
| `plugin/lib/briefing.py` | generator, `_get_active_work`, findings summary | unit tests |
| `plugin/lib/buildplan_refs.py` | `_parse_build_plan_status`, `_current_chunk_id_from_status` | unit tests |
| `plugin/lib/critic_mode.py` | source of the reusable `_git_aware_progress` path (read, likely don't edit) | unit tests |
| `plugin/bin/prawduct-hook` | `cmd_clear` archival; new `handoff preview` | runtime tests |
| `plugin/lib/core.py` | session-file set (new file must be listed) | packaging tests |
| gitignore management | new session file must be ignored | `test_gitignore_management.py` |
| `plugin/methodology/building.md` | chunk-close sequence + the `:120` sentence | **budget <4600** |
| `plugin/methodology/reflection.md` | work-cycle-boundary step | budget |
| `plugin/methodology/session-digest.md` / `-slim.md` | one line each | pointer tests + 10k char |
| `CLAUDE.md` | only if the roster needs it | **150-line guard** |
| `.prawduct/artifacts/architecture.md` | persistence-boundary description | — |
| `.prawduct/cross-cutting-concerns.md` | continuity row | — |

## Build Chunks

### Chunk 01: The forward channel
**Type:** code

The thin vertical slice: prove the whole path before widening it. Create the model-owned channel
new `.prawduct/.handoff-notes.md`, have `generate_session_handoff` read it and emit it **first**
(above every machine section), and make the generator non-destructive.

Two independent mechanisms, because they fail differently:
- **The channel** (the documented path): the model writes notes; the generator consumes them into
  the handoff and `cmd_clear` archives them alongside `.session-reflected`.
- **The preservation net** (the safety net): the generator always emits a machine marker line. On
  the next run, a `.session-handoff.md` *lacking* that marker was authored by a model or human —
  preserve its body under a clearly-labelled section instead of dropping it. This catches the
  agent that writes the wrong file out of habit, which the evidence says is the common case.

`[ASSUMPTION: the two-mechanism design is worth its complexity over just the channel | MED impact
| user can drop the net]` The net is ~20 lines and is the only thing that helps an agent trained
on the old (wrong) affordance. Named separately so it can be cut cleanly.

**Persisted-format note** (planning.md — a persisted format is always lock-in). The file is
free-text markdown, so the lock-in is not the schema but the **contract**: who writes it, who
reads it, and when it is cleared. Enumerate before implementing: does anything other than the
handoff generator ever read it (the briefing? `/prawduct:pr`?); is it per-worktree or shared;
what happens to notes written but never consumed because the session ended without `/clear`.

*Enumerated and recorded* in `architecture.md` § "The one model-owned session file": sole reader is
the handoff generator (the briefing reads only the generated handoff; `/prawduct:pr` never touches
it); per-worktree like every session file; unconsumed notes persist to the next `/clear` — at most
one stale hop, and visible in the handoff when it happens.

`[DECISION: a pre-marker `.session-handoff.md` is preserved as "hand-authored" on the first `/clear`
after this ships, rather than sniffed as machine-generated | because the only discriminator for an
old machine handoff is its section headings, and a model-authored file using those same headings
would then be silently dropped — the exact failure being fixed. The cost of accepting it is one
mislabeled section, once, self-clearing on the next run | user can ask for the heuristic]`

**Done when:**
1. A note written to `.handoff-notes.md` appears, first, in the next session's handoff.
2. A model-authored `.session-handoff.md` is preserved, not destroyed, by `/clear`.
3. The generator still produces a useful handoff when no note exists (the no-warning `/clear` path).
4. Handoff generation still cannot block `/clear` under any failure.
5. New file is gitignored and in the session-file set.
6. Full suite green; `/prawduct:critic` passes with no blocking findings.

### Chunk 02: Parser correctness
**Type:** code

Fix defects 3-5, all in the read path feeding the handoff.

- Apply the done-predicate in `_get_active_work` by reusing `staleness_scan`'s logic — a plan with
  status items and no `current_chunk` is NOT active. Never label it `**Task**`. **Do this together
  with BRF-6K2D**, which makes `staleness_scan`'s own delete-nudge merge-aware: same two
  functions, and separating them means touching both twice.
- `views_enabled`: **sweep, don't patch.** Give `buildplan_refs` the git-derived current-chunk path
  that `critic_mode._git_aware_progress` (`critic_mode.py:520`) already implements, and route
  every consumer through it — the handoff, `verify-chunk-refs` (**closes BLD-7K3Q**), and any
  other caller of `_current_chunk_id_from_status`. CRT-7B4M shipped this derivation for
  `infer-critic-mode` alone; the defect recurring at two more consumers is the cost of not
  sweeping then. Grep for the callers rather than working from this list.
- `description`: fall back to the plan's `scope:` / filename when there is no `# Build Plan` H1,
  so the work section can never silently vanish.
- `context`: read the full block to the next heading, not one physical line; decide and document
  first-wins vs last-wins for multiple `Context:` lines.

Scope the changes **by pattern, not line number** (planning.md "Line-number scoping") — the line
numbers in this plan are evidence of where the defects were observed, not the edit list.

**Done when:**
1. A completed plan is never reported as active work; regression test pins it.
2. A `views_enabled` plan mid-flight reports the correct chunk at **every** consumer; regression
   test pins the case that fails today (all boxes `[ ]`, three chunks committed). BLD-7K3Q closes
   with this chunk — `/prawduct:backlog update BLD-7K3Q status=shipped closed-by=session-handoff-continuity`.
3. Only one implementation of "which chunk is current" survives the sweep; no consumer still reads
   first-unchecked directly.
4. A frontmatter-style plan with no H1 still produces a work section.
5. A multi-paragraph `Context:` survives whole.
6. BRF-6K2D landed with the done-predicate work, or explicitly deferred with a reason.
7. Full suite green; `/prawduct:critic` passes with no blocking findings.

### Chunk 03: Proactive close and the documentation surfaces
**Type:** doc-only

Make writing notes part of chunk close, and fix the affordance that caused the bug.

- `building.md` chunk-close sequence gains a write-the-notes step; the affirmative signal becomes
  "… handoff notes written. Safe to `/clear`." The `:120` sentence is corrected to describe both
  files and which one the agent owns.
- `reflection.md:63`'s "Complete handoff" is disambiguated — it currently reads as an action on
  the generated file.
- One line in each digest naming the channel.
- Optional: `prawduct-hook handoff preview` renders what the next session would receive, so the
  user can check without clearing.

`[DECISION: the "substantive work happened but no forward note exists" signal is an ADVISORY
note, never a block | because the architecture's ratified norm is "authority fails closed; advice
fails soft" and the handoff is advice — no gate reads it. Making continuity blocking would also
punish the legitimate case where there is genuinely nothing to say. The bug report's "minimum
bar" (the generator must not let the model narrate false success) is met by surfacing the absence,
not by refusing to clear | user can veto and ask for a hard gate]`

**Done when:**
1. Chunk-close sequence and the safe-to-`/clear` signal both name the notes step.
2. No surviving text implies the agent authors `.session-handoff.md`.
3. `cross-cutting-concerns.md` gains a session-continuity row, all four dimensions filled
   honestly — Discovery n/a; Artifact `architecture.md` § "The one model-owned session file";
   Builder the `building.md` chunk-close step this chunk adds; Critic **none today**, stated as
   such rather than left blank. (The surface table named this row and no chunk owned it — a
   Chunk 01 Critic finding under Framework Check 10.)
4. Every touched budget still passes; no ceiling raised.
5. `/prawduct:critic` passes with no blocking findings.

### Chunk 04: CRT-7P5J — the handoff stops reporting resolved findings
**Type:** code

`_summarize_critic_findings` (`briefing.py`) reads `.critic-findings.json` — a derived view of the
newest review fact — and never composes resolution facts, so findings resolved by a
`verify-resolutions` pass still print as outstanding. Compose over the evidence store, and make
the summary line and the enumerated findings derive from the *same* computation (today they can
disagree: "ready to proceed" printed above three WARNINGs).

The item notes this is pattern-shaped: sweep for other non-gate consumers reading the derived view
the same way, rather than fixing the one site.

**Done when:**
1. Review records N warnings → `verify-resolutions` resolves them → handoff shows zero outstanding.
2. Summary counts and enumerated findings cannot disagree.
3. Other derived-view consumers are swept and either fixed or recorded as correct.
4. Full suite green; `/prawduct:critic` passes with no blocking findings.

### Chunk 05: SCN-7K4B — design only
**Type:** doc-only

`[DECISION: SCN-7K4B gets a design chunk, not build chunks | because it is `stage: design` and the
framework's own rule routes an early-stage item to discovery rather than code; it also has two
sibling items (MET-8J5R "when is a plan a program", DOC-3V7T "the parent artifact's home") that
partition the same problem, so building the pointer here would pre-empt decisions those items own
| user can veto and ask for it to be built in this plan]`

Deliverable is a decision, not a mechanism: does program-level continuity belong in this handoff
machinery at all, or in the `active_program` pointer SCN-7K4B sketches? Chunks 01-02 will have
just rebuilt the surface it would attach to, so the design is cheap to do now and expensive to
retrofit later. Output: a recorded design in this plan (or a short artifact), the item advanced to
`stage=ready` with the design linked, or an explicit deferral with its reason.

**Done when:**
1. The design question is answered in writing, with the sibling-item boundaries stated.
2. SCN-7K4B is advanced to `stage=ready` or explicitly deferred — never left silently unchanged.
3. `/prawduct:critic` passes with no blocking findings.

## Verification Strategy

Beyond the suite, this plan's whole subject is a cross-session behaviour, so verify it *across an
actual session boundary* — the defect survived unit-level correctness for months precisely because
nobody exercised the real path:

1. In a scratch clone, write notes, `/clear`, and read what the next session actually receives.
2. Repeat with **no** notes written (the user who clears without warning) — continuity must still
   be useful.
3. Repeat with a model-authored `.session-handoff.md` and confirm the net preserves it.
4. Repeat on a `views_enabled` plan mid-flight and confirm the reported chunk is right.

## Governance Checkpoints

- **After Chunk 01** — the architecture-validation checkpoint. Does the two-file split hold once
  it is real, or does the model still reach for the wrong file? If the net fires often in practice,
  that is evidence the naming is wrong, and it is cheap to change now and expensive later.
  **Known residual gap, named not closed:** the net catches an agent that *replaces*
  `.session-handoff.md`, not one that *appends* to a marked (machine-generated) one — that text is
  still lost. Closing it means retaining a copy or hash of what was generated to diff against;
  disproportionate for a case the marker explicitly redirects. Chunk 03's affordance work is the
  real mitigation. Revisit if the checkpoint shows the net firing at all.
- **After Chunk 02** — re-run the live reproduction from Problem items 3-5 against this repo's own
  plan. Each must now be correct; a green unit test is not the same evidence.
- **Before Chunk 05** — confirm with the owner that designing SCN-7K4B here does not collide with
  MET-8J5R / DOC-3V7T, which own adjacent decisions.
