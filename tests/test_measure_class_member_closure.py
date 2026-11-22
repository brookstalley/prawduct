"""Guards for `tools/measure-class-member-closure.py` (#847's D2 go/no-go).

The positive control is the 2026-09-19 incident's shape, with the reviewers' own
sentences: a class finding enumerating `_write`'s OSError sources, then a later
same-scope BLOCKING finding naming the one (`target.parent.mkdir`) the fix left
out. The tool must count it — and must NOT count the same later finding on
another scope, an earlier one, a non-blocking one, or one matching only a file
path. Across two clones holding the same fact, the fact counts once.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "tools" / "measure-class-member-closure.py"
sys.path.insert(0, str(REPO_ROOT / "plugin"))

from lib import evidence  # noqa: E402

_spec = importlib.util.spec_from_file_location("measure_class_member_closure", _TOOL)
tool = importlib.util.module_from_spec(_spec)
sys.modules["measure_class_member_closure"] = tool
_spec.loader.exec_module(tool)

SINCE = dt.datetime(2026, 8, 4, tzinfo=dt.timezone.utc)

#: Round 4 of the 2026-09-19 branch, verbatim in the part that lists members.
ROUND_4 = {
    "fid": "R-2", "severity": "blocking", "goal": "Nothing Is Broken",
    "title": "the example's write-failure guard is silent and covers one of its two hooks",
    "recommendation": (
        "R-1's second named member — \"the example's `_write` has no failure handling\" — was "
        "closed at the one site the finding happened to name. `pytest_sessionfinish` still calls "
        "`_write` bare, and `_write` itself has no guard — `target.parent.mkdir`, "
        "`tempfile.mkstemp`, `os.chmod` and `os.replace` all raise OSError."
    ),
    "files": ["plugin/docs/test-report-contract.md"],
}
#: Round 5, verbatim in the part that names the member left out.
ROUND_5 = {
    "fid": "R-1", "severity": "blocking", "goal": "Nothing Is Broken",
    "title": "R-2 is not resolved: the example's write guard still lets an OSError out of both hooks",
    "recommendation": (
        "The fix guarded three of the four. `plugin/docs/test-report-contract.md:144` is "
        "`target.parent.mkdir(parents=True, exist_ok=True)` OUTSIDE the `try:`."
    ),
    "files": ["plugin/docs/test-report-contract.md"],
}


def _review(fid: str, ts: str, scope: "str | None", findings: list) -> dict:
    return {"kind": "review", "id": fid, "ts": ts, "body": {"scope": scope, "findings": findings}}


def _store(*facts: dict) -> dict:
    return {"status": "ok", "facts": list(facts)}


def _report(*stores: dict) -> dict:
    return tool.build_report(list(stores), SINCE, control_scope="test-report-scope")


class TestThePositiveControl:
    def test_round_four_to_five_is_counted(self):
        report = _report(_store(
            _review("rev-4", "2026-09-19T15:09:27Z", "test-report-scope", [ROUND_4]),
            _review("rev-5", "2026-09-19T15:20:41Z", "test-report-scope", [ROUND_5]),
        ))
        assert report["review_facts"] == 2 and report["class_framed"] >= 1
        assert report["a_enumerated"] == 1
        assert report["b_identifier"] == 1
        (event,) = report["control"]["events"]
        assert event["class_finding"] == "rev-4/R-2" and event["raised_by"] == "rev-5/R-1"
        assert "target.parent.mkdir" in event["members_named"]

    def test_round_four_to_five_reads_in_the_cli(self, tmp_path):
        """The same control through discovery, `read_facts` and the fact-id
        dedupe: two clones holding the same two facts count them once."""
        root = tmp_path / "src"
        for name in ("clone-alpha-xq", "clone-bravo-xq"):
            repo = root / name
            repo.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(repo), check=True,
                           capture_output=True, timeout=15)
            for fid, ts, finding in (("rev-4", "2026-09-19T15:09:27Z", ROUND_4),
                                     ("rev-5", "2026-09-19T15:20:41Z", ROUND_5)):
                envelope = {"schema": evidence.SCHEMA_VERSION, "kind": "review", "id": fid, "ts": ts,
                            "actor": {"session": "s", "worktree": str(repo)},
                            "body": {"scope": "test-report-scope", "findings": [finding]}}
                assert evidence.append_envelope(repo, envelope)["status"] == "appended"
        out = subprocess.run([sys.executable, str(_TOOL), "--root", str(root), "--json"],
                             capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, out.stderr
        report = json.loads(out.stdout)
        assert report["clones"] == 2
        assert report["review_facts"] == 2
        assert report["b_identifier"] == 1
        assert "alpha-xq" not in out.stdout and "bravo-xq" not in out.stdout  # no repo is named


class TestWhatIsNotCounted:
    def test_another_scope_an_earlier_review_and_a_warning_are_not_matches(self):
        later_warning = dict(ROUND_5, severity="warning")
        report = _report(_store(
            _review("rev-0", "2026-09-19T15:00:00Z", "test-report-scope", [ROUND_5]),  # earlier
            _review("rev-4", "2026-09-19T15:09:27Z", "test-report-scope", [ROUND_4]),
            _review("rev-x", "2026-09-19T15:20:41Z", "other-scope", [ROUND_5]),
            _review("rev-w", "2026-09-19T15:30:00Z", "test-report-scope", [later_warning]),
        ))
        assert report["b_identifier"] == 0 and report["b_any_site"] == 0

    def test_a_path_only_match_is_the_upper_bound_not_the_decision(self):
        later = dict(ROUND_5, recommendation="Something else in the same file.")
        report = _report(_store(
            _review("rev-4", "2026-09-19T15:09:27Z", "test-report-scope", [ROUND_4]),
            _review("rev-5", "2026-09-19T15:20:41Z", "test-report-scope", [later]),
        ))
        assert (report["b_identifier"], report["b_any_site"]) == (0, 1)

    def test_an_instance_label_is_not_class_framed(self):
        instance = dict(ROUND_4, recommendation="Scope: instance. `_write` and `os.replace` differ.")
        assert not tool.is_class_framed(instance)
        assert tool.is_class_framed(dict(ROUND_4, recommendation="Scope: CLASS — `a` and `b`."))
        assert tool.is_class_framed({"scope": "class", "recommendation": ""})

    def test_facts_before_the_era_split_are_not_read(self):
        report = _report(_store(
            _review("rev-4", "2026-08-01T00:00:00Z", "test-report-scope", [ROUND_4]),
            _review("rev-5", "2026-08-02T00:00:00Z", "test-report-scope", [ROUND_5]),
        ))
        assert report["review_facts"] == 0 and report["b_identifier"] == 0


class TestTheDecision:
    def test_the_bar_is_three_a_month_on_the_identifier_reading(self):
        assert tool.decide(3.0, 3.0, 3.0)["go"]
        assert not tool.decide(2.9, 9.0, 1.0)["go"]
        assert not tool.decide(2.9, 9.0, 1.0)["robust"]
        assert tool.decide(5.0, 9.0, 4.0)["robust"]

    def test_a_dotted_identifier_is_not_a_path(self):
        """The control's member `target.parent.mkdir` read as `name.ext` and fell
        out of the decision reading until the extension had to be a file's."""
        assert not tool.is_path("target.parent.mkdir")
        assert not tool.is_path("os.replace")
        assert tool.is_path("pyproject.toml") and tool.is_path("plugin/lib/x")

    def test_recorded_members_are_the_sites_when_present(self):
        finding = {"scope": "class", "recommendation": "`noise_a` `noise_b`",
                   "members": [{"id": "m1", "site": "pkg/mod.py::alpha"}, {"id": "m2", "site": "beta_fn"}]}
        assert tool.sites_of(finding) == {"pkg/mod.py::alpha", "beta_fn"}
