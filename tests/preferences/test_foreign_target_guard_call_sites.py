"""Every production call to a guarded backlog write states its own_repos.

#1013's foreign-target guard lives in ``core``'s five id-addressed writes, and
``own_repos=None`` means "skip it". A default of None keeps ~200 test calls
short, so the decision is made visible at each PRODUCTION call instead: a call
that omits the keyword is a guard bypass nobody chose (Critic R-6 on the
backlog-burndown branch). Import and merge pass ``own_repos=None`` explicitly,
on purpose, because they are owner-prompted and outside the skill's grant.
"""

from __future__ import annotations

import ast
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugin"
GUARDED = {"set_status", "update_item", "comment_item", "link", "unlink"}


def _is_guarded_ref(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr in GUARDED
        and isinstance(node.value, ast.Name)
        and node.value.id == "core"
    )


def _call_sites() -> list[tuple[str, int, bool]]:
    sites = []
    for path in sorted(PLUGIN.rglob("*.py")):
        if path.name == "core.py" and path.parent.name == "backlog":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # A name bound to a guarded function (`fn = core.link if ... else core.unlink`).
        aliases = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(_is_guarded_ref(sub) for sub in ast.walk(node.value))
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if _is_guarded_ref(func) or (isinstance(func, ast.Name) and func.id in aliases):
                passed = any(kw.arg == "own_repos" for kw in node.keywords)
                sites.append((path.relative_to(PLUGIN).as_posix(), node.lineno, passed))
    return sites


def test_the_sweep_finds_the_known_callers():
    files = {f for f, _, _ in _call_sites()}
    assert {"lib/backlog/cli.py", "lib/backlog/migrate.py"} <= files, files


def test_every_production_call_states_own_repos():
    missing = [f"{f}:{line}" for f, line, passed in _call_sites() if not passed]
    assert not missing, (
        f"guarded backlog writes called without own_repos: {missing} — pass the "
        "repo's identities, or own_repos=None with a comment saying why the "
        "foreign-target guard does not apply"
    )
