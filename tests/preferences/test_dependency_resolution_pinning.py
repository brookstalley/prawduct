"""Clause 5 conformance: this repo's own dependency resolution is pinned and frozen.

`plugin/docs/upstream-dependency-policy.md` clause 5 says the resolved dependency set
is committed and authoritative, and that installs in CI do not re-resolve. Prawduct
ships that policy, so prawduct is bound by it — a framework whose own repo ignores its
nudge is the aspirational-rule shape the norm lifecycle exists to catch.

The mechanism is `constraints.txt` plus `pip install -c constraints.txt ".[dev]"` in
`.github/workflows/tests.yml`. Five ways it can rot that are answerable from the tree,
one test class each — a checked set, not a claim that nothing else can go wrong:

1. **The file is deleted or emptied.** Listed first because it is the one that makes every
   assertion below pass *vacuously* — a guard that cannot fail against a repo pinning
   nothing at all is not a guard.
2. **A dependency is added to the `dev` extra and never pinned.** The suite stays green,
   CI keeps passing, and exactly one package silently re-resolves on every run.
3. **A transitive dependency is never pinned** — the same hole one rung down, and the one
   that actually shipped: `typing-extensions` sat unpinned because it is reached only
   *through* a marker-gated package, and a guard comparing against the four declared names
   could never fail for it. See `TestTheClosureIsClosed` for what that check can and
   cannot reach.
4. **A pin softens into a floor.** `pytest>=9.1.1` in a constraints file bounds nothing
   below the newest release; it reads like a pin and behaves like the absence of one.
   Requiring `==` throughout also keeps the file from becoming a second declaration of
   *what* this repo depends on, which is the `dev` extra's job.
5. **The workflow stops reading the file.** A pinned resolution nothing installs through
   is documentation, not enforcement.

This sentence has now been wrong twice in the same way. It read "Three ways that can rot"
while the module carried four classes; the fix counted four while the module carried five,
because `TestTheConstraintsFileExists` reads as a precondition rather than a rot mode and
got waved past. Both times the defect was the module's own subject wearing the module's own
clothes: a docstring asserting completeness is a claim, and prose goes stale silently
because nothing tests it. If you add a class here, this list is part of the change.

Deliberately NOT asserted here: that the pinned versions satisfy clause 1's minimum
release age. That check needs each version's publication time, which needs the index —
and a test that reaches the network is a test that fails when the network does. Release
age is the update procedure's job (`plugin/templates/upstream-dependency-update-runbook.md`),
which is where the registry read belongs; this file checks only the properties that are
answerable from the tree.
"""

from __future__ import annotations

import re
from pathlib import Path

# Imported plainly rather than via `importorskip`, matching
# `test_ci_workflow_conventions.py`: PyYAML is a declared dev dependency, so its
# absence is a broken environment rather than a reason to skip — and a guard that
# skips itself is indistinguishable from one that passes.
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONSTRAINTS = REPO_ROOT / "constraints.txt"
PYPROJECT = REPO_ROOT / "pyproject.toml"
TESTS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"

