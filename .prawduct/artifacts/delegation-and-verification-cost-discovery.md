# Discovery — Delegation and Verification Cost

**Status:** requirements draft · **Date:** 2026-08-21, revised the same day against owner rulings 6-11
(§7) — 6-8 collapsed the design from four mechanism-bearing pillars to guidance, and 11 gave it back the
one rule guidance cannot supply: a default on whether to delegate at all. **Author:** builder,
from a sweep of six governed product repos and 56.5k assistant turns of transcript
**Governs:** a new prawduct capability. No build plan yet; open decisions at the end.

---

## 1. The two reported symptoms

The owner reports, from consumer repos:

1. Subagents are **not used often enough**.
2. When used, they **run very expensive tests**, overload the machine, and crash their own and
   sibling agents' test workers.

Both are true. Both are measured below. They are **not two problems** — they are one absence
seen from two sides.

## 2. What the evidence says

### 2.1 Delegation is vanishingly rare, and mostly not a choice

Swept every Claude Code transcript for this account: 29 project directories, ~56,500 assistant
turns, **31,220 tool calls**, of which **106 are subagent dispatches — 0.34%**.

Of those 106, **52 are the `/prawduct:pr` release-readiness reviewer** and a further handful are
Critic reviewers. *Prawduct's own structural mandates produce more than half of all delegation in
this entire account.* Where the framework requires a subagent, one appears; where it merely
permits one, one almost never does.

Fan-out has happened **11 times ever**, maximum width **4**.

### 2.2 The work that should have been delegated is easy to find

115 transcript segments contain **≥40 tool calls between two user messages** — long autonomous
runs. Their agent-dispatch count is essentially zero. The largest:

| tool calls | files touched | agents | repo | what it was |
|---|---|---|---|---|
| 571 | 26 | 0 | wt-discodon-kairo | a `/prawduct:methodology building` build cycle |
| 314 | 45 | 0 | samsung-frame-art-loader | a build cycle |
| 305 | 27 | 0 | wt-discodon-evalviz | a build cycle |
| 298 | 28 | 0 | samsung-frame-art-loader | a build cycle |
| 261 | 14 | 0 | wt-discodon-backlog | a build cycle |

**The single largest concentration of un-delegated, independently-partitionable work in every
governed repo is the prawduct build cycle itself.** That is the finding. Build plans already
decompose work into chunks that are *defined* as independently verifiable slices with declared
deliverables — the partition is already drawn, on disk, before the first line of code — and the
main agent then executes all of it serially in one context.

Within those 115 segments: **894 test-suite invocations**, 362 of them unscoped whole-suite runs.
Verification, not editing, is the wall-clock.

### 2.3 The expensive-tests behaviour is prawduct's instruction, verbatim

`plugin/methodology/building.md` § Delegating Work to Subagents:

> **How:** give the subagent the chunk spec and referenced artifacts, the project directory path,
> the instruction "Read the build cycle via `/prawduct:methodology building`", **and to run the
> full suite before and after.**

That is the whole of what prawduct says about what a delegate should verify. At fan-out of 3 it
means three concurrent whole-suite runs in one working tree. It is the proximate cause of
symptom 2, and it is a framework defect, not a consumer error.

The corrective exists — but only as prose the *owner had to type by hand*, which then survived as
a quotation inside three separate dispatch prompts:

> "**Run ONLY your own test module** — do NOT run the full suite; the main agent owns the combined
> run and all end-to-end verification. **This is an explicit user directive.**"

Three hand-typed repetitions of the same rule, in three different sessions, none of which became
durable anywhere. That is the promotion gap, observed.

### 2.4 Oversubscription does not fail loudly — it fails green

The sharpest finding, measured in-repo by discodon and recorded in `pyproject.toml`:

> "At 9 (and at 6, and once at 4) workers died mid-run and their tests were silently dropped:
> three separate full-suite runs reported 9457 / 9027 / 8207 'passed' against 18770 collected,
> **all exiting 0**."

