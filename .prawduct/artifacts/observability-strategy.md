---
artifact: observability-strategy
version: 2
depends_on:
  - artifact: nonfunctional-requirements
  - artifact: product-brief   # purpose lives in documentation/purpose.md
last_validated: null
---

# Observability Strategy

<!-- Prawduct is a terminal + file based developer tool with no server and no sensitive data. Its
     "operators" are the product owner reading terminal output and the AI runtime reading the same
     output and files directly. Observability is therefore mostly "make the right thing legible in
     the terminal and durable on disk" — with one genuinely structured signal, the governance
     ledger. Written toward the design we want. -->

## What You Get

The scenarios this design must make answerable:

1. **"What state is my repo in right now?"** → the SessionStart briefing assembles it at the top of
   every session (branch, active work, advisories, stale artifacts, size warnings) — for the *agent*,
   on stdout. The owner learns the parts that matter **by relay**: the agent is directed to surface
   consequential advisories and version changes in conversation (see § How the owner actually learns).
2. **"Is my prawduct install healthy?"** → `/prawduct:doctor` reports **healthy** or **degraded**
   with the specific reason.
3. **"Why did a gate block me?"** → the block message names the gate and the remedy inline; nothing
   blocks silently.
4. **"Is review costing too much?"** → `review-stats` aggregates the governance ledger into
   wall-clock, run-count, and finding-yield numbers (this is how the P0 wall-clock budget in
   `nonfunctional-requirements.md` is actually watched).
5. **"What nudges am I ignoring?"** → `/prawduct:advisory list` on demand; and for `warn`/`urgent`,
   the relay raises them unasked, so ignoring one is a choice rather than an accident.

If those five are answerable from the terminal and the committed/local state, observability has
done its job.

### How the owner actually learns

The channel norm below is deliberate and correct: stdout is the agent's, stderr is the person's. The
consequence is easy to miss and was missed for several releases — **almost everything prawduct says
about itself is said to the model.** The briefing, its advisory block, and the version-delta banner
all print to stdout. The banner compounds it: it renders once at a version crossing, then advances
its marker and never renders again.

So a capability could ship, be announced, and reach nobody. That is not hypothetical — it is how the
backlog service shipped: announced at the crossing, on the agent's channel, with the one advisory
that would have nudged it registered as a no-op.

The mechanism that closes it is a **relay directive** at each emission site — `banner.RELAY_MARKER`
for a version crossing, `briefing.ADVISORY_RELAY_TEXT` for an active `warn`/`urgent` advisory. Each
instructs the agent to surface the news in conversation, which is the one channel the owner reliably
reads. Two properties are load-bearing:

- **At the emission site, not in the session digest.** A directive fires only when there is something
  to say; a digest rule is re-read every session to cover the minority that have news, and sits far
  from the content it governs. This mirrors the same release's learnings change — deliver the rule
  where it applies rather than parking it in a file to be read later.
- **`warn`/`urgent` only.** Relaying `info` every session is nagging, and a channel that nags gets
  tuned out — which would cost the `warn` case the audience it exists for.

**Rejected: routing advisories to stderr by consequence.** Tempting, since the norm already provides
the split and stderr is the person's channel. Rejected because the relay covers advisories,
headlines, and gate activations through one mechanism, whereas channel-routing would solve only the
advisory third and add a second way for the same signal to reach the same person. Revisit if the
relay proves unreliable in practice — the evidence to watch for is an owner surprised by a `warn`
they were never told about.

## Direction

<!-- Ratified norms (2026-07-17). See docs/norms.md. -->

- **Terminal signals use a stable severity-prefix vocabulary (`CRITICAL:` / `WARNING:` / `NOTE:` / `PRAWDUCT:` / `BLOCKED —…`) with a channel split: stdout is the agent-facing channel (composed into model context), stderr is the user-and-diagnostics channel.**
  Why: the AI runtime is a primary observability consumer, so a stable prefix vocabulary is what makes terminal output machine-legible, and the stdout/stderr split keeps context-injection clean while warnings and blocker text still reach the human.
  Status: steady-state.
- **The governance ledger has a single writer (the `ledger-append` helper); agents never hand-author it.**
  Why: the derived metrics `review-stats` reports are only trustworthy if the event stream has one disciplined writer — a hand-authored ledger line is an unvalidated fact in the observability path.
  Status: steady-state.
