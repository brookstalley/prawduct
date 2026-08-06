---
artifact: discovery
# scope intentionally empty: requirements for a future plan; no plan scope is
# owned here (same opt-out as kernel-redesign-discovery.md).
scope:
status: discovery complete 2026-08-05 — four owner decisions ruled same day; next: planning
created: 2026-08-05
depends_on: [build-plan-api-design.md]
---

# Upstream Dependency Policy — Discovery

Requirements for a **language-, platform-, and package-manager-agnostic policy for
accepting upstream code into a prawduct-governed product**. Motivated by the 2026
supply-chain campaigns; scoped as the intake half of a concern the framework
currently covers only on its justification half.

**The governing sentence, and the one every downstream decision answers to:**

> This policy is about **dependencies**, not about package managers. It governs any
> upstream artifact a product incorporates whose release someone else controls —
> independent of delivery mechanism. Enumerating ecosystems is a **mapping appendix**,
> never the definition. An ecosystem prawduct has never heard of is *covered by the
> policy* and enforced at whatever tier it can reach.

## 1. Problem (observable, evidenced)

A prawduct-governed product has no recorded terms on which it accepts third-party
code, and the framework never asks. Concretely, today:

- **Nothing asks.** `.prawduct/cross-cutting-concerns.md` row *Dependency management*
  records **no discovery leg**, and Known Gaps states the position explicitly:
  *"Dependency management has no discovery trigger. Dependencies are a planning
  concern. This is by design."* That position predates the current threat model and
  this document overturns it.
- **What coverage exists is about justification, not intake.** `building.md` §
  Decision Research makes a new dependency a *major decision* owed research and a
  rationale; Critic Goal 3 flags *unlisted* dependencies (BLOCKING) and Goal 1 flags
  *known-vulnerable* ones (WARNING). All three ask "should we depend on this at all" —
  none ask "on what terms does a new **version** of something we already trust get in."
- **`update` is ungoverned.** The janitor's *Dependency Health* theme asks whether
  dependencies are current — i.e. it applies pressure toward taking updates, with no
  counterweight naming when taking one is unsafe.
- **The agent is an unmodelled actor.** Prawduct's whole premise is an agent that
  writes code. An agent that runs `npm install`, `uv add`, or an update sweep is making
  intake decisions continuously, against no recorded policy.

**Why this is a separate concern from the existing row, not an extension of it.** Same
relationship as `API design (produced)` vs `Foreign API verification`: adjacent,
separately owned. *Dependency management* asks **should we depend on this** (planning,
one-time, per-package). This asks **on what terms does upstream code enter** (standing,
per-release, per-actor). A product can have a perfect dependency manifest and still take
a compromised patch release four minutes after publication.

## 2. What the research established (checked 2026-08-05, not recalled)

This is a fast-moving domain (Principle 24, `discovery.md` "Calibrate Rigor" — volatility
trigger). Everything below was verified against current sources today; citations in §10.

1. **Only update *bots* exempt security fixes from a cooldown. No package manager does.**
   Renovate and Dependabot both bypass cooldown for vulnerability-driven updates. Every
   package manager surveyed — npm, pnpm, yarn, bun, deno, uv, pip, poetry, PDM, pipenv,
   pixi, Bundler, Hex — has **no native security exemption**. A naive blanket cooldown at
   the package-manager layer therefore **delays patching known CVEs**, which is a net
   security regression. The security fast-path is a first-class clause, and expressing it
   is a tier-2 capability only (§5).
2. **The ecosystem converged on ~3 days.** Dependabot defaults to 3 (July 2026 onward);
   Renovate's `config:best-practices` has carried 3 for npm since 2025; pnpm v11 ships
   `minimumReleaseAge` **on by default**; Yarn defaults 1d since 4.15; Deno 24h since 2.9.
   StepSecurity recommends 10.
