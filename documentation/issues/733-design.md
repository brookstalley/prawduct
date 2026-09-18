# Issue #733 — Governance: Let a Product Declare Its Consumer Release Digest: Design

`status: draft · stage: design · area: governance · added: 2026-09-18 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/733`

Builds on `documentation/issues/733-requirements.md` (DIG1 through DIG8, Decisions 1-5 — the
`sentinel-heading` / `open-heading-pattern` keying rule, the `project-state.yaml` declaration
shape, and the "coverage/headline logic reused verbatim" constraint). This document places the
declaration reader and the two locator functions in `plugin/lib/release_readiness.py`, resolves
one wiring question the requirements doc left open (what "the release's own tree" means for a
check that runs *before* the tag exists), and specifies file-by-file changes an implementation
chunk can follow directly.

Related: `plugin/lib/release_verification.py`'s `_read_declaration`/`VersionFile` (the
`release_version_files:` shape precedent DIG1/DIG2 name explicitly) and its module docstring's
"read from the tag's own tree" rule; `plugin/lib/core.py`'s `read_yaml_block` (the shared
column-0 block reader every declaration in this codebase now goes through).

## Summary of what ships

1. **DIG1** — a new `ConsumerDigest` NamedTuple (`path`, `keying`, `heading`, `pattern`) and a new
   reader, `_read_consumer_digest_declaration(project_dir)`, parsing a single mapping (not a list)
   under `consumer_digest:` in `.prawduct/project-state.yaml` via `core.read_yaml_block`. Returns
   `(digest_or_none, invalid_reason_or_none)` — three states, matching DIG1's "absent / invalid /
   valid" distinction exactly.
2. **DIG3, DIG4** — two new locator functions, `_locate_sentinel_heading` and
   `_locate_open_heading_pattern`, both returning the same `(heading, body)` shape
   `_open_digest_section` already returns. A small shared helper, `_section_span`, is extracted
   from `_open_digest_section`'s tail so all three locators compute "everything to the next `## `
   heading or EOF" once.
3. **DIG5, DIG6, DIG8** — `_digest_advisories` gains a second branch: `_ships_the_plugin_tree` true
   keeps today's exact behavior (prawduct's own hardcoded path and locator, byte-identical output,
   DIG6); false now tries a `consumer_digest:` declaration before returning nothing, instead of
   returning nothing unconditionally (DIG8 for the no-declaration case, DIG1/DIG7 for the
   invalid-declaration case).
4. **A signature widening on `_read_digest`, `_headline_advisory`, `_coverage_advisory`** — each
   gains one parameter (`rel_path: str`) replacing their internal use of the module constant
   `_DIGEST_REL_PATH`. See Decision 2 below: without this, every message a declared product's
   checks print would misname the file, which is the same false-reporting shape DIG7 exists to
   rule out, moved from "which section" to "which file."
5. **`plugin/templates/project-state.yaml`** — a new documented `# CONSUMER DIGEST (opt-in)`
   block, placed immediately after `# RELEASE VERSION FILES`, following that section's own
   comment style (what it buys, what declaring changes, the YAML shape, both keying examples).

Nothing here touches `_digest_mentions`, `_section_headline`, `_ships_the_plugin_tree`,
`_open_digest_section`'s matching rule, or the call site in `check_releasability`
(`release_readiness.py:867-875`) — that call site already passes `project_dir` and `pending` and
needs no change; everything new is internal to `_digest_advisories`.

## Decisions resolved

### Decision 1 — what "the release's own tree" means when there is no tree yet

