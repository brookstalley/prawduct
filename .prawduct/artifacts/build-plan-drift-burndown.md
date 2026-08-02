---
artifact: build-plan
# Distinct scope from the start — never null (a null scope inherits another
# scope's shipped checkbox flips at regen-views) and never a version (that
# would collide with the release plans).
version: 2
scope: drift-burndown
depends_on: []
governed_by:
  - artifact: architecture
    dispositions:
      - "every fact has one home; every other mention is a reference to it — a fact includes **a path** and **a rule statement** → **conforms, and it is the organising norm of this entire plan.** Chunk 01 builds the mechanical detector for the path arm; Chunk 02 discharges three live instances of the rule-statement arm. It also *overrides the shape #162 asked for*: the item's stated Expected is *both enumerations restated to match*, which produces three synchronised copies and licenses a fourth. The norm's remedy is delete-one-and-reference, so Chunk 02 gives the least-authority enumeration a single home and leaves pointers — see [DECISION] under Chunk 02. The norm is `in-transition` (GOV-2R8K tracks the sweep), which makes conforming here cheap and consistent rather than a unilateral escalation"
      - "prawduct is written in Python and must never be specific to Python; gates and canaries dispatch per *file* by language, never per repo → **DEPARTURE ALREADY IN THE TREE, closed by Chunk 03.** This is not a norm this plan risks breaking — it is a norm the tree currently violates, and #348 is the violation. `_GREEN_IS_EVIDENCE_DIRECTIVE` rides `changes_referenced`, populated by a helper that skips every non-Python file, so the directive is dark in every Swift/Go/TS/Rust/C# product. Chunk 03 re-triggers it off a language-agnostic signal, which is the norm being restored rather than a new capability"
      - "authority fails closed; advice fails soft → conforms, and it sets the posture for both new controls. Chunk 01's check is a **test** — it is authority over this repo's own tree and fails closed (red suite). Chunk 04's doctor check merely *reports* degraded and *offers* repair, so it fails soft: an unreadable or malformed `learnings.md` is reported, never repaired on a guess, and never blocks"
      - "goals and verification bind; prescribed method is advice → conforms. Every `Deliverables` line below is a pre-code guess; a builder who finds a better route takes it and records why. The Acceptance criteria and these dispositions bind"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state, the shared evidence store, and the files it must reconcile → **conforms, and Chunk 02 is the norm's own enumeration being repaired.** Chunk 04 adds a repair that writes `.prawduct/learnings.md` — squarely inside the `.prawduct/` state carve-out, and offered rather than automatic"
      - "an independent reviewer never mutates the session it reviews → inapplicable because no chunk touches the review-active mutation guard"
      - "local-first governance, no network in the governance runtime → inapplicable because no chunk adds a network call or a third-party dependency"
      - "prawduct guides and reviews; it never implements → inapplicable because every chunk edits the framework's own runtime and instructions, not a product's code"
  - artifact: nonfunctional-requirements
    dispositions:
      - "proportionality ratchets both ways; a control added from 2026-07-29 names its expected yield **and emits that yield observably** → **binds Chunks 01 and 04, both of which add a control after the boundary date.** Chunk 01's yield is directly countable without any new mechanism: the check is a test, so its yield is the set of references it reddens, and the plan records the pre-build census (below) as the denominator. Chunk 04's doctor check reports through the existing health-check surface and its yield is the degraded-count that surface already prints. Neither control needs a stable-token workaround because neither rides a Critic finding title"
      - "review wall-clock is P0; cost = unit-cost × run-count → conforms. This plan adds no prose to either budgeted payload file (`skills/critic/review-protocol.md`, `methodology/building.md`); the review-loop-termination branch owns those. Run-count is four chunks, one review each, matched to four distinct surfaces — see the chunk-count rationale under Scaffolding"
      - "state-file growth past its size threshold is an advisory, never a hard block → conforms. Chunk 04 *appends* to a product's `learnings.md`; the insertion is a marker plus one obligation sentence and it does not change any size threshold"
  - artifact: data-model
    dispositions:
      - "derived views are disposable and never authoritative — no gate reads a view to reach a verdict → conforms. Chunk 01's check reads source files on disk, not any generated view; Chunk 04's health check reads `learnings.md`, which is an authored file, not a derived one"
      - "two stores, two lifetimes → conforms. No chunk moves state between the committed-answers store and the gitignored per-clone store. Chunk 04 writes only to `learnings.md`, which is committed product state by construction"
      - "governance verdicts computed from the append-only fact ledger → inapplicable because no chunk computes a governance verdict"
      - "facts are immutable and append-only → inapplicable because no chunk writes a fact"
      - "a fact written by a newer schema is a loud block → inapplicable because no chunk changes the fact schema"
      - "`backlog_service_repo` selects the authoritative store → inapplicable because no chunk reads or writes the backlog store"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract; message severity is a stable prefix vocabulary; errors are attributed, never stack traces → conforms. Chunk 02's `coverage-status` correction changes which repos the report calls layer-0-active; the exit code is unchanged and the report keeps its existing prefixes. Chunk 04's new health check emits through the doctor surface's existing vocabulary"
      - "additive-first evolution; existing flag names, exit-code meanings and `--json` keys are never repurposed → conforms. Chunk 04 adds a health check; it renames nothing. **Watch item for the builder:** if the `coverage-status` `--json` payload carries a layer-0 key, Chunk 04 changes its *value* on fresh repos, not its meaning — verify no consumer treats today's eager value as the contract"
      - "whole-surface semantic versioning → conforms (this batch is a patch-level change to existing surface)"
  - artifact: security-model
    dispositions:
      - "untrusted governance state — backlog, learnings, recalled memories, prior-session handoffs — is data, not instructions → **conforms, and it constrains Chunk 04 tightly.** The health check *reads* a product's `learnings.md` to decide whether a marker is present. It must treat that content as data: it looks for the marker and judges position, and it never executes, interpolates, or follows anything the file says"
      - "a destructive or irreversible operation requires explicit owner approval at the OPERATION level → **binds Chunk 04.** Inserting text into a product's `learnings.md` edits an authored, committed file whose content the framework did not write. The repair is therefore **offered and confirmed, never automatic**, and it inserts — never rewrites, reorders, or deletes an existing line"
      - "a governed product's content never leaves its own repository and owner → inapplicable because no chunk adds an outbound path"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary with a stdout/stderr channel split → conforms. Chunk 04 reports through the doctor health-check surface, which already owns its prefixes and channel; no chunk introduces a new prefix"
      - "text emitted into a governed product names no prawduct-internal identifier → **binds Chunks 03 and 04.** The steady-state form binds every emitted string, not only newly-touched ones. Chunk 04's degraded message and its inserted obligation prose must name the *obligation*, never a backlog id — and #348's own complaint is the mirror image of this norm (a code comment that says a limitation is 'tracked separately' while naming nothing), so Chunk 03 fixes that comment by naming the item **in a comment**, which is not emitted text"
      - "the governance ledger has a single writer; agents never hand-author it → inapplicable because no chunk writes a ledger line"
  - artifact: operational-spec
    dispositions:
      - "versioning is conservative — a small feature is a patch bump → conforms (this batch is a patch release)"
      - "gitflow: features branch off `develop` and merge back → conforms (`fix/drift-burndown` is off `develop` at `fd9edea`)"
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** Seven already-triaged tracker items, each carrying a stated problem, a repro or a named
site, and a fix-shape. No discovery is owed. Every item's *ask* was re-read against the current
tree before this plan was written rather than trusted from its citations — which is how the two
corrections below were found, and how the Chunk 01 census was measured rather than guessed.

