"""Test determinism and dependency scope — the shapes a reviewer should not have to spot.

A test result is worth caching, and worth trusting, only when it depends on what the
test exercises and comes out the same on any machine and any run. Five shapes break
that in ways the source shows without running anything, and this module finds them
in what a change ADDS (the catalogue, its remedies and what a reviewer judges instead:
``docs/test-determinism.md``):

* ``test-scope-conftest`` — a root ``conftest.py`` imports first-party code at module
  level, so every test's dependency closure becomes that code's closure.
* ``test-scope-autouse`` — an autouse fixture in a ``conftest.py`` imports first-party
  code: the same widening, paid by every test beneath that conftest. One declared in a
  test module reaches only that module, so it is not a site.
* ``test-scope-init`` — a first-party package ``__init__.py`` imports every one of its
  submodules, so importing any name from the package imports all of it.
* ``test-clock-fake`` — a shared test helper (a conftest, a fake, a helper module under
  a test tree) reads the real clock or real randomness, by a call or by handing the
  function on (``default_factory=datetime.now``), so every test using it stops repeating.
* ``test-clock-import`` — test code calls the real clock or randomness at import time
  (module level, a decorator argument such as ``parametrize``, a default argument),
  which no fixture can freeze and every test in the process inherits.

**Introduced, not present.** Each site is keyed by what it is — the file, the importer,
the imported module, or the API and the text of the line that reads it — never by line
number, and only a site whose key the base did not carry is reported, at its own line.
A product's existing sites therefore never block an unrelated change; the whole-tree
listing (:func:`scan_tree`) is the janitor's, which advises. A renamed file is compared
with its old path, so a move introduces nothing. A change can also create a site in a
file it did not touch — deleting the conftest above one makes it the root, adding a
project file makes a package first-party, deleting a package's last unimported
submodule makes its ``__init__`` import everything — so every conftest and the
``__init__`` beside a changed module are read too.

**Per file, by language** (``architecture.md`` § Direction: written in Python, never
specific to Python). Rules are populated for Python, classified by pytest's own
conventions. A changed test file in any other language, or any non-data file under a
test tree that is not Python, is reported ``unchecked`` under a name no severity is
assigned to, so it reaches the review as an observation for the reviewer to judge —
never silently passed, and never a warning the product cannot clear. A Python file
that cannot be parsed reports ``unchecked`` against the blocking check, which
record-lint rates one step down. Either way the run was partial, so every check's
count is ``None``, not ``0``.

**Waived on the line.** ``prawduct:allow prawduct/test-scope -- reason`` on the site's
line, or on a comment line directly above it, drops that site (``docs/waivers.md``).
A trailing waiver on the previous statement does not reach the next one. The reason
must say why the site stays on purpose; one without a reason waives nothing.

**Cost is the diff.** One renames diff, one name-and-object listing per side, one
batched blob read per side. Only Python files under a test tree, package
``__init__.py`` files and conftests are parsed.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path, PurePosixPath

from . import evidence, waivers

CONFTEST_CHECK = "test-scope-conftest"
AUTOUSE_CHECK = "test-scope-autouse"
INIT_CHECK = "test-scope-init"
CLOCK_FAKE_CHECK = "test-clock-fake"
CLOCK_IMPORT_CHECK = "test-clock-import"

#: Every check this module emits, in the order record-lint lists them.
CHECKS = (CONFTEST_CHECK, AUTOUSE_CHECK, INIT_CHECK, CLOCK_FAKE_CHECK, CLOCK_IMPORT_CHECK)

#: The name a language with no rules is reported under. Deliberately not a check
#: record-lint rates, so its ``unchecked`` entry is an observation.
UNRULED = "test-scope"

WAIVER_REF = "prawduct/test-scope"

#: APIs that read the real clock or real randomness, by fully qualified name. A seeded
#: ``random.Random(seed)`` is deterministic and is not here; ``random.Random()`` with no
#: argument is handled in :func:`_ambient_site`. ``time.monotonic`` and
#: ``time.perf_counter`` are not here either: they are interval clocks, read for
#: timeouts, polling deadlines and durations, not for a value a result carries, and
#: rating every polling loop a warning would teach products to waive the check.
AMBIENT_CALLS = frozenset({
    "datetime.datetime.now", "datetime.datetime.utcnow", "datetime.datetime.today",
    "datetime.date.today",
    "time.time", "time.time_ns",
    "uuid.uuid1", "uuid.uuid4",
    "os.urandom", "os.getrandom",
    "random.random", "random.randint", "random.randrange", "random.choice",
    "random.choices", "random.shuffle", "random.sample", "random.uniform",
    "random.getrandbits", "random.randbytes", "random.gauss",
    "secrets.token_bytes", "secrets.token_hex", "secrets.token_urlsafe",
    "secrets.choice", "secrets.randbelow", "secrets.randbits",
})

#: pytest's test directories. Python is classified by pytest's conventions only, so a
#: product module named like an RSpec or Jest spec is not mistaken for a test helper.
_PY_TEST_DIRS = frozenset({"tests", "test", "testing"})

#: Every ecosystem's test directories, for the languages without rules.
_TEST_DIRS = _PY_TEST_DIRS | frozenset({"__tests__", "spec", "specs"})

#: File-name stems that mark a test beside its source, by the conventions of the
#: ecosystems that co-locate them: Go and Dart `_test`, Jest/Vitest `.test`/`.spec`,
#: RSpec `_spec`, JVM/Swift/.NET `FooTest`/`FooTests`/`FooSpec`.
_TEST_STEM_SUFFIXES = ("_test", "_spec", ".test", ".spec")
_TEST_STEM_CAMEL_SUFFIXES = ("Test", "Tests", "Spec")

#: Suffixes of files a test tree holds as data rather than code: fixtures, snapshots,
#: goldens, media, configuration. Everything else that is not Python is code in a
#: language without rules, and is reported as such rather than passed.
_DATA_SUFFIXES = frozenset({
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env",
    ".txt", ".md", ".rst", ".csv", ".tsv", ".xml", ".html", ".htm", ".css", ".svg",
    ".snap", ".golden", ".out", ".log", ".lock", ".sql", ".graphql", ".proto",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp", ".tif", ".tiff",
    ".pdf", ".wav", ".mp3", ".mp4", ".ogg", ".flac", ".mov", ".ttf", ".otf",
    ".woff", ".woff2", ".zip", ".gz", ".tgz", ".tar", ".bz2", ".xz", ".7z",
    ".bin", ".dat", ".db", ".sqlite", ".parquet", ".pkl", ".npy", ".npz",
    ".pem", ".crt", ".key", ".pub", ".pyi", ".pyc", ".map", ".gitkeep",
})

#: Top-level names that are never the product's code even when they sit at the root.
_NOT_FIRST_PARTY = frozenset({"conftest", "setup", "noxfile", "tasks", "manage"}) | _TEST_DIRS

_PROJECT_FILES = frozenset({"pyproject.toml", "setup.py", "setup.cfg"})

#: What ``ast.parse`` raises on input it cannot read: a syntax error, a NUL byte, and an
#: expression nested or sized past the parser's limits (generated fixtures do this).
_PARSE_ERRORS = (SyntaxError, ValueError, RecursionError, MemoryError)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _parts(path: str) -> tuple[str, ...]:
    return PurePosixPath(path).parts


def _in_test_dir(parts: "tuple[str, ...]", dirs: frozenset) -> bool:
    """A directory component names a test tree. Case-insensitive: Swift packages and
    .NET solutions spell it `Tests/`, and a .NET test project is `MyApp.Tests/`."""
    for part in parts:
        lowered = part.lower()
        if lowered in dirs or lowered.endswith((".tests", ".test")):
            return True
    return False


def is_test_path(path: str) -> bool:
    """A file belongs to a test tree. Python by pytest's conventions (a test directory,
    ``conftest.py``, ``test_*.py``, ``*_test.py``); any other file by the test-directory
    and test-name conventions of the ecosystems that use them."""
    parts = _parts(path)
    if not parts:
        return False
    name = parts[-1]
    if name.endswith(".py"):
        return (
            _in_test_dir(parts[:-1], _PY_TEST_DIRS)
            or name == "conftest.py"
            or name.startswith("test_")
            or name.endswith("_test.py")
        )
    if _in_test_dir(parts[:-1], _TEST_DIRS):
        return True
    stem = PurePosixPath(name).stem
    # Camel-case only, so `latest.js` and `contest.go` are not tests.
    return stem.lower().endswith(_TEST_STEM_SUFFIXES) or stem.endswith(_TEST_STEM_CAMEL_SUFFIXES)


def _is_test_module(path: str) -> bool:
    """A Python file that holds tests rather than shared helpers. A clock read in one
    test module costs that module; the same read in a helper costs every user of it."""
    name = _parts(path)[-1]
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def _project_roots(listing) -> "list[tuple[str, ...]]":
    """The repo root and every directory that declares a Python project, deepest
    first, so a monorepo's subprojects (``packages/agent/acl/``, ``app/``) are roots in
    their own right. A project inside a test tree is a fixture, not the product."""
    roots = {()}
    for path in listing:
        parts = _parts(path)
        if parts and parts[-1] in _PROJECT_FILES and not _in_test_dir(parts[:-1], _TEST_DIRS):
            roots.add(parts[:-1])
    return sorted(roots, key=len, reverse=True)


def _importable(path: str, roots: "list[tuple[str, ...]]") -> "tuple[str, ...] | None":
    """The import path of a file, relative to the deepest project root holding it,
    with a ``src/`` layout's ``src`` dropped; ``None`` outside every root."""
    parts = _parts(path)
    for root in roots:
        if parts[: len(root)] == root and len(parts) > len(root):
            rel = parts[len(root):]
            return rel[1:] if rel[0] == "src" and len(rel) > 1 else rel
    return None


