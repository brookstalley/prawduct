"""The gitignore contract is judged by what git would ignore, not by line equality (#762).

``core._contract_diff`` used to compare literal ``.gitignore`` lines. A wholesale rule such
as ``.prawduct/`` subsumes every session entry and matches none of them literally, so the
contract failed in BOTH directions: it called ignored session files "missing" (and the fixer
then appended redundant lines forever), and it never noticed that files prawduct needs
COMMITTED were being ignored by that same rule. "Needs committed" is the v2 product repo's own
state (``core.V2_COMMITTED_PATHS``), NOT ``MANAGED_FILES``: that is the 1.x file-sync registry
``migrate_plugin`` deletes, so a plugin-governed repo never has those files.

The fixtures here use the issue's own repro, a ``.gitignore`` of exactly ``.prawduct/`` and
``__pycache__/``, in two worlds: a real git repo, and a directory with no repo at all (the
onboard-before-``git init`` case), because the two take different paths to the same answer.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))

from lib import (  # noqa: E402
    change_fragments,
    change_log,
    change_log_archive,
    consumer_digest,
    init_product,
)
from lib import gitignore_probes as gp  # noqa: E402
from lib.advisory_store import Codebase, ProjectState, clear_registry  # noqa: E402
from lib.core import (  # noqa: E402
    GITIGNORE_ENTRIES,
    MANAGED_FILES,
    V2_COMMITTED_PATHS,
    describe_ignored_by_rule,
    gitignore_contract_drift,
    gitignore_covers,
    update_gitignore,
)

# `.claude/settings.local.json` is the one session entry outside `.prawduct/`.
OUTSIDE = ".claude/settings.local.json\n__pycache__/\n"
WHOLESALE = ".prawduct/\n" + OUTSIDE
# What a plugin-governed (v2) product repo commits, written out by hand from
# documentation/project-structure.md ("Product repos") and what `init_product` scaffolds. It is an
# INDEPENDENT copy of `core.V2_COMMITTED_PATHS`: `test_the_committed_set_is_the_v2_set` pins the
# two together, so neither can drift alone. A directory ends in "/".
V2_ALWAYS = [
    "AGENTS.md",
    "CLAUDE.md",
    ".claude/settings.json",
    ".claude/rules/",
    ".prawduct/project-state.yaml",
    ".prawduct/backlog.md",
    ".prawduct/changes/",
    ".prawduct/artifacts/",
]
V2_ON_DEMAND = [
    ".prawduct/change-log.md",
    ".prawduct/change-log-archive/",
    ".prawduct/releases/",
    ".prawduct/release-headline.md",
    ".prawduct/operator-verification.md",
    ".prawduct/owner-rulings.md",
    ".prawduct/runbooks/",
]
V2_ALL = [*V2_ALWAYS, *V2_ON_DEMAND]
# Under a wholesale `.prawduct/` rule in a tree where nothing optional exists yet, these are
# reported; with every optional path on disk, PRAWDUCT_ALL is.
PRAWDUCT_ALWAYS = sorted(p for p in V2_ALWAYS if p.startswith(".prawduct/"))
PRAWDUCT_ALL = sorted(p for p in V2_ALL if p.startswith(".prawduct/"))
# The lines that re-include all of it under a `.prawduct/*` rule.
REINCLUDE = [f"!.prawduct/{p.split('/')[1]}{'/' if p.count('/') > 1 else ''}" for p in PRAWDUCT_ALL]
# 1.x file-sync files `migrate_plugin` deletes: a v2 repo never has them, so the advisory must
# never name them as files prawduct "needs committed".
V1_ONLY = sorted(
    p for p in MANAGED_FILES if p not in V2_ALL and p not in ("tools/product-hook",)
)


def _sample(rel: str) -> str:
    """A path git is asked about for a committed entry: the file, or a file inside a directory."""
    return rel + "x.md" if rel.endswith("/") else rel


def _materialize(root: Path, rels=V2_ALL) -> None:
    for rel in rels:
        path = root / _sample(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")


def _git_ignores(repo: Path, rel: str) -> bool:
    """Independent of the code under test: ask git directly whether `rel` would be ignored."""
    proc = subprocess.run(  # noqa: S603
        ["git", "check-ignore", "--no-index", "-q", _sample(rel)],
        cwd=repo, capture_output=True, timeout=30,
    )
    assert proc.returncode in (0, 1), proc.stderr
    return proc.returncode == 0


_PASTE_MARKERS = ("Replace it with these lines: ", "Add these lines after it: ")


def _lines_in(sentence: str) -> list[str]:
    """The lines one printed sentence tells the owner to paste (its first option)."""
    for marker in _PASTE_MARKERS:
        if marker in sentence:
            return re.findall(r"`([^`]+)`", sentence.split(marker, 1)[1].split(". ", 1)[0])
    return []


def _advice_lines(entries) -> list[str]:
    """The lines the owner is told to paste, parsed from the printed sentences."""
    return [line for sentence in describe_ignored_by_rule(entries) for line in _lines_in(sentence)]


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
    assert len(PRAWDUCT_ALWAYS) >= 3 and len(PRAWDUCT_ALL) > len(PRAWDUCT_ALWAYS)
    assert V1_ONLY, "no 1.x-only managed path to prove the advisory stays off them"


def test_the_committed_set_is_the_v2_set():
    """The named constant is the hand-written v2 list above, not MANAGED_FILES (the 1.x
    migration registry), and each entry says whether a scaffolded repo always has it."""
    got = {c.path: c.always for c in V2_COMMITTED_PATHS}
    assert got == {**{p: True for p in V2_ALWAYS}, **{p: False for p in V2_ON_DEMAND}}


def test_the_committed_set_agrees_with_the_modules_that_write_it():
    """The paths other modules own, read from them: a rename there fails here."""
    paths = {c.path for c in V2_COMMITTED_PATHS}
    assert f"{change_fragments.FRAGMENT_DIR_REL}/" in paths
    assert f"{change_log_archive.ARCHIVE_DIR_REL}/" in paths
    assert change_log.CHANGE_LOG_REL_PATH in paths
    assert f"{consumer_digest.RELEASES_DIR_REL}/" in paths
    assert consumer_digest.HEADLINE_FILE_REL in paths
    assert consumer_digest.STATE_FILE_REL in paths
    # every file init_product places is either committed state or under a committed directory
    for dst, _tpl in init_product._STATE_TEMPLATES:
        assert dst in paths or any(dst.startswith(p) for p in paths if p.endswith("/")), dst


def test_a_v1_only_file_is_never_named_as_needing_commit(world):
    _write(world, WHOLESALE)
    _materialize(world)
    named = {e["path"] for e in gitignore_contract_drift(world)["ignored_by_rule"]}
    assert named, "control: the wholesale rule must report something"
    assert named.isdisjoint(V1_ONLY), sorted(named & set(V1_ONLY))
    for sentence in describe_ignored_by_rule(gitignore_contract_drift(world)["ignored_by_rule"]):
        for v1 in V1_ONLY:
            assert v1 not in sentence


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
    assert sorted(p for p in by_rule if p.startswith(".prawduct/")) == PRAWDUCT_ALWAYS
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
    assert sorted(e["path"] for e in result["ignored_by_rule"] if e["path"].startswith(".prawduct/")) == PRAWDUCT_ALWAYS
    assert gi.read_bytes() == before, "a user-authored wholesale rule was rewritten without consent"


def test_dry_run_is_byte_identical_and_reports_the_same(world):
    gi = _write(world, WHOLESALE)
    before = gi.read_bytes()
    preview = update_gitignore(world, dry_run=True)
    assert gi.read_bytes() == before
    assert sorted(e["path"] for e in preview["ignored_by_rule"] if e["path"].startswith(".prawduct/")) == PRAWDUCT_ALWAYS


def test_negated_reinclusion_satisfies_the_contract(world):
    # The shape the owner's remedy produces: `.prawduct/*` plus a re-include per managed file.
    text = ".prawduct/*\n" + "".join(f"{x}\n" for x in REINCLUDE) + OUTSIDE
    _write(world, text)
    drift = gitignore_contract_drift(world)
    assert drift["ignored_by_rule"] == []
    assert drift["missing"] == []
    assert drift["incorrectly_ignored"] == []


def test_partial_reinclusion_reports_only_what_is_still_ignored(world):
    kept = ".prawduct/project-state.yaml"
    rest = [p for p in PRAWDUCT_ALWAYS if p != kept]
    assert kept in PRAWDUCT_ALWAYS and rest
    _write(world, f".prawduct/*\n!{kept}\n" + OUTSIDE)
    drift = gitignore_contract_drift(world)
    assert sorted(e["path"] for e in drift["ignored_by_rule"] if e["path"].startswith(".prawduct/")) == sorted(rest)


def test_star_form_of_the_wholesale_rule_is_caught_too(world):
    _write(world, ".prawduct/*\n" + OUTSIDE)
    drift = gitignore_contract_drift(world)
    assert sorted(e["path"] for e in drift["ignored_by_rule"] if e["path"].startswith(".prawduct/")) == PRAWDUCT_ALWAYS
    assert drift["missing"] == []


def test_literal_managed_entry_is_still_removed_and_not_double_reported(world):
    managed = ".claude/settings.json"  # in MANAGED_FILES (stripped) and committed in v2 (reported)
    assert managed in MANAGED_FILES
    gi = _write(world, f"{managed}\n")
    drift = gitignore_contract_drift(world)
    assert drift["incorrectly_ignored"] == [managed]
    assert managed not in [e["path"] for e in drift["ignored_by_rule"]]
    result = update_gitignore(world)
    assert result["unignored"] == [managed]
    assert managed not in gi.read_text().splitlines()


@pytest.mark.parametrize(
    "rules",
    [
        [".prawduct/"],
        [".prawduct/*"],
        ["/.prawduct"],
        [".prawduct/**"],
        [".claude/"],
        [".claude/*"],
        [".prawduct/", ".claude/"],  # two rules, two sentences, pasted together
        ["*.md"],  # not a directory rule: the advice is per-file `!` lines after it
        # A basename directory rule (common for build output) excludes the committed
        # directory ITSELF, at any depth: `!dir/**` alone cannot re-include its contents.
        ["artifacts/"],
        ["releases/"],
    ],
)
def test_the_advised_lines_leave_every_v2_path_unignored(tmp_path, rules):
    """Follow the advice and ask GIT, not the advisory, about every v2 committed path.

    Clearing the advisory is not the goal; the files being committable is. The old advice cleared
    the advisory while project-state.yaml and the change fragments stayed hidden, so this pastes
    what the owner is offered and asserts, path by path, that git no longer ignores any of them.
    Session files must still be ignored afterwards (the rule was narrowed, not deleted)."""
    _git(tmp_path, "init", "-q", ".")
    _materialize(tmp_path)
    prefix = "\n".join(rules) + "\n"
    _write(tmp_path, prefix + OUTSIDE)
    before = gitignore_contract_drift(tmp_path)
    assert before["ignored_by_rule"], "control: the rule must be reported before the advice is followed"
    assert any(_git_ignores(tmp_path, p) for p in V2_ALL), "control: the rule must really hide a v2 path"
    lines = _advice_lines(before["ignored_by_rule"])
    assert lines, "the printed advice carries no lines to paste"
    # A wholesale directory rule is REPLACED by the advice; any other rule stays and the lines follow it.
    kept = [r for r in rules if not r.rstrip("/*").lstrip("/") in (".prawduct", ".claude")]
    _write(tmp_path, "\n".join([*kept, *lines]) + "\n" + OUTSIDE)
    still = [p for p in V2_ALL if _git_ignores(tmp_path, p)]
    assert still == [], f"following the advice left these ignored: {still}"
    after = gitignore_contract_drift(tmp_path)
    assert after["ignored_by_rule"] == []
    if ".prawduct/" in rules:  # only then does a rule stand in for the session entries
        assert after["missing"] == []
        assert _git_ignores(tmp_path, ".prawduct/.critic-active")


def test_a_literal_line_naming_a_v2_file_is_advised_by_deleting_it(tmp_path):
    # CLAUDE.md is a stripped MANAGED line, so use files the fixer does not own.
    _git(tmp_path, "init", "-q", ".")
    _materialize(tmp_path)
    _write(tmp_path, "AGENTS.md\n.prawduct/backlog.md\n" + OUTSIDE)
    entries = gitignore_contract_drift(tmp_path)["ignored_by_rule"]
    assert sorted(e["path"] for e in entries) == [".prawduct/backlog.md", "AGENTS.md"]
    for sentence in describe_ignored_by_rule(entries):
        assert "Delete that line" in sentence and "these lines" not in sentence
    _write(tmp_path, OUTSIDE)  # the advice, followed
    assert [p for p in V2_ALL if _git_ignores(tmp_path, p)] == []


def test_a_rule_that_is_the_directory_itself_is_advised_by_deleting_it(world):
    # `!dir/` cannot re-include a directory a rule excludes, so no replacement lines are offered.
    _write(world, ".prawduct/artifacts/\n" + OUTSIDE)
    entries = gitignore_contract_drift(world)["ignored_by_rule"]
    assert [e["path"] for e in entries] == [".prawduct/artifacts/"]
    (sentence,) = describe_ignored_by_rule(entries)
    assert "Delete that line" in sentence and "these lines" not in sentence


def test_optional_state_is_reported_only_when_it_exists(world):
    """`.prawduct/releases/` exists only in a repo that declares `consumer_digest:`. A repo
    without it must not be told that prawduct needs it committed."""
    _write(world, WHOLESALE)
    absent = {e["path"] for e in gitignore_contract_drift(world)["ignored_by_rule"]}
    assert absent == set(V2_ALWAYS) & {e for e in absent} and ".prawduct/releases/" not in absent
    _materialize(world, [".prawduct/releases/", ".prawduct/operator-verification.md"])
    present = {e["path"] for e in gitignore_contract_drift(world)["ignored_by_rule"]}
    assert {".prawduct/releases/", ".prawduct/operator-verification.md"} <= present
    assert ".prawduct/runbooks/" not in present


def test_the_replacement_reincludes_optional_state_that_does_not_exist_yet(world):
    # The cut will create `.prawduct/releases/` later; pasting the advice must not hide it then.
    _write(world, WHOLESALE)
    lines = _advice_lines(gitignore_contract_drift(world)["ignored_by_rule"])
    assert "!.prawduct/releases/" in lines and "!.prawduct/release-headline.md" in lines


def test_a_claude_rule_does_not_ask_to_unignore_personal_skills(world):
    _write(world, ".claude/\n" + OUTSIDE)
    sentences = " ".join(describe_ignored_by_rule(gitignore_contract_drift(world)["ignored_by_rule"]))
    assert "`.claude/*`" in sentences and "!.claude/settings.json" in sentences
    assert "skills" not in sentences


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


@pytest.fixture
def global_excludes(tmp_path_factory, monkeypatch):
    """A user-level excludes file NAMED `.gitignore` (the common `~/.gitignore`), outside the repo.

    Env-scoped: HOME points at a scratch home holding its own `.gitconfig`, so the real user's
    config is never read or written. Returns the file."""
    home = tmp_path_factory.mktemp("home")
    gfile = home / ".gitignore"
    gfile.write_text(
        ".claude/settings.local.json\n.prawduct/.critic-active\n.prawduct/.prawduct-version\n"
        "CLAUDE.md\n.prawduct/project-state.yaml\n",
        encoding="utf-8",
    )
    (home / ".gitconfig").write_text(f"[core]\n\texcludesFile = {gfile}\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg"))
    monkeypatch.delenv("GIT_CONFIG_GLOBAL", raising=False)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return gfile


def test_a_global_excludes_file_named_dot_gitignore_is_not_shared(world, global_excludes):
    """`core.excludesFile=~/.gitignore` shares a NAME with the repo's file and nothing else.

    It was counted as shared because the source's basename was `.gitignore`, so the user's own
    rules satisfied the repo's contract (session entries never written, the version marker never
    added) and hid the v2 files from the report. The decision is by PATH: a `.gitignore` inside
    the repo's work tree."""
    _write(world, "")
    # Control: git really does apply the global file here, and names it as the source.
    if (world / ".git").is_dir():
        proc = subprocess.run(
            ["git", "check-ignore", "--no-index", "-v", ".prawduct/.critic-active"],
            cwd=world, capture_output=True, text=True, timeout=30,
        )
        assert str(global_excludes) in proc.stdout, proc.stdout
    drift = gitignore_contract_drift(world)
    assert ".prawduct/.critic-active" in drift["missing"]
    assert ".claude/settings.local.json" in drift["missing"]
    assert drift["ignored_by_rule"] == []  # CLAUDE.md / project-state.yaml hidden only by the user's file
    assert gitignore_covers(world, ".prawduct/.prawduct-version") is False
    result = update_gitignore(world)
    assert ".prawduct/.critic-active" in result["missing"]
    assert ".prawduct/.critic-active" in (world / ".gitignore").read_text().splitlines()