**The cluster was the owner's choice**, made against a three-way comparison (drift-plus-the-check /
surface reduction / cheap docs sweep). The theme is one failure mode: *a durable record asserting
something the tree does not support*. Six items are instances; **#193 is the mechanical detector
for the largest instance class**, which is why it leads.

**Two items' stated Expected was overridden by evidence, both recorded as decisions below:** #193's
artifact surface (the census says the naive scope is 195 unresolved refs, 102 of them in three
completed historical plans) and #162's fix shape (the *one home* norm forbids the three-synchronised-
copies remedy the item asks for).

**Open assumptions / unknowns:**

- [ASSUMPTION: #193's artifact surface covers **live** artifacts only, excluding completed plans |
  HIGH impact | user can veto] Measured on this tree 2026-08-02: 195 unresolved backticked path
  refs across 37 artifact files, of which **102 sit in three completed plans** (`v1.5-critic-
  proportionality-plan.md` 57, `v1.6.0-advisory-infrastructure-plan.md` 40, `v1.4-maintenance-plan.md`
  5) that describe the **pre-`plugin/` tree layout** — `tools/lib/core.py`, `agents/critic/SKILL.md`.
  Those references were accurate when written and rewriting them would falsify the record; allowlisting
  them individually would blow the "small and reasoned" constraint #193 sets for itself. The learning
  that earned this item names *durable planning artifacts read by future sessions as current
  instruction* (DOC-2R7M) — a completed plan is not current instruction. **Chunk 01 therefore scopes
  the artifact surface to live artifacts and makes "live" a mechanical predicate, not a hand-list.**
  If the owner wants completed plans swept too, that is a separate item with a different remedy
  (a historical-layout note at each plan's head, not 102 edits).
- [ASSUMPTION: #162 is fixed by one-home-plus-references, not by restating both enumerations | MED
  impact | user can override] The item's Expected reads *"Both enumerations restated to match, with
  the falsifying grep carried alongside so a fourth copy cannot hide."* That produces three
  synchronised copies of one rule statement and the falsifying grep is a mitigation for a shape the
  governing norm rejects outright. See [DECISION] under Chunk 02. Restating all three is the
  reversible-but-wrong option; if the owner prefers it, it is a one-line change to Chunk 02.
- [ASSUMPTION: #351's check extends the doctor surface rather than the janitor's | LOW impact | user
  can override] #351 names two open questions — whether it extends health check #5, and whether the
  inserted prose comes from a shared constant. This plan answers: **a new check, not an extension of
  #5** (#5 asserts existence and stopping there is its job; a marker check has a different verdict and
  a different repair), and **yes, a shared constant** (GOV-2R8K's argument, and the alternative is a
  second home for the obligation text — the very norm this batch is about). Doctor rather than janitor
  per `docs/doctor-vs-janitor.md`, though note the project-preferences norm index names doctor as an
  enforcement mechanism for exactly one row today; this widens it by one and the reviewer should say
  so if that is the wrong organ.
