"""SessionStart briefing assembly + cross-/clear session handoff.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 7 — the final chunk). Holds
the session-start surface the SessionStart (``clear``) hook renders: the
content-based staleness scan, the structured session briefing (project identity,
work-in-progress, other-branch WIP, worktree awareness, advisories, learnings,
backlog), the subagent governance briefing, and the cross-``/clear`` session
handoff. Plus the previous-session governance check ``cmd_clear`` warns on.

``cmd_clear`` itself STAYS in the hook (it is the deliberately-inline hot-path
SessionStart entry point that orchestrates session-marker hygiene, the advisory
probe step, and the git baseline; design constraint 1). It reaches these
functions via the lazy ``_briefing()`` accessor — the hook's five resident call
sites (``staleness_scan`` / ``assemble_session_briefing`` /
``generate_subagent_briefing`` / ``_check_previous_session_gates`` in
``cmd_clear`` itself, and ``generate_session_handoff`` in its boundary helper
``_boundary_close_session``, which runs only at a real session boundary) are each
already wrapped in a broad catch, so a ``lib.briefing`` import failure on an
incomplete plugin install degrades to a skipped briefing (stderr NOTE) and never
blocks session start — the lib-free hook top level is preserved (the ch.2–6
precedent, no separate degradation shim).

Depends on its lib siblings ``gitstate`` / ``gates`` / ``buildplan_refs`` and
``core`` (``resolve_build_plan_path`` — the canonical twin of the hook's
parity-pinned inline ``_resolve_build_plan_path`` mirror), plus the stdlib.
``briefing`` is the top of the decomposition DAG — nothing imports it. Sanctioned
rewrites of the moved bodies (behavior-preserving): ``get_prawduct_dir`` →
``gitstate.get_prawduct_dir``, ``_resolve_build_plan_path`` →
``core.resolve_build_plan_path``, the ``_gitstate()`` / ``_gates()`` /
``_buildplan_refs()`` accessor calls → direct sibling references.
"""


from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from . import buildplan_refs, gates, gitstate
from .backlog import legacy as backlog
from .coverage import _resolve_base_branch
from .core import (
    BUILD_PLAN_POINTER_KEY,
    atomic_write_text,
    read_str_yaml_key,
    resolve_build_plan_path,
)


# =============================================================================
# Staleness Scan (v5: content-based artifact freshness)
# =============================================================================


def _plan_work_possibly_unmerged(
    project_dir: Path, prawduct_dir: Path
) -> tuple[bool, str]:
    """Is the completed plan's work plausibly still unmerged? ``(bool, reason)``.

    The build plan is session-local and gitignored, so it survives a branch
    switch: complete every chunk on a feature branch, check out the base branch,
    and the staleness scan recommends deleting a plan whose work has not shipped.
    Following that advice orphans live work — reported from the field.

    Two independent sufficient signals, either one enough:

    1. **Foreign-branch WIP** — ``project-state.yaml`` records work in progress
       on a branch other than the current one. That is the reported repro
       exactly: a plan surviving a switch onto the base branch.
    2. **Branch ahead of base** — the current branch is not the base and
       ``git merge-base --is-ancestor HEAD <base>`` says HEAD is not reachable
       from it, i.e. this branch has commits the base does not.

    Signal 1 is checked first and does not need a resolvable branch, so on a
    detached HEAD every recorded WIP entry counts as foreign and the answer is
    "keep". That is deliberate — an unidentifiable HEAD is the *worst* moment to
    recommend deleting a plan — but it means the fail-toward-``(False, "")``
    posture below describes signal 2 only.

    Signal 2 fails toward ``(False, "")`` on every uncertainty: no base resolves,
    git unavailable, any return code other than the "not an ancestor" 1. Both
    signals may only ADD a keep-recommendation on positive evidence; neither may
    silently suppress a legitimate delete nudge, because a plan that really is
    finished and merged should still be cleaned up.
    """
    try:
        current_branch = gitstate.current_branch(project_dir)
        others = _get_other_branch_wip(prawduct_dir, current_branch or "")
        if others:
            return True, (
                f"{len(others)} other branch(es) still record work in progress"
            )

        base, _ = _resolve_base_branch(project_dir)
        if not base or current_branch is None:
            return False, ""
        # `base` may be `origin/develop`; compare against the bare branch name
        # too, so standing ON the base branch is recognized either spelling.
        if current_branch in (base, base.removeprefix("origin/")):
            return False, ""
        proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "HEAD", base],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        # rc 0 = HEAD is reachable from base (merged). rc 1 = not an ancestor
        # (unmerged). Any other rc is an error — fail toward "merged" so the
        # ordinary nudge survives.
        if proc.returncode == 1:
            return True, f"its commits are not yet in {base}"
        return False, ""
    except (OSError, subprocess.SubprocessError):
        return False, ""


def _extract_dependency_names(dep_file: Path) -> list[str]:
    """Extract package names from dependency files."""
    try:
        content = dep_file.read_text()
    except Exception:  # prawduct:allow prawduct/broad-except -- dependency scanning is best-effort
        return []

    name = dep_file.name

    if name == "requirements.txt":
        deps = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            match = re.match(r"([a-zA-Z0-9][a-zA-Z0-9._-]*)", line)
            if match:
                deps.append(match.group(1).lower())
        return deps

    if name == "package.json":
        try:
            data = json.loads(content)
            deps = list(data.get("dependencies", {}).keys())
            deps += list(data.get("devDependencies", {}).keys())
            return deps
        except (json.JSONDecodeError, AttributeError):
            return []

    return []