def _first_party(listing) -> "set[str]":
    """Top-level importable names this repo provides: a package (a directory with an
    ``__init__.py``) or a module directly under a project root or its ``src/``, never
    one inside a test tree."""
    roots = _project_roots(listing)
    names: set[str] = set()
    for path in listing:
        if not path.endswith(".py") or _in_test_dir(_parts(path)[:-1], _TEST_DIRS):
            continue
        rel = _importable(path, roots)
        if rel is None:
            continue
        if len(rel) == 2 and rel[1] == "__init__.py":
            names.add(rel[0])
        elif len(rel) == 1:
            names.add(rel[0][:-3])
    return {n for n in names if n.isidentifier() and n not in _NOT_FIRST_PARTY}


def _is_root_conftest(path: str, listing) -> bool:
    """A conftest with no conftest in any directory above it: the one pytest loads
    for every test beneath it."""
    parts = _parts(path)
    if not parts or parts[-1] != "conftest.py":
        return False
    for depth in range(len(parts) - 1):
        if "/".join((*parts[:depth], "conftest.py")) in listing:
            return False
    return True


def _package_of_init(path: str, first_party: "set[str]", listing) -> "tuple[str, str] | None":
    """``(directory, dotted package name)`` for a first-party package's
    ``__init__.py``, else ``None``."""
    parts = _parts(path)
    if not parts or parts[-1] != "__init__.py" or _in_test_dir(parts[:-1], _TEST_DIRS):
        return None
    rel = _importable(path, _project_roots(listing))
    if not rel or len(rel) < 2 or rel[0] not in first_party:
        return None
    return "/".join(parts[:-1]), ".".join(rel[:-1])


