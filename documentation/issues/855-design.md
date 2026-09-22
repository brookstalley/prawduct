# Issue #855 — Gates: Nothing Detects a Build Plan That Was Never Persisted: Design

`status: draft · stage: design · area: gates · added: 2026-09-22 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/855`

Related: #661 (the v3.6.0 close-out item #855 was split from — split rather than closed, per its
own Evidence section); #843 (`documentation/issues/843-design.md`, the nearest structural
precedent — a sibling `area:gates` "nothing detects X" item designed the same week, cited
throughout below for its documented conventions); `buildplan_refs.unticked_committed_chunk_notice`
(the existing, adjacent mechanism this design deliberately does not duplicate — see Grounding
facts).

**No separate requirements doc exists for #855, and none is needed.** The issue's own body already
carries the problem statement, the reported incident (a lost 7-chunk plan, re-pasted from terminal
scrollback), the reason it is filed at `stage: design` rather than `stage: ready` (three named
candidate triggers, "the cheapest honest trigger is not obvious"), and three acceptance criteria.
That is what a requirements pass would otherwise produce; this document evaluates the three named
candidates against the actual code, rules one of them out as insufficient (with a reason), folds
the third into the first as a wiring detail rather than a separate mechanism, and turns what is
left into a concrete build — the same convention #843's design states for itself, which itself
cites `167-design.md`, `669-design.md`, `712-design.md`, `755-design.md` as prior instances of the
same pattern.

## Grounding facts

Re-verified against the current tree (`develop`, 2026-09-22):

- **The three candidates named in the issue are not equally available.** The issue names: (a) "a
  chunk-shaped commit subject with no resolvable plan", (b) "`active_build_plan` naming a missing
  path", and (c) "a Stop-hook check." (b) already ships as a *different* control, doesn't cover the
  reported failure, and fires too late even where it would apply — see next bullet. (c) is not a
  standalone option; it is *where* (a) would have to be wired to satisfy the "before the session
  ends" acceptance criterion, argued below. That leaves (a), argued as the trigger, wired per (c).