A crashed xdist worker is not re-queued and does not fail the run. The same shape exists on the
JS side: discodon capped `maxWorkers: 2` in `web/vitest.config.ts` after one unbounded pool drove
the run queue to ~25 on 10 cores and cost a release gate 57 tests to timeouts.

**This lands directly on prawduct's honesty machinery.** `.test-evidence.json` is written from
real junit and is the record the Stop gates and the Critic read. Under contention that record
can say *passed: 9457* about a suite that collects 18770, and nothing in the framework can tell.
Prawduct is currently encouraging concurrency while holding an evidence mechanism that concurrency
can silently falsify. Tests Are Contracts (Principle 1) is being violated by the framework's own
recommendation, invisibly.

### 2.5 Per-suite clamps do not compose

Every repo that hit this fixed it *inside the suite config* — discodon `--maxprocesses=5` and
`maxWorkers: 2`, samsung `-m browser -n0`. Those clamps are **per process**. Three delegates each
launching a correctly-clamped run produce 3× the workers on one machine. The clamp that protects
a box from one run is worthless against N runs, and nothing in any repo knows how many runs are in
flight — except discodon, which built `tools/testlock.py`, a cross-worktree advisory lease, by
hand, in 4,948 lines of `tools/test.sh`. That lease is the single most promotable artifact found
in the sweep.

### 2.6 Delegating is expensive, so agents rationally avoid it

`.prawduct/.subagent-briefing.md`, handed to shared-worktree delegates: **prawduct 96 KB ·
discodon 152 KB · samsung 81 KB · hallucinote 61 KB**. A delegate that costs tens of thousands of
tokens to brief is not worth spawning for a small chunk. Backlog #652 already names this. It is a
*cause* of symptom 1, not a side issue: the economics of delegation are currently bad, and the
model is responding to them correctly.

### 2.7 Every repo invented its own testing regime, and prawduct knows none of them

| repo | regime |
|---|---|
| discodon | 6 named stages (its own vocabulary, not prawduct's), 13 enforced markers, cost tiers (`live_local`/`live_creds`/`live_cost`), population markers, a change-scope detector, a cross-run lease, remote dispatch |
| hallucinote | 2 opt-in markers (`audio`, `ableton`), one ~2 min suite, no tiers |
| samsung | a `browser` marker forced serial with `-n0`, three separate project roots |
| 3tears | `integration` (docker) / `live` (env-gated) markers, a workspace sweep excluding a sidecar |

Prawduct's entire vocabulary for this is `test_command:` — **one canonical maximal invocation**,
plus `test_commands:` for multi-environment repos. There is nothing for a delegation instruction
to *name* except the whole suite — which is exactly what `building.md` named. The answer is not to make prawduct learn these
regimes (§6); it is to stop the framework from naming a command at all, and let the coordinator,
who can read the regime in front of it, choose.

### 2.8 Prior art in this repo, reached second

`documentation/remote-test-execution-proposal.md` (branch `docs/remote-test-execution-proposal`,
v0.1 2026-08-03, unmerged) investigated *where* tests execute. This discovery investigated *how
much* verification a delegate should run. They are the same cost problem from two angles, and that
proposal independently reached three conclusions this one depends on:

1. **`project-state.yaml`'s `test_command` is the right config home**, and prawduct is the right
   distribution vehicle — "not because prawduct needs a test-runner feature, but because the
   distribution problem is already solved there and nowhere else" (7 of 9 repos sampled carry
   `.prawduct/`). The delegation policy lands in the same neighbourhood, reached independently.
2. **The reusable part is small.** Of discodon's remote lane, ~40 lines are generalizable dispatch
   and ~100 are repo-specific tree preparation that "cannot be shared with any other repo" and
   "was never shareable." That is the correct calibration for this feature too, and the owner's
   ruling (§7.6) goes further: prawduct owns the goal and the guidance, and none of the mechanism.
