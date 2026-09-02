"""Issue-structure standard — the deterministic title/body composer + linter.

Implements ``documentation/backlog-service-issue-standard.md`` (§1 title, §2 body
sections, §4 lint thresholds), so *one* place owns the title shape, the section
contract, and the quality thresholds. The net-new ``file`` path routes its title
through :func:`normalize_title` and audits with :func:`lint`; the section composer
:func:`render_body` serves callers that assemble a body from parts (the migration
restructure pre-pass, MG6 — :mod:`restructure` composes through it).

**No model, ever (INV-1).** Everything here is pure/deterministic string work:
the *content* of an issue is model-authored (or human-authored via Issue Forms);
this module only normalizes the title, assembles authored sections into the
canonical body layout, and *audits* the result. It never invents prose.

**The four §1 TITLE checks BLOCK; every body and label lint stays WARN-only.**
This module still returns findings rather than a verdict — the posture lives in
the callers — but the split is now load-bearing, so a change here changes what
can be written:

- :func:`lint_title` (``title-too-long`` / ``-too-short`` / ``-placeholder`` /
  ``-non-atomic``) is consumed by every write path as a **refusal**: ``file`` and
  ``update`` reject a non-conforming title before the write, and the migration
  pre-flight refuses a whole corpus before its first write. Loosening a threshold
  here silently widens what enters the backlog; tightening one can hard-refuse an
  irreversible ~900-issue migration. Both directions want a test.
- :func:`lint`'s body and label findings are advisory and gate nothing. That is
  deliberate, not an oversight: a body budget blocking an edit to an unrelated
  field is the confirmation-fatigue shape ``security-model.md``'s approval norm
  rejects, and a title is both the handle every reader triages by and cheap to
  rewrite.

A **false positive here is a false refusal**, which is a different cost than the
noise it used to be — the placeholder check matches whole words for exactly that
reason (see ``_PLACEHOLDER_PHRASE_RE``). The rules themselves are owned by
``documentation/backlog-service-issue-standard.md`` §1; the norm requiring their
enforcement lives in ``.prawduct/artifacts/data-model.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import encode

# The kinds the standard recognizes (§3). Under-populated in practice today, so
# `file` going forward and the migration pre-pass must assign one.
KINDS: tuple[str, ...] = ("bug", "feature", "task", "chore", "spike")

# --- Section contract (§2) ---------------------------------------------------
#
# Each template is an ordered list of (canonical label, required?) sections. The
# canonical label is what `render_body` emits as a `### Label` heading and what
# `lint` looks for; the section rendering matches GitHub Issue Forms (BKL-7F3D),
# which render each field as `### <label>`, so a form-filed issue and a
# programmatically composed one read identically.
#
# `bug` uses the bug template; every other kind (feature/task/chore/spike) uses
# the task/feature template. Required/optional follows §2 verbatim: only the
# sections §2 marks "(opt)" are optional.

_BUG_SECTIONS: tuple[tuple[str, bool], ...] = (
    ("Problem", True),
    ("Repro", True),
    ("Actual", True),
    ("Expected", True),
    ("Evidence", True),
    ("Env", False),
)
_TASK_SECTIONS: tuple[tuple[str, bool], ...] = (
    ("Problem", True),
    ("Proposed change", True),
    ("Acceptance", True),
    ("Scope-out", True),
    ("Evidence", False),
)

# Accepted spellings for a canonical section label (case-insensitive). Keeps the
# linter from false-warning when an author writes a common synonym; `render_body`
# always emits the canonical label.
_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "Repro": ("repro", "reproduction", "repro/input", "steps", "reproduce"),
    "Proposed change": ("proposed change", "change", "proposal", "proposed"),
    "Scope-out": ("scope-out", "scope out", "out of scope", "non-goals", "non goals"),
    "Actual": ("actual", "actual behavior", "actual behaviour"),
    "Expected": ("expected", "expected behavior", "expected behaviour"),
    "Env": ("env", "environment", "env/version"),
}

# §4 thresholds (single source of truth so lint and any doc stay in step).
TITLE_MAX = 72
TITLE_MIN = 15
# The single implementation constant behind the issue standard's body budget.
# Reconciled 2026-07-31 (owner ruling) from three disagreeing numbers: the
# standard's §2 said ~120, its §4 and this constant said 150, and §2's own
# per-section budgets already summed to ~143-155 BEFORE any Evidence section --
# so an author following §2 exactly could produce a conforming issue that still
# tripped `body-too-long`. The standard was unsatisfiable at its own limits.
# 175 is deliberately generous: it clears the per-section sum with headroom for
# a visible Evidence line or two, and bulk evidence belongs in a fence, which
# `_visible_words` excludes from the count anyway.
BODY_MAX_WORDS = 175
EVIDENCE_MAX_LINES = 30
LABELS_MAX = 6

# Low-signal titles the standard calls out (❌ vague / non-specific). A title
# whose summary is *only* one of these tokens, or contains one of the vague
# phrases, reads as a placeholder.
_PLACEHOLDER_TOKENS = frozenset(
    {"fix", "bug", "todo", "wip", "update", "change", "test", "stuff",
     "misc", "temp", "tmp", "placeholder", "chore", "task", "issue"}
)
_PLACEHOLDER_PHRASES = ("the thing", "something", "some stuff", "a bug", "fix it")

# Whole-word alternation over the phrases above. Unanchored `in` matching reads
# straight through word boundaries: "fix it" is a substring of "pre-FIX IT-em",
# so `single-use prefix item 6` linted as a placeholder. Harmless while these
# findings were advisory; a false refusal once they BLOCK a write — so the
# classification is fixed here rather than the budget loosened at the call site.
# "something" keeps its own entry because \b would not fire mid-word anyway and
# the phrase is already whole.
_PLACEHOLDER_PHRASE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in _PLACEHOLDER_PHRASES) + r")\b"
)


def _template_for(kind: str | None) -> tuple[tuple[str, bool], ...] | None:
    """The section template for ``kind`` (bug → bug template, every other known
    kind → task template). ``None`` when ``kind`` is unknown/absent — the caller
    then can't section-check (it doesn't know which template applies)."""
    if kind == "bug":
        return _BUG_SECTIONS
    if kind in KINDS:
        return _TASK_SECTIONS
    return None


# --- Title (§1) --------------------------------------------------------------


def normalize_title(title: str, area: str | None = None) -> str:
    """Emit the §1 title shape: ``area: specific summary``.

    Prepends the ``area:`` prefix when an ``area`` is known and the title is not
    already prefixed with *that* area. Idempotent, and it never fights a title the
    author already prefixed (any ``word:`` lead-in is left as-is) — the linter,
    not this normalizer, flags a *wrong* or missing prefix. Whitespace-only or
    absent area → the title is returned untouched (trimmed).
    """
    title = (title or "").strip()
    area = (area or "").strip()
    if not area:
        return title
    if _split_area(title)[0] is not None:
        # Already carries some `word:` prefix — respect the author's choice.
        return title
    return f"{area}: {title}"


def _split_area(title: str) -> tuple[str | None, str]:
    """Split ``area: summary`` → ``(area, summary)``; ``(None, title)`` when the
    title carries no ``word:`` prefix. The prefix must be a single token followed
    by ``: `` (so a mid-sentence ``foo: bar`` colon or a ``file.py: 12`` reference
    is not mistaken for a prefix). Case-insensitive on the token: an author's
    ``CLI:`` counts as a prefix so ``normalize_title`` never double-prefixes it
    (canonical area labels are lowercase, but a human title may not be).

    ``/`` is IN the charset because areas carry it — ``governance/kernel``,
    ``methodology/planning``, ``templates/artifacts`` and nine more on this
    backlog alone. Without it a slash-bearing area matched as no prefix at all,
    so ``normalize_title`` prepended a second copy and the create then tripped
    the ``title-too-long`` lint it had just caused (#591). The single-token
    anchoring is what keeps a mid-sentence colon out; the charset was the
    defect, not the structure."""
    match = re.match(r"^([A-Za-z][A-Za-z0-9._/-]*): +(\S.*)$", title)
    if match:
        return match.group(1), match.group(2)
    return None, title


# --- Body (§2) ---------------------------------------------------------------


def render_body(kind: str | None, sections: dict[str, str]) -> str:
    """Assemble authored ``sections`` into the canonical ``### Label`` body (§2).

    Sections are emitted in the template order for ``kind``; any key not in the
    template is appended afterward in the caller's given order (never dropped —
    additive-forever, like the block). Empty/whitespace values are skipped so an
    omitted optional section leaves no empty heading. This is the *shared*
    composer, intended for callers that assemble a body from sections — the
    migration restructure pre-pass (MG6, :mod:`restructure`) composes through
    here so a migrated body and a net-new one are byte-identical in layout. The
    net-new ``file`` path authors the body directly (guided + linted), so it does
    not call this today.
    """
    template = _template_for(kind)
    order = [label for label, _req in template] if template else []
    emitted: set[str] = set()
    blocks: list[str] = []

    def _emit(label: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        blocks.append(f"### {label}\n\n{text}")

    # Canonical-order sections first, matched case-insensitively (incl. aliases).
    for label in order:
        key = _match_key(label, sections)
        if key is not None:
            _emit(label, sections[key])
            emitted.add(key)
    # Then any extra authored sections, in the caller's order.
    for key, text in sections.items():
        if key not in emitted:
            _emit(key, text)

    return "\n\n".join(blocks)


def _match_key(canonical: str, sections: dict[str, str]) -> str | None:
    """Find the key in ``sections`` that spells ``canonical`` (case-insensitive,
    alias-aware); ``None`` if absent."""
    accepted = {canonical.lower(), *(_SECTION_ALIASES.get(canonical, ()))}
    for key in sections:
        if key.strip().lower() in accepted:
            return key
    return None


# --- Linter (§4) -------------------------------------------------------------


@dataclass(frozen=True)
class LintFinding:
    """One lint finding. ``rule`` is a stable kebab-case id (so callers can
    filter/suppress); ``message`` is human-facing.

    ``severity`` is always ``warn`` because this type carries no posture — the
    CALLER decides. A `title-*` finding reaching a write path becomes a refusal
    (`core._title_refusal`, `migrate.preflight_titles`); the same dataclass, with
    the same ``"severity": "warn"``, therefore also rides inside a BLOCKING
    validation error. Do not read this field as "this finding is advisory"."""

    rule: str
    message: str
    severity: str = "warn"

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "message": self.message, "severity": self.severity}


def lint(title: str, body: str, labels: list[str] | None = None) -> list[LintFinding]:
    """Audit an issue against the standard §4. Returns findings (possibly empty)
    and **never raises** — but "never blocks" is a statement about THIS function,
    not about its findings: callers refuse on the `title-*` rules it returns (see
    the module docstring). Reused by ``file`` and by the migration's audit pass
    over restructured items.

    ``body`` is the *human* body (no ``prawduct:`` block) and ``labels`` are the
    ``<facet>:value`` labels the issue carries.
    """
    labels = labels or []
    findings: list[LintFinding] = []
    findings += lint_title(title or "", labels)
    findings += _lint_labels(labels)
    findings += _lint_body(body or "", labels)
    return findings


def lint_title(title: str, labels: list[str] | None = None) -> list[LintFinding]:
    """The standard's four §1 **title** checks, alone. Public because the title
    rules are the only lints that BLOCK a write (`file`, `update`, `import`),
    while every body/label lint stays WARN-only — so callers enforcing the
    blocking half need the title findings without the advisory ones mixed in.

    ``labels`` is accepted for symmetry with :func:`lint` and is unused: no §1
    title rule depends on a label. It stays in the signature so a future rule
    that does need one is not a caller-visible break."""
    labels = labels or []
    out: list[LintFinding] = []
    n = len(title)
    if n > TITLE_MAX:
        out.append(LintFinding("title-too-long", f"title is {n} chars (budget {TITLE_MAX})"))
    if n < TITLE_MIN:
        out.append(LintFinding("title-too-short", f"title is {n} chars (aim ≥ {TITLE_MIN})"))

    _area, summary = _split_area(title)
    lowered = summary.lower().strip().rstrip(".")
    if lowered in _PLACEHOLDER_TOKENS or _PLACEHOLDER_PHRASE_RE.search(lowered):
        out.append(LintFinding("title-placeholder", "title is vague/placeholder — say what + where"))

    # Non-atomic: an em-dash or semicolon join in the summary usually means ≥2
    # claims (the standard's own ❌ example). Conservative on purpose — `and` is
    # too noisy a signal to warn on.
    if re.search(r"\s[—–-]\s", summary) or ";" in summary:
        out.append(LintFinding("title-non-atomic", "title joins ≥2 claims — split into atomic issues"))
    return out


def _lint_labels(labels: list[str]) -> list[LintFinding]:
    out: list[LintFinding] = []
    if encode.facet_value(labels, "kind") is None:
        out.append(LintFinding("no-kind", f"no kind: label (assign one of {'/'.join(KINDS)})"))
    if encode.facet_value(labels, "area") is None:
        out.append(LintFinding("no-area", "no area: label"))
    if len(labels) > LABELS_MAX:
        out.append(LintFinding("too-many-labels", f"{len(labels)} labels (keep ≤ {LABELS_MAX})"))
    return out


def _lint_body(body: str, labels: list[str]) -> list[LintFinding]:
    out: list[LintFinding] = []

    # Section presence/emptiness — only when we know the template (kind present).
    kind = encode.facet_value(labels, "kind")
    template = _template_for(kind)
    if template is not None:
        present = _sections_present(body)
        for label, required in template:
            if not required:
                continue
            accepted = {label.lower(), *(_SECTION_ALIASES.get(label, ()))}
            hit = next((h for h in present if h[0] in accepted), None)
            if hit is None:
                out.append(LintFinding("missing-section", f"missing required section: {label}"))
            elif not hit[1]:
                out.append(LintFinding("empty-section", f"empty required section: {label}"))

        # Acceptance prose without checkboxes (task/feature templates only).
        if kind != "bug":
            acc = next((h for h in present if h[0] in {"acceptance"}), None)
            if acc is not None and acc[1] and "- [ ]" not in acc[2] and "- [x]" not in acc[2].lower():
                out.append(
                    LintFinding("acceptance-no-checkbox", "Acceptance has prose but no `- [ ]` items")
                )

        # Env carries the product version (+ environment) on a bug (§2). It is not
        # a *required* section — but a self-filed bug that records the product
        # version it was found in is far cheaper to triage, so a bug with no Env
        # line gets a gentle WARN nudge (never blocks — the advisory posture holds,
        # §4). Distinct from `missing-section` (which reads as "required"): this is
        # a recommendation, not a mandate.
        if kind == "bug":
            env_accepted = {"env", *(_SECTION_ALIASES.get("Env", ()))}
            if not any(h[0] in env_accepted for h in present):
                out.append(
                    LintFinding(
                        "bug-missing-env",
                        "bug has no Env line — record the product version (+ environment)",
                    )
                )

    visible = _visible_words(body)
    if visible > BODY_MAX_WORDS:
        out.append(LintFinding("body-too-long", f"~{visible} visible words (budget {BODY_MAX_WORDS})"))

    run = _max_unwrapped_run(body)
    if run > EVIDENCE_MAX_LINES:
        out.append(
            LintFinding(
                "evidence-unwrapped",
                f"{run} unwrapped lines — put long evidence in a fence or <details>",
            )
        )
    return out


# --- body parsing helpers ----------------------------------------------------

_HEADING_RE = re.compile(r"^#{2,4}\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^\s*```")


def _sections_present(body: str) -> list[tuple[str, bool, str]]:
    """Parse ``### Label`` sections → ``[(label_lower, has_content, content), …]``.
    ``has_content`` is whether any non-blank line follows the heading before the
    next heading. Headings inside a fenced block are ignored (not real sections).
    """
    out: list[tuple[str, bool, str]] = []
    lines = body.splitlines()
    in_fence = False
    current: str | None = None
    content: list[str] = []

    def _flush() -> None:
        if current is not None:
            text = "\n".join(content).strip()
            out.append((current.strip().lower(), bool(text), text))

    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            if current is not None:
                content.append(line)
            continue
        m = None if in_fence else _HEADING_RE.match(line)
        if m:
            _flush()
            current = m.group(1)
            content = []
        elif current is not None:
            content.append(line)
    _flush()
    return out


def _strip_wrapped(body: str) -> str:
    """Remove fenced code blocks and ``<details>`` regions — the "hidden" content
    that progressive disclosure keeps out of the visible budget."""
    without_fences = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    without_details = re.sub(r"<details>.*?</details>", "", without_fences, flags=re.DOTALL | re.IGNORECASE)
    return without_details


def _visible_words(body: str) -> int:
    """Count visible words: authored prose minus fenced/``<details>`` content and
    the ``### Label`` heading words themselves (headings are structure, not prose)."""
    stripped = _strip_wrapped(body)
    stripped = "\n".join(
        "" if _HEADING_RE.match(line) else line for line in stripped.splitlines()
    )
    return len(stripped.split())


def _max_unwrapped_run(body: str) -> int:
    """Longest run of consecutive non-blank lines that are *not* inside a fence or
    ``<details>`` — a long unwrapped run is the "evidence dump that should be
    wrapped" signal (§4)."""
    lines = body.splitlines()
    in_fence = False
    in_details = False
    run = 0
    longest = 0
    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            run = 0
            continue
        low = line.strip().lower()
        if low.startswith("<details"):
            in_details = True
            run = 0
            continue
        if low.startswith("</details>"):
            in_details = False
            run = 0
            continue
        if in_fence or in_details:
            continue
        if line.strip() and not _HEADING_RE.match(line):
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return longest