def test_a_gitignore_in_the_work_tree_still_counts_with_a_global_file_present(world, global_excludes):
    # The control for the path decision: same rule text, but in the repo's own `.gitignore`.
    _write(world, ".prawduct/.critic-active\n")
    assert ".prawduct/.critic-active" not in gitignore_contract_drift(world)["missing"]
    _write(world, ".prawduct/.prawduct-version\n")
    assert gitignore_covers(world, ".prawduct/.prawduct-version") is True


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


def test_a_rule_hiding_committed_files_is_a_warning_in_the_owners_words(world):
    """Hidden committed files are lost on the next clone, the same stake as the legacy
    change-log advisory (`warn`), so this is not `info`. Its evidence is relayed to the
    product owner: it names the condition, never prawduct's source layout."""
    _write(world, WHOLESALE)
    (cand,) = gp.probe_gitignore_contract_drift(ProjectState({}), Codebase(root=world))
    assert cand.type == "contract-ignored-by-rule"
    assert cand.priority == "warn"
    for text in (*cand.evidence, cand.trigger_summary, cand.owner_action):
        assert "lib/" not in text and ".py" not in text and "V2_COMMITTED_PATHS" not in text, text


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


# --- following the advice literally, as the CLI prints it ------------------------


def _session_samples(root: Path) -> list[str]:
    """Write a file at every session entry under `.prawduct/` (a file inside a directory
    entry), as a working clone has them. Returns their repo-relative paths."""
    rels = [_sample(e) for e in GITIGNORE_ENTRIES if e.startswith(".prawduct/")]
    for rel in rels:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x\n", encoding="utf-8")
    assert rels, "fixture is vacuous: no session entry under .prawduct/"
    return rels