def staleness_scan(project_dir: Path) -> list[str]:
    """Lightweight content-based staleness checks. Returns list of warnings."""
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    findings: list[str] = []

    state_path = prawduct_dir / "project-state.yaml"
    if not state_path.is_file():
        return findings

    try:
        state_content = state_path.read_text()
    except Exception:  # prawduct:allow prawduct/broad-except -- staleness scan is best-effort
        return findings

    # 1. Architecture coverage (test_count is now computed, not tracked)
    source_root_match = re.search(r"source_root:\s*[\"']?([^\"'\n#]+)", state_content)
    source_root = None
    if source_root_match:
        val = source_root_match.group(1).strip().strip("\"'")
        if val and val != "null":
            source_root = val

    arch_path = prawduct_dir / "artifacts" / "architecture.md"
    if source_root and arch_path.is_file():
        try:
            arch_content = arch_path.read_text()
            src_dir = project_dir / source_root
            if src_dir.is_dir():
                candidates = [
                    d.name
                    for d in sorted(src_dir.iterdir())
                    if d.is_dir()
                    and not d.name.startswith((".", "__"))
                    and d.name not in arch_content
                ]
                # A git-IGNORED directory is not architecture — it is scratch,
                # build output, or vendored dependencies, and architecture.md is
                # right not to name it. Without this the probe reported
                # `node_modules` to every JS product, `target` to every Rust one,
                # and any local scratch dir to everybody, forever: a permanent
                # advisory whose only remedy is documenting something that should
                # not be documented. Batched into ONE `check-ignore` call, and
                # only when there is something to ask about, so the session-start
                # hot path pays nothing on a clean repo.
                relative = [f"{source_root.rstrip('/')}/{name}" for name in candidates]
                ignored = gitstate.git_paths_ignored(project_dir, relative)
                unmentioned = [
                    name
                    for name, rel in zip(candidates, relative)
                    if rel not in ignored
                ]
                if unmentioned:
                    findings.append(
                        f"architecture: {', '.join(unmentioned[:3])} in {source_root}/ not in architecture.md"
                    )
        except Exception:  # prawduct:allow prawduct/broad-except -- staleness scan is best-effort
            pass

    # 3. Dependency coverage
    dep_manifest = prawduct_dir / "artifacts" / "dependency-manifest.md"
    if dep_manifest.is_file():
        try:
            manifest_content = dep_manifest.read_text().lower()
            for dep_file_name in ["requirements.txt", "package.json"]:
                dep_file = project_dir / dep_file_name
                if dep_file.is_file():
                    dep_names = _extract_dependency_names(dep_file)
                    missing = [d for d in dep_names if d.lower() not in manifest_content]
                    if missing:
                        preview = ", ".join(missing[:3])
                        more = f" +{len(missing) - 3} more" if len(missing) > 3 else ""
                        findings.append(
                            f"dependencies: {len(missing)} in {dep_file_name} not in manifest ({preview}{more})"
                        )
        except Exception:  # prawduct:allow prawduct/broad-except -- staleness scan is best-effort
            pass

    # 4. Stale build plan detection — check Status section first, fall back to WIP
    build_plan_path = resolve_build_plan_path(prawduct_dir)
    build_plan_label = f".prawduct/{build_plan_path.relative_to(prawduct_dir).as_posix()}"
    if build_plan_path.is_file():
        try:
            status = buildplan_refs._parse_build_plan_status(project_dir)
            if status.get("current_chunk"):
                pass  # Active work — not stale
            elif buildplan_refs.build_plan_is_complete(status):
                # All items checked — work complete
                unmerged, unmerged_reason = _plan_work_possibly_unmerged(
                    project_dir, prawduct_dir
                )
                if unmerged:
                    findings.append(
                        f"build plan: {build_plan_label} has all chunks complete but "
                        f"{unmerged_reason} — keep the plan until it merges "
                        "(deleting now would orphan unshipped work)"
                    )
                else:
                    findings.append(
                        f"build plan: {build_plan_label} has all chunks complete — "
                        "if work is done, delete the plan"
                    )
            else:
                # No Status items — check WIP as fallback for old-style repos
                current_branch = _get_current_branch(project_dir)
                wip = _parse_wip(prawduct_dir, branch=current_branch)
                if not wip.get("description"):
                    unmerged, unmerged_reason = _plan_work_possibly_unmerged(
                        project_dir, prawduct_dir
                    )
                    if unmerged:
                        findings.append(
                            f"build plan: {build_plan_label} exists but no active work, and "
                            f"{unmerged_reason} — keep the plan until it merges "
                            "(deleting now would orphan unshipped work)"
                        )
                    else:
                        findings.append(
                            f"build plan: {build_plan_label} exists but no active work — "
                            "if work is complete, delete the plan"
                        )
        except Exception:  # prawduct:allow prawduct/broad-except -- staleness scan is best-effort
            pass

    # 5. Completed but uncleaned build plan in state
    if not build_plan_path.is_file():
        try:
            if "\n  strategy:" in state_content:
                strategy_match = re.search(r"\n  strategy:\s*(.+)", state_content)
                if strategy_match:
                    strategy_val = strategy_match.group(1).strip().strip("\"'")
                    if strategy_val and strategy_val != "null":
                        if not gates._has_build_plan_in_state(prawduct_dir):
                            findings.append(
                                "build plan: project-state.yaml has a completed build plan "
                                "(strategy set, no active chunks) — consider resetting to defaults"
                            )
        except Exception:  # prawduct:allow prawduct/broad-except -- staleness scan is best-effort
            pass

    return findings


# =============================================================================
# Session Briefing (v5: structured context for SessionStart)
# =============================================================================


def _get_product_name(prawduct_dir: Path) -> str:
    """Extract product name from project-state.yaml."""
    state_path = prawduct_dir / "project-state.yaml"
    if not state_path.is_file():
        return "Unknown"
    try:
        content = state_path.read_text()
        in_identity = False
        for line in content.splitlines():
            if "product_identity:" in line:
                in_identity = True
            elif in_identity and line.strip().startswith("name:"):
                val = line.split(":", 1)[1].strip().strip("\"'")
                if val and val != "null" and not val.startswith("{{"):
                    return val
                break
            elif in_identity and not line.startswith(" ") and line.strip():
                break
    except Exception:  # prawduct:allow prawduct/broad-except -- product name extraction is best-effort
        pass
    return "Unknown"


def _get_current_branch(project_dir: Path) -> str:
    """Get current git branch name. Returns 'main' on failure/detached — a
    display default for the briefing. Contrast ``gitstate.current_branch``,
    which returns None so a caller that must not be MISLED about which tree it
    resolved to (the Critic's visibility print) can tell (PDT-WT9K)."""
    return gitstate.current_branch(project_dir) or "main"


def _parse_wip(prawduct_dir: Path, branch: str | None = None) -> dict[str, str]:
    """Parse work_in_progress fields from project-state.yaml.

    Supports two formats:
    - Branch-scoped (v6+): fields nested under branch name key
    - Flat (legacy): fields directly under work_in_progress

    When branch is None, auto-detects from git. Returns a dict of non-null
    field values, or empty dict on any failure.
    """
    state_path = prawduct_dir / "project-state.yaml"
    if not state_path.is_file():
        return {}
    try:
        if branch is None:
            branch = _get_current_branch(prawduct_dir.parent)

        content = state_path.read_text()
        in_wip = False
        in_branch = False
        is_flat = False
        wip: dict[str, str] = {}

        for line in content.splitlines():
            stripped = line.strip()

            # Find work_in_progress section
            if stripped.startswith("work_in_progress:"):
                in_wip = True
                continue

            if not in_wip:
                continue

            # Exit WIP section on unindented non-empty line
            if line and not line[0].isspace() and stripped:
                break

            # Detect format: 2-space indent with known field = flat; otherwise branch-keyed
            if not in_branch and not is_flat and line.startswith("  ") and not line.startswith("    "):
                key_part = stripped.split(":")[0].strip()
                if key_part in ("description", "size", "type", "current_chunk", "governance_level", "context"):
                    # Flat format (legacy) — parse directly
                    is_flat = True

            if is_flat:
                # Flat format: 2-space indent = field
                if line.startswith("  ") and ":" in line:
                    key, _, val = stripped.partition(":")
                    val = val.strip().strip("\"'")
                    if val and val != "null":
                        wip[key.strip()] = val
                continue

            # Branch-keyed format: look for our branch at 2-space indent
            if line.startswith("  ") and not line.startswith("    "):
                # This is a branch key line like "  feature/foo:" or "  main:"
                branch_key = stripped.rstrip(":").strip()
                if branch_key == branch:
                    in_branch = True
                elif in_branch:
                    # We were in our branch, hit another branch — done
                    break
            elif in_branch and line.startswith("    ") and ":" in line:
                # 4-space indent = field under our branch
                key, _, val = stripped.partition(":")
                val = val.strip().strip("\"'")
                if val and val != "null":
                    wip[key.strip()] = val

        return wip
    except Exception:  # prawduct:allow prawduct/broad-except -- WIP extraction is best-effort
        return {}


