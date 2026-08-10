# Change Evidence — Design

<!-- artifact: design -->

**Status:** target design, not current reality. Nothing described below is built. The
one shipped piece — `bin/test-reference-verify` feeding `verify-coverage` — is named by
`architecture.md`'s Direction as a **confirmed violating site** of the
Python-specificity norm, "the most serious instance found." This artifact states where
that migration lands, not what exists today.

**Governed by:** `architecture.md` (Direction: *prawduct is written in Python and must
never be specific to Python*; *prawduct guides and reviews, it never implements*;
*local-first / no third-party runtime dependencies*; *every fact has one home*) ·
`nonfunctional-requirements.md` (Direction: *review wall-clock is P0*; *a new control
names the yield it expects and emits that yield observably*).

**Parent requirement:** LNG-5W8R (Python-specificity migration) names
`test-reference-verify` and `verify-coverage` explicitly. This artifact is that site's
design, not a new capability.

---

## The defect this corrects

One word — *coverage* — has been carrying four unrelated questions. They have different
instruments, different costs, and different portability. Conflating them is why the
framework's only shipped answer is a Python symbol-grep that proves nothing about
execution and goes silently dark on every other language.

| # | Question | What answers it | Test-runtime cost | Portability |
|---|---|---|---|---|
| 1 | Is this change exercised at all? | diff coverage over a native report | ~5% (line) | near-universal |
| 2 | What else does this change put at risk? | reference / call index | **zero** (static) | 10+ languages |
| 3 | Would a test have *failed* if behaviour changed? | diff-scoped mutation | high | per-language |
| 4 | Did I break a published contract? | API-diff | near zero | per-ecosystem |

The framework currently gestures at #1 and answers none of the others. A change that
breaks an output format fifty callers depend on is questions 2 and 4 — the two with the
*cheapest* instruments and no implementation at all.

**What the sockets are actually worth, from the one measurement we have.** The owner's
observation (2026-08-07) is that **a typical build cycle runs 2–3× as many reviews as
strictly required** — re-reviews that exist because a finding surfaced late, or because a
reviewer could not tell from the change alone whether something was covered. That number
is what sets the sockets' expected value, and it sets it higher than a
review-quality argument would. The saving is not "reviews get better"; it is *review
rounds that never happen*, and a round is the expensive unit under the review-wall-clock
P0 norm — reviewers run on opus. A socket that answers question 2 statically, for free, at
dispatch time, displaces a round in which a reviewer reads call sites to answer the same
question by hand. Two of the four questions cost near-zero at test time, so the ratio to
beat is not close. Recorded here because it is an owner observation with no other source
and no instrument in the repo reproduces it: nothing today counts reviews-per-cycle
against reviews-required, which is itself the *yield* measurement the NFR Direction
demands of any control added after 2026-07-29 — so a socket rollout that wants to prove
this claim has to start counting before it lands, not after.

## The socket contract

For each question prawduct declares a **socket**: a producer the product names, an
artifact shape prawduct consumes, and a verdict prawduct composes into a gate. Prawduct
computes none of it.

    product declares producer → producer emits artifact → prawduct consumes verdict

This is `architecture.md`'s *never re-implements* norm applied to change evidence, and
its *no third-party runtime dependencies* norm is what forces the shape: prawduct cannot
depend on a coverage parser, so the product runs the tool and prawduct reads the result.
The two constraints agree, which is the tell that this is the intended design rather
than a convenient one.

**Three consequences, each load-bearing:**

- **Prawduct writes no parser.** Diff coverage over Cobertura/Clover/JaCoCo/LCOV is
  solved and commoditized (`diff-cover`, `diff-test-coverage`). Consuming a normalizer's
  verdict is correct; re-deriving it is the norm's named error.
- **A missing producer reports *unchecked*, never *passed*.** Required by the
  Python-specificity norm's fail-open clause — a language with no producer must be
  visibly unanswered, because a silent no-op and a clean pass are indistinguishable at
  the output, and that invisibility is precisely what let the Python-only floor survive.
