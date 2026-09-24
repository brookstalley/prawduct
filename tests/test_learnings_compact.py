"""`learnings-compact`: a corpus becomes one-line rules under its caps.

Two questions organise the suite, as for its precedent `learnings-migrate`:

**Can a rule be lost?** Only by an owner-approved drop. Every row needs a
decision, `moved-to` must find its text at the destination, an unapproved drop
is refused, and the written files must pass the Stop gate's own format check.
:class:`TestRefusals` covers each route to a loss.

**Does the history survive?** A rewritten rule gets a new unit hash, which
would orphan its citations and count it as newly written. `learning.compacted`
events carry the old hash to the new one. :class:`TestContinuity` pins both
readers: `review-stats` joins through them, and the Stop hook skips them.

Each test names the change that turns it red.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib import learnings_compact as lc  # noqa: E402
from lib import learnings_files as lf  # noqa: E402
from lib import ledger  # noqa: E402

HOOK = _PLUGIN_ROOT / "bin" / "prawduct-hook"
REPO = Path(__file__).resolve().parent.parent

CORE = f"{lf.RULES_DIR_REL}/core.md"
LONG = "a rule that grew a body and a paragraph-length heading " * 6


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=30,
    )


def _repo(tmp_path: Path, core: str, areas: "dict[str, str] | None" = None) -> Path:
    """A committed repo with a rules tree. Committed because the commit is the
    undo, and an uncommitted corpus is one of the refusals."""
    root = tmp_path / "repo"
    rules = root / lf.RULES_DIR_REL
    rules.mkdir(parents=True)
    (root / ".prawduct").mkdir()
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n")
    (rules / "core.md").write_text(core)
    for name, text in (areas or {}).items():
        (rules / name).write_text(text)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "corpus")
    return root


def _legacy_core() -> str:
    return (
        lf.CORE_HEADER + "\n"
        f"### {LONG}\n\nThe story of how it was learned.\n\n"
        "### A short rule\n\n"
        "- a bullet rule about `src/app.py`\n"
    )


def _decide(ws: dict, decisions: "dict[str, dict]") -> dict:
    for row in ws["rows"]:
        row["disposition"] = decisions.get(row["id"])
    return ws


def _all_rewritten(ws: dict) -> dict:
    return _decide(ws, {
        row["id"]: {"action": "rewrite", "text": f"- rule {row['id']}, one line", "file": "core.md"}
        for row in ws["rows"]
    })


def _hook(repo: Path, *argv: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        [sys.executable, str(HOOK), "learnings-compact", *argv],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=60,
    )


class TestPlan:
    def test_every_rule_unit_becomes_a_row(self, tmp_path):
        # Red if the worksheet parser and rule_units disagree about what a rule is.
        repo = _repo(tmp_path, _legacy_core())
        ws = lc.build_worksheet(repo)
        assert [r["text"] for r in ws["rows"]] == lf.rule_units(_legacy_core())
        assert ws["rows"][0]["body"] == "The story of how it was learned."

    def test_a_rule_naming_a_path_gets_the_matching_area_as_a_candidate(self, tmp_path):
        repo = _repo(tmp_path, _legacy_core(), {
            "app.md": '---\npaths:\n  - "src/**"\n---\n# app\n\n- an app rule\n',
        })
        ws = lc.build_worksheet(repo)
        bullet = next(r for r in ws["rows"] if "src/app.py" in r["text"])
        assert bullet["candidate_areas"] == ["app.md"]

    def test_the_real_corpus_is_walked_whole(self):
        """Read the real artifact, not only fixtures I wrote. Red if any rules
        file or unit is skipped (the count must equal rule_units over the tree)."""
        ws = lc.build_worksheet(REPO)
        layout = lf.resolve(REPO)
        expected = sum(len(lf.rule_units(p.read_text(encoding="utf-8"))) for p in layout.files)
        assert expected > 0
        assert len(ws["rows"]) == expected
        assert set(ws["files"]) == {p.relative_to(REPO).as_posix() for p in layout.files}

    def test_related_rows_are_found_where_rules_overlap(self, tmp_path):
        """A positive control for the hint: two paraphrases of one rule must be
        related, or the detector is measuring nothing."""
        repo = _repo(tmp_path, lf.CORE_HEADER + "\n"
            "- verify a review artifact's cited gaps against HEAD before acting on them\n"
            "- a review artifact's cited gaps must be verified against HEAD first\n"
            "- unrelated guidance about naming branches\n")
        rows = lc.build_worksheet(repo)["rows"]
        assert rows[1]["id"] in rows[0]["related"]
        assert rows[2]["id"] not in rows[0]["related"]


class TestRefusals:
    def _ws(self, tmp_path):
        repo = _repo(tmp_path, _legacy_core())
        return repo, lc.build_worksheet(repo)

    def test_a_row_without_a_decision_refuses(self, tmp_path):
        repo, ws = self._ws(tmp_path)
        res = lc.validate(repo, ws)
        assert res.undispositioned == [r["id"] for r in ws["rows"]]
        assert any("no disposition" in r for r in res.refusals)

    def test_a_rewrite_over_the_limit_refuses(self, tmp_path):
        repo, ws = self._ws(tmp_path)
        ws = _all_rewritten(ws)
        ws["rows"][0]["disposition"]["text"] = "- " + "x" * lf.RULE_LINE_MAX
        assert any("over the" in r for r in lc.validate(repo, ws).refusals)

    def test_a_rewrite_must_be_a_bullet_on_one_line(self, tmp_path):
        repo, ws = self._ws(tmp_path)
        ws = _all_rewritten(ws)
        ws["rows"][0]["disposition"]["text"] = "- two\nlines"
        ws["rows"][1]["disposition"]["text"] = "### a heading"
        refusals = lc.validate(repo, ws).refusals
        assert any("one non-empty line" in r for r in refusals)
        assert any("`- ` bullet" in r for r in refusals)

    def test_an_unknown_destination_refuses(self, tmp_path):
        repo, ws = self._ws(tmp_path)
        ws = _all_rewritten(ws)
        ws["rows"][0]["disposition"]["file"] = "nowhere.md"
        assert any("neither an existing rules file" in r for r in lc.validate(repo, ws).refusals)

    def test_an_unapproved_drop_refuses_and_names_the_rows(self, tmp_path):
        """Red if a drop can be applied without the owner's date."""
        repo, ws = self._ws(tmp_path)
        ws = _all_rewritten(ws)
        first = ws["rows"][0]["id"]
        ws["rows"][0]["disposition"] = {"action": "drop", "reason": "never cited"}
        refusals = lc.validate(repo, ws).refusals
        assert any("owner" in r and first in r for r in refusals)

    def test_an_approved_drop_is_accepted(self, tmp_path):
        repo, ws = self._ws(tmp_path)
        ws = _all_rewritten(ws)
        ws["rows"][0]["disposition"] = {"action": "drop", "reason": "never cited", "approved": "2026-09-24"}
        assert lc.validate(repo, ws).refusals == []

    def test_moved_to_needs_the_text_at_the_destination(self, tmp_path):
        repo, ws = self._ws(tmp_path)
        ws = _all_rewritten(ws)
        ws["rows"][0]["disposition"] = {
            "action": "moved-to", "path": "src/app.py", "anchor": "a ruling that was never moved there",
        }
        assert any("anchor text is not in" in r for r in lc.validate(repo, ws).refusals)
        (repo / "src" / "app.py").write_text("# a ruling that was never moved there, until now\n")
        # The move changed a non-rules file, so the corpus digest still matches.
        assert lc.validate(repo, ws).refusals == []

    def test_moved_to_may_not_point_back_into_the_rules_directory(self, tmp_path):
        repo, ws = self._ws(tmp_path)
        ws = _all_rewritten(ws)
        ws["rows"][0]["disposition"] = {"action": "moved-to", "path": CORE, "anchor": "x" * 30}
        assert any("outside the rules directory" in r for r in lc.validate(repo, ws).refusals)

    def test_merge_into_must_name_a_rewritten_row(self, tmp_path):
        repo, ws = self._ws(tmp_path)
        ws = _all_rewritten(ws)
        ws["rows"][0]["disposition"] = {"action": "merge-into", "row": "U999"}
        assert any("merge-into" in r for r in lc.validate(repo, ws).refusals)

    def test_a_corpus_edited_after_plan_refuses(self, tmp_path):
        # Red if the digest check is removed: the rows would describe other text.
        repo, ws = self._ws(tmp_path)
        ws = _all_rewritten(ws)
        (repo / CORE).write_text((repo / CORE).read_text() + "- a later rule\n")
        assert any("changed since --plan" in r for r in lc.validate(repo, ws).refusals)

    def test_an_area_file_over_its_budget_refuses(self, tmp_path):
        repo, ws = self._ws(tmp_path)
        ws["new_areas"] = {"big.md": ["src/**"]}
        ws = _decide(ws, {r["id"]: {"action": "rewrite", "text": "- " + "y" * 240, "file": "big.md"} for r in ws["rows"]})
        many = [dict(r, id=f"X{i:04d}") for i in range(80) for r in ws["rows"][:1]]
        ws["rows"].extend(many)
        assert any("big.md would be" in r for r in lc.validate(repo, ws).refusals)

    def test_uncommitted_rules_refuse_unless_local(self, tmp_path):
        """The commit is the undo. Red if an uncommitted corpus can be overwritten."""
        repo, ws = self._ws(tmp_path)
        (repo / lf.RULES_DIR_REL / "scratch.md").write_text("# scratch\n")
        assert lc.undo_refusals(repo, local=False)
        assert lc.undo_refusals(repo, local=True) == []


