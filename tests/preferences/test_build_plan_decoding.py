"""Every reader of the build plan decodes it the same way, and fails the same way.

A preference pin, not a unit test: the rule it enforces was a convention for
three consecutive Critic rounds and lost every time. Each sweep reached exactly
as far as the unit being edited — the function, then the module — because a
boundary you are inside is invisible. A pin has no field of view.

The risk is NOT that a plan fails to decode; PEP 538/540 coerce C/POSIX to UTF-8
on Linux and macOS, so reachability is narrow. The risk is DISAGREEMENT: readers
of the same file answering differently about whether it parses. Two axes produce
that, and sweeping only one leaves the class open —

* the **codec** — a bare ``read_text()`` uses the operator's locale, so one
  reader decodes a plan another cannot;
* the **except-set** — ``UnicodeDecodeError`` is a ``ValueError``, NOT an
  ``OSError``, so ``except OSError`` around a read lets it escape. Six of eleven
  readers degraded to a designed empty answer while five raised past callers
  that had no guard, turning ``verify-chunk-refs``' documented ``cannot-verify:``
  exit into a traceback across a boundary whose error model forbids one.

``plan_path.read_text(`` is the idiom every build-plan reader shares, which is
what makes the rule greppable. Related backlog item: ROB-7T2N (the same class
across the ~67 other runtime reads, deliberately out of scope here).
"""

from __future__ import annotations

import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent.parent / "plugin"

# `plan_path.read_text(...)` and, on the following lines, the `except` guarding it.
_READ = re.compile(r"plan_path\.read_text\((?P<args>[^)]*)\)")


def _build_plan_reads() -> list[tuple[str, int, str, str]]:
    """``(relpath, lineno, args, following_except)`` for each build-plan read."""
    found = []
    for path in sorted(PLUGIN.rglob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            m = _READ.search(line)
            if not m:
                continue
            following = ""
            for probe in lines[i + 1 : i + 4]:
                if probe.strip().startswith("except"):
                    following = probe.strip()
                    break
            found.append(
                (path.relative_to(PLUGIN).as_posix(), i + 1, m.group("args"), following)
            )
    return found


def test_the_pin_has_something_to_check():
    """Guard the guard: a renamed idiom would silently empty this file's coverage."""
    assert len(_build_plan_reads()) >= 8, (
        "no build-plan reads matched `plan_path.read_text(` — if the idiom was "
        "renamed, update this pin rather than letting it pass vacuously."
    )


def test_every_build_plan_read_names_utf8():
    offenders = [
        f"{rel}:{num}"
        for rel, num, args, _exc in _build_plan_reads()
        if 'encoding="utf-8"' not in args
    ]
    assert not offenders, (
        f"{offenders} decode the build plan with the operator's locale codec. "
        'Pass encoding="utf-8" so every reader of the file agrees on what it says.'
    )


def test_every_guarded_build_plan_read_catches_unicode_decode_error():
    """The half that was swept a round later than the codec.

    A read that is guarded at all must catch what it can actually raise.
    An UNGUARDED read is out of scope here — that is a deliberate
    let-it-propagate choice, and this pin does not second-guess it.
    """
    offenders = [
        f"{rel}:{num} -> {exc}"
        for rel, num, _args, exc in _build_plan_reads()
        if exc and "UnicodeDecodeError" not in exc
    ]
    assert not offenders, (
        f"{offenders} catch OSError but not UnicodeDecodeError, which is a "
        "ValueError and escapes. Catch (OSError, UnicodeDecodeError) so the "
        "designed degradation actually runs."
    )
