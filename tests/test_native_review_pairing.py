"""A development build's boundary review starts the host's native review beside
the Critic (#1130), and nothing else does.

``critic-begin`` decides the pairing once, in code: a ``cumulative`` review, a
development build (``-dev`` in the plugin version), and no
``native_review_pairing: false`` opt-out. When it pairs, the manifest carries a
``native_review`` block — the exact arguments, the wrapper prompt and the text
path — that the coordinator dispatches verbatim. When it does not, the manifest
has no block and the Critic dispatch is unchanged.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import contribution, core, ledger, native_review  # noqa: E402
from lib import critic_consolidate as cc  # noqa: E402

DEV = "3.8.2-dev.1"
RELEASED = "3.8.2"

#: What the paired run must never pass: a flag that writes (to the tree under
#: review or to the PR), or a level the host reserves for an explicit request
#: (`max`, and `ultra`, the cloud review).
FORBIDDEN = ("--fix", "--comment", "--post", "max", "ultra")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()


@pytest.fixture
def branch_repo(tmp_path: Path) -> Path:
    """A feature branch one judgeable commit ahead of ``main``: the committed
    bundle a ``cumulative`` review exists for."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "src").mkdir()
    (repo / "src/app.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "init")
    _git(repo, "switch", "--quiet", "-c", "feature/thing")
    (repo / "src/app.py").write_text("x = 2\n")
    _git(repo, "commit", "--quiet", "-am", "feat: change x")
    (repo / ".prawduct").mkdir()
    return repo.resolve()


def _begin(repo: Path, mode: str, monkeypatch, version: str) -> dict:
    monkeypatch.setattr(core, "PRAWDUCT_VERSION", version)
    result = cc.begin_review(repo, mode, force=True, session_model="claude-opus-5-5")
    assert result["status"] == "ok", result
    return result


class TestDevelopmentBuild:
    def test_the_dev_suffix_is_what_makes_a_development_build(self):
        assert core.is_dev_version(DEV)
        assert core.is_dev_version("3.9.0-dev.12")
        assert not core.is_dev_version(RELEASED)
        # A tree with no VERSION file reads "dev" — not a version string at all,
        # so it is not a development build of one.
        assert not core.is_dev_version("dev")
        assert not core.is_dev_version(None)

    def test_contribution_buckets_ask_the_same_question(self):
        """One home: the contribution bucket and the pairing cannot disagree on
        which builds are development builds."""
        fact = {"actor": {"plugin": DEV}}
        assert contribution.contribution_bucket(fact).endswith("-dev")
        fact = {"actor": {"plugin": RELEASED}}
        assert not contribution.contribution_bucket(fact).endswith("-dev")


class TestPairingDecision:
    @pytest.mark.parametrize("mode", ["chunk", "final", "verify-resolutions"])
    def test_only_the_boundary_review_pairs(self, tmp_path, mode):
        paired, reason = cc.native_review_pairing(tmp_path, mode, version=DEV)
        assert not paired
        assert mode in reason

    def test_a_dev_cumulative_pairs(self, tmp_path):
        assert cc.native_review_pairing(tmp_path, "cumulative", version=DEV) == (True, "paired")

    def test_a_released_build_never_pairs(self, tmp_path):
        paired, reason = cc.native_review_pairing(tmp_path, "cumulative", version=RELEASED)
        assert not paired and "released" in reason

    @pytest.mark.parametrize(
        "line, paired",
        [
            ("native_review_pairing: false\n", False),
            ("native_review_pairing: False\n", False),
            ("native_review_pairing: true\n", True),
            # Only an explicit false opts out: the experiment is the default on
            # development builds, so a typo keeps it running rather than
            # silently ending the measurement.
            ("native_review_pairing: flase\n", True),
            ("other_key: false\n", True),
        ],
    )
    def test_only_an_explicit_false_opts_out(self, tmp_path, line, paired):
        (tmp_path / "project-state.yaml").write_text(line)
        got, reason = cc.native_review_pairing(tmp_path, "cumulative", version=DEV)
        assert got is paired
        if not paired:
            assert "native_review_pairing" in reason


class TestManifestBlock:
    def test_a_dev_cumulative_manifest_carries_the_native_review(self, branch_repo, monkeypatch):
        result = _begin(branch_repo, "cumulative", monkeypatch, DEV)
        manifest = result["manifest"]
        native = manifest["native_review"]
        base, head = manifest["base_commit"], manifest["head_commit"]
        assert native["skill"] == "code-review"
        assert native["level"] == "high"
        assert native["args"] == f"high {base}...{head}"
        assert native["text_path"] == str(
            branch_repo / ".prawduct" / ".native-reviews" / f"{result['id']}.md"
        )
        assert native["dispatched_at"]
        # The wrapper runs on the reviewers' model: the native review runs on
        # its caller's model, so a fair comparison pins the two together.
        assert native["model"] == manifest["reviewer_model"]
        # The prompt is rendered once, here, and carries every value it names.
        for value in (native["args"], native["text_path"], result["id"], str(branch_repo)):
            assert value in native["prompt"]
        assert cc.validate_manifest(manifest) == (True, "")

    def test_the_arguments_never_carry_a_fix_a_post_or_a_costly_level(self, branch_repo, monkeypatch):
        native = _begin(branch_repo, "cumulative", monkeypatch, DEV)["manifest"]["native_review"]
        tokens = native["args"].split()
        assert tokens[0] == "high"  # the level is always explicit, never remembered
        assert not set(tokens) & set(FORBIDDEN)

    def test_a_released_build_writes_no_block(self, branch_repo, monkeypatch):
        manifest = _begin(branch_repo, "cumulative", monkeypatch, RELEASED)["manifest"]
        assert "native_review" not in manifest

    def test_the_opt_out_writes_no_block(self, branch_repo, monkeypatch):
        (branch_repo / ".prawduct" / "project-state.yaml").write_text("native_review_pairing: false\n")
        manifest = _begin(branch_repo, "cumulative", monkeypatch, DEV)["manifest"]
        assert "native_review" not in manifest

    def test_a_dev_final_writes_no_block_and_says_nothing(self, branch_repo, monkeypatch):
        """``final`` reviews uncommitted work, so it has no head commit and would
        skip the block even if the mode guard were gone — the absent note is what
        tells the two apart: a final that the mode guard let through says it
        could not name a range."""
        (branch_repo / "src/app.py").write_text("x = 3\n")
        result = _begin(branch_repo, "final", monkeypatch, DEV)
        assert "native_review" not in result["manifest"]
        assert not [n for n in result["notes"] if "native review" in n], result["notes"]

    def test_the_dispatch_says_why_it_did_not_pair(self, branch_repo, monkeypatch):
        """A development build's boundary review that skips the pairing says so,
        because a silent skip reads as a native review that never landed."""
        (branch_repo / ".prawduct" / "project-state.yaml").write_text("native_review_pairing: false\n")
        notes = _begin(branch_repo, "cumulative", monkeypatch, DEV)["notes"]
        assert any("native review not paired" in n for n in notes), notes


class TestManifestValidation:
    def _manifest(self, branch_repo, monkeypatch) -> dict:
        return _begin(branch_repo, "cumulative", monkeypatch, DEV)["manifest"]

    @pytest.mark.parametrize("token", FORBIDDEN)
    def test_a_forbidden_argument_is_refused(self, branch_repo, monkeypatch, token):
        manifest = self._manifest(branch_repo, monkeypatch)
        manifest["native_review"]["args"] += f" {token}"
        ok, reason = cc.validate_manifest(manifest)
        assert not ok and "native_review" in reason

    @pytest.mark.parametrize("key", ["skill", "args", "level", "text_path", "prompt", "dispatched_at"])
    def test_a_missing_field_is_refused(self, branch_repo, monkeypatch, key):
        manifest = self._manifest(branch_repo, monkeypatch)
        del manifest["native_review"][key]
        ok, reason = cc.validate_manifest(manifest)
        assert not ok and key in reason

    def test_no_block_is_valid(self, branch_repo, monkeypatch):
        manifest = self._manifest(branch_repo, monkeypatch)
        del manifest["native_review"]
        assert cc.validate_manifest(manifest) == (True, "")


class TestDispatchLine:
    """The fork learns of the pairing from what ``critic-begin`` prints — pinned
    at the CLI, because the line is the wiring and a test of the renderer alone
    stays green with the print deleted."""

    @pytest.fixture
    def hook(self):
        import importlib.machinery
        import importlib.util

        path = ROOT / "bin" / "prawduct-hook"
        loader = importlib.machinery.SourceFileLoader("prawduct_hook_native_pairing", str(path))
        module = importlib.util.module_from_spec(
            importlib.util.spec_from_loader("prawduct_hook_native_pairing", loader)
        )
        loader.exec_module(module)
        return module

    def _dispatch(self, hook, repo, monkeypatch, capsys, version) -> "tuple[str, str]":
        monkeypatch.chdir(repo)
        monkeypatch.setattr(core, "PRAWDUCT_VERSION", version)
        rc = hook.cmd_critic_begin(
            repo, ["--mode", "cumulative", "--force", "--session-model", "claude-opus-5-5"]
        )
        captured = capsys.readouterr()
        assert rc == 0, captured.out + captured.err
        return captured.out, captured.err

    def test_a_paired_dispatch_prints_the_native_line(self, hook, branch_repo, monkeypatch, capsys):
        out, _err = self._dispatch(hook, branch_repo, monkeypatch, capsys, DEV)
        lines = [line for line in out.splitlines() if "native review paired" in line]
        assert len(lines) == 1, out
        assert "native_review.prompt" in lines[0]
        assert "general-purpose" in lines[0]

    def test_a_released_dispatch_prints_no_native_line(self, hook, branch_repo, monkeypatch, capsys):
        out, err = self._dispatch(hook, branch_repo, monkeypatch, capsys, RELEASED)
        assert "dispatched" in out  # the dispatch itself happened
        # Nothing new on either channel: dispatch notes go to stderr.
        assert "native review" not in out
        assert "native review" not in err

    def test_control_a_dev_opt_out_says_why_on_stderr(self, hook, branch_repo, monkeypatch, capsys):
        """Control for the stderr half above: the channel does carry the note
        when a development build's boundary review does not pair."""
        (branch_repo / ".prawduct" / "project-state.yaml").write_text("native_review_pairing: false\n")
        out, err = self._dispatch(hook, branch_repo, monkeypatch, capsys, DEV)
        assert "native review paired" not in out
        assert "native review not paired" in err


class TestNativeTextDoesNotVoidTheReview:
    """The wrapper writes the native text while the Critic's reviewers are still
    running. Consolidation refuses a tree changed since dispatch, exempting only
    prawduct's own session files by path — so the text's home must be one of
    them, or every paired review is refused on the experiment's own output."""

    def test_writing_the_native_text_leaves_the_dispatch_tree_unchanged(self, branch_repo, monkeypatch):
        manifest = _begin(branch_repo, "cumulative", monkeypatch, DEV)["manifest"]
        text = Path(manifest["native_review"]["text_path"])
        text.parent.mkdir(parents=True, exist_ok=True)
        text.write_text("Result:\n(none)\n")
        assert cc.tree_changed_since_dispatch(branch_repo, manifest) == ("unchanged", [])

    def test_control_a_product_file_written_mid_review_still_changes_it(self, branch_repo, monkeypatch):
        """Control: the exemption is the text's directory, not every new file."""
        manifest = _begin(branch_repo, "cumulative", monkeypatch, DEV)["manifest"]
        (branch_repo / "src" / "new.py").write_text("y = 1\n")
        status, paths = cc.tree_changed_since_dispatch(branch_repo, manifest)
        assert status == "changed" and "src/new.py" in paths

    def test_the_text_home_is_a_session_path(self):
        assert f".prawduct/{native_review.DIRNAME}/" in core.GITIGNORE_ENTRIES


# --- Chunk 02: the record, and the builder sees both lists -------------------

THREE = """Result:
(none)

```json
[
  {"file": "a.py", "line": 3, "summary": "SECRET-SUMMARY-ONE", "failure_scenario": "x"},
  {"file": "b.py", "line": 9, "summary": "SECRET-SUMMARY-TWO", "failure_scenario": "y"},
  {"file": "c.py", "summary": "SECRET-SUMMARY-THREE", "failure_scenario": "z"}
]
```
"""


class TestParseFindings:
    def test_a_json_array_wins_over_the_none_header(self):
        assert native_review.parse_findings(THREE) == [
            {"file": "a.py", "line": 3}, {"file": "b.py", "line": 9}, {"file": "c.py", "line": None},
        ]

    def test_none_alone_is_an_empty_run(self):
        assert native_review.parse_findings("Result:\n(none)\n\nThe pass found nothing.") == []

    def test_prose_is_not_countable(self):
        """Control for the line above: prose with no ``(none)`` line and no array
        is unknown, never a guessed zero."""
        assert native_review.parse_findings("I looked at the diff and it seemed fine (none found).") is None

    def test_an_array_of_non_objects_is_not_findings(self):
        assert native_review.parse_findings("see [1, 2, 3] in the range") is None


def _paired(repo: Path, monkeypatch) -> dict:
    return _begin(repo, "cumulative", monkeypatch, DEV)


def _ledger_events(repo: Path, kind: str) -> list[dict]:
    path = repo / ".prawduct" / ".governance-ledger.jsonl"
    if not path.is_file():
        return []
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [e for e in events if e.get("event") == kind]


class TestRecord:
    def test_dispatch_writes_the_sidecar_record_reads(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        sidecar = json.loads(native_review.sidecar_path(branch_repo / ".prawduct", result["id"]).read_text())
        manifest = result["manifest"]
        assert sidecar["review_id"] == result["id"]
        assert sidecar["args"] == manifest["native_review"]["args"]
        assert sidecar["head_tree"] == manifest["head_tree"]
        assert sidecar["model"]  # the block's, else the session's the wrapper inherits

    def test_record_appends_one_event_with_counts_and_no_text(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        rc, message = native_review.record(branch_repo, pd, result["id"])
        assert rc == 0, message
        assert "3 finding(s)" in message
        [event] = _ledger_events(branch_repo, "review.native")
        assert event["actor"]["role"] == "native"
        review = event["review"]
        assert review["critic_review_id"] == result["id"]
        assert review["findings"] == [
            {"file": "a.py", "line": 3}, {"file": "b.py", "line": 9}, {"file": "c.py", "line": None},
        ]
        assert review["findings_parsed"] is True
        assert review["level"] == "high"
        assert review["head_tree"] == result["manifest"]["head_tree"]
        # The clock is code's: the dispatch stamp critic-begin wrote.
        assert event["dispatched_at"] == result["manifest"]["native_review"]["dispatched_at"]
        # No finding text in the ledger — not in the event, not anywhere in the file.
        ledger_text = (pd / ".governance-ledger.jsonl").read_text()
        assert "SECRET-SUMMARY" not in ledger_text
        # No fact_id: the native row must never join the Critic's dispositions.
        assert "fact_id" not in review

    def test_record_is_idempotent(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        assert native_review.record(branch_repo, pd, result["id"])[0] == 0
        rc, message = native_review.record(branch_repo, pd, result["id"])
        assert rc == 0 and "already recorded" in message
        assert len(_ledger_events(branch_repo, "review.native")) == 1

    def test_prose_records_as_not_countable(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text("It reads fine to me.")
        rc, message = native_review.record(branch_repo, pd, result["id"])
        assert rc == 0 and "not countable" in message
        [event] = _ledger_events(branch_repo, "review.native")
        assert event["review"]["findings_parsed"] is False

    def test_record_works_after_consolidation_removed_the_manifest(self, branch_repo, monkeypatch):
        """The native run may finish after the Critic consolidates, which deletes
        the manifest — the sidecar is what record reads."""
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        cc.remove_partials(pd)
        assert not cc.manifest_path(pd).exists()
        native_review.text_path(pd, result["id"]).write_text(THREE)
        assert native_review.record(branch_repo, pd, result["id"])[0] == 0

    def test_nothing_to_record_is_refused_with_its_reason(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        rc, reason = native_review.record(branch_repo, pd, result["id"])
        assert rc == 1 and "has not been written" in reason
        rc, reason = native_review.record(branch_repo, pd, "rev-20990101T000000Z-deadbeef")
        assert rc == 1 and "no paired native review" in reason
        assert _ledger_events(branch_repo, "review.native") == []

    @pytest.mark.parametrize("bad", ["../manifest", "rev-1/../../x", "", "rev-a.b"])
    def test_an_id_that_could_leave_the_directory_is_refused(self, tmp_path, bad):
        rc, reason = native_review.record(tmp_path, tmp_path, bad)
        assert rc == 1 and "not a review id" in reason
        rc, reason = native_review.show(tmp_path, bad)
        assert rc == 1 and "not a review id" in reason


class TestShow:
    def test_show_prints_the_newest_text_by_default(self, tmp_path):
        d = tmp_path / native_review.DIRNAME
        d.mkdir()
        old, new = d / "rev-1.md", d / "rev-2.md"
        old.write_text("OLD TEXT")
        new.write_text("NEW TEXT")
        import os
        os.utime(old, (1, 1))
        rc, out = native_review.show(tmp_path)
        assert rc == 0 and "NEW TEXT" in out and "OLD TEXT" not in out
        rc, out = native_review.show(tmp_path, "rev-1")
        assert rc == 0 and "OLD TEXT" in out

    def test_a_missing_text_says_it_may_still_be_running(self, tmp_path):
        rc, reason = native_review.show(tmp_path, "rev-9")
        assert rc == 1 and "still be running" in reason


class TestLedgerKind:
    def test_review_native_cannot_be_hand_appended(self, tmp_path, capsys):
        (tmp_path / ".prawduct").mkdir()
        rc = ledger.ledger_append(tmp_path, ["--event", "review.native"])
        assert rc == 1
        assert "native-review record" in capsys.readouterr().err
        assert "review.native" not in ledger._cli_appendable()

    def test_review_stats_reads_the_native_event_as_its_own_role(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        assert native_review.record(branch_repo, pd, result["id"])[0] == 0
        out = subprocess.run(
            [sys.executable, str(ROOT / "bin" / "prawduct-hook"), "review-stats"],
            cwd=str(branch_repo), capture_output=True, text=True, timeout=60,
        )
        assert out.returncode == 0, out.stderr
        assert "native / " in out.stdout, out.stdout
        assert "0 invalid payload(s)" in out.stdout and "0 unknown kind(s)" in out.stdout


class TestNextAction:
    """The builder's one travelling sentence names the native list (#1130 step 4)."""

    def _consolidate(self, repo: Path, monkeypatch) -> dict:
        result = _paired(repo, monkeypatch)
        manifest = result["manifest"]
        assert manifest["roster"] == ["reviewer"], manifest["roster"]
        partial = {
            "role": "reviewer", "goals": "1-7", "dispatch_id": result["id"],
            "commit_reviewed": manifest["commit_reviewed"], "model": "opus",
            "duration_seconds": 60, "findings": [], "summary": "clean",
        }
        (repo / manifest["rendezvous"]["reviewer"]["partial"]).write_text(json.dumps(partial))
        return result

    def _next_action(self, repo: Path) -> str:
        return json.loads((repo / ".prawduct" / ".critic-findings.json").read_text())["next_action"]

    def test_a_running_native_review_is_named(self, branch_repo, monkeypatch):
        result = self._consolidate(branch_repo, monkeypatch)
        assert cc.consolidate(branch_repo, trigger="explicit") == 0
        sentence = self._next_action(branch_repo)
        assert "native review" in sentence and "still running" in sentence
        assert f"native-review show {result['id']}" in sentence

    def test_a_landed_native_review_is_counted(self, branch_repo, monkeypatch):
        result = self._consolidate(branch_repo, monkeypatch)
        native_review.text_path(branch_repo / ".prawduct", result["id"]).write_text(THREE)
        assert cc.consolidate(branch_repo, trigger="explicit") == 0
        sentence = self._next_action(branch_repo)
        assert "3 finding(s)" in sentence and "still running" not in sentence

    def test_control_an_unpaired_review_says_nothing(self, branch_repo, monkeypatch):
        (branch_repo / ".prawduct" / "project-state.yaml").write_text("native_review_pairing: false\n")
        self._consolidate(branch_repo, monkeypatch)
        assert cc.consolidate(branch_repo, trigger="explicit") == 0
        assert "native review" not in self._next_action(branch_repo)


class TestUntrackedFootprint:
    def test_a_paired_review_leaves_nothing_for_git_to_see(self, branch_repo, monkeypatch):
        """In a repo whose ``.gitignore`` knows nothing of the native reviews —
        any repo before ``update-gitignore`` — the sidecar and the text stay out
        of ``git status``, so no ``git add -A`` commits them."""
        assert not (branch_repo / ".gitignore").exists()
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        status = _git(branch_repo, "status", "--porcelain", "--untracked-files=all")
        assert ".native-reviews" not in status, status
        # Control: the same status call does see an ordinary untracked file.
        (pd / "note.txt").write_text("x")
        assert ".prawduct/note.txt" in _git(branch_repo, "status", "--porcelain", "--untracked-files=all")
