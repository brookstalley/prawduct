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


REPO_ROOT = Path(__file__).resolve().parents[1] / "plugin"

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
            "Bash(prawduct-hook infer-critic-mode*)",
        ]
        allowed = _extract_allowed_tools(_PLUGIN_CRITIC_SKILL.read_text())
        for tool in expected:
            assert tool in allowed, (
                f"{_PLUGIN_CRITIC_SKILL.relative_to(REPO_ROOT)} dropped legitimate "
                f"tool `{tool}` from allowed-tools"
            )

    def test_verify_chunk_refs_grant_is_retired(self):
        """`verify-chunk-refs` left this list on purpose, not by accident.

        The chunk-deliverable check now runs at DISPATCH (`critic-begin`
        computes it into the manifest's `record_lint` block), and
        `review-protocol.md` tells reviewers to read that result rather than
        re-derive it. A standing grant for a command no instruction issues is a
        mechanism's name outliving its mechanism — and re-running it by hand is
        precisely the duplicated work the dispatch-time move removed. The
        assertion is here rather than the entry merely being deleted above so a
        future re-add has to argue with a stated decision instead of silently
        restoring a line that looks like an oversight."""
        allowed = _extract_allowed_tools(_PLUGIN_CRITIC_SKILL.read_text())
        assert "verify-chunk-refs" not in allowed
        assert "critic-begin" in allowed, "dispatch is where the check now runs"

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



class TestExplicitModeArgContract:
    """CRT-2N7V: Skill-tool invocation of a fork-context skill does not
    substitute `$ARGUMENTS` (anthropics/claude-code#34164), so the SKILL must
    never parse the placeholder itself — it forwards whatever arguments were
    delivered to `prawduct-hook infer-critic-mode`, which owns the full
    precedence (explicit token > plan-override > inference) and returns
    rationale `explicit-args` for a recognized forwarded token. These pins
    keep the prose contract from regressing to self-parsing."""

    def test_exactly_one_substitution_placeholder(self):
        """One labeled placeholder line. More would garble sentences when
        substitution DOES fire (all occurrences are replaced — a precedence
        parenthetical containing the placeholder once read 'explicit `chunk`'
        after substitution); zero would switch delivery to the auto-append
        path, whose fork behavior is unverified."""
        content = _PLUGIN_CRITIC_SKILL.read_text()
        assert content.count("$ARGUMENTS") == 1
        assert '**Invocation arguments:** "$ARGUMENTS"' in content

    def test_step1_forwards_to_helper_not_self_parses(self):
        content = _PLUGIN_CRITIC_SKILL.read_text()
        # The forwarding instruction and the helper invocation are present...
        assert "infer-critic-mode <args" in content
        assert "Do NOT interpret the arguments yourself" in content
        # ...and the known harness limitation travels with the contract.
        assert "34164" in content
        # The old self-parse instruction must not return: the only line
        # mentioning the placeholder is the labeled one (asserted above), so
        # an "If `$ARGUMENTS` contains a recognized mode token" revival would
        # bump the count and fail test_exactly_one_substitution_placeholder.

    def test_helper_wildcard_still_in_allowed_tools(self):
        """Forwarding needs the wildcarded allow entry — the bare
        `Bash(prawduct-hook infer-critic-mode)` form would reject the
        argument-carrying invocation.

        The star is attached to the command word with NO space: #730 made the
        spaced form (`infer-critic-mode *`) stop covering a BARE call, and the
        skill instructs one. The house grant form is written down in
        tests/test_skill_command_grants.py's module docstring; this pin follows
        it rather than restating a second convention."""
        allowed = _extract_allowed_tools(_PLUGIN_CRITIC_SKILL.read_text())
        assert "Bash(prawduct-hook infer-critic-mode*)" in allowed


_PLUGIN_REVIEW_PROTOCOL = REPO_ROOT / "skills" / "critic" / "review-protocol.md"


class TestCoordinatorDispatchIsConcurrent:
    """The three coordinator reviewers must be dispatched in one message.

    They are independent by construction — disjoint goals, per-role partial
    files, and the protocol forbids resuming to aggregate — so serial dispatch
    pays the pattern's whole cost (three agents, three context loads, a
    consolidation step) and discards the wall-clock saving that is the only
    thing it buys.

    This was never specified: the framework relied on the harness's ambient
    "batch independent calls" behaviour, which is outside its control and has
    been observed to differ between sessions. An unpinned instruction is how it
    silently reverts, so both dispatch surfaces are asserted.
    """

    def test_review_protocol_step_2_demands_one_message(self):
        content = _PLUGIN_REVIEW_PROTOCOL.read_text()
        assert "ONE message" in content
        assert "concurrently" in content

    def test_skill_routing_bullet_demands_one_message(self):
        content = _PLUGIN_CRITIC_SKILL.read_text()
        assert "in a single message so they run concurrently" in content


