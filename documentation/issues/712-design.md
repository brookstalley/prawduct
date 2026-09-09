# Issue #712 — Backlog: No Sweep Detects Merged Work Whose Item Is Still Open: Design

`status: draft · stage: design · area: backlog · added: 2026-09-08 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/712`

**No separate requirements doc exists for #712, and none is needed.** The requirement itself is
already specified at the backlog-service-adapter level — `documentation/backlog-service-requirements.md`
**GV3** (ship traceability replaces ship atomicity), **GV10** (chunk-close hygiene is the front-line,
this sweep the backstop) and **GV12** (advisory, never hard-gate); the field home in
`documentation/backlog-service-data-model.md` §1.1 (`closed_by`) and its note under the table;
`documentation/backlog-service-api-contract.md` §2.6 (native close-ref + block fallback + "a janitor
workflow… not a single op"); and the test shape in `documentation/backlog-service-test-specifications.md`
§3.12 (**GOV-1**, including the `drift-corpus` fixture). None of that is restated here. What those
docs deliberately left open — "a periodic `list`+timeline scan" is named as the *shape*, never
specified — is what #712 owes, and what this document resolves: **which signal carries enough
precision** for each of the two drift directions, and the concrete module/CLI/wiring that implements
it. #712's own body already narrows the choice ("prefer high-precision inputs… over prose matching")
and warns against the BLD-4K7P false-positive family; this document picks the specific primitives.

## Grounding facts

Re-verified against the current tree (2026-09-08):

- **Nothing implements the sweep today.** Janitor Step 2.5 runs exactly 7 numbered checks
  (`plugin/skills/janitor/SKILL.md:225-238`); none is GV3. Check 5 ("neglected hygiene") is a
  different, still-dormant concept blocked on the `promoted` GH-Issues gap (#529), not this one.
- **`/prawduct:pr` already names #712 as its own missing backstop.** Merge Flow's "Close the backlog
  items this PR resolves" step
  (`plugin/skills/pr/SKILL.md:165`) and its "Honest limit" note (`:167`) point here by number: "If you
  merge through the GitHub UI, or the session ends at the merge, nothing downstream notices the close
  never fired… tracked as #712."
- **`closed_by` is not a cache column.** `cachequery.py`'s `_FULL_COLUMNS`
  (`plugin/lib/backlog/cachequery.py:51-65`) has no `closed_by` field, so no existing `cache-query`
  answer can serve this sweep — confirming the sibling docs' own framing that GV3 is a **live** read,
  never a cache one. The **block** `closed-by:` value *is* visible in the cached `body` column when the
  sanctioned close flow wrote it, but the **native** timeline close-ref that is authoritative on a
  merge-close (`documentation/backlog-service-data-model.md:55,60-65`) is not fetched into the cache at
  all today.
- **Shipped/dropped items are already synced into the local store.** `sync.py:571` fetches
  `state="all"`, and `encode.py:65` decodes closed+`state_reason=completed` to `status="shipped"`. So
  the `item` table already holds shipped items with their cached body (hence any block `closed-by:`
  value) — a free, zero-network candidate source for direction (b) below.
- **No GraphQL call exists anywhere in `plugin/lib/backlog/` today** (`grep -ri graphql` is empty).
  The sibling test spec already commits to one, though: the fake's contract in
  `documentation/backlog-service-test-specifications.md:786` states the timeline reader goes "over
  **GraphQL** for `MarkedAsDuplicateEvent.canonical`… and the `closed` event (carrying the closing
  PR/commit ref **for GV3**)". That decision was made when the sibling docs were written; it was never
  built. This design does not invent GraphQL as a new call style — it finishes a call style the
  backlog-service spec already committed GV3 to and flags exactly where.
- **`list_timeline` already exists and already names GV3 as its consumer.** Its docstring
  (`plugin/lib/backlog/transport.py:382-386`) reads: "Returns a list of `{event, actor, created_at,
  …}` dicts… what `export` serializes **and GV3/`closed_by` reads**." The REST implementation
  (`transport.py:742`, `GET …/issues/{number}/timeline`) is live today, but REST's `closed` timeline
  event carries a commit ref, not a direct PR number — which is exactly why the test spec routed the
  closer specifically through GraphQL (`ClosedEvent.closer`, which resolves to a `PullRequest` or
  `Commit` directly).
- **The one existing precedent for "cache-ranked candidates, then a bounded live fan-out" is `pick`**
  (`plugin/lib/backlog/query.py:183-291`): it ranks from the cache, then fans out a live REST call
  per candidate (`transport.list_blocked_by`, `:287`) bounded by the caller's `limit`. This sweep
  reuses that shape rather than inventing a new one.
- **Method naming is load-bearing on `Transport`.** `plugin/lib/backlog/transport.py:276-282`: the
  pacing decorator classifies every call as read/write from its name prefix (`get_`/`list_` read;
  `create_`/`update_`/`add_`/`remove_` write) and *raises* on an unrecognized prefix. Any new method
  this design adds must carry `get_` or `list_`.
- **`gh api graphql` reuses the existing egress site, not a new one.** `GhTransport` already drives
  `gh` as a subprocess through `_api`/`_api_paged` (`transport.py:868-926`), list-form args, with the
  SEC-1 secret-scrubbing this file's own header describes. `.prawduct/project-state.yaml:184` names
  `lib/backlog/transport.py` as one of exactly three egress sites in the whole framework; a GraphQL
  call issued as `gh api graphql -f query=…` through the same `_api` helper stays inside that site — it
  does not open a fourth one.
- **This repo dogfoods the Issues backend against itself** (`backlog_service_repo:
  brookstalley/prawduct`, `.prawduct/project-state.yaml:35`), so the sweep this design specifies is
  immediately exercisable here, not only theoretical.

## Decisions resolved

### Decision 1 — the precision signal for *merged-but-item-open*

**Use GitHub's own keyword parser via GraphQL `closingIssuesReferences`, never a prose regex over PR
bodies.** A merged pull request's `closingIssuesReferences` field lists exactly the issues GitHub's
own "Closes #N"/"Fixes #N"/"Resolves #N" parser recognized on that PR — populated the moment the
keyword is parsed, independent of whether the PR's base branch made the auto-close fire (auto-close
fires only for merges into the repository's **default** branch, per GitHub's docs; keyword
*recognition* is not gated that way). This is the "native PR↔issue
link" #712's body asks to prefer: prawduct never inspects PR text itself, it reads the field GitHub's
parser already populated, which is exactly the BLD-4K7P-avoiding property the issue names as a
requirement, not a nicety.

**Candidate generation is PR-first, not issue-first**, which is also the cost argument: merged PRs in
a lookback window are a small, slowly-growing set, while re-scanning every open item's timeline on
every sweep is not. Concretely:

```
GhTransport.list_merged_pull_requests(owner, repo, *, since: str) -> list[dict]
```

— a GraphQL query over `search(query: "repo:{owner}/{repo} is:pr is:merged merged:>={since}", type:
ISSUE, …)`, each result carrying `number`, `mergedAt`, and `closingIssuesReferences { number }`. For
every `(pr_number, issue_number)` pair returned, resolve `issue_number` against the **local cache**
(a plain `SELECT status FROM item WHERE id = ?`, or `cachequery.resolve` for the redirect-aware path)
— free, no extra network call. An issue that resolves **open** is a `merged_but_item_open` finding;
one that resolves `shipped`/`dropped` is not (the drift never happened, or already self-healed);
one the cache does not hold is a full miss and reported as `unavailable`-scoped-to-that-PR rather than
silently dropped, per the cache contract's own "unavailable is never empty" rule
(`cachequery.py:8-12`).

**Verify before building, not assumed:** whether `is:pr is:merged` search plus `closingIssuesReferences`
truly populates independent of base branch is a live-platform fact, not a documented guarantee this
repo has pinned yet. Per this doc family's own convention (`documentation/backlog-service-data-model.md:24-26`,
"Altitude & foreign-API note" — design intent, not exact GraphQL shape; a `verify-api` step at build
confirms it against live payloads), the build chunk runs one `verify-api` pass against a throwaway PR
on a non-default base branch before wiring this in. If the fact does not hold as expected, the fallback
is `ConnectedEvent`/`CrossReferencedEvent.willCloseTarget` read from the **issue's own** `timelineItems`
(GraphQL) — strictly more expensive (issue-first, not PR-first) but the same native, non-prose
precision; name this as the fallback in the build chunk rather than re-opening the design.

### Decision 2 — the precision signal for *shipped-but-PR-died*

**Read the item's own `closed_by` the way GV3 already specifies it should be read: native
`ClosedEvent.closer` first, the block `closed-by:` field only as fallback** — this direction needs no
new decision beyond finishing the one the sibling docs already made (data-model.md:60-65,
api-contract.md:162-170). Concretely, a second new method:

```
GhTransport.get_issue_closer(owner, repo, number) -> dict | None
```

— GraphQL, reading the issue's `timelineItems(itemTypes: [CLOSED_EVENT], last: 1)`, and on that
event's `closer`: `{"kind": "pull_request", "number": N, "merged": bool}` when it resolves to a
`PullRequest`, `{"kind": "commit", "sha": …}` when it resolves to a bare commit, or `None` when the
issue was closed with no linked entity at all (a `status`-only close through `/prawduct:backlog`,
which never carries a native closer — exactly the case api-contract §2.6 says the block field exists
to cover).

Candidate generation for this direction is **cache-served and free**: `status = 'shipped'` items are
already in the local `item` table (state="all" sync, confirmed above), so a new, narrowly-scoped
cachequery-style read —

```
shipped_since(project_dir, *, scope, since, now) -> dict   # items with status='shipped',
                                                             # updated_at >= since
```

— reuses `cachequery.stale_items`'s exact `_instant(...)` comparison shape (`cachequery.py:288-316`)
against `updated_at` rather than a new pattern, bounded by a lookback window (default matching the
existing stale-items horizon, so the sweep has one horizon concept rather than two) to keep the
per-run candidate count small and slowly growing rather than the whole shipped archive every time.

For each candidate: call `get_issue_closer`. If it names a PR and that PR's `merged` is `false` (the
`shipped-but-PR-died` case), or if `closer is None` and the block `closed-by:` value (already present
in the cached body — no extra call) names something the block-value cannot itself confirm as merged,
resolve *that* reference through the same `get_issue_closer`-style PR-state check when it parses as a
PR number, or report it under **scope-out** below when it does not.

### Decision 3 — where this lives

**A new module, `plugin/lib/backlog/reconcile.py`, not `cachequery.py` and not `query.py`.**
`cachequery.py`'s own docstring is explicit that its invariant is "never opens a connection [to the
network] themselves, the same way nothing but `transport.py` reaches the network"
(`cachequery.py:1-6`) — this sweep is a live read by definition (Decisions 1–2), so folding it into
`cachequery.py` would break that module's one invariant for every other reader of it. `query.py` is
close in shape (`pick`'s cache→live-fan-out pattern, Decision-1/2's template) but is scoped to ready-
work ranking; a distinct module names the sweep as its own thing, the way `sync.py` is its own module
rather than a function bolted onto `cache.py`.

`reconcile.py` exposes one function per direction (`merged_but_item_open`, `shipped_but_pr_died`) and
one composing entry point (`drift_sweep`) that calls both and returns one envelope — mirroring
`cachequery._serve`'s `{status, data, warnings}` shape (`cachequery.py:162-209`) so a caller already
handling that envelope shape (the janitor, `/prawduct:backlog`) needs no second parsing convention. On
a transport failure (auth, rate limit, network), it returns `unavailable` with a reason — never an
empty result — the same rule `cache-reads.md:62-66` states for the cache surface, applied here to the
live one.

### Decision 4 — the CLI surface

**A new `prawduct-hook backlog drift-sweep` subcommand, not a `cache-query` — because it is not one.**
`_run_cache_query`'s own docstring states the contract that makes it grantable to the `critic-reviewer`
agent: "no provider call, no store write, no session state touched" (`cli.py:1029-1033`). This sweep
makes provider calls by construction; folding it into `cache-query` would either violate that
docstring's contract or force every `cache-query`-holding reader to newly reach the network, which is
exactly the narrow-tool-list guarantee `review-cycle.md`'s no-execution contract depends on. It is a
sibling top-level op beside `cache-query`/`archive-plan`/`review-stats`, dispatched from `cmd_backlog`
the same way those are, taking `--repo owner/repo` (required, same as `cache-query`) and an optional
`--since ISO` / `--lookback-days N` (defaulting to the stale-items horizon per Decision 2) to bound
cost. Output is the two-list JSON envelope from Decision 3, or human-mode text for direct/janitor use.

### Decision 5 — wiring into janitor Step 2.5

**A new numbered check, scoped to the Issues backend and only there** — the inverse of checks 6–7's
markdown-only scoping (`plugin/skills/janitor/SKILL.md:233-238`), because GV3's drift is a
*consequence* of leaving git for traceability (requirements.md:278-281); on the markdown backend the
archive still rides the closing PR atomically, so this class of drift is structurally impossible
there, not merely unchecked. Inserted after check 7 (renumbering none of the existing checks, since
these two are named by number rather than order-dependent):

```
8. Ship-reconciliation drift (GV3) — Issues backend only; `prawduct-hook backlog drift-sweep
   --repo <scope>`. Surfaces both directions from the Backlog Health block: an item marked
   `shipped` whose closing PR never merged, and a merged PR whose linked item is still open.
   Advisory only — never auto-closes or auto-reopens (D4, GV12); each finding routes to the
   same infer-confirm-proceed reconciliation Step 3 already runs, recommending
   `/prawduct:backlog update <id> status=…` and leaving the call to the operator. Exit 6
   (unavailable) reports as one line, the same rule check-count-5's own dormancy note and
   `cache-reads.md:62-66` both already follow — never silently omitted.
```

`allowed-tools` in the janitor frontmatter (`plugin/skills/janitor/SKILL.md:29`) gains the matching
grant pair, in the same place the existing `cache-query`/`archive-plan`/`review-stats` grants sit:
`Bash(prawduct-hook backlog drift-sweep*), Bash(python3 plugin/bin/prawduct-hook backlog
drift-sweep*)` — both spellings, for the same reason the frontmatter's own comment already states for
the other three (`SKILL.md:20-22`): a prompt a restricted janitor declines reads exactly like the
unreadable store it exists to report.

### Decision 6 — nothing acts automatically

Both directions produce **findings only**. Neither `reconcile.py` nor the CLI wrapper ever calls
`update`/`status` itself — the acceptance criterion ("nothing is closed or reopened automatically") is
met by construction: the sweep module has no write path, the same way `cachequery.py` has none. The
janitor's existing Step 3 reconciliation (infer → confirm → proceed) is the only place a finding here
turns into an actual `/prawduct:backlog update` call, and only after an explicit operator confirm —
identical to how check 5's `## Promoted` surfacing already works today (`SKILL.md:231`).

## What ships

1. Two new `Transport`/`GhTransport` methods (`transport.py`): `get_issue_closer` and
   `list_merged_pull_requests`, both GraphQL via the existing `_api` seam, both prefixed `get_`/`list_`
   for the pacing decorator.
2. A new module `plugin/lib/backlog/reconcile.py`: `merged_but_item_open`, `shipped_but_pr_died`,
   `drift_sweep` (composing entry point), following `cachequery._serve`'s envelope shape.
3. One new narrow cachequery-style read, `shipped_since`, mirroring `stale_items`'s `_instant(...)`
   comparison shape against `status='shipped'` instead of the open set.
4. A new `drift-sweep` subcommand wired into `cmd_backlog`'s dispatch (`cli.py`), sibling to
   `cache-query`/`archive-plan`/`review-stats`, taking `--repo` (required) and `--since`/
   `--lookback-days` (optional, defaulting to the stale-items horizon).
5. `plugin/skills/janitor/SKILL.md`: new check 8 in Step 2.5 (Decision 5) and the matching
   `allowed-tools` grant pair.

## Acceptance criteria — how each is met

- **A sweep detects open items whose closing work is merged, and shipped items whose PR never
  merged** — `merged_but_item_open` and `shipped_but_pr_died` (Decisions 1–2).
- **Runs cross-session (janitor Backlog Health), not per-branch** — a janitor-invoked CLI subcommand,
  not a Critic/PR reviewer op; nothing here is scoped to a single branch's evidence (Decision 4–5).
- **Advisory only, never blocking** — Decision 6; no write path exists in the new code at all.
- **Precision is designed for, not assumed — no headline-keyword matching** — Decision 1's whole
  argument: the signal is GitHub's own keyword parser (`closingIssuesReferences`), never a prawduct-
  side regex over PR text.
- **Nothing is closed or reopened automatically** — Decision 6.

## Scope-out (unchanged from the issue, restated for build-chunk clarity)

- **A `closed-by:` value that names a bare branch or tag, not a resolvable PR number**, cannot be
  precision-verified by this design (there is no native "this branch merged" link the way there is for
  a PR) — the sweep reports it as `closed_by_unresolvable: <value>` rather than guessing via `git
  branch --merged`, which would reintroduce exactly the prose/heuristic matching #712 rules out.
  Tightening `closed-by`'s writable shape to prefer a PR number is a separate item if this proves
  common in practice; not assumed here.
- Reviving check 5's `promoted` semantics (#529) — unrelated gap, unchanged.
- Any change to how `/prawduct:pr` performs the close itself — this sweep is the backstop GV3 named,
  not a replacement for Merge Flow's "Close the backlog items this PR resolves" step.
- An incremental cursor for `list_merged_pull_requests` (mirroring `sync.py`'s watermark pattern,
  `sync.py:399-465`) would cut the PR-side scan to "since last sweep" rather than a fixed lookback
  window — a real cost optimization, deliberately deferred to the build chunk rather than decided here,
  since the fixed-window default already bounds cost acceptably at this repo's current PR volume and
  a wrong cursor design is more expensive to unwind than a missed optimization.
