"""Test determinism and dependency scope — the shapes a reviewer should not have to spot.

A test result is worth caching, and worth trusting, only when it depends on what the
test exercises and comes out the same on any machine and any run. Five shapes break
that in ways the source shows without running anything, and this module finds them
in what a change ADDS (the catalogue, its remedies and the shapes only a reviewer can
judge: ``docs/test-determinism.md``):

* ``test-scope-conftest`` — a root ``conftest.py`` imports first-party code at module
  level, so every test's dependency closure becomes that code's closure.
* ``test-scope-autouse`` — an autouse fixture imports first-party code: the same
  widening, paid by every test the fixture reaches.
* ``test-scope-init`` — a first-party package ``__init__.py`` imports every one of its
  submodules, so importing any name from the package imports all of it.
* ``test-clock-fake`` — a shared test helper (a conftest, a fake, a helper module
  under a test tree) reads the real clock or real randomness, so every test that
  uses it stops repeating.
* ``test-clock-import`` — test code reads the real clock or randomness at import time
  (module level, a decorator argument such as ``parametrize``, a default argument),
  which no fixture can freeze and every test in the process inherits.

**Introduced, not present.** Each site is keyed by what it is (file, importer, imported
module, API), not by line, and only a site whose key the base did not carry is
reported. A product's existing sites therefore never block an unrelated change; the
whole-tree listing (:func:`scan_tree`) is the doctor's and the janitor's, which advise.
A renamed file is compared with its old path, so a move introduces nothing.

**Per file, by language** (``architecture.md`` § Direction: written in Python, never
specific to Python). Rules are populated for Python. A changed test file in any other
language is reported ``unchecked`` under a name no severity is assigned to, so it
reaches the review as an observation for the reviewer to judge — never silently
passed, and never a warning the product cannot clear. A Python file that cannot be
parsed reports ``unchecked`` against the blocking check, which record-lint rates one
step down.

**Waived on the line.** ``prawduct:allow prawduct/test-scope -- reason`` on the site's
line or the line above it drops that site (``docs/waivers.md``). The reason must say
why the site stays on purpose; one without a reason waives nothing.

**Cost is the diff.** One ``git diff`` for the changed paths and renames, one tree
listing per side, one batched blob read per side. Only Python files under a test tree
and package ``__init__.py`` files are parsed.
"""

from __future__ import annotations

import ast
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

#: Calls that read the real clock or real randomness, by fully qualified name. A seeded
#: ``random.Random(seed)`` is deterministic and is not here; ``random.Random()`` with no
#: argument is handled in :func:`_is_ambient_call`.
AMBIENT_CALLS = frozenset({
    "datetime.datetime.now", "datetime.datetime.utcnow", "datetime.datetime.today",
    "datetime.date.today",
    "time.time", "time.time_ns", "time.monotonic", "time.monotonic_ns",
    "uuid.uuid1", "uuid.uuid4",
    "os.urandom", "os.getrandom",
    "random.random", "random.randint", "random.randrange", "random.choice",
    "random.choices", "random.shuffle", "random.sample", "random.uniform",
    "random.getrandbits", "random.randbytes", "random.gauss",
    "secrets.token_bytes", "secrets.token_hex", "secrets.token_urlsafe",
    "secrets.choice", "secrets.randbelow", "secrets.randbits",
})

_TEST_DIRS = frozenset({"tests", "test", "testing", "__tests__", "spec", "specs"})

#: Source suffixes that name a language this module has no rules for yet. A changed
#: file with one of these under a test tree is reported ``unchecked``.
_OTHER_LANGUAGE_SUFFIXES = frozenset({
    ".swift", ".kt", ".java", ".go", ".rs", ".ts", ".tsx", ".js", ".jsx", ".mjs",
    ".cjs", ".rb", ".cs", ".fs", ".cpp", ".cc", ".c", ".m", ".mm", ".scala", ".ex",
    ".exs", ".php", ".dart", ".lua",
})

#: Top-level names that are never the product's code even when they sit at the root.
_NOT_FIRST_PARTY = frozenset({"conftest", "setup", "noxfile", "tasks", "manage"}) | _TEST_DIRS


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _parts(path: str) -> tuple[str, ...]:
    return PurePosixPath(path).parts


#: File-name stems that mark a test beside its source, by the conventions of the
#: ecosystems that co-locate them: Go and Dart `_test`, Jest/Vitest `.test`/`.spec`,
#: RSpec `_spec`, JVM/Swift/.NET `FooTest`/`FooTests`/`FooSpec`.
_TEST_STEM_SUFFIXES = ("_test", "_spec", ".test", ".spec")
_TEST_STEM_CAMEL_SUFFIXES = ("Test", "Tests", "Spec")


