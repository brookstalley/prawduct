"""Query — structured ``list``, ready-work ``pick``, and derived ``counts``.

The read side of the adapter (API §2.2). All three run **online off the REST
list endpoint** with **no cache** (Q1-structured, strongly consistent in
practice — a just-written item appears immediately; the rare brief post-create
window is handled by the caller's bounded settle-retry, ``core.get_item``).

- ``list_items`` — structured field/label filters + sort + paginate, one page as
  the caller requests. Applies the **PROV-2** filter: a plain repo issue carrying
  no prawduct marker is out-of-scope (ignored, not malformed).
- ``pick`` — stage-aware ready-work (Data Model §4): candidates are
  ``open ∧ stage:ready``, then two predicates that are *not* list filters are
  applied — "no **live** claim" (an assignee whose ``claimed_at`` is past the
  staleness TTL is reap-eligible, not a live claim), which is free once the item
  is decoded, and the blocker predicate (native dependencies, read live so a
  cross-repo blocker is judged correctly), which costs one REST read per issue.
  The claim predicate and the ranking are therefore resolved first, and the
  dependency **fan-out is taken lazily down the ranking**, stopping at ``limit``.
  Returns ranked candidates each with a *why* that distinguishes *no
  dependencies recorded* from *all recorded dependencies closed*.
- ``counts`` — per-project rollups derived **on read** (never persisted; the GV2
  briefing snapshot in :mod:`snapshot` is a separate op).

Layering: this module sits **above** ``core`` — it reuses core's envelope
(``ok``/``error``) and the ``pick --claim`` path delegates to ``core.claim`` so
the atomic take-and-verify lives in exactly one place. It never touches a model
(INV-1) and never shells out except through ``transport`` (the sole egress).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import encode, snapshot
from .core import (
    DEFAULT_CLAIM_TTL_SECONDS,
    error,
    from_transport_error,
    log_diag,
    ok,
)
from .transport import Transport, TransportError, paginate

# The structured facets ``list`` accepts as label filters (each an AND term).
_LABEL_FACETS: tuple[str, ...] = ("stage", "kind", "area", "effort", "impact", "source")


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
    (``stage``/``kind``/``area``/``effort``/``impact``/``source``), ``assignee``
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
        issues = _all_issues(
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
    owner: str,
    repo: str,
    limit: int = 1,
    claim: bool = False,
    claim_ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
    now: datetime | None = None,
    default_owner: str | None = None,
) -> dict:
    """Ready-work ``pick`` (GV1/DM3/CC3): the correct set, ranked, with a *why*.

    Ready-work = ``open ∧ stage:ready ∧ (unassigned ∨ claim past TTL) ∧ all
    blockers closed``. The first two predicates are REST list filters; the
    assignee/TTL predicate is applied per decoded item (cheap, no I/O); the
    blocker predicate is a per-issue REST fan-out whose states are read **live**,
    so a cross-repo blocker is judged correctly and never picked while open.

    Candidates rank fresh-unassigned before reap-eligible, then oldest issue
    first — **and the ranking is computed before the fan-out runs**, so the
    dependency reads are taken lazily down the ranking and stop once ``limit``
    is filled. Ranking is independent of blocker state, so the result set is the
    same either way; the ordering matters only for cost, which is otherwise one
    REST call per eligible issue on every call regardless of ``limit``.

    A candidate's ``why`` distinguishes *no dependencies recorded* from *all
    recorded dependencies closed* — see :func:`_blocker_clause` for why that
    distinction is not cosmetic.

    With ``claim=True`` the top candidate is taken atomically via
    :func:`core.claim` (take-and-verify); a lost race returns ``claim_conflict``
    (non-fatal) so the caller re-picks.
    """
    now = now or datetime.now(timezone.utc)
    issues = _all_issues(transport, owner, repo, state="open", labels=["stage:ready"])
    if isinstance(issues, dict):  # an error envelope bubbled up from the fan-out
        return issues

    eligible: list[tuple[str, int, dict]] = []
    warnings: list[str] = []
    for issue in issues:
        if not encode.is_prawduct_issue(issue):
            continue  # PROV-2
        number = issue.get("number")
        canonical = f"{owner}/{repo}#{number}"
        item, decode_warnings = encode.decode_item(issue, canonical_id=canonical)
        warnings.extend(decode_warnings)

        if item.get("superseded_by"):
            # Open-but-redirected: the CRASH-2 window between a merge's redirect
            # write and its close. The item is merged-away — never ready work
            # (BKL-5R2K); the merge re-run converges it to closed.
            continue

        eligibility = _claim_eligibility(item, now, claim_ttl_seconds)
        if eligibility is None:
            continue  # a live claim — not ready work

        candidate = dict(item)
        candidate["reap_eligible"] = eligibility == "reap"
        eligible.append((eligibility, number, candidate))

    # Rank: prefer genuinely free work over reaping a stale claim, then oldest.
    eligible.sort(key=lambda e: (e[2]["reap_eligible"], e[1] or 0))

    # Then read dependencies lazily, in rank order, stopping once `limit` is
    # filled. The ranking key does not depend on blocker state, so filtering
    # before ranking (the previous shape) and ranking before filtering yield the
    # identical result set — but this pays one dependency read per *selected*
    # candidate instead of one per *eligible* one. That difference is the whole
    # cost of `pick` on a large backlog: the reads are a per-issue REST fan-out,
    # so the old shape charged the full backlog size on every call no matter how
    # small the requested limit.
    #
    # One deliberate semantic change rides along: a dependency read that fails
    # now surfaces only if `pick` actually needed that candidate. Previously any
    # eligible issue's unreachable dependency failed the whole call, including
    # issues ranked far below anything that would be returned. Failing the call
    # over an item the caller was never going to see is worse than not looking —
    # the predicate is still never *assumed* for a candidate that is returned,
    # which is the property that matters.
    candidates: list[dict] = []
    want = max(0, limit)
    for eligibility, number, candidate in eligible:
        if len(candidates) >= want:
            break
        try:
            blockers = transport.list_blocked_by(owner, repo, number)
        except TransportError as exc:
            return from_transport_error(exc)
        except (OSError, json.JSONDecodeError) as exc:  # ERR-6
            log_diag(f"unexpected transport failure on pick fan-out: {type(exc).__name__}")
            return error("unavailable", "the backend request failed unexpectedly")
        if any(b.get("state") != "closed" for b in blockers):
            continue  # an open blocker — not ready work

        candidate["why"] = _why(eligibility, candidate, now, claim_ttl_seconds, blockers)
        candidates.append(candidate)

    selected = candidates

    if claim and selected:
        from . import core  # local import — query sits above core

        top = selected[0]
        claim_result = core.claim(
            transport,
            id_raw=top["id"],
            now=now,
            claim_ttl_seconds=claim_ttl_seconds,
            default_owner=default_owner,
        )
        if claim_result.get("status") != "ok":
            return claim_result  # claim_conflict / error surfaces for a re-pick
        # Refresh the candidate with the post-claim item (fresh assignee +
        # claimed_at), keeping the ranking annotations (why/reap_eligible).
        top.update(claim_result.get("data") or {})
        top["claimed"] = True

    return ok({"candidates": selected, "count": len(selected)}, warnings)


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
    issues = _all_issues(transport, owner, repo, state="all", labels=None)
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


def _all_issues(
    transport: Transport,
    owner: str,
    repo: str,
    *,
    state: str,
    labels: list[str] | None,
    assignee: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
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
        for key, value in (("assignee", assignee), ("sort", sort), ("direction", direction))
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


def _claim_eligibility(item: dict, now: datetime, ttl_seconds: int) -> str | None:
    """Is a ready candidate takeable? ``"free"`` (unassigned), ``"reap"`` (a claim
    aged past the TTL), or ``None`` (a live claim — not ready work).

    An assignee with **no** ``claimed_at`` stamp is treated as a live claim (a
    human/UI assignment we cannot age) — never reaped out from under it.
    """
    if not item.get("assignee"):
        return "free"
    claimed_at = encode.parse_iso(item.get("claimed_at"))
    if claimed_at is None:
        return None
    if (now - claimed_at).total_seconds() > ttl_seconds:
        return "reap"
    return None


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


def _why(
    eligibility: str,
    item: dict,
    now: datetime,
    ttl_seconds: int,
    blockers: list[dict],
) -> str:
    """A short, human/agent-readable reason this candidate is ready work."""
    blocker_clause = _blocker_clause(blockers)
    if eligibility == "reap":
        claimed_at = encode.parse_iso(item.get("claimed_at"))
        age_h = int((now - claimed_at).total_seconds() // 3600) if claimed_at else None
        who = item.get("assignee")
        aged = f"~{age_h}h" if age_h is not None else "past TTL"
        return f"ready: stage:ready, stale claim by {who} ({aged}), {blocker_clause}"
    return f"ready: stage:ready, unassigned, {blocker_clause}"
