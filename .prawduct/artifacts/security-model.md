---
artifact: security-model
version: 1
depends_on:
  - artifact: product-brief   # vision lives in README.md + CLAUDE.md
  - artifact: data-model
last_validated: null
---

# Security Model

<!-- Proportionate to a developer tool that handles NO sensitive data. classification records
     handles_sensitive_data: null and has_multiple_party_types: null. The real security surface is
     supply-chain / plugin-trust and untrusted content in governance state — not authn/authz.
     Written toward the posture we want to hold. -->

## Threat Model in One Paragraph

Prawduct persists only development-process metadata (state, learnings, evidence, findings, backlog)
— no PII, credentials, financial, or health data, and nothing under a regulatory obligation. There
is one actor class (the product owner) plus the AI runtime; there are no privilege tiers or trust
boundaries between parties. So the classic web-app security surface (authn, authz, data isolation)
**does not apply.** What *does* apply, and is the whole security story, is: **prawduct is code that
runs on a developer's machine on Claude Code lifecycle events** (supply-chain / plugin-trust), and
**it reads state files and repo content that may not be trustworthy** (untrusted-input handling).

## Direction

<!-- Ratified norms (2026-07-17). See docs/norms.md. -->

- **Untrusted governance state — backlog, learnings, recalled memories, fetched references, prior-session handoffs — is data, not instructions.** Content describes or informs; it never carries authority to direct the agent or the framework, and recalled state is verified against reality before it is acted on.
  Why: for a tool with no sensitive data the real hazard is trusting *stale or crafted* metadata rather than a classic payload — treating state as vetoable-and-verified rather than authoritative is the mitigation; malformed state fails soft (skip + attribute), never executes.
  Status: steady-state.