3. **Throughput comes from concurrency across runs, not width within one** — with numbers.

It also names two gaps this design inherits: **TST-Q7ZK** (prawduct's own `test-evidence record`
bypasses arbitration) and its open **Q4**, that per-machine configuration — how many slots this
box has, where the remote host is — *has no home anywhere*, being neither a repo fact nor a user
preference. §7 decision 5.

A third finding worth carrying: hallucinote, trenchant and worldground carry `.prawduct/` but have
**no test entrypoint at all**. For those repos the prior problem is the easier one — "declare a test
command" — which is why the guidance must work for a project with no tiers at all.

## 3. Diagnosis

**Prawduct governs what work is done and to what standard. It has no model of who does the work.**
The main agent is assumed to be the only worker; verification is assumed to have one setting,
maximum.

From that single absence: nothing asks whether work should be split, so it isn't (symptom 1); there
is no cheaper verification to *name*, so delegates are told to run the most expensive one
(symptom 2); and the failure mode of that is a green record, so nobody finds out.

**The absence is a decision absence, not a mechanism absence.** This is the correction that
reshaped everything below. A first draft of this document proposed a framework-defined rung
vocabulary, declared contention classes, a slot semaphore, and a mechanical ownership-disjointness
check. All four are ruled out (§6) — and `docs/norms.md` § Deliberate Non-Design already forbade
them: *"Norms are prose read by capable models… Structure would trade away the judgment this
depends on,"* and *"No mechanical divergence gates. Every scenario defeats a checker built for the
previous one; all of them yield to the same questions asked by a capable reviewer with the right
context."* The coordinating agent holds what a framework cannot: this machine, this project, this
test regime, this moment's load. Prawduct's job stops at the goal, the considerations, the
anti-patterns, and the record.

**Ordering claim, and it survives the reshaping.** Fan-out *without* a cost bound is strictly worse
than staying serial: three delegates each running a whole suite is more machine load, more wall
clock and more silent-drop risk than one agent running one suite. Guidance that encourages fan-out
lands together with guidance that bounds each delegate's verification — never before it.

## 4. The shape of the answer

Prawduct states the **goal**, supplies the **considerations** and the **anti-patterns**, gives the
project a **place to record what it decided**, and **discloses delegation before it happens**. The
coordinator chooses mechanism.

### 4.1 The goal

A delegate verifies what proves its own change, and nothing beyond it. The coordinator owns
integration verification and all governance — the combined run, Critic, reflection, state, merges.
And the cost of briefing a delegate must be proportionate to the work delegated; today it is not
(§2.6), which is a rational reason to stay serial.

### 4.2 Considerations — questions, not rules

*What must this delegate prove, and what is the smallest thing that proves it? Who checks the seams
between delegates, and when? What is this machine already doing? What in this project's test regime
is expensive — in time, money, credentials, or dependence on something nobody here controls — and
does this delegate need any of it? Is briefing this delegate cheaper than doing the work inline?*

On that last kind of expense: a failure in a test that depends on an uncontrolled third party is not
a signal about the delegate's change at all. discodon paid to learn this — a 403 from a video host
failed a gate for a diff touching only that repo's visualization code, and the identical tree passed
seven minutes later. Prawduct names the consideration; the project decides what it means for its own
suite.

### 4.3 Anti-patterns, each with a tell

The tell is what makes a rule fire at the moment of the error rather than read as true afterwards
(`learnings.md` preamble — *"delivery is not descent"*). Each of these is observed in §2.

- **The delegate that verifies the whole product** — tell: the brief names a command the
  *coordinator* would run at integration.
- **N baselines** — tell: the brief says "make sure tests pass before you start."
- **The unattributable green** — tell: you accepted a pass count without knowing what was collected,
  from a box running several agents.
- **Boundaryless fan-out** — tell: you cannot say which files each delegate owns without reopening
  their briefs.
- **The delegate that governs** — tell: a delegate ran the Critic, updated project state, or ticked
  a Status box.
