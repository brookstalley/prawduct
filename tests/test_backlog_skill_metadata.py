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
# item edits, claims, and edge links. `update` routes to comment/link/unlink, so
# those ride the everyday grant too.
EVERYDAY_OPS = (
    "file", "get", "status", "update", "comment",
    "list", "pick", "counts", "claim", "unclaim", "link", "unlink",
)

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
IRREVERSIBLE_OPS = ("import", "merge")

_INVOCATIONS = ("prawduct-hook backlog", "python3 plugin/bin/prawduct-hook backlog")


def _allowed_tools() -> str:
    m = re.search(
        r"^allowed-tools:\s*(.+)$", BACKLOG_SKILL.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert m is not None, "backlog SKILL.md missing `allowed-tools:` frontmatter field"
    return m.group(1).strip()


def _granted_patterns() -> list[str]:
    """Every `Bash(...)` pattern in the grant, as written."""
    return re.findall(r"Bash\(([^)]*)\)", _allowed_tools())


def _grant_matches(pattern: str, command: str) -> bool:
    """Whether a `Bash(...)` grant pattern would permit ``command``.

    Claude Code grants are glob-ish: ``*`` stands for "any remainder". Comparing
    the *semantics* rather than the literal string is the point — see
    :func:`test_scrub_ops_not_granted`.
    """
    regex = "".join(".*" if part == "*" else re.escape(part)
                    for part in re.split(r"(\*)", pattern.strip()))
    return re.fullmatch(regex, command) is not None


def test_no_bare_wildcard_grant():
    allowed = _allowed_tools()
    for inv in _INVOCATIONS:
        assert f"Bash({inv} *)" not in allowed, (
            f"backlog SKILL.md still grants the bare wildcard `Bash({inv} *)` — "
            "narrow it to the everyday ops so high-consequence scrub ops prompt "
            "(BKL-5N9W)."
        )


def test_everyday_ops_granted_in_both_forms():
    allowed = _allowed_tools()
    missing: list[str] = []
    for op in EVERYDAY_OPS:
        for inv in _INVOCATIONS:
            grant = f"Bash({inv} {op} *)"
            if grant not in allowed:
                missing.append(grant)
    assert not missing, (
        "backlog SKILL.md is missing everyday-op grants (both invocation forms are "
        "required — JNT-4R2M):\n  - " + "\n  - ".join(missing)
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
        m = re.search(
            r"^allowed-tools:\s*(.+)$", skill.read_text(encoding="utf-8"), re.MULTILINE
        )
        patterns = re.findall(r"Bash\(([^)]*)\)", m.group(1)) if m else []
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
