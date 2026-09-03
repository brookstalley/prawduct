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
- **The op surface describes itself.** `prawduct-hook backlog --help` prints the whole usage
  table — every op the adapter exposes — and `prawduct-hook backlog <op> --help` prints one op's
  flags. Both go to **stdout at exit 0**, so they are safe to run before any call. That output is
  the op set: read it rather than inferring an op or a flag from this file.

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

### The retry budget — bounded, or it is not a budget

**The adapter never retries a call for you.** It runs `gh` once per op, classifies the failure and
returns — there is no loop and no backoff anywhere on the single-op path, and a hung `gh` is cut at
30s. The one exception is `import`, which pauses and retries a *rate-limited record* inside its own
run and then ends resumably; never wrap that op in a retry of your own.

So every retry is yours, and `retryable: true` is a hint that re-attempting **can** work — never a
licence to loop until it does. The budget for one operation:

- **Retry only a `retryable: true` error.** `unavailable`, `rate_limited` and `conflict` are the
  retryable codes. `validation`, `not_found`, `ambiguous_id`, `alias_collision`, `auth` and
  `unsupported` are permanent — re-running one is a defect, not a recovery. Fix the call or stop.
- **Max attempts: 3** — the first call plus at most **2** retries.
- **Pause 2s, then 4s** between them. On `rate_limited`, use `error.details.retry_after` instead
  when the server sent one, capped at 60s; if that pause would outlast the deadline, give up now.
- **Deadline: 120s** from the first attempt — whichever bound trips first ends it. A healthy op
  answers in under 2s, so the deadline is a runaway ceiling, not an allowance to spend.
- **`conflict` (exit 4) is a re-read, not a retry.** Re-fetch with `get`, re-apply on top of what
  you read, send once. Re-sending the same `--if-updated-at` conflicts forever.
- **Before replaying a `file` or a `comment`, check whether it landed** (`cache-query search`, or
  `list`): neither carries an idempotency key, so a call that failed *after* the write reached
  GitHub duplicates on replay. `status`, `update`, `link`/`unlink` and `merge` converge on re-run,
  so replaying those is safe.
- **Give up rule.** On the third failed attempt, or when the deadline passes, **stop**. Report the
  last `error.code` and `message` and how many attempts you made, exactly as the discipline above
  says. Do not re-plan into a different op, do not retarget another repo, and do not read the
  frozen markdown. An unbounded retry loop is the *opposite* of never-block.

## Read operations

### summary (no args)
`prawduct-hook backlog counts --repo <r> --json` → render the section rollup from `data` (open /
in-progress / … per the two-axis status) plus the action menu. Post-cutover the **live** actions are
`pick`, `add`, `list`, `update`, `find` and `dedup` (and `merge` when both ids are known) — `find`
and `dedup` run on the local cache's full-text index, below — and omit `migrate`/`scrub` (the
one-time markdown→Issues cutover is already done). Counts are **derived by the adapter** — never persist one yourself. Richer breakdowns
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

This set is a **superset of the security model's `quarantine`**, which is the *non-collaborator*
half of it (Security §6/F7). The author predicate is not implemented, so `--untriaged` is what
reaches an anonymous filing today — over-including the owner's own unlabeled issues rather than
missing one. Do not describe the two as the same query.

### get <id> — view one item
When you need one item's full detail (a direct "show me PFX-XXXX", or before an `update`):
`prawduct-hook backlog get <id> --repo <r> --json` → render the item's fields + body from `data`.

`get` also returns the item's **comment thread** — `data.comments`, oldest-first
`{id, author, created_at, body, url}` — because comments are where an item evolves after filing: a
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
mutation path** — the adapter exposes exactly the ops in the usage table `prawduct-hook backlog --help`
prints, each with its own crash-safety
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
[--effort E] [--impact I] [--source SRC] [--refs R]`. Author an issue-standard title (`area: summary`, ≤72,
atomic, 15-72 chars) + a sectioned body; set `--kind`. **A title failing §1 is REFUSED** with a
`validation` error, not filed — rewrite and retry. The result may carry `lint[]` (body/label
issue-standard hints — surface, never blocks). **Dedup-on-create runs on the cache**: check with
`cache-query search "<the title's distinctive words>" --area <area> --json` before filing. That
search is deliberately cache-served rather than delegated — the provider's index is not
read-your-writes, so an item filed seconds ago is invisible to it, which is exactly the moment this
check is asked. If the cache exits 6, say the dedup check could not run; do **not** report "no
duplicates found".

**Then run `SKILL.md`'s `add` step 2 before filing — the three-way offer.** It is the one step of
that procedure this section does not replace, because the question is about the work rather than
about where the item lands: when the item describes work in this repo that is **ready to build**,
say the three options out loud — *delegate it, do it now, or backlog it* — with the delegate's cost
attached. Read it there; it is not restated here. What this backend has to translate is the
in-flight mark: on *delegate it*, `status <id> --to in-progress` (the bridge above) plus
`update <id> --working-branch owner/repo@branch` once that branch is pushed — there is no
`accepted-by:` here.

**Always pass `--stage`** when you can infer it (a clearly-scoped bug or cleanup → `ready`; a vague
one-liner → `idea`), and omit it only when genuinely unclear. It is also what the offer above reads
— `ready` is that bar, and this is the only place it is recorded. An item filed stageless is one
`ready-work` and `pick` will never present as buildable, and it leaves that offer with nothing to
read.

**The ```` ```prawduct ```` block is adapter-owned — do not hand-write one.** It is a serialization
the adapter composes, stamps and emits, exactly one per issue; the flags and `link` are how you set
what goes in it. They are checked, they are what the cache indexes, and a hand-written block is
free-text you can typo into a field nothing reads. This is a prohibition, not a preference: a body
you author carries prose, never a block.

