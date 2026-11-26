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

#: The decoder and the parsers built on it, each reference counting once against a read.
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


#: Runners that trim git's output, and the keyword that stops it (``None``: always trims).
#: Trimming takes the leading space off the first line: a porcelain status column, or a name
#: that begins with a space. Module-local wrappers that trim are named by their file.
TRIMMING: dict[str, "str | None"] = {"run_git": "strip", "_git_text": None}
TRIMMING_IN_FILE: dict[str, frozenset[str]] = {
    "lib/boundary_coverage.py": frozenset({"git", "_git"}),
    "lib/git_hygiene.py": frozenset({"_git"}),
    "lib/evidence_sync.py": frozenset({"_git"}),
    "lib/stranded_work.py": frozenset({"_git"}),
}

#: `<file>::<function>` → why a function reading ``git_status_output``'s text needs no decoder.
STATUS_TEXT_READERS: dict[str, str] = {
    "bin/prawduct-hook::cmd_stop": "passes the text to git_has_session_changes and session_work_span",
    "bin/prawduct-hook::_boundary_capture_git_anchors": (
        "stores it byte-exact as the session baseline, compared later line by line with status "
        "text taken the same way"),
    "lib/gates.py::session_work_span": "passes the text to gitstate._get_session_changed_files",
    "lib/gitstate.py::git_has_changes": "returns its first line, read for truthiness and shown as-is",
}


def _is_name_read(words: "set[str]") -> bool:
    """Whether a git argument list asks for output that prints path names."""
    return bool(
        words & {"--name-only", "--name-status", "ls-files", "ls-tree", "diff-tree"}
        or ("grep" in words and words & {"-l", "-L", "--files-with-matches", "--files-without-match"})
        or any(word.startswith("--porcelain") for word in words)
    )


def _constants(items: "list[ast.AST]") -> "set[str]":
    return {i.value for i in items if isinstance(i, ast.Constant) and isinstance(i.value, str)}


def _name(node: ast.AST) -> str:
    return node.attr if isinstance(node, ast.Attribute) else node.id if isinstance(node, ast.Name) else ""


class Facts:
    """What one top-level function (or method) does with git names. A nested function's
    reads belong to the function it sits in, which is where their output is used."""

    def __init__(self) -> None:
        self.reads = 0          # name-printing git argument lists without `-z`
        self.decoders = 0       # references to a decoder, called or passed uncalled
        self.trimmed = False    # a trimming runner reads names (with or without `-z`)
        self.parses_headers = False   # it parses `diff --git` header lines
        self.header_decoded = False   # ... through `gitstate.diff_header_path`
        self.status_text = False      # it reads `git_status_output`'s text


def scan(source: str, rel: str = "") -> "dict[str, Facts]":
    tree = ast.parse(source)
    trimming = dict(TRIMMING) | {name: None for name in TRIMMING_IN_FILE.get(rel, ())}
    if rel == "lib/stranded_work.py":
        trimming["_git"] = "strip"
    out: dict[str, Facts] = {}

    def record(key: str, node: ast.AST) -> None:
        facts = out.setdefault(key, Facts())
        if isinstance(node, (ast.List, ast.Tuple)):
            words = _constants(node.elts)
            if _is_name_read(words) and "-z" not in words:
                facts.reads += 1
        elif isinstance(node, ast.Call):
            words = _constants(node.args)
            for arg in node.args:
                if isinstance(arg, (ast.List, ast.Tuple)):
                    words |= _constants(arg.elts)
            direct = _constants(node.args)
            if _is_name_read(direct) and "-z" not in direct:
                facts.reads += 1
            runner = _name(node.func)
            if runner in trimming and _is_name_read(words):
                keyword = trimming[runner]
                kept = any(k.arg == keyword and isinstance(k.value, ast.Constant) and k.value.value is False
                           for k in node.keywords) if keyword else False
                facts.trimmed = facts.trimmed or not kept
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "diff --git" in node.value:
            facts.parses_headers = True
        name = _name(node)
        if name in DECODERS:
            facts.decoders += 1
        if name == "diff_header_path":
            facts.header_decoded = True
        if name == "git_status_output":
            facts.status_text = True

    def visit(scope: str, body: "list[ast.stmt]", owner: bool) -> None:
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and not owner:
                visit(f"{scope}{stmt.name}.", stmt.body, True)
                continue
            if isinstance(stmt, ast.ClassDef) and not owner:
                visit(f"{scope}{stmt.name}.", stmt.body, False)
                continue
            for node in ast.walk(stmt):
                record(scope.rstrip(".") or "<module>", node)

    visit("", tree.body, False)
    return {key: facts for key, facts in out.items()
            if facts.reads or facts.trimmed or facts.parses_headers or facts.status_text}


def inventory() -> "dict[str, Facts]":
    found: dict[str, Facts] = {}
    for path in plugin_python_sources():
        rel = path.relative_to(PLUGIN).as_posix()
        for function, facts in scan(path.read_text(encoding="utf-8", errors="replace"), rel).items():
            found[f"{rel}::{function}"] = facts
    return found