DIG2 says the declaration is read from "the release's own tree — `<tag-or-candidate-ref>:
.prawduct/project-state.yaml`" and cites `release_verification.py`'s tag-based read as the rule
being followed. That module's rule is unambiguous for its own caller: `check_released` runs
*after* the tag is pushed, so `<tag>:path` is a real `git show`. `_digest_advisories` has a
different caller. `check_releasability` is Phase 0 — it runs **before** the cut, specifically so a
maintainer can fix a missing headline or an uncovered scope while the section is still being
written (`_headline_advisory`'s own docstring: "Phase 0 runs before the step that writes the
headline"). There is no tag to `git show` yet; the tree being judged is whatever `develop` (or
whatever branch Phase 0 runs on) currently holds.

That is what "candidate ref" names in DIG2's own phrasing, and it resolves to: **read directly from
`project_dir`, exactly as `_read_digest` and `_ships_the_plugin_tree` already do today** — no `git
show`, no tag resolution, no new subprocess. This is not a departure from DIG2; it is DIG2 applied
to a caller that has no tag, the same way `release_verification.py` applies it to a caller that
does. The `path` field in the declaration is deliberately still a plain repo-relative path (not a
ref-qualified one) so the same `ConsumerDigest` shape would also serve a future tag-based consumer
without changing its fields — but no such consumer exists in this codebase today, and building one
is out of scope (the requirements doc's own Scope-out: "this item is requirements[-and-design]
only," and #733's acceptance criteria are all about `check_releasability`).

**Consequence for `_read_consumer_digest_declaration`:** it takes `project_dir: Path`, reads
`project_dir / ".prawduct" / "project-state.yaml"`, and treats an unreadable or absent file as "no
declaration" (`(None, None)`) — the same fail-soft precedent `risk.read_declared_surfaces` and
`suite_coupled_prefixes` already set for this exact file: an unreadable state file cannot be
distinguished from a product that never wrote one, and both must fall through to "undeclared,"
never to "invalid."

### Decision 2 — `_headline_advisory` and `_coverage_advisory` gain a `rel_path` parameter

DIG5 says these two are "called unchanged (same function signatures, same `(heading, body)`
input)." Read literally, that forbids adding a parameter. But both functions' *messages* — not
their judging logic — embed the module constant `_DIGEST_REL_PATH` directly:

```python
f"the open {_DIGEST_REL_PATH} section ({heading}) has no headline — ..."
f"could not find release-pending scope={scope!r} in the open {_DIGEST_REL_PATH} section ..."
```

A declared product's file is not `plugin/CHANGELOG.md`. Leaving these two f-strings as-is would
make every warning a generalized declaration produces name the wrong file — a maintainer reading
"the open `plugin/CHANGELOG.md` section has no headline" while editing `CHANGELOG.md` would look in
the wrong place, or conclude the check is broken and ignore it. That is the same category of defect
DIG7 rules out for section-*finding* (a false all-clear), moved one field over to file-*naming*: an
advisory that reliably points somewhere wrong is worse than the "no advisory" state DIG8 already
allows for an undeclared product, because it looks like it is doing its job.

**Resolution:** widen both signatures to `_headline_advisory(heading, body, rel_path)` and
`_coverage_advisory(heading, body, pending, rel_path)`, replacing every in-message
`_DIGEST_REL_PATH` reference with the parameter. This is a parameterization, not a fork — there
remains exactly **one** implementation of each function, called from exactly one place
(`_digest_advisories`), with both the prawduct-hardcoded caller and the declared caller passing
their own path. DIG5's actual concern — verified against its own docstring reasoning ("reuse the
already-correct logic, change only what genuinely varies") — is that the *judging* logic
(`_digest_mentions`, `_section_headline`, the headline-empty/still-seeded tests) stays untouched
and un-duplicated. It does: this change touches only the literal path substituted into already-
existing message templates. `_read_digest`'s own error message (`f"cannot read {_DIGEST_REL_PATH}:
{exc}"`) has the identical problem and gets the identical fix — `_read_digest(project_dir,
rel_path)`.

### Decision 3 — an invalid `pattern` regex is an invalid declaration, not a crash or a silent skip

Neither the requirements doc nor `release_version_files:`'s precedent addresses what happens when
an `open-heading-pattern` declaration's `pattern` field does not compile — DIG7 places pattern
*correctness* on the operator ("does this pattern match the intended headings") but says nothing
about pattern *validity* (does it compile at all). Left unhandled, `re.compile` raises `re.error`
inside `_locate_open_heading_pattern`, which would propagate out of `_digest_advisories` and crash
`check_releasability` — turning a typo in one YAML field into a Phase 0 gate that cannot run at
all, for every scope, not just the digest questions. That is strictly worse than DIG1's own
"invalid, reported" rule for the declaration's structural fields.

**Resolution:** `_read_consumer_digest_declaration` compiles the pattern once, at read time, inside
the same validation pass that checks `keying` and the `heading`/`pattern` exclusivity (DIG1/DIG7).
A `re.error` there is reported exactly like every other invalid-declaration reason — a WARNING
naming the bad pattern and the compiler's own message, `digest, invalid_reason = (None, "...")`.
`_locate_open_heading_pattern` itself never sees an uncompilable pattern, because a declaration
that failed to compile never reaches it (mirrors `check_version_files`'s own split: `_read_version`
never receives a `spec` whose `fmt` it cannot read — the invalid case is filtered before the
locator/reader runs, not inside it).

## Section 1 — `_read_consumer_digest_declaration` (DIG1, DIG7)

New constants, placed beside the existing digest constants (`release_readiness.py:40-78`):

```python
#: The declared-digest key, project-state.yaml. A single mapping, not a list —
#: contrast `release_version_files:`, which is a list because a product can
#: name several files; a product has exactly one consumer digest.
_CONSUMER_DIGEST_KEY = "consumer_digest"