**If one reaches `--body` anyway it is merged, not dropped.** Composition folds any block already in
the body under the fields the command itself sets and emits a single block, so an edge like
`related:` written at filing time still lands. Two fields are the exception in **both** directions:
`automated` and `worker` are attribution stamps — who filed this — and are stripped from an embedded
block whether or not the command sets them, so a body cannot launder a background sweep into looking
human. The merge is a safety net for a mistake, and it is why the mistake now costs you a wrong
field rather than a missing one; it is not permission to write the block.

### update `<id>`
Route by what changed:
- **status** (`status=X`) → `status <id> --to <mapped>` (bridge table above). Idempotent (re-run =
  no-op). A close records `closed_by` natively **only on close-on-merge** (the timeline close-ref);
  a bare `status --to shipped` carries no handle, so pass a `closed-by=<scope>` argument through as
  `update <id> --closed-by <scope>` in the same breath or the ship handle is simply lost. GitHub's own timeline holds *who*
  closed the issue (and the closing PR or commit when the close rides a merge), but the adapter
  neither stamps nor surfaces it, and the *scope* is not recoverable from it. `update` **does** take
  a `--closed-by` flag writing a queryable block field (#550/#564) — the comment workaround this
  paragraph used to prescribe is retired. `status` itself still takes none, which is why the scope
  rides the paired `update` above rather than the close. Never hand-write it into a `prawduct:`
  block: that block is adapter-owned.
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
- **editorial block field** (`refs:`/`revisit:`/`closed-by:`) → `update <id> --refs V`,
  `--revisit V`, `--closed-by V` — each takes a value, and an **empty** value clears the field, so
  an expired `revisit:` can be removed rather than blanked. `file` also takes `--refs` so a new item
  can carry its governing-doc link from birth. With `--affected`, `--working-branch` and `--tags`
  above, these are the only writable block fields; **`--body` is not a route into the block** — a
  pasted block is stripped and the existing one re-appended, so a block edit sent that way changes
  nothing. It does not do so silently: a pasted block asking for something the write did not land (compared against the block as it finally stands, after the flags layer on — not against the stored one) comes back
  with a warning naming the differing fields, so check `warnings` rather than reading `ok` as "the
  block edit landed". A body carrying NO block is not reported — "I deleted it" and "I never pasted
  one" are the same text.
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
candidates + a one-line *why*. Keep the skill's framing on top: **build-plan overlap** (resolve the
active plan as the skill says — `branch:` claim first, `active_build_plan` second, and it is the
skill that states which claim wins when several name one branch — and surface
overlapping candidates first) and **stage-aware routing** (don't
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

## The local cache — `sync` and `cache-query`

The store behind `pick` is also queryable directly, and it is what `find` and `dedup` run on.

**`sync`** — `prawduct-hook backlog sync --repo <r> [--rebuild]` is how the store learns what
*other* people changed. Incremental by default: it fetches what the provider reports changed since
the stored watermark and takes a rate-free 304 when nothing has. `--rebuild` forces the full scan,
which is the answer to a corrupt store or a schema bump; the incremental path already falls back to
it when no watermark exists.

**Your own writes mostly do not wait for it.** `file`, `status`, `update`, `merge` and
`link/unlink --edge related` mirror themselves into the store as they go, so there is no window in
which the cache disagrees with one of those — which is what makes the dedup claim below true rather
than merely intended. **The exceptions are real and worth knowing:** `comment`, `provision` and
`reconcile-labels` change nothing the store holds; the native `blocks`/`parent` edges are not cached
at all; and `import` refreshes by a sync after the run, skipped when no store exists yet. A sync is
still what brings in edits made elsewhere.

**You rarely need to run it by hand.** Session start fires it detached, beside the counts warm — the
briefing never blocks on it, so a session opens with the store already warming. Run it explicitly
when a reader reports the store unavailable or conspicuously old, or when a write warned that the
cache was not updated.

**`cache-query`** — `prawduct-hook backlog cache-query <query> [args] --repo <r> --json` reads that
store and nothing else: no network, no writes. `find <query>` maps to `cache-query search <text>
[--area A]`, and `dedup`'s duplicate scan is `search` per area cluster. **Cache-served rather than
delegated on purpose:** the provider's index is not read-your-writes, and the moment a dedup check is
asked is exactly the moment the item it should find was just filed.

The other queries — `open`, `by-area`, `stale`, `unstaged`, `created-since`, `resolve`, `affecting` —
and the two rules every caller binds to (**exit 6 means the store could not be read, not that nothing
matched**; every payload carries a visible age) are in `cache-reads.md`, which the Critic, PR reviewer
and janitor read too.

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
