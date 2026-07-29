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


def _subs(name: str) -> dict[str, str]:
    return {"{{PRODUCT_NAME}}": name, "{{PRAWDUCT_VERSION}}": core.PRAWDUCT_VERSION}


def _record_backlog_service_repo(project_dir: Path, spec: str) -> bool:
    """Append ``backlog_service_repo: <spec>`` to project-state.yaml when absent.

    For a product adopting the GitHub Issues backlog backend at onboard
    (``--backlog-repo``). Additive single key, mirroring ``record_distribution``;
    a no-op when the key is already present (never a duplicate, never a clobber).
    Offline and shape-only: the caller validates ``spec`` as ``owner/repo`` but
    this never checks GitHub — a repo that is not (yet) a GitHub remote, or not a
    git repo at all, still records the intended target. Provisioning the taxonomy
    against it is a separate, ``gh``-requiring onboard step.
    """
    path = project_dir / ".prawduct" / "project-state.yaml"
    if core.read_str_yaml_key(path, "backlog_service_repo") is not None:
        return False
    content = path.read_text(encoding="utf-8") if path.is_file() else ""
    block = (
        "\n# GitHub Issues backlog backend — recorded at onboard for a product adopting\n"
        "# the Issues backend from day one (init-product --backlog-repo). The normal\n"
        "# path is markdown-first and sets this later, at scrub/cutover.\n"
        "# `/prawduct:backlog` routes on this scalar.\n"
        f"backlog_service_repo: {spec}\n"
    )
    if content and not content.endswith("\n"):
        content += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + block, encoding="utf-8")
    return True


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


def init_product(
    project_dir: str | Path,
    name: str,
    *,
    backlog_repo: str | None = None,
    apply: bool = False,
) -> dict:
    """Scaffold (or plan) a new plugin-governed product repo at ``project_dir``.

    Returns a summary dict. Dry-run (``apply=False``) computes the plan by
    inspection without mutating; ``apply=True`` performs the idempotent writes and
    reports what actually changed. Either way: ``created`` (new files), ``edited``
    (existing files changed in place), ``created_dirs``, and ``already_scaffolded``.

    ``backlog_repo`` (``owner/repo``), when given, records ``backlog_service_repo``
    for a product adopting the GitHub Issues backlog backend from day one — the
    reported ``backlog_service_repo`` field carries it back (``None`` when absent or
    malformed). Shape-only and offline: a malformed value is skipped with a warning,
    never recorded; the repo need not exist on GitHub (or be a git repo) to record
    the intended target. Ignored on a re-run of an already-scaffolded repo (that is a
    cutover, owned by ``/prawduct:backlog scrub``, not a re-scaffold).
    """
    project_dir = Path(project_dir).resolve()
    created: list[str] = []
    edited: list[str] = []
    created_dirs: list[str] = []
    warnings: list[str] = []

    # Validate the backlog target shape once, offline (owner/repo, two clean
    # segments) — reusing the adapter's single source of shape truth.
    backlog_repo_recorded: str | None = None
    if backlog_repo is not None:
        from .backlog.ids import parse_repo

        if parse_repo(backlog_repo) is None:
            warnings.append(
                f"ignored --backlog-repo {backlog_repo!r}: not a clean owner/repo — "
                "backlog_service_repo not recorded"
            )
        else:
            backlog_repo_recorded = backlog_repo

    if already_scaffolded(project_dir):
        if backlog_repo is not None:
            warnings.append(
                "already scaffolded — --backlog-repo ignored; recording "
                "backlog_service_repo on an existing repo is a cutover "
                "(/prawduct:backlog scrub), not a re-scaffold"
            )
        return {
            "target": str(project_dir),
            "product_name": name,
            "already_scaffolded": True,
            "applied": apply,
            "created": created,
            "edited": edited,
            "created_dirs": created_dirs,
            "backlog_service_repo": None,
            "warnings": warnings,
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
                core.write_template(core.TEMPLATES_DIR / tmpl, dst, subs)

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

    # backlog_service_repo — only when a valid --backlog-repo was given (day-one
    # Issues adoption). Appended to the same new project-state.yaml, so like the
    # distribution line it needs no separate `created`/`edited` entry.
    if apply and backlog_repo_recorded is not None:
        _record_backlog_service_repo(project_dir, backlog_repo_recorded)
        # Report what the file HOLDS, not what was asked for. The writer no-ops
        # when the key is already present, so a report derived from the request
        # disagrees with the tree the moment those two differ — and the caller
        # uses this field to decide whether to provision against that repo.
        backlog_repo_recorded = core.read_str_yaml_key(
            project_dir / ".prawduct" / "project-state.yaml", "backlog_service_repo"
        )

    # .gitignore — session files + the per-repo version marker.
    gitignore = project_dir / ".gitignore"
    gitignore_existed = gitignore.is_file()
    unignored: list[str] = []
    if apply:
        gi_result = core.update_gitignore(project_dir)
        changed = bool(gi_result.get("modified"))
        unignored = list(gi_result.get("unignored") or [])
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
        # Paths whose stale ignore lines were stripped (managed files, retired
        # entries like the tracked-by-default build plan — gate-soundness
        # ch.3). The caller (onboard/doctor) should advise `git add` on these.
        "unignored": unignored,
        # The day-one Issues backend. On apply this is read BACK from
        # project-state.yaml, so it reports what the file holds. On a dry run it is
        # the requested value — nothing was written, and reporting what *would* be
        # recorded is the point of a dry run. A caller that provisions off this
        # field must therefore gate on `applied`: provisioning against a dry run
        # writes labels into a real repo whose scaffold does not exist.
        "backlog_service_repo": backlog_repo_recorded,
        "warnings": warnings,
    }


