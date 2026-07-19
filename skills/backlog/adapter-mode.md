# Adapter mode — driving the GitHub-Issues backend

This runbook is the **post-cutover** path for `/prawduct:backlog`: it applies when
`backlog_service_repo: owner/repo` is set in `.prawduct/project-state.yaml` (see "Backend routing"
in `SKILL.md`). The live backlog is GitHub Issues, reached through the `prawduct-hook backlog`
adapter — the stable public CLI contract. You do **not** touch `.prawduct/backlog.md` in this mode.

## Invocation

Every operation is one adapter call:

```
prawduct-hook backlog <op> --repo <owner/repo> --json [op flags]
```

- `<owner/repo>` is the value of `backlog_service_repo` — resolve it once, pass it as `--repo`.
- Always pass `--json`: the JSON envelope becomes the **sole stdout content**, so you parse stdout
  directly; diagnostics and progress go to stderr.
- Developing prawduct itself (repo-local, uncommitted `bin/`)? Use `python3 bin/prawduct-hook backlog …`
  rather than the on-PATH `prawduct-hook` — identical contract, just the local build.
- The adapter is **non-interactive** — it never prompts. Any confirm-before-write step is yours to
  run in conversation *before* the call; never expect the adapter to ask.

## Reading the result — envelope + exit code

Bind to the **exit code and the JSON envelope**, never to human text (exit codes are the contract;
`--json` readers tolerate unknown keys, so read the fields you need and ignore the rest). The exit
class:

| code | class | meaning |
|------|-------|---------|
| 0 | ok | operation succeeded |
| 2 | validation | bad input (unknown id spelling, bad flag value) |
| 3 | not-found | the id / resource does not exist |
| 4 | conflict | a claim / optimistic-concurrency conflict |
| 5 | auth | not authenticated, or a write withheld |
| 6 | unavailable | the backend (`gh` / network) is unreachable |

The stdout envelope is one of three shapes:

- **`{"status":"ok","data":…,"warnings":[…]}`** — render `data` for the operation. If `warnings[]`
  is non-empty, surface each to the user as a `NOTE:` line — they are advisory (unknown soft-enum, a
  self-heal audit line) and do **not** mean failure.
- **`{"status":"error","error":{"code":…,"message":…,"retryable":…}}`** — surface `error.message`
  (name the `code`) to the user, per the exit class. **Also surface any `warnings[]` present on the
  error envelope** — the error path can still carry advisory audit lines, and those are one-shot;
  dropping them loses information permanently.
- **`{"status":"queued","data":{"provisional_id":…}}`** — an *optional* offline-queue layer that is
  **not built today**. If a future build queues a write while GitHub is unreachable, report the
  `provisional_id` and that it reconciles on reconnect. **In the current state there is no queue: an
  unreachable backend returns `unavailable` (exit 6) instead** — handle it per the error discipline
  below.

A `file` result may also carry **`"lint":[{"rule","message","severity":"warn"}]`** — surface these
as `WARNING:` issue-standard hints. Lint **never** changes `status` or the exit code (it is not a
gate).

## Error discipline — fail loud, never fall back

On exit **5 (auth)** or **6 (unavailable)** the backend could not be reached. Surface a clear
`NOTE:` — e.g. *"backlog service unavailable (<message>); the backlog is GitHub Issues at
`<owner/repo>` — not falling back to the frozen markdown"* — and stop. **Never** read
`.prawduct/backlog.md` as a substitute: it is frozen pre-cutover history, and presenting it as the
live backlog is exactly the stale-as-live failure this mode exists to prevent. (Advice degrades to a
note; it never silently substitutes stale data.)

## Read operations

### summary (no args)
`prawduct-hook backlog counts --repo <r> --json` → render the section rollup from `data` (open /
in-progress / … per the two-axis status) plus the action menu (`pick`, `add`, `find`, `list`,
`update`, `dedup`, `import`, `scrub`). Counts are **derived by the adapter** — never persist one
yourself. Richer breakdowns (top `area:` tags, a stale-item count) come from `list`; run it if
asked rather than approximating from `counts`.

### list [filters]
`prawduct-hook backlog list --repo <r> --json [--status S] [--stage S] [--kind K] [--area A]
[--effort E] [--impact I] [--source SRC] [--assignee A|none|*] [--state open|closed|all]
[--sort created|updated] [--direction asc|desc] [--per-page N] [--page N]` → render the tabular view
(`ID · title · effort · impact · area · status`) from `data`'s items. Map the human/`--flag` filters
onto the adapter flags; **claimed-item exclusion is `--assignee none`** (the issue assignee *is* the
claim). Keep the render lean — a handful of rows, most-relevant first.

### get <id> — view one item
When you need one item's full detail (a direct "show me PFX-XXXX", or before an `update`):
`prawduct-hook backlog get <id> --repo <r> --json` → render the item's fields + body from `data`.

## Grooming timestamp
`list` (and `pick`) still stamp `backlog_last_groomed_at: <today>` in `project-state.yaml` on
invocation, regardless of backend — the fact that resolves the `backlog-overdue-grooming` advisory.
It is a *timestamp*, never a persisted count (counts are always re-derived).
