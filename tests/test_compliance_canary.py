"""The session-end compliance canary: what it still reports, and what it no
longer does.

The code-without-tests check is gone (#164 rules it deleted; test adequacy is
Critic Goal 1's). It fired on every session that changed code without a test
file, a research spike script under `docs/` included (#935). What its removal
must not take with it are the three checks that survive, which had no tests of
their own until now.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import compliance, gitstate  # noqa: E402


@pytest.fixture
def product(tmp_path: Path, monkeypatch):
    (tmp_path / ".prawduct" / "artifacts").mkdir(parents=True)
    changed: list[str] = []
    monkeypatch.setattr(gitstate, "_get_session_changed_files", lambda _p: list(changed))

    def change(rel: str, content: str = "x = 1\n") -> None:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        changed.append(rel)

    return tmp_path, change


def test_code_changed_without_a_test_is_not_reported(product):
    root, change = product
    change("docs/research/bend-tilt/spike.py")
    change("src/app.py")
    # The control: the same run still reports what the canary does check, so
    # an empty result cannot come from the canary never running.
    change("src/waived.py", "try:\n    x()\nexcept Exception:  # prawduct:allow prawduct/broad-except\n    pass\n")
    findings = compliance.compliance_canary(root)
    assert any("Reason-less prawduct:allow waiver" in f for f in findings)
    assert not any("no test files" in f for f in findings)


def test_a_dependency_change_without_the_manifest_is_reported(product):
    root, change = product
    (root / ".prawduct" / "artifacts" / "dependency-manifest.md").write_text("# deps\n")
    change("pyproject.toml", "[project]\n")
    findings = compliance.compliance_canary(root)
    assert any("dependency-manifest.md was not updated" in f for f in findings)


def test_a_dependency_change_with_the_manifest_is_quiet(product):
    root, change = product
    change(".prawduct/artifacts/dependency-manifest.md", "# deps\n")
    change("pyproject.toml", "[project]\n")
    assert compliance.compliance_canary(root) == []


def test_broad_exception_handling_is_reported(product):
    root, change = product
    change("src/app.py", "try:\n    x()\nexcept Exception:\n    pass\n")
    findings = compliance.compliance_canary(root)
    assert any("Broad exception handling detected in: src/app.py" in f for f in findings)


def test_no_changes_report_nothing(product):
    root, _change = product
    assert compliance.compliance_canary(root) == []
