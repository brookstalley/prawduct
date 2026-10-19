# Issue #989 — telemetry: measure governance tax as wall clock and tokens per change: Requirements

`status: draft (rev 2) · stage: requirements · area: governance/telemetry · added: 2026-10-10 · revised: 2026-10-15 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/989`

Carried from #985 (deleted and refiled to scrub edit history); the first draft lived only on session branch
`claude/youthful-galileo-t56x8g`. Rev 2 re-grounds it on `origin/develop` at 3ba0337b, where `stats` now ships,
and closes the questions that shipping answers.

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

Re-derive these rather than trusting them; each names its command.

- **`prawduct-hook stats` exists** (`plugin/lib/stats.py`, `cmd_stats` in `plugin/bin/prawduct-hook`;
  definitions' one home is `plugin/docs/governance-telemetry.md` § `prawduct-hook stats`). It reads the
  clone-shared **evidence store**, buckets every number by plugin `major.minor` taken from each fact's
  `actor.plugin`, and has `--json` with `REPORT_SCHEMA_VERSION`. (`grep -n "def stats_cmd" plugin/lib/stats.py`)
- Its **cost** side already has *review time* (measured `dispatched_at`→`ts` only, self-estimates counted
  apart) and *rounds per scope*. That is the audit's C2. It has **no per-change wall clock and no tokens**.
- **No change-level record exists.** The ledger envelope is `{schema_version, event, ts, duration_seconds,
  project, scope, chunk, actor, git}`; there is no merge event and no change-start event
  (`plugin/lib/ledger.py` docstring: `build.chunk` / `plan.authored` accommodated, not built).
- **Nothing reads Claude Code usage.** `grep -rn ccusage plugin` finds no consumer.
- `review-stats` (`lib/telemetry.py`) is per-worktree and ledger-based; it is not the host for this metric.
- Evidence: `.prawduct/artifacts/governance-roi-study-2026-10.md` (result 5, Recommendations) and
  `.prawduct/artifacts/roi-audit-2026-10-02.md` are now on `develop`.
- Unmerged prior art: the first draft above and #951's draft (`claude/youthful-galileo-ywq1py`), whose
  open question 3 (plugin version per record) is the same gap this document closes below.

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
are absent, not zero, for an ungoverned repo. Plugin version for a change is read from the `actor.plugin` of the change's own review facts in the evidence
store (the mechanism `stats` already uses); a change with no review fact is bucketed `unknown`, never
guessed from a release tag. This closes the old open question on ledger lines lacking a version: the
evidence store, not the ledger, is the source.

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

## Decisions this revision makes

- **Name.** `stats` already owns "review time" as the audit's C2. The new metric is called **change cost**
  (wall clock + tokens per merged change) in output and docs; "C2" is not reused. Owner may veto.
- **Host.** It joins `prawduct-hook stats` as a new section and bumps `REPORT_SCHEMA_VERSION` per the
  existing `--json` contract; no new subcommand. Governed-only joins use the evidence store; git/GitHub
  fields do not need it (R4).
- **Plugin version.** From review facts' `actor.plugin` (R4).

## Open questions for design

1. **Token source.** `ccusage` is external. Options: shell out to it when present; read Claude Code's
   local transcript usage directly; accept a user-supplied usage file. Cloud sessions may not persist
   transcripts; those changes are `unattributed` and the report must make the resulting bias legible.
2. **`started_at` for squash-merged PRs.** Branch commit times live in the PR's commit list, not on the
   squash commit, so the git-only R4 path depends on the GitHub API; decide whether direct landings use
   first-parent time deltas instead.
3. **Idle time.** Whether to report an active-time variant (gaps over N minutes excluded) beside raw wall
   clock, given weekends would otherwise dominate p90.
4. **Cross-repo comparison.** `stats` reads one clone's evidence store; running it on an ungoverned repo
   needs a git-only entry path. Decide whether that is a flag on `stats` or part of `aggregate-stats`.
5. **Wave-2 payload.** Whether change-cost aggregates join the contribution allowlist, which needs its own
   privacy review (token counts and timestamps per change are more identifying than review counts).
