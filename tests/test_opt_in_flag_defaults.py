"""GD1 — every opt-in flag's template value equals its code default.

**This is the guard against the root cause, not against a symptom.** The
derived-view subsystem was retired because a flag had three declarations —
the template a product is scaffolded from, the code that reads it, and the prose
explaining it — and nothing compared them. The template shipped one default
while the reader assumed another; the disagreement was invisible for four minor
versions, and unwinding it took a whole plan. Without this test the same drift
recurs on whatever flag is added next.

The comparison is against the **real** template, reached through
``core.TEMPLATES_DIR``, never a fixture. A fixture would pin what this test's
author believed the template said, which is precisely the third declaration that
caused the problem.
"""

from __future__ import annotations

import re

import pytest

from lib import core

STATE_TEMPLATE = core.TEMPLATES_DIR / "project-state.yaml"

#: A column-0 ``key: true|false`` scalar — the shape :func:`core.read_bool_yaml_key`
#: recognises, so the scan and the reader agree on what counts as a flag.
_BOOL_KEY_RE = re.compile(r"^([a-z_]+):\s*(true|false)\s*(?:#.*)?$")


def _template_text() -> str:
    assert STATE_TEMPLATE.is_file(), f"the state template is missing: {STATE_TEMPLATE}"
    return STATE_TEMPLATE.read_text(encoding="utf-8")


def _template_bool_keys() -> dict[str, bool]:
    """Every column-0 boolean key the shipped template declares, with its value."""
    found: dict[str, bool] = {}
    for line in _template_text().splitlines():
        match = _BOOL_KEY_RE.match(line)
        if match:
            found[match.group(1)] = match.group(2) == "true"
    return found


@pytest.mark.parametrize("flag", core.OPT_IN_FLAGS)
def test_template_declares_every_registered_flag(flag: str) -> None:
    """A registered flag the template never mentions would pass the value check
    vacuously — absent reads as False, and False is the expected default, so the
    comparison would agree about a flag nobody scaffolds."""
    assert flag in _template_bool_keys(), (
        f"{flag} is registered in core.OPT_IN_FLAGS but the shipped template "
        f"{STATE_TEMPLATE.name} does not declare it, so a scaffolded product "
        f"never sees it. Add it to the template or drop it from the registry."
    )


@pytest.mark.parametrize("flag", core.OPT_IN_FLAGS)
def test_template_value_equals_code_default(flag: str, tmp_path) -> None:
    """The template's shipped value must equal what the reader does with no file.

    The code default is *measured*, not asserted: it is read from a state file
    that omits the key, which is exactly the fail-soft path a real product hits.
    Writing the expected default as a literal here would make this test agree
    with a belief instead of with the code.
    """
    empty_state = tmp_path / "project-state.yaml"
    empty_state.write_text("# no flags declared\n", encoding="utf-8")
    code_default = core.read_bool_yaml_key(empty_state, flag)

    template_value = _template_bool_keys()[flag]
    assert template_value == code_default, (
        f"{flag} disagrees with itself: the shipped template says "
        f"{str(template_value).lower()}, the code default is "
        f"{str(code_default).lower()}. A product scaffolded from the template "
        f"would behave differently from one that never set the flag."
    )


def test_every_template_boolean_is_a_registered_flag() -> None:
    """The cross-check in the other direction.

    Without it, a flag added to the template but never registered is governed by
    nothing — which is the same one-sided declaration this test exists to stop,
    entering from the other end.
    """
    unregistered = sorted(set(_template_bool_keys()) - set(core.OPT_IN_FLAGS))
    assert not unregistered, (
        f"the shipped template declares boolean flag(s) {unregistered} that are "
        f"not in core.OPT_IN_FLAGS, so nothing compares their template value "
        f"against their code default. Register them or make them non-boolean."
    )


def test_opt_in_means_false_by_default() -> None:
    """Pins the contract the registry's docstring states.

    ``read_bool_yaml_key`` fails soft to False on every unreadable input, which
    is what makes these flags opt-in. A future edit making one default to True
    would silently turn a gate on in every repo that never asked for it.
    """
    missing = core.TEMPLATES_DIR / "does-not-exist.yaml"
    for flag in core.OPT_IN_FLAGS:
        assert core.read_bool_yaml_key(missing, flag) is False, (
            f"{flag} does not default to False on an unreadable state file; "
            f"opt-in flags must stay off until a product turns them on."
        )
