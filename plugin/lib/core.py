"""
Core utilities and constants shared across the plugin's governance modules.

After the file-sync engine was retired in M4 (``MIG-M4-REMOVE``), the only
consumers of this module are the plugin-native governance commands — chiefly
``migrate_plugin`` (which derives its file-sync→plugin REMOVE set from the
``MANAGED_FILES`` / ``MANAGED_DIRS`` path registry) and ``init_product`` (which
renders the place-once product-state templates and seeds ``.gitignore``). The
sync/init/validate command layer that once lived in ``tools/lib/`` — and the
helper functions here that only served it (manifest building, settings merge,
template/skill placement, framework-dir resolution, vN gitignore migration) —
is gone.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from collections.abc import Sequence
from typing import NamedTuple

# The plugin root: ``<root>/lib/core.py`` → ``<root>``. The previous
# ``parent.parent.parent`` was a byte-parity holdover from the file-sync
# ``tools/lib/`` depth — it resolved one level ABOVE the plugin root, so
# ``TEMPLATES_DIR`` pointed at a nonexistent path and ``PRAWDUCT_VERSION``
# silently read ``"dev"``. Fixed in review-fixes Chunk 1 (the file-sync
# engine, the parity constraint's reason, was removed in M4).
FRAMEWORK_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = FRAMEWORK_DIR / "templates"


# =============================================================================
# Constants
# =============================================================================

try:
    PRAWDUCT_VERSION = (FRAMEWORK_DIR / "VERSION").read_text().strip()
except FileNotFoundError:
    PRAWDUCT_VERSION = "dev"

#: What marks a development build's version (``3.8.2-dev.1``): the one test both
#: the contribution buckets and the native-review pairing ask, so they cannot
#: disagree on which builds are development builds.
DEV_VERSION_MARKER = "-dev"


def is_dev_version(version: "str | None") -> bool:
    """True when ``version`` names a development build. The bare ``"dev"`` a
    tree without a ``VERSION`` file reads is no version at all, so it is not."""
    return isinstance(version, str) and DEV_VERSION_MARKER in version


def is_dev_build() -> bool:
    """True when the running plugin is a development build. Reads
    :data:`PRAWDUCT_VERSION` at call time, so tests can set it."""
    return is_dev_version(PRAWDUCT_VERSION)

BLOCK_BEGIN = "<!-- PRAWDUCT:BEGIN -->"
BLOCK_END = "<!-- PRAWDUCT:END -->"

# The framework-managed file path registry. These are the file-sync framework
# files a *consuming* repo carries; ``migrate_plugin`` derives the cutover
# REMOVE / edit-in-place set from this registry (CLAUDE.md + .claude/settings.json
# are edited, the rest are removed), and ``update_gitignore`` un-ignores them so
# they stay committed. The plugin never *places* these — it ships governance from
# its own ``skills/`` + ``methodology/`` — so only the paths matter; the file-sync
# template/strategy metadata retired with the engine.
MANAGED_FILES: frozenset[str] = frozenset({
    "CLAUDE.md",
    ".prawduct/critic-review.md",
    ".prawduct/pr-review.md",
    ".prawduct/build-governance.md",
    ".claude/skills/pr/SKILL.md",
    ".claude/skills/janitor/SKILL.md",
    ".claude/skills/prawduct-doctor/SKILL.md",
    ".claude/skills/learnings/SKILL.md",
    ".claude/skills/prawduct-advisory/SKILL.md",
    ".claude/skills/backlog/SKILL.md",
    ".claude/skills/critic/SKILL.md",
    "tools/product-hook",  # prawduct:allow prawduct/legacy-ref -- 1.x file-sync hook; migration removes it from the consumer
    ".claude/settings.json",
})

# Managed directories: every matching file is framework-owned. The sole consumer
# is ``migrate_plugin``, which globs the *consumer's* ``tools/lib`` so it removes
# that repo's full (possibly older) module set during the cutover onto the plugin.
MANAGED_DIRS: dict[str, dict] = {
    "tools/lib": {  # prawduct:allow prawduct/legacy-ref -- 1.x file-sync module dir; migration globs + removes it
        "glob": "*.py",
    },
}

class CommittedPath(NamedTuple):
    """One path a plugin-governed product repo commits (see :data:`V2_COMMITTED_PATHS`)."""

    path: str  # repo-relative; a trailing "/" is a directory
    always: bool  # True: a scaffolded repo has it. False: it exists only once its feature is used
    why: str  # where it comes from, so the entry can be checked against its owner


# What a plugin-governed (v2) product repo needs COMMITTED, which is what a `.gitignore` rule must
# never hide. This is NOT ``MANAGED_FILES``: that is the 1.x file-sync registry, which
# ``migrate_plugin`` DELETES from a consumer, so a v2 repo never has those files. Source of truth:
# ``documentation/project-structure.md`` ("Product repos (plugin-governed)") plus what
# ``init_product`` scaffolds; each entry names its owner in ``why``.
#
# ``always`` splits what the scaffold creates (reported wherever it is hidden, present or not, so
# onboarding can say so before ``git init``) from state a feature writes later (reported only once
# it exists, so a repo that never uses the feature is not told it "needs" files it will not have).
# The "replace" remedy re-includes every entry regardless, so a rule narrowed today does not hide a
# file the feature creates tomorrow.
#
# Settled explicitly, because each was open to argument:
#   * ``.prawduct/project-state.yaml`` is committed: it is the shared source of truth, and
#     nothing in prawduct writes per-clone state into it (per-clone state is the dot-files in
#     ``GITIGNORE_ENTRIES``).
#   * ``.prawduct/releases/`` and ``release-headline.md`` are committed, ``always=False``: the
#     release cut (``change_cut``) writes them where ``consumer_digest:`` is declared, and they ARE
#     the shipped record; an ignored copy is lost on the next clone.
#   * ``.claude/rules/`` is committed (the learnings corpus) but ``.claude/`` as a whole is not:
#     personal skills and ``settings.local.json`` stay the owner's, so the remedy never asks to
#     un-ignore them.
V2_COMMITTED_PATHS: tuple[CommittedPath, ...] = (
    CommittedPath("AGENTS.md", True, "init_product: the governance anchor"),
    CommittedPath("CLAUDE.md", True, "init_product: imports AGENTS.md"),
    CommittedPath(".claude/settings.json", True, "init_product: the install reference"),
    CommittedPath(".claude/rules/", True, "learnings_files: the learnings corpus"),
    CommittedPath(".prawduct/project-state.yaml", True, "init_product: product state"),
    CommittedPath(".prawduct/backlog.md", True, "init_product: deferred work"),
    CommittedPath(".prawduct/changes/", True, "change_fragments.FRAGMENT_DIR_REL: the change record"),
    CommittedPath(".prawduct/artifacts/", True, "init_product: specs, plans, archive/"),
    CommittedPath(".prawduct/change-log.md", False, "change_log.CHANGE_LOG_REL_PATH: legacy log, until migrate-change-log"),
    CommittedPath(".prawduct/change-log-archive/", False, "change_log_archive.ARCHIVE_DIR_REL: shipped history"),
    CommittedPath(".prawduct/releases/", False, "consumer_digest.RELEASES_DIR_REL: written by the release cut"),
    CommittedPath(".prawduct/release-headline.md", False, "consumer_digest.HEADLINE_FILE_REL: the next release's headline"),
    CommittedPath(".prawduct/operator-verification.md", False, "operator_verification: the queue"),
    CommittedPath(".prawduct/owner-rulings.md", False, "methodology/building.md: the owner's dated rulings"),
    CommittedPath(".prawduct/runbooks/", False, "docs/runbook-authoring.md: operational procedures"),
)

# Session files that should be gitignored in product repos
GITIGNORE_ENTRIES = [
    ".claude/settings.local.json",
    ".prawduct/.critic-active",
    ".prawduct/.critic-findings.json",
    ".prawduct/.critic-partials/",
    ".prawduct/.critic-partials-archive/",
    # The paired native review's text (#1130), one file per Critic review. Its
    # wrapper writes it while the reviewers still run, so it must be a session
    # path: consolidation exempts these by path, and anything else written
    # mid-review refuses the review as a changed tree.
    ".prawduct/.native-reviews/",
    ".prawduct/.delegate-brief.md",
    ".prawduct/.governance-ledger.jsonl",
    ".prawduct/.handoff-notes.md",
    # The PR description `/prawduct:pr` drafts for `check-pr-body` and
    # `gh pr create --body-file`. The skill removes it after the create; a flow
    # that stops first leaves it, so it is ignored here and swept at the next
    # session boundary rather than ridden into the next `git add -A`.
    ".prawduct/.pr-body.md",
    ".prawduct/.test-evidence.json",
    # The conventional test report and its scope record
    # (`docs/test-report-contract.md`). Run output, regenerated by every run —
    # per-clone, never committed. They are listed here rather than left to each
    # product's own .gitignore because the contract fixes the path: a repo that
    # wires its runner to emit there gets the ignore rules from the managed
    # section it already has, without being told to add anything.
    ".prawduct/.test-report.xml",
    ".prawduct/.test-report.xml.scope.json",
    ".prawduct/.critic-review-dispatch.json",
    # What the Stop hook has parsed of each session's host transcript
    # (`host.session_tool_activity`), so a Stop reads only what was appended.
    ".prawduct/.session-activity.json",
    ".prawduct/.session-base-tree",
    ".prawduct/.session-git-baseline",
    ".prawduct/.session-handoff.md",
    ".prawduct/.session-reflected",
    ".prawduct/.session-start",
    ".prawduct/.subagent-briefing.md",
    ".prawduct/.gates-waived",
    ".prawduct/.advisories.json",
    ".prawduct/.work-model-index.json",
    "__pycache__/",
]

# Entries this list used to carry but that must now be TRACKED —
# update_gitignore strips them from existing repos and reports them so
# init-product/doctor can advise `git add`. Build plans (gate-soundness ch.3):
# a build plan is a durable, multi-session, release-spanning artifact — the
# methodology retains it through a gitflow release-pending window while
# tracked project-state.yaml points `active_build_plan:` at it. Ignoring it
# made every multi-clone repo carry a tracked pointer to a file the other
# clones don't have (scriob PR #43), and `_untrack_session_files` actively
# reverted any product that tracked its plan.
RETIRED_GITIGNORE_ENTRIES = [
    ".prawduct/artifacts/build-plan.md",
]


# =============================================================================
# Core utilities
# =============================================================================


def log(msg: str) -> None:
    """Print status to stderr."""
    print(msg, file=sys.stderr)


def atomic_write_text(
    path: Path, text: str, *, encoding: str = "utf-8", newline: str | None = None
) -> None:
    """Write ``text`` to ``path`` atomically: tmp sibling + ``os.replace``.

    ``encoding`` defaults to **utf-8**. It previously defaulted to ``None``,
    i.e. ``locale.getpreferredencoding(False)``, which made the round trip
    lossy on any non-UTF-8 locale and raised ``UnicodeEncodeError`` outright on
    non-ASCII content. That stayed latent only because the early callers wrote
    JSON at ``ensure_ascii=True``; ``.session-handoff.md`` does not, and it
    routinely carries em-dashes. The defect is invisible on a UTF-8 machine,
    which is why it survived so long — the guarding test forces the locale in a
    subprocess rather than asserting in-process.

    **The writer alone does not settle the round trip — each reader must ask
    for utf-8 too.** There are 11 call sites (four of them in the extensionless
    ``bin/prawduct-hook``, which a ``*.py``-filtered grep does not see), and
    their readers were not uniformly utf-8: ``operator_verification`` wrote
    through here and read back with a bare ``read_text()``. That pair was
    self-inverse while both used the locale encoding and became asymmetric the
    moment this default changed — transcoding a committed product file on the
    next status mutation. Fixed at that reader. Before adding a call site,
    check what reads the file back.

    ``newline`` still defaults to ``None`` (universal-newline translation) and
    is a separate concern: it exists for callers whose target is **not**
    framework state, where a write into a product's authored file must not
    re-line-end the bytes around its insertion. Pass ``newline=""`` from any
    repair that edits a file the product wrote — an operation promising to touch
    two keys otherwise hands back a whole-file reformat on a CRLF repo.

    The shared writer for ``.prawduct/`` state files (STH-8M3V; same pattern
    as the hook's ``.test-evidence.json`` writer). Their readers fail open on
    a missing or corrupt file, so a torn write from two concurrent sessions
    on one repo degrades a gate silently rather than crashing — ``os.replace``
    guarantees every reader sees either the old content or the new, never a
    prefix. OSErrors propagate: each caller owns its failure policy
    (best-effort + stderr NOTE on the hook's session paths, a
    ``{status: error}`` return in ``advisory_store.write_store``). A stale
    ``.tmp`` sibling left by a crash between write and replace is harmless —
    the next write overwrites it.
    """
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding=encoding, newline=newline) as handle:
        handle.write(text)
    os.replace(tmp, path)


def _read_exact(path: Path) -> str:
    """``path``'s text with its line endings untouched (no universal-newline read)."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def read_text_and_eol(path: Path) -> tuple[str, str]:
    """``(text, eol)``: ``path``'s text as a universal-newline read gives it, and its line ending.

    For a writer that rewrites a file it did not create through
    :func:`write_all_or_none`, which writes ``newline=""``: parse ``text`` as
    before, then write :func:`with_eol` of the result, so a CRLF file stays
    CRLF. The parsers downstream keep seeing ``\\n`` only, which is why this
    hands back normalized text rather than the exact bytes. ``eol`` is the
    first line's terminator; a file with mixed endings comes back in that one.
    Raises what ``Path.read_text`` raises.
    """
    exact = _read_exact(path)
    return exact.replace("\r\n", "\n").replace("\r", "\n"), eol_of(exact)


def eol_of(exact: str) -> str:
    """The terminator of ``exact``'s first line — ``"\\n"`` when it has none."""
    for index, char in enumerate(exact):
        if char == "\n":
            return "\n"
        if char == "\r":
            return "\r\n" if exact[index + 1 : index + 2] == "\n" else "\r"
    return "\n"


def with_eol(text: str, eol: str) -> str:
    """``text`` (``\\n``-terminated lines) with every line ending ``eol``."""
    return text if eol == "\n" else text.replace("\n", eol)


class RollbackIncomplete(OSError):
    """A :func:`write_all_or_none` write failed, and the rollback left files changed.

    ``unrestored`` names the files that kept their new content. Its message is
    the original failure's, and ``__cause__`` is that failure.
    """

    def __init__(self, cause: BaseException, unrestored: "list[Path]") -> None:
        super().__init__(str(cause))
        self.unrestored = unrestored


def write_failure_outcome(exc: BaseException) -> str:
    """What a failed :func:`write_all_or_none` left behind, as a sentence for the refusal.

    The one place a caller learns whether "every file was restored" is true, so
    no caller reports a restore that did not happen.
    """
    if isinstance(exc, RollbackIncomplete):
        names = ", ".join(str(path) for path in exc.unrestored)
        return (
            f"The rollback could not restore {names}, which kept its new content while the "
            "rest were restored; do not re-run until it is reconciled by hand."
        )
    return "Every file was restored; re-run when the cause is fixed."


def write_all_or_none(writes: "Sequence[tuple[Path, str]]") -> None:
    """Write every ``(path, text)`` pair, or leave every one of them untouched.

    :func:`atomic_write_text` makes ONE file's write all-or-nothing. It says
    nothing about two, and a command that rewrites a pair of files has a failure
    mode neither call can see: the first write lands, the second raises, and the
    two files now disagree in a way no reader can detect. Where the pair is a
    record and its archive — entries MOVED from one to the other — that state
    holds every entry twice, and the natural recovery (run it again) duplicates
    them into an append-only file.

    Each write still goes through the atomic writer, so no reader ever sees a
    partial file. What this adds is the rollback ACROSS them: prior contents are
    captured first, and a failure restores every file already written — deleting
    the ones that did not exist before — then re-raises so the caller's failure
    policy is unchanged.

    Rollback is best-effort by construction: if restoring also fails there is
    nothing left to try, and the original exception is the one worth raising, so
    an ``OSError`` from a restore does not mask it — but it is NOT silent: every
    path the rollback could not restore is named on stderr, and an ordinary
    failure is raised as :class:`RollbackIncomplete` carrying those paths, so
    the caller's message comes from that state (:func:`write_failure_outcome`).
    The pair is then half-applied, and the documented recovery (run it again)
    would duplicate every moved entry into an append-only file. An interrupt is
    still re-raised unchanged. Only ``OSError`` is caught there
    — anything else escaping a restore is a bug in this function, not a disk
    that filled, and swallowing it would hide it forever.

    Two edges the rollback cannot cover are refused up front instead. Every prior
    is read BEFORE the first write: a file that exists but cannot be read is one
    the rollback could only delete, and turning "unreadable" into "gone" is a
    worse state than the one it started in. And the rollback runs on
    ``BaseException``, not ``Exception``: an operator's Ctrl-C between the two
    replaces is exactly the half-applied pair this function exists to prevent,
    and it is not an error in the ordinary sense — but it is still the moment to
    restore, and the interrupt is re-raised unchanged.

    **Text goes through byte for byte, both ways.** Every write and every
    restore uses ``newline=""``, and every prior is read the same way, so
    neither direction translates line endings. A caller's ``\n`` is written as
    ``\n`` and a CRLF file it rewrites keeps its ``\r\n``. A universal-newline
    read of the prior would quietly turn a product's CRLF file into LF on the one
    path meant to leave it as it was: the rollback.
    """
    priors: list[str | None] = []
    for path, _text in writes:
        priors.append(_read_exact(path) if path.exists() else None)
    written: list[tuple[Path, str | None]] = []
    try:
        for (path, text), prior in zip(writes, priors):
            atomic_write_text(path, text, newline="")
            written.append((path, prior))
    except BaseException as exc:
        unrestored: list[Path] = []
        for path, prior in reversed(written):
            try:
                if prior is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write_text(path, prior, newline="")
            except OSError as restore_exc:
                unrestored.append(path)
                print(
                    f"ROLLBACK FAILED for {path}: {restore_exc} — this file kept its NEW "
                    "content while the others were restored; do not re-run until it is "
                    "reconciled by hand",
                    file=sys.stderr,
                )
        if unrestored and isinstance(exc, Exception):
            raise RollbackIncomplete(exc, unrestored) from exc
        raise


# Optional project-state pointer naming the active build plan (relative to the
# `.prawduct/` dir). When unset, tooling uses the conventional default below, so
# repos that don't set it keep their existing behavior.
BUILD_PLAN_POINTER_KEY = "active_build_plan"
DEFAULT_BUILD_PLAN_REL = "artifacts/build-plan.md"


#: The three answers a column-0 scalar read can give. ``read_str_yaml_key``
#: collapses the last two, which is right for every key whose absence and whose
#: explicit ``null`` mean the same thing. Where they mean DIFFERENT things — a
#: control that is on unless a repo turns it off — the collapse is the bug, so
#: the distinction gets a reader rather than each such key re-scanning the file.
YAML_SCALAR_ABSENT = "absent"
YAML_SCALAR_NULL = "null"
YAML_SCALAR_VALUE = "value"


def unquote_scalar(value: str) -> str:
    """Strip one pair of quotes only when they wrap the WHOLE value.

    A bare ``strip("\\"'")`` is not unquoting: it corrupts any value that merely
    starts or ends with a quote, and a declared test command routinely does
    (``node --test 'dir/*.mjs'``, ``"$VENV/bin/pytest" -k "not slow"``), leaving
    an unbalanced quote that fails far from here. A value whose quote character
    recurs inside is left as written, because it is several quoted words rather
    than one quoted scalar."""
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0] and value[0] not in value[1:-1]:
        return value[1:-1]
    return value


