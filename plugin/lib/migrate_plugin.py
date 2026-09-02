"""Plugin-distribution cutover engine — ``/prawduct:migrate`` (build-plan Chunk 9).

Migrates a file-sync consumer repo OFF committed framework files ONTO the
prawduct plugin, as one reviewable, reversible change.

The REMOVE set is **derived from the framework registry** (``core.MANAGED_FILES``
/ ``core.MANAGED_DIRS`` — write-strategy ``!=`` place-once), never from "any path
prawduct ever placed." Everything else — product-owned ``.prawduct/`` state
(``project-state.yaml``, ``learnings*.md``, ``backlog.md``, ``change-log.md``,
``artifacts/``) and every non-framework file (the product's own
skills, ``src/``, ``tests/``, MCP server, configs) — is preserved byte-for-byte
(the place-once contract, design §7). A real consumer (hallucinote) intermixes
~20 product skills with the 7 framework skills and ~12 product ``tools/*.py``
with the framework ``tools/lib/``, so the precise registry derivation — not a
"delete ``.claude/skills/``" sweep — is what keeps product code safe.

Plugin-native: migration is a plugin-initiated act, so this module lives ONLY in
the plugin's ``lib/`` (no counterpart in the legacy file-sync ``tools/lib/``).
Idempotent: a repo already recording ``distribution: plugin`` is a no-op.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from . import core, lifecycle_repair

# The committed install reference (design §8). Pins the marketplace + plugin
# source to ref:"main" (the release surface, §5b); autoUpdate keeps consumers
# always-latest. NOTE: ``autoUpdate`` in settings.json follows design §8 but is
# pending the Chunk-2 empirical spike (still deferred) — a ~5-line correction if
# the spike contradicts it.
INSTALL_REFERENCE: dict[str, dict] = {
    "extraKnownMarketplaces": {
        "prawduct": {
            "source": {"source": "github", "repo": "brookstalley/prawduct", "ref": "main"},
            "autoUpdate": True,
        }
    },
    "enabledPlugins": {"prawduct@prawduct": True},
}

DISTRIBUTION_KEY = "distribution"
DISTRIBUTION_VALUE = "plugin"

# The gitflow integration-base knob every gate that resolves a diff base reads
# (``coverage._resolve_base_branch``). Written at onboard/cutover ONLY when the
# remote's own default branch names something outside the main family — see
# ``detect_base_branch``.
BASE_BRANCH_KEY = "base_branch"

# Per-repo last-seen version marker (Chunk 7 banner). Gitignored at migration so
# a plugin version bump never produces a tracked-file diff (the Chunk 9 deferral
# from Chunk 7 — adding it to the frozen 1.x gitignore lists was rejected).
VERSION_MARKER = ".prawduct/.prawduct-version"

# Now-inert framework state: the sync manifest. Not in MANAGED_FILES (it is
# framework *state*, normally gitignored), but the cutover removes it explicitly.
SYNC_MANIFEST = ".prawduct/sync-manifest.json"

# MANAGED_FILES entries that are EDITED in place (block-strip / settings merge),
# never deleted.
_EDIT_IN_PLACE = frozenset({"CLAUDE.md", ".claude/settings.json"})

# --- Thin static CLAUDE.md governance anchor (Chunk 10, design §4) -----------
# The heavy PRAWDUCT block leaves the repo with the plugin; in its place migrate
# inserts this small, **static, version-free** anchor — the few hardest rules
# plus a pointer to the plugin. It is a stable contract (it changes rarely, NOT
# with every methodology revision) and carries NO version number — the active
# version is injected at runtime by the SessionStart banner. The single sentinel
# marker (deliberately NOT the BEGIN/END block markers, so `extract_block` never
# treats the anchor as a strippable block) makes anchor insertion idempotent and
# future re-anchoring detectable.
ANCHOR_SENTINEL = "PRAWDUCT:ANCHOR"
ANCHOR_MARKER = (
    "<!-- PRAWDUCT:ANCHOR — static governance pointer managed by the prawduct "
    "plugin. Keep it small and version-free: principles, methodology, and the "
    "active version live in the plugin and are injected at session start. -->"
)
STATIC_ANCHOR = f"""{ANCHOR_MARKER}

## Governance (Prawduct)

