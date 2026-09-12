"""Tests for F10 — operator-verification queue."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1] / "plugin"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import operator_verification as ov  # noqa: E402


# =============================================================================
# Parser + round-trip
# =============================================================================


class TestParseOperatorVerification:
    def test_empty_content(self):
        preamble, entries = ov.parse_operator_verification("")
        assert preamble == ""
        assert entries == []

    def test_preamble_only(self):
        preamble, entries = ov.parse_operator_verification(
            "# Header\n\nSome intro prose.\n"
        )
        assert "# Header" in preamble
        assert entries == []

    def test_single_entry(self):
        content = (
            "# Header\n"
            "\n"
            "## VRF-001 — Chunk 14 — sample\n"
            "\n"
            "**Status:** pending\n"
            "**Added:** 2026-05-19\n"
        )
        preamble, entries = ov.parse_operator_verification(content)
        assert "# Header" in preamble
        assert len(entries) == 1
        assert entries[0].vrf_id == "VRF-001"
        assert entries[0].status == "pending"

    def test_multiple_entries_in_order(self):
        content = (
            "## VRF-001 — Chunk 1 — first\n"
            "**Status:** verified\n"
            "\n"
            "## VRF-002 — Chunk 2 — second\n"
            "**Status:** pending\n"
            "\n"
            "## VRF-003 — Chunk 3 — third\n"
            "**Status:** accepted\n"
        )
        _, entries = ov.parse_operator_verification(content)
        assert [e.vrf_id for e in entries] == ["VRF-001", "VRF-002", "VRF-003"]
        assert [e.status for e in entries] == ["verified", "pending", "accepted"]

    def test_unrelated_heading_treated_as_preamble(self):
        # Headings that don't match ``## VRF-`` shouldn't accidentally be
        # parsed as queue entries (e.g. ``## Notes``).
        content = (
            "# Title\n"
            "## Notes\n"
            "Just a notes section, not a VRF entry.\n"
            "## VRF-001 — Chunk N — real entry\n"
            "**Status:** pending\n"
        )
        preamble, entries = ov.parse_operator_verification(content)
        assert "## Notes" in preamble
        assert "Just a notes section" in preamble
        assert len(entries) == 1
        assert entries[0].vrf_id == "VRF-001"

    def test_missing_status_line_defaults_to_pending(self):
        # Missing/malformed status falls back to pending so the gate
        # surfaces the problem rather than silently passing.
        content = (
            "## VRF-001 — sample\n"
            "Body without a Status line at all.\n"
        )
        _, entries = ov.parse_operator_verification(content)
        assert entries[0].status == "pending"

    def test_unknown_status_value_defaults_to_pending(self):
        content = (
            "## VRF-001 — sample\n"
            "**Status:** wibble\n"
        )
        _, entries = ov.parse_operator_verification(content)
        assert entries[0].status == "pending"

    def test_round_trip_preserves_body(self):
        content = (
            "# Header\n"
            "<!-- comment -->\n"
            "\n"
            "## VRF-001 — Chunk 14 — sample\n"
            "\n"
            "**Status:** pending\n"
            "**Added:** 2026-05-19\n"
            "**Where to verify:** somewhere\n"
            "\n"
            "**Verify:**\n"
            "- thing 1\n"
            "- thing 2\n"
        )
        preamble, entries = ov.parse_operator_verification(content)
        out = ov.format_operator_verification(preamble, entries)
        # Round-trip is byte-exact up to trailing newline normalization.
        re_preamble, re_entries = ov.parse_operator_verification(out)
        assert re_preamble == preamble
        assert len(re_entries) == 1
        assert re_entries[0].vrf_id == "VRF-001"
        assert "- thing 1" in "\n".join(re_entries[0].body_lines)
        assert "- thing 2" in "\n".join(re_entries[0].body_lines)


# =============================================================================
# Mutators (mark_verified / mark_accepted)
# =============================================================================


class TestMarkVerified:
    def _entry(self, status: str = "pending") -> ov.VerificationEntry:
        return ov.VerificationEntry(
            vrf_id="VRF-001",
            heading="## VRF-001 — sample",
            body_lines=[f"**Status:** {status}", "**Added:** 2026-05-19"],
        )

    def test_pending_to_verified(self):
        entry = self._entry("pending")
        ov.mark_verified(entry, today=date(2026, 5, 19))
        assert entry.status == "verified"
        joined = "\n".join(entry.body_lines)
        assert "**Verified:** 2026-05-19" in joined

    def test_already_verified_is_noop(self):
        entry = self._entry("verified")
        original_lines = list(entry.body_lines)
        ov.mark_verified(entry, today=date(2026, 5, 19))
        assert entry.body_lines == original_lines  # no Verified line appended

    def test_accepted_refuses_verify(self):
        entry = self._entry("accepted")
        with pytest.raises(ValueError, match="accepted"):
            ov.mark_verified(entry, today=date(2026, 5, 19))


class TestMarkAccepted:
    def _entry(self, status: str = "pending") -> ov.VerificationEntry:
        return ov.VerificationEntry(
            vrf_id="VRF-001",
            heading="## VRF-001 — sample",
            body_lines=[f"**Status:** {status}", "**Added:** 2026-05-19"],
        )

    def test_pending_to_accepted_with_rationale(self):
        entry = self._entry("pending")
        ov.mark_accepted(
            entry, rationale="shipping for demo", today=date(2026, 5, 19)
        )
        assert entry.status == "accepted"
        joined = "\n".join(entry.body_lines)
        assert "**Accepted:** 2026-05-19 — rationale: shipping for demo" in joined

    def test_empty_rationale_rejected(self):
        entry = self._entry("pending")
        with pytest.raises(ValueError, match="rationale"):
            ov.mark_accepted(entry, rationale="", today=date(2026, 5, 19))

    def test_whitespace_only_rationale_rejected(self):
        entry = self._entry("pending")
        with pytest.raises(ValueError, match="rationale"):
            ov.mark_accepted(entry, rationale="   ", today=date(2026, 5, 19))

    def test_already_accepted_is_noop(self):
        entry = self._entry("accepted")
        original_lines = list(entry.body_lines)
        ov.mark_accepted(
            entry, rationale="new reason", today=date(2026, 5, 19)
        )
        assert entry.body_lines == original_lines

    def test_already_verified_is_noop(self):
        # Verified is a drained state — no need to also accept.
        entry = self._entry("verified")
        original_lines = list(entry.body_lines)
        ov.mark_accepted(
            entry, rationale="overriding", today=date(2026, 5, 19)
        )
        assert entry.body_lines == original_lines


# =============================================================================
# Counting helpers
# =============================================================================


class TestPendingHelpers:
    def test_count_pending(self):
        entries = [
            ov.VerificationEntry("VRF-001", "## h", ["**Status:** pending"]),
            ov.VerificationEntry("VRF-002", "## h", ["**Status:** verified"]),
            ov.VerificationEntry("VRF-003", "## h", ["**Status:** pending"]),
            ov.VerificationEntry("VRF-004", "## h", ["**Status:** accepted"]),
        ]
        assert ov.count_pending(entries) == 2
        pending = ov.pending_entries(entries)
        assert [e.vrf_id for e in pending] == ["VRF-001", "VRF-003"]


# =============================================================================
# is_operator_verification_required (column-0 YAML scanner)
# =============================================================================


class TestIsOperatorVerificationRequired:
    def test_missing_file_is_false(self, tmp_path: Path):
        assert (
            ov.is_operator_verification_required(tmp_path / "nope.yaml")
            is False
        )

    def test_missing_key_is_false(self, tmp_path: Path):
        state = tmp_path / "state.yaml"
        state.write_text("other_key: true\n")
        assert ov.is_operator_verification_required(state) is False

    def test_true_value_recognized(self, tmp_path: Path):
        state = tmp_path / "state.yaml"
        state.write_text("operator_verification_required: true\n")
        assert ov.is_operator_verification_required(state) is True

    def test_false_value_recognized(self, tmp_path: Path):
        state = tmp_path / "state.yaml"
        state.write_text("operator_verification_required: false\n")
        assert ov.is_operator_verification_required(state) is False

    def test_indented_occurrence_ignored(self, tmp_path: Path):
        # Nested mention inside a YAML block must not count as the top-level
        # declaration.
        state = tmp_path / "state.yaml"
        state.write_text(
            "nested:\n  operator_verification_required: true\n"
        )
        assert ov.is_operator_verification_required(state) is False

    def test_inline_comment_tolerated(self, tmp_path: Path):
        # Mirrors the Chunk 10 detector/mutator inline-comment lesson.
        state = tmp_path / "state.yaml"
        state.write_text(
            "operator_verification_required: true  # F10 opt-in\n"
        )
        assert ov.is_operator_verification_required(state) is True


# =============================================================================
# run_check_operator_verification
# =============================================================================


def _make_product(tmp_path: Path, *, required: bool, queue_body: str = "") -> Path:
    product = tmp_path / "product"
    prawduct = product / ".prawduct"
    prawduct.mkdir(parents=True)
    state = (
        "operator_verification_required: "
        + ("true" if required else "false")
        + "\n"
    )
    (prawduct / "project-state.yaml").write_text(state)
    if queue_body:
        (prawduct / "operator-verification.md").write_text(queue_body)
    return product


class TestRunCheckOperatorVerification:
    def test_gate_off_returns_satisfied(self, tmp_path: Path):
        product = _make_product(tmp_path, required=False)
        result = ov.run_check_operator_verification(product)
        assert result["required"] is False
        assert result["pending"] == 0
        assert result["first_pending"] is None

    def test_gate_on_no_queue_file(self, tmp_path: Path):
        product = _make_product(tmp_path, required=True)
        result = ov.run_check_operator_verification(product)
        assert result["required"] is True
        assert result["pending"] == 0
        assert "no queue file" in result["message"]

    def test_gate_on_empty_queue(self, tmp_path: Path):
        product = _make_product(
            tmp_path, required=True, queue_body="# Empty queue\n"
        )
        result = ov.run_check_operator_verification(product)
        assert result["pending"] == 0

    def test_gate_on_pending_entry(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body=(
                "# Queue\n\n"
                "## VRF-001 — sample\n**Status:** pending\n"
            ),
        )
        result = ov.run_check_operator_verification(product)
        assert result["pending"] == 1
        assert result["first_pending"] == "VRF-001"
        assert "blocking" in result["message"]
        # Plural / singular phrasing — single pending uses singular.
        assert "entry" in result["message"]

    def test_gate_on_multiple_pending_pluralized(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body=(
                "## VRF-001 — a\n**Status:** pending\n\n"
                "## VRF-002 — b\n**Status:** pending\n"
            ),
        )
        result = ov.run_check_operator_verification(product)
        assert result["pending"] == 2
        assert "entries" in result["message"]

    def test_drained_entries_dont_block(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body=(
                "## VRF-001 — a\n**Status:** verified\n\n"
                "## VRF-002 — b\n**Status:** accepted\n"
            ),
        )
        result = ov.run_check_operator_verification(product)
        assert result["pending"] == 0


# =============================================================================
# run_verify_entry
# =============================================================================


class TestRunVerifyEntry:
    def test_no_prawduct_dir_errors(self, tmp_path: Path):
        result = ov.run_verify_entry(tmp_path / "nope", "VRF-001")
        assert "error" in result
        assert "Not a prawduct product" in result["error"]

    def test_no_queue_file_errors(self, tmp_path: Path):
        product = _make_product(tmp_path, required=True)
        result = ov.run_verify_entry(product, "VRF-001")
        assert "error" in result
        assert "No operator-verification queue" in result["error"]

    def test_unknown_id_errors(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** pending\n",
        )
        result = ov.run_verify_entry(product, "VRF-999")
        assert "error" in result
        assert "VRF-999" in result["error"]

    def test_pending_to_verified(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** pending\n",
        )
        result = ov.run_verify_entry(
            product, "VRF-001", today=date(2026, 5, 19)
        )
        assert "error" not in result
        assert result["previous_status"] == "pending"
        assert result["status"] == "verified"
        assert result["actions"]
        # File was written back.
        queue = (product / ".prawduct" / "operator-verification.md").read_text()
        assert "**Status:** verified" in queue
        assert "**Verified:** 2026-05-19" in queue

    def test_already_verified_is_noop(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** verified\n",
        )
        result = ov.run_verify_entry(product, "VRF-001")
        assert result["previous_status"] == "verified"
        assert result["status"] == "verified"
        assert not result["actions"]
        assert result["notes"]

    def test_accepted_entry_refuses_verify(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** accepted\n",
        )
        result = ov.run_verify_entry(product, "VRF-001")
        assert "error" in result
        assert "accepted" in result["error"]


# =============================================================================
# run_accept_pending
# =============================================================================


class TestRunAcceptPending:
    def test_empty_rationale_rejected(self, tmp_path: Path):
        product = _make_product(tmp_path, required=True)
        result = ov.run_accept_pending(product, "   ")
        assert "error" in result

    def test_no_pending_returns_clean(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** verified\n",
        )
        result = ov.run_accept_pending(product, "rationale")
        assert "error" not in result
        assert result["accepted_ids"] == []
        assert result["notes"]

    def test_pending_to_accepted_with_rationale(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body=(
                "## VRF-001 — a\n**Status:** pending\n\n"
                "## VRF-002 — b\n**Status:** verified\n\n"
                "## VRF-003 — c\n**Status:** pending\n"
            ),
        )
        result = ov.run_accept_pending(
            product, "shipping for demo", today=date(2026, 5, 19)
        )
        assert result["accepted_ids"] == ["VRF-001", "VRF-003"]
        queue = (product / ".prawduct" / "operator-verification.md").read_text()
        # VRF-002 (verified) untouched, others now accepted with rationale.
        assert queue.count("**Status:** accepted") == 2
        assert queue.count("**Status:** verified") == 1
        assert (
            "**Accepted:** 2026-05-19 — rationale: shipping for demo"
            in queue
        )


# =============================================================================
# prawduct-hook check-operator-verification / accept-operator-verification
# (subprocess so we exercise the plugin-runtime dispatch wiring)
# =============================================================================


def _run_hook(project_dir: Path, *args: str) -> subprocess.CompletedProcess:
    """Invoke the plugin runtime the way a governed repo does.

    Module-level rather than a method so a second dispatch class can reach it
    without subclassing the first — inheriting a pytest class re-collects its
    tests, so the tidy-looking reuse silently runs three subprocess tests twice.
    """
    cmd = [sys.executable, str(REPO_ROOT / "bin" / "prawduct-hook"), *args]
    return subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        env={
            "CLAUDE_PROJECT_DIR": str(project_dir),
            "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
            "PATH": "/usr/bin:/bin",
        },
    )


class TestPrawductHookOperatorVerification:
    """Subprocess-level coverage of the plugin runtime's dispatch wiring.

    Kept intentionally minimal — three subprocess tests verify the
    commands are reachable and exit-code semantics are correct. Branch
    coverage of the underlying logic lives in the in-process
    Test* classes above.
    """

    def _hook(self, project_dir: Path, *args: str) -> subprocess.CompletedProcess:
        return _run_hook(project_dir, *args)

    def test_check_dispatch_returns_0_when_gate_off(self, tmp_path: Path):
        product = _make_product(tmp_path, required=False)
        cp = self._hook(product, "check-operator-verification")
        assert cp.returncode == 0

    def test_check_dispatch_returns_1_with_pending(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** pending\n",
        )
        cp = self._hook(product, "check-operator-verification")
        assert cp.returncode == 1

    def test_accept_dispatch_requires_rationale_arg(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** pending\n",
        )
        cp = self._hook(product, "accept-operator-verification")
        assert cp.returncode == 1
        assert "rationale" in cp.stderr.lower()




# =============================================================================
# encoding round trip — the writer and the reader must agree
# =============================================================================


class TestQueueEncodingRoundTrip:
    """`_write_queue` and `_load_queue` must use the same encoding.

    They were self-inverse by accident: both used the locale encoding, so a
    mangled write was mangled back on read and nothing was observably wrong.
    When the shared writer's default became utf-8, a bare `read_text()` here
    would have made the pair asymmetric — and this queue is a **committed
    product file**, so the next status mutation would rewrite it transcoded.

    Runs under a forced non-UTF-8 locale in a subprocess: on a UTF-8 host both
    halves agree whatever they ask for, so an in-process assertion passes
    identically against the broken code. The reader guard is invisible without
    this, which is how it shipped untested in the first place.
    """

    _ENV_KEYS = {
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONUTF8": "0",
        "PYTHONCOERCECLOCALE": "0",
    }

    def test_non_ascii_survives_write_then_read_under_c_locale(self, tmp_path):
        import os

        queue = tmp_path / "operator-verification.md"
        # An em-dash and an accent: exactly what this queue's prose carries.
        preamble = "# Operator verification\n\nEntries below — verify each.\n\n"
        script = (
            "from pathlib import Path\n"
            "from lib import operator_verification as ov\n"
            f"q = Path({str(queue)!r})\n"
            f"ov._write_queue(q, {preamble!r}, [])\n"
            "pre, entries = ov._load_queue(q)\n"
            "assert '\\u2014' in pre, 'em-dash did not survive the round trip'\n"
            "print('ok')\n"
        )
        # The script goes to a FILE, not to `-c`. Under `LC_ALL=C` on Linux,
        # Python decodes argv with the C locale's ASCII codec, so the em-dash in
        # this source arrives as surrogates and the interpreter dies with
        # "Unable to decode the command from the command line" before reaching
        # the assertion — the test failing for its own delivery mechanism rather
        # than for the encoding behaviour it exists to check. macOS hides this
        # by always decoding argv as UTF-8, which is why it took a Linux CI
        # runner to surface. Source *files* are UTF-8 by language definition
        # (PEP 3120) regardless of locale, so the intent survives intact and
        # only ASCII crosses the command line.
        runner = tmp_path / "roundtrip.py"
        runner.write_text(script, encoding="utf-8")
        env = {**os.environ, **self._ENV_KEYS, "PYTHONPATH": str(REPO_ROOT)}
        result = subprocess.run(
            [sys.executable, str(runner)], capture_output=True, text=True, env=env
        )
        assert result.returncode == 0, (
            "the queue write/read pair disagrees about encoding under a "
            f"non-UTF-8 locale. stderr={result.stderr!r}"
        )
        assert queue.read_bytes().decode("utf-8").startswith("# Operator verification")

    def test_readers_ask_for_utf8_in_source(self):
        """Source pin, mirroring the writer's pin in test_atomic_state_writes.

        A behavioural test cannot see a reader that is never reached on this
        host; the source pin can, and it is what makes a reverted guard fail
        somewhere rather than nowhere.
        """
        src = (REPO_ROOT / "lib" / "operator_verification.py").read_text(encoding="utf-8")
        assert 'queue_path.read_text(encoding="utf-8")' in src, (
            "_load_queue must decode utf-8 — it reads back what _write_queue "
            "wrote through the shared utf-8 writer"
        )
        assert 'state_path.read_text(encoding="utf-8")' in src, (
            "the operator_verification_required read must decode utf-8"
        )
        # Receiver-qualified so the assertion cannot be satisfied or broken by
        # prose: the docstring above the fix names ``read_text()`` on purpose.
        assert "queue_path.read_text()" not in src, (
            "a bare read_text() reintroduces the locale-encoding asymmetry"
        )
        assert "state_path.read_text()" not in src


# ---------------------------------------------------------------------------
# A queue that could not be READ is not a queue that is EMPTY.
#
# The reported failure was a repo holding 32 entries as bullets under one
# `## Pending` heading: `parse_operator_verification` recognised none of them,
# `run_check_operator_verification` reported `pending: 0`, and the gate blocked
# on nothing while every entry sat unseen. The parser's leniency is deliberate
# and unchanged — it is what lets a trailing `## Notes` section coexist with
# real entries — so the fix is downstream, at the frame that discards the
# preamble those unrecognised lines land in.
#
# The two silence tests are the load-bearing ones. A gate that fires on a
# healthy repo is worse than the bug, and this one BLOCKS `/pr create`, so both
# real corpora prawduct ships or maintains are asserted quiet.
# ---------------------------------------------------------------------------

import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

_PLUGIN = str(_Path(__file__).resolve().parent.parent / "plugin")
if _PLUGIN not in _sys.path:
    _sys.path.insert(0, _PLUGIN)

from lib import core as _core  # noqa: E402
from lib import operator_verification as _ov  # noqa: E402


def _repo(tmp_path, queue_text, *, required=True):
    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    (prawduct / "project-state.yaml").write_text(
        f"operator_verification_required: {'true' if required else 'false'}\n",
        encoding="utf-8",
    )
    if queue_text is not None:
        (prawduct / "operator-verification.md").write_text(queue_text, encoding="utf-8")
    return tmp_path


_FIELD_SHAPE = """# Operator Verification Queue

