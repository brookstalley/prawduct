"""Core — deterministic CRUD and the return-value envelope (G1, API §3/§4).

Core holds all the operation logic; the CLI and MCP fronts are thin over it
(Test Specs §1.1). It **never** touches a model client (INV-1): no module under
``lib/backlog/`` imports or calls a model — the scrub's model step lives in the
skill/workflow layer, never here. Errors are **return-value based** (the project
convention): every op returns an envelope, never raises into a caller; the only
exceptions caught here are the boundary ``TransportError`` (expected transport
failures) and unexpected ``OSError``/``JSONDecodeError`` from the transport,
which are mapped and logged, never swallowed (ERR-6).

Implemented ops: ``file``, ``get``, the two-axis ``set-status`` transition,
``update`` (optimistic CAS + mass-assignment guard), ``comment``, ``link`` /
``unlink`` (typed relationship edges), and the minimal ``provision``. The read
side (``list`` / ``pick`` / ``counts``) lives in the sibling ``query`` module,
which reuses this module's envelope helpers.

**There is no ``claim`` op**, and its absence is a decision rather than a gap.
Taking an item used to mean assigning it and stamping an expiry, which needed a
TTL nobody could set well, a reap tier in the ranking, and a policy for a stamp
nobody refreshes. It is replaced by ``working-branch`` (a body-block field
``update`` writes like any other): if an item names a pushed branch, someone is
on it, and how alive that work is can be read from the branch itself instead of
inferred from a timestamp. ``assignee`` therefore returns to native/protected —
GitHub's own UI still assigns, and prawduct simply stops reading assignment as
meaning.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone

from . import encode, ids, issuefmt, provision
from .transport import RETRYABLE_DEFAULTS, Transport, TransportError, paginate

# --- The envelope (API §3/§4) ------------------------------------------------
#
# The stable error-code → `retryable` default table is owned by `transport`
# (`RETRYABLE_DEFAULTS`) — the single source of truth, imported here rather than
# copied, so the CLI-generated and transport-generated errors can never drift.


def ok(data, warnings: list[str] | None = None) -> dict:
    return {"status": "ok", "data": data, "warnings": warnings or []}


def error(
    code: str,
    message: str,
    *,
    retryable: bool | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable if retryable is not None else RETRYABLE_DEFAULTS.get(code, False),
            "details": details or {},
        },
    }


def from_transport_error(exc: TransportError) -> dict:
    return error(exc.code, exc.message, retryable=exc.retryable, details=exc.details)


#: A write path's local-mirror hook: ``(issue, owner, repo) -> None``. Named once
#: so the eight signatures that thread it agree by construction, and so a reader
#: binding one in Chunk 03 has a shape to bind against rather than a bare `absorb`.
Absorb = Callable[[dict, str, str], None]


def _mirror(absorb: Absorb | None, issue: dict, owner: str, repo: str) -> None:
    """Hand a just-written issue to the local mirror, if a caller bound one.

    **This module stays provider-only and never imports the store.** The write
    paths here are the only place an authoritative post-write issue exists — a
    create response, or the ``get_issue`` a status/field write ends on — so the
    mirror has to be *invoked* from here, but it does not have to be *known*
    here. An injected callback keeps the dependency pointing the right way and
    leaves every function below testable with no store on disk.

    ``owner``/``repo`` travel as arguments rather than being read back out of the
    issue JSON because the caller has already resolved them on ``nid``; deriving
    them again from ``repository_url`` would be a second, weaker spelling of a
    fact this module holds exactly."""
    if absorb is None:
        return
    absorb(issue, owner, repo)


def log_diag(message: str) -> None:
    print(f"backlog: {message}", file=sys.stderr)


# --- file --------------------------------------------------------------------

# The soft-enum facets `file` accepts as flags → their label facet name.
_FILE_FACETS: tuple[str, ...] = ("stage", "kind", "area", "effort", "impact", "source")


def file_item(
    transport: Transport,
    *,
    owner: str,
    repo: str,
    title: str,
    body: str,
    facets: dict[str, str] | None = None,
    automated: bool = False,
    worker: str | None = None,
    absorb: Absorb | None = None,
) -> dict:
    """Create one item (AG2): ``title`` + ``body`` suffice; every facet optional.

    Returns the new item's ID immediately (dedup is advisory-async and deferred).
    Attribution is the resolved **API identity** (SEC-3), never the git-push
    identity. New items default to ``open`` (no ``status:`` label — Data Model §4).

    When ``automated`` (an **unattended** run — Security §1a/SEC-6), the block is
    stamped ``automated: true`` + a ``worker`` marker so a background sweep is not
    misattributed to the human. The front resolves the unattended context (see
    ``context.py``); ``core`` just records what it is told.
    """
    facets = facets or {}
    if not title or not title.strip():
        return error("validation", "title is required")
    if body is None:
        return error("validation", "body is required (may be empty text, not omitted)")

    # Emit the §1 title shape (`area: summary`) before the create so the issue is
    # born standard-compliant (issue-standard §1). Idempotent; never fights a
    # title the author already prefixed.
    title = issuefmt.normalize_title(title, facets.get("area"))

    # The §1 title rules BLOCK (data model: every issue written to the backlog
    # store conforms, on every write path). Lint the NORMALIZED string, because
    # that is the one `create_issue` writes — linting the caller's argument would
    # judge a title that never reaches GitHub. Body and label lints stay WARN-only
    # below; only the title refuses.
    refusal = _title_refusal(title)
    if refusal is not None:
        return refusal

    warnings: list[str] = []
    labels: list[str] = []
    for facet in _FILE_FACETS:
        value = facets.get(facet)
        if value is None:
            continue
        check = encode.check_enum(facet, value)
        if not check.ok:
            return error("validation", check.message or f"invalid {facet}")
        if check.warning:
            warnings.append(check.warning)
        labels.append(f"{facet}:{value}")

    try:
        actor = transport.get_authenticated_user().get("login")
        # Provision the labels this create references, so the create never names a
        # non-existent label (the create is the authority; provisioning first is
        # correct regardless of GitHub's auto-create behavior).
        if labels:
            prov = provision.ensure_labels(transport, owner, repo, labels)
            warnings.extend(prov.warnings)
        full_body = _body_with_block(body, automated=automated, worker=worker)
        issue = transport.create_issue(
            owner, repo, title=title, body=full_body, labels=labels
        )
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6 — unexpected boundary
        log_diag(f"unexpected transport failure on file: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    _mirror(absorb, issue, owner, repo)
    canonical = f"{owner}/{repo}#{issue.get('number')}"
    item, decode_warnings = encode.decode_item(issue, canonical_id=canonical)
    warnings.extend(decode_warnings)
    item["actor"] = actor
    # Audit the created issue against the standard (§4). WARN-only — findings ride
    # in their own `lint` field (a distinct category from operational `warnings`),
    # never block, and reuse the shape the migration audit consumes. Lints the
    # *human* body (no prawduct: block) + the final labels.
    result = ok(item, warnings)
    result["lint"] = [f.as_dict() for f in issuefmt.lint(title, body, labels)]
    return result


def _title_refusal(title: str) -> dict | None:
    """The blocking half of the issue standard: a ``validation`` error when
    ``title`` fails any §1 rule, else ``None``.

    Shared by ``file`` and ``update`` so the two paths cannot drift into
    disagreeing about what a conforming title is — the norm binds *that* the
    rules are enforced, and `issuefmt` stays the one home for the rules
    themselves.

    The message names the failing rule AND echoes the title, because the caller
    on both these paths is an agent that has to decide what to write instead; a
    refusal it cannot act on just gets retried verbatim."""
    findings = issuefmt.lint_title(title)
    if not findings:
        return None
    detail = "; ".join(f"{f.rule}: {f.message}" for f in findings)
    return error(
        "validation",
        f"title does not conform to the issue standard §1 — {detail}. "
        f"Rewrite it and retry (got: {title!r})",
        details={
            "title": title,
            "rules": [f.rule for f in findings],
            "lint": [f.as_dict() for f in findings],
        },
    )


def _body_with_block(body: str, *, automated: bool = False, worker: str | None = None) -> str:
    """Append a minimal ``prawduct:`` block (``v: 1``) to the issue body.

    An unattended create stamps ``automated: true`` + a ``worker`` marker (CC4/
    SEC-6) so a background sweep is not misattributed to the human."""
    fields = {"v": "1"}
    if automated:
        fields["automated"] = "true"
        if worker:
            fields["worker"] = worker
    # The body↔block framing is shared with the importer via encode.compose_body,
    # so the two fresh-block writers can never diverge on separator/newline.
    return encode.compose_body(body, fields)


def _body_update_preserving_block(old_body: str, new_body: str) -> str:
    """Apply a caller's body edit while **preserving the existing ``prawduct:``
    block**.

    The block carries body-authoritative fields (``id_aliases``, ``verified``,
    ``superseded_by`` …) that live ONLY in the body (Data Model §2) — a naive
    full-body replacement would silently drop them (an MG2 / permanent-alias-loss
    footgun). So: merge EVERY block in the existing body, strip any block the
    caller pasted into the new text (the block is edited through its own fields,
    not free-text ``--body``), and re-append the preserved block. No existing
    block → a fresh ``v: 1`` (same as ``file``).

    **Merged, not re-parsed** — via :func:`encode.merge_all_block_fields`, the
    one home for how a writer reads a body's blocks. Using ``parse_block`` here
    kept only the LAST block while ``strip_block`` removed them all, so an
    ``update --body`` over a two-block body dropped the earlier block's
    ``id_aliases`` — the exact footgun this docstring names — and emitted one
    block, so the multi-block warning could never fire to signal it. Third site
    of that pairing found on one branch; the first two were in ``encode.py``,
    which is why bounding the class by MODULE missed this one.
    """
    fields = encode.merge_all_block_fields(old_body)
    human = encode.strip_block(new_body)
    rendered = encode.serialize_block(fields) if fields else encode.serialize_block({"v": "1"})
    if human:
        return f"{human}\n\n{rendered}\n"
    return f"{rendered}\n"


# --- get ---------------------------------------------------------------------


def get_item(
    transport: Transport,
    *,
    id_raw: str,
    default_owner: str | None = None,
    default_repo: tuple[str, str] | None = None,
    settle_retries: int = 0,
    sleeper=None,
) -> dict:
    """Fetch one item by any accepted ID spelling **or a hand-minted ``PFX`` alias**;
    decode into the item shape.

    A ``PFX`` (e.g. ``BKL-0QR1``) is resolved via its ``id:PFX`` alias label against
    ``default_repo`` (``--repo``); see :func:`resolve_ref` for the not-found /
    collision / no-repo verdicts. ``settle_retries`` handles the **observed** brief
    post-create replication window (QRY-1): reading *your own just-written item* can
    404 momentarily. It is opt-in and **only** for a read-your-own-write
    (a create's own verify read) — a plain ``get`` keeps ``settle_retries=0`` so a genuine
    not-found stays fast and the never-block floor is never diluted with retries on
    real absences.
    """
    try:
        nid = resolve_ref(
            transport, id_raw, default_owner=default_owner, default_repo=default_repo
        )
        if not nid.ok:
            return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")
        issue = _get_issue_settling(
            transport, nid.owner, nid.repo, nid.number, settle_retries, sleeper
        )
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on get: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    item, warnings = encode.decode_item(issue, canonical_id=nid.canonical)
    superseded = item.get("superseded_by")
    if superseded:
        # A merged-away source: follow the redirect chain so the caller learns
        # the survivor (BKL-5R2K — MG1's "old refs resolve forever" includes
        # resolving THROUGH a merge). The item itself is still returned — the
        # redirect is surfaced, not silently substituted; an unresolvable chain
        # degrades to no enrichment, never a failed get (ERR-6 posture).
        try:
            survivor = resolve_survivor(transport, nid.canonical, owner=nid.owner)
        except (TransportError, OSError, json.JSONDecodeError) as exc:  # ERR-6
            log_diag(f"redirect-follow failed on get: {type(exc).__name__}")
            survivor = None
        if survivor and survivor != nid.canonical:
            item["resolves_to"] = survivor
            warnings.append(
                f"{nid.canonical} was merged away — superseded by {survivor}"
            )
    return ok(item, warnings)


def resolve_survivor(transport: Transport, canonical: str, *, owner: str) -> str:
    """Follow a merged-away source to its survivor: read each hop's block
    ``superseded_by`` and chase it via :func:`ids.resolve_redirect` (bounded,
    cycle-safe — fail-open at the last resolvable node). The transport wiring
    for the pure redirect-follow (CRASH-2)."""

    def fetch(canon: str) -> str | None:
        nid = ids.normalize_id(canon, default_owner=owner)
        if not nid.ok:
            return None
        try:
            issue = transport.get_issue(nid.owner, nid.repo, nid.number)
        except TransportError:
            return None
        return encode.parse_block(issue.get("body")).superseded_by()

    return ids.resolve_redirect(canonical, fetch=fetch)


def _get_issue_settling(
    transport: Transport,
    owner: str,
    repo: str,
    number: int,
    settle_retries: int,
    sleeper,
) -> dict:
    """``get_issue`` with a bounded retry on ``not_found`` (the post-create
    replication window). Raises the last ``TransportError`` if it never settles."""
    sleep = sleeper if sleeper is not None else _default_settle_sleep
    attempt = 0
    while True:
        try:
            return transport.get_issue(owner, repo, number)
        except TransportError as exc:
            if exc.code == "not_found" and attempt < settle_retries:
                sleep(attempt)
                attempt += 1
                continue
            raise


def _default_settle_sleep(attempt: int) -> None:
    time.sleep(0.25 * (attempt + 1))


# --- ref resolution (spelling + PFX alias) -----------------------------------
#
# Every id-taking op normalizes its ``id_raw`` through here. A canonical/short
# spelling resolves purely (``ids.normalize_id``); a hand-minted ``PFX`` (e.g.
# ``BKL-0QR1``, minted by a source before migration) has no ``owner/repo#number``
# form, so it is resolved via its permanent ``id:PFX`` **alias label** — the read-
# path half of MG1's "a migrated item's original id stays a valid ref forever".


def resolve_ref(
    transport: Transport,
    id_raw: str,
    *,
    default_owner: str | None = None,
    default_repo: tuple[str, str] | None = None,
) -> "ids.NormalizedId":
    """Normalize ``id_raw`` to a canonical ``owner/repo#number``, resolving a hand-
    minted ``PFX`` alias via its ``id:PFX`` label when the plain spellings don't
    match (MG1). ``default_repo`` (``(owner, repo)``, from ``--repo``) is the repo a
    bare ``PFX`` is resolved against; absent it a ``PFX`` cannot resolve and is a
    ``validation`` error (never a silent guess). A ``PFX`` that matches no live item
    is ``not_found``; one that matches more than one is an ``alias_collision`` (the
    §5 uniqueness invariant broke — flag it, never pick one).

    A digit-suffix token (``ADR-12``) matches BOTH the shell ``repo-number``
    spelling and the PFX grammar. With ``default_repo`` present the alias is
    authoritative when an item carries it — an exact, uniqueness-checked match
    (MG1) beats a guess at a repo name — and the ``repo-number`` reading stands
    when no item does. The ``#`` spellings never match the PFX grammar, so
    ``repo#number`` / ``owner/repo#number`` are the unambiguous escape hatch.

    **Does a label search for any token that can be an alias** (with
    ``default_repo`` set), so it may raise ``TransportError`` — call it inside
    the caller's transport ``try``/``except`` (a ``#`` or ``/`` spelling does
    no I/O)."""
    nid = ids.normalize_id(id_raw, default_owner=default_owner)
    if nid.ok:
        if default_repo and ids.is_pfx(id_raw):
            # Both grammars match — alias-if-exists precedence (see docstring).
            owner, repo = default_repo
            verdict = _alias_verdict(transport, owner, repo, id_raw.strip())
            if verdict is not None:
                return verdict
        return nid
    if not ids.is_pfx(id_raw):
        # An unresolved token that isn't a PFX either — return normalize_id's
        # verdict verbatim (its error message is the right one).
        return nid
    pfx = id_raw.strip()
    if not default_repo:
        return ids.NormalizedId(
            canonical=None,
            error="validation",
            message=(
                f"hand-minted id {id_raw!r} needs a target repo to resolve — "
                "pass --repo owner/repo (or use its owner/repo#number id)"
            ),
        )
    owner, repo = default_repo
    verdict = _alias_verdict(transport, owner, repo, pfx)
    if verdict is None:
        return ids.NormalizedId(
            canonical=None,
            error="not_found",
            message=f"no item with alias {ids.alias_label(pfx)} in {owner}/{repo}",
        )
    return verdict


def _alias_verdict(
    transport: Transport, owner: str, repo: str, pfx: str
) -> "ids.NormalizedId | None":
    """The alias reading of ``pfx`` against ``owner/repo``: the canonical id of
    the unique item carrying ``id:PFX``, the ``alias_collision`` error when the
    §5 uniqueness invariant broke, or ``None`` when no item carries the alias
    (the caller decides whether that is ``not_found`` or a fallback)."""
    numbers = _numbers_for_alias(transport, owner, repo, pfx)
    if len(numbers) > 1:
        return ids.NormalizedId(
            canonical=None,
            error="alias_collision",
            message=(
                f"alias {ids.alias_label(pfx)} resolves to {len(numbers)} items "
                f"in {owner}/{repo} "
                f"({', '.join(f'#{n}' for n in numbers)}) — alias uniqueness violated"
            ),
        )
    if not numbers:
        return None
    number = numbers[0]
    return ids.NormalizedId(
        canonical=f"{owner}/{repo}#{number}", owner=owner, repo=repo, number=number
    )


def _numbers_for_alias(
    transport: Transport, owner: str, repo: str, pfx: str
) -> list[int]:
    """The issue numbers carrying the ``id:PFX`` alias label (all states — a
    migrated item may be closed). Exactly one on a healthy repo (§5)."""
    issues = transport.list_issues(
        owner, repo, state="all", labels=[ids.alias_label(pfx)], per_page=100, page=1
    )
    # A labeled PR must never resolve as the aliased item (BKL-5T3J — the raw
    # issues list interleaves PRs).
    return [
        issue["number"]
        for issue in issues
        if issue.get("number") is not None and not encode.is_pull_request(issue)
    ]


# --- status (set-status: the crash-safe two-axis transition) -----------------


def set_status(
    transport: Transport,
    *,
    id_raw: str,
    target: str,
    default_owner: str | None = None,
    default_repo: tuple[str, str] | None = None,
    absorb: Absorb | None = None,
) -> dict:
    """Idempotent, crash-safe two-axis status transition (Data Model §4 B1, CC1/M5).

    Canonical write order so a crashed client never half-writes:
      1. **state authority first** — for a *closed* target set closed +
         ``state_reason`` (that alone makes the decoded status correct even if steps
         2–3 never run); for an *open* target reopen if needed (clearing any stale
         close reason);
      2. **add** the target's ``status:`` label *before* removing any other — never a
         zero-label window (this step exists only for the open sub-states, whose one
         encoding is the label; ``open``/``shipped``/``dropped`` have no such label);
      3. remove every *other* ``status:`` label (the losers / stale sub-state).
    Each step is guarded (skipped when already satisfied), so a re-run — including
    the re-run after an injected mid-transition crash — is a no-op and converges.

    (For a closed target this reduces to state-first-then-strip-labels — there is no
    ``status:shipped``/``status:dropped`` label in the taxonomy, and the closed
    ``state_reason`` is the authority the decoder reads regardless of any transient
    label, so there is never an unreadable window. ``closed_by`` recording — native
    timeline handle + the manual ``--closed-by`` block stamp, Data Model §1.1 /
    API §2.6 — is deferred, tracked as a NOTE.)
    """
    if target not in encode.STATUS_VALUES:
        return error(
            "validation",
            f"unknown status {target!r}; expected one of {', '.join(encode.STATUS_VALUES)}",
        )

    target_state, target_reason, target_label = encode.encode_status(target)
    warnings: list[str] = []
    try:
        # A bare hand-minted PFX resolves via its id:PFX alias (a label search — I/O),
        # so resolution lives inside the transport try/except (MG1). A '#' or '/'
        # spelling does no I/O.
        nid = resolve_ref(transport, id_raw, default_owner=default_owner, default_repo=default_repo)
        if not nid.ok:
            return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")
        issue = transport.get_issue(nid.owner, nid.repo, nid.number)

        # Step 1 — move the state authority first.
        cur_state = (issue.get("state") or "open").lower()
        cur_reason = issue.get("state_reason")
        needs_state = cur_state != target_state or (
            target_state == "closed" and cur_reason != target_reason
        )
        if needs_state:
            # A close sets the reason; a (re)open clears any stale close reason.
            fields = {
                "state": target_state,
                "state_reason": target_reason if target_state == "closed" else None,
            }
            issue = transport.update_issue(nid.owner, nid.repo, nid.number, fields=fields)

        # Steps 2–3 — reconcile the status: labels toward the target: add the
        # target's label BEFORE removing any loser (never a zero-label window),
        # then strip the losers (remove is idempotent).
        present = encode.status_labels_present(encode.label_names(issue))
        to_add, to_remove = encode.reconcile_status_labels(present, target_label)
        for name in to_add:
            prov = provision.ensure_labels(transport, nid.owner, nid.repo, [name])
            warnings.extend(prov.warnings)
            transport.add_labels(nid.owner, nid.repo, nid.number, [name])
        for name in to_remove:
            transport.remove_label(nid.owner, nid.repo, nid.number, name)

        issue = transport.get_issue(nid.owner, nid.repo, nid.number)
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on status: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    _mirror(absorb, issue, nid.owner, nid.repo)
    item, decode_warnings = encode.decode_item(issue, canonical_id=nid.canonical)
    warnings.extend(decode_warnings)
    return ok(item, warnings)


# --- update (field-wise edit; optimistic CAS + mass-assignment guard) ---------

# The ONLY fields `update` may write (SEC-2 allowlist). `status` goes through
# set-status; native/protected fields — `assignee` among them — are never writable
# from request input.
#
# `assignee` was reachable once, through the retired `claim` op, and its return to
# this side of the line is deliberate: prawduct no longer reads assignment as
# meaning, so writing it would be prawduct asserting something it does not itself
# consult. GitHub's UI still assigns; `working-branch` is where prawduct records
# that someone is on an item.
_UPDATE_DIRECT: tuple[str, ...] = ("title", "body")
_UPDATE_FACETS: tuple[str, ...] = ("stage", "kind", "area", "effort", "impact", "source")

# A DELIBERATE WIDENING of the SEC-2 allowlist, in two new categories rather than
# three more facets — and the split is mechanical, not stylistic.
#
# `_UPDATE_FACETS` is a label *swap*: add the new value, strip every other label
# with the same prefix. That is exactly right for `area` (exactly-one, wired to
# the title) and exactly wrong for both new shapes. `tags` is the one facet that
# accumulates, so a swap would silently make setting a second tag remove the
# first; `affected` and `working-branch` are body-block fields, so routing them
# through the facet loop would write `affected:…` labels for data that has no
# label representation at all.
#
# Every field a caller may write still passes one allowlist check, which is the
# property SEC-2 rests on: reject off-list keys rather than ignoring them, so a
# mass-assignment attempt or a caller typo surfaces instead of being dropped.
_UPDATE_MULTI_FACETS: tuple[str, ...] = ("tags",)
_UPDATE_BLOCK_FIELDS: tuple[str, ...] = ("affected", "working-branch")

#: Domain field name → the `prawduct:` block key that carries it. The block's
#: keys are snake_case throughout and are additive-only-forever (Data Model §7),
#: so `working-branch` keeps its kebab spelling on the CLI and gets its snake one
#: in the body; this mapping is the single place the two meet on the write side
#: (`encode.Block.working_branch` is its read-side twin).
_BLOCK_KEY: dict[str, str] = {"affected": "affected", "working-branch": "working_branch"}


def _prepare_new_fields(fields: dict):
    """Validate ``affected`` / ``tags`` / ``working-branch`` offline.

    Returns ``(block_values, desired_tags, working_ref)`` or an **error
    envelope**. ``block_values`` maps each named block field to its formatted
    value (``None`` = clear the key); ``desired_tags`` is the whole intended tag
    set or ``None`` when the caller did not name ``tags``; ``working_ref`` is the
    parsed ``(owner, repo, branch)`` whose pushed-ness still has to be asked of
    the provider, or ``None``.

    ``None`` means *not named* everywhere here and an empty value means *clear* —
    the two are never conflated, because conflating them is how "unset this
    field" becomes a silent no-op.
    """
    block_values: dict[str, str | None] = {}
    working_ref: tuple[str, str, str] | None = None

    if "affected" in fields:
        entries, message = encode.validate_affected(encode.parse_list(fields["affected"] or ""))
        if message:
            return error("validation", message, details={"field": "affected"})
        block_values["affected"] = encode.format_list(entries) if entries else None

    if "working-branch" in fields:
        raw = (fields["working-branch"] or "").strip()
        if not raw:
            block_values["working-branch"] = None
        else:
            parsed = encode.parse_working_branch(raw)
            if parsed is None:
                return error(
                    "validation",
                    f"`working-branch` must be repo-qualified as owner/repo@branch "
                    f"(got {raw!r}) — the backlog repo and the code repo are not "
                    "necessarily the same one, so a bare branch name names nothing.",
                    details={"field": "working-branch"},
                )
            working_ref = parsed
            block_values["working-branch"] = raw

    desired_tags: list[str] | None = None
    if "tags" in fields:
        tags, message = encode.validate_tags(encode.parse_list(fields["tags"] or ""))
        if message:
            return error("validation", message, details={"field": "tags"})
        desired_tags = tags

    return block_values, desired_tags, working_ref


def update_item(
    transport: Transport,
    *,
    id_raw: str,
    fields: dict,
    expected_updated_at: str | None = None,
    default_owner: str | None = None,
    default_repo: tuple[str, str] | None = None,
    absorb: Absorb | None = None,
) -> dict:
    """Field-wise edit with optimistic CAS (CC2) and a mass-assignment guard (SEC-2).

    Writes **only** the documented item fields the caller named — ``title``,
    ``body``, the soft-enum facets (``stage``/``kind``/``area``/``effort``/
    ``impact``/``source``), the multi-valued ``tags``, and the block-authoritative
    ``affected`` / ``working-branch``. ``status`` goes through set-status,
    and ``assignee`` is not writable at all; any other key — a native/protected field
    (``node_id``, ``number``, ``state``, ``history``), an ``automated:`` marker,
    foreign attribution — is **rejected**, never written from request input
    (attribution comes only from the API identity). When ``expected_updated_at``
    is supplied, a live ``updated_at`` mismatch returns a **retryable
    ``conflict``** (the lost-update guard) so the caller re-reads and retries.

    ``tags`` sets the **whole** tag set (missing ones added, absent ones stripped)
    rather than appending, because that is the only semantics under which a
    caller can *remove* a tag; ``tags=`` clears them. ``affected=`` and
    ``working-branch=`` likewise clear their block keys.
    """
    if not fields:
        return error("validation", "update requires at least one field to change")
    # SEC-2 — reject any field off the allowlist. Reject (not silently ignore) so a
    # mass-assignment attempt or a caller typo is surfaced, never quietly dropped.
    allowed = (
        set(_UPDATE_DIRECT)
        | set(_UPDATE_FACETS)
        | set(_UPDATE_MULTI_FACETS)
        | set(_UPDATE_BLOCK_FIELDS)
    )
    rejected = sorted(key for key in fields if key not in allowed)
    if rejected:
        return error(
            "validation",
            f"update cannot write field(s) {rejected}; writable fields are {sorted(allowed)}",
            details={"rejected": rejected},
        )

    # The §1 title rules block on the title BEING WRITTEN — not on the issue's
    # resulting title (owner ruling 2026-08-06). Checked before any I/O: a
    # refusal should cost no round-trip.
    #
    # The narrow scope is load-bearing, not a softening. An AGENT is at this
    # write — nothing automated calls `update` — so gating every field on the
    # stored title would not block the ~11% of live issues that predate the rule;
    # it would make an agent silently RETITLE them to get past the gate, one at a
    # time, as a side effect of archiving them, with none of the aggregate owner
    # approval the import scrub keeps. That breaches the norm's own
    # `Retroactivity: contain` — the containment boundary is the write path —
    # and it is the confirmation-fatigue shape `security-model.md` rejects.
    if "title" in fields:
        refusal = _title_refusal(fields["title"] or "")
        if refusal is not None:
            return refusal

    # Same discipline for the three new fields: everything decidable without the
    # network is decided here, so a malformed value costs no round-trip. The one
    # question that cannot be answered offline — is this branch actually pushed —
    # waits until the transport try below.
    prepared = _prepare_new_fields(fields)
    if isinstance(prepared, dict):
        return prepared
    block_values, desired_tags, working_ref = prepared

    warnings: list[str] = []
    try:
        # A bare hand-minted PFX resolves via its id:PFX alias inside the transport
        # try (a label search — I/O); a '#' or '/' spelling does no I/O (MG1).
        nid = resolve_ref(transport, id_raw, default_owner=default_owner, default_repo=default_repo)
        if not nid.ok:
            return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")
        issue = transport.get_issue(nid.owner, nid.repo, nid.number)

        # CC2 — optimistic CAS on updated_at (only when the caller supplied one).
        if expected_updated_at is not None and issue.get("updated_at") != expected_updated_at:
            return error(
                "conflict",
                "the item changed since you last read it; re-fetch and retry",
                details={
                    "expected_updated_at": expected_updated_at,
                    "actual_updated_at": issue.get("updated_at"),
                },
            )

        # The pushed-ref check (Cache Spec §3): `working-branch` names a branch
        # another agent can go and look at, so an unpublished one is an invisible
        # claim of the item — the single failure the field exists to prevent. Asked before the
        # PATCH so a refusal leaves the item untouched.
        if working_ref is not None:
            branch_owner, branch_repo, branch_name = working_ref
            if not transport.branch_exists(branch_owner, branch_repo, branch_name):
                return error(
                    "validation",
                    f"`working-branch` must name a PUSHED branch, and "
                    f"{branch_owner}/{branch_repo}@{branch_name} is not on the remote. "
                    "Push the branch, then set the field — do not rename the branch or "
                    "point the field at a different one to get past this.",
                    details={"repo": f"{branch_owner}/{branch_repo}", "branch": branch_name},
                )

        # Direct fields — one PATCH; labels are untouched by this. A body edit
        # preserves the existing prawduct: block (block-authoritative fields live
        # only in the body — Data Model §2); other direct fields pass through.
        patch: dict = {k: fields[k] for k in _UPDATE_DIRECT if k in fields and k != "body"}
        # The block-authoritative fields ride the SAME body, layered on top of any
        # `--body` edit in this call rather than beside it: two `patch["body"]`
        # writers would mean the last one wins and the other's edit is lost.
        new_body = None
        if "body" in fields:
            new_body = _body_update_preserving_block(issue.get("body") or "", fields["body"])
        for name, value in block_values.items():
            base = new_body if new_body is not None else (issue.get("body") or "")
            new_body = encode.upsert_block_field(base, _BLOCK_KEY[name], value)
        # Only PATCH a body that actually changed — clearing a field that was
        # never set would otherwise spend a write and bump `updated_at`, and that
        # stamp is not inert: it is the sync watermark and the CAS comparand, so a
        # no-op write makes the item look edited to every later reader.
        if new_body is not None and new_body != (issue.get("body") or ""):
            patch["body"] = new_body
        if patch:
            issue = transport.update_issue(nid.owner, nid.repo, nid.number, fields=patch)

        # Facet edits — each is a label swap (add the new value before removing the
        # old, same never-empty-window discipline as set-status). Facets are
        # independent prefixes, so each reads its own present set off `issue`.
        for facet in _UPDATE_FACETS:
            if facet not in fields:
                continue
            value = fields[facet]
            check = encode.check_enum(facet, value)
            if not check.ok:
                return error("validation", check.message or f"invalid {facet}")
            if check.warning:
                warnings.append(check.warning)
            new_label = f"{facet}:{value}"
            present = [n for n in encode.label_names(issue) if n.startswith(f"{facet}:")]
            if new_label not in present:
                prov = provision.ensure_labels(transport, nid.owner, nid.repo, [new_label])
                warnings.extend(prov.warnings)
                transport.add_labels(nid.owner, nid.repo, nid.number, [new_label])
            for old in present:
                if old != new_label:
                    transport.remove_label(nid.owner, nid.repo, nid.number, old)

        # Tags — a set reconciliation, not a swap. `desired_tags` is the whole
        # intended set, so what is missing is added and what is absent is
        # stripped; that is the only shape under which a caller can remove one.
        # Add before remove, the same never-empty-window discipline as above.
        if desired_tags is not None:
            prefix = f"{encode.TAG_FACET}:"
            present_tags = [n for n in encode.label_names(issue) if n.startswith(prefix)]
            wanted = [f"{prefix}{value}" for value in desired_tags]
            to_add = [name for name in wanted if name not in present_tags]
            if to_add:
                prov = provision.ensure_labels(transport, nid.owner, nid.repo, to_add)
                warnings.extend(prov.warnings)
                transport.add_labels(nid.owner, nid.repo, nid.number, to_add)
            for old in present_tags:
                if old not in wanted:
                    transport.remove_label(nid.owner, nid.repo, nid.number, old)

        issue = transport.get_issue(nid.owner, nid.repo, nid.number)
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on update: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    _mirror(absorb, issue, nid.owner, nid.repo)
    item, decode_warnings = encode.decode_item(issue, canonical_id=nid.canonical)
    warnings.extend(decode_warnings)

    # An update that did NOT write a title still REPORTS a stored title that fails
    # §1 — advisory, never blocking (see the ruling above). Advice failing soft is
    # not advice failing silent: the finding names the rule, and the line beside it
    # names the consequence, so a reader is not left inferring whether this write
    # quietly fixed the title. It did not, deliberately.
    #
    # Accrued BEFORE `ok()`, which snapshots the list — appending afterwards
    # reaches nobody. (Found by the test below, which is the third time on this
    # branch that enriching one exit path missed the constructor building it.)
    stored_findings: list = []
    if "title" not in fields:
        stored_findings = issuefmt.lint_title((issue.get("title") or "").strip())
        if stored_findings:
            warnings.append(
                f"this item's stored title does not conform to the issue standard §1 "
                f"({', '.join(f.rule for f in stored_findings)}) — NOT changed by this update; "
                "retitle it deliberately with `update <id> title=...` if it matters"
            )

    result = ok(item, warnings)
    if stored_findings:
        result["lint"] = [f.as_dict() for f in stored_findings]
    return result


# --- comment -----------------------------------------------------------------


def comment_item(
    transport: Transport,
    *,
    id_raw: str,
    body: str,
    default_owner: str | None = None,
    default_repo: tuple[str, str] | None = None,
) -> dict:
    """Add a native, attributed comment (DM5). Not idempotent. Attribution is the
    **API identity** (GitHub stamps the authenticated user), never caller-supplied.
    """
    if not body or not body.strip():
        return error("validation", "comment body is required")
    try:
        # A bare hand-minted PFX resolves via its id:PFX alias inside the transport
        # try (a label search — I/O); a '#' or '/' spelling does no I/O (MG1).
        nid = resolve_ref(transport, id_raw, default_owner=default_owner, default_repo=default_repo)
        if not nid.ok:
            return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")
        comment = transport.create_comment(nid.owner, nid.repo, nid.number, body=body)
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on comment: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    data = {
        "id": comment.get("id"),
        "item": nid.canonical,
        "url": comment.get("html_url"),
        "actor": (comment.get("user") or {}).get("login"),
    }
    return ok(data)


# --- link / unlink (typed relationship edges) --------------------------------

# The typed edges `link`/`unlink` set (API §2.3). `blocks`/`blocked-by` are native
# dependencies (so a blocker is queryable — DM3, the ready-work predicate);
# `parent`/`child` are native sub-issues; `related` has no native GitHub edge, so
# it lives in the block as a `related: [ids]` list (block-authoritative, Data
# Model §2 — parallel to `id_aliases`).
_EDGE_TYPES: tuple[str, ...] = ("blocks", "blocked-by", "parent", "child", "related")


def link(
    transport: Transport,
    *,
    id_raw: str,
    edge: str,
    target_raw: str,
    default_owner: str | None = None,
    default_repo: tuple[str, str] | None = None,
    absorb: Absorb | None = None,
) -> dict:
    """Set a typed edge from an item to a target (idempotent). ``edge`` is one of
    ``blocks``/``blocked-by``/``parent``/``child``/``related``. Either endpoint may
    be a hand-minted ``PFX`` alias, resolved against ``default_repo`` (``--repo``)."""
    return _mutate_edge(
        transport, id_raw, edge, target_raw, default_owner, default_repo, add=True, absorb=absorb
    )


def unlink(
    transport: Transport,
    *,
    id_raw: str,
    edge: str,
    target_raw: str,
    default_owner: str | None = None,
    default_repo: tuple[str, str] | None = None,
    absorb: Absorb | None = None,
) -> dict:
    """Clear a typed edge from an item to a target (idempotent)."""
    return _mutate_edge(
        transport, id_raw, edge, target_raw, default_owner, default_repo, add=False, absorb=absorb
    )


def _mutate_edge(
    transport: Transport,
    id_raw: str,
    edge: str,
    target_raw: str,
    default_owner: str | None,
    default_repo: tuple[str, str] | None,
    *,
    add: bool,
    absorb: Absorb | None = None,
) -> dict:
    if edge not in _EDGE_TYPES:
        return error(
            "validation",
            f"unknown edge {edge!r}; expected one of {', '.join(_EDGE_TYPES)}",
        )
    try:
        nid = resolve_ref(
            transport, id_raw, default_owner=default_owner, default_repo=default_repo
        )
        if not nid.ok:
            return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")
        tid = resolve_ref(
            transport, target_raw, default_owner=default_owner, default_repo=default_repo
        )
        if not tid.ok:
            return error(
                tid.error or "validation", tid.message or f"bad target ID {target_raw!r}"
            )
        if nid.canonical == tid.canonical:
            return error("validation", "an item cannot be linked to itself")

        if edge == "blocked-by":
            _dep(transport, nid, tid, add=add)
        elif edge == "blocks":
            # A blocks B ⇔ B is blocked-by A.
            _dep(transport, tid, nid, add=add)
        elif edge == "parent":
            # target is the parent ⇒ this item is target's sub-issue.
            _sub(transport, tid, nid, add=add)
        elif edge == "child":
            _sub(transport, nid, tid, add=add)
        else:  # related — block-list machinery
            # The ONLY edge the cache holds anything for. `blocks`/`blocked-by`
            # and `parent`/`child` are native GitHub edges with no column and no
            # index here — `pick` reads dependencies live, permanently — so
            # mirroring them would be mirroring nothing. `related` lives in the
            # body block, which the store does hold and index.
            written = _related(transport, nid, tid.canonical, add=add)
            if written is not None:
                _mirror(absorb, written, nid.owner, nid.repo)
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        verb = "link" if add else "unlink"
        log_diag(f"unexpected transport failure on {verb}: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    return ok(
        {"item": nid.canonical, "edge": edge, "target": tid.canonical, "linked": add}
    )


def _dep(transport: Transport, blocked, blocker, *, add: bool) -> None:
    """Add/remove a native dependency: ``blocked`` is blocked-by ``blocker``."""
    fn = transport.add_blocked_by if add else transport.remove_blocked_by
    fn(
        blocked.owner,
        blocked.repo,
        blocked.number,
        blocker_owner=blocker.owner,
        blocker_repo=blocker.repo,
        blocker_number=blocker.number,
    )


def _sub(transport: Transport, parent, child, *, add: bool) -> None:
    """Add/remove a native sub-issue edge: ``child`` under ``parent``."""
    fn = transport.add_sub_issue if add else transport.remove_sub_issue
    fn(
        parent.owner,
        parent.repo,
        parent.number,
        child_owner=child.owner,
        child_repo=child.repo,
        child_number=child.number,
    )


def _related(transport: Transport, nid, target_canonical: str, *, add: bool) -> dict | None:
    """Add/remove a ``related`` ref in the item's block list (no native edge).

    Returns the **updated issue** when a write happened, else ``None`` — an
    idempotent no-op has nothing for a caller to mirror, and returning the
    unchanged issue would make one look like a write."""
    issue = transport.get_issue(nid.owner, nid.repo, nid.number)
    # Read through the WRITER's view, not `parse_block`'s. The write below
    # merges every block, but a value computed from a last-block-wins read would
    # then overwrite the merged-in earlier one — so a body whose EARLIER block
    # carries `related` and whose later block does not would lose those edges,
    # silently, the same shape the writers were just fixed for. Reading and
    # writing may disagree (`parse_block` says why); a read-modify-WRITE may not
    # disagree with itself.
    fields = encode.merge_all_block_fields(issue.get("body"))
    current = set(encode.parse_list(fields.get("related")))
    if add:
        current.add(target_canonical)
    else:
        current.discard(target_canonical)
    value = encode.format_list(sorted(current)) if current else None
    old_body = issue.get("body") or ""
    new_body = encode.upsert_block_field(old_body, "related", value)
    if new_body == old_body:
        return None
    return transport.update_issue(nid.owner, nid.repo, nid.number, fields={"body": new_body})


# --- alias self-heal (id:PFX label ↔ block id_aliases drift) -----------------
#
# The permanent ``id:PFX`` label is both the read-resolution key and the import
# skip-authority, but a human can delete a per-issue label. The block
# ``id_aliases`` field is the durable record of the same alias, so it is the
# recovery source: this scan pairs every block-recorded PFX with the issue that
# carries it, letting the importer skip-not-duplicate (``migrate._find_by_key``)
# and ``reconcile-labels`` restore a deleted label — both keyed off one scan.


def iter_alias_issues(transport: Transport, owner: str, repo: str):
    """Yield ``(number, pfxs, label_names, status)`` for every issue in the repo (all
    states, paginated): ``pfxs`` are the well-formed hand-minted ids recorded in the
    body block ``id_aliases``; ``label_names`` are the issue's current label names
    (so a caller can tell whether the matching ``id:PFX`` label is present); ``status``
    is the **decoded** status. Raises ``TransportError`` on a transport failure
    (caught at each caller's boundary), including a page-cap trip — an alias scan
    that stopped early would report an existing item as missing, which is the
    opposite of the skip-not-duplicate guarantee it exists to provide.

    **Why the decoded status and not the raw ``state``.** The completeness gate has
    to answer "is this item on the target *at the status the source says it should
    be*", and reconstructing that from ``state`` means re-implementing the decoder's
    rules — closed + ``state_reason``, open sub-state labels — at a second site,
    where they can drift from :func:`encode.decode_status`. Yielding it costs
    nothing: this scan already fetches with ``state="all"`` and already parses each
    body, so the state and labels the decode needs are in hand and were previously
    discarded. Decode advisories (a torn or unrecognized encoding) are *not*
    surfaced here — this is a coverage scan, not a decoder audit, and the decode
    fails open to a safe value by design.
    """
    issues = paginate(
        lambda page, size: transport.list_issues(
            owner, repo, state="all", per_page=size, page=page
        ),
        what="alias scan",
    )
    for issue in issues:
        if encode.is_pull_request(issue):
            continue  # PRs interleave the raw issues list (BKL-5T3J)
        number = issue.get("number")
        if number is None:
            continue
        block = encode.parse_block(issue.get("body"))
        pfxs = [pfx for pfx in block.id_aliases() if ids.is_pfx(pfx)]
        label_names = {
            name for label in issue.get("labels", []) if (name := label.get("name"))
        }
        status, _decode_warnings = encode.decode_status(issue, sorted(label_names))
        yield number, pfxs, label_names, status


# --- provision ---------------------------------------------------------------


def provision_labels(transport: Transport, *, owner: str, repo: str) -> dict:
    """Create/reconcile the base namespaced taxonomy (minimal — PROV-1)."""
    try:
        result = provision.ensure_labels(
            transport, owner, repo, provision.base_labels()
        )
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on provision: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    data = {
        "repo": f"{owner}/{repo}",
        "created": result.created,
        "existing": result.existing,
    }
    return ok(data, result.warnings)


def reconcile_labels(transport: Transport, *, owner: str, repo: str) -> dict:
    """Reconcile the full namespaced taxonomy (GV6): create any missing base
    label, leave every existing/foreign label untouched, **re-derive any deleted
    per-issue ``id:PFX`` alias label from the durable block ``id_aliases``**, and
    report the coexistence picture. Idempotent and collision-free — drift is
    corrected by *adding* what is missing, never by removing (Data Model §3, PROV-1,
    DM7). The alias restore keeps MG1's "a migrated id resolves forever" true even
    after a human deletes an alias label (the same drift the importer self-heals)."""
    try:
        result = provision.reconcile(transport, owner, repo)
        restored = _restore_alias_labels(transport, owner, repo)
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on reconcile-labels: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    data = {
        "repo": f"{owner}/{repo}",
        "created": result.created,
        "existing": result.existing,
        "foreign_untouched": result.foreign_untouched,
        "aliases_restored": restored,
    }
    return ok(data, result.warnings)


def _restore_alias_labels(transport: Transport, owner: str, repo: str) -> list[str]:
    """Re-add any ``id:PFX`` alias label that the block ``id_aliases`` records but
    the issue no longer carries (a human deleted it). Add-only (ensures the label
    definition, then adds it to the issue); returns the ``owner/repo#n → id:PFX``
    restorations made. A repo with no drift restores nothing (idempotent)."""
    restored: list[str] = []
    for number, pfxs, label_names, _status in iter_alias_issues(transport, owner, repo):
        for pfx in pfxs:
            label = ids.alias_label(pfx)
            if label in label_names:
                continue  # the alias label is present — nothing to restore
            provision.ensure_labels(transport, owner, repo, [label])
            transport.add_labels(owner, repo, number, [label])
            restored.append(f"{owner}/{repo}#{number} → {label}")
    return restored
