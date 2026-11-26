"""Backlog skill metadata test — the adapter grant is narrowed to the everyday
ops, in both invocation forms (BKL-5N9W).

`skills/backlog/SKILL.md` carries `disable-model-invocation: false` (the model may
invoke it on its own initiative) and, since BKL-3W6K, its first Bash grant. That
grant was a **wildcard** over the entire adapter op set — including the
high-consequence one-shot-migration ops (`import` bulk-creates 100–250 real GitHub
issues; `merge`/`provision`/`reconcile-labels`). This pins the narrowed grant:

- every **everyday** op is granted, in BOTH forms (`prawduct-hook …` and the
  self-hosted `python3 plugin/bin/prawduct-hook …`) — the JNT-4R2M dual-form rule;
  landing only the bare form re-opens the self-hosted path;
- the **scrub-only** ops are NOT granted, so they surface a permission prompt when
  the scrub runbook reaches them (defense-in-depth atop the runbook's
  owner-confirmation step; CRT-9V4T — an `allowed-tools` list is a no-prompt
  allow-list, not a hard cap);
- the bare wildcard is gone.
"""

from __future__ import annotations

import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
BACKLOG_SKILL = PLUGIN / "skills" / "backlog" / "SKILL.md"

# The everyday ops the skill actually drives (SKILL.md + adapter-mode.md): reads,
# item edits, and edge links. `update` routes to comment/link/unlink, so those
# ride the everyday grant too — and it is also where taking an item now happens
# (`--working-branch`), which is why `claim`/`unclaim` are not on this list.
EVERYDAY_OPS = (
    "file", "get", "status", "update", "comment",
    "list", "pick", "counts", "link", "unlink",
    # `sync` and `cache-query` joined the everyday set when `adapter-mode.md`
    # started routing `find` and `dedup` through the cache — the runbook naming an
    # op the grant omits is the gap this tuple exists to catch, and it opened in
    # the same changeset that wrote the runbook.
    "sync", "cache-query",
)

# Every op name the CLI no longer dispatches. A grant, a documented flag, or a
# usage line naming one of these is a HALF retirement: the CLI would exit
# "unknown op" while the skill went on telling a reader to run it, and the unit
# suite would stay green throughout because nothing imports prose. That gap is
# exactly what the code-and-prose pairing exists to close, so it is asserted
# here rather than trusted.
RETIRED_OPS = ("claim", "unclaim")

# Adapter flags only. `--include-claimed` is deliberately NOT here: the retirement
# is scoped to the **Issues adapter**, whose `claim` op collapsed an assignee take,
# a `claimed_at` stamp and a staleness TTL into one `working-branch` field. The
# markdown backend has none of those three — `accepted-by:` is a line in a file —
# and `working-branch` would require a pushed ref and a named repo, which a
# local-only repo or a shared-trunk team cannot supply. So the markdown prose keeps
# `accepted-by:`/`--include-claimed` and the adapter prose uses
# `working-branch`/`--include-working`: one field per backend, each native to its
# substrate.
RETIRED_FLAGS = ("--claim", "--claim-ttl")

# The one-shot, owner-confirmed migration ops. Left OUT of the grant on purpose so
# they prompt (BKL-5N9W). `merge` is dual-use (dedup also folds), but its blast
# radius (close an issue) puts it with the migration set; post-cutover dedup is
# degraded anyway.
SCRUB_ONLY_OPS = ("import", "merge", "provision", "reconcile-labels")

# The subset that is UNRECALLABLE, and therefore the one rail that binds every
# model-invocable skill rather than just this one. `import` writes 100-250 real
# issues and GitHub has no ordinary issue-delete; `merge` closes an issue. The
# other two are additive and idempotent by construction — `reconcile_labels`
# "corrects drift by adding what is missing, never by removing" — so onboard and
# doctor grant them no-prompt on purpose: running them IS what those flows are
# for. They stay out of the backlog skill's own grant regardless (below).
IRREVERSIBLE_OPS = ("import", "merge", "file-upstream")

