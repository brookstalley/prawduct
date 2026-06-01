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
Drift in the framework-owned skill, the product-distribution template, or the
plugin-distributed skill (v2.0.0) fails loud.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

CRITIC_SKILL_SURFACES = [
    REPO_ROOT / ".claude" / "skills" / "critic" / "SKILL.md",
    REPO_ROOT / "templates" / "skill-critic.md",
    # The plugin-distributed Critic skill (v2.0.0): the governance surface that
    # runs for plugin-consuming repos. It must satisfy the SAME structural
    # safety blocks (pure-allow deny set, read-only git) as the framework skill.
    # Chunk 5 deliberately repoints its runtime-hook invocations from
    # `python3 tools/product-hook …` to the bundled `prawduct-hook …` (on the
    # Bash PATH), so its frontmatter is no longer byte-identical — the safety
    # set is, the invocation prefix is not.
    REPO_ROOT / "skills" / "critic" / "SKILL.md",
]

# The plugin Critic surface (distribution-specific invocation prefix).
_PLUGIN_CRITIC_SKILL = REPO_ROOT / "skills" / "critic" / "SKILL.md"

# The shadow Critic twin must obey the same read-only-git constraint (CRT-2M5P)
# even though it carries no deny patterns and doesn't gate session end.
GIT_READONLY_SURFACES = CRITIC_SKILL_SURFACES + [
    REPO_ROOT / ".claude" / "skills" / "critic-test" / "SKILL.md",
]

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

    def test_framework_skill_has_all_deny_patterns(self):
        content = CRITIC_SKILL_SURFACES[0].read_text()
        allowed = _extract_allowed_tools(content)
        for pat in REQUIRED_DENY_PATTERNS:
            assert pat in allowed, (
                f"framework .claude/skills/critic/SKILL.md is missing deny "
                f"pattern `{pat}` in allowed-tools"
            )

    def test_product_template_has_all_deny_patterns(self):
        content = CRITIC_SKILL_SURFACES[1].read_text()
        allowed = _extract_allowed_tools(content)
        for pat in REQUIRED_DENY_PATTERNS:
            assert pat in allowed, (
                f"templates/skill-critic.md is missing deny pattern `{pat}` "
                f"in allowed-tools"
            )

    def test_plugin_skill_has_all_deny_patterns(self):
        content = CRITIC_SKILL_SURFACES[2].read_text()
        allowed = _extract_allowed_tools(content)
        for pat in REQUIRED_DENY_PATTERNS:
            assert pat in allowed, (
                f"plugin skills/critic/SKILL.md is missing deny pattern `{pat}` "
                f"in allowed-tools"
            )

    def test_existing_legitimate_tools_preserved(self):
        """The deny additions must not accidentally drop existing allows.

        Common tools are checked on every surface; the runtime-hook invocation
        prefix is distribution-specific — file-sync surfaces call
        `python3 tools/product-hook …`, the plugin surface calls the bundled
        `prawduct-hook …` (Chunk 5 repoint)."""
        common = ["Read", "Glob", "Grep", "Bash(wc *)", "Write", "Agent"]
        legacy_hook_tools = [
            "Bash(python3 tools/product-hook test-status)",
            "Bash(python3 tools/product-hook verify-chunk-refs *)",
            "Bash(python3 tools/product-hook infer-critic-mode *)",
        ]
        plugin_hook_tools = [
            "Bash(prawduct-hook test-status)",
            "Bash(prawduct-hook verify-chunk-refs *)",
            "Bash(prawduct-hook infer-critic-mode *)",
        ]
        for surface in CRITIC_SKILL_SURFACES:
            allowed = _extract_allowed_tools(surface.read_text())
            expected = common + (
                plugin_hook_tools if surface == _PLUGIN_CRITIC_SKILL else legacy_hook_tools
            )
            for tool in expected:
                assert tool in allowed, (
                    f"{surface.relative_to(REPO_ROOT)} dropped legitimate "
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

    def test_all_surfaces_have_equivalent_deny_sets(self):
        """Drift between any Critic surface (framework dogfood, product template,
        plugin distribution) and the framework skill = bug."""
        framework_path = CRITIC_SKILL_SURFACES[0]
        framework_denies = set(
            re.findall(r"!Bash\([^)]+\)", _extract_allowed_tools(framework_path.read_text()))
        )
        for surface in CRITIC_SKILL_SURFACES[1:]:
            surface_denies = set(
                re.findall(r"!Bash\([^)]+\)", _extract_allowed_tools(surface.read_text()))
            )
            assert surface_denies == framework_denies, (
                f"deny-set drift: {surface.relative_to(REPO_ROOT)} has "
                f"{surface_denies - framework_denies} that the framework skill lacks; "
                f"framework has {framework_denies - surface_denies} that it lacks"
            )