- **The brief that costs more than the work** — tell: the context you assembled exceeds what the
  chunk changes.
- **Serial by default** — tell: a plan with independent chunks and no partition decision recorded
  either way.

### 4.4 The brief contract, stated qualitatively

What any delegate must be told: the work; the ownership boundary (what it owns, what it must not
touch); a **verification ceiling** — the narrowest run covering its own change, never the
coordinator's run; what to return; and who integrates. No template, no generator, no schema — the
list of what must be said, in the coordinator's own words.

### 4.5 Placement — the part that decides whether any of this works

**Guidance-only is what already failed.** `building.md` has said "when chunks are independent and
parallelizable" the whole time, and delegation ran at 0.34%. What reliably produced subagents was
`/prawduct:pr` *doing it* — 52 of 106 dispatches. The lesson is not that mechanism is required; it
is that **guidance must arrive where the coordinator is already stopping.** So the delegation
question is raised when chunk boundaries are drawn in planning, and at a chunk close — not as a
passage in a file someone might open. Placement, not machinery.

### 4.6 Disclosure and consent

Delegation should never be a surprise. Two obligations, deliberately asymmetric because informing is
cheap and asking costs a round-trip:

**Inform, always.** A plan that will delegate says so when it is presented: how many delegates, in
isolated worktrees or the shared one, what they will touch, and what they will *not* do. The
disclosure carries what **varies between plans** — one that could be copy-pasted from the last plan
is boilerplate, and boilerplate stops being read.

**Ask only on a named reason.** The condition is a closed list, because an agent resolving vagueness
asks defensively every time, which is the cost this is trying to avoid. Reasons to ask:

- **This project has never delegated before**, so the user has no precedent for what it looks like.
  This is the "sudden" in sudden use of subagents, and it is the strongest single trigger.
- The fan-out is materially wider than anything this project has done.
- Delegates will write in the **shared** worktree, so the user's own tree changes under them.
- Something irreversible or outward-facing sits inside a delegated chunk.

And the standing negatives: don't ask if the user already approved this plan's delegation, if
preferences record delegation as pre-approved, or if the user asked for the plan and its execution
without further interruption.

**Approval can be made durable.** On a yes, offer the preferences row — otherwise the same question
returns every plan, which is the unnecessary-asking failure wearing a seatbelt. That is the
promotion path (§4.7) arriving at the one moment the answer is fresh.

This is the same concern as `reflection.md`'s rule that a turn with dispatched agents is `RUNNING`
and never `COMPLETE` — don't leave the user unaware that agents are in play. Disclosure is that rule
moved one step earlier, to before they start.

### 4.7 Recording and promotion

- **Policy lives in `project-preferences.md`, in the project's own words** — how much to delegate,
  what a delegate may run, whether delegation is pre-approved, or `off`. Prose, indexed by the
  Enforcement table like every other norm. Not a schema.
- **Detect, propose, ratify.** `/prawduct:doctor` reads what the repo already says about itself —
  markers, scripts, Makefile targets, CI jobs — and proposes candidate practice for the owner to
  ratify. Every repo in the sweep already encodes its regime somewhere machine-readable; none of it
  reaches prawduct.
- **Promotion is a first-class verb.** The observed failure is exact: the right rule was stated by
  the owner three times, in three sessions, and never became durable anywhere (§2.3).

### 4.8 Home

`plugin/methodology/delegation.md`, routed as `/prawduct:methodology delegation` alongside the five
existing topics — same file class, read on demand, zero session-start cost. `building.md` cannot
hold it: it sits at 4717 against a ceiling of 4800, and this content is 400-600 tokens. The budget
comment's own remedy is *"place canonical detail in the file that owns the concept."* `building.md`
keeps a condensed pointer and the verification-ceiling rule; `planning.md` gets the
partition-and-disclose prompt at the point a plan is drawn and presented.

## 5. Requirements