## Pending

- VRF-001 check the dashboard renders
- VRF-002 confirm the webhook fires
- VRF-003 verify the export
"""


import subprocess as _subprocess  # noqa: E402

_HOOK_PATH = _Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"


def _run_check(repo):
    """Invoke the gate against `repo` with a PINNED environment.

    Inheriting `os.environ` does not work here even with `cwd` set:
    `gitstate.resolve_project_dir` returns the `CLAUDE_PROJECT_DIR` pin whenever
    cwd is not a git work tree, and a pytest `tmp_path` never is — so the hook
    would grade the real repo instead of the fixture. These two calls are
    read-only, so the failure is a spurious result rather than a mutation; the
    destructive form of the same mistake is documented at
    `tests/test_learnings_pairing.py::_run_hook` and at
    `tests/test_audit_learnings.py::TestAuditLearningsCLI`.
    """
    return _subprocess.run(
        [_sys.executable, str(_HOOK_PATH), "check-operator-verification"],
        capture_output=True, text=True,
        env={"CLAUDE_PROJECT_DIR": str(repo), "PATH": "/usr/bin:/bin"},
    )


def test_unparsed_queue_blocks_instead_of_reporting_empty(tmp_path):
    """The field case: entries in a shape the parser does not recognise."""
    result = _ov.run_check_operator_verification(_repo(tmp_path, _FIELD_SHAPE))

    assert result["queue_status"] == _ov.QUEUE_UNREADABLE
    assert result["unparsed_lines"] == 4
    assert "NOT a clear queue" in result["message"]


def test_unparsed_queue_refusal_forbids_rewriting_the_queue(tmp_path):
    """An agent meeting this refusal will reach for the file.

    Reformatting an operator-authored record to satisfy a gate is a silent
    edit nobody reviewed — a worse outcome than the silent no-op being fixed,
    so the refusal has to say so in the imperative.
    """
    result = _ov.run_check_operator_verification(_repo(tmp_path, _FIELD_SHAPE))

    assert "DO NOT rewrite the queue" in result["message"]


def test_the_shipped_template_is_not_flagged(tmp_path):
    """Pinned against the real artifact, not a fixture copy.

    `init_product` copies this file verbatim, so a discriminator that fires on
    it fires on every freshly onboarded repo.
    """
    template = (_Path(_core.TEMPLATES_DIR) / "operator-verification.md").read_text(
        encoding="utf-8"
    )

    result = _ov.run_check_operator_verification(_repo(tmp_path, template))

    assert result["queue_status"] == _ov.QUEUE_OK


def test_this_repos_own_live_queue_is_not_flagged():
    """The other real corpus. A false positive here blocks this repo's own PRs."""
    live = _Path(__file__).resolve().parent.parent / ".prawduct" / "operator-verification.md"
    if not live.is_file():
        import pytest as _pytest
        _pytest.skip("no live queue in this checkout")

    preamble, entries = _ov.parse_operator_verification(live.read_text(encoding="utf-8"))

    assert entries, "the live queue should parse"
    assert _ov.unparsed_content_lines(preamble) == []


