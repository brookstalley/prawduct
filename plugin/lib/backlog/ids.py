"""Identifier normalization — the four accepted spellings → canonical form.

The canonical item identifier is GitHub's own cross-reference syntax
``owner/repo#number`` (Data Model §5, API §8). Consumers may pass any of four
spellings and the adapter normalizes on the way in (API §3):

- ``owner/repo#number``  — canonical
- ``repo#number``        — short, same-owner (needs a ``default_owner``)
- ``repo/number``        — shell-friendly (no ``#`` to escape)
- ``repo-number``        — shell-friendly

Short/shell-friendly forms carry no owner, so they resolve **same-owner only**
and require a ``default_owner`` (the target repo's owner). Absent one they are a
``validation`` error rather than a silent guess.

This module is a **pure, function-level seam** (Test Specs §2.1): no transport,
no I/O. It also holds the **PFX-alias & redirect machinery** the importer uses
(D4/DM4/§5): the pure label helpers (``alias_label``/``pfx_from_alias_label``)
and the redirect-follow (``resolve_redirect``) whose GitHub lookup is **injected**
as a callback — so the module stays transport-free while still owning the
resolution *logic*. The spelling→canonical normalization (ID-1) is above.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A GitHub owner or repo segment: letters, digits, hyphen, underscore, dot.
# (GitHub is stricter still, but this is the adapter's tolerant input gate — the
# real existence check happens at the transport, not here.)
_SEGMENT = r"[A-Za-z0-9._-]+"
_NUMBER = re.compile(r"^\d+$")


@dataclass(frozen=True)
class NormalizedId:
    """The result of normalizing an ID spelling.

    On success ``canonical`` is ``owner/repo#number`` and the components are
    populated. On failure ``canonical`` is ``None`` and ``error`` carries the
    stable error code (``validation`` or ``ambiguous_id``) plus a ``message``.
    """

    canonical: str | None
    owner: str | None = None
    repo: str | None = None
    number: int | None = None
    error: str | None = None
    message: str | None = None

    @property
    def ok(self) -> bool:
        return self.canonical is not None


def _fail(message: str, *, code: str = "validation") -> NormalizedId:
    return NormalizedId(canonical=None, error=code, message=message)


def _build(owner: str, repo: str, number: str) -> NormalizedId:
    canonical = f"{owner}/{repo}#{number}"
    return NormalizedId(
        canonical=canonical, owner=owner, repo=repo, number=int(number)
    )


def normalize_id(raw: str, *, default_owner: str | None = None) -> NormalizedId:
    """Normalize any accepted ID spelling to canonical ``owner/repo#number``.

    ``default_owner`` supplies the owner for the short/shell spellings that omit
    it. Idempotent: ``normalize_id(normalize_id(x).canonical)`` reproduces the
    same canonical string for any ``x`` that normalizes at all (ID-1).
    """
    if raw is None:
        return _fail("no ID given")
    text = raw.strip()
    if not text:
        return _fail("empty ID")

    # ---- Form 1 & 2: an explicit '#number' suffix. --------------------------
    if "#" in text:
        left, _, num = text.partition("#")
        if not _NUMBER.match(num):
            return _fail(f"issue number after '#' must be digits, got {num!r}")
        if "/" in left:
            owner, _, repo = left.partition("/")
            if not owner or not repo or "/" in repo:
                return _fail(f"malformed owner/repo in {raw!r}")
            if not _valid_segment(owner) or not _valid_segment(repo):
                return _fail(f"malformed owner/repo in {raw!r}")
            return _build(owner, repo, num)
        # Short 'repo#number' — same-owner only.
        if not _valid_segment(left):
            return _fail(f"malformed repo in {raw!r}")
        if not default_owner:
            return _fail(
                f"short ID {raw!r} needs an owner — pass owner/repo#number or set the target repo"
            )
        return _build(default_owner, left, num)

    # ---- Form 3: 'repo/number' (number is the trailing all-digit segment). --
    if "/" in text:
        head, _, tail = text.rpartition("/")
        if _NUMBER.match(tail) and head and "/" not in head:
            # 'repo/number' — same-owner.
            if not _valid_segment(head):
                return _fail(f"malformed repo in {raw!r}")
            if not default_owner:
                return _fail(
                    f"short ID {raw!r} needs an owner — pass owner/repo#number or set the target repo"
                )
            return _build(default_owner, head, tail)
        # 'owner/repo' with no issue number is not an item ID.
        return _fail(f"{raw!r} has no issue number (expected owner/repo#number)")

    # ---- Form 4: 'repo-number' (number is the trailing all-digit segment). --
    if "-" in text:
        head, _, tail = text.rpartition("-")
        if _NUMBER.match(tail) and head:
            if not _valid_segment(head):
                return _fail(f"malformed repo in {raw!r}")
            if not default_owner:
                return _fail(
                    f"short ID {raw!r} needs an owner — pass owner/repo#number or set the target repo"
                )
            return _build(default_owner, head, tail)

    return _fail(f"unrecognized ID spelling {raw!r} (expected owner/repo#number)")


def _valid_segment(segment: str) -> bool:
    # `_SEGMENT` admits `.` and `..` because dots are legal *inside* an owner or
    # repo name (`my.repo`). A segment that is nothing but dots is not a name —
    # it is a path traversal, and these segments are interpolated straight into
    # `repos/{owner}/{repo}/...` at the transport. The reachable source is
    # attacker-writable: a `superseded_by` block field carries an id parsed from
    # issue-body text, so `../../` here would redirect a `gh api` call to an
    # unrelated endpoint.
    if not segment.strip("."):
        return False
    return bool(re.fullmatch(_SEGMENT, segment))


def parse_repo(spec: str) -> tuple[str, str] | None:
    """Parse an ``owner/repo`` target-repo spec into ``(owner, repo)``.

    Returns ``None`` for anything that is not a clean two-segment ``owner/repo``
    (used to resolve ``--repo`` for ``file``/``provision`` and the ``get`` owner
    default). Not an item ID — no ``#number``.
    """
    if not spec:
        return None
    parts = spec.strip().split("/")
    if len(parts) != 2:
        return None
    owner, repo = parts
    if not owner or not repo or not _valid_segment(owner) or not _valid_segment(repo):
        return None
    return owner, repo


# --- PFX aliases & redirects (the importer's identity machinery, D4/DM4/§5) ---
#
# A migrated item keeps its hand-minted ``PFX-XXXX`` id forever as a permanent
# ``id:PFX-XXXX`` alias **label** (queryable/resolvable) plus an ``id_aliases``
# block entry (the export round-trip record) — Data Model §1.2/§5. **No new PFX is
# ever minted.** Alias uniqueness is an integrity constraint: an ``id:PFX`` must
# resolve to **exactly one** live item (§5) — a second claimant is a collision the
# importer flags (``alias_collision``), so ref resolution can't be hijacked.

ALIAS_FACET = "id"

# A hand-minted prefix id: a letter, then letters/digits, then **one or more**
# ``-``-joined alnum segments (e.g. ``BKL-7M4Q``, ``ADR-12``, ``A-1``,
# ``MIG-M4-REMOVE``). Deliberately lenient — the same reason ``legacy.ID_RE`` is:
# the importer absorbs whatever ID-shaped token a source used across its 27–58
# hand-minted prefixes (MIG-2) rather than minting a new scheme.
#
# Multi-segment ids are not an edge case: ~21% of surveyed backlogs carry one.
# Rejecting an id here is load-bearing twice over — this gates alias *minting* at
# import (a rejected id gets **no** ``id:`` alias), and it filters the block's
# ``id_aliases`` again on read-back (``core.iter_alias_issues``), so an id this
# rejects cannot be recognized on the target either. There is also no repair after
# the fact: the completeness gate derives ``unaliasable`` from the **source parse
# alone** (``migrate.verify_migration``), so the shape has to be right up front.
_PFX_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+")


def is_pfx(token: str | None) -> bool:
    """Whether ``token`` is a well-formed hand-minted ``PFX-XXXX`` id."""
    if not token:
        return False
    return re.fullmatch(_PFX_RE, token.strip()) is not None


def alias_label(pfx: str) -> str:
    """The permanent ``id:PFX-XXXX`` alias label for a migrated id (Data Model §5)."""
    return f"{ALIAS_FACET}:{pfx.strip()}"


def pfx_from_alias_label(name: str) -> str | None:
    """The ``PFX`` an ``id:`` alias label carries, or ``None`` if ``name`` is not a
    well-formed alias label. (An ``id:`` label whose value is not PFX-shaped is not
    treated as an alias — the importer never mints one, so a malformed value is a
    human artifact, ignored here.)"""
    prefix = f"{ALIAS_FACET}:"
    if not name.startswith(prefix):
        return None
    pfx = name[len(prefix) :]
    return pfx if is_pfx(pfx) else None


def resolve_redirect(canonical: str, *, fetch, max_hops: int = 16) -> str:
    """Follow ``superseded_by`` redirects from ``canonical`` to the final live item.

    ``fetch(canonical) -> target_canonical_or_None`` reads one item's redirect
    target (the block ``superseded_by`` field) — **injected** so this stays pure of
    the transport. Used by the merge/transfer redirect (a ref to a merged-away
    source resolves to its survivor — CRASH-2). Bounded by ``max_hops`` and a
    seen-set so a redirect **cycle** (a human A→B, B→A edit) terminates at where it
    is rather than looping forever (fail-open: return the last node visited)."""
    seen: set[str] = set()
    current = canonical
    for _ in range(max_hops):
        if current in seen:
            return current  # cycle guard — fail open at the current node
        seen.add(current)
        target = fetch(current)
        if not target or target == current:
            return current
        current = target
    return current