#: The two keying strategies DIG1/Decision 1 (requirements) name. No third
#: value is accepted — see that Decision for why plain positional-topmost is
#: deliberately not offered as a declarable strategy.
_SENTINEL_HEADING = "sentinel-heading"
_OPEN_HEADING_PATTERN = "open-heading-pattern"
```

New import, added to the existing `from . import ...` block:

```python
from .core import YAML_ABSENT, YAML_UNPARSEABLE, read_yaml_block
```

New type and reader, placed immediately before `_digest_advisories` (after `_coverage_advisory`,
`release_readiness.py:620`):

```python
class ConsumerDigest(NamedTuple):
    """A product's declared consumer-release digest — DIG1's shape.

    ``keying`` selects which of ``heading``/``pattern`` is meaningful; the
    other is always empty on a value this reader returns, because
    :func:`_read_consumer_digest_declaration` refuses (DIG1/DIG7) rather than
    silently ignoring a conflicting pair.
    """

    path: str
    keying: str
    heading: str = ""
    pattern: str = ""


def _read_consumer_digest_declaration(
    project_dir: Path,
) -> tuple[ConsumerDigest | None, str | None]:
    """``(digest, invalid_reason)`` for ``consumer_digest:`` in this repo's
    ``.prawduct/project-state.yaml`` — Decision 1's "candidate ref" read.

    Three outcomes, and DIG1 requires all three distinguished:
    ``(None, None)`` — no declaration (absent key, or a state file this
    process cannot read — the same fail-soft precedent
    :func:`risk.read_declared_surfaces` and :func:`core.suite_coupled_prefixes`
    already set for this file: an unreadable state file cannot be told apart
    from one that never declared, so both read as "undeclared").
    ``(None, reason)`` — declared, but invalid: both required fields absent, an
    unsupported ``keying``, ``heading``/``pattern`` not matching the declared
    ``keying``, or (Decision 3) a ``pattern`` that does not compile. Never
    silently treated as "undeclared" — DIG1's own wording.
    ``(digest, None)`` — declared and valid.
    """
    try:
        text = (project_dir / ".prawduct" / "project-state.yaml").read_text(encoding="utf-8")
    except _UNREADABLE:
        return None, None
    status, body = read_yaml_block(text, _CONSUMER_DIGEST_KEY)
    if status == YAML_ABSENT:
        return None, None
    if status == YAML_UNPARSEABLE:
        return None, f"{_CONSUMER_DIGEST_KEY}: is declared in a shape prawduct cannot parse"

    fields: dict[str, str] = {}
    for line in body:
        if ":" not in line:
            return None, f"{_CONSUMER_DIGEST_KEY}: line {line!r} is not a `field: value` pair"
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("\"'")

    path, keying = fields.get("path", ""), fields.get("keying", "")
    heading, pattern = fields.get("heading", ""), fields.get("pattern", "")
    if not path or keying not in (_SENTINEL_HEADING, _OPEN_HEADING_PATTERN):
        return None, (
            f"{_CONSUMER_DIGEST_KEY}: needs `path` and `keying` "
            f"({_SENTINEL_HEADING!r} or {_OPEN_HEADING_PATTERN!r}) — "
            f"got path={path!r} keying={keying!r}"
        )
    wants_heading = keying == _SENTINEL_HEADING
    if wants_heading and (not heading or pattern):
        return None, (
            f"{_CONSUMER_DIGEST_KEY}: keying: {_SENTINEL_HEADING} needs `heading` "
            "and no `pattern`"
        )
    if not wants_heading and (not pattern or heading):
        return None, (
            f"{_CONSUMER_DIGEST_KEY}: keying: {_OPEN_HEADING_PATTERN} needs `pattern` "
            "and no `heading`"
        )
    if not wants_heading:
        try:
            re.compile(pattern)
        except re.error as exc:
            return None, f"{_CONSUMER_DIGEST_KEY}: pattern {pattern!r} does not compile: {exc}"
    return ConsumerDigest(path, keying, heading, pattern), None
