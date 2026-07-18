"""Structural + behavioral invariants for the backlog package.

- **INV-1** — zero model client on the CRUD path (G1): no module under
  ``lib/backlog/`` imports or calls an LLM; driving ``file``/``get`` performs only
  transport operations.
- **Egress discipline** — ``transport.py`` is the *sole* egress: no other module
  shells out or opens a socket (Test Specs §2.1, the seam).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lib.backlog import core  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

_PKG = _REPO_ROOT / "lib" / "backlog"
_MODULES = sorted(p for p in _PKG.glob("*.py"))

# Model-SDK import roots + call patterns that would signal an LLM on the path.
_MODEL_IMPORT_ROOTS = {"anthropic", "openai", "litellm", "langchain", "cohere", "google.generativeai"}
_MODEL_CALL_SNIPPETS = (".messages.create", ".completions.create", ".chat.completions")

# Transport egress: shelling out / sockets belong only in transport.py.
_EGRESS_IMPORT_ROOTS = {"subprocess", "socket", "http", "urllib", "requests", "httpx"}


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


class TestNoModelOnCrudPath:
    """INV-1 — the data plane never touches a model."""

    def test_no_model_sdk_imported_anywhere_in_package(self):
        for path in _MODULES:
            roots = _imported_roots(ast.parse(path.read_text()))
            assert not (roots & _MODEL_IMPORT_ROOTS), f"{path.name} imports a model SDK"

    def test_no_model_call_pattern_in_source(self):
        for path in _MODULES:
            src = path.read_text()
            for snippet in _MODEL_CALL_SNIPPETS:
                assert snippet not in src, f"{path.name} contains a model call {snippet!r}"

    def test_crud_ops_touch_only_transport_methods(self):
        fake = FakeGitHub()
        core.provision_labels(fake, owner="octo", repo="repo")
        core.file_item(fake, owner="octo", repo="repo", title="X", body="b", facets={"stage": "ready"})
        core.get_item(fake, id_raw="octo/repo#1")
        allowed = {
            "get_authenticated_user",
            "create_issue",
            "get_issue",
            "list_labels",
            "create_label",
        }
        used = {call[0] for call in fake.calls}
        assert used <= allowed, f"unexpected non-transport calls: {used - allowed}"


class TestEgressDiscipline:
    """transport.py is the sole egress (the primary test seam)."""

    def test_only_transport_module_shells_out_or_sockets(self):
        for path in _MODULES:
            roots = _imported_roots(ast.parse(path.read_text()))
            offending = roots & _EGRESS_IMPORT_ROOTS
            if path.name == "transport.py":
                assert "subprocess" in roots, "transport.py must own the subprocess egress"
            else:
                assert not offending, f"{path.name} imports egress module(s) {offending}"
