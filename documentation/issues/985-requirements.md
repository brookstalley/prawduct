# Issue #985 — telemetry: measure governance tax as wall clock and tokens per change: Requirements

`status: draft · stage: requirements · area: governance/telemetry · added: 2026-10-10 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/985`

Related: #262 (cross-product review cost, shipped), #291 and #941 (review-stats), #951 (escapes, B5 —
the quality side this sits beside), #693 (`/clear` rebuild cost and per-turn context growth — adjacent
token measurement).

## Problem

The governance ROI study (2026-10) found governed and ungoverned repos merge source at about the same
rate (pooled 4.4 vs 4.7 kLOC per active day), yet governed work feels slow. Its conclusion: the cost is
in wall clock per change, owner attention and tokens, and none of those were measured. Today the tax
side of governance ROI is an impression, so no mechanism can be retired or re-priced on evidence.

What exists: `review-stats` (`plugin/lib/telemetry.py`) aggregates `review.*` events from the
governance ledger (`.prawduct/.governance-ledger.jsonl`) — review duration (measured vs self-reported),
yield, per role/model/mode/stage/scope. It answers "what does a *review* cost". It cannot answer "what
does a *change* cost", because no record joins a change's start, its reviews and its merge, and no
record carries tokens at all.

## Grounding facts

Verified against `origin/develop` (2026-10-10):