- **Products may author a producer.** Where no tool exists (embedded, proprietary,
  exotic stacks), the socket is a published contract a product can satisfy itself. The
  research says this is the rare road, not the common one — producers already exist for
  questions 1, 2 and 4 across most ecosystems — so it is the escape hatch that keeps the
  contract honest, not the expected path.

## Default posture

**Static producers are preferred over dynamic ones.** Questions 2 and 4 cost nothing at
test time because they read an index or a built surface; questions 1 and 3 tax every
run. Under the review-wall-clock norm the ordering is not a preference, it follows from
the constraint.

**Every socket defaults to report-only.** A product opts into a blocking threshold. This
matches today's `coverage_required: false` posture and is required by the
proportionality norm: adoption must never become a surprise red gate.

**Each socket names its expected yield and emits it observably** — the NFR Direction
requires this of any control added after 2026-07-29, and all four are. A socket whose
findings are printed and forgotten can never be retired on evidence, only defended on
principle, which is the ratchet the norm exists to stop.

## Per-socket design

### Socket 1 — Exercised? (diff coverage)

- **Producer:** the product's own coverage tooling emitting LCOV / Cobertura / Clover /
  JaCoCo, normalized to a diff verdict by an existing diff-coverage tool.
- **Minimal primitive (required, not an afterthought):** the socket's contract is a set
  of *uncovered changed lines* — `file:line`. The four formats above are conveniences
  layered on top, never the contract itself. This repo already paid for this lesson once:
  `test-evidence record` was JUnit-XML-coupled until a hardware-in-the-loop rig had no
  way in, and `--from-counts` was the fix, because the minimum viable result was counts
  and forcing them through XML *was* the coupling. Design question to answer before
  building, not after: **which real toolchains cannot produce any of the four formats?**
  Agnostic-for-lcov is not agnostic.
- **Verdict:** changed lines not executed by any test.
- **Consumer:** the Critic's Goal 1, and the gate when a product opts into blocking. A
  channel produced and never consumed is a defect — every socket below names its
  consumer for the same reason.
- **Posture:** line-level. **Branch coverage is optional enrichment, never required** —
  it is the *most expensive* option available, not a modest upgrade: `sys.monitoring`
  gives line coverage under ~5% overhead but branch coverage under the same core can run
  2× slower than the default. Requiring it would spend the wall-clock budget on the
  least portable signal.
- **Does not prove:** that any assertion constrained the executed line. See *Blind spots*.

### Socket 2 — Blast radius (reference index)

- **Producer:** a SCIP index (indexers exist for Java/Scala/Kotlin, TS/JS, Rust, C/C++,
  Ruby, Python, .NET, Dart, PHP; converts to LSIF for older consumers), queried for
  references to changed symbols. Floor fallback: symbol grep across the repo — the
  mechanism `test-reference-verify` already implements, pointed at all callers instead
  of the tests tree.
- **Verdict:** for each changed symbol, the set of dependents, and which of them the
  diff also touches.
- **Posture:** report-only, always. This is orientation for a reviewer, not a pass/fail
  claim — a large dependent set is information, not a defect.
- **Consumer:** the Critic's review payload. If no reviewer reads it, it must not be
  produced.
- **Why it earns its place:** zero test-runtime cost, and it is the only socket that
  speaks to "what else did I just put at risk," which is the question the shipped floor
  cannot form.

### Socket 3 — Would a test have failed? (diff-scoped mutation)

- **Producer:** the product's mutation tool scoped to the diff (PIT incremental,
  Stryker `--since`, mutmut `--incremental`/`--since`).
- **Verdict:** surviving mutants in changed code.
- **Posture:** opt-in, off by default, and the only socket expected to stay rare.
  Diff-scoping and result reuse have moved this from an overnight batch job to something
  runnable in the loop, which is why it is a socket at all rather than a footnote.
- **Consumer:** the Critic's test-adequacy goal — the one place a surviving mutant
  changes a verdict about whether the tests are worth anything.
- **Note:** this is the only socket that answers question 3. Nothing cheaper does.

### Socket 4 — Contract broken? (API diff)

- **Producer:** per-ecosystem — `cargo-public-api`/`cargo-semver-checks`,
  `japicmp`/Revapi/Roseau, `gocompat`/`gorelease`, AexPy, `api-extractor`. For products
  whose published surface is an HTTP API, `oasdiff` is *format*-scoped rather than
  language-scoped and applies across every backend language.