# =============================================================================
# Every mandated hook subcommand is granted on every surface that mandates it
# =============================================================================

_PLUGIN_CRITIC_REVIEWER = REPO_ROOT / "agents" / "critic-reviewer.md"

#: The Critic's instruction surfaces, mapped to the grant list(s) that bind the
#: agent that READS each one. This mapping is the substance of the check: a
#: mandate is only runnable if it is granted on the surface whose reader meets
#: it, and the Critic has two readers with two different grant lists.
#:
#:   * the fork (`SKILL.md`'s `allowed-tools`) reads `SKILL.md`, `goals-1-3.md`,
#:     `review-cycle.md`, `framework-checks.md`, and - in single-pass
#:     `final`/`cumulative` - `review-protocol.md`;
#:   * the dispatched `critic-reviewer` subagent (`critic-reviewer.md`'s
#:     `tools:`) reads `review-protocol.md` and its own definition.
#:
#: `review-protocol.md` therefore binds BOTH, which is the case the original
#: defect lived in: its Goal 1 `verify-coverage` mandate was granted to neither.
_SURFACE_GRANTS: dict[str, tuple[Path, ...]] = {
    "skills/critic/SKILL.md": (_PLUGIN_CRITIC_SKILL,),
    "skills/critic/goals-1-3.md": (_PLUGIN_CRITIC_SKILL,),
    "skills/critic/review-cycle.md": (_PLUGIN_CRITIC_SKILL,),
    "skills/critic/framework-checks.md": (_PLUGIN_CRITIC_SKILL,),
    "skills/critic/review-protocol.md": (_PLUGIN_CRITIC_SKILL, _PLUGIN_CRITIC_REVIEWER),
    "agents/critic-reviewer.md": (_PLUGIN_CRITIC_REVIEWER,),
}

#: A mandate this surface issues that the named grant list deliberately withholds.
#: Keyed by (surface, grant-list stem, subcommand); the value is the reason, and
#: adding a row is meant to be uncomfortable enough to make you check.
_MANDATE_NOT_GRANTED: dict[tuple[str, str, str], str] = {
    # `review-protocol.md`'s consolidate instruction is explicitly labelled
    # "single-pass only - coordinator reviewers get this schema from their agent
    # definition", and that definition tells the dispatched reviewer the exact
    # opposite: "do NOT run `prawduct-hook critic-consolidate`". The missing grant
    # IS that rule's enforcement - a reviewer that could consolidate could persist
    # a review from three partials of which only one exists.
    ("skills/critic/review-protocol.md", "critic-reviewer", "critic-consolidate"): (
        "single-pass only; a dispatched reviewer must never consolidate"
    ),
    # `review-cycle.md` prints this inside the NOTE text the Critic hands the
    # BUILDER when backlog reconciliation is unavailable. It is remedy prose the
    # operator runs, and granting it would give a read-only review a network write.
    ("skills/critic/review-cycle.md", "critic", "backlog sync"): (
        "remedy text reported to the builder, never run by the review"
    ),
}

#: "run `prawduct-hook <sub>`" - the imperative that makes a subcommand a mandate.
#: Matched on the whitespace-normalised text (prose wraps mid-command) and only
#: within a short window after the verb, so a table cell reading "**Goals run**"
#: does not adopt every command later in the same row. 90 characters is the
#: measured setting: it reaches the second command of a chained mandate ("run
#: `... classify-diff-risk` for the tier, then `... critic-begin`") and stops
#: short of the next unrelated one (at 120 a `check-cumulative-critic` mention
#: two clauses away in `review-cycle.md` gets adopted).
_MANDATE_WINDOW = 90
_RUN_RE = re.compile(r"\brun\b", re.IGNORECASE)
_NEGATED_RE = re.compile(r"(?:\b(?:not|never|n't|neither)\s+|\brefuses?\s+to\s+)$", re.I)
_HOOK_CALL_RE = re.compile(r"`prawduct-hook ([a-z][a-z0-9-]*(?: [a-z][a-z0-9-]*)?)")


def _mandated_subcommands(text: str) -> set[str]:
    """Every `prawduct-hook` subcommand this surface tells its reader to RUN.

    A negated verb ("do NOT run", "refuses to run") is not a mandate - those are
    the prohibitions the grant lists enforce by omission, and reading them as
    mandates would invert the check.
    """
    flat = " ".join(text.split())
    found: set[str] = set()
    for m in _RUN_RE.finditer(flat):
        if _NEGATED_RE.search(flat[: m.start()]):
            continue
        end = m.end() + _MANDATE_WINDOW
        # Never cut a command in half: a window boundary that lands mid-token
        # turns `verify-coverage` into a subcommand named `verify-cover`, which
        # is ungranted everywhere and would be reported as the gap.
        while end < len(flat) and flat[end] not in " `":
            end += 1
        found.update(_HOOK_CALL_RE.findall(flat[m.end() : end]))
    return found


