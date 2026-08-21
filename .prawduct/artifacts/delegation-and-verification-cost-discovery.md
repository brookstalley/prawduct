# Discovery — Delegation and Verification Cost

**Status:** requirements draft, not yet ratified · **Date:** 2026-08-21 · **Author:** builder, from a
sweep of six governed product repos and 56.5k assistant turns of transcript
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
| discodon | 6 named rungs, 13 enforced markers, cost tiers (`live_local`/`live_creds`/`live_cost`), population markers, a change-scope detector, a cross-run lease, remote dispatch |
| hallucinote | 2 opt-in markers (`audio`, `ableton`), one ~2 min suite, no tiers |
| samsung | a `browser` marker forced serial with `-n0`, three separate project roots |
| 3tears | `integration` (docker) / `live` (env-gated) markers, a workspace sweep excluding a sidecar |

Prawduct's entire vocabulary for this is `test_command:` — **one canonical maximal invocation**,
plus `test_commands:` for multi-environment repos. There is no way for a repo to tell the
framework "here is a cheaper run that proves less," so there is nothing for a delegation
instruction to *name* except the whole suite. Which is exactly what `building.md` names.

### 2.8 Prior art in this repo, reached second

`documentation/remote-test-execution-proposal.md` (branch `docs/remote-test-execution-proposal`,
v0.1 2026-08-03, unmerged) investigated *where* tests execute. This discovery investigated *how
much* verification a delegate should run. They are the same cost problem from two angles, and that
proposal independently reached three conclusions this one depends on:

1. **`project-state.yaml`'s `test_command` is the right config home**, and prawduct is the right
   distribution vehicle — "not because prawduct needs a test-runner feature, but because the
   distribution problem is already solved there and nowhere else" (7 of 9 repos sampled carry
   `.prawduct/`). Pillar A lands in the same place, reached independently.
2. **The reusable part is small.** Of discodon's remote lane, ~40 lines are generalizable dispatch
   and ~100 are repo-specific tree preparation that "cannot be shared with any other repo" and
   "was never shareable." That is the correct calibration for this feature too: prawduct should own
   the vocabulary and the arbitration, and own none of the repo's execution.
3. **Throughput comes from concurrency across runs, not width within one** — with numbers.

It also names two gaps this design inherits: **TST-Q7ZK** (prawduct's own `test-evidence record`
bypasses arbitration) and its open **Q4**, that per-machine configuration — how many slots this
box has, where the remote host is — *has no home anywhere*, being neither a repo fact nor a user
preference. §7 decision 5.

A third finding worth carrying: hallucinote, trenchant and worldground carry `.prawduct/` but have
**no test entrypoint at all**. For those repos "declare your ladder" is the easier prior problem
"declare a test command," which reinforces R3 — a no-ladder repo must remain first-class.

## 3. Diagnosis

**Prawduct governs what work is done and to what standard. It has no model of who does the work
or what the machine can afford.** The main agent is assumed to be the only worker; the machine is
assumed to be free and infinite; verification is assumed to have one setting, maximum.

From that single absence:

- nothing asks whether work should be split, so it isn't (symptom 1);
- there is no cheaper verification to name, so delegates are told to run the most expensive one
  (symptom 2);
- per-suite clamps are the only defence and they don't compose, so the box oversubscribes;
- and the failure mode of oversubscription is a green record, so nobody finds out.

**Ordering claim, and it is load-bearing:** fan-out *without* a cost model is strictly worse than
staying serial. Three delegates each running a whole suite is more machine load, more wall clock,
and more silent-drop risk than one agent running one suite. **The verification-cost model is a
prerequisite for the delegation model, not a companion to it.** Anything that increases fan-out
before the cost model lands makes the reported problem worse.

## 4. The shape of the answer

Four pillars. Each is independently useful; the order is a dependency order.

### Pillar A — Verification rungs: a claim vocabulary the repo maps to its own commands

Prawduct defines a small **closed vocabulary of claims**, ordered by blast radius. A repo maps the
ones it has to its own commands. That is what makes it language- and platform-agnostic: the *claim*
is universal, the *discharge* is local.

| rung | the claim | discharged by, e.g. |
|---|---|---|
| `focused` | "the thing I changed works" | `pytest tests/test_x.py`, `swift test --filter`, `go test ./pkg/x`, `vitest run src/x.test.ts` |
| `adjacent` | "I did not break my neighbours" | the package / module / app the change lives in |
| `whole` | "I did not break the product" | everything hermetic and offline |
| `live` | "it works against the real world" | external services, devices, browsers, paid APIs, hardware |

