"""Inclusive `[since, until]` bounds over ISO timestamps — one home, two readers.

`review-stats` (`lib/telemetry.py`) and `tools/pr-review-yield.py` both grade a
before/after split over the same governance ledger. When each carried its own
copy of these predicates the two had **already diverged**: the tool compared a
lower bound as a bare string while the library parsed it, so the same
`--since` selected different populations in the two instruments a reader would
naturally compare against each other. That is the failure `architecture.md`'s
*every fact has one home* names, and a shared matcher alone would not have
fixed it — sharing the predicate AND the reader that feeds it is what shares
the definition.

This module is deliberately dependency-free (stdlib only, no relative
imports) so a standalone script under `tools/` can import it the same way it
already imports `review_dispatch`.

**The rule the bounds obey.** Both ends are INCLUSIVE, and a bound shorter than
a full timestamp names a PERIOD rather than an instant: `2026` is a year,
`2026-09` the whole of September, `2026-09-01` that whole day. Compared as bare
strings every one of those excludes its own period, because
`2026-09-01T00:00:01Z` sorts after `2026-09-01` — which silently shortens
whichever window the bound closes, and the newest window is the one a
before/after comparison is read from.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

FULL_TIMESTAMP_LEN = len("YYYY-MM-DDTHH:MM:SS")

#: A bound shorter than a full timestamp names a period — these are exactly the
#: forms compared by prefix rather than parsed.
LOOKS_LIKE_PERIOD = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def parse_instant(stamp) -> "datetime | None":
    """Parse an ISO stamp, treating a missing zone as UTC.

    The zone default is not cosmetic: ledger rows are written `...Z`, and a
    bound typed without one would be naive — comparing naive to aware raises
    rather than answering. A window bound is a FILTER, so it must never be able
    to end the run.
    """
    if not isinstance(stamp, str):
        return None
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_usable_bound(value: str) -> bool:
    """Whether a bound names a real instant or a real period.

    Parsing is not enough and neither is the shape: `2026-09-31` matches the
    period pattern and is not a date, so accepting it silently means
    2026-10-01 — a bound meaning something other than what was typed, which is
    the one failure a window must never have. A period is therefore checked by
    CONSTRUCTING its first instant.
    """
    if parse_instant(value) is not None:
        return True
    if not LOOKS_LIKE_PERIOD.match(value):
        return False
    y, m, d = (value.split("-") + ["01", "01"])[:3]
    return parse_instant(f"{y}-{m}-{d}T00:00:00Z") is not None


def exceeds_upper(ts: str, bound: str) -> bool:
    """True when `ts` falls after an INCLUSIVE upper bound."""
    if len(bound) < FULL_TIMESTAMP_LEN:
        return ts[: len(bound)] > bound
    a, b = parse_instant(ts), parse_instant(bound)
    if a is None or b is None:
        return ts > bound
    return a > b


def precedes_lower(ts: str, bound: str) -> bool:
    """True when `ts` falls before an INCLUSIVE lower bound.

    The mirror of :func:`exceeds_upper`, and it must exist separately rather
    than fall back to a bare string compare. For a PERIOD bound the two agree
    by luck — a period's inclusive start IS its own string prefix — which is
    why a mutation swapping this for `ts < bound` survived a full suite. What
    does NOT agree is a full timestamp carrying a zone offset:
    `2026-08-04T12:00:00+02:00` is 10:00Z, and compared as text against a
    `...Z` stamp it means nothing at all.
    """
    if len(bound) < FULL_TIMESTAMP_LEN:
        return ts[: len(bound)] < bound
    a, b = parse_instant(ts), parse_instant(bound)
    if a is None or b is None:
        return ts < bound
    return a < b


def in_window(ts, since: "str | None", until: "str | None") -> bool:
    """Whether `ts` falls inside an inclusive `[since, until]`.

    An event with no usable `ts` is KEPT when no bound is given and DROPPED
    once either is — a row that cannot say when it happened cannot be claimed
    for a window, and silently counting it in both halves of a before/after
    split is the error that would flatter every comparison.
    """
    if since is None and until is None:
        return True
    if not isinstance(ts, str) or not ts:
        return False
    if since and precedes_lower(ts, since):
        return False
    if until and exceeds_upper(ts, until):
        return False
    return True