def _siblings(directory: str, listing) -> "set[str]":
    """The submodules directly inside a package directory."""
    prefix = directory + "/"
    names: set[str] = set()
    for path in listing:
        if not path.startswith(prefix):
            continue
        rest = path[len(prefix):].split("/")
        if len(rest) == 1 and rest[0].endswith(".py") and rest[0] != "__init__.py":
            names.add(rest[0][:-3])
        elif len(rest) == 2 and rest[1] == "__init__.py":
            names.add(rest[0])
    return {n for n in names if n.isidentifier()}


# ---------------------------------------------------------------------------
# Python rules
# ---------------------------------------------------------------------------


class _Site:
    __slots__ = ("check", "key", "line", "detail")

    def __init__(self, check: str, key: tuple, line: int, detail: str):
        self.check = check
        self.key = key
        self.line = line
        self.detail = detail


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _module_level_imports(body: "list[ast.stmt]"):
    """Import statements that run when the module is imported: the module body and the
    blocks of any compound statement at module level, but not ``if TYPE_CHECKING:``."""
    for node in body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        elif isinstance(node, ast.If):
            if not _is_type_checking(node.test):
                yield from _module_level_imports(node.body)
            yield from _module_level_imports(node.orelse)
        elif isinstance(node, ast.Match):
            for case in node.cases:
                yield from _module_level_imports(case.body)
        else:
            for block in ("body", "orelse", "finalbody"):
                yield from _module_level_imports(getattr(node, block, None) or [])
            for handler in getattr(node, "handlers", None) or []:
                yield from _module_level_imports(handler.body)


