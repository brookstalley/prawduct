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
- **No destructive action without an explicit `--apply` step; state-mutating lifecycle commands default to a dry run.**
  Why: a preview-by-default gate on migrate/init/scaffold/repo-disable/learnings-audit means no irreversible change happens by accident; the one destructive migration lands as a single revertible commit.
  Status: steady-state.

## Authentication & Authorization

**Not applicable — single actor, no privilege tiers.** There is nobody to authenticate and no
access to partition. If this ever changes (a shared or multi-party governance surface), it is a
`has_multiple_party_types` characteristic flip that re-derives this model — not an incremental feature.

## Supply-Chain & Plugin Trust (the primary concern)

Prawduct executes on the user's machine — Python hooks fire on SessionStart/Stop/UserPromptSubmit/
SubagentStop, and skills invoke the `prawduct-hook` CLI. Running someone else's plugin is a trust
decision, and prawduct's job is to be worthy of it. The posture we hold:

- **Least authority over the machine.** The plugin reads and writes **only** the governed repo's
  `.prawduct/` (per-worktree) and the clone's shared evidence store inside `.git`, plus the
  `.gitignore` and `.claude/settings*.json` it must reconcile. Plugin code itself is read-only from
  the repo's perspective; the framework never writes framework files into a repo.
- **Zero external dependencies, no network.** The governance runtime is standard-library Python with
  no third-party packages and makes no network calls — the entire coordination substrate is process
  spawn + local files + git. This shrinks the supply-chain surface to prawduct's own code plus git.
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
- **No destructive action without an explicit apply step.** State-mutating lifecycle commands
  (migrate, init, scaffold, repo-disable, learnings-audit) default to a dry run and require an
  explicit `--apply`; the one destructive migration lands as a single revertible commit.
