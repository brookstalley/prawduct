# Issue #262 — Cross-project review-telemetry aggregation: Requirements

`status: draft · stage: requirements · area: governance/telemetry · added: 2026-08-03 · source:
scheduled backlog session · issue: https://github.com/brookstalley/prawduct/issues/262`

Related: TEL-7A4X (this item's id alias), `plugin/docs/governance-telemetry.md` (the per-project
ledger and `review-stats --json` contract this item builds on), CLAUDE.md "Reviewing product
feedback" route (the existing local-scan pattern for `learnings.md` this item generalizes).

## Problem

Proportionality tuning — which products' chunk reviews yield nothing, where escalation to a
deeper reviewer tier actually pays off — is decided per-project today, because no view aggregates
`review-stats --json` output across the products prawduct governs. The `--json` contract
(`schema_version` / `project` / `generated_at` at the top level) has existed since v2.1.0
specifically as the integration seam for this item (`plugin/lib/telemetry.py:212-330`), but nothing
consumes it across repos yet.

The source issue named three open requirements questions before code should start: where the
aggregate view lives, product opt-in/privacy posture, and whether differing plugin versions skew
comparability. This document resolves them.

## Grounding facts

- The per-project ledger (`.prawduct/.governance-ledger.jsonl`) is **gitignored, local, per-clone
  state** (`.gitignore:6`, `plugin/docs/governance-telemetry.md` "The event ledger"). Nothing in it
  is committed or pushed anywhere today.
- There is **no committed registry of "known product directories."** The CLAUDE.md "Reviewing
  product feedback" route instructs a scan for `.prawduct/learnings.md` across "known product
  directories," but that knowledge is tacit — carried by whoever is running the session, not
  recorded in any file this repo or any product repo owns.
- Ledger events (`plugin/lib/ledger.py`) carry `schema_version`, `event`, `ts`,
  `duration_seconds`, `project`, `scope`, `chunk`, `actor {role, model}`, `git {head, base}`, and
  the nested `review` payload — **no plugin-version field**. `evidence.py` records a `plugin`
  version (`_plugin_version()`, `plugin/lib/evidence.py:88`) for a different artifact
  (`.critic-findings.json`); that field does not exist on ledger lines, so nothing today lets a
  reader tell which plugin version produced a given `review-stats` report.

These three facts are why the source issue's three questions were genuinely open — they are not
solvable by inspection of what already exists; each needs a decision.

## Decisions

**1. Where the aggregate view lives.** It is a `prawduct-hook` subcommand plus a
`/prawduct:janitor` section, **not** a new committed document and **not** a standalone skill. A
committed document would imply the aggregate is a durable artifact the framework tracks, but its
inputs are local, gitignored, and only as fresh as the last time each product's ledger was written
— it is a report, generated on demand, the same way `review-stats` itself is a report and not a
file. Homing it under `/prawduct:janitor` (which already owns the "reviewing product feedback"
cross-repo scan in CLAUDE.md) reuses an existing operator habit — janitor sessions are when an
operator already has multiple product checkouts in mind — rather than adding a fourth place to
remember to look.

**2. Product opt-in / privacy posture.** No auto-discovery of arbitrary filesystem paths. The
aggregator only ever reads product directories the operator names **explicitly**, at invocation
time — CLI positional arguments (paths) or a `--from-file <path>` list, mirroring the "bring your
own list" posture `test-reference-verify --merge-into` already uses for a related problem
(COV-4M2J's escape hatch). This resolves the privacy question directly: since the ledger never
leaves the machine anyway (it is gitignored, per-clone state — see Grounding facts), the only
privacy-relevant act is the *aggregator itself reading it*, and requiring an explicit, per-run list
means a product is only ever included because the person running the command named it, never
because it happened to sit in a sibling directory. No portfolio-composition list is committed to
this repo or to any product repo — an owner's set of governed products is not itself a fact
prawduct records anywhere.

**3. Plugin-version skew.** Ledger events must gain a `plugin` field on write (mirroring
`evidence.py`'s existing `_plugin_version()` — do not invent a second version-detection
mechanism). This is a **prerequisite**, not a nice-to-have: without it, the aggregator has no way
to even detect skew, let alone report it, and a cross-project comparison that silently blends
review data from different plugin versions is worse than no aggregation, because it looks
authoritative. The aggregator surfaces the plugin version(s) present per project in its output —
it does not block or refuse to aggregate across versions (that is the operator's judgment call,
same as the existing model-family fold is informational, not exclusionary) — but a project whose
ledger predates this field reports its version as `null`, honestly, not inferred.

## Requirements

MUST unless marked SHOULD.

- **TEL1** `plugin/lib/ledger.py`'s event envelope gains a `plugin` field (the running plugin
  version string, or `null` when undeterminable), written the same way `evidence.py`'s
  `_plugin_version()` already resolves it. This is additive to the existing envelope
  (`schema_version`, `event`, `ts`, `duration_seconds`, `project`, `scope`, `chunk`, `actor`,
  `git`, `review`) — existing ledger lines without the field remain valid; readers treat a missing
  `plugin` key as `null`, not as a parse error.
