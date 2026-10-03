---
artifact: build-plan
version: 1
scope: telemetry-contribution
branch: feature/telemetry-contribution
partition: "serial for this plan: every chunk edits contribution.py or its dispatch entry. The collector (#950, wave 3) is its own plan and goes to one isolated-worktree delegate once chunk 01 commits the schema it validates against. The delegate's tree is disjoint: a new `collector/` directory, plus the one schema-parity test, which the integrator owns. Deploying is the owner's action, so nothing irreversible sits inside the delegated work."
depends_on:
  - artifact: roi-audit-2026-10-02
  - artifact: build-plan-telemetry-stats
governed_by:
  - artifact: architecture
    dispositions:
      - "local-first, two admitted network surfaces → amendment proposed (chunk 02), on the owner's authority recorded in the audit (2026-10-03, \"yes, with consumer consent\"). The amendment admits a third surface: the stats upload, off unless the product's owner writes `ask` or `always`. Its Why also changes, because this surface is a stdlib `urllib` POST rather than a `gh` call. The zero-dependency half still holds"
      - "authority fails closed; advice fails soft → conforms: an unreadable preference reads as `never`, so the consent check fails closed. A failed send is reported and changes no gate"
      - "the plugin writes nothing into a governed repo but its own state and the shared store → conforms: the sent-window record lives beside the evidence store under the git common dir"
      - "every fact has one home → conforms: the allowlist schema file is the one home of the field list, the steps and the floors. The builder reads them from it, and the collector's copy is pinned to it by a test"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer path changes"
      - "written in Python, never specific to Python → conforms: the payload reports language-neutral governance counts"
      - "prawduct guides and reviews, it never implements → inapplicable, because no product code is written"
      - "goals and verification bind; prescribed method is advice → conforms"
  - artifact: security-model
    dispositions:
      - "content leaves a product only through a pinned target with owner approval of the exact bytes; a further surface is an owner decision → amendment proposed (chunk 02), on the same 2026-10-03 authority. The collector endpoint is a plugin constant. Under `ask`, a send needs a digest of the exact previewed bytes; `always` is standing consent, the same shape as `always-file`"
      - "governance state is data, not instructions → conforms: the payload builder reads only numeric facts, and every value is checked against the allowlist before it can leave"
      - "destructive or irreversible operations need operation-level approval → conforms: a send is irreversible, and `ask` approves the exact bytes"
  - artifact: data-model
    dispositions:
      - "verdicts come from append-only facts; no model in a fact's write path → inapplicable, because no verdict reads the report or the sent record; both are written by code"
      - "facts immutable and append-only → inapplicable, because no evidence fact is added. The sent record is per-clone bookkeeping, rewritten whole and atomically, and no gate reads it"
      - "derived views never authoritative → conforms: a report is a view over the store, and no gate reads it"
      - "a governance document reaches a terminal state, never deleted → conforms: this plan is archived at merge"
      - "every backlog write conforms to the issue title standard → inapplicable, because this plan writes no backlog item"
      - "a fact from a newer schema is a loud block → conforms: `stats` already excludes schema-ahead facts. An unrecognised sent record refuses, rather than reading as empty and re-offering every window"
      - "two stores, two lifetimes → conforms: the consent is a committed answer (`project-preferences.md`), and the sent record is per-clone, gitignored state beside the evidence store"
      - "backlog_service_repo selects the authoritative backlog store → inapplicable, because no backlog read or write changes"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; persisted data schema-versioned → conforms: the payload carries `schema`, and the sent record carries its own version"
      - "exit codes are the contract → conforms: 0 preview or sent; 1 bad arguments or an unreadable store; 2 a refusal (consent, digest, no collector)"
      - "additive-first evolution → conforms: a new subcommand and a new preference row"
  - artifact: observability-strategy
    dispositions:
      - "terminal signals use the severity-prefix vocabulary and the stdout/stderr split → conforms: refusals are `BLOCKED:` and failures `WARNING:` on stderr; the preview is on stdout"
      - "the ledger has one writer → inapplicable, because nothing is written to the ledger"
      - "emitted text names no internal identifier → conforms"
---

# Build Plan: telemetry contribution, wave 2 (#949)

## Problem

Wave 1's `prawduct-hook stats` reports cost and yield per plugin version, but only for one clone.
Framework decisions still rest on whichever products the owner can read by hand. The owner's goals
(audit § Owner goals): collect telemetry to improve prawduct, and know nothing about the
contributor.

## Success

- `prawduct-hook contribute` previews the exact bytes of every pending report and sends nothing.
- `contribute --send` sends them to the pinned collector, but only when the product's own
  `project-preferences.md` says `ask` (with the previewed digest) or `always`. Anything else
  refuses.
- Every report passes the committed allowlist before it can leave. No window is sent twice, and
  below-floor metrics are absent.

## Out of scope

- The collector and its ingestion: #950, its own plan.
- Oblivious HTTP, DAP/Prio and GitHub-issue transport (audit § Not chosen).
- Escapes (B5): #951.
- Any send from a hook. A hook only advises; the agent or the person runs the send.

## Requirements Confidence: Medium

