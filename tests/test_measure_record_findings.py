"""Guards for `tools/measure-record-findings.py` (#771).

A synthetic evidence store holds one record-only `fixed` BLOCKING finding, one mixed
finding and one no-files finding; the tool must count each in its class. Also pinned:
the record prefixes are the plugin's own object, the era split reads `actor.plugin`,
and only a `fixed` resolution makes a finding round-buying.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "tools" / "measure-record-findings.py"
sys.path.insert(0, str(REPO_ROOT / "plugin"))

from lib import coverage_algebra, evidence  # noqa: E402

_spec = importlib.util.spec_from_file_location("measure_record_findings", _TOOL)
tool = importlib.util.module_from_spec(_spec)
sys.modules["measure_record_findings"] = tool
_spec.loader.exec_module(tool)

CUMULATIVE = "cumulative (bundle review, ready for merge)"
CHUNK = "chunk (incremental review)"


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "product"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(repo), check=True, capture_output=True, timeout=15)
    (repo / ".prawduct").mkdir()
    (repo / ".prawduct" / ".governance-ledger.jsonl").write_text("")  # how the fleet scan finds a repo
    return repo


def _put(repo: Path, kind: str, fact_id: str, body: dict, plugin: str = "3.5.0") -> None:
    envelope = {"schema": evidence.SCHEMA_VERSION, "kind": kind, "id": fact_id, "ts": "2026-11-01T00:00:00Z",
                "actor": {"session": "s", "worktree": str(repo), "plugin": plugin}, "body": body}
    assert evidence.append_envelope(repo, envelope)["status"] == "appended"


def _finding(fid: str, files, severity: str = "blocking") -> dict:
    return {"fid": fid, "severity": severity, "goal": "g", "title": fid, "files": files}


def _fix(repo: Path, rid: str, fid: str, plugin: str = "3.5.0") -> None:
    _put(repo, "resolution", f"res-{rid}-{fid}",
         {"finding": {"review_id": rid, "fid": fid}, "disposition": "fixed", "verified_by": "v"}, plugin)


def _run(root: Path, *extra: str) -> dict:
    out = subprocess.run([sys.executable, str(_TOOL), "--root", str(root), "--json", *extra],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_each_finding_is_counted_in_its_class(tmp_path):
    repo = _repo(tmp_path)
    _put(repo, "review", "rev-1", {"mode": CUMULATIVE, "scope": "s", "findings": [
        _finding("R-1", [".prawduct/artifacts/plan.md", ".claude/rules/learnings/core.md"]),
        _finding("R-2", ["plugin/lib/a.py", ".prawduct/project-state.yaml"], "warning"),
        _finding("R-3", None, "warning"),
        _finding("R-4", ["plugin/lib/b.py"], "warning"),
    ]})
    _fix(repo, "rev-1", "R-1")
    report = _run(tmp_path)
    post = report["cells"]["post"]["boundary"]
    assert (post["all"]["record-only"], post["all"]["mixed"], post["all"]["no-files"], post["all"]["subject-only"]) == (1, 1, 1, 1)
    assert post["fixed"]["record-only"] == 1 and post["fixed"]["total"] == 1
    assert post["fixed"]["record_only_share"] == 1.0
    assert (report["clones"], report["review_facts"], report["findings"]) == (1, 1, 4)
    assert report["no_files_share"] == 0.25
    assert report["severity"]["post"]["boundary"]["blocking"]["fixed"]["record-only"] == 1
    # one record-only finding of one round-buying one at the boundary breaches the 10% bar
    assert report["decision"]["breached"] == ["boundary"]
    assert report["decision"]["undecided"] == ["inner"]  # no inner round-buying findings: no verdict


def test_only_a_fixed_resolution_is_round_buying(tmp_path):
    repo = _repo(tmp_path)
    _put(repo, "review", "rev-1", {"mode": CHUNK, "scope": "s", "findings": [
        _finding("R-1", [".prawduct/a.md"]), _finding("R-2", [".prawduct/b.md"])]})
    _put(repo, "resolution", "res-2", {"finding": {"review_id": "rev-1", "fid": "R-2"},
                                       "disposition": "waived", "verified_by": "v"})
    inner = _run(tmp_path)["cells"]["post"]["inner"]
    assert inner["all"]["record-only"] == 2 and inner["fixed"]["total"] == 0


def test_eras_split_on_actor_plugin(tmp_path):
    repo = _repo(tmp_path)
    for rid, plugin in (("rev-old", "3.4.0"), ("rev-dev1", "3.4.1-dev.1"), ("rev-new", "3.4.1-dev.2"), ("rev-x", "garbage")):
        _put(repo, "review", rid, {"mode": CUMULATIVE, "findings": [_finding("R-1", [".prawduct/a.md"])]}, plugin)
    cells = _run(tmp_path)["cells"]
    assert cells["pre"]["boundary"]["all"]["total"] == 2
    assert cells["post"]["boundary"]["all"]["total"] == 1
    assert cells["unknown"]["boundary"]["all"]["total"] == 1


def test_a_worktree_of_one_clone_is_read_once(tmp_path):
    repo = _repo(tmp_path)
    _put(repo, "review", "rev-1", {"mode": CUMULATIVE, "findings": [_finding("R-1", [".prawduct/a.md"])]})
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"],
                   cwd=str(repo), check=True, capture_output=True, timeout=15)
    wt = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "b2", str(wt)], cwd=str(repo), check=True,
                   capture_output=True, timeout=30)
    (wt / ".prawduct").mkdir(exist_ok=True)
    (wt / ".prawduct" / ".governance-ledger.jsonl").write_text("")
    report = _run(tmp_path)
    assert report["clones"] == 1 and report["review_facts"] == 1


def test_record_prefixes_are_the_plugins_object():
    """A restated prefix list would keep classifying by yesterday's oracle set."""
    assert tool.coverage_algebra.RECORD_PREFIXES is coverage_algebra.RECORD_PREFIXES
    assert tool.classify([".prawduct/x"]) == "record-only"
    assert tool.classify(["./.claude/rules/learnings/core.md"]) == "record-only"
    assert tool.classify([]) == "no-files" and tool.classify(None) == "no-files"


def test_the_fleet_scan_with_nothing_to_read_exits_loudly(tmp_path):
    out = subprocess.run([sys.executable, str(_TOOL), "--root", str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert out.returncode != 0 and "no governed repos" in out.stderr
