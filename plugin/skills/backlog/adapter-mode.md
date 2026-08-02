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
- Developing prawduct itself (repo-local, uncommitted `plugin/bin/`)? Use `python3 plugin/bin/prawduct-hook backlog …`
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
in-progress / … per the two-axis status) plus the action menu. Post-cutover the **live** actions are
`pick`, `add`, `list`, `update` (and `merge` when both ids are known); present `find`/`dedup` as
**not available on this backend yet** rather than ready, and omit `migrate`/`scrub` (the one-time markdown→Issues cutover is
already done). Counts are **derived by the adapter** — never persist one yourself. Richer breakdowns
(top `area:` tags, a stale-item count) come from `list`; run it if asked rather than approximating
from `counts`.

**Surface `untriaged` by exception.** `data.untriaged` counts OPEN issues on the backlog repo
carrying neither a namespaced label nor a `prawduct:` block — filed by a human or by another
governed product, and never triaged. When it is non-zero, say so **above** the rollup and offer
`list --untriaged`, because an untriaged item is the one nobody has looked at and must read louder
than a triaged one, not quieter. When it is zero, say nothing. It is a **subset** of the open
count, not an addend — never add the two.

### list [filters]
`prawduct-hook backlog list --repo <r> --json [--status S] [--stage S] [--kind K] [--area A]
[--effort E] [--impact I] [--source SRC] [--assignee A|none|*] [--state open|closed|all]
[--sort created|updated] [--direction asc|desc] [--per-page N] [--page N] [--untriaged]` → render the
tabular view
(`ID · title · effort · impact · area · status`) from `data`'s items. Map the human/`--flag` filters
onto the adapter flags; **claimed-item exclusion is `--assignee none`** (the issue assignee *is* the
claim). Keep the render lean — a handful of rows, most-relevant first.

`--untriaged` **inverts** the scope filter: it returns only the issues `list` normally drops (the
ones `counts.untriaged` counts), so it is how you show an operator what needs triage without
sending them to the GitHub web UI. It scans every page and **refuses** `--per-page`/`--page`
(re-run without them); every other filter still applies. These are not items yet — they have no
stage, kind or area — so render `ID · title` and treat the missing facets as *untriaged*, not as
missing data.

### get <id> — view one item
When you need one item's full detail (a direct "show me PFX-XXXX", or before an `update`):
`prawduct-hook backlog get <id> --repo <r> --json` → render the item's fields + body from `data`.

`get` also returns the item's **comment thread** — `data.comments`, oldest-first
`{author, created_at, body, url}` — because comments are where an item evolves after filing: a
clarification, a narrowed scope, a link to the fix. **Read the thread before acting on an item**;
the body alone may be stale. Every read (`get`/`list`/`pick`) carries `comments_count`, so a
nonzero count on a list line is your cue to drill down with `get`. If the thread can't be fetched,
`get` still succeeds — `comments` comes back empty while `comments_count` keeps the payload count,
and a warning says the discussion is there but unread; don't treat that as "no comments".

## Write operations

Same envelope + exit discipline as reads. Render by the **operation you invoked** (you know which
one you ran) — never sniff the envelope for "which key is present," which is how a shared-key result
type shadows another. Two write-specific notes: a write can return exit **5 (auth)** when withheld
under an untrusted CI trigger (SEC-5) — surface it plainly, don't retry-loop; and **you never invent a
mutation path** — the adapter exposes exactly the ops in the usage table, each with its own crash-safety
contract (idempotent/resumable `import`, redirect-before-close `merge`). No generic preview-or-apply flag
sits over those mutations: the only preview-before-write is `restructure-preview` (the deterministic
before/after a bulk `import` would produce, approved in aggregate), and the upstream filing op adds its
own preview-by-default when it ships.

### Status vocabulary bridge
The markdown skill's statuses are **not** the adapter's. Map before calling `status --to`:

