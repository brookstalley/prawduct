"""Query — structured ``list``, ready-work ``pick``, and derived ``counts``.

The read side of the adapter (API §2.2). ``list`` and ``counts`` run **online off
the REST list endpoint** with **no cache** (Q1-structured, strongly consistent in
practice — a just-written item appears immediately; the rare brief post-create
window is handled by the caller's bounded settle-retry, ``core.get_item``).
``pick`` is the one read that is cache-backed, and the paragraph below is the
whole of what that costs and buys.

- ``list_items`` — structured field/label filters + sort + paginate, one page as
  the caller requests. Applies the **PROV-2** filter: a plain repo issue carrying
  no prawduct marker is out-of-scope (ignored, not malformed).
- ``pick`` — stage-aware ready-work (Data Model §4). Candidates come from the
  local store (``cachequery.ready_items``: ``open ∧ stage:ready ∧ no working
  branch``) after a **revalidating sync**, and the blocker predicate is then
  applied from a **live** read so a cross-repo blocker is judged correctly. The
  ranking is resolved first and the dependency **fan-out taken lazily down it**,
  stopping at ``limit``. Returns ranked candidates each with a *why* that
  distinguishes *no dependencies recorded* from *all recorded dependencies
  closed*.
- ``counts`` — per-project rollups derived **on read** (never persisted; the GV2
  briefing snapshot in :mod:`snapshot` is a separate op).

Layering: this module sits **above** ``core`` — it reuses core's envelope
(``ok``/``error``). It never touches a model (INV-1) and never shells out except
through ``transport`` (the sole egress); the store it reads is reached only
through ``cachequery``, which is the same discipline one layer over.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import encode, snapshot
from .core import (
    error,
    from_transport_error,
    log_diag,
    ok,
)
from .transport import Transport, TransportError, paginate

# The structured facets ``list`` accepts as label filters (each an AND term).
# ``tag`` rides the same mechanism because a tag *is* a namespaced label — the
# difference is that an item may carry several, so this filters on one of them
# rather than selecting the item's single value.
_LABEL_FACETS: tuple[str, ...] = ("stage", "kind", "area", "effort", "impact", "source", "tag")


# --- list --------------------------------------------------------------------


def list_items(
    transport: Transport,
    *,
    owner: str,
    repo: str,
    filters: dict | None = None,
    sort: str = "created",
    direction: str = "asc",
    per_page: int = 100,
    page: int = 1,
) -> dict:
    """Structured, online ``list`` (Q1-structured). One page as requested —
    except under ``untriaged``, which scans the whole set (see below).

    ``filters`` may carry ``status`` (two-axis: mapped to state + label, then
    refined on the decoded status because closed ``shipped``/``dropped`` differ
    only in ``state_reason`` which is not a list parameter), the label facets
    (``stage``/``kind``/``area``/``effort``/``impact``/``source``/``tag`` — the
    last selects items carrying that ONE tag, since an item may hold many),
    ``assignee``
    (a login, ``none`` for unassigned, ``*`` for any), and an explicit ``state``
    (``open``/``closed``/``all``; default ``open``). Non-prawduct issues are
    dropped (PROV-2).

    The returned ``count`` is the number of in-scope items **on this page** (a
    ``status`` refinement can make it smaller than ``per_page`` even when more
    pages exist) — it is not a total. Drive pagination by ``has_more``: derived
    from the **raw** page length, so a page whose raw entries are entirely
    pull requests / out-of-scope issues (items ``[]`` but ``has_more`` true)
    does not falsely end the walk (BKL-5T3J — "page until an empty page" was
    trippable by an all-PR page in a PR-bearing repo).

    ``filters["untriaged"]`` **inverts** the PROV-2 scope filter, returning only
    the issues this function normally drops. That branch scans every page and
    reports ``has_more: False``; every other filter (``assignee``, ``sort``,
    ``direction``, ``state``, the label facets) applies as usual, and an
    explicit page request is refused at the CLI rather than ignored.
    """
    filters = filters or {}
    # GitHub silently clamps per_page to 100; clamp locally too so `has_more`
    # (raw-length == per_page) stays honest for an out-of-range request.
    per_page = max(1, min(per_page, 100))
    state = filters.get("state", "open")
    labels: list[str] = [f"{f}:{filters[f]}" for f in _LABEL_FACETS if f in filters]

    status_filter = filters.get("status")
    if status_filter is not None:
        check = encode.check_enum("status", status_filter)
        if not check.ok:
            return error("validation", check.message or f"invalid status {status_filter!r}")
        st_state, _reason, st_label = encode.encode_status(status_filter)
        state = st_state
        if st_label:
            labels.append(st_label)

    assignee = filters.get("assignee")

    if filters.get("untriaged"):
        # The inverse of the PROV-2 scope filter: show exactly the issues
        # `list` normally drops. Without this the only way to reach an
        # untriaged item is the GitHub web UI, which is how nine of them
        # accumulated unnoticed over five months — counting them is what makes
        # them visible, but a count you cannot act on is only half the fix.
        #
        # **Scanned whole, not one page.** This is a surface-by-exception view
        # of a set that should be near-empty, and its members are typically the
        # NEWEST issues — so a single ascending page is precisely where they are
        # not. Returning page 1 of the untriaged set would answer "nothing to
        # triage" while items waited on page 2: a short answer indistinguishable
        # from a complete one, the same failure the shared paginator's loud cap
        # exists to prevent.
        #
        # Paging is therefore the one thing this branch cannot honour. The CLI
        # refuses an explicit `--per-page`/`--page` alongside `--untriaged`
        # (`cli._run_list`) rather than ignoring it, because only the CLI can
        # tell a passed value from this function's default. Every other filter
        # — assignee, sort, direction, state, the label facets — is honoured
        # normally, so none is silently dropped.
        issues = all_issues(
            transport,
            owner,
            repo,
            state=state,
            labels=labels or None,
            assignee=assignee,
            sort=sort,
            direction=direction,
        )
        if isinstance(issues, dict):
            return issues  # an error envelope bubbled up from the scan
        items, warnings = _decode_unscoped(issues, owner, repo)
        if status_filter is not None:
            items = [it for it in items if it["status"] == status_filter]
        return ok({"items": items, "count": len(items), "has_more": False}, warnings)

    try:
        issues = transport.list_issues(
            owner,
            repo,
            state=state,
            labels=labels or None,
            assignee=assignee,
            sort=sort,
            direction=direction,
            per_page=per_page,
            page=page,
        )
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6 — unexpected boundary
        log_diag(f"unexpected transport failure on list: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    items, warnings = _decode_scope(issues, owner, repo)
    if status_filter is not None:
        # Refine: a `closed` list can hold both shipped and dropped.
        items = [it for it in items if it["status"] == status_filter]
    # has_more reads the RAW page length — the caller's pagination signal must
    # never derive from the filtered view (BKL-5T3J).
    return ok(
        {"items": items, "count": len(items), "has_more": len(issues) == per_page},
        warnings,
    )


# --- pick (ready-work) -------------------------------------------------------


def pick(
    transport: Transport,
    *,
    project_dir: Path,
    owner: str,
    repo: str,
    limit: int = 1,
    include_working: bool = False,
    now: datetime | None = None,
) -> dict:
    """Ready-work ``pick`` (GV1/DM3): the correct set, ranked, with a *why*.

    Ready-work = ``open ∧ stage:ready ∧ no working branch ∧ all blockers
    closed``. The first three come from the local store in one indexed read; the
    fourth is a per-issue REST fan-out whose states are read **live**, so a
    cross-repo blocker is judged correctly and never picked while open.

    **The split is deliberate and is the design, not an optimisation.** The
    candidate predicate is a property of the items themselves, which the store
    mirrors faithfully and a sync brings level; the blocker predicate is a
    property of *other* items, possibly in another repo this store does not hold.
    A cached edge could record only that a dependency existed, never whether it is
    still open — so a stale store must not be able to let a blocked item through,
    and here it structurally cannot, because it is never asked.

    **Freshness: a revalidating sync runs first.** `pick` is the closest thing in
    this adapter to a decision-driving read, and the freshness contract for one is
    that it is never more than a conditional request behind. In the steady state
    that request is a 304 costing zero rate-limit points. When it fails — offline,
    rate-limited, an unreachable provider — the store is still served, with the
    failure and the store's visible age both reported as warnings: degraded and
    *said*, never silently stale, and never silently empty (an unreachable store
    is an ``unavailable`` envelope, not an empty candidate list).

    Candidates rank oldest first, **and the ranking is computed before the fan-out
    runs**, so the dependency reads are taken lazily down the ranking and stop
    once ``limit`` is filled. Ranking is independent of blocker state, so the
    result set is the same either way; the ordering matters only for cost, which
    is otherwise one REST call per eligible issue regardless of ``limit``.

    A candidate's ``why`` distinguishes *no dependencies recorded* from *all
    recorded dependencies closed* — see :func:`_blocker_clause` for why that
    distinction is not cosmetic.

    ``include_working=True`` adds back the items someone is already working, each
    carrying its branch in the ``why``, for a caller deliberately looking at
    contested work.
    """
    from . import cachequery, sync  # noqa: PLC0415 — lazy: only `pick` drives the store

    now = now or datetime.now(timezone.utc)
    scope = f"{owner}/{repo}"
    warnings: list[str] = []

    revalidated = sync.incremental_sync(
        transport, project_dir=project_dir, owner=owner, repo=repo, now=now
    )
    if revalidated.get("status") != "ok":
        # Degrade to the store, and say so. The alternative — failing the call —
        # would make an offline `pick` useless where a warm store can still answer
        # it well; the alternative to *saying* so would be a silently stale answer,
        # which is the failure this whole layer exists to end.
        reason = (revalidated.get("error") or {}).get("message") or "unknown reason"
        warnings.append(f"backlog not revalidated ({reason}); answering from the local cache")

    ready = cachequery.ready_items(
        project_dir, scope=scope, now=now, include_working=include_working
    )
    if ready.get("status") != "ok":
        return ready  # unavailable — never an empty candidate set
    warnings.extend(ready.get("warnings") or [])
    data = ready["data"]
    warnings.append(
        f"candidates read from the backlog cache, confirmed {data['synced_at']} "
        f"(~{int(data['age_seconds'])}s old)"
    )

    # Read dependencies lazily, in rank order, stopping once `limit` is filled.
    # The ranking key does not depend on blocker state, so filtering before
    # ranking and ranking before filtering yield the identical result set — but
    # this pays one dependency read per *selected* candidate instead of one per
    # *eligible* one.
    #
    # A dependency read that fails surfaces only if `pick` actually needed that
    # candidate. Failing the call over an item the caller was never going to see
    # is worse than not looking — the predicate is still never *assumed* for a
    # candidate that is returned, which is the property that matters.
    candidates: list[dict] = []
    want = max(0, limit)
    for row in data["items"]:
        if len(candidates) >= want:
            break
        number = _number_of(row["id"], scope=scope)
        if number is None:
            # A stored id this call cannot address — malformed, or belonging to a
            # different repo. Reported rather than skipped silently: the blocker
            # predicate is unanswerable for it, and returning it unchecked would
            # be exactly the assumed-clear the fan-out exists to prevent. The
            # query already filters by scope; this is the second half of the same
            # guard, at the point where the number is about to be handed to a read
            # against *this* call's owner/repo.
            warnings.append(f"skipped {row['id']!r}: not an addressable issue id in {scope}")
            continue
        try:
            blockers = transport.list_blocked_by(owner, repo, number)
        except TransportError as exc:
            return from_transport_error(exc)
        except (OSError, json.JSONDecodeError) as exc:  # ERR-6
            log_diag(f"unexpected transport failure on pick fan-out: {type(exc).__name__}")
            return error("unavailable", "the backend request failed unexpectedly")
        if any(b.get("state") != "closed" for b in blockers):
            continue  # an open blocker — not ready work

        candidate = dict(row)
        candidate["why"] = _why(candidate, blockers)
        candidates.append(candidate)

    return ok({"candidates": candidates, "count": len(candidates)}, warnings)


def _number_of(canonical: str, *, scope: str) -> int | None:
    """The issue number in ``canonical``, or ``None`` unless it belongs to ``scope``.

    Parsed rather than stored because the store holds prawduct's vocabulary and an
    issue number is the provider's — the id is the one place the two already meet
    (Cache Spec §4 rule 1: the id is whatever the provider assigned at creation).

    **The scope check is the load-bearing half.** A bare number handed to
    ``list_blocked_by(owner, repo, number)`` is judged against *this* call's repo,
    so a row from another scope would have its blockers read from whatever issue
    this repo happens to have at that number — and could come back clear while
    genuinely blocked. The query is already scoped; this refuses to convert an id
    into a number the moment the two could disagree, so neither guard has to be
    the only one.
    """
    owner_repo, sep, tail = canonical.rpartition("#")
    if not sep or owner_repo != scope:
        return None
    try:
        return int(tail)
    except ValueError:
        return None


# --- counts ------------------------------------------------------------------


def counts(transport: Transport, *, owner: str, repo: str) -> dict:
    """Per-project rollups derived **on read** (Q5) — never persisted here.

    **Untriaged issues are counted, not skipped.** An issue carrying neither a
    prawduct-namespaced label nor a ``prawduct:`` body block is not a decoded
    item (PROV-2 still holds — see :func:`list_items`, which drops them), but in
    a repo nominated as the backlog service it is unmistakably *backlog*: it is
    an open issue on the backlog tracker that nobody has triaged. Excluding it
    from the rollup made the pending figure impossible to reconcile against
    ``gh issue list --state open``, and made the least-attended items — the ones
    filed by humans and by consuming products, which arrive with no block —
    the *only* ones invisible to the tooling. An untriaged item must be louder
    than a triaged one, never quieter, so it is counted here and reported
    separately as ``untriaged``.

    ``untriaged`` is a strict subset of the ``by_status`` tally, not an addend:
    these issues have a real GitHub state, so they decode to a real status the
    same way every other issue does. Adding them to a total that already counts
    them would double-count.

    **It counts OPEN untriaged issues only**, while ``total``/``by_status`` span
    every state. A closed issue has been dispositioned — whatever else is true
    of it, nobody needs to triage it — so counting it here would inflate a
    number whose whole purpose is "work waiting to be looked at". It also keeps
    this figure equal to what ``list --untriaged`` shows, which defaults to open
    and is printed one line beneath it; a count and its own drill-down command
    disagreeing is worse than either being absent.
    """
    issues = all_issues(transport, owner, repo, state="all", labels=None)
    if isinstance(issues, dict):
        return issues

    by_status: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    total = 0
    untriaged = 0
    warnings: list[str] = []
    for issue in issues:
        if encode.is_pull_request(issue):
            continue  # PRs interleave the raw issues list and are never items
        scoped = encode.is_prawduct_issue(issue)
        # Normalised the same way `encode.decode_status` reads it — a bare
        # `== "open"` would miss "OPEN" and treat an absent state as closed.
        if not scoped and (issue.get("state") or "open").lower() == "open":
            untriaged += 1
        item, decode_warnings = encode.decode_item(issue)
        # Decode advisories are about *item* encoding; an untriaged issue has no
        # encoding to be wrong about, so warning on it would report every
        # ordinary GitHub issue as malformed.
        if scoped:
            warnings.extend(decode_warnings)
        total += 1
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
        stage_key = item["stage"] or "(none)"
        by_stage[stage_key] = by_stage.get(stage_key, 0) + 1

    data = {
        "repo": f"{owner}/{repo}",
        "total": total,
        "untriaged": untriaged,
        "by_status": dict(sorted(by_status.items())),
        "by_stage": dict(sorted(by_stage.items())),
    }
    return ok(data, warnings)


# --- refresh-counts (persist the GV2 briefing snapshot) ----------------------


def refresh_counts(
    transport: Transport,
    *,
    project_dir: Path,
    owner: str,
    repo: str,
    now: datetime | None = None,
) -> dict:
    """Derive live counts and **persist** them to the ``briefing_counts`` snapshot
    so session start never waits (GV2/M3).

    The write half of the counts story: :func:`counts` is the always-live read;
    this stamps the same rollup into the degenerate cache with a visible
    ``fetched_at``. On a backend failure it returns the error envelope and writes
    **nothing** — the prior snapshot survives intact (never a corrupt or
    regressing write; the old counts stay readable with a growing visible age). If
    persistence itself is unavailable (not a git repo, or a filesystem error) the
    fresh counts are still returned, with a warning — the refresh degrades, never
    hangs or crashes.
    """
    result = counts(transport, owner=owner, repo=repo)
    if result.get("status") != "ok":
        return result  # backend down — do NOT clobber the last good snapshot

    scope = f"{owner}/{repo}"
    data = dict(result["data"])
    warnings = list(result.get("warnings") or [])

    path = snapshot.snapshot_path(project_dir)
    if path is None:
        warnings.append("counts not persisted: not inside a git repository")
        data["persisted"] = False
        data["fetched_at"] = None
    else:
        written = snapshot.write(path, scope, result["data"], now=now)
        if written.get("status") == "written":
            data["persisted"] = True
            data["fetched_at"] = written.get("fetched_at")
        else:
            warnings.append(f"counts not persisted: {written.get('reason')}")
            data["persisted"] = False
            data["fetched_at"] = None
    return ok(data, warnings)


# --- helpers -----------------------------------------------------------------


def _decode_scope(issues: list[dict], owner: str, repo: str) -> tuple[list[dict], list[str]]:
    """Decode the in-scope (prawduct) issues; drop non-prawduct ones (PROV-2)."""
    items: list[dict] = []
    warnings: list[str] = []
    for issue in issues:
        if not encode.is_prawduct_issue(issue):
            continue
        canonical = f"{owner}/{repo}#{issue.get('number')}"
        item, decode_warnings = encode.decode_item(issue, canonical_id=canonical)
        items.append(item)
        warnings.extend(decode_warnings)
    return items, warnings


def _decode_unscoped(issues: list[dict], owner: str, repo: str) -> tuple[list[dict], list[str]]:
    """Decode only the issues :func:`_decode_scope` drops — the untriaged ones.

    Pull requests are excluded here as everywhere: they interleave the REST
    issues list and are never items, triaged or not. Decode advisories are not
    collected — an issue with no prawduct encoding cannot have a malformed one,
    so surfacing them would flag every ordinary GitHub issue as damaged.
    """
    items: list[dict] = []
    for issue in issues:
        if encode.is_pull_request(issue) or encode.is_prawduct_issue(issue):
            continue
        canonical = f"{owner}/{repo}#{issue.get('number')}"
        item, _decode_warnings = encode.decode_item(issue, canonical_id=canonical)
        items.append(item)
    return items, []


def all_issues(
    transport: Transport,
    owner: str,
    repo: str,
    *,
    state: str,
    labels: list[str] | None,
    assignee: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
    since: str | None = None,
) -> list[dict] | dict:
    """Fetch **every** matching issue across pages (for whole-set ops — ``pick``,
    ``counts``). Returns the issue list, or an error **envelope** to bubble up.

    A page-cap trip arrives as a ``TransportError`` from the shared paginator and
    converts to an envelope here like any other transport failure — so a scan
    that could not be completed reports as unavailable rather than as a short
    list, which ``counts`` would otherwise publish as a smaller backlog."""
    # Only pass the optional axes when set: `pick`/`counts` call this without
    # them, and a transport fake's `list_issues` need not accept sort/direction.
    extra = {
        key: value
        for key, value in (
            ("assignee", assignee),
            ("sort", sort),
            ("direction", direction),
            ("since", since),
        )
        if value is not None
    }
    try:
        return list(
            paginate(
                lambda page, size: transport.list_issues(
                    owner,
                    repo,
                    state=state,
                    labels=labels or None,
                    per_page=size,
                    page=page,
                    **extra,
                ),
                what="list scan",
            )
        )
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on list scan: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")


def _blocker_clause(blockers: list[dict]) -> str:
    """How the blocker predicate was satisfied — *verified clear* vs *nothing on
    file*, which are different facts and must not read alike.

    An empty native-dependency read means no dependency was ever recorded, not
    that the item was checked and found free. The distinction is load-bearing
    for a backlog migrated out of markdown: `related:` is carried in the issue
    body and mapped to no native edge, so every migrated item reads back zero
    dependencies permanently. Phrasing that as "no open blockers" would state a
    confident all-clear about a field the migration guarantees is empty.
    """
    if not blockers:
        return "no blockers recorded"
    n = len(blockers)
    return f"all {n} blocker{'s' if n != 1 else ''} closed"


def _why(item: dict, blockers: list[dict]) -> str:
    """A short, human/agent-readable reason this candidate is ready work.

    A candidate that reached here **with** a working branch was asked for
    explicitly, and its branch is named rather than the fact of it: naming the
    branch is what lets the reader decide whether the work is live or abandoned,
    which is the whole of the expiry policy this field replaced.
    """
    blocker_clause = _blocker_clause(blockers)
    branch = item.get("working_branch")
    if branch:
        return f"ready: stage:ready, being worked on {branch}, {blocker_clause}"
    return f"ready: stage:ready, no working branch, {blocker_clause}"