Design rules that fall out of the evidence, each with a reason:

- **Rungs are named, never numbered.** A number becomes local jargon ("Stage 3") that means
  something different in every repo and invites cross-repo comparison of incomparable things.
  Explicitly out of scope: importing discodon's stage numbering into the framework.
- **The ladder is a partial map, and one rung is a valid ladder.** A repo declaring only `whole`
  (hallucinote) is a first-class, zero-ceremony configuration. Delegation must still work there —
  it simply means delegates verify nothing and the integrator owns the whole claim.
- **A rung declaration carries cost, not just a command**: measured wall-clock, and its
  **contention class** — does it fork workers, and does it need exclusive access to a shared
  resource (a port, a database, a device, a display, the committed tree)? Contention class is what
  makes arbitration mechanical instead of advisory.
- **A rung is only trustworthy if it is exercised.** A declared command that nothing runs is a
  stale artifact by construction (Living Documentation). Declared-but-never-executed must be
  *visible*, not silently trusted.

**Home:** `project-state.yaml`, extending the existing `test_command:` block. These are facts about
this repo's commands and costs, and that is where those already live. No new file class
(`docs/norms.md` § Deliberate Non-Design).

### Pillar B — Machine-level arbitration, because per-suite clamps do not compose

- A **slot semaphore**, not a mutex. `documentation/remote-test-execution-proposal.md` (§2,
  measured 2026-08-03 on a 16c/32t host) settles the shape: `-n8` 130.7s · `-n16` 110.8s ·
  `-n24` 124.3s wall. **Past ~8 workers extra CPU buys nothing, and throughput comes from
  concurrency *across* runs rather than width *within* one.** That is the empirical case for the
  whole design — narrow each run, then widen the agent count — and it means the primitive is N
  slots, not one lock. discodon's `testlock.py` (binary, clone-wide) and the remote lane's
  `flock`-based 3-slot semaphore are the two existing implementations; the semaphore is the
  right generalisation and the lock is its N=1 case.
- A waiting run **announces who it is waiting for and re-announces**, so a queue is never
  mistakable for a hang. Documented opt-out. Known wart to inherit deliberately or fix: the
  remote lane's all-busy fallback queues on slot 1 specifically, so a run can wait behind a long
  holder while other slots free first — unfairness, not a bug, and *never exercised under real
  concurrency* (that proposal's open Q2).
- **Prawduct's own entry point must participate.** `prawduct-hook test-evidence record` shells a
  bare suite invocation, takes no lock, and is — per discodon's `TESTING.md`, tracked there as
  **TST-Q7ZK** — a *frequent* full-suite entry point that today bypasses every arbitration a repo
  has built. The framework is currently a contended-resource consumer that does not participate
  in its own consumers' arbitration.
- **Fan-out width and delegate rung trade off against each other**, and the trade must be
  expressible. Wide fan-out at `focused` is cheap. Fan-out of 3 at `whole` is the reported bug.
- **The framework's own harness already caps agent concurrency** (`min(16, CPUs-2)` in the
  Workflow tool). That caps *agents*; it does not cap what each agent forks. Prawduct must reason
  about the second number, which is the one that kills the box.

### Pillar C — Degradation must be visible, or the evidence record is a lie

Independently valuable, arguably shippable first, and the item with the worst
consequence-if-skipped:

- A verification record must be able to say **it was degraded**. At minimum: carry
  **collected vs. reported** counts, and treat a shortfall as a failed record rather than a pass.
- A run whose worker died must not be able to write a green fact into the evidence store.
- This closes a hole that already exists today, before any new delegation feature ships, and it
  gets worse in exact proportion to how much concurrency the framework encourages.

### Pillar D — Delegation as a plan-time decision with a generated brief

**The decision moves to planning time.** Chunk boundaries are drawn in `planning.md`, when the
partition is being reasoned about — not at build time, when the main agent is already deep in
context and delegation looks like extra work. Requirements:

- The build plan records, per chunk or per plan, whether the work is delegable, and **when it is
  not, why**. A silent omission becomes a visible decision — the pattern prawduct already uses for
  descoping a requirement. This is the direct fix for symptom 1: *nothing currently asks the
  question.*