def test_the_scan_sees_each_spelling():
    """The scan's own control: each spelling of a read, `-z`, a decoder called or passed, a
    function that decodes one of its two reads, a trimming runner, a header parser and a
    status-text reader, each answered as it must be."""
    source = '''
def raw_list(p):
    return subprocess.run(["git", "diff", "--name-only", "x"], cwd=p).stdout.splitlines()

def helper_args(p):
    return run_git(p, "ls-files", "--others", strip=False)[1].splitlines()

def built_tuple(p):
    args = ("grep", "-l", "-e", "x")
    return run_git(p, *args, strip=False)

def nested(p):
    def _git(*a):
        return subprocess.run(["git", *a])
    return _git("ls-tree", "-r", "--name-only", "HEAD").stdout.splitlines()

def with_z(p):
    return run_git(p, "status", "--porcelain", "-z", strip=False)

def decoded(p):
    return gitstate.git_path_lines(run_git(p, "diff", "--name-only", strip=False)[1])

def decoded_by_map(p):
    return list(map(gitstate.parse_porcelain_line, run_git(p, "status", "--porcelain", strip=False)[1]))

def one_of_two_decoded(p):
    a = gitstate.git_path_lines(run_git(p, "diff", "--name-only", strip=False)[1])
    return a, run_git(p, "ls-files", strip=False)[1].split("\\n")

def trimmed(p):
    return run_git(p, "ls-files", "-z")[1].split("\\0")

def header_parser(out):
    return [line for line in out.split("\\n") if line.startswith("diff --git ")]

_HEADER_RE = re.compile(r"^diff --git a/(?:.*) b/(.+)$")

def status_reader(p):
    return gitstate.git_status_output(p).split("\\n")

def unrelated(p):
    return run_git(p, "rev-parse", "HEAD")
'''
    found = {key: (f.reads, f.decoders, f.trimmed, f.parses_headers, f.status_text)
             for key, f in scan(source).items()}
    assert found == {
        "raw_list": (1, 0, False, False, False),
        "helper_args": (1, 0, False, False, False),
        "built_tuple": (1, 0, False, False, False),
        "nested": (1, 0, False, False, False),
        "decoded": (1, 1, False, False, False),
        "decoded_by_map": (1, 1, False, False, False),
        "one_of_two_decoded": (2, 1, False, False, False),
        "trimmed": (0, 0, True, False, False),
        "header_parser": (0, 0, False, True, False),
        "<module>": (0, 0, False, True, False),
        "status_reader": (0, 0, False, False, True),
    }


def test_every_name_read_is_decoded_or_listed():
    """A function decodes each name read it makes (one decoder per read), or is listed with the
    reason its reads use no name."""
    found = inventory()
    # The scan reached the readers it exists for.
    assert found["lib/coverage.py::_coverage_changed_files"].decoders >= 2, sorted(found)
    assert found["bin/prawduct-hook::_judge_flakes"].reads == 1, sorted(found)
    short = {key for key, f in found.items() if f.reads > f.decoders}
    assert short == set(UNDECODED), "\n".join(sorted(short ^ set(UNDECODED)))


def test_no_name_read_is_trimmed():
    """`evidence.run_git` trims git's output unless told `strip=False`, which takes the status
    column's leading space off the first porcelain line and a leading space off a first name."""
    trimmed = {key for key, f in inventory().items() if f.trimmed} - set(UNDECODED)
    assert trimmed == set(), "\n".join(sorted(trimmed))


def test_every_diff_header_parser_decodes_the_header():
    found = inventory()
    parsers = {key for key, f in found.items() if f.parses_headers}
    assert "lib/record_lint.py::_parse_diff" in parsers, sorted(parsers)
    undecoded = {key for key, f in found.items() if f.parses_headers and not f.header_decoded}
    assert undecoded == {"lib/gitstate.py::diff_header_path"}, sorted(undecoded)


def test_every_reader_of_status_text_decodes_or_is_listed():
    """`gitstate.git_status_output` returns git's porcelain text undecoded; each function that
    reads it decodes, or says why it needs no name."""
    found = inventory()
    readers = {key for key, f in found.items() if f.status_text}
    assert readers, "the scan found no reader of git_status_output"
    short = {key for key in readers if not found[key].decoders}
    assert short == set(STATUS_TEXT_READERS), "\n".join(sorted(short ^ set(STATUS_TEXT_READERS)))


#: Runner names a git call goes through. A call to one whose arguments hold no literal is
#: invisible to the scan above unless something else accounts for it.
_RUNNERS = frozenset({"run_git", "_git", "git", "_git_text", "_run_git_text", "_git_lines"})

#: `<file>::<function>` → why its git call with no literal arguments reads no name unseen.
_SHOW = "record_lint._git_text runs `git show <tree>:<path>` on a path it is given, and prints no name"
DYNAMIC_CALLS: dict[str, str] = {
    "lib/record_lint.py::_check_learnings_budget": _SHOW,
    "lib/record_lint.py::budgets_at": _SHOW,
}


def _own_nodes(function: ast.AST) -> "list[ast.AST]":
    """``function``'s nodes, without those of a function nested in it (judged on its own)."""
    out, stack = [], list(ast.iter_child_nodes(function))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        out.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return out


def test_every_git_call_the_scan_cannot_read_is_accounted_for():
    """The scan reads argument literals. A call whose arguments hold none is a wrapper that
    forwards its caller's arguments (the caller's literals are scanned), or sits in a function
    that builds its arguments as a literal list (scanned), or is listed.

    Its limit: a call that holds one literal but takes a name-printing flag from a variable or
    a module constant (`run_git(p, "diff", NAME_FLAG)`) is not seen; no plugin call does so."""
    unseen: set[str] = set()
    for path in plugin_python_sources():
        rel = path.relative_to(PLUGIN).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        for function in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            forwards = function.args.vararg is not None
            own = _own_nodes(function)
            builds = any(isinstance(n, (ast.List, ast.Tuple)) and _constants(n.elts) for n in own)
            for call in (n for n in own if isinstance(n, ast.Call)):
                if _name(call.func) not in _RUNNERS:
                    continue
                literal = _constants(call.args) or any(isinstance(a, (ast.List, ast.Tuple)) for a in call.args)
                if not literal and not forwards and not builds:
                    unseen.add(f"{rel}::{function.name}")
    assert unseen == set(DYNAMIC_CALLS), "\n".join(sorted(unseen ^ set(DYNAMIC_CALLS)))