def strip_scalar_comment(value: str) -> str:
    """A scalar's text with its trailing ``#`` comment removed, quote-aware.

    A ``#`` inside a quoted scalar is data — this repo spells backlog ids
    ``#772``, and a recorded answer quoting one must round-trip whole. So a
    single quoted scalar keeps everything through its closing quote (honouring
    its escapes), and only what follows can be a comment. Otherwise a comment
    starts at a ``#`` that begins the value or follows whitespace (YAML's rule,
    so ``foo#bar`` stays whole) and sits outside any quoted word — a declared
    command is several quoted words (``"$VENV/bin/pytest" -k "not #slow"``), and
    a quote only opens a word, so the apostrophe in ``Ada's`` opens nothing.
    An unterminated quote keeps the rest of the line rather than guessing where
    it meant to end.
    """
    value = value.strip()
    if value[:1] in ("\"", "'"):
        quote = value[0]
        i = 1
        while i < len(value):
            if quote == '"' and value[i] == "\\":
                i += 2
                continue
            if value[i] == quote:
                if quote == "'" and value[i + 1:i + 2] == "'":
                    i += 2  # '' is an escaped quote inside a single-quoted scalar
                    continue
                rest = value[i + 1:].lstrip()
                if not rest or rest[0] == "#":
                    return value[: i + 1]
                break  # several quoted words, not one quoted scalar
            i += 1
        else:
            return value
    in_quote = None
    for i, char in enumerate(value):
        if in_quote:
            if char == in_quote:
                in_quote = None
        elif char in ("\"", "'") and (i == 0 or value[i - 1] in " \t"):
            in_quote = char
        elif char == "#" and (i == 0 or value[i - 1] in " \t"):
            return value[:i].rstrip()
    return value