```

`NamedTuple` needs adding to the module's `typing` import (currently none — add
`from typing import NamedTuple`).

## Section 2 — the two locators, and `_section_span` (DIG3, DIG4)

Extracted from `_open_digest_section`'s existing tail (`release_readiness.py:470-480`) so all three
locators share one "to the next heading or EOF" computation — the same "don't reinvent the
containment guard" posture Decision 4 (requirements) names, applied to the span computation instead
of to `_digest_mentions`/`_section_headline`:

```python
def _section_span(lines: list[str], start: int) -> tuple[str, list[str]]:
    """``(heading, body)`` for the `## ` section beginning at ``lines[start]``.

    Shared by :func:`_open_digest_section` (topmost, unconditionally) and the
    two declared locators below (topmost matching a keying rule) — all three
    answer the same question once a start line is fixed.
    """
    for i in range(start + 1, len(lines)):
        if _DIGEST_SECTION_RE.match(lines[i]):
            return lines[start].strip(), lines[start + 1 : i]
    return lines[start].strip(), lines[start + 1 :]


def _heading_text(line: str) -> str:
    """A `## `-matched line's text, marker and surrounding whitespace stripped."""
    return line.strip()[2:].strip()


def _locate_sentinel_heading(lines: list[str], heading: str) -> tuple[str, list[str]] | None:
    """DIG3: the first `## ` heading whose stripped text equals ``heading``.

    Case-insensitive, exact match. Self-verifying by construction (Decision 1,
    requirements): the sentinel text is a fixed literal, disjoint from any
    version-number heading, so there is no position for a stale section to
    hide behind — the sentinel exists, or it does not.
    """
    target = heading.strip().lower()
    for i, line in enumerate(lines):
        if _DIGEST_SECTION_RE.match(line) and _heading_text(line).lower() == target:
            return _section_span(lines, i)
    return None


def _locate_open_heading_pattern(lines: list[str], pattern: str) -> tuple[str, list[str]] | None:
    """DIG4: the topmost `## ` heading whose text matches ``pattern``.

    ``pattern`` was already compiled once by
    :func:`_read_consumer_digest_declaration` (Decision 3) — a declaration
    that failed to compile never reaches this function, so no second
    ``re.error`` guard is needed here.
    """
    compiled = re.compile(pattern)
    for i, line in enumerate(lines):
        if _DIGEST_SECTION_RE.match(line) and compiled.search(_heading_text(line)):
            return _section_span(lines, i)
    return None
```

`_open_digest_section` (`:455-480`) is refactored to call `_section_span` after finding its own
`start` (unconditional topmost), rather than repeating the loop — behavior-preserving, pinned by
the existing suite (`tests/test_release_readiness.py`) passing unmodified; no new test is owed for
this extraction alone.

## Section 3 — `_digest_advisories` wiring (DIG5, DIG6, DIG7, DIG8)

`release_readiness.py:441-452` (`_read_digest`), `:542-579` (`_headline_advisory`), `:582-620`
(`_coverage_advisory`) each gain the `rel_path` parameter from Decision 2 — a mechanical
substitution of every `_DIGEST_REL_PATH` reference inside each function body for the new parameter;
no other line in any of the three changes.

`_digest_advisories` itself (`:623-674`):

```python
def _digest_advisories(
    project_dir: Path, pending: list[str]
) -> tuple[list[str], str | None, list[str]]:
    """Everything the consumer digest can be asked at Phase 0, from one read.

    [... existing docstring's first two paragraphs, unchanged ...]

    Returns ``(warnings, note, emissions)`` — all three empty-or-``None`` in a
    repo that ships neither prawduct's own tree nor a `consumer_digest:`
    declaration (DIG8), where neither question has a subject at all.

    **DIG1/DIG7.** A `consumer_digest:` declaration this reader cannot make
    sense of is reported as a WARNING naming the reason, never silently
    treated as absent — the same "advice fails soft is not advice fails
    silent" rule the rest of this function already applies to an unreadable or
    sectionless digest.
    """
    if _ships_the_plugin_tree(project_dir):
        rel_path = _DIGEST_REL_PATH
        digest = None  # unchanged path (DIG6): the hardcoded locator below
    else:
        digest, invalid_reason = _read_consumer_digest_declaration(project_dir)
        if invalid_reason is not None:
            return [f"{invalid_reason} — the consumer digest checks did not run"], None, []
        if digest is None:
            return [], None, []  # DIG8: undeclared, unchanged from today
        rel_path = digest.path

    lines, reason = _read_digest(project_dir, rel_path)
    if reason is None:
        if digest is None:
            section = _open_digest_section(lines)
        elif digest.keying == _SENTINEL_HEADING:
            section = _locate_sentinel_heading(lines, digest.heading)
        else:
            section = _locate_open_heading_pattern(lines, digest.pattern)
    else:
        section = None
    if section is None:
        reason = reason or f"{rel_path} has no matching `## ` section to read"
        return [], (
            f"digest coverage not checked: {reason}. No release-pending scope "
            f"was tested for a consumer-facing note, so one shipping with "
            f"nothing written about it would not be reported here — and the "
            f"headline every upgrading repo is shown went unread with it."
        ), []

    heading, body = section
    headline_warnings, headline_emission = _headline_advisory(heading, body, rel_path)
    coverage_warnings, coverage_emission = _coverage_advisory(heading, body, pending, rel_path)
    return (
        headline_warnings + coverage_warnings,
        None,
        [headline_emission, coverage_emission],
    )
