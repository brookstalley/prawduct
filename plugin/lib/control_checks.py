"""Which Critic control a finding is a firing of — a structured ``check``
derived from the title token the reviewer already writes.

A control shipped under the observable-yield obligation
(``.prawduct/artifacts/nonfunctional-requirements.md`` § Direction) is
retired or kept on its yield, and yield is only measurable if a firing can be
counted. The persisted ``goal`` cannot carry that: it is reviewer-written and
drifts. So each such control tells the reviewer to open the finding's title
with a stable token, and this module turns that token into a field once, at
consolidation, from a closed registry. Reviewers write nothing new, so the
budgeted reviewer payloads do not grow.

**The registry is closed.** :data:`KNOWN_CHECKS` holds every token a reviewer
surface instructs, and ``tests/test_control_yield_tokens.py`` fails if a
protocol instructs a token missing from it or the registry names one no
protocol instructs any more.

**The token is read at the title's lead**, after an optional file prefix
(``foo.py: cross-component-contract — …``), case-insensitively and with the
colon optional — never anywhere in the title. A title that NAMES a control
while reporting a defect about it ("The scope-trace: retire rule's numerator
is already polluted") is not a firing of it. Matching anywhere counted eight
such titles among the 172 carrying a token in this clone's evidence store when
measured on 2026-11-18, and that is how a retire numerator gets polluted by
findings about the control itself.
"""

from __future__ import annotations

import re

#: Every control whose firing is counted by a title token. Order is the
#: registry's, and it is stable: a reader grouping on ``check`` keys on these.
KNOWN_CHECKS: tuple[str, ...] = (
    "cross-component-contract",
    "scope-trace",
    "rule-unenforced",
    "read-cost",
)

# An optional leading file reference — `path.ext`, `path.ext:12` or
# `path.ext:12-30`, optionally backticked — closed by a colon or a dash.
_FILE_PREFIX = r"(?:`?[\w./-]+\.\w+(?::\d+(?:-\d+)?)?`?\s*[:—–-]\s*)?"

_LEAD = re.compile(
    r"^[\s`*_\[(]*" + _FILE_PREFIX + r"[`*_\[(]*"
    r"(" + "|".join(re.escape(slug) for slug in KNOWN_CHECKS) + r")"
    # The slug ends the word: `scope-trace-ish` and `read-costs` are not it.
    r"(?![\w-])",
    re.IGNORECASE,
)


def derive_check(text: "str | None") -> "str | None":
    """The registry slug ``text`` (a finding or observation title) opens with,
    or ``None`` when it opens with none — including when ``text`` is not a
    string. Never raises: a title is reviewer-written free text."""
    if not isinstance(text, str):
        return None
    match = _LEAD.match(text)
    return match.group(1).lower() if match else None