#: The grant form for each everyday op. `<op>*` is the house form (JNT-4R2M, #730)
#: and holds wherever no other dispatched op extends the op's name. `file` is the
#: exception and the reason the rule below exists: `file*` also permits
#: `file-upstream`, which writes into a FOREIGN public repo irreversibly, so its
#: grant stops at the flag lead-in. `test_no_everyday_grant_leaks_another_op`
#: proves this map is complete rather than remembered.
_GRANT_SUFFIX: dict[str, str] = {"file": " --*"}


def _grant_form(inv: str, op: str) -> str:
    return f"Bash({inv} {op}{_GRANT_SUFFIX.get(op, '*')})"

_INVOCATIONS = ("prawduct-hook backlog", "python3 plugin/bin/prawduct-hook backlog")


def _allowed_tools() -> str:
    m = re.search(
        r"^allowed-tools:\s*(.+)$", BACKLOG_SKILL.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert m is not None, "backlog SKILL.md missing `allowed-tools:` frontmatter field"
    return m.group(1).strip()


def _dispatched_ops() -> tuple[str, ...]:
    """The CLI's own op surface — asked of the source, never re-typed here, so an
    op added tomorrow is checked by the rules below without anyone remembering."""
    import sys

    sys.path.insert(0, str(PLUGIN))
    from lib.backlog import cli

    return cli._ALL_OPS


def _granted_patterns() -> list[str]:
    """Every `Bash(...)` pattern in the grant, as written."""
    return re.findall(r"Bash\(([^)]*)\)", _allowed_tools())


def _normalized(pattern: str) -> str:
    """A trailing ``:*`` is the legacy spelling of a trailing `` *``."""
    p = pattern.strip()
    return p[:-2] + " *" if p.endswith(":*") else p


def _grant_matches(pattern: str, command: str) -> bool:
    """Whether a `Bash(...)` grant pattern would permit ``command``.

    Claude Code grants are glob-ish: ``*`` stands for any text. Comparing the
    *semantics* rather than the literal string is the point — see
    :func:`test_scrub_ops_not_granted`. Two documented rules besides the star
    (code.claude.com/docs/en/permissions, "Wildcard patterns"): ``:*`` at the end
    equals `` *``, and a trailing `` *`` that is the pattern's only wildcard also
    admits the bare command (`Bash(git log *)` admits `git log`). These rails
    guard OVER-permission, so they take the wider reading;
    `test_skill_command_grants.py` guards under-permission and takes the narrower.
    """
    p = _normalized(pattern)
    regex = "".join(".*" if part == "*" else re.escape(part) for part in re.split(r"(\*)", p))
    if re.fullmatch(regex, command) is not None:
        return True
    return p.endswith(" *") and p.count("*") == 1 and command == p[:-2]


def test_no_bare_wildcard_grant():
    # Both spellings, so the narrowing cannot be undone by respelling the star:
    # `backlog *` and `backlog*` confer the same thing.
    allowed = _allowed_tools()
    for inv in _INVOCATIONS:
        for grant in (f"Bash({inv} *)", f"Bash({inv}*)"):
            assert grant not in allowed, (
                f"backlog SKILL.md still grants the bare wildcard `{grant}` — "
                "narrow it to the everyday ops so high-consequence scrub ops prompt "
                "(BKL-5N9W)."
            )


def test_everyday_ops_granted_in_both_forms():
    """The house grant form (#730): the star attaches to the last command word with
    NO space, one line per command.

    A Bash grant is a literal prefix match, so the old `... <op> *)` spelling
    required a trailing space plus an argument and did not cover the bare call —
    which fell through to a permission prompt nothing in an unattended run can
    answer. The attached star covers the bare call and every argument form at once.

    ``_GRANT_SUFFIX`` records where the house form cannot hold: an attached star
    also covers every op whose name *extends* this one, which is a widening nobody
    writing the grant intended.
    """
    allowed = _allowed_tools()
    missing: list[str] = []
    for op in EVERYDAY_OPS:
        for inv in _INVOCATIONS:
            grant = _grant_form(inv, op)
            if grant not in allowed:
                missing.append(grant)
    assert not missing, (
        "backlog SKILL.md is missing everyday-op grants in the house form — the "
        "star attaches to the op with no space, and both invocation forms are "
        "required (JNT-4R2M, #730):\n  - " + "\n  - ".join(missing)
    )


def test_no_everyday_grant_leaks_another_op():
    """An everyday-op grant must permit that op and no other dispatched one.

    The house form `<op>*` is a prefix match, so it silently confers every op whose
    name extends the granted one. `file*` permitted `file-upstream` — a filing into
    a foreign public repo, irreversible, and precisely the op whose whole design is
    a per-report human approval — from the moment that op existed, with every
    grant test green. The narrowing is real but the general rule is what keeps it:
    the next op named `list-*` or `sync-*` reopens this the same way.
    """
    patterns = _granted_patterns()
    everyday = set(EVERYDAY_OPS)
    leaked: list[str] = []
    for op in _dispatched_ops():
        if op in everyday:
            continue
        for inv in _INVOCATIONS:
            command = f"{inv} {op} --title T"
            leaked += [
                f"`Bash({p})` permits `{command}`"
                for p in patterns
                if _grant_matches(p, command)
            ]
    assert not leaked, (
        "an everyday-op grant reaches an op that is not an everyday op — narrow it "
        "(record the narrowing in `_GRANT_SUFFIX`) so the extra op prompts:\n  - "
        + "\n  - ".join(leaked)
    )


def _model_invocable(skill: Path) -> bool:
    """Whether the MODEL can invoke this skill without a human naming it.

    The frontmatter field is opt-OUT, so an undeclared skill is the permissive
    case, not the safe one — which is exactly how janitor came to be the only
    skill that never declared it.
    """
    m = re.search(
        r"^disable-model-invocation:\s*(\S+)\s*$",
        skill.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return not (m and m.group(1).lower() == "true")


def test_scrub_ops_not_granted_in_backlog_skill():
    """The backlog skill withholds all four scrub ops — semantically, not by string.

    Scoped to this skill because it is the general-purpose, model-invocable
    backlog surface: nothing about *it* justifies a one-shot migration write, so
    all four stay out and prompt (BKL-5N9W). The narrower cross-skill rail below
    is the one that binds flows whose whole purpose is a setup write.
    """
    patterns = _granted_patterns()
    leaked = [
        f"`Bash({p})` permits `{inv} {op} --repo owner/repo`"
        for op in SCRUB_ONLY_OPS
        for inv in _INVOCATIONS
        for p in patterns
        if _grant_matches(p, f"{inv} {op} --repo owner/repo")
    ]
    assert not leaked, (
        "backlog SKILL.md grants a high-consequence scrub op no-prompt — these must "
        "stay OUT of the grant so they prompt at the migration write (BKL-5N9W):\n  - "
        + "\n  - ".join(leaked)
    )


def test_no_model_invocable_skill_grants_an_irreversible_op():
    """No skill the model can invoke may permit an UNRECALLABLE op — any spelling.

    This asks the semantic question, not the literal one, and it asks it of
    every skill rather than one file. Both widenings were paid for. The first
    version checked exact strings like ``Bash(prawduct-hook backlog import *)``
    and was evadable by a *broader* wildcard, which re-grants the withheld set
    while every test here stays green. The second was scoped to the backlog
    skill alone, and missed janitor's ``Bash(python3 *)`` — a grant nobody reads
    as a backlog grant, which nonetheless permits ``python3
    plugin/bin/prawduct-hook backlog import``. The rail is about the OP, so the
    check has to follow the op wherever it can be reached.

    Scoped to ``IRREVERSIBLE_OPS`` rather than all four: onboard and doctor
    grant ``provision``/``reconcile-labels`` deliberately, and those are additive
    and idempotent. Enforcing the full set here would read as a security finding
    when the real defect is the classification.

    Skills a human must invoke by name are out of scope: the deliberate act the
    prompt exists to force has already happened.
    """
    leaked: list[str] = []
    for skill in sorted((PLUGIN / "skills").glob("*/SKILL.md")):
        if not _model_invocable(skill):
            continue
        patterns = _skill_bash_patterns(skill)
        for op in IRREVERSIBLE_OPS:
            for inv in _INVOCATIONS:
                command = f"{inv} {op} --repo owner/repo"
                leaked += [
                    f"{skill.parent.name}: `Bash({p})` permits `{command}`"
                    for p in patterns
                    if _grant_matches(p, command)
                ]
    assert not leaked, (
        "a model-invocable skill permits a high-consequence scrub op no-prompt — these "
        "must prompt at the migration write (BKL-5N9W):\n  - " + "\n  - ".join(leaked)
    )


# --- A model-invocable grant must not REACH a command that has to prompt -------
#
# A Bash grant in a skill the model can invoke pre-approves every command its
# pattern admits, not only the one its author meant. `Bash(git *)` admits
# `git push --force`. `Bash(find *)` admits `find . -exec <cmd> \;`.
# `Bash(git diff*)` admits `git difftool -x <cmd>`, and a leading star admits any
# command that carries the grant's tail as an argument. So this rail asks what
# each grant can REACH: one probe set of commands that must prompt, matched
# against every model-invocable skill's grants and every agent's tool list. A
# new grant is judged by the commands it admits, not by whether its spelling is
# on a list.
#
# It judges the grant text alone. Claude Code also refuses some commands a
# prefix grant admits (a `find` action, an exec wrapper), but that is the
# harness's behaviour in one version, and a grant whose safety rests on it is
# one nothing here can test.

#: Why each probe class must prompt.
_PROBE_CLASSES = {
    "exec": "runs a command the caller names, so it reaches every op an allow-list withholds",
    "destructive-git": "destroys git state or work that version control cannot give back",
    "irreversible-op": "an unrecallable write (IRREVERSIBLE_OPS)",
    "git-tidy-apply": "deletes branches, remote ones included, and worktrees",
    "plan-archive": "ends a plan's life; the prompt is the owner's say over which plan",
    "file-write": "writes a file the caller names",
}

#: Both spellings a grant may admit the hook by.
_HOOKS = ("prawduct-hook", "python3 plugin/bin/prawduct-hook")


def _git(*forms: str) -> tuple[str, ...]:
    """Each git probe, bare and behind `-C .`: a `git -C * <verb> *` grant's
    first star absorbs everything up to the verb."""
    return tuple(f"git {f}" for f in forms) + tuple(f"git -C . {f}" for f in forms)


#: (class, command that must prompt, tokens whose presence makes it safe). A
#: grant reaches a probe when some command it admits STARTS with the probe; the
#: tokens cover the one case an added argument defuses (`--dry-run`).
_MUST_PROMPT: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    *(("exec", c, ()) for c in (
        "python3 -c X", "python -c X", "bash -c X", "sh -c X", "zsh -c X",
        "node -e X", "uv run X", "uvx X", "npm run X", "npx X",
        "find . -exec X \\;",
        *_git("-c alias.a='!X' a", "difftool -x X", "rebase --exec X"),
    )),
    *(("destructive-git", c, ()) for c in _git(
        "push --force", "reset --hard", "branch -D x", "clean -fdx",
        "checkout -- .", "worktree remove --force x",
    )),
    *(("irreversible-op", f"{inv} {op} --repo owner/repo", ())
      for inv in _INVOCATIONS for op in IRREVERSIBLE_OPS),
    # An irreversible op carrying a leading-star grant's tail as an argument.
    ("irreversible-op", "prawduct-hook backlog import --repo o/r --title ' python -m pytest'", ()),
    *(("git-tidy-apply", f"{hook} git-tidy {args}", ())
      for hook in _HOOKS
      for args in ("--apply fp", "--offline --apply fp", "--json --apply fp",
                   "--reap wt", "--json --reap wt")),
    *(("plan-archive", f"{hook} archive-plan .prawduct/artifacts/plan.md", ("--dry-run",))
      for hook in _HOOKS),
    *(("file-write", c, ()) for c in _git("log --output=X", "diff --output=X", "show --output=X")),
)

#: Reach a grant keeps on purpose, each with its reason. Keyed by (holder, or
#: None for every holder; probe class, or "*" for every class; a regex the
#: whole grant pattern must match). `test_no_stale_reach_exemptions` fails a
#: row nothing uses.
_REACH_EXEMPT: dict[tuple[str | None, str, str], str] = {
    (None, "file-write", r"git (-C \* )?(diff|log|show) \*"): (
        "a read verb's star admits `--output=<file>`, and a prefix grant cannot exclude a "
        "flag. Withholding `git diff|log|show` would make every review and survey read "
        "prompt. The reach is one file written; nothing runs"
    ),
    ("agents/critic-reviewer.md", "*", r"git -C \* [a-z-]+ \*"): (
        "the reviewer must address the project as `git -C <dir>` "
        "(tests/test_critic_reviewer_agent.py), and no prefix grant can fix the directory, "
        "so the star before the verb also admits `-c <key>=<cmd>`. Only the critic "
        "coordinator dispatches it, under the no-execution contract"
    ),
    ("skills/doctor/SKILL.md", "plan-archive", r"prawduct-hook archive-plan\*"): (
        "doctor archives only plans the owner names, after showing the `--dry-run`, and "
        "the Lifecycle Convergence Flow takes one confirmation for the whole act "
        "(security-model.md § Direction: a per-action gate is itself a safety "
        "regression). `plan-backfill --apply`, granted, makes the same move in bulk"
    ),
}


def _bash_patterns(path: Path, key: str = "allowed-tools") -> list[str]:
    """The `Bash(...)` grants on ``path``'s ``key:`` line. A `!Bash(...)` entry is
    a deny, not a grant: the harness does not reliably honour it, and reading it
    as a grant would fail a skill for denying what it should."""
    m = re.search(rf"^{key}:\s*(.+)$", path.read_text(encoding="utf-8"), re.MULTILINE)
    return re.findall(r"(?<![!\w])Bash\(([^)]*)\)", m.group(1)) if m else []


def _skill_bash_patterns(skill: Path) -> list[str]:
    return _bash_patterns(skill)


def _grant_holders() -> list[tuple[str, list[str]]]:
    """(label, Bash grants) for every model-invocable skill and every agent."""
    holders = [
        (f"skills/{skill.parent.name}/SKILL.md", _skill_bash_patterns(skill))
        for skill in sorted((PLUGIN / "skills").glob("*/SKILL.md"))
        if _model_invocable(skill)
    ]
    holders += [
        (f"agents/{agent.name}", _bash_patterns(agent, "tools"))
        for agent in sorted((PLUGIN / "agents").glob("*.md"))
    ]
    return holders


def _reach_witness(pattern: str, probe: str) -> str | None:
    """A command ``pattern`` admits that begins with ``probe``, or None.

    An added argument rarely makes a command safe — `git push --force origin x` is
    still a force push — so a grant reaches a probe when SOME command it admits
    starts with the probe. Once the probe has covered the grant's literal head,
    the first star absorbs the probe's remainder and the grant's other literals
    follow as arguments. Each witness is re-checked with :func:`_grant_matches`,
    so this cannot claim a reach the matcher denies."""
    p = _normalized(pattern)
    star = p.find("*")
    head = p if star < 0 else p[:star]
    if star < 0:
        witness = p if p == probe or p.startswith(probe + " ") else None
    elif probe.startswith(head):
        witness = probe + p[star + 1:].replace("*", "")
    elif head.rstrip() == probe or head.startswith(probe + " "):
        witness = p.replace("*", "")
    else:
        witness = None
    if witness is not None:
        assert _grant_matches(pattern, witness), (pattern, witness)
    return witness


def _reaches(pattern: str, probe: str, safe: tuple[str, ...]) -> str | None:
    witness = _reach_witness(pattern, probe)
    return witness if witness and not set(safe) & set(witness.split()) else None


def _reach_findings() -> list[tuple[str, str, str, str]]:
    """(holder, grant, probe class, witness) for every probe a grant reaches."""
    return [
        (holder, pattern, cls, witness)
        for holder, patterns in _grant_holders()
        for pattern in patterns
        for cls, probe, safe in _MUST_PROMPT
        if (witness := _reaches(pattern, probe, safe))
    ]


def _exemption(holder: str, pattern: str, cls: str) -> tuple[str | None, str, str] | None:
    for row in _REACH_EXEMPT:
        row_holder, row_cls, rx = row
        if row_holder in (None, holder) and row_cls in ("*", cls) and re.fullmatch(rx, _normalized(pattern)):
            return row
    return None


def test_doctor_and_janitor_are_model_invocable():
    """An agent may run both, not only a human typing the slash command
    (`.prawduct/owner-rulings.md`, 2026-11-26). Pinned because the rails here go
    quietly green on a skill taken out of model invocation."""
    for name in ("doctor", "janitor"):
        assert _model_invocable(PLUGIN / "skills" / name / "SKILL.md"), name


def test_no_model_invocable_grant_reaches_a_command_that_must_prompt():
    holders = dict(_grant_holders())
    assert len(holders) >= 8, f"control: the grant holders were reached: {sorted(holders)}"
    for reached in ("skills/janitor/SKILL.md", "skills/pr/SKILL.md", "agents/critic-reviewer.md"):
        assert holders.get(reached), f"control: {reached} was read and holds Bash grants"
    leaked = sorted({
        f"{holder}: `Bash({pattern})` admits `{witness}` — {_PROBE_CLASSES[cls]}"
        for holder, pattern, cls, witness in _reach_findings()
        if _exemption(holder, pattern, cls) is None
    })
    assert not leaked, (
        "a grant the model can use without a prompt reaches a command that must prompt. "
        "Narrow it to the commands the skill instructs (space-terminated: `git diff *`, "
        "not `git diff*`), leave the step to prompt, or record a reasoned row in "
        "_REACH_EXEMPT:\n  - " + "\n  - ".join(leaked)
    )


def test_no_stale_reach_exemptions():
    used = {_exemption(h, p, c) for h, p, c, _w in _reach_findings()}
    stale = [row for row in _REACH_EXEMPT if row not in used]
    assert not stale, f"_REACH_EXEMPT rows no grant needs any more: {stale}"


#: For each probe class, grants that must read as reaching it. Each is a shape a
#: skill here has carried or was one edit from carrying.
_REACHING_CONTROLS = {
    "exec": ("python3 *", "npm *", "*", "node*", "uv run *", "bash -c*", "npx *",
             "find *", "git *", "git diff*", "git -C * status*", "* python -m pytest*"),
    "destructive-git": ("git *", "git push *", "git reset *", "git branch *", "git clean *",
                        "git checkout *", "git worktree *", "git -C * add *", "git push:*"),
    "irreversible-op": ("prawduct-hook backlog*", "python3 *", "* python -m pytest*",
                        "prawduct-hook backlog import *"),
    "git-tidy-apply": ("prawduct-hook git-tidy*", "prawduct-hook git-tidy --json*",
                       "prawduct-hook git-tidy --offline*",
                       "python3 plugin/bin/prawduct-hook git-tidy*"),
    "plan-archive": ("prawduct-hook archive-plan*", "prawduct-hook archive-plan *",
                     "python3 plugin/bin/prawduct-hook archive-plan*"),
    "file-write": ("git log*", "git diff *", "git show:*", "git -C * log *"),
}

#: Grants that must read as reaching NONE of the classes named beside them: the
#: narrowed forms this rail sends a skill to.
_STOPPING_CONTROLS = {
    "git diff *": ("exec", "destructive-git"),
    "git log *": ("exec", "destructive-git"),
    "git status *": tuple(_PROBE_CLASSES),
    "git branch --list *": tuple(_PROBE_CLASSES),
    "git worktree list *": tuple(_PROBE_CLASSES),
    "git clean -fx -- .prawduct/.pr-body.md": tuple(_PROBE_CLASSES),
    "prawduct-hook git-tidy": tuple(_PROBE_CLASSES),
    "prawduct-hook git-tidy --offline --json": tuple(_PROBE_CLASSES),
    "prawduct-hook git-tidy --after-merge *": tuple(_PROBE_CLASSES),
    "prawduct-hook archive-plan * --dry-run": tuple(_PROBE_CLASSES),
    "prawduct-hook backlog list*": tuple(_PROBE_CLASSES),
}


def test_each_probe_class_is_caught_by_a_grant_that_reaches_it():
    """Positive control, per class: without it a probe that could never match
    (a typo, a matcher that stopped matching) leaves the sweep green."""
    assert set(_REACHING_CONTROLS) == set(_PROBE_CLASSES) == {c for c, _p, _s in _MUST_PROMPT}
    missed = [
        f"{cls}: `Bash({grant})`"
        for cls, grants in _REACHING_CONTROLS.items()
        for grant in grants
        if not any(_reaches(grant, probe, safe) for c, probe, safe in _MUST_PROMPT if c == cls)
    ]
    assert not missed, "a grant that reaches a probe class reads as safe:\n  - " + "\n  - ".join(missed)


def test_a_narrowed_grant_reaches_nothing_it_should_not():
    reached = [
        f"`Bash({grant})` reaches `{probe}` ({cls})"
        for grant, classes in _STOPPING_CONTROLS.items()
        for cls, probe, safe in _MUST_PROMPT
        if cls in classes and _reaches(grant, probe, safe)
    ]
    assert not reached, "a narrowed grant reads as reaching a probe:\n  - " + "\n  - ".join(reached)


def test_a_deny_entry_is_not_read_as_a_grant():
    critic = _skill_bash_patterns(PLUGIN / "skills" / "critic" / "SKILL.md")
    assert "git diff *" in critic, "control: critic's grants were read"
    assert not any("pytest" in p for p in critic), critic


def test_janitor_keeps_the_survey_reads():
    patterns = _skill_bash_patterns(PLUGIN / "skills" / "janitor" / "SKILL.md")
    for read in ("git log --since=14.days", "git status --short", "git rev-parse HEAD",
                 "git worktree list", "git stash list", "git branch --list",
                 "prawduct-hook git-tidy", "prawduct-hook git-tidy --offline --json"):
        assert any(_grant_matches(p, read) for p in patterns), f"janitor no longer admits `{read}`"


def test_pr_runs_its_reads_and_bookkeeping_but_a_push_prompts():
    """The PR flow's push is the step a prompt guards in default mode: a prefix
    grant cannot admit `git push` without also admitting `git push --force`."""
    patterns = _skill_bash_patterns(PLUGIN / "skills" / "pr" / "SKILL.md")
    for command in ("git branch --show-current", "git status --short",
                    "git log --oneline main..HEAD", "git merge-base origin/develop HEAD",
                    "git rev-parse refs/heads/x",
                    "git commit -m x -- .prawduct/changes/x.md"):
        assert any(_grant_matches(p, command) for p in patterns), f"pr no longer admits `{command}`"
    assert not any(_grant_matches(p, "git push -u origin feature") for p in patterns)


def test_no_retired_op_survives_in_the_skill_prose():
    """The half-retirement guard. A reader follows the skill, not the source."""
    from lib.backlog import cli

    surfaces = sorted((PLUGIN / "skills" / "backlog").glob("*.md"))
    assert surfaces, "no backlog skill surfaces found"

    dispatched = set(cli._ALL_OPS)
    offences: list[str] = []
    for op in RETIRED_OPS:
        assert op not in dispatched, f"{op!r} is still dispatched — this test is out of date"
        for surface in surfaces:
            for lineno, line in enumerate(surface.read_text(encoding="utf-8").splitlines(), 1):
                # An op is only *invoked* when it follows the adapter's own name
                # or sits in a grant. Prose that merely says the word — "there is
                # no `claim` op", which is the sentence the retirement had to
                # write — is not an instruction to run one.
                for form in (f"backlog {op} ", f"backlog {op}<", f"`{op} <id>`"):
                    if form in line:
                        offences.append(f"{surface.name}:{lineno} invokes retired op {op!r}")
    for flag in RETIRED_FLAGS:
        for surface in surfaces:
            for lineno, line in enumerate(surface.read_text(encoding="utf-8").splitlines(), 1):
                if flag in line:
                    offences.append(f"{surface.name}:{lineno} documents retired flag {flag!r}")

    assert not offences, "retired claim surface still in the skill prose:\n  - " + "\n  - ".join(offences)
