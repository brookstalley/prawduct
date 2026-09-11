# Issue #623 — Backlog: Add `gh` Auth Preflight to Doctor for the Issues Backend: Requirements

`status: draft · stage: requirements · area: backlog · added: 2026-08-12 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/623`

Related: sibling #622 (migration runbook — same discodon gap-7 evidence, a different fix
surface).

## Problem

Post-cutover (`backlog_service_repo` set), a contributor whose `gh` is unauthenticated cannot
tell "GitHub is down" from "you never ran `gh auth login`" — and only the second is theirs to
fix. `/prawduct:doctor` has no `gh` preflight anywhere: its only `gh`-touching health check
(Health Check #12, label reconcile) explicitly says "if `gh` is unavailable, report the repair
is pending and move on," which coalesces three distinct causes — the binary missing, the
identity unauthenticated, the identity authenticated but under-scoped for this repo — into one
generic non-finding.

## Grounding facts

Re-verified against the current tree (2026-08-12):

- **The adapter already distinguishes "missing binary" from "auth failure" at the transport
  layer, but nothing above it reads that distinction.** `GhTransport._spawn`
  (`plugin/lib/backlog/transport.py:854-877`) catches `FileNotFoundError` and raises
  `TransportError("unavailable", "the 'gh' CLI is required but was not found on PATH", …)` —
  already a *named* condition, not a generic failure. `_map_failure` (`:891-935`) maps `gh`'s own
  exit 4 and HTTP 401/403 to `TransportError("auth", …)` (`:904-906,923-924`). These two codes
  reach `core.reconcile_labels` (`plugin/lib/backlog/core.py:1127-1151`) today via
  `from_transport_error(exc)` on the `except TransportError` branch (`:1138-1139`) — the `code`
  field is already in the JSON envelope `reconcile-labels` returns. Doctor's Health Check #12
  (`plugin/skills/doctor/SKILL.md:56`) just never reads it: its instruction is "if `gh` is
  unavailable, report the repair is pending and move on" for any failure, full stop.
- **No `TransportError` code distinguishes "authenticated but insufficient scope" from plain
  "unauthenticated."** `RETRYABLE_DEFAULTS` (`transport.py:73-83`) enumerates `validation`,
  `not_found`, `ambiguous_id`, `alias_collision`, `conflict`, `auth`, `unavailable`,
  `rate_limited`, `unsupported` — no `scope` code exists, and `_map_failure` folds every 401/403
  into `auth` regardless of whether the token is absent, expired, or merely missing a required
  scope (`:923-924`, `"authentication" in scrubbed or "must authenticate" in scrubbed`, a
  substring check that does not look for GitHub's distinct "missing required scopes" wording).
  Scope is a real GitHub concept: on a live request the API returns it via response headers
  (`X-OAuth-Scopes` granted, `X-Accepted-OAuth-Scopes` required) — but only for **classic**
  personal access tokens and OAuth apps. A **fine-grained PAT**, a **GitHub App installation
  token**, or an **Actions `GITHUB_TOKEN`** carry no OAuth scope headers at all; GitHub's own docs
  describe fine-grained-PAT permissions as a separate, non-header-visible model. Any scope check
  built on those headers is therefore inherently partial, not universal — it has a real answer for
  one auth style and none for the others.
- **`gh auth status` is the standard non-mutating gh diagnostic for exactly "installed,
  authenticated, and what scopes."** It exits 0 when logged in to at least one host (non-zero
  otherwise) and, for a classic-token identity, its human output includes a `Token scopes:` line.
  It performs no write and no repo-scoped API call — it is the natural preflight primitive, not a
  live mutating request used as a probe. (No `gh` binary is present in this execution
  environment to re-verify the exact output shape by running it directly; the exit-code and
  scopes-line behavior above is gh's long-documented, stable CLI contract, not new-in-this-doc
  guesswork — flagged here as inferred-from-documentation rather than freshly executed.)
- **`build_env()` passes the ambient environment through unchanged** (`transport.py:232-244`):
  it only sets `GH_PROMPT_DISABLED`, `GH_NO_UPDATE_NOTIFIER`, `GH_PAGER`/`PAGER`, and `CLICOLOR`
  on top of `dict(os.environ)`. `gh` itself honors `GH_TOKEN`/`GITHUB_TOKEN` when set, ahead of
  any `gh auth login` keyring state. That means an automated or CI session (this very scheduled
  session included) can be "authenticated" purely via an env var with no interactive login ever
  having happened — so a preflight that always tells the user to run `gh auth login` is not
  actionable in that context; the fix there is checking or rotating the token the env var points
  at.
- **The skip rule this item must reuse already exists and is named in the issue itself.**
  `backlog_service_repo` is read via `core.read_str_yaml_key` (used identically at
  `plugin/lib/briefing.py:859` and `plugin/bin/prawduct-hook:5802`) — presence, not truthiness,
  is what post-cutover checks gate on (`plugin/bin/prawduct-hook:5794-5802`,
  `_is_service_backed`-equivalent). Health Check #12's own skip rule
  (`plugin/skills/doctor/SKILL.md:56`, "Unset → skip … this is healthy, not a finding") is the
  literal precedent the issue asks this preflight to mirror.
- **The closest existing precedent for "a small, read-only diagnostic module feeding one doctor
  Health Check line, with no `--apply`" is `learnings_obligation.py`, not `norm_index_scaffold.py`
  (which has one).** `learnings_obligation.check()` (`plugin/lib/learnings_obligation.py:66-73`)
  reports one of a closed set of named statuses (`ok`, `missing`, `misplaced`, `absent`,
  `unreadable`) and is wired into `prawduct-hook learnings-obligation` for doctor Health Check #13
  to relay. A `gh` preflight has no in-repo file to insert into on `--apply` — the remedy is
  external (`gh auth login`, a token refresh) — so it is closer in shape to a status-only reader
  than to a repair command.
- **No implementation exists today.** Nothing in `plugin/` currently calls `gh auth status`, and
  no `prawduct-hook` subcommand mentions "preflight" or "scope" in this sense — this is greenfield
  wiring onto existing primitives (`_spawn`'s FileNotFoundError handling, `build_env()`), not a
  rework of the adapter's live-operation error path.

## Decisions

**1. The preflight is a new, independent read-only check — it does not fold into
`reconcile_labels`'s error path.** Doctor needs a determinate answer ("nothing to report") on a
healthy repo, and needs to answer the question even when the operator isn't currently running
`reconcile-labels` at all (e.g. Health Check runs standalone). Piggybacking on
`reconcile_labels`'s `TransportError` handling would only ever fire when that specific repair is
invoked, and would still need the scope question answered separately (Grounding facts: no
existing code distinguishes it). A dedicated `prawduct-hook` subcommand, mirroring
`learnings_obligation`'s shape (small `plugin/lib/` module → one subcommand → one doctor Health
Check line), keeps the check runnable and testable on its own.

**2. The primitive is `gh auth status`, not a live repo-scoped API call used as a probe.** It is
gh's own purpose-built, non-mutating diagnostic, already answers "installed" (via the same
`FileNotFoundError` → PATH-missing path `_spawn` already implements — reused, not duplicated) and
"authenticated" (exit code) directly, and needs no `--repo`/`owner/repo` argument to answer those
two of the three conditions. It runs through the same `build_env()`/non-interactive contract
every other `gh` call in the adapter already uses, so it cannot hang on a missing TTY.