- **Text emitted into a governed product names no prawduct-internal identifier.** Advisory fields, reviewer findings, and hook stdout/stderr carry the plain-language reason; requirement, chunk, and backlog ids stay on the non-emitted side — comments, docstrings, tests, build plans, learnings, and the instruction prose a skill reads but never speaks.
  Why: an operator in a downstream product cannot resolve `GV8` or `MG6` — the id displaces the sentence that would have made the message actionable and reads as a reference to a defect tracker they have no access to. The trace still exists for prawduct developers one line away, so nothing is lost by moving it there.
  Status: **steady-state** as of 2026-08-02 — transitioned from `in-transition` when OBS-7M4D (#209) closed the last emitted sites. The four the item inventoried: `cmd_clear`'s critic-active refusal (`CRT-3X9D`), the backlog CLI `_HELP` `reconcile-labels` (`GV6`) and `import` (`MG6`) lines, and `validate_partial`'s waived-disposition error (`R7`). Plus **three the item's inventory did not contain**, found only when the sweep was widened (below): `_worktree_redirect_note`'s Stop-hook stderr line (`STH-4K7N`), the designer-handoff waiver note (`v1.4 F6`), and the restructure-preview document's title line (`MG6`), which is written for the owner to read. Each id moved to the adjacent comment and each message now carries the reason it stood for. Two further sites named in the original inventory — the `--archive-scope open` warnings in `cli.py` and `lib/backlog/migrate.py` — had already left it when commit `0191f1e` rewrote both and the `MG2` id went with the export promise; the interim rule is what made that rewrite clean up after itself. The interim rule (*emitted text a changeset writes or edits complies*) is **retired with the transition** — there is no longer an untouched-site backlog for it to except, so the norm now binds every emitted string unconditionally.

  **Enforcement is the reviewer's judgment, not a regex** — recorded here at the transition because it is the norm's one standing weakness, and demonstrated *by* the transition. The first sweep run against this norm narrowed to string literals passed **as arguments** to `print`/`error`/`log_diag`/`TransportError`, and reported clean. It was wrong three times over, because the emitted-text surface is not syntactic: a string can be **returned** from one function and printed by its caller (`_worktree_redirect_note` → `cmd_stop`), **appended to a list** that is printed at session end (the waiver notes), or **assembled into a document** written to disk for a human (the restructure preview). Two independent reviewers caught the first; only the widened sweep caught the other two. The falsifying command is therefore *every non-docstring string literal under `plugin/lib/` and `plugin/bin/`, reviewed by eye* — ten hits today, of which the survivors are ordinary English (`NO-GO`, `RE-ENABLE`, `SCHEMA-AHEAD`), regex character classes, or placeholders in the operator's own vocabulary (`VRF-NNN`, `PFX-XXXX`, `ABC-1234`). Even that is a floor: id prefixes are open-ended, so a new prefix is invisible to any pattern by construction. A clean sweep means "no *known-shaped* id survives in a literal" — never "no emitted text names an id", which is why the Critic reads emitted text rather than trusting the command.
  Retroactivity: migrate — swept at birth with an id-shaped-token heuristic over string literals and skill prose. Five sites were in the birthing changeset and were fixed there: the three dormancy NOTE copies, `skills/backlog/adapter-mode.md`'s `find` NOTE, and `probe_checks_dormant`'s advisory evidence (which named `C-B1`–`C-B4` and `R-1`/`R-2` — check labels are internal ids for this norm's purpose, ruled explicitly rather than left as the interim rule's first exception). The remaining six are sized into OBS-7M4D. The heuristic is **not** exhaustive — id prefixes are open-ended — so the durable enforcement is the reviewer's judgment, not a regex.

## Architecture

```
governance code ──emits──▶ terminal (stdout/stderr, prefixed messages)  ──▶ human + agent read live
      │
      └──appends──▶ .governance-ledger.jsonl (structured events) ──pulled──▶ review-stats / janitor
      └──writes───▶ evidence.jsonl + .critic-findings.json ──────────────▶ gates + briefing
```

There is no exporter, collector, or backend to run. Signals live in the terminal (ephemeral,
read live) and in local files (durable, read on demand). This is deliberate: an observability stack
that required infrastructure would violate the local-first, zero-dependency posture.

## Signal Types

### Logging

Terminal messages with a **stable severity prefix vocabulary** — `CRITICAL:` / `WARNING:` /
`NOTE:` / `PRAWDUCT:` / `BLOCKED —…` — and a disciplined channel split we want to hold:

- **stdout is the agent-facing channel** (SessionStart hooks surface stdout into the model's
  context) — briefings and injected guidance go here.
- **stderr is the user-and-diagnostics channel** — warnings, blocker text, and fail-soft
  attribution notes go here, keeping stdout clean for context injection.

There is no log aggregation and no retention policy — the terminal is the log, and durable events go
to the ledger instead. That is the right level for this product.

### Metrics

Metrics are **derived, not separately instrumented** — the cheaper design. The governance ledger
(`.governance-ledger.jsonl`) is an append-only event stream written by a **single writer** (the
`ledger-append` helper — agents never hand-author it), and `review-stats` derives the operational
metrics that matter (review wall-clock, run-count, finding yield, cost) from it. Telemetry is
**pulled, not pushed**: no hook nags about it; maintenance (`/prawduct:janitor`) and on-demand
`review-stats` read it. The report carries a schema version so cross-version aggregation stays
sound. Corrupt or unusable ledger lines are reported **with counts**, never silently dropped.

### Tracing

No distributed tracing — there are no network hops. The equivalent need — "which review covered
which change?" — is served by **tree-keyed correlation** instead: facts and ledger events reference
git tree/commit SHAs and carry `project`, `scope`, `chunk`, and `actor` (role/model), so any review
verdict can be traced back to the exact tree it attests and the reviewer that produced it.

## Instrumentation Layers

- **Layer 1 (automatic):** the SessionStart briefing and the version-delta banner emit on every
  session with no per-call instrumentation.
- **Layer 2 (declarative):** gate blocks and advisory probes emit prefixed messages as a byproduct
  of running; the ledger event is appended by the one consolidation path.
- **Layer 3 (contextual):** ledger events and facts are enriched with scope/chunk/tree/actor.
- **Layer 4 (manual):** kept minimal — explicit `NOTE:` emissions at fail-soft boundaries. Most
  coverage comes from layers 1–2, as intended.

## Correlation Context

Per-session and per-tree. The session anchor (session-start marker) and the git **tree SHA** tie
related events together: a session's briefing, its gate outcomes, and its review facts all key off
the same session/tree identity. There is no cross-request or cross-user correlation because there
are no concurrent requests or users.

## Sensitive Data Filtering

**No sensitive data in scope** (see `security-model.md`) — there is nothing to redact. The general
structural default still applies as good practice: signals record *what happened and which entity*
(operation + tree/entity id), not payload contents. Governance state that travels with the repo
(committed files) should not carry secrets — a hygiene rule, not a filtering mechanism.

## Alerting

**No automated alerting** — there is nobody to page and nothing running unattended in the
server sense. The advisory system is the closest analogue: post-sync **advisories** surface at
session start as durable, dismissible nudges (per-clone dismissal state), and gate blocks are the
"alert" that stops an unsafe session end. Both are pull/inline, not push.

## Health Signals

- **Healthy** = install reference present, `distribution: plugin`, no leftover framework residue,
  core state present and parseable, discovery captured. `/prawduct:doctor` says so explicitly.
- **Degraded** = governance still works but something is off (stale artifact, size-over-threshold
  warning, missing optional decision, unratified norms). Named and surfaced, not hidden.
- The **fail-soft posture is itself a health signal**: if the briefing renders, the plugin loaded
  and basic health holds; a probe that errored prints an attributed `NOTE` and the session
  continues.

## Infrastructure and Deployment

None. No observability backend is deployed — signals are terminal + local files. Observability is
**always-on and zero-cost**: there is nothing to configure, nothing to opt into, and no cost to the
observability itself beyond the bytes of the ledger. This is the correct scale for a local,
single-actor developer tool; prawduct deliberately prescribes no tracing/metrics vendor.

## Agent-Accessible Observability

**First-class — the AI runtime is a primary observability consumer.** Every signal is directly
readable by the agent: terminal output composes into context, and all durable signals are plain
files (`evidence.jsonl`, `.governance-ledger.jsonl`, `.critic-findings.json`, `project-state.yaml`)
the agent can read and the `prawduct-hook` CLI can query (`evidence status|list`, `review-stats`,
`coverage-status`). The agent's debugging loop — run → observe → investigate → fix → verify — never
breaks at "investigate," because investigation is just reading files and running read-only
subcommands. This is why observability here needs no rich visualization: the consumers read text.

## Verification

Observability is working when each "What You Get" scenario is reproducible: start a session and the
briefing renders; run `/prawduct:doctor` and it states healthy/degraded with reasons; trigger a
gate block and the message names the gate and remedy; run `review-stats` and it returns real
numbers from the ledger; list advisories and see their state. These are exercised as part of normal
use, so drift is caught quickly.

## Examples

See `docs/examples/` for observability design examples for other product shapes (a three-signal API
service, an event-driven system). Prawduct itself is the "CLI tool: the terminal and the log file
are the observability" end of that spectrum — with the governance ledger as its one structured
signal.