def _imported_modules(node: "ast.Import | ast.ImportFrom") -> list[str]:
    """Absolute module names an import statement loads; relative imports (test-local
    by construction) are not returned."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if node.level or not node.module:
        return []
    return [node.module]


def _aliases(tree: ast.Module) -> "dict[str, str]":
    """Local name → fully qualified name, for every import anywhere in the module."""
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    names[alias.asname] = alias.name
                else:
                    top = alias.name.split(".")[0]
                    names[top] = top
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                names[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return names


def _dotted(expr: ast.expr) -> "str | None":
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        base = _dotted(expr.value)
        return f"{base}.{expr.attr}" if base else None
    return None


_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


class _Scopes:
    """Parent links and qualified names over one module, so any node can answer
    "does this run at import?" and "which function is it in?"."""

    def __init__(self, tree: ast.Module):
        self.parent: dict = {}
        self.qualname: dict = {}
        self._visit(tree, "")

    def _visit(self, node, prefix):
        for child in ast.iter_child_nodes(node):
            self.parent[child] = node
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{child.name}"
                self.qualname[child] = name
                self._visit(child, f"{name}.")
            elif isinstance(child, ast.Lambda):
                name = f"{prefix}<lambda>"
                self.qualname[child] = name
                self._visit(child, f"{name}.")
            else:
                self._visit(child, prefix)

    def enclosing_function(self, node) -> "ast.AST | None":
        """The innermost function or lambda whose BODY holds ``node`` — what runs it
        later rather than at import. Decorators, defaults and annotations are not in
        a body: they run when the ``def`` itself runs."""
        child, current = node, self.parent.get(node)
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child in current.body:
                    return current
            elif isinstance(current, ast.Lambda) and child is current.body:
                return current
            child, current = current, self.parent.get(current)
        return None


def _ambient_site(node, scopes: _Scopes, aliases: "dict[str, str]") -> "tuple[str, bool] | None":
    """``(api, is_call)`` when ``node`` is the outermost name of a reference to an
    ambient API (``time.time``, an aliased ``now``), else ``None``."""
    if not isinstance(node, (ast.Name, ast.Attribute)):
        return None
    parent = scopes.parent.get(node)
    if isinstance(parent, ast.Attribute) and parent.value is node:
        return None  # an inner link of a longer chain; the chain's end is judged
    dotted = _dotted(node)
    if not dotted:
        return None
    head, _, rest = dotted.partition(".")
    resolved = aliases.get(head)
    if resolved is None:
        return None
    qualified = f"{resolved}.{rest}" if rest else resolved
    is_call = isinstance(parent, ast.Call) and parent.func is node
    if qualified in AMBIENT_CALLS:
        return qualified, is_call
    if qualified == "random.Random" and is_call and not parent.args and not parent.keywords:
        return "random.Random()", True
    return None


def _is_autouse_fixture(fn) -> bool:
    for deco in fn.decorator_list:
        if not isinstance(deco, ast.Call):
            continue
        name = _dotted(deco.func) or ""
        if not (name == "fixture" or name.endswith(".fixture")):
            continue
        for kw in deco.keywords:
            if kw.arg == "autouse" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
    return False


def python_sites(path: str, source: str, listing, first_party: "set[str]") -> "list[_Site]":
    """Every site of every rule in one Python file. Raises one of ``_PARSE_ERRORS``
    when the file cannot be parsed."""
    tree = ast.parse(source, filename=path)
    lines = source.splitlines()
    sites: list[_Site] = []

    def first_party_of(module: str) -> "str | None":
        top = module.split(".")[0]
        return top if top in first_party else None

    def text_at(lineno: int) -> str:
        return lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""

    in_test_tree = is_test_path(path)
    is_conftest = _parts(path)[-1] == "conftest.py"

    if in_test_tree and _is_root_conftest(path, listing):
        for node in _module_level_imports(tree.body):
            for module in _imported_modules(node):
                if first_party_of(module):
                    sites.append(_Site(
                        CONFTEST_CHECK, (path, module), node.lineno,
                        f"the root conftest imports `{module}` at module level, so every "
                        "test under it depends on that module and everything it imports; "
                        "import it inside the fixtures that need it",
                    ))

    scopes = _Scopes(tree)

    if in_test_tree and is_conftest:
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or not _is_autouse_fixture(fn):
                continue
            qualname = scopes.qualname.get(fn, fn.name)
            for node in ast.walk(fn):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for module in _imported_modules(node):
                        if first_party_of(module):
                            sites.append(_Site(
                                AUTOUSE_CHECK, (path, qualname, module), node.lineno,
                                f"autouse fixture `{qualname}` imports `{module}`, so every "
                                "test beneath this conftest depends on that module; make "
                                "the fixture opt-in, or import lazily where a test needs it",
                            ))

    package = _package_of_init(path, first_party, listing)
    if package is not None:
        directory, dotted = package
        siblings = _siblings(directory, listing)
        if len(siblings) >= 3:
            imported: set[str] = set()
            first_line = None
            for node in _module_level_imports(tree.body):
                names: set[str] = set()
                if isinstance(node, ast.ImportFrom) and node.level == 1:
                    if node.module:
                        names.add(node.module.split(".")[0])
                    else:
                        names.update(a.name for a in node.names)
                else:
                    for module in _imported_modules(node):
                        if module.startswith(dotted + "."):
                            names.add(module[len(dotted) + 1:].split(".")[0])
                    if isinstance(node, ast.ImportFrom) and node.module == dotted:
                        names.update(a.name for a in node.names)
                hit = names & siblings
                if hit and first_line is None:
                    first_line = node.lineno
                imported |= hit
            if siblings <= imported:
                sites.append(_Site(
                    INIT_CHECK, (path,), first_line or 1,
                    f"`{path}` imports every one of its {len(siblings)} submodules, so "
                    "importing any name from the package imports all of it; import "
                    "submodules where they are used, or load them lazily",
                ))

    if in_test_tree:
        aliases = _aliases(tree)
        helper = not _is_test_module(path)
        for node in ast.walk(tree):
            found = _ambient_site(node, scopes, aliases)
            if found is None:
                continue
            api, is_call = found
            fn = scopes.enclosing_function(node)
            if fn is None and is_call:
                sites.append(_Site(
                    CLOCK_IMPORT_CHECK, (path, api, text_at(node.lineno)), node.lineno,
                    f"`{api}` runs when the module is imported, so no fixture can freeze "
                    "it and every test in the process inherits the value; move it into a "
                    "fixture or the test body, behind an injected clock or seeded generator",
                ))
            elif helper:
                where = scopes.qualname.get(fn, "<module>") if fn is not None else "<module>"
                sites.append(_Site(
                    CLOCK_FAKE_CHECK, (path, where, api, text_at(node.lineno)), node.lineno,
                    f"shared test helper `{where}` reads `{api}`, so every test using it "
                    "stops repeating; take the clock or generator as a parameter, or "
                    "freeze it",
                ))
    return sites


# ---------------------------------------------------------------------------
# Git — every call takes NUL-separated output, so no path is ever C-quoted
# ---------------------------------------------------------------------------


def _listing(project_dir: Path, tree: str) -> "dict[str, str] | None":
    """Path → blob id for every file in ``tree``."""
    rc, out, _err = evidence.run_git(
        project_dir, "ls-tree", "-r", "-z", "--full-tree", tree, strip=False,
    )
    if rc != 0:
        return None
    listing: dict[str, str] = {}
    for entry in out.split("\0"):
        meta, sep, path = entry.partition("\t")
        fields = meta.split()
        if sep and len(fields) == 3 and fields[1] == "blob":
            listing[path] = fields[2]
    return listing


def _blobs(project_dir: Path, listing: "dict[str, str]", paths: "list[str]") -> "dict[str, str] | None":
    """Each path's content, read by blob id in one batched call; a path absent from
    ``listing`` is absent from the result."""
    wanted = [(p, listing[p]) for p in paths if p in listing]
    if not wanted:
        return {}
    request = "".join(f"{sha}\n" for _p, sha in wanted)
    rc, out, _err = evidence.run_git(
        project_dir, "cat-file", "--batch", input=request, strip=False,
    )
    if rc != 0:
        return None
    # `cat-file` sizes count bytes. run_git decodes with surrogateescape, so encoding
    # the same way recovers the exact bytes, and the walk below is over those.
    data = out.encode("utf-8", "surrogateescape")
    result: dict[str, str] = {}
    pos = 0
    for path, _sha in wanted:
        end = data.find(b"\n", pos)
        if end < 0:
            return None
        fields = data[pos:end].split()
        pos = end + 1
        if len(fields) != 3 or not fields[2].isdigit():
            return None
        size = int(fields[2])
        if pos + size > len(data):
            return None
        result[path] = data[pos:pos + size].decode("utf-8", "surrogateescape")
        pos += size + 1
    return result


def _renames(project_dir: Path, base_tree: str, head_tree: str) -> "dict[str, str] | None":
    """New path → old path for every rename between the trees."""
    rc, out, _err = evidence.run_git(
        project_dir, "diff", "-z", "--name-status", "-M", "--no-color",
        base_tree, head_tree, strip=False,
    )
    if rc != 0:
        return None
    tokens = out.split("\0")
    renames: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        status = tokens[i]
        if status.startswith(("R", "C")) and i + 2 < len(tokens):
            if status.startswith("R"):
                renames[tokens[i + 2]] = tokens[i + 1]
            i += 3
        else:
            i += 2
    return renames


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def _subject(path: str) -> str:
    """Which rule family a path is a candidate for: ``python``, ``other`` (code under a
    test tree in a language without rules) or ``""``."""
    if path.endswith(".py"):
        if is_test_path(path) or _parts(path)[-1] == "__init__.py":
            return "python"
        return ""
    suffix = PurePosixPath(path).suffix.lower()
    if is_test_path(path) and suffix and suffix not in _DATA_SUFFIXES:
        return "other"
    return ""


def _affected(paths: "list[str]", listing) -> "set[str]":
    """Files whose verdict a change can alter without editing them: every conftest
    (a deleted or added conftest moves which one is the root, and a project file moves
    what is first-party) and the ``__init__`` beside each changed module."""
    extra = {p for p in listing if _parts(p)[-1] == "conftest.py"}
    for path in paths:
        if path.endswith(".py"):
            parent = PurePosixPath(path).parent
            init = "__init__.py" if str(parent) == "." else f"{parent}/__init__.py"
            if init in listing:
                extra.add(init)
    return extra


#: Every finding ends with the way out for a site that must stay, so the remedy and the
#: exception arrive together (``docs/test-determinism.md`` has each shape's fix).
_WAIVER_REMEDY = (
    f"; if it must stay, waive it on its line with `prawduct:allow {WAIVER_REF} -- <why it "
    "cannot move>` (prawduct's docs/test-determinism.md)"
)


def _finding(site: _Site, path: str) -> dict:
    return {
        "check": site.check, "path": path, "line": site.line,
        "detail": site.detail + _WAIVER_REMEDY,
    }


def _waived(lines: "list[str]", lineno: int) -> bool:
    """The site's own line carries the waiver, or a comment-only line directly above
    it does. A trailing waiver on the previous statement is that statement's."""
    i = lineno - 1
    if 0 <= i < len(lines) and waivers.line_waives(lines[i], WAIVER_REF):
        return True
    return 0 < i <= len(lines) and lines[i - 1].lstrip().startswith("#") and waivers.line_waives(
        lines[i - 1], WAIVER_REF
    )