| skill (markdown) | adapter `--to` |
|------------------|----------------|
| `open`           | `open` |
| `promoted` (in an active build plan) | **`in-progress`** |
| `shipped`        | `shipped` |
| `dropped`        | `dropped` |

The adapter also has **`submitted`** — a triage/intake state (e.g. an upstream-filed item awaiting
triage) with no markdown equivalent; know it exists. There are **no `## Open`/`## Promoted`/`## Archive`
sections** post-cutover: open/closed state + `status:` labels carry lifecycle placement.

### add
`prawduct-hook backlog file --repo <r> --title T --body B [--stage S] [--kind K] [--area A]
[--effort E] [--impact I] [--source SRC]`. Author an issue-standard title (`area: summary`, ≤72,
atomic) + a sectioned body; set `--kind`. The result may carry `lint[]` (WARN-only issue-standard
hints — surface, never blocks). **Dedup-on-create is degraded** while the backend has no full-text search: do a
coarse check with `list --area=<area> --json` and eyeball recent titles for overlap before filing,
and say full dedup is not available on this backend yet.

### update `<id>`
Route by what changed:
- **status** (`status=X`) → `status <id> --to <mapped>` (bridge table above). Idempotent (re-run =
  no-op); a close records `closed_by` natively.
- **field** (title/body/stage/kind/area/effort/impact/source) → `update <id> [--flag …]` (last write
  wins — correct for the interactive single-actor case). The item envelope does **not** surface an
  `updated_at`, so the optional `--if-updated-at <ts>` optimistic-concurrency guard (exit **4
  conflict** on a stale timestamp) is only usable when a caller already holds that timestamp from
  elsewhere; the skill's normal path omits it.
- **claim** (`accepted-by=@x` / clear) → `claim <id> [--claim-ttl S]` / `unclaim <id>`.
- **link edge** (`related:`/blocks/blocked-by/parent/child) → `link <id> --edge <e> --to <target>` /
  `unlink …`.
- **a free note** → `comment <id> --body B`.

### pick
`prawduct-hook backlog pick --repo <r> [--limit N] [--claim] [--claim-ttl S]` → the adapter returns
ranked ready-work (impact/effort fan-out, blocker-aware, excludes claimed). Render 1–3 candidates + a
one-line *why*. Keep the skill's framing on top: **build-plan overlap** (read `active_build_plan`,
surface overlapping candidates first) and **stage-aware routing** (don't present an early-stage item
as buildable). `--claim` soft-claims the top pick.

## Deferred operations — search-dependent (land when backend search does)

No adapter search op exists yet (cache-served `search` is not built yet), so these degrade — do **not**
fabricate a search:
- **find `<query>`** → a `NOTE:` — *"full-text search is not available on the Issues backend yet; meanwhile filter with `list
  --area=`/`--status=`/`--stage=`/`--kind=`, or use GitHub's issue search in the browser."*
- **dedup** → the duplicate-scan needs search → same `NOTE:`. `merge <source-id> --into
  <target-id>` still works when you already know both ids (folds A→B, redirect-before-close).

## Operations that don't apply post-cutover

The live backlog is Issues, so these markdown-file operations are moot — return a brief `NOTE:`:
- **migrate** (legacy → structured *markdown*) — nothing to migrate; the one-time markdown→Issues
  cutover is `scrub`, already run.
- **import `<path>`** (external file → backlog) — to bring external items in now, create issues:
  `import --from <backlog.md>` for a markdown backlog, or `file` per item for arbitrary sources.
- **archive split (Q2)** — Issues has no archive-file size limit; closed issues are the archive. N/A.

## Grooming timestamp
`list` (and `pick`) still stamp `backlog_last_groomed_at: <today>` in `project-state.yaml` — the fact
that resolves the `backlog-overdue-grooming` advisory. Stamp it **only on a successful (exit-0)**
call: in adapter mode a `list`/`pick` can fail (exit 5/6), and stamping on a failed call would
falsely resolve the advisory. It is a *timestamp*, never a persisted count (counts are always
re-derived).
