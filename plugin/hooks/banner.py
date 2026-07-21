#!/usr/bin/env python3
"""Prawduct plugin SessionStart banner — version-delta + new-gate attribution.

Chunk 7 of the v2.0.0 plugin-distribution build plan. The banner is the *safety
net* for always-latest distribution (design §5/§5a): because the plugin
auto-updates, every version move must be made VISIBLE, never silent. On each
session start the banner:

  1. prints the one-line identity banner (``═══ Prawduct vY (plugin) ═══``),
     carrying a load-provenance segment (``(plugin · develop@a1b2c3d)``) when the
     plugin was loaded from a local working tree rather than a managed install;
  2. compares the plugin's ``plugin.json`` version against a per-repo last-seen
     marker (``.prawduct/.prawduct-version``);
  3. on a CHANGE, prints ``vX → vY`` plus the changelog highlights for the bump
     (from the bundled ``CHANGELOG.md``) and ANNOUNCES any gate whose ``since``
     falls in the crossed range (from the bundled ``hooks/gates.json``), so a
     new gate that starts blocking is attributable to the update that shipped it;
  4. otherwise stays quiet (no delta block).

Governing invariant (design §2): the plugin ships immutable, read-only code. The
ONLY thing this script writes is the per-repo marker under
``${CLAUDE_PROJECT_DIR}/.prawduct/`` — mutable, per-repo state, exactly where the
invariant allows it. It writes nowhere else, and only when the version changed.

No consumer-repo NOISE: the marker is gitignored so a version bump never
produces a tracked-file diff — in the Prawduct repo via its own ``.gitignore``;
in a consuming repo at migration (Chunk 9), where the cutover gitignores it and
the plugin runtime auto-untracks it. (It is deliberately NOT added to the legacy
1.x ``GITIGNORE_ENTRIES``/``_SESSION_GITIGNORED_PATHS`` lists — that would touch
the frozen 1.x runtime and push a gratuitous ``.gitignore`` diff into pure
file-sync repos that never create the marker.) The changelog + gate registry
live inside the plugin, out of every consumer's tree.

Load provenance: ``VERSION``/``plugin.json`` only move at release-prep, so an
integration branch carrying unreleased work reports the same version as the
release it was cut from — the version string cannot tell an operator *which*
plugin code is loaded. The identity line therefore names the ref and short sha
when the plugin root is a working tree, and stays byte-identical for a managed
install. The distinction is a pure path comparison against the managed plugin
directory, NOT a ``.git`` probe: a marketplace install is itself a clone. That
gate is also what keeps the git subprocess off the hot path for every ordinary
user (see :func:`is_managed_install`).

Marker discipline: the delta/marker logic runs ONLY when ``CLAUDE_PROJECT_DIR``
is explicitly set (always true for a real hook invocation). Without it the
banner prints identity only and writes nothing — so running the script with no
project context (e.g. a bare unit test) never mutates whatever repo is cwd.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_SEMVER_HEADER = re.compile(r"^##\s+v(\d+\.\d+\.\d+)\b")

# Bound the provenance git call. It runs only for a local checkout (never for a
# managed install), but a wedged git must not hold up session start.
_GIT_TIMEOUT_SECONDS = 5
# Commit abbreviation for the provenance segment. Fixed rather than git's
# adaptive `--short` so the rendered banner is reproducible across repo sizes.
_SHA_CHARS = 7


def plugin_root() -> Path:
    """Resolve the plugin root.

    Prefers ``CLAUDE_PLUGIN_ROOT`` (set by Claude Code when the hook fires).
    Falls back to the parent of this file's directory (``hooks/`` -> root) so
    the script is also runnable directly, e.g. from tests.
    """
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent


def project_dir() -> Path | None:
    """The consuming repo, from ``CLAUDE_PROJECT_DIR``.

    Returns ``None`` when unset. Deliberately does NOT fall back to cwd: the
    marker write must never land in an unexpected repo just because the script
    was run without project context.
    """
    env_proj = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env_proj) if env_proj else None


def managed_plugin_home() -> Path:
    """Claude Code's managed plugin directory (``~/.claude/plugins``).

    Honors ``CLAUDE_CONFIG_DIR`` so an alternate config home resolves correctly.
    """
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(cfg) if cfg else Path.home() / ".claude"
    return base / "plugins"


def is_managed_install(root: Path) -> bool:
    """True when ``root`` sits under the managed plugin directory.

    This is the gate that keeps provenance a *local-development* affordance. It
    is a pure path comparison — deliberately no git, no filesystem probing of the
    root's contents — because a marketplace install is itself a git clone
    (``~/.claude/plugins/marketplaces/<name>/.git``), so "has a .git dir" does
    NOT distinguish the two. Checking the path instead means a managed install
    never pays for the subprocess in :func:`checkout_provenance`.

    An unresolvable path answers **True** (treat as managed). Answering False
    would route a genuine managed install into the git probe, which then
    *succeeds* — marketplace installs are clones — and renders a segment, so the
    operator would read presence as proof the local checkout won. Failing toward
    "managed" costs at most a missing segment on a local checkout while keeping
    presence-is-proof unconditional, which is the property the feature sells.
    """
    try:
        return root.resolve().is_relative_to(managed_plugin_home().resolve())
    except (OSError, RuntimeError, ValueError):
        return True


def _git(root: Path, *args: str) -> subprocess.CompletedProcess | Exception:
    """Run a read-only git command in ``root``.

    Returns the raised exception rather than a bare ``None`` so a caller
    reporting the failure can name its cause — git missing, git unrunnable, and
    a timeout are three different things to an operator trying to explain a
    banner.
    """
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            # A non-UTF-8 ref name must not cost us the segment. This is the
            # primary guard; the ValueError below is the backstop. Removing this
            # does not crash — decoding raises, the backstop catches it, and the
            # caller reports an attributed failure — but the provenance is lost
            # where it could have rendered with replacement characters.
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return exc


def checkout_provenance(root: Path) -> str:
    """``ref@sha`` (plus ``+dirty``) for a plugin loaded from a local checkout.

    Returns ``""`` for a managed install, a non-git directory, or any git
    failure — so the identity banner degrades to its plain form rather than
    breaking. The empty string is meaningful to the reader: a provenance segment
    appears only when the plugin was loaded from a working tree (``--plugin-dir``
    or equivalent), which makes its presence a reliable signal of *which* copy of
    the plugin won when a managed install is also enabled.

    Dirtiness is measured over tracked files only (``--untracked-files=no``):
    untracked scratch files are normal during local development and do not change
    what the plugin executes.

    Absence of a segment is *load-bearing information* — the operator reads it as
    "a managed install won" — so a probe that was supposed to produce one and
    could not says so on stderr rather than degrading into that same silence
    ("advice fails soft ... swallowed with attribution", ``architecture.md``
    Failure Model). The genuinely-nothing-to-report paths (managed install, plain
    directory) stay quiet, because for them the empty result is the truth.
    """
    if is_managed_install(root):
        return ""
    # One porcelain-v2 call yields ref, oid and tracked-file dirtiness together —
    # cheaper than separate rev-parse/diff calls, and `--untracked-files=no` is
    # what makes untracked scratch files not count as dirty.
    status = _git(root, "status", "--porcelain=v2", "--branch", "--untracked-files=no")
    if not isinstance(status, subprocess.CompletedProcess):
        # git absent, unrunnable, or past the timeout. Tested against the POSITIVE
        # type rather than `isinstance(status, Exception)` so that anything else a
        # future `_git` might hand back — `None`, most likely — takes this guarded
        # path instead of an AttributeError on `.returncode`. `main()` calls this
        # outside its try blocks, so an escape here breaks session start.
        # Distinct from "not a repo": here a segment WAS expected, so say why none
        # appears, naming the cause — "unavailable" and "timed out" want different fixes.
        print(
            f"NOTE: Prawduct could not read plugin load provenance: {status!r}; "
            "the banner cannot show which checkout is loaded.",
            file=sys.stderr,
        )
        return ""
    if status.returncode != 0:
        return ""  # not a git repo — a plain directory has no provenance to report
    ref = sha = ""
    dirty = False
    for line in status.stdout.splitlines():
        if line.startswith("# branch.head "):
            ref = line[len("# branch.head "):].strip()
        elif line.startswith("# branch.oid "):
            sha = line[len("# branch.oid "):].strip()
        elif line and not line.startswith("#"):
            dirty = True  # any entry line is a tracked add/modify/delete/rename
    if not ref or not sha or sha == "(initial)":  # unborn branch has no commit to name
        return ""
    if ref == "(detached)":  # name the state rather than echoing git's parentheses
        ref = "detached"
    return f"{ref}@{sha[:_SHA_CHARS]}{'+dirty' if dirty else ''}"


def read_version(root: Path) -> str:
    """Read the semver ``version`` from the bundled plugin manifest."""
    manifest = root / ".claude-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return str(data.get("version", "unknown"))


def version_tuple(v: str) -> tuple:
    """Parse a semver string into a comparable tuple. Tolerant: a non-numeric
    or malformed value sorts below any real version so it never wins a range
    comparison (an unparseable marker is treated as 'older than everything')."""
    parts = v.strip().lstrip("v").split(".")
    out: list[int] = []
    for p in parts:
        if p.isdigit():
            out.append(int(p))
        else:
            return (-1,)
    return tuple(out) if out else (-1,)


def read_marker(prawduct_dir: Path) -> str | None:
    """Last-seen version recorded for this repo, or ``None`` if never seen."""
    marker = prawduct_dir / ".prawduct-version"
    if not marker.is_file():
        return None
    try:
        return marker.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def write_marker(prawduct_dir: Path, version: str) -> None:
    """Record the now-seen version. Best-effort; never raises."""
    try:
        (prawduct_dir / ".prawduct-version").write_text(version + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"NOTE: Prawduct banner could not update version marker: {exc}", file=sys.stderr)


def parse_changelog(root: Path) -> list[tuple[str, str]]:
    """Parse the bundled CHANGELOG.md into ordered ``(version, headline)`` pairs.

    A version section is ``## vX.Y.Z``; its headline is the first following
    non-empty line that is not itself a markdown header. Missing/unreadable
    changelog -> empty list (the delta still renders ``vX → vY`` without
    highlights — highlights are best-effort, the version move is not).
    """
    path = root / "CHANGELOG.md"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        m = _SEMVER_HEADER.match(lines[i])
        if not m:
            i += 1
            continue
        version = m.group(1)
        headline = ""
        j = i + 1
        while j < len(lines):
            stripped = lines[j].strip()
            if not stripped:
                j += 1
                continue
            if stripped.startswith("#"):
                break
            headline = stripped.lstrip("-* ").strip()
            break
        out.append((version, headline))
        i += 1
    return out


def parse_gates(root: Path) -> list[dict]:
    """Load the bundled gate registry. Missing/invalid -> empty list."""
    path = root / "hooks" / "gates.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    gates = data.get("gates", [])
    return gates if isinstance(gates, list) else []


def highlights_in_range(changelog: list[tuple[str, str]], last: str, current: str) -> list[tuple[str, str]]:
    """Changelog entries for versions ``v`` with ``last < v <= current``,
    newest first. Empty on a downgrade (range is empty)."""
    lo, hi = version_tuple(last), version_tuple(current)
    picked = [(v, h) for (v, h) in changelog if lo < version_tuple(v) <= hi]
    picked.sort(key=lambda vh: version_tuple(vh[0]), reverse=True)
    return picked


def new_gates_in_range(gates: list[dict], last: str, current: str) -> list[dict]:
    """Gates whose ``since`` falls in ``last < since <= current`` — i.e. gates
    that activate on this bump and warrant a heads-up (design §5a)."""
    lo, hi = version_tuple(last), version_tuple(current)
    return [g for g in gates if lo < version_tuple(str(g.get("since", "0"))) <= hi]


def render_delta(last: str, current: str, root: Path) -> list[str]:
    """Lines for the delta block shown when the version changed."""
    lines = [f"↑ Prawduct updated: v{last} → v{current}"]
    for _v, headline in highlights_in_range(parse_changelog(root), last, current):
        if headline:
            lines.append(f"  • {headline}")
    for g in new_gates_in_range(parse_gates(root), last, current):
        name = g.get("name", g.get("id", "?"))
        summary = g.get("summary", "")
        suffix = f" — {summary}" if summary else ""
        lines.append(f"  ⊕ new gate \"{name}\"{suffix} (enforced now)")
    return lines


def main() -> int:
    try:
        root = plugin_root()
        version = read_version(root)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- a banner failure must never break session start
        print(f"NOTE: Prawduct banner could not read plugin version: {exc}", file=sys.stderr)
        return 0

    provenance = checkout_provenance(root)
    suffix = f" · {provenance}" if provenance else ""
    print(f"═══ Prawduct v{version} (plugin{suffix}) ═══")

    # Version-delta + marker: only with explicit project context, only when the
    # repo has a .prawduct/ to record into. Fully best-effort.
    try:
        proj = project_dir()
        if proj is None:
            return 0
        prawduct = proj / ".prawduct"
        if not prawduct.is_dir():
            return 0
        last = read_marker(prawduct)
        if last is None:
            # First time this repo has seen Prawduct — nothing to diff against.
            # Record silently; the identity line above already states the version.
            write_marker(prawduct, version)
            return 0
        if last == version:
            return 0  # same version -> quiet
        for line in render_delta(last, version, root):
            print(line)
        write_marker(prawduct, version)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- delta/marker is a safety net; never break session start
        print(f"NOTE: Prawduct version-delta banner degraded: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
