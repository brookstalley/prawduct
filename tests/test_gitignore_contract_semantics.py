"""The gitignore contract is judged by what git would ignore, not by line equality (#762).

``core._contract_diff`` used to compare literal ``.gitignore`` lines. A wholesale rule such
as ``.prawduct/`` subsumes every session entry and matches none of them literally, so the
contract failed in BOTH directions: it called ignored session files "missing" (and the fixer
then appended redundant lines forever), and it never noticed that files prawduct needs
COMMITTED (``MANAGED_FILES``) were being ignored by that same rule.

The fixtures here use the issue's own repro, a ``.gitignore`` of exactly ``.prawduct/`` and
``__pycache__/``, in two worlds: a real git repo, and a directory with no repo at all (the
onboard-before-``git init`` case), because the two take different paths to the same answer.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))

from lib import gitignore_probes as gp  # noqa: E402
from lib.advisory_store import Codebase, ProjectState, clear_registry  # noqa: E402
from lib.core import (  # noqa: E402
    GITIGNORE_ENTRIES,
    MANAGED_FILES,
    RETIRED_GITIGNORE_ENTRIES,
    describe_ignored_by_rule,
    gitignore_contract_drift,
    update_gitignore,
)

# `.claude/settings.local.json` is the one session entry outside `.prawduct/`.
OUTSIDE = ".claude/settings.local.json\n__pycache__/\n"
WHOLESALE = ".prawduct/\n" + OUTSIDE
# Everything under `.prawduct/` the contract needs COMMITTED: managed files, plus the
# retired entries (the build plan is a tracked artifact, one directory down).
PRAWDUCT_MANAGED = sorted(
    p for p in {*MANAGED_FILES, *RETIRED_GITIGNORE_ENTRIES} if p.startswith(".prawduct/")
)
# The lines that re-include all of it under a `.prawduct/*` rule.
REINCLUDE = ["!.prawduct/artifacts/", *(f"!{p}" for p in PRAWDUCT_MANAGED if p.count("/") == 1)]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, timeout=30)


@pytest.fixture(params=["repo", "no-repo"])
def world(request, tmp_path: Path) -> Path:
    """A project dir that is a real git repo, or one that is not (yet)."""
    if request.param == "repo":
        _git(tmp_path, "init", "-q", ".")
    return tmp_path


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def _write(root: Path, text: str) -> Path:
    gi = root / ".gitignore"
    gi.write_text(text, encoding="utf-8")
    return gi


def test_fixture_is_not_vacuous():
    assert PRAWDUCT_MANAGED, "MANAGED_FILES holds no .prawduct/ path; the wholesale fixtures prove nothing"
    assert len(PRAWDUCT_MANAGED) >= 2


# --- the false "missing" direction ------------------------------------------------


def test_wholesale_rule_leaves_no_session_entry_missing(world):
    _write(world, WHOLESALE)
    drift = gitignore_contract_drift(world)
    # Every `.prawduct/...` session entry is ignored by `.prawduct/`; the rest are literal.
    assert drift["missing"] == []


def test_update_gitignore_appends_nothing_under_a_wholesale_rule(world):
    gi = _write(world, WHOLESALE)
    before = gi.read_bytes()
    result = update_gitignore(world)
    assert result["missing"] == []
    assert gi.read_bytes() == before, "the fixer rewrote a file whose session entries are all ignored"


def test_a_genuinely_missing_entry_is_still_missing(world):
    # The control: the rule covers `.prawduct/`, so only entries OUTSIDE it can be missing.
    _write(world, ".prawduct/\n")
    drift = gitignore_contract_drift(world)
    outside = [e for e in GITIGNORE_ENTRIES if not e.startswith(".prawduct/")]
    assert outside, "fixture is vacuous: every session entry is under .prawduct/"
    assert drift["missing"] == outside


# --- the false "fine" direction ---------------------------------------------------


def test_wholesale_rule_ignoring_managed_files_is_reported(world):
    _write(world, WHOLESALE)
    drift = gitignore_contract_drift(world)
    by_rule = {e["path"]: e for e in drift["ignored_by_rule"]}
    assert sorted(by_rule) == PRAWDUCT_MANAGED
    for entry in by_rule.values():
        assert entry["pattern"] == ".prawduct/"
        assert entry["line"] == 1
        assert entry["source"].endswith(".gitignore")
    # Nothing literal to strip: the fixer cannot repair this, and must say so rather than guess.
    assert drift["incorrectly_ignored"] == []


def test_update_gitignore_reports_but_never_edits_a_wholesale_rule(world):
    gi = _write(world, WHOLESALE)
    before = gi.read_bytes()
    result = update_gitignore(world)
    assert result["modified"] is False
    assert result["unignored"] == []
    assert sorted(e["path"] for e in result["ignored_by_rule"]) == PRAWDUCT_MANAGED
    assert gi.read_bytes() == before, "a user-authored wholesale rule was rewritten without consent"


def test_dry_run_is_byte_identical_and_reports_the_same(world):
    gi = _write(world, WHOLESALE)
    before = gi.read_bytes()
    preview = update_gitignore(world, dry_run=True)
    assert gi.read_bytes() == before
    assert sorted(e["path"] for e in preview["ignored_by_rule"]) == PRAWDUCT_MANAGED


def test_negated_reinclusion_satisfies_the_contract(world):
    # The shape the owner's remedy produces: `.prawduct/*` plus a re-include per managed file.
    text = ".prawduct/*\n" + "".join(f"{x}\n" for x in REINCLUDE) + OUTSIDE
    _write(world, text)
    drift = gitignore_contract_drift(world)
    assert drift["ignored_by_rule"] == []
    assert drift["missing"] == []
    assert drift["incorrectly_ignored"] == []


def test_partial_reinclusion_reports_only_what_is_still_ignored(world):
    kept = ".prawduct/critic-review.md"
    rest = [p for p in PRAWDUCT_MANAGED if p != kept]
    assert kept in PRAWDUCT_MANAGED and rest
    _write(world, f".prawduct/*\n!{kept}\n" + OUTSIDE)
    drift = gitignore_contract_drift(world)
    assert sorted(e["path"] for e in drift["ignored_by_rule"]) == sorted(rest)


def test_star_form_of_the_wholesale_rule_is_caught_too(world):
    _write(world, ".prawduct/*\n" + OUTSIDE)
    drift = gitignore_contract_drift(world)
    assert sorted(e["path"] for e in drift["ignored_by_rule"]) == PRAWDUCT_MANAGED
    assert drift["missing"] == []


def test_literal_managed_entry_is_still_removed_and_not_double_reported(world):
    managed = PRAWDUCT_MANAGED[0]
    gi = _write(world, f"{managed}\n")
    drift = gitignore_contract_drift(world)
    assert drift["incorrectly_ignored"] == [managed]
    assert managed not in [e["path"] for e in drift["ignored_by_rule"]]
    result = update_gitignore(world)
    assert result["unignored"] == [managed]
    assert managed not in gi.read_text().splitlines()


@pytest.mark.parametrize("rule", [".prawduct/", ".prawduct/*", "/.prawduct", ".prawduct/**"])
def test_the_advised_lines_actually_resolve_it(world, rule):
    """Follow the advice (the effect, not the advisory object): paste the lines the
    owner is offered and the drift is gone; leave the rule and it is not."""
    _write(world, f"{rule}\n" + OUTSIDE)
    before = gitignore_contract_drift(world)
    assert before["ignored_by_rule"], "control: the rule must be reported before the advice is followed"
    (sentence,) = describe_ignored_by_rule(before["ignored_by_rule"])
    offered = sentence.split("replace it with these lines:")[1].rstrip(".")
    lines = [part.strip("` ") for part in offered.split(", ")]
    assert lines[0] == ".prawduct/*" and len(lines) > 2
    _write(world, "\n".join(lines) + "\n" + OUTSIDE)
    after = gitignore_contract_drift(world)
    assert after["ignored_by_rule"] == []
    assert after["missing"] == []


# --- the contract is the SHARED .gitignore, not this machine's excludes -----------


def test_a_per_clone_exclude_does_not_satisfy_the_contract(tmp_path):
    _git(tmp_path, "init", "-q", ".")
    _write(tmp_path, "")
    (tmp_path / ".git" / "info" / "exclude").write_text(
        ".prawduct/.critic-active\nCLAUDE.md\n", encoding="utf-8"
    )
    drift = gitignore_contract_drift(tmp_path)
    # Another clone would not have `.git/info/exclude`: the entry is still missing from the contract...
    assert ".prawduct/.critic-active" in drift["missing"]
    # ...and a managed file hidden only on this machine is not a committed-file hazard.
    assert drift["ignored_by_rule"] == []


def test_a_nested_gitignore_in_the_repo_counts(tmp_path):
    _git(tmp_path, "init", "-q", ".")
    _write(tmp_path, "__pycache__/\n")
    (tmp_path / ".prawduct").mkdir()
    (tmp_path / ".prawduct" / ".gitignore").write_text(
        "\n".join(e[len(".prawduct/"):] for e in GITIGNORE_ENTRIES if e.startswith(".prawduct/")) + "\n",
        encoding="utf-8",
    )
    drift = gitignore_contract_drift(tmp_path)
    assert [e for e in drift["missing"] if e.startswith(".prawduct/")] == []


# --- git unavailable: the boundary is stated, not hidden --------------------------


def test_without_git_the_comparison_falls_back_to_literal_lines_and_says_so(tmp_path, monkeypatch):
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    _write(proj, WHOLESALE)
    drift = gitignore_contract_drift(proj)
    assert drift["basis"] == "literal"
    # Literal comparison cannot see the subsumption; that is the documented boundary.
    assert ".prawduct/.critic-active" in drift["missing"]
    assert drift["ignored_by_rule"] == []
    assert update_gitignore(proj, dry_run=True)["basis"] == "literal"


def test_with_git_the_basis_is_git(world):
    _write(world, WHOLESALE)
    assert gitignore_contract_drift(world)["basis"] == "git"


# --- the probe --------------------------------------------------------------------


def test_probe_is_not_a_missing_entries_nag_under_a_wholesale_rule(world):
    _write(world, WHOLESALE)
    out = gp.probe_gitignore_contract_drift(ProjectState({}), Codebase(root=world))
    assert [c.type for c in out] == ["contract-ignored-by-rule"]
    cand = out[0]
    assert "missing" not in cand.trigger_summary
    # The fixer cannot resolve it (it will not edit the owner's rule), so it must not be offered.
    assert cand.recommended_action == ""
    assert ".gitignore:1" in cand.trigger_summary
    # The exact lines to paste ride in the relayed summary.
    assert ".prawduct/*" in cand.trigger_summary
    for line in REINCLUDE:
        assert f"`{line}`" in cand.trigger_summary


def test_probe_is_inert_once_the_rule_is_narrowed(world):
    text = ".prawduct/*\n" + "".join(f"{x}\n" for x in REINCLUDE) + OUTSIDE
    _write(world, text)
    assert gp.probe_gitignore_contract_drift(ProjectState({}), Codebase(root=world)) == []


def test_probe_fires_both_when_entries_missing_and_a_rule_hides_managed_files(tmp_path):
    _git(tmp_path, "init", "-q", ".")
    _write(tmp_path, ".claude/\n")
    out = gp.probe_gitignore_contract_drift(ProjectState({}), Codebase(root=tmp_path))
    assert sorted(c.type for c in out) == ["contract-drift", "contract-ignored-by-rule"]


# --- the fixer's CLI voice --------------------------------------------------------


def _hook(repo: Path, *args: str):
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        [sys.executable, str(ROOT / "bin" / "prawduct-hook"), "update-gitignore", *args],
        capture_output=True, text=True, env=env, timeout=60,
    )


def test_cli_names_the_rule_and_the_lines_and_does_not_claim_it_updated(world):
    gi = _write(world, WHOLESALE)
    before = gi.read_bytes()
    for args in (["--dry-run"], []):
        proc = _hook(world, *args)
        assert proc.returncode == 0, proc.stderr
        assert "ignored by `.prawduct/`" in proc.stdout
        assert ".gitignore:1" in proc.stdout
        assert ".prawduct/*" in proc.stdout
        assert "will not edit" in proc.stdout
        assert "updated .gitignore" not in proc.stdout
        assert gi.read_bytes() == before


# --- the other callers ------------------------------------------------------------


def test_onboard_does_not_append_redundant_entries_under_a_wholesale_rule(world):
    from lib.init_product import run

    gi = _write(world, WHOLESALE)
    before = gi.read_bytes()
    assert run([str(world), "--name", "P", "--apply"]) == 0
    assert gi.read_bytes() == before, "onboard appended lines a wholesale rule already covers"


def test_onboard_dry_run_predicts_no_gitignore_edit_under_a_wholesale_rule(world, capsys):
    import json

    from lib.init_product import run

    _write(world, WHOLESALE)
    assert run([str(world), "--name", "P", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert ".gitignore" not in result["edited"] + result["created"]


def test_a_literal_entry_a_later_negation_undoes_is_not_re_added_forever(world):
    # The fixer appends what is missing; if a literally present line still read as
    # missing (git says the later `!` un-ignores it), every run would append it again
    # and `modified` would never settle.
    entry = ".prawduct/.critic-active"
    rest = [e for e in GITIGNORE_ENTRIES if e != entry]
    gi = _write(world, "\n".join([entry, f"!{entry}", *rest]) + "\n")
    before = gi.read_bytes()
    assert entry not in gitignore_contract_drift(world)["missing"]
    assert update_gitignore(world)["modified"] is False
    assert gi.read_bytes() == before


def test_onboard_reports_the_rule_it_will_not_edit(world, capsys):
    import json

    from lib.init_product import run

    _write(world, WHOLESALE)
    assert run([str(world), "--name", "P", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert sorted(e["path"] for e in result["ignored_by_rule"]) == PRAWDUCT_MANAGED
    assert run([str(world), "--name", "P"]) == 0
    out = capsys.readouterr().out
    assert "cannot fix automatically:" in out and "`.prawduct/`" in out
