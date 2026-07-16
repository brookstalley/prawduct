---
artifact: api-contract
version: 1
scope: backlog-service
depends_on:
  - artifact: data-model-backlog-service
  - artifact: security-model-backlog-service
  - artifact: api-notes-github-issues
last_validated: 2026-07-16
---

# API Contract — `prawduct-backlog` CLI

## Overview & Surface Type

**Surface:** CLI (`bin/prawduct-backlog`), non-interactive, flags only — no prompts ever (AG1).
**Consumers:** internal (the `/prawduct:backlog` skill, briefing, hooks) *and* external (adopter
agents scripting against JSON output once the plugin ships) — external consumers are why the JSON
envelope below is a versioned contract, not incidental output.
**Canonical contract:** this document. The exit-code scheme + JSON envelope are the stable
machine surface; human output is presentation, never parsed.

## Operations (P0 surface)

| Command | Effect | Safe/idempotent |
|---|---|---|
| `add --title T [--body B] [--stage S] [--label pb:…]…` | create item (one-call: title suffices, AG2) | no / no |
| `get <id>` | fetch one item, any ID grammar form | yes |
| `list [filters]` | query items (see filters below) | yes |
| `update <id> [--title] [--body] [--stage] [--add-label] [--remove-label] [--field k=v]` | field-wise update; `--field` writes body-block keys only and **rejects op-owned keys** (`id`, `node`, `verified`, `closed-by`, `superseded-by`) with a `usage` error naming the dedicated op | no / yes per field |
| `close <id> --as shipped\|dropped [--closed-by H]` | close with two-axis mapping | no / yes |
| `reopen <id>` | reopen | no / yes |
| `comment add <id> --body B` · `comment list <id>` | basic comment primitive (DM5 P0 slice) | no / no · yes |
| `claim <id> [--as login]` · `release <id>` | take-and-verify assignee claim / release | no (race-checked) |
| `verify <id> [--as login]` | TF2 stamp: rewrite `verified:` block field | no / yes |
| `ready` | ready-work query (open ∧ stage:ready ∧ unclaimed ∧ blockers closed) | yes |
| `stale [--days N=90]` | open items unverified in N days | yes |
| `count [filters]` | counts derived on read (Q5) | yes |
| `import --dry-run\|--execute [--journal P]` | file → issues migration | dry-run: read-only |
| `export [--out DIR]` | issues → plain files, full fidelity (MG2) | yes |
| `rollback --journal P` | close/label exactly the journal's created set | no / yes |

`list` filters: `--status V` `--stage V` `--label L` (repeatable, AND) `--assignee A`
`--source P` `--state open|closed|all` `--since CURSOR` (Q2) `--text STR` (client-side
title/body scan) `--limit N` `--full` (include bodies in list output). Changed-since is `list --since`; the CLI echoes
`"cursor": <max updated_at>` in list output for the next call.

Global flags: `--json` · `--repo owner/name` (overrides `backlog.repo` config) · `--timeout S`
· `--version` · `--help`.

## Inputs & Outputs

- IDs accepted in every grammar form (data model §4); **all output echoes canonical
  `owner/repo#N`**.
- **JSON mode** (`--json`): single JSON object on stdout, nothing else on stdout ever.

```json
{"v": 1, "ok": true, "data": …, "warnings": ["stale_status_label: …"]}
{"v": 1, "ok": false, "error": {"kind": "rate_limited", "message": "…",
 "retryable": true, "status": 403, "retry_after": 42,
 "detail": {"github_request_id": "…"}}, "warnings": []}
```

- **Item shape** (`data` for `get`; `data.items[]` for list-family) — a curated projection,
  not GitHub's raw object (excessive-exposure discipline; raw fields available only via the
  `url`):

```json
{"id": "brookstalley/prawduct#42", "number": 42, "node": "I_kwDO…",
 "title": "…", "status": "in-progress", "stage": "ready",
 "facets": {"area": "hooks", "effort": "M", "source": "discodon"},
 "labels_other": ["good first issue"], "assignees": ["brookstalley"],
 "alias": "BKL-5D2C", "verified": "2026-07-16 brookstalley", "added": "2026-07-13",
 "closed_by_handle": null, "related": ["prawduct#40"],
 "blocked_by_count": 0, "sub_issues": {"total": 0, "completed": 0},
 "state_reason": null, "url": "https://github.com/…/issues/42",
 "created_at": "…", "updated_at": "…", "body": "… (get only; list omits unless --full)"}
```