**The goal**
- **R1** A delegate verifies what proves its own change and nothing beyond it; the coordinator owns
  integration verification and all governance.
- **R2** The cost of briefing a delegate is proportionate to the work delegated.

**What prawduct supplies**
- **R18** A stated default on *whether* to delegate, not only how: **prefer delegation when the
  same work finishes in less wall clock and the delegates will not fight each other**, with the
  cases that override it (the user asks; a chunk wants a clean context) and the cases that defeat
  it (dependency or shared files, briefing cost above the work's, a project policy that says
  otherwise). The guide routes to `project-preferences.md` for per-project policy.
  **Qualifier, and it is the builder's addition rather than the owner's words:** the wall-clock
  comparison is only valid *after* each delegate's verification bound is applied. Three delegates
  each running the coordinator's suite is more wall clock than one agent running it once (§2.4,
  §2.5), so the naive "this parallelizes, so it is faster" estimate is the same reasoning that
  produced the silent green.
  **And it has to work at PLAN time** — the partition decision is drawn with chunk boundaries
  (R6), before any brief exists. It does, because the bound is a property of the *chunk* rather
  than of the brief, and a chunk's deliverables are already declared: the plan-time form of the
  question is "what would prove this chunk on its own?" A chunk that cannot be answered is not
  scoped tightly enough to delegate, which is a more useful answer than the estimate. Chunk 02
  carries this, since it owns the plan-time prompt.
- **R3** Considerations, framed as questions rather than rules. **R18 is a deliberate exception:**
  a default posture is a rule, and it is the one thing the questions cannot supply — an agent with
  no default answers "should I delegate?" by not delegating, which is the observed 0.34%.
- **R4** Anti-patterns, each carrying a recognizable tell.
- **R5** The brief contract stated qualitatively — what must be said, not a template that says it.

**Placement**
- **R6** The delegation question arrives where the coordinator already stops: when chunk boundaries
  are drawn, and at a chunk close.
- **R7** A plan's partition decision is recorded either way, including "serial, because X."

**Disclosure and consent**
- **R8** A plan that will delegate says so when presented: how many, isolated or shared tree, what
  they touch, what they will not do.
- **R9** The disclosure carries what varies between plans, not boilerplate.
- **R10** Approval is asked only on an enumerated reason; absent one, disclose and proceed.
- **R11** Approval can be made durable in preferences rather than re-asked each plan.

**Recording and promotion**
- **R12** Delegation policy is tunable in `project-preferences.md` in the project's own words,
  including `off` and pre-approved.
- **R13** `/prawduct:doctor` proposes candidate practice from what the repo already encodes.
- **R14** A working practice can be promoted to a ratified preference in one step.
- **R15** No new artifact file class: guidance is a methodology guide, policy is preference prose.

**Honest verification** *(ruled in scope — §7.9)*
- **R16** A verification record can say it was degraded, rather than recording a green a contended
  run did not earn.
  **Design note, unresolved and it shapes the chunk:** junit carries a *reported* test count and no
  notion of *collected*, so "compare collected to reported" is not available from the report alone.
  Three shapes: compare against the last recorded count for the same suite and flag a drop
  (cheap, noisy on legitimate test-count changes); parse the runner's summary text (per-runner, and
  prawduct does not want per-runner knowledge — §6); or let the record simply *carry* a degraded
  flag the coordinator sets when it observes one. The third is the smallest and the most consistent
  with §7.6 — the framework's record gains the vocabulary, the coordinator supplies the
  observation — and it is the builder's recommendation.

**Landed**
- **R17** ✅ `building.md`'s "run the full suite before and after" replaced with a verification
  ceiling (`008bd5f0`), net-zero against the then-current budget.

## 6. Explicitly out of scope

Ruled out by the owner, 2026-08-21. Recorded so they are not reconsidered from scratch.

- **Any arbitration mechanism** — no lease, no semaphore, no slot accounting, no cross-run lock. The
  coordinator has environment context a framework does not.