def _take_value(argv: list[str], i: int) -> tuple[str, int]:
    """``(value, index)`` for the value-taking flag at ``argv[i]``.

    A following token starting with ``-`` is the NEXT FLAG, not this flag's
    value. Consuming it does double damage: it invents a nonsense value AND
    silently swallows the flag it ate — ``--name --json --apply`` scaffolded a
    product named ``"--json"`` with JSON output off, so a machine caller got a
    real repo and could not parse the result. A missing value yields ``""``
    (never ``None``), which each flag's own validation already rejects loudly;
    ``None`` would be indistinguishable from the flag being absent, and for
    ``--backlog-repo`` that silently forfeits the one-shot day-one window.
    """
    if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
        return argv[i + 1], i + 1
    return "", i


def _parse_argv(
    argv: list[str],
) -> tuple[str | None, str | None, str | None, bool, bool]:
    """Parse ``<target> --name <name> [--backlog-repo owner/repo] [--apply] [--json]``."""
    apply = False
    as_json = False
    target: str | None = None
    name: str | None = None
    backlog_repo: str | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--apply":
            apply = True
        elif arg == "--json":
            as_json = True
        elif arg == "--name":
            name, i = _take_value(argv, i)
        elif arg.startswith("--name="):
            name = arg.split("=", 1)[1]
        elif arg == "--backlog-repo":
            backlog_repo, i = _take_value(argv, i)
        elif arg.startswith("--backlog-repo="):
            backlog_repo = arg.split("=", 1)[1]
        elif not arg.startswith("-") and target is None:
            target = arg
        i += 1
    return target, name, backlog_repo, apply, as_json


def run(argv: list[str]) -> int:
    """CLI entry: ``prawduct-hook init-product <target> --name "<name>" [--backlog-repo owner/repo] [--apply] [--json]``."""
    target, name, backlog_repo, apply, as_json = _parse_argv(argv)
    if not target or not name:
        msg = (
            "usage: prawduct-hook init-product <target> --name \"<name>\" "
            "[--backlog-repo owner/repo] [--apply] [--json]"
        )
        if as_json:
            print(json.dumps({"error": msg}))
        else:
            print(msg)
        return 1

    if backlog_repo is not None:
        from .backlog.ids import parse_repo

        if parse_repo(backlog_repo) is None:
            msg = (
                f"invalid --backlog-repo {backlog_repo!r}: expected a clean "
                "owner/repo (two segments, no scheme or trailing slash)"
            )
            if as_json:
                print(json.dumps({"error": msg}))
            else:
                print(msg)
            return 1

    result = init_product(target, name, backlog_repo=backlog_repo, apply=apply)

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
    for f in result.get("unignored", []):
        # Stale ignore lines stripped (managed files / retired entries like the
        # tracked-by-default build plan) — the onboard skill advises `git add`.
        print(f"  unignored   {f} — now tracked-by-contract; `git add` it if present")
    if result.get("backlog_service_repo"):
        print(f"  {verb}      backlog_service_repo: {result['backlog_service_repo']} "
              "(GitHub Issues backend — provision its labels next)")
    for w in result.get("warnings", []):
        print(f"  warning     {w}")
    if not apply:
        print("\nDry run — re-run with --apply to write. Then open the target in a "
              "new Claude Code session for governance.")
    else:
        print("\nDone. Open the target in a new Claude Code session — the plugin's "
              "hooks and briefing activate there. Run /prawduct:doctor to health-check.")
    return 0
