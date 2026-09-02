"""The descent-obligation detector and its offered repair (#351).

``/prawduct:learnings`` tells every product's reader to apply the obligation marked
``prawduct:descent-obligation`` in that product's own ``learnings.md``. Only
``init_product``'s starter corpus ever wrote that marker, and only when the file did
not already exist — so the whole already-onboarded fleet holds a pointer at nothing.

**Everything here runs against a fixture, never against this repo.** This repo has
the marker, correctly placed, which is exactly why the defect shipped: a check
exercised only here is green for the one repo that never needed it. The framework's
own state stands in for the propagated contract only if you never look at anything
else, and this file is the "anything else".
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from lib import learnings_obligation as lo

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

MARKER = lo.MARKER

_PREAMBLE = (
    "# Learnings\n\n"
    "Accumulated wisdom from building this product. Entries use "
    '"When X, do Y because Z" format.\n'
)
_RULES = (
    "\n## Always pin the timezone\n\n"
    "When storing a timestamp, store it in UTC because local time is ambiguous.\n\n"
    "## Never swallow an exception\n\n"
    "When catching, name the type because a bare catch hides the next bug.\n"
)


def _product_raw(tmp_path: Path, learnings: str) -> Path:
    """A product whose corpus is written VERBATIM — no newline translation.

    `_product` goes through `write_text`'s default `newline=None`, which maps
    every ``\\n`` to ``os.linesep`` on write. The byte-fidelity tests need the
    bytes they asked for, not the platform's opinion of them.
    """
    (tmp_path / ".prawduct").mkdir(parents=True, exist_ok=True)
    with (tmp_path / lo.LEARNINGS_REL).open("w", encoding="utf-8", newline="") as handle:
        handle.write(learnings)
    return tmp_path


def _read_raw(tmp_path: Path) -> str:
    """The corpus back, verbatim — translation off on the way in too."""
    with (tmp_path / lo.LEARNINGS_REL).open(encoding="utf-8", newline="") as handle:
        return handle.read()


def _product(tmp_path: Path, learnings: str | None) -> Path:
    """A product-shaped repo: `.prawduct/` with a learnings corpus (or none)."""
    (tmp_path / ".prawduct").mkdir(parents=True, exist_ok=True)
    if learnings is not None:
        (tmp_path / lo.LEARNINGS_REL).write_text(learnings, encoding="utf-8")
    return tmp_path


def _marker_line(text: str) -> int | None:
    return next((i for i, ln in enumerate(text.splitlines()) if MARKER in ln), None)


def _first_rule_line(text: str) -> int | None:
    return next((i for i, ln in enumerate(text.splitlines()) if ln.startswith("## ")), None)


# ---------------------------------------------------------------------------
# check — the four answers that are not "ok"
# ---------------------------------------------------------------------------


class TestCheck:
    def test_a_product_corpus_without_the_marker_is_missing(self, tmp_path):
        _product(tmp_path, _PREAMBLE + _RULES)
        result = lo.check(tmp_path)
        assert result["status"] == lo.STATUS_MISSING
        assert result["marker_lines"] == []
        assert MARKER in result["detail"]

    def test_the_marker_above_the_first_rule_is_ok(self, tmp_path):
        _product(tmp_path, _PREAMBLE + "\n" + lo.OBLIGATION_BLOCK + _RULES)
        result = lo.check(tmp_path)
        assert result["status"] == lo.STATUS_OK
        assert result["marker_lines"] and result["first_rule_line"]
        assert result["marker_lines"][0] < result["first_rule_line"]

    def test_an_append_to_end_insertion_fails_the_position_check(self, tmp_path):
        """Position is the other half of presence, not a refinement of it.

        A repair that appends the block to the end of the file satisfies every
        presence check and is still wrong: the reader meets the obligation after
        the rules it governs. This is the variant the criterion names, and without
        it the position assertion below could pass on a check that only looks for
        the string anywhere.
        """
        _product(tmp_path, _PREAMBLE + _RULES + "\n" + lo.OBLIGATION_BLOCK)
        result = lo.check(tmp_path)
        assert result["status"] == lo.STATUS_MISPLACED
        assert "below the first rule" in result["detail"]

    def test_a_prose_mention_below_the_rules_does_not_fake_a_misplacement(self, tmp_path):
        """The home is the FIRST occurrence, and this is why.

        An earlier cut graded on *every* occurrence, so that a second copy below the
        rules would be caught. But the marker is an ordinary string: a corpus with a
        rule *about* the obligation — which a prawduct-derived product will write —
        then grades `misplaced`, the one status the repair declines. Doctor would
        report degraded, tell the owner to move a block that is already correctly
        placed, and offer no repair. A dead-end verdict on a healthy corpus is how a
        check teaches its reader to skip it.
        """
        corpus = (
            _PREAMBLE + "\n" + lo.OBLIGATION_BLOCK + _RULES
            + "\n## Keep the obligation above the rules\n\n"
            "When editing learnings.md, keep the `prawduct:descent-obligation` "
            "marker above the first rule because a reader meets it in file order.\n"
        )
        _product(tmp_path, corpus)
        assert lo.check(tmp_path)["status"] == lo.STATUS_OK

    def test_a_marker_only_below_the_rules_is_still_misplaced(self, tmp_path):
        # The first-occurrence rule must not become "any occurrence anywhere is
        # fine": a corpus whose ONLY marker is below the rules is the real defect.
        _product(tmp_path, _PREAMBLE + _RULES + "\n" + lo.OBLIGATION_BLOCK)
        assert lo.check(tmp_path)["status"] == lo.STATUS_MISPLACED

    def test_no_learnings_file_is_absent_not_missing(self, tmp_path):
        _product(tmp_path, None)
        result = lo.check(tmp_path)
        assert result["status"] == lo.STATUS_ABSENT
        assert "Health Check #5" in result["detail"]

    def test_undecodable_bytes_report_rather_than_guess(self, tmp_path):
        _product(tmp_path, "")
        (tmp_path / lo.LEARNINGS_REL).write_bytes(b"# Learnings\n\xff\xfe not utf-8\n")
        assert lo.check(tmp_path)["status"] == lo.STATUS_UNREADABLE

    def test_a_corpus_with_no_rules_yet_still_grades(self, tmp_path):
        _product(tmp_path, _PREAMBLE)
        result = lo.check(tmp_path)
        assert result["status"] == lo.STATUS_MISSING
        assert result["first_rule_line"] is None


# ---------------------------------------------------------------------------
# repair — insert-only, above the first rule, dry by default
# ---------------------------------------------------------------------------


class TestRepair:
    def test_the_repair_inserts_above_the_first_rule(self, tmp_path):
        _product(tmp_path, _PREAMBLE + _RULES)
        result = lo.repair(tmp_path, apply=True)
        assert result["applied"] is True

        text = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8")
        marker_at, first_rule = _marker_line(text), _first_rule_line(text)
        assert marker_at is not None and first_rule is not None
        assert marker_at < first_rule
        assert lo.check(tmp_path)["status"] == lo.STATUS_OK

    def test_the_dry_run_writes_nothing_and_names_what_it_would_write(self, tmp_path):
        _product(tmp_path, _PREAMBLE + _RULES)
        before = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8")
        result = lo.repair(tmp_path)
        assert result["applied"] is False
        assert result["repairable"] is True
        assert (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8") == before
        # The confirmation seam: the exact text, at the exact line.
        assert MARKER in result["insert_text"]
        assert result["insert_before_line"] == (_first_rule_line(before) or 0) + 1

    def test_the_repair_never_loses_an_authored_line(self, tmp_path):
        # Insert-only is the constraint that makes editing a product-authored file
        # a bounded act. Every original line survives, in order.
        original = _PREAMBLE + _RULES
        _product(tmp_path, original)
        lo.repair(tmp_path, apply=True)
        after = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8").splitlines()

        cursor = iter(after)
        for line in original.splitlines():
            assert any(candidate == line for candidate in cursor), f"lost line: {line!r}"

    def test_the_repair_preserves_crlf_endings_on_lines_it_did_not_touch(self, tmp_path):
        # "Never rewrites an existing line" is a claim about BYTES, not about
        # content. Rebuilding the file from `splitlines()` re-emits every line
        # with a fresh ending, so a CRLF corpus comes back LF and the owner's
        # diff shows a whole-file rewrite instead of one insertion.
        original = (_PREAMBLE + _RULES).replace("\n", "\r\n")
        _product_raw(tmp_path, original)
        lo.repair(tmp_path, apply=True)
        after = _read_raw(tmp_path)

        assert "\n" not in after.replace("\r\n", ""), "an LF-only line ending appeared"
        for line in original.split("\r\n"):
            if line:
                assert f"{line}\r\n" in after, f"line lost its ending: {line!r}"

    def test_the_repair_preserves_separators_that_splitlines_would_eat(self, tmp_path):
        # `str.splitlines()` breaks on \v, \f, \x1c-\x1e, \x85, U+2028 and U+2029.
        # Rejoining on \n replaces each with a newline — a character the owner
        # wrote, silently substituted on a line the repair never meant to touch.
        exotic = "  \x0b\x0c\x1c\x1d\x1e\x85"
        original = _PREAMBLE + f"\nA line holding {exotic} separators.\n" + _RULES
        _product_raw(tmp_path, original)
        lo.repair(tmp_path, apply=True)
        after = _read_raw(tmp_path)

        assert f"A line holding {exotic} separators." in after
        assert after.count(" ") == 1 and after.count("\x85") == 1

    def test_the_repair_leaves_an_unterminated_corpus_byte_identical_around_it(self, tmp_path):
        # A corpus with no trailing newline still gets exactly one added — you
        # cannot append below an unterminated line — and nothing else moves.
        original = (_PREAMBLE + _RULES).rstrip("\n")
        _product_raw(tmp_path, original)
        lo.repair(tmp_path, apply=True)
        after = _read_raw(tmp_path)

        head, block, tail = after.partition(lo.OBLIGATION_BLOCK)
        assert block, "the block was not inserted"
        assert not after.endswith("\n"), "a trailing newline the owner did not write"
        assert original.startswith(head.rstrip("\n")), "bytes before the block changed"
        assert original.endswith(tail), "bytes after the block changed"

    def test_the_repair_encodes_the_owners_corpus_as_utf8_not_the_locale(self, tmp_path):
        # The shared writer defaults to the LOCALE encoding (`#562`). On cp1252 or
        # latin-1 this block's em dashes encode cleanly, so the write SUCCEEDS and
        # silently re-encodes every non-ASCII character the owner wrote — after
        # which check() reports `unreadable` against a corpus the repair broke.
        # Pinned at the call, because a passing round-trip on a UTF-8 host proves
        # nothing about the hosts where this fails.
        seen = {}
        real = lo.core.atomic_write_text

        def spy(path, text, **kwargs):
            seen.update(kwargs)
            return real(path, text, **kwargs)

        _product_raw(tmp_path, _PREAMBLE + "\nAn — em dash, a ü, a 漢.\n" + _RULES)
        with mock.patch.object(lo.core, "atomic_write_text", spy):
            lo.repair(tmp_path, apply=True)

        assert seen.get("encoding") == "utf-8"
        assert seen.get("newline") == ""
        assert "An — em dash, a ü, a 漢." in _read_raw(tmp_path)

    def test_repairing_twice_is_an_idempotent_no_op(self, tmp_path):
        _product(tmp_path, _PREAMBLE + _RULES)
        lo.repair(tmp_path, apply=True)
        once = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8")
        second = lo.repair(tmp_path, apply=True)
        assert second["applied"] is False
        assert second["status"] == lo.STATUS_OK
        assert (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8") == once

    def test_a_misplaced_marker_is_declined_not_moved_and_not_duplicated(self, tmp_path):
        before = _PREAMBLE + _RULES + "\n" + lo.OBLIGATION_BLOCK
        _product(tmp_path, before)
        result = lo.repair(tmp_path, apply=True)
        assert result["repairable"] is False
        assert result["applied"] is False
        assert result["status"] == lo.STATUS_MISPLACED
        assert (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8") == before

    @pytest.mark.parametrize("corpus", [None, "unreadable"])
    def test_absent_and_unreadable_are_declined(self, tmp_path, corpus):
        _product(tmp_path, None if corpus is None else "")
        if corpus == "unreadable":
            (tmp_path / lo.LEARNINGS_REL).write_bytes(b"\xff\xfe")
        result = lo.repair(tmp_path, apply=True)
        assert result["repairable"] is False and result["applied"] is False

    def test_a_ruleless_corpus_gets_the_block_at_the_end(self, tmp_path):
        _product(tmp_path, _PREAMBLE)
        lo.repair(tmp_path, apply=True)
        assert lo.check(tmp_path)["status"] == lo.STATUS_OK

    def test_a_failed_write_reports_and_claims_nothing(self, tmp_path, monkeypatch):
        # The one error path with no other coverage. A repair that cannot write must
        # not return applied=True — the whole value of the status is that an owner
        # can believe it.
        _product(tmp_path, _PREAMBLE + _RULES)

        def _boom(path, text, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(lo.core, "atomic_write_text", _boom)
        result = lo.repair(tmp_path, apply=True)
        assert result["applied"] is False
        assert "could not write" in result["detail"]
        assert lo.check(tmp_path)["status"] == lo.STATUS_MISSING  # untouched
        # ...and the RESULT says the repair failed, not that the marker is
        # missing (#571). The branch used to leave `status` at whatever check()
        # had set, so the one field doctor grades on relayed a failed write as
        # the finding it had been asked to fix — an owner told "missing" and
        # never told prawduct had already tried. `detail` carried the truth and
        # nothing reads `detail` for a grade.
        assert result["status"] == lo.STATUS_UNWRITABLE
        assert result["repairable"] is False

    def test_an_encoding_failure_refuses_rather_than_raising(self, tmp_path, monkeypatch):
        """A `UnicodeEncodeError` is not an `OSError`, so it needs naming.

        With the encode pinned to utf-8 this is no longer the locale gap (`#562`)
        it was filed as — it is a genuine "this text cannot be encoded", e.g. a
        lone surrogate carried in from elsewhere. Rare, but the module promises
        "reported, never half-applied", and a traceback is not a report.
        """
        _product(tmp_path, _PREAMBLE + _RULES)

        def _boom(path, text, **kwargs):
            raise UnicodeEncodeError("utf-8", "\ud800", 0, 1, "surrogates not allowed")

        monkeypatch.setattr(lo.core, "atomic_write_text", _boom)
        result = lo.repair(tmp_path, apply=True)
        assert result["applied"] is False
        assert "could not write" in result["detail"]
        assert result["status"] == lo.STATUS_UNWRITABLE

    def test_the_insertion_survives_the_round_trip_intact(self, tmp_path):
        # The block is non-ASCII (em-dashes). An encoding mismatch between the write
        # and the read would corrupt the owner's corpus, and the marker — pure
        # ASCII — would still be found, so the status alone cannot see it.
        _product(tmp_path, _PREAMBLE + _RULES)
        lo.repair(tmp_path, apply=True)
        text = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8")
        assert lo.OBLIGATION_BLOCK in text

    def test_the_block_is_not_welded_to_its_neighbours(self, tmp_path):
        # Markdown collapses adjacent lines into one paragraph; a block run into the
        # preceding sentence stops introducing anything.
        _product(tmp_path, _PREAMBLE + _RULES)
        lo.repair(tmp_path, apply=True)
        lines = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8").splitlines()
        marker_at = _marker_line("\n".join(lines))
        assert lines[marker_at - 1].strip() == ""
        assert lines[_first_rule_line("\n".join(lines)) - 1].strip() == ""


# ---------------------------------------------------------------------------
# The repair plants the block this module owns
# ---------------------------------------------------------------------------


def test_repair_writes_the_obligation_block(tmp_path):
    """The repair is the only writer of this block.

    It once had a twin: `init_product` planted the same block into a starter
    `.prawduct/learnings.md`, and this test pinned the two together so a reworded
    obligation could not reach newly-onboarded products while skipping repaired
    ones. Onboarding no longer scaffolds a `.prawduct/` corpus at all — a new
    product gets `.claude/rules/learnings/core.md` from
    `learnings_files.CORE_HEADER`, whose obligation is pinned by
    `tests/test_learnings_files.py`. So there is one writer here again, and the
    thing worth asserting is that it writes.
    """
    _product(tmp_path, _PREAMBLE + _RULES)
    lo.repair(tmp_path, apply=True)
    repaired = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8")
    assert lo.OBLIGATION_BLOCK in repaired


# ---------------------------------------------------------------------------
# The command surface the doctor skill actually calls
# ---------------------------------------------------------------------------


def _run(project_dir: Path, *args: str) -> subprocess.CompletedProcess:
    home = project_dir.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(HOOK), "learnings-obligation", *args],
        capture_output=True, text=True, env=env, timeout=30,
    )


class TestCommand:
    def test_dry_run_reports_the_finding_and_exits_zero(self, tmp_path):
        # An advisory report: a finding is not a failure state.
        _product(tmp_path, _PREAMBLE + _RULES)
        before = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8")
        result = _run(tmp_path, "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == lo.STATUS_MISSING
        assert data["applied"] is False
        assert (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8") == before

    def test_the_human_dry_run_shows_the_text_it_would_insert(self, tmp_path):
        # `--json`-only tests never exercise the formatter, and this formatter IS
        # the informed confirmation the security model requires before an edit to a
        # file the framework did not author.
        _product(tmp_path, _PREAMBLE + _RULES)
        result = _run(tmp_path)
        assert result.returncode == 0
        assert "dry-run" in result.stdout
        assert MARKER in result.stdout
        assert "Would insert into .prawduct/learnings.md above line" in result.stdout

    def test_apply_writes_and_exits_zero(self, tmp_path):
        _product(tmp_path, _PREAMBLE + _RULES)
        result = _run(tmp_path, "--apply", "--json")
        assert result.returncode == 0
        assert json.loads(result.stdout)["applied"] is True
        assert lo.check(tmp_path)["status"] == lo.STATUS_OK

    def test_apply_on_a_healthy_corpus_is_a_zero_exit_no_op(self, tmp_path):
        _product(tmp_path, _PREAMBLE + "\n" + lo.OBLIGATION_BLOCK + _RULES)
        result = _run(tmp_path, "--apply", "--json")
        assert result.returncode == 0
        assert json.loads(result.stdout)["applied"] is False

    @pytest.mark.parametrize("corpus", [None, _PREAMBLE + _RULES + "\n" + lo.OBLIGATION_BLOCK])
    def test_apply_refuses_with_exit_one_when_it_cannot_write(self, tmp_path, corpus):
        # State-mutating writer: refused → 1, never a false success.
        _product(tmp_path, corpus)
        assert _run(tmp_path, "--apply").returncode == 1

    def test_a_refused_apply_is_not_labelled_a_dry_run(self, tmp_path):
        # The label names the mode the operator asked for. Reading it off "did a
        # write happen" told someone who passed --apply and hit a refusal that they
        # had run a dry run — an invitation to re-run the flag they did pass.
        _product(tmp_path, _PREAMBLE + _RULES + "\n" + lo.OBLIGATION_BLOCK)
        result = _run(tmp_path, "--apply")
        assert result.returncode == 1
        assert "(apply)" in result.stdout
        assert "dry-run" not in result.stdout

    def test_an_unreadable_corpus_could_not_run(self, tmp_path):
        _product(tmp_path, "")
        (tmp_path / lo.LEARNINGS_REL).write_bytes(b"\xff\xfe")
        assert _run(tmp_path).returncode == 1

    def test_an_absent_corpus_is_a_finding_not_an_unrun_check(self, tmp_path):
        # Dry run distinguishes "graded, and the answer is bad" (0) from "could not
        # grade" (1). A missing learnings.md is the former — doctor #5's finding.
        _product(tmp_path, None)
        result = _run(tmp_path, "--json")
        assert result.returncode == 0
        assert json.loads(result.stdout)["status"] == lo.STATUS_ABSENT

    def test_an_unknown_argument_is_a_usage_error(self, tmp_path):
        _product(tmp_path, _PREAMBLE + _RULES)
        result = _run(tmp_path, str(tmp_path))
        assert result.returncode == 2
        assert "unknown argument" in result.stderr


DOCTOR_SKILL = ROOT / "skills" / "doctor" / "SKILL.md"


def _doctor_check_13() -> str:
    """The prose of doctor Health Check #13, and nothing either side of it."""
    text = DOCTOR_SKILL.read_text(encoding="utf-8")
    head = "13. **Descent obligation in `learnings.md`**"
    assert head in text, f"{DOCTOR_SKILL} no longer carries Health Check #13"
    return text.split(head, 1)[1].split("\n14. ", 1)[0]