def _visible(repo: Path) -> set[str]:
    """What `git status` would offer to commit: untracked, not ignored."""
    proc = subprocess.run(  # noqa: S603
        ["git", "status", "--porcelain", "-uall"], cwd=repo,
        capture_output=True, text=True, timeout=30, check=True,
    )
    return {line[3:] for line in proc.stdout.splitlines() if line.startswith("?? ")}


def _printed_advice(repo: Path) -> str:
    proc = _hook(repo, "--dry-run")
    assert proc.returncode == 0, proc.stderr
    (sentence,) = [x for x in proc.stdout.splitlines() if x.startswith("cannot fix automatically:")]
    return sentence


def _follow_the_delete_option(repo: Path, sentence: str, rule: str) -> None:
    """Do what the deletion option says, word for word: drop the line, then run each
    `prawduct-hook` command that same option names (and nothing it does not)."""
    clause = re.split(r"(?i)\b(?=delete (?:it|that line))", sentence, maxsplit=1)[1]
    gi = repo / ".gitignore"
    gi.write_text(
        "".join(f"{x}\n" for x in gi.read_text(encoding="utf-8").splitlines() if x != rule),
        encoding="utf-8",
    )
    for op in re.findall(r"`prawduct-hook ([a-z-]+)`", clause):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "bin" / "prawduct-hook"), op],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
        )
        assert proc.returncode == 0, proc.stderr