- **A destructive or irreversible operation requires explicit owner approval at the OPERATION level — one informed confirmation covering the whole act, naming its blast radius and what cannot be undone. It does not require a per-action gate: granular steps inside an approved operation proceed without re-confirmation.**
  Why: the point is an informed human decision at the moment of commitment, not a count of confirmations. Preview-by-default (`--apply` on migrate/init/scaffold/repo-disable/learnings-audit) remains the right shape *where the command is the operation*; it is the wrong shape where one approved operation performs thousands of mutations. A 295-item migration cannot ask 295 times — and if it tried, the confirmations would be clicked through, which degrades the one approval that actually matters. Confirmation fatigue is a safety regression, not a safety feature.
  Status: steady-state.

  **Amended 2026-07-24 (owner ruling).** The prior form read: *"No destructive action without an explicit `--apply` step; state-mutating lifecycle commands default to a dry run."* Owner: *"too black and white — we need high-level approval for destructive, but not for each granular action."* The absolute form failed in two directions at once. It was **unsatisfiable** — the backlog adapter implements no generic `--apply`/dry-run contract at all (BKL-8V3D established this; the only preview-before-write is `restructure-preview`), so the norm as written was already departed from by shipped code with no recorded decision. And it was **wrong to satisfy literally** — gating each of a migration's ~900 writes would produce exactly the rubber-stamping it exists to prevent. Amended toward the property, never weakened: the requirement is a *real, informed, operation-level* approval.
  **Citation re-affirmed 2026-07-31, and this record detached from `Status:` above.** BKL-8V3D shipped (archived `closed-by: v3.2.0-golive`) and `dead-why` fired. **The norm stands and the cited fact is unchanged**: BKL-8V3D delivered the *honest claim* — `adapter-mode.md` now reads "No generic preview-or-apply flag sits over those mutations" — not a dry-run contract, so the adapter still has no generic `--apply` and the amendment's premise is now better evidenced than when written (an undocumented departure became a documented absence). The probe fired because `_direction_lines` soft-wrap-joins an unseparated paragraph onto the preceding field, so this **historical** record was being read as live `Status:` rationale. The blank line above is the fix the probe's own contract prescribes ("a paragraph after a blank line stands alone"). The id literal is deliberately **kept** — dropping it would silence the probe by making the premise untraceable, which is the opposite of what norm citations are for.
  What this does **not** relax: the operation-level approval must be genuine — it names the target, the volume, and the irreversibility *before* the first write, and it is a distinct act, never inferred from the user having asked for something adjacent. An operation that cannot state its blast radius up front has not earned a single approval either.
  Conformance of the two live cases: **the migration** (`migration-scrub.md` Step 0 — owner-confirmed target repo, bound by every later step, with MG1's no-issue-delete stated) conforms; **`file-upstream`** (preview → `payload-digest` → `--approve <digest>`, per report) conforms, and there the operation *is* one filing, so per-report approval is operation-level rather than granular.
- **A governed product's content never leaves that product's own repository and owner. The backlog adapter reaches exactly the repo named in `backlog_service_repo`; the upstream bug channel is filesystem-local. Any cross-owner or public-plane filing surface is an owner decision, never an increment.**
  Why: a **private** consuming repo filing upstream into prawduct's **public** tracker would carry that repo's paths, code excerpts, learnings prose and product detail across a trust boundary in a direction nobody chose — and the damage is irreversible on a public tracker. The cross-owner design (`file-upstream`, XP1/XP2 in `documentation/backlog-service-security-model.md`) is already written and deferred to roadmap wave W3, so the risk is not that someone invents this surface — it is that it lands quietly as "the next wave." Making it a decision is the whole mitigation.
  Status: in-transition — tracking item **BKL-7Q4M** (safe upstream filing: content minimization, redaction, and owner preview-and-consent for the outbound payload), the named 3.2.0 release blocker. **Requirements settled 2026-07-23**, captured in the single durable requirements doc `documentation/backlog-service-requirements.md` (Upstream bug reporting — XP4–XP7); the norm stays `in-transition` because the capability is still **unbuilt** (design + build pending). The end state is *not* permanent prohibition: a private repo filing upstream is a capability prawduct wants, and BKL-7Q4M is the work that makes it safe to have. Interim rule: **no surface that sends product content to a foreign owner ships until BKL-7Q4M's requirements are settled and its design reviewed.** Local-only channels (the `incoming-bugs/` drop-box, the product's own `backlog_service_repo`) are unaffected and remain the supported path meanwhile.
  Mechanism: `tests/preferences/test_no_upstream_content_egress.py` — fails if a `file-upstream` surface appears anywhere in the plugin, or if prawduct's own tracker reaches the backlog adapter. This is *interim* enforcement of the interim rule; when BKL-7Q4M lands, the test is **replaced** by one asserting the XP7 adapter contract (target-pinned, authenticated, refuses-without-owner-approval, no self-file), and this norm is amended to its steady-state form. It is never weakened to let an unreviewed surface through.
  Retroactivity: none required — no shipped surface departs from this at birth. Verified 2026-07-21: `file-upstream` has zero occurrences plugin-wide, `/prawduct:report-bug` writes only to a local `incoming-bugs/` drop-box and explicitly refuses a remote write when no local checkout is reachable, and `backlog_service_repo` names the product's own repo.
- **Code someone else releases enters this repo only on the terms recorded in `## Upstream Dependencies` below.** The clauses, the tier model and the per-ecosystem mapping are the framework's and are stated once in `plugin/docs/upstream-dependency-policy.md`; what this norm binds is that prawduct's *own* intake is governed by them rather than exempt from them.
  Why: prawduct ships this policy to every product it governs, and a rule its author's own repo ignores is the aspirational-rule shape the norm lifecycle exists to catch. There is also a direct exposure and it is not hypothetical — the repo runs GitHub Actions with its credentials and installs test dependencies that execute in CI and on contributors' machines. The clause-1 default earned its keep on the day this norm was written: the resolver's choice of `packaging` was a release published two days earlier, which the minimum release age excluded (see the tier record below). The figure itself stays in clause 1 of the spec — this file's own "Chosen values" paragraph refuses to copy it, and a *Why* line is not an exemption from that.
  Status: steady-state, with one clause departed from (clause 4, install-time execution) and two surfaces knowingly below their best reachable tier (the build backend, and local/agent installs as distinct from CI). All three are named in the section below rather than left for a later reader to discover — a record that counts its own exceptions low is the failure mode this norm's own subject matter is about.
  Retroactivity: applied at birth to both existing intake surfaces, not deferred. The CI-action pins were already conformant on their own recorded reasoning; the Python dev extra was not, and was raised to tier 1 in the same commit as this entry rather than filed.