def read_scalar_yaml_key(state_path: Path, key: str) -> "tuple[str, str | None]":
    """``(state, value)`` for a top-level (column-0) ``key: value`` scalar.

    ``state`` is :data:`YAML_SCALAR_ABSENT` (no such key, or the file is
    missing/unreadable), :data:`YAML_SCALAR_NULL` (declared with an empty value
    or the YAML null literal ``null`` / ``~``, case-insensitive), or
    :data:`YAML_SCALAR_VALUE` with the value carried alongside. Surrounding
    quotes and inline ``#`` comments are stripped; indented and commented-out
    occurrences are ignored.

    THE column-0 scanner: :func:`read_str_yaml_key` is a thin wrapper that
    collapses the two unset states, so there is one parser to be wrong.
    """
    try:
        content = state_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # A file that is not decodable text is *unreadable*, which is what this
        # promises to fail soft on. `UnicodeDecodeError` is a `ValueError`, so
        # catching only `OSError` let it escape — and every caller reads this
        # through a guard shaped for the absent answer, so the raise surfaced
        # far from here. `already_migrated` is the sharp case: it calls this
        # first, so an undecodable state file aborted the cutover before any of
        # the later steps could reach their own decode guards.
        return YAML_SCALAR_ABSENT, None
    needle = f"{key}:"
    for raw in content.splitlines():
        if raw[:1] in (" ", "\t"):
            continue
        if not raw.startswith(needle):
            continue
        value = unquote_scalar(strip_scalar_comment(raw[len(needle):]))
        if not value or value.lower() in ("null", "~"):
            return YAML_SCALAR_NULL, None
        return YAML_SCALAR_VALUE, value
    return YAML_SCALAR_ABSENT, None