def test_a_genuinely_empty_queue_still_reports_empty(tmp_path):
    result = _ov.run_check_operator_verification(
        _repo(tmp_path, "# Operator Verification Queue\n\n<!-- notes -->\n")
    )

    assert result["queue_status"] == _ov.QUEUE_OK
    assert result["pending"] == 0
    assert "empty" in result["message"]


def test_a_missing_queue_file_still_reports_empty(tmp_path):
    result = _ov.run_check_operator_verification(_repo(tmp_path, None))

    assert result["queue_status"] == _ov.QUEUE_OK
    assert result["pending"] == 0


def test_a_notes_section_beside_real_entries_is_not_flagged(tmp_path):
    """The leniency this fix deliberately preserves."""
    text = (
        "# Operator Verification Queue\n\n"
        "## VRF-001 — Chunk 01 — a thing\n\n**Status:** pending\n\n"
        "## Notes\n\nsome free prose the parser ignores\n"
    )
    result = _ov.run_check_operator_verification(_repo(tmp_path, text))

    assert result["queue_status"] == _ov.QUEUE_OK
    assert result["pending"] == 1


def test_not_required_short_circuits_before_the_new_check(tmp_path):
    """Only a repo that opted into this gate can be blocked by it."""
    result = _ov.run_check_operator_verification(
        _repo(tmp_path, _FIELD_SHAPE, required=False)
    )

    assert result["required"] is False
    assert result["queue_status"] == _ov.QUEUE_OK


