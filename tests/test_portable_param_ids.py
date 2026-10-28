"""Parametrize ids are the same on every machine that collects them.

The suite runs on a pool: one runner collects, another runs the id it was handed.
An id pytest generates from a string value with a newline, a trailing space or
non-ASCII text did not survive that hand-off, and the run reported an error for a
test that passes. ``conftest.pytest_make_parametrize_id`` gives such values a
stable hashed id instead.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import portable_param_id

_SAFE = "plain-value_1.json"


@pytest.mark.parametrize(
    "value",
    ["a\nb", "trailing space ", "em—dash", "x" * 81, " leading", "tab\there"],
    ids=["newline", "trailing-space", "non-ascii", "long", "leading-space", "tab"],
)
def test_a_value_pytest_cannot_carry_gets_a_hashed_id(value):
    pid = portable_param_id(value, "seed")
    assert pid is not None and pid.startswith("seed-")
    assert pid.isascii() and pid == pid.strip() and "\n" not in pid and len(pid) <= 40
    assert portable_param_id(value, "seed") == pid, "the id is deterministic"


def test_distinct_values_get_distinct_ids():
    assert portable_param_id("a\nb", "seed") != portable_param_id("a\nc", "seed")


@pytest.mark.parametrize("value", [_SAFE, "", None, 3, ("a", "b")], ids=str)
def test_an_ordinary_value_keeps_pytests_own_id(value):
    """Control: only the values that broke the hand-off are renamed, so every
    other test keeps the id it has always had."""
    assert portable_param_id(value, "seed") is None


def test_the_hook_reaches_collection(tmp_path: Path):
    """The hook is wired, not only defined: a file collected with this conftest's
    hook reports the hashed id, and an ordinary value its usual one."""
    hook_src = Path(__file__).with_name("conftest.py")
    (tmp_path / "conftest.py").write_text(
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('repo_conftest', {str(hook_src)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "pytest_make_parametrize_id = mod.pytest_make_parametrize_id\n"
    )
    (tmp_path / "test_probe.py").write_text(
        "import pytest\n"
        "@pytest.mark.parametrize('seed', ['ok', 'a\\nb'])\n"
        "def test_probe(seed):\n"
        "    pass\n"
    )
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:randomly",
         "-p", "no:xdist", "-p", "no:cacheprovider", "--rootdir", str(tmp_path),
         "-c", "/dev/null", str(tmp_path / "test_probe.py")],
        capture_output=True, text=True, cwd=str(tmp_path), timeout=60,
    ).stdout
    ids = [line for line in out.splitlines() if "test_probe[" in line]
    assert any(line.endswith("test_probe[ok]") for line in ids), out
    hashed = portable_param_id("a\nb", "seed")
    assert any(line.endswith(f"test_probe[{hashed}]") for line in ids), out
