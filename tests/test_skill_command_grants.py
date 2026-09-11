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

## The house grant form

Grants are matched as a literal PREFIX of the command string, so where the star
sits decides what a grant covers. This repo writes ONE form, and this module is
where it is defined:

    Bash(prawduct-hook <command words>*)

— the star **attached to the last command word, with no space before it**, and
exactly one grant line per command. It covers the bare call and every argument
form at once. `Bash(prawduct-hook <cmd> *)` — a SPACED star — does not cover a
bare call: its prefix carries the trailing space, so something has to follow it,
and `run prawduct-hook <cmd>` falls through to a permission prompt that nothing
in an unattended run can answer. The old workaround was to write both spellings;
the house form replaces the pair with one line that cannot fall out of step.

The one exception is a command that takes **no arguments at all**
(`test-status`, `resolve-base`, `check-pr-doc-only`): those are granted bare,
`Bash(prawduct-hook <cmd>)`, because a star there would widen the grant past
anything the command can do.

`_covers` enforces the difference, so a starred-only grant paired with a bare
call is now a red test rather than a silent runtime prompt (#730).
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

#: A ``prawduct-hook`` invocation, as the SEQUENCE of subcommand words after the
#: binary — not just the first one. Comparing first tokens alone is what let a
#: group-level call read as granted: `Bash(prawduct-hook backlog list *)` and the
#: instruction `prawduct-hook backlog --help` both reduce to `backlog`, so a skill
#: that may run thirteen named ops looked equally able to run the group itself. It
#: cannot — a grant is a literal prefix match — so the instruction prompts, and a
#: prompt the model cannot get answered is indistinguishable from the command
#: failing.
_SUBCOMMAND_WORD = re.compile(r"^[a-z][a-z0-9-]*$")

#: The HOUSE GRANT FORM: the star is attached to the last command word, with no
#: space before it — ``Bash(prawduct-hook lifecycle-repair*)``. A Bash grant is
#: matched as a literal PREFIX of the command string, so where the star sits is the
#: whole rule:
#:
#:   * attached — ``lifecycle-repair*`` — the prefix ends at the command name, so the
#:     bare call AND every argument form match. One grant, both shapes.
#:   * spaced — ``lifecycle-repair *`` — the prefix carries the trailing space, so
#:     something must follow it. A **bare** call does not match, and falls through to
#:     a runtime permission prompt that nothing in a headless run can answer.
#:
#: The tree used to demonstrate both remedies — the spaced star plus a second bare
#: grant (``classify-diff-risk`` + ``classify-diff-risk *``), and the attached star
#: (``review-stats*``) — which is how the class regrew after each instance was fixed.
#: One form is now the house form, and it is the attached star: it is a single grant
#: line per command instead of two that have to be kept in step.
_STAR_ATTACHED = "*"
_STAR_SPACED = " *"

#: Command names that are a FAMILY rather than a command — the binary refuses them
#: without an op, so writing one bare is a reference to the group, not an invocation.
#: Anything not listed here is a leaf: ``prawduct-hook coverage-status`` is a whole
#: command, and a grant that cannot run it bare is a real gap. Conflating the two is
#: what let a starred-only grant read as covering a bare call — every single-word
#: call was treated as an unrunnable group reference and waved through.
_COMMAND_GROUPS = frozenset({"backlog", "advisory", "evidence", "test-evidence", "handoff"})


def _hook_call_key(text: str, start: int) -> tuple[str, ...]:
    """The command words following a ``prawduct-hook`` match at ``start``.

    Two shapes end a command name and begin its arguments: a token that is not a
    bare subcommand word, and the end of the code span it was written in. Both are
    honoured, because prose runs straight on from a closing backtick — reading two
    tokens blind turns "``prawduct-hook review-stats`` for the history" into a
    command called ``review-stats for``.

    A ``--flag`` IS kept, as the second element and the last. That is what makes a
    group-level call distinguishable from the group: ``backlog --help`` is a command
    a skill must be granted, and a grant naming thirteen sub-ops does not confer it.

    **A trailing star is PRESERVED**, as a final element that is one of
    ``_STAR_ATTACHED`` / ``_STAR_SPACED`` — never folded into the command words. The
    key used to end with ``.rstrip("*")``, which erased the one character the
    starred-vs-bare defect turns on: ``Bash(prawduct-hook coverage-status *)`` and
    the instruction ``prawduct-hook coverage-status`` reduced to the identical key,
    so no amount of grant data could make the guard fire on this axis.
    """
    key: list[str] = []
    star = ""
    #: Three tokens, not two, because a spaced star is a third token after two
    #: command words (``backlog cache-query *``). The two-word ceiling on the KEY
    #: itself is unchanged — the third token is only ever read for a star.
    for raw in text[start:].split()[:3]:
        ended = "`" in raw
        token = raw.split("`")[0].strip(",.;:)")
        if token == _STAR_ATTACHED:
            star = _STAR_SPACED
            break
        stripped = token.rstrip("*")
        if stripped != token:
            star = _STAR_ATTACHED
            token = stripped
            if token.startswith("--") or _SUBCOMMAND_WORD.match(token):
                if len(key) < 2:
                    key.append(token)
            break
        if len(key) == 2:
            break
        if token.startswith("--"):
            key.append(token)
            break
        if not _SUBCOMMAND_WORD.match(token):
            break
        key.append(token)
        if ended:
            break
    return tuple(key) + ((star,) if star else ())


def _split_star(key: tuple[str, ...]) -> tuple[tuple[str, ...], str]:
    """A key as (command words, star) — the star being "" where there is none."""
    if key and key[-1] in (_STAR_ATTACHED, _STAR_SPACED):
        return key[:-1], key[-1]
    return key, ""


def _covers(grant_key: tuple[str, ...], call_key: tuple[str, ...]) -> bool:
    """Whether a grant covers a call: the grant must be a PREFIX of the call.

    A broader grant covers a narrower call (``backlog *`` covers ``backlog list``);
    the reverse is the defect — ``backlog list *`` does not confer a bare
    ``backlog --help``.

    **A spaced star does not cover a bare call.** ``Bash(prawduct-hook coverage-status *)``
    is the prefix ``prawduct-hook coverage-status `` — trailing space included — and
    the instruction ``run prawduct-hook coverage-status`` does not carry it. Only the
    attached star (the house form) covers both shapes from one line.

    A call naming only a FAMILY (`_COMMAND_GROUPS`) is a REFERENCE rather than an
    invocation — the binary refuses it without an op — so it is satisfied by any
    grant into that group. A single-word LEAF command is a real invocation and gets
    no such pass; that distinction is the whole fix.

    The converse direction — a bare-only grant against a call that takes arguments —
    is deliberately left lenient here (#730 scopes it out, and sizes it at
    ``pr/SKILL.md``'s ``test-status`` / ``check-cumulative-critic`` / ``resolve-base``).
    """
    grant_words, grant_star = _split_star(grant_key)
    call_words, _ = _split_star(call_key)
    if not grant_words or not call_words:
        return False
    if len(call_words) == 1 and call_words[0] in _COMMAND_GROUPS:
        return grant_words[0] == call_words[0]
    if len(grant_words) > len(call_words):
        return False
    if call_words[: len(grant_words)] != grant_words:
        return False
    if grant_star == _STAR_SPACED and len(call_words) == len(grant_words):
        return False
    return True


#: The self-hosted spelling: reaches the hook through the in-tree checkout. Optional
#: — a skill is free to grant only the bare form — but never sufficient on its own.
_SELF_HOSTED_GRANT_RE = re.compile(r"bin/prawduct-hook\s+([a-z][a-z0-9-]*)")

#: A ``gh`` grant, captured with whatever follows the executable inside the parens.
#: ``(?![\w-])`` keeps it off ``ghost``-shaped names.
_GH_GRANT_RE = re.compile(r"Bash\(gh(?![\w-])([^)]*)\)")

#: What a scoped ``gh`` grant looks like: whitespace, then a subcommand family.
_GH_SCOPED_RE = re.compile(r"^\s+[a-z][a-z0-9-]*\b")

#: ``gh`` subcommands that do not narrow anything, so naming one is not scoping.
#: Both send an arbitrary request to an arbitrary endpoint against every repo the
#: ambient token reaches — `Bash(gh api *)` is the wildcard wearing a subcommand's
#: name, and it would satisfy the shape check above while giving up exactly the
#: boundary that check exists to hold. Prawduct's own raw calls live in the
#: backlog transport, which runs as a hook subprocess under its own grant and is
#: unaffected by this rule. A skill that genuinely needs one should have to argue
#: for it rather than inherit it from a regex.
_GH_UNSCOPING = frozenset({"api", "graphql"})


def _unscoped_gh_grants(grant_line: str) -> list[str]:
    """The ``gh`` grants on this line that hand over more than a subcommand family.

    Factored out so the controls below exercise THIS expression rather than a
    re-spelling of it — a control that tests a different predicate than the rule
    passes while the rule rots.
    """
    out = []
    for tail in _GH_GRANT_RE.findall(grant_line):
        scoped = _GH_SCOPED_RE.match(tail)
        if scoped is None or scoped.group().strip() in _GH_UNSCOPING:
            out.append(f"Bash(gh{tail})")
    return out

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
    # Cross-reference: the janitor EMITS this string to the operator when the
    # backlog cache is unreadable ("run `prawduct-hook backlog sync --repo
    # <scope>`") — it is the remedy a human runs, not a step the janitor takes.
    # Granting it would hand a maintenance survey a network write it has no
    # business making, which is the opposite of what the grant is for.
    ("janitor", "backlog sync"): "remedy text printed for the operator, never run by the janitor",
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


def _key(spelling: str) -> tuple[str, ...]:
    """The key for one written ``prawduct-hook …`` spelling, grant or call."""
    match = re.search(r"prawduct-hook(?=\s)", spelling)
    assert match is not None, spelling
    return _hook_call_key(spelling, match.end())


def test_a_spaced_star_does_not_cover_a_bare_call() -> None:
    """The rule the house grant form exists to make true (#730).

    This is asserted directly on the predicate rather than by reverting a real
    grant line, because the members are the churn and the rule is the thing. A
    guard that only fires on today's tree passes the day someone writes the
    ninth instance.

    Each row is (grant spelling, call spelling, covered?), and every one of them
    is a shape the tree has actually carried.
    """
    cases = [
        # The defect: the grant's prefix ends in a space, the call does not.
        ("Bash(prawduct-hook coverage-status *)", "prawduct-hook coverage-status", False),
        ("Bash(prawduct-hook backlog cache-query *)", "prawduct-hook backlog cache-query", False),
        # The house form: one line, both shapes.
        ("Bash(prawduct-hook coverage-status*)", "prawduct-hook coverage-status", True),
        ("Bash(prawduct-hook coverage-status*)", "prawduct-hook coverage-status --json", True),
        ("Bash(prawduct-hook backlog cache-query*)", "prawduct-hook backlog cache-query", True),
        # A spaced star still covers what it always covered — an argument form.
        ("Bash(prawduct-hook coverage-status *)", "prawduct-hook coverage-status --json", True),
        # An argument-less command granted bare covers its bare call.
        ("Bash(prawduct-hook resolve-base)", "prawduct-hook resolve-base", True),
        # A grant into a family does not confer a DIFFERENT op in that family.
        ("Bash(prawduct-hook backlog list*)", "prawduct-hook backlog pick", False),
        # …but a bare family name is a reference, not an invocation: the binary
        # refuses it without an op, so any grant into the family satisfies it.
        ("Bash(prawduct-hook backlog list*)", "prawduct-hook backlog", True),
    ]
    wrong = [
        (grant, call, expected)
        for grant, call, expected in cases
        if _covers(_key(grant), _key(call)) is not expected
    ]
    assert not wrong, (
        f"star-aware coverage is wrong for: {wrong}. A grant is a literal prefix "
        f"match, so `<cmd> *` requires a trailing space plus an argument and the "
        f"bare call prompts; only the attached star covers both."
    )


def test_the_star_survives_the_key() -> None:
    """``_hook_call_key`` must not erase the character the rule turns on.

    The predicate above can only be right if the two spellings reach it as
    different keys. They did not: the key was built with ``.rstrip("*")``, which
    made ``coverage-status *`` and a bare ``coverage-status`` identical before
    anything compared them — so no grant data could have made the guard fire.
    """
    starred = _key("Bash(prawduct-hook coverage-status *)")
    attached = _key("Bash(prawduct-hook coverage-status*)")
    bare = _key("prawduct-hook coverage-status")
    assert len({starred, attached, bare}) == 3, (
        f"the three spellings must be three keys, got {starred}, {attached}, {bare}"
    )
    # And a bare call in prose is still just its command words — a trailing
    # sentence must not become a star or a second command word.
    assert _key("run `prawduct-hook coverage-status` and read the chain") == ("coverage-status",)


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_every_instructed_command_is_granted(skill_path: Path) -> None:
    name = skill_path.parent.name
    text = skill_path.read_text(encoding="utf-8")
    grant = _frontmatter_grant(text)
    if grant is None:
        pytest.skip(f"{name} declares no allowed-tools (unrestricted)")

    granted = {
        _hook_call_key(grant, m.end())
        for m in re.finditer(r"(?<![\w/-])prawduct-hook(?=\s)", grant)
    }
    granted |= {
        _hook_call_key(grant, m.end())
        for m in re.finditer(r"bin/prawduct-hook(?=\s)", grant)
    }
    # SKILL.md only. A skill's BUNDLED files are instruction prose read under this
    # same grant, and sweeping them finds real gaps — but dozens of them, each a
    # decision about whether the sentence instructs the agent or narrates what an
    # operator does by hand. That is its own work, filed rather than half-made here;
    # the referent this batch depends on is pinned directly below instead.
    body = text[text.index(grant) + len(grant) :]
    calls = {
        _hook_call_key(body, m.end())
        for m in re.finditer(r"prawduct-hook(?=\s)", body)
    }
    missing = sorted(
        " ".join(call)
        for call in calls
        if call
        and not any(_covers(g, call) for g in granted if g)
        and (name, call[0]) not in _NOT_GRANTED
        and (name, " ".join(call)) not in _NOT_GRANTED
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
        text = path.read_text(encoding="utf-8")
        mentioned = {
            " ".join(_hook_call_key(text, m.end()))
            for m in re.finditer(r"prawduct-hook(?=\s)", text)
        }
        # A row may be keyed by the whole call (`backlog sync`) or by its first word,
        # so a first-word row stays live while any call into that family is mentioned.
        if command not in mentioned and not any(
            m.split(" ")[0] == command for m in mentioned if m
        ):
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

    unscoped = _unscoped_gh_grants(grant)
    assert not unscoped, (
        f"skills/{name}/SKILL.md grants {', '.join(unscoped)} — reach the whole "
        f"GitHub CLI, or an arbitrary endpoint through it, against every repo the "
        f"token covers. Name the subcommand family the skill actually runs, e.g. "
        f"`Bash(gh pr *)`; `gh api`/`gh graphql` do not count as naming one."
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
    assert _unscoped_gh_grants(grant)


@pytest.mark.parametrize("grant", [" Bash(gh pr *)", " Bash(gh issue view *)"])
def test_a_scoped_gh_grant_is_accepted(grant: str) -> None:
    """And the complement — naming a subcommand family is what the rule asks for."""
    assert not _unscoped_gh_grants(grant)


@pytest.mark.parametrize("grant", [" Bash(gh api *)", " Bash(gh graphql *)"])
def test_a_raw_endpoint_subcommand_does_not_count_as_scoping(grant: str) -> None:
    """`gh api` satisfies "names a subcommand family" and narrows nothing — it sends
    an arbitrary request to an arbitrary endpoint against every repo the token
    covers. Without this the rule reads as closed while the widest grant available
    walks through it wearing a subcommand's name."""
    assert _unscoped_gh_grants(grant)


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


def test_the_op_set_referent_is_granted_where_it_is_instructed() -> None:
    """The bound that stops a model inventing a mutation path has to be RUNNABLE.

    `backlog/adapter-mode.md` bounds its reader to "the ops in the usage table
    `prawduct-hook backlog --help` prints". A grant naming thirteen sub-ops does not
    confer the group-level call: grants match literally, so the instruction prompts,
    and a prompt the model cannot get answered is indistinguishable from the command
    failing — at which point the reader falls back to its own notion of the op set,
    which is the whole failure the bound exists to prevent.

    Pinned here rather than by sweeping the bundled files, which surfaces a wider
    class than this asserts (see the note in `test_every_instructed_command_is_granted`).
    """
    grant = _frontmatter_grant((SKILLS_DIR / "backlog" / "SKILL.md").read_text(encoding="utf-8"))
    assert grant is not None
    adapter = (SKILLS_DIR / "backlog" / "adapter-mode.md").read_text(encoding="utf-8")
    assert "prawduct-hook backlog --help" in adapter, (
        "adapter-mode.md no longer cites `prawduct-hook backlog --help` as the op-set "
        "referent — if the bound moved, move this pin with it rather than deleting it"
    )
    for spelling in ("prawduct-hook backlog --help",
                     "python3 plugin/bin/prawduct-hook backlog --help"):
        assert spelling in grant, (
            f"skills/backlog/SKILL.md instructs `prawduct-hook backlog --help` as the "
            f"op-set referent but does not grant `{spelling}`. Both spellings are "
            f"needed: the bare one is the only form that runs in a governed product, "
            f"and the self-hosted one is the only form that runs in this checkout."
        )


# --- agent definitions -------------------------------------------------------
#
# `plugin/agents/*.md` ships a `tools:` grant and is read verbatim as a subagent's
# system prompt. It is the same PROPERTY the rules above exist for — instruction
# prose carrying a permission grant — reached through a different frontmatter key
# and a different directory, which is exactly how it escaped all three of them.
# Bounding a rule by the container it was written for is what leaves the next
# member silent; these bound it by the property instead. The tree complies today,
# which is why the omission was invisible rather than harmless.

AGENTS_DIR = SKILLS_DIR.parent / "agents"


def _agent_files() -> list[Path]:
    return sorted(AGENTS_DIR.glob("*.md"))


def _agent_grant(text: str) -> str | None:
    match = re.search(r"^tools:(.*)$", text, re.M)
    return match.group(1) if match else None


def test_the_agent_sweep_has_subjects() -> None:
    """A rule asserted over an empty set is a rule that cannot fail."""
    files = _agent_files()
    assert files, f"no agent definitions found under {AGENTS_DIR}"
    assert any(_agent_grant(f.read_text(encoding="utf-8")) for f in files), (
        "no agent definition declares a `tools:` grant — if the key was renamed, "
        "follow it here rather than leaving the sweep green over nothing"
    )


@pytest.mark.parametrize("agent_path", _agent_files(), ids=lambda p: p.stem)
def test_an_agent_gh_grant_names_the_subcommand_it_needs(agent_path: Path) -> None:
    grant = _agent_grant(agent_path.read_text(encoding="utf-8"))
    if grant is None:
        pytest.skip(f"{agent_path.name} declares no tools (unrestricted)")
    unscoped = _unscoped_gh_grants(grant)
    assert not unscoped, (
        f"agents/{agent_path.name} grants {', '.join(unscoped)} — reach the whole "
        f"GitHub CLI, or an arbitrary endpoint through it, against every repo the "
        f"token covers. Name the subcommand family it actually runs."
    )


@pytest.mark.parametrize("agent_path", _agent_files(), ids=lambda p: p.stem)
def test_an_agent_self_hosted_hook_grant_never_stands_alone(agent_path: Path) -> None:
    grant = _agent_grant(agent_path.read_text(encoding="utf-8"))
    if grant is None:
        pytest.skip(f"{agent_path.name} declares no tools (unrestricted)")
    self_hosted = set(_SELF_HOSTED_GRANT_RE.findall(grant))
    bare = set(_BARE_GRANT_RE.findall(grant))
    orphaned = sorted(self_hosted - bare)
    assert not orphaned, (
        f"agents/{agent_path.name} grants "
        f"{', '.join('python3 plugin/bin/prawduct-hook ' + c for c in orphaned)} with "
        f"no bare `prawduct-hook` sibling — that covers only a checkout carrying the "
        f"plugin in its own tree. In a governed product the plugin installs elsewhere "
        f"and the bare spelling is the only one that runs."
    )