def _parse_all_wip_branches(prawduct_dir: Path) -> dict[str, dict[str, str]]:
    """Parse all branch WIP entries. Returns {branch: {field: value}} dict.

    For flat format, returns {"_flat": {fields}}.
    """
    state_path = prawduct_dir / "project-state.yaml"
    if not state_path.is_file():
        return {}
    try:
        content = state_path.read_text()
        in_wip = False
        branches: dict[str, dict[str, str]] = {}
        current_branch: str | None = None

        for line in content.splitlines():
            stripped = line.strip()

            if stripped.startswith("work_in_progress:"):
                in_wip = True
                continue

            if not in_wip:
                continue

            if line and not line[0].isspace() and stripped:
                break

            # 2-space indent, not 4-space = branch key (or flat field)
            if line.startswith("  ") and not line.startswith("    "):
                key_part = stripped.split(":")[0].strip()
                if key_part in ("description", "size", "type", "current_chunk", "governance_level", "context"):
                    # Flat format
                    if "_flat" not in branches:
                        branches["_flat"] = {}
                    val_part = stripped.partition(":")[2].strip().strip("\"'")
                    if val_part and val_part != "null":
                        branches["_flat"][key_part] = val_part
                else:
                    # Branch key
                    current_branch = stripped.rstrip(":").strip()
                    if current_branch not in branches:
                        branches[current_branch] = {}
            elif current_branch and line.startswith("    ") and ":" in line:
                key, _, val = stripped.partition(":")
                val = val.strip().strip("\"'")
                if val and val != "null":
                    branches[current_branch][key.strip()] = val

        return branches
    except Exception:  # prawduct:allow prawduct/broad-except -- WIP extraction is best-effort
        return {}


def _get_active_work(project_dir: Path) -> dict[str, str]:
    """Get active work context, preferring build plan Status over project-state.yaml WIP.

    A build plan whose chunks are ALL complete is not active work. Without that
    predicate a finished plan was reported as the next session's ``**Task**``
    forever — ``staleness_scan`` read the identical parse and correctly said
    "all chunks complete", while this function said "in progress" from the same
    bytes. Both now ask ``buildplan_refs.build_plan_is_complete``.
    """
    work = buildplan_refs._parse_build_plan_status(project_dir)
    if work.get("description") and not buildplan_refs.build_plan_is_complete(work):
        return work
    return _parse_wip(gitstate.get_prawduct_dir(project_dir))


def _get_work_in_progress(project_dir: Path, wip: dict[str, str] | None = None) -> str:
    """Format work in progress as a one-line summary for the session briefing.

    ``wip`` lets a caller that has already resolved the active work pass it in;
    resolution reads git on a ``views_enabled`` repo, and the briefing needs the
    same answer twice.
    """
    if wip is None:
        wip = _get_active_work(project_dir)
    if wip.get("description"):
        parts = [wip["description"]]
        qualifiers = []
        if wip.get("size"):
            qualifiers.append(wip["size"])
        if wip.get("type"):
            qualifiers.append(wip["type"])
        if qualifiers:
            parts.append(f"({', '.join(qualifiers)})")
        return " ".join(parts)
    return "none active"