## Authentication & Authorization

**Not applicable — single actor, no privilege tiers.** There is nobody to authenticate and no
access to partition. If this ever changes (a shared or multi-party governance surface), it is a
`has_multiple_party_types` characteristic flip that re-derives this model — not an incremental feature.

## Supply-Chain & Plugin Trust (the primary concern)

Prawduct executes on the user's machine — Python hooks fire on SessionStart/Stop/UserPromptSubmit/
SubagentStop, and skills invoke the `prawduct-hook` CLI. Running someone else's plugin is a trust
decision, and prawduct's job is to be worthy of it. The posture we hold:

- **Least authority over the machine.** The plugin writes nothing into a governed repo beyond what
  `architecture.md` § Direction's reconciled-files norm enumerates, and never framework files. That
  norm is the enumeration's one home and this posture deliberately points at it rather than
  restating a membership that would then drift — which it did: the 2026-07-30 amendment adding
  `CLAUDE.md` reached the norm and not the two copies. Plugin code itself is read-only from the
  repo's perspective.
- **Zero external dependencies, no network.** The governance runtime is standard-library Python with
  no third-party packages and makes no network calls — the entire coordination substrate is process
  spawn + local files + git. This shrinks the supply-chain surface to prawduct's own code plus git.
  **Three sites reach the network, and one of them IS on a hook path** — stated precisely because
  the first version of this paragraph said "neither on a hook path" and was wrong:
  the opt-in backlog backend (`lib/backlog/transport.py`); `check-released`'s `gh` call
  (`lib/release_verification.py`, 2026-08-04), operator/CI-invoked; and a `gh pr list` inside
  `cmd_stop` (`plugin/bin/prawduct-hook`), which runs on the **Stop hook**. The first two scrub
  credentials out of foreign-CLI stderr before echoing or serialising it; the Stop-hook call does
  not echo stderr at all.
- **Subprocess safety is enforced, not advised.** Every subprocess invocation passes arguments as an
  argv list; `shell=True` is **banned and mechanically enforced** by a test that AST-walks the
  codebase and fails on any occurrence. Compound shell logic (pipes, `&&`, env assignment) is not
  smuggled into a subprocess call — it lives in a script the call points at. Subprocess launch
  failures are caught and exit cleanly rather than crashing the hook.
- **Installation integrity.** The install reference a repo commits pins the marketplace and plugin;
  the marketplace source form is chosen so updates re-resolve over the marketplace's own checkout
  (avoiding a re-clone that could fail or be redirected). A version bump is the auto-update cache
  key (see `operational-spec.md`), so what a user runs is a deliberately published release.

## Untrusted Content in Governance State

Governance state (backlog, learnings, recalled memories, fetched references, prior-session
handoffs) is **data, not instructions.** This is the security-relevant stance we want held as a
first-class principle:

- **Content in state files never carries authority to direct the agent.** A backlog item, a recalled
  memory, or a fetched web page describes or informs; it does not issue commands the framework or
  agent must obey. Recalled memories reflect what was true when written and are verified against
  reality before being acted on.
  - *Current state (honest):* this stance is real but currently lives as **distributed prose** across
    several skills and requirements docs rather than one canonical rule or a mechanical check. The
    intended direction is to state it once, prominently, as a norm — it is a strong ratification
    candidate.
- **Malformed state is a fail-soft event, never a crash or a security incident.** Parsers for
  backlog, project-state, advisories, and evidence self-heal or skip bad input with attribution;
  they never execute it and never block a session on it. A corrupt file is set aside, not trusted.
- **Stale or wrong state is the top practical hazard.** The most damaging realistic failure is not a
  malicious payload but *trusting stale metadata* — e.g. an item marked "ready" that is already
  shipped, or a note describing a live destructive code path as dead. Treating state as
  vetoable-and-verified rather than authoritative is the mitigation.