class TestApply:
    def test_it_writes_one_line_rules_that_pass_the_gate(self, tmp_path):
        """Red if the written files would fail the Stop gate's own check."""
        repo = _repo(tmp_path, _legacy_core())
        ws = _all_rewritten(lc.build_worksheet(repo))
        res = lc.apply(repo, ws)
        text = (repo / CORE).read_text()
        assert text.startswith(lf.CORE_HEADER.rstrip("\n"))
        assert lf.shape_violations(text) == []
        assert res.outputs and not res.refusals

    def test_new_area_files_carry_their_globs_and_resolve(self, tmp_path):
        repo = _repo(tmp_path, _legacy_core())
        ws = _all_rewritten(lc.build_worksheet(repo))
        ws["new_areas"] = {"app.md": ["src/**"]}
        ws["rows"][2]["disposition"]["file"] = "app.md"
        lc.apply(repo, ws)
        layout = lf.resolve(repo)
        app = next(a for a in layout.areas if a.path.name == "app.md")
        assert app.globs == ["src/**"]
        assert lf.files_for_paths(layout, ["src/app.py"])[-1].name == "app.md"

    def test_an_area_left_with_no_rules_is_deleted(self, tmp_path):
        repo = _repo(tmp_path, _legacy_core(), {
            "old.md": '---\npaths:\n  - "src/**"\n---\n# old\n\n- an old rule\n',
        })
        ws = _all_rewritten(lc.build_worksheet(repo))  # every row lands in core.md
        res = lc.apply(repo, ws)
        assert f"{lf.RULES_DIR_REL}/old.md" in res.deletions
        assert not (repo / lf.RULES_DIR_REL / "old.md").exists()

    def test_banners_keep_a_section_heading(self, tmp_path):
        repo = _repo(tmp_path, lf.CORE_HEADER + "\n## Unsorted\n\n- a rule\n")
        ws = lc.build_worksheet(repo)
        ws = _decide(ws, {
            "U001": {"action": "banner", "text": "Unsorted", "file": "core.md"},
            "U002": {"action": "rewrite", "text": "- a rule", "file": "core.md"},
        })
        lc.apply(repo, ws)
        assert "\n## Unsorted\n- a rule\n" in (repo / CORE).read_text()

    def test_an_over_cap_core_is_applied_and_reported(self, tmp_path):
        """Unattended: everything but drops lands, and core.md stays over its cap
        (frozen). Red if an over-cap core refuses the whole compaction."""
        big = lf.CORE_HEADER + "\n" + "".join(f"- rule number {i} " + "z" * 200 + "\n" for i in range(80))
        repo = _repo(tmp_path, big)
        ws = lc.build_worksheet(repo)
        ws = _decide(ws, {r["id"]: {"action": "rewrite", "text": "- " + r["text"], "file": "core.md"} for r in ws["rows"]})
        res = lc.apply(repo, ws)
        assert res.over_cap and not res.refusals

    def test_apply_refuses_when_validation_does(self, tmp_path):
        # The guard lives in apply, not only in the command, so a caller that
        # skipped the dry run cannot skip the refusal with it.
        repo = _repo(tmp_path, _legacy_core())
        before = (repo / CORE).read_text()
        with pytest.raises(lc.CompactRefused):
            lc.apply(repo, lc.build_worksheet(repo))
        assert (repo / CORE).read_text() == before

    def test_local_backs_up_before_writing(self, tmp_path):
        repo = _repo(tmp_path, _legacy_core())
        before = (repo / CORE).read_text()
        ws = _all_rewritten(lc.build_worksheet(repo))
        lc.apply(repo, ws, local=True)
        from lib import learnings_migrate
        backups = list(learnings_migrate.backup_root(repo).glob(f"compact-*/{CORE}"))
        assert len(backups) == 1 and backups[0].read_text() == before


