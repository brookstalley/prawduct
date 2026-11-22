"""The plugin never fails on a byte that is not UTF-8, at either end (#1188).

git hands back file content, commit messages and pathnames as raw bytes, and a
consuming repo can hold any of them in a legacy encoding: vendored C headers in
Windows-1251, a latin-1 doc. Two rules keep one such byte from failing a gate.

**Decoding.** A subprocess call that decodes its output names
``encoding="utf-8"`` and a non-strict ``errors``. ``text=True`` alone decodes
with the locale's codec and ``errors="strict"``, so one byte anywhere in a diff
made the whole diff "could not be read" and ``check-pr-hygiene`` checked no
other file for credentials. ``surrogateescape`` is the default, because a
pathname then round-trips back into a git argument byte for byte; ``replace``
and ``backslashreplace`` are for output that is only ever displayed.

**Encoding.** ``surrogateescape`` turns the byte into a lone surrogate, which a
strict encoder raises on, so the failure would only move from the read to the
first write. Every text write and every ``.encode()`` therefore names a
non-strict ``errors`` too. Files are written with ``backslashreplace`` (through
``core.atomic_write_text``'s default, or spelled out), so they stay valid UTF-8
for their strict readers; a file that mirrors git's bytes exactly, and a hash
input, use ``surrogateescape``. Content that cannot hold a surrogate is outside
the rule: a string literal, and ``json.dumps`` at its default ``ensure_ascii``,
which escapes one as ``\\udce9``.

**Scope.** Only what the call spells out can be read. A spawning call that
passes a ``**`` splat, and an ``open`` whose mode is not a literal, are reported
as unreadable rather than skipped, so hoisting an argument into a variable
cannot quietly take a call out of the check.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = REPO_ROOT / "plugin"

#: The subprocess entry points that can decode output.
_SPAWNERS = {"run", "Popen", "check_output", "call", "check_call"}
_DECODING_KEYWORDS = {"text", "universal_newlines", "encoding", "errors"}
_TOLERANT_ERRORS = {"surrogateescape", "replace", "backslashreplace"}


def _sources() -> list[Path]:
    """Every Python file the plugin ships, the extensionless binaries included."""
    found = sorted(PLUGIN.rglob("*.py"))
    for path in sorted((PLUGIN / "bin").iterdir()):
        if path.is_file() and path.suffix == "" and path.read_text(encoding="utf-8").startswith("#!"):
            found.append(path)
    return found


def _literal(node: ast.expr) -> object:
    return node.value if isinstance(node, ast.Constant) else ast.unparse(node)


def _callee(node: ast.Call) -> str | None:
    func = node.func
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)


def _keywords(node: ast.Call) -> dict[str, ast.expr]:
    return {kw.arg: kw.value for kw in node.keywords if kw.arg}


def _surrogate_free(node: ast.expr) -> bool:
    """Whether this expression's value can be seen, statically, to hold no lone
    surrogate: a literal, a ``json.dumps`` at default ``ensure_ascii``, or a
    concatenation of those."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _surrogate_free(node.left) and _surrogate_free(node.right)
    if isinstance(node, ast.Call) and ast.unparse(node.func) == "json.dumps":
        ascii_kw = _keywords(node).get("ensure_ascii")
        return ascii_kw is None or (isinstance(ascii_kw, ast.Constant) and ascii_kw.value is True)
    return False


def _codec_problems(where: str, encoding: ast.expr | None, errors: ast.expr | None, act: str) -> list[str]:
    problems = []
    enc = _literal(encoding) if encoding is not None else None
    err = _literal(errors) if errors is not None else None
    if enc != "utf-8":
        problems.append(f"{where}: {act} with encoding={enc!r}, not 'utf-8'")
    if err not in _TOLERANT_ERRORS:
        problems.append(f"{where}: {act} with errors={err!r}, which raises on a byte that is not UTF-8")
    return problems


