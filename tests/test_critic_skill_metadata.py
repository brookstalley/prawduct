"""Critic skill metadata tests — structural enforcement of "no test execution"
and "no working-tree mutation".

The recurring failure mode (memory rule `feedback_critic_no_test_execution.md`)
is "Critic invokes pytest despite prose forbidding it." Prose alone doesn't hold
under load. The REAL structural block is the pure-allow `allowed-tools` list: no
allow pattern matches a pytest invocation (`test_no_allow_pattern_permits_pytest`,
CRT-8H3D). The `!Bash(...pytest*)` deny entries are kept as belt-and-suspenders
documentation and still asserted present, but skill-frontmatter `!`-deny is not
reliably honored by the harness, so they are not the mechanism. Git is likewise
restricted to read-only verbs so a review can't mutate the tree (CRT-2M5P).
Drift in the plugin-distributed Critic skill fails loud.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

# Critic skill surface that must carry the structural safety set (pure-allow deny
# set, read-only git verbs only). Chunk 13 removed the legacy framework
# `.claude/skills/critic/SKILL.md` (this repo is now governed by the plugin) and
# retired the `critic-test` shadow skill; M4 Chunk 4 deleted the file-sync product
# template (`templates/skill-critic.md`) when the engine retired. The plugin-
# distributed skill is the sole surviving surface — its runtime-hook invocations
# call the bundled `prawduct-hook …` (Chunk 5 repoint).
_PLUGIN_CRITIC_SKILL = REPO_ROOT / "skills" / "critic" / "SKILL.md"
CRITIC_SKILL_SURFACES = [_PLUGIN_CRITIC_SKILL]

# The same read-only-git constraint (CRT-2M5P) applies to every Critic surface.
GIT_READONLY_SURFACES = CRITIC_SKILL_SURFACES

REQUIRED_DENY_PATTERNS = [
    "!Bash(pytest*)",
    "!Bash(python -m pytest*)",
    "!Bash(python3 -m pytest*)",
    "!Bash(* python -m pytest*)",
]


def _extract_allowed_tools(content: str) -> str:
    """Return the verbatim `allowed-tools:` value from a skill's frontmatter."""
    m = re.search(r"^allowed-tools:\s*(.+)$", content, re.MULTILINE)
    assert m is not None, "skill missing `allowed-tools:` frontmatter field"
    return m.group(1).strip()


class TestCriticSkillDenyPatterns:
    """Both Critic skill surfaces must structurally deny pytest invocations."""

    def test_plugin_skill_has_all_deny_patterns(self):
        allowed = _extract_allowed_tools(_PLUGIN_CRITIC_SKILL.read_text())
        for pat in REQUIRED_DENY_PATTERNS:
            assert pat in allowed, (
                f"plugin skills/critic/SKILL.md is missing deny pattern `{pat}` "
                f"in allowed-tools"
            )

    def test_existing_legitimate_tools_preserved(self):
        """The deny additions must not accidentally drop existing allows.

        The plugin Critic surface calls the bundled `prawduct-hook …` runtime
        (Chunk 5 repoint, replacing the retired `python3 tools/product-hook …`)."""
        expected = [
            "Read", "Glob", "Grep", "Bash(wc *)", "Write", "Agent",
            "Bash(prawduct-hook test-status)",
            "Bash(prawduct-hook verify-chunk-refs *)",
            "Bash(prawduct-hook infer-critic-mode *)",
        ]
        allowed = _extract_allowed_tools(_PLUGIN_CRITIC_SKILL.read_text())
        for tool in expected:
            assert tool in allowed, (
                f"{_PLUGIN_CRITIC_SKILL.relative_to(REPO_ROOT)} dropped legitimate "
                f"tool `{tool}` from allowed-tools"
            )

    def test_git_is_read_only(self):
        """CRT-2M5P: the Critic must NOT have the broad `Bash(git *)` allow —
        it let a review run `git checkout` and corrupt the working tree. Git is
        restricted to read-only verbs."""
        readonly_verbs = [
            "Bash(git diff *)",
            "Bash(git log *)",
            "Bash(git status *)",
            "Bash(git show *)",
            "Bash(git rev-parse *)",
            "Bash(git merge-base *)",
        ]
        for surface in GIT_READONLY_SURFACES:
            allowed = _extract_allowed_tools(surface.read_text())
            assert "Bash(git *)" not in allowed, (
                f"{surface.relative_to(REPO_ROOT)} still grants broad `Bash(git *)` "
                f"— it permits state-mutating verbs (checkout/reset/stash). Use "
                f"explicit read-only verbs (CRT-2M5P)."
            )
            for verb in readonly_verbs:
                assert verb in allowed, (
                    f"{surface.relative_to(REPO_ROOT)} missing read-only git verb "
                    f"`{verb}`"
                )

    def test_no_allow_pattern_permits_pytest(self):
        """CRT-8H3D: the real, structural pytest block is the PURE-ALLOW list —
        the `!Bash(...pytest*)` deny entries are documented as non-functional
        (skill-frontmatter `!`-deny isn't reliably honored). This is the
        negative-path probe that backs that claim: no ALLOW pattern may match a
        pytest invocation."""
        import fnmatch

        pytest_cmds = [
            "pytest",
            "python -m pytest",
            "python3 -m pytest tests/",
            "cd foo && python3 -m pytest",
        ]
        for surface in CRITIC_SKILL_SURFACES:
            allowed = _extract_allowed_tools(surface.read_text())
            allow_patterns = [
                entry.strip()[len("Bash("):-1]
                for entry in allowed.split(",")
                if entry.strip().startswith("Bash(") and entry.strip().endswith(")")
            ]
            for cmd in pytest_cmds:
                for pat in allow_patterns:
                    assert not fnmatch.fnmatch(cmd, pat), (
                        f"{surface.relative_to(REPO_ROOT)}: allow pattern "
                        f"`Bash({pat})` would permit `{cmd}` — pytest is not "
                        f"structurally blocked by the allow-list"
                    )