#: States of a ``project-preferences.md`` Workflow row, as read by
#: :func:`read_preference_row`.
PREF_ROW_NO_FILE = "no-file"
PREF_ROW_UNREADABLE = "unreadable"
PREF_ROW_ABSENT = "absent"
PREF_ROW_PRESENT = "present"


class PreferenceRow(NamedTuple):
    """One Workflow row of ``project-preferences.md``. ``value`` is set only
    when the row is present: lowercased, unquoted, and cut at the first ``(``,
    because the parenthetical is guidance for the human. A row reading
    ``(unset — …)`` therefore has the empty value. ``error`` is set only when
    the file exists and cannot be read."""

    state: str
    value: "str | None" = None
    error: "str | None" = None


def read_preference_row(project_dir: Path, label: str, *, lower: bool = True) -> PreferenceRow:
    """THE reader of a ``- **<Label>**: value (…)`` row, shared by every consent
    gate so a parser fix cannot reach one gate and miss another. Each caller
    maps the result to its own states and defaults, because they differ on
    purpose: upstream filing defaults to asking, stats contribution to never.

    ``lower=False`` keeps the value's case, for a row whose value names things
    that are case-sensitive, such as git branches."""
    path = Path(project_dir) / ".prawduct" / "artifacts" / "project-preferences.md"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return PreferenceRow(PREF_ROW_NO_FILE)
    except (OSError, UnicodeDecodeError) as exc:
        return PreferenceRow(PREF_ROW_UNREADABLE, error=str(exc))
    match = re.search(
        rf"^[ \t]*[-*][ \t]*\*\*[ \t]*{re.escape(label)}[ \t]*\*\*[ \t]*:(?P<value>.*)$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if match is None:
        return PreferenceRow(PREF_ROW_ABSENT)
    value = match.group("value").split("(", 1)[0].strip().strip("`")
    return PreferenceRow(PREF_ROW_PRESENT, value=value.lower() if lower else value)


def read_str_yaml_key(state_path: Path, key: str) -> str | None:
    """Value of a top-level (column-0) ``key: value`` scalar, or None.

    Mirrors the column-0 idiom used by :func:`read_bool_flag` — no PyYAML
    dependency, fail-soft to None on a missing/unreadable file or absent key.
    Surrounding quotes and inline ``#`` comments are stripped; an empty value, or the YAML null literal (``null`` /
    ``~``, case-insensitive), reads as None — so ``active_build_plan: null`` means
    "unset", the same opt-out :func:`lib.plan_index.parse_build_plan_frontmatter_scope`
    already honors for ``scope:`` (VWS-7N3K). Without this, a literal ``null``
    survived as the truthy string ``"null"`` and resolved to ``.prawduct/null``.
    """
    return read_scalar_yaml_key(state_path, key)[1]


# =============================================================================
# The one block-sequence reader (BKL-#590)
# =============================================================================
#
# Four hand-rolled column-0 minimal-YAML readers had drifted, and two of them
# returned SILENTLY WRONG answers on inputs the others handled. A column-0
# comment inside a block truncated the list in two of them; flow style
# (``key: [a, b]``) read as *declared empty* in two of them — and
# ``risk_surfaces:`` honours declared-empty EXCLUSIVELY, so a real declaration
# resolved to zero risk surfaces and a governance gate quietly relaxed.
#
# The parsing is one implementation now. What legitimately differs per key is
# the POLICY on the third outcome — what "declared in a shape I cannot parse"
# should cost — and that is a call-site decision, stated at each call site:
#
#   ``test_commands``          refuse loudly (running the deprecated fallback
#                              against an operator's explicit declaration could
#                              persist GREEN evidence for an invocation nobody
#                              declared)
#   ``risk_surfaces``          refuse loudly (the alternative is relaxing a
#                              governance gate on a typo)
#   ``release_version_files``  UNVERIFIABLE, naming the shape (a guess must
#                              never be able to FAIL a release, so refusing is
#                              too strong; passing over it is too weak)
#
# The three outcomes the readers agree on.

#: No column-0 ``key:`` line exists — a fallback is legitimate.
YAML_ABSENT = "absent"
#: Parsed cleanly. The item list may be empty (``key: []``, or an empty block),
#: which is a *deliberate* declaration and never the same fact as absence.
YAML_DECLARED = "declared"
#: The key is there, in a shape this reader does not parse. Never a partial
#: answer: a half-read declaration is how an operator's statement gets silently
#: dropped while the record claims full evidence.
YAML_UNPARSEABLE = "unparseable"


def read_yaml_block(text: str, key: str) -> tuple[str, tuple[str, ...]]:
    """The significant lines under a column-0 ``key:`` block, and how it read.

    Returns ``(status, lines)`` where ``status`` is :data:`YAML_ABSENT`,
    :data:`YAML_DECLARED` or :data:`YAML_UNPARSEABLE`, and ``lines`` are the
    block's indented lines with comments stripped and whitespace trimmed. Shape
    interpretation is the caller's — this answers only "is the key there, does
    the block terminate cleanly, and what is in it".

    **Comments and blank lines are inert at ANY indent, column 0 included.**
    Treating a column-0 comment as the end of the block is the truncation bug:
    the declaration continues below it and everything after is silently dropped.

    **An inline value other than ``[]`` is unparseable, not empty.** Flow style
    (``key: [a, b]``) and a scalar under a list key are real declarations this
    reader cannot read, and calling them "declared empty" inverts their meaning.
    ``key: []`` alone is the deliberate empty declaration.

    No PyYAML: the governance runtime is stdlib-only, and these files are read on
    the session-start hot path.
    """
    lines = text.splitlines()
    needle = f"{key}:"
    for index, raw in enumerate(lines):
        if raw[:1] in (" ", "\t"):
            continue
        if not strip_scalar_comment(raw).startswith(needle):
            continue
        inline = strip_scalar_comment(raw).split(":", 1)[1].strip()
        if inline == "[]":
            return YAML_DECLARED, ()
        if inline:
            return YAML_UNPARSEABLE, ()
        body: list[str] = []
        for follow in lines[index + 1:]:
            stripped = strip_scalar_comment(follow)
            if not stripped:
                continue  # blank or comment-only — inert at any indent
            if follow[:1] not in (" ", "\t"):
                break  # the next column-0 key ends the block cleanly
            body.append(stripped)
        return YAML_DECLARED, tuple(body)
    return YAML_ABSENT, ()


def read_block_sequence(text: str, key: str) -> tuple[str, tuple[str, ...]]:
    """:func:`read_yaml_block` narrowed to a block sequence of plain strings.

    Any in-block anomaly — a nested mapping, a bare dash, a wrapped continuation
    line, an empty item — makes the WHOLE declaration
    :data:`YAML_UNPARSEABLE`, never a partial list. A partial list is the
    dangerous answer: it silently drops part of what an operator declared while
    every downstream record claims the declaration was honoured.
    """
    status, body = read_yaml_block(text, key)
    if status != YAML_DECLARED:
        return status, ()
    items: list[str] = []
    for line in body:
        if not line.startswith("- "):
            return YAML_UNPARSEABLE, ()
        value = unquote_scalar(line[2:].strip())
        if not value:
            return YAML_UNPARSEABLE, ()
        items.append(value)
    return YAML_DECLARED, tuple(items)


def yaml_top_level_key_present(text: str, key: str) -> bool:
    """Whether a column-0 ``key:`` line exists at all — presence, not shape.

    The companion that lets a caller tell "absent" (a fallback is legitimate)
    from "declared in a shape the reader does not parse" (say so; silently
    degrading past an operator's declaration is the failure mode). Redundant with
    :data:`YAML_UNPARSEABLE` for callers that read the status, and kept for the
    ones that only carry a ``list | None``.
    """
    return any(
        raw[:1] not in (" ", "\t") and strip_scalar_comment(raw).startswith(f"{key}:")
        for raw in text.splitlines()
    )


#: Default size, in KB, above which a governance file earns a size nudge.
#: ~10K tokens ≈ ~40KB, and every reader of these files pays it once per session.
OVERSIZED_FILE_KB = 40

#: ``project-state.yaml`` key overriding :data:`OVERSIZED_FILE_KB` for this repo.
#:
#: A bare constant penalises thorough decision recording: a product whose
#: ``project-state.yaml`` is mostly ``technical_decisions`` is doing exactly what
#: the Reasoned Decisions principle asks for, and a fixed ceiling tells it to stop
#: — the more faithfully a repo records reasoning, the louder the framework
#: complains. A repo that has weighed the trade can raise its own ceiling instead
#: of living with a nag it has correctly decided not to act on.
OVERSIZED_FILE_THRESHOLD_KEY = "oversized_file_threshold_kb"


#: Path prefixes whose files a NON-HERMETIC test in THIS repo reads, declared by
#: the repo rather than assumed by the framework.
#:
#: :data:`coverage_algebra.TEST_COUPLED_STATE` is the shipped half — files like
#: ``project-state.yaml`` that every governed product has. This is the half that
#: cannot be shipped: which directories hold prose a test scans is a fact about
#: one repo's layout, and hardcoding any of it into the runtime makes the rule
#: inert for every product that names its directories differently while taxing
#: every product that happens to match. Absent means empty, so a product that
#: declares nothing behaves exactly as before.
SUITE_COUPLED_PREFIXES_KEY = "suite_coupled_prefixes"


def suite_coupled_prefixes(prawduct_dir: Path) -> tuple[str, ...]:
    """Path prefixes this repo declares its non-hermetic tests read.

    Reads :data:`SUITE_COUPLED_PREFIXES_KEY` from ``project-state.yaml`` as a
    block sequence of strings via :func:`read_block_sequence`. ``()`` on a
    missing file or an absent key — the pre-declaration behaviour.

    **A declaration the reader cannot read whole couples EVERYTHING** (``("",)``,
    a prefix every path starts with), never a partial list or ``()`` (#780). A
    dropped root reads its files as not suite-coupled, so a change under it would
    let day-old evidence read *current* over a red tree — the false-fresh verdict
    the key exists to prevent. Coupling every path can only cost a suite run, the
    same escalation the ``risk_surfaces`` path-wise reader makes on a shape it
    cannot parse.

    Entries are plain path prefixes against repo-relative paths, so a trailing
    slash matters and is the caller's to write: ``doc/`` must not match
    ``documentation/``. They are NOT restricted to ``.md`` — declaring a root
    couples every file under it, which is the fail-safe direction.
    """
    state = prawduct_dir / "project-state.yaml"
    try:
        text = state.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ()
    status, items = read_block_sequence(text, SUITE_COUPLED_PREFIXES_KEY)
    if status == YAML_UNPARSEABLE:
        return ("",)
    return items


def oversized_file_threshold(prawduct_dir: Path) -> int:
    """Bytes above which a governance file earns a size nudge, for this repo.

    :data:`OVERSIZED_FILE_KB` unless ``project-state.yaml`` sets
    :data:`OVERSIZED_FILE_THRESHOLD_KEY` to a positive integer. Fail-soft in both
    directions — a missing file, an absent key, or a value that is not a positive
    integer all fall back to the default, because a typo in a tuning knob must not
    silence a nudge (0 or a negative would make everything oversized or nothing).

    KB here is 1000 bytes, matching the constant this replaced (``40000``), so an
    unconfigured repo sees the same threshold it always did.
    """
    raw = read_str_yaml_key(prawduct_dir / "project-state.yaml", OVERSIZED_FILE_THRESHOLD_KEY)
    kilobytes = OVERSIZED_FILE_KB
    if raw is not None:
        try:
            configured = int(raw)
        except ValueError:
            configured = 0
        if configured > 0:
            kilobytes = configured
    return kilobytes * 1000


REVIEW_ROUND_BUDGET_KEY = "review_round_budget"

#: Full review rounds one body of work may buy before the framework stops
#: selling them. **On by default in every governed repo**, unlike the opt-in
#: flags below — an off-by-default terminating rule is a mechanism that works
#: and that nobody knows exists (#716 reports exactly that about
#: ``cost-of-commit``), and the loop this ends is one the data says has no
#: natural fixed point: measured across this clone's evidence store, finding
#: yield per full round rises rather than decays (13.5 → 15.4 → 15.5 → 18.4),
#: 99% of them new. Where nothing decays, the only principled stop is a
#: declared one.
#:
#: Six rather than four: it sits above every chain in the measured store that
#: ever produced a late BLOCKING finding, so it costs close to nothing in
#: missed defects, while still catching the 20-to-34-round chains whose round
#: count is indefensible on any reading.
REVIEW_ROUND_BUDGET_DEFAULT = 6


def review_round_budget(prawduct_dir: Path) -> "int | None":
    """This repo's full-round ceiling, or ``None`` when it is disabled.

    :data:`REVIEW_ROUND_BUDGET_DEFAULT` unless ``project-state.yaml`` declares
    :data:`REVIEW_ROUND_BUDGET_KEY`. **An explicit ``null`` disables the budget
    and an absent key does not** — which is why this reads through
    :func:`read_scalar_yaml_key` rather than :func:`read_str_yaml_key`, whose
    collapse of those two states would make "off" unexpressible.

    Fail-soft in the direction that keeps working: a value that is not a
    positive integer falls back to the default rather than to disabled, because
    a typo in a stopping rule must not silently remove it — and 0 or a negative
    would refuse a scope's very first round, which no repo means.
    """
    state, raw = read_scalar_yaml_key(
        prawduct_dir / "project-state.yaml", REVIEW_ROUND_BUDGET_KEY
    )
    if state == YAML_SCALAR_NULL:
        return None
    if state == YAML_SCALAR_VALUE:
        try:
            configured = int(raw)
        except ValueError:
            return REVIEW_ROUND_BUDGET_DEFAULT
        if configured > 0:
            return configured
    return REVIEW_ROUND_BUDGET_DEFAULT


#: Every boolean opt-in flag a product may set in ``project-state.yaml``.
#:
#: **This exists because "three declarations with nothing comparing them" is a
#: root cause, not a tidiness complaint.** A flag is declared in the template a
#: product is scaffolded from, in the code that reads it, and in the prose that
#: explains it — and when the template shipped one default while the reader
#: assumed another, the disagreement was invisible for four minor versions and
#: cost a whole subsystem's retirement to unwind. Naming the set here gives the
#: comparison something to iterate, so the next flag whose template value and
#: code default diverge fails a test instead of shipping.
#:
#: Opt-in is the whole contract: :func:`read_bool_flag` reads False for a missing
#: file, an absent key, or a malformed line, so **False is the code default for
#: every member** and the template must say so too. A file that exists and
#: cannot be read is not "absent" and does not default: it is reported.
OPT_IN_FLAGS: tuple[str, ...] = (
    "coverage_required",
    "operator_verification_required",
)


#: States of a boolean opt-in flag read, as returned by :func:`read_bool_flag`.
FLAG_OK = "ok"
FLAG_UNREADABLE = "unreadable"


def read_bool_flag(path: Path, key: str) -> dict:
    """The one reader of a top-level (column-0) boolean opt-in ``key``.

    Returns ``{"status": FLAG_OK | FLAG_UNREADABLE, "value": bool, "reason":
    str | None}``. ``value`` is True only for a readable ``key: true``; the
    value is lowercased and compared to ``"true"`` (quotes are *not* stripped,
    so a quoted ``"true"`` reads as False).

    **Absent is not unreadable, and the two take opposite answers.** A missing
    file, a path whose parent is not a directory, an absent key or an indented
    line is a repo that never opted in: ``ok`` with ``value`` False. A file that
    EXISTS and cannot be read (permission denied, a directory in its place,
    bytes that are not UTF-8) is ``unreadable``: an operator who turned a gate on
    cannot be told it is off because the file holding the answer went bad. The
    caller turns that status into its own refusal (api-contract.md § Error
    Model) rather than a verdict.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError):
        return {"status": FLAG_OK, "value": False, "reason": None}
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "status": FLAG_UNREADABLE,
            "value": False,
            "reason": (
                f"cannot read {path} ({type(exc).__name__}), so whether `{key}` "
                "is on is unknown. An unreadable state file is not a gate that "
                "is off: fix the file's permissions or encoding and re-run."
            ),
        }
    needle = f"{key}:"
    for raw in content.splitlines():
        if raw[:1] in (" ", "\t"):
            continue
        line = raw.split("#", 1)[0].rstrip()
        if not line.startswith(needle):
            continue
        value = line.split(":", 1)[1].strip().lower()
        return {"status": FLAG_OK, "value": value == "true", "reason": None}
    return {"status": FLAG_OK, "value": False, "reason": None}


def pointer_plan_path(prawduct_dir: Path) -> Path | None:
    """The ``active_build_plan:`` scalar as a path, or ``None`` when unset.

    The one place the scalar becomes a PATH, and that is now true by
    construction rather than by convention: the legacy window of the work-unit
    binding (``work_unit.resolve``), the release sweep's archive guard
    (:func:`plan_backfill._active_plan_path`) and the operator notices route
    through here. They previously spelled the prefix rule
    themselves — four copies of one rule, so widening or tightening the accepted
    spelling here would have left the sweep and the notices resolving a different
    file from the same line of YAML. (The raw string is still read directly
    wherever a message quotes what the operator actually wrote — that is the
    value, not the path.)

    Returns ``None`` for an unset pointer AND for one that is nothing but the
    prefix, since stripping it leaves no path to name.

    The pointer is ``.prawduct/``-relative, but the natural repo-relative
    spelling (``.prawduct/artifacts/x-plan.md``) is accepted by stripping the
    prefix — that spelling once shipped and silently disabled the gates for a
    work cycle (STH-5P2W).
    """
    pointer = read_str_yaml_key(prawduct_dir / "project-state.yaml", BUILD_PLAN_POINTER_KEY)
    if pointer and pointer.startswith(".prawduct/"):
        pointer = pointer[len(".prawduct/"):]
    return prawduct_dir / pointer if pointer else None


def fallback_plan_path(prawduct_dir: Path) -> Path:
    """The plan the fallback routes name: the ``active_build_plan`` pointer, else
    the conventional ``artifacts/build-plan.md``. May not exist.

    The raw candidate, before ``work_unit.resolve`` asks whether the legacy
    window may serve it — exposed so the resolver and a diagnosis of *why*
    nothing resolved (``buildplan_refs.unresolved_scope_cause``) read the same
    file rather than re-spelling the two routes.
    """
    return pointer_plan_path(prawduct_dir) or prawduct_dir / DEFAULT_BUILD_PLAN_REL


def foreign_fallback_claim(prawduct_dir: Path) -> tuple[Path, str] | None:
    """``(plan, its branch)`` when the fallback plan declares a branch other than
    the one checked out, else ``None``.

    A diagnosis, not a resolution: ``buildplan_refs.unresolved_scope_cause``
    explains a scope-less review by it. The refusal it explains is
    ``work_unit.resolve``'s — a plan declaring a branch is never served to
    another, and its claim closes the legacy window for the whole repo.
    ``None`` too when the plan is missing, unreadable or claims nothing, and on
    a detached HEAD or outside a work tree, where there is no branch for a
    claim to contradict.
    """
    fallback = fallback_plan_path(prawduct_dir)
    from . import plan_index  # noqa: PLC0415 — lazy: core's top level stays stdlib-only

    try:
        declared = plan_index.parse_build_plan_frontmatter_branch(
            fallback.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError):
        return None  # missing or unreadable: each caller already says so
    if declared is None:
        return None

    from . import gitstate  # noqa: PLC0415 — same reason; also a git subprocess

    branch = gitstate.current_branch(prawduct_dir.parent)
    if branch and branch != declared:
        return fallback, declared
    return None


def extract_block(content: str) -> tuple[str | None, str, str]:
    """Extract content between PRAWDUCT markers.

    Returns (block, before, after) where before + block + after == content.
    Returns (None, content, "") if markers are missing or malformed
    (e.g. BEGIN without END, or END before BEGIN).
    """
    begin_idx = content.find(BLOCK_BEGIN)
    end_idx = content.find(BLOCK_END)

    if begin_idx == -1 or end_idx == -1 or end_idx <= begin_idx:
        return (None, content, "")

    before = content[:begin_idx]
    block = content[begin_idx : end_idx + len(BLOCK_END)]
    after = content[end_idx + len(BLOCK_END) :]

    return (block, before, after)


# =============================================================================
# Template / file operations
# =============================================================================


def render_template(template_path: Path, subs: dict[str, str]) -> str:
    """Read a template file and apply variable substitutions."""
    content = template_path.read_text()
    for key, value in subs.items():
        content = content.replace(key, value)
    return content


def write_template(src: Path, dst: Path, subs: dict[str, str], *, overwrite: bool = False) -> bool:
    """Copy a template with variable substitution.

    Without overwrite: skips if dst exists.
    With overwrite: idempotent via content comparison.
    Returns True if file was written.
    """
    content = render_template(src, subs)

    if dst.is_file():
        if not overwrite:
            return False
        if dst.read_text() == content:
            return False  # Already up to date

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content)
    return True


#: Appended to a directory entry (``.prawduct/.critic-partials/``) to name a file
#: inside it. A directory entry is satisfied when the files INSIDE it are ignored,
#: by its own rule or by a broader one, so that is the path git is asked about.
_DIR_ENTRY_PROBE = "prawduct-probe"


def _entry_probe_path(entry: str) -> str:
    return entry + _DIR_ENTRY_PROBE if entry.endswith("/") else entry


#: The file git is asked about for a COMMITTED directory entry. ``.md`` on purpose: what lives in
#: those directories is mostly Markdown, so a ``*.md`` rule must show up as hiding them.
_COMMITTED_DIR_PROBE = "prawduct-probe.md"


def _committed_probe_path(path: str) -> str:
    return path + _COMMITTED_DIR_PROBE if path.endswith("/") else path


def _committed_in_scope(target: Path) -> list[str]:
    """The v2 committed paths whose being ignored is worth reporting for ``target``.

    :data:`V2_COMMITTED_PATHS` entries that a scaffolded repo always has, plus the on-demand ones
    that exist on disk here; plus the retired entries not already inside a committed directory
    (the build plan is covered by ``.prawduct/artifacts/``, and naming both says one thing twice).
    """
    out = [
        c.path for c in V2_COMMITTED_PATHS if c.always or (Path(target) / c.path).exists()
    ]
    dirs = [c.path for c in V2_COMMITTED_PATHS if c.path.endswith("/")]
    out += [r for r in RETIRED_GITIGNORE_ENTRIES if not any(r.startswith(d) for d in dirs)]
    return out


def _shared_ignore_matches(
    target: Path, content: str, paths: list[str]
) -> dict[str, tuple[str, int, str]] | None:
    """Which of ``paths`` a SHARED ``.gitignore`` rule ignores, asked of git.

    Returns ``{path: (source, line, pattern)}`` for the paths ignored by a
    non-negated rule in a ``.gitignore`` file, or ``None`` when git could not be
    asked at all (the caller then falls back to literal lines and says so).

    **Why git is asked rather than the file parsed.** gitignore semantics (parent
    directory exclusion, ``*``/``**``, anchoring, negation order, nested files) are
    exactly what a re-implementation gets subtly wrong, and the failure is the one
    this function exists to prevent: a confident wrong answer about what git hides.

    **Two ways to ask.** In a work tree, of the repo itself (so a nested
    ``.gitignore`` counts). Where there is no work tree (the ``onboard`` case
    before the repo exists), in a scratch repo holding only the ``.gitignore``
    text; that evaluates the same rules without a repo to ask. ``None`` only when
    git is missing or fails both ways.

    **Only a ``.gitignore`` inside the work tree counts, decided by PATH.** The
    contract is about what travels with the repo. A rule from ``.git/info/exclude``
    or a global excludes file is this machine's, not another clone's, so it neither
    satisfies a session entry nor makes a committed file a hazard. A global file is
    commonly named ``.gitignore`` too (``core.excludesFile=~/.gitignore``), so the
    name alone proves nothing: see :func:`_is_tree_gitignore`.
    """
    from . import gitstate  # noqa: PLC0415 — lazy: keeps core's import surface unchanged

    tree = target
    rules = gitstate.git_ignore_rules(target, paths)
    if rules is None:
        import subprocess  # noqa: PLC0415
        import tempfile  # noqa: PLC0415

        # A scratch repo must not inherit GIT_DIR / GIT_WORK_TREE / GIT_INDEX_FILE
        # (set while a git hook runs): creating it would then act on THAT repo.
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        with tempfile.TemporaryDirectory(prefix="prawduct-gitignore-") as scratch:
            try:
                subprocess.run(
                    ["git", "init", "-q", "."],
                    cwd=scratch, env=env, check=True, capture_output=True, timeout=10,
                )
                (Path(scratch) / ".gitignore").write_text(content, encoding="utf-8")
            except (OSError, subprocess.SubprocessError):
                return None
            rules = gitstate.git_ignore_rules(Path(scratch), paths, env=env)
            tree = Path(scratch)
        if rules is None:
            return None
    return {
        path: rule
        for path, rule in rules.items()
        if _is_tree_gitignore(rule[0], tree) and not rule[2].startswith("!")
    }


def _is_tree_gitignore(source: str, tree: Path) -> bool:
    """Whether a rule's ``source`` (as ``git check-ignore -v`` prints it) is a ``.gitignore``
    inside the work tree ``tree``, the one whose ``.gitignore`` was given.

    git prints a rule from inside the work tree as a path relative to its root
    (``.gitignore``, ``sub/.gitignore``) and every rule from elsewhere as an absolute
    path: ``core.excludesFile`` (expanded), ``$XDG_CONFIG_HOME/git/ignore``.
    ``.git/info/exclude`` is relative but is not named ``.gitignore``. So the file must
    be named ``.gitignore``, and be relative, or absolute and resolve to under ``tree``.
    """
    path = Path(source)
    if path.name != ".gitignore":
        return False
    if not path.is_absolute():
        return True
    try:
        path.resolve().relative_to(Path(tree).resolve())
    except (OSError, ValueError):
        return False
    return True


def _contract_diff(target: Path, content: str) -> dict:
    """Gitignore-contract diff for the ``.gitignore`` text ``content`` of ``target``.

    The single source of truth for what "satisfies the session-file contract"
    means, shared by :func:`update_gitignore` (which reads it to decide what to
    write), the ``gitignore`` advisory probe (via :func:`gitignore_contract_drift`),
    and ``init_product``'s onboarding — so the nudge can never disagree with the fix.

    **What git would ignore, not which lines are present (#762).** Comparing
    literal lines fails both ways against a wholesale rule such as ``.prawduct/``:
    every session entry reads "missing" although all are ignored, and files that
    must be committed are ignored and go unnoticed. So the comparison asks git
    (:func:`_shared_ignore_matches`). Returns:

    * ``missing`` — session entries that SHOULD be ignored and are not: not a
      literal line, and not ignored by any shared rule.
    * ``incorrectly_ignored`` — managed/retired paths with a LITERAL line in the
      file. The fixer removes exactly these lines, and only these: a line is
      removed only when it names the path itself. This is ``MANAGED_FILES``'s role
      here: the 1.x files a literal line must not hide from a repo mid-migration.
    * ``ignored_by_rule`` — paths a v2 repo commits (:data:`V2_COMMITTED_PATHS`,
      plus the retired build plan) ignored by a rule the fixer will NOT touch
      (``{"path", "source", "line", "pattern"}``): a wholesale ``.prawduct/``,
      ``.claude/``, a glob, or a literal line for a file the fixer does not own.
      Those are the owner's own rules, so this is reported, never repaired. Git names
      only the LAST matching rule per path, so a path a literal line also hides can
      surface here one run later, after the literal is stripped. ``path`` is the
      entry as the constant spells it (a directory keeps its trailing ``/``).
    * ``basis`` — ``"git"``, or ``"literal"`` when git could not be asked at all.
      Then ``missing`` and ``incorrectly_ignored`` are the old literal comparison
      and ``ignored_by_rule`` is empty: a wholesale rule is invisible. That is the
      boundary, and callers say so rather than present it as a clean bill.

    ``missing`` and ``incorrectly_ignored`` are disjoint (session files vs.
    managed files), and ``update_gitignore``'s ``modified`` is exactly
    ``missing or incorrectly_ignored``: ``ignored_by_rule`` never makes it write.
    A literally present entry is never ``missing`` even if a later negation
    un-ignores it, so a repaired file stays repaired (the fixer would otherwise
    append the same line on every run).
    """
    existing_lines = set(content.splitlines())
    not_literal = [e for e in GITIGNORE_ENTRIES if e not in existing_lines]
    literal_managed = sorted(
        e for e in (*MANAGED_FILES, *RETIRED_GITIGNORE_ENTRIES) if e in existing_lines
    )
    must_commit = _committed_in_scope(target)
    probes = [_entry_probe_path(e) for e in not_literal]
    commit_probes = {path: _committed_probe_path(path) for path in must_commit}
    matches = _shared_ignore_matches(target, content, [*probes, *commit_probes.values()])
    if matches is None:
        return {
            "missing": not_literal,
            "incorrectly_ignored": literal_managed,
            "ignored_by_rule": [],
            "basis": "literal",
        }
    missing = [e for e in not_literal if _entry_probe_path(e) not in matches]
    removable = set(literal_managed)
    ignored_by_rule = [
        {
            "path": path,
            "source": matches[probe][0],
            "line": matches[probe][1],
            "pattern": matches[probe][2],
        }
        for path, probe in commit_probes.items()
        if probe in matches and matches[probe][2] not in removable
    ]
    return {
        "missing": missing,
        "incorrectly_ignored": literal_managed,
        "ignored_by_rule": ignored_by_rule,
        "basis": "git",
    }


def _read_gitignore(target: Path) -> str:
    """``target/.gitignore`` text; a missing or unreadable file reads as empty."""
    try:
        return (target / ".gitignore").read_text()
    except OSError:
        return ""


def gitignore_contract_drift(target: Path) -> dict:
    """Read-only: how ``target``'s ``.gitignore`` diverges from the contract.

    Reads ``target/.gitignore`` (a missing or unreadable file reads as empty, so
    every session entry then counts as ``missing``) and returns the
    :func:`_contract_diff` result. Never mutates and never raises on a missing
    file — the ``gitignore`` advisory probe calls this on every session start, so
    it must be cheap (one git subprocess) and side-effect-free.
    """
    return _contract_diff(target, _read_gitignore(target))


def gitignore_covers(target: Path, rel_path: str) -> bool:
    """True when ``target``'s ``.gitignore`` already ignores ``rel_path``.

    A literal line, or any shared rule git says matches. For writers that add one
    entry (the version marker) and must not append a line a broader rule already
    makes redundant. When git cannot be asked, only the literal line counts.
    """
    content = _read_gitignore(target)
    if rel_path in content.splitlines():
        return True
    matches = _shared_ignore_matches(target, content, [rel_path])
    return matches is not None and rel_path in matches


def _directory_rule(pattern: str) -> str | None:
    """The directory a wholesale rule excludes (``.prawduct/``, ``/.prawduct``,
    ``.prawduct/*``, ``.prawduct/**``), else ``None`` for any other shape."""
    base = pattern
    for suffix in ("/**", "/*", "/"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    base = base.lstrip("/")
    if not base or any(c in base for c in "*?[]\\!"):
        return None
    return base


def describe_ignored_by_rule(entries: list[dict]) -> list[str]:
    """One plain sentence per offending rule: what it hides, and the exact lines.

    The fixer never edits the owner's rule (#762), so this is the repair. For a wholesale
    directory rule the choice is delete it (the session entries prawduct manages already
    ignore what should not be committed) or replace it with ``dir/*`` plus one ``!``
    re-include for every top-level entry :data:`V2_COMMITTED_PATHS` holds under that
    directory: all of them, hidden today or not, so the narrowed rule does not hide a file a
    feature creates later (git will not re-include a file whose parent directory is
    excluded, hence ``!dir/artifacts/`` and not a file inside it). A bare ``dir/`` rule
    cannot be negated, which is why it is replaced, not appended to. A rule that excludes a
    committed directory itself can only be deleted. Any other rule keeps standing and takes
    ``!`` lines after it, one per path it hides; a directory takes two, ``!dir/`` for a
    rule that excludes the directory itself and ``!dir/**`` for its contents.
    """
    groups: dict[tuple[str, int, str], list[str]] = {}
    for e in entries:
        groups.setdefault((e["source"], e["line"], e["pattern"]), []).append(e["path"])
    out: list[str] = []
    for (source, line, pattern), paths in groups.items():
        many = len(paths) > 1
        sentence = (
            f"{', '.join(f'`{p}`' for p in paths)} {'are' if many else 'is'} ignored by "
            f"`{pattern}` ({source}:{line}), but prawduct needs {'them' if many else 'it'} "
            "committed. Prawduct will not edit your rule. Delete that line"
        )
        directory = _directory_rule(pattern)
        if directory and any(p.rstrip("/") == directory for p in paths):
            pass  # the rule IS a committed directory: `!` cannot re-include it, so only deleting works
        elif directory and all(p.startswith(directory + "/") for p in paths):
            reincludes: list[str] = []
            for c in V2_COMMITTED_PATHS:
                if not c.path.startswith(directory + "/"):
                    continue
                head, sep, _ = c.path[len(directory) + 1 :].partition("/")
                line_ = f"!{directory}/{head}{sep}"
                if line_ not in reincludes:
                    reincludes.append(line_)
            for p in paths:  # a retired path, or anything not in the constant
                head, sep, _ = p[len(directory) + 1 :].partition("/")
                line_ = f"!{directory}/{head}{sep}"
                if line_ not in reincludes:
                    reincludes.append(line_)
            sentence += ", or replace it with these lines: " + ", ".join(
                f"`{x}`" for x in [f"{directory}/*", *reincludes]
            )
        else:
            # A directory entry gets `!dir/` as well as `!dir/**`: a rule such as `artifacts/`
            # excludes the directory ITSELF, and git never re-includes a file whose parent
            # directory is excluded, so `!dir/**` alone leaves it hidden.
            lines = [
                x for p in paths
                for x in ([f"!{p}", f"!{p}**"] if p.endswith("/") else [f"!{p}"])
            ]
            sentence += ", or add these lines after it: " + ", ".join(f"`{x}`" for x in lines)
        out.append(sentence + ".")
    return out


def update_gitignore(target: Path, dry_run: bool = False) -> dict:
    """Add prawduct entries to .gitignore and remove incorrect ones.

    Managed files (MANAGED_FILES, the 1.x file-sync set) are un-ignored by literal line, and
    what a v2 repo commits (V2_COMMITTED_PATHS) is reported when a rule hides it.
    Session files (GITIGNORE_ENTRIES) should be gitignored.
    Returns dict with 'modified' bool, 'unignored' list of paths that were
    removed from .gitignore (caller should advise user to git-add these), and
    'missing' list of session entries that were added.

    Two more keys report what this function will NOT repair (#762):
    ``ignored_by_rule`` lists committed-by-contract files hidden by a rule of the owner's own
    (a wholesale ``.prawduct/``; see :func:`describe_ignored_by_rule` for the exact
    lines to offer), and ``basis`` is ``"git"`` or ``"literal"`` (git could not be
    asked, so a wholesale rule was invisible). A user's rule is never rewritten or
    deleted here: ``ignored_by_rule`` does not make ``modified`` true.

    ``dry_run=True`` computes the same answers and skips the write, so a
    caller can PREVIEW the reconcile. The whole point is that the preview and
    the repair share one body: a separate "what would change" implementation is
    free to drift from the fixer, and a preview that disagrees with the fix is
    worse than no preview.
    """
    gitignore = target / ".gitignore"

    content = gitignore.read_text() if gitignore.is_file() else ""

    modified = False
    unignored: list[str] = []

    # Shared contract diff (single source of truth with the advisory probe):
    # managed/retired entries wrongly ignored, and session entries still missing.
    # The sets are disjoint, so computing both up front (before the removal
    # mutates the file) yields the same result as the sequential passes below.
    diff = _contract_diff(target, content)
    incorrectly_ignored = set(diff["incorrectly_ignored"])
    missing = diff["missing"]

    # Remove lines that gitignore managed files (they should be committed) —
    # plus retired entries the framework used to write itself (tracked-by-
    # default build plans, gate-soundness ch.3).
    if incorrectly_ignored:
        lines = content.splitlines(keepends=True)
        filtered = [line for line in lines if line.rstrip("\n") not in incorrectly_ignored]
        content = "".join(filtered)
        unignored = sorted(incorrectly_ignored)
        modified = True

    # Add missing session file entries
    if missing:
        parts = []
        if content and not content.endswith("\n"):
            parts.append("\n")
        if content.strip():
            parts.append("\n")
        parts.append("# Prawduct session files\n")
        for entry in missing:
            parts.append(entry + "\n")
        content += "".join(parts)
        modified = True

    if modified and not dry_run:
        gitignore.write_text(content)

    return {
        "modified": modified,
        "unignored": unignored,
        "missing": list(missing),
        "ignored_by_rule": diff["ignored_by_rule"],
        "basis": diff["basis"],
    }