Goals, content rules and consent are owner-decided (audit; #950 comment 2026-10-03). These are
inferred:

- [ASSUMPTION: a report's window is one closed ISO week × one plugin `major.minor` × dev flag. Weeks
  give data on a release while it is current; the cost is more below-floor drops for quiet
  products than per-version windows would have | MED impact | owner can override]
- [ASSUMPTION: only the 8 most recent closed weeks are offered, so a first opt-in previews at most
  a few reports rather than months of history; older weeks are never sent | LOW impact | owner can
  override]
- [ASSUMPTION: at-most-once delivery: a window is recorded as sent before the POST, and the record
  is withdrawn only when the request provably never reached the collector (refused connection,
  DNS failure). A timeout loses that window rather than risk a duplicate | LOW impact | owner can
  override]
- [ASSUMPTION: `always` means no per-report preview. The briefing tells the agent that windows are
  pending, and the agent runs the send; no hook opens a socket | MED impact | owner can override]
- [ASSUMPTION: the floor is 5 for every denominator | LOW impact | owner can override]
- [ASSUMPTION: `HTTPS_PROXY` is honoured as `urllib` honours it, which means HTTP CONNECT proxies.
  Tor needs an HTTP front (or `torsocks`), because the stdlib has no SOCKS | LOW impact | owner can
  override]

What would raise it: the owner's read of the week-window and `always` assumptions.

## Chunks

### Chunk 01: allowlist schema, payload builder, preview

new `plugin/lib/contribution_schema.json` is the one home of the allowlist: every field's type (an
integer, a stepped number, or an enum), its step and bounds, and its floor denominator. new
`plugin/lib/contribution.py` builds one payload per pending window from `stats.aggregate`,
coarsens it, drops below-floor fields and validates the result. `prawduct-hook contribute`
(preview only) prints each payload's exact bytes and one digest over all of them.

The questions the payload must answer (the data-model lock-in rule): per plugin version, across
products: rounds per scope (C1); measured review time (C2); empty verify rounds (C3); re-reviews
(C4); stops blocked, loops and guard refusals per session (C5, C6); findings raised per review,
acted-on rate per severity, and blocking and warning fixed per scope (B1–B3); and the red suite-run
share (B4).

Done when:
1. A payload with a key outside the schema, a non-numeric non-enum value, an off-step number or an
   out-of-range number is refused by the validator. Each case has a test.
2. No payload field can carry text: the schema admits only integers, stepped numbers and enums,
   and a test walks the schema to pin that.
3. A metric whose denominator is under its floor is absent from the payload (tested at 4 and 5).
4. Volumes are log bands, rates and medians are stepped, and the version is `major`/`minor`
   integers plus a `dev` flag. A `-dev.N` build never leaks its `N`.
5. Only closed weeks are offered, at most 8 of them. Windows in the sent record are skipped.
6. `contribute` prints the exact bytes `--send` would send and a digest over them, and it opens no
   socket. A test pins that it never reaches the transport seam.

### Chunk 02: consent, send, the record, and the norm amendments

The `Stats contribution` preference row is read fail-closed: absent, empty, misspelled or
unreadable all mean `never`. `contribute --send [--approve sha256:…]` checks consent, then the
digest under `ask`, then that a collector endpoint is pinned. It writes the sent record, POSTs
each report through `urllib` and reports the outcome. The endpoint constant stays empty until #950
deploys, and an empty endpoint refuses. The architecture and security-model Direction entries are
amended to admit the third surface, citing the audit's owner line, and `project-state.yaml`'s
egress record gains the site. `templates/project-preferences.md` ships the row reading `never`
(moved here from chunk 03, because the consent tests pin the shipped default).

Done when:
1. Under `never`, or under any unreadable or unrecognised row, `--send` refuses before the
   transport seam, and nothing is recorded.
2. Under `ask`, a send whose `--approve` does not match a re-render of the bytes refuses.
3. A window already recorded is never sent again, including after a send that timed out.
4. An empty endpoint refuses with a message naming #950.
5. The architecture and security-model amendments each carry a `[DECISION: …]` citing the audit's
   owner line, and the egress record lists the new site.
6. The shipped template row reads `never` (tested).

Also carries the fixes for the cumulative review `rev-20261003T135311Z-94eefd47`:
- R-1: transfer grants are counted apart from guard refusals, in `stats` and in the report;
- R-8: `stats` exports `answered`, and the report's floor reads it;
- R-6: a week is offered only once it has settled for `SETTLE_DAYS`, and the docstring states the
  week edge's costs;
- R-9 and R-14: the docstring and the schema's `about` no longer claim that a collector exists, and
  both name the band type.

### Chunk 03: the opt-in surfaces

The briefing says when windows
are pending, but only under `ask` or `always` and only with an endpoint pinned. Under `never` it
stays silent. `/prawduct:janitor` offers the opt-in as a question to the person and never writes
the row without their answer. `docs/governance-telemetry.md` documents the payload and the
command, and the CHANGELOG gains an entry.

**Type:** cumulative-final

Done when:
1. With the row absent, nothing prompts outside the janitor offer.
2. The briefing line appears only under `ask` or `always` with windows pending and an endpoint
   pinned (each arm tested).
3. The janitor skill's offer is phrased as a question and says the row is the person's to write.

## Verification strategy

Run `contribute` against this clone's real evidence store and read the preview as a contributor
would: is every byte explainable, and could anything identify the product? Run `--send` against a
local `http.server` stub, once with a set `HTTPS_PROXY`, to see the bytes that arrive.

## Status

- [x] Chunk 01: allowlist schema, payload builder, preview
- [x] Chunk 02: consent, send, the record, and the norm amendments
- [ ] Chunk 03: the opt-in surfaces