- **A framework-defined tier vocabulary.** No `focused`/`adjacent`/`whole`/`live`, no declared
  commands, no contention classes, no attributes. Consumers' test systems are not knowable in
  advance; the guidance is qualitative and the project maps it.
- **Per-machine configuration.** A consequence of the mechanism, and it dies with it.
- **Mechanical checking of ownership disjointness.**
- **Remote or offloaded execution.** `documentation/remote-test-execution-proposal.md` covers it and
  reached the same conclusion in its own domain: *"the valuable, reusable part is small… copy-pasting
  40 lines across repos is not the problem people assume it is."*
- **Test selection intelligence** (testmon, coverage-based selection, change-scope detection).
- **Stage numbering, in any form.**
- **Mandating delegation.** `off` stays a supported, ceremony-free setting (R12).

## 7. Decisions

Owner rulings, 2026-08-21, with the alternatives so they are not relitigated.

1. **Sequencing — RULED: one build plan.** The dependency order still binds *inside* it: nothing may
   encourage fan-out before the guidance bounding a delegate's verification exists (§3).
2. **Arbitration scope — SUPERSEDED by 6.** (Was: clone-wide, keyed to widen later.)
3. **R17 — RULED: own branch, landed now.** ✅ `008bd5f0`.
4. **The `live` rung's shape — SUPERSEDED by 7.** (Was: one rung with attributes.)
5. **Per-machine configuration home — MOOT under 6.**
6. **RULED: prawduct states the goal, not the mechanism.** Guidance is considerations and
   anti-patterns; the coordinator, holding environment and product context, chooses how.
7. **RULED: testing guidance is qualitative.** No framework-defined tiers or taxonomy — consumers'
   regimes differ and prawduct cannot know them in advance.
8. **RULED: `building.md`'s ceiling may rise to 4800** to carry the verification-ceiling rule's
   *why*. Scoped to this feature; the standing prefer-trimming-over-bumping posture is unchanged.
9. **RULED: the record the framework owns is inside the line.** R16 stands. The boundary is
   ownership, not mechanism-vs-guidance: `.test-evidence.json` is prawduct's artifact, it can today
   record a green for a run that silently dropped half its tests (§2.4), and no guidance to a
   coordinator can fix a record the framework owns. Everything touching a *consumer's* test system
   stays guidance.
10. **RULED: `plugin/methodology/delegation.md` is the home**, as a sixth `/prawduct:methodology`
   topic (§4.8).
11. **RULED: the guide states a default on WHEN to delegate** (owner, 2026-08-21, at the plan's
   post-Chunk-01 checkpoint — the guide as first written "leaps right into the weeds"). Owner's
   framing: *"by default, prefer delegation to subagents when the same work can be done in shorter
   wall clock but without significant cost from conflicts, read project preferences for per-project
   guidance."* Explicitly **not to be belaboured** — models are capable, and the yield is the
   default existing, not its length. This is R18, and it amends R3's questions-not-rules framing at
   exactly one point rather than generally. The alternative — leaving the "when" to `building.md`'s
   existing line — is what the 0.34% measurement already falsified.

## 8. Assumptions

- `[ASSUMPTION: the transcript sweep is representative of consumer behaviour generally, not just of
  this account | MED impact | user can correct]` — six repos, one operator. The mechanisms are
  structural rather than habitual, which limits exposure; the *rates* (0.34%) are one operator's.
- `[ASSUMPTION: guidance placed where the coordinator already stops changes behaviour where guidance
  in a file has not | HIGH impact | falsifiable by the next few build cycles]` — the load-bearing bet
  of the whole design (§4.5), with §2.1 as evidence that the weaker form fails. Worth measuring
  rather than assuming: re-running the same transcript sweep after this ships answers it directly.
- `[ASSUMPTION: consumers want opt-in delegation, not automatic fan-out | HIGH impact | user can
  correct]` — from the owner's framing, "if they want to."