def test_every_check_result_carries_the_same_keys(tmp_path):
    """A caller must not have to know which branch produced its result."""
    keys = None
    for text, required in [
        (_FIELD_SHAPE, True),
        (None, True),
        ("# Operator Verification Queue\n", True),
        (_FIELD_SHAPE, False),
        ("## VRF-1 — c — t\n\n**Status:** pending\n", True),
    ]:
        result = _ov.run_check_operator_verification(_repo(tmp_path, text, required=required))
        if keys is None:
            keys = set(result)
        assert set(result) == keys
        for f in (tmp_path / ".prawduct").glob("operator-verification.md"):
            f.unlink()


def test_accept_pending_refuses_an_unparsed_queue(tmp_path):
    """The override reaches the same queue by a different door.

    Without this it reports "gate already satisfied" and records
    `accepted_ids: []` — a recorded bypass covering entries nobody read, which
    is worse than the check's version of the same bug because the operator has
    deliberately chosen to override and is entitled to know what they overrode.
    """
    result = _ov.run_accept_pending(_repo(tmp_path, _FIELD_SHAPE), "shipping anyway")

    assert "error" in result
    assert "parsed 0 entries" in result["error"]
    assert "accepted_ids" not in result


def test_accept_pending_still_reports_satisfied_on_a_genuinely_empty_queue(tmp_path):
    """The negative: refusing here would break every clean override."""
    result = _ov.run_accept_pending(
        _repo(tmp_path, "# Operator Verification Queue\n"), "shipping anyway"
    )

    assert "error" not in result
    assert result["accepted_ids"] == []


