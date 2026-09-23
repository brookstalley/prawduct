"""Structural pins for the `pr-reviewer` plugin agent.

The PR review used to be a generic subagent spawned with a prompt. Two things a
prompt cannot hold moved into an agent definition: a tool allow-list scoped to
what a release-readiness review needs, and `omitClaudeMd: true`, which keeps the
repo's `CLAUDE.md` hierarchy, its always-loaded `.claude/rules/` project rules and
its `MEMORY.md` out of the reviewer's starting context — a corpus
`review-protocol.md` forbids this reviewer to scan the diff against. A
path-scoped rules file still arrives on a matching Read; that gap is pinned in
:class:`TestClaudeMdIsOmitted` rather than left for the prose to overstate.

**Ported from `tests/test_critic_reviewer_agent.py`, deliberately.** That file
enumerates the branches this design creates, and citing a precedent without
carrying its coverage is how a module borrows a design and leaves its tests
behind. Three of its four classes port; the fourth does not, and the reason is
recorded rather than left as an absence:

* `TestSubagentStopMatcherMatchesRuntimeAgentType` does **not** port. The Critic
  coordinator dispatches and stops, so a `SubagentStop` hook is what runs its
  consolidation, and the bare-vs-plugin-scoped `agent_type` trap is live for it.
  `/prawduct:pr` Step 3 instead *waits* for this agent and reads the evidence
  file itself, so no hook keys on this agent's name and there is no matcher to
  get wrong. `test_the_skill_waits_rather_than_relying_on_a_hook` pins the half
  of that which is a real contract. If a hook is ever added for this agent, port
  that class with it — the trap applies unchanged.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
AGENT_DEF = PLUGIN / "agents" / "pr-reviewer.md"
PROTOCOL = PLUGIN / "skills" / "pr" / "review-protocol.md"
SKILL = PLUGIN / "skills" / "pr" / "SKILL.md"


def _step3_of(skill_text: str) -> str:
    """Step 3 alone — the dispatch template's span. Bound to the smallest
    region carrying the behaviour: a match anywhere in `SKILL.md` would be
    satisfied by Step 2's prose about the base, which is not what the reviewer
    is handed."""
    return skill_text[skill_text.index("### Step 3"):skill_text.index("### Step 4")]


def _frontmatter(path: Path) -> str:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m is not None, f"{path.name} missing YAML frontmatter"
    return m.group(1)


def _field(frontmatter: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.+)$", frontmatter, re.MULTILINE)
    assert m is not None, f"frontmatter missing `{key}:`"
    return m.group(1).strip()


def _tools(frontmatter: str) -> list[str]:
    """Split the `tools:` list the way the plugin agent schema reads it.

    Commas inside `Bash(...)` are not separators in practice here (no grant uses
    one), but split on top-level commas anyway so a future `Bash(a, b)` does not
    silently produce two malformed entries that every pattern test then passes
    over.
    """
    raw = _field(frontmatter, "tools")
    parts, depth, cur = [], 0, ""
    for ch in raw:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch in ",|" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def _bash_patterns(tools: list[str]) -> list[str]:
    return [t[len("Bash("):-1] for t in tools if t.startswith("Bash(") and t.endswith(")")]


def _admits(patterns: list[str], command: str) -> bool:
    return any(fnmatch.fnmatch(command, pat) for pat in patterns)


class TestAgentDefinitionExists:
    def test_file_exists_at_plugin_agents_dir(self):
        # Auto-discovered from the plugin root's agents/ dir (no plugin.json entry needed).
        assert AGENT_DEF.is_file(), "agents/pr-reviewer.md must exist"

    def test_name_is_pr_reviewer(self):
        # The bare name is the dispatch `subagent_type`; at runtime the agent_type
        # Claude Code reports is the plugin-scoped `prawduct:pr-reviewer`. Nothing
        # in this flow compares against the scoped form (see the module docstring),
        # so only the dispatch name is a contract here.
        assert _field(_frontmatter(AGENT_DEF), "name") == "pr-reviewer"

    def test_has_description(self):
        assert _field(_frontmatter(AGENT_DEF), "description")

    def test_model_is_inherit(self):
        # `/prawduct:pr` Step 3 promises the reviewer runs on the session model.
        # A pinned model here would make that sentence false without touching it.
        assert _field(_frontmatter(AGENT_DEF), "model") == "inherit"


class TestClaudeMdIsOmitted:
    """The ~108KB this agent exists to not be handed.

    Verified against Claude Code 2.1.277 before this agent was written: a
    plugin-supplied agent carrying `omitClaudeMd: true` reported both the
    `CLAUDE.md` hierarchy and `.claude/rules/learnings/core.md` absent from its
    context, while the same agent without the field quoted a heading out of
    `core.md` verbatim.
    """

    def test_the_field_is_present_and_boolean_true(self):
        """By PROPERTY, not by a literal that any rewording satisfies.

        `"omitClaudeMd: true" in body` would pass on a prose sentence mentioning
        the field, on a commented-out line, and on the string `"true"` — none of
        which turns the behaviour on. So: parse the frontmatter, take the value,
        and require it to be the YAML boolean.
        """
        raw = _field(_frontmatter(AGENT_DEF), "omitClaudeMd")
        value = raw.split("#", 1)[0].strip().strip("\"'")
        assert value == "true", (
            f"omitClaudeMd is {raw!r} — only the bare YAML boolean `true` turns "
            "the omission on; a quoted string or a prose mention does not"
        )

    def test_the_field_is_in_the_frontmatter_not_the_body(self):
        """Discriminating: the body DOES discuss the field (that is where the
        reason lives), so a test reading the whole file would pass with the
        frontmatter key deleted."""
        body = AGENT_DEF.read_text().split("---\n", 2)[2]
        assert "omitClaudeMd" in body, (
            "the body should still explain why the omission exists — this test "
            "is only meaningful while it does"
        )
        assert re.search(r"^omitClaudeMd:", _frontmatter(AGENT_DEF), re.MULTILINE)

    def test_every_surface_names_what_the_omission_does_not_cover(self):
        """Measured 2026-09-22 (#888): two reviewer runs received the
        `authoring.md` learnings area file after a Read its `paths:` matched,
        and a control that Read an unmatched path received nothing. Claude Code
        documents no per-agent setting that stops it. Three surfaces had
        claimed the reviewer gets no learnings at all; a reviewer told that
        reads an arriving area file as an instruction it was meant to have.

        Each assertion is bound to the sentence carrying the correction, not
        to the file: `pr-reviewer.md` said "path-scoped" (of `Write`) before
        this change, so a whole-file search could not fail.
        """
        def flat(text: str) -> str:
            return " ".join(text.split())

        body = AGENT_DEF.read_text().split("---\n", 2)[2]
        rest = body[body.index("## What your context does not contain"):]
        end = rest.find("\n## ", 1)
        section = flat(rest if end < 0 else rest[:end])
        assert "its always-loaded `.claude/rules/` project rules" in section
        assert "One kind of rules file still reaches you: a **path-scoped** one" in section
        assert "it is not a checklist to scan the diff against" in section

        step3 = flat(_step3_of(SKILL.read_text()))
        assert "its always-loaded `.claude/rules/` files" in step3
        assert "does not stop a **path-scoped** rules file" in step3

        protocol = flat(PROTOCOL.read_text())
        assert "not given the learnings at dispatch" in protocol
        assert "a path-scoped learnings file can still arrive" in protocol

    def test_the_agent_is_told_not_to_read_around_the_omission(self):
        body = AGENT_DEF.read_text()
        assert "do not reconstruct it from a file you were deliberately not given" in body, (
            "an agent told only that its context is smaller will go and read the "
            "files itself, which restores the cost and the forbidden scan at once"
        )


class TestAgentToolsAreRestricted:
    """The agent-def tools allow-list, which is what a dispatch prompt cannot hold."""

    def _tools(self) -> list[str]:
        return _tools(_frontmatter(AGENT_DEF))

    def test_has_code_analysis_and_write(self):
        tools = self._tools()
        for required in ("Read", "Glob", "Grep", "Write"):
            assert required in tools, f"pr-reviewer must allow {required}"

    def test_no_broad_bash(self):
        tools = self._tools()
        assert "Bash" not in tools, "pr-reviewer must not have unrestricted Bash"
        assert not any(t == "Bash(*)" for t in tools)

    def test_git_is_read_only(self):
        tools = self._tools()
        assert "Bash(git *)" not in tools, (
            "no broad git — the read-only verbs are granted one by one, which "
            "is the intent this file declares; whether a pattern narrows WITHIN "
            "an exposed Bash is the consumer's permission settings' answer"
        )
        for verb in ("Bash(git diff *)", "Bash(git log *)", "Bash(git show *)"):
            assert verb in tools, f"pr-reviewer missing read-only git verb {verb}"

    def test_no_allow_pattern_permits_pytest(self):
        """The negative probe: no Bash allow pattern may match a test run."""
        patterns = _bash_patterns(self._tools())
        for cmd in ("pytest", "python -m pytest", "python3 -m pytest tests/",
                    "cd x && python3 -m pytest"):
            assert not _admits(patterns, cmd), (
                f"an allow pattern would permit `{cmd}` — no grant here may "
                "name a test run. The guarantee is the tool SET (no unrestricted "
                "`Bash` entry); this asserts the declared patterns do not "
                "contradict it"
            )

    def test_the_payload_grant_does_not_reach_its_writer_sibling(self):
        """A Bash grant is a PREFIX match and `pr-review-payload` has a sibling,
        `pr-review-dispatch`, that WRITES. `Bash(prawduct-hook pr-review*)` reads
        as "the PR review commands" and hands a read-only reviewer the writer.

        Asserted as a property of the patterns rather than as the absence of one
        spelling: `"pr-review*" not in frontmatter` passes for
        `Bash(prawduct-hook pr-*)`, which has exactly the same effect.
        """
        patterns = _bash_patterns(self._tools())
        for writer in (
            "prawduct-hook pr-review-dispatch --begin",
            "python3 plugin/bin/prawduct-hook pr-review-dispatch --begin",
        ):
            assert not _admits(patterns, writer), (
                f"an allow pattern admits `{writer}` — that command marks the "
                "dispatch clock and belongs to the caller, never the reviewer"
            )

    def test_the_payload_itself_is_admitted(self):
        """The positive control for the test above. Without it, deleting the
        payload grant entirely would satisfy the writer check and leave the
        reviewer unable to run the one command its protocol opens with."""
        patterns = _bash_patterns(self._tools())
        assert _admits(patterns, "prawduct-hook pr-review-payload"), (
            "the reviewer cannot run `pr-review-payload`, which is step 1 of its "
            "own activation section"
        )

    def test_the_backlog_cache_read_survives_the_narrowing(self):
        """R-2 has no other owner anywhere in the pipeline.

        Scoping an allow-list is where a capability silently disappears, and
        `skills/backlog/cache-reads.md` wrote the warning for exactly this move.
        The payload resolves the ids it can see; this grant is what lets the
        reviewer resolve one it meets inside a diff hunk instead of guessing.
        """
        patterns = _bash_patterns(self._tools())
        for cmd in (
            "prawduct-hook backlog cache-query resolve 249",
            "python3 plugin/bin/prawduct-hook backlog cache-query open",
        ):
            assert _admits(patterns, cmd), (
                f"the narrowed allow-list no longer admits `{cmd}` — a reviewer "
                "that cannot read the backlog reports 'reconciled' having "
                "reconciled nothing"
            )

    def test_the_grants_admit_the_git_dash_C_form_the_file_mandates(self):
        """The grant and the instruction have to agree, and they did not.

        Both files tell the reviewer every git call is `git -C <project dir>
        <verb>` — the anchoring that stops a subagent reviewing the primary
        checkout — while the grants read `Bash(git <verb> *)`, which does not
        match a command whose second token is `-C`. On a consumer that actually
        enforces its allow-list, every mandated call is the one shape not
        granted: the reviewer is stopped at the first read, or worse, quietly
        does the un-anchored thing that IS granted and reviews the wrong tree.
        Discriminating by construction — the asserted command carries `-C`, so
        the old grants fail it and the new ones pass.
        """
        patterns = _bash_patterns(self._tools())
        for verb in ("diff", "log", "show"):
            cmd = f"git -C /abs/project {verb} origin/develop...HEAD"
            assert _admits(patterns, cmd), (
                f"the allow-list does not admit {cmd!r}, which this agent "
                f"definition requires the reviewer to run"
            )
        # The un-anchored form stays granted too: the caller may dispatch into a
        # cwd that IS the project, and removing it would trade one gap for another.
        assert _admits(patterns, "git diff origin/develop...HEAD")

    def test_no_network_tool(self):
        """The payload carries the default branch, so the reviewer needs no `gh`
        — and a release reviewer that can reach the network is a reviewer whose
        findings depend on something outside the tree it was dispatched against."""
        tools = self._tools()
        assert "WebFetch" not in tools and "WebSearch" not in tools
        assert not _admits(_bash_patterns(tools), "gh pr view 1 --json headRefOid")


class TestAgentWritesOnlyItsEvidenceFile:
    def test_directs_the_callers_exact_path(self):
        body = AGENT_DEF.read_text()
        assert "verbatim" in body
        assert "Do not\n  compute a filename" in body or "do not\n  compute a filename" in body.lower()

    def test_forbids_a_second_write(self):
        body = AGENT_DEF.read_text()
        assert "exactly one file" in body
        assert ".prawduct/" in body  # named in a "do not touch" instruction
        assert "not path-scoped" in body, (
            "the agent must be told its Write is unscoped and its contract is "
            "what binds — otherwise 'one file' reads as a guarantee it has"
        )


class TestReviewerAnchorsToTheDispatchedTree:
    """A reviewer must resolve every path against the directory it was sent to.

    Ported wholesale from the Critic reviewer's pins, because the failure is
    identical and does not care which review it is: a subagent does not inherit
    the caller's cwd, so in a worktree session a relative path resolves into the
    primary checkout — a different tree, on a different branch — and the review
    comes back clean. The failure mode is a pass, which is invisible.
    """

    def test_agent_is_told_its_cwd_is_not_the_project_directory(self):
        body = AGENT_DEF.read_text()
        assert "not necessarily your cwd" in body
        assert "primary checkout" in body

    def test_agent_requires_git_dash_c_on_git_calls(self):
        body = AGENT_DEF.read_text()
        assert body.count("git -C") >= 2, (
            "the agent definition must require `git -C <project dir>`; a bare git "
            "verb answers for whichever tree the subagent process started in"
        )

    def test_agent_reconciles_the_payload_against_the_prompt_on_a_discriminating_fact(self):
        """The payload answers about SOME tree. Two answers for one fact is a
        disagreement worth surfacing, not one to silently pick from.

        **Contract renegotiated, in the open (cumulative R-1/R-9).** This pinned
        the base BRANCH as the reconciled fact, and both halves have since moved:
        the base cannot discriminate (a worktree and its primary checkout resolve
        the same name, which is precisely the wrong-tree case the cross-check
        exists for), and the payload now reports the project directory and HEAD
        it actually answered about. So the pin is the same property over the
        operand that can actually differ — and it stays a BOTH-OR-NEITHER, which
        is what caught the earlier regression: a cross-check with one operand
        cannot fire, and its failure mode is a silent pass.
        """
        body = AGENT_DEF.read_text()
        assert "If either disagrees" in body, (
            "the agent must be told to surface a payload/prompt disagreement "
            "rather than pick one"
        )
        reconciles = "project dir" in body and "HEAD" in body
        step3 = _step3_of(SKILL.read_text())
        prompt_carries_the_directory = "(absolute)" in step3
        assert reconciles == prompt_carries_the_directory, (
            "the agent's cross-check and Step 3's dispatch prompt are two halves "
            f"of one check: the agent reconciles dir/HEAD ({reconciles}) while "
            f"the prompt carries an absolute directory "
            f"({prompt_carries_the_directory})"
        )

    def test_the_agent_is_told_to_pass_the_directory_not_assume_it(self):
        """The fix R-1/R-9 asked for, and the half a prose-only rewrite would
        miss: the agent holds no `cd` grant, and `pr-review-payload` resolves
        `CLAUDE_PROJECT_DIR` — the LAUNCH dir — before its own cwd. So "run it
        from that directory" was an act the tool set cannot perform."""
        body = AGENT_DEF.read_text()
        # Bound to each SECTION that carries it, not to the file. The file
        # states the mandate twice for two readers — the anchoring rules a
        # reviewer follows before touching anything, and the per-tool notes it
        # consults while working — and a file-wide `in body` is satisfied by
        # either one, so it went green when a mutation reverted the anchoring
        # bullet alone. A mutation sweep found that; reading it did not.
        anchoring = body[body.index("## The project directory is not necessarily your cwd"):
                         body.index("## Your tools, and what each is for")]
        tools = body[body.index("## Your tools, and what each is for"):
                     body.index("## What your context does not contain")]
        for section, where in ((anchoring, "the anchoring rules"), (tools, "the tool notes")):
            assert "pr-review-payload <project dir>" in section, (
                f"{where} no longer tell the reviewer to PASS the directory. "
                "Without the argument the payload can answer about the primary "
                "checkout while the reviewer's `-C` diff reads a worktree — and "
                "it reads clean, which is the silent pass this file's own "
                "premise is written against"
            )
        tools = _frontmatter(AGENT_DEF)
        assert "Bash(prawduct-hook pr-review-payload *)" in tools, (
            "the argument form is mandated by the prose and must be granted, or "
            "the reviewer meets a refusal on its first read"
        )

    def test_the_skill_passes_an_absolute_project_directory(self):
        """The agent definition alone does not bind a reviewer whose prompt
        overrides it — the dispatch template has to carry it too."""
        skill = SKILL.read_text()
        step3 = skill[skill.index("### Step 3"):skill.index("### Step 4")]
        assert "(absolute)" in step3
        assert "never your cwd" in step3


class TestTheSkillDispatchesThisAgent:
    def _step3(self) -> str:
        skill = SKILL.read_text()
        return skill[skill.index("### Step 3"):skill.index("### Step 4")]

    def test_the_dispatch_names_the_agent_type(self):
        assert "subagent_type: pr-reviewer" in self._step3(), (
            "Step 3 must dispatch the named agent — a generic subagent inherits "
            "CLAUDE.md and the project rules regardless of what this file says"
        )

    def test_the_skill_waits_rather_than_relying_on_a_hook(self):
        """Why no `SubagentStop` matcher exists for this agent (module docstring).

        The caller waits and reads the evidence file itself. That is a contract:
        if it ever stops waiting, the evidence is read before it is written and
        the gate at Step 4 passes on a stale file from a previous review.
        """
        step3 = self._step3()
        assert "**Wait for the agent to complete.**" in step3
        assert "If the file does not exist, the review did not complete" in step3

    def test_the_skill_states_why_the_agent_is_named(self):
        step3 = self._step3()
        assert "omitClaudeMd" in step3, (
            "the reason the dispatch changed shape has to be where the dispatch "
            "is, or the next editor 'simplifies' it back to a generic agent"
        )