# A requirement's name ends at the first character that cannot be part of one.
# PEP 508 names are `[A-Za-z0-9._-]`, so this stops at `=`, `<`, `>`, `;`, `[` or space.
_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def _normalize(name: str) -> str:
    """PEP 503 normalisation — `PyYAML`, `pyyaml` and `py_yaml` are one package.

    Without this the checks below compare spellings rather than packages, and
    `PyYAML` in the extra against `pyyaml` in the constraints file reads as a
    missing pin when nothing is missing.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def _constraint_entries() -> list[str]:
    """Every non-comment, non-blank line of `constraints.txt`."""
    lines = []
    for raw in CONSTRAINTS.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def _dev_extra_requirements() -> list[str]:
    """The `dev` extra's requirement strings, read by regex rather than by TOML.

    `tomllib` is 3.11+, and this repo's declared floor — exercised by CI's matrix — is
    3.10. Importing it here would make the guard that protects the floor leg the thing
    that breaks it. The fallback (`tomli` on <3.11) would work only for as long as
    pytest keeps requiring it, which is somebody else's decision to change. The sibling
    `test_ci_workflow_conventions.py` reads `requires-python` out of the same file by
    regex for the same reason, so this matches its house style as well.
    """
    text = PYPROJECT.read_text()
    block = re.search(r"^dev\s*=\s*\[(.*?)\]", text, re.MULTILINE | re.DOTALL)
    assert block, "pyproject.toml must declare a `dev` extra as a list"
    requirements = re.findall(r'"([^"]+)"', block.group(1))
    assert requirements, "the `dev` extra parsed as empty — the regex has drifted from the file"
    return requirements


def _scalars(node: object) -> list[str]:
    """Every string in a parsed workflow — keys and values, recursively.

    Same rationale as its twin in `test_ci_workflow_conventions.py`: these checks
    look at what the workflow *executes*, and parsing drops the comments that a raw
    text scan would mistake for the thing they explain.
    """
    found: list[str] = []
    if isinstance(node, str):
        found.append(node)
    elif isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                found.append(key)
            found.extend(_scalars(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_scalars(item))
    return found


class TestTheConstraintsFileExists:
    def test_constraints_file_is_present(self):
        # Red if the file is deleted or renamed. Without this the assertions below
        # would all pass vacuously against a repo that pins nothing at all.
        assert CONSTRAINTS.exists(), (
            "constraints.txt is missing; clause 5 of the upstream dependency policy "
            "requires this repo's resolved dependency set to be committed"
        )

    def test_it_pins_something(self):
        assert _constraint_entries(), (
            "constraints.txt contains no requirements — an empty constraints file "
            "constrains nothing and installs re-resolve exactly as if it were absent"
        )


class TestEveryDeclaredDependencyIsPinned:
    def test_dev_extra_names_all_appear_in_constraints(self):
        """The load-bearing one: a dependency added and not pinned.

        Nothing else catches this. The new package installs, the suite passes, and
        that one package re-resolves on every CI run — a clause-5 hole that is
        invisible in the diff that opened it.
        """
        pinned = {
            _normalize(match.group(1))
            for entry in _constraint_entries()
            if (match := _NAME.match(entry))
        }
        declared = {
            _normalize(match.group(1))
            for requirement in _dev_extra_requirements()
            if (match := _NAME.match(requirement))
        }
        unpinned = sorted(declared - pinned)
        assert not unpinned, (
            f"declared in pyproject.toml's dev extra but not pinned in constraints.txt: "
            f"{', '.join(unpinned)}. Every declared dependency needs a pin, or it "
            "re-resolves on every install while everything still looks green"
        )


class TestTheClosureIsClosed:
    """The pin set must be closed under dependency, not merely cover what is declared.

    `test_dev_extra_names_all_appear_in_constraints` compares against the four names in
    the `dev` extra, so a transitive dependency can never fail it — which is how
    `typing-extensions` sat unpinned while four durable records said the closure was
    complete. It is reached only *through* a marker-gated package (`exceptiongroup`
    requires it on `python_version < "3.13"`, and pytest requires `exceptiongroup` on
    `< "3.11"`), so walking the roots' own markers one level does not find it.

    **Scope, stated because it is not total.** This checks the requirements of pinned
    distributions that are *installed in the environment running the test*, using their
    real metadata. On a modern interpreter the marker-gated packages are absent, so the
    check cannot see them here — and the CI matrix's floor leg is exactly where they are
    installed, which is what makes the two legs together cover the union. A gap this
    misses locally is caught there rather than nowhere, and no assertion below claims
    more than the environment can support.
    """

    def test_every_requirement_of_an_installed_pin_is_itself_pinned(self):
        from importlib.metadata import PackageNotFoundError, distribution

        pinned = {
            _normalize(match.group(1)): entry
            for entry in _constraint_entries()
            if (match := _NAME.match(entry))
        }
        gaps: list[str] = []
        checked = 0
        for name in sorted(pinned):
            try:
                dist = distribution(name)
            except PackageNotFoundError:
                continue  # not installed on this interpreter — the other CI leg covers it
            checked += 1
            for raw in dist.requires or []:
                requirement = raw.split(";", 1)
                marker = requirement[1].strip() if len(requirement) > 1 else ""
                # Extras are opt-in and nothing here installs them.
                if "extra ==" in marker:
                    continue
                dep = _NAME.match(requirement[0].strip())
                if dep and _normalize(dep.group(1)) not in pinned:
                    gaps.append(f"{name} requires {dep.group(1)}, which is not pinned")
        assert checked, (
            "no pinned distribution is installed, so this check proved nothing — run the "
            "suite in an environment where the dev extra is actually installed"
        )
        assert not gaps, (
            "constraints.txt is not closed under dependency:\n  "
            + "\n  ".join(gaps)
            + "\nAn unpinned transitive dependency re-resolves on every install exactly "
            "like an unpinned direct one; the records that call this set 'the whole "
            "closure' are wrong until it is added"
        )


class TestConstraintsAreExactPins:
    def test_every_entry_is_an_exact_version(self):
        """`==` throughout, for two reasons that happen to want the same rule.

        A floor in a constraints file bounds nothing above it, so `pytest>=9.1.1`
        reads as a pin and behaves as its absence. And an exact version is what keeps
        this file a record of a resolution rather than a second declaration of what
        the repo depends on — the `dev` extra owns that, and two homes for it is the
        drift `test_ci_workflow_conventions.py` was written to prevent next door.
        """
        offenders = []
        for entry in _constraint_entries():
            # Strip an environment marker before judging the specifier: the `>=` in
            # `; python_version >= "3.11"` is a marker operator, not a version floor.
            specifier = entry.split(";", 1)[0].strip()
            if "==" not in specifier:
                offenders.append(entry)
        assert not offenders, (
            f"constraints.txt entries are not exact pins: {offenders}. A floor or range "
            "in a constraints file leaves the upstream free to move, which is the "
            "re-resolution clause 5 forbids"
        )


class TestTheWorkflowInstallsThroughTheConstraints:
    def test_ci_passes_the_constraints_file_to_pip(self):
        """A pinned resolution nothing installs through is documentation.

        Red if the install step drops `-c constraints.txt` — at which point the file
        stays committed, this repo keeps claiming tier 1 in its recorded policy, and
        every CI run re-resolves.
        """
        doc = yaml.safe_load(TESTS_WORKFLOW.read_text())
        if True in doc:  # PyYAML reads the bare key `on` as the boolean True
            doc["on"] = doc.pop(True)
        installs = [
            scalar
            for scalar in _scalars(doc)
            if "pip install" in scalar and '".[dev]"' in scalar
        ]
        assert installs, "tests.yml no longer installs the dev extra"
        for step in installs:
            assert "-c constraints.txt" in step, (
                f"the install step does not read constraints.txt ({step!r}); without it "
                "CI re-resolves and the committed pins bind nothing"
            )
