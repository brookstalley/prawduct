"""`prawduct-hook --project-dir`: a caller names the tree a command acts on (#1253).

Measured on Claude Code 2.1.332: a `context: fork` skill invoked by a subagent
that works in a second repository runs its shell in the session's launch repo,
and its environment names nothing of the caller. So `/prawduct:critic` reviewed
the launch repo ("nothing to review"), and `/prawduct:backlog` or
`/prawduct:advisory` would have written into the launch repo's store. The
forked skill's arguments do reach it, so the caller names its repo and the fork
passes `--project-dir` to every `prawduct-hook` call. `_dispatch` pops it before
any command parses, validates it, `chdir`s there and makes it the project dir
over the launch pin and the cwd.

Every CLI case here reproduces the measured shape: the shell's cwd AND
`CLAUDE_PROJECT_DIR` both name repo A, and the option names repo B. Sterile git
repos under `tmp_path`, HOME outside them (the pyc-cache learning), mirroring
`tests/test_classify_diff_risk.py`.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
SKILLS_DIR = ROOT / "skills"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import advisory_store  # noqa: E402
from lib import critic_consolidate  # noqa: E402
from conftest import scrubbed_env  # noqa: E402

_loader = importlib.machinery.SourceFileLoader("prawduct_hook_project_dir", str(HOOK))
_spec = importlib.util.spec_from_loader("prawduct_hook_project_dir", _loader)
_hook = importlib.util.module_from_spec(_spec)
_loader.exec_module(_hook)

PARTIALS_MANIFEST = Path(".prawduct") / ".critic-partials" / "manifest.json"
TREE_LINE_RE = re.compile(r"^PRAWDUCT: tree (?P<top>\S+) · (?P<branch>\S+) @ (?P<sha>\S+)$")


# --- fixtures ----------------------------------------------------------------


def _env(tmp_path: Path, pin: Path) -> dict[str, str]:
    return scrubbed_env(tmp_path / "_home", CLAUDE_PROJECT_DIR=str(pin))


def _git(repo: Path, tmp_path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=scrubbed_env(tmp_path / "_home"), check=True, timeout=10,
    ).stdout.strip()


def _init_repo(tmp_path: Path, name: str) -> Path:
    repo = (tmp_path / name).resolve()
    repo.mkdir(parents=True)
    _git(repo, tmp_path, "init", "--quiet", "-b", "main")
    _git(repo, tmp_path, "config", "user.email", "test@example.com")
    _git(repo, tmp_path, "config", "user.name", "Test")
    _git(repo, tmp_path, "config", "commit.gpgsign", "false")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x = 1\n")
    (repo / ".prawduct").mkdir()
    (repo / ".prawduct" / "project-state.yaml").write_text(f"project_name: {name}\n")
    _git(repo, tmp_path, "add", "-A")
    _git(repo, tmp_path, "commit", "--quiet", "-m", "init")
    return repo


def _advisory(advisory_id: str) -> dict:
    return {
        "id": advisory_id, "feature": "synthetic", "type": "synthetic-condition",
        "probe_version": 1, "triggered_at": "2026-05-01T00:00:00Z",
        "triggered_by_sync_version": "", "trigger_summary": "synthetic trigger.",
        "evidence": ["sig"], "recommended_action": "/synthetic fix",
        "alternative_actions": [], "priority": "info", "state": "active",
        "superseded_by": None, "dismissed_at": None, "dismissed_reason": None,
        "resolved_at": None, "resolved_by": None,
    }


A_ID = "synthetic-synthetic-condition-v1-aaaaaa"
B_ID = "synthetic-synthetic-condition-v1-bbbbbb"


@pytest.fixture
def two_repos(tmp_path):
    """Repo A (the launch repo: cwd and pin) and repo B (the caller's), each with
    an advisory store holding one advisory of its own."""
    a = _init_repo(tmp_path, "a")
    b = _init_repo(tmp_path, "b")
    advisory_store.write_store(str(a), {"schema_version": 1, "advisories": [_advisory(A_ID)]})
    advisory_store.write_store(str(b), {"schema_version": 1, "advisories": [_advisory(B_ID)]})
    return a, b


def _run(tmp_path: Path, cwd: Path, pin: Path, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), *argv], cwd=str(cwd), capture_output=True,
        text=True, env=_env(tmp_path, pin), timeout=60,
    )


def _state(repo: Path, advisory_id: str) -> str:
    store = advisory_store.read_store(str(repo))
    return next(a["state"] for a in store["advisories"] if a["id"] == advisory_id)


# --- the option wins over the pin and the cwd --------------------------------


def test_a_read_acts_on_the_named_tree(tmp_path, two_repos):
    a, b = two_repos
    control = _run(tmp_path, a, a, "advisory", "list")
    assert control.returncode == 0, control.stderr
    assert A_ID in control.stdout and B_ID not in control.stdout, (
        "control: without the option the launch repo answers"
    )
    named = _run(tmp_path, a, a, "advisory", "list", "--project-dir", str(b))
    assert named.returncode == 0, named.stderr
    assert B_ID in named.stdout and A_ID not in named.stdout


def test_a_write_acts_on_the_named_tree(tmp_path, two_repos):
    a, b = two_repos
    result = _run(tmp_path, a, a, "advisory", "dismiss", "--project-dir", str(b), B_ID)
    assert result.returncode == 0, result.stderr
    assert _state(b, B_ID) == "dismissed"
    assert _state(a, A_ID) == "active", "the launch repo's store is untouched"


def test_the_same_tree_named_twice_is_one_tree(tmp_path, two_repos):
    """A skill forwards its arguments verbatim to `infer-critic-mode` and is
    also told to append the option, so the same value can arrive twice."""
    a, b = two_repos
    result = _run(tmp_path, a, a, "advisory", "list", "--project-dir", str(b), f"--project-dir={b}")
    assert result.returncode == 0, result.stderr
    assert B_ID in result.stdout and A_ID not in result.stdout


def test_the_equals_form_is_the_same_option(tmp_path, two_repos):
    a, b = two_repos
    result = _run(tmp_path, a, a, "advisory", "list", f"--project-dir={b}")
    assert result.returncode == 0, result.stderr
    assert B_ID in result.stdout and A_ID not in result.stdout


def test_a_critic_review_dispatches_against_the_named_tree(tmp_path, two_repos):
    """The acceptance criterion: the measured repro's shape reviews B, and the
    run's first line names B. Without the option the line names A."""
    a, b = two_repos
    (a / "src" / "app.py").write_text("x = 'a'\n")
    (b / "src" / "app.py").write_text("x = 'b'\n")
    named = _run(tmp_path, a, a, "critic-begin", "--mode", "chunk", "--project-dir", str(b))
    assert named.returncode == 0, named.stderr
    first = TREE_LINE_RE.match(named.stdout.splitlines()[0])
    assert first and Path(first["top"]) == b, named.stdout
    assert (b / PARTIALS_MANIFEST).is_file()
    assert not (a / PARTIALS_MANIFEST).exists()
    manifest = json.loads((b / PARTIALS_MANIFEST).read_text())
    assert Path(manifest["worktree"]).resolve() == b

    _run(tmp_path, b, b, "critic-end")
    control = _run(tmp_path, a, a, "critic-begin", "--mode", "chunk")
    assert control.returncode == 0, control.stderr
    first = TREE_LINE_RE.match(control.stdout.splitlines()[0])
    assert first and Path(first["top"]) == a, control.stdout


# --- refusals: each by name, nothing run --------------------------------------


@pytest.mark.parametrize(
    "shape, code, message",
    [
        ("missing-at-end", 2, "requires a value"),
        ("missing-before-flag", 2, "requires a value"),
        ("empty-equals", 2, "requires a value"),
        ("relative", 2, "is a relative path"),
        ("two-trees", 2, "names two trees"),
        ("nonexistent", 1, "no such directory"),
        ("subdirectory", 1, "not its toplevel"),
        ("not-a-repo", 1, "is not a git work tree"),
    ],
)
def test_each_refusal_names_itself_and_runs_nothing(tmp_path, two_repos, shape, code, message):
    a, b = two_repos
    plain = tmp_path / "plain"
    plain.mkdir()
    option = {
        "missing-at-end": ["--project-dir"],
        "missing-before-flag": ["--project-dir", "--reason", "x"],
        "empty-equals": ["--project-dir="],
        "relative": ["--project-dir", "b"],
        "two-trees": ["--project-dir", str(b), "--project-dir", str(a)],
        "nonexistent": ["--project-dir", str(tmp_path / "nowhere")],
        "subdirectory": ["--project-dir", str(b / "src")],
        "not-a-repo": ["--project-dir", str(plain)],
    }[shape]
    # The id is A's, so a refusal that fell through to the launch repo would
    # dismiss it there — "nothing ran" is checked on the store, not the prose.
    result = _run(tmp_path, a, a, "advisory", "dismiss", A_ID, *option)
    assert result.returncode == code, (result.stdout, result.stderr)
    assert message in result.stderr and "Nothing ran." in result.stderr
    assert _state(a, A_ID) == "active"
    assert _state(b, B_ID) == "active"


# --- a bare `--` ends the dispatcher's reach -----------------------------------


def test_the_option_after_a_bare_separator_is_the_passthrough_commands():
    remaining = ["record", "--no-rerun", "--", "--project-dir", "/somewhere"]
    assert _hook._pop_project_dir("test-evidence", list(remaining)) == (None, remaining, 0)
    # Control: before the separator it is the dispatcher's.
    assert _hook._pop_project_dir(
        "test-evidence", ["record", "--project-dir", "/p", "--", "-k", "x"]
    ) == ("/p", ["record", "--", "-k", "x"], 0)


def test_the_passthrough_receives_a_later_project_dir_through_the_cli(tmp_path, two_repos):
    """Through the real CLI: `test-evidence record --no-rerun` refuses extra
    args by name, so the token reached the passthrough rather than being
    validated (and refused as a missing directory) by the dispatcher."""
    a, _b = two_repos
    result = _run(
        tmp_path, a, a, "test-evidence", "record", "--no-rerun",
        "--", "--project-dir", str(tmp_path / "nowhere"),
    )
    assert "no such directory" not in result.stderr, result.stderr
    assert "extra args are not allowed with --no-rerun" in result.stderr, result.stderr


# --- PDT-WT9K agrees with the named tree --------------------------------------


def test_the_wrong_tree_guard_passes_with_the_option(tmp_path, two_repos):
    """Shell in A, pin on an unrelated B: without the option the guard refuses
    (below); naming B makes the shell and the review one tree."""
    a, b = two_repos
    (b / "src" / "app.py").write_text("x = 'b'\n")
    result = _run(tmp_path, a, b, "critic-begin", "--mode", "chunk", "--project-dir", str(b))
    assert result.returncode == 0, result.stderr
    assert "refusing" not in result.stderr
    assert (b / PARTIALS_MANIFEST).is_file()


def test_the_wrong_tree_guard_still_refuses_without_it(tmp_path, two_repos):
    a, b = two_repos
    (b / "src" / "app.py").write_text("x = 'b'\n")
    result = _run(tmp_path, a, b, "critic-begin", "--mode", "chunk")
    assert result.returncode == 1
    assert "refusing" in result.stderr and "--project-dir" in result.stderr
    first = TREE_LINE_RE.match(result.stdout.splitlines()[0])
    assert first and Path(first["top"]) == b, "the refusal still names the tree it resolved"
    assert not (b / PARTIALS_MANIFEST).exists()


# --- the tree line leads every critic-begin outcome ---------------------------


def _fake_results() -> dict[str, tuple[dict, int]]:
    cc = critic_consolidate
    return {
        "budget-exhausted": ({"status": "budget-exhausted", "reason": "budget spent"}, 4),
        "no-review-needed": ({"status": "no-review-needed", "reason": "nothing judgeable"}, 3),
        "precondition-failed": ({"status": "precondition-failed", "reason": "stale"}, 7),
        "chunks-ambiguous": (
            {"status": "error", "kind": cc.CHUNKS_AMBIGUOUS_KIND, "reason": "two chunks"}, 8,
        ),
        "credential": ({"status": cc.CREDENTIAL_REFUSED, "findings": ["f.py:1 key"]}, 9),
        "scope-widened": ({"status": "error", "kind": "scope-widened", "reason": "wide"}, 2),
        "store-unusable": ({"status": "error", "kind": "store-unusable", "reason": "bad"}, 6),
        "error": ({"status": "error", "reason": "a review is live"}, 1),
    }


@pytest.mark.parametrize("outcome", sorted(_fake_results()))
def test_the_tree_line_is_first_on_every_refusal(tmp_path, monkeypatch, capsys, outcome):
    """Every `begin_review` outcome `cmd_critic_begin` branches on, each with
    its own exit code, so a branch that returned before the line would show."""
    repo = _init_repo(tmp_path, "r")
    result, code = _fake_results()[outcome]
    monkeypatch.chdir(repo)
    monkeypatch.setattr(critic_consolidate, "begin_review", lambda *_a, **_k: result)
    assert _hook.cmd_critic_begin(repo, ["--mode", "chunk"]) == code
    head = _git(repo, tmp_path, "rev-parse", "HEAD")[:12]
    assert capsys.readouterr().out.splitlines()[0] == f"PRAWDUCT: tree {repo} · main @ {head}"


def test_the_tree_line_is_first_when_a_review_dispatches_and_when_none_is_needed(tmp_path, two_repos):
    """The two outcomes a caller most often reads as an answer, through the CLI."""
    a, _b = two_repos
    free = _run(tmp_path, a, a, "critic-begin", "--mode", "chunk")
    assert free.returncode == 3, (free.stdout, free.stderr)
    (a / "src" / "app.py").write_text("x = 2\n")
    dispatched = _run(tmp_path, a, a, "critic-begin", "--mode", "chunk")
    assert dispatched.returncode == 0, dispatched.stderr
    head = _git(a, tmp_path, "rev-parse", "HEAD")[:12]
    for run in (free, dispatched):
        assert run.stdout.splitlines()[0] == f"PRAWDUCT: tree {a} · main @ {head}"


def test_the_tree_line_names_a_detached_head_and_a_tree_outside_git(tmp_path, monkeypatch, capsys):
    repo = _init_repo(tmp_path, "r")
    _git(repo, tmp_path, "checkout", "--quiet", "--detach")
    assert _hook._critic_tree_line(repo).split(" · ")[1].startswith("(detached) @ ")
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _hook._critic_tree_line(plain) == f"PRAWDUCT: tree {plain} · (not a git work tree)"


def test_a_tree_that_is_not_onboarded_is_named_too(tmp_path, two_repos):
    a, _b = two_repos
    bare = _init_repo(tmp_path, "c")
    _git(bare, tmp_path, "rm", "-r", "--quiet", ".prawduct")
    _git(bare, tmp_path, "commit", "--quiet", "-m", "off")
    result = _run(tmp_path, a, a, "critic-begin", "--mode", "chunk", "--project-dir", str(bare))
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert TREE_LINE_RE.match(lines[0]) and Path(TREE_LINE_RE.match(lines[0])["top"]) == bare
    assert "not an onboarded repo" in lines[1]


# --- the forked skills accept and pass the option ------------------------------


def _frontmatter(text: str) -> tuple[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert match, "a SKILL.md without frontmatter"
    return match.group(1), match.group(2)


def _forked_skills() -> dict[str, tuple[str, str]]:
    found = {}
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        front, body = _frontmatter(path.read_text(encoding="utf-8"))
        if re.search(r"^context:\s*fork\s*$", front, re.M):
            found[path.parent.name] = (front, body)
    return found


def test_the_forked_skill_sweep_has_subjects():
    forked = _forked_skills()
    assert forked, "no `context: fork` skill found — the guard below swept nothing"
    assert {"critic", "backlog", "advisory"} <= set(forked), sorted(forked)


@pytest.mark.parametrize("name", sorted(_forked_skills()))
def test_every_forked_skill_accepts_and_passes_project_dir(name):
    """A fork starts in the launch repo whoever invokes it, so every forked
    skill — including one added later — must accept the caller's tree and say
    how to carry it."""
    front, body = _forked_skills()[name]
    hint = re.search(r"^argument-hint:(.*)$", front, re.M)
    assert hint and "--project-dir" in hint.group(1), f"{name}: argument-hint lacks --project-dir"
    assert "--project-dir" in body, f"{name}: the body never says how to carry --project-dir"


@pytest.mark.parametrize("name", sorted(_forked_skills()))
def test_a_bare_hook_grant_admits_the_option(name):
    """A grant is a literal prefix: `Bash(prawduct-hook critic-end)` does not
    match `prawduct-hook critic-end --project-dir /x`, so every bare grant in a
    forked skill carries its `--project-dir` sibling."""
    front, _body = _forked_skills()[name]
    grants = re.findall(r"Bash\(([^)]*)\)", front)
    bare = [g for g in grants if "prawduct-hook" in g and not g.endswith("*")]
    for grant in bare:
        assert f"{grant} --project-dir *" in grants, f"{name}: {grant!r} has no --project-dir form"


def test_the_critic_grants_every_git_verb_through_git_c():
    """Under `--project-dir` every git call is `git -C <dir> …`, and a grant is
    a literal prefix, so each verb the critic may run needs its `-C` form."""
    front, _body = _forked_skills()["critic"]
    grants = re.findall(r"Bash\((git [^)]*)\)", front)
    plain = [g for g in grants if not g.startswith("git -C ")]
    assert len(plain) >= 7, plain
    for grant in plain:
        assert "git -C * " + grant[len("git "):] in grants, f"no -C form of {grant!r}"