- Delegable chunks declare their **file-ownership set**. Disjointness across concurrently
  dispatched chunks is then **mechanically checkable**, and an overlapping parallel dispatch can be
  refused rather than merged by hand afterwards.
- **The dispatch brief is generated, not hand-written.** Observed hand-written prompts ranged
  583 → 7,949 characters with no common structure; the rules that matter survived only as
  quoted owner directives. A generated brief carries a fixed contract: the work, the ownership
  boundary (own / must-not-touch), the **verification rung and its exact command plus an explicit
  ceiling — do not run above this rung**, the return contract, who integrates and what they will
  run, and a context floor that is *not* the 96 KB briefing.
- **What stays with the integrator is unchanged and should be restated where the brief is
  generated:** the combined run at the highest rung, Critic, reflection, state updates, merge
  conflicts.
- **Delegation cost must be proportionate to delegated work** (blocked on / shared with #652,
  role-scoping the briefing). Today it is not, and that is a rational reason to stay serial.

### Cross-cutting — declaring the regime must be cheap, and practice must be promotable

The owner asked for both, and the evidence says both are needed.

- **Detect, propose, ratify.** `/prawduct:doctor` should read what the repo already says about
  itself — pytest markers and `addopts`, `package.json` scripts, Makefile / justfile targets, CI
  workflow jobs — propose a rung mapping and its contention classes, and let the owner ratify.
  Every repo in the sweep already encodes its regime somewhere machine-readable; none of it
  reaches prawduct.
- **Promotion is a first-class verb.** A practice that works — "delegates run only their own
  module", a measured `--maxprocesses` value, a marker that names the expensive tier — must have a
  one-step path into `project-preferences.md` as a ratified norm. The observed failure is exact:
  the right rule was stated by the owner three times, in three sessions, and never became durable
  anywhere. Prawduct already has the ratification surface (`doctor` § Norm Ratification Flow) and
  the enforcement table (`project-preferences.md` § Enforcement); this needs a route into them,
  not a new mechanism.
- **Policy lives in preferences; facts live in state.** The ladder (commands, costs, contention)
  is a fact about the repo → `project-state.yaml`. How much to delegate, what rung a delegate may
  run, the fan-out ceiling, whether the lease is on → `project-preferences.md`, which is where
  the owner already tunes behaviour and where "adjust subagent usage" belongs.

## 5. Requirements

Numbered for reference; not yet prioritised into a build plan.

**Verification rungs**
- **R1** A repo can declare a ladder of named rungs, each mapping a claim to one command.
- **R2** A rung declaration carries measured cost and a contention class (forks workers? needs an
  exclusive resource? which one?).
- **R3** The ladder is a partial map. A one-rung ladder, and no ladder at all, are both valid and
  must not degrade delegation into today's behaviour.
- **R4** Rung names are fixed by the framework and are never numbers.
- **R5** A declared rung that is never executed is visible as unexercised, not silently trusted.

**Arbitration**
- **R6** The framework ships a lease that serialises contended verification across concurrent
  agents, with an announced wait and a documented opt-out.
- **R7** Fan-out width and per-delegate rung are jointly bounded by declared policy, not by
  judgment under load.
- **R8** Bounds are stated in terms of the *machine*, and account for what a run forks — not only
  how many agents are running.

**Honest verification**
- **R9** A verification record carries collected-vs-reported counts.
- **R10** A run that lost a worker cannot record a passing fact.
- **R11** Degradation is reported to the operator at the point it happens, not discovered later.

**Delegation**
- **R12** The build cycle asks the delegation question at a fixed point (planning), and the answer
  — including "no, and why" — is recorded in the plan.
- **R13** A delegable chunk declares its file-ownership set.
- **R14** Overlapping ownership across a concurrent dispatch is refused, not reconciled afterwards.
- **R15** Dispatch briefs are generated from a fixed contract, including an explicit verification
  ceiling.
- **R16** The context cost of briefing a delegate is proportionate to the work delegated.
- **R17** Governance duties (Critic, reflection, state, merges, the top-rung run) stay with the
  integrator, and the generated brief says so to the delegate.

**Configuration and promotion**
- **R18** `/prawduct:doctor` detects a candidate ladder from what the repo already encodes and
  proposes it for ratification.
- **R19** Delegation policy is tunable in `project-preferences.md`, including "off".
- **R20** A working practice can be promoted to a ratified preference in one step.
- **R21** No new artifact file class: ladder → `project-state.yaml`, policy →
  `project-preferences.md`.