def is_test_path(path: str) -> bool:
    """A file belongs to a test tree: a directory named like one above it, or a
    test-shaped file name anywhere."""
    parts = _parts(path)
    if not parts:
        return False
    name = parts[-1]
    # Case-insensitive: Swift packages and .NET solutions spell it `Tests/`, and a
    # .NET test project is a directory named `MyApp.Tests`.
    for part in parts[:-1]:
        lowered = part.lower()
        if lowered in _TEST_DIRS or lowered.endswith((".tests", ".test")):
            return True
    if name == "conftest.py" or (name.startswith("test_") and name.endswith(".py")):
        return True
    stem = PurePosixPath(name).stem
    # Camel-case only, so `latest.js` and `contest.go` are not tests.
    return stem.lower().endswith(_TEST_STEM_SUFFIXES) or stem.endswith(_TEST_STEM_CAMEL_SUFFIXES)


def _is_test_module(path: str) -> bool:
    """A file that holds tests rather than shared helpers. A clock read in one test
    module costs that module; the same read in a helper costs every user of it."""
    name = _parts(path)[-1]
    return (name.startswith("test_") or name.endswith("_test.py")) and name.endswith(".py")


def _first_party(listing: "set[str]") -> "set[str]":
    """Top-level importable names this repo provides: a package (a directory with an
    ``__init__.py``) or a module, at the root or under ``src/``."""
    names: set[str] = set()
    for path in listing:
        parts = _parts(path)
        if parts and parts[0] == "src":
            parts = parts[1:]
        if len(parts) == 2 and parts[1] == "__init__.py":
            names.add(parts[0])
        elif len(parts) == 1 and parts[0].endswith(".py"):
            names.add(parts[0][:-3])
    return {n for n in names if n.isidentifier() and n not in _NOT_FIRST_PARTY}


def _is_root_conftest(path: str, listing: "set[str]") -> bool:
    """A conftest with no conftest in any directory above it: the one pytest loads
    for every test beneath it."""
    parts = _parts(path)
    if not parts or parts[-1] != "conftest.py":
        return False
    for depth in range(len(parts) - 1):
        ancestor = "/".join((*parts[:depth], "conftest.py"))
        if ancestor in listing:
            return False
    return True


def _package_of_init(path: str, first_party: "set[str]") -> "tuple[str, str] | None":
    """``(directory, dotted package name)`` for a first-party package's
    ``__init__.py``, else ``None``."""
    parts = _parts(path)
    if not parts or parts[-1] != "__init__.py":
        return None
    pkg = parts[:-1]
    dotted_parts = pkg[1:] if pkg and pkg[0] == "src" else pkg
    if not dotted_parts or dotted_parts[0] not in first_party:
        return None
    return "/".join(pkg), ".".join(dotted_parts)


def _siblings(directory: str, listing: "set[str]") -> "set[str]":
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
    """Import statements that run when the module is imported: the module body and
    any ``if``/``try``/``with`` at module level, but not ``if TYPE_CHECKING:``."""
    for node in body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node
        elif isinstance(node, ast.If):
            if not _is_type_checking(node.test):
                yield from _module_level_imports(node.body)
            yield from _module_level_imports(node.orelse)
        elif isinstance(node, ast.Try):
            for block in (node.body, node.orelse, node.finalbody):
                yield from _module_level_imports(block)
            for handler in node.handlers:
                yield from _module_level_imports(handler.body)
        elif isinstance(node, ast.With):
            yield from _module_level_imports(node.body)


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


def _ambient_name(call: ast.Call, aliases: "dict[str, str]") -> "str | None":
    """The fully qualified ambient API a call reaches, or ``None``."""
    dotted = _dotted(call.func)
    if not dotted:
        return None
    head, _, rest = dotted.partition(".")
    resolved = aliases.get(head)
    if resolved is None:
        return None
    qualified = f"{resolved}.{rest}" if rest else resolved
    if qualified in AMBIENT_CALLS:
        return qualified
    if qualified == "random.Random" and not call.args and not call.keywords:
        return "random.Random()"
    return None


def _is_autouse_fixture(fn: "ast.FunctionDef | ast.AsyncFunctionDef") -> bool:
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