- `closed_by_handle` is the GV3 ship-traceability handle from the body block's `closed-by:`
  field — **not** GitHub's `closed_by` user object, which is not projected. `state_reason` is
  the raw GitHub value (`null` here: an open item; the example is a coherent in-progress state
  per the data model's decode matrix). `error.detail` is an optional object for correlation
  data (`github_request_id`) — part of the versioned envelope, additive like all `detail` keys.
- List-family responses: `{"items": […], "count": N, "cursor": "<max updated_at>"}`; the CLI
  auto-follows `Link: rel="next"` cursors (never page math — captured), bounded by `--limit`.
- **Human mode** (default): one line per item
  (`owner/repo#N  [stage:ready] [in-progress] Title  (area:hooks, effort:M)`), details
  indented; errors to **stderr**. Human output may change without notice; only JSON is contract.

## Error Model   <!-- recorded decision → api_error_model_approach -->

**Return-value errors end-to-end** (project convention): the HTTP client returns
`status`/`reason` dicts, the core maps them to a stable **kind vocabulary**, the command layer
renders envelope + exit code. Exceptions escape only at the `bin/` boundary (never a traceback
on any operational failure).

| `error.kind` | Meaning / mapped from (captured shapes) | `retryable` | Exit |
|---|---|---|---|
| `usage` | bad flags/args, unknown command, ambiguous ID | no | 2 |
| `auth` | 401 "Bad credentials" / no token resolvable / permission-denied 403 (any 403 that fails the rate-limit discriminator below) | no | 1 |
| `not_found` | 404; also PR-numbered IDs (`reason: is_pull_request`) | no | 1 |
| `validation` | 422 (message passed through), unknown-value hard conflicts | no | 1 |
| `conflict` | claim lost race (read-back shows another holder) | no | 1 |
| `network` | DNS/connect/timeout — fail < 2 s on cut network (G2 floor) | yes | 3 |
| `rate_limited` | `429` always; `403` **only when** a `retry-after` header is present or `x-ratelimit-remaining: 0` (rate headers ride on every response — captured — so bare 403 ≠ rate-limited); `retry_after` from `retry-after`/`x-ratelimit-reset` | yes | 3 |
| `server` | 5xx | yes | 3 |
| `internal` | bug in us (the only traceback path, at `bin/` after the envelope prints) | no | 1 |

**Exit codes: 0 success · 1 operational, not retryable · 2 usage · 3 retryable.** Code 3 is the
never-block floor's shell-visible signal — a gate/hook can back off on `$? == 3` without parsing
JSON. **P0 performs no automatic retries**: fail fast with `retryable` + `retry_after` and let
the caller decide (an auto-retry loop inside a session-start hook is exactly how never-block
dies). `warnings` (advisory validation, DM1) never affect exit codes.

## Versioning   <!-- recorded decision → api_versioning_approach -->

- **Mechanism:** integer envelope field `v`, whole-surface granularity. **Status: active, `v: 1`
  from the CLI's first release.**
- `v` bumps **only** on breaking change (removing/renaming a field, changing semantics or exit
  codes). Additive changes (new fields, new commands, new warnings) never bump it.
- `--version` prints the plugin version (the CLI ships inside the plugin and is versioned by it);
  `v` is the *contract* version and moves independently and rarely.
- Consumers pin behavior by checking `v`; unknown envelope fields must be ignored
  (tolerant-reader expectation, stated here as part of the contract).

## Deprecation & Compatibility   <!-- part of api_versioning_approach -->

- **Evolution rules:** additive-only within a `v`; never remove or repurpose a field, flag, exit
  code, or `error.kind`; new enum-ish values (kinds, warnings) may appear — consumers must
  tolerate unknown values (mirroring DM1's tolerant stance).
- **Deprecation:** a deprecated flag/command keeps working for **≥ 1 minor plugin release**,
  emitting a one-line warning on **stderr** (never stdout) and a `"deprecated": [...]` envelope
  field; removal lands only with a `v` bump, recorded in the change-log.
- **Compatibility commitment:** stable-tier surface cannot break without a `v` bump + deprecation
  window; internal consumers (skill/briefing) update in lock-step with the plugin, so windows
  exist for external adopters.

## Surface Inventory & Stability Tiers

- **Stable** (once the backlog-service P0 slice ships — its closing cumulative review, recorded in the change-log): every operation in the table above, the
  envelope, item shape, exit codes, error kinds.
- **Experimental** (may change without window): until the slice ships, everything is
  experimental; the tier then flips to stable as a whole — recorded in the change-log.
  `--full` and `--text` stay experimental beyond that point (client-side scan semantics may
  move server-side when the cache layer lands).
- No hidden/admin commands. `import`/`rollback` are stable but guarded (explicit `--execute`,
  journal required — see security model).

## Conventions

- Timestamps: ISO-8601 UTC (`2026-07-16T17:19:30Z`), as GitHub emits them; dates in body-block
  fields are `YYYY-MM-DD`.
- IDs: canonical `owner/repo#N` strings — human-readable by design (D4); GitHub `node` exposed
  for transfer-proof persistence.
- Naming: snake_case JSON fields; `null` = "known absent", omitted = "not fetched"
  (e.g. `body` in list mode).
- stdout = data, stderr = diagnostics, always.

## Security

Authentication/credential resolution: `security-model-backlog-service.md`. API-design failure
modes at this boundary:

- **Object authorization is GitHub's** (PV1 structural): the CLI holds no ACLs; a token that
  can't read a repo gets `auth`/`not_found` passed through honestly.
- **Mass assignment:** `update` binds only enumerated flags; `--field k=v` writes only
  body-block keys, never GitHub-native fields; nothing reflects raw request JSON.
- **Excessive exposure:** curated item projection only; no `user` emails, reactions, or raw
  payloads in output.
- **Cost bounds:** auto-pagination bounded by `--limit`; import paced < 80 writes/min
  (GitHub's documented secondary write ceiling — observed headroom recorded during the import
  burst, S3); single-attempt requests with bounded timeouts (`--timeout`, default connect 2 s
  / total 10 s).
- Tokens never appear in argv, logs, JSON, or error text (a regression test forces an auth failure and asserts the token appears in no output stream).

## Conditional Patterns

- **Concurrency:** claim = take-and-verify (data model §6); general optimistic concurrency
  (CC2 compare-and-set) is deferred P1 — recorded, not silent.
- **Conditional requests:** the client sends no `If-None-Match` in P0 (online-only, always
  fresh); ETag handling is specced for the P1 cache layer (`api-notes` §Conditional).
- **Correlation:** `x-github-request-id` is surfaced in `error.detail` for support/debugging.