**Immediate, independent of all of the above**
- **R22** `building.md`'s "run the full suite before and after" is removed. It is the proximate
  cause of the reported overload and it is wrong at any fan-out ≥ 2. The replacement, pending the
  ladder, is: the delegate runs the narrowest verification that covers its own change; the
  integrator owns the combined run.

## 6. Explicitly out of scope

- **A scheduler, a CI system, or a test runner.** Prawduct names claims and arbitrates cost; the
  repo's own tooling runs the tests.
- **Remote / offloaded execution.** Discodon's `DD_TEST_REMOTE` is a good repo-specific
  optimisation. Prawduct should make it *expressible* as a rung's command, and own none of it.
- **Test selection intelligence** (testmon, coverage-based selection, change-scope detectors).
  A repo may put one behind a rung; the framework does not implement one.
- **Stage numbering, in any form.**
- **Mandating delegation.** The owner's framing is "helps consumers efficiently use subagents *if
  they want to*". `off` must remain a supported, ceremony-free setting (R19).

## 7. Decisions

Owner rulings taken 2026-08-21, recorded with the alternatives so they are not relitigated.

1. **Sequencing — RULED: full design, one build plan.** All four pillars planned together rather
   than sequenced as hotfix → A → D → B (the builder's recommendation) or as a correctness-first
   C+B release. Consequence the plan must respect: the dependency order still holds *inside* the
   plan even though the release boundary does not. Chunks must land A before D and before B, and
   the plan must not raise fan-out anywhere before the cost model exists (§3, ordering claim).
   Risk accepted: a large surface in a framework whose backlog already carries a deletion-only
   simplification pass (GOV-6D4Q).
2. **Arbitration scope — RULED: clone-wide, keyed so machine-wide is a later widening rather than
   a rewrite.** Key on git-common-dir, the evidence store's existing precedent. Machine-wide was
   rejected for now (couples unrelated products; a stuck holder in one repo blocks every other);
   advisory-prose-only was rejected outright — a hand-typed rule was measured to survive about
   three sessions (§2.3). **Note the tension this leaves open**: the operator runs six repos on one
   box concurrently, so clone-wide arbitration does not actually bound this machine. It bounds one
   clone's worktrees, which is the observed fan-out case, and defers the rest.
3. **R22 — RULED: new branch, land now.** Not folded into the feature's first chunk (the wrong
   instruction would keep shipping until the plan lands) and not queued behind Chunk 03 of
   `fix/coverage-honesty`.
4. **Cost-bearing rungs — OPEN.** Whether `live` gains an attribute for cost-bearing / credentialed
   / nondeterministic, or splits into rungs. discodon separates all three and its stated reason is
   good: "a third party declining is not a signal about your diff," which is a *selection* rule, not
   a cost rule. Builder recommendation stands: one rung with attributes.
5. **Per-machine configuration — OPEN, and inherited.** Slot count, core budget, remote host: not a
   repo fact (so not `project-state.yaml`), not a code-style preference (so not
   `project-preferences.md`), and prawduct has a standing no-new-file-class constraint. The remote
   proposal hit this same wall as its Q4 and left it unanswered. Pillar B cannot ship without an
   answer, and "an ad-hoc environment variable in no rc file and no `.env`" is the status quo it
   must beat.

## 8. Assumptions

- `[ASSUMPTION: the transcript sweep is representative of consumer behaviour generally, not just
  of this account | MED impact | user can correct]` — six repos, one operator. The mechanisms
  identified are structural rather than habitual, which limits the exposure, but the *rates*
  (0.34%) are one operator's.
- `[ASSUMPTION: harness capabilities are as documented in-session — worktree isolation, background
  agents, a Workflow concurrency cap of min(16, CPUs-2) | HIGH impact | verify before designing
  against any of them]` — this is a fast-moving surface and the design must not encode a
  capability that has moved.
- `[ASSUMPTION: consumers want opt-in delegation, not automatic fan-out | HIGH impact | user can
  correct]` — taken from the owner's framing, "if they want to". If automatic fan-out were
  wanted, R12 becomes a gate and Pillar B becomes mandatory rather than optional.
- `[ASSUMPTION: the ladder belongs in project-state.yaml beside `test_command:` rather than in a
  new artifact | MED impact | user can override]` — chosen to respect the no-new-file-class
  constraint in `docs/norms.md`.