def _unwaived(sites: "list[_Site]", source: str) -> "list[_Site]":
    lines = source.splitlines()
    return [s for s in sites if not _waived(lines, s.line)]


def check(
    project_dir: Path, paths: "list[str] | None", base_tree: str, head_tree: str
) -> "tuple[list[dict], list[str], set[str]]":
    """Sites a change introduces, as ``(findings, unchecked, no_answer)`` — the shape
    record-lint's other arms return."""
    changed = list(paths or [])
    # A product module or project file can change a verdict elsewhere (`_affected`), so
    # only a change touching neither Python nor a project file reads nothing.
    if not any(
        _subject(p) or p.endswith(".py") or PurePosixPath(p).name in _PROJECT_FILES
        for p in changed
    ):
        return [], [], set()
    head_listing = _listing(project_dir, head_tree)
    base_listing = _listing(project_dir, base_tree)
    renames = _renames(project_dir, base_tree, head_tree)
    if head_listing is None or base_listing is None or renames is None:
        return [], [
            f"{CONFTEST_CHECK} unchecked — the trees could not be listed, so no "
            "test-scope or test-clock check ran on this change"
        ], set(CHECKS)

    candidates = {p for p in changed if _subject(p)} | _affected(changed, head_listing)
    python = sorted(p for p in candidates if _subject(p) == "python" and p in head_listing)
    other = sorted(p for p in candidates if _subject(p) == "other" and p in head_listing)
    old_path = {p: renames.get(p, p) for p in python}
    head_src = _blobs(project_dir, head_listing, python)
    base_src = _blobs(project_dir, base_listing, sorted(set(old_path.values())))
    if head_src is None or base_src is None:
        return [], [
            f"{CONFTEST_CHECK} unchecked — file contents could not be read, so no "
            "test-scope or test-clock check ran on this change"
        ], set(CHECKS)

    head_fp = _first_party(head_listing)
    base_fp = _first_party(base_listing)
    findings: list[dict] = []
    unchecked: list[str] = []
    unparsed: list[str] = []
    for path in python:
        source = head_src.get(path)
        if source is None:
            continue
        try:
            head_sites = _unwaived(python_sites(path, source, head_listing, head_fp), source)
        except _PARSE_ERRORS:
            unparsed.append(path)
            continue
        # Waived sites leave BOTH sides before matching, so an old waived read never
        # stands in for a new unwaived one with the same key.
        base_keys: Counter = Counter()
        old = old_path[path]
        if old in base_src:
            try:
                for site in _unwaived(
                    python_sites(old, base_src[old], base_listing, base_fp), base_src[old]
                ):
                    base_keys[(site.check, (path, *site.key[1:]))] += 1
            except _PARSE_ERRORS:
                pass  # an unparseable base has no sites to subtract: every head site is new
        for site in head_sites:
            ident = (site.check, site.key)
            if base_keys[ident] > 0:
                base_keys[ident] -= 1
                continue
            findings.append(_finding(site, path))
    if unparsed:
        unchecked.append(
            f"{CONFTEST_CHECK} unchecked on {', '.join(unparsed)} — the file does not "
            "parse as Python, so its test-scope and test-clock checks did not run"
        )
    if other:
        unchecked.append(
            f"{UNRULED} unchecked on {', '.join(other)} — no determinism or "
            "dependency-scope rules exist for this language yet; the reviewer judges "
            "these files against prawduct's docs/test-determinism.md"
        )
    # A partial run answers nothing as a count (record-lint's `_count`: no_answer wins).
    return findings, unchecked, set(CHECKS) if (unparsed or other) else set()