class TestContinuity:
    def _fired(self, repo: Path, text: str) -> None:
        ledger.append_learning_event(
            repo, "learning.fired", file=CORE, unit_hash=lf.unit_hash(text), review_id="rev-1",
        )

    def test_citations_follow_a_rewritten_rule(self, tmp_path):
        """Red if review-stats stops reading through learning.compacted: the
        rewritten rule would read as never cited."""
        from lib import telemetry
        repo = _repo(tmp_path, lf.CORE_HEADER + "\n- the old wording of a rule that was cited\n")
        self._fired(repo, "the old wording of a rule that was cited")
        ws = lc.build_worksheet(repo)
        assert ws["rows"][0]["cited"] == 1
        ws = _decide(ws, {"U001": {"action": "rewrite", "text": "- the new wording", "file": "core.md"}})
        lc.apply(repo, ws)
        ledger.append_learning_event(repo, "learning.written", file=CORE, unit_hash=lf.unit_hash("the new wording"))
        _events, _skipped, learning, _err = telemetry._read_events(
            repo / ".prawduct" / ".governance-ledger.jsonl"
        )
        assert learning["units_fired"] == 1
        assert learning["units_uncited"] == 0

    def test_a_merge_records_one_event_per_source_rule(self, tmp_path):
        repo = _repo(tmp_path, lf.CORE_HEADER + "\n- first phrasing\n- second phrasing\n")
        ws = lc.build_worksheet(repo)
        ws = _decide(ws, {
            "U001": {"action": "rewrite", "text": "- the merged rule", "file": "core.md"},
            "U002": {"action": "merge-into", "row": "U001"},
        })
        lc.apply(repo, ws)
        events = [
            e["learning"] for _n, e in ledger.iter_events_newest_first(repo / ".prawduct")
            if e.get("event") == "learning.compacted"
        ]
        assert {e["from_hash"] for e in events} == {lf.unit_hash("first phrasing"), lf.unit_hash("second phrasing")}
        assert {e["unit_hash"] for e in events} == {lf.unit_hash("the merged rule")}

    def test_apply_records_what_the_stop_hook_reads(self, tmp_path):
        # The Stop-side half is pinned in test_learning_events.py, against cmd_stop.
        repo = _repo(tmp_path, lf.CORE_HEADER + "\n- first phrasing\n")
        ws = _decide(lc.build_worksheet(repo), {
            "U001": {"action": "rewrite", "text": "- the rewritten rule", "file": "core.md"},
        })
        lc.apply(repo, ws)
        assert lf.unit_hash("the rewritten rule") in ledger.compacted_unit_hashes(repo / ".prawduct")


