# Issue #262 — Cross-product governance stats: Design

`status: revised 2026-10-03 · stage: ready · area: governance/telemetry · added: 2026-08-04 ·
issue: https://github.com/brookstalley/prawduct/issues/262`

Builds on `documentation/issues/262-requirements.md` (Decisions 1–4, AGG1–AGG7). The build plan is
`.prawduct/artifacts/build-plan-telemetry-aggregate.md`.

## Command

```
prawduct-hook aggregate-stats [<product-dir>...] [--from-file <list>]
                              [--bundles <file-or-dir>]... [--collector] [--json]
```

At least one source is required: a product, a bundle path, or `--collector`. Otherwise exit 1, as
for any bad argument. `--from-file` holds one path per line; blank lines and `#` lines are skipped,
and paths resolve against the working directory.

Exit codes: 0 with a report (no reports at all is an answer); 1 on bad arguments, a `--bundles`
path that does not exist, or a `--collector` fetch that fails. A fetch failure exits rather than
reporting without the contributed data, because a view that silently lacks half its input looks
complete. Read-only: it writes nothing anywhere.

## Local products (AGG1, AGG5, AGG6)

Each named path is resolved and read through `evidence.read_facts`. Outcomes:

| Condition | Outcome |
|---|---|
| not a directory | skipped, `invalid-path` |
| not inside a git repository, or the store cannot be read | skipped, with `read_facts`' reason |
| no store yet | skipped, `no-store` |
| same store as a path already named | skipped, `same-store` (worktrees share one store) |
| contributed data included and the sent-window record cannot be read | skipped, `unreadable-sent-record` |
| readable | included |

Reports come from `contribution.weekly_reports(facts, now, schema, max_weeks=None)`, which is
`pending_reports` without the sent-window filter and with the week cap optional; `pending_reports`
becomes a filter over it. So a local report is byte-for-byte what that product would contribute for
the week. When bundles or the collector are included, windows in the clone's sent record are left
out and counted as `already_contributed`. A report sent but not yet flushed into a bundle is missed
for up to a day; that is accepted.

## Contributed reports (AGG2, AGG3)

- `--bundles <file>` reads one bundle, and `--bundles <dir>` reads every `*.jsonl` in it, in name
  order.
- `--collector` fetches `bundles/index.json` from the collector origin (derived from
  `contribution.COLLECTOR_ENDPOINT`), then each listed day's bundle. It sends a GET with the
  `prawduct` user agent, refuses redirects (the endpoint is pinned), times out, and caps each
  response's size. A `404` on the index means nothing is published yet, which is zero reports, not
  a failure.
- Each non-empty line is parsed and checked with `contribution.validate`. A line that does not parse
  or fails the allowlist is counted under `refused` and otherwise ignored. Duplicate lines are kept.

## Aggregation (AGG4)

The version key is `"{plugin_major}.{plugin_minor}"`, plus `-dev` when `dev` is true. Local and
contributed reports go through the same function. For each version:

- `reports`: `{local, contributed}`;
- `weeks`: the first and last `YYYY-Www` covered;
- `volume`: for `sessions`, `scopes` and `reviews`, a count of reports per band;
- `metrics`: for every number field in the allowlist that at least one report carries, `n`,
  `median` and `trimmed_mean`. The trimmed mean drops `floor(n / 10)` values from each end. A metric
  a report omitted, because its denominator was under the floor, is absent from that report and is
  not a zero.

Each report counts once: one product-week for one version. Versions sort by `(major, minor, dev)`.

## `--json` shape

```json
{
  "schema_version": 1,
  "generated_at": "2026-10-04T12:00:00Z",
  "sources": {
    "local": [{"path": "/abs/product", "reports": 7, "already_contributed": 2, "schema_ahead": 0}],
    "local_skipped": [{"path": "/abs/other", "reason": "no-store"}],
    "contributed": {"bundles": 3, "lines": 41, "refused": 1}
  },
  "by_version": {
    "3.7": {
      "reports": {"local": 5, "contributed": 12},
      "weeks": {"first": "2026-W36", "last": "2026-W39"},
      "volume": {"reviews": {"1-9": 9, "10-49": 8}},
      "metrics": {"review_minutes_median": {"n": 15, "median": 11.0, "trimmed_mean": 11.6}}
    }
  }
}
```

`contributed` is `null` when no bundle source was given.

## Surfaces

- new `plugin/lib/aggregate.py`: the command body, the bundle reader and fetcher, and the
  aggregation.
- `plugin/lib/contribution.py`: `weekly_reports`, with `pending_reports` rebuilt on it.
- `plugin/bin/prawduct-hook`: a thin `cmd_aggregate_stats` wrapper, dispatch, `_USAGE`, and the
  read-only command set.
- `plugin/skills/janitor/SKILL.md`: one sentence in Step 1, plus a grant in both spellings.
- `plugin/docs/governance-telemetry.md`: a section for the command.
- `collector/README.md`: the input contract names `aggregate-stats`.
