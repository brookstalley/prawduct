"""
Plugin-native new-product scaffolding.

Creates a fresh product repo's **product-owned** state — the design §3 "what STAYS
in the consuming repo" set — for the plugin distribution model, with NONE of the
file-sync machinery. The legacy counterpart is the file-sync ``tools/lib/init_cmd.py``;
this module is **plugin-only** (no ``tools/lib/`` twin), mirroring ``migrate_plugin.py``
— onboarding a new product onto the plugin is a plugin-initiated act, and a consumer
that committed only the install reference has no framework checkout to call back to.

Creates:
  - ``.prawduct/project-state.yaml``                  (rendered; ``distribution: plugin`` recorded)
  - ``.prawduct/learnings.md``                        (starter)
  - ``.prawduct/backlog.md``                          (template)
  - ``.prawduct/change-log.md``                       (template)
  - ``.prawduct/artifacts/project-preferences.md``    (template)
  - ``.prawduct/artifacts/boundary-patterns.md``      (template)
  - ``.prawduct/.pr-reviews/``                        (dir)
  - ``CLAUDE.md``                                     (thin static governance anchor — §4)
  - ``.claude/settings.json``                         (committed install reference)
  - ``.gitignore``                                    (session files + version marker)

Creates NONE of: ``tools/product-hook``, ``tools/lib/``, committed
``.claude/skills/*``, ``.prawduct/sync-manifest.json``, or the
``.prawduct/{critic-review,pr-review,build-governance}.md`` protocol docs — the
plugin provides all governance.

Dry-run by default; ``--apply`` mutates. Idempotent: once ``distribution: plugin``
is recorded, a re-run is a no-op.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import core
from .migrate_plugin import (
    ANCHOR_SENTINEL,
    DISTRIBUTION_VALUE,
    INSTALL_REFERENCE,
    apply_claude_anchor,
    ensure_marker_gitignored,
    record_distribution,
    transform_settings,
)

# Product-owned state rendered from the plugin's bundled ``templates/``
# (place-once: created only when missing). (repo-relative dst, template filename)
_STATE_TEMPLATES: list[tuple[str, str]] = [
    (".prawduct/project-state.yaml", "project-state.yaml"),
    (".prawduct/backlog.md", "backlog.md"),
    (".prawduct/change-log.md", "change-log.md"),
    (".prawduct/artifacts/project-preferences.md", "project-preferences.md"),
    (".prawduct/artifacts/boundary-patterns.md", "boundary-patterns.md"),
]

_SCAFFOLD_DIRS = (".prawduct", ".prawduct/artifacts", ".prawduct/.pr-reviews")

_LEARNINGS_REL = ".prawduct/learnings.md"
_LEARNINGS_STARTER = "# Learnings\n\nAccumulated wisdom from building this product.\n"


def _plugin_root() -> Path:
    """The plugin root — ``<root>/lib/init_product.py`` → ``<root>``.

    Resolve ``templates/`` and ``VERSION`` from the plugin root directly rather
    than via ``core.TEMPLATES_DIR`` / ``core.PRAWDUCT_VERSION``: ``core.py`` is
    byte-parity-locked to ``tools/lib/core.py`` (Chunk 5), and its
    ``FRAMEWORK_DIR = __file__.parent.parent.parent`` is correct only at the
    ``tools/lib/`` depth — in the plugin's top-level ``lib/`` it lands one level
    too high (``…/source`` instead of ``…/<plugin>``). The plugin always resolves
    its own resources from the plugin root (as ``bin/`` and ``hooks/`` do); this is
    the first plugin code to render ``templates/`` at runtime, so it does the same.
    """
    return Path(__file__).resolve().parent.parent


def _templates_dir() -> Path:
    return _plugin_root() / "templates"


def _prawduct_version() -> str:
    try:
        return (_plugin_root() / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return core.PRAWDUCT_VERSION  # best-effort fallback


def _subs(name: str) -> dict[str, str]:
    return {"{{PRODUCT_NAME}}": name, "{{PRAWDUCT_VERSION}}": _prawduct_version()}


def already_scaffolded(project_dir: Path) -> bool:
    """True once ``project-state.yaml`` records ``distribution: plugin``.

    Mirrors ``migrate_plugin.already_migrated`` — the same idempotency signal, so a
    repo that was migrated (or already scaffolded) is a guaranteed no-op.
    """
    state = Path(project_dir) / ".prawduct" / "project-state.yaml"
    return core.read_str_yaml_key(state, "distribution") == DISTRIBUTION_VALUE


def _install_reference_present(project_dir: Path) -> bool:
    """True when ``.claude/settings.json`` already carries the full install reference."""
    path = Path(project_dir) / ".claude" / "settings.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    for top_key, mapping in INSTALL_REFERENCE.items():
        existing = data.get(top_key)
        if not isinstance(existing, dict):
            return False
        for k, v in mapping.items():
            if existing.get(k) != v:
                return False
    return True


def init_product(project_dir: str | Path, name: str, *, apply: bool = False) -> dict:
    """Scaffold (or plan) a new plugin-governed product repo at ``project_dir``.

    Returns a summary dict. Dry-run (``apply=False``) computes the plan by
    inspection without mutating; ``apply=True`` performs the idempotent writes and
    reports what actually changed. Either way: ``created`` (new files), ``edited``
    (existing files changed in place), ``created_dirs``, and ``already_scaffolded``.
    """
    project_dir = Path(project_dir).resolve()
    created: list[str] = []
    edited: list[str] = []
    created_dirs: list[str] = []

    if already_scaffolded(project_dir):
        return {
            "target": str(project_dir),
            "product_name": name,
            "already_scaffolded": True,
            "applied": apply,
            "created": created,
            "edited": edited,
            "created_dirs": created_dirs,
        }

    subs = _subs(name)

    if apply:
        project_dir.mkdir(parents=True, exist_ok=True)

    # Directories.
    for rel in _SCAFFOLD_DIRS:
        d = project_dir / rel
        if not d.is_dir():
            created_dirs.append(rel)
            if apply:
                d.mkdir(parents=True, exist_ok=True)

    # Product-owned state rendered from bundled templates (place-once).
    for rel, tmpl in _STATE_TEMPLATES:
        dst = project_dir / rel
        if not dst.is_file():
            created.append(rel)
            if apply:
                dst.parent.mkdir(parents=True, exist_ok=True)
                core.write_template(_templates_dir() / tmpl, dst, subs)

    # Learnings starter (no template — a one-line seed, mirroring file-sync init).
    learnings = project_dir / _LEARNINGS_REL
    if not learnings.is_file():
        created.append(_LEARNINGS_REL)
        if apply:
            learnings.parent.mkdir(parents=True, exist_ok=True)
            learnings.write_text(_LEARNINGS_STARTER, encoding="utf-8")

    # CLAUDE.md — thin static governance anchor (created fresh, or anchored into an
    # existing product CLAUDE.md). Same anchor a migrated repo keeps (Chunk 10).
    claude = project_dir / "CLAUDE.md"
    claude_exists = claude.is_file()
    anchor_needed = (not claude_exists) or (
        ANCHOR_SENTINEL not in claude.read_text(encoding="utf-8")
    )
    if anchor_needed:
        (edited if claude_exists else created).append("CLAUDE.md")
        if apply:
            apply_claude_anchor(project_dir)

    # .claude/settings.json — committed install reference (merged, preserving any
    # existing user keys/hooks/marketplaces).
    settings = project_dir / ".claude" / "settings.json"
    settings_exists = settings.is_file()
    if not _install_reference_present(project_dir):
        (edited if settings_exists else created).append(".claude/settings.json")
        if apply:
            transform_settings(project_dir)

    # distribution: plugin (the stand-down signal; also the idempotency marker).
    if apply:
        record_distribution(project_dir)
    # project-state.yaml is already in `created` above; the distribution line is an
    # append to that same new file, so it needs no separate report entry.

    # .gitignore — session files + the per-repo version marker.
    gitignore = project_dir / ".gitignore"
    gitignore_existed = gitignore.is_file()
    if apply:
        changed = bool(core.update_gitignore(project_dir).get("modified"))
        changed = ensure_marker_gitignored(project_dir) or changed
        if changed:
            (edited if gitignore_existed else created).append(".gitignore")
    else:
        # Predict: any required entry missing → the file will be written.
        existing_lines = (
            set(gitignore.read_text(encoding="utf-8").splitlines())
            if gitignore_existed
            else set()
        )
        from .migrate_plugin import VERSION_MARKER

        required = set(core.GITIGNORE_ENTRIES) | {VERSION_MARKER}
        if not required.issubset(existing_lines):
            (edited if gitignore_existed else created).append(".gitignore")

    return {
        "target": str(project_dir),
        "product_name": name,
        "already_scaffolded": False,
        "applied": apply,
        "created": created,
        "edited": edited,
        "created_dirs": created_dirs,
    }


def _parse_argv(argv: list[str]) -> tuple[str | None, str | None, bool, bool]:
    """Parse ``<target> --name <name> [--apply] [--json]``."""
    apply = False
    as_json = False
    target: str | None = None
    name: str | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--apply":
            apply = True
        elif arg == "--json":
            as_json = True
        elif arg == "--name":
            i += 1
            name = argv[i] if i < len(argv) else None
        elif arg.startswith("--name="):
            name = arg.split("=", 1)[1]
        elif not arg.startswith("-") and target is None:
            target = arg
        i += 1
    return target, name, apply, as_json


def run(argv: list[str]) -> int:
    """CLI entry: ``prawduct-hook init-product <target> --name "<name>" [--apply] [--json]``."""
    target, name, apply, as_json = _parse_argv(argv)
    if not target or not name:
        msg = "usage: prawduct-hook init-product <target> --name \"<name>\" [--apply] [--json]"
        if as_json:
            print(json.dumps({"error": msg}))
        else:
            print(msg)
        return 1

    result = init_product(target, name, apply=apply)

    if as_json:
        print(json.dumps(result, indent=2))
        return 0

    if result["already_scaffolded"]:
        print(f"Already a plugin product (distribution: plugin) — nothing to do: {result['target']}")
        return 0

    verb = "Created" if apply else "Would create"
    edit_verb = "Edited" if apply else "Would edit"
    print(f"{'Scaffolded' if apply else 'Plan for'} plugin product '{name}' at {result['target']}")
    for d in result["created_dirs"]:
        print(f"  {verb} dir  {d}/")
    for f in result["created"]:
        print(f"  {verb}      {f}")
    for f in result["edited"]:
        print(f"  {edit_verb}     {f}")
    if not apply:
        print("\nDry run — re-run with --apply to write. Then open the target in a "
              "new Claude Code session for governance.")
    else:
        print("\nDone. Open the target in a new Claude Code session — the plugin's "
              "hooks and briefing activate there. Run /prawduct:doctor to health-check.")
    return 0
