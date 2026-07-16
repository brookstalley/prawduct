---
artifact: api-notes
version: 1
scope: backlog-service
depends_on:
  - artifact: backlog-service-prd
last_validated: 2026-07-16
---

# API Notes — GitHub REST Issues (captured live shapes)

Captured **2026-07-16** against `api.github.com` with `X-GitHub-Api-Version: 2022-11-28`,
authenticated as a user token (`gho_…`, classic scopes incl. `repo`) obtained via `gh auth token`.
Target: throwaway private repo `brookstalley/prawduct-backlog-scratch` (safe to delete; kept as
the live-verification scratch repo while the service is built). Probes ran over **direct HTTPS
(curl)** — no `gh` in the data path — which is itself the S1 confirmation: user-token auth is a
plain `Authorization: Bearer <token>` header. The service's transport fakes are built from these
captures, never from recalled shapes (re-probe on live failure before touching a fake).

## Request conventions (all confirmed working)

```
Authorization: Bearer <token>          # gho_ user token accepted with Bearer scheme
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json         # on bodies
```

Rate headers arrive on **every** response: `x-ratelimit-limit: 5000`, `-remaining`, `-used`,
`-reset` (epoch), `-resource: core`. `/rate_limit` snapshot matched headers and is itself free.
Whether a 304 costs rate budget was **not settled by these probes** (interleaved calls made
`x-ratelimit-used` deltas unattributable); docs claim 304s are free, but treat that as
unverified until the import write-burst's S3 observation — it only matters for the P1 cache layer anyway.

## Issue object (fields the service consumes)

`POST /repos/{o}/{r}/issues` → 201; `GET /repos/{o}/{r}/issues/{n}` → 200. Same shape from
list, dependency, and sub-issue endpoints (those add a `repository` object).

```json
{
  "number": 1, "id": 4904408044, "node_id": "I_kwDOTasGxM8AAAABJFNT7A",
  "state": "open", "state_reason": null,
  "title": "Probe item one",
  "body": "Item body line.\n\n```prawduct\nid: PBK-0001\n…\n```\n",
  "labels": [{"id": …, "node_id": "LA_…", "name": "pb:stage:ready", "color": "0e8a16",
              "default": false, "description": "…"}],
  "assignee": null, "assignees": [],
  "user": {"login": "brookstalley", "id": 512114, "type": "User"},
  "issue_dependencies_summary": {"blocked_by": 1, "total_blocked_by": 1,
                                 "blocking": 0, "total_blocking": 0},
  "sub_issues_summary": {"total": 1, "completed": 0, "percent_completed": 0},
  "created_at": "2026-07-16T17:19:30Z", "updated_at": "…", "closed_at": null,
  "closed_by": null, "milestone": null, "locked": false,
  "html_url": "https://github.com/…/issues/1", "url": "https://api.github.com/…"
}
```