3. **Measured incident dwell times are hours, not days.** axios: malicious versions live
   ~3 hours (March 2026). TanStack Router/Start: detected within minutes, deprecated
   within ~1.5 hours (May 2026). The May 2026 campaign — TanStack, Mistral AI, UiPath,
   OpenSearch — spanned 170+ npm packages and 404 malicious versions across npm *and*
   PyPI simultaneously.
4. **The concept has at least eleven names across 15+ tools** — `cooldown`,
   `minimumReleaseAge`, `min-release-age`, `npmMinimalAgeGate`, `exclude-newer`,
   `stabilityDays`, `uploaded-prior-to`, `min-age`, `cooldown-days`,
   `minimumDependencyAge`, `autoUpdateDelay`. This is the strongest possible evidence
   that the useful artifact is an **abstraction with a mapping**, not a config recipe.
5. **Six major ecosystems have no native support at all** — Go, Maven/Gradle, NuGet,
   Composer, SwiftPM, pub. A design that assumes declarative enforcement leaves them
   uncovered, which is why tier 3 exists (§5).
6. **Cooldown alone does not address the observed payload vector.** The 2026 worms
   executed **obfuscated payloads at install time** and self-propagated. Waiting N days
   does not stop `install` from running arbitrary lifecycle scripts once the wait ends.

## 3. Success (what "done" looks like)

1. A product records its upstream intake terms, or records a deliberate "none" — the
   same *force-the-decision-don't-mandate-the-answer* stance the api-design work
   established.
2. The recorded policy is **expressed in the strongest mechanism the ecosystem allows**,
   and where that is weak, the product knows it (§5 — the tier is recorded, not assumed).
3. A product that has *not* recorded a policy is nudged ambiently, on-demand, and in
   deep sweep — the three-surface pattern (advisory / doctor / janitor).
4. Setting the policy triggers a conformance scan of every intake surface the repo
   actually has, which **reports what it could not classify** rather than reporting clean.
5. The agent's own dependency actions are governed by the same policy, through a
   procedure it reads rather than remembers.

## 4. The policy (stated without reference to any ecosystem)

Six clauses. Each is stated in terms of *dependencies*; §5 says how each is enforced and
§9's appendix says how each is spelled in a given toolchain.

**Clause 1 — Minimum release age.** An upstream release is not adopted until it has been
publicly available for the policy's minimum age. **Default: 7 days** for untrusted
upstream. Rationale for 7 over the ecosystem's 3: it is more than double the observed
dwell time of every 2026 incident, and it additionally covers the *stability* failure
mode (a release ships broken and is superseded within days) that none of the
security-motivated defaults target. Products may raise or lower it as a recorded decision
with a why.

**Clause 2 — Trust tiers.** Two tiers.
- **Trusted** — same repository, same owner, or explicitly declared trusted (e.g. a
  close partner). Trusted upstream is taken at latest, no minimum age.
- **Untrusted** — everything else. Clause 1 applies.

**Clause 3 — Security fast path.** A release that fixes a known vulnerability the product
is exposed to is **exempt from the minimum age** and adopted on its merits, immediately.
Without this clause the policy converts a security control into a security regression
(§2.1). Exercising the exemption is a recorded act, not a silent one.

**Clause 4 — Install-time execution.** Upstream code is not granted arbitrary execution
at install time by default. Where the toolchain can deny lifecycle/build scripts, it
denies them, and the packages that genuinely need them are an allowlist with reasons.
This is the clause that addresses the *observed* payload vector (§2.6); clause 1 alone
does not.

**Clause 5 — Resolution is pinned and frozen.** The resolved dependency set is committed
and authoritative. Installs in CI, and installs performed by an agent, do not re-resolve —
they install exactly what is pinned. Without this, clauses 1–4 govern the manifest while
something else silently decides what actually lands.

**Clause 6 — New-dependency intake.** Adding a dependency that is new to the product is
governed twice: the **version adopted** must satisfy clause 1 like any other release, and
the **package identity** must be verified to be the one intended. The second half is the
AI-specific vector and the reason this clause is not folded into clause 1: an agent can
hallucinate a plausible package name, and attackers pre-register hallucinated names
(typosquatting / "slopsquatting"). Verification means confirming the package's source
repository, publication history, and maintainer are the ones the decision was made about —
not that a name resolves.