- [ASSUMPTION: the two unmerged sibling branches merge after this one and resolve their own conflicts
  | LOW impact | user can reorder] Measured 2026-08-02. `fix/backlog-block-field-writes` (primary
  checkout, 8 commits, **reviewed and complete but with no PR and unpushed**) touches
  `plugin/lib/backlog/*`, `plugin/skills/backlog/*.md` and three test files; `fix/review-loop-
  termination` (267 behind, 2 ahead, no PR) touches `methodology/building.md` and the two critic
  protocol files. **This plan touches none of those files for content** — the only overlap is the
  shared append-at-top records (`change-log.md`, `learnings*.md`, `project-state.yaml`), which conflict
  textually and resolve trivially. **One real interaction:** Chunk 01's check will scan the skill and
  methodology prose those branches edit, so whichever merges second inherits the check. That is the
  check working, not a conflict.

**What would raise confidence:** N/A at High. The two HIGH/MED assumptions are both one-line owner
answers and neither blocks a chunk from starting.

## Status

<!-- Derived view (`views_enabled: true`). Mark a chunk shipped by adding a change-log entry
     tagged scope=drift-burndown / status=shipped, then run regen-views.
     Do NOT hand-flip the checkboxes. Stays [ ] on this branch until the release ships —
     a built chunk is recorded in Context below, not by its checkbox. -->