def _import_time_exprs(tree: ast.Module):
    """Every expression evaluated when the module is imported: module and class
    bodies, decorator arguments and default arguments — never a function body."""

    def visit_stmts(stmts):
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield from stmt.decorator_list
                yield from stmt.args.defaults
                yield from (d for d in stmt.args.kw_defaults if d is not None)
            elif isinstance(stmt, ast.ClassDef):
                yield from stmt.decorator_list
                yield from stmt.bases
                yield from visit_stmts(stmt.body)
            elif isinstance(stmt, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                for field in ("test", "iter", "items"):
                    value = getattr(stmt, field, None)
                    if isinstance(value, ast.expr):
                        yield value
                    elif isinstance(value, list):
                        yield from (i.context_expr for i in value if hasattr(i, "context_expr"))
                for block in ("body", "orelse", "finalbody"):
                    yield from visit_stmts(getattr(stmt, block, []) or [])
                for handler in getattr(stmt, "handlers", []) or []:
                    yield from visit_stmts(handler.body)
            else:
                yield stmt

    yield from visit_stmts(tree.body)


def _calls_outside_functions(node: ast.AST):
    """Calls inside ``node`` that are not inside a nested function or lambda body
    (those run later, not at import)."""
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, ast.Call):
            yield current
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            stack.append(child)


def _enclosing_functions(tree: ast.Module):
    """``(qualified name, function node)`` for every function and method."""

    def walk(stmts, prefix):
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{stmt.name}"
                yield name, stmt
                yield from walk(stmt.body, f"{name}.")
            elif isinstance(stmt, ast.ClassDef):
                yield from walk(stmt.body, f"{prefix}{stmt.name}.")

    yield from walk(tree.body, "")


def python_sites(
    path: str, source: str, listing: "set[str]", first_party: "set[str]"
) -> "list[_Site]":
    """Every site of every rule in one Python file. Raises ``SyntaxError`` (or
    ``ValueError``) when the file cannot be parsed."""
    tree = ast.parse(source, filename=path)
    sites: list[_Site] = []

    def first_party_of(module: str) -> "str | None":
        top = module.split(".")[0]
        return top if top in first_party else None

    in_test_tree = is_test_path(path)

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

    if in_test_tree:
        for qualname, fn in _enclosing_functions(tree):
            if not _is_autouse_fixture(fn):
                continue
            for node in ast.walk(fn):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for module in _imported_modules(node):
                        if first_party_of(module):
                            sites.append(_Site(
                                AUTOUSE_CHECK, (path, qualname, module), node.lineno,
                                f"autouse fixture `{qualname}` imports `{module}`, so every "
                                "test it reaches depends on that module; make the fixture "
                                "opt-in, or import lazily where a test needs it",
                            ))

    package = _package_of_init(path, first_party)
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
        import_time_calls: Counter = Counter()
        for expr in _import_time_exprs(tree):
            for call in _calls_outside_functions(expr):
                api = _ambient_name(call, aliases)
                if api:
                    import_time_calls[api] += 1
                    sites.append(_Site(
                        CLOCK_IMPORT_CHECK, (path, api, import_time_calls[api]), call.lineno,
                        f"`{api}` runs when the module is imported, so no fixture can "
                        "freeze it and every test in the process inherits the value; "
                        "move it into a fixture or the test body, behind an injected "
                        "clock or seeded generator",
                    ))
        if not _is_test_module(path):
            per_fn: Counter = Counter()
            for qualname, fn in _enclosing_functions(tree):
                for stmt in fn.body:
                    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue  # a nested function is its own site, walked on its own
                    for call in _calls_outside_functions(stmt):
                        api = _ambient_name(call, aliases)
                        if api:
                            per_fn[(qualname, api)] += 1
                            sites.append(_Site(
                                CLOCK_FAKE_CHECK,
                                (path, qualname, api, per_fn[(qualname, api)]),
                                call.lineno,
                                f"shared test helper `{qualname}` reads `{api}`, so every "
                                "test using it stops repeating; take the clock or "
                                "generator as a parameter, or freeze it",
                            ))
    return sites


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------


def _listing(project_dir: Path, tree: str) -> "set[str] | None":
    rc, out, _err = evidence.run_git(
        project_dir, "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", tree,
    )
    if rc != 0:
        return None
    return {line for line in out.splitlines() if line}