def test_following_the_delete_option_exposes_no_session_file(tmp_path):
    """The repo this advice exists for ignores `.prawduct/` wholesale, which is why
    `update_gitignore` (it adds no line a broader rule already covers) never wrote a
    session entry there. Deleting the rule alone therefore offers every session file to
    the next `git add -A`; the deletion option must carry the step that restores them."""
    _git(tmp_path, "init", "-q", ".")
    _materialize(tmp_path)
    session = _session_samples(tmp_path)
    _write(tmp_path, ".prawduct/\n__pycache__/\n")
    assert not set(session) & _visible(tmp_path), "control: the rule hides the session files"
    _follow_the_delete_option(tmp_path, _printed_advice(tmp_path), ".prawduct/")
    visible = _visible(tmp_path)
    assert not set(session) & visible, sorted(set(session) & visible)
    # The deletion did its job: what prawduct commits is visible now.
    assert ".prawduct/project-state.yaml" in visible


def test_deleting_the_rule_without_the_named_step_exposes_session_files(tmp_path):
    # The control: the step the advice names is what keeps them hidden, not the fixture.
    _git(tmp_path, "init", "-q", ".")
    _materialize(tmp_path)
    session = _session_samples(tmp_path)
    _write(tmp_path, ".prawduct/\n__pycache__/\n")
    _write(tmp_path, "__pycache__/\n")
    assert set(session) <= _visible(tmp_path)


