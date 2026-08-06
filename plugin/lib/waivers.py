"""Intentional-waiver pragma recognition (``prawduct:allow``).

A *waiver* is a source-comment pragma declaring that a line intentionally
violates a named principle or check, with a mandatory reason::

    <comment-leader> prawduct:allow <scope>/<rule-id> -- <reason>

The recognizer is **language-agnostic**: it scans for the keyword token and
does not care which comment syntax wraps it (``#``, ``//``, ``--``, ``;``,
``%``, ``<!-- -->``, ``/* */`` all work), so the same pragma reads correctly in
Python, shell, C#, Java, SQL, HTML, and so on.

``<scope>`` is ``prawduct`` (a framework principle/check) or ``project`` (a
consuming repo's own convention). A check is waived iff a waiver's
``scope/rule-id`` matches the check's own ref — scope-matching prevents one
rule's waiver from silencing another. The legacy ``prawduct:ok-broad-except``
spelling is honored as ``prawduct/broad-except``.

Full specification: ``docs/waivers.md``. This module is the single source of
truth for recognition, imported by the compliance canary and any future check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# The canonical waiver keyword. Stable across versions; never renamed.
KEYWORD = "prawduct:allow"

# The legacy single-purpose spelling, equivalent to ``prawduct/broad-except``.
LEGACY_KEYWORD = "prawduct:ok-broad-except"
_LEGACY_REF = "prawduct/broad-except"

# A ref is ``scope/rule-id`` — both kebab/alnum, slash required. The slash is
# what distinguishes a well-formed ref from a scopeless (malformed) one, which
# deliberately does not match so the underlying finding resurfaces.
_REF = r"[A-Za-z][\w.-]*/[A-Za-z][\w.-]*"
_REFS = rf"{_REF}(?:\s*,\s*{_REF})*"
_GENERAL_RE = re.compile(rf"{re.escape(KEYWORD)}\s+(?P<refs>{_REFS})(?P<rest>.*)$")
# Trailing `(?!\w)` boundary so the legacy keyword is not matched as a prefix of a
# longer word (e.g. ``prawduct:ok-broad-exception``). A word char ends the token;
# every valid separator (space, ``-``, ``—``, ``:``) is a non-word char, so an
# immediately-adjacent ``--reason`` still parses.
_LEGACY_RE = re.compile(rf"{re.escape(LEGACY_KEYWORD)}(?!\w)(?P<rest>.*)$")


@dataclass(frozen=True)
class Waiver:
    """One intentional-waiver declaration parsed from a source line."""

    scope: str  # "prawduct" | "project" | (any other scope a repo defines)
    rule_id: str  # e.g. "broad-except"
    reason: str  # mandatory; "" means malformed (see invalid_waivers)
    line: str  # the source line the waiver was found on

    @property
    def ref(self) -> str:
        """The ``scope/rule-id`` reference, e.g. ``prawduct/broad-except``."""
        return f"{self.scope}/{self.rule_id}"

    @property
    def has_reason(self) -> bool:
        return bool(self.reason)


def _clean_reason(rest: str) -> str:
    """Strip a leading ``--`` / ``—`` separator and surrounding whitespace.

    The canonical separator is ``--`` (ESLint-style); an em dash ``—`` is
    accepted for continuity with the legacy ``ok-broad-except`` spelling. A
    bare separator with no following text yields ``""`` (a malformed waiver).

    An HTML comment terminator is stripped FIRST, before the separator is even
    looked for. A waiver in a markdown file has to live inside ``<!-- ... -->``,
    and without this the closing ``-->`` is itself read as ``--`` + a reason of
    ``>`` — so a bare, reason-less pragma would silently satisfy
    :meth:`Waiver.has_reason`, which is the one thing the reason requirement
    exists to prevent. Source-code comments never contain the token, so this
    costs nothing anywhere else.
    """
    rest = rest.strip()
    if rest.endswith("-->"):
        rest = rest[: -len("-->")].rstrip()
    if rest.startswith("--"):
        rest = rest[2:]
    elif rest.startswith("—"):  # em dash
        rest = rest[1:]
    return rest.strip()


def parse_waivers(line: str) -> list[Waiver]:
    """Every waiver declared on a single source ``line`` (general + legacy).

    A single ``prawduct:allow`` may list comma-separated refs; each becomes its
    own :class:`Waiver` sharing the line's reason. Malformed (scopeless) refs
    do not match and are silently absent.
    """
    waivers: list[Waiver] = []
    for m in _GENERAL_RE.finditer(line):
        reason = _clean_reason(m.group("rest"))
        for ref in re.split(r"\s*,\s*", m.group("refs")):
            scope, _, rule_id = ref.partition("/")
            waivers.append(Waiver(scope=scope, rule_id=rule_id, reason=reason, line=line))
    for m in _LEGACY_RE.finditer(line):
        reason = _clean_reason(m.group("rest"))
        scope, _, rule_id = _LEGACY_REF.partition("/")
        waivers.append(Waiver(scope=scope, rule_id=rule_id, reason=reason, line=line))
    return waivers


def line_waives(line: str, rule_ref: str) -> bool:
    """True if ``line`` carries a waiver matching ``rule_ref`` with a reason.

    ``rule_ref`` is a ``scope/rule-id`` string, e.g. ``"prawduct/broad-except"``.
    A reason-less (malformed) waiver does not waive — it is itself a finding
    (see :func:`invalid_waivers`), and the underlying check should still fire.
    """
    return any(w.ref == rule_ref and w.has_reason for w in parse_waivers(line))


def waives(lines: list[str], index: int, rule_ref: str) -> bool:
    """True if the line at ``index`` — or the line immediately above it —
    waives ``rule_ref``. Supports both trailing and leading placement."""
    if index < 0 or index >= len(lines):
        return False
    if line_waives(lines[index], rule_ref):
        return True
    return index > 0 and line_waives(lines[index - 1], rule_ref)


def invalid_waivers(lines: list[str]) -> list[Waiver]:
    """Waivers present but missing a reason — malformed, and a finding.

    The reason is mandatory: a waiver without one is "I'm setting aside a rule
    but won't say why," which defeats the purpose. The canary surfaces these.
    """
    bad: list[Waiver] = []
    for line in lines:
        bad.extend(w for w in parse_waivers(line) if not w.has_reason)
    return bad
