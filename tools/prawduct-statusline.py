#!/usr/bin/env python3
"""
prawduct-statusline.py — Claude Code statusline for prawduct sessions.

Reads Claude Code's stdin JSON, combines with project state and governance
data, and outputs a 1-2 line statusline. Line 1 shows prawduct state (session
state, work detail, governance todos). Line 2 shows universal session info
(context bar, git, duration). Non-prawduct projects get only Line 2.

Performance target: <100ms. Key optimizations:
- No `import yaml` — line-level parsing for the ~6 fields needed
- mtime-based cache — YAML parsing only runs when the file changes
- Atomic cache writes — tempfile + rename to prevent partial reads
- Silent failure — every I/O operation wrapped; errors produce blank output
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

RESET = "\033[0m"
ORANGE = "\033[38;2;255;140;60m"
BOLD_CYAN = "\033[1;36m"
BOLD_RED = "\033[1;31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"

SHRIMP = "\U0001f990"

GIT_CACHE_TTL = 5  # seconds


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def _cache_path(project_dir: str) -> str:
    h = hashlib.md5(project_dir.encode()).hexdigest()
    return f"/tmp/prawduct-statusline-{h}.json"


def _load_cache(project_dir: str) -> dict:
    try:
        with open(_cache_path(project_dir)) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(project_dir: str, data: dict) -> None:
    path = _cache_path(project_dir)
    try:
        fd, tmp = tempfile.mkstemp(dir="/tmp", prefix="prawduct-sl-")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.rename(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def _file_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Data extraction: project state (line-level YAML)
# ---------------------------------------------------------------------------

def extract_project_state(prawduct_dir: str) -> dict | None:
    """Parse minimal fields from project-state.yaml without a YAML library."""
    ps_path = os.path.join(prawduct_dir, "project-state.yaml")
    if not os.path.isfile(ps_path):
        return None

    result = {
        "current_stage": None,
        "current_chunk": None,
        "total_chunks": 0,
        "obs_next_count": 0,
    }

    try:
        with open(ps_path) as f:
            lines = f.readlines()
    except Exception:
        return None

    in_build_plan = False
    in_chunks = False
    in_obs_backlog = False
    in_obs_items = False
    chunk_count = 0
    obs_next = 0

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Track top-level sections (no leading whitespace)
        if line[0:1] not in (" ", "\t"):
            in_build_plan = False
            in_chunks = False
            in_obs_backlog = False
            in_obs_items = False

            if line.startswith("current_stage:"):
                val = stripped.split(":", 1)[1].strip().strip("'\"")
                if val and val != "null":
                    result["current_stage"] = val
            elif line.startswith("build_plan:"):
                in_build_plan = True
            elif line.startswith("observation_backlog:"):
                in_obs_backlog = True
            continue

        # Inside build_plan section
        if in_build_plan:
            if stripped.startswith("current_chunk:"):
                val = stripped.split(":", 1)[1].strip().strip("'\"")
                if val and val != "null":
                    result["current_chunk"] = val
            elif stripped == "chunks:":
                in_chunks = True
            elif stripped.startswith("chunks:") and stripped.endswith("[]"):
                in_chunks = False
            elif in_chunks and stripped.startswith("- "):
                chunk_count += 1
            elif in_chunks and not stripped.startswith("- ") and ":" in stripped:
                if line.startswith("  ") and not line.startswith("    "):
                    in_chunks = False

        # Inside observation_backlog section
        if in_obs_backlog:
            if stripped == "items:":
                in_obs_items = True
            elif in_obs_items and stripped.startswith("priority:"):
                val = stripped.split(":", 1)[1].strip().strip("'\"")
                if val == "next":
                    obs_next += 1

    result["total_chunks"] = chunk_count
    result["obs_next_count"] = obs_next
    return result


# ---------------------------------------------------------------------------
# Data extraction: session governance (JSON)
# ---------------------------------------------------------------------------

def extract_session_governance(prawduct_dir: str) -> dict | None:
    """Load governance debt fields from .session-governance.json."""
    path = os.path.join(prawduct_dir, ".session-governance.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Data extraction: critic findings (JSON)
# ---------------------------------------------------------------------------

def extract_critic_findings(prawduct_dir: str) -> dict | None:
    """Load critic findings state."""
    path = os.path.join(prawduct_dir, ".critic-findings.json")
    try:
        with open(path) as f:
            data = json.load(f)
        data["_age_seconds"] = time.time() - _file_mtime(path)
        return data
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Data extraction: git state
# ---------------------------------------------------------------------------

def get_git_state(project_dir: str) -> dict:
    """Get branch, staged count, modified count via git."""
    result = {"branch": "", "staged": 0, "modified": 0}
    try:
        p = subprocess.run(
            ["git", "-C", project_dir, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        if p.returncode == 0:
            result["branch"] = p.stdout.strip()

        p = subprocess.run(
            ["git", "-C", project_dir, "status", "--porcelain"],
            capture_output=True, text=True, timeout=3,
        )
        if p.returncode == 0:
            for line in p.stdout.splitlines():
                if len(line) >= 2:
                    if line[0] in "MADRCU":
                        result["staged"] += 1
                    if line[1] in "MADRCU":
                        result["modified"] += 1
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# Todo generation
# ---------------------------------------------------------------------------

def generate_todos(gov: dict | None, critic: dict | None) -> list[tuple[str, str]]:
    """Generate (label, color) todo tuples from governance/critic state."""
    todos: list[tuple[str, str]] = []
    if not gov:
        return todos

    gs = gov.get("governance_state", {})
    dc = gov.get("directional_change", {})
    pfr = gov.get("pfr_state", {})
    fe = gov.get("framework_edits", {})

    # --- Red: blockers ---

    # Review debt (merged: unreviewed files + stale findings)
    edited_files = [f.get("path", "") for f in fe.get("files", [])]
    reviewed = set(critic.get("reviewed_files", [])) if critic else set()
    unreviewed = [f for f in edited_files if f not in reviewed]
    stale = critic and (critic.get("_age_seconds", 0) > 7200
                        or critic.get("total_checks", 0) < 4)
    if unreviewed or (edited_files and stale):
        todos.append(("critic", BOLD_RED))

    # Chunk review debt
    chunks_no_review = gs.get("chunks_completed_without_review", 0)
    if chunks_no_review > 0:
        todos.append((f"{chunks_no_review} chunk{'s' if chunks_no_review != 1 else ''} unreviewed", BOLD_RED))

    # Checkpoint
    if gs.get("governance_checkpoints_due"):
        todos.append(("checkpoint", BOLD_RED))

    # PFR: RCA needed
    if pfr.get("required"):
        has_rca = bool(pfr.get("rca")) or pfr.get("diagnosis_written", False)
        if not has_rca:
            todos.append(("RCA", BOLD_RED))

    # --- Yellow: advisories ---

    # Observation debt (deduplicated across PFR, DCP, critic)
    needs_obs = False
    if pfr.get("required") and (bool(pfr.get("rca")) or pfr.get("diagnosis_written")) \
       and not pfr.get("observation_file"):
        needs_obs = True
    if dc.get("active") and not dc.get("observation_captured"):
        needs_obs = True
    if critic and gs.get("observations_captured_this_session", 0) == 0 \
       and critic.get("highest_severity") in ("warning", "blocking"):
        needs_obs = True
    if needs_obs:
        todos.append(("obs", YELLOW))

    # DCP: classify
    if dc.get("needs_classification") and not dc.get("tier"):
        todos.append(("classify", YELLOW))

    # DCP: retro
    if dc.get("active") and not dc.get("retrospective_completed"):
        todos.append(("retro", YELLOW))

    # DCP: artifact check
    if dc.get("active") and dc.get("tier") in ("enhancement", "structural") \
       and not dc.get("artifacts_verified"):
        todos.append(("artifact check", YELLOW))

    # Cap at 4 + overflow
    if len(todos) > 4:
        overflow = len(todos) - 4
        todos = todos[:4]
        todos.append((f"+{overflow} more", YELLOW))

    return todos


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

STAGE_DISPLAY = {
    "intake": "Intake",
    "discovery": "Discovery",
    "definition": "Definition",
    "artifact_generation": "Artifacts",
    "artifact-generation": "Artifacts",
    "build_planning": "Planning",
    "build-planning": "Planning",
    "build": "Build",
    "building": "Build",
}

MAX_ACTIVITY_LEN = 40


def _resolve_state(project_state: dict, gov: dict | None,
                   governance_active: bool) -> tuple[str, str | None]:
    """Return (state, detail) tuple describing what the session is doing."""
    if not governance_active:
        return ("Starting", None)

    stage = project_state.get("current_stage", "")

    # Product build stages use stage name directly
    if stage in ("intake", "discovery", "definition",
                 "artifact_generation", "artifact-generation",
                 "build_planning", "build-planning"):
        return (STAGE_DISPLAY.get(stage, stage.capitalize()), None)

    if stage in ("build", "building"):
        chunk = project_state.get("current_chunk")
        total = project_state.get("total_chunks", 0)
        if chunk:
            detail = f"{chunk} [{total}]" if total else chunk
            return ("Build", detail)
        return ("Build", None)

    # Iteration / framework dev: contextual state
    if gov:
        dc = gov.get("directional_change", {})
        if dc.get("active") and dc.get("plan_description"):
            desc = dc["plan_description"]
            if len(desc) > MAX_ACTIVITY_LEN:
                desc = desc[:MAX_ACTIVITY_LEN - 1] + "\u2026"
            return ("Working", desc)

        fe = gov.get("framework_edits", {})
        files = fe.get("files", [])
        if files:
            n = len(files)
            return ("Working", f"{n} file{'s' if n != 1 else ''} edited")

    return ("Ready", None)


def render_line1(project_state: dict | None, gov: dict | None,
                 todos: list[tuple[str, str]],
                 governance_active: bool) -> str | None:
    """Render prawduct state line. Returns None if not a prawduct project."""
    if not project_state or not project_state.get("current_stage"):
        return None

    state, detail = _resolve_state(project_state, gov, governance_active)

    # State (always shown)
    line = f"{ORANGE}{SHRIMP}{RESET} {BOLD_CYAN}{state}{RESET}"

    # Detail (optional)
    if detail:
        line += f": {detail}"

    # Todos (optional) — "TODO: critic, RCA, obs, ..."
    if todos:
        todo_strs = [f"{color}{label}{RESET}" for label, color in todos]
        line += f"  \u26a0 TODO: " + ", ".join(todo_strs)

    return line


def render_line2(model_name: str, pct: float, duration_ms: int, git: dict,
                 lines_added: int, lines_removed: int) -> str:
    """Render model + context bar + duration + git + session lines."""
    # Context bar
    filled = max(0, min(10, int(pct / 10)))
    empty = 10 - filled

    if pct >= 85:
        bar_color = RED
    elif pct >= 70:
        bar_color = YELLOW
    else:
        bar_color = GREEN

    bar = bar_color + "\u2593" * filled + DIM + "\u2591" * empty + RESET
    pct_str = f"{int(pct)}%"

    # Duration
    minutes = max(0, duration_ms // 60000)
    if minutes >= 60:
        dur_str = f"{minutes // 60}h{minutes % 60}m"
    else:
        dur_str = f"{minutes}m"

    # Git info
    branch = git.get("branch", "")
    staged = git.get("staged", 0)
    modified = git.get("modified", 0)
    git_parts = []
    if branch:
        git_parts.append(branch)
    if staged > 0:
        git_parts.append(f"{GREEN}+{staged}{RESET}")
    if modified > 0:
        git_parts.append(f"{YELLOW}~{modified}{RESET}")
    git_str = " ".join(git_parts)

    # Session lines
    lines_parts = []
    if lines_added > 0:
        lines_parts.append(f"{GREEN}+{lines_added}{RESET}")
    if lines_removed > 0:
        lines_parts.append(f"{RED}-{lines_removed}{RESET}")
    if lines_parts:
        lines_str = " ".join(lines_parts) + " lines"
    else:
        lines_str = ""

    # Assemble: Model ▓▓▓ 62% | 12m | main +2 ~3 | +156 -23 lines
    segments = []
    ctx_segment = f"{bar} {pct_str} | {dur_str}"
    if model_name:
        ctx_segment = f"{model_name} {ctx_segment}"
    segments.append(ctx_segment)
    if git_str:
        segments.append(git_str)
    if lines_str:
        segments.append(lines_str)

    return " | ".join(segments)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        stdin_data = json.load(sys.stdin)
    except Exception:
        return

    ctx = stdin_data.get("context_window", {})
    pct = ctx.get("used_percentage", 0) or 0

    cost = stdin_data.get("cost", {})
    duration_ms = cost.get("total_duration_ms", 0)
    lines_added = cost.get("total_lines_added", 0)
    lines_removed = cost.get("total_lines_removed", 0)

    model = stdin_data.get("model", {})
    model_name = model.get("display_name", "")

    workspace = stdin_data.get("workspace", {})
    project_dir = workspace.get("project_dir", "")
    if not project_dir:
        return

    prawduct_dir = os.path.join(project_dir, ".prawduct")
    is_prawduct = os.path.isdir(prawduct_dir)

    # CCPID-aware product resolution: if CCPID is set, read the declared
    # product from .sessions/<ccpid>/product and use that product's .prawduct/
    # for governance state and project-state display.
    product_prawduct_dir = prawduct_dir
    ccpid = os.environ.get("CCPID", "").strip()
    if ccpid and is_prawduct:
        product_file = os.path.join(prawduct_dir, ".sessions", ccpid, "product")
        try:
            with open(product_file) as f:
                session_product = f.read().strip()
            if session_product and os.path.isdir(session_product):
                candidate = os.path.join(session_product, ".prawduct")
                if os.path.isdir(candidate):
                    product_prawduct_dir = candidate
        except OSError:
            pass  # Fall back to session-level

    cache = _load_cache(project_dir)

    # --- Session governance (mtime-cached, reads from product dir) ---
    gov = None
    if is_prawduct:
        gov_path = os.path.join(product_prawduct_dir, ".session-governance.json")
        gov_mtime = _file_mtime(gov_path)
        if cache.get("gov_mtime") == gov_mtime and "gov" in cache:
            gov = cache["gov"]
        else:
            gov = extract_session_governance(product_prawduct_dir)
            cache["gov_mtime"] = gov_mtime
            cache["gov"] = gov

    # --- Project state (mtime-cached, reads from product dir) ---
    project_state = None
    if is_prawduct:
        ps_path = os.path.join(product_prawduct_dir, "project-state.yaml")
        ps_mtime = _file_mtime(ps_path)
        if cache.get("ps_mtime") == ps_mtime and "project_state" in cache:
            project_state = cache["project_state"]
        else:
            project_state = extract_project_state(product_prawduct_dir)
            cache["ps_mtime"] = ps_mtime
            cache["project_state"] = project_state

    # --- Critic findings (mtime-cached, _age_seconds always fresh) ---
    critic = None
    if is_prawduct:
        critic_path = os.path.join(product_prawduct_dir, ".critic-findings.json")
        critic_mtime = _file_mtime(critic_path)
        if cache.get("critic_mtime") == critic_mtime and "critic" in cache:
            critic = cache["critic"]
            if critic:
                critic["_age_seconds"] = time.time() - critic_mtime
        else:
            critic = extract_critic_findings(product_prawduct_dir)
            cache["critic_mtime"] = critic_mtime
            cache["critic"] = critic

    # --- Git state (TTL-cached) ---
    now = time.time()
    if now - cache.get("git_time", 0) > GIT_CACHE_TTL:
        git = get_git_state(project_dir)
        cache["git"] = git
        cache["git_time"] = now
    else:
        git = cache.get("git", {})

    _save_cache(project_dir, cache)

    # --- Activation marker is the authority for session-level data ---
    governance_active = is_prawduct and os.path.isfile(
        os.path.join(prawduct_dir, ".orchestrator-activated"))
    if not governance_active:
        # Session files are ephemeral; suppress stale cached data when
        # the activation marker is absent (e.g., new session before
        # Orchestrator runs, or between /clear and reactivation).
        gov = None
        critic = None

    # --- Generate output ---
    todos = generate_todos(gov, critic) if is_prawduct else []
    line1 = render_line1(project_state, gov, todos, governance_active) if is_prawduct else None
    line2 = render_line2(model_name, pct, duration_ms, git, lines_added, lines_removed)

    output_lines = []
    if line1:
        output_lines.append(line1)
    output_lines.append(line2)

    print("\n".join(output_lines))


if __name__ == "__main__":
    main()