def _blobs(project_dir: Path, tree: str, paths: "list[str]") -> "dict[str, str] | None":
    """Each path's content at ``tree`` in one batched read; a path absent there is
    absent from the result."""
    if not paths:
        return {}
    request = "".join(f"{tree}:{p}\n" for p in paths)
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
    for path in paths:
        end = data.find(b"\n", pos)
        if end < 0:
            return None
        fields = data[pos:end].split()
        pos = end + 1
        if len(fields) == 2 and fields[1] == b"missing":
            continue
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
        project_dir, "-c", "core.quotepath=false", "diff", "--name-status", "-M",
        "--no-color", base_tree, head_tree,
    )
    if rc != 0:
        return None
    renames: dict[str, str] = {}
    for line in out.splitlines():
        fields = line.split("\t")
        if len(fields) == 3 and fields[0].startswith("R"):
            renames[fields[2]] = fields[1]
    return renames


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def _subject(path: str) -> str:
    """Which rule family a path is a candidate for: ``python``, ``other`` (a test
    file in a language without rules) or ``""``."""
    if path.endswith(".py"):
        if is_test_path(path) or _parts(path)[-1] == "__init__.py":
            return "python"
        return ""
    if is_test_path(path) and PurePosixPath(path).suffix in _OTHER_LANGUAGE_SUFFIXES:
        return "other"
    return ""


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


def _unwaived(sites: "list[_Site]", source: str) -> "list[_Site]":
    """``sites`` without those waived on their line or the line above, renumbered so
    each ordinal key counts only the unwaived reads it stands for."""
    lines = source.splitlines()
    kept = [s for s in sites if not waivers.waives(lines, s.line - 1, WAIVER_REF)]
    seen: Counter = Counter()
    for site in kept:
        if site.check in (CLOCK_FAKE_CHECK, CLOCK_IMPORT_CHECK):
            stem = site.key[:-1]
            seen[(site.check, stem)] += 1
            site.key = (*stem, seen[(site.check, stem)])
    return kept


def check(
    project_dir: Path, paths: "list[str] | None", base_tree: str, head_tree: str
) -> "tuple[list[dict], list[str], set[str]]":
    """Sites a change introduces, as ``(findings, unchecked, no_answer)`` — the shape
    record-lint's other arms return."""
    candidates = sorted({p for p in (paths or []) if _subject(p)})
    if not candidates:
        return [], [], set()
    head_listing = _listing(project_dir, head_tree)
    base_listing = _listing(project_dir, base_tree)
    renames = _renames(project_dir, base_tree, head_tree)
    if head_listing is None or base_listing is None or renames is None:
        return [], [
            f"{CONFTEST_CHECK} unchecked — the trees could not be listed, so no "
            "test-scope or test-clock check ran on this change"
        ], set(CHECKS)

    python = [p for p in candidates if _subject(p) == "python" and p in head_listing]
    other = [p for p in candidates if _subject(p) == "other" and p in head_listing]
    old_path = {p: renames.get(p, p) for p in python}
    head_src = _blobs(project_dir, head_tree, python)
    base_src = _blobs(project_dir, base_tree, sorted(set(old_path.values())))
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
            head_sites = python_sites(path, source, head_listing, head_fp)
        except (SyntaxError, ValueError):
            unparsed.append(path)
            continue
        # Waived sites leave BOTH sides before matching. Ordinal keys (the n-th
        # read of one API in one place) would otherwise pair a new unwaived read
        # with an old waived one, and the new read would vanish.
        base_keys: Counter = Counter()
        old = old_path[path]
        if old in base_src:
            try:
                for site in _unwaived(
                    python_sites(old, base_src[old], base_listing, base_fp), base_src[old]
                ):
                    base_keys[(site.check, (path, *site.key[1:]))] += 1
            except (SyntaxError, ValueError):
                pass  # an unparseable base has no sites to subtract: every head site is new
        for site in _unwaived(head_sites, source):
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
    return findings, unchecked, set()


def scan_tree(project_dir: Path, tree: str = "HEAD") -> "dict | None":
    """Every site in a tree, unwaived, largest blast radius first — the doctor's and
    the janitor's view of what already exists. ``None`` when the tree cannot be read.

    Returns ``{"sites": [{check, path, line, detail}], "scanned": N, "unparsed": [...],
    "unruled": [...]}``; ``scanned`` is the number of files the rules read, so an empty
    ``sites`` is visibly a scan of something."""
    listing = _listing(project_dir, tree)
    if listing is None:
        return None
    python = sorted(p for p in listing if _subject(p) == "python")
    unruled = sorted(p for p in listing if _subject(p) == "other")
    sources = _blobs(project_dir, tree, python)
    if sources is None:
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
        except (SyntaxError, ValueError):
            unparsed.append(path)
            continue
        sites.extend(_finding(site, path) for site in _unwaived(found, source))
    sites.sort(key=lambda s: (rank[s["check"]], s["path"], s["line"]))
    return {"sites": sites, "scanned": len(python), "unparsed": unparsed, "unruled": unruled}
