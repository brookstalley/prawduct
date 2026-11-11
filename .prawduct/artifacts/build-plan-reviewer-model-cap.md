---
artifact: build-plan
version: 2
scope: reviewer-model-cap
branch: feature/reviewer-model-cap
base: develop
working-branches: []
partition: "serial inside one Opus builder in an isolated worktree - all three chunks edit the Critic skill, the reviewer contract and the dispatch code; the coordinator integrates, runs the suite once and governs"
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → amendment proposed; the norm's why says the reviewer's model tier is fixed at the session's, and the owner's ruling of 2026-11-10 caps it at Opus-class. The hand-off adds one subagent start to a capped single-pass round, on a tier the 2026-06 comparison measured at about a quarter of the wall clock"
      - "proportionality ratchets both ways → conforms; no control is added, a cost ceiling is"
      - "state-file growth is advisory, never a hard block → inapplicable because no state file grows"
      - "review rigor is stage-keyed → conforms; which model reviews changes, what each stage rates does not"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms; a handed-off reviewer writes its marker and its partial, as a roster reviewer does"
      - "authority fails closed; advice fails soft → conforms; the cap is advice to the dispatcher and no gate reads it, and consolidation still refuses a malformed partial"
      - "local-first → conforms"
      - "the plugin writes nothing into a governed repo except its own state → conforms"
      - "written in Python, never specific to Python → inapplicable because no product code is read"
      - "guides and reviews, never implements → conforms"
      - "goals and verification bind, method is advice → conforms"
      - "every fact has one home → conforms; the ceiling and the alias it resolves to live in one function, and the dispatch directives have one renderer feeding both stdout and the manifest"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms; the manifest's reviewer model is dispatch guidance derived by code, and no verdict reads it"
      - "facts immutable and append-only → conforms; no fact is rewritten"
      - "derived views never authoritative → conforms"
      - "a newer-schema fact is surfaced, never dropped → inapplicable because the review fact's schema does not change; the manifest gains optional fields"
      - "two stores, two lifetimes → inapplicable because no store changes"
      - "backlog_service_repo selects the authoritative backlog store → inapplicable because the backlog skill changes only the model it runs on"
      - "backlog issues conform to the title rules → inapplicable because no write path changes"
      - "a governance document reaches a terminal state and is never deleted → inapplicable because no plan or record lifecycle changes"
depends_on:
  - plugin/skills/critic/SKILL.md
  - plugin/skills/critic/coordinator.md
  - plugin/agents/critic-reviewer.md
  - plugin/skills/pr/SKILL.md
  - .prawduct/artifacts/project-preferences.md
  - .prawduct/owner-rulings.md
last_validated: 2026-11-11
---

## Goals

**Response taken:** Proceed, citing it, after one batch of two questions. #1136 carries the
requirement. The owner's ruling of 2026-11-10 is its authority: "Yes cap at opus. In fact we need
to be very careful to not accidentally spam fable subagents anywhere, given the cost. Sometimes it
makes sense, but most fable orchestrators should use opus and sonnet for most delegation". Two
choices the host forces were put to the owner on 2026-11-11 and are recorded in
`.prawduct/owner-rulings.md`: "Hand off to Opus (Recommended)" for the forked Critic's own
reviews, and "Sonnet for both (Recommended)" for the forked backlog and advisory skills.

**Product:** On a session running above Opus-class, no review and no forked skill runs on the
session's tier by accident. Reviewers run on Opus-class there and on the session's model
everywhere else. The owner gets the cost ceiling without choosing a model per review.