def _detect_worktrees(project_dir: Path) -> list[dict[str, str]]:
    """Return a list of git worktrees attached to this repo, or [] if not in a repo
    or only one worktree exists.

    Each entry: {"path": str, "branch": str, "is_active": "true"/"false"}.
    "is_active" is "true" for the worktree at project_dir.
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=10,
        )
        if result.returncode != 0:
            return []
    except Exception:  # prawduct:allow prawduct/broad-except -- worktree detection is best-effort
        return []

    # Porcelain output: groups of "worktree <path>", "HEAD <sha>", "branch refs/heads/<name>"
    # (or "detached"), separated by blank lines.
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            if current:
                worktrees.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            current["path"] = line.removeprefix("worktree ").strip()
        elif line.startswith("branch "):
            current["branch"] = line.removeprefix("branch ").removeprefix("refs/heads/").strip()
        elif line == "detached":
            current["branch"] = "(detached)"
    if current:
        worktrees.append(current)

    if len(worktrees) <= 1:
        return []  # Single worktree = no need to surface; degenerate case.

    project_resolved = str(project_dir.resolve())
    for w in worktrees:
        wpath = w.get("path", "")
        try:
            w["is_active"] = "true" if Path(wpath).resolve() == Path(project_resolved) else "false"
        except OSError:
            w["is_active"] = "false"
    return worktrees


def _get_other_branch_wip(prawduct_dir: Path, current_branch: str) -> list[str]:
    """Get one-line summaries of WIP on other branches."""
    all_wip = _parse_all_wip_branches(prawduct_dir)
    others = []
    for branch, fields in all_wip.items():
        if branch == current_branch or branch == "_flat":
            continue
        desc = fields.get("description", "")
        if desc:
            others.append(f"{branch}: {desc}")
    return others


#: Leading glyph of the advisory relay directive. A *directive to the agent*, not a
#: severity signal, so it sits outside the ``CRITICAL:``/``WARNING:``/``NOTE:``
#: vocabulary and alongside the briefing's own ``•``/``→`` line glyphs.
ADVISORY_RELAY_MARKER = "⇒ "

#: Advisory priorities worth interrupting a person for. `info` is excluded on
#: purpose: it repeats every session until dismissed, and a channel that nags is a
#: channel that gets tuned out — which would cost the `warn` case its audience.
_RELAY_PRIORITIES = frozenset({"warn", "urgent"})

#: Why this exists: the briefing prints to stdout, which this project's ratified
#: observability norm defines as the AGENT-facing channel (stderr is the person's).
#: So an advisory is an instruction the model reads, not a nudge the owner reads —
#: and an advisory whose recommended action is the owner's call to make goes
#: unanswered every session while looking, from the inside, perfectly delivered.
#: Relaying it into conversation is what makes the owner's decision reachable.
ADVISORY_RELAY_TEXT = (
    f"{ADVISORY_RELAY_MARKER}Tell the user about the advisories above, in your first "
    "reply this session — they do not see this briefing. Theirs to action, not yours "
    "to silently resolve or dismiss."
)


def assemble_session_briefing(project_dir: Path, staleness: list[str]) -> str:
    """Assemble session briefing text. Target: <400 tokens (excluding handoff pointer)."""
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    lines = ["== SESSION BRIEFING =="]

    # Project identity + work in progress (branch-scoped). Resolved once and
    # reused below — on a views_enabled repo this reads git.
    project_name = _get_product_name(prawduct_dir)
    current_branch = _get_current_branch(project_dir)
    wip = _get_active_work(project_dir)
    work_desc = _get_work_in_progress(project_dir, wip)
    lines.append(f"Project: {project_name} | Branch: {current_branch} | Work: {work_desc}")

    # Dangling build-plan pointer guard (STH-5P2W). A SET pointer that resolves
    # to no file means governance treats the repo as having NO active plan —
    # the Critic gate, plan-aware mode inference, and chunk-ref verification
    # all go silently blind (this happened live for a full work cycle). Say so
    # at the top of the briefing, every session, until the pointer is fixed.
    try:
        pointer = read_str_yaml_key(
            prawduct_dir / "project-state.yaml", BUILD_PLAN_POINTER_KEY
        )
        if pointer:
            pointed = resolve_build_plan_path(prawduct_dir)
            if not pointed.is_file():
                rel = pointed.relative_to(prawduct_dir).as_posix()
                lines.append(
                    f"⚠ active_build_plan points at a MISSING file: '{pointer}' "
                    f"resolved to .prawduct/{rel}. Governance sees no active plan "
                    "(Critic gate, mode inference, and chunk-ref checks are blind). "
                    "Fix the pointer in project-state.yaml — it is .prawduct/-relative "
                    "(e.g. artifacts/build-plan-<scope>.md) — or unset it."
                )
    except Exception:  # prawduct:allow prawduct/broad-except -- briefing must never block session start
        pass

    # Work context and current chunk (resolved above; build plan Status
    # preferred, falling back to WIP)
    if wip.get("current_chunk"):
        lines.append(f"Resume: {wip['current_chunk']}")
    if wip.get("context"):
        # The briefing has a token budget, so it takes the first 200 chars of
        # what may now be a multi-paragraph block. The handoff carries it whole.
        ctx = " ".join(wip["context"].split())
        if len(ctx) > 200:
            ctx = ctx[:197] + "..."
        lines.append(f"Context: {ctx}")

    # Other branches with active WIP
    other_wip = _get_other_branch_wip(prawduct_dir, current_branch)
    if other_wip:
        lines.append(f"Other active branches: {len(other_wip)}")
        for owip in other_wip[:3]:  # Cap at 3 to keep briefing concise
            lines.append(f"  - {owip}")

    # Worktree awareness — surface only when more than one worktree exists.
    # Hooks operate on $CLAUDE_PROJECT_DIR; if the agent thinks it is in a
    # different worktree, gates will look at the wrong tree. Orient the agent to
    # THIS worktree only — deliberately WITHOUT enumerating sibling worktrees'
    # branches/paths. That list read as a menu of adoptable work and lured
    # agents into another worktree (which may hold another live session's WIP);
    # siblings stay discoverable on demand via `git worktree list`.
    worktrees = _detect_worktrees(project_dir)
    if worktrees:
        active = next((w for w in worktrees if w.get("is_active") == "true"), None)
        active_branch = active.get("branch", "?") if active else "?"
        active_path = active.get("path", str(project_dir)) if active else str(project_dir)
        lines.append(
            f"Worktree: operating on '{active_branch}' at {active_path} — work and gates "
            f"are scoped to THIS worktree only. Other worktrees belong to their own "
            f"sessions; do not read or modify them."
        )

    # Handoff from previous session
    handoff_path = prawduct_dir / ".session-handoff.md"
    if handoff_path.is_file():
        lines.append("Previous session context available: read .prawduct/.session-handoff.md")

    # Staleness warnings
    if staleness:
        for s in staleness:
            lines.append(f"Stale: {s}")

    # ADVISORIES (post-sync) — the per-clone nag log `.prawduct/.advisories.json`,
    # refreshed by cmd_clear's probe step before the briefing is assembled (the
    # file-sync runtime refreshed it during `sync`). Read here via the
    # dependency-light standalone reader (not the bundled advisory_store) so the
    # briefing stays robust on a partial install. Active advisories are listed
    # priority-ordered (urgent→warn→info, then newest first), capped at 5. Empty
    # active set with nothing newly resolved → omit the section entirely
    # (spec §5.2 / A5 — no "0 active" noise).
    adv_store = gitstate._read_advisory_store(prawduct_dir)
    adv_all = adv_store.get("advisories", []) if isinstance(adv_store, dict) else []
    active_adv = [a for a in adv_all if isinstance(a, dict) and a.get("state") == "active"]
    # Stable two-pass sort: newest-first within each priority band.
    active_adv.sort(key=lambda a: a.get("triggered_at") or "", reverse=True)
    _adv_prio = {"urgent": 0, "warn": 1, "info": 2}
    active_adv.sort(key=lambda a: _adv_prio.get(a.get("priority", "info"), 2))
    # "Resolved/Dismissed since last session" — entries that transitioned at or
    # after this session's start stamp (the just-run sync resolves; dismissals
    # carry their own timestamp).
    resolved_since = 0
    dismissed_since = 0
    session_start_path = prawduct_dir / ".session-start"
    if session_start_path.is_file():
        try:
            session_start_ts = session_start_path.read_text().strip()
        except OSError:
            session_start_ts = ""
        if session_start_ts:
            resolved_since = sum(
                1
                for a in adv_all
                if isinstance(a, dict)
                and a.get("state") == "resolved"
                and (a.get("resolved_at") or "") >= session_start_ts
            )
            dismissed_since = sum(
                1
                for a in adv_all
                if isinstance(a, dict)
                and a.get("state") == "dismissed"
                and (a.get("dismissed_at") or "") >= session_start_ts
            )
    if active_adv or resolved_since or dismissed_since:
        if active_adv:
            lines.append(f"ADVISORIES (post-sync, {len(active_adv)} active):")
            for adv in active_adv[:5]:
                feature = adv.get("feature", "?")
                summary = adv.get("trigger_summary", "")
                lines.append(f"  • [{feature}] {summary}")
                action = adv.get("recommended_action", "")
                if action:
                    aid = adv.get("id", "")
                    lines.append(f"    → Run {action} (or /prawduct:advisory dismiss {aid})")
            if len(active_adv) > 5:
                lines.append(
                    f"  ... and {len(active_adv) - 5} more (run /prawduct:advisory list)"
                )
            # Relay directive — see ADVISORY_RELAY_TEXT. Keyed off the full active
            # set rather than the displayed slice. Today the two agree: the sort
            # above ranks `urgent`/`warn` ahead of `info`, so a relay-priority
            # advisory can only be displaced by another one and is always visible.
            # Keying off the full set means that stays correct if the sort changes,
            # rather than silently going quiet on the case it exists for.
            if any(a.get("priority") in _RELAY_PRIORITIES for a in active_adv):
                lines.append(ADVISORY_RELAY_TEXT)
        else:
            lines.append("ADVISORIES (post-sync):")
        if dismissed_since:
            lines.append(
                f"  Dismissed since last session: {dismissed_since} "
                f"(run /prawduct:advisory list --state=dismissed to see)"
            )
        if resolved_since:
            lines.append(f"  Resolved since last session: {resolved_since}")

    # CLAUDE.md size check
    claude_md_path = project_dir / "CLAUDE.md"
    if claude_md_path.is_file():
        try:
            claude_content = claude_md_path.read_text()
            claude_lines = claude_content.splitlines()
            total_lines = len(claude_lines)
            # Count project-specific lines (outside PRAWDUCT markers)
            in_prawduct = False
            prawduct_lines = 0
            for cl in claude_lines:
                if "PRAWDUCT:BEGIN" in cl:
                    in_prawduct = True
                elif "PRAWDUCT:END" in cl:
                    in_prawduct = False
                    prawduct_lines += 1  # count the END line itself
                elif in_prawduct:
                    prawduct_lines += 1
            project_lines = total_lines - prawduct_lines
            # Only surface genuine bloat. The soft ~150-line guideline is already
            # enforced by the Critic at review time (the actionable moment); a
            # 250+ line CLAUDE.md is a real problem worth a standing reminder.
            # Re-nagging every session at the soft threshold was pure tax.
            if project_lines > 250:
                lines.append(
                    f"CLAUDE.md is large ({project_lines} project lines) — move architecture "
                    f"docs, config tables, and component inventories to docs/ or .prawduct/artifacts/"
                )
        except Exception:  # prawduct:allow prawduct/broad-except -- briefing must never block session start
            pass

    # (Cut: per-session "Tests: ~N" count and the "Last Critic review took …"
    # timing quip. Neither is actionable at session start — the canonical test
    # count lives in .test-evidence.json, and a past review's duration is noise.)

    # Relevant learnings — show count + pointer so Claude knows rules exist
    learnings_path = prawduct_dir / "learnings.md"
    if learnings_path.is_file():
        try:
            learnings_content = learnings_path.read_text()
            # One rule per `## ` entry (the documented learnings format). The
            # bullet count is a fallback for legacy bullet-list files — counting
            # bullets FIRST under-reported entry-format files as 0 rules, which
            # silently dropped this line on any repo using the real format
            # (found while landing the MET-6W3J size nudge below).
            heading_count = sum(
                1 for line in learnings_content.splitlines() if line.startswith("## ")
            )
            bullet_count = sum(
                1 for line in learnings_content.splitlines() if line.strip().startswith("- ")
            )
            rule_count = heading_count or bullet_count
            # Collapse to a count + pointer. The full topic index re-printed
            # unchanged every session — a static table of contents is tax; the
            # /prawduct:learnings skill is the intended lookup path.
            if rule_count > 0:
                lines.append(f"Learnings ({rule_count} rules): /prawduct:learnings <topic> or read .prawduct/learnings.md")
            # Size nudge (MET-6W3J): every /prawduct:learnings lookup and
            # Critic learnings cross-check reads the whole file, so size is a
            # recurring per-session cost — same 40KB threshold and mechanical-
            # check pattern as the project-state.yaml warning. (An earlier 8KB
            # clear-hook warning was retired when the fork-skill lookup landed;
            # at ~80KB the lookup itself became the cost, so the nudge returns
            # at the project-state threshold.)
            size = learnings_path.stat().st_size
            if size > 40000:  # ~10K tokens ≈ ~40KB
                lines.append(
                    f"learnings.md is large ({size // 1024}KB > 40KB) — compact: keep each "
                    "entry's When-X-do-Y-because-Z rule here, move narrative to "
                    "learnings-detail.md (never delete it)"
                )
        except Exception:  # prawduct:allow prawduct/broad-except -- briefing must never block session start
            pass

    # Backlog — surface the count of outstanding items (cutover-aware; see
    # _backlog_pending_line for the adapter-vs-markdown routing).
    try:
        backlog_line = _backlog_pending_line(prawduct_dir, project_dir)
        if backlog_line:
            lines.append(backlog_line)
    except Exception:  # prawduct:allow prawduct/broad-except -- briefing must never block session start
        pass

    return "\n".join(lines)


def _backlog_pending_line(
    prawduct_dir: Path, project_dir: Path, *, popen=None, now=None
) -> str | None:
    """The one-line backlog rollup for the session briefing, cutover-aware.

    **Post-cutover** (``backlog_service_repo: owner/repo`` set in
    ``project-state.yaml`` — written by the migration session): read the GV2
    ``briefing_counts`` snapshot with its **visible age**, then fire the
    **detached** refresh warm (``snapshot.spawn_refresh``). The briefing path
    touches **no network, ever** — the never-block requirement (BLOCK-5 /
    NFR §6 "few s") is satisfied structurally, not by a timeout: a stalled or
    slow backend costs the briefing nothing because the backend is only reached
    by the fire-and-forget child. No snapshot yet → a clear "warming" line, and
    the warm is still fired (the next session reads it).

    **Pre-cutover** (key absent): parse the markdown backlog exactly as before.
    ``popen``/``now`` are injectable for tests.
    """
    scope = read_str_yaml_key(prawduct_dir / "project-state.yaml", "backlog_service_repo")
    if scope:
        from .backlog import encode, snapshot  # noqa: PLC0415 — lazy; pre-cutover repos never pay it

        path = snapshot.snapshot_path(project_dir)
        snap = snapshot.read(path, scope, now=now) if path else None
        # Read the snapshot first, then warm — the warm's outcome decides what the
        # no-snapshot line may honestly claim, so its result is never discarded.
        warmed = _spawn_snapshot_warm(project_dir, scope, popen=popen)
        line = None
        if snap and isinstance(snap.get("counts"), dict):
            by_status = snap["counts"].get("by_status") or {}
            # OPEN_STATUSES derives from encode's status SoT — no out-of-band copy.
            pending = sum(by_status.get(status, 0) for status in encode.OPEN_STATUSES)
            if pending:
                age = _humanize_age(snap.get("age_seconds"))
                line = (
                    f"Backlog: {pending} pending on {scope} "
                    f"(snapshot {age}; /prawduct:backlog to triage)"
                )
        elif warmed:
            # Degrade visibly, never silently (G3): the count is not available
            # yet, and the warm just fired — the next session start has it.
            line = f"Backlog: counts warming for {scope} (/prawduct:backlog to triage)"
        else:
            # The warm never started, so "warming" would be a standing falsehood —
            # a session that says it forever is indistinguishable from one in
            # flight, and the child's stderr goes to DEVNULL. Name the real state
            # and hand back the manual path.
            line = (
                f"Backlog: counts unavailable for {scope} — background refresh "
                f"could not start; run `prawduct-hook backlog refresh-counts "
                f"--repo {scope}` (/prawduct:backlog to triage)"
            )
        return line

    backlog_path = prawduct_dir / "backlog.md"
    if not backlog_path.is_file():
        return None
    pending_items = backlog.parse_backlog(backlog_path.read_text()).pending_items()
    if not pending_items:
        return None
    # One count line, not a 5-item dump every session. /prawduct:backlog is the
    # triage path; dumping arbitrary items here was tax.
    return f"Backlog: {len(pending_items)} pending (/prawduct:backlog to triage)"


def _spawn_snapshot_warm(project_dir: Path, scope: str, *, popen=None) -> bool:
    """Fire the detached snapshot refresh (D6). Never raises, never waits."""
    from .backlog import snapshot  # noqa: PLC0415 — lazy

    hook = Path(__file__).resolve().parent.parent / "bin" / "prawduct-hook"
    if not hook.is_file():
        return False
    return snapshot.spawn_refresh(
        [sys.executable, str(hook)], project_dir, scope, popen=popen
    )


def _humanize_age(age_seconds) -> str:
    """``age_seconds`` → a compact human age ("just now", "4m old", "3h old")."""
    if not isinstance(age_seconds, (int, float)) or age_seconds < 0:
        return "age unknown"
    if age_seconds < 60:
        return "just now"
    if age_seconds < 3600:
        return f"{int(age_seconds // 60)}m old"
    if age_seconds < 86400:
        return f"{int(age_seconds // 3600)}h old"
    return f"{int(age_seconds // 86400)}d old"


# =============================================================================
# Subagent Briefing (v5: governance context for delegated agents)
# =============================================================================


def _extract_critical_rules(project_dir: Path) -> list[str]:
    """Extract Critical Rules bullet points from the project's CLAUDE.md.

    Falls back to a minimal hardcoded set if extraction fails.
    """
    fallback = [
        "- Write tests alongside code, never after.",
        "- Never weaken a test to make it pass. Fix the code, not the test.",
        "- Never silently drop a requirement. If you can't implement it, say so.",
        "- Never catch broad exceptions without logging and re-raising.",
        "- Run the full test suite before finishing work.",
        "- When changes cross boundaries (API, database, IPC), verify consumers.",
    ]
    claude_md = project_dir / "CLAUDE.md"
    if not claude_md.is_file():
        return fallback
    try:
        content = claude_md.read_text()
        # Find Critical Rules section
        in_section = False
        rules: list[str] = []
        for line in content.splitlines():
            if line.strip().startswith("## Critical Rules"):
                in_section = True
                continue
            if in_section and line.strip().startswith("## "):
                break
            if in_section and line.strip().startswith("- **"):
                rules.append(line.strip())
        return rules if rules else fallback
    except Exception:  # prawduct:allow prawduct/broad-except -- rule extraction is best-effort
        return fallback


def generate_subagent_briefing(project_dir: Path) -> None:
    """Generate .prawduct/.subagent-briefing.md for subagent governance."""
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    if not prawduct_dir.is_dir():
        return

    project_name = _get_product_name(prawduct_dir)
    rules = _extract_critical_rules(project_dir)

    sections = [
        f"# Subagent Briefing — {project_name}\n",
        "Read this file before starting work. It contains project-specific governance rules.\n",
        "## Governance Rules\n",
        *[r for r in rules],
        "",
    ]

    # Project preferences
    prefs_path = prawduct_dir / "artifacts" / "project-preferences.md"
    if prefs_path.is_file():
        try:
            prefs = prefs_path.read_text().strip()
            if prefs and "- **Language**:\n" not in prefs:
                sections.append("## Project Preferences\n")
                lines = prefs.splitlines()
                summary_lines = []
                past_header = False
                for line in lines:
                    if line.startswith("# "):
                        past_header = True
                        continue
                    if past_header:
                        summary_lines.append(line)
                    if len(summary_lines) > 30:
                        summary_lines.append("(see full file for details)")
                        break
                sections.append("\n".join(summary_lines).strip() + "\n")
        except Exception:  # prawduct:allow prawduct/broad-except -- briefing generation is best-effort
            pass

    # Active learnings
    learnings_path = prawduct_dir / "learnings.md"
    if learnings_path.is_file():
        try:
            learnings = learnings_path.read_text().strip()
            if learnings:
                sections.append("## Active Learnings\n")
                sections.append(learnings + "\n")
        except Exception:  # prawduct:allow prawduct/broad-except -- briefing generation is best-effort
            pass

    (prawduct_dir / ".subagent-briefing.md").write_text("\n".join(sections))


# =============================================================================
# Session Handoff (context transfer across /clear boundaries)
# =============================================================================


def _git_session_commits(project_dir: Path) -> list[str]:
    """Get commit subjects made during this session. Returns list of one-line summaries."""
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    session_start_path = prawduct_dir / ".session-start"
    if not session_start_path.is_file():
        return []
    try:
        since = session_start_path.read_text().strip()
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--oneline", "--no-decorate"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()
    except Exception:  # prawduct:allow prawduct/broad-except -- commit listing is best-effort
        pass
    return []


def _summarize_critic_findings(prawduct_dir: Path) -> str | None:
    """Extract a brief summary from .critic-findings.json. Returns None if unavailable."""
    findings_path = prawduct_dir / ".critic-findings.json"
    if not findings_path.is_file():
        return None
    try:
        data = json.loads(findings_path.read_text())
        summary = data.get("summary", "")
        findings = data.get("findings", [])
        if not summary and not findings:
            return None
        parts = []
        if summary:
            parts.append(summary)
        if findings:
            blocking = [f for f in findings if f.get("severity") == "blocking"]
            warnings = [f for f in findings if f.get("severity") == "warning"]
            notes = [f for f in findings if f.get("severity") == "note"]
            counts = []
            if blocking:
                counts.append(f"{len(blocking)} blocking")
            if warnings:
                counts.append(f"{len(warnings)} warning")
            if notes:
                counts.append(f"{len(notes)} note")
            if counts:
                parts.append(f"Findings: {', '.join(counts)}")
            for f in blocking:
                parts.append(f"  BLOCKING: {f.get('summary', 'no summary')}")
            for f in warnings[:3]:
                parts.append(f"  WARNING: {f.get('summary', 'no summary')}")
        return "\n".join(parts)
    except Exception:  # prawduct:allow prawduct/broad-except -- findings summarization is best-effort
        return None


# The machine marker. Every generated handoff carries it as its first body
# line; its absence is how the generator recognises a `.session-handoff.md`
# that a model or a human wrote by hand, so it can be rescued rather than
# overwritten. Detection matches the stable PREFIX, never the whole line, so
# the human-readable tail can be reworded without stranding older files.
HANDOFF_MARKER_PREFIX = "<!-- prawduct:generated-handoff"
HANDOFF_MARKER = (
    f"{HANDOFF_MARKER_PREFIX} — written by the machine at /clear. Do not hand-edit: "
    "the next /clear regenerates this file. Forward notes for the next session go in "
    "`.prawduct/.handoff-notes.md`. -->"
)

# The forward channel: the one file in the handoff pair that a model owns.
HANDOFF_NOTES_NAME = ".handoff-notes.md"

# What became of the notes file this run. The caller deletes on CARRIED and
# EMPTY and on nothing else: "absent" has nothing to delete, and the two
# failure states hold text that never reached the handoff, so unlinking them
# would destroy the note — the exact loss this channel exists to prevent.
# Collapsing "unreadable" into "no notes" is what makes that mistake easy, so
# the states are kept distinct all the way to the deletion site.
NOTES_ABSENT = "absent"
NOTES_EMPTY = "empty"
NOTES_CARRIED = "carried"
NOTES_UNREADABLE = "unreadable"
NOTES_UNDELIVERED = "undelivered"

# What became of an existing `.session-handoff.md` the machine did not write.
# Same reason the notes states exist: "nothing to preserve" and "could not read
# the thing I am about to overwrite" demand opposite handling, and collapsing
# them into one empty string is what made the destructive case invisible.
RESCUE_NONE = "none"
RESCUE_CARRIED = "carried"
RESCUE_UNREADABLE = "unreadable"


class HandoffResult(NamedTuple):
    """Outcome of a handoff generation: was it written, and what became of the notes."""

    written: bool
    notes_state: str

    @property
    def notes_consumed(self) -> bool:
        """True when the notes file may be deleted without losing anything."""
        return self.notes_state in (NOTES_CARRIED, NOTES_EMPTY)


class HandoffRender(NamedTuple):
    """The assembled handoff text, and what each input contributed to it.

    ``text`` is ``""`` whenever there is nothing to write: no ``.prawduct/``,
    nothing beyond the boilerplate header, or an existing handoff that could not
    be read — and the last of those is the one the writer must handle
    differently (leave the file alone rather than overwrite it), which is why
    ``rescue_state`` is carried alongside rather than folded into the text.
    """

    text: str
    notes_state: str
    rescue_state: str


def _read_handoff_notes(prawduct_dir: Path) -> tuple[str, str]:
    """Read the model-authored forward notes as ``(text, state)``.

    The counterpart to every other handoff source, which is machine state
    looking backward: this is the only place an agent can leave intent for the
    next session. Consumed into the handoff and then cleared by `/clear`, so a
    note never outlives the session boundary it was written for.

    The state is returned rather than inferred from an empty string because
    "there were no notes" and "the notes could not be read" demand opposite
    handling at the deletion site.
    """
    notes_path = prawduct_dir / HANDOFF_NOTES_NAME
    if not notes_path.is_file():
        return "", NOTES_ABSENT
    try:
        # Explicit encoding: the notes are markdown written by an agent, and
        # decodability must not depend on the operator's locale.
        text = notes_path.read_text(encoding="utf-8").strip()
    except (UnicodeDecodeError, OSError):
        return "", NOTES_UNREADABLE
    return (text, NOTES_CARRIED if text else NOTES_EMPTY)


def _read_unmarked_handoff(prawduct_dir: Path) -> tuple[str, str]:
    """Return ``(body, state)`` for a `.session-handoff.md` the machine did not write.

    A file without :data:`HANDOFF_MARKER_PREFIX` was authored by a model or a
    human, and overwriting it is exactly the silent context loss this generator
    exists to prevent — so its body is preserved into the new handoff instead.
    Belt to the notes channel's braces: the channel is the documented path, this
    catches the agent who writes the familiar filename out of habit.

    The state is returned rather than inferred from an empty body, for the same
    reason its sibling :func:`_read_handoff_notes` returns one. A bare ``""``
    meant three different things here — absent, machine-generated, and
    *unreadable* — and the caller reads it as "nothing to preserve" and
    overwrites. So the one failure the net exists to survive destroyed the file
    silently. Reachable, not exotic: this read had no explicit ``encoding``, so
    it used the operator's locale, and a single em dash in a model-authored
    handoff raises ``UnicodeDecodeError`` under ``LC_ALL=C``.

    Undecodable bytes are recovered lossily rather than dropped — replacement
    characters in a preserved paragraph beat a deleted one. Only a file that
    cannot be read at all yields :data:`RESCUE_UNREADABLE`, and the caller
    declines to overwrite on it.
    """
    handoff_path = prawduct_dir / ".session-handoff.md"
    if not handoff_path.is_file():
        return "", RESCUE_NONE
    try:
        existing = handoff_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            existing = handoff_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "", RESCUE_UNREADABLE
    except OSError:
        return "", RESCUE_UNREADABLE
    if HANDOFF_MARKER_PREFIX in existing:
        return "", RESCUE_NONE
    body = existing.strip()
    # Drop a leading "# Session Handoff" H1 so the rescued body nests cleanly
    # under its own section heading instead of re-titling the document.
    lines = body.splitlines()
    if lines and lines[0].strip().lower() == "# session handoff":
        body = "\n".join(lines[1:]).strip()
    return (body, RESCUE_CARRIED if body else RESCUE_NONE)


def _no_forward_note_section(changed: list[str], commits: list[str]) -> list[str]:
    """The handoff's own statement that its forward half is missing.

    Advice fails soft, so nothing here blocks anything — but failing soft is
    not failing silent. A handoff that lists a session's commits and says
    nothing else *reads* as a complete account of that session, which is how
    continuity got lost while the agent reported success. When work happened
    and no forward note was left, the handoff says so, in the position the note
    would have occupied.

    Empty when the session produced no diff. Stated honestly, that is a *limit*
    rather than a claim that nothing happened — a design or discovery session
    has plenty to hand off and leaves no files changed. What it does mean is
    that the handoff for such a session is visibly thin, so it cannot pass for a
    complete account the way a list of commits can, and a notice fired on every
    read-only session would only teach the reader to skip the section.
    """
    if not changed and not commits:
        return []
    did = []
    if changed:
        did.append(f"{len(changed)} file{'' if len(changed) == 1 else 's'} changed")
    if commits:
        did.append(f"{len(commits)} commit{'' if len(commits) == 1 else 's'}")
    return [
        "## No Forward Note From The Previous Session",
        "<!-- the machine can report this absence; it cannot fill it -->",
        f"That session ({', '.join(did)}) left no `.prawduct/{HANDOFF_NOTES_NAME}`. "
        "Everything below is machine-derived and backward-looking: a record of what "
        "happened, not a statement of what to do next or of what the previous agent "
        "knew and did not write down. Re-derive intent from the build plan rather "
        "than reading this handoff as complete.",
        "",
    ]


def render_session_handoff(project_dir: Path) -> HandoffRender:
    """Assemble the handoff text without writing, deleting, or consuming anything.

    Split out from :func:`generate_session_handoff` so the content can be
    inspected without causing it. `/clear` is the only other way to see this
    text, and it is also the act that destroys what it replaces — so until this
    existed, the check that would prevent the mistake required making it.

    Reads the repo and nothing else: no file is created, modified, or removed
    here, and the notes file is never consumed. The states it reports are what
    the writer needs in order to decide both of those.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    if not prawduct_dir.is_dir():
        return HandoffRender("", NOTES_ABSENT, RESCUE_NONE)

    sections: list[str] = ["# Session Handoff", "", HANDOFF_MARKER, ""]
    # Everything above is boilerplate every run emits; content is anything past it.
    header_len = len(sections)

    # 0. The model's forward notes come first, above every machine section —
    #    intent for the next session outranks the record of the last one.
    notes, notes_state = _read_handoff_notes(prawduct_dir)
    if notes:
        sections.append("## Notes For The Next Session")
        sections.append("<!-- written by the previous session's agent, not the machine -->")
        sections.append(notes)
        sections.append("")

    # 0b. Preservation net: rescue a handoff the machine did not write.
    rescued, rescue_state = _read_unmarked_handoff(prawduct_dir)
    if rescue_state == RESCUE_UNREADABLE:
        # The one case where NOT writing is the safe move. The file cannot be
        # read, so it cannot be folded in, so writing would destroy content that
        # may be the previous agent's only forward context. Rendering stops here
        # and reports the state; the writer declines and narrates it.
        return HandoffRender("", notes_state, rescue_state)
    if rescued:
        sections.append("## Preserved: Hand-Authored Handoff")
        sections.append(
            "<!-- the previous `.session-handoff.md` had no machine marker, so it was "
            "authored by a model or a human and is preserved here rather than "
            f"overwritten. Write forward notes to `.prawduct/{HANDOFF_NOTES_NAME}` instead — "
            "this file is regenerated on every /clear. -->"
        )
        sections.append(rescued)
        sections.append("")

    # What the session actually did. Read here rather than at their own sections
    # below because the no-forward-note signal is a judgement about the same
    # facts, and deriving "was this a substantive session" from a second source
    # would let the two answers drift.
    changed = gitstate._get_session_changed_files(project_dir)
    commits = _git_session_commits(project_dir)

    # 0c. The forward channel exists and was not used. Deliberately NOT fired on
    # NOTES_UNREADABLE: a note WAS left there, and saying otherwise would blame
    # the agent for the machine's failure to read it — that state has its own
    # notice at the consumption site. A rescued hand-authored handoff is forward
    # context too, so it suppresses this as well.
    if notes_state in (NOTES_ABSENT, NOTES_EMPTY) and not rescued:
        sections.extend(_no_forward_note_section(changed, commits))

    # 1. Work context (prefer build plan Status, fall back to project-state.yaml WIP)
    wip = _get_active_work(project_dir)
    if wip.get("description"):
        sections.append("## Work In Progress")
        sections.append(f"**Task**: {wip['description']}")
        qualifiers = []
        if wip.get("size"):
            qualifiers.append(f"size={wip['size']}")
        if wip.get("type"):
            qualifiers.append(f"type={wip['type']}")
        if wip.get("governance_level"):
            qualifiers.append(f"governance={wip['governance_level']}")
        if qualifiers:
            sections.append(f"**Classification**: {', '.join(qualifiers)}")
        if wip.get("context"):
            sections.append(f"**Context**: {wip['context']}")
        if wip.get("current_chunk"):
            sections.append(f"**Current chunk**: {wip['current_chunk']}")
        sections.append("")

    # 2. Session reflection (from .session-reflected, before it gets archived)
    reflected_path = prawduct_dir / ".session-reflected"
    if reflected_path.is_file():
        try:
            reflection = reflected_path.read_text().strip()
            if reflection:
                sections.append("## Previous Session Reflection")
                sections.append(reflection)
                sections.append("")
        except Exception:  # prawduct:allow prawduct/broad-except -- handoff generation is best-effort
            pass

    # 3. Critic findings summary
    critic_summary = _summarize_critic_findings(prawduct_dir)
    if critic_summary:
        sections.append("## Critic Findings")
        sections.append(critic_summary)
        sections.append("")

    # 4. Files changed during session
    if changed:
        sections.append("## Files Changed This Session")
        for f in changed[:20]:  # Cap at 20 to keep handoff manageable
            sections.append(f"- {f}")
        if len(changed) > 20:
            sections.append(f"- ... and {len(changed) - 20} more")
        sections.append("")

    # 5. Commits made during session
    if commits:
        sections.append("## Commits This Session")
        for c in commits[:10]:
            sections.append(f"- {c}")
        if len(commits) > 10:
            sections.append(f"- ... and {len(commits) - 10} more")
        sections.append("")

    # Nothing beyond the boilerplate header means nothing to write — and,
    # because the rescued body counts as content, that verdict is only reached
    # when there is no hand-authored context either. Deliberately NOT a guard on
    # overwriting: preservation happens by folding the old body in above, never
    # by declining to write.
    #
    # Non-empty notes always push past header_len, so an empty render can never
    # coincide with notes pending — nothing is dropped by returning "".
    text = "\n".join(sections) + "\n" if len(sections) > header_len else ""
    return HandoffRender(text, notes_state, rescue_state)


