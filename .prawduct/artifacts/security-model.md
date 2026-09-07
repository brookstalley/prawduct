---
artifact: security-model
version: 1
depends_on:
  - artifact: product-brief   # purpose lives in documentation/purpose.md
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
  Conformance of the two live cases: **the migration** (`migration-scrub.md`'s target-selection step — owner-confirmed target repo, bound by every later step, with MG1's no-issue-delete stated) conforms; **`file-upstream`** (preview → `payload-digest` → `--approve <digest>`, per report) conforms, and there the operation *is* one filing, so per-report approval is operation-level rather than granular.
- **A governed product's content leaves that product's own repository and owner only through a surface whose target the plugin pins and whose every filing the owner approves against the exact outbound bytes. The backlog adapter reaches exactly the repo named in `backlog_service_repo`; `file-upstream` is the one cross-owner surface, and it refuses to send unless every check holds — XP7's four adapter guarantees (pinned target, authenticated, no filing without a recorded owner approval, never self-filing) and XP5's per-report consent gate. Any further cross-owner or public-plane filing surface is an owner decision, never an increment.**
  Why: a **private** consuming repo filing upstream into prawduct's **public** tracker would carry that repo's paths, code excerpts, learnings prose and product detail across a trust boundary in a direction nobody chose — and the damage is irreversible on a public tracker. What makes the surface safe to have is not that it is narrow but that the owner reads the exact bytes and approves them before any of them leave: the ceremony **is** the mitigation, so a later surface that reached the same tracker without it would be the same irreversible crossing under a friendlier name. That is why the last sentence of the statement outlives the capability that occasioned it.
  Status: steady-state — BKL-7Q4M delivered the surface this norm was waiting on, and the guarantee is now asserted as a contract rather than as an absence.
  Mechanism: `tests/preferences/test_no_upstream_content_egress.py` — asserts the XP7 adapter contract: the target is pinned to a plugin constant and a caller-supplied `--repo` cannot move it, the session is authenticated, no filing leaves without an owner approval matching a re-render of the bytes previewed, and the running repo can never file into itself. Those four, plus XP5's preference gate, are the five §5 checks, and each is asserted to refuse **independently**, and every refusal is asserted at the transport seam — nothing written — because "an error was returned" and "nothing was filed" are different claims and only the second is the guarantee. It is never weakened to let an unreviewed filing path through.
  Retroactivity: none required — no shipped surface departed from this **at birth**. The birth-time verification, 2026-07-21: `file-upstream` had zero occurrences plugin-wide, `/prawduct:report-bug` wrote only to a local `incoming-bugs/` drop-box and explicitly refused a remote write when no local checkout was reachable, and `backlog_service_repo` named the product's own repo. That inventory is the record of the sweep, not a live claim — the first of those three facts is deliberately no longer true, and the amendment below is why.

  **Amended 2026-09-07 (owner ruling), `in-transition` → `steady-state`.** The prior statement read: *"A governed product's content never leaves that product's own repository and owner. The backlog adapter reaches exactly the repo named in `backlog_service_repo`; the upstream bug channel is filesystem-local."* That form described the world in which the capability was designed but unbuilt, and its interim rule — no surface sending product content to a foreign owner ships until BKL-7Q4M's requirements are settled and its design reviewed — was satisfied on its own terms before this amendment: the requirements settled 2026-07-23 (`documentation/backlog-service-requirements.md`, XP4–XP7) and the design was reviewed at v1 (`documentation/backlog-service-upstream-filing.md`), which §8 of that design names as the trigger for this transition. **Amended toward the guarantee, never weakened.** The absence proved something only while there was no surface; once one exists an absence proves nothing at all, and what replaces it is strictly stronger — five checks that each refuse independently and file nothing, in place of a token scan asserting the surface was missing. The interim `Mechanism:` was written to be replaced by exactly this, in the same file, and it was: the enforcement row and the filename are unchanged, so nothing about this norm's enforcement moved house on the way. What did **not** relax: the third sentence of the statement is untouched, so the next cross-owner or public-plane surface is a fresh owner decision and inherits no permission from this one.

## Authentication & Authorization

**Not applicable — single actor, no privilege tiers.** There is nobody to authenticate and no
access to partition. If this ever changes (a shared or multi-party governance surface), it is a
`has_multiple_party_types` characteristic flip that re-derives this model — not an incremental feature.

## Supply-Chain & Plugin Trust (the primary concern)

Prawduct executes on the user's machine — Python hooks fire on SessionStart/Stop/SubagentStop,
and skills invoke the `prawduct-hook` CLI. Running someone else's plugin is a trust
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
  `lib/backlog/transport.py` (TWO callers — the opt-in backlog backend, and the owner-approved
  `file-upstream` op, which reaches the pinned upstream repo with `backlog_service_repo` unset);
  `check-released`'s `gh` call
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
