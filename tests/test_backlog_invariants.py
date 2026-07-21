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


class TestArchiveScopeWarningTruthfulness:
    """Every ``--archive-scope open`` skip notice must tell the operator the truth
    about where the skipped items went.

    These strings shipped saying the skipped set "remains in the source markdown +
    MG2 export". The export half is impossible: ``export_backlog`` dumps the
    *migrated repo* and the migration runbook runs it after the first import, so it
    can never contain what the import excluded. An operator choosing ``open`` on
    that basis expects a restorable archive artifact that is never produced.

    Scanned over the package source rather than asserted per call site, because the
    claim shipped in two places and a third emission would otherwise inherit the
    old wording while a per-site test stayed green — the derivation-hole shape this
    repo has been bitten by before. The rule: a literal that markets ``open``'s
    preservation names the source markdown and never credits an export.

    The export ban is a deliberately blunt substring check, and it bans a *word*
    where the real defect is a *false credit*. If a future change makes some export
    artifact genuinely hold the skipped set — the step-0 source-export shape is one
    open candidate — this test will fail on a sentence that is finally true. That is
    the intended failure mode: retarget the assertion to the new mechanism (and
    re-verify it), never delete it to make a red suite green."""

    _MARKER = "archive-scope open"

    @staticmethod
    def _text_of(node) -> str | None:
        """The full text of a string expression, following implicit concatenation.

        Adjacent plain literals fold into one ``Constant``, but as soon as one
        piece interpolates, the whole run becomes a ``JoinedStr`` whose parts must
        be rejoined — otherwise the marker and the corrective clause land in
        different fragments and a per-fragment scan reads each as a separate,
        half-true string. Interpolated values contribute nothing scannable, so
        they are skipped rather than rendered."""
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else None
        if isinstance(node, ast.JoinedStr):
            parts = [
                v.value
                for v in node.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
            ]
            return "".join(parts) if parts else None
        return None

    def _claim_literals(self) -> list[tuple[str, str]]:
        """Every whole string expression in the package that markets ``open``.

        An f-string's own fragments are skipped: ``ast.walk`` yields them
        alongside the ``JoinedStr`` that owns them, and judging a fragment is how
        a true sentence gets reported as a false one — the marker sits in the
        first fragment, the corrective clause in a later one."""
        found: list[tuple[str, str]] = []
        for path in _MODULES:
            tree = ast.parse(path.read_text())
            consumed = {
                id(part)
                for node in ast.walk(tree)
                if isinstance(node, ast.JoinedStr)
                for part in node.values
            }
            for node in ast.walk(tree):
                if id(node) in consumed:
                    continue
                text = self._text_of(node)
                if text and self._MARKER in text:
                    found.append((path.name, text))
        return found

    def test_the_claim_is_emitted_somewhere(self):
        # Guards the scan itself: if the marker is reworded, this fails loudly
        # rather than the truthfulness test passing over an empty set.
        assert self._claim_literals(), (
            f"no string literal mentions {self._MARKER!r}; if the wording changed, "
            "retarget this invariant rather than deleting it"
        )

    def test_no_skip_notice_credits_an_export(self):
        for name, literal in self._claim_literals():
            assert "export" not in literal.lower(), (
                f"{name}: an --archive-scope open notice credits an export with preserving "
                f"skipped items, but the export dumps the migrated repo: {literal!r}"
            )

    def test_every_skip_notice_names_the_real_home(self):
        for name, literal in self._claim_literals():
            assert "source markdown" in literal, (
                f"{name}: an --archive-scope open notice does not tell the operator the "
                f"skipped items remain in the git-tracked source markdown: {literal!r}"
            )