def generate_session_handoff(project_dir: Path) -> HandoffResult:
    """Write .prawduct/.session-handoff.md with context for the next session.

    Called during /clear BEFORE session files are deleted. The content comes
    from :func:`render_session_handoff` (the model-authored forward notes, any
    hand-authored handoff being rescued, WIP context, session reflection, critic
    findings, files changed, and commits made during the session); this function
    owns only the two things a preview must not do — writing the file, and
    narrating the failures to the audience that can act on them.

    Reports whether a handoff was written and what became of the notes, so the
    caller can clear the notes file only once its text is durably in the
    handoff. A note that was never carried — unreadable, or lost to a failed
    write — survives for the next `/clear` rather than being dropped.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    if not prawduct_dir.is_dir():
        return HandoffResult(False, NOTES_ABSENT)

    rendered = render_session_handoff(project_dir)
    notes_state = rendered.notes_state

    if rendered.rescue_state == RESCUE_UNREADABLE:
        # The existing handoff could not be read, so it could not be folded in,
        # so writing would destroy content that may be the previous agent's only
        # forward context. Say so on stdout — SessionStart shows stdout to the
        # model, and the incoming agent is the party harmed by a stale handoff.
        print(
            "NOTE: .prawduct/.session-handoff.md could not be read, so it was left "
            "untouched rather than overwritten — anything you read in it is from an "
            "earlier session, and this session's context is NOT in it. Move or fix "
            f"that file, then write forward notes to `.prawduct/{HANDOFF_NOTES_NAME}`."
        )
        return HandoffResult(
            False, NOTES_UNDELIVERED if notes_state == NOTES_CARRIED else notes_state
        )

    if rendered.text:
        try:
            # Atomic: the next session's briefing reads this file, and a torn
            # handoff silently loses cross-session context.
            atomic_write_text(prawduct_dir / ".session-handoff.md", rendered.text)
            return HandoffResult(True, notes_state)
        except Exception as exc:  # prawduct:allow prawduct/broad-except -- handoff write must never block clear
            # Fails soft, but never silent — degrading gracefully and narrating
            # false success are not the same thing. This half is the operator's:
            # a write that failed is theirs to diagnose, so it goes to stderr
            # with its housekeeping siblings. The agent-facing half (a note that
            # did not reach the next session) is emitted by the caller on
            # stdout, which is the channel the incoming agent actually reads.
            print(
                f"NOTE: could not write .session-handoff.md ({exc}) — this session's "
                "context will not reach the next one"
                + (
                    f"; {HANDOFF_NOTES_NAME} is kept for the next /clear"
                    if notes_state == NOTES_CARRIED
                    else ""
                ),
                file=sys.stderr,
            )
            return HandoffResult(
                False, NOTES_UNDELIVERED if notes_state == NOTES_CARRIED else notes_state
            )
    return HandoffResult(False, notes_state)


def handoff_cmd(project_dir: Path, argv: list[str]) -> int:
    """``prawduct-hook handoff preview`` — what the next session would receive.

    Read-only by construction: it renders through the same function `/clear`
    does and stops, so the preview is the artifact rather than a description of
    it, and looking is not the same act as replacing. Nothing is written and the
    notes file is never consumed.

    Exit codes per ``artifacts/api-contract.md``: 0 for a successful preview,
    including the truthful "nothing would be written"; 1 when the preview cannot
    be produced (no ``.prawduct/``, or the render failed); 2 for a usage error.
    Content goes to stdout so it can be piped; every diagnostic goes to stderr so
    it cannot be mistaken for content.
    """
    if argv[:1] != ["preview"] or len(argv) > 1:
        print("Usage: prawduct-hook handoff preview", file=sys.stderr)
        return 2

    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    if not prawduct_dir.is_dir():
        print("handoff: no .prawduct/ in this repo — nothing to preview", file=sys.stderr)
        return 1

    try:
        rendered = render_session_handoff(project_dir)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- CLI boundary: the error model forbids a stack trace crossing it
        # Every reader on the render path degrades internally, so reaching here
        # means something unanticipated. It still gets an attributed message and
        # an exit code rather than a traceback, because that is what the caller
        # can act on — and because a *preview* crashing must not read as
        # evidence that `/clear` itself is broken.
        print(f"handoff: could not render the preview ({exc})", file=sys.stderr)
        return 1
    if rendered.rescue_state == RESCUE_UNREADABLE:
        print(
            "NOTE: .prawduct/.session-handoff.md exists and cannot be read, so /clear "
            "would leave it untouched rather than overwrite it — the next session would "
            "read an EARLIER session's handoff. Move or fix that file.",
            file=sys.stderr,
        )
        return 0
    # Before any verdict about the content: a note that exists and cannot be
    # read is the one fact the preview must not omit, and it is orthogonal to
    # whether anything else would be written. Reporting "nothing to hand off"
    # first made the preview and `/clear` disagree about exactly that — `/clear`
    # announces the unreadable note, so a preview that swallowed it would send
    # the agent away reassured about the case most worth acting on.
    if rendered.notes_state == NOTES_UNREADABLE:
        print(
            f"NOTE: .prawduct/{HANDOFF_NOTES_NAME} exists and could not be read (not "
            "valid UTF-8?) — none of it is in the preview, and none of it would reach "
            "the next session. It is kept, not consumed; rewrite or remove it.",
            file=sys.stderr,
        )

    if not rendered.text:
        print(
            "NOTE: nothing to hand off yet — /clear would leave "
            ".prawduct/.session-handoff.md exactly as it is.",
            file=sys.stderr,
        )
        return 0

    print(rendered.text, end="")
    return 0


# =============================================================================
# Previous-session governance check (cmd_clear warns, never blocks)
# =============================================================================


def _check_previous_session_gates(project_dir: Path) -> list[str]:
    """Check if the previous session had unmet governance gates.

    Returns list of warning messages. Used by cmd_clear to warn (not block)
    when starting a new session without completing the previous one's governance.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    warnings: list[str] = []

    # Capture `git status --porcelain` once and thread it through the three
    # baseline-diff probes below (STH-6Q9D) instead of each re-spawning git.
    status_output = gitstate.git_status_output(project_dir)

    # Was there a previous session with changes?
    had_changes = gitstate.git_has_session_changes(project_dir, status_output)
    if not had_changes:
        return warnings

    # Honor any waivers the previous session declared (file is deleted right
    # after this check runs, so waivers never carry past the gate they covered).
    waivers = gates._read_gates_waived(prawduct_dir)

    # Gate 1: Reflection (skipped for doc-only changes or when waived).
    # "Doc-only" = no judgeable session change (the one predicate, via gates —
    # kernel-v3 chunk 04).
    doc_only = gates.session_changes_all_non_judgeable(project_dir, status_output)
    if not doc_only and "reflection" not in waivers:
        reflected_file = prawduct_dir / ".session-reflected"
        try:
            if not reflected_file.is_file() or len(reflected_file.read_text().strip()) < 50:
                warnings.append("reflection not captured")
        except (UnicodeDecodeError, OSError):
            warnings.append("reflection not captured")

    # Gate 2: Critic review (only when building against an active plan).
    # STH-4F7C: delegates to the shared lib/gates.py session gate — the same
    # composed-coverage verdict cmd_stop blocks on (kernel-v3 chunk 04), so
    # the advisory and the blocking gate can never diverge. Advisory tone:
    # one warning line, not the full remedy text.
    has_build_plan = gates._has_active_build_plan_file(prawduct_dir) or gates._has_build_plan_in_state(prawduct_dir)
    if has_build_plan and not doc_only and "critic" not in waivers and gitstate.git_has_code_changes(project_dir, status_output):
        verdict = gates.session_review_verdict(project_dir)
        status = verdict.get("status")
        if status == "blocked":
            warnings.append(
                f"Critic review left {len(verdict.get('unresolved', []))} "
                "unresolved blocking finding(s)"
            )
        elif status != "covered":
            warnings.append("Critic review not recorded")

    return warnings
