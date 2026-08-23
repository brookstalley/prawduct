"""Every `prawduct-hook` command a skill tells you to RUN is one it may run.

The failure this pins is quiet and consumer-only. A skill's `allowed-tools` is a
pure-allow list; a command outside it is not something the skill can invoke
without leaving its grant. In THIS repo the gap is invisible, because the two
skills with a broad `Bash(python3 *)` interpreter grant reach
`python3 plugin/bin/prawduct-hook` — the plugin is in the tree here. In a
governed product the plugin is installed elsewhere and the bare `prawduct-hook`
spelling, which is the one every SKILL.md writes, is the only one that works.
`skills/janitor/SKILL.md` already records exactly this reasoning for granting
`backlog cache-query` despite its interpreter grant; this test generalises it.

Found by hand while scrubbing the artifact-lifecycle branch: the archival work
gave doctor, janitor and pr each an `archive-plan` instruction and granted it to
none of them — and doctor's own edit had added the two sibling commands, so the
list was being maintained, just not completely. Four older instances were found
in the same sweep. Prose review had not caught any of them in either direction,
which is the argument for a mechanical check rather than a resolution to be
careful.

**Existing skill-metadata tests guard OVER-permission** (the Critic must not be
able to run pytest — `test_critic_skill_metadata.py`). This is the other
direction, and the two are not substitutes: a skill that cannot run what it
instructs fails silently, by prompting, at the moment a consumer needs it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


SKILLS_DIR = Path(__file__).resolve().parents[1] / "plugin" / "skills"

#: `prawduct-hook <command>` anywhere. Subcommand families (`backlog pick`,
#: `advisory list`, `evidence status`) are matched at their FIRST word only —
#: grants are written per family (`Bash(prawduct-hook backlog *)`), so the family
#: name is the unit that has to appear.
#: The separator is ANY run of whitespace, not a literal space. Prose wraps, and
#: a `prawduct-hook` that ended one line with its subcommand on the next was
#: invisible to this guard — so a skill instructing an ungranted command read as
#: clean purely because of where the line broke. Found in `migrate/SKILL.md`,
#: whose `test-evidence` cross-reference wrapped exactly there while doctor's
#: identical mention (on one line) was caught. A guard whose coverage depends on
#: line width is indistinguishable from one that passed.
_INVOCATION_RE = re.compile(r"prawduct-hook\s+([a-z][a-z0-9-]*)")

#: The same family name, but only where the grant writes the BARE ``prawduct-hook``
#: spelling. ``python3 plugin/bin/prawduct-hook <sub>`` is a different grant covering
#: a different command string, and only one of the two is portable: in a governed
#: product the plugin is installed outside the repo, so ``plugin/bin/prawduct-hook``
#: is not a path that exists there and the bare spelling is the only one that runs.
#: Reading both spellings as "granted" — which a pattern without this lookbehind
#: does — lets a skill hold only the self-hosted half and still read as covered.
_BARE_GRANT_RE = re.compile(r"(?<![\w/-])prawduct-hook\s+([a-z][a-z0-9-]*)")

#: The self-hosted spelling: reaches the hook through the in-tree checkout. Optional
#: — a skill is free to grant only the bare form — but never sufficient on its own.
_SELF_HOSTED_GRANT_RE = re.compile(r"bin/prawduct-hook\s+([a-z][a-z0-9-]*)")

#: A ``gh`` grant, captured with whatever follows the executable inside the parens.
#: ``(?![\w-])`` keeps it off ``ghost``-shaped names.
_GH_GRANT_RE = re.compile(r"Bash\(gh(?![\w-])([^)]*)\)")

#: What a scoped ``gh`` grant looks like: whitespace, then a subcommand family.
_GH_SCOPED_RE = re.compile(r"^\s+[a-z][a-z0-9-]*\b")

#: Commands a skill NAMES but is deliberately not granted. Every entry is a
#: decision with a reason, not a suppression: the whole value of this test is
#: that adding a row is uncomfortable enough to make you check.
#:
#: Two shapes qualify, and nothing else does:
#:   * a CROSS-REFERENCE — the text describes what some *other* flow runs, so
#:     granting it would hand this skill a capability it has no business with;
#:   * a DELIBERATE EXCLUSION — the skill's own protocol states that it must not
#:     run the command, and the missing grant is the mechanism enforcing that.
_NOT_GRANTED: dict[tuple[str, str], str] = {
    # Deliberate exclusion, stated in the Critic's own protocol: "what happens
    # to a completed review's findings — discarded, or brought back — is an
    # operator decision and belongs to the main session, which is why both are
    # absent from your `allowed-tools`."
    ("critic", "critic-discard"): "operator decision, not the reviewer's",
    ("critic", "critic-restore"): "operator decision, not the reviewer's",
    # Deliberate exclusion, and load-bearing: an independent reviewer must never
    # mutate the session it is reviewing. `clear` appears only as the thing the
    # critic-active marker REFUSES.
    ("critic", "clear"): "the review must not mutate the session it reviews",
    # Cross-reference: doctor explains that `init-product`'s starter corpus wrote
    # a marker, and points at `/prawduct:onboard` for onboarding. Doctor covers
    # already-onboarded repos and must not scaffold one.
    ("doctor", "init-product"): "narrative; onboarding belongs to /prawduct:onboard",
    # Cross-reference, and a grant here would be actively wrong: doctor names the
    # evidence store as where a real test count lives, so an operator dropping the
    # hand-maintained `build_state.test_tracking` knows what to read instead.
    # Recording evidence RUNS the product's suite — doctor reports and guides, and
    # never executes the product's own tooling.
    ("doctor", "test-evidence"): "pointer to where the real count lives; recording "
    "it would run the product's suite, which doctor must not do",
    # Same cross-reference, same reason, in the sibling flow: migrate names the
    # evidence store as what to read instead of the hand-maintained count it
    # removes. The cutover runs no test suite. This row was missing while the
    # invocation pattern required a literal space — the mention wrapped across
    # two lines and no one, including the guard, could see it.
    ("migrate", "test-evidence"): "pointer to where the real count lives; the "
    "cutover runs no test suite",
    # Cross-reference: names what the RELEASE CHECKLIST runs when gitflow
    # retention ends. The PR flow archives one plan by name; a fleet sweep is
    # not its to run.
    ("pr", "plan-backfill"): "cross-reference to the release checklist",
}


def _skill_files() -> list[Path]:
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _frontmatter_grant(text: str) -> str | None:
    match = re.search(r"^allowed-tools:(.*)$", text, re.M)
    return match.group(1) if match else None


def test_the_sweep_has_subjects() -> None:
    """A green assert-absent test proves nothing if it swept an empty set."""
    files = _skill_files()
    assert len(files) >= 8, f"only {len(files)} skills found"
    assert any(_frontmatter_grant(p.read_text(encoding="utf-8")) for p in files)


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_every_instructed_command_is_granted(skill_path: Path) -> None:
    name = skill_path.parent.name
    text = skill_path.read_text(encoding="utf-8")
    grant = _frontmatter_grant(text)
    if grant is None:
        pytest.skip(f"{name} declares no allowed-tools (unrestricted)")

    granted = set(_BARE_GRANT_RE.findall(grant))
    body = text[text.index(grant) + len(grant) :]
    missing = sorted(
        command
        for command in set(_INVOCATION_RE.findall(body))
        if command not in granted and (name, command) not in _NOT_GRANTED
    )
    assert not missing, (
        f"skills/{name}/SKILL.md tells its reader to run "
        f"{', '.join('prawduct-hook ' + c for c in missing)} but does not grant "
        f"{'it' if len(missing) == 1 else 'them'} in allowed-tools. In a governed "
        f"product the bare `prawduct-hook` spelling is the only one that works, so "
        f"the skill will prompt at exactly the moment it is needed. Add the grant, "
        f"or — if the text is a cross-reference to another flow, or the command is "
        f"one this skill must NOT run — add it to _NOT_GRANTED with the reason."
    )


def test_no_stale_exemptions() -> None:
    """An exemption outlives the sentence that earned it.

    A row here is a standing claim that some skill still names some command. If
    the mention goes away the row must go too — otherwise the list slowly
    becomes a place where a real grant can hide.
    """
    stale = []
    for (name, command), reason in _NOT_GRANTED.items():
        path = SKILLS_DIR / name / "SKILL.md"
        if not path.is_file():
            stale.append((name, command, "skill no longer exists"))
            continue
        if command not in _INVOCATION_RE.findall(path.read_text(encoding="utf-8")):
            stale.append((name, command, f"no longer mentioned ({reason})"))
    assert not stale, f"stale _NOT_GRANTED rows: {stale}"


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_a_self_hosted_hook_grant_never_stands_alone(skill_path: Path) -> None:
    """Granting only ``python3 plugin/bin/prawduct-hook <sub>`` covers the wrong repo.

    The two spellings are not interchangeable and only one of them is portable. A
    governed product installs the plugin outside its own tree, so nothing there
    answers to ``plugin/bin/prawduct-hook`` and the bare name is the only command
    string that resolves. Granting the self-hosted spelling alone therefore covers
    exactly the checkout where the framework is developed and none of the repos it
    governs — and the failure is a permission prompt at the moment a consumer needs
    the command, which is invisible to anyone dogfooding.

    The reverse is allowed on purpose: a bare grant with no self-hosted sibling is a
    skill that runs everywhere the plugin is installed, which is the normal case.
    """
    name = skill_path.parent.name
    grant = _frontmatter_grant(skill_path.read_text(encoding="utf-8"))
    if grant is None:
        pytest.skip(f"{name} declares no allowed-tools (unrestricted)")

    bare = set(_BARE_GRANT_RE.findall(grant))
    orphaned = sorted(set(_SELF_HOSTED_GRANT_RE.findall(grant)) - bare)
    assert not orphaned, (
        f"skills/{name}/SKILL.md grants "
        f"{', '.join('python3 plugin/bin/prawduct-hook ' + c for c in orphaned)} "
        f"with no bare `prawduct-hook` sibling. That path does not exist in a "
        f"governed product, so the grant covers only this checkout. Add "
        f"{', '.join('Bash(prawduct-hook ' + c + ' *)' for c in orphaned)}."
    )


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_a_gh_grant_names_the_subcommand_it_needs(skill_path: Path) -> None:
    """``Bash(gh *)`` is the whole GitHub CLI, not the part a skill uses.

    A grant is a security boundary whose only enforcement is the text of one line.
    ``gh`` reaches everything the ambient token can reach — issues, releases, repo
    settings, secrets, arbitrary REST and GraphQL through ``gh api``, and every
    repository the token is scoped to, not just this one. A skill that opens PRs
    needs ``gh pr`` and nothing else, so the wildcard buys no capability it uses
    and gives up the whole boundary.

    Asserted over every skill rather than over the one that has the grant today:
    the failure mode is a future edit widening a narrowed grant back, and a check
    that names the site cannot see that happen anywhere else.
    """
    name = skill_path.parent.name
    grant = _frontmatter_grant(skill_path.read_text(encoding="utf-8"))
    if grant is None:
        pytest.skip(f"{name} declares no allowed-tools (unrestricted)")

    unscoped = [
        f"Bash(gh{tail})"
        for tail in _GH_GRANT_RE.findall(grant)
        if not _GH_SCOPED_RE.match(tail)
    ]
    assert not unscoped, (
        f"skills/{name}/SKILL.md grants {', '.join(unscoped)} — the entire GitHub "
        f"CLI against every repo the token reaches. Name the subcommand family the "
        f"skill actually runs, e.g. `Bash(gh pr *)`."
    )


MIGRATION_SCRUB = SKILLS_DIR / "backlog" / "migration-scrub.md"

#: ``--repo`` followed by an argument. A backticked mention of the flag alone
#: (``` `--repo` is required ``` ) has no whitespace after it and is not matched.
_REPO_FLAG_RE = re.compile(r"--repo\s+(\S+)")

#: The one placeholder the runbook binds. Trailing backtick and comma are prose.
_BOUND_TARGET = "<target>"


def test_the_migration_runbook_never_re_derives_its_target_repo() -> None:
    """Every ``--repo`` in the migration runbook takes the value bound at Step 0.

    The runbook migrates a product's whole backlog onto a GitHub repo, and its
    Step 0 exists to make the operator name that repo once, on the record, with the
    owner confirming it. Everything after that is written ``--repo <target>`` so the
    reader substitutes one value in one place. A second placeholder spelling — a
    bare ``<owner>/<repo>``, or a literal repo — invites the reader to re-derive the
    destination halfway through a migration that is already writing issues, and the
    two answers can differ without anything noticing: the commands succeed, against
    the wrong repository.

    A literal repository name is worse still. This runbook ships to every product
    that adopts the backlog service, so a concrete ``owner/name`` in it is one
    product's repo handed to all the others as a default.
    """
    text = MIGRATION_SCRUB.read_text(encoding="utf-8")
    unbound = sorted(
        {
            arg
            for arg in _REPO_FLAG_RE.findall(text)
            if arg.rstrip("`,.);") != _BOUND_TARGET
        }
    )
    assert not unbound, (
        f"{MIGRATION_SCRUB.name} passes --repo values other than `{_BOUND_TARGET}`: "
        f"{', '.join(unbound)}. Step 0 binds the destination once and every later "
        f"step reuses that binding; a second spelling is a second chance to name a "
        f"different repo."
    )


def test_the_cutover_scalar_reuses_the_bound_target() -> None:
    """The scalar that makes the migration live names the same value as the flags.

    ``backlog_service_repo`` is what repoints the session briefing and retires the
    markdown-premise advisories, so it is the switch that declares the migration
    real. Writing it with any spelling other than the bound one would let an
    operator flip the product onto a repo the import never wrote to — the failure
    is a live backlog pointed at an empty repository.
    """
    text = MIGRATION_SCRUB.read_text(encoding="utf-8")
    assert f"backlog_service_repo: {_BOUND_TARGET}" in text, (
        f"{MIGRATION_SCRUB.name}'s cutover scalar must be written "
        f"`backlog_service_repo: {_BOUND_TARGET}` — the same binding every "
        f"`--repo` in the runbook uses."
    )


def test_the_repo_binding_sweep_has_subjects() -> None:
    """The two assertions above are assert-absent; an unread file passes both."""
    text = MIGRATION_SCRUB.read_text(encoding="utf-8")
    assert len(_REPO_FLAG_RE.findall(text)) >= 5, (
        "the migration runbook stopped carrying --repo invocations — either the "
        "runbook moved or the extractor stopped matching"
    )


@pytest.mark.parametrize(
    "grant",
    [
        " Bash(gh *), Read",
        " Read, Bash(gh:*)",
        " Bash(gh)",
    ],
)
def test_an_unscoped_gh_grant_is_recognised(grant: str) -> None:
    """The gh rule pins a narrowing that already shipped, so nothing in the tree can
    demonstrate it has teeth. These do: each is a spelling of "the whole CLI"."""
    assert [t for t in _GH_GRANT_RE.findall(grant) if not _GH_SCOPED_RE.match(t)]


@pytest.mark.parametrize("grant", [" Bash(gh pr *)", " Bash(gh issue view *)"])
def test_a_scoped_gh_grant_is_accepted(grant: str) -> None:
    """And the complement — naming a subcommand family is what the rule asks for."""
    assert not [t for t in _GH_GRANT_RE.findall(grant) if not _GH_SCOPED_RE.match(t)]


def test_a_self_hosted_only_grant_is_recognised() -> None:
    """The bare/self-hosted split is invisible to a pattern that reads both spellings
    as one, which is how a grant covering only this checkout reads as covered."""
    grant = " Bash(python3 plugin/bin/prawduct-hook review-stats *), Read"
    assert set(_SELF_HOSTED_GRANT_RE.findall(grant)) == {"review-stats"}
    assert not set(_BARE_GRANT_RE.findall(grant))
    assert set(_INVOCATION_RE.findall(grant)) == {"review-stats"}, (
        "the pre-existing pattern reads the self-hosted spelling as a bare grant — "
        "that conflation is what the bare pattern exists to break"
    )
