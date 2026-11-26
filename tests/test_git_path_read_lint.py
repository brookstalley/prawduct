"""Every git read in the plugin that prints path names is decoded, unquoted by `-z`, or
listed here with the reason it needs neither.

git C-quotes a name holding a non-ASCII byte, a quote, a backslash or a control character, and
a reader that compares that text with names on disk misses the file (`lib.gitstate.
unquote_git_path` is the one decoder; `tests/test_git_path_names.py` holds each reader to real
names). This scan finds each argument list that asks git for names, so a new reader cannot
skip the decoder without someone writing down why.
"""

from __future__ import annotations

import ast
from pathlib import Path

from conftest import plugin_python_sources

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"

#: The decoder and the parsers built on it. A function that calls one decodes what it reads.
DECODERS = frozenset({"git_path_lines", "unquote_git_path", "parse_porcelain_line", "diff_header_path"})

#: `<file>::<function>` → why its name-printing git read needs no decoding.
UNDECODED: dict[str, str] = {
    "hooks/banner.py::checkout_provenance": "porcelain v2 read for its branch headers and a dirty flag",
    "lib/boundary_coverage.py::_release_file_candidate": "ls-tree of a path it was given, read for emptiness",
    "lib/coverage.py::_committed_log_pending_verdict": "ls-tree of the fixed change-log path, read for emptiness",
    "lib/critic_mode.py::_working_tree_is_empty": "status read for emptiness",
    "lib/evidence.py::read_plugin_build": "ls-files --error-unmatch for its exit code; status for a dirty flag",
    "lib/git_hygiene.py::_reprove": "status read for emptiness",
    "lib/git_hygiene.py::_submodule_hold": "status read for emptiness",
    "lib/git_hygiene.py::reap": "status read for emptiness",
    "lib/gitstate.py::git_status_output": (
        "returns the porcelain text; its readers compare whole lines with a baseline taken the "
        "same way, then parse with parse_porcelain_line"),
    "lib/gitstate.py::worktree_records": "git prints worktree paths raw, never quoted",
    "lib/learnings_migrate.py::dirty_legacy_files": "the pathspec names only the fixed ASCII legacy files",
    "lib/learnings_migrate.py::unrecoverable_legacy_files": "ls-files --error-unmatch for its exit code",
    "lib/migrate_plugin.py::_git_untrack_kept": "ls-files --error-unmatch for its exit code",
    "lib/native_review.py::_return_review_tree": "status read for emptiness",
    "lib/native_review.py::_review_tree_refusal": "status read for emptiness",
    "lib/native_review.py::leftover_tree": "status read for emptiness",
    "lib/pr_gate.py::_legacy_log_touched": "diff of the fixed change-log path, read for emptiness",
}


def _is_name_read(words: "set[str]") -> bool:
    """Whether a git argument list asks for output that prints path names."""
    return bool(
        words & {"--name-only", "--name-status", "ls-files", "ls-tree", "diff-tree"}
        or ("grep" in words and "-l" in words)
        or any(word.startswith("--porcelain") for word in words)
    )


def _words(node: ast.AST) -> "set[str]":
    """The string constants an argument list carries: a list or tuple literal's elements, or a
    call's positional arguments and the list or tuple literals among them."""
    items: list[ast.AST] = []
    if isinstance(node, (ast.List, ast.Tuple)):
        items = list(node.elts)
    elif isinstance(node, ast.Call):
        for arg in node.args:
            items.extend(arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else [arg])
    return {i.value for i in items if isinstance(i, ast.Constant) and isinstance(i.value, str)}


def _calls_a_decoder(function: ast.AST) -> bool:
    """Whether ``function`` uses a decoder, called or passed uncalled (``map(parse, lines)``)."""
    for node in ast.walk(function):
        name = node.attr if isinstance(node, ast.Attribute) else node.id if isinstance(node, ast.Name) else ""
        if name in DECODERS:
            return True
    return False


def name_reads(source: str) -> "dict[str, bool]":
    """``{function: decoded}`` for each top-level function (or method) holding a name-printing
    git read without `-z`. A nested function's read belongs to the function it sits in, which
    is where its output is used."""
    tree = ast.parse(source)
    out: dict[str, bool] = {}

    def visit(scope: str, body: "list[ast.stmt]", owner: "ast.AST | None") -> None:
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and owner is None:
                visit(f"{scope}{stmt.name}.", stmt.body, stmt)  # a new owner
                continue
            if isinstance(stmt, ast.ClassDef) and owner is None:
                visit(f"{scope}{stmt.name}.", stmt.body, None)
                continue
            # Anything else, a nested function included, is read as part of its owner.
            for node in ast.walk(stmt):
                words = _words(node)
                if words and _is_name_read(words) and "-z" not in words:
                    key = scope.rstrip(".") or "<module>"
                    out[key] = _calls_a_decoder(owner) if owner is not None else False

    visit("", tree.body, None)
    return out


def inventory() -> "dict[str, bool]":
    found: dict[str, bool] = {}
    for path in plugin_python_sources():
        rel = path.relative_to(PLUGIN).as_posix()
        for function, decoded in name_reads(path.read_text(encoding="utf-8", errors="replace")).items():
            found[f"{rel}::{function}"] = decoded
    return found


def test_the_scan_sees_each_spelling():
    """The scan's own control: a literal list, a helper's arguments, a tuple built before the
    call, a nested helper, `-z`, and a decoded read, each answered as it must be."""
    source = '''
def raw_list(p):
    return subprocess.run(["git", "diff", "--name-only", "x"], cwd=p).stdout.splitlines()

def helper_args(p):
    return run_git(p, "ls-files", "--others")[1].splitlines()

def built_tuple(p):
    args = ("grep", "-l", "-e", "x")
    return run_git(p, *args)

def nested(p):
    def _git(*a):
        return subprocess.run(["git", *a])
    return _git("ls-tree", "-r", "--name-only", "HEAD").stdout.splitlines()

def with_z(p):
    return run_git(p, "status", "--porcelain", "-z")

def decoded(p):
    return gitstate.git_path_lines(run_git(p, "diff", "--name-only")[1])

def decoded_by_map(p):
    return list(map(gitstate.parse_porcelain_line, run_git(p, "status", "--porcelain")[1].split()))

def unrelated(p):
    return run_git(p, "rev-parse", "HEAD")
'''
    assert name_reads(source) == {
        "raw_list": False, "helper_args": False, "built_tuple": False, "nested": False,
        "decoded": True, "decoded_by_map": True,
    }


def test_every_name_read_is_decoded_or_listed():
    found = inventory()
    # The scan reached the readers it exists for: the decoded ones are in its set.
    assert found.get("lib/coverage.py::_coverage_changed_files") is True, sorted(found)
    assert found.get("bin/prawduct-hook::_judge_flakes") is True, sorted(found)
    undecoded = {key for key, decoded in found.items() if not decoded}
    assert undecoded == set(UNDECODED), "\n".join(sorted(undecoded ^ set(UNDECODED)))