This repo is governed by **Prawduct**, installed as a Claude Code plugin — not as
committed framework files. The principles, methodology, Critic protocol, and PR
review live in the plugin and are read on demand (run `/prawduct:methodology`);
they are intentionally not copied into this repo.

**Before writing any code, STOP and read the build cycle: `/prawduct:methodology building`.**
Skipping it is the #1 governance failure.

The hardest rules (everything else is in the plugin):

- **Tests are contracts** — fix the code, never weaken a test.
- **No "pre-existing" exception** — fix what you find, or flag why you can't.
- **Never silently drop a requirement** — say so explicitly.
- **Run `/prawduct:critic` after medium+ work** — never write Critic findings
  yourself; the independence is the value.

**Enforcement is structural:** the plugin's Stop hook runs at session end and
**blocks** if code changed against an active build plan with no Critic findings.
The session-start banner shows the active version and what changed — this anchor
stays version-free.
"""


# =============================================================================
# Registry-derived plan
# =============================================================================


def framework_skill_dirs() -> list[str]:
    """The framework skill dir names, derived from the registry.

    Every ``.claude/skills/<name>/SKILL.md`` key in ``MANAGED_FILES`` yields the
    framework-owned dir ``.claude/skills/<name>``. Product skill dirs (not in the
    registry) are never returned, so they are never removed.
    """
    dirs: list[str] = []
    for rel in core.MANAGED_FILES:
        parts = rel.split("/")
        if len(parts) == 4 and parts[0] == ".claude" and parts[1] == "skills" and parts[3] == "SKILL.md":
            dirs.append(f".claude/skills/{parts[2]}")
    return sorted(dirs)


def framework_files(project_dir: Path) -> list[str]:
    """Registry-derived framework files present in the repo (the DELETE set).

    Excludes the two edit-in-place files (``CLAUDE.md``, ``.claude/settings.json``).
    Returns sorted, repo-relative paths.
    """
    found: set[str] = set()
    for rel in core.MANAGED_FILES:
        if rel in _EDIT_IN_PLACE:
            continue
        if (project_dir / rel).is_file():
            found.add(rel)
    # Managed directories (``tools/lib/*.py``) — glob the CONSUMER's dir so an
    # older/extra module set is removed in full, not the framework's current set.
    for dir_rel, cfg in core.MANAGED_DIRS.items():
        d = project_dir / dir_rel
        if d.is_dir():
            for f in sorted(d.glob(cfg.get("glob", "*"))):
                if f.is_file():
                    found.add(f"{dir_rel}/{f.name}")
    # Now-inert sync manifest (framework state, not a MANAGED_FILES entry).
    if (project_dir / SYNC_MANIFEST).is_file():
        found.add(SYNC_MANIFEST)
    return sorted(found)


def already_migrated(project_dir: Path) -> bool:
    """True when ``project-state.yaml`` already records ``distribution: plugin``."""
    state = Path(project_dir) / ".prawduct" / "project-state.yaml"
    return core.read_str_yaml_key(state, DISTRIBUTION_KEY) == DISTRIBUTION_VALUE


def claude_anchor_pending(project_dir: Path) -> bool:
    """True when migrate would change ``CLAUDE.md``.

    Either a ``PRAWDUCT:BEGIN/END`` block is present (to strip), or the static
    anchor is not yet present (to insert) — including when the file is absent
    (migrate would create it carrying the anchor). Drives the dry-run edit plan.
    """
    path = Path(project_dir) / "CLAUDE.md"
    if not path.is_file():
        return True
    content = path.read_text(encoding="utf-8")
    block, _, _ = core.extract_block(content)
    return block is not None or ANCHOR_SENTINEL not in content


#: Where the marketplace entry lives inside the contract. Presence of *this*
#: subtree is what "the repo has onboarded" means, which is why it is the one
#: path named explicitly rather than walked.
_MARKETPLACE_ENTRY_PATH = ("extraKnownMarketplaces", "prawduct")


def _contract_leaves(node: dict, path: tuple = ()) -> list[tuple[tuple, object]]:
    """Every ``(path, expected_value)`` leaf in a contract subtree, depth-first.

    Walking the constant is what makes the drift check single-source: a field
    added to :data:`INSTALL_REFERENCE` is compared with no edit here. Transcribing
    field paths instead is how a check silently stops covering half its contract.
    """
    leaves: list[tuple[tuple, object]] = []
    for key, value in node.items():
        if isinstance(value, dict):
            leaves.extend(_contract_leaves(value, path + (key,)))
        else:
            leaves.append((path + (key,), value))
    return leaves


def _dig(data: object, path: tuple):
    """Read ``path`` out of nested dicts; ``None`` if any hop is absent or not a dict."""
    node = data
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _field_label(path: tuple) -> str:
    """Operator-facing name for a contract path.

    Marketplace-entry leaves read relative to the entry (``source.ref``,
    ``autoUpdate``) because that is the object the operator is looking at in
    ``settings.json``; anything else keeps its full path (``enabledPlugins.…``).
    """
    if path[: len(_MARKETPLACE_ENTRY_PATH)] == _MARKETPLACE_ENTRY_PATH:
        return ".".join(path[len(_MARKETPLACE_ENTRY_PATH) :])
    return ".".join(path)


def install_reference_drift(project_dir: str | Path) -> dict:
    """Report how a repo's committed install reference departs from the contract.

    The contract is :data:`INSTALL_REFERENCE` itself — *walked*, never
    transcribed — so this check cannot outlive a change to the value prawduct
    writes, and cannot silently cover only part of it. This is the same
    single-source property :func:`lib.core.gitignore_contract_drift` gives the
    ``.gitignore`` contract, and it is a real parity claim: that function
    iterates its whole entry set, and so does this one. An earlier revision
    compared two hand-named field paths while making the same claim, which left
    ``enabledPlugins`` — a repo with governance switched off entirely, strictly
    worse than a version pin — completely unchecked.

    Scope is deliberately narrow in one specific way: it answers "does the
    *present* entry disagree with the contract", not "is an entry present at
    all." A repo with no ``extraKnownMarketplaces.prawduct`` entry reports
    ``present: False`` and no drift — that absence is `/prawduct:doctor` Health
    Check #1's finding, and a probe firing on it would nag every repo that has
    not onboarded yet. Note this gates on the *marketplace entry* only: once a
    repo has onboarded, every contract leaf is compared, ``enabledPlugins``
    included.

    Returns ``{"present": bool, "drifted": [{"field", "expected", "actual"}, ...]}``.
    Unreadable or malformed settings report ``present: False`` — an unparseable
    file is not evidence of drift, and guessing at one is how a nudge earns its
    dismissal.
    """
    path = Path(project_dir) / ".claude" / "settings.json"
    if not path.is_file():
        return {"present": False, "drifted": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"present": False, "drifted": []}
    if not isinstance(data, dict):
        return {"present": False, "drifted": []}

    if not isinstance(_dig(data, _MARKETPLACE_ENTRY_PATH), dict):
        return {"present": False, "drifted": []}

    drifted = [
        {"field": _field_label(leaf_path), "expected": expected, "actual": _dig(data, leaf_path)}
        for leaf_path, expected in _contract_leaves(INSTALL_REFERENCE)
        if _dig(data, leaf_path) != expected
    ]
    return {"present": True, "drifted": drifted}


# =============================================================================
# Edit-in-place transforms (each returns True iff it changed the file)
# =============================================================================


def _is_prawduct_hook(hook: object) -> bool:
    """A hook entry whose command invokes the legacy ``product-hook`` script."""
    return isinstance(hook, dict) and "product-hook" in str(hook.get("command", ""))


def transform_settings(project_dir: Path) -> bool:
    """Strip the committed prawduct hook wiring + framework banner from
    ``.claude/settings.json`` and merge the install reference.

    Preserves every user-owned key, including user-defined hooks and any other
    marketplaces/plugins. ``companyAnnouncements`` (the v1.x framework banner) is
    dropped — the plugin's SessionStart hook owns the banner now (Chunk 7).
    """
    path = Path(project_dir) / ".claude" / "settings.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    else:
        data = {}
    if not isinstance(data, dict):
        data = {}

    before = json.dumps(data, sort_keys=True)

    # Drop the framework-owned banner.
    data.pop("companyAnnouncements", None)

    # Strip prawduct hook wiring, preserving any user-defined hooks.
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        for event in list(hooks.keys()):
            groups = hooks.get(event)
            if not isinstance(groups, list):
                continue
            kept_groups: list[object] = []
            for group in groups:
                if not isinstance(group, dict):
                    kept_groups.append(group)
                    continue
                inner = group.get("hooks")
                if isinstance(inner, list):
                    kept_inner = [h for h in inner if not _is_prawduct_hook(h)]
                    if not kept_inner:
                        continue  # whole group was prawduct hooks → drop it
                    group = {**group, "hooks": kept_inner}
                kept_groups.append(group)
            if kept_groups:
                hooks[event] = kept_groups
            else:
                del hooks[event]
        if not hooks:
            data.pop("hooks", None)

    # Merge the committed install reference (shallow per top key preserves
    # sibling entries: other marketplaces, other enabled plugins).
    for top_key, mapping in INSTALL_REFERENCE.items():
        existing = data.get(top_key)
        if not isinstance(existing, dict):
            existing = {}
        existing.update(mapping)
        data[top_key] = existing

    if json.dumps(data, sort_keys=True) == before and path.is_file():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


# Framework boilerplate comments the template places *around* the PRAWDUCT
# block (outside BEGIN/END). They reference the markers, so they must go when the
# block goes — otherwise the migrated CLAUDE.md dangles a reference to markers
# that no longer exist (caught on the hallucinote acceptance copy).
_GENERATOR_COMMENT_MARKERS = (
    "Generated by Prawduct",
    "Add project-specific instructions above or below the markers",
)


def _drop_generator_comments(text: str) -> str:
    return "\n".join(
        ln for ln in text.splitlines()
        if not any(m in ln for m in _GENERATOR_COMMENT_MARKERS)
    )


def _collapse_blank_runs(text: str) -> str:
    """Collapse any run of 3+ consecutive newlines to 2 (one blank line).

    Dropping a generator-comment line that sat between two blank lines (e.g. the
    template comments between the H1 and the first product section) leaves the
    surrounding blanks adjacent, producing a triple-newline run = a double blank
    line. Cosmetic only — markdown collapses it on render — but it is a wart in a
    diff meant to be pristine, so the assembled CLAUDE.md normalises it (MIG-8C3V).
    """
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text


def apply_claude_anchor(project_dir: Path) -> bool:
    """Strip the heavy ``PRAWDUCT:BEGIN/END`` governance block (and the framework
    generator comments that bracket it) and ensure the thin static governance
    anchor (§4) is present in ``CLAUDE.md``.

    The anchor replaces the block **in place** — between the product's own content
    above and below — so the document keeps its shape (title → governance →
    product instructions). Idempotent: when the anchor is already present and no
    block remains, this is a no-op (so a re-run never duplicates the anchor).
    Returns True iff the file changed.
    """
    path = Path(project_dir) / "CLAUDE.md"
    anchor = STATIC_ANCHOR.strip()

    if not path.is_file():
        # Defensive: a file-sync repo always carries CLAUDE.md, but if it is
        # absent the migrated repo must still carry the governance anchor.
        path.write_text(f"# CLAUDE.md\n\n{anchor}\n", encoding="utf-8")
        return True

    original = path.read_text(encoding="utf-8")
    block, before, after = core.extract_block(original)

    if block is not None:
        head = _collapse_blank_runs(_drop_generator_comments(before)).rstrip("\n")
        tail = _collapse_blank_runs(_drop_generator_comments(after)).strip("\n")
        pieces = [p for p in (head, anchor, tail) if p]
        new = "\n\n".join(pieces) + "\n"
    elif ANCHOR_SENTINEL in original:
        return False  # already-migrated CLAUDE.md: anchor present, no block
    else:
        base = original.rstrip("\n")
        new = f"{base}\n\n{anchor}\n" if base else f"{anchor}\n"

    if new == original:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def _state_file_unreadable(project_dir: Path) -> "str | None":
    """Why the state file could not be read, or ``None`` when it reads fine.

    Asked only to explain a no-op. Every step that touches the state file fails
    soft, so without this three silent skips read as "nothing needed".

    **Both failure modes, not just the interesting one.** This first covered only
    `UnicodeDecodeError`, which left a permission-locked file producing exactly
    the silent half-cutover the note exists to prevent — the guard reproduced, one
    level up, the same "caught the wrong exception class" defect it was written to
    report. The two are distinguished in the message because they send the
    operator to different fixes: re-encode the file, or fix its permissions.
    """
    path = project_dir / ".prawduct" / "project-state.yaml"
    if not path.is_file():
        return None
    try:
        path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "not decodable as UTF-8"
    except OSError as exc:
        return f"could not be read ({exc.strerror or exc})"
    return None


def retired_state_keys(project_dir: Path) -> list[str]:
    """The retired ``project-state.yaml`` keys this cutover would remove.

    Reads; never writes. Used for the dry-run plan so the operator's one
    confirmation names the removal before it happens.
    """
    path = project_dir / ".prawduct" / "project-state.yaml"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return [item["key"] for item in reversed(lifecycle_repair.state_removals(text))]


def strip_retired_state(project_dir: Path) -> list[str]:
    """Remove retired framework keys from the product's state file.

    **This is framework residue, not product content.** The cutover's
    preserve-verbatim rule protects what the *product* authored; every key
    removed here was written by a framework mechanism that no longer exists —
    the derived-view model's ``views_enabled`` / ``scope_rollups``, and the
    hand-maintained ``build_state.test_tracking`` counts that the test evidence
    store replaced. Deleting them belongs to the same act that deletes the
    framework's files, and leaving them is what let them reach the plugin era in
    ten products.

    Detection lives in :mod:`lib.lifecycle_repair`, which owns the same removal
    for the already-onboarded case. The division is by *when*, not by *what*:
    this runs during the cutover, ``lifecycle-repair`` converges a repo that
    cut over before the removal existed. Neither carries its own idea of what a
    retired key is.
    """
    return lifecycle_repair.strip_state_file(
        project_dir / ".prawduct" / "project-state.yaml"
    )


def record_distribution(project_dir: Path) -> bool:
    """Append ``distribution: plugin`` to ``project-state.yaml`` when absent.

    Additive single key (the Chunk-8 stand-down signal). When the key is already
    present (any value), this is a no-op — never a duplicate key, never a clobber
    of surrounding product state.
    """
    path = Path(project_dir) / ".prawduct" / "project-state.yaml"
    if core.read_str_yaml_key(path, DISTRIBUTION_KEY) is not None:
        return False
    return _append_state_block(
        path,
        "\n# Distribution mode — set by /prawduct:migrate (v2.0.0 plugin cutover).\n"
        "# `plugin` tells the legacy file-sync hook to stand down (Chunk 8).\n"
        f"{DISTRIBUTION_KEY}: {DISTRIBUTION_VALUE}\n",
    )


def _append_state_block(path: Path, block: str) -> bool:
    """Append one comment+key block to ``project-state.yaml``, preserving endings.

    `newline=""` disables universal-newline translation, and the block is
    rewritten to match. Without both, appending one key to a CRLF product file
    rewrote every line in it to LF — so the surgical edit this promises to be
    landed as a whole-file reformat with the real change buried inside.
    `lib.lifecycle_repair` carries the same contract for the same reason, and
    the distribution append runs immediately after its removal on the same file:
    the removal preserved the endings and this call flattened them right back.

    Returns True when the block was written. Shared by every additive key this
    module records (``distribution``, ``base_branch``) so one ending-preserving
    writer covers them all — a second appender written by hand is how the CRLF
    flattening got in the first time.
    """
    content = ""
    if path.is_file():
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                content = handle.read()
        except (OSError, UnicodeDecodeError):
            # Never append to a file we could not read: the alternative is
            # writing our block over content we cannot see. The caller reports
            # this, because a cutover that silently skips the distribution
            # marker looks migrated and is not.
            return False
    if "\r\n" in content:
        block = block.replace("\n", "\r\n")
    if content and not content.endswith(("\n", "\r")):
        content += "\r\n" if "\r\n" in content else "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    core.atomic_write_text(path, content + block, encoding="utf-8", newline="")
    return True


def detect_base_branch(project_dir: Path) -> "str | None":
    """The remote's default branch when it is NOT ``main``/``master``, else None.

    The write half of #254. ``coverage._resolve_base_branch`` consults
    ``refs/remotes/origin/HEAD`` when no ``base_branch:`` is recorded, but that
    fallback is blind to the repo whose remote default is ``main`` while its
    integration branch is ``develop`` — only the written knob can see that one,
    and onboarding is where it is cheap to write. (Prawduct's own repo is
    exactly that case.)

    The decision is deliberately the SAME predicate the resolver applies, read
    from the resolver itself rather than restated here: ``origin/HEAD``
    resolving, naming ``origin/<b>`` with ``<b>`` outside ``coverage._MAIN_FAMILY``,
    and that ref existing. Two copies of "non-main-family" would drift, and the
    knob would then disagree with the gate it exists to steer.

    Three reasons this stays silent rather than guessing:

    * **A trunk repo gets no key.** Where the remote default IS ``main`` /
      ``master``, the resolver's own candidate list already answers correctly,
      so writing the knob would add a line to every ordinary repo that says
      only what the default already says — noise that later readers must
      maintain and reconcile.
    * **An absent ``origin/HEAD`` writes nothing.** A fresh ``git init``, an
      ``init`` + ``remote add``, a non-repo directory: onboarding must scaffold
      anyway, so every failure here degrades to ``None``.
    * **A dangling ``origin/HEAD`` writes nothing.** ``symbolic-ref`` happily
      names a branch that was never fetched, and a configured-but-unresolvable
      ``base_branch:`` fails the gates CLOSED. Writing an unverified name would
      convert a working repo into a broken one, so the ref must exist.

    Returns the bare branch name (``"develop"``), never ``origin/develop`` —
    the knob is a branch name and the resolver prefixes ``origin/`` itself.
    """
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return None
    # Lazily imported: `coverage` is the runtime's git-inspection layer, and the
    # cutover engine has no other reason to pull it in. Reached through the
    # module (`coverage._x`) as `ledger`, `risk` and `stale_base_probes` reach
    # the same layer's internals — the resolver owns this vocabulary.
    from . import coverage

    try:
        origin_head = coverage._origin_head_ref(project_dir)
        if not origin_head:
            return None
        branch = origin_head[len("origin/") :]
        if branch in coverage._MAIN_FAMILY:
            return None
        if not coverage._git_ref_exists(project_dir, origin_head):
            return None
    except (OSError, subprocess.SubprocessError):
        # No git on PATH, a timeout, an unreadable git dir: onboarding a repo
        # must never fail because the knob could not be inferred.
        return None
    return branch


def record_base_branch(project_dir: Path) -> "str | None":
    """Append ``base_branch: <b>`` when the remote default is non-main-family.

    Returns the recorded branch name, or ``None`` when nothing was written —
    the key is already present (never a clobber of an operator's own choice),
    the remote says ``main``/``master``/nothing, or the state file could not be
    read. See :func:`detect_base_branch` for the decision itself.
    """
    path = Path(project_dir) / ".prawduct" / "project-state.yaml"
    if core.read_str_yaml_key(path, BASE_BRANCH_KEY) is not None:
        return None
    branch = detect_base_branch(Path(project_dir))
    if branch is None:
        return None
    written = _append_state_block(
        path,
        "\n# Integration base branch — the branch feature work merges into. Every\n"
        "# gate that resolves a diff base (coverage, cumulative Critic, PR) anchors\n"
        "# here; without it they guess `main` and a gitflow repo reviews the whole\n"
        "# develop..main promotion delta. Written at onboard because origin/HEAD\n"
        f"# named `{branch}`. Change it if this repo integrates somewhere else.\n"
        f"{BASE_BRANCH_KEY}: {branch}\n",
    )
    return branch if written else None


def ensure_marker_gitignored(project_dir: Path) -> bool:
    """Add the version marker to ``.gitignore`` when not already ignored."""
    gitignore = Path(project_dir) / ".gitignore"
    content = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    if VERSION_MARKER in content.splitlines():
        return False
    parts: list[str] = []
    if content and not content.endswith("\n"):
        parts.append("\n")
    if content.strip():
        parts.append("\n")
    parts.append("# Prawduct plugin version marker (per-repo last-seen)\n")
    parts.append(VERSION_MARKER + "\n")
    gitignore.write_text(content + "".join(parts), encoding="utf-8")
    return True


# =============================================================================
# Filesystem + git helpers
# =============================================================================


def _remove_pycache(directory: Path) -> None:
    """Best-effort removal of a ``__pycache__`` subdir (compiled bytecode)."""
    cache = directory / "__pycache__"
    if cache.is_dir():
        shutil.rmtree(cache, ignore_errors=True)


def _git_untrack_kept(project_dir: Path, rel: str) -> bool:
    """``git rm --cached`` a path that should be ignored-but-kept (the marker).

    Best-effort: returns False on a non-repo, an untracked path, or any git
    error. Never deletes the working-tree file.
    """
    try:
        check = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            capture_output=True, text=True, cwd=str(project_dir), timeout=10,
        )
        if check.returncode != 0:
            return False
        rm = subprocess.run(
            ["git", "rm", "--cached", "--quiet", rel],
            capture_output=True, text=True, cwd=str(project_dir), timeout=10,
        )
        return rm.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# =============================================================================
# Orchestrator
# =============================================================================


def migrate_to_plugin(project_dir: str | Path, *, apply: bool = False) -> dict:
    """Plan (default) or apply the file-sync → plugin cutover.

    Returns a structured result: ``removed`` / ``removed_dirs`` (registry-derived
    framework files + emptied framework dirs), ``edited`` (the three edit-in-place
    files actually changed), ``gitignored`` / ``untracked`` (the version marker),
    ``already_migrated`` (idempotent no-op), and ``notes``. In dry-run the lists
    are the *plan*; with ``apply=True`` they reflect what was done.
    """
    project_dir = Path(project_dir)
    result: dict = {
        "applied": apply,
        "already_migrated": False,
        "removed": [],
        "removed_dirs": [],
        "edited": [],
        "state_keys_removed": [],
        "gitignored": [],
        "untracked": [],
        # The gitflow knob, when the remote's default branch earns one (#254).
        # None in every ordinary trunk repo — see `detect_base_branch`.
        "base_branch": None,
        "notes": [],
    }

    if already_migrated(project_dir):
        result["already_migrated"] = True
        result["notes"].append(
            "Repo already records distribution: plugin — nothing to migrate."
        )
        return result

    removals = framework_files(project_dir)
    skill_dirs = [d for d in framework_skill_dirs() if (project_dir / d).is_dir()]
    managed_dirs = [d for d in core.MANAGED_DIRS if (project_dir / d).is_dir()]

    # Edit predictions (used for the dry-run plan; the apply path recomputes the
    # real change set so a no-op edit is not over-reported).
    planned_edits: list[str] = []
    if claude_anchor_pending(project_dir):
        planned_edits.append("CLAUDE.md")
    planned_edits.append(".claude/settings.json")
    planned_state_keys = retired_state_keys(project_dir)
    # An unreadable state file is the one case where the apply path declines an
    # edit the naive plan would promise: `read_str_yaml_key` fails soft to None,
    # which is indistinguishable from "key absent" here. Over-reporting is the
    # safe direction, but the preview is what the operator's single confirmation
    # is given against, so it should describe the act that will actually happen.
    state_unreadable = _state_file_unreadable(project_dir)
    state_path = project_dir / ".prawduct" / "project-state.yaml"
    # Predicted the same way the apply decides it: only when the key is absent
    # AND the remote names a non-main-family default. Pure git inspection — a
    # dry run stays read-only.
    planned_base = (
        detect_base_branch(project_dir)
        if not state_unreadable
        and core.read_str_yaml_key(state_path, BASE_BRANCH_KEY) is None
        else None
    )
    if not state_unreadable and (
        planned_state_keys
        or planned_base
        or core.read_str_yaml_key(state_path, DISTRIBUTION_KEY) is None
    ):
        planned_edits.append(".prawduct/project-state.yaml")

    if not apply:
        result["base_branch"] = planned_base
        result["removed"] = removals
        result["removed_dirs"] = sorted(skill_dirs + managed_dirs)
        result["edited"] = planned_edits
        result["state_keys_removed"] = planned_state_keys
        result["gitignored"] = [VERSION_MARKER]
        if state_unreadable:
            result["notes"].append(
                f".prawduct/project-state.yaml {state_unreadable} — it will be left "
                "untouched, so the `distribution: plugin` marker will NOT be "
                "recorded and no retired keys will be removed. Fix the file first."
            )
        result["notes"].append(
            "Dry run — no files changed. Re-run with --apply to perform the cutover."
        )
        return result

    # --- APPLY ---
    removed: list[str] = []
    for rel in removals:
        target = project_dir / rel
        try:
            target.unlink()
            removed.append(rel)
        except OSError as exc:  # pragma: no cover - unexpected fs error
            result["notes"].append(f"could not remove {rel}: {exc}")

    removed_dirs: list[str] = []
    for rel in sorted(skill_dirs + managed_dirs):
        d = project_dir / rel
        _remove_pycache(d)
        if d.is_dir() and not any(d.iterdir()):
            try:
                d.rmdir()
                removed_dirs.append(rel)
            except OSError:  # pragma: no cover - non-empty/locked dir
                result["notes"].append(f"left {rel} in place (not empty)")

    edited: list[str] = []
    if apply_claude_anchor(project_dir):
        edited.append("CLAUDE.md")
    if transform_settings(project_dir):
        edited.append(".claude/settings.json")
    # Before the append, so the distribution marker lands at the end of a state
    # file that has already shed its retired keys rather than above them.
    state_keys_removed = strip_retired_state(project_dir)
    distribution_recorded = record_distribution(project_dir)
    base_branch = record_base_branch(project_dir)
    if distribution_recorded or state_keys_removed or base_branch:
        edited.append(".prawduct/project-state.yaml")
    else:
        unreadable = _state_file_unreadable(project_dir)
        if unreadable:
            # Said out loud rather than left to the diff. Every state-file step
            # fails soft on a file it cannot read — which is right, because none
            # of them may write over content they cannot see — but the sum of
            # three silent skips is a repo that looks cut over and never got its
            # marker.
            result["notes"].append(
                f".prawduct/project-state.yaml {unreadable} — it was left "
                "untouched, so the `distribution: plugin` marker was NOT recorded "
                "and no retired keys were removed. Fix the file and re-run."
            )

    gitignored = [VERSION_MARKER] if ensure_marker_gitignored(project_dir) else []
    untracked = [VERSION_MARKER] if _git_untrack_kept(project_dir, VERSION_MARKER) else []

    result["removed"] = removed
    result["removed_dirs"] = removed_dirs
    result["edited"] = edited
    result["state_keys_removed"] = state_keys_removed
    result["base_branch"] = base_branch
    result["gitignored"] = gitignored
    result["untracked"] = untracked
    result["notes"].append(
        "Cutover applied. Review `git status`, then commit as one reversible commit."
    )
    return result


def run(project_dir: str | Path, argv: list[str]) -> int:
    """CLI entry for ``prawduct-hook migrate-plugin [--apply] [--json]``.

    Defaults to a dry-run plan (safe). ``--apply`` performs the cutover.

    Unrecognised tokens are refused by the ``cmd_migrate_plugin`` wrapper in
    ``bin/prawduct-hook``, alongside every other flag-only guard, so the
    ``"--flag" in argv`` reads below cannot see one. Without that,
    ``--apply --dry-run`` performs the cutover while the caller believes they
    asked for a preview — the idiom reads a token it does not know as *absent*.
    """
    apply = "--apply" in argv
    json_mode = "--json" in argv
    result = migrate_to_plugin(project_dir, apply=apply)

    if json_mode:
        print(json.dumps(result, indent=2))
        return 0

    if result["already_migrated"]:
        print("Already on the plugin (distribution: plugin) — nothing to do.")
        return 0

    verb = "Removed" if apply else "Would remove"
    print(f"prawduct → plugin cutover ({'apply' if apply else 'dry run'})\n")
    if result["removed"]:
        print(f"{verb} {len(result['removed'])} framework file(s):")
        for rel in result["removed"]:
            print(f"  - {rel}")
    if result["removed_dirs"]:
        print(f"{verb} empty framework dir(s): {', '.join(result['removed_dirs'])}")
    if result["edited"]:
        print(f"{'Edited' if apply else 'Would edit'}: {', '.join(result['edited'])}")
    if result["state_keys_removed"]:
        # Named explicitly rather than folded into "edited": this is the one
        # part of the blast radius that DELETES from a file the product
        # hand-authored, and an operator giving the single confirmation this
        # operation takes has to see it before saying yes, not afterwards in the
        # diff. `--json` carried it from the start; the human path did not.
        keys = ", ".join(result["state_keys_removed"])
        print(f"{'Removed' if apply else 'Would remove'} retired state key(s): {keys}")
    if result["base_branch"]:
        # Named, not folded into "edited": it changes what every diff-base gate
        # measures against, and the operator is the one who knows whether this
        # repo really integrates on that branch.
        print(
            f"{'Recorded' if apply else 'Would record'} "
            f"base_branch: {result['base_branch']} (origin/HEAD names it — every "
            "diff-base gate will anchor here)"
        )
    if result["gitignored"]:
        print(f"Gitignored: {', '.join(result['gitignored'])}")
    for note in result["notes"]:
        print(f"\n{note}")
    return 0