- **Verdict:** breaking changes to the published surface.
- **Posture:** report-only by default; a product with real consumers will want it
  blocking, and that is its call.
- **Consumer:** the PR-review gate, where a breaking surface change is a release
  decision rather than a chunk-local one.
- **Why it matters most for the motivating case:** a one-line change that breaks an
  output format fifty callers depend on is detected here, at build time, with no tests
  involved — while socket 1 reports green.

## Blind spots — state these wherever the guarantee is stated

**Covered ≠ verified (Case B).** Socket 1 proves a changed line *executed*; it does not
prove any assertion constrained its behaviour. A change can be fully diff-covered and
still have no test that would fail if its contract broke. The literature calls the gap
*checked coverage*. Socket 3 is the only instrument here that closes it, and socket 4
sidesteps it for published surfaces. **Socket 1 must never be described as if it closes
Case B** — a green coverage verdict buys reviewer trust, so an over-claimed one is worse
than no verdict at all.

**Per-test attribution is not free.** Knowing *which* tests covered a line is useful
navigation and answers nothing about assertions. It is also mutually exclusive with the
fast coverage core in Python — `sys.monitoring` does not support dynamic contexts — so
it costs the ~5% path outright. Optional, reporting-only, default off.

**A reference index is not a call graph of intent.** Socket 2 finds textual or symbolic
dependents; it cannot rank which of them care about the property you changed.

## What prawduct builds

A declaration schema, an evidence record shape, a gate that composes verdicts, and
honest documentation of what each signal does and does not prove.

**What prawduct never builds:** a coverage engine, a report parser, a language matrix, a
per-language symbol table, or a second copy of any tool the ecosystem already owns.

## Adoption

**Retroactivity: contain — and by construction, not by policy.** Every socket is
diff-scoped: coverage over changed lines, references to changed symbols, mutants in
changed code, API surface against the previous release. None can render a verdict on
code the author did not touch. A whole-repo coverage threshold would judge a legacy repo
for its entire history the moment it was enabled; nothing here can. This is the property
that makes the three adoption paths below safe, and it should not be traded away later
for a whole-repo percentage without re-deciding the retroactivity question explicitly.

### Existing products upgrading the plugin

**One advisory, earned by yield.** Owner decision, 2026-08-07: this warrants a nag, not
a doctor check. `/prawduct:doctor` is a fallback people rarely run, and a capability this
significant should not wait to be discovered. Four constraints keep that from becoming
the ratchet the proportionality norm exists to stop:

- **Yield-gated, not granted at birth.** The advisory ships only after the sockets prove
  significantly beneficial in this repo and its siblings. That condition *is* the
  proportionality norm's requirement that a control name the yield it expects — here the
  yield is measured before the nag exists, not promised alongside it.
  `[DECISION: surface adoption as a session advisory rather than a doctor check | doctor
  is rarely run and the capability is major enough to warrant a nag; the yield condition
  the owner attached is what keeps it inside the proportionality norm | user can
  veto/override]`
- **One advisory, not four.** Four sockets nagging separately on upgrade day is the
  accumulation pattern, regardless of each one's individual merit.
- **Detection-backed and actionable.** It names what the repo already has — "this repo
  publishes lcov in CI; declare it as socket 1's producer" — rather than describing a
  capability in the abstract. An advisory that cannot name the next action is noise.
- **Dismissible through the existing path.** `/prawduct:advisory` already carries
  dismiss/undismiss/resolve, so the off-switch exists and needs no new machinery.

Independently of the advisory, the *unchecked* state is also recorded where a reviewer
meets it in context — the evidence record the Critic reads when reviewing an actual
change. That is what preserves the Python-specificity norm's fail-open clause; the
advisory prompts adoption, the record keeps the unanswered question visible meanwhile.

Two compatibility obligations:

- **New evidence fields are optional, and the two directions differ.** A field *absent*
  because the record predates it fails open — an old record must stay readable. A record
  written by a *newer* schema than the reader is a loud block, never a silent drop, per
  `api-contract.md`'s forward-incompatibility norm and `data-model.md`'s. Adding a
  required field would break every product's evidence file on upgrade; conflating the
  two directions would let a newer record be silently misread as an incomplete one.
- **`test-reference-verify` is demoted, not deleted.** It becomes socket 1's fallback
  producer when no better one is declared — which is what lets the Python-specificity
  norm be satisfied without breaking the Python products currently relying on it. The
  existing `coverage_level: referenced` vs `executed` distinction already carries the
  honesty about which one answered.

### New products

The cheapest case, and the highest-value one: the producers get declared while the
toolchain is being chosen, before there is any code to retrofit.

`architecture.md`'s *never implements* norm already names the upstream gap — discovery
captures testing and tooling preferences generally but never asks, per ecosystem
present, which checker is standard. The sockets fold into that same question rather than
adding a new one: naming the linter and naming the coverage producer are one
conversation, at one moment, about one toolchain.

**Socket 4 hangs off an existing structural characteristic.** A product with no
consumers has no published surface to break, so API-diff is premature until
`exposes_programmatic_interface` is set — the same flag that already triggers the API
contract artifact. Reuse the trigger; do not invent a second one.

Posture stays report-only at birth. A new product opts into blocking when it has
consumers to protect, which is a decision it is not yet equipped to make on day one.

### Existing products onboarding

**This is part of formalizing the product's testing methodology — first-class, not a
side channel.** Owner decision, 2026-08-07. Onboarding an existing repo already runs
discovery in **reconciliation mode**, reading what is there and backfilling
`project-state.yaml`, and `coverage-scaffold` already enforces that every expected
strategy artifact exists. Change evidence rides that existing chain rather than adding a
parallel one: the producer declarations belong to the product's testing artifact, filled
during the same reconciliation pass that backfills requirements, architecture and
security.
`[DECISION: change-evidence producers are captured during onboarding's testing
formalization, not offered afterward | the inventory-and-backfill chain already exists
for security, testing and vision docs, and a capability introduced outside it is a
capability that gets skipped | user can veto/override]`

**Detect first, then prompt.** An existing repo has already made these choices — a
coverage config, a CI job publishing lcov, a jest or JaCoCo setup. Onboarding's job is
to find them and propose the wiring, with the user confirming rather than choosing from
scratch (Principle 20: infer, confirm, proceed). Prompting is expected here; it is the
moment the product's testing story is being written down, and the producer question
belongs in that conversation rather than after it.

**Record what is unavailable as a first-class stub.** A repo in a language with no
producer for a socket is recorded *unchecked* from day one — a one-line recorded
resolution, never a suppression flag. This is the same rule `coverage-scaffold` already
applies to strategy artifacts, where a `(not relevant — <reason>)` stub **is** coverage:
prawduct is opinionated that absence be a recorded decision, not that documentation be
voluminous. A legacy repo that looks clean because nothing was ever asked is the failure
mode the fail-open clause names.

The retroactivity property above is what makes this safe: onboarding a repo with poor
historical coverage produces no findings about its history. The first verdict any socket
renders concerns the first change made after onboarding — which is also the first change
the product had any opportunity to do differently.

## Open questions

- Whether the four sockets share one declaration surface in `project-state.yaml` or four.
- Whether socket 2's grep floor has a tolerable false-positive rate on common symbol
  names, or whether "no producer → unchecked" is the better default than a noisy floor.
- The retirement path for `test-reference-verify` once socket 1 exists: it is the
  Python-specificity norm's named violating site, and leaving it in place alongside a
  working socket would be two homes for one fact.
- **Where these facts live.** `data-model.md` records that extending the append-only
  evidence store to subsume `test-run` / `pr-review` evidence is *design direction, not
  a ratified norm* — reserved kinds exist but nothing has been decided. Four new
  evidence channels land squarely on that undecided question. Settle it before the first
  socket persists anything: a persisted schema's requirements are its consumers' future
  queries, and reversal cost, not line count, is what makes it lock-in.
- Which real toolchains cannot emit any of socket 1's four formats — the question that
  determines whether the minimal `file:line` primitive is the contract or a fallback.
