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


#: Why a command produced no answer. ``_run`` returns one of these in place of
#: a result, because "the tool is not installed" and "the tool hung" lead to
#: different verdicts and the callers were reading a single ``None`` oppositely.
MISSING = "missing"
ERRORED = "errored"


def _run(args: list[str], cwd: Path) -> tuple[int, str, str] | str:
    """Run ``args`` in ``cwd``.

    Returns ``(returncode, stdout, stderr)``, or :data:`MISSING` when the
    executable is not installed, or :data:`ERRORED` when it hung or the spawn
    failed. Three outcomes, not two: the docstring used to promise that
    distinction while the code collapsed both into ``None``, and the two callers
    then read that ``None`` in opposite directions — one degraded to
    *unverifiable*, the other fabricated three "not present in the tag's tree"
    failures and exited 1. A false red out of the module whose own comments
    argue that a false red is worse than no check.
    """
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, cwd=str(cwd), timeout=_TIMEOUT
        )
    except FileNotFoundError:
        return MISSING
    except (OSError, subprocess.SubprocessError):
        return ERRORED
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _scrub(text: str) -> str:
    """Strip credentials from foreign-CLI stderr before it is echoed or logged.

    ``gh``'s errors can carry a token or an authenticated URL, and this text
    reaches both stderr and the ``--json`` payload. The backlog transport runs
    the same denylist over the same class of output at its own egress boundary;
    reusing it keeps one rule rather than two that drift. Degrades to returning
    the text unchanged only if the helper cannot be imported — the scrub is a
    backstop, and losing it must not lose the diagnostic.
    """
    try:
        from .backlog.transport import scrub_secrets  # noqa: PLC0415 -- lazy: heavy import DAG
    except ImportError:
        return text
    return scrub_secrets(text)


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


def check_version_files(project_dir: Path, tag: str) -> tuple[str, str]:
    """Whether the version files in the tag's tree agree with the tag.

    **A file absent from the tree is skipped, not failed.** This module ships to
    every governed product, and :data:`_VERSION_FILES` is prawduct's own layout:
    a product with no ``pyproject.toml`` is not a broken release, and printing
    ``not-released`` while naming files that cannot exist there is the hazard
    ``release_readiness`` already documented for its own messages. The verdict
    is about files that are *present and disagree*.

    A tree carrying none of them is ``UNVERIFIABLE`` — nothing was measured, and
    saying so is not the same as passing.
    """
    expected = tag[1:] if tag.startswith("v") else tag
    problems: list[str] = []
    checked: list[str] = []
    for rel_path, kind in _VERSION_FILES:
        shown = _run(["git", "show", f"{tag}:{rel_path}"], project_dir)
        if shown == MISSING:
            return UNVERIFIABLE, "git is not installed"
        if shown == ERRORED:
            return UNVERIFIABLE, "git could not read the tag's tree"
        if shown[0] != 0:  # absent from this tree — not this product's layout
            continue
        checked.append(rel_path)
        found = _version_from(kind, shown[1])
        if found is None:
            problems.append(f"{rel_path}: no version string found")
        elif found != expected:
            problems.append(f"{rel_path}: says {found}, tag says {expected}")
    if not checked:
        # Two very different causes land here — a product with a different
        # layout, and a tag this clone has not fetched. Say both rather than
        # asserting the first, which reads as a finding about the product.
        return UNVERIFIABLE, (
            f"no known version file present in {tag}'s tree "
            "(a different product layout, or a tag this clone has not fetched)"
        )
    if problems:
        return FAILED, "; ".join(problems)
    # Name what was read, and name what was not. A bare count cannot be acted on:
    # a tag tree missing `plugin/.claude-plugin/plugin.json` — the auto-update
    # cache key, and the root cause this whole check exists for — passes as
    # `released`, exit 0, distinguishable from a complete release only by a "2"
    # where a "3" should be. Skipping an absent file stays correct (this module
    # ships to products with other layouts); reporting the skip silently does not.
    detail = f"{len(checked)} version file(s) agree at {tag}: {', '.join(checked)}"
    skipped = [path for path, _ in _VERSION_FILES if path not in checked]
    if skipped:
        detail += f" — not in this tree: {', '.join(skipped)}"
    return OK, detail