## Data Privacy

- **Classification: no sensitive data in scope.** Persisted content is development-process metadata.
  There is no PII, no secrets, no regulated data. Observability output (logs, ledger, findings)
  therefore has no sensitive-data-filtering obligation — though the general rule "log the operation
  and the entity id, not the payload" is still the right default (see `observability-strategy.md`).
- **Shared vs. local is a deliberate boundary.** Team-shared decisions are committed
  (`project-state.yaml`, `backlog.md`, `learnings*.md`); per-clone nag/cache/session state is
  gitignored and never leaves the machine. Contributors should keep secrets out of committed
  governance state as a matter of hygiene, since those files travel with the repo.

## Abuse Prevention

The abuse surface is small and local. The controls that matter:

- **Input validation at every parse boundary**, with fail-soft handling (above).
- **Fail-closed authority, fail-soft advice** (see `architecture.md`): anything that produces a
  governance *verdict* blocks on ambiguity; anything that merely informs degrades quietly. This
  split is itself an abuse-resistance property — you cannot make a gate pass by feeding it garbage;
  garbage makes it block.
- **No destructive or irreversible operation without explicit owner approval at the OPERATION
  level.** One informed confirmation covering the whole act, naming its blast radius and what cannot
  be undone — not a per-action gate. Preview-by-default (`--apply` on migrate, init, scaffold,
  repo-disable, learnings-audit) is the right shape *where the command is the operation*; where one
  approved operation performs thousands of writes the approval is taken once, up front, and granular
  steps proceed without re-confirmation. The one destructive migration lands as a single revertible
  commit. *This control tracks the `## Direction` norm as amended 2026-07-24 — the pre-amendment
  absolute form is recorded there as history, and must not be restated here as live.*

## Upstream Dependencies

The six clauses, the three enforcement tiers and the ecosystem mapping live in
`plugin/docs/upstream-dependency-policy.md` and are not restated here. What follows is only what is
this repo's own: the chosen values, the trusted register, and the tier each intake surface reaches.

**Chosen values.** Clauses 1, 3 and 6 take the framework defaults unmodified — the minimum release
age is the figure in clause 1 of the spec and is deliberately not copied here, the security fast path
is adopted, and new-dependency intake requires verifying package identity rather than accepting that
a name resolves. The defaults are *chosen*, not inherited by omission, and the decision block in
`project-state.yaml` records them so the choice is legible to the checks that read it.

**Why an exact-version constraints file, and not something stronger.** Tier rule 1 says prefer the
strongest mechanism the ecosystem allows, so the mechanism that expresses clause 5 is itself a
decision and is recorded rather than left to look inevitable. Three were weighed. A **committed
lockfile** (`uv.lock`, `poetry.lock`) was rejected because it requires adopting that resolver as the
repo's install path, which is a toolchain commitment out of proportion to a five-package dev extra —
and `.gitignore` already records that a second resolved set would be redundant beside this one.
**Hash-pinned requirements** (`pip install --require-hashes`) is the genuinely stronger declarative
form and is the one worth naming, because rejecting it is not obvious: it pins *artifacts* rather
than versions, so a re-uploaded or substituted wheel fails the install instead of passing it.
It is not adopted here for a reason that was **verified rather than reasoned about**: this repo's CI
line installs the local project itself (`pip install ".[dev]"`), and pip refuses to hash a directory
requirement at all — `ERROR: Can't verify hashes for these file:// requirements because they point
to directories` (checked on pip 26.2.1, with a control proving the same command succeeds against
hashed wheels alone). So the flag does not degrade on this install shape, it fails it. The first
draft of this paragraph blamed build isolation — the mechanism that defeats constraints for
setuptools — and the experiment falsified that; the real blocker is one rung earlier and has nothing
to do with the build backend. **So: exact-version constraints today, and hash pinning becomes
reachable only if the local-project install leaves the hashed command** (installing the project
separately, or not at all in the test job) — not a mechanism nobody considered. A product copying
this record should copy the reasoning, not the conclusion: a product that installs only third-party
wheels can reach `--require-hashes` immediately and should.

