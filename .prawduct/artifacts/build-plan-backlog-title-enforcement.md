---
artifact: build-plan
version: 2
scope: backlog-title-enforcement
depends_on:
  - artifact: backlog-import-title-boundary-discovery
governed_by:
  # Every norm in each artifact gets a line — "that one doesn't apply" is an
  # interpretation, and it belongs where a reviewer can disagree with it.
  - artifact: data-model
    dispositions:
      - "Every issue written to the backlog store conforms to the issue standard's §1 title rules, on every write path → conforms, and this plan is the tracking item (#614) that moves the norm's Status from in-transition to steady-state. All three paths gain the refusal"
      - "Retroactivity: contain — everything written from here conforms; what is already stored does not change → conforms, and it is LOAD-BEARING for the update-path ruling below. The containment boundary is the write path, so a `status=shipped` update that writes no title leaves an already-stored non-conforming title alone by design. The rejected alternative (lint the resulting title on every update) would have breached this norm by forcing retro-conformance one issue at a time, unreviewed"
      - "Governance verdicts are computed from the append-only fact ledger, never mutable model-written state → inapplicable because no governance verdict is computed here; this is the backlog adapter's write path, not the Critic data plane"
      - "Facts are immutable and append-only → inapplicable because this work writes no fact to the evidence store"
      - "Derived views are disposable and never authoritative → inapplicable because no view is read or written"
      - "A fact written by a newer schema is a loud block → inapplicable because no fact is read for its schema on this path"
      - "Two stores, two lifetimes → inapplicable because no store is added and neither store's lifetime changes"
      - "`backlog_service_repo` selects the authoritative backlog store → conforms — every path changed here is already behind the adapter that routes on the scalar; the markdown backend's hand-authored bullets are explicitly out of scope per the title norm's own Scope line"
  - artifact: architecture
    dispositions:
      - "Authority fails closed; advice fails soft → conforms. The title refusal is authority and fails closed (an unparseable title is refused, not waved through); the non-title-update lint warning is advice and fails soft (it never blocks the write)"
      - "Prawduct guides and reviews; it never implements → inapplicable because this changes prawduct's own backlog adapter, not any product's code"
      - "Every fact has one home; every other mention is a reference → conforms — §1's title rules stay solely in `documentation/backlog-service-issue-standard.md`; the norm binds *that* they are enforced and this plan restates neither"
      - "Written in Python, never specific to Python → conforms — title linting is language-agnostic text validation"
      - "Local-first: governance coordination is process-spawn + atomically-written files + the git object database → inapplicable because no coordination surface changes"
      - "An independent reviewer never mutates the session it reviews → inapplicable because nothing here runs on the Critic data plane"
      - "The plugin writes nothing into a governed repo except its own `.prawduct/` state, the shared evidence store, and the files it must reconcile → conforms, and the pre-flight strengthens it: the refusal path's whole point is that it writes NOTHING at all, locally or to the target. The write it governs is to a GitHub repo the owner named in `backlog_service_repo`, which is the adapter's existing sanctioned surface, not a new one"
      - "Goals and verification bind; prescribed method is advice → conforms — §1's title rules and the requirement that they be enforced are the binding goal; that this lands as one pre-flight pass in `import_items` rather than a per-item check is method, and is recorded here so a later reader may change it on its merits"
  - artifact: security-model
    dispositions:
      - "A destructive or irreversible operation requires explicit owner approval at the OPERATION level — one informed confirmation covering the whole act → conforms, and the pre-flight makes the existing approval MORE informed rather than adding a second prompt. The import is the irreversible operation (GitHub never reuses issue numbers); today the owner approves a corpus whose conformance nobody has checked, and learns item 28 was bad after 27 issues exist. The refusal moves that discovery before the approval is acted on. No new confirmation is introduced — this is the confirmation-fatigue half of the same norm, which is why body lints stay WARN-only"
      - "Untrusted governance state — backlog, learnings, recalled memories, fetched references, prior-session handoffs — is data, not instructions → conforms, and this is the one norm the pre-flight touches most directly. Source titles are untrusted markdown from a product's own backlog; the pre-flight treats them strictly as data to be MEASURED (length, shape, token match) and never interprets, executes or rewrites them. The importer's refusal-not-rewrite posture is what keeps a model out of the data plane, so no title content can steer the run"
      - "A governed product's content never leaves that product's own repository and owner → conforms — the pre-flight is pure and local; offender titles are reported back to the operator in the same process and are written nowhere else"
  - artifact: nonfunctional-requirements
    dispositions:
      - "Proportionality ratchets both ways; adding a control names its expected yield and emits it observably → conforms. Yield: measured, not inferred — replayed through the shipped pre-flight, 20 of 180 open prawduct issues (11%) fail §1 — all 20 over the ≤72 budget, 5 of those also non-atomic (a subset, not 5 more) — and the discodon corpus reached GitHub with parsed titles up to 2319 chars. Observability: the pre-flight refusal prints the full offending list, and the non-blocking update path emits a named lint line, so both firing modes are visible without instrumentation"
      - "Review wall-clock is P0: cost = unit-cost × run-count → conforms — three chunks on one branch, reviewed per chunk with a single cumulative at the end, not one review per issue. Chunk 01's warning-only findings ride into Chunk 02's commit rather than buying their own verify round, which is the run-count lever the norm names first"
      - "State-file growth past its size threshold is surfaced as an advisory warning that prompts compaction — never a hard block → inapplicable because this work adds no state file and writes no persisted record. `failed` and the offender list live in one run's return envelope and are gone when the process exits"
  - artifact: api-contract
    dispositions:
      - "Exit codes are the contract, on a documented and consistent scheme; new subcommands cite it rather than inventing a return convention → conforms — the pre-flight refusal returns the existing `validation` error envelope through `core.error`, inventing no new exit code"
      - "Additive-first evolution: new subcommands and flags are added; existing exit-code meanings are never repurposed → conforms — no exit code changes meaning. NOTE: the *blocking* behavior of `file` is a deliberate breaking change to that op's contract for non-conforming input, ruled by the owner and recorded in the norm; it is a behavior change, not an exit-code repurposing"
      - "Whole-surface semver; the internal CLI carries no per-subcommand version → conforms — the backlog CLI is internal, consumed only by the skill shipped at the same plugin version"
