---
artifact: build-plan
version: 1
scope: backlog-comments-read
depends_on:
  - artifact: backlog-service-api-contract   # documentation/backlog-service-api-contract.md §2.1
  - artifact: backlog-service-data-model     # documentation/backlog-service-data-model.md §1.3
last_validated: 2026-08-02
---

# Build Plan — `get` reads the comment thread (DM5 read side)

**Problem.** DM5 contracts comments as "the drill-down channel" and the `comment`
op writes them natively — but no read op returns them. `core.get_item` fetches
only the issue payload, the decoded item shape carries neither the thread nor a
count, and the backlog skill's `allowed-tools` confine agents to
`prawduct-hook backlog …` ops. So when a filed issue is later clarified by a
comment (or a comment links the solution), every agent working from the backlog
acts on the stale body and never sees the clarification. The full-text-over-
comments query (Q1) was deferred to the read-through cache, but the *drill-down
read* needs no cache — it is one extra REST call on a single-item `get`.

**Success.** `prawduct-hook backlog get <id>` returns the item **with its comment
thread**: `comments` = `[{id, author, created_at, body, url}]` (oldest-first, all
pages) and `comments_count`. Every decoded item (list/pick/get) carries
`comments_count` from the issue payload, so "this item has discussion" is visible
before drilling down. Human `get` output renders the thread. A failed comment
fetch degrades — warning + payload count + empty thread, never a failed `get`
(ERR-6 posture, same as the redirect-follow). The skill docs tell agents the
thread arrives with `get` and must be read before acting on an item.

**Out of scope.** Full-text search over comments (Q1-fulltext — stays with the
read-through cache). Comment rendering in `list`/`pick` *lines* (count rides in
the JSON; the thread is `get`'s job). Threading/replies structure (GitHub issue
comments are flat). Any new mutation path.

## Requirements Confidence

**Level:** High — DM5 already names comments the drill-down channel and the
requirement gap is the *read* contract, which this plan adds to the API contract
`get` row (the documented parent) rather than inventing silently. The user's
acceptance scenario is concrete: an issue clarified by a comment must show that
comment to a backlog-skill agent.

## Status

- [ ] Chunk 01: transport + core + CLI + docs + tests

Context: plan authored and chunk BUILT 2026-08-02 in one work cycle
(`feature/backlog-comments-read` off `develop`), from the user's direct ask
("agents that use the backlog skill would see" clarifying comments). Suite
green: 3346 passed, 7 skipped. Verified live against `brookstalley/prawduct#128`
(4-comment thread renders; JSON carries `comments`/`comments_count`). The `[ ]`
above flips at release via the `scope=backlog-comments-read` change-log tag
(views_enabled). Remaining in-cycle: cumulative Critic, backlog item
file-and-archive.

## Chunks

### Chunk 01: transport + core + CLI + docs + tests

- `plugin/lib/backlog/transport.py`: `list_comments(owner, repo, number)` on the
  `Transport` protocol and `GhTransport` (`_api_paged` over the REST issue
  comments endpoint, reduced to
  `{id, author, created_at, body, url}` — the `list_timeline` precedent).
- `tests/fakes/fake_github.py`: `list_comments` (stateful, not_found on a missing
  issue, `_maybe_unreachable`); issue payloads model the native `comments` count
  (0 at create, incremented by `create_comment`).
- `plugin/lib/backlog/encode.py`: `decode_item` gains
  `comments_count: issue["comments"]` (present on every decoded item for free).
- `plugin/lib/backlog/core.py`: `get_item` fetches the thread when the payload
  count is nonzero (skip the call at 0), attaches `comments` +
  `comments_count=len(...)`; on fetch failure appends a warning and returns the
  item with the payload count and an empty thread (ERR-6).
- `plugin/lib/backlog/cli.py`: human `get` renders the thread (author · date,
  body indented).
- `plugin/skills/backlog/adapter-mode.md` `get` section: the thread arrives with
  `get`; read it before acting — clarifications and solution links land there
  (DM5 drill-down). *Deliberately NOT `SKILL.md`* (narrowed during the build,
  recorded per Critic R-2): SKILL.md routes every Issues-backend operation to
  adapter-mode.md, so a duplicate line there would violate the routing design
  and drift.
- `documentation/backlog-service-api-contract.md` §2.1 `get` row and
  `documentation/backlog-service-data-model.md` §1.3: the read side of DM5.
- **Type:** feature (small-medium; one contract surface — the item shape gains
  two additive fields, no consumer relies on their absence).
- **Done when:**
  1. L1 tests cover: thread on `get`, zero-comment skip, degraded fetch,
     count fidelity in the fake, human rendering. Full suite green.
  2. Reviewed by `/prawduct:critic` (cumulative — ships in one PR).
  3. Backlog item filed for traceability and archived on this branch
     (`closed-by=backlog-comments-read`).
  4. Committed and chunk marked `[x]`.