```

`digest is None` inside the `rel_path`-already-resolved block is the DIG6 signal for "use the
unconditional topmost locator" — it is only ever `None` there on the `_ships_the_plugin_tree`
branch, since the declared branch already returned on every path that would leave `digest` unset.
This keeps `_open_digest_section`'s call site and behavior for prawduct's own tree completely
unchanged, satisfying DIG6's "verified by the existing test suite... passing unmodified" literally:
no existing fixture (all of which write `plugin/VERSION`, per `tests/test_release_readiness.py`'s
`_make_project`) takes the new branch at all.

The docstring's existing final paragraph — "Why both questions stay prawduct-only, rather than
taking a declared path the way the version files do" (`:641-652`) — is the one prose block this
item's whole job was to answer (per the 2026-09-03 progress comment on the issue) and is replaced
with the paragraph shown above; nothing else in the module's prose changes.

## Section 4 — `plugin/templates/project-state.yaml`

New block inserted after the existing `# RELEASE VERSION FILES` section
(`plugin/templates/project-state.yaml:312-355`), before `# COVERAGE EVIDENCE`, matching that
section's comment style exactly (what it buys, what declaring changes, the shape, both strategies):

```yaml
# =============================================================================
# CONSUMER DIGEST (opt-in)
# =============================================================================
# Lets `prawduct-hook check-releasability` ask your own consumer-facing
# changelog the same two questions it already asks prawduct's: does the
# section for the release being prepared carry a real headline, and does it
# name every scope shipping in this release. Both are advisory (WARNING,
# never a refusal) — see #733 for why.
#
# **Declaring is what gives you a subject.** Leave it unset and neither check
# runs against your repo at all — there is nothing here to guess at, unlike
# `release_version_files:`, because "the section this release is being
# written into" is an editorial convention, not a property of changelogs in
# general (see the requirements doc linked in #733 for the reasoning).
#
# `keying` picks how the OPEN section is found — the section the release
# currently being prepared is being written into:
#   sentinel-heading      — a fixed heading text that is never renamed
#                            (Keep a Changelog's `## [Unreleased]`); the
#                            open section is whatever sits under the first
#                            heading matching it. Self-verifying: the
#                            sentinel can never coincide with a shipped
#                            version heading.
#   open-heading-pattern  — a regex that only an unshipped heading
#                            satisfies (prawduct's own convention,
#                            generalized: `-dev\.\d+$`); the open section is
#                            the topmost heading matching it. The pattern's
#                            correctness — that it matches only what you mean
#                            it to — is yours to get right, the same trust
#                            boundary `release_version_files:`'s `key` path
#                            already asks of you.
#
# Exactly one of `heading` / `pattern` is required, matching `keying`; both
# set, or neither, is refused rather than guessed.
#
# consumer_digest:
#   path: CHANGELOG.md
#   keying: sentinel-heading
#   heading: "Unreleased"

