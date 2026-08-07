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
| 4 | conflict | an optimistic-concurrency (CAS) conflict on `update` |
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
as `WARNING:` issue-standard hints. These body/label findings never change `status` or the exit
code. **The four §1 TITLE checks are different — they BLOCK**: `file` and `update` refuse a
non-conforming title with a `validation` error (exit 2) before writing, and `import` refuses the
whole corpus pre-flight. So a `lint[]` you can surface is by construction the advisory kind; a
blocking one arrived as an error instead.

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
[--effort E] [--impact I] [--source SRC] [--tag T] [--assignee A|none|*] [--state open|closed|all]
[--sort created|updated] [--direction asc|desc] [--per-page N] [--page N] [--untriaged]` → render the
tabular view
(`ID · title · effort · impact · area · status`) from `data`'s items. Map the human/`--flag` filters
onto the adapter flags. **Items someone is already on are excluded by rendering, not by a filter:**
each item carries `working_branch`, so drop the ones that have it unless the user asked for
`--include-working`, and show the branch in the row when you do. There is no server-side filter for
it — it is a body-block field, so the provider cannot select on it, and post-filtering a page would
make the returned `count` disagree with the page it came from. `--assignee` is still a filter, but
assignment no longer means anything to prawduct: `claim` is retired and nothing writes assignees.
Keep the render lean — a handful of rows, most-relevant first.

`--untriaged` **inverts** the scope filter: it returns only the issues `list` normally drops (the
ones `counts.untriaged` counts), so it is how you show an operator what needs triage without
sending them to the GitHub web UI. It scans every page and **refuses** `--per-page`/`--page`
(re-run without them); every other filter still applies. These are not items yet — they have no
stage, kind or area — so render `ID · title` and treat the missing facets as *untriaged*, not as
missing data.

### get <id> — view one item
When you need one item's full detail (a direct "show me PFX-XXXX", or before an `update`):
`prawduct-hook backlog get <id> --repo <r> --json` → render the item's fields + body from `data`.

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
atomic, 15-72 chars) + a sectioned body; set `--kind`. **A title failing §1 is REFUSED** with a
`validation` error, not filed — rewrite and retry. The result may carry `lint[]` (body/label
issue-standard hints — surface, never blocks). **Dedup-on-create is degraded** while the backend has no full-text search: do a
coarse check with `list --area=<area> --json` and eyeball recent titles for overlap before filing,
and say full dedup is not available on this backend yet.

### update `<id>`
Route by what changed:
- **status** (`status=X`) → `status <id> --to <mapped>` (bridge table above). Idempotent (re-run =
  no-op); a close records `closed_by` natively.
- **field** (title/body/stage/kind/area/effort/impact/source) → `update <id> [--flag …]` (last write
  wins — correct for the interactive single-actor case). **`--title` is gated**: a new title failing
  §1 is refused (exit 2) before any write. Every OTHER field goes through untouched even when the
  item's *stored* title does not conform — that is deliberate, so archiving an old item never forces
  a drive-by retitle; the result carries an advisory `lint[]` saying the title was left alone.
- **tags** (`--tags a,b`) → sets the **whole** set: absent tags are stripped, `--tags ''` clears
  them. That is the only semantics under which a caller can remove one. Tags are an open
  folksonomy — invent values freely, and never build a check that reads them (`--tag T` on `list`
  filters by one of them).
- **affected** (`--affected p1,p2`) → repo-relative paths only, **no prose and no globs**; a
  directory covers everything under it, so write `plugin/lib/backlog`, never `plugin/lib/backlog/**`.
  An entry carrying whitespace or a glob character is refused (exit 2) — put the annotation in the
  body. This is what lets a reviewer intersect items against a changed-file set instead of reading
  item text and inferring.
- **working-branch** (`--working-branch owner/repo@branch`) → the branch someone is working the item
  on. It must name a **pushed** branch (exit 2 otherwise — push it, don't rename it or point the
  field somewhere else) and must be **repo-qualified**, because the backlog repo and the code repo
  are not necessarily the same one. `--working-branch ''` clears it, and **nothing else ever does**:
  no code path rewrites the field when a branch is merged or deleted, and none should — a merged
  item's branch is the record of what shipped it. A merge makes the marker *inert* (the item leaves
  ready-work on its status), it does not remove it. Do not "tidy" one away after a merge.
  **This is how an item is taken. There is no `claim` op** — it is retired, along with `unclaim`,
  the TTL and the assignee stamp. Setting the branch is the whole of taking an item, and `pick`
  excludes on it, so nothing else has to be recorded. Nothing expires it: the branch's last commit
  is the activity signal, which is why there is no TTL to configure and no reap to wait for.
- **link edge** (`related:`/blocks/blocked-by/parent/child) → `link <id> --edge <e> --to <target>` /
  `unlink …`.
- **a free note** → `comment <id> --body B`.

The item envelope does **not** surface an `updated_at`, so the optional `--if-updated-at <ts>`
optimistic-concurrency guard (exit **4 conflict** on a stale timestamp) is only usable when a caller
already holds that timestamp from elsewhere; the skill's normal path omits it. It applies to the
whole `update` op, not to any one field above.

### pick
`prawduct-hook backlog pick --repo <r> [--limit N] [--include-working]` → the adapter returns
ranked ready-work (blocker-aware; items carrying a `working-branch` are excluded). Render 1–3
candidates + a one-line *why*. Keep the skill's framing on top: **build-plan overlap** (read
`active_build_plan`, surface overlapping candidates first) and **stage-aware routing** (don't
present an early-stage item as buildable). `--include-working` adds back the items someone is on,
each naming its branch, for when you deliberately want to see contested work.

`pick` takes nothing. Recording that you are on an item is
`update <id> --working-branch owner/repo@branch`, after the branch is pushed — a separate,
deliberate act, so a `pick` that only wanted to *look* never marks anything.

**The candidates come from the local cache, and the answer says how old it is.** `pick`
revalidates first (a conditional request, free in the steady state) and then reads the store, so
its `warnings` carry the store's confirmed-at stamp and age; if the revalidation failed, a warning
says so too and the answer is the last good one rather than a fresh one. Blockers are the
exception — they are read live on every call, because a blocker can live in a repo the cache does
not hold. Surface the age when you render: a stale answer presented as a current one is the failure
the visible age exists to prevent.

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