- [ ] Chunk 01: The detector, and the scope decision that keeps it honest (#193)
- [ ] Chunk 02: Three records that outlived what they describe (#162, #196, #179)
- [ ] Chunk 03: The directive that is dark everywhere it is needed (#348)
- [ ] Chunk 04: Two doctor surfaces that disagree with reality (#241, #351)

Context: Plan authored 2026-08-02 on `fix/drift-burndown` off `develop` at `fd9edea`, from the
owner's choice of the drift cluster over surface-reduction and a docs sweep. Seven items, all
claimed on the tracker at authoring time (24h TTL) — **claiming is new practice this batch**, and it
exists because #550 was independently built to completion on a sibling branch while the pick agent
reported it unclaimed and buildable. `active_build_plan` still points at `build-plan-v3.2.0-golive.md`
**by design** and must not be repointed: the gates resolve the *branch's* plan by scope, and the
golive plan is retained until the pending `develop`→`main` release regenerates it.

**Chunk 01 BUILT 2026-08-02** (#193) — `tests/test_path_reference_resolution.py`, 8 tests, plus one
live fix in a shipped file. **The plan's own Chunk 01 design was superseded before any code was
written**: the live-artifact predicate was dropped once form-based extraction reduced the surface
from 195 unresolved references to 6, and the named allowlist came in at **one** file against a
budget of four. The distinction that did the work — *a citation is not a reference* — is not in
#193's text; it came from the measurement and from the sibling `${CLAUDE_PLUGIN_ROOT}` check.

Two extractor defects surfaced from the tests, not from reading: requiring a file extension in
command position would have missed `plugin/bin/prawduct-hook`, the extensionless path whose
relocation earned the item; and a markdown link quoted inside a code span was followed as a link, so
the check reddened on this plan. Both are the same rule one level down.

**Two review rounds, 0 blocking in both.** The chunk pass (4 warnings, 1 note) found the
non-vacuity floor guarding references *extracted* rather than *checked* — so widening the unbounded
record predicate would have darkened the check with the suite green — and a version-shaped exclusion
that exempted the pending release plan. The verify pass (2 warnings, 1 note) found that the first
fix to the `plugin/` fallback **scoped it by file and claimed that closed the finding, when skills
live inside the retained scope**; the closing fix scopes by form as well. That is a record asserting
what the code does not support, written by me, inside the batch whose subject is exactly that.

**Coverage and census figures have one home: the change-log entry for this chunk.** They are not
restated here — an earlier draft of this paragraph carried three post-fix numbers that were stale
within the hour, which is the defect being burned down appearing in the burndown's own plan.

**Release deferral, reaffirmed 2026-08-02.** The owner was offered release-first and chose to keep
burning down. The `develop`→`main` promotion is now **three batches deep** and `#533`'s filer stays
blocked behind `ref: main` until it ships. This is a recorded decision, not an oversight — do not
re-litigate it at every chunk close, and do not let it silently become four.

## Scaffolding

### Build & Test Configuration

Unchanged. `python3 -m pytest tests/ -q` runs everything (`test_command` in `project-state.yaml`
adds the junit path used by `test-evidence record`). No new dependencies, no scaffold changes.

**Verify hook behaviour with `python3 plugin/bin/prawduct-hook` from this checkout.** A `$PATH`
`prawduct-hook` resolves to a different tree and will silently answer for the wrong code — and this
batch is *about* surfaces that answer confidently for the wrong thing, so getting caught by it here
would be its own joke.

**Three worktrees share ten cores.** Running `-n auto` in all of them roughly doubles a suite run;
stagger rather than parallelise.

### Verification Strategy

**Chunk 01 is verified by what it catches, not by its own green.** A path-resolution check that
passes on the repo it was written against has proved nothing — and this repo is the reference repo,
so the standing trap applies directly (*a nudge narrowed to pass a zero-fire acceptance criterion
suppresses the exact signal on the reference repo*). The chunk therefore records a **pre-build
census** — the measured unresolved-reference counts per surface, taken before any fix — and verifies
the check by reproducing those numbers, then by deliberately breaking a resolving path in each
covered surface and confirming a red. Its acceptance is *the census is explained*: every unresolved
reference is fixed, allowlisted with a named reason, or out of scope by the recorded predicate. A
count that merely drops is not evidence.

**Chunks 02 and 03 are verified by the falsifying query, not by the edit.** For each corrected
record, the acceptance is that the *concept* query returns nothing — not that the named site was
edited. This is the repo's own standing rule and it has been paid for repeatedly on the last three
branches, most recently when a prose sweep run over a phrase rather than a concept stopped two sites
short.

**Chunk 04 is verified against a repo that is not this one.** Prawduct's own `learnings.md` carries
the descent-obligation marker, hand-added long before `init_product` existed, so every check run from
inside prawduct comes back green — that blind spot is *why* #351 survived review. Verification builds
a throwaway product-shaped fixture without the marker and confirms the check reports degraded, that
the offered repair inserts **above the first rule**, and that an append-to-end insertion would fail
the position assertion.

### Why four chunks

Four surfaces, four review scopes: a new test (01), durable records (02), the hook's directive
trigger (03), the doctor surface (04). Chunks 02 and 03 could merge on size, but not on review kind —
02 is prose whose defects are claims, 03 is a trigger whose defect is reachability, and a single
review pass over both is the shape that has repeatedly let prose defects through on this repo.

## Build Chunks

### Chunk 01: The detector, and the scope decision that keeps it honest (#193)

- **Description:** Build the check that verifies intra-repo path references **resolve**, complementing
  `tests/test_plugin_packaging.py`'s `NOT_DISTRIBUTED_DIRS`, which pins only where files may *live*.
  Structural enforcement earned by a third recurrence of the `relocating a source file: sweep every
  READER of the old path` learning. The surfaces are covered in the learning's own **sweep order, by
  how silently each fails**: `allowed-tools:` grants → skill and methodology prose → live durable
  artifacts. Docstrings are explicitly out of scope (lowest stakes, highest false-positive rate).
  The named risk is false positives from prose that mentions paths illustratively; the mitigation is
  extraction scoped to **command position and front-matter**, plus a small, reasoned allowlist.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/nonfunctional-requirements.md` (the proportionality
  norm's yield obligation binds this new control), `.prawduct/artifacts/architecture.md` (*every fact
  has one home* — a path is a fact)
- **Deliverables:** new `tests/test_path_reference_resolution.py` — the extractor, the per-surface
  cases, the allowlist with a reason string required per entry, and the live-artifact predicate;
  a short block in `plugin/docs/` or the test's own module docstring recording the census and the
  scope decision so the next reader does not re-derive it.
- **Tests:** the new file is the deliverable. Each surface gets a red-verified case: break one
  resolving path per surface and confirm exactly that surface reddens.

**[DECISION — SUPERSEDED 2026-08-02, before any code: extraction is by REFERENCE FORM, and the
live-artifact predicate is dropped entirely | measurement replaced the hypothesis | user can veto]**

The plan first proposed scoping the artifact surface with a mechanical live-artifact predicate,
because the census counted 195 unresolved refs and 102 of them sat in completed plans. That census
extracted **every backticked path token**, which is the wrong extractor — it cannot tell a path
someone is told to *use* from a path someone is *talking about*, and the plan's own six unresolvable
citations are the proof.

The existing sibling check named the fix. `test_no_shipped_file_points_at_an_unshipped_plugin_root_
path` keys on `${CLAUDE_PLUGIN_ROOT}/…` — a **form** that unambiguously means *go read this*. Applying
the same idea, the high-signal forms are: **`allowed-tools:` front-matter grants**, **command
position** (a backticked span whose first token is an executable), and **markdown links**
`[text](path)`. A bare backticked path in a sentence is a citation and is not extracted.

**Re-measured across all 233 tracked `.md` files with relative links resolved against the containing
file** (the first pass got this wrong and over-reported 21 link failures that were simply relative):

| form | unresolved |
|---|---|
| markdown links | **1** |
| command position | **5** |
| `allowed-tools:` grants | **0** |

Six total, and the whole 195-citation problem evaporates because citations are never extracted.
**No live-artifact predicate is needed, and the allowlist is four historical-record entries rather
than a hand-list of excluded files.** This is the difference between a check with a real catch and
one whose allowlist is longer than its catch.

**The one markdown-link failure is a genuine defect in a shipped file, and it is this chunk's proof
of value:** `plugin/docs/principles.md:5` links to `[learnings file](../.prawduct/learnings.md)`.
From `plugin/docs/` that resolves to `plugin/.prawduct/learnings.md`, which does not exist here and
is equally broken in a consumer's plugin cache — the reader is sent to the product's learnings file
and lands nowhere. It is the same class the `${CLAUDE_PLUGIN_ROOT}` test already guards, arriving in
the one form that test cannot see.

The five command-position failures are `.prawduct/backlog.md` and `.prawduct/change-log.md` naming
the pre-relocation `tools/prawduct-*.py` (frozen history — `backlog.md` is frozen by the Issues
cutover and the change-log is a record, so both are allowlisted **as record files, one entry each,
not one per reference**) and `documentation/prompt-management-requirements.md` naming
`config/models.yaml`, a requirements doc describing a config that does not exist yet — a forward
reference, allowlisted with that reason.

**A citation is not a reference, and this plan proves it.** Measured against this file at authoring
time: it carries **six** path tokens that do not resolve — `tools/lib/core.py` and
`agents/critic/SKILL.md` (quoted as examples of the pre-`plugin/` layout), `skills/foo/bar.md`
(quoted as planning.md's worked example), and `.prawduct/artifacts/build-plan.md`,
`.prawduct/.handoff-notes.md`, `.prawduct/sync-manifest.json` (quoted as known-benign runtime and
product-side paths). Every one is *mentioned in order to discuss it*, and a check that reddens on
them reddens on its own build plan on day one. This is the named false-positive risk arriving before
any code was written, and it is why the artifact surface cannot be "every backticked path in a live
artifact": the artifact surface is dominated by **evidence citations** — `refs:` lines, quoted
sites, worked examples — while the instruction-bearing content a future session actually follows is
in deliverables, scaffolding and command position. **The builder's first task is to make that
distinction mechanical**, and if it cannot be made mechanical with a small reasoned allowlist, the
honest outcome is to cover the two prose surfaces properly and report the artifact surface as
deferred with the reason — not to ship a check whose allowlist is longer than its catch.

- **Acceptance criteria:**
  - Each of the six measured failures is **fixed** or **allowlisted with a named reason**, and the
    chunk states which applies to each. The `principles.md` link is fixed, not allowlisted — it is a
    live defect in a shipped file.
  - **The check is green on this plan file**, whose six unresolvable *citations* are listed above.
    If it reddens on them, the extraction rule is wrong — not the plan. This is the single sharpest
    acceptance criterion in the chunk: the plan is the adversarial case, and it was written before
    the check existed.
  - The check reddens on a deliberately broken path in **each** covered form — grant, command,
    link — verified one form at a time. A form with no red-verified case is a form that is not
    actually covered.
  - **The scan is proved non-vacuous**, following the precedent already set in
    `tests/test_plugin_packaging.py` (`assert len(scanned) > 50`): an extractor that silently
    matches nothing passes forever. Assert a floor on both files scanned and references extracted —
    the second matters more, since a regex that stops matching is the likely failure and a file
    count would not notice.
  - Relative links resolve against the **containing file**, not the repo root, with a case pinning
    it. Getting this wrong over-reported 21 failures during the census and would have sent the
    builder to fix twenty non-defects.
  - The allowlist is **four entries or fewer**, each with a reason, and record files are allowlisted
    **as files** rather than one entry per reference — an allowlist that grows per-reference is the
    ceremony #193 warned about.
- **Done when:** acceptance criteria pass · `/prawduct:critic` · change-log entry
- **Critic mode:** (inferred — `chunk`)
- **Type:** code

### Chunk 02: Three records that outlived what they describe (#162, #196, #179)

- **Description:** Three durable records asserting something the tree does not support. **#162** — the
  reconciled-files carve-out was amended in `architecture.md` to name `CLAUDE.md`, and two sibling
  artifacts restating the same enumeration were not updated *in the same bundle that amended it*, so a
  reader reaching `security-model.md` first concludes the plugin violates its own least-authority norm.
  **#196** — `cross-cutting-concerns.md:42` claims Discovery and Builder coverage for the
  backend-declaration concern, attributing text to `discovery.md` and `building.md` that neither file
  contains and **no commit ever added**; the row makes the matrix report three stages of coverage where
  only Critic judgment is real. `BLD-4Q8W` is the identical failure on row `:36`, so the fix is
  two-part: correct the row, then sweep the rest. **#179** — VRF-010 verified all three relationship and
  timeline readers live and discharged MIG-3, and that closure never reached `project-state.yaml`
  (which still calls the shapes fake-verified and cites a now-archived item) or the golive plan's
  Chunk 09 flip list.
- **Depends on:** Chunk 01 — not for code, but because the detector's census may name additional
  live-artifact references that belong in this chunk's sweep rather than in an allowlist.
- **Artifacts consumed:** `.prawduct/artifacts/architecture.md` (the amended norm and the *one home*
  norm), `.prawduct/operator-verification.md` (VRF-010, the discharge evidence)
- **Deliverables:** the least-authority enumeration given one home with references from the other two
  (`.prawduct/artifacts/security-model.md`, `.prawduct/artifacts/api-contract.md`,
  `.prawduct/artifacts/architecture.md`); the corrected row and the swept remainder in
  `.prawduct/cross-cutting-concerns.md`; the corrected `integration_test_strategy` claim in
  `.prawduct/project-state.yaml` and the completed flip list in
  `.prawduct/artifacts/build-plan-v3.2.0-golive.md`.
- **Tests:** none directly — this is prose. The verification is the falsifying query per record
  (below), which is stronger here than an assertion would be.

**[DECISION: #162 is fixed by giving the least-authority enumeration ONE home and leaving references,
not by restating it in three artifacts | the *every fact has one home* norm names a rule statement as
a fact and prescribes delete-one-over-update-both, on the evidence that coherence findings are the
largest Critic category and nearly all are one fact copied and drifting; #162's own Expected asks for
three synchronised copies plus a falsifying grep, which is a mitigation for the shape the norm
rejects — and the item is itself the second recurrence of this exact enumeration drifting | user can
override]** `architecture.md` is the home (it carries the norm and its amendment history);
`security-model.md` and `api-contract.md` carry a one-line reference to it. The falsifying grep stays
in the chunk's acceptance as a *check*, not as a durable mitigation — with one home there is nothing
for a fourth copy to hide behind.

**Constraint on #179 the builder must not lose:** this is about the flip **list** being complete, not
about flipping now. The release convention holds; nothing is marked shipped ahead of Chunk 09. Per D4
a `status=shipped` call stays explicit and human-made, never inferred from an audit — recording
discharge evidence is not a status change. `project-state.yaml` cites the archived item **by id**
under an explicit do-not-renumber instruction, so the propagation corrects the surrounding claim and
leaves the id alone.

- **Acceptance criteria:**
  - **#162:** a concept query for the least-authority enumeration returns exactly one authoring site
    and two references — not three enumerations that happen to agree. The query is over the *concept*
    (the carve-out's membership), not over a phrase already known to be wrong.
  - **#196:** the corrected row states what is true, and the **sweep is reported as a query result**:
    every remaining row's cited coverage was checked against the file it attributes, and the chunk
    names how many rows were checked and how many were wrong. A count of rows fixed is not the
    deliverable; the falsifying query returning nothing is.
  - **#179:** Chunk 09's flip list carries the flips it owes; `project-state.yaml` no longer claims
    the shapes are fake-verified; VRF-010 is recorded as discharge evidence. Nothing is flipped to
    shipped.
  - No new copy of any corrected fact is introduced anywhere, including in this plan.
- **Done when:** acceptance criteria pass · `/prawduct:critic` · change-log entry
- **Critic mode:** (inferred — `chunk`)
- **Type:** doc-only

### Chunk 03: The directive that is dark everywhere it is needed (#348)

- **Description:** `_GREEN_IS_EVIDENCE_DIRECTIVE` fires off `changes_referenced`, which is populated by
  `plugin/bin/test-reference-verify`, which skips every non-Python file. In a Swift/Go/TS/Rust/C#
  product the set is empty, the trigger never fires, and the directive is **silently dark in a product
  whose owner has no way to observe that it was supposed to fire**. This is a standing Direction norm
  in violation, not merely a bug: *prawduct must never be specific to Python; gates dispatch per file
  by language, never per repo*. It matters beyond one dormant directive because code-delivered
  directives are the only proven path by which prawduct ships a general learning into a consuming
  product — if one of the two exemplars is Python-only, that path is narrower than the items citing it
  assume.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/architecture.md` (the never-Python-specific norm)
- **Deliverables:** a language-agnostic trigger for the directive in `plugin/bin/prawduct-hook` —
  the changed-file set or test-evidence presence, rather than Python-symbol references; and the
  code comment that claims the limitation is "tracked separately" while naming nothing, corrected to
  name the item.
- **Tests:** a red-verified case proving the directive fires for a changed-file set containing **no
  Python at all**. This is the whole point of the chunk and the one assertion that cannot be omitted:
  a test using a Python fixture would pass today and prove nothing.

**Scope boundary the item sets explicitly:** this is *not* COV-4M2J. Same root cause, different
consequence, plausibly a different fix — and this closes by re-triggering off a language-agnostic
signal with **no** language-aware coverage floor in existence. Do not let it grow into the L-sized
requirements pass it does not depend on. The cheap half — naming the item in the comment — is worth
doing regardless, because a tracking reference pointing at no id is not a tracking reference.

- **Acceptance criteria:**
  - The directive fires on a non-Python changed-file set, verified red first.
  - The Python path still fires — the change widens the trigger, it does not move it.
  - The code comment names the tracking item rather than gesturing at one.
  - No language-aware coverage floor is introduced; if the builder finds one is needed, that is a
    finding to file, not scope to absorb.
- **Done when:** acceptance criteria pass · `/prawduct:critic` · change-log entry
- **Critic mode:** (inferred — `chunk`)
- **Type:** code

### Chunk 04: Two doctor surfaces that disagree with reality (#241, #351)

- **Description:** Two reports that answer confidently for a state the repo is not in. **#241** —
  `cmd_coverage_status` computes layer-0-active purely from *not `structural_characteristics_recorded`*,
  without the `_has_product_definition_work` gate that the ambient briefing nudge and doctor Health
  Check #6 both apply, so on a freshly-onboarded empty repo the report says coverage is degraded while
  the nudge it claims to mirror correctly stays silent. Bounded and cosmetic — a report line, no wrong
  behavior — and worth correcting rather than documenting precisely because the report's own claim is
  that it reads the *same* expectation table. **#351** — `/prawduct:learnings` points every product at a
  `prawduct:descent-obligation` marker that only newly-scaffolded products receive, because
  `init_product.py` guards the starter write with `if not learnings.is_file()`. **The defect is closed
  for the empty set and open for the real one**: the live fleet is entirely already-onboarded, and
  nothing — not onboard, not migrate, not a re-run — ever backfills it. Verified: exactly three sites
  mention the marker (the starter constant, the reader that points at it, and a position guard test).
  No detector, no repair, no advisory anywhere between the writer and the reader.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/security-model.md` (owner approval at the operation
  level; untrusted state is data), `.prawduct/artifacts/architecture.md` (advice fails soft),
  `plugin/docs/doctor-vs-janitor.md` (why doctor)
- **Deliverables:** the `_has_product_definition_work` gate on the layer-0 determination in
  `cmd_coverage_status`; a new doctor health check that detects a `learnings.md` preamble carrying no
  descent-obligation marker, reports **degraded**, and offers a position-aware insertion; the
  obligation prose lifted to a shared constant consumed by both `init_product.py` and the repair.
- **Tests:** the coverage-status agreement pinned on a fixture with no product work — the report and
  the nudge must agree, asserted against **both** surfaces rather than against a hardcoded expectation.
  For the marker check: a product-shaped fixture *without* the marker (this repo has it, so a fixture
  is the only honest test), an assertion that the repair inserts above the first rule, and an
  assertion that an append-to-end insertion **fails** — position is load-bearing, and a naive presence
  check would accept the wrong answer.

**Position is the whole check.** The existing guard pins that a reader meets the obligation *before*
the rules it governs. A repair that appends to the end satisfies a presence check and is still wrong,
so the position assertion is not a refinement of the marker assertion — it is the second half of it.

**The repair is offered, not applied.** Inserting into a product's authored `learnings.md` is an edit
to a file the framework did not write; per the security-model norm it takes an informed confirmation
naming what changes. It inserts only — it never rewrites, reorders, or removes an existing line — and
on a malformed or unreadable file it reports and declines rather than guessing.

- **Acceptance criteria:**
  - `coverage-status` and the ambient nudge agree on a fresh repo with no product work, asserted
    against both surfaces.
  - The new health check reports degraded on a marker-less fixture and stays silent on one with the
    marker correctly placed.
  - The offered repair inserts above the first rule; an append-to-end variant fails the position
    assertion.
  - The obligation prose has one home, consumed by both writers.
  - The check is verified against a fixture, **not** against this repo — a green run here proves
    nothing, which is the blind spot that let #351 ship.
- **Done when:** acceptance criteria pass · `/prawduct:critic cumulative` · change-log entry ·
  forward notes · reflection
- **Critic mode:** (inferred — `cumulative`)
- **Type:** cumulative-final

## Early Feedback Milestone

**Milestone chunk:** 01 — the detector's census is the first honest read on whether this batch's
premise holds. If the covered surfaces turn out to be nearly clean once illustrative prose is excluded,
then the drift this batch targets lives in *claims* rather than *paths*, and Chunks 02–04 are the whole
value while Chunk 01 is insurance against the next relocation. Either outcome is worth knowing at chunk
one rather than at the PR.

**Note on the usual first-chunk rule:** this plan has no walking skeleton. A burn-down batch against
existing surface has no architecture to prove, and inventing a vertical slice would be ceremony. Chunk
01 leads because it is the measurement the other chunks are calibrated against, not because it is a
skeleton.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes — per-chunk commit is what
scopes `chunk`-mode reviews, and this plan relies on it. The last chunk's `cumulative` review makes the
branch PR-ready; `/prawduct:pr create` is gated on it and runs when the owner asks.

- **After Chunk 01:** confirm the check earns its keep. Two failure modes to check for explicitly: a
  check narrowed until it passes on this repo (the reference-repo trap — the acceptance criteria are
  written to make this visible, but they are only as good as the census being honest), and an allowlist
  that has quietly become the answer to every awkward case. State the allowlist's size and defend it.
- **After Chunk 02:** verify the corrections did not each become a new copy. This batch is about facts
  with too many homes, and the most likely way to fail it is to fix three records by writing a fourth.
- **After Chunk 04 (cumulative):** full-bundle review. Verify specifically that the batch **reduced**
  the number of places a fact lives rather than adding controls on top of the duplication — two chunks
  add governance surface (#193's check, #351's health check) and the counterweight is that Chunk 02
  removes two copies outright. Check that the proportionality yield obligation was **discharged with
  the census** rather than declared.