def decoding_violations(source: str, name: str) -> tuple[list[str], int]:
    """``(problems, decoding calls inspected)`` for subprocess output."""
    problems: list[str] = []
    inspected = 0
    for node in ast.walk(ast.parse(source, filename=name)):
        if not isinstance(node, ast.Call) or _callee(node) not in _SPAWNERS:
            continue
        where = f"{name}:{node.lineno}"
        if any(kw.arg is None for kw in node.keywords):
            problems.append(f"{where}: keywords passed by ** splat cannot be read")
            continue
        kws = _keywords(node)
        if not _DECODING_KEYWORDS & kws.keys():
            continue
        inspected += 1
        problems += _codec_problems(where, kws.get("encoding"), kws.get("errors"), "decodes")
    return problems, inspected


def _text_mode(node: ast.Call, mode_index: int) -> str | None:
    """The literal mode of an ``open``-like call, ``"?"`` when not a literal."""
    kws = _keywords(node)
    mode = kws.get("mode")
    if mode is None and len(node.args) > mode_index:
        mode = node.args[mode_index]
    if mode is None:
        return "r"
    return mode.value if isinstance(mode, ast.Constant) and isinstance(mode.value, str) else "?"


#: Calls the encoding check reads as an open with an unreadable mode but which
#: open no file, each as ``(file, the call's source)`` with why. Each entry must
#: still match a call, so a moved or renamed one fails instead of going stale.
NOT_FILE_OPENS = {
    ("plugin/lib/aggregate.py", "opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)"):
        "a urllib opener sending an HTTP request",
    ("plugin/lib/contribution.py", "opener.open(request, timeout=SEND_TIMEOUT_SECONDS)"):
        "a urllib opener sending an HTTP request",
}

#: The shared writer's own ``open`` passes its parameters through; what reaches
#: them is checked at every call of it instead.
_OWNER = "atomic_write_text"


def encoding_violations(source: str, name: str) -> tuple[list[str], int]:
    """``(problems, encoding sites inspected)`` for text writes and ``.encode()``."""
    problems: list[str] = []
    inspected = 0
    tree = ast.parse(source, filename=name)
    owner_calls = {
        id(inner)
        for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef) and fn.name == _OWNER
        for inner in ast.walk(fn)
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or id(node) in owner_calls:
            continue
        if (name, ast.unparse(node)) in NOT_FILE_OPENS:
            continue
        callee = _callee(node)
        where = f"{name}:{node.lineno}"
        kws = _keywords(node)
        if callee == "write_text":
            if node.args and _surrogate_free(node.args[0]):
                continue
            inspected += 1
            problems += _codec_problems(where, kws.get("encoding"), kws.get("errors"), "writes")
        elif callee in ("open", "fdopen"):
            # Builtin `open(path, mode)` and `os.fdopen(fd, mode)` take the
            # mode second; `Path.open(mode)` takes it first.
            is_method_open = callee == "open" and isinstance(node.func, ast.Attribute) and ast.unparse(node.func) != "os.open"
            if ast.unparse(node.func) == "os.open":
                continue
            mode = _text_mode(node, 0 if is_method_open else 1)
            if mode == "?":
                problems.append(f"{where}: an open whose mode is not a literal cannot be read")
                continue
            if "b" in mode or not set(mode) & set("wax+"):
                continue
            inspected += 1
            problems += _codec_problems(where, kws.get("encoding"), kws.get("errors"), "writes")
        elif callee == "atomic_write_text":
            inspected += 1
            if "errors" in kws and _literal(kws["errors"]) not in _TOLERANT_ERRORS:
                problems.append(f"{where}: writes with errors={_literal(kws['errors'])!r}")
        elif callee == "encode" and isinstance(node.func, ast.Attribute):
            if _surrogate_free(node.func.value):
                continue
            inspected += 1
            encoding = kws.get("encoding") or (node.args[0] if node.args else None)
            errors = kws.get("errors") or (node.args[1] if len(node.args) > 1 else None)
            if encoding is None:
                encoding = ast.Constant("utf-8")  # str.encode's default
            problems += _codec_problems(where, encoding, errors, "encodes")
    return problems, inspected


def _sweep(check) -> tuple[list[str], int]:
    problems: list[str] = []
    inspected = 0
    for path in _sources():
        found, count = check(path.read_text(encoding="utf-8"), str(path.relative_to(REPO_ROOT)))
        problems += found
        inspected += count
    return problems, inspected


def test_every_plugin_subprocess_decodes_tolerantly():
    problems, inspected = _sweep(decoding_violations)
    assert problems == [], "\n".join(problems)
    assert inspected > 0


