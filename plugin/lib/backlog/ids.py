"""Identifier normalization — every accepted spelling → canonical form.

The canonical item identifier is GitHub's own cross-reference syntax
``owner/repo#number`` (Data Model §5, API §8). Consumers may pass any of the
spellings below and the adapter normalizes on the way in (API §3):

- ``owner/repo#number``  — canonical
- ``repo#number``        — short, same-owner (needs a ``default_owner``)
- ``repo/number``        — shell-friendly (no ``#`` to escape)
- ``repo-number``        — shell-friendly
- ``number`` / ``#number`` — bare (needs a ``default_repo``)

Short/shell-friendly forms carry no owner, so they resolve **same-owner only**
and require a ``default_owner`` (the target repo's owner). Absent one they are a
``validation`` error rather than a silent guess.

The bare forms carry no repo either, so a ``default_owner`` cannot resolve them —
they need a full ``default_repo``. They exist because a bare number is what an
operator reads off a GitHub URL, and without them a fully-disambiguating
``--repo owner/repo`` still could not resolve one.

This module is a **pure, function-level seam** (Test Specs §2.1): no transport,
no I/O. It also holds the **alias & redirect machinery** the importer and the
cache use (D4/DM4/§5): the pure label helpers
(``alias_label``/``pfx_from_alias_label``), the **provider-alias grammar**
(``provider_alias``/``parse_provider_alias`` — Cache Spec §4's tagged spelling,
which is what keeps a historical citation resolving across a provider migration),
and the redirect-follow (``resolve_redirect``) whose lookup is **injected** as a
callback — so the module stays transport-free while still owning the resolution
*logic*. The spelling→canonical normalization (ID-1) is above.
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


def normalize_id(
    raw: str,
    *,
    default_owner: str | None = None,
    default_repo: tuple[str, str] | None = None,
) -> NormalizedId:
    """Normalize any accepted ID spelling to canonical ``owner/repo#number``.

    ``default_owner`` supplies the owner for the short/shell spellings that omit
    it. ``default_repo`` is an ``(owner, repo)`` pair supplying BOTH for the bare
    forms, which carry neither — an owner alone cannot resolve a bare number, so
    the two defaults are not interchangeable. Idempotent:
    ``normalize_id(normalize_id(x).canonical)`` reproduces the same canonical
    string for any ``x`` that normalizes at all (ID-1).
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
        # Bare '#number' — carries neither owner nor repo, so only a full
        # `default_repo` resolves it. Handled before the short form because an
        # empty left side is not a malformed repo name: there is no repo in the
        # input to be malformed, and saying so sent readers to fix the wrong thing.
        if not left:
            if not default_repo:
                return _fail(
                    f"bare ID {raw!r} needs a repo — pass owner/repo#number or set the target repo"
                )
            return _build(default_repo[0], default_repo[1], num)
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

    # ---- Form 0: a bare 'number'. ------------------------------------------
    # The spelling an operator reads straight off a GitHub URL. Last, so it can
    # never shadow a repo whose name is all digits in the hyphen/slash forms above.
    if _NUMBER.match(text):
        if not default_repo:
            return _fail(
                f"bare ID {raw!r} needs a repo — pass owner/repo#number or set the target repo"
            )
        return _build(default_repo[0], default_repo[1], text)

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
    """The permanent ``id:PFX-XXXX`` alias label for a migrated id (Data Model §5).

    **Labels index PFX aliases only**, and that asymmetry is deliberate rather
    than an omission. A label is the *live* path's index — it is what lets
    ``core.resolve_ref`` find an item by alias with one search against the
    provider — and a hand-minted ``PFX`` has no other coordinates, so without a
    label it is unfindable. A **provider** alias (:func:`provider_alias`) does
    have coordinates: it is a real ``owner/repo#number`` that the cache's
    ``item_alias`` table resolves without asking the provider anything. Minting
    labels for it would add a write path, a self-heal obligation and a 50-char
    label budget to buy a second index over a set that is already indexed."""
    return f"{ALIAS_FACET}:{pfx.strip()}"


# --- provider aliases (the cross-migration half of Cache Spec §4) -------------
#
# A migration mints no new id: the new record carries the OLD one as an alias, so
# every historical citation — `(#614)` in a commit message, `#249` in the
# change-log — keeps resolving. Cache Spec §4 makes the two spellings asymmetric
# on purpose:
#
#   live ref  — untagged (`owner/repo#249`): it inherits the product's
#               configured backend, so per-item tagging would be noise.
#   alias     — tagged (`github:owner/repo#249`): after a migration a
#               foreign-era id sits beside a live one, and `owner/repo#number` is
#               NOT GitHub-unique — GitLab uses `group/project#123` and Gitea is
#               GitHub-shaped by design, which are precisely the self-hosted
#               options motivating provider neutrality.
#
# The tag is what stops resolution degrading into shape-parsing, which §4's rule 3
# forbids: an untagged `owner/repo#number` is a live coordinate, a tagged one is a
# historical record, and nothing has to guess which by looking at its shape.

#: A provider tag: lowercase alphanumeric, e.g. ``github``, ``gitlab``, ``gitea``.
#: Deliberately open rather than a closed set — the alias spellings this has to
#: *read* are written by whatever backend a product migrated away from, and a
#: closed set here would make a tag minted by a future adapter unreadable by the
#: reader whose whole job is reading old spellings.
_PROVIDER_TAG = re.compile(r"^[a-z][a-z0-9]*$")


def provider_alias(canonical: str, *, provider: str = "github") -> str | None:
    """The tagged alias spelling for a provider id, or ``None`` if either half is
    malformed.

    ``canonical`` must already be a full ``owner/repo#number`` — a short spelling
    has no owner, and an alias that resolved differently depending on who read it
    would be worse than no alias."""
    if not _PROVIDER_TAG.match(provider or ""):
        return None
    nid = normalize_id(canonical)
    if not nid.ok:
        return None
    return f"{provider}:{nid.canonical}"


def parse_provider_alias(token: str | None) -> tuple[str, str] | None:
    """``(provider, canonical)`` for a tagged alias, or ``None``.

    **The ref half is re-normalized rather than trusted**, and that is the point
    of routing it through :func:`normalize_id` instead of splitting on ``#``. An
    alias arrives from an issue body — attacker-writable text — and the canonical
    id it yields is handed to callers that interpolate ``owner`` and ``repo`` into
    ``repos/{owner}/{repo}/…`` at the transport. The question at this seam is not
    *is this well-formed* but *what else could this successfully resolve*:
    ``github:../../x#1`` parses fine as three tokens and points somewhere else
    entirely. ``normalize_id``'s segment gate is the one place that judgment
    lives, so this defers to it rather than repeating it."""
    if not token:
        return None
    provider, sep, ref = token.strip().partition(":")
    if not sep or not _PROVIDER_TAG.match(provider):
        return None
    nid = normalize_id(ref)
    if not nid.ok or nid.canonical != ref.strip():
        # Only the canonical spelling is an alias. A short form (`repo#7`) would
        # need a default owner to mean anything, so accepting one here would make
        # the same stored string resolve to different items in different repos.
        return None
    return provider, nid.canonical


def is_alias_token(token: str | None) -> bool:
    """Whether ``token`` is a well-formed alias in either accepted spelling — a
    hand-minted ``PFX`` or a tagged provider id.

    The filter on what goes into the cache's alias index: an ``id_aliases`` entry
    that is neither is a human artifact (a hand-edited body), and indexing it
    would let a typo claim a resolution."""
    return is_pfx(token) or parse_provider_alias(token) is not None


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
