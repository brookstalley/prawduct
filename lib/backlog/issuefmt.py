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

The linter is **WARN-only by construction** — it returns findings, never a
verdict, and no caller blocks on them (the ``file`` path was never a blocking
gate; this is quality nudging, not enforcement — distinct from the "never demote
a real blocking gate to a warning" rule).
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
}

# §4 thresholds (single source of truth so lint and any doc stay in step).
TITLE_MAX = 72
TITLE_MIN = 15
BODY_MAX_WORDS = 150
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
    (canonical area labels are lowercase, but a human title may not be)."""
    match = re.match(r"^([A-Za-z][A-Za-z0-9._-]*): +(\S.*)$", title)
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
    """One WARN-only lint finding. ``rule`` is a stable kebab-case id (so callers
    can filter/suppress); ``message`` is human-facing. Severity is always
    ``warn`` — this linter has no other level."""

    rule: str
    message: str
    severity: str = "warn"

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "message": self.message, "severity": self.severity}


def lint(title: str, body: str, labels: list[str] | None = None) -> list[LintFinding]:
    """Audit an issue against the standard §4. Returns findings (possibly empty);
    **never** raises and never blocks. Reused verbatim by ``file`` (warn on
    create) and by the migration as an audit-only pass over restructured items.

    ``body`` is the *human* body (no ``prawduct:`` block) and ``labels`` are the
    ``<facet>:value`` labels the issue carries.
    """
    labels = labels or []
    findings: list[LintFinding] = []
    findings += _lint_title(title or "", labels)
    findings += _lint_labels(labels)
    findings += _lint_body(body or "", labels)
    return findings


def _lint_title(title: str, labels: list[str]) -> list[LintFinding]:
    out: list[LintFinding] = []
    n = len(title)
    if n > TITLE_MAX:
        out.append(LintFinding("title-too-long", f"title is {n} chars (budget {TITLE_MAX})"))
    if n < TITLE_MIN:
        out.append(LintFinding("title-too-short", f"title is {n} chars (aim ≥ {TITLE_MIN})"))

    _area, summary = _split_area(title)
    lowered = summary.lower().strip().rstrip(".")
    if lowered in _PLACEHOLDER_TOKENS or any(p in lowered for p in _PLACEHOLDER_PHRASES):
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