**3. Scope-checking is explicitly best-effort and must say so, not silently degrade to a false
pass.** For a classic-PAT or OAuth-app identity, scope is checkable (the `Token scopes:` line, or
equivalently the `X-OAuth-Scopes` header on a cheap authenticated request — `transport.py` already
has header-parsing precedent in `_parse_head`, `:134-153`, for a different purpose, reusable
shape). For a fine-grained PAT, GitHub App token, or `GITHUB_TOKEN`, no such signal exists
(Grounding facts) — the check reports **"scope: unchecked,"** never a fabricated pass, mirroring
the framework's existing "a missing producer reports unchecked, never passed" posture used
elsewhere for this exact reason (change-evidence sockets, `gates.py`'s `changes_unjudged` split).
A repo/token this check cannot judge is a degraded finding, not a silent healthy.

**4. The unauthenticated remedy branches on how `gh` is authenticating.** When `GH_TOKEN` or
`GITHUB_TOKEN` is set in the environment (Grounding facts: `build_env()` passes it through), the
remedy names checking/rotating that token — telling an automated session to interactively `gh
auth login` is not actionable there. When neither is set, the remedy is `gh auth login`. This is
a wording branch on an environment read, not a new authentication mechanism.

**5. The gate is `backlog_service_repo` presence, read exactly as Health Check #12 already reads
it** (`read_str_yaml_key`) **— no new skip condition, no second detector.** A markdown-backend
repo (the scalar unset) sees nothing new from this check, same as it sees nothing from #12 today.

**6. This item extends Health Check #12's own gh-touching guidance, not the adapter's error
mapping or `refresh_counts`.** Both are already correct per the issue's own "Not the bug it looks
like" analysis (Grounding facts, `refresh_counts` at `plugin/lib/backlog/query.py:395-396`
preserves the last snapshot on failure rather than clobbering it) — this item is diagnosability
at the doctor layer only.