def test_accept_pending_does_not_rewrite_the_unparsed_queue(tmp_path):
    """It must refuse WITHOUT touching the file it refused over."""
    repo = _repo(tmp_path, _FIELD_SHAPE)
    queue = repo / ".prawduct" / "operator-verification.md"
    before = queue.read_text(encoding="utf-8")

    _ov.run_accept_pending(repo, "shipping anyway")

    assert queue.read_text(encoding="utf-8") == before


def test_cli_exits_3_on_an_unparsed_queue_not_1(tmp_path):
    """Exit 1 already means "pending entries, drain or override the first".

    Both of those remedies are inapplicable to a queue that yielded no entries,
    so reusing 1 would send the caller to a fix that cannot work — ending at the
    queue file, which is the move the refusal exists to prevent. 3 still blocks.
    """
    proc = _run_check(_repo(tmp_path, _FIELD_SHAPE))

    assert proc.returncode == 3, (proc.returncode, proc.stderr)
    assert proc.returncode != 1
    assert "NOT a clear queue" in proc.stderr


def test_cli_still_exits_1_on_genuinely_pending_entries(tmp_path):
    """The neighbour that must keep its meaning."""
    proc = _run_check(
        _repo(tmp_path, "## VRF-001 — Chunk 01 — a thing\n\n**Status:** pending\n")
    )

    assert proc.returncode == 1
    assert "VRF-001" in proc.stderr


# =============================================================================
# The write-only failure (#183)
# =============================================================================

TEMPLATE = REPO_ROOT / "templates" / "operator-verification.md"
LIVE_QUEUE = Path(__file__).resolve().parents[1] / ".prawduct" / "operator-verification.md"


def test_the_template_teaches_splitting_the_deferral():
    """The rule belongs where deferrals are MADE, not where they are drained.

    One entry in this repo's own queue deferred three integration facts together
    because "matcher semantics vary by Claude Code version". True of two of them.
    False of the third, which was a pure static question, was decidable that day,
    was broken, and sat unexamined for seventeen days while the entry that named
    it waited on a live session it never got. Deferring a statically-decidable
    claim alongside a genuinely-live one launders an untested assertion into a
    queue nobody reads.
    """
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "SPLIT THE DEFERRAL" in text, (
        f"{TEMPLATE} must teach the split — 'can this be true in principle' "
        f"(static, testable now) vs 'does the harness actually do it' (live) — "
        f"at the moment of deferral, which is the only moment it can help"
    )
    assert "ONLY THE SECOND HALF BELONGS IN THIS QUEUE" in text, (
        "the split is useless without the consequence: the static half is a test "
        "you write now, not a queue entry"
    )
    assert "Drain before you flip" in text, (
        f"{TEMPLATE} must warn that turning the flag on makes the queue a "
        f"blocking gate — a queue full of un-dispositioned entries stops work "
        f"rather than starting it"
    )


def test_the_status_line_grammar_is_documented_where_it_bites():
    """Six live entries read as drained and parsed as pending (#183).

    `_STATUS_LINE_RE` takes one token and fails closed on anything else, so
    `**Status:** verified (2026-07-17, throwaway repo foo)` counts as PENDING.
    The parser is right to fail closed; what was missing was anyone saying so
    where an author writes the line.
    """
    for path in (TEMPLATE, LIVE_QUEUE):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        assert "bare token and nothing else" in text, (
            f"{path} must state that `**Status:**` takes the bare token and "
            f"nothing else — trailing prose parses as malformed and fails "
            f"closed to `pending`, so the gate blocks on finished work"
        )


def test_every_pending_entry_in_the_live_queue_carries_a_disposition():
    """The acceptance criterion of #183, kept rather than done once.

    A queue is write-only when entries go in and nothing ever says what would
    take them out. Each pending entry must name what it turns on and whose
    harness can answer it — the four in this repo that genuinely need a live
    harness say so, which is a different and honest state from silence.
    """
    if not LIVE_QUEUE.is_file():
        pytest.skip("no live queue in this checkout")
    _preamble, entries = ov.parse_operator_verification(
        LIVE_QUEUE.read_text(encoding="utf-8")
    )
    undispositioned = [
        e.vrf_id
        for e in ov.pending_entries(entries)
        if "DRAIN DISPOSITION" not in "\n".join(e.body_lines)
    ]
    assert not undispositioned, (
        f"pending entries with no disposition: {undispositioned}. Every deferral "
        f"needs a dated `> === <date> — DRAIN DISPOSITION ===` block saying what "
        f"it turns on and whose harness answers it — written when you defer, not "
        f"when someone finally asks. Splitting it first (see the template) often "
        f"turns half of it into a test you can write today."
    )


