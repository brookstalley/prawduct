"""An advisory's static evidence changes only with its type's version.

An advisory's id is ``<feature>-<type>-v<version>-<hash of evidence>``
(``advisory_store.compute_id``), so rewording a candidate's evidence mints a new
id. If the version is unchanged, the old and new ids carry one version for two
conditions: an open advisory is resolved as if its condition cleared, instead of
being superseded by the refined one, and the change reads as an accident. The
convention (``norm_probes``' sweep-overdue candidate) is to bump the version so
the supersession is deliberate. Remembering it at the edit is the weak form; this
test makes the edit fail until it is done.

**Scope.** Only evidence the probe module spells as string literals or
module-level string constants can be pinned. A candidate whose evidence is built
from live data (a path, a count, a rule) is read and skipped, and the skip is
counted so a hoisted string cannot silently drop out of the pinned set.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

import pytest

from lib import advisory_store, probe_families

LIB = Path(__file__).resolve().parent.parent / "plugin" / "lib"

#: ``(feature, type)`` → ``(version, sorted evidence digests)``. A digest is the
#: first 12 hex characters of SHA-256 over the evidence lines joined by newlines,
#: the same join ``compute_id`` hashes. Change a row only together with the
#: version it pins: a new digest under the same version is the defect this file
#: exists to catch.
PINS: dict[tuple[str, str], tuple[int, tuple[str, ...]]] = {
    ("api-design", "api-versioning"): (1, ("29170885011a",)),
    ("backlog", "legacy-backlog-format"): (1, ("13b34ab74ea6",)),
    ("backlog", "backlog-service-migration-required"): (1, ("e5f7a5f7da07",)),
    ("backlog", "backlog-archive-deferred"): (1, ("f588856d2282",)),
    ("structural-coverage", "strategy-artifact-missing"): (1, ("16625aa109ec",)),
    ("structural-coverage", "discovery-not-captured"): (1, ("0001f363aec7",)),
    ("governance", "oversized-evidence-store"): (1, ("775e19b3962a",)),
    ("gitignore", "contract-ignored-by-rule"): (1, ("f3b248d8a304",)),
    ("gitignore", "contract-drift"): (1, ("48f9dd431449",)),
    ("install-reference", "contract-drift"): (1, ("5984082aa24c",)),
    ("install-reference", "tripwire-missing"): (1, ("24d89d5074d9",)),
    ("norm-lifecycle", "revisit-due"): (1, ("f21b888a0ff8",)),
    ("norm-lifecycle", "dead-why"): (1, ("fcdc48db83e9",)),
    ("norm-lifecycle", "stalled-transition"): (1, ("5ddc7e91daef",)),
    ("norm-lifecycle", "norm-registry-unratified"): (1, ("06b00ec17e74",)),
    ("norm-lifecycle", "norm-health-sweep-overdue"): (1, ("2a338fa5cbba",)),
    ("report-bug", "untriaged-upstream-reports"): (
        2, ("5d6ff516aa6d", "ac25e0c379ca", "dbc85dc4246c"),
    ),
}

#: How many candidates build their evidence from live data and so are not
#: pinned. A literal moved behind a helper or computed name lands here instead of
#: in PINS; this count is what makes that visible.
DYNAMIC_EVIDENCE_CANDIDATES = 21


def _digest(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:12]


def _static_str(node: ast.AST | None, module) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and isinstance(getattr(module, node.id, None), str):
        return getattr(module, node.id)
    return None


def _scan() -> tuple[dict[tuple[str, str], set[str]], int, list[str]]:
    """``(digests by (feature, type), dynamic count, unreadable sites)``."""
    found: dict[tuple[str, str], set[str]] = {}
    dynamic = 0
    unreadable: list[str] = []
    for path in sorted(LIB.glob("*_probes.py")):
        module = importlib.import_module(f"lib.{path.stem}")
        feature = getattr(module, "FEATURE", None)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "AdvisoryCandidate"):
                continue
            kwargs = {k.arg: k.value for k in node.keywords}
            evidence = kwargs.get("evidence")
            lines = (
                [_static_str(e, module) for e in evidence.elts]
                if isinstance(evidence, ast.Tuple) else [None]
            )
            if None in lines:
                dynamic += 1
                continue
            ctype = _static_str(kwargs.get("type"), module)
            if not isinstance(feature, str) or ctype is None:
                unreadable.append(f"{path.name}:{node.lineno}")
                continue
            found.setdefault((feature, ctype), set()).add(_digest(lines))
    return found, dynamic, unreadable


@pytest.fixture(scope="module")
def versions():
    advisory_store.clear_registry()
    probe_families.register_all()
    try:
        yield advisory_store.registered_versions()
    finally:
        advisory_store.clear_registry()


def test_static_evidence_moves_only_with_its_version(versions):
    found, _dynamic, _unreadable = _scan()
    problems = []
    for key, digests in sorted(found.items()):
        version = versions.get(key)
        current = (version, tuple(sorted(digests)))
        pinned = PINS.get(key)
        if pinned is None:
            problems.append(f"{key}: not pinned; add {key!r}: {current!r}")
        elif pinned[1] != current[1] and pinned[0] == version:
            problems.append(
                f"{key}: evidence changed but its version is still {version}. The id "
                "changes either way; bump the version so the refined advisory "
                "supersedes the old one, then re-pin. Every type sharing that "
                "version constant is re-minted with it: when a sibling's evidence did "
                f"not change, give the refined type a constant of its own. Now: {current!r}"
            )
        elif pinned != current:
            problems.append(f"{key}: version moved; re-pin as {current!r}")
    for key in sorted(set(PINS) - set(found)):
        problems.append(f"{key}: pinned but no longer emitted with static evidence; drop the row")
    assert not problems, "\n".join(problems)


def test_every_static_candidate_is_attributable():
    _found, _dynamic, unreadable = _scan()
    assert unreadable == [], (
        "static evidence whose feature or type cannot be read statically, so it is "
        f"not pinned: {unreadable}"
    )


def test_the_unpinned_set_is_counted():
    _found, dynamic, _unreadable = _scan()
    assert dynamic == DYNAMIC_EVIDENCE_CANDIDATES, (
        f"{dynamic} candidates now build evidence from live data, not "
        f"{DYNAMIC_EVIDENCE_CANDIDATES}. If one that was literal moved behind a helper, "
        "its edits are no longer pinned: keep it literal, or accept that and update "
        "the count."
    )
