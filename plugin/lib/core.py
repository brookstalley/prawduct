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

# Session files that should be gitignored in product repos
GITIGNORE_ENTRIES = [
    ".claude/settings.local.json",
    ".prawduct/.critic-active",
    ".prawduct/.critic-findings.json",
    ".prawduct/.critic-partials/",
    ".prawduct/.critic-partials-archive/",
    ".prawduct/.delegate-brief.md",
    ".prawduct/.governance-ledger.jsonl",
    ".prawduct/.handoff-notes.md",
    ".prawduct/.test-evidence.json",
    ".prawduct/.pr-reviews/",
    ".prawduct/.session-base-tree",
    ".prawduct/.session-git-baseline",
    ".prawduct/.session-handoff.md",
    ".prawduct/.session-reflected",
    ".prawduct/.session-start",
    ".prawduct/.subagent-briefing.md",
    ".prawduct/.gates-waived",
    ".prawduct/.advisories.json",
    ".prawduct/.work-model-index.json",
    ".prawduct/reflections.md",
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
    # `open` rather than `write_text(newline=…)`: the latter wants Python 3.10+,
    # and the hook runs under whatever `python3` a product's PATH resolves to —
    # 3.9.6 on a stock macOS. `open` has taken both keywords since forever.
    with tmp.open("w", encoding=encoding, newline=newline) as handle:
        handle.write(text)
    os.replace(tmp, path)


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
    an ``OSError`` from a restore is suppressed rather than masking it. Only
    ``OSError`` — anything else escaping a restore is a bug in this function,
    not a disk that filled, and swallowing it would hide it forever.
    """
    written: list[tuple[Path, str | None]] = []
    try:
        for path, text in writes:
            prior = None
            if path.exists():
                try:
                    prior = path.read_text(encoding="utf-8")
                except OSError:
                    prior = None
            atomic_write_text(path, text)
            written.append((path, prior))
    except Exception:
        for path, prior in reversed(written):
            try:
                if prior is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write_text(path, prior)
            except OSError:
                pass
        raise


# Optional project-state pointer naming the active build plan (relative to the
# `.prawduct/` dir). When unset, tooling uses the conventional default below, so
# repos that don't set it keep their existing behavior.
BUILD_PLAN_POINTER_KEY = "active_build_plan"
DEFAULT_BUILD_PLAN_REL = "artifacts/build-plan.md"


class BranchClaim(NamedTuple):
    """Which plan governs the checked-out branch, and what else claimed it.

    ``chosen`` is the plan; ``claimants`` is every live plan that declared this
    branch, ``chosen`` included, in path order. ``basis`` names the precedence
    step that decided it (see :func:`resolve_branch_claim`), so a surface can
    say *why* this plan and not the others.

    ``open_claimants`` is the subset still holding unticked chunks — carried
    rather than recomputed because the sentence a reader gets **must be derived
    from the state, not asserted about it**: the ``order`` basis is reached both
    when nothing has open work and when several plans do, and one sentence
    covering both tells half its readers the opposite of the truth. ``None``
    means *not computed* (the uncontested path never asks), which is different
    from an empty tuple and is why it is not one.

    This tuple exists because attribution is what a multi-claim branch is owed.
    Returning the winner alone would make governing by one of three plans look
    exactly like governing by the only one — which is the failure mode the
    branch declaration was supposed to remove, not introduce.
    """

    chosen: Path
    claimants: "list[Path]"
    branch: str
    basis: str
    open_claimants: "list[Path] | None" = None
    #: What ``active_build_plan`` resolved to when the tie-break consulted it,
    #: or ``None`` for unset — and also ``None`` on the paths that never asked
    #: (a sole claimant, or one claimant with chunks left). Carried for the same
    #: reason as ``open_claimants``: the sentence a reader gets must be derived
    #: from what the scalar actually says, and "names none of them" was asserted
    #: on a repo whose scalar named one.
    pointer: "Path | None" = None

    @property
    def contested(self) -> bool:
        """Whether more than one live plan claimed this branch."""
        return len(self.claimants) > 1


#: The three answers a column-0 scalar read can give. ``read_str_yaml_key``
#: collapses the last two, which is right for every key whose absence and whose
#: explicit ``null`` mean the same thing. Where they mean DIFFERENT things — a
#: control that is on unless a repo turns it off — the collapse is the bug, so
#: the distinction gets a reader rather than each such key re-scanning the file.
YAML_SCALAR_ABSENT = "absent"
YAML_SCALAR_NULL = "null"
YAML_SCALAR_VALUE = "value"


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
        line = raw.split("#", 1)[0].rstrip()
        if not line.startswith(needle):
            continue
        value = line.split(":", 1)[1].strip().strip("\"'")
        if not value or value.lower() in ("null", "~"):
            return YAML_SCALAR_NULL, None
        return YAML_SCALAR_VALUE, value
    return YAML_SCALAR_ABSENT, None


def read_str_yaml_key(state_path: Path, key: str) -> str | None:
    """Value of a top-level (column-0) ``key: value`` scalar, or None.

    Mirrors the column-0 idiom used by :func:`read_bool_yaml_key` and
    bin/prawduct-hook's ``_read_bool_yaml_key`` — no PyYAML dependency, fail-soft to None on a
    missing/unreadable file or absent key. Surrounding quotes and inline ``#``
    comments are stripped; an empty value, or the YAML null literal (``null`` /
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
        if not raw.split("#", 1)[0].rstrip().startswith(needle):
            continue
        inline = raw.split("#", 1)[0].rstrip().split(":", 1)[1].strip()
        if inline == "[]":
            return YAML_DECLARED, ()
        if inline:
            return YAML_UNPARSEABLE, ()
        body: list[str] = []
        for follow in lines[index + 1:]:
            stripped = follow.split("#", 1)[0].strip()
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
        value = line[2:].strip().strip("\"'")
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
        raw[:1] not in (" ", "\t") and raw.split("#", 1)[0].rstrip().startswith(f"{key}:")
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
    YAML list. Fail-soft to ``()`` on a missing file, an absent key, or an
    unparseable block — the empty answer is the pre-declaration behaviour, so a
    typo here can only fail toward running the suite's freshness check as it
    always did, never toward a false-fresh verdict.

    Entries are plain path prefixes against repo-relative paths, so a trailing
    slash matters and is the caller's to write: ``doc/`` must not match
    ``documentation/``. They are NOT restricted to ``.md`` — declaring a root
    couples every file under it, which is the fail-safe direction.
    """
    state = prawduct_dir / "project-state.yaml"
    try:
        text = state.read_text(encoding="utf-8")
    except OSError:
        return ()
    status, lines = read_yaml_block(text, SUITE_COUPLED_PREFIXES_KEY)
    if status != YAML_DECLARED:
        return ()
    out = []
    for line in lines:
        if not line.startswith("- "):
            continue
        value = line[2:].strip().strip("'\"")
        if value:
            out.append(value)
    return tuple(out)


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
#: Opt-in is the whole contract: :func:`read_bool_yaml_key` fails soft to False
#: on a missing file, an absent key, or a malformed line, so **False is the code
#: default for every member** and the template must say so too.
OPT_IN_FLAGS: tuple[str, ...] = (
    "coverage_required",
    "operator_verification_required",
)


def read_bool_yaml_key(path: Path, key: str) -> bool:
    """True if ``path`` has a top-level (column-0) ``key: true`` scalar.

    The boolean sibling of ``read_str_yaml_key``, sharing the same no-PyYAML
    column-0 idiom but with boolean semantics: the value is lowercased and
    compared to ``"true"`` (quotes are *not* stripped — a quoted ``"true"``
    reads as False). Fail-soft to False on a missing/unreadable file, an absent
    key, or a malformed/indented line — opt-in by design.

    Reads the repo's opt-in flags — ``coverage_required`` today. It once also
    read ``views_enabled``, which was retired along with derived views; the
    function is general and outlived its second caller. bin/prawduct-hook's
    ``_read_bool_yaml_key`` stays an inline mirror (import-light hot path),
    pinned by a parity test.
    """
    if not path.exists():
        return False
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # Same hole as `read_str_yaml_key`: undecodable is unreadable, and this
        # promises to fail soft on unreadable. Fixed in both, because the two
        # are documented as siblings sharing one idiom.
        return False
    needle = f"{key}:"
    for raw in content.splitlines():
        if raw[:1] in (" ", "\t"):
            continue
        line = raw.split("#", 1)[0].rstrip()
        if not line.startswith(needle):
            continue
        value = line.split(":", 1)[1].strip().lower()
        return value == "true"
    return False


def pointer_plan_path(prawduct_dir: Path) -> Path | None:
    """The ``active_build_plan:`` scalar as a path, or ``None`` when unset.

    The one place the scalar becomes a PATH, and that is now true by
    construction rather than by convention: the resolution path (the tie-break
    in :func:`resolve_branch_claim`, the fallback in
    :func:`resolve_build_plan_path`), the release sweep's archive guard
    (:func:`plan_backfill._active_plan_path`) and both operator notices in
    ``prawduct-hook`` route through here. They previously spelled the prefix rule
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


def resolve_branch_claim(prawduct_dir: Path) -> BranchClaim | None:
    """Which live plan governs the checked-out branch, or ``None`` for no claim.

    **Several live plans may claim one branch, and that is an ordinary
    arrangement — not an error.** A `release/2-0` branch can carry a telemetry
    plan and a documentation plan; one consumer repo carries three plans on a
    single fix branch. An earlier reading treated the second claimant as an
    authority failure and refused to resolve at all, which blocked the very
    workflow the declaration was added to serve. Refusing is the right posture
    when a control cannot know the answer; it is the wrong posture when the
    answer is "all of them, and here is the one being worked."

    Precedence over the claimants, and every step is stated because the choice
    is reported (``basis``):

    1. **A sole claimant wins outright** — no further test. Deliberately ahead
       of step 2: the unfinished-chunk signal goes false the moment the last box
       is ticked, which happens *during* the closing PR, and a plan that stopped
       governing between its final review and its merge would take the gates
       with it.
    2. **The one claimant with unfinished chunks** — of several plans on a
       branch, the one still holding open work is the one governance is about.
    3. **The ``active_build_plan`` pointer**, when it names a plan **still in
       contention** — that is, one of the claimants step 2 left standing, not
       merely any claimant. This is what the scalar is *for* once branches carry
       their own plans: the operator's explicit choice, used to break a tie
       within a branch rather than to name one plan for a whole product. The
       narrowing is deliberate and is the case to keep in mind: with two plans
       still open and the scalar naming a third whose boxes are all ticked, the
       scalar is stale evidence and the open ones are live evidence, so the
       pointer does not resurrect a finished plan. The reader is told that is
       what happened — see :func:`describe_branch_claim`, which derives the
       pointer's clause rather than asserting one.
    4. **Path order**, as the last resort. Arbitrary, so it is never silent —
       ``basis`` says ``order`` and the caller names the plans it passed over.

    ``None`` — and therefore the pointer — on a detached HEAD, outside a work
    tree, and when no live plan claims this branch.

    **The plan scan runs before the branch probe deliberately.** A repo where no
    plan has opted in gets its answer from a walk it was already paying for on
    every session boundary, and never spawns git; ordering it the other way
    would add a subprocess to every resolve in every repo to answer a question
    that is almost always "nobody claims anything."
    """
    from . import plan_index  # noqa: PLC0415 — lazy: core's top level stays stdlib-only

    artifacts_dir = prawduct_dir / "artifacts"
    claims = plan_index.branch_claiming_plans(artifacts_dir)
    if not claims:
        return None

    from . import gitstate  # noqa: PLC0415 — same reason; also a git subprocess

    branch = gitstate.current_branch(prawduct_dir.parent)
    if not branch:
        return None
    matched = sorted(path for path, claimed in claims if claimed == branch)
    if not matched:
        return None
    if len(matched) == 1:
        return BranchClaim(matched[0], matched, branch, "sole")  # open set not asked

    # **Lazy is load-bearing here, not an optimization.** `buildplan_refs`
    # imports THIS module at module scope, so hoisting this to the top would be
    # an import cycle at plugin load — unlike the `plan_index` import in that
    # module, which was hoisted on measured cost precisely because it could be.
    # A maintainer applying that same reasoning here breaks the install, so the
    # reason is the constraint and not the cost. (The cost is real too: only a
    # contested branch pays it, and the common shapes are answered above.)
    #
    # It also reaches a private, which is the honest cost of putting the choice
    # here. Considered and not taken: moving the Status-roster predicate down
    # into `plan_index`, which would keep core's dependencies pointing downward.
    # That is the better shape and it is a refactor of the parser's home, not a
    # line — filed rather than smuggled into a fix for something else.
    from . import buildplan_refs  # noqa: PLC0415 — lazy is REQUIRED: buildplan_refs imports core

    unfinished = [p for p in matched if buildplan_refs._has_unfinished_chunk(p)]
    if len(unfinished) == 1:
        return BranchClaim(unfinished[0], matched, branch, "unfinished", unfinished)
    # An empty `unfinished` means every claimant reads finished, which is the
    # post-tick window rather than an absence of candidates — fall back to the
    # full claimant set rather than to the pointer, so a branch whose plans are
    # all ticked still resolves among ITS plans.
    pool = unfinished or matched
    pointed = pointer_plan_path(prawduct_dir)
    if pointed is not None and pointed in pool:
        return BranchClaim(pointed, matched, branch, "pointer", unfinished, pointed)
    return BranchClaim(pool[0], matched, branch, "order", unfinished, pointed)


def describe_branch_claim(claim: BranchClaim, artifacts_dir: Path) -> str:
    """One sentence naming the governing plan and what else claimed the branch.

    **One caller today: the session briefing.** That is deliberate, not an
    accident waiting to be spread — the gates already name the plan they graded
    (``record-lint``'s ``plan_graded``), so what a gate is missing is not the
    choice but the context for it, which is session-scoped and arrives before
    any gate runs. It lives here rather than inline in the briefing so a second
    caller inherits the wording instead of paraphrasing it; the wording is not
    yet shared, and this docstring does not get to claim it is.

    Empty for an uncontested claim — there is nothing to disambiguate, and a
    sentence printed on every ordinary session is a sentence nobody reads by the
    time it matters.
    """
    from . import plan_index  # noqa: PLC0415 — lazy: core's top level stays stdlib-only

    if not claim.contested:
        return ""
    others = [
        plan_index.display_path(p, artifacts_dir)
        for p in claim.claimants
        if p != claim.chosen
    ]
    if claim.basis == "unfinished":
        why = "it is the only one with chunks left"
    elif claim.basis == "pointer":
        why = "`active_build_plan` names it"
    else:
        # The `order` case is arbitrary, so it says so AND names the remedy. Its
        # first clause is DERIVED, because this basis is reached from two states
        # that want opposite sentences: several plans still holding open work
        # (the shipped headline case — a release branch with two live
        # workstreams and no pointer set), and none of them holding any (the
        # post-tick window). Asserting either one tells the other's reader the
        # opposite of the truth about their own repo.
        open_count = len(claim.open_claimants or ())
        distinguish = (
            f"{open_count} of them still hold open work"
            if open_count > 1
            else "none of them has chunks left"
        )
        # The pointer's clause is derived for the same reason the count is, and
        # it is the reason this sentence needed fixing twice: "names none of
        # them" was asserted, and it is false on the repo whose scalar names a
        # claimant that step 2 had already ruled out for being finished.
        if claim.pointer is None:
            scalar = "`active_build_plan` is unset"
        elif claim.pointer in claim.claimants:
            scalar = (
                f"`active_build_plan` names "
                f"{plan_index.display_path(claim.pointer, artifacts_dir)}, which is "
                "not among them — its chunks are all ticked, so the plans still "
                "holding work outrank it"
            )
        else:
            scalar = "`active_build_plan` names no plan on this branch"
        why = (
            f"{distinguish} and {scalar}, so this is path order rather than a "
            "judgement — point the scalar at the plan you are building to decide it"
        )
    return (
        f"{len(claim.claimants)} live plans declare `branch: {claim.branch}` — "
        f"governing by {plan_index.display_path(claim.chosen, artifacts_dir)} "
        f"because {why}. Also claiming: {', '.join(others)}."
    )


def resolve_build_plan_path(prawduct_dir: Path) -> Path:
    """Resolve the active build-plan path. Branch-scoped first, pointer second.

    Precedence:

    1. **The live plan that claims this branch.** A build plan may declare
       ``branch: <name>`` in its frontmatter; a non-archived plan under
       ``artifacts/`` whose declaration matches the checked-out branch governs
       it. Which branch a plan governs is a fact about the plan, so the plan is
       where it belongs — held in a product-level scalar instead, two concurrent
       branches conflict on one line every time, and after the merge one of the
       two plans is invisible to every pointer-resolved surface. Several plans
       may claim one branch; :func:`resolve_branch_claim` states which wins and
       why, and callers that report the active plan report that too.
    2. **The ``active_build_plan:`` pointer** in ``project-state.yaml`` (a path
       relative to the ``.prawduct/`` dir), letting a project name its plan by
       scope (``artifacts/v1.6.0-foo-plan.md``).
    3. **The conventional** ``artifacts/build-plan.md``.

    A repo whose plans declare no ``branch:`` therefore resolves exactly as it
    did before step 1 existed — opting in is per plan, and nothing migrates.

    The returned path may not exist; callers treat a missing plan as "no active
    build plan."
    """
    claim = resolve_branch_claim(prawduct_dir)
    if claim is not None:
        return claim.chosen
    return pointer_plan_path(prawduct_dir) or prawduct_dir / DEFAULT_BUILD_PLAN_REL


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


def _contract_diff(existing_lines: set[str]) -> dict:
    """Pure gitignore-contract diff for a set of existing ``.gitignore`` lines.

    The single source of truth for what "satisfies the session-file contract"
    means, shared by :func:`update_gitignore` (which reads it to decide what to
    write) and the ``gitignore`` advisory probe (which reads
    :func:`gitignore_contract_drift` to decide whether to nudge) — so the nudge
    can never disagree with the fix. Returns
    ``{"missing", "incorrectly_ignored"}``: session entries that SHOULD be ignored
    but aren't, and managed/retired entries that ARE ignored but shouldn't be.
    Both empty ⇔ :func:`update_gitignore` makes no change (its ``modified``
    condition is exactly ``missing or incorrectly_ignored``). The two entry sets
    are disjoint (session files to ignore vs. managed files to commit), so the
    order in which the fixer removes then adds never affects either set.
    """
    missing = [e for e in GITIGNORE_ENTRIES if e not in existing_lines]
    incorrectly_ignored = sorted(
        e for e in (*MANAGED_FILES, *RETIRED_GITIGNORE_ENTRIES) if e in existing_lines
    )
    return {"missing": missing, "incorrectly_ignored": incorrectly_ignored}


def gitignore_contract_drift(target: Path) -> dict:
    """Read-only: how ``target``'s ``.gitignore`` diverges from the contract.

    Reads ``target/.gitignore`` (a missing or unreadable file reads as empty, so
    every session entry then counts as ``missing``) and returns the
    :func:`_contract_diff` result. Never mutates and never raises on a missing
    file — the ``gitignore`` advisory probe calls this on every session start, so
    it must be cheap and side-effect-free.
    """
    gitignore = target / ".gitignore"
    try:
        existing_lines = set(gitignore.read_text().splitlines())
    except OSError:
        existing_lines = set()
    return _contract_diff(existing_lines)


def update_gitignore(target: Path, dry_run: bool = False) -> dict:
    """Add prawduct entries to .gitignore and remove incorrect ones.

    Managed files (MANAGED_FILES) should be committed, not gitignored.
    Session files (GITIGNORE_ENTRIES) should be gitignored.
    Returns dict with 'modified' bool, 'unignored' list of paths that were
    removed from .gitignore (caller should advise user to git-add these), and
    'missing' list of session entries that were added.

    ``dry_run=True`` computes the same three answers and skips the write, so a
    caller can PREVIEW the reconcile. The whole point is that the preview and
    the repair share one body: a separate "what would change" implementation is
    free to drift from the fixer, and a preview that disagrees with the fix is
    worse than no preview.
    """
    gitignore = target / ".gitignore"

    if gitignore.is_file():
        content = gitignore.read_text()
        existing_lines = set(content.splitlines())
    else:
        content = ""
        existing_lines = set()

    modified = False
    unignored: list[str] = []

    # Shared contract diff (single source of truth with the advisory probe):
    # managed/retired entries wrongly ignored, and session entries still missing.
    # The sets are disjoint, so computing both up front (before the removal
    # mutates the file) yields the same result as the sequential passes below.
    diff = _contract_diff(existing_lines)
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

    return {"modified": modified, "unignored": unignored, "missing": list(missing)}