# =============================================================================
# Unreadable status lines — refuse, never half-write
#
# The defect these pin: `_set_status_line` correctly reported "no status line
# to rewrite" and both mutators discarded that answer, appending a drain footer
# anyway. The status never moved, the footer said it had, the command exited 0
# saying so, and every re-run appended one more footer. Reported twice from two
# products a day apart (one root-caused by direct call, one inferred from the
# artifact), which is what identified the malformed shape as convergent rather
# than a typo: it is what an agent writes composing a compact entry header.
# =============================================================================


_COMBINED_METADATA_LINE = (
    "**Chunk:** a chunk · **Raised:** 2026-01-01 · **Status:** pending"
)


class TestStatusDefectClassification:
    """`status` is unchanged on every input; the defect is purely additive."""

    def test_well_formed_entry_has_no_defect(self):
        _, entries = ov.parse_operator_verification(
            "## VRF-001 — a\n**Status:** pending\n"
        )
        assert entries[0].status == "pending"
        assert entries[0].status_defect is None

    def test_status_inside_a_combined_metadata_line(self):
        _, entries = ov.parse_operator_verification(
            f"## VRF-001 — a\n{_COMBINED_METADATA_LINE}\n"
        )
        entry = entries[0]
        assert entry.status == "pending"  # strictness preserved: fails closed
        assert entry.status_defect.kind == ov.STATUS_DEFECT_UNPARSED_LINE
        assert entry.status_defect.line == _COMBINED_METADATA_LINE

    def test_first_body_line_is_prose_rather_than_a_status_line(self):
        _, entries = ov.parse_operator_verification(
            "## VRF-001 — a\nBody without a Status line at all.\n"
        )
        assert entries[0].status == "pending"
        assert entries[0].status_defect.kind == ov.STATUS_DEFECT_UNPARSED_LINE

    def test_entry_with_empty_body(self):
        _, entries = ov.parse_operator_verification("## VRF-001 — a\n\n")
        assert entries[0].status == "pending"
        assert entries[0].status_defect.kind == ov.STATUS_DEFECT_NO_STATUS_LINE
        assert entries[0].status_defect.line is None

    def test_unknown_status_token(self):
        _, entries = ov.parse_operator_verification(
            "## VRF-001 — a\n**Status:** wibble\n"
        )
        assert entries[0].status == "pending"
        assert entries[0].status_defect.kind == ov.STATUS_DEFECT_UNKNOWN_TOKEN

    def test_reader_and_writer_agree_on_which_line_is_the_status_line(self):
        """A later bare status line does not rescue a malformed first line.

        The two used to disagree: the reader required the status on the first
        non-blank body line, while the writer rewrote the first line matching
        the pattern *anywhere* in the body. On this entry that gap let the
        writer silently edit a line the reader never consults — changing the
        file while the entry went on reading `pending` forever.
        """
        _, entries = ov.parse_operator_verification(
            f"## VRF-001 — a\n{_COMBINED_METADATA_LINE}\n"
            "\n"
            "**Status:** pending\n"
        )
        entry = entries[0]
        assert entry.status_defect is not None
        before = list(entry.body_lines)
        assert ov.mark_verified(entry, today=date(2026, 5, 19)) is False
        assert entry.body_lines == before


class TestMutatorsRefuseRatherThanHalfWrite:
    def _malformed(self) -> ov.VerificationEntry:
        _, entries = ov.parse_operator_verification(
            f"## VRF-001 — a\n{_COMBINED_METADATA_LINE}\n"
        )
        return entries[0]

    def test_mark_verified_refuses_and_touches_nothing(self):
        entry = self._malformed()
        before = list(entry.body_lines)
        assert ov.mark_verified(entry, today=date(2026, 5, 19)) is False
        assert entry.body_lines == before
        assert not any("Verified" in line for line in entry.body_lines)

    def test_mark_accepted_refuses_and_touches_nothing(self):
        entry = self._malformed()
        before = list(entry.body_lines)
        assert (
            ov.mark_accepted(entry, rationale="r", today=date(2026, 5, 19))
            is False
        )
        assert entry.body_lines == before
        assert not any("Accepted" in line for line in entry.body_lines)

    def test_well_formed_entries_still_report_success(self):
        _, entries = ov.parse_operator_verification(
            "## VRF-001 — a\n**Status:** pending\n"
        )
        assert ov.mark_verified(entries[0], today=date(2026, 5, 19)) is True

    def test_already_verified_reports_no_work_outstanding(self):
        _, entries = ov.parse_operator_verification(
            "## VRF-001 — a\n**Status:** verified\n"
        )
        assert ov.mark_verified(entries[0], today=date(2026, 5, 19)) is True


class TestDescribeStatusDefect:
    """The refusal has to name the edit that WORKS, not merely say 'malformed'.

    Correcting the status word inside the combined line changes nothing — the
    reader never looks at that line's interior — so a message that stops at
    "malformed" sends an operator to make an edit that cannot help, twice.
    """

    def _describe(self, content: str) -> str:
        _, entries = ov.parse_operator_verification(content)
        return ov.describe_status_defect(
            entries[0].vrf_id, entries[0].status_defect
        )

    def test_quotes_the_offending_line_back(self):
        msg = self._describe(f"## VRF-001 — a\n{_COMBINED_METADATA_LINE}\n")
        assert _COMBINED_METADATA_LINE in msg

    def test_says_editing_in_place_will_not_help(self):
        msg = self._describe(f"## VRF-001 — a\n{_COMBINED_METADATA_LINE}\n")
        assert "NOT help" in msg
        assert "own line" in msg

    def test_unknown_token_lists_the_valid_ones(self):
        msg = self._describe("## VRF-001 — a\n**Status:** wibble\n")
        for token in ("pending", "verified", "accepted"):
            assert token in msg

    def test_claims_nothing_about_mutation(self):
        """The gate check shares this string and mutates nothing."""
        msg = self._describe(f"## VRF-001 — a\n{_COMBINED_METADATA_LINE}\n")
        assert "nothing was changed" not in msg.lower()