Full key roster also includes: `active_lock_reason, author_association, comments (count),
comments_url, events_url, labels_url, performed_via_github_app, pinned_comment, reactions,
repository_url, timeline_url`. **Markdown bodies round-trip verbatim** — the fenced
` ```prawduct ` block survived create → PATCH → GET byte-identical.

## State & state_reason (captured transition cycle)

| PATCH sent | resulting `state` | resulting `state_reason` |
|---|---|---|
| `{"state":"closed","state_reason":"completed"}` | closed | `completed` |
| `{"state":"open"}` | open | `reopened` ← **not null** |
| `{"state":"closed","state_reason":"not_planned"}` | closed | `not_planned` |
| `{"state":"open"}` | open | `reopened` |

Fresh issues have `state_reason: null`. Decoders must treat `reopened` (and `null`) as
"no closed-reason", not as a third status.

## Labels

- CRUD: `POST /repos/{o}/{r}/labels` 201 · `PATCH /labels/{name}` 200 (colon names URL-encode
  fine un-encoded in path) · `DELETE /labels/{name}` 204 · `GET /labels` 200.
- Duplicate create → **422** `{"errors":[{"resource":"Label","code":"already_exists","field":"name"}]}`.
  Duplicate detection is **case-insensitive** (`PB:STAGE:READY` collides with `pb:stage:ready`).
- Name limit: **50 characters** (422 `"name is too long (maximum is 50 characters)"` at 66; exactly
  50 succeeds). **Spaces are legal** in names (`pb:source:planning session` → 201).
- A fresh repo ships **9 default labels** (`bug, documentation, duplicate, enhancement,
  good first issue, help wanted, invalid, question, wontfix`) — the GV5 collision surface is real
  from day one; none collide with a `pb:`-prefixed namespace.
- Issue-level set ops, all confirmed: `POST /issues/{n}/labels {"labels":[…]}` **appends**,
  `PUT` same path **replaces the whole set**, `DELETE /issues/{n}/labels/{name}` removes one
  (200, returns remaining array). `PATCH /issues/{n} {"labels":[…]}` also replaces.

## Comments

- `POST /repos/{o}/{r}/issues/{n}/comments {"body":…}` → 201
  `{id, node_id, user:{login…}, body, created_at, updated_at, reactions, …}`.
- `GET …/comments` → array, oldest-first; supports `since=` (ISO-8601; future timestamp
  returned `[]` — filters like the issues list).

## Assignees — the take-and-verify capture

- `POST /issues/{n}/assignees {"assignees":["brookstalley"]}` → 201, assignee present on read-back.
- `POST` with a **nonexistent user → 201 and silently no assignment** (assignees unchanged).
  No error signal at all. This is why claims are take-**and-verify**: the write status proves
  nothing; only the read-back does (CC3).
- `DELETE /issues/{n}/assignees {"assignees":[…]}` → 200, removed.

## Dependencies (blocked-by) & sub-issues — endpoints live and confirmed

- `POST /repos/{o}/{r}/issues/{n}/dependencies/blocked_by {"issue_id": <database id, not number>}`
  → 201, returns the *blocked* issue with updated `issue_dependencies_summary`.
- `GET  …/dependencies/blocked_by` → array of **full issue objects** (incl. `state`) — the
  ready-work blocker check reads `state` straight off this response.
- `GET  …/dependencies/blocking` → reverse direction, same shape.
- `POST /repos/{o}/{r}/issues/{n}/sub_issues {"sub_issue_id": <database id>}` → 201 (parent
  returned, `sub_issues_summary` updated). `GET …/sub_issues` → array of issue objects.
- Both take the **database `id`**, not `number` — a client footgun worth a test.

**`issue_dependencies_summary` semantics — captured via close/reopen cycle:**

- `blocked_by` counts **open** blockers only; `total_blocked_by` counts all. Proven: closing the
  sole blocker moved the summary from `{blocked_by:1, total_blocked_by:1}` to
  `{blocked_by:0, total_blocked_by:1}`.
- The summary is **eventually consistent after state changes**: immediately after reopening the
  blocker it still read `blocked_by: 0`; minutes later it read `1` (both on the single GET and
  in list items). Do **not** treat a summary read taken near a mutation as truth.
- The `GET …/dependencies/blocked_by` **list is read-your-writes**: it showed the blocker's
  `state: "closed"` immediately after the close and `"open"` immediately after the reopen.
  Consequence: the summary is a pre-filter; per-item verification reads the list.

## Listing & queries

`GET /repos/{o}/{r}/issues` with:

- `state=open|closed|all` — works; list items carry `state_reason`,
  `issue_dependencies_summary`, `sub_issues_summary`, full `body`, full `labels` — so
  ready-work/stale-verification pre-filtering needs **no per-item fetches**.
- `labels=a,b` — comma = AND; single label filter confirmed exact.
- `assignee=<login>` — confirmed.
- `since=<ISO8601>` — **an `updated_at` cursor**: returns items with `updated_at` strictly after
  the timestamp; exclusion proven (mid-window probe returned only the later-updated items).
- `per_page=N` — pagination via `Link` header, now **cursor-form**
  (`…&after=Y3Vyc29y…&page=2>; rel="next"`, `rel="prev"` on page 2): follow `rel="next"`
  verbatim; never construct page URLs.
- Sort default: `created` desc.
- **Open PRs did NOT appear in the issues list** (probe: open PR present, list returned issues
  only). PRs **share the number space** (the probe PR took #4) and **are addressable** via
  `GET /issues/4` (response carries a `pull_request` key). Clients must still handle a
  PR-numbered `get` (refuse: not a backlog item) — but list-filtering appears no longer needed.
  Historical documented behavior said lists include PRs; treat this as version-current behavior,
  re-verify if a list ever shows a `pull_request` key (cheap invariant check in the client).

## Conditional requests (ETag) — cache-layer groundwork

- Single issue GET: strong `etag: "3f30e6…"` + `last-modified`; `If-None-Match` → **304**
  (empty body, same etag) while unchanged; after a PATCH the old etag → **200** with new body.
- List GET (`?state=all`): also etagged; `If-None-Match` → **304** confirmed.
- `cache-control: private, max-age=60` — GitHub itself hints 60 s.

## Error shapes (the return-value error model maps from these)

| Case | Status | Body |
|---|---|---|
| missing issue | 404 | `{"message":"Not Found","documentation_url":…,"status":"404"}` |
| create w/o title | 422 | `{"message":"Invalid request.\n\n\"title\" wasn't supplied.",…,"status":"422"}` |
| bad token | 401 | `{"message":"Bad credentials",…,"status":"401"}` |
| dup label | 422 | `{"message":"Validation Failed","errors":[{resource,code,field}]}` |

`status` in bodies is a **string**. Rate-limit exhaustion (403/429 + `retry-after` /
`x-ratelimit-reset`) was not provoked; map from headers per docs and observe live during
the importer's paced write burst (S3).

## Facts that corrected recalled knowledge (why probes precede fakes)

1. Issues list **excludes open PRs** (old lore: PRs contaminate the list).
2. Invalid assignee adds are **silent 201 no-ops** (no error to catch — verify by read-back).
3. Reopen sets `state_reason: "reopened"` (not back to null).
4. Pagination is cursor-based in the `Link` header now (page-number math would break).
5. Label duplicate detection is case-insensitive.
6. `issue_dependencies_summary` lags mutations (eventually consistent); only the
   `dependencies/blocked_by` list read is immediate.