**One clause is departed from, and this is its rationale.** **Clause 4 (install-time execution) is
not satisfied:** upstream code is not denied execution at install time. `pip` builds the local
project from source on every install, so `--only-binary :all:` would refuse the install itself rather
than merely deny upstream build scripts — the denial is unavailable without restructuring how this
repo is installed at all. Recorded as an accepted state rather than as coverage. The janitor's intake
question ("is install-time execution still as recorded") therefore grades against *not denied*, which
is what the decision block says and what this paragraph now says too.

**Declared trusted parties — one, with its why.**

- **`actions/*` — GitHub's own organisation.** Taken at the floating major tag (`@v7`) with no
  minimum age. Why: the major tag is the publisher's documented contract, and floating on it is what
  picks up their security fixes without a bump — pinning to a SHA here would trade a real benefit for
  protection against a compromise of the platform that is already executing the workflow. The
  reasoning was recorded in `.github/workflows/tests.yml` before this policy existed; declaring it
  here makes it auditable rather than a comment.
- **Deliberately NOT trusted: `pytest`, `pytest-xdist`, `pytest-timeout`, `pyyaml`, `setuptools`.**
  Widely-used and reputable, which is the property the 2026 campaigns exploited via maintainer-account
  compromise — the spec's accepted-risk note applies to them exactly. They are untrusted, so clause 1
  governs them, which is what `constraints.txt` enforces.

**Per-surface tier record.** Rule 2 of the tier model is to record the tier actually reached, not the
one aspired to.

| Intake surface | Tier reached | Basis |
|---|---|---|
| GitHub Actions (`.github/workflows/`) | 3 | Trusted party, so clause 1 does not apply; the standing rule that a *third-party* action would be SHA-pinned is the tier-3 procedure. No update bot, so tier 2 is unavailable. |
| Python test dependencies — **in CI** | 1 | `constraints.txt` pins the full resolved closure and the workflow installs through it, so clauses 1, 2 and 5 bind that path mechanically. |
| Python test dependencies — **local and agent installs** | 3 | The `-c` flag lives on one workflow line. Nothing pip reads on its own carries it — no committed pip config, no exported `PIP_CONSTRAINT` — so a contributor or an in-session agent running the documented command is bound by the procedure, not by the toolchain. Splitting the row rather than claiming tier 1 for both is rule 2 applied: the CI path really is tier 1, and the other really is not. |
| Runtime dependencies | n/a | There are none. `architecture.md` § Direction forbids third-party runtime dependencies, and the plugin imports only the standard library. |

**What "tier 3" currently denotes here.** For the surfaces recorded at tier 3 above, the procedure is
the sentence in this section and in the decision record — not a filled copy of
`templates/upstream-dependency-update-runbook.md`, which this repo has not authored for itself. The
spec is explicit that tier 3 must be a procedure rather than a prompt, so this is the weaker form and
is named as such. Blast radius is small: the CI-action surface is trusted, so clause 1 does not reach
it, and the build backend below is one package. Recording what the tier denotes is rule 2 again — a
reader comparing this record against the spec should not have to infer which sense of tier 3 is meant.

**Below best reachable tier, knowingly — the build backend.** `[build-system] requires =
["setuptools>=61"]` resolves in pip's isolated build environment, which **no constraints mechanism
reaches**: verified on pip 26.2.1, a `setuptools==60.0.0` pin below the declared floor was ignored
via both `-c` and `PIP_CONSTRAINT`, and the build environment fetched 83.0.0 regardless. So setuptools
re-resolves on every CI install and is enforced at tier 3 only. It is deliberately absent from
`constraints.txt` rather than listed there: a pin that cannot bind would read as coverage this repo
does not have, which rule 2 calls worse than an absent claim. Closing it needs `--no-build-isolation`
with setuptools pre-installed, or dropping the local build step altogether — tracked as **#609**,
cited literally so the residual's tracking is checkable rather than taken on trust.
