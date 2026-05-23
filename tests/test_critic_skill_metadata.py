"""Critic skill metadata tests — structural enforcement of "no test execution".

v1.5.1 Chunk 02. The recurring failure mode (memory rule
`feedback_critic_no_test_execution.md`, Wave 2 cumulative-Critic violation) is
"Critic invokes pytest despite prose forbidding it." Prose alone doesn't hold
under load. These tests assert that the Critic skill's `allowed-tools`
frontmatter explicitly denies pytest invocations — drift in either the
framework-owned skill or the product-distribution template fails loud.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

CRITIC_SKILL_SURFACES = [
    REPO_ROOT / ".claude" / "skills" / "critic" / "SKILL.md",
    REPO_ROOT / "templates" / "skill-critic.md",
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

    def test_existing_legitimate_tools_preserved(self):
        """The deny additions must not accidentally drop existing allows."""
        legitimate_prefixes = [
            "Read",
            "Glob",
            "Grep",
            "Bash(git *)",
            "Bash(wc *)",
            "Bash(python3 tools/product-hook test-status)",
            "Bash(python3 tools/product-hook verify-chunk-refs *)",
            "Bash(python3 tools/product-hook infer-critic-mode *)",
            "Write",
            "Agent",
        ]
        for surface in CRITIC_SKILL_SURFACES:
            allowed = _extract_allowed_tools(surface.read_text())
            for tool in legitimate_prefixes:
                assert tool in allowed, (
                    f"{surface.relative_to(REPO_ROOT)} dropped legitimate "
                    f"tool `{tool}` from allowed-tools"
                )

    def test_both_surfaces_have_equivalent_deny_sets(self):
        """Drift between framework dogfood and product template = bug."""
        framework = _extract_allowed_tools(CRITIC_SKILL_SURFACES[0].read_text())
        template = _extract_allowed_tools(CRITIC_SKILL_SURFACES[1].read_text())
        framework_denies = set(re.findall(r"!Bash\([^)]+\)", framework))
        template_denies = set(re.findall(r"!Bash\([^)]+\)", template))
        assert framework_denies == template_denies, (
            f"deny-set drift: framework has {framework_denies - template_denies} "
            f"that template lacks; template has {template_denies - framework_denies} "
            f"that framework lacks"
        )
