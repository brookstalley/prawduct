"""Structural pins for the redesigned Critic coordinator (critic-persistence-redesign Ch.03).

The coordinator no longer resumes to aggregate + write findings (v2.1.198 backgrounds
Agent subagents, so the resume never fired and reviews were silently lost). Instead:

* reviewers are the plugin **`critic-reviewer` agent type** whose OWN `tools` allow-list
  binds them to code-analysis + writing a single partial (no test execution — CRT-3X9D
  becomes structural, not prose);
* the coordinator writes a manifest, dispatches the reviewers, and STOPS;
* `critic-consolidate` (Ch.02) persists deterministically.

These tests fail loud if the plugin-distributed agent def or the rewritten coordinator
prose drifts back toward the old inline-write flow. Single-pass prose must stay put.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_DEF = REPO_ROOT / "agents" / "critic-reviewer.md"
REVIEW_PROTOCOL = REPO_ROOT / "skills" / "critic" / "review-protocol.md"
SKILL = REPO_ROOT / "skills" / "critic" / "SKILL.md"


def _frontmatter(path: Path) -> str:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m is not None, f"{path.name} missing YAML frontmatter"
    return m.group(1)


def _field(frontmatter: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.+)$", frontmatter, re.MULTILINE)
    assert m is not None, f"frontmatter missing `{key}:`"
    return m.group(1).strip()


class TestAgentDefinitionExists:
    def test_file_exists_at_plugin_agents_dir(self):
        # Auto-discovered from the plugin root's agents/ dir (no plugin.json entry needed).
        assert AGENT_DEF.is_file(), "agents/critic-reviewer.md must exist"

    def test_name_is_critic_reviewer(self):
        # The name is dispatch subagent_type AND the SubagentStop matcher target.
        assert _field(_frontmatter(AGENT_DEF), "name") == "critic-reviewer"

    def test_has_description(self):
        assert _field(_frontmatter(AGENT_DEF), "description")


class TestAgentToolsAreRestricted:
    """The agent-def tools allow-list is the structural no-execution guarantee for
    reviewers (unlike a skill's allowed-tools, an agent type's tools DO bind it)."""

    def _tools(self) -> list[str]:
        raw = _field(_frontmatter(AGENT_DEF), "tools")
        # Comma- or pipe-separated per the plugin agent schema.
        parts = re.split(r"[,|]", raw)
        return [p.strip() for p in parts if p.strip()]

    def test_has_code_analysis_and_write(self):
        tools = self._tools()
        for required in ("Read", "Glob", "Grep", "Write"):
            assert required in tools, f"critic-reviewer must allow {required}"

    def test_no_broad_bash(self):
        tools = self._tools()
        assert "Bash" not in tools, "critic-reviewer must not have unrestricted Bash"
        assert not any(t == "Bash(*)" for t in tools)

    def test_git_is_read_only(self):
        tools = self._tools()
        assert "Bash(git *)" not in tools, "no broad git — mutating verbs must be impossible"
        for verb in ("Bash(git diff *)", "Bash(git log *)", "Bash(git show *)"):
            assert verb in tools, f"critic-reviewer missing read-only git verb {verb}"

    def test_no_allow_pattern_permits_pytest(self):
        """The negative probe: no Bash allow pattern may match a pytest invocation."""
        bash_patterns = [
            t[len("Bash("):-1]
            for t in self._tools()
            if t.startswith("Bash(") and t.endswith(")")
        ]
        for cmd in ("pytest", "python -m pytest", "python3 -m pytest tests/",
                    "cd x && python3 -m pytest"):
            for pat in bash_patterns:
                assert not fnmatch.fnmatch(cmd, pat), (
                    f"agent tool `Bash({pat})` would permit `{cmd}` — reviewers must "
                    f"be structurally unable to run tests"
                )


class TestAgentWritesOnlyItsPartial:
    def test_directs_partial_path(self):
        body = AGENT_DEF.read_text()
        assert ".prawduct/.critic-partials/" in body

    def test_forbids_inline_consolidation_and_findings(self):
        body = AGENT_DEF.read_text()
        # The reviewer must be told NOT to write the canonical file or consolidate/end.
        assert "critic-findings.json" in body  # (named in a "do NOT write" instruction)
        assert "critic-consolidate" in body
        assert "critic-end" in body
        # A crude but effective pin that the mentions are prohibitions.
        assert "do NOT" in body or "Do NOT" in body


class TestCoordinatorProseRewritten:
    def test_protocol_declares_manifest_and_partials(self):
        text = REVIEW_PROTOCOL.read_text()
        assert "manifest.json" in text
        assert ".critic-partials" in text
        assert "critic-reviewer" in text
        assert "critic-consolidate" in text

    def test_protocol_says_stop_no_resume(self):
        text = REVIEW_PROTOCOL.read_text()
        # The load-bearing behavior change: the coordinator does not resume to write.
        assert "do not resume" in text.lower() or "no resume-to-aggregate" in text.lower()

    def test_protocol_coordinator_does_not_write_findings_inline(self):
        """The old step 3 ('persist .critic-findings.json') must be gone from the
        Coordinator Pattern — the coordinator writes the manifest, not the findings."""
        text = REVIEW_PROTOCOL.read_text()
        coord = text.split("### Coordinator Pattern", 1)[1].split("## Output Format", 1)[0]
        assert "persist `.prawduct/.critic-findings.json`" not in coord

    def test_skill_coordinator_path_present(self):
        text = SKILL.read_text()
        assert "critic-reviewer" in text
        assert "manifest" in text
        assert "critic-consolidate" in text

    def test_skill_single_pass_writes_partial_not_findings(self):
        """kernel-v3 chunk 05 renegotiation (single-pass unification, design D8):
        the old '(Single-pass only) Write findings to .critic-findings.json +
        ledger-append + critic-end' steps are deleted — every mode now flows
        begin(manifest) → partial(s) → critic-consolidate, and consolidate is
        the ONLY writer of the findings cache and the ledger. The successor pin:
        the single-pass fork writes its one `reviewer` partial and runs
        consolidate itself; the skill never instructs authoring the findings
        file or a ledger line."""
        text = SKILL.read_text()
        assert ".critic-partials/reviewer.json" in text
        assert "run `prawduct-hook critic-consolidate` yourself" in text
        assert "ledger-append" not in text, (
            "the skill must not instruct hand-appending the ledger — "
            "critic-consolidate is the only ledger writer for reviews"
        )
        assert "Write findings** to `.prawduct/.critic-findings.json`" not in text


class TestSinglePassUnchanged:
    def test_chunk_and_verify_still_single_pass(self):
        text = REVIEW_PROTOCOL.read_text()
        assert "single-pass" in text.lower()
        # chunk / verify-resolutions must remain outside the coordinator path.
        exec_section = text.split("## Review Execution", 1)[1].split("### Coordinator", 1)[0]
        assert "chunk" in exec_section and "verify-resolutions" in exec_section