## Requirements

MUST unless marked SHOULD.

- **GHA-1** A new read-only `prawduct-hook` subcommand runs a `gh` auth preflight and reports
  three conditions as **distinct**, named findings: `gh` missing (not on PATH), `gh` installed
  but unauthenticated, and `gh` authenticated but insufficient-or-unverifiable scope for the
  backlog repo (Decision 1).
- **GHA-2** The check is a no-op — produces no new doctor report line — when
  `backlog_service_repo` is unset in `project-state.yaml`, read via the existing
  `read_str_yaml_key` helper, mirroring Health Check #12's own skip rule exactly (Decision 5).
- **GHA-3** The "missing" and "unauthenticated" conditions are detected via `gh auth status`
  (missing binary reuses `_spawn`'s existing `FileNotFoundError` → PATH-missing handling rather
  than a second detector) (Decision 2).
- **GHA-4** The scope condition is checked on a best-effort basis for auth methods that expose a
  scope signal (classic PAT / OAuth app); for auth methods that expose none (fine-grained PAT,
  GitHub App token, `GITHUB_TOKEN`), the finding is explicitly **"scope: unchecked"** — never
  coalesced with, or reported as, a passing scope check (Decision 3).
- **GHA-5** Each finding names a concrete remedy: missing → install/PATH guidance; unauthenticated
  → `gh auth login` when no `GH_TOKEN`/`GITHUB_TOKEN` is set in the environment, or
  check/rotate-the-token guidance when one is (Decision 4); insufficient scope → the specific
  scope needed (`repo`, or `public_repo` for a public repo) and the command to grant it (`gh auth
  refresh -h github.com -s repo`).
- **GHA-6** A repo with `backlog_service_repo` set, `gh` installed, authenticated, and
  (where checkable) correctly scoped produces **no new doctor output** — surface-by-exception,
  consistent with every other Health Check.
- **GHA-7** The preflight performs no write (no label creation, no issue mutation) and runs
  independent of whether `reconcile-labels` is separately invoked — it does not require Health
  Check #12's repair step to fire in order to report.
- **GHA-8 (SHOULD)** The preflight reuses `build_env()` for its `gh` invocation rather than
  constructing a second non-interactive environment, so its non-prompting/non-paging contract
  cannot drift from every other adapter `gh` call.

## Acceptance

- [ ] doctor reports `gh` missing / unauthenticated / insufficient-or-unverifiable scope as three
      distinct findings, not one generic "gh unavailable" line.
