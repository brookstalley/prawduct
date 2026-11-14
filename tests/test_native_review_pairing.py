"""A development build's boundary review, and a sample of its inner ``chunk``
and ``verify-resolutions`` reviews, start the host's native review beside the
Critic (#1130, #1166), and nothing else does.

``critic-begin`` decides the pairing once, in code: a ``cumulative`` review or
a sampled inner one, a development build (``-dev`` in the plugin version), and
no ``native_review_pairing: false`` opt-out. When it pairs, the manifest carries a
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
    def test_final_never_pairs(self, tmp_path, monkeypatch):
        """``final`` is an inner review the owner did not ask to sample — rare,
        and not where the Critic's correctness volume is. Even an id the sample
        would take does not pair it."""
        monkeypatch.setattr(cc, "native_review_sampled", lambda _id: True)
        paired, reason = cc.native_review_pairing(tmp_path, "final", version=DEV, review_id="rev-x")
        assert not paired
        assert "final" in reason

    @pytest.mark.parametrize("mode", ["chunk", "verify-resolutions"])
    def test_an_unsampled_inner_review_does_not_pair(self, tmp_path, monkeypatch, mode):
        monkeypatch.setattr(cc, "native_review_sampled", lambda _id: False)
        paired, reason = cc.native_review_pairing(tmp_path, mode, version=DEV, review_id="rev-x")
        assert not paired
        assert "sample" in reason

    @pytest.mark.parametrize("mode", ["chunk", "verify-resolutions"])
    def test_a_sampled_inner_review_pairs(self, tmp_path, monkeypatch, mode):
        monkeypatch.setattr(cc, "native_review_sampled", lambda _id: True)
        assert cc.native_review_pairing(tmp_path, mode, version=DEV, review_id="rev-x") == (True, "paired")

    @pytest.mark.parametrize("mode", ["chunk", "verify-resolutions"])
    def test_a_sampled_inner_review_still_honours_release_and_opt_out(self, tmp_path, monkeypatch, mode):
        monkeypatch.setattr(cc, "native_review_sampled", lambda _id: True)
        assert not cc.native_review_pairing(tmp_path, mode, version=RELEASED, review_id="rev-x")[0]
        (tmp_path / "project-state.yaml").write_text("native_review_pairing: false\n")
        assert not cc.native_review_pairing(tmp_path, mode, version=DEV, review_id="rev-x")[0]

    def test_the_sample_is_one_in_six_and_reproducible(self):
        """Chosen from the review id, so the same review always gets the same
        answer and no clock or random state decides what is measured."""
        ids = [f"rev-20261113T{i:06d}Z-{i * 7919 % 16**8:08x}" for i in range(1200)]
        taken = [i for i in ids if cc.native_review_sampled(i)]
        assert cc.NATIVE_REVIEW_INNER_SAMPLE == 6
        assert 140 <= len(taken) <= 260, len(taken)
        assert [i for i in ids if cc.native_review_sampled(i)] == taken
        assert not cc.native_review_sampled(None)

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

    @pytest.mark.parametrize("key, bad", [("mode", "final"), ("mode", "bogus"), ("synthetic_range", "yes")])
    def test_a_mode_that_does_not_pair_or_a_non_boolean_range_kind_is_refused(
        self, branch_repo, monkeypatch, key, bad,
    ):
        manifest = self._manifest(branch_repo, monkeypatch)
        manifest["native_review"][key] = bad
        ok, reason = cc.validate_manifest(manifest)
        assert not ok and f"native_review.{key}" in reason

    @pytest.mark.parametrize("mode", ["cumulative", "chunk", "verify-resolutions"])
    def test_control_every_mode_that_pairs_is_valid(self, branch_repo, monkeypatch, mode):
        manifest = self._manifest(branch_repo, monkeypatch)
        manifest["native_review"].update(mode=mode, synthetic_range=True)
        assert cc.validate_manifest(manifest) == (True, "")

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

    # Renegotiated at the boundary review (R-1): this case once read
    # "Result:\n(none)\n\nThe pass found nothing." and expected an empty run.
    # The wrapper writes what FOLLOWS `Result:`, so the host's header is the
    # text's first line — and the host prints that `(none)` on every result,
    # whatever the review found. A leading `(none)` is therefore no answer.
    def test_a_lone_none_is_an_empty_run(self):
        assert native_review.parse_findings("(none)\n") == []

    def test_the_host_header_alone_before_prose_is_not_countable(self):
        text = "(none)\n\nThe pass found one wrong condition in a.py and an unchecked None in b.py."
        assert native_review.parse_findings(text) is None

    # #1161: a wrapper that keeps the `Result:` line puts the host's header on
    # the SECOND line, where the first-line strip never looked.
    def test_a_kept_result_line_does_not_hide_the_host_header(self):
        text = "Result:\n(none)\n\nThe pass found one wrong condition in a.py."
        assert native_review.parse_findings(text) is None

    def test_a_result_line_and_header_on_one_line_is_still_the_header(self):
        assert native_review.parse_findings("Result: (none)\n\nThe pass found a bug in a.py.") is None

    @pytest.mark.parametrize("text", [
        "Result:\n\n(none)\n\nThe pass found a bug in a.py.",   # a blank line between them
        "Result: (none)\n\nThe pass found a bug in a.py.",       # one line
        "\n\nResult:\n(none)\n\nThe pass found a bug in a.py.",  # leading blank lines
    ])
    def test_every_layout_of_the_header_is_the_header(self, text):
        """The paired native review on #1161: the header's answer must not depend
        on its layout — each of these is header plus prose, so not countable."""
        assert native_review.parse_findings(text) is None

    @pytest.mark.parametrize("text", ["Result:\n(none)\n", "Result: (none)\n", "Result:\n\n(none)"])
    def test_every_layout_of_a_header_alone_is_an_empty_run(self, text):
        assert native_review.parse_findings(text) == []

    def test_a_kept_result_line_with_nothing_after_the_header_is_an_empty_run(self):
        assert native_review.parse_findings("Result:\n(none)\n") == []

    def test_the_reviews_own_none_after_the_header_is_an_empty_run(self):
        assert native_review.parse_findings("(none)\n\nI read the diff once.\n\n(none)\n") == []

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
        [event] = _ledger_events(branch_repo, "native.review")
        # Boundary review R-2: every ledger reader, older builds included, takes a
        # `review.*` event with a `review` payload as a Critic review — this one
        # must look like neither, so those readers skip it as unknown.
        assert not event["event"].startswith("review.") and "review" not in event
        assert event["actor"]["role"] == "native"
        review = event["native"]
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
        assert len(_ledger_events(branch_repo, "native.review")) == 1

    def test_prose_records_as_not_countable(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text("It reads fine to me.")
        rc, message = native_review.record(branch_repo, pd, result["id"])
        assert rc == 0 and "not countable" in message
        [event] = _ledger_events(branch_repo, "native.review")
        assert event["native"]["findings_parsed"] is False

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
        assert _ledger_events(branch_repo, "native.review") == []

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
        rc = ledger.ledger_append(tmp_path, ["--event", "native.review"])
        assert rc == 1
        assert "native-review record" in capsys.readouterr().err
        assert "native.review" not in ledger._cli_appendable()

    def test_review_stats_reports_native_runs_apart_and_in_no_critic_total(self, branch_repo, monkeypatch):
        """Renegotiated in Chunk 03: Chunk 02 let the native event read as a role
        in the Critic's grouping, and so into `overall`, the stage and span rows
        and every other Critic total — a boundary review's yield inflated by a
        second instrument. The contract now: a native run moves no Critic figure
        and is reported on its own."""
        TestNextAction()._consolidate(branch_repo, monkeypatch)
        assert cc.consolidate(branch_repo, trigger="explicit") == 0

        def stats() -> dict:
            out = subprocess.run(
                [sys.executable, str(ROOT / "bin" / "prawduct-hook"), "review-stats", "--json"],
                cwd=str(branch_repo), capture_output=True, text=True, timeout=60,
            )
            assert out.returncode == 0, out.stderr
            return json.loads(out.stdout)

        before = stats()
        assert before["events_total"] == 1  # the Critic's review, read
        assert before["native_review"]["runs"] == 0
        pd = branch_repo / ".prawduct"
        review_id = json.loads((pd / ".critic-findings.json").read_text())["fact_id"]
        native_review.text_path(pd, review_id).write_text(THREE)
        assert native_review.record(branch_repo, pd, review_id)[0] == 0
        after = stats()
        for key in ("events_total", "overall", "by_role_model_mode", "by_stage", "by_span", "by_scope"):
            assert after[key] == before[key], key
        assert after["skipped"] == before["skipped"]  # neither dropped nor misread
        assert after["native_review"]["runs"] == 1
        assert after["native_review"]["findings"] == 3
        assert after["native_review"]["countable_runs"] == 1
        human = subprocess.run(
            [sys.executable, str(ROOT / "bin" / "prawduct-hook"), "review-stats"],
            cwd=str(branch_repo), capture_output=True, text=True, timeout=60,
        ).stdout
        # Renegotiated with the inner sample: one line per stage, since pooled
        # inner and boundary runs give a median that describes neither.
        assert "native review, boundary (paired, #1130; in no total here): 1 run(s)" in human, human
        assert after["native_review"]["by_stage"]["boundary"]["runs"] == 1


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

    def test_an_unlanded_native_review_is_named_without_going_stale(self, branch_repo, monkeypatch):
        """The record outlives the moment it was written (the next session's
        briefing reads it), so it says the run MAY still be running — never that
        it is."""
        result = self._consolidate(branch_repo, monkeypatch)
        assert cc.consolidate(branch_repo, trigger="explicit") == 0
        sentence = self._next_action(branch_repo)
        assert "native review" in sentence and "may still be running" in sentence
        assert "is still running" not in sentence
        assert f"native-review show {result['id']}" in sentence

    def test_a_landed_native_review_is_counted(self, branch_repo, monkeypatch):
        result = self._consolidate(branch_repo, monkeypatch)
        native_review.text_path(branch_repo / ".prawduct", result["id"]).write_text(THREE)
        assert cc.consolidate(branch_repo, trigger="explicit") == 0
        sentence = self._next_action(branch_repo)
        assert "(3 finding(s))" in sentence and "still running" not in sentence

    def test_the_record_rendered_from_the_fact_names_it_too(self, branch_repo, monkeypatch):
        """Boundary review R-5: the clause belongs to the record, so a clone that
        re-renders `.critic-findings.json` from the fact (`derive_branch_cache`)
        tells its builder the same thing consolidation did."""
        result = self._consolidate(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        assert cc.consolidate(branch_repo, trigger="explicit") == 0
        (pd / ".critic-findings.json").unlink()
        from lib import evidence

        facts = evidence.read_facts(branch_repo)["facts"]
        head = result["manifest"]["commit_reviewed"]
        derived = cc.derive_branch_cache(pd, facts, [head])
        assert derived["status"] == "derived", derived
        assert "(3 finding(s))" in self._next_action(branch_repo)

    def test_a_landed_text_that_is_not_countable_says_so(self, branch_repo, monkeypatch):
        """#1161: "may still be running" is false once the text has landed; a text
        that holds no countable answer says it landed and is not countable."""
        result = self._consolidate(branch_repo, monkeypatch)
        native_review.text_path(branch_repo / ".prawduct", result["id"]).write_text(
            "(none)\n\nI looked at the diff; two things worried me."
        )
        assert cc.consolidate(branch_repo, trigger="explicit") == 0
        sentence = self._next_action(branch_repo)
        assert "(landed, not countable)" in sentence and "may still be running" not in sentence

    def test_a_text_that_cannot_be_read_is_not_called_running(self, branch_repo, monkeypatch):
        result = self._consolidate(branch_repo, monkeypatch)
        native_review.text_path(branch_repo / ".prawduct", result["id"]).mkdir()  # exists, unreadable
        assert cc.consolidate(branch_repo, trigger="explicit") == 0
        sentence = self._next_action(branch_repo)
        assert "(text unreadable)" in sentence and "may still be running" not in sentence

    def test_a_text_with_bad_bytes_neither_breaks_record_nor_consolidate(self, branch_repo, monkeypatch):
        """Boundary review R-7: the text is model output; one undecodable byte
        must not make every retry fail."""
        result = self._consolidate(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_bytes(b"(none)\n\n\xff\xfe broken\n\n(none)\n")
        assert cc.consolidate(branch_repo, trigger="explicit") == 0
        assert "(0 finding(s))" in self._next_action(branch_repo)
        assert native_review.record(branch_repo, pd, result["id"])[0] == 0

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


class TestRecordCommandBinary:
    def test_the_wrapper_records_with_the_binary_that_dispatched(self, branch_repo, monkeypatch):
        """The sidecar's writer and reader must be one build: the prompt names the
        dispatching plugin's own hook, never whatever `prawduct-hook` PATH finds
        (a framework checkout and its installed plugin differ)."""
        result = _paired(branch_repo, monkeypatch)
        command = cc.native_review_record_command(result["id"])
        assert str(core.FRAMEWORK_DIR / "bin" / "prawduct-hook") in command
        assert command.endswith(f"native-review record {result['id']}")
        prompt = result["manifest"]["native_review"]["prompt"]
        assert command in prompt
        # Control: the PATH form is not what the prompt carries.
        assert f"`prawduct-hook native-review record {result['id']}`" not in prompt


class TestSidecarFailure:
    def test_an_unwritable_sidecar_costs_a_note_not_the_review(self, branch_repo, monkeypatch):
        def boom(*_a, **_k):
            raise OSError("disk full")

        monkeypatch.setattr(native_review, "write_dispatch", boom)
        result = _paired(branch_repo, monkeypatch)
        assert result["status"] == "ok"
        assert "native_review" in result["manifest"]
        assert any("dispatch record was not written" in n and "disk full" in n for n in result["notes"]), result["notes"]


# --- The inner sample (#1166) --------------------------------------------------


def _inner(repo: Path, monkeypatch, mode: str = "chunk") -> dict:
    """A sampled inner review of a dirty working tree: the shape most inner
    reviews have, with no head commit to name."""
    monkeypatch.setattr(cc, "native_review_sampled", lambda _id: True)
    (repo / "src/app.py").write_text("x = 3\n")
    (repo / "src/new.py").write_text("y = 1\n")  # untracked: the Critic's capture takes it in
    return _begin(repo, mode, monkeypatch, DEV)


def _range(args: str) -> "tuple[str, str]":
    level, span = args.split()
    assert level == "high"
    base, head = span.split("...")
    return base, head


class TestInnerRange:
    def test_a_dirty_tree_range_diffs_to_exactly_the_reviewed_interval(self, branch_repo, monkeypatch):
        """The native review takes a commit range and an inner review usually
        reads a working tree; the range must still be the Critic's interval,
        untracked files included."""
        result = _inner(branch_repo, monkeypatch)
        manifest = result["manifest"]
        assert manifest["head_commit"] is None  # the shape that needed naming
        base, head = _range(manifest["native_review"]["args"])
        assert manifest["native_review"]["synthetic_range"] is True
        assert _git(branch_repo, "diff", f"{base}...{head}") == _git(
            branch_repo, "diff", manifest["base_tree"], manifest["head_tree"]
        )
        changed = _git(branch_repo, "diff", "--name-only", f"{base}...{head}").split()
        assert sorted(changed) == ["src/app.py", "src/new.py"]

    def test_naming_the_range_moves_no_ref_index_or_file(self, branch_repo, monkeypatch):
        """An independent reviewer never mutates the session it reviews: the two
        commits are unreachable objects, nothing else."""
        (branch_repo / "src/app.py").write_text("x = 3\n")
        before = (
            _git(branch_repo, "for-each-ref"), _git(branch_repo, "rev-parse", "HEAD"),
            _git(branch_repo, "status", "--porcelain", "--untracked-files=all", "--", "src"),
            _git(branch_repo, "stash", "list"),
        )
        manifest = _inner(branch_repo, monkeypatch)["manifest"]
        # `_inner` wrote src/new.py, so the status after it differs by that file alone.
        after = (
            _git(branch_repo, "for-each-ref"), _git(branch_repo, "rev-parse", "HEAD"),
            _git(branch_repo, "status", "--porcelain", "--untracked-files=all", "--", "src"),
            _git(branch_repo, "stash", "list"),
        )
        assert before[:2] == after[:2] and before[3] == after[3]
        status = lambda out: {line.strip() for line in out.splitlines()}  # noqa: E731
        assert status(after[2]) == status(before[2]) | {"?? src/new.py"}
        _base, head = _range(manifest["native_review"]["args"])
        assert _git(branch_repo, "branch", "--contains", head) == ""

    def test_a_base_with_no_commit_is_named_from_its_tree(self, branch_repo):
        """``verify-resolutions`` after a ``chunk`` review starts from a dirty
        tree the earlier review saw, which no commit holds."""
        (branch_repo / "src/app.py").write_text("x = 5\n")
        base_tree = _git(branch_repo, "write-tree")  # index unchanged: HEAD's tree
        _git(branch_repo, "add", "src/app.py")
        mid_tree = _git(branch_repo, "write-tree")
        (branch_repo / "src/app.py").write_text("x = 6\n")
        _git(branch_repo, "add", "src/app.py")
        head_tree = _git(branch_repo, "write-tree")
        _git(branch_repo, "reset", "--quiet")
        got = cc.native_review_range(branch_repo, None, mid_tree, None, head_tree, "rev-t")
        assert got["status"] == "ok", got
        assert got["synthetic"] is True
        assert _git(branch_repo, "diff", f"{got['base']}...{got['head']}") == _git(
            branch_repo, "diff", mid_tree, head_tree
        )
        assert base_tree != mid_tree  # the fixture's base really is no commit's tree

    def test_real_commits_are_passed_through(self, branch_repo):
        base = _git(branch_repo, "rev-parse", "main")
        head = _git(branch_repo, "rev-parse", "HEAD")
        got = cc.native_review_range(branch_repo, base, "t", head, "t", "rev-t")
        assert got == {"status": "ok", "base": base, "head": head, "synthetic": False}

    def test_a_range_that_cannot_be_named_is_a_note_not_an_error(self, branch_repo, monkeypatch):
        monkeypatch.setattr(
            cc, "native_review_range", lambda *_a: {"status": "error", "reason": "commit-tree failed"}
        )
        result = _inner(branch_repo, monkeypatch)
        assert "native_review" not in result["manifest"]
        assert any("native review not paired" in n and "commit-tree failed" in n for n in result["notes"])

    def test_a_bad_tree_reports_why(self, branch_repo):
        got = cc.native_review_range(branch_repo, None, "0" * 40, None, "0" * 40, "rev-t")
        assert got["status"] == "error" and got["reason"]

    def test_control_an_unsampled_inner_review_writes_and_says_nothing(self, branch_repo, monkeypatch):
        monkeypatch.setattr(cc, "native_review_sampled", lambda _id: False)
        (branch_repo / "src/app.py").write_text("x = 3\n")
        result = _begin(branch_repo, "chunk", monkeypatch, DEV)
        assert "native_review" not in result["manifest"]
        assert not [n for n in result["notes"] if "native review" in n], result["notes"]
        assert not native_review.reviews_dir(branch_repo / ".prawduct").exists()


class TestInnerRecord:
    def test_the_event_says_what_kind_of_review_it_was_paired_with(self, branch_repo, monkeypatch):
        result = _inner(branch_repo, monkeypatch, "chunk")
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        assert native_review.record(branch_repo, pd, result["id"])[0] == 0
        [event] = _ledger_events(branch_repo, "native.review")
        assert event["native"]["mode"] == "chunk"
        assert event["native"]["stage"] == "inner"
        assert event["native"]["synthetic_range"] is True
        assert event["native"]["tree_moved"] is False

    def test_a_boundary_event_is_unchanged(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        assert native_review.record(branch_repo, pd, result["id"])[0] == 0
        [event] = _ledger_events(branch_repo, "native.review")
        assert (event["native"]["mode"], event["native"]["stage"]) == ("cumulative", "boundary")
        assert event["native"]["synthetic_range"] is False

    def test_an_edit_to_a_reviewed_file_before_the_record_is_noted(self, branch_repo, monkeypatch):
        """The native review reads source from the working tree, and an inner
        Critic pass finishes well before it: a builder fixing a reviewed file in
        between changes what the native run read."""
        result = _inner(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        (branch_repo / "src/app.py").write_text("x = 4\n")
        assert native_review.record(branch_repo, pd, result["id"])[0] == 0
        [event] = _ledger_events(branch_repo, "native.review")
        assert event["native"]["tree_moved"] is True

    def test_control_an_edit_outside_the_interval_is_not_a_move(self, branch_repo, monkeypatch):
        result = _inner(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        (branch_repo / "README.md").write_text("unrelated\n")
        assert native_review.record(branch_repo, pd, result["id"])[0] == 0
        [event] = _ledger_events(branch_repo, "native.review")
        assert event["native"]["tree_moved"] is False

    def test_an_edit_to_a_reviewed_doc_is_a_move(self, branch_repo, monkeypatch):
        """The native review reads docs too: a plain doc in the interval, edited
        before the run lands, is a move even though it is not judgeable."""
        (branch_repo / "docs").mkdir()
        (branch_repo / "docs/guide.md").write_text("one\n")
        result = _inner(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        (branch_repo / "docs/guide.md").write_text("two\n")
        assert native_review.record(branch_repo, pd, result["id"])[0] == 0
        [event] = _ledger_events(branch_repo, "native.review")
        assert event["native"]["tree_moved"] is True

    def test_control_a_prawduct_record_written_during_the_run_is_not_a_move(self, branch_repo, monkeypatch):
        """Consolidation and the builder write `.prawduct/` during any review;
        this fixture tracks it (no `.gitignore`), so the record is in the
        reviewed interval."""
        (branch_repo / ".prawduct" / "notes.md").write_text("one\n")
        result = _inner(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        (pd / "notes.md").write_text("two\n")
        assert native_review.record(branch_repo, pd, result["id"])[0] == 0
        [event] = _ledger_events(branch_repo, "native.review")
        assert event["native"]["tree_moved"] is False

    def test_a_sidecar_from_before_the_inner_sample_records_as_boundary(self, branch_repo, monkeypatch):
        """A native run in flight across the upgrade has a sidecar with no mode
        or stage; every such run was a boundary pairing."""
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        path = native_review.sidecar_path(pd, result["id"])
        sidecar = json.loads(path.read_text())
        for key in ("mode", "stage", "synthetic_range"):
            sidecar.pop(key)
        path.write_text(json.dumps(sidecar))
        native_review.text_path(pd, result["id"]).write_text(THREE)
        assert native_review.record(branch_repo, pd, result["id"])[0] == 0
        [event] = _ledger_events(branch_repo, "native.review")
        assert (event["native"]["mode"], event["native"]["stage"]) == ("cumulative", "boundary")
        assert event["native"]["synthetic_range"] is False


class TestInnerRunIsNotPutToTheBuilder:
    def test_an_inner_run_adds_no_clause(self, branch_repo, monkeypatch):
        """A second, unrated list beside an inner pass would manufacture rounds;
        the boundary pairing puts the same code's native findings to the builder."""
        result = _inner(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        assert native_review.next_action_clause(pd, result["id"]) == ""
        # Still readable on request.
        rc, text = native_review.show(pd, result["id"])
        assert rc == 0 and "SECRET-SUMMARY-ONE" in text

    def test_a_sidecar_that_cannot_be_read_still_names_the_list(self, branch_repo, monkeypatch):
        """Only a sidecar that says inner silences the clause: one that exists
        and cannot be read still means a native list was dispatched."""
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        native_review.sidecar_path(pd, result["id"]).write_text("{truncated")
        assert "(3 finding(s))" in native_review.next_action_clause(pd, result["id"])

    def test_control_a_boundary_run_adds_its_clause(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        assert "(3 finding(s))" in native_review.next_action_clause(pd, result["id"])


class TestReviewStatsByStage:
    def _event(self, stage, seconds, findings):
        native = {"findings": [{"file": "a.py", "line": 1}] * findings, "findings_parsed": True}
        if stage is not None:
            native["stage"] = stage
        return {"event": "native.review", "native": native, "duration_seconds": seconds}

    def test_inner_and_boundary_runs_are_reported_apart(self, monkeypatch):
        from lib import telemetry

        monkeypatch.setattr(telemetry, "_measured_duration", lambda e: e["duration_seconds"])
        block = telemetry._native_block([
            self._event("inner", 60, 1), self._event("boundary", 300, 4), self._event(None, 280, 2),
        ])
        assert block["runs"] == 3
        # An event from before the stage was recorded is a boundary run.
        assert block["by_stage"]["boundary"]["runs"] == 2
        assert block["by_stage"]["boundary"]["findings"] == 6
        assert block["by_stage"]["inner"]["runs"] == 1
        assert block["by_stage"]["inner"]["duration_measured"]["median_seconds"] == 60
        lines = telemetry._native_line(block)
        assert [line.split(" (")[0] for line in lines] == ["native review, boundary", "native review, inner"]


class TestTreePins:
    """A native run's reviewed trees are pinned, so `git gc` cannot prune them
    before the experiment's blind verification reads the code at them (#1174).

    A dirty working tree's tree is written through a temporary index, so nothing
    else references it; git prunes an unreferenced object after gc.pruneExpire."""

    @staticmethod
    def _kind(repo: Path, sha: str) -> str:
        import subprocess  # noqa: PLC0415 — only this class reads object kinds directly

        return subprocess.run(  # noqa: S603 — list-form argv, no shell (project preference)
            ["git", "-C", str(repo), "cat-file", "-t", sha], capture_output=True, text=True,
        ).stdout.strip()

    def _recorded(self, repo, monkeypatch):
        result = _inner(repo, monkeypatch)
        pd = repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        rc, message = native_review.record(repo, pd, result["id"])
        assert rc == 0, message
        [event] = _ledger_events(repo, "native.review")
        self.message = message
        return result, event["native"]

    def test_record_pins_both_trees(self, branch_repo, monkeypatch):
        result, native = self._recorded(branch_repo, monkeypatch)
        assert "could not be pinned" not in self.message
        # Read from the refs, never stored: a later pin is never contradicted.
        assert "trees_pinned" not in native
        for name in ("base", "head"):
            ref = f"{native_review.PIN_PREFIX}/{result['id']}/{name}"
            assert _git(branch_repo, "rev-parse", ref) == native[f"{name}_tree"]

    def test_a_pinned_tree_survives_gc_and_an_unpinned_one_does_not(self, branch_repo, monkeypatch):
        result, native = self._recorded(branch_repo, monkeypatch)
        head = native["head_tree"]
        _git(branch_repo, "gc", "--quiet", "--prune=now")
        assert self._kind(branch_repo, head) == "tree", "the pin must keep the reviewed tree"
        # The control: drop the pins and the same tree goes, which is the risk.
        for name in ("base", "head"):
            _git(branch_repo, "update-ref", "-d", f"{native_review.PIN_PREFIX}/{result['id']}/{name}")
        _git(branch_repo, "reflog", "expire", "--expire=now", "--all")
        _git(branch_repo, "gc", "--quiet", "--prune=now")
        assert self._kind(branch_repo, head) != "tree", "without the pin nothing references the tree"

    def test_a_record_already_made_still_pins(self, branch_repo, monkeypatch):
        # Re-running record is how a run recorded before pins existed gets one.
        result, native = self._recorded(branch_repo, monkeypatch)
        ref = f"{native_review.PIN_PREFIX}/{result['id']}/head"
        _git(branch_repo, "update-ref", "-d", ref)
        rc, message = native_review.record(branch_repo, branch_repo / ".prawduct", result["id"])
        assert rc == 0 and "already recorded" in message
        assert _git(branch_repo, "rev-parse", ref) == native["head_tree"]

    def test_a_pin_that_fails_never_blocks_the_record(self, branch_repo, monkeypatch):
        from lib import evidence  # noqa: PLC0415 — native_review imports it lazily, so patch its home

        real = evidence.run_git

        def failing(project_dir, *args, **kw):
            if args and args[0] == "update-ref":
                return 1, "", "locked"
            return real(project_dir, *args, **kw)

        monkeypatch.setattr(evidence, "run_git", failing)
        result, _native = self._recorded(branch_repo, monkeypatch)
        assert "could not be pinned" in self.message, "the one line the wrapper reports must say so"
        # The re-run is the remedy the message names; it says so again while the pin still fails.
        rc, again = native_review.record(branch_repo, branch_repo / ".prawduct", result["id"])
        assert rc == 0 and "already recorded" in again and "could not be pinned" in again

    def test_an_unsafe_review_id_pins_nothing(self, branch_repo):
        # A name git accepts as a ref path but that is no review id: without the
        # check it would write refs/prawduct/native-trees/heads/main/{base,head}.
        tree = _git(branch_repo, "rev-parse", "HEAD^{tree}")
        assert native_review.pin_trees(branch_repo, "heads/main", tree, tree) is False
        listed = _git(branch_repo, "for-each-ref", "--format=%(refname)", native_review.PIN_PREFIX)
        assert listed == "", listed