- The ledger's envelope is `{schema_version, event, ts, duration_seconds, project, scope, chunk, actor,
  git: {head, base}}`; emitted kinds are `review.critic`, `review.pr`, `learning.written`,
  `learning.fired`. `build.chunk` / `plan.authored` are accommodated by the envelope and deliberately not
  built (`plugin/lib/ledger.py` docstring). **There is no merge event and no change-start event.**
- `review.*` events carry `dispatched_at` when a dispatch marker was found, so review wall clock is
  already measurable per review; per change it must be summed or spanned by `scope`/`git.head`.
- The only stats subcommand is `prawduct-hook review-stats [--json] [--since] [--until]`
  (`plugin/bin/prawduct-hook:9177`). The issue and the ROI audit say `prawduct-hook stats`; **no `stats`
  command exists on `develop`**. The audit's phase-1 build may add it; this document treats "the stats
  command" as whichever entry point wave 1 ships, and does not create a second one.
- The audit's own **C2 is "measured review time per work unit"** (`dispatched_at`→`ts` only). The issue
  uses "C2" for a broader quantity (wall clock + tokens per merged change). These are different
  metrics under one label; see Open question 1.
- Nothing in the repo reads Claude Code session usage; `ccusage` is named only in the issue.
- `.prawduct/artifacts/governance-roi-study-2026-10.md` (the issue's evidence) is not on `develop`; the
  study's claims below are taken from the issue body.

## Users and the decision they make

The single user is the framework owner (and, via the cross-project aggregator, owners of governed
products), deciding whether a governance mechanism earns its cost. The decision this metric feeds is
retire / re-price / keep, so the output must be **comparable** (governed vs ungoverned; version vs
version) before it must be precise.

## Requirements

### R1 — A change is a unit with a start and an end

A **change** is one landing: a merged PR, or a direct landing on the default branch when no PR is used.
Each carries:

- `started_at`: the earlier of first commit time on the change's commits and plan start (when a build
  plan scope exists). Source-of-truth precedence is fixed so two readers agree.
- `merged_at`: merge time (PR merge, or landing commit time for a direct landing).
- `wall_clock_s` = `merged_at − started_at`, always reported **with** the span's endpoints' provenance
  (git commit time vs plan start) so an idle-weekend gap is visible and not silently averaged in.
- `review_wall_clock_s` and `review_rounds`: summed from the change's `review.*` events (measured
  durations only; self-reported kept in a separate population, as `review-stats` already does).

A change with no recoverable start or end is counted as **unmeasured**, never dropped and never zero.

### R2 — Tokens are attributed to a change, with the attribution method stated

Each change carries `tokens` (input, output, cache read/write, as the usage source reports them) and
`tokens_attribution`, one of `exact` (session lies wholly inside the change), `apportioned` (session
spans several changes; share by the stated rule) or `unattributed`.

Attribution rule for a session spanning several changes (the issue's open requirement) — requirement,
not design: usage is split **by time window** between the change's `started_at`/`merged_at` and the
session's turn timestamps; overlap between concurrent changes is apportioned by turn count and the
result is labelled `apportioned`. A report must show the `exact`/`apportioned`/`unattributed` mix beside
every token figure, so a reader can discount accordingly. Token numbers are never presented without
that mix.

### R3 — Reporting

The stats entry point reports, per plugin version and per repo:

- median and p90 `wall_clock_s` and `tokens` per merged change;
- the unmeasured and unattributed counts;
- review share of wall clock (`review_wall_clock_s / wall_clock_s`) as a derived column, since the study's
  hypothesis is that governed work is slow *because of* review and gates.

Output has a `--json` form with a stated schema version, following `review-stats`'s contract (key
changes bump the version; prose home `docs/governance-telemetry.md`).

### R4 — Comparable across a governed and an ungoverned repo

The ungoverned repo has no ledger and no plugin version. Therefore the **git-derived fields (R1 minus
review fields) must be computable from the repository and GitHub alone**, so the same report runs on a
repo that never installed prawduct. Governed-only fields (review wall clock, rounds, plugin version)
are absent, not zero, for an ungoverned repo. Plugin version for a change is the version in force at
merge (see Open question 3).

### R5 — Visible cost, no extra governance

Collecting this must not add per-change author steps or hook latency to a session (it is Principle 9
applied to the framework). Collection is pulled at report time from git, GitHub and the usage source;
nothing new is written in the Stop hook path. The one possible producer — a `change.landed` ledger
event — is accepted only if a named consumer reads it in the same change (learnings: no produced-and-
never-consumed channel); otherwise it is not built.

## Acceptance (maps to the issue)

- Each merged change in the window yields a record with `wall_clock_s`, `tokens` and their provenance,
  or an explicit `unmeasured`/`unattributed` entry. (R1, R2)
- The stats command prints median and p90 wall clock and tokens per merged change by plugin version.
  (R3)
- Running it against a governed and an ungoverned repo produces the same shape, with governed-only
  fields absent for the latter. (R4)
- A test feeds it a session spanning two changes and asserts the tokens land `apportioned` and sum to
  the session total — a case the instrument must catch, not only the happy path.

## Out of scope

- Throughput in kLOC (the study shows it does not separate the groups).
- Owner attention, unless a cheap proxy appears — candidate proxy to evaluate in design: count of
  owner-authored comments/review actions per change, from GitHub.
- Dollar cost (token counts only; pricing changes under the metric).
- Retiring any mechanism on the strength of the first report — this issue produces the measurement.

## Open questions for design

1. **Which "C2".** The audit's C2 (measured review time per unit) and the issue's C2 (change wall clock
   plus tokens) share a label. Decide whether the stats output keeps them as two named metrics, and
   rename one before both ship.
2. **Token source.** `ccusage` is external. Options: shell out to it when present; read Claude Code's
   local transcript usage directly; accept a user-supplied usage file. Needs a decision on what is
   available in cloud sessions, where local transcripts may not persist — those changes would be
   `unattributed`, and the report must make the resulting bias legible.
3. **Plugin version per change.** Ledger lines carry no plugin version (the gap that descoped B6 in
   #948, per #951's discussion); decide whether to stamp it on the envelope, or infer it from the release
   tag in force at `merged_at`.
4. **`started_at` for squash-merged PRs.** Branch commit times survive in the PR's commit list, not on the
   squash commit; the source must be the PR, which makes the git-only R4 path a GitHub-API dependency.
   Decide whether direct-to-default landings use first-parent time deltas instead.
5. **Idle time.** Whether to report an active-time variant (gaps over N minutes excluded) beside raw
   wall clock, given weekends would otherwise dominate p90.
6. **Where it ships relative to wave 1.** Which entry point and schema version it joins, given `stats`
   does not yet exist on `develop`.