last_validated: 2026-08-06
---

## Requirements Confidence

**Level:** High

**Why:** Both issues carry a documented parent — `backlog-import-title-boundary-discovery.md` §5
items 3–4 (#612, recorded DEFERRED not descoped) and §4b/§4c (#614) — and the one contradiction
that held #614 at `stage: requirements` was ruled by the owner on 2026-08-06 and is already
recorded in three places on `develop`. Problem, success and scope are each statable in one
sentence. The one genuinely open question — what `update` gates on — was put to the owner this
session and ruled before any code was written (below).

**Owner ruling 2026-08-06, on the update path:**

`[DECISION: on `update`, the blocking title lint gates the title BEING WRITTEN, not the issue's
resulting title. A non-title update proceeds and emits a named, non-blocking lint line naming the
non-conformance | owner ruled 2026-08-06, after the agent surfaced that an LLM — not a human — sits
at the write on `file`/`update` | user can veto]`

**Why this shape, engaging the norm's why.** The question was first framed as "~25 issues become
un-updatable" (the real figure is 20 — the non-atomic set is a subset of the over-budget set, not additional). The owner asked whether an LLM was in the loop, and verification changed the
answer: nothing automated calls `file`/`update` (swept across `plugin/hooks/`, `plugin/lib/`, the
release path — every `status=shipped` hit in `views.py` / `release_readiness.py` /
`buildplan_refs.py` is a change-log tag, a different namespace). Only an agent running
`/prawduct:backlog` reaches them. So broad enforcement would not *block* those 20 issues — it would
make an agent **auto-retitle** them to get past the gate, one at a time, as a side effect of
archiving them, with no human review and none of the aggregate owner approval that §4b
deliberately preserves for the import scrub. That is §4c's over-split entrenchment arriving through
a second door, and it is a direct breach of the title norm's own `Retroactivity: contain`.

**Open assumptions / unknowns:**

- `[ASSUMPTION: per-item failure isolation is error-class-scoped — `validation` (422) records the
  item and continues; `auth` / `not_found` / `unavailable` / exhausted `rate_limited` keep today's
  resumable cut | HIGH impact | user can widen or narrow]` #612 says only "a write failure records
  that item and continues." Taken literally that turns a revoked token into 396 futile API calls
  and a 396-line failure list instead of "your token expired." `transport.py:737-769` already
  classifies into exactly these codes, so the split needs no new taxonomy.
- `[ASSUMPTION: a consecutive-`validation`-failure breaker cuts the run | MED impact | user can
  drop it]` Pre-flight makes the known 422 cause unreachable, so residual validation failures
  should be rare; a run where they are not is a systematically bad corpus, and hammering the API
  396 times to prove it is waste.
- `[ASSUMPTION: the pre-flight validates §1 title conformance, not only the 256-char GitHub cap |
  LOW impact | user can narrow]` This is what makes #612's pre-flight *be* #614's import-path
  enforcement rather than a second, weaker gate that #614 would immediately replace.

## Status

- [ ] Chunk 01: The import loop validates before it writes, and one bad row stops being fatal
- [ ] Chunk 02: `file` and `update` refuse a non-conforming title they are asked to write
- [ ] Chunk 03: The dedup sweep asks whether one fix would close all of these

Context: authored 2026-08-06 on `fix/backlog-title-enforcement` off `develop` at `486d453`
(v3.2.6 released; #605, #615 and #616 merged-but-unreleased). Closes **#612** and **#614**.

**ALL THREE CHUNKS COMPLETE — the empty boxes above are correct and must stay empty** (see the
`views_enabled` note below). Chunk 01 at `1d1881e`, Chunk 02 at `02608c4`, Chunk 03 with the
Chunk-02 review's blocking fix in the commit after them; `git log --oneline 486d453..HEAD` is the
enumeration, because a list written here stops growing the moment a commit edits this paragraph
without adding itself. Suite green — read the count from `prawduct-hook test-status`, not from a
figure transcribed here.

Reviews: `rev-20260807T035551Z-0e1d5837` (`cumulative`, Chunk 01 — 0 blocking, 6 warning, 2 note,
all dispositioned) and `rev-20260807T042936Z-2fe91481` (`verify-resolutions`, Chunk 02 — all six
prior findings verified fixed, **1 blocking**: R-3's `restructure-preview` fix shipped with no
test). That blocker is closed by two tests in `tests/test_backlog_restructure.py`, red-verified
against `1d1881e`'s `cli.py`. The same review's observation 1 caught a **fifth** instance of the
advisory-prose class — `cli.py:111`'s usage text — which this plan's own Chunk 02 surface list had
enumerated and the chunk still missed; fixed in the same commit rather than deferred.

`active_build_plan` still points at `artifacts/build-plan-critic-review-identity.md` and **must not
be repointed** until the `develop`→`main` release ships (gitflow, `methodology/planning.md` "Plan
lifecycle"; the same note is on `build-plan-gate-as-dispatcher.md`, which shipped under it).

The boxes above stay `[ ]`. `views_enabled: true`, so `## Status` is a DERIVED VIEW: `regen-views`
rewrites every checkbox from the change-log's shipped set, this branch's entry is statusless
because its base is `develop`, and hand-flipping is silently reverted at the release. Completion is
recorded in this prose and by the tagged change-log entry.

## Why #612 and #614 are one branch and not two

#614's "import: conform or refuse" **is** #612's pre-flight validation — the same call to
`issuefmt._lint_title` at the same point in `migrate.py`. Built separately, either the pre-flight is
written twice, or #612 ships a length-only gate that #614 immediately replaces. Independently,
§4c's sequencing constraint forbids shipping the enforcement half without the shared-root-cause
question: the intervening window is exactly when a scrub builds a large, tidy, **over-split**
backlog that then has to be merged back by hand. Chunk 03 is not optional polish — it is the
co-ship condition the owner directive attaches to Chunks 01 and 02.

## Verification Strategy

Tests carry most of this. Three things they cannot say:

1. **Replay against a real corpus.** Run the pre-flight (read-only, no writes) against the live
   prawduct backlog export and confirm it names the 20 over-budget and 5 non-atomic titles measured
   this session — a pre-flight that cannot reproduce a hand-measured count is wrong regardless of
   unit tests. **DONE at Chunk 01:** 180 issues in, 20 offenders out — all 20 `title-too-long`, 5 of
   those also `title-non-atomic`. The 5 are a **subset** of the 20, not 5 more; the "~25" figure this
   plan carried in its first draft was the union computed as if they were disjoint.
2. **The isolation path needs a real 422.** Unit tests use a fake transport; at least one exercise
   must drive a genuine GitHub validation rejection (a deliberately over-cap title against a scratch
   repo) and confirm the run continues and reports it at the end.
3. **The refusal has to read well.** `file` and `update` refusals are read by an agent that must
   decide what to do next. Exercise both by hand and confirm the message names the failing rule and
   the offending title, so the next actor's move is obvious without reading the standard.

## Chunk 01's review, and what rides into Chunk 02

`rev-20260807T035551Z-0e1d5837` (`cumulative`, interval `486d4535...1d1881eb`): **0 blocking**,
6 warnings, 2 notes. The review is over — nothing in it required another round.

Two were fixed at once, because both are pure subtraction and neither touches judgeable behavior:
**R-5** removed `fail_at_mutation(times=…)`, a fake capability this branch added, argued for in an
8-line docstring, and then never called (the suite uses `_fail_creates`) — reverted to develop's
version verbatim; **R-6** completed this plan's own `governed_by` dispositions, which covered 6 of
architecture's 8 norms, 1 of security-model's 3 and 2 of NFR's 3, against the standard this plan
states in its own frontmatter comment.

**R-1 through R-4 ride into Chunk 02's commit.** That is not the deferral the review protocol warns
about: deferring to a later *round* buys a round, while riding a commit that is being made anyway
buys none, and Chunk 02 already owns three of the four surfaces. They are enumerated in Chunk 02's
deliverables below so they cannot be dropped. **R-7** (no change-log entry — it will refuse
`/prawduct:pr create`) belongs to Chunk 03, which is where the branch's entry gets written.

The six warnings share one cause worth stating plainly, because it is the same class that dominated
the previous branch: **the enforcement landed in code and not in the surfaces that describe it.**
Chunk 01 made `import` block, and four separate documents still tell a reader the linter is
advisory. One of them — `issuefmt.py`'s own module docstring — was owned by no chunk of this plan at
all, which is how it got missed: the plan enumerated the surfaces Chunk 02 would touch and never
asked which surfaces *Chunk 01* falsified.

## Build Chunks

### Chunk 01: The import loop validates before it writes, and one bad row stops being fatal

- **Description:** The import loop writes before it validates and treats a per-item 422 as fatal for
  the whole run. Add a corpus-wide pre-flight that refuses with the full offending list and zero
  writes, and make a `validation` failure that still occurs mid-run isolate to its item. This chunk
  also discharges #614's `import` row — the pre-flight validates §1, so a non-conforming title
  cannot be imported.

  *Not the "dry run that validates identically" trap.* That learning targets an **optional mode**
  whose validation drifts from the real run's because nothing forces them together. This pre-flight
  is an unconditional phase of every import with no flag to skip it, and it is the only §1 gate on
  the path — there is no second implementation for it to drift from.
- **Depends on:** none
- **Artifacts consumed:** `backlog-import-title-boundary-discovery.md` §5 items 3–4 (the two
  guardrails), §4b (the import-path design that keeps the model out of the data plane)
- **Deliverables:**
  - a pre-flight validator over the whole record set in `plugin/lib/backlog/migrate.py`, run before
    the first write, refusing through `core.error("validation", …)` with every offending item listed
  - error-class-scoped isolation in `import_items` — `validation` records the item into a new
    `failed` list and continues; every other code keeps today's resumable cut
  - a consecutive-`validation` breaker that cuts the run rather than hammering a bad corpus
  - `failed` carried in the success envelope AND in **both** error returns — `import_items` has two
    (`except TransportError` and `except (OSError, json.JSONDecodeError)`), and they are built by a
    different constructor (`core.from_transport_error`) than the success path (`core.ok`), which has
    no slot for the field and drops it silently. **This is the third instance of a named learning
    class in this exact function** — BKL-3K9N (rate-limit path) and BKL-9V2W (TransportError path)
    were the first two. The learning's own instruction: grep the error/exception returns whenever
    you enrich a success envelope.
  - new `tests/test_backlog_import_preflight.py`
- **Tests:** each red-verified against the code that ships:
  - a corpus with one over-cap title → refuses, names it, and the transport records **zero** writes
  - a corpus with several non-conforming titles → the refusal names **all** of them, not the first.
    The offender list is a SET, so assert it is non-empty **and** contains each expected item —
    a membership-only assertion passes against an empty list, which is the "green means nothing was
    looked at" failure the learnings name
  - a resumable cut on the `(OSError, json.JSONDecodeError)` path → `failed` survives, not only on
    the `TransportError` path (the two are separate returns; testing one proves nothing about the
    other, which is how this class recurred twice already)
  - a conforming corpus → pre-flight passes and the run proceeds unchanged (no regression)
  - a mid-run `validation` failure → that item lands in `failed`, the run continues, and the
    remaining items are still imported
  - a mid-run `auth` / `not_found` / `unavailable` failure → today's resumable cut, unchanged
  - an exhausted `rate_limited` budget → today's resumable cut, unchanged (the retry path must not
    be reclassified as item-fatal)
  - N consecutive `validation` failures → the breaker cuts, and the envelope says why
  - a resumable cut after some items failed → `failed` survives into `error.details` (the same
    permanence argument the docstring already makes for accrued warnings)
- **Acceptance criteria:** full suite green; Verification Strategy §1 reproduces the hand-measured
  20 over-budget / 5 non-atomic split against the live corpus; a conforming corpus imports with
  byte-identical behavior to today.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. **Commit first**, then `/prawduct:critic`, and resolve blocking findings.
     <!-- Commit-then-review: `chunk` mode diffs HEAD against the WORKING tree, so reviewing a
          clean tree yields an empty interval and the gate-as-dispatcher refusal declines to
          dispatch. Reviewing after the commit means the reviewed tree IS the commit's tree. -->
  3. Write `.prawduct/.handoff-notes.md` and reflect

### Chunk 02: `file` and `update` refuse a non-conforming title they are asked to write

- **Description:** `file` runs the lint and ignores it; `update` is not verified to lint titles at
  all. Make the four §1 **title** checks blocking on both, scoped per the owner ruling: `file`
  always gates the title it writes; `update` gates a title it is asked to write and otherwise emits
  a named non-blocking lint line. Every **body** and **label** lint stays WARN-only. Then move the
  norm's `Status` from in-transition to steady-state, which is the whole point of the tracking item.
- **Depends on:** Chunk 01 (the `import` row of the same three-path table is already discharged
  there; this chunk must not re-implement it)
- **Artifacts consumed:** `backlog-import-title-boundary-discovery.md` §4b (the three-path table and
  the lifecycle block); `documentation/backlog-service-issue-standard.md` §1 and §4
- **Surfaces this touches** (enumerated up front — this is a project-wide concept landing):
  `plugin/lib/backlog/core.py` (`file_item`, `update_item`), `plugin/lib/backlog/cli.py` (the
  advisory-lint print and the usage text at :111), `plugin/skills/backlog/SKILL.md` (`add` and
  `update` sections), `documentation/backlog-service-issue-standard.md` §4,
  `.prawduct/artifacts/data-model.md` (the norm's Status, Interim rule and Rulings lines),
  `.prawduct/artifacts/project-preferences.md` (the Enforcement index pointer row).
- **Deliverables:**
  - blocking title lint in `core.file_item` — refuses through the existing `validation` envelope
  - blocking title lint in `core.update_item`, **only when a title is in the update**
  - a non-blocking, named lint line on a non-title `update` whose stored title fails §1. *Advice
    fails soft is not advice fails silent* — the line names the rule, the offending title, **and the
    consequence** (this write is proceeding; the title stays non-conforming until someone rewrites
    it deliberately), so a reader is not left inferring what was and was not done
  - the norm's lifecycle updated in `data-model.md`: `Status: in-transition` → `steady-state`, the
    `Interim rule` line retired (its mechanism now exists), and the update-path ruling recorded as a
    `Rulings:` line with its why
  - §4 of the issue standard states the update-path scope, so a reader meets the rule where it lives
  - the preferences Enforcement index row loses its now-false parenthetical *"(blocking once #614
    lands; advisory today — all three write paths non-conforming)"*. **Registry-goes-stale was the
    dominant finding class of the last branch — four instances, three costing a review round each.**
    This row and the `data-model.md` lifecycle above it are this chunk's registry debt; they land in
    the same commit as the code, not after it.
  - new `tests/test_backlog_title_enforcement.py`
  - **Carried from Chunk 01's review — these land in THIS chunk's commit:**
    - **R-1** the four surfaces that still call the linter advisory. `plugin/lib/backlog/issuefmt.py`'s
      module docstring ("WARN-only by construction … no caller blocks on them") is now flatly false
      and is what a maintainer reads before touching `TITLE_MAX` — route the class through one
      owner rather than fixing the instance the review named. The other three
      (`data-model.md`, `project-preferences.md`, `backlog-service-issue-standard.md`) are already
      this chunk's registry debt above.
    - **R-2** `cli._print_human_ok` omits `failed`, so the summary triple silently stops summing to
      `total_source` — and the strictly *less* severe `status_unreconciled` gets its own stdout line
      for exactly this reason. Needs a human-path test: a `--json`-only test never exercises the
      formatter.
    - **R-3** `restructure-preview` does not run the pre-flight. That preview is the owner's
      aggregate pre-approval artifact for an irreversible ~900-issue run, so today it can report
      clean and then have the import hard-refuse. It must call `preflight_titles` over the
      restructured records and surface offenders in the preview.
    - **R-4** `plugin/skills/backlog/migration-scrub.md` Step 4 documents the reconcile warning in
      detail and is silent on both new failure modes — including that the refusal's remedy lives one
      step earlier, in the scrub itself.
- **Tests:** each red-verified:
  - `file` with a conforming title → succeeds
  - `file` with each of the four failing shapes (`too-long`, `too-short`, `placeholder`,
    `non-atomic`) → refused, and the message names the rule **and** the offending title
  - `file` with a conforming title but a failing **body** lint → succeeds with a warning (the
    WARN-only boundary is the thing most at risk of over-enforcement, and it needs a pin)
  - `update title=<non-conforming>` → refused
  - `update title=<conforming>` → succeeds
  - `update status=shipped` on an issue whose **stored** title fails §1 → **succeeds**, and emits
    the named lint line. This is the owner ruling's pin and the one a future "tighten it up" change
    would break silently
  - `update status=shipped` with no title anywhere → succeeds, no title lint attempted
- **Acceptance criteria:** full suite green; the 20 non-conforming open prawduct issues remain
  updatable on every field except `title`, verified by exercise not inspection; no body or label
  lint blocks anything.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. **Commit first**, then `/prawduct:critic`, and resolve blocking findings
  3. Write `.prawduct/.handoff-notes.md` and reflect

### Chunk 03: The dedup sweep asks whether one fix would close all of these

- **Description:** §4c's co-ship condition. The dedup sweep pairs on title-keyword + body overlap —
  a *duplicate* test. Over-splitting is a fact *between* issues that no per-title lint can catch,
  and the two come apart exactly where it matters: `crash on emoji` and `crash on UTF-16` share a
  root cause and almost no keywords. Add the altitude question to the sweep, which §4c establishes
  is the only place it can live.
- **Type:** doc-only
- **Critic mode:** cumulative-final
- **Depends on:** Chunks 01 and 02 (this is their release condition, not their prerequisite — but it
  must not be dropped, or the branch breaches §4c)
- **Artifacts consumed:** `backlog-import-title-boundary-discovery.md` §4c
- **Deliverables:**
  - the shared-root-cause question added to `plugin/skills/backlog/SKILL.md` `### dedup` step 1,
    alongside (not replacing) the existing keyword/body-overlap grouping
  - the same question in `plugin/skills/backlog/migration-scrub.md`, where the scrub runs
    corpus-wide before an import
  - §1 of the issue standard names over-splitting as a first-class failure beside under-splitting,
    if it does not already
  - a prose pin in `tests/test_v5_methodology.py` (or the nearest existing prose-pin suite) so the
    question cannot be silently dropped from either surface
- **Tests:** the prose pin asserts both surfaces carry the question; red-verified by deleting the
  sentence and watching it fail.
- **Acceptance criteria:** full suite green; a reader of either surface meets the altitude question
  before proposing merges.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. **Commit first**, then `/prawduct:critic cumulative` — one pass over the whole branch, which is
     also the `/prawduct:pr create` gate
  3. Resolve blocking findings; write `.prawduct/.handoff-notes.md` and reflect

## What this plan deliberately does not build

- **Retro-conforming existing corpora.** The title norm's `Retroactivity: contain` and §4c both bar
  it, and §4c gives the reason: a scrub run before the shared-root-cause check exists entrenches an
  over-split backlog. Chunk 03 builds the precondition; the scrub itself is a later, owner-approved
  act.
- **`import --rollback` / the run manifest.** Recorded out-of-scope in §5 — it changes the import's
  data model and is a separate decision.
- **#613 (retitle-in-place on skip).** §5 item 5, filed separately. It repairs the 27 already-created
  discodon issues; nothing here depends on it and it depends on nothing here.
- **The three smaller observations** in the upstream report (progress counter disagreeing with item
  count, unexplained `1 collision(s)`, stale advisory count frozen at first-seen) — §5 out-of-scope.