## 5. Enforcement tiers — the load-bearing structure

The policy is one statement. What varies per ecosystem is **the strongest mechanism
available to enforce it.** This mirrors the shape `project-preferences.md` already uses
for norms (linter / test / Critic, ordered by strength, *"assign the mechanism when you
add the preference so it doesn't quietly become aspirational"*).

| Tier | Mechanism | Binds | Can express |
|---|---|---|---|
| **1 — Declarative** | The toolchain's own config | **Every actor**: owner, agent, CI, contractor, a script neither wrote | Clauses 1, 2, 4, 5 |
| **2 — Bot** | The update bot's config | Proposed updates | Clauses 1, 2, **3** (the only tier that can) |
| **3 — Agent-mediated** | A documented procedure: enumerate available updates, read publication timestamps, apply the policy per package, act | The agent, per invocation | **All six**, including judgment clauses 3 and 6 |

Three rules govern the tiers:

1. **Prefer the strongest tier the ecosystem allows.** A tier-1 expression binds actors
   who have never read the policy; a tier-3 expression binds one actor on a good day.
2. **Record the tier actually reached, per intake surface.** A policy that claims
   coverage it does not have is worse than an absent one. "Enforced at tier 3" is a valid
   and honest recorded state — "unenforceable" is not a state this design produces.
3. **Tier 3 is not merely a fallback for ecosystems without tier-1 support.** It is where
   judgment lives everywhere. *"This release is five days old, under our seven, but it is
   the fix for a CVE we are exposed to"* is clause 3, and no config key can make that
   call. Tier 1 sets a floor that cannot be forgotten; tier 3 handles the exceptions and
   everything the floor cannot see.

**Tier 3 must be a procedure, not a prompt.** Guidance that lives only in an agent's
instructions is the weakest form of the weakest tier. The deliverable is a
policy-derived, per-ecosystem **update procedure** written into the product — enumerate
outdated, obtain publication times, classify by tier and clause, act — which is exactly
the shape `templates/runbook.md` exists for, and which the matrix row *"Operational
procedures are authored, not improvised"* already governs.

## 6. Detection — and why the obvious approach is wrong

The first draft of this requirement proposed detecting applicability by scanning for a
closed list of manifest filenames (`package.json`, `pyproject.toml`, `go.mod`, …). **That
is an allowlist classifier, and this repo has already ratified the rule it breaks:**
cross-cutting-concerns row *Language-agnostic file classification* — *"Adopt
exclusion-by-default for any new classifier, and treat an allowlist as the departure that
needs a reason"* — plus learning #135, *"When you add an ingest/IO surface to a
platform-agnostic framework, expose the minimal data primitive — not one ecosystem's
file format — or you silently lock out the toolchains the agnosticism promised."*

The allowlist is wrong on two independent axes:

- **It under-enumerates package managers.** Missing from the draft list alone:
  `requirements*.txt`, `Pipfile`, `setup.py`, `environment.yml`, `mix.exs`, `build.sbt`,
  `deno.json`, `Podfile`, `Cartfile`, `vcpkg.json`, `conanfile.txt`, `renv.lock`,
  `Project.toml`, `cpanfile`, `*.cabal`, `stack.yaml`, `build.zig.zon`, `dub.json`.
  Any list written today is wrong by next year.
- **It mistakes "package manager" for "delivery mechanism," which is the deeper error.**
  Upstream code enters a repo through routes no package manifest names: container base
  images, CI actions/workflows pinned by mutable tag, git submodules, vendored
  directories, `curl | sh` installers, infrastructure providers and modules, chart
  repositories, editor/IDE extensions, agent plugins and MCP servers, and downloaded
  model weights. **CI actions are the sharpest case** — upstream code executing with the
  repository's credentials, referenced by a mutable tag, present in no manifest.

**The design that follows from this** splits one question into two, which is also what
makes the completeness problem tractable:

- **"Has this product recorded its intake terms?"** — asked of **every** product,
  universally, with no detection gate at all. Every product that consumes any upstream
  code needs an answer, and a product that genuinely consumes none records that in one
  line, exactly as `"none — internal-only"` is a valid recorded API versioning decision.
  Universality removes the allowlist from the trigger path entirely.
- **"Where does upstream code enter this repo, and is the policy expressed there?"** —
  the conformance scan. Recognized surfaces are a **fast path, deliberately open-ended**:
  an unrecognized candidate is reported as **unclassified**, never passed over. The scan's
  output is three-valued — *conformant* / *drifted* / *unclassified* — and a scan that
  finds unclassified surfaces does not report clean.

## 7. Where it threads (the pipeline legs)

Modelled on the api-design coverage pattern, which is the closest precedent in the repo.

| Leg | Surface |
|---|---|
| **Discovery** | A "Surface Upstream Dependency Policy" section in `discovery.md`, sibling to error handling / observability — asked of every product, scaled to risk, with prawduct's opinionated defaults offered and explained rather than interrogated (Principle 20). |
| **Artifact** | A decision record in `project-state.yaml` (`design_decisions.upstream_dependency_policy`) plus a top-level answer-store fact for the advisory; the policy's rationale, per-surface tier record, and trusted-party register as a `## Direction` norm entry in `security-model.md`. |
| **Builder** | A `planning.md` section declaring the policy's bearing on chunks that add or update dependencies; `building.md`'s existing Decision Research trigger extended from *"should we depend on this"* to *"on what terms."* |
| **Critic** | Goal 2 / Goal 3 **WARNING** — a chunk that adds or updates a dependency, or edits an updater config, against no recorded policy or against the recorded one. Never BLOCKING (matching api-design's force-the-decision stance). |
| **Retroactive** | An advisory probe (ambient, dismissible, resolved by the recorded fact) + a `/prawduct:doctor` health check (on-demand conformance) + a `janitor` theme (deep sweep, judgment) — the same three-surface split the api-design work used, allocated per `docs/doctor-vs-janitor.md`. |
| **Onboarding** | The policy interview runs at onboard and on advisory resolution; setting the policy triggers the §6 conformance scan. |
| **Agent** | The tier-3 update procedure (§5), generated into the product from the recorded policy. |

**Conformance drift posture: offer, apply on confirmation.** The scan reports drift and
presents the exact per-surface edit; the edit is made only on an explicit yes. These are the
product's build and CI configs — mutating them is an owner decision, consistent with
`coverage-scaffold`'s `--apply` gate and doctor's read-and-guide posture.

**Reconciled 2026-08-06 to the build plan's ROUTING NOTE, which resolved *who holds the file
handle*.** This sentence originally read "it writes only on an explicit yes", which named the
scan as the writer — the posture two ratified `architecture.md` norms forbid, since a product's
build and CI configs are in neither set the plugin may write. `prawduct-hook jurisdiction`
surfaced the conflict at plan-authoring and it was resolved by conforming rather than by
exception: **prawduct reports the drift and presents the exact edit; the agent in session makes
it, with the owner's confirmation.** The owner's ruling is untouched — it was always about *who
decides*, never about which process writes. Amended here rather than only in the plan, on this
document's own standing rule that the two must not disagree; the delivered surfaces already say
it correctly (doctor #15: "This check writes nothing — least of all the product's own build, CI,
or package configuration … prawduct reports; the agent applies").

**Amended 2026-08-06: the Critic row's conformance half is delivered *partially*, and the
missing part is named rather than dropped.** The row commits the Critic to WARN on a change made
"against no recorded policy **or against the recorded one**." What shipped in
`plugin/skills/critic/review-protocol.md` and `goals-1-3.md` at plan-authoring checked **presence
only** — the second disjunct went missing with no descope recorded anywhere, which is precisely
the requirement-dropped-by-a-pivot class this document's own §7 exists to prevent, and the
cumulative review caught the same class twice elsewhere (R-1, R-18) while missing it here.

`[DECISION: the Critic checks conformance against the recorded terms the tree can answer —
pinning, the trusted register, install-time execution, and the tier each surface records — and
does NOT check clause 1's minimum release age | release age is answerable only against the
package index, and the Critic reviews with no network and no execution (CRT-3X9D); a check it
cannot perform would be an aspirational rule, which §5 rule 2 calls worse than an absent one |
agent-proposed, owner ruled 2026-08-06]`

Release age is therefore held by the two surfaces that *can* reach the index: `/prawduct:doctor`
check #15(b)'s conformance scan and the tier-3 update procedure
(`templates/upstream-dependency-update-runbook.md`). The delivered bullets name that split
inline, so a reviewer meets the boundary at the moment it binds rather than inferring it — and
`tests/preferences/test_dependency_resolution_pinning.py` already draws the identical line for
the same reason ("Deliberately NOT asserted here: that the pinned versions satisfy clause 1's
minimum release age").

## 8. Scope

**In scope (v1):** all six clauses in the recorded policy; the three-tier enforcement
model with recorded per-surface tier; the universal "policy recorded?" trigger; the
open-ended conformance scan; discovery/artifact/builder/Critic/retroactive/onboard legs;
the tier-3 update procedure.

**Out of scope (named, not forgotten):**
- Prawduct implementing vulnerability scanning, SBOM generation, or provenance
  verification. Where an ecosystem offers provenance or attestation, the policy *points*
  at it; prawduct does not re-implement what an ecosystem's tooling owns (the 2026-07-29
  norm that is retiring the broad-except canary).
- Blocking gates. Every new check here is WARNING or advisory.
- A curated registry of trusted publishers. Trust is per-product and owner-declared.
- Maintaining an exhaustive ecosystem mapping table as a normative artifact — see §9.

## 9. The mapping appendix is non-normative, and that is load-bearing

A table of *"in npm write X, in uv write Y"* is useful and will go stale. It is therefore
recorded as an **appendix to the policy, explicitly non-normative**: it accelerates the
common cases and constrains nothing. Three consequences follow, and all three are
requirements:

1. **No policy statement, gate, or check may be phrased in terms of a named ecosystem.**
2. **An ecosystem absent from the table is fully covered by the policy** and is enforced
   at the best tier it can reach — in the worst case tier 3, which is always available.
3. **A stale table is a documentation defect, never a coverage gap.** The scan's
   *unclassified* verdict (§6) is what keeps an out-of-date table from reading as clean.

## 10. Owner decisions (ruled 2026-08-05)

- `[DECISION: default minimum release age is 7 days, one number, not tiered by ecosystem | double the ecosystem's 3-day convergence and >2x every measured 2026 dwell time, while also covering the stability failure mode; one number is auditable across 15+ toolchains where a per-ecosystem table is not | owner ruled]`
- `[DECISION: two trust tiers — same repo, same owner, OR explicitly declared partner, all taken at latest | owner ruled after the counter-argument below was raised and considered]`
  **Accepted risk, recorded once and not re-litigated:** the 2026 campaigns compromised
  *reputable, widely-used* upstreams (TanStack, Mistral AI, axios) through maintainer
  account compromise, so a declared-trusted third party whose publishing account is
  compromised has an unmediated path in. Same-repo and same-owner do not carry this risk
  (the product controls the publish and would know). The mitigation available without
  re-opening the decision: each declared trusted party is a **named norm exception with a
  why**, so the register is auditable and revisitable rather than invisible.
- `[DECISION: no revisit date on the policy | revisiting is always available and requires no scheduled prompt; a `revisit:` expiry would manufacture work rather than surface it | owner ruled]`
- `[DECISION: conformance drift is offered and applied only on confirmation | build and CI configs are owner-owned surfaces | owner ruled]`
- `[DECISION: new-dependency intake (clause 6) is in v1 scope, covering both the version's age and package-identity verification | the identity half is the AI-specific vector and prawduct is the framework whose agent creates it | owner ruled]`

## 11. Open assumptions (vetoable)

- `[ASSUMPTION: the policy is a decision record (design_decisions.upstream_dependency_policy) plus a top-level answer-store fact, with rationale and the trusted-party register as a security-model ## Direction norm entry — not a new strategy-class artifact template | MED impact | owner can promote it to its own artifact template if the per-surface tier record proves too big for a Direction entry]`
- `[ASSUMPTION: enforcement posture matches api-design end to end — advisory + doctor + janitor + Critic WARNING, never BLOCKING | MED impact | owner can request a blocking gate on updater-config drift]`
- `[ASSUMPTION: the tier-3 update procedure ships as a FILLABLE TEMPLATE consuming the existing runbook machinery, not a generator and not a new artifact class | MED impact | owner can prefer prose in the methodology instead, accepting the weaker binding]` — **owner-confirmed 2026-08-05** ("nice on tier 3 fillable runbook template"); this entry previously read "generated runbook" and was corrected here rather than only in the build plan, so the two do not disagree.
- `[ASSUMPTION: the Critic trigger is an author-declared **Dependency change:** build-plan field, mirroring Foreign API's and Exposed API's opt-in model, rather than diff-detected from touched manifests | MED impact | diff-detection is the stronger guarantee but requires classifying "is this a dependency manifest", which is the §6 allowlist trap; deferred to backlog as api-design did]` — added at plan-authoring time.
- `[ASSUMPTION: the advisory probe fires universally on the missing fact with no codebase scan at all, per §6's universal trigger | LOW impact | the alternative is a scan, which is the rejected allowlist]` — added at plan-authoring time.
- `[ASSUMPTION: "declared trusted" is recorded per-party with a why in the security-model Direction entry, not as a bare list | LOW impact]`
- `[ASSUMPTION: the conformance scan reads intake-surface configs but never executes package-manager commands to enumerate them | MED impact — keeps the scan hermetic and offline, consistent with the local-first/no-network norm in architecture.md; the tier-3 procedure is where network reads legitimately happen]`

## 12. Sources (checked 2026-08-05)

- [Dependency Cooldowns — cross-tool configuration reference](https://cooldowns.dev/) — per-tool key, syntax, default, and security-exemption status
- [Package Managers Need to Cool Down — Andrew Nesbitt](https://nesbitt.io/2026/03/04/package-managers-need-to-cool-down.html) — the eleven names
- [Minimum Release Age — Renovate Docs](https://docs.renovatebot.com/key-concepts/minimum-release-age/)
- [GitHub and PyPI Bet On Time to Slow Down Software Supply Chain Attacks — DevOps.com](https://devops.com/github-and-pypi-bet-on-time-to-slow-down-software-supply-chain-attacks/) — Dependabot's 3-day default and security bypass
- [TanStack and 160+ npm/PyPI Packages Compromised in Supply Chain Worm — Orca Security](https://orca.security/resources/blog/tanstack-npm-supply-chain-worm/) and [safedep](https://safedep.io/mass-npm-supply-chain-attack-tanstack-mistral/) — May 2026 campaign, install-time payloads
- [Supply Chain Attacks Surge March 2026 — Zscaler ThreatLabz](https://www.zscaler.com/blogs/security-research/supply-chain-attacks-surge-march-2026) and [Dependency cooldowns: a simple supply chain fix](https://christian-schneider.net/blog/dependency-cooldowns-supply-chain-defense/) — measured dwell times
- [How to Protect Against Python Supply Chain Attacks with uv](https://pydevtools.com/handbook/how-to/how-to-protect-against-python-supply-chain-attacks-with-uv/) — uv `exclude-newer` relative durations, pip `--uploaded-prior-to`
