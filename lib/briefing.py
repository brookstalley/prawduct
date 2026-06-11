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
functions via the lazy ``_briefing()`` accessor — its five resident call sites
(``staleness_scan`` / ``assemble_session_briefing`` / ``generate_subagent_briefing``
/ ``generate_session_handoff`` / ``_check_previous_session_gates``) are each
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
from pathlib import Path

from . import backlog, buildplan_refs, gates, gitstate
from .core import BUILD_PLAN_POINTER_KEY, read_str_yaml_key, resolve_build_plan_path


# =============================================================================
# Staleness Scan (v5: content-based artifact freshness)
# =============================================================================


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
                unmentioned = []
                for d in sorted(src_dir.iterdir()):
                    if d.is_dir() and not d.name.startswith((".", "__")):
                        if d.name not in arch_content:
                            unmentioned.append(d.name)
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
            status = buildplan_refs._parse_build_plan_status(prawduct_dir)
            if status.get("current_chunk"):
                pass  # Active work — not stale
            elif status.get("_has_status_items"):
                # All items checked — work complete
                findings.append(
                    f"build plan: {build_plan_label} has all chunks complete — "
                    "if work is done, delete the plan"
                )
            else:
                # No Status items — check WIP as fallback for old-style repos
                current_branch = _get_current_branch(project_dir)
                wip = _parse_wip(prawduct_dir, branch=current_branch)
                if not wip.get("description"):
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
    """Get current git branch name. Returns 'main' on failure."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=str(project_dir), timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:  # prawduct:allow prawduct/broad-except -- branch detection is best-effort
        pass
    return "main"


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


def _get_active_work(prawduct_dir: Path) -> dict[str, str]:
    """Get active work context, preferring build plan Status over project-state.yaml WIP."""
    work = buildplan_refs._parse_build_plan_status(prawduct_dir)
    if work.get("description"):
        return work
    return _parse_wip(prawduct_dir)


def _get_work_in_progress(prawduct_dir: Path) -> str:
    """Format work in progress as a one-line summary for the session briefing."""
    wip = _get_active_work(prawduct_dir)
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


def assemble_session_briefing(project_dir: Path, staleness: list[str]) -> str:
    """Assemble session briefing text. Target: <400 tokens (excluding handoff pointer)."""
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    lines = ["== SESSION BRIEFING =="]

    # Project identity + work in progress (branch-scoped)
    project_name = _get_product_name(prawduct_dir)
    current_branch = _get_current_branch(project_dir)
    work_desc = _get_work_in_progress(prawduct_dir)
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

    # Work context and current chunk (prefer build plan Status, fall back to WIP)
    wip = _get_active_work(prawduct_dir)
    if wip.get("current_chunk"):
        lines.append(f"Resume: {wip['current_chunk']}")
    if wip.get("context"):
        ctx = wip["context"]
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
    # Hooks operate on $CLAUDE_PROJECT_DIR; if the agent thinks they are in a
    # different worktree, gates will look at the wrong tree. Surfacing this
    # avoids silent confusion (see issue: discodon worktree gate firing on
    # main repo branch state).
    worktrees = _detect_worktrees(project_dir)
    if worktrees:
        active = next((w for w in worktrees if w.get("is_active") == "true"), None)
        active_branch = active.get("branch", "?") if active else "?"
        active_path = active.get("path", str(project_dir)) if active else str(project_dir)
        lines.append(
            f"Worktrees: {len(worktrees)} attached — hook is operating on '{active_branch}' "
            f"at {active_path}. Other worktrees are NOT visible to gates this session."
        )
        for w in worktrees:
            if w.get("is_active") == "true":
                continue
            lines.append(f"  - {w.get('branch', '?')} @ {w.get('path', '?')}")

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

    # Backlog — surface the count of outstanding items. Parsed via lib.backlog so
    # the count tracks the structured item format (Open + Promoted, minus struck /
    # resolved) rather than a hand-rolled line scan.
    backlog_path = prawduct_dir / "backlog.md"
    if backlog_path.is_file():
        try:
            pending = backlog.parse_backlog(backlog_path.read_text()).pending_items()
            if pending:
                # One count line, not a 5-item dump every session. /prawduct:backlog
                # is the triage path; dumping arbitrary items here was tax.
                lines.append(f"Backlog: {len(pending)} pending (/prawduct:backlog to triage)")
        except Exception:  # prawduct:allow prawduct/broad-except -- briefing must never block session start
            pass

    return "\n".join(lines)


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


def generate_session_handoff(project_dir: Path) -> None:
    """Generate .prawduct/.session-handoff.md with context for the next session.

    Called during /clear BEFORE session files are deleted. Assembles handoff
    from: WIP context, session reflection, critic findings, files changed,
    and commits made during the session.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    if not prawduct_dir.is_dir():
        return

    sections: list[str] = ["# Session Handoff", ""]

    # 1. Work context (prefer build plan Status, fall back to project-state.yaml WIP)
    wip = _get_active_work(prawduct_dir)
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
    changed = gitstate._get_session_changed_files(project_dir)
    if changed:
        sections.append("## Files Changed This Session")
        for f in changed[:20]:  # Cap at 20 to keep handoff manageable
            sections.append(f"- {f}")
        if len(changed) > 20:
            sections.append(f"- ... and {len(changed) - 20} more")
        sections.append("")

    # 5. Commits made during session
    commits = _git_session_commits(project_dir)
    if commits:
        sections.append("## Commits This Session")
        for c in commits[:10]:
            sections.append(f"- {c}")
        if len(commits) > 10:
            sections.append(f"- ... and {len(commits) - 10} more")
        sections.append("")

    # Only write if there's actual content beyond the header
    if len(sections) > 2:
        try:
            (prawduct_dir / ".session-handoff.md").write_text("\n".join(sections) + "\n")
        except Exception:  # prawduct:allow prawduct/broad-except -- handoff write must never block clear
            pass


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

    # Was there a previous session with changes?
    had_changes = gitstate.git_has_session_changes(project_dir)
    if not had_changes:
        return warnings

    # Honor any waivers the previous session declared (file is deleted right
    # after this check runs, so waivers never carry past the gate they covered).
    waivers = gates._read_gates_waived(prawduct_dir)

    # Gate 1: Reflection (skipped for doc-only changes or when waived)
    doc_only = gitstate._session_changes_are_doc_only(project_dir)
    if not doc_only and "reflection" not in waivers:
        reflected_file = prawduct_dir / ".session-reflected"
        try:
            if not reflected_file.is_file() or len(reflected_file.read_text().strip()) < 50:
                warnings.append("reflection not captured")
        except (UnicodeDecodeError, OSError):
            warnings.append("reflection not captured")

    # Gate 2: Critic review (only when building against an active plan).
    # STH-4F7C: delegates to the shared lib/gates.py session gate — the same
    # freshness + schema + verify-resolutions scope logic cmd_stop blocks on.
    # This advisory copy had diverged (no scope check), so it could report a
    # stale verify-resolutions record as satisfying.
    has_build_plan = gates._has_active_build_plan_file(prawduct_dir) or gates._has_build_plan_in_state(prawduct_dir)
    if has_build_plan and not doc_only and "critic" not in waivers and gitstate.git_has_code_changes(project_dir):
        satisfied, scope_reason = gates.critic_findings_satisfy_session_gate(
            prawduct_dir, project_dir
        )
        if not satisfied:
            if scope_reason:
                warnings.append(
                    f"Critic review stale — verify-resolutions scope exceeded: {scope_reason}"
                )
            else:
                warnings.append("Critic review not recorded")

    return warnings