#: hypothesis's own ways of moving its example database: the storage environment
#: variable, an explicit database object, or a settings call or profile that sets
#: `database=`. A bare `database=` elsewhere (a Django or SQLAlchemy setting) is not one.
_HYPOTHESIS_REDIRECT_RE = re.compile(
    r"HYPOTHESIS_STORAGE_DIRECTORY|ExampleDatabase|(?:settings|register_profile)\s*\([^)]*\bdatabase\s*=",
    re.S,
)
_CONFIG_FILES = frozenset({"pyproject.toml", "setup.cfg", "pytest.ini", "tox.ini"})


def _uses_hypothesis(source: str) -> bool:
    return any(
        line.lstrip().startswith(("import hypothesis", "from hypothesis"))
        for line in source.splitlines()
    )


def _tool_state(sources: "dict[str, str]", config: "dict[str, str]") -> "list[dict]":
    """Tool state that changes test outcomes and lives in the checkout. Today one
    shape: hypothesis keeps the failing examples it found in ``.hypothesis/`` under
    the working directory and replays them first, so a result depends on what earlier
    runs on that machine found, unless the project points the database elsewhere."""
    users = sorted(p for p, src in sources.items() if is_test_path(p) and _uses_hypothesis(src))
    if not users:
        return []
    texts = list(config.values()) + [
        src for p, src in sources.items() if _parts(p)[-1] == "conftest.py"
    ]
    if any(_HYPOTHESIS_REDIRECT_RE.search(text) for text in texts):
        return []
    return [{
        "path": users[0],
        "detail": (
            f"hypothesis is used ({len(users)} test file(s)) and its example database is "
            "left in the checkout, so a run replays whatever earlier runs on this machine "
            "found; point it outside the checkout (a settings profile's `database=`, or "
            "HYPOTHESIS_STORAGE_DIRECTORY)"
        ),
    }]