- [ ] Each finding names a concrete, actionable remedy — the unauthenticated remedy correctly
      distinguishes an interactive session (`gh auth login`) from a token-env-var session
      (check/rotate the token).
- [ ] The check is a no-op when `backlog_service_repo` is unset.
- [ ] A healthy, authenticated, correctly-scoped repo (or one where scope is inherently
      unverifiable for its auth method, and says so) reports nothing new beyond the explicit
      "scope: unchecked" note where applicable.
- [ ] The check performs no write and does not require `reconcile-labels` to run.

## Scope-out (this item)

- The adapter's `TransportError` code mapping and `reconcile_labels`'s handling of it — both
  already correct (Grounding facts, Decision 6); this item does not add a new shared
  `TransportError` code such as `scope` to `RETRYABLE_DEFAULTS`. The preflight's scope read is a
  separate, best-effort diagnostic (Decision 3), not a change to the live-operation error
  taxonomy every write path shares.
- `refresh_counts`'s snapshot-preservation behavior on backend failure — already correct
  (`query.py:395-396`), not touched here.
- Auto-remediation — running `gh auth login` or writing/rotating a token on the operator's
  behalf. The check reports and names the remedy; the operator runs it, consistent with every
  other doctor finding (Enable-Gate, label reconcile, etc.).
- Adding a `gh` preflight to onboarding/discovery — this is a doctor (health-check/repair)
  concern per the issue's own framing, not an onboarding-time addition.
- The migration runbook's post-cutover repair/handoff gap (#622) — a sibling item covering the
  same discodon gap-7 evidence from the runbook-documentation side, not restated here.
- Exact wording/format of `gh auth status`'s output across `gh` CLI versions — this environment
  has no `gh` binary to re-verify against (Grounding facts); the design pass should re-confirm
  current output shape against an installed `gh` before parsing it.

## Evidence / references

- `plugin/lib/backlog/transport.py:73-83` — `RETRYABLE_DEFAULTS`, the closed set of
  `TransportError` codes; no `scope` code exists today.
- `plugin/lib/backlog/transport.py:232-244` — `build_env()`, the non-interactive `gh` environment
  contract, and its pass-through of `GH_TOKEN`/`GITHUB_TOKEN` from the ambient environment.
- `plugin/lib/backlog/transport.py:854-877` — `_spawn`, the existing `FileNotFoundError` →
  PATH-missing mapping to reuse rather than duplicate.
- `plugin/lib/backlog/transport.py:885-935` — `_run`/`_map_failure`, the existing exit-4 and
  401/403 → `auth` mapping, and the absence of scope-specific detection.
- `plugin/lib/backlog/transport.py:134-153` — `_parse_head`, the existing header-parsing
  primitive whose shape a header-based scope check (Decision 3) would reuse.
- `plugin/lib/backlog/core.py:1127-1151` — `reconcile_labels`, which already surfaces
  `TransportError`'s `code` field in its JSON envelope via `from_transport_error`.
- `plugin/lib/backlog/query.py:395-396` — `refresh_counts`'s failure handling (preserves the last
  snapshot; does not clobber), cited by the issue's own "not the bug it looks like" analysis.
- `plugin/lib/learnings_obligation.py:15-73` — the closest existing precedent for a small,
  read-only diagnostic module reporting a closed set of named statuses into one doctor Health
  Check line.
- `plugin/skills/doctor/SKILL.md:56` — Health Check #12, its current "if `gh` is unavailable,
  report the repair is pending and move on" guidance, and its `backlog_service_repo`-unset skip
  rule this item mirrors.
- `plugin/lib/briefing.py:859`, `plugin/bin/prawduct-hook:5794-5802` — existing
  `read_str_yaml_key(…, "backlog_service_repo")` call sites, the precedent GHA-2 reuses.
- Issue #623 — problem statement, "not the bug it looks like" analysis, proposed change, and
  acceptance criteria this document grounds.