# consumer_digest:
#   path: CHANGELOG.md
#   keying: open-heading-pattern
#   pattern: '-dev\.\d+$'
```

Two commented examples (one per strategy) rather than one with both fields shown together, because
showing both `heading:` and `pattern:` set at once in a template a product copies from is exactly
the conflicting-declaration shape DIG1 refuses — the template must not model the invalid case.

## Files touched

| File | Change |
|---|---|
| `plugin/lib/release_readiness.py` | `ConsumerDigest`, `_CONSUMER_DIGEST_KEY`, `_SENTINEL_HEADING`, `_OPEN_HEADING_PATTERN`, `_read_consumer_digest_declaration` (DIG1, DIG7); `_section_span`, `_heading_text`, `_locate_sentinel_heading`, `_locate_open_heading_pattern` (DIG3, DIG4); `_open_digest_section` refactored onto `_section_span` (behavior-preserving); `_read_digest`, `_headline_advisory`, `_coverage_advisory` gain `rel_path` (Decision 2); `_digest_advisories` rewired (DIG5, DIG6, DIG7, DIG8) and its docstring's stale final paragraph replaced; new `from typing import NamedTuple` and `from .core import YAML_ABSENT, YAML_UNPARSEABLE, read_yaml_block` imports |
| `plugin/templates/project-state.yaml` | New `# CONSUMER DIGEST (opt-in)` block after `# RELEASE VERSION FILES` |
| `tests/test_release_readiness.py` | See test plan below |

Nothing in `plugin/lib/release_verification.py` changes — Decision 1 places this item's whole
wiring inside `check_releasability`'s Phase 0 caller; no post-cut consumer of `consumer_digest:`
exists or is added here.

## Test plan

