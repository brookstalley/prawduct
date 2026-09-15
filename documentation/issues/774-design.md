# Issue #774 — Governance: No Norm Governs Comment Content or Volume: Design

`status: draft · stage: design · area: governance · added: 2026-09-13 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/774`

Builds on `documentation/issues/774-requirements.md` (CCN-1 through CCN-9, Decisions 1–9). One
requirements-doc grounding fact is corrected below before design proceeds — the correction changes
CCN-1/CCN-2's shape substantially, so it is surfaced first rather than silently designed around.

Related: `plugin/lib/norm_probes.py::probe_norm_registry_unratified` (the structural precedent
CCN-5 mirrors), `plugin/lib/compliance.py::_is_source_file` (the classifier CCN-3 extends),
`.prawduct/artifacts/architecture.md` § Direction (the two ratified norms the requirements doc's
reconciliation cites, and — corrected below — this norm's actual new home).

## Correction to the requirements doc's grounding

**`.prawduct/project-preferences.md` does not exist, but `.prawduct/artifacts/project-preferences.md` does, and it is populated.**

The requirements doc's central grounding fact — "`.prawduct/project-preferences.md` does not exist
in this repo... confirms acceptance criterion 2... is authoring a file from scratch" — checked the
wrong path. This repo's actual, canonical location is `.prawduct/artifacts/project-preferences.md`
(alongside the other six strategy-class artifacts), not `.prawduct/project-preferences.md`. The
code that will consume this norm already reads it from there:
`norm_probes.py:872`'s `_read_text(codebase.root / ".prawduct" / "artifacts" /
"project-preferences.md")`, and `prawduct-hook`'s own preferences check (`:1530`) and
`briefing.py:1350` agree. The file is 153 lines, has a live `## Enforcement` section with two real
tables (`Code-level preferences`, `Direction norms (architectural)`), and is cited by name in over
a dozen build plans as this repo's own preferences artifact. It is not a scaffold — the file
carries **no** placeholder rows (Health Check #14's leftover-scaffold concern does not apply).

This does not reopen Decisions 1–9; it corrects one fact those decisions were built on top of, and
narrows CCN-2's scope in this item's favor: **this item ADDS to two existing files (`architecture.md`
and `project-preferences.md`); it authors neither from scratch.** See Decision D10 below for where
the Direction entry actually goes, given this repo's own established pattern for Direction-vs-
preferences-table placement.

## Summary of what ships

1. **D10 / CCN-1** — one new `## Direction` entry in `.prawduct/artifacts/architecture.md` (this
   repo's home for cross-cutting process norms, not `project-preferences.md` — see Decision below),
   carrying Statement/Why/Status(`in-transition`)/Retroactivity(`migrate: #772`).
2. **CCN-2** — one new **pointer row** in `.prawduct/artifacts/project-preferences.md`'s existing
   `### Direction norms (architectural)` table, naming `architecture.md` as the home, `Critic` as
   mechanism, `advisory` as audit home (CCN-5 names the mechanical hook).
3. **CCN-6** — a template/data fix, not a code change: `plugin/templates/project-preferences.md`
   and `.prawduct/artifacts/project-preferences.md`'s own two existing rows are corrected from
   `(Goal 4: Norms)` to `(Goal 3: Normative authority)` — the actual routing per
   `review-protocol.md`'s Normative-authority preamble, and the literal source of the issue's own
   stale citation (traced below).
4. **CCN-3 / CCN-4 / D11** — a new pure module, `plugin/lib/comment_density.py`, computing the
   SonarQube-style ratio per file with **one language-agnostic marker set**, never a table keyed by
   extension — resolving the tension between CCN-3's literal wording and the two architecture.md
   norms the reconciliation comment cites (Decision D11 below). `_is_source_file` is imported and
   used unmodified to select which files count.
5. **CCN-8** — a new read-only `prawduct-hook comment-density [--json] [--top N]` subcommand,
   following `coverage-status`'s degrade-never-crash shape, ranking the worst files by ratio.
6. **CCN-5** — one new probe, `probe_comment_content_norm_unratified`, in `plugin/lib/norm_probes.py`,
   gated on its own dedicated key `comment_content_norm_ratified` (never `RATIFIED_FACT`),
   structurally mirroring `probe_norm_registry_unratified`.
7. **CCN-9 / Decision D5, D9 carried forward** — no change to `review-protocol.md`, Goal 3, or
   Goal 4: findings against this norm already route through the existing Normative-authority
   preamble once the norm exists (see Decision D10 below); this item ships no protocol text change.

## Decisions resolved

### D10 — Where the Direction entry goes (not `project-preferences.md` itself)

The corrected grounding fact (above) shows this repo's own established pattern, read directly off
its populated `project-preferences.md`: that file carries **two** kinds of rows — plain
`Code-level preferences` rows (Mechanism / Enforcement artifact / Audit home / Why, no
Status/Retroactivity columns, used for steady-state conventions), and `Direction norms
(architectural)` **pointer** rows indexing `## Direction` sections that live in the *other*
strategy-class artifacts (`architecture.md`, `data-model.md`, `observability-strategy.md`). No
existing convention puts a full Direction entry (with Status/Retroactivity, which this norm needs
per Decision 6/CCN-1) inside `project-preferences.md` itself — the file's own table format has no
columns for those fields.

This norm needs `Status: in-transition` and `Retroactivity: migrate: #772` (Decision 6). Those
fields exist only in the Anatomy of a full Direction entry (`norms.md` § Anatomy), so this item
follows the established pattern exactly: **the entry goes in `architecture.md` § Direction**, and
`project-preferences.md` gets one pointer row, mirroring the existing `LNG-5W8R` pointer row's
shape precisely (`Norm (pointer) | Home § Direction | Mechanism | Audit home | Why (terse)`).

`architecture.md` is the right strategy artifact, not `data-model.md` or `observability-strategy.md`:
it already homes the two norms the requirements doc's own reconciliation cites almost verbatim
(`architecture.md:82` "Prawduct is written in Python and must never be specific to Python...",
`architecture.md:88` "Prawduct guides and reviews; it never implements...") — both are
cross-cutting, code-craft-adjacent process norms, and this is a third of the same genus (how code
in any governed product is written and reviewed), not a data-model or observability concern.

### D11 — The locator computes a ratio without a per-language syntax table

**The tension.** CCN-3 says the locator "MUST compute the SonarQube-style ratio... across every
file `compliance.py::_is_source_file` recognizes" (12 extensions: `.py .js .ts .jsx .tsx .go .rs
.java .rb .swift .kt .cs .c .cpp .h`). But the issue's own "design change from planning" comment
(posted before the requirements pass, and requirements Decision 1 explicitly carries it forward)
quotes two ratified `architecture.md` norms that forbid exactly the naive reading of that
sentence: *"no gate acquires a language-specific parser — suffix matching only; a parser per
language, and a syntax-pattern table per language, are both the complexity ratchet this norm
exists to prevent"* (`architecture.md:84`, the Python-specificity norm — its Scope note confirms
it governs "what gates *assume about the code they inspect*", which this locator does, over
exactly the polyglot governed-product corpus that norm exists for) and *"prawduct guides and
reviews; it never implements... never re-implements what a product's own tooling already does"*
(`architecture.md:88`). Knowing that a `.py` file's comments start with `#` and a `.java` file's
start with `//` or `/* */` **is** a syntax-pattern table keyed by language if built as a per-
extension dispatch dict — the exact shape `_check_broad_exceptions`-style per-language regex tables
were retired for elsewhere in this same file's Retroactivity enumeration.

**The resolution: one flat marker set, applied identically regardless of extension.**

```python
# plugin/lib/comment_density.py
_COMMENT_OPEN_MARKERS = ("#", "//", "/*", "*", '"""', "'''", "///", "/**")

def _is_comment_or_doc_line(stripped: str) -> bool:
    return any(stripped.startswith(m) for m in _COMMENT_OPEN_MARKERS)
```

This is not a table keyed by language — `_is_comment_or_doc_line` never inspects a file's
extension to decide which markers apply; the same eight-marker set runs against every file
`_is_source_file` selects, Python and Rust and Swift alike. That is the literal property the
Python-specificity norm asks for ("no gate may assume the governed product shares the runtime's
language"), read the other way: a check that assumes nothing about *which* language a file is
written in cannot be Python-specific, because it never asks. It is coarser than a real per-language
lexer (a `"""` inside a Python string body without doc-comment role would be miscounted; a `*` mid
expression in a C file's multiplication would not, since `_is_comment_or_doc_line` only tests
*line-start* markers on the stripped text) — that imprecision is the same trade the false-confidence
guardrail already names for this exact norm (`project-preferences.md`'s own template text,
requirements Decision 2): CCN-4 forbids this number from ever gating a build or review, so an
approximate **ranking** signal that sometimes over- or under-counts a line is the correct-priced
instrument, not a defect to fix with more per-language precision. **What this resolution explicitly
does NOT do**, because either would recreate the forbidden shape: it does not branch on file
extension anywhere in the counting logic, and it does not shell out to a per-ecosystem tool the way
issue #620's API-diff socket does (that pattern fits a *build-time, opt-in, blocking-capable* gate
with real per-ecosystem tools already installed; this is an *ambient, informational, ranking-only*
locator where a missing per-ecosystem producer would leave most products with nothing to point at
all, which is a worse outcome than a rough universal heuristic that always produces a ranking).

**`_is_source_file` is reused unmodified** (CCN-3's own words: "extending that shared classifier
rather than forking a second one") purely to decide which files are counted at all — filtering,
not comment detection — so Decision 1's actual constraint ("rather than forking a second
per-language classifier") is satisfied by construction: there is no second classifier, per-language
or otherwise.

```python
# plugin/lib/comment_density.py
from __future__ import annotations

from pathlib import Path

from .compliance import _is_source_file

_COMMENT_OPEN_MARKERS = ("#", "//", "/*", "*", '"""', "'''", "///", "/**")


def _is_comment_or_doc_line(stripped: str) -> bool:
    """True if a line's stripped text opens with a comment/doc-comment marker.

    Language-agnostic by construction (issue #774 Decision D11): this checks
    the same flat marker set against every file regardless of extension —
    never a table keyed by language, which `architecture.md` § Direction (the
    Python-specificity norm) forbids. Approximate on purpose: this feeds a
    ranking-only locator (CCN-4), never a pass/fail gate.
    """
    return any(stripped.startswith(m) for m in _COMMENT_OPEN_MARKERS)


def density_for_file(path: Path) -> dict | None:
    """SonarQube-style ratio for one file: comment_lines / (code_lines + comment_lines).

    Returns ``None`` for a file `_is_source_file` would reject, or one that
    cannot be decoded UTF-8 (fails open to "not counted", never to a crash —
    matches this repo's own file-reading convention elsewhere in `norm_probes.py`).
    Blank lines count toward neither numerator nor denominator (SonarQube's own
    `comment_lines_density` excludes them the same way — issue #774 Prior Art).
    """
    if not _is_source_file(str(path)):
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    comment_lines = code_lines = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _is_comment_or_doc_line(stripped):
            comment_lines += 1
        else:
            code_lines += 1
    total = comment_lines + code_lines
    if total == 0:
        return None
    return {"path": str(path), "comment_lines": comment_lines, "code_lines": code_lines,
            "ratio": comment_lines / total}


def rank_worst(root: Path, top: int = 15) -> list[dict]:
    """Every counted file's density, worst (highest ratio) first, capped at `top`.

    Walks `root` skipping the same directories `advisory_store`'s Codebase
    scanner skips (`.git`, `node_modules`, `.venv`, etc.) — imported, not
    re-listed, so the two scans can't drift on what "the codebase" means.
    """
    from .advisory_store import _SCAN_SKIP_DIRS  # noqa: PLC0415 — avoids a cycle at import time

    results = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in _SCAN_SKIP_DIRS for part in path.parts):
            continue
        d = density_for_file(path)
        if d is not None:
            results.append(d)
    results.sort(key=lambda d: d["ratio"], reverse=True)
    return results[:top]
```

`rank_worst` is the one function both CCN-5 (the probe) and CCN-8 (the CLI) call — one
implementation, two callers, per this repo's own "every fact has one home" norm
(`architecture.md:104`).

### D12 — CCN-6's fix is a template/data correction, and it has three sites, not one

Tracing the issue's own stale "Goal 4 (Norms)" phrase to ground: it is not an invention of the
issue text. `plugin/templates/project-preferences.md:67`'s own Enforcement mechanism-table legend
reads `| **Critic** | \`/critic\` review (Goal 4: Norms) | ...` — this is the literal shipped
template every product's preferences.md scaffolds from, and it is simply wrong against
`review-protocol.md`'s actual goal titles (requirements Grounding facts: no goal named "Norms"
exists; Goal 4 is "Everything Is Coherent"; every normative departure routes to Goal 3's
Normative-authority preamble). **This repo's own `.prawduct/artifacts/project-preferences.md`
inherited the same wrong text at two rows** (found by the same grep the requirements doc ran, one
level further): line 69's Critic mechanism-table legend, and line 102's `Backlog filing: fix,
don't file` row, which cites `Goal 4 (Norms)` directly as its enforcement artifact. All three sites
get the same fix — `(Goal 4: Norms)` / `Goal 4 (Norms)` → `(Goal 3: Normative authority)` — with no
other wording changed, so this is a citation correction, not a re-litigation of what either row's
norm says.

```diff
- | **Critic** | `/critic` review (Goal 4: Norms) | Judgment-required rules ...
+ | **Critic** | `/critic` review (Goal 3: Normative authority) | Judgment-required rules ...
```

(applied to both `plugin/templates/project-preferences.md:67` and
`.prawduct/artifacts/project-preferences.md:69`, and the `Goal 4 (Norms)` cell at
`.prawduct/artifacts/project-preferences.md:102` becomes `Goal 3 (Normative authority)`.)

This closes CCN-6 without touching `review-protocol.md` itself: that file already routes
correctly (Grounding facts) — the bug was always in the two files that *cite* it, not in the
routing.

### D13 — CCN-5's probe: dedicated key, mirrored shape, computed trigger text

```python
# plugin/lib/norm_probes.py — new module-level constant, alongside RATIFIED_FACT
COMMENT_NORM_RATIFIED_FACT = "comment_content_norm_ratified"


def probe_comment_content_norm_unratified(state: ProjectState, codebase: Codebase):
    """Fire once: this repo has measurable source but has not ratified (or dismissed)
    the comment-content-and-volume norm (issue #774).

    Independently gated from :data:`RATIFIED_FACT` (Decision D4/CCN-5) — dismissing the
    general norm-registry advisory must not silently dismiss this one, and vice
    versa. Applicability gate mirrors `probe_norm_registry_unratified`'s own shape
    (a structural-presence guard before the ratification question): here, "is
    there anything to measure" rather than "does a strategy artifact exist" —
    a repo with no `_is_source_file` files has nothing this norm could apply to.
    """
    if state.get(COMMENT_NORM_RATIFIED_FACT):
        return []
    from . import comment_density  # noqa: PLC0415 — lazy, mirrors this module's other lazy imports

    worst = comment_density.rank_worst(codebase.root, top=5)
    if not worst:
        return []
    overall_ratio = sum(d["comment_lines"] for d in worst) / max(
        1, sum(d["comment_lines"] + d["code_lines"] for d in worst)
    )
    return [
        AdvisoryCandidate(
            type="comment-content-norm-unratified",
            evidence=(
                "prawduct ships a candidate norm for comment/doc-comment content and volume "
                "(issue #774); this product has not ratified or dismissed it",
            ),
            trigger_summary=(
                f"Comment-content norm not yet ratified — the worst-measured file here runs "
                f"~{worst[0]['ratio']:.0%} comment/doc-comment lines. Ratify via "
                "/prawduct:doctor, or dismiss."
            ),
            owner_action=(
                "Say go and I will propose the comment-content norm — what a comment is for, "
                "and where change history goes instead — for you to ratify or decline, same as "
                "any other candidate norm."
            ),
            recommended_action="/prawduct:doctor",
            priority="info",
        )
    ]
```

`register()` gains one line: `register_probe(FEATURE, "comment-content-norm-unratified",
PROBE_VERSION, probe_comment_content_norm_unratified)`. No `PROBE_VERSION` bump — this is a new
probe *type* under the existing `"norm-lifecycle"` feature, not a semantic change to an existing
one; the module docstring's "Five deterministic... probes" becomes "Six."

**Why `worst[0]` and not a full-repo aggregate for the headline number:** `rank_worst` already caps
at `top` files for the CLI's ranking use (CCN-8); reusing it here with a small `top=5` keeps the
probe's per-session cost bounded to the same handful of files it will name, rather than a second,
larger full-tree pass just to compute one summary percentage. This is an approximation of "you are
at X%" (issue Decision 4's own phrasing), not a repo-wide average — precise enough for a
one-line nudge that names a real, currently-worst file, never claimed as a repo-wide statistic in
the trigger text.

### D14 — Doctor wiring: one paragraph, no new Health Check number

The existing **Norm Ratification Flow** (`skills/doctor/SKILL.md` §"Norm Ratification Flow") already
proposes candidate norms generically and lets the owner ratify or veto each individually — this
candidate rides that same flow unchanged. The one addition needed is that step 5 ("Record the
outcome") must also record **this norm's own disposition** distinctly, per Decision D4/CCN-5:

```diff
  5. **Record the outcome** — set `norm_registry_ratified: <today>` (top-level scalar) in
     `project-state.yaml`. ...
+    **Per-candidate dedicated keys** (issue #774's `comment_content_norm_ratified` is the first):
+    a candidate norm whose advisory is gated on its OWN key, not `norm_registry_ratified`
+    (`probe_comment_content_norm_unratified`'s own docstring names the reason), gets its key set
+    the same way — `<key>: <today> — ratified` or `<key>: <today> — dismissed: <reason>` — as part
+    of the SAME ratification session, whether or not the bulk registry outcome is also being
+    recorded this time. A dismissal is a valid, complete outcome (Adoption's "no norms to ratify"
+    precedent, applied per-norm).
```

No new numbered Health Check — this is a one-paragraph addition to a flow that already exists and
already handles individually-surfaced candidates (its own step 3: "decision-worthy candidates...
surfaced individually with their fork").

## Files touched

| File | Change |
|---|---|
| `.prawduct/artifacts/architecture.md` | New `## Direction` entry: comment-content norm (Statement/Why/Status: in-transition/Retroactivity: migrate #772) — D10/CCN-1 |
| `.prawduct/artifacts/project-preferences.md` | One new pointer row in `### Direction norms (architectural)` (CCN-1/CCN-2); two existing cells corrected `Goal 4 (Norms)` → `Goal 3 (Normative authority)` (D12/CCN-6) |
| `plugin/templates/project-preferences.md` | One cell corrected `(Goal 4: Norms)` → `(Goal 3: Normative authority)` (D12/CCN-6) |
| `plugin/lib/comment_density.py` (new) | `_is_comment_or_doc_line`, `density_for_file`, `rank_worst` — CCN-3/CCN-4/D11 |
| `plugin/lib/norm_probes.py` | New `COMMENT_NORM_RATIFIED_FACT`; new `probe_comment_content_norm_unratified`; one `register()` line; module docstring count five→six (CCN-5) |
| `plugin/bin/prawduct-hook` | New `cmd_comment_density(project_dir, argv)` (`--json`, `--top N`), CLI dispatch entry, docstring — CCN-8 |
| `plugin/skills/doctor/SKILL.md` | One paragraph added to Norm Ratification Flow step 5 (D14/CCN-5) |
| `tests/test_comment_density.py` (new) | Locator unit tests (below) |
| `tests/test_norm_probes.py` | New probe's gating, independence from `RATIFIED_FACT`, trigger-text tests |

## `cmd_comment_density` (CCN-8)

```python
def cmd_comment_density(project_dir: Path, argv: list[str]) -> int:
    """Report the worst-N files by comment/doc-comment density (issue #774's locator).

    Read-only and informational — always exits 0, mirroring `coverage-status`: a
    ranking report must not fail an operator's shell, and this locator never
    passes or fails anything (CCN-4). ``--top N`` overrides the default of 15;
    ``--json`` emits the structured list for the doctor/advisory surfaces.
    """
    rejected = _reject_unknown_args("comment-density", argv, {"--json", "--top"})
    if rejected is not None:
        return rejected
    top = 15
    if "--top" in argv:
        idx = argv.index("--top")
        try:
            top = int(argv[idx + 1])
        except (IndexError, ValueError):
            print("error: --top requires an integer", file=sys.stderr)
            return 2
    want_json = "--json" in argv
    lib_root = _plugin_root()
    if lib_root not in sys.path:
        sys.path.insert(0, lib_root)
    try:
        from lib import comment_density
    except ImportError as exc:
        print(f"NOTE: comment-density unavailable (plugin lib/ not importable: {exc})", file=sys.stderr)
        return 0
    worst = comment_density.rank_worst(project_dir, top=top)
    if want_json:
        print(json.dumps({"worst": worst}, indent=2))
        return 0
    if not worst:
        print("comment-density: no source files counted.")
        return 0
    print(f"Comment/doc-comment density — worst {len(worst)} file(s) (ranking only; never pass/fail):")
    for d in worst:
        print(f"  {d['ratio']:6.1%}  {d['path']}  ({d['comment_lines']}c / {d['code_lines']}code)")
    return 0
```

`--top` accepting a bad value returns exit 2 (usage error) per this repo's own documented exit-code
scheme (`project-state.yaml` `api_error_model_approach`: "usage error 2"); every other path is a
report and returns 0, matching `coverage-status`'s own "a health report must not fail the operator's
shell" rationale verbatim.

## Test plan

**`tests/test_comment_density.py`:**

1. A `.py` fixture file with a known count of `#`-prefixed lines and code lines → `density_for_file`
   returns the exact expected ratio.
2. A `.js` fixture with `//` and `/* */` lines → same formula, same function, no per-extension
   branch exercised (pins D11: one code path serves both, demonstrating CCN-3's "at least one
   non-Python file" acceptance criterion).
3. A file `_is_source_file` rejects (e.g. `test_foo.py`, or a `.md` file) → `density_for_file`
   returns `None`, not zero — pins that exclusions are inherited from the shared classifier, not
   re-derived.
4. A file that is not valid UTF-8 → `None`, not a raised exception.
5. An all-blank-lines file → `None` (division-by-zero guard), not a crash.
6. `rank_worst` over a small fixture tree returns files sorted highest-ratio-first, capped at
   `top`, and skips `.git`/`node_modules`-style directories via the shared `_SCAN_SKIP_DIRS` set.

**`tests/test_norm_probes.py` additions:**

7. `probe_comment_content_norm_unratified` fires on a fixture repo with source files and
   `comment_content_norm_ratified` unset.
8. Setting `norm_registry_ratified` (the OTHER key) does **not** suppress this probe — pins
   independence (Decision D4).
9. Setting `comment_content_norm_ratified` to any truthy value (including a dismissal string)
   suppresses it.
10. A repo with zero `_is_source_file` files (e.g., a docs-only repo) never fires this probe.
11. `register()` registers the new probe type under `FEATURE = "norm-lifecycle"`; a full
    `run_all_probes` pass surfaces it alongside the existing five when applicable.

**`prawduct-hook` CLI test additions** (existing subcommand-test file):

12. `comment-density` on a fixture tree with no source files → exit 0, "no source files counted."
13. `comment-density --top 2` returns exactly 2 entries when 3+ qualifying files exist.
14. `comment-density --top notanumber` → exit 2.
15. `comment-density --json` output round-trips through `json.loads` and matches `rank_worst`'s
    return shape exactly (no silent reformatting between the lib call and the CLI print).

## Open items for the build chunk (not resolved here)

- Exact prose wording of the `architecture.md` Direction entry's Statement and Why sentences —
  this document fixes the required fields (Status: in-transition, Retroactivity: migrate #772) and
  the content each must cover (interface + non-obvious why; history to change-log/build-plan), not
  the final sentence-level wording, which is an authoring task for the chunk that writes it.
- Whether `_COMMENT_OPEN_MARKERS` needs any addition beyond the eight listed (e.g., HTML/XML `<!--`
  for any recognized extension that uses it) — none of the 12 extensions `_is_source_file`
  recognizes today use `<!--`, so none is included; a future extension added to `_is_source_file`
  that does would need this set revisited, which is a one-line addition, not a redesign.
- Whether doctor's Norm Ratification Flow should surface this specific candidate's measured
  worst-file list (from `rank_worst`) inline when proposing it, versus pointing the owner at
  `prawduct-hook comment-density` — a presentation choice for the chunk that wires doctor's prompt
  text, not a structural one.

## Acceptance (carried from requirements, now with an implementation path)

- [ ] A Direction entry exists in `architecture.md`, with a pointer row in
      `project-preferences.md`'s existing Enforcement table — not a freshly-authored preferences
      file (corrected from CCN-2's literal wording per the grounding correction above).
- [ ] The locator (`comment_density.rank_worst`) runs across every language `_is_source_file`
      recognizes using one language-agnostic marker set, demonstrated on a non-Python fixture —
      pinned by test-plan cases 1–2.
- [ ] The locator never fails a build or review on a number — `cmd_comment_density` always exits 0
      except a usage error, and nothing else in this item calls it from a gating context.
- [ ] The one-shot invitation (`probe_comment_content_norm_unratified`) fires once, is dismissible,
      and records its own decision independent of `norm_registry_ratified` — pinned by cases 7–10.
- [ ] Findings against this norm are raised as Goal 3 findings — no protocol change needed
      (Grounding facts already confirmed this routes correctly); the only correction is the two
      stale citations naming "Goal 4 (Norms)" instead — pinned by D12's diff.
- [ ] No line-count or percentage pass/fail threshold exists anywhere in the shipped mechanism —
      `comment_density` never returns a verdict, only a ranking (CCN-4).

## Evidence / references

- `documentation/issues/774-requirements.md` — CCN-1 through CCN-9, Decisions 1–9, and the
  Grounding facts this design corrects (the `.prawduct/project-preferences.md` path) and builds on
  (the 12-extension count, the goal-name mismatch, the `RATIFIED_FACT`-independence requirement).
- `.prawduct/artifacts/project-preferences.md:1-153` (full file, confirming it exists, is
  populated, and shows this repo's own Direction-entry-vs-pointer-row convention); `:69`, `:102`
  (the two stale "Goal 4 (Norms)" citations D12 corrects).
- `.prawduct/artifacts/architecture.md:82-87` (Python-specificity norm, its Scope note, and its
  "no gate acquires a language-specific parser" Status text — D11's constraint), `:88-89`
  ("prawduct guides and reviews; it never implements... never re-implements what a product's own
  tooling already does" — D11's second constraint), `:104` ("every fact has one home" — D11's
  `rank_worst`-is-the-one-implementation rationale).
- `plugin/lib/compliance.py:29-44` (`_is_source_file`, its 12 extensions, test/`.prawduct/`
  exclusions) — reused unmodified by `density_for_file`.
- `plugin/lib/norm_probes.py:140-166` (`FEATURE`, `PROBE_VERSION`, `RATIFIED_FACT`), `:1204-1253`
  (`probe_norm_registry_unratified`, the structural precedent D13 mirrors), `:1322-1326`
  (`register()`).
- `plugin/lib/advisory_store.py:79` (`_SCAN_SKIP_DIRS`, reused by `rank_worst` rather than
  re-listed), `:88-135` (`AdvisoryCandidate` fields).
- `plugin/bin/prawduct-hook:5193-5347` (`cmd_coverage_status`, the read-only/degrade-never-crash
  shape `cmd_comment_density` follows).
- `plugin/skills/doctor/SKILL.md` § "Norm Ratification Flow" (step 5's existing "Record the
  outcome" instruction, extended by D14) and its step 3 (individually-surfaced candidates —
  the existing mechanism this candidate rides unchanged).
- `plugin/templates/project-preferences.md:59-77` (`## Enforcement`, the mechanism-table legend
  whose Critic row D12 corrects; the false-confidence guardrail cited for D11's precision
  trade-off).
- Issue #774 body, "design change from planning" comment (2026-09-10) — the two architecture.md
  norm quotes D11 reconciles, and the "you are at X%... ratify via /prawduct:doctor, or dismiss"
  phrasing D13's `trigger_summary` matches.
