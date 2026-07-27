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
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / "plugin"
AGENT_DEF = REPO_ROOT / "agents" / "critic-reviewer.md"
REVIEW_PROTOCOL = REPO_ROOT / "skills" / "critic" / "review-protocol.md"
SKILL = REPO_ROOT / "skills" / "critic" / "SKILL.md"
HOOKS = REPO_ROOT / "hooks" / "hooks.json"
PLUGIN_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"

# SubagentStop matcher semantics, per https://code.claude.com/docs/en/hooks
# (verified 2026-07-27), corroborated by reading the matcher implementation out
# of the installed Claude Code 2.1.220 binary during the CRT-2J8N review.
#
# For SubagentStop, a matcher of ONLY letters, digits, `_`, `-`, spaces, `,` and
# `|` is an exact string — or a `|`/`,`-separated LIST of exact strings. A matcher
# containing any other character is a JavaScript regular expression, tested
# UNANCHORED via RegExp.prototype.test.
#
# The `startup|resume|clear|compact|fork` SessionStart matchers in the same
# hooks.json are `|`-separated exact lists and are correct as written — but they
# are correct under SessionStart's own literal class, NOT as a consequence of the
# SubagentStop rule above. Do not derive one event's behaviour from another's.
#
# SCOPE: which literal class an event uses is NOT uniform across hook events —
# this encoding is asserted for SubagentStop only, which is all these tests
# evaluate. Do not lift `_matcher_matches` to another event without re-verifying.
_LITERAL_MATCHER = re.compile(r"^[A-Za-z0-9_\- ,|]+$")


def _matcher_matches(matcher: str, value: str) -> bool:
    """Evaluate a SubagentStop hook matcher the way Claude Code evaluates it.

    Mirrors the two-path rule documented above. The exact-string path is why a
    bare agent name can never match a plugin-scoped `agent_type` — the defect
    this module's SubagentStop pins exist to catch.
    """
    if _LITERAL_MATCHER.match(matcher):
        return value in {p.strip() for p in re.split(r"[,|]", matcher) if p.strip()}
    return re.search(matcher, value) is not None


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
        # The bare name is the dispatch `subagent_type`. It is NOT what the
        # SubagentStop matcher is compared against — at runtime that value is
        # the plugin-scoped `prawduct:critic-reviewer`. Conflating the two is
        # what let CRT-2J8N ship; the contract itself is pinned by
        # TestSubagentStopMatcherMatchesRuntimeAgentType below.
        assert _field(_frontmatter(AGENT_DEF), "name") == "critic-reviewer"

    def test_has_description(self):
        assert _field(_frontmatter(AGENT_DEF), "description")


class TestSubagentStopMatcherMatchesRuntimeAgentType:
    """The SubagentStop matcher must match the value Claude Code actually supplies.

    For a subagent shipped by a plugin, the runtime `agent_type` is the
    PLUGIN-SCOPED identifier (`prawduct:critic-reviewer`), not the bare
    frontmatter name. A bare-name matcher takes the exact-string path and so can
    never match — the hook simply never fires, consolidation silently falls to
    the session-end backstop, and anyone reading `.critic-findings.json` without
    running `critic-consolidate` gets the PREVIOUS review (CRT-2J8N).
    """

    def _matcher(self) -> str:
        entries = json.loads(HOOKS.read_text())["hooks"]["SubagentStop"]
        matchers = [e["matcher"] for e in entries if "matcher" in e]
        assert len(matchers) == 1, f"expected exactly one SubagentStop matcher, got {matchers}"
        return matchers[0]

    def test_matches_the_plugin_scoped_agent_type(self):
        name = _field(_frontmatter(AGENT_DEF), "name")
        plugin = json.loads(PLUGIN_MANIFEST.read_text())["name"]
        scoped = f"{plugin}:{name}"
        assert _matcher_matches(self._matcher(), scoped), (
            f"SubagentStop matcher {self._matcher()!r} does not match the runtime "
            f"agent_type {scoped!r} — the hook will never fire"
        )

    def test_bare_name_matcher_cannot_match_a_scoped_value(self):
        # Pins the mechanism, not just the symptom: a future "simplification"
        # back to the bare name must fail here rather than fail silently.
        assert not _matcher_matches("critic-reviewer", "prawduct:critic-reviewer")

    def test_does_not_over_match_lookalike_agent_types(self):
        # DISCRIMINATING by construction: every value here CONTAINS the agent
        # name as a substring, so a lazily-broadened matcher (`critic-reviewer`
        # on the regex path, or a bare `.*critic-reviewer.*`) matches them and
        # fails here. Values that merely differ — `general-purpose`, `Explore` —
        # would pass under every candidate matcher including the broken one, so
        # they test nothing; that vacuity is the TST-9M2X defect class.
        for other in (
            "foo-critic-reviewer",  # the form the change-log claims is refused
            "prawduct:critic-reviewer-helper",
            "notprawduct:xcritic-reviewer",
        ):
            assert not _matcher_matches(self._matcher(), other), f"over-matches {other}"

    def test_the_over_match_guard_is_not_vacuous(self):
        # Proves the fixture above can fail: a deliberately sloppy matcher must
        # be caught by it. Without this, a future edit could weaken the matcher
        # and the guard would still pass for the wrong reason.
        assert _matcher_matches("critic-reviewer$", "foo-critic-reviewer")


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