**Architecture:**
- One function answers "which model does a reviewer run on, given the session's model": nothing
  (the session's own) when the session is recognisably at or below Opus-class, the Opus-class
  alias otherwise. The alias has that one home.
- `critic-begin` takes the dispatcher's own model and writes the answer into the dispatch
  manifest. The PR skill gets the same answer from the command it already runs to mark its
  dispatch. Dispatch prose names no model; it passes what code answered.
- When the manifest carries a reviewer model, the forked Critic reviews nothing itself. It
  dispatches every roster role, the single-pass role included, as a `critic-reviewer` on that
  model and stops. `SubagentStop` consolidates, as it does for the three-reviewer roster today.
- The manifest's `tier` stays telemetry and selects no model. Nothing chooses a model by diff
  risk or size.

**Constraints:**
- A session at or below Opus-class dispatches exactly as today: no override, single-pass reviews
  inline, the fork consolidating its own.
- The norm's statement ("Reviewers run on the session model — no intelligent model switching")
  is not edited. The amendment is recorded in the norm's entry with the owner's words and date,
  in the form `nonfunctional-requirements.md` § Direction already uses (`Amended: <date>, …`).
- The reviewer agents keep `model: inherit` and the Critic skill's front matter names no model:
  a fixed model there would raise a Sonnet session's reviews and fail where Opus is not offered.
- Build, research and integration delegates are out of scope; `methodology/delegation.md` covers
  them.
- The review fact's schema does not change. The model that ran is recorded as it is today.
- `plugin/methodology/session-digest.md` has a hard character wall; anything added there is paid
  for in place.

**Tradeoffs accepted:**
- The cap trades review depth for cost at the boundary: the 2026-06 comparison
  (`.prawduct/artifacts/reviewer-model-ab-2026-06-10.md`, one bundle) had the stronger tier raise
  six novel real findings to Opus-class's one. Worth revisiting if boundary reviews start missing
  defects that later surface; the lever is an explicit stronger-tier boundary review, not removing
  the cap.
- On a capped session the fork still starts on the session's model, for the routing steps only.
- Backlog and advisory drop a tier on an Opus-class session.

**Inferences, for the owner to veto at the boundary:**
- *Inferred:* "above Opus-class" is decided by exclusion. A session model that names Haiku, Sonnet
  or Opus is at or below the ceiling; any other value, and no value at all, is treated as above
  it. A new stronger tier is then capped with no code change. The cost: a session on a model the
  code does not recognise, or a dispatcher that omits its model, gets Opus-class reviewers.
- *Inferred:* the acceptance line "`stats` reports reviews by the model that ran" means
  `review-stats`, which already groups by role, model and mode. What is missing is a count of
  reviews recorded above the ceiling; that is added to `review-stats`. `stats` is not changed:
  its report is the one contributed outside the repo, and a new field there is a format decision
  this item does not need.
- *Inferred:* the cap covers a `final` or `cumulative` review that the roster rule keeps
  single-pass, by the same hand-off.
- *Inferred:* the dispatch-time directives `critic-begin` prints for the reviewing fork reach a
  handed-off reviewer through the manifest, written by the code that prints them, rather than
  being pasted into the dispatch prompt by the fork.

**Decisions made mid-build:** *(appended while building)*
- The family fold and the ceiling share one leaf module, `plugin/lib/model_tier.py`; `review-stats`'s
  `_canonical_model` is that module's function, not a copy. Settled by "every fact has one home".
- Both commands print the answer as one line, `reviewer model: <alias>` or `reviewer model: none`,
  followed by what to do with it; `critic-begin` also writes it to the manifest. The PR mark's
  existing reader parses its `dispatch marked:` line, so the answer is a line of its own. Settled by
  the architecture goal that dispatch prose passes what code answered.
- `pr-review-dispatch` prints the answer before attempting the mark, so a clock that cannot be
  written keeps the cap. Settled by the product goal: nothing runs on the session's tier by accident.
- The PR skill's grant for the mark widens to the house form `--begin*`, which covers
  `--session-model` and nothing past `--begin`. Settled by `tests/test_skill_command_grants.py`'s
  house grant form.
- The amendment to the table-row norm sits in its Why cell with the owner's words and no
  `[DECISION: …]` block: the index parser splits cells on `|`, and the owner made the call directly
  (`docs/norms.md` "One standard"). `nonfunctional-requirements.md` carries the `Amended:` line and
  a `Retires:` line for the two sentences the cap made false. Settled by `docs/norms.md` § Amendment.

**Level:** Medium. The design rests on host behaviour read from the documentation on 2026-11-11
and not all yet observed: an Agent call's `model` overrides a plugin agent's `model: inherit`
(documented, and observed in this repo's reviews of 2026-11-10); a forked skill may name a fixed
model in front matter (documented, not yet observed here). What raises it: the first governed
session after the installed plugin is advanced runs one capped chunk review and one
`/prawduct:advisory`, and reads the recorded models.

## Verification Strategy

Each chunk's tests are red first at the seam the chunk adds. Prose deliverables are checked by
falsifying queries whose output goes in the builder's report: every statement that reviewers run
on or inherit the session model, in `plugin/`, `tests/`, `documentation/` and the live artifacts
(not archives, reflections or release notes), agrees with the amended rule. The full suite runs
once, on the integrated branch. Host behaviour is verified live after the installed plugin is
advanced, and is queued for that session rather than claimed here.

## Build Chunks

### Chunk 01: Dispatched reviewers are capped at Opus-class

- **Description:** Add the one function that answers the reviewer model for a session model.
  `critic-begin` accepts the dispatcher's model (`--session-model`) and writes `reviewer_model`
  into the manifest (absent or null when no override applies). The command the PR skill runs to
  mark its dispatch accepts the same flag and prints the answer. `coordinator.md` and the PR
  skill pass that answer as the Agent call's `model` and pass none when there is none. Record the
  amendment in the norm's entry in `project-preferences.md` and in
  `nonfunctional-requirements.md` § Direction, and correct every sentence the cap makes false:
  the "Model floor and coherence pass" preference and its enforcement row ("no machinery selects <!-- prawduct:allow prawduct/retired-claim-survives -- the plan names the retired claims it corrects -->
  models at dispatch time", "the runtime cannot observe which model it is"), the paused-tiering
  comments in `plugin/lib/telemetry.py` and `plugin/lib/risk.py` where they describe reviewers,
  and the reviewer-dispatch prose. Rewrite `tests/preferences/test_reviewer_model_dispatch_prose.py`
  to pin the amended rule.
- **Depends on:** none
- **Deliverables:** the function and its tests; the two flags; the manifest field accepted by
  `validate_manifest`; `plugin/skills/critic/coordinator.md`, `plugin/skills/critic/SKILL.md`
  (the `critic-begin` invocation) and `plugin/skills/pr/SKILL.md`; the amended norm entries; the
  rewritten prose pin.
- **Tests:** Red first: a session model above Opus-class yields the Opus-class alias in the
  manifest and in the PR dispatch mark's output; Haiku, Sonnet and Opus ids, in alias, full-id and
  bracket-suffixed forms, yield none; an unrecognised id and an absent flag yield the alias. The
  answer does not vary with `--tier`. The prose pin: dispatch surfaces carry no literal model
  alias, name the session model and the ceiling, and take the model from the code's answer; the
  reviewer agents declare `model: inherit`; the Critic skill's front matter names no model.
- **Acceptance criteria:** on a session above Opus-class a three-reviewer Critic review and a PR
  review are dispatched on Opus-class; at or below it the dispatch is unchanged; the norm's
  statement is unchanged and the amendment sits in its entry with the owner's words and date.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 02: A capped single-pass review is handed to one Opus-class reviewer

- **Description:** When the manifest carries a reviewer model and the roster is single-pass, the
  fork dispatches one `critic-reviewer` for the `reviewer` role on that model and stops, exactly
  as the coordinator does for three. `plugin/agents/critic-reviewer.md` learns the `reviewer`
  role: which protocol file it reads for which mode (`goals-1-3.md` for `chunk` and
  `verify-resolutions`; `review-protocol.md` with its siblings for a single-pass `final` or
  `cumulative`), that it writes `resolutions` on a `verify-resolutions` dispatch and only there,
  and that it never consolidates. The directives `critic-begin` prints for a reviewing fork are
  rendered by one function, in their pinned order, and written into the manifest when a reviewer
  model is set; the handed-off reviewer reads them there. Check the reviewer agent's tool list
  against every command the single-pass protocol tells its reader to run, and reconcile. Correct
  every statement that a single-pass review is always inline or always consolidates itself: the
  session digest's sentence on when to run `critic-consolidate` before reading findings,
  `methodology/building.md` "Resolve findings", `skills/critic/review-cycle.md`,
  `goals-1-3.md`'s closing instruction, the comments in `plugin/lib/critic_consolidate.py` that
  reason from "always single-pass, so the fork consolidates", and
  `.prawduct/artifacts/critic-persistence-redesign.md`.
- **Depends on:** Chunk 01
- **Deliverables:** `plugin/skills/critic/SKILL.md` step 7; `plugin/agents/critic-reviewer.md`;
  the directive renderer and the manifest field; the corrected statements; tests.
- **Tests:** Red first: a manifest with a reviewer model and a single-pass roster carries the
  directives its mode is owed, in the pinned order, and the same text is what `critic-begin`
  prints; without a reviewer model the manifest carries none. A `reviewer` partial written by a
  dispatched agent consolidates through the `subagent-stop` trigger for `chunk` and for
  `verify-resolutions` with resolutions. A guardrail reads the reviewer contract as a handed-off
  reviewer would and finds its protocol file, its two write paths and the directives.
- **Acceptance criteria:** on a session above Opus-class a `chunk` and a `verify-resolutions`
  review run on Opus-class and consolidate without the fork; at or below it they run inline as
  today; no shipped sentence says a single-pass review is always inline.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 03: The utility forks name Sonnet, the sweep is recorded, and review-stats counts reviews above the ceiling

- **Description:** `plugin/skills/backlog/SKILL.md` and `plugin/skills/advisory/SKILL.md` name
  Sonnet-class in front matter. Enumerate, by query, every place the plugin starts a subagent or
  a forked skill (agent definitions, skill front matter, and methodology or skill text that tells
  an agent to start one) and record each in the change fragment with the model it runs on and
  why; any start found that names no model and is not covered by `methodology/delegation.md` is
  fixed here. `review-stats` reports how many reviews in its window were recorded on a model above
  the ceiling, in the JSON report and the human rendering, using Chunk 01's function. Write the
  new `.prawduct/changes/reviewer-model-cap.md` fragment and update
  `plugin/docs/governance-telemetry.md` where it describes the model dimension.
- **Depends on:** Chunk 02
- **Deliverables:** the two front-matter lines; the inventory in the change fragment;
  `review-stats`'s count and its tests; the documentation that describes them.
- **Tests:** Red first: a ledger holding reviews recorded on a model above the ceiling, at it,
  below it and with none is counted correctly in both renderings. A pin: every skill declaring
  `context: fork` either names a model at or below Opus-class or is the Critic, whose reason is
  stated beside the pin.
- **Acceptance criteria:** the inventory is in the change record and matches the query that
  produced it; `review-stats` reports reviews by the model that ran and counts those above the
  ceiling; #1136's acceptance list is met line by line, with the inferences above standing in
  where it was loose.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed, the declared suite green on the integrated branch
  3. `/prawduct:critic cumulative` run once and blocking findings resolved
