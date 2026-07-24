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


def test_scrub_ops_not_granted():
    """No granted pattern may MATCH a scrub-op invocation.

    This asks the semantic question, not the literal one. The first version
    checked for the exact strings ``Bash(prawduct-hook backlog import *)`` etc.
    and was therefore evadable in a way that mattered: a *broader* wildcard —
    ``Bash(prawduct-hook *)`` — re-grants every withheld op while leaving all
    three tests in this file green, because none of the exact strings it looks
    for would appear. Widening a grant is the most natural way this rail gets
    dismantled ("the prompts are annoying"), so the check has to catch the
    widening, not one spelling of it. (Cumulative Critic, 2026-07-24.)
    """
    patterns = _granted_patterns()
    leaked: list[str] = []
    for op in SCRUB_ONLY_OPS:
        for inv in _INVOCATIONS:
            command = f"{inv} {op} --repo owner/repo"
            for pattern in patterns:
                if _grant_matches(pattern, command):
                    leaked.append(f"`Bash({pattern})` permits `{command}`")
    assert not leaked, (
        "backlog SKILL.md grants a high-consequence scrub op no-prompt — these must "
        "stay OUT of the grant so they prompt at the migration write (BKL-5N9W):\n  - "
        + "\n  - ".join(leaked)
    )