def test_doctor_check_13_enumerates_every_status_this_module_can_report():
    """The health check's documented enumeration must match the command's (#571).

    A status the module can return and the check does not name is a state with
    no documented grade — the model relaying it either invents one or reports
    the nearest thing it recognises. That is exactly how a failed repair got
    relayed as `missing`: `unwritable` did not exist, so the write-failure
    branch left `status` alone and the check's five-member list still looked
    complete.

    Asserted in both directions on purpose. A member the check names and the
    module cannot produce is dead prose that reads as coverage, and it ages into
    a grade for a state that was renamed somewhere else.
    """
    prose = _doctor_check_13()
    statuses = {
        value
        for name, value in vars(lo).items()
        if name.startswith("STATUS_") and isinstance(value, str)
    }
    assert len(statuses) >= 5, "status set shrank; this test's premise is stale"

    undocumented = sorted(s for s in statuses if f"`{s}`" not in prose)
    assert not undocumented, (
        f"doctor Health Check #13 does not name {undocumented}, which "
        f"`learnings_obligation` can report. Every status needs a documented "
        f"grade — healthy, degraded, or degraded because ungraded — or the "
        f"relay is left to invent one."
    )

    # The converse: every backticked lowercase word in the grading sentence must
    # be a real status. Scoped to that sentence onward so ordinary prose earlier
    # in the check is not swept in.
    graded = prose.split("Report **degraded** on", 1)[1]
    named = set(re.findall(r"`([a-z]+)`", graded))
    invented = sorted(named - statuses - {"apply", "json"})
    assert not invented, (
        f"doctor Health Check #13 grades {invented}, which `learnings_obligation` "
        f"never returns — a grade for a state that cannot occur reads as coverage "
        f"and hides the one that can."
    )
