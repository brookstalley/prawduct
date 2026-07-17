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
no I/O. Alias resolution and redirects (``id:PFX`` aliases, ``superseded-by:``)
are separate machinery built with the importer; this module handles only the
spelling→canonical normalization (D4/DM4, ID-1).
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