@pytest.mark.parametrize("rules", [[".prawduct/"], [".claude/"], ["*.md"]])
def test_the_option_that_leads_is_safe_on_its_own(tmp_path, rules):
    """The first option printed is the one an owner follows; it needs no second step.
    Pasting its lines leaves every session file hidden and every v2 path visible.

    The starting `.gitignore` is what the fixer leaves (it has already run), so each
    world holds exactly the session lines a real repo under that rule has: none under
    `.prawduct/` for a wholesale `.prawduct/`, all of them otherwise."""
    _git(tmp_path, "init", "-q", ".")
    _materialize(tmp_path)
    session = _session_samples(tmp_path)
    (tmp_path / ".claude" / "settings.local.json").write_text("{}\n", encoding="utf-8")
    _write(tmp_path, "\n".join(rules) + "\n__pycache__/\n")
    update_gitignore(tmp_path)
    sentence = _printed_advice(tmp_path)
    lead = sentence.split("Prawduct will not edit your rule. ", 1)[1]
    assert lead.startswith(_PASTE_MARKERS), lead
    lines = _lines_in(sentence)
    assert lines, sentence
    # A directory rule is REPLACED by the lines; any other rule stays and they follow it.
    rest = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    pasted: list[str] = []
    for x in rest:
        if x in rules:
            pasted += [x, *lines] if x.startswith("*") else lines
        else:
            pasted.append(x)
    _write(tmp_path, "\n".join(pasted) + "\n")
    visible = _visible(tmp_path)
    assert not set(session) & visible, sorted(set(session) & visible)
    assert [p for p in V2_ALL if _git_ignores(tmp_path, p)] == []


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
    assert sorted(e["path"] for e in result["ignored_by_rule"]) == PRAWDUCT_ALWAYS
    assert run([str(world), "--name", "P"]) == 0
    out = capsys.readouterr().out
    assert "cannot fix automatically:" in out and "`.prawduct/`" in out