class TestCommand:
    def test_plan_and_apply_together_is_a_usage_error(self, tmp_path):
        repo = _repo(tmp_path, _legacy_core())
        assert _hook(repo, "--plan", "--apply").returncode == 2

    def test_an_unknown_flag_is_refused(self, tmp_path):
        repo = _repo(tmp_path, _legacy_core())
        assert _hook(repo, "--bogus").returncode == 2

    def test_plan_then_dry_run_then_apply(self, tmp_path):
        repo = _repo(tmp_path, _legacy_core())
        out = _hook(repo, "--plan")
        assert out.returncode == 0 and "rule(s) to decide" in out.stdout
        path = lc.worksheet_path(repo)
        dry = _hook(repo)
        assert dry.returncode == 1 and "no disposition" in dry.stdout
        lc.save(path, _all_rewritten(lc.load(path)))
        dry = _hook(repo, "--json")
        assert dry.returncode == 0 and json.loads(dry.stdout)["applied"] is False
        done = _hook(repo, "--apply")
        assert done.returncode == 0, done.stderr
        assert "`git revert` is the undo" in done.stdout
        assert not path.exists(), "an applied worksheet is removed so it cannot be re-applied"

    def test_plan_will_not_overwrite_decisions_without_force(self, tmp_path):
        repo = _repo(tmp_path, _legacy_core())
        _hook(repo, "--plan")
        path = lc.worksheet_path(repo)
        lc.save(path, _all_rewritten(lc.load(path)))
        assert _hook(repo, "--plan").returncode == 1
        assert _hook(repo, "--plan", "--force").returncode == 0

    def test_a_legacy_repo_is_sent_to_migrate(self, tmp_path):
        root = tmp_path / "legacy"
        (root / ".prawduct").mkdir(parents=True)
        (root / lf.LEGACY_REL).write_text("# Learnings\n- a rule\n")
        _git(root, "init", "-q")
        out = _hook(root, "--plan")
        assert out.returncode == 1 and "learnings-migrate" in out.stderr