def check_tag_on_main(project_dir: Path, tag: str) -> tuple[str, str]:
    """Whether ``tag`` names a commit contained in ``origin/main``.

    Ancestry is the right question *here* — a promotion commit is authored on
    ``main``, so the tag's commit is on it or the release never landed. (It is
    the wrong question for "did this scope ship", which is about tree content;
    that distinction is why this is scoped to the tag and nothing else.)
    """
    resolved = _run(["git", "rev-parse", f"{tag}^{{commit}}"], project_dir)
    if resolved == MISSING:
        return UNVERIFIABLE, "git is not installed"
    if resolved == ERRORED:
        # git ran and did not complete. That is not evidence about the tag, and
        # reporting it as one would blame the release for a broken toolchain.
        return UNVERIFIABLE, "git could not resolve the tag"
    if resolved[0] != 0:
        return FAILED, f"tag {tag} does not resolve to a commit"
    commit = resolved[1]
    # Establish that the reference EXISTS before asking what it contains.
    # Without this, a clone with no `origin/main` — a fresh checkout, a fork, a
    # shallow CI fetch — gets `not contained`, which reads as "this release is
    # broken" when the truth is "this clone cannot answer". A false red on a
    # release check is worse than no check, because it is the reading that
    # teaches people to ignore it.
    main_ref = _run(["git", "rev-parse", "--verify", "--quiet", "origin/main"], project_dir)
    if isinstance(main_ref, str):
        return UNVERIFIABLE, "git unavailable"
    if main_ref[0] != 0:
        return UNVERIFIABLE, (
            "origin/main is not present in this clone — a shallow or "
            "single-ref checkout cannot answer containment"
        )
    ancestor = _run(
        ["git", "merge-base", "--is-ancestor", commit, "origin/main"], project_dir
    )
    if isinstance(ancestor, str):
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
    if viewed == MISSING:
        return UNVERIFIABLE, "gh is not installed"
    if viewed == ERRORED:
        return UNVERIFIABLE, "gh did not complete"
    if viewed[0] != 0:
        detail = _scrub(viewed[2]) or "no release"
        # Measured against gh 2.x rather than assumed — an absent release prints
        # `release not found`. Anything else (unauthenticated, rate-limited,
        # 5xx) is deliberately NOT read as absence: this check cannot tell a
        # missing release from a refused question, and guessing turns a broken
        # token into "your release is fine".
        if "release not found" in detail.lower():
            return FAILED, f"no GitHub Release for {tag} — the tag alone is not a release"
        return UNVERIFIABLE, f"gh could not answer: {detail.splitlines()[0][:160]}"
    return OK, viewed[1]


#: Exit code for "nothing failed, but not everything could be checked".
#: Distinct from 0 on purpose — see :func:`check_released`.
EXIT_UNVERIFIABLE = 3


def check_released(
    project_dir: Path,
    release: str,
    json_output: bool = False,
    allow_unverifiable: bool = False,
) -> int:
    """Verify a published release.

    ``0`` verified · ``1`` a check failed · ``3`` nothing failed but something
    could not be checked.

    **Why unverifiable is not 0.** It was, and that made the gate green in
    precisely the environment it exists for. A tag-push job using
    ``actions/checkout`` has no ``origin/main`` — absent containment is the
    *normal* state there, not an edge case — and a step without a token gets a
    ``gh`` that cannot answer. Both routed to unverifiable, which exited 0: a
    green build over an empty Releases page, which is the original defect with a
    passing check on top. A separate code keeps the local operator's honest
    answer ("I could not check the Releases page") distinct from a pass, while
    CI, which fails on any non-zero, goes red. ``allow_unverifiable`` is the
    explicit opt-out for someone who genuinely wants the local subset.
    """
    tag = normalize_version(release)

    version_state, version_detail = check_version_files(project_dir, tag)
    tag_state, tag_detail = check_tag_on_main(project_dir, tag)
    release_state, release_detail = check_github_release(project_dir, tag)

    checks = [
        {"check": "version-files", "state": version_state, "detail": version_detail},
        {"check": "tag-on-main", "state": tag_state, "detail": tag_detail},
        {"check": "github-release", "state": release_state, "detail": release_detail},
    ]
    failed = [c for c in checks if c["state"] == FAILED]
    unverifiable = [c for c in checks if c["state"] == UNVERIFIABLE]

    if failed:
        verdict, code = "not-released", 1
    elif unverifiable and not allow_unverifiable:
        verdict, code = "unverified", EXIT_UNVERIFIABLE
    else:
        verdict, code = "released", 0

    if json_output:
        print(json.dumps({"release": tag, "verdict": verdict, "checks": checks}, indent=2))
        return code

    if failed:
        print(f"not-released: {tag}", file=sys.stderr)
    elif code == EXIT_UNVERIFIABLE:
        print(
            f"unverified: {tag} — nothing failed, but "
            f"{len(unverifiable)} of {len(checks)} checks could not run",
            file=sys.stderr,
        )
    else:
        print(f"released: {tag} — {len(checks) - len(unverifiable)} of {len(checks)} verified")

    for check in checks:
        if check["state"] == OK:
            print(f"  ok: {check['check']}: {check['detail']}")
    for check in failed:
        print(f"  ERROR: {check['check']}: {check['detail']}", file=sys.stderr)
    for check in unverifiable:
        print(f"  unverified: {check['check']}: {check['detail']}", file=sys.stderr)
    return code
