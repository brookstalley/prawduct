"""Post-release verification: is this release complete and *public*?

The mirror of :mod:`release_readiness`, at the other end of the same release.
That gate asks "is everything fit to ship?" before the promotion; this one asks
"did the whole thing actually arrive?" after it.

**Why it exists.** Every check in the release runbook was expressed as a git
command run by the person doing the release, and every one of them passed for
thirty consecutive releases while the surface a consumer actually looks at — the
repository's Releases page — stayed empty. Nothing verified the consumer's view,
so nothing could report that it was wrong. Tag pushed, release invisible, gate
green.

**What it reads, and from where.** Version agreement is checked against the
**tag's own tree** (``git show <tag>:<path>``), never the working tree. What a
release shipped is a fact about the tree that release names, and the checkout
you happen to be standing in is a different question — a feature branch, or a
later `develop`, answers it confidently and wrongly.

**Failure posture is split on purpose** (``architecture.md`` § Direction — a
command's posture follows what it produces). The local checks produce a verdict
about the release and fail **closed**: unreadable tag, absent file, disagreeing
version are all failures. The Releases-page check needs the network, which the
governance runtime does not take — this command is an operator/CI command, not a
session gate, so it may, but a machine without ``gh`` must not be told its
release is broken when what is actually missing is a CLI. That case reports
**unverifiable** and is called out as such. In CI ``gh`` is present, which is
where this check is authoritative and where a forgotten publish turns the build
red.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .release_readiness import normalize_version

#: Subprocess ceiling. Matches ``gitstate``'s: these are local plumbing calls,
#: except the ``gh`` one, which is the reason it is not shorter.
_TIMEOUT = 15

#: Per-check outcomes. ``UNVERIFIABLE`` is deliberately not a failure — see the
#: module docstring on split posture.
OK = "ok"
FAILED = "failed"
UNVERIFIABLE = "unverifiable"

#: Files carrying the release version, and how to find it in each. The bare
#: semver (no ``v``) is what all three hold; the tag carries the ``v``.
#: Keyed by repo-relative path because that is what ``git show <tag>:<path>``
#: takes, and checking anything else would read the wrong tree.
_VERSION_FILES = (
    ("plugin/VERSION", "bare"),
    ("plugin/.claude-plugin/plugin.json", "json"),
    ("pyproject.toml", "toml"),
)


def _run(args: list[str], cwd: Path) -> tuple[int, str, str] | None:
    """Run ``args`` in ``cwd``. ``None`` when the executable is missing or hangs.

    ``None`` and a non-zero return code mean different things to every caller
    here — "the tool is not installed" is not "the tool said no" — so they are
    kept distinguishable rather than collapsed into a falsy result.
    """
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, cwd=str(cwd), timeout=_TIMEOUT
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _version_from(kind: str, content: str) -> str | None:
    """The version string a release file carries, or ``None`` if unparseable."""
    if kind == "bare":
        return content.strip() or None
    if kind == "json":
        try:
            value = json.loads(content).get("version")
        except (ValueError, AttributeError):
            return None
        return str(value) if value else None
    for line in content.splitlines():
        stripped = line.strip()
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        # The key must *be* ``version``, not merely start with it — a prefix
        # match reads ``versioning`` or ``version_scheme`` as the release
        # version and reports a confident wrong number.
        if key.strip() != "version":
            continue
        # The first assignment wins: ``[project].version`` sits above any
        # ``[tool.*]`` table that might also carry the key.
        return value.strip().strip('"').strip("'") or None
    return None


def check_version_files(project_dir: Path, tag: str) -> list[tuple[str, str]]:
    """Disagreements between the tag's tree and the version the tag names.

    Returns ``(path, problem)`` pairs — empty when all three agree.
    """
    expected = tag[1:] if tag.startswith("v") else tag
    problems: list[tuple[str, str]] = []
    for rel_path, kind in _VERSION_FILES:
        shown = _run(["git", "show", f"{tag}:{rel_path}"], project_dir)
        if shown is None or shown[0] != 0:
            problems.append((rel_path, f"not present in {tag}'s tree"))
            continue
        found = _version_from(kind, shown[1])
        if found is None:
            problems.append((rel_path, "no version string found"))
        elif found != expected:
            problems.append((rel_path, f"says {found}, tag says {expected}"))
    return problems


def check_tag_on_main(project_dir: Path, tag: str) -> tuple[str, str]:
    """Whether ``tag`` names a commit contained in ``origin/main``.

    Ancestry is the right question *here* — a promotion commit is authored on
    ``main``, so the tag's commit is on it or the release never landed. (It is
    the wrong question for "did this scope ship", which is about tree content;
    that distinction is why this is scoped to the tag and nothing else.)
    """
    resolved = _run(["git", "rev-parse", f"{tag}^{{commit}}"], project_dir)
    if resolved is None or resolved[0] != 0:
        return FAILED, f"tag {tag} does not resolve to a commit"
    commit = resolved[1]
    # Establish that the reference EXISTS before asking what it contains.
    # Without this, a clone with no `origin/main` — a fresh checkout, a fork, a
    # shallow CI fetch — gets `not contained`, which reads as "this release is
    # broken" when the truth is "this clone cannot answer". A false red on a
    # release check is worse than no check, because it is the reading that
    # teaches people to ignore it.
    main_ref = _run(["git", "rev-parse", "--verify", "--quiet", "origin/main"], project_dir)
    if main_ref is None:
        return UNVERIFIABLE, "git unavailable"
    if main_ref[0] != 0:
        return UNVERIFIABLE, "origin/main is not present in this clone"
    ancestor = _run(
        ["git", "merge-base", "--is-ancestor", commit, "origin/main"], project_dir
    )
    if ancestor is None:
        return UNVERIFIABLE, "git unavailable"
    if ancestor[0] != 0:
        return FAILED, f"{commit[:9]} is not contained in origin/main"
    return OK, commit[:9]


def check_github_release(project_dir: Path, tag: str) -> tuple[str, str]:
    """Whether a GitHub Release exists for ``tag``.

    Absent ``gh`` is *unverifiable*, not failed: telling an operator without the
    CLI that their release is broken would be a false red, and the false red is
    how a check gets ignored.
    """
    viewed = _run(["gh", "release", "view", tag, "--json", "url", "--jq", ".url"], project_dir)
    if viewed is None:
        return UNVERIFIABLE, "gh is not installed"
    if viewed[0] != 0:
        detail = viewed[2] or "no release"
        if "release not found" in detail.lower():
            return FAILED, f"no GitHub Release for {tag} — the tag alone is not a release"
        return UNVERIFIABLE, f"gh could not answer: {detail.splitlines()[0][:120]}"
    return OK, viewed[1]


def check_released(project_dir: Path, release: str, json_output: bool = False) -> int:
    """Verify a published release. ``0`` when complete, ``1`` when not.

    ``UNVERIFIABLE`` results never fail the command — they are reported and the
    exit code reflects only what could actually be established.
    """
    tag = normalize_version(release)

    version_problems = check_version_files(project_dir, tag)
    tag_state, tag_detail = check_tag_on_main(project_dir, tag)
    release_state, release_detail = check_github_release(project_dir, tag)

    checks = [
        {
            "check": "version-files",
            "state": FAILED if version_problems else OK,
            "detail": (
                "; ".join(f"{p}: {why}" for p, why in version_problems)
                if version_problems
                else f"all three agree at {tag}"
            ),
        },
        {"check": "tag-on-main", "state": tag_state, "detail": tag_detail},
        {"check": "github-release", "state": release_state, "detail": release_detail},
    ]
    failed = [c for c in checks if c["state"] == FAILED]
    unverifiable = [c for c in checks if c["state"] == UNVERIFIABLE]

    if json_output:
        print(
            json.dumps(
                {
                    "release": tag,
                    "verdict": "not-released" if failed else "released",
                    "checks": checks,
                },
                indent=2,
            )
        )
        return 1 if failed else 0

    if failed:
        print(f"not-released: {tag}", file=sys.stderr)
        for check in failed:
            print(f"  ERROR: {check['check']}: {check['detail']}", file=sys.stderr)
        for check in unverifiable:
            print(f"  unverified: {check['check']}: {check['detail']}", file=sys.stderr)
        return 1

    print(f"released: {tag} — {len(checks) - len(unverifiable)} of {len(checks)} checks verified")
    for check in checks:
        if check["state"] == OK:
            print(f"  ok: {check['check']}: {check['detail']}")
    for check in unverifiable:
        print(f"  unverified: {check['check']}: {check['detail']}", file=sys.stderr)
    return 0