# ---------------------------------------------------------------------------
# Every refusal, named — one case per `refusals.append(` site in the module
# ---------------------------------------------------------------------------


def _base(tmp_path):
    repo = _repo(tmp_path, _legacy_core(), {
        "app.md": '---\npaths:\n  - "src/**"\n---\n# app\n\n- an app rule\n',
    })
    return repo, _all_rewritten(lc.build_worksheet(repo))


def _set(ws, i, disposition):
    ws["rows"][i]["disposition"] = disposition
    return ws


def _gitignored(repo, ws):
    (repo / ".gitignore").write_text(".claude/\n")
    return ws


def _dirty(repo, ws):
    (repo / lf.RULES_DIR_REL / "scratch.md").write_text("# s\n")
    return ws


def _bad_preamble(repo, ws):
    ws["files"][CORE]["preamble"] = "# core\n\n- a rule in the preamble\nand a body under it"
    return ws


def _area_over_budget(repo, ws):
    ws["new_areas"] = {"big.md": ["src/**"]}
    for r in ws["rows"]:
        r["disposition"] = {"action": "rewrite", "text": "- " + "y" * 240, "file": "big.md"}
    ws["rows"].extend(dict(ws["rows"][0], id=f"X{i:03d}") for i in range(80))
    return ws


REFUSALS = [
    # (name, mutate(repo, ws) -> ws, needs git failure, substring)
    ("old schema", lambda repo, ws: {**ws, "schema": 0}, "schema"),
    ("corpus edited after plan", lambda repo, ws: ((repo / CORE).write_text("- edited\n"), ws)[1], "changed since --plan"),
    ("file created after plan", lambda repo, ws: ((repo / lf.RULES_DIR_REL / "new.md").write_text("# n\n"), ws)[1], "not in the worksheet"),
    ("new area named with a slash", lambda repo, ws: {**ws, "new_areas": {"../escape.md": ["src/**"]}}, "must be a plain"),
    ("new area that exists", lambda repo, ws: {**ws, "new_areas": {"app.md": ["src/**"]}}, "already exists"),
    ("new area with no globs", lambda repo, ws: {**ws, "new_areas": {"web.md": []}}, "needs at least one"),
    ("row without an id", lambda repo, ws: {**ws, "rows": [{"text": "x"}]}, "needs its `id`"),
    ("undecided row", lambda repo, ws: _set(ws, 0, None), "no disposition"),
    ("multi-line text", lambda repo, ws: _set(ws, 0, {"action": "rewrite", "text": "- a\nb", "file": "core.md"}), "one non-empty line"),
    ("unknown destination", lambda repo, ws: _set(ws, 0, {"action": "rewrite", "text": "- a", "file": "nope.md"}), "neither an existing"),
    ("rule not a bullet", lambda repo, ws: _set(ws, 0, {"action": "rewrite", "text": "a", "file": "core.md"}), "`- ` bullet"),
    ("banner with a marker", lambda repo, ws: _set(ws, 0, {"action": "banner", "text": "## A", "file": "core.md"}), "banner's text is plain"),
    ("rule over the limit", lambda repo, ws: _set(ws, 0, {"action": "rewrite", "text": "- " + "x" * 300, "file": "core.md"}), "over the"),
    ("drop without a reason", lambda repo, ws: _set(ws, 0, {"action": "drop", "approved": "2026-09-24"}), "names its reason"),
    ("moved-to outside the repo", lambda repo, ws: _set(ws, 0, {"action": "moved-to", "path": "../elsewhere.md", "anchor": "x" * 30}), "outside the rules directory"),
    ("moved-to with a short anchor", lambda repo, ws: _set(ws, 0, {"action": "moved-to", "path": "src/app.py", "anchor": "x = 1"}), "an `anchor` of at least"),
    ("moved-to text absent", lambda repo, ws: _set(ws, 0, {"action": "moved-to", "path": "src/app.py", "anchor": "text that was never moved here"}), "anchor text is not in"),
    ("unapproved drop", lambda repo, ws: _set(ws, 0, {"action": "drop", "reason": "stale"}), "approved:"),
    ("merge into a non-rewrite", lambda repo, ws: _set(ws, 0, {"action": "merge-into", "row": "U999"}), "merge-into must name"),
    ("written file breaks the format", _bad_preamble, "would still break the format"),
    ("area over its budget", _area_over_budget, "big.md would be"),
    ("gitignored rules without --local", _gitignored, "gitignored"),
    ("git cannot answer", "GITFAIL", "git could not report"),
    ("uncommitted rules", _dirty, "uncommitted changes"),
]