def scan_tree(project_dir: Path, tree: str = "HEAD") -> "dict | None":
    """Every site in a tree, unwaived, largest blast radius first — the janitor's view
    of what already exists. ``None`` when the tree cannot be read.

    Returns ``{"sites": [{check, path, line, detail}], "tool_state": [{path, detail}],
    "scanned": N, "unparsed": [...], "unruled": [...]}``; ``scanned`` is the number of
    files the rules read, so an empty ``sites`` is visibly a scan of something."""
    listing = _listing(project_dir, tree)
    if listing is None:
        return None
    python = sorted(p for p in listing if _subject(p) == "python")
    unruled = sorted(p for p in listing if _subject(p) == "other")
    roots = _project_roots(listing)
    config_paths = sorted(
        p for p in listing
        if _parts(p)[-1] in _CONFIG_FILES and _parts(p)[:-1] in roots
    )
    sources = _blobs(project_dir, listing, python)
    config = _blobs(project_dir, listing, config_paths)
    if sources is None or config is None:
        return None
    first_party = _first_party(listing)
    rank = {c: n for n, c in enumerate(CHECKS)}
    sites: list[dict] = []
    unparsed: list[str] = []
    for path in python:
        source = sources.get(path)
        if source is None:
            continue
        try:
            found = python_sites(path, source, listing, first_party)
        except _PARSE_ERRORS:
            unparsed.append(path)
            continue
        sites.extend(_finding(site, path) for site in _unwaived(found, source))
    sites.sort(key=lambda s: (rank[s["check"]], s["path"], s["line"]))
    return {
        "sites": sites,
        "tool_state": _tool_state(sources, config),
        "scanned": len(python),
        "unparsed": unparsed,
        "unruled": unruled,
    }


