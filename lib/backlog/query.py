"""Query — structured ``list``, ready-work ``pick``, and derived ``counts``.

The read side of the adapter (API §2.2). All three run **online off the REST
list endpoint** with **no cache** (Q1-structured, strongly consistent in
practice — a just-written item appears immediately; the rare brief post-create
window is handled by the caller's bounded settle-retry, ``core.get_item``).

- ``list_items`` — structured field/label filters + sort + paginate, one page as
  the caller requests. Applies the **PROV-2** filter: a plain repo issue carrying
  no prawduct marker is out-of-scope (ignored, not malformed).
- ``pick`` — stage-aware ready-work (Data Model §4): candidates are
  ``open ∧ stage:ready``, then a **per-candidate fan-out** applies the two
  predicates that are *not* list filters — "no open blockers" (native
  dependencies, read live so a cross-repo blocker is judged correctly) and "no
  **live** claim" (an assignee whose ``claimed_at`` is past the staleness TTL is
  reap-eligible, not a live claim). Returns ranked candidates each with a *why*.
- ``counts`` — per-project rollups derived **on read** (never persisted; the GV2
  briefing snapshot is a separate op, Chunk 04).

Layering: this module sits **above** ``core`` — it reuses core's envelope
(``ok``/``error``) and the ``pick --claim`` path delegates to ``core.claim`` so
the atomic take-and-verify lives in exactly one place. It never touches a model
(INV-1) and never shells out except through ``transport`` (the sole egress).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import encode
from .core import (
    DEFAULT_CLAIM_TTL_SECONDS,
    error,
    from_transport_error,
    log_diag,
    ok,
)
from .transport import Transport, TransportError

# The structured facets ``list`` accepts as label filters (each an AND term).
_LABEL_FACETS: tuple[str, ...] = ("stage", "kind", "area", "effort", "impact", "source")
_MAX_PAGES: int = 100  # runaway guard for the internal full-scan paginator


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
    """Structured, online ``list`` (Q1-structured). One page as requested.

    ``filters`` may carry ``status`` (two-axis: mapped to state + label, then
    refined on the decoded status because closed ``shipped``/``dropped`` differ
    only in ``state_reason`` which is not a list parameter), the label facets
    (``stage``/``kind``/``area``/``effort``/``impact``/``source``), ``assignee``
    (a login, ``none`` for unassigned, ``*`` for any), and an explicit ``state``
    (``open``/``closed``/``all``; default ``open``). Non-prawduct issues are
    dropped (PROV-2).

    The returned ``count`` is the number of in-scope items **on this page** (a
    ``status`` refinement can make it smaller than ``per_page`` even when more
    pages exist) — it is not a total, so drive pagination by requesting the next
    ``page`` until an *empty* page, not until ``count < per_page``.
    """
    filters = filters or {}
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
    return ok({"items": items, "count": len(items)}, warnings)


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
    assignee/TTL and blocker predicates are applied per candidate (a fan-out —
    the blocker states are read **live**, so a cross-repo blocker is judged
    correctly and never picked while open). Candidates rank fresh-unassigned
    before reap-eligible, then oldest issue first.

    With ``claim=True`` the top candidate is taken atomically via
    :func:`core.claim` (take-and-verify); a lost race returns ``claim_conflict``
    (non-fatal) so the caller re-picks.
    """
    now = now or datetime.now(timezone.utc)
    issues = _all_issues(transport, owner, repo, state="open", labels=["stage:ready"])
    if isinstance(issues, dict):  # an error envelope bubbled up from the fan-out
        return issues

    candidates: list[dict] = []
    warnings: list[str] = []
    for issue in issues:
        if not encode.is_prawduct_issue(issue):
            continue  # PROV-2
        number = issue.get("number")
        canonical = f"{owner}/{repo}#{number}"
        item, decode_warnings = encode.decode_item(issue, canonical_id=canonical)
        warnings.extend(decode_warnings)

        eligibility = _claim_eligibility(item, now, claim_ttl_seconds)
        if eligibility is None:
            continue  # a live claim — not ready work

        try:
            blockers = transport.list_blocked_by(owner, repo, number)
        except TransportError as exc:
            return from_transport_error(exc)
        except (OSError, json.JSONDecodeError) as exc:  # ERR-6
            log_diag(f"unexpected transport failure on pick fan-out: {type(exc).__name__}")
            return error("unavailable", "the backend request failed unexpectedly")
        open_blockers = [b["ref"] for b in blockers if b.get("state") != "closed"]
        if open_blockers:
            continue

        candidate = dict(item)
        candidate["reap_eligible"] = eligibility == "reap"
        candidate["why"] = _why(eligibility, item, now, claim_ttl_seconds)
        candidates.append(candidate)

    # Rank: prefer genuinely free work over reaping a stale claim, then oldest.
    candidates.sort(key=lambda c: (c["reap_eligible"], c.get("number") or 0))
    selected = candidates[: max(0, limit)]

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
    """Per-project rollups derived **on read** (Q5) — never persisted here."""
    issues = _all_issues(transport, owner, repo, state="all", labels=None)
    if isinstance(issues, dict):
        return issues

    by_status: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    total = 0
    warnings: list[str] = []
    for issue in issues:
        if not encode.is_prawduct_issue(issue):
            continue  # PROV-2
        item, decode_warnings = encode.decode_item(issue)
        warnings.extend(decode_warnings)
        total += 1
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
        stage_key = item["stage"] or "(none)"
        by_stage[stage_key] = by_stage.get(stage_key, 0) + 1

    data = {
        "repo": f"{owner}/{repo}",
        "total": total,
        "by_status": dict(sorted(by_status.items())),
        "by_stage": dict(sorted(by_stage.items())),
    }
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


def _all_issues(
    transport: Transport, owner: str, repo: str, *, state: str, labels: list[str] | None
) -> list[dict] | dict:
    """Fetch **every** matching issue across pages (for whole-set ops — ``pick``,
    ``counts``). Returns the issue list, or an error **envelope** to bubble up.
    Bounded by ``_MAX_PAGES`` so a pathological repo can never spin forever."""
    collected: list[dict] = []
    page = 1
    per_page = 100
    while page <= _MAX_PAGES:
        try:
            batch = transport.list_issues(
                owner, repo, state=state, labels=labels or None, per_page=per_page, page=page
            )
        except TransportError as exc:
            return from_transport_error(exc)
        except (OSError, json.JSONDecodeError) as exc:  # ERR-6
            log_diag(f"unexpected transport failure on list scan: {type(exc).__name__}")
            return error("unavailable", "the backend request failed unexpectedly")
        collected.extend(batch)
        if len(batch) < per_page:
            return collected
        page += 1
    log_diag(f"list scan hit the {_MAX_PAGES}-page cap; results truncated")
    return collected


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


def _why(eligibility: str, item: dict, now: datetime, ttl_seconds: int) -> str:
    """A short, human/agent-readable reason this candidate is ready work."""
    if eligibility == "reap":
        claimed_at = encode.parse_iso(item.get("claimed_at"))
        age_h = int((now - claimed_at).total_seconds() // 3600) if claimed_at else None
        who = item.get("assignee")
        aged = f"~{age_h}h" if age_h is not None else "past TTL"
        return f"ready: stage:ready, stale claim by {who} ({aged}), no open blockers"
    return "ready: stage:ready, unassigned, no open blockers"