def test_the_table_covers_every_refusal_site():
    """Red when a refusal is added to the module without a case here — the
    count comes from the source, not from memory."""
    source = (_PLUGIN_ROOT / "lib" / "learnings_compact.py").read_text(encoding="utf-8")
    assert source.count("refusals.append(") == len(REFUSALS)


@pytest.mark.parametrize("name,mutate,expect", REFUSALS, ids=[r[0] for r in REFUSALS])
def test_each_refusal_is_named(tmp_path, monkeypatch, name, mutate, expect):
    repo, ws = _base(tmp_path)
    if mutate == "GITFAIL":
        from lib import learnings_migrate
        monkeypatch.setattr(learnings_migrate, "_git", lambda *a, **k: None)
    else:
        ws = mutate(repo, ws)
    refusals = lc.validate(repo, ws).refusals + lc.undo_refusals(repo, local=False)
    assert any(expect in r for r in refusals), refusals
    with pytest.raises(lc.CompactRefused):
        lc.apply(repo, ws)


class TestAnInterruptedApply:
    """A write that fails part-way leaves a half-written tree. The worksheet
    survives, the report names what reached disk, and the remedy restores and
    re-applies — never --plan --force, which would discard every decision."""

    def _two_file_ws(self, tmp_path):
        repo = _repo(tmp_path, _legacy_core())
        ws = _all_rewritten(lc.build_worksheet(repo))
        ws["new_areas"] = {"app.md": ["src/**"]}
        ws["rows"][2]["disposition"]["file"] = "app.md"
        return repo, ws

    def test_the_interruption_names_what_reached_disk(self, tmp_path, monkeypatch):
        repo, ws = self._two_file_ws(tmp_path)
        real = Path.write_text
        calls = {"n": 0}

        def failing(self, *a, **k):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("disk full")
            return real(self, *a, **k)

        monkeypatch.setattr(Path, "write_text", failing)
        with pytest.raises(lc.CompactInterrupted) as exc:
            lc.apply(repo, ws)
        assert len(exc.value.written) == 1

    def test_restore_then_reapply_with_the_same_worksheet_works(self, tmp_path, monkeypatch):
        repo, ws = self._two_file_ws(tmp_path)
        (repo / CORE).write_text("- half written\n")  # the interrupted state
        assert any("INTERRUPTED" in r for r in lc.validate(repo, ws).refusals)
        _git(repo, "checkout", "--", lf.RULES_DIR_REL)
        lc.apply(repo, ws)
        assert (repo / lf.RULES_DIR_REL / "app.md").is_file()

    def test_the_command_keeps_the_worksheet_and_says_not_to_force(self, tmp_path, monkeypatch, capsys):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("prawduct_hook_compact", str(HOOK))
        spec = importlib.util.spec_from_loader("prawduct_hook_compact", loader)
        hook = importlib.util.module_from_spec(spec)
        loader.exec_module(hook)
        repo, ws = self._two_file_ws(tmp_path)
        path = lc.worksheet_path(repo)
        lc.save(path, ws)

        def interrupted(*a, **k):
            raise lc.CompactInterrupted("OSError: disk full", [CORE])

        monkeypatch.setattr(lc, "apply", interrupted)
        rc = hook.cmd_learnings_compact(repo, ["--apply"])
        err = capsys.readouterr().err
        assert rc == 1 and "INTERRUPTED" in err and "Do NOT --plan --force" in err
        assert path.is_file()