Following `TestDigestCoverageIsAdvisory`'s own style (`tests/test_release_readiness.py:1053-1168`)
— fixtures, never this repo's live digest, and an explicit control/treatment pair wherever the
claim is about an *effect* rather than a single verdict. New fixtures for the declared path must
**not** write `plugin/VERSION` (that makes a project prawduct-shaped and always takes the DIG6
branch, per `_make_project`'s own comment at `tests/test_release_readiness.py:100-103`), and must
write `.prawduct/project-state.yaml` with a `consumer_digest:` block plus the digest content at the
declared `path`.

New class `TestDeclaredConsumerDigest`:

1. **No declaration, no digest file → today's exact silence (DIG8).** A non-prawduct-shaped project
   (`plugin/VERSION` absent) with no `project-state.yaml` at all: `check_releasability` prints
   nothing naming any digest path or `consumer_digest`, exactly the existing
   `test_a_repo_that_publishes_no_digest_says_nothing_at_all` assertion style, re-run against a
   project this test itself builds (that existing test relies on `plugin/VERSION` being present to
   reach `_ships_the_plugin_tree`'s own no-subject path — a different branch, same externally
   observable silence, both worth pinning separately since DIG6 vs. DIG8 are now two different code
   paths reaching one outcome).
2. **`sentinel-heading`, scope covered → no warning.** Declares `consumer_digest: {path:
   CHANGELOG.md, keying: sentinel-heading, heading: "Unreleased"}`, writes `CHANGELOG.md` with `##
   Unreleased` followed by a note mentioning the pending scope. `check_releasability` warns on
   nothing digest-related.
3. **`sentinel-heading`, scope uncovered → warns, and the warning names the DECLARED path.** Same
   declaration, digest body unrelated to the scope. Assert the warning contains `CHANGELOG.md`
   (Decision 2's whole point) and not `plugin/CHANGELOG.md`.
4. **`open-heading-pattern`, topmost matching heading wins.** Two `## ` sections, only the topmost
   matching `-dev\.\d+$`; body under the older, non-matching heading must not be read as the open
   section (mirrors `_open_digest_section`'s own "topmost, not any" test, one layer up).
5. **Invalid declaration is a WARNING, not a crash, and not silence (DIG1).** Three sub-cases in one
   parametrized test: `keying` naming neither strategy, both `heading` and `pattern` set, and a
   `pattern` that fails to compile (Decision 3) — each asserts `check_releasability` still returns
   its ordinary exit code (the digest check is advisory; DIG1 does not make it a refusal) and stderr
   names `consumer_digest` and the specific reason, never falling silent the way an absent
   declaration correctly does.
6. **An unreadable `project-state.yaml` reads as undeclared, not invalid.** Directory in place of
   the file (or unreadable permissions where the test runner allows it) → same silent DIG8 outcome
   as case 1, pinning Decision 1's fail-soft precedent.
7. **The advisory never changes a passing or failing verdict**, parametrized the same way
   `test_the_advisory_never_changes_a_passing_verdict` /
   `..._never_changes_a_failing_verdict` already do, run once through the declared path instead of
   the hardcoded one — the exit-code contract DIG-anything must not touch.

`_open_digest_section`'s refactor onto `_section_span` needs no new test (behavior-preserving,
existing suite pins it); a mutation of `_section_span`'s boundary (`range(start + 1, ...)` off by
one) is caught by the existing multi-section tests already exercising `_open_digest_section`.

## Open items for the build chunk (not resolved here)

- Exact wording of the invalid-declaration WARNING strings (cosmetic; Section 1's draft wording is
  a starting point, not pinned prose).
- Whether `_read_consumer_digest_declaration`'s per-line `field: value` parse should reject a
  duplicate field (e.g. two `path:` lines) explicitly, or let the last one silently win. No existing
  reader in this codebase (`_read_declaration`, `read_yaml_block` itself) rejects duplicates within
  one mapping; matching that precedent is the default unless a build-time reviewer wants stricter
  behavior for a key this consequential.
- Whether the two commented template examples (Section 4) should be combined into one block with
  the inactive strategy's fields commented per-line, rather than two full `consumer_digest:` blocks
  — a call the build chunk can make by reading how `risk_surfaces:`'s single example reads in
  context.

## Acceptance (carried from requirements, now with an implementation path)

- [ ] The keying rule is stated as a requirement before any code — requirements doc Decision 1
      (DIG1, DIG3, DIG4), implemented in Section 1 (`_read_consumer_digest_declaration`) and
      Section 2 (the two locators).
- [ ] Declaring gets both checks; others unchanged — Section 3's `_digest_advisories` rewiring
      (DIG5, DIG6, DIG8), pinned by test-plan cases 2-4 (declared gets both) and case 1 (undeclared
      stays silent), with DIG6 additionally pinned by the existing suite passing unmodified (no
      fixture reaches the new branch).
- [ ] No declaration shape can yield a false all-clear — Section 1's three-way
      absent/invalid/valid split (DIG1, DIG2, DIG7) plus Decision 2's `rel_path` parameterization
      (a false all-clear on *which file* is the same defect one field over), pinned by test-plan
      cases 3 and 5.

## Evidence / references

- `plugin/lib/release_readiness.py:415-480` (`_ships_the_plugin_tree`, `_read_digest`,
  `_open_digest_section`), `:483-620` (`_digest_mentions`, `_section_headline`,
  `_headline_advisory`, `_coverage_advisory`), `:623-674` (`_digest_advisories`), `:861-875` (the
  `check_releasability` call site — unchanged by this design).
- `plugin/lib/release_verification.py:69-111` (`VersionFile`, `_FALLBACK_VERSION_FILES` — the
  declared/guessed asymmetry DIG1 mirrors), `:209-259` (`_read_declaration` — the closest existing
  precedent for parsing a hand-rolled mapping out of a `read_yaml_block` body, for a list rather
  than a single mapping), `:14-24` (module docstring's "read from the tag's own tree" rule, the one
  Decision 1 applies to a caller with no tag yet).
- `plugin/lib/core.py:385-427` (`read_yaml_block`, the shared reader every declaration in this
  design goes through), `:453-465` (`yaml_top_level_key_present`, not used here — `read_yaml_block`
  already answers presence via its own status).
- `plugin/lib/risk.py:96-121` (`read_declared_surfaces` — the fail-soft-on-unreadable-file
  precedent Decision 1's declaration reader follows).
- `plugin/templates/project-state.yaml:284-355` (`# RISK SURFACES`, `# RELEASE VERSION FILES` — the
  comment-style precedent Section 4 follows).
- `tests/test_release_readiness.py:66-113` (`_make_project` — `plugin/VERSION` is what makes a
  fixture prawduct-shaped; every new declared-path fixture must omit it), `:1053-1168`
  (`TestDigestCoverageIsAdvisory` — the control/treatment test style this design's test plan
  extends to the declared path).
- Issue #733, comment 2026-09-03 (`documentation/issues/733-requirements.md`'s own landing comment)
  — "Next step: design (exact declaration parsing, locator functions, and the `check_releasability`
  wiring)," the three things this document resolves.
