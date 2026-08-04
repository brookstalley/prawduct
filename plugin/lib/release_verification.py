"""Post-release verification: is this release complete and *public*?

The mirror of :mod:`release_readiness`, at the other end of the same release.
That gate asks "is everything fit to ship?" before the promotion; this one asks
"did the whole thing actually arrive?" after it.

**Why it exists.** Every check in the release runbook was expressed as a git
command run by the person doing the release, and every one of them passed for
every release this repo ever cut while the surface a consumer actually looks at — the
repository's Releases page — stayed empty. Nothing verified the consumer's view,
so nothing could report that it was wrong. Tag pushed, release invisible, gate
green.

**What it reads, and from where.** Version agreement is checked against the
**tag's own tree** (``git show <tag>:<path>``), never the working tree. What a
release shipped is a fact about the tree that release names, and the checkout
you happen to be standing in is a different question — a feature branch, or a
later `develop`, answers it confidently and wrongly. That rule governs the
``release_version_files:`` declaration too, not only the files it names: which
files carried a release's version is itself a fact about that release's tree,
so the declaration is read from ``<tag>:.prawduct/project-state.yaml``. A
product that reorganises its layout afterwards therefore cannot retroactively
misgrade an older release, and a release cut before the key existed falls back
to the guess below — which, being a guess, cannot fail it.

**Which files carry the version is the product's to state, not ours to infer**
(``architecture.md`` § Direction, LNG-5W8R — no gate acquires a
language-specific parser, remedy owner-ruled as declaration rather than broader
parsing). A product declares ``release_version_files:`` as path + format + key
path; the format names a *structural shape* (``bare``, ``json``, ``toml``) and
the key path is descended literally, so nothing here decides which table of a
manifest wins. Reading ``toml`` **delegates to stdlib** ``tomllib`` rather than
hand-rolling a parser, which is that norm's interim rule applied as written;
on an interpreter without it (3.10) such a file is *unverifiable*, never failed.

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
from typing import Callable, NamedTuple

from .release_readiness import normalize_version

#: Subprocess ceiling. Matches ``gitstate``'s: these are local plumbing calls,
#: except the ``gh`` one, which is the reason it is not shorter.
_TIMEOUT = 15

#: Per-check outcomes. ``UNVERIFIABLE`` is deliberately not a failure — see the
#: module docstring on split posture.
OK = "ok"
FAILED = "failed"
UNVERIFIABLE = "unverifiable"

class VersionFile(NamedTuple):
    """One file that carries the release version, and how to read it.

    ``fmt`` names a **structural shape, never a language** — ``bare`` (the whole
    file is the value), ``json``, ``toml``. The distinction is the point: shapes
    are shared across ecosystems (``package.json``, ``composer.json`` and
    ``plugin.json`` are one shape), so this vocabulary does not grow a branch per
    language the way a manifest-parser table does.

    ``key`` is a dotted path descended literally through the decoded mapping and
    is what makes the read *dumb*. The product names where its version lives, so
    nothing here decides which table of a manifest is authoritative — the defect
    that made ``[tool.myplugin] version = "9.9.9"`` above ``[project]`` report a
    confident wrong number. Empty for ``bare``, which has no key to descend. A
    literal dot inside a key name is not expressible, and deliberately so: the
    escape hatch is to point at a ``bare`` or ``json`` file instead.
    """

    path: str
    fmt: str
    key: str = ""


#: Where a release's own declaration lives, inside that release's tree.
_STATE_PATH = ".prawduct/project-state.yaml"

#: The declaration's key. Absent from a tree ⇒ that release never declared, and
#: :data:`_FALLBACK_VERSION_FILES` applies as a guess.
_DECLARATION_KEY = "release_version_files"

#: The layout assumed when a release's tree declares nothing. This is
#: **prawduct's own** layout, and this module ships to every governed product —
#: so against any other product it is a guess, which is exactly why a
#: disagreement found through it may never reach :data:`FAILED`
#: (see :func:`check_version_files`). The bare semver (no ``v``) is what these
#: hold; the tag carries the ``v``. Keyed by repo-relative path because that is
#: what ``git show <tag>:<path>`` takes, and checking anything else would read
#: the wrong tree.
_FALLBACK_VERSION_FILES = (
    VersionFile("plugin/VERSION", "bare"),
    VersionFile("plugin/.claude-plugin/plugin.json", "json", "version"),
    VersionFile("pyproject.toml", "toml", "project.version"),
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


def _outside_repo_reason(project_dir: Path) -> str | None:
    """Why ``project_dir`` cannot answer a git question, or ``None`` if it can.

    Exists because ``git rev-parse`` exits **128** for two unrelated states — the
    ref does not exist, and this is not a repository — and a caller that reads
    the first meaning out of a bare non-zero states a finding about the release
    from an environment that could not ask the question. A false red on a
    release check is worse than no check, because it is the reading that teaches
    people to ignore it (this module's own docstrings, twice).

    **Three outcomes, not two**, and the reason is the same one this commit
    applies one function down. A first cut returned ``bool`` and folded "git is
    not installed" into "not a git repository", defending the collapse on the
    grounds that both callers turn it into ``UNVERIFIABLE`` anyway. Equal
    verdicts are not equal diagnoses: an operator told "not a git repository"
    inside their own checkout goes looking at the checkout, and the actual fix
    is to install git. That is precisely the defect being repaired in
    :func:`check_version_files`, so making it here would have been the same
    error one frame over.
    """
    probe = _run(["git", "rev-parse", "--git-dir"], project_dir)
    if probe == MISSING:
        return "git is not installed"
    if probe == ERRORED:
        return "git did not complete"
    return None if probe[0] == 0 else "not a git repository"


def _read_declaration(text: str) -> list[VersionFile] | None:
    """``release_version_files:`` as declared, or ``None`` when undeclared.

    Minimal-YAML by the same discipline as ``risk._read_list_yaml_key`` and
    ``core.read_str_yaml_key`` — a column-0 key, indented ``- path: …`` entries
    until the next column-0 key, inline comments stripped. No PyYAML: the
    governance runtime is stdlib-only.

    **Three outcomes, not two.** ``None`` (undeclared) and ``[]`` (declared
    empty) are different facts and the caller reads them oppositely — the first
    falls back to a guess that cannot fail the release, the second is a
    deliberate "this product ships no version file" and is honoured exclusively.
    ``risk_surfaces:`` draws the same line for the same reason.

    **Block style only.** A flow-style ``release_version_files: [ … ]`` yields no
    entries and so reads as *declared empty*, reporting "no version file to
    check" rather than silently reverting to the guess — loud, and naming the
    key, which is what an operator needs to spot the wrong syntax. An explicit
    ``== "[]"`` branch sat here to make the empty case deliberate and was
    removed: the block scan already returns ``[]`` for it by every route, so the
    branch could not change an answer and no test could have caught its
    deletion.
    """
    lines = text.splitlines()
    needle = f"{_DECLARATION_KEY}:"
    for index, raw in enumerate(lines):
        if raw[:1] in (" ", "\t"):
            continue
        line = raw.split("#", 1)[0].rstrip()
        if not line.startswith(needle):
            continue
        entries: list[dict[str, str]] = []
        for follow in lines[index + 1:]:
            if follow[:1] not in (" ", "\t") and follow.strip():
                break  # next column-0 key — the block ended
            stripped = follow.split("#", 1)[0].strip()
            if not stripped:
                continue
            if stripped.startswith("- "):
                entries.append({})
                stripped = stripped[2:].strip()
            if not entries or ":" not in stripped:
                continue
            field, _, value = stripped.partition(":")
            entries[-1][field.strip()] = value.strip().strip("\"'")
        # An entry with no `path` names no file and is dropped; one with no
        # `format` is KEPT, and reports itself unreadable rather than being
        # silently skipped — an unknown shape is "unchecked", never "passed"
        # (`architecture.md` § Direction, the same clause that put the read
        # under declaration in the first place).
        return [
            VersionFile(e["path"], e.get("format", ""), e.get("key", ""))
            for e in entries
            if e.get("path")
        ]
    return None


def _toml_loader() -> Callable[[str], dict] | None:
    """``tomllib.loads``, or ``None`` on an interpreter without it.

    **Delegation, not a parser.** ``architecture.md``'s in-transition LNG-5W8R
    says no gate acquires a language-specific parser, and its interim rule says
    new gate code *delegates first*. The branch this replaced was a hand-rolled
    scan for one language's manifest format — named on that norm's own
    retroactivity list — so the repair deletes it rather than teaching it about
    tables. ``tomllib`` is 3.11+ and ``requires-python`` is ``>=3.10``; that
    floor is a supported state here, not an error, and it degrades to
    *unverifiable* because an interpreter's stdlib is not evidence about a
    release.
    """
    try:
        import tomllib  # noqa: PLC0415 -- 3.11+ only; its absence is a supported state
    except ImportError:
        return None
    return tomllib.loads


def _descend(data: object, key: str) -> object | None:
    """The value at a dotted ``key``, or ``None`` if the path does not resolve."""
    cursor = data
    for part in key.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


class _Read(NamedTuple):
    """The outcome of reading one version file.

    ``blocked`` separates *we could not read this at all* from *we read it and
    the version is not there*, because they are opposite verdicts: the first is
    a limitation of this runtime and can only ever be ``UNVERIFIABLE``, while
    the second is a statement about a file the product declared. Collapsing them
    is the module's founding defect ("I could not ask" read as "the answer is
    no") one level down.
    """

    value: str | None
    problem: str | None
    blocked: bool = False


def _read_version(spec: VersionFile, content: str) -> _Read:
    """The version ``spec`` names inside ``content``."""
    if spec.fmt == "bare":
        value = content.strip()
        return _Read(value or None, None if value else "is empty")
    if spec.fmt == "json":
        loader: Callable[[str], object] | None = json.loads
    elif spec.fmt == "toml":
        loader = _toml_loader()
        if loader is None:
            return _Read(
                None,
                "reading toml needs Python 3.11+ (tomllib); this interpreter is "
                f"{sys.version_info.major}.{sys.version_info.minor}",
                blocked=True,
            )
    else:
        named = f"format {spec.fmt!r}" if spec.fmt else "no format"
        return _Read(None, f"declares {named}, which this check cannot read", blocked=True)
    try:
        data = loader(content)
    except ValueError:
        # Both `json.JSONDecodeError` and `tomllib.TOMLDecodeError` derive from
        # ValueError, so one specific catch covers both loaders.
        return _Read(None, f"is not valid {spec.fmt}")
    if not spec.key:
        return _Read(None, f"declares no key path, which {spec.fmt} needs")
    value = _descend(data, spec.key)
    if value is None or value == "":
        return _Read(None, f"has no {spec.key}")
    return _Read(str(value), None)


def check_version_files(project_dir: Path, tag: str) -> tuple[str, str]:
    """Whether the version files in the tag's tree agree with the tag.

    **The posture splits on provenance, and that split is the whole point.**
    When the release's tree declares ``release_version_files:``, the product has
    stated a fact about itself: these files carry the version. A declared file
    that is absent, or present and unreadable, is then a real defect in the
    release and reaches ``FAILED``. When nothing is declared,
    :data:`_FALLBACK_VERSION_FILES` is prawduct's own layout applied to a product
    that never claimed it — a guess, which may reach ``OK`` or ``UNVERIFIABLE``
    but **never** ``FAILED``. Without that asymmetry declaration is cosmetic:
    the guess would keep grading products against a layout they never chose,
    which is how a setuptools-scm project or a tooling-only ``pyproject.toml``
    was told its release was broken.

    **A file absent from the tree is skipped under the fallback, not failed.**
    A product with no ``pyproject.toml`` is not a broken release, and printing
    ``not-released`` while naming files that cannot exist there is the hazard
    ``release_readiness`` already documented for its own messages.

    A tree from which nothing could be measured is ``UNVERIFIABLE`` — saying so
    is not the same as passing.
    """
    expected = tag[1:] if tag.startswith("v") else tag

    shown_state = _run(["git", "show", f"{tag}:{_STATE_PATH}"], project_dir)
    if shown_state == MISSING:
        return UNVERIFIABLE, "git is not installed"
    if shown_state == ERRORED:
        return UNVERIFIABLE, "git could not read the tag's tree"
    # A non-zero here is an absent declaration, not an error: most trees — every
    # release cut before this key existed, and every product that never opted in
    # — legitimately carry no `.prawduct/project-state.yaml` at this path.
    declared = _read_declaration(shown_state[1]) if shown_state[0] == 0 else None
    specs = declared if declared is not None else list(_FALLBACK_VERSION_FILES)
    if not specs:
        return UNVERIFIABLE, (
            f"{tag}'s tree declares {_DECLARATION_KEY}: with no entries "
            "— no version file to check"
        )

    problems: list[str] = []
    blocked: list[str] = []
    checked: list[str] = []
    for spec in specs:
        shown = _run(["git", "show", f"{tag}:{spec.path}"], project_dir)
        if shown == MISSING:
            return UNVERIFIABLE, "git is not installed"
        if shown == ERRORED:
            return UNVERIFIABLE, "git could not read the tag's tree"
        if shown[0] != 0:
            if declared is not None:
                problems.append(f"{spec.path}: declared, but not in {tag}'s tree")
            continue  # under the guess, absent means "not this product's layout"
        read = _read_version(spec, shown[1])
        if read.blocked:
            blocked.append(f"{spec.path}: {read.problem}")
            continue
        if read.value is None:
            if declared is not None:
                problems.append(f"{spec.path}: declared to carry the version but {read.problem}")
            continue  # under the guess, an unreadable file is not this product's
        if read.value != expected:
            problems.append(f"{spec.path}: says {read.value}, tag says {expected}")
            continue
        # `checked` holds files that were read AND agreed, not merely read: it is
        # reported as "did agree" in the soft-failure detail below, where a file
        # that disagreed would make that sentence false.
        checked.append(spec.path)

    if problems and declared is not None:
        # Failures dominate a blocked sibling: a file that genuinely disagrees is
        # evidence about the release however many others could not be read.
        return FAILED, "; ".join(problems)
    if problems:
        # Undeclared, so these are real disagreements found through a GUESSED
        # layout. Worth reporting in full — the signal is the point — but not as
        # a verdict about the release, and the one edit that would make it one
        # gets named rather than left for the reader to deduce.
        problems.append(
            f"but {tag}'s tree declares no {_DECLARATION_KEY}:, so this layout is "
            "prawduct's guess; declare it to make a disagreement a failure"
        )
    if blocked or problems:
        # Report every soft finding, never just the first kind. Returning only
        # `blocked` here would drop a live version disagreement because an
        # unrelated sibling file could not be read — "advice fails soft" is not
        # "advice fails silent", one level down again.
        parts = [*blocked, *problems]
        if checked:
            parts.append(f"{len(checked)} file(s) did agree: {', '.join(checked)}")
        return UNVERIFIABLE, "; ".join(parts)
    if not checked:
        # THREE very different causes land here, and the third was missing: a
        # `git show` outside a repository fails per-file exactly like an absent
        # path, so every file "skipped" and this branch reported a layout
        # question. The verdict was already the right one (unverifiable), but
        # naming the wrong cause is the same defect one level down — "advice
        # fails soft" is not "advice fails silent", and a soft failure still
        # owes its reader the real reason.
        outside = _outside_repo_reason(project_dir)
        if outside is not None:
            return UNVERIFIABLE, f"{outside} — no tree to read version files from"
        return UNVERIFIABLE, (
            f"no known version file present in {tag}'s tree "
            "(a different product layout, or a tag this clone has not fetched)"
        )
    # Name what was read, and name what was not. A bare count cannot be acted on:
    # a tag tree missing `plugin/.claude-plugin/plugin.json` — the auto-update
    # cache key, and the root cause this whole check exists for — passes as
    # `released`, exit 0, distinguishable from a complete release only by a "2"
    # where a "3" should be. Skipping an absent file stays correct (this module
    # ships to products with other layouts); reporting the skip silently does not.
    detail = f"{len(checked)} version file(s) agree at {tag}: {', '.join(checked)}"
    skipped = [spec.path for spec in specs if spec.path not in checked]
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
        # git exits 128 for BOTH "no such tag" and "not a git repository", so a
        # non-zero here is not yet evidence about the tag. Ask which one it was.
        # This mirrors the `origin/main` existence probe below: establish that the
        # question CAN be asked before reading an answer into the silence.
        blocked = _outside_repo_reason(project_dir)
        if blocked is not None:
            return UNVERIFIABLE, (
                f"{blocked} — this directory cannot answer whether {tag} exists"
            )
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