def _granted_subcommands(grant_line: str) -> set[str]:
    """Bare-spelling `prawduct-hook` grants, as their subcommand words.

    Only the bare spelling counts: in a governed product the plugin is installed
    outside the repo, so `python3 plugin/bin/prawduct-hook ...` names a path that
    does not exist there and the bare form is the only string that resolves.
    """
    out: set[str] = set()
    for m in re.finditer(r"(?<![\w/-])prawduct-hook\s+([^)]*)\)", grant_line):
        # Both grant spellings reduce to the same subcommand words. The house
        # form (#730) attaches the star to the last command word with no space
        # -- `infer-critic-mode*` -- so the star is grant syntax, not part of
        # the command name, and has to come off before the word is matched.
        # Reading it as a name silently drops the grant and reports the
        # subcommand as ungranted, which is exactly what it did.
        words = [
            stripped
            for w in m.group(1).split()
            if re.fullmatch(r"[a-z][a-z0-9-]*", (stripped := w.rstrip("*")))
        ]
        if words:
            out.add(" ".join(words))
    return out


def _grant_line(path: Path) -> str:
    text = path.read_text()
    m = re.search(r"^(?:allowed-tools|tools):\s*(.+)$", text, re.MULTILINE)
    assert m is not None, f"{path.name} declares no tool grant"
    return m.group(1).strip()


def test_mandated_hook_subcommands_are_granted_on_every_binding_surface():
    """A BLOCKING check the protocol mandates must be runnable by the agent it
    is mandated to.

    The instance this generalises: `review-protocol.md` and `goals-1-3.md` both
    grade `prawduct-hook verify-coverage` **BLOCKING per missing file** and say
    the wording "must not be softened" - while neither the fork's
    `allowed-tools` nor the dispatched reviewer's `tools:` granted it. The
    reviewer meets a mandatory command it cannot issue, and the only outcomes
    are a permission prompt in a subagent that cannot answer one, or a
    silently-skipped blocking check. Either way the finding is never made, and
    nothing anywhere goes red.

    The converse direction has been pinned since Chunk 13
    (`test_no_allow_pattern_permits_pytest`, `test_verify_chunk_refs_grant_is_retired`):
    a grant with no instruction behind it is a mechanism's name outliving its
    mechanism. This is the missing half - an instruction with no grant behind it.
    """
    gaps = []
    for surface, grant_paths in _SURFACE_GRANTS.items():
        surface_path = REPO_ROOT / surface
        mandated = _mandated_subcommands(surface_path.read_text())
        for grant_path in grant_paths:
            stem = (
                grant_path.parent.name if grant_path.name == "SKILL.md" else grant_path.stem
            )
            granted = _granted_subcommands(_grant_line(grant_path))
            for sub in sorted(mandated):
                if (surface, stem, sub) in _MANDATE_NOT_GRANTED:
                    continue
                family = sub.split(" ")[0]
                if sub in granted or family in granted:
                    continue
                gaps.append(
                    f"{surface} mandates `prawduct-hook {sub}`, "
                    f"ungranted in {grant_path.name}"
                )
    assert not gaps, (
        "a Critic instruction surface mandates a `prawduct-hook` subcommand its "
        "reader is not granted:\n  " + "\n  ".join(gaps) + "\n"
        "Grant it in that surface's binding tool list (the bare `prawduct-hook` "
        "spelling - the self-hosted one does not exist in a governed product), "
        "demote the instruction so it is no longer a mandate, or add a "
        "_MANDATE_NOT_GRANTED row with the reason."
    )


def test_the_mandate_sweep_has_subjects():
    """A green assert-absent test proves nothing if it swept an empty set."""
    per_surface = {
        s: _mandated_subcommands((REPO_ROOT / s).read_text()) for s in _SURFACE_GRANTS
    }
    assert sum(len(v) for v in per_surface.values()) >= 8, per_surface
    assert "verify-coverage" in per_surface["skills/critic/review-protocol.md"], (
        "the mandate this test was written for is no longer detected - either "
        "Goal 1's symbol-coverage check moved, or the detector stopped seeing it"
    )
    assert "verify-coverage" in per_surface["skills/critic/goals-1-3.md"]


def test_no_stale_mandate_exemptions():
    """An exemption outlives the sentence that earned it."""
    stale = [
        key
        for key in _MANDATE_NOT_GRANTED
        if key[2] not in _mandated_subcommands((REPO_ROOT / key[0]).read_text())
    ]
    assert not stale, f"stale _MANDATE_NOT_GRANTED rows: {stale}"