def test_every_plugin_text_write_and_encode_is_tolerant():
    problems, inspected = _sweep(encoding_violations)
    assert problems == [], "\n".join(problems)
    assert inspected > 0


def test_each_not_a_file_open_still_names_a_call():
    for (rel, call), why in NOT_FILE_OPENS.items():
        tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))
        assert any(
            isinstance(n, ast.Call) and ast.unparse(n) == call for n in ast.walk(tree)
        ), f"{rel}: no call `{call}` any more ({why}); drop or update the entry"


def test_the_shared_git_runners_are_in_the_inspected_set():
    """The subject was reached: the two shared git runners are decoding calls
    the sweep must see."""
    for rel, function, check in (
        ("lib/evidence.py", "run_git", decoding_violations),
        ("lib/gitstate.py", "_run_git_text", decoding_violations),
    ):
        tree = ast.parse((PLUGIN / rel).read_text(encoding="utf-8"))
        body = next(
            n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function
        )
        problems, inspected = check(ast.unparse(body), f"{rel}:{function}")
        assert inspected == 1 and problems == [], (rel, function, problems)


def test_the_decoding_check_catches_each_strict_shape():
    """Positive controls: each shape that raises on a non-UTF-8 byte is named,
    and the tolerant forms pass."""
    strict = {
        "subprocess.run(a, text=True)": "encoding=None",
        "subprocess.run(a, universal_newlines=True)": "encoding=None",
        "subprocess.run(a, encoding='utf-8')": "errors=None",
        "subprocess.run(a, encoding='utf-8', errors='strict')": "errors='strict'",
        "subprocess.run(a, text=True, errors='replace')": "encoding=None",
        "subprocess.check_output(a, encoding='latin-1', errors='replace')": "encoding='latin-1'",
        "_sp.Popen(a, text=True)": "encoding=None",
        "subprocess.run(a, encoding=ENC, errors='replace')": "encoding='ENC'",
        "subprocess.run(a, **TEXT)": "splat",
    }
    for source, expected in strict.items():
        problems, _ = decoding_violations(source, "x.py")
        assert problems and expected in problems[0], (source, problems)
    tolerant = (
        "subprocess.run(a, encoding='utf-8', errors='surrogateescape')",
        "subprocess.run(a, text=True, encoding='utf-8', errors='replace')",
        "subprocess.run(a, capture_output=True)",
        "subprocess.Popen(a, stdout=subprocess.DEVNULL)",
        "json.loads(s)",
    )
    for source in tolerant:
        assert decoding_violations(source, "x.py")[0] == [], source


def test_the_encoding_check_catches_each_strict_shape():
    strict = {
        "p.write_text(text)": "encoding=None",
        "p.write_text(text, encoding='utf-8')": "errors=None",
        "p.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')": "errors=None",
        "open(p, 'w', encoding='utf-8')": "errors=None",
        "open(p, mode='a', encoding='utf-8', errors='strict')": "errors='strict'",
        "p.open('w', encoding='utf-8')": "errors=None",
        "os.fdopen(fd, 'w')": "encoding=None",
        "open(p, m)": "not a literal",
        "atomic_write_text(p, t, errors='strict')": "errors='strict'",
        "name.encode()": "errors=None",
        "text.encode('utf-8')": "errors=None",
        "text.encode(encoding='utf-8', errors='strict')": "errors='strict'",
    }
    for source, expected in strict.items():
        problems, _ = encoding_violations(source, "x.py")
        assert problems and expected in problems[0], (source, problems)
    tolerant = (
        "p.write_text(text, encoding='utf-8', errors='backslashreplace')",
        "p.write_text(json.dumps(d, indent=2) + '\\n')",
        "p.write_text('')",
        "open(p, encoding='utf-8')",
        "open(p, 'rb')",
        "p.open('wb')",
        "os.open(p, os.O_WRONLY)",
        "open(p, 'a', encoding='utf-8', errors='surrogateescape')",
        "atomic_write_text(p, t)",
        "text.encode('utf-8', 'surrogateescape')",
        "json.dumps(d).encode('utf-8')",
        "'literal'.encode()",
    )
    for source in tolerant:
        assert encoding_violations(source, "x.py")[0] == [], source