- **TEL2** `prawduct-hook review-stats --json`'s top-level output surfaces the plugin version(s)
  seen across the aggregated events for that project (e.g. a `plugin_versions` list), so a
  single-project report already shows whether its own history spans multiple plugin versions
  before any cross-project step is taken.
- **TEL3** A new `prawduct-hook aggregate-review-stats <path> [<path> ...] | --from-file <list>`
  command reads each named path's `.prawduct/.governance-ledger.jsonl` (erroring per-path, not
  aborting the whole run, on a missing or unreadable ledger — same "skip with counts, never
  silent" posture `review-stats` itself uses today), and renders a cross-project view: review
  wall-clock and actionable-finding rate by mode, model, and project. It never discovers paths on
  its own — every project in the output was named by the operator at invocation.
- **TEL4** The command's output surfaces, per project, the plugin version(s) present in that
  project's contributing events (from TEL1/TEL2) — never silently blended across versions into a
  single unlabeled number.
- **TEL5** No new file is committed to this repo, or expected to be committed to any product repo,
  to support TEL3 — the path list is supplied at invocation (CLI args or `--from-file`), consistent
  with Decision 2's opt-in posture. Whatever wraps this in `/prawduct:janitor` (design-stage detail)
  passes the operator-supplied list through; it does not maintain its own registry either.
- **TEL6** `aggregate-review-stats` supports `--json`, with a stable, versioned top-level shape
  (`schema_version` at minimum), matching the precedent `review-stats --json` already set as "the
  integration point" — this is the seam a future janitor UI or further tooling builds on, so it
  must not be a print-only human report from the start.

## Acceptance

- [ ] A cross-project view exists and is evidence-driven (the source issue's original acceptance
      criterion).
- [ ] The view never reads a product's ledger unless that product's path was named explicitly at
      invocation.
- [ ] The view distinguishes projects on different plugin versions rather than blending their
      numbers unlabeled.
- [ ] A project whose ledger predates the `plugin` field degrades to `null`/unknown, not a crash or
      a guessed version.

## Scope-out (this item)

- The exact `/prawduct:janitor` UX for invoking the aggregator (prompt copy, how the operator
  supplies the path list interactively) — design-stage detail.
- Any policy about *what to do* when plugin versions skew (e.g. whether janitor should recommend
  upgrading a lagging product before trusting a comparison) — TEL4 requires the skew to be visible;
  deciding how the operator or the skill should react to it is out of scope here.
- Backfilling a `plugin` version onto ledger lines already written before TEL1 ships — not
  possible (the information was never captured) and not required; TEL1 only governs new writes.
- Any persistence of aggregated cross-project results (a saved report, a trend over time) — TEL3/
  TEL6 describe an on-demand command, not a new durable store.

## Evidence / references

- `plugin/docs/governance-telemetry.md` — the ledger envelope, `review-stats --json` contract, and
  the explicit statement that this contract "is the seam cross-project aggregation (TEL-7A4X)
  builds on."
- `plugin/lib/telemetry.py:212-330` — `aggregate_review_stats`, `review_stats`,
  `REPORT_SCHEMA_VERSION` — the existing per-project aggregation this item extends across
  projects rather than reimplementing.
- `plugin/lib/ledger.py` — the event envelope TEL1 extends; confirmed no `plugin` field exists
  today.
- `plugin/lib/evidence.py:88` — `_plugin_version()`, the existing version-resolution mechanism
  TEL1 reuses rather than inventing a second one.
- `.gitignore:6` — confirms `.governance-ledger.jsonl` is gitignored, grounding Decision 2's
  privacy posture.
- `CLAUDE.md` "Reviewing product feedback" route — the existing "scan known product directories"
  pattern this item's aggregator generalizes, and the reason Decision 1 homes the new surface
  under `/prawduct:janitor` rather than inventing a fourth place operators need to remember.