class TestRunnersRefuseAndWriteNothing:
    QUEUE = (
        "# Operator Verification Queue\n"
        "\n"
        "## VRF-101 — well formed\n"
        "\n"
        "**Status:** pending\n"
        "\n"
        "## VRF-102 — status inside a metadata line\n"
        "\n"
        f"{_COMBINED_METADATA_LINE}\n"
    )

    def test_verify_leaves_the_file_byte_identical(self, tmp_path: Path):
        product = _make_product(tmp_path, required=True, queue_body=self.QUEUE)
        queue = product / ".prawduct" / "operator-verification.md"
        before = queue.read_bytes()
        result = ov.run_verify_entry(product, "VRF-102", today=date(2026, 5, 19))
        assert "error" in result
        assert "Nothing was changed" in result["error"]
        assert queue.read_bytes() == before

    def test_verify_is_idempotent_when_refusing(self, tmp_path: Path):
        """Each re-run used to append one more `**Verified:**` footer."""
        product = _make_product(tmp_path, required=True, queue_body=self.QUEUE)
        queue = product / ".prawduct" / "operator-verification.md"
        before = queue.read_bytes()
        for _ in range(3):
            assert "error" in ov.run_verify_entry(
                product, "VRF-102", today=date(2026, 5, 19)
            )
        assert queue.read_bytes() == before

    def test_verify_still_drains_the_well_formed_sibling(self, tmp_path: Path):
        product = _make_product(tmp_path, required=True, queue_body=self.QUEUE)
        result = ov.run_verify_entry(product, "VRF-101", today=date(2026, 5, 19))
        assert "error" not in result
        assert result["status"] == "verified"

    def test_accept_is_all_or_nothing(self, tmp_path: Path):
        """One unreadable entry aborts the whole override, writing nothing.

        A bypass that covered every pending entry but one, silently, would
        record a decision about work nobody read — and the gate would go on
        blocking on the entry it skipped.
        """
        product = _make_product(tmp_path, required=True, queue_body=self.QUEUE)
        queue = product / ".prawduct" / "operator-verification.md"
        before = queue.read_bytes()
        result = ov.run_accept_pending(product, "shipping anyway", today=date(2026, 5, 19))
        assert "error" in result
        assert "no entries were accepted" in result["error"].lower()
        assert queue.read_bytes() == before

    def test_check_names_the_unreadable_entries_separately(self, tmp_path: Path):
        product = _make_product(tmp_path, required=True, queue_body=self.QUEUE)
        result = ov.run_check_operator_verification(product)
        assert result["pending"] == 2
        assert result["unparsed_status_entries"] == ["VRF-102"]
        assert "VRF-102" in result["message"]
        assert "cannot be drained or overridden" in result["message"]

    def test_check_does_not_offer_the_override_it_would_refuse(self, tmp_path: Path):
        """The override is all-or-nothing, so one unreadable entry stops it.

        Naming it as an available remedy here would repeat, one level up, the
        defect this whole change closes: advice that provably cannot work on
        the entry it is given about.
        """
        product = _make_product(tmp_path, required=True, queue_body=self.QUEUE)
        result = ov.run_check_operator_verification(product)
        assert "--accept-pending-verification \"rationale\"" not in result["message"]
        assert "override is unavailable" in result["message"]
        # The readable sibling is still reported as drainable.
        assert "1 can be drained" in result["message"]

    def test_check_on_a_queue_whose_only_pending_entry_is_unreadable(
        self, tmp_path: Path
    ):
        """The shape both upstream reports actually filed.

        Every other check test here pairs a readable entry with an unreadable
        one, so the `drainable == []` branch — no remedy is offered at all —
        was never taken. A regression that re-offered the override, or leaked a
        "0 can be drained" sentence, would have shipped green.
        """
        product = _make_product(
            tmp_path,
            required=True,
            queue_body=f"## VRF-001 — a\n{_COMBINED_METADATA_LINE}\n",
        )
        result = ov.run_check_operator_verification(product)
        assert result["pending"] == 1
        assert result["unparsed_status_entries"] == ["VRF-001"]
        assert "can be drained" not in result["message"]
        assert "--accept-pending-verification" not in result["message"]
        assert "1 entry cannot be drained or overridden" in result["message"]

    def test_check_pluralises_when_several_entries_are_unreadable(
        self, tmp_path: Path
    ):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body=(
                f"## VRF-001 — a\n{_COMBINED_METADATA_LINE}\n\n"
                f"## VRF-002 — b\n{_COMBINED_METADATA_LINE}\n"
            ),
        )
        result = ov.run_check_operator_verification(product)
        assert result["unparsed_status_entries"] == ["VRF-001", "VRF-002"]
        assert "2 entries cannot be drained or overridden" in result["message"]
        assert "Their status counts as pending" in result["message"]

    def test_check_stays_silent_on_a_healthy_queue(self, tmp_path: Path):
        """The fix must add nothing to the output for a well-formed queue."""
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** pending\n",
        )
        result = ov.run_check_operator_verification(product)
        assert result["unparsed_status_entries"] == []
        assert "cannot be drained" not in result["message"]

    def test_every_check_branch_carries_the_same_keys(self, tmp_path: Path):
        """The runner's docstring promises identical keys on every branch."""
        cases = [
            _make_product(tmp_path / "off", required=False),
            _make_product(tmp_path / "empty", required=True),
            _make_product(
                tmp_path / "ok",
                required=True,
                queue_body="## VRF-001 — a\n**Status:** pending\n",
            ),
            _make_product(
                tmp_path / "unreadable",
                required=True,
                queue_body="## Pending\n- an item in some other format\n",
            ),
        ]
        shapes = {
            frozenset(ov.run_check_operator_verification(p)) for p in cases
        }
        assert len(shapes) == 1, shapes
        assert "unparsed_status_entries" in next(iter(shapes))


# =============================================================================
# The write path must not damage the file it was handed
#
# The queue is an operator-authored record. Every defect below hits WELL-FORMED
# entries — they are not consequences of the malformed shape above, and each
# one edited a part of the file nobody asked this command to touch.
# =============================================================================