def scan_cmd(project_dir: Path, argv: "list[str]") -> int:
    """``prawduct-hook determinism-scan [--json]`` — the existing sites in HEAD, for
    ``/prawduct:janitor``'s Test Fitness theme to relay. Read-only, and advice: exit 0
    whenever the scan ran, whatever it found; 3 when the tree could not be read."""
    import json  # noqa: PLC0415 — only this entry point prints JSON

    as_json = "--json" in argv  # the hook's wrapper refuses any other token
    result = scan_tree(project_dir)
    if result is None:
        if as_json:
            print(json.dumps({"status": "unchecked", "reason": "HEAD could not be read"}))
        else:
            print("determinism-scan: unchecked — HEAD could not be read, so nothing was scanned")
        return 3
    if as_json:
        print(json.dumps({"status": "scanned", **result}, indent=2))
        return 0
    sites, tool_state = result["sites"], result["tool_state"]
    print(
        f"determinism-scan: {len(sites)} site(s) and {len(tool_state)} tool-state finding(s) "
        f"over {result['scanned']} Python file(s) at HEAD"
    )
    for site in sites:
        print(f"  {site['check']}  {site['path']}:{site['line']} — {site['detail']}")
    for item in tool_state:
        print(f"  tool-state  {item['path']} — {item['detail']}")
    if result["unparsed"]:
        print(f"  not read (does not parse): {', '.join(result['unparsed'])}")
    if result["unruled"]:
        print(
            f"  not read (no rules for the language yet): {len(result['unruled'])} test "
            "file(s); judge them against prawduct's docs/test-determinism.md"
        )
    return 0