- **(b) is already built, and it is a `SessionStart` briefing notice, not a gate — and it only
  fires when the pointer was explicitly set.** `briefing.py:870-891` prints `⚠ active_build_plan
  points at a MISSING file` when the scalar names a path that does not resolve. Two gaps against
  #855's own acceptance criteria: it fires at the **next** `SessionStart`, after the session whose
  context held the plan has already ended (fails "detected before the session ends" by
  construction) — and it fires only when `active_build_plan` was *set* to a since-vanished path.
  The reported incident is the opposite shape: the operator never got as far as writing a pointer
  at all, because the plan itself was never written to a file. An unset scalar (`active_build_plan:
  null`, the shipped default — `.prawduct/project-state.yaml:616`) produces no warning under this
  check, by design (`core.py:834`, `"active_build_plan" is unset` is a *normal*, silent reading
  everywhere it's consulted). Fixing this gap by widening (b) would mean warning on every ordinary
  repo with no plan pointer — the exact "planless small work" nagging the issue's own acceptance
  criteria rule out.
- **The prior-order relationship to `unticked_committed_chunk_notice` (`buildplan_refs.py:963-
  1065`) is the load-bearing fact for scoping (a).** That control already reports a chunk whose
  work is committed but whose Status box is unticked — but it requires a plan file to exist in the
  first place (`buildplan_refs.py:1021: if not plan_path.is_file(): return None`). #855 is the
  question one step earlier: no plan file resolves *at all*. The two are complementary, not
  overlapping — a fix for #855 must return `None` in every case `unticked_committed_chunk_notice`
  already handles, and vice versa; the dividing line is exactly `plan_path.is_file()`.
- **`unticked_committed_chunk_notice`'s own docstring states, and defends, the honest-partial-
  coverage posture this design adopts wholesale.** Quoted directly because #855 inherits the same
  shape and the same limitation: *"The honest summary is that this catches the mistake in repos
  that already follow the convention and does nothing elsewhere; a signal independent of commit
  subjects … is the obvious strengthening and is not attempted here."* (`buildplan_refs.py:1001-
  1005`). A commit-subject trigger for #855 inherits precisely that ceiling — see Decision 1's
  stated limitation.
- **A transcript-based trigger — reading `transcript_path` from the Stop-hook payload to see a
  plan drafted but never saved — is the one candidate that would close that ceiling, and it is
  disqualified by this codebase's own stated invariant, not by cost.** `prawduct-hook`'s module
  docstring states the constraint in its own words: *"Governing invariant (design §2): reads/
  writes ONLY the governed repo's `.prawduct/` — the session's active git worktree … No mutable
  state is shared between unrelated repos through the plugin."* (`plugin/bin/prawduct-hook:22-
  24`). `transcript_path` (documented at `:2304-2305` as part of the Stop-hook stdin payload,
  confirmed unread by any current `lib/` code — `git grep transcript_path` returns only that one
  docstring line) names a file under Claude Code's own session-storage tree, outside the governed
  repo and outside `.prawduct/` entirely. Reading it would be the first surface in this plugin to
  cross that boundary — a bigger decision than #855 is chartered to make on its own, and disallowed
  outright given the standing rule in `.claude/rules/learnings/core.md`: *"Verify the constraint
  before adopting the recommendation"* and *"the 'canonical' mechanism for a capability can be
  disqualified by a plugin's composability + always-on constraints."* Scoped out below, not
  attempted, honestly, exactly as `unticked_committed_chunk_notice` scopes out its own stronger
  alternative.
- **`plan_backfill.py` is not a reusable "reconstruct a missing plan" primitive — checked and
  ruled out, not assumed.** Its docstring (`plugin/lib/plan_backfill.py:1-16`) is explicit: it
  moves *already-shipped* plans that exist on disk into `archive/`, keyed off change-log
  `release=` tags. It has no code path that authors a plan file from git history; there is nothing
  here for #855 to extend.
- **The scope→plan lookup this design needs already exists, archive-inclusive, one call.**
  `plan_index.build_scope_to_plan_map(artifacts_dir, include_archived=True)`
  (`plugin/lib/plan_index.py:502-524`) returns `{scope: path}` for every plan (live or archived)
  declaring a `scope:`. This is exactly what distinguishes the reported failure (no plan anywhere)
  from the look-alike, non-failure case: a plan that governed the committed chunks, finished, and
  was correctly archived after those commits landed — at which point `resolve_build_plan_path`
  no longer resolves to it (archived plans are pruned from live resolution by design), but the work
  was never lost. Without this check, a design keyed only on "does `resolve_build_plan_path` return
  a file" would misfire on every branch that carries old chunk-shaped commits from a plan that
  has since shipped and archived cleanly — the opposite of the intended failure.
- **All the primitives this design needs are already imported siblings inside
  `buildplan_refs.py`.** `_CHUNK_COMMIT_RE`, `_COMMIT_SCOPE_RE` (`:403-409`), `_commits_ahead_of_
  base` (`:421-436`), `_committed_chunk_ids` (`:438-`, unscoped reading when no `plan_scope` is
  passed — the correct call shape here, since there is no plan to scope by), `_resolve_base_branch`
  (imported from `coverage.py` at module scope, `:58`), `resolve_build_plan_path` (imported from
  `core.py`), and `plan_index` (imported at module scope, per the module's own docstring, `:13-25`).
  No new cross-module dependency is introduced.
- **The waiver mechanism this design's escape hatch reuses is a fixed, hand-maintained set, not a
  registry.** `KNOWN_WAIVER_KEYS` (`plugin/bin/prawduct-hook:2439`) is a literal Python set compared
  against `.gates-waived`'s keys; adding a gate that wants a waiver means adding one string to that
  set and one `blockers.append(_attributed(...))` call with a matching escape-hatch paragraph,
  exactly the shape of the existing `reflection` (`:2574`) / `critic` (`:3005`, a second occurrence
  at `:3208`) / `pr` (`:3419`) / `learnings` (`:2689`) / `learnings-budget` (`:2799`) blockers.
- **`_committed_chunk_ids`'s own docstring documents a real, cited case of a plan's commit-scope
  diverging from its frontmatter `scope:`** ("on this very branch the continuity plan's commits
  say `session-continuity` while its frontmatter says `session-handoff-continuity`",
  `buildplan_refs.py:464-467`). This is directly relevant to Decision 2's false-positive shape:
  a real, persisted plan can still produce commits whose conventional-commit scope does not match
  any key in `build_scope_to_plan_map`, for the same reason.

## Decisions

**1. Trigger is git/filesystem composition — candidate (a) — never the transcript. Its ceiling is
stated, not hidden.** A commit-subject-and-scope check answers #855's acceptance criteria for every
case where at least one chunk's work was actually committed before the session that drafted the
plan ended; it cannot catch a plan lost *before* any chunk was committed (the purely-conversational,
zero-commits case, which the reported incident may or may not have been — the issue does not say).
That gap is real and is left open (Scope-out), for the reason in Grounding facts: closing it needs a
transcript read, which conflicts with this plugin's own stated `.prawduct/`-only invariant. Matching
`unticked_committed_chunk_notice`'s own precedent, an honest partial control that is silent outside
its stated shape is preferred over inventing a second, weaker "is this a plan" heuristic over
conversation text.

**2. The predicate — every clause named, because a false fire here is expensive (issue's own
framing) and each clause exists to suppress one specific false positive:**

```
def unpersisted_plan_notice(project_dir: Path) -> str | None:
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    if resolve_build_plan_path(prawduct_dir).is_file():
        return None                                    # clause A
    base, _ = _resolve_base_branch(project_dir)
    if not base or _commits_ahead_of_base(project_dir, base) <= 0:
        return None                                    # clause B
    chunk_ids = _committed_chunk_ids(project_dir, base)   # unscoped: no plan to scope by
    if len(chunk_ids) < _MIN_UNPLANNED_CHUNK_IDS:          # clause C, = 2
        return None
    scope_map = plan_index.build_scope_to_plan_map(
        prawduct_dir / "artifacts", include_archived=True
    )
    if _any_commit_scope_resolves(project_dir, base, scope_map):
        return None                                    # clause D
    return <message: chunk_ids, their carrying commit subjects, the would-be plan path>
```

- **Clause A (no plan resolves, live).** Reuses `resolve_build_plan_path` exactly as every other
  gate does — the one resolver (`buildplan_refs.py:15-16`'s own module docstring: "there is one
  resolver now, the hook's inline mirror of it having been retired"). A plan governing the branch,
  by pointer, or at the conventional path all clear this and correctly suppress the notice.
- **Clause B (commits exist ahead of base).** No commits, nothing to check — mirrors
  `unticked_committed_chunk_notice`'s own guard (`buildplan_refs.py:1038-1039`) verbatim.
- **Clause C (≥ 2 distinct chunk ids, unscoped reading).** This is the "planless small work is not
  nagged" bound (acceptance criterion 2). A single `(Chunk 1)`-tagged commit in a repo with no
  formal build-plan habit is indistinguishable from an informal, one-off use of the phrase; two or
  more *distinct* ids on one branch, with no plan anywhere, is the actual signature of a plan that
  was being executed chunk-by-chunk and never got written down. **Stated limitation**: a real
  one-chunk plan that was never persisted is invisible to this predicate by construction — accepted
  per Decision 1's honesty posture, and named again in Scope-out so it is not rediscovered as a
  surprise later.
- **Clause D (no commit's own scope already resolves to a plan, live or archived).** This is what
  keeps the notice silent on a branch carrying old chunk-shaped commits from a plan that finished
  and was correctly archived (Grounding facts) — the look-alike case that a plan-existence check
  alone would misclassify as the bug. It also absorbs the documented commit-scope-vs-frontmatter-
  scope divergence (Grounding facts, last bullet) in the SAFE direction: when scopes disagree, this
  clause can under-suppress (fire when a plan genuinely exists but under a mismatched scope) rather
  than over-suppress (stay silent when nothing exists) — the same asymmetry `_committed_chunk_ids`'s
  own docstring accepts for the same reason ("the cost of not archiving is a plan that stays visible
  one release longer; the cost of archiving wrongly is a live plan disappearing" — same shape,
  applied to a notice rather than an archive move). A plan whose commit scope drifted this way and
  who additionally triggers this notice is a one-line waiver away from silence (Decision 3); false
  suppression down clause A/D is not recoverable in the same way, so the bias is deliberate.
- **`_any_commit_scope_resolves` is one new, small helper** in `buildplan_refs.py`: walks the same
  `base..HEAD` subject list `_committed_chunk_ids` already fetches (a second `git log`/`rev-list`
  call rather than refactoring the existing one to return scopes too — refactoring a function three
  other call sites depend on for one new caller's convenience is the wider, riskier change; an extra
  local `git` subprocess is not a cost this codebase treats as worth avoiding — #843's Decision 4
  budget-guards *network* calls specifically and leaves local git calls unbounded throughout
  `cmd_stop`), applies `_COMMIT_SCOPE_RE`, and returns whether any extracted scope is a key in
  `scope_map`.

**3. Wired as a blocking Stop-hook gate, with a waiver escape hatch — not the advisory roster.**
The advisory roster (`probe_families`/`advisory_store`, the surface #843's design uses) runs at
`SessionStart`/`/clear` sync — the *next* session boundary, which is exactly the "too late" gap
Grounding facts states against candidate (b). #855's own acceptance criterion is "detected **before
the session ends**", which only a Stop-hook check can satisfy: it is the one point where blocking
output still reaches the session that holds the plan in context, before that context is gone. This
also matches the issue's own `area: gates` filing (not `area: probes`). Consequences accepted
deliberately:
  - It can block a session end on a false positive (Decision 2's stated residual cases). The
    remedy is cheap by construction — write the missing plan file, or waive it — never a rewrite.
  - It needs the same waiver mechanism every other blocking gate here already has:
    `KNOWN_WAIVER_KEYS` gains `"plan-not-persisted"`, and the blocker's message ends with the
    standard escape-hatch paragraph (`echo '{"plan-not-persisted": "reason"}' >
    .prawduct/.gates-waived`), matching `reflection`/`critic`/`pr`/`learnings` verbatim in shape.
  - **Never auto-writes the missing plan.** Per Grounding facts (`plan_backfill.py`'s own stated
    ruling — "only a session with the work in context may say which chunk is done" — and the
    broader report-never-write posture the codebase applies to plan/checkbox state throughout),
    the gate names the gap and asks the session to author the file; it does not attempt to
    reconstruct plan content from commit diffs.

**4. Message names the evidence, not a conclusion — same posture `unticked_committed_chunk_notice`
uses.** The blocker cites the chunk ids found, the subject of the first commit carrying each
(`_committed_chunk_ids` already returns this), and the path `resolve_build_plan_path` would have
resolved to (the file the session should create) — enough for the agent to act without re-deriving
anything, and enough for a human reviewing the block to independently confirm or dismiss it.

## What ships

1. `plugin/lib/buildplan_refs.py`: `_MIN_UNPLANNED_CHUNK_IDS = 2` (module constant, beside
   `UNTICKED_CHUNK_TOKEN`); `_any_commit_scope_resolves(project_dir, base, scope_map) -> bool` (new
   private helper); `unpersisted_plan_notice(project_dir) -> str | None` (new public function,
   Decision 2's algorithm, docstring mirroring `unticked_committed_chunk_notice`'s stated-limitation
   style).
2. `plugin/bin/prawduct-hook`: `cmd_stop` gains a new blocking check calling
   `buildplan_refs.unpersisted_plan_notice`, gated the same way the existing gates are (only spends
   the filesystem check `resolve_build_plan_path(...).is_file()` up front — the common case, a repo
   with a live plan, never reaches a git call); on a non-`None` result and no matching waiver, append
   to `blockers` via `_attributed("plan-not-persisted", …)` with the standard escape-hatch paragraph.
   `KNOWN_WAIVER_KEYS` gains `"plan-not-persisted"`.
3. `plugin/hooks/gates.json`: new entry, `id: "plan-not-persisted"`, `name:
   "plan-not-persisted"`, `summary: "chunk-shaped commits exist on this branch but no build plan
   file resolves anywhere, live or archived — the plan was never written down"`, `since` filled in
   at the release that ships it (not asserted here — `.prawduct/project-state.yaml` currently opens
   `3.6.1-dev.1`, per `git log`, but which release actually carries this build is a build-time fact,
   not a design-time one).
4. Tests (mirroring `tests/test_stop_gate_defer.py` / the codebase's per-gate test convention): the
   four suppression clauses (A: live plan present; B: no commits ahead of base; C: single chunk id;
   D: commit scope resolves via `build_scope_to_plan_map`, live and archived cases both), the firing
   case, the waiver, and message content (chunk ids + subjects + would-be path all present).

## Acceptance criteria — how each is met

- **"A build plan that exists only in context is detected before the session ends"** — for the
  case where at least one chunk was committed before session end: Decisions 1-3, wired into
  `cmd_stop`. **Not met** for a plan lost before any commit landed — Decision 1's stated ceiling,
  the transcript-invariant conflict in Grounding facts, and Scope-out.
- **"A repo doing planless small work is not nagged"** — Decision 2, clause A (a resolvable plan,
  however small, is fully silent) and clause C (a single incidental "(Chunk N)" commit is not
  evidence of an unpersisted *plan*).
- **"The trigger is named and its false-positive shape stated"** — this document: the trigger is
  candidate (a), wired per (c) (Decision 1); the false-positive/false-suppression shapes are named
  per clause in Decision 2, plus the accepted asymmetry (favors under-suppression risk over
  over-suppression risk, stated and justified) and the zero-commits blind spot (Decision 1, Scope-
  out).

## Scope-out (this item)

- **Transcript-based detection of a plan drafted but never committed at all.** The strictly
  complete answer to the reported incident, and the one candidate this design does not attempt —
  Grounding facts states the specific invariant it would cross (`prawduct-hook`'s own `.prawduct/`-
  only reads/writes boundary) and why relaxing that boundary is a decision bigger than this item, not
  a cost this item declined to pay. A follow-on item, if this gap proves to matter in practice, needs
  its own owner-level decision to widen that invariant — not a design smuggled in here.
- **A single-chunk plan that was never persisted.** Excluded by Decision 2 clause C's threshold,
  for the reason stated there (indistinguishable from incidental commit-message phrasing without a
  second signal this design does not have). Not solved by raising an alternative, weaker signal —
  matching the issue's own instruction ("do not solve it by … adding a gate" applied by analogy from
  #847's adjacent framing: a weak signal should not be made to carry more than it can).
- **Auto-authoring the missing plan file from commit history.** Decision 3's explicit "never auto-
  writes" — `plan_backfill.py`'s own ruling and the report-never-write posture on plan/checkbox
  state both argue against it, and it is not what the issue asks for (it asks for *detection*).
- **A configurable chunk-count threshold, or a preferences row for this control.** Ships as the
  hardcoded module constant `_MIN_UNPLANNED_CHUNK_IDS = 2` (Decision 2); matches #843's own Decision
  2 precedent for the same reason — a guessed default is a smaller commitment than new declared
  vocabulary, and #820's live triage thread already records a standing owner caution against adding
  framework-read vocabulary without a reason (Grounding facts of that item, cited for the same
  caution here, not re-litigated).
- **Retiring or merging this control with `unticked_committed_chunk_notice`.** They stay separate
  functions with a stated, mutually-exclusive dividing line (`plan_path.is_file()`) rather than one
  function branching on it — matching this codebase's stated aversion to re-deriving a second,
  parallel classifier for a question an existing one already answers (`plugin/lib/coverage.py:1063`,
  "a prose copy is the fourth classifier this function shipped once already" — cited in #843's
  design for the same reason, there at a since-shifted line number, re-verified here against HEAD).

## Evidence / references

- `plugin/methodology/building.md:76` ("Persist plans immediately … an uncommitted amendment is
  invisible to [a delegate]") and `plugin/methodology/reflection.md:59-74` ("Step 6: Persistence and
  Boundary Check" — "anything not in a file is lost") — the standing, unenforced instructions #855's
  own Problem statement cites as guidance-only.
- `plugin/lib/briefing.py:870-891` — the existing `active_build_plan` dangling-pointer warning
  (candidate (b)), and why it does not close this gap (Grounding facts).
- `plugin/lib/buildplan_refs.py:963-1065` (`unticked_committed_chunk_notice`, its docstring's
  stated honest-partial-coverage posture at `:1001-1005`), `:403-409` (`_CHUNK_COMMIT_RE`,
  `_COMMIT_SCOPE_RE`), `:421-436` (`_commits_ahead_of_base`), `:438-` (`_committed_chunk_ids`,
  its base-commits guard at `:1039`, and its documented commit-scope-vs-frontmatter-scope
  divergence example at `:464-467`) — the primitives this design reuses verbatim, and the
  precedent it follows for stating its own limitation.
- `plugin/lib/core.py:666-693` (`pointer_plan_path`), `:855-875` (`resolve_build_plan_path`), and
  `:834` (an unset `active_build_plan` reads as normal, not a warning) — the one resolver this
  design reuses for clause A.
- `plugin/lib/plan_index.py:502-524` (`build_scope_to_plan_map`, `include_archived=True`) — the
  archive-inclusive lookup Decision 2's clause D depends on.
- `plugin/lib/plan_backfill.py:1-16` — read and ruled out as a reuse target (Grounding facts,
  Decision 3).
- `plugin/bin/prawduct-hook:22-24` (module docstring, the `.prawduct/`-only governing invariant),
  `:2304-2305` (`transcript_path` documented, confirmed unread elsewhere by `git grep`) — the
  citation for ruling out transcript-based detection (Grounding facts, Decision 1, Scope-out).
- `plugin/bin/prawduct-hook:2439-2450` (`KNOWN_WAIVER_KEYS`, the unknown-waiver-key stderr note),
  `:2574` / `:3005` (also `:3208`) / `:3419` (the `reflection` / `critic` / `pr` blocker escape-
  hatch paragraphs) — the waiver convention Decision 3 extends by one key.
- `plugin/hooks/gates.json` — the gate registry this design adds one entry to, and its own stated
  purpose (new-gate attribution for the version-delta banner and Stop-hook blocking messages).
- Issue #843's design document (`documentation/issues/843-design.md`) — the structural precedent
  cited throughout: "no separate requirements doc" framing, per-decision reuse-over-reinvention
  posture, and the "fourth classifier" anti-pattern citation this document reapplies in Scope-out.
- Issue #855's own body (2026-09-20) — the three named candidate triggers this document evaluates,
  the three acceptance criteria mapped above, and the split-from-#661 provenance.