class TestWritePathPreservesTheFile:
    def test_round_trip_is_identity_including_the_preamble_blank_line(self):
        """Parse → format with no mutation must return the input unchanged.

        The preamble was joined with separators and re-terminated with a single
        newline, which cannot tell "the last preamble line was blank" from "no
        trailing newline" — so each drain deleted the blank line between the
        file's header comment and its first entry.
        """
        content = (
            "# Operator Verification Queue\n"
            "\n"
            "<!-- a header comment -->\n"
            "\n"
            "## VRF-001 — a\n"
            "\n"
            "**Status:** pending\n"
        )
        preamble, entries = ov.parse_operator_verification(content)
        assert ov.format_operator_verification(preamble, entries) == content

    def test_drained_entry_does_not_weld_itself_to_the_next_heading(self):
        content = (
            "## VRF-001 — a\n"
            "\n"
            "**Status:** pending\n"
            "\n"
            "## VRF-002 — b\n"
            "\n"
            "**Status:** pending\n"
        )
        preamble, entries = ov.parse_operator_verification(content)
        assert ov.mark_verified(entries[0], today=date(2026, 5, 19)) is True
        out = ov.format_operator_verification(preamble, entries)
        assert "**Verified:** 2026-05-19\n\n## VRF-002" in out

    def test_drain_adds_exactly_one_blank_line_above_the_footer(self):
        content = "## VRF-001 — a\n\n**Status:** pending\n\n"
        preamble, entries = ov.parse_operator_verification(content)
        assert ov.mark_verified(entries[0], today=date(2026, 5, 19)) is True
        out = ov.format_operator_verification(preamble, entries)
        assert "**Status:** verified\n\n**Verified:**" in out

    def test_repeated_drains_do_not_accumulate_blank_lines(self):
        """Idempotence on the file, not just on the status token."""
        content = "## VRF-001 — a\n\n**Status:** pending\n"
        preamble, entries = ov.parse_operator_verification(content)
        ov.mark_verified(entries[0], today=date(2026, 5, 19))
        once = ov.format_operator_verification(preamble, entries)
        preamble2, entries2 = ov.parse_operator_verification(once)
        ov.mark_verified(entries2[0], today=date(2026, 5, 19))
        assert ov.format_operator_verification(preamble2, entries2) == once

    def test_draining_the_last_entry_invents_no_trailing_blank_line(self):
        """A drain must not author an end-of-file line nobody asked for.

        Asserted on the exact bytes: the substring checks above pass whether or
        not a trailing blank is appended, which is how this went unnoticed.
        """
        content = "## VRF-001 — a\n\n**Status:** pending\n"
        preamble, entries = ov.parse_operator_verification(content)
        assert ov.mark_verified(entries[0], today=date(2026, 5, 19)) is True
        out = ov.format_operator_verification(preamble, entries)
        assert out == (
            "## VRF-001 — a\n"
            "\n"
            "**Status:** verified\n"
            "\n"
            "**Verified:** 2026-05-19\n"
        )

    def test_draining_a_middle_entry_keeps_its_separator_exactly(self):
        content = (
            "## VRF-001 — a\n\n**Status:** pending\n\n"
            "## VRF-002 — b\n\n**Status:** pending\n"
        )
        preamble, entries = ov.parse_operator_verification(content)
        assert ov.mark_verified(entries[0], today=date(2026, 5, 19)) is True
        out = ov.format_operator_verification(preamble, entries)
        assert out == (
            "## VRF-001 — a\n"
            "\n"
            "**Status:** verified\n"
            "\n"
            "**Verified:** 2026-05-19\n"
            "\n"
            "## VRF-002 — b\n"
            "\n"
            "**Status:** pending\n"
        )

    def test_operator_double_spacing_survives_a_drain(self):
        """Spacing the operation did not name is not the drain's to normalize."""
        content = (
            "## VRF-001 — a\n\n**Status:** pending\n\n\n"
            "## VRF-002 — b\n\n**Status:** pending\n"
        )
        preamble, entries = ov.parse_operator_verification(content)
        ov.mark_verified(entries[0], today=date(2026, 5, 19))
        out = ov.format_operator_verification(preamble, entries)
        assert "**Verified:** 2026-05-19\n\n\n## VRF-002" in out

    def test_crlf_queue_keeps_crlf_across_a_drain(self, tmp_path: Path):
        """A two-word status edit must not hand back a whole-file reformat."""
        product = _make_product(tmp_path, required=True)
        queue = product / ".prawduct" / "operator-verification.md"
        queue.write_bytes(
            b"# Queue\r\n\r\n## VRF-001 - a\r\n\r\n**Status:** pending\r\n"
        )
        result = ov.run_verify_entry(product, "VRF-001", today=date(2026, 5, 19))
        assert "error" not in result
        raw = queue.read_bytes()
        assert b"\r\n" in raw
        assert b"\n" not in raw.replace(b"\r\n", b"")

    def test_line_ending_detection(self, tmp_path: Path):
        """The terminator is read from the bytes on disk, not guessed.

        Stated as its own contract because the two callers only ever exercise
        the two happy shapes: a queue is written back only when it already
        existed, so the missing-file and no-newline defaults are otherwise
        unreachable and would sit unexamined.
        """
        cases = {
            b"a\nb\n": "\n",
            b"a\r\nb\r\n": "\r\n",
            b"no newline at all": "\n",
            b"": "\n",
            b"\nleading blank": "\n",
        }
        for raw, expected in cases.items():
            target = tmp_path / "q.md"
            target.write_bytes(raw)
            assert ov._existing_line_ending(target) == expected, raw
        assert ov._existing_line_ending(tmp_path / "absent.md") == "\n"

    def test_lf_queue_stays_lf(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** pending\n",
        )
        queue = product / ".prawduct" / "operator-verification.md"
        ov.run_verify_entry(product, "VRF-001", today=date(2026, 5, 19))
        assert b"\r" not in queue.read_bytes()


class TestDispatchRefusesUnreadableStatus:
    """Exit-code semantics at the CLI boundary.

    Exit 1, not a new code: these are state-mutating writers, whose documented
    refusal value is 1 (validation failed, nothing written). The third-outcome
    rule that gives `check-operator-verification` its exit 3 is scoped to a GATE
    whose subject could not be read, where 1 already carries a remedy that
    cannot apply — a different channel with a different table row.
    """

    def test_verify_dispatch_refuses_unreadable_status(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body=f"## VRF-001 — a\n{_COMBINED_METADATA_LINE}\n",
        )
        queue = product / ".prawduct" / "operator-verification.md"
        before = queue.read_bytes()
        cp = _run_hook(product, "verify-operator-verification", "VRF-001")
        assert cp.returncode == 1
        assert "own line" in cp.stderr
        assert queue.read_bytes() == before

    def test_verify_dispatch_still_drains_a_well_formed_entry(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** pending\n",
        )
        cp = _run_hook(product, "verify-operator-verification", "VRF-001")
        assert cp.returncode == 0
        assert "pending → verified" in cp.stdout
