# Issue #275 — Build-plan: Extend `verify-chunk-refs` Beyond File Paths: Design

`status: draft · stage: design · area: build-plan · added: 2026-08-29 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/275`

Builds on `documentation/issues/275-requirements.md` (Decisions 1–5, requirements BLD5V8F-1–8).
That document scoped the exact wiring of the cache-unavailable condition (BLD5V8F-5) to design —
"a new field alongside `file_paths`/`backlog_refs`, vs. reusing `error`" — and this document
resolves it. It also flagged, but did not resolve, where the shared id regexes should live
(Decision 2); this document picks `plugin/lib/core.py`.

Grounding facts re-verified against current `develop` (2026-08-29, one day after the requirements
pass): line numbers have drifted slightly from that document's citations because the tree kept
moving — `_parse_build_plan_chunk_refs` is now `buildplan_refs.py:1750-1874` (was cited at
`1626-1750`), `_verify_chunk_refs` is `:2183-2219`, and `prawduct-hook`'s closing count line is
now `:4046` (`count = len(refs["file_paths"])`), not `:3746`. No content drift — same functions,
same shapes, only line numbers moved. One new fact the requirements pass did not need: **an
existing test suite, `tests/test_build_plan_resolution.py`, asserts `_verify_chunk_refs(...) ==
[]` or indexes its return value as a bare list at ~25 call sites.** That constrains this design
more than the requirements doc anticipated — see §4's rejected alternative.

## 1. Summary of what ships

1. **BLD5V8F-2** — `BACKLOG_ID_RE` and `ISSUE_REF_RE` move from `norm_probes.py` (private,
   underscore-prefixed) to `plugin/lib/core.py` (public), which both `norm_probes.py` and
   `buildplan_refs.py` import. `norm_probes.py` keeps its existing private names as thin aliases,
   so none of its ~10 call sites change.
2. **BLD5V8F-1, 4, 6** — `_parse_build_plan_chunk_refs` gains a `backlog_refs` list in its return
   dict, populated only when `backlog_service_repo` is set, reusing the exact `forward_refs`/
   `gone_refs`/waiver-pragma machinery `file_paths` already goes through.
3. **BLD5V8F-3, 5** — `_verify_chunk_refs` resolves each `backlog_refs` entry via
   `backlog.cachequery.resolve`, appending a `kind: "backlog_ref"` entry to its existing `missing`
   list for a real non-resolution, and at most one `kind: "backlog_ref_unchecked"` entry when the
   cache itself could not answer. **No change to `_verify_chunk_refs`'s return type** — still
   `list[dict]` — which is what keeps this item from touching ~25 existing assertions (§4).
4. **BLD5V8F-8** — both callers (`cmd_verify_chunk_refs`, `_check_chunk_refs`) branch on the new
   `kind` values: a `backlog_ref` entry prints/finds exactly like a `file_path` miss; a
   `backlog_ref_unchecked` entry is pulled out and reported through each caller's own existing
   "could not run" channel (`cannot-verify:` in the hook; `gap` in `record_lint.py`) rather than
   as a missing-deliverable claim.
5. **BLD5V8F-7** — no change anywhere to symbol (`path::symbol`) handling; `_ref_path_part` is
   called exactly as before.

## 2. `plugin/lib/core.py` — the shared id-citation shape (BLD5V8F-2)

```python
# plugin/lib/core.py — new imports/constants

import re  # not previously imported here

# A backlog-item citation, in either spelling a norm, chunk, or dispatch note
# uses: a hand-minted PFX id (`BKL-7M4Q`) or an issue reference (`#249`,
# `owner/repo#249`). Definitions moved here from norm_probes.py (BLD5V8F-2) so
# buildplan_refs.py can classify a backticked token against the same shape
# without adding a third copy — issue #336 already tracks two independent
# copies of the PFX pattern (norm_probes.py and release_readiness.py); a
# design pass for THIS item must not add a fourth without at least not adding
# a third along the way. Consolidating #336's existing two copies is separate,
# larger work and stays out of this item's scope.
BACKLOG_ID_RE = re.compile(r"\b[A-Z]{2,4}-[A-Z0-9]{4}\b")
ISSUE_REF_RE = re.compile(r"(?<![\w#])(?:[\w.-]+/[\w.-]+)?#\d+\b")
```

`norm_probes.py`'s own definitions (`:162,176`) are replaced with imports, keeping the old private
names as aliases so its `_extract_ids` (`:465-476`) and every other reference needs no edit:

```python
# plugin/lib/norm_probes.py — replaces the two `re.compile(...)` lines
from .core import BACKLOG_ID_RE as _BACKLOG_ID_RE, ISSUE_REF_RE as _ISSUE_REF_RE
```

The narrative comments explaining *why* each shape looks the way it does (`:157-176` — the 2–4
letter/4-char rationale, the issue-ref lookbehind, the "false shape is harmless" argument) move
with the constants to `core.py`; `norm_probes.py` keeps a one-line pointer rather than restating
them, matching how this file already treats moved logic (`buildplan_refs.py:3971-3977`'s own
"moved to X, see there" comment is the precedent for the pointer style).

**Why `core.py` and not a new module.** `core.py` already hosts the cross-module low-level
constants and helpers both files import (`read_str_yaml_key`, `resolve_build_plan_path`); adding
two regex constants is squarely inside its stated charter ("Core utilities and constants shared
across the plugin's governance modules") and creates no new import edge — `buildplan_refs.py`
already imports `core` as a module (`:56`), and `norm_probes.py` gains its first `core` import,
which is a strictly lower-risk addition than a new shared module neither file currently depends
on. `backlog/core.py` (a different, package-scoped module inside `lib/backlog/`) is not a
candidate — these regexes classify prose/build-plan tokens, not backlog-store data, and importing
the backlog package from `buildplan_refs.py`'s hot classification path would pull in a heavier
dependency for a two-line regex.

**Not moved:** `_extract_ids` (norm_probes.py `:465-476`) stays where it is. It scans a whole
prose *line* for every citation (`findall`), which is what `norm_probes.py`'s Direction-line
scanning needs; `buildplan_refs.py` needs the opposite operation — classify one already-isolated
backticked token — so it calls `BACKLOG_ID_RE.fullmatch(token)` / `ISSUE_REF_RE.fullmatch(token)`
directly (§3) rather than reusing a line-scanning helper built for a different shape of input.
`release_readiness.py`'s independent `_ITEM_ID_RE` (`:49`) is left untouched — folding it into
this consolidation is issue #336 itself, not this item (Scope-out, unchanged from requirements).

## 3. `buildplan_refs.py` — extraction (BLD5V8F-1, 4, 6)

`_parse_build_plan_chunk_refs`'s return dict gains a third key, and the match loop gains one
branch. The existing `file_paths` branch is untouched — new code is additive, guarded by the
`_looks_like_file_path` check already there:

```python
# plugin/lib/buildplan_refs.py — _parse_build_plan_chunk_refs, ~:1782 onward

result: dict = {"file_paths": [], "backlog_refs": [], "error": None}
if plan_path is None:
    plan_path = resolve_build_plan_path(prawduct_dir)
if not plan_path.is_file():
    result["error"] = f"missing build-plan: {plan_path}"
    return result
try:
    content = plan_path.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError) as exc:
    result["error"] = f"unreadable build-plan: {exc}"
    return result

section = _chunk_section_lines(content, chunk_id)
gap = chunk_section_gap(chunk_id, section)
if gap:
    result["error"] = gap
    return result
section_lines = section.lines

# BLD5V8F-4: a no-op read on a markdown-backend repo — gates the whole
# backlog-ref half of the scan below. Read once per call, not once per token;
# `read_str_yaml_key` is a small file read, but the loop below can run over
# every backticked token in a chunk section.
backlog_scope = read_str_yaml_key(prawduct_dir / "project-state.yaml", "backlog_service_repo")

forward_refs: set[str] = { ... }   # unchanged
completed = _completed_chunk_ids(content)   # unchanged
gone_refs: set[str] = { ... }      # unchanged

seen: set[tuple[str, int]] = set()
seen_backlog: set[tuple[str, int]] = set()
section_texts = [text for _, text in section_lines]
for index, (line_num, line) in enumerate(section_lines):
    if waivers.waives(section_texts, index, "prawduct/chunk-ref-missing"):
        continue
    for match in _BUILD_PLAN_PATH_RE.finditer(line):
        path_part = _ref_path_part(match.group(1))
        if _looks_like_file_path(path_part):
            if path_part in forward_refs or path_part in gone_refs:
                continue
            key = (path_part, line_num)
            if key in seen:
                continue
            seen.add(key)
            result["file_paths"].append({"line_num": line_num, "ref": path_part})
            continue
        if not backlog_scope:
            continue
        if path_part in forward_refs or path_part in gone_refs:
            continue
        if core.BACKLOG_ID_RE.fullmatch(path_part) or core.ISSUE_REF_RE.fullmatch(path_part):
            key = (path_part, line_num)
            if key in seen_backlog:
                continue
            seen_backlog.add(key)
            result["backlog_refs"].append({"line_num": line_num, "ref": path_part})
return result
```

**Why `fullmatch`, not the `findall` `_extract_ids` uses.** `path_part` is already one isolated
token — `_BUILD_PLAN_PATH_RE` extracted it from between backticks, and `_ref_path_part` reduced it
— so classifying it is "is this token entirely a citation," not "find every citation somewhere in
this text." `findall` on an already-isolated token and `fullmatch` agree on every case that
matters here, but `fullmatch` is the correct operation to reach for, not an equivalent
substitution, and does not require constructing a throwaway list to test membership.

**Why the `forward_refs`/`gone_refs` check is repeated rather than hoisted above the
`_looks_like_file_path` branch.** BLD5V8F-6 requires the exemption to apply to both kinds, and
both sets are plain string sets keyed on the reduced token — nothing about them is
file-path-specific (they are built from `` new `X` ``/`` gone `X` `` qualifier lines by the same
`_ref_path_part` reduction applied to citations). Repeating the two-line check rather than
hoisting it above the branch keeps the existing `file_paths` branch's code and behavior
byte-for-byte unchanged, which matters more here than four saved lines: a hoist that
subtly reordered when `_looks_like_file_path` runs relative to the exemption check would be a
behavior change to a heavily-commented, already-correct function for a refactor with no
requirement behind it.

**Why extraction — not just verification — is gated on `backlog_scope`.** BLD5V8F-4 says a
markdown-backend repo gets "nothing new," not just "nothing new that fails." Extracting into
`backlog_refs` unconditionally and gating only at verification time would still change
`result["backlog_refs"]` from absent to `[]` for every repo, and any future caller iterating
`result.items()` (none exist today, but the shape is now public API surface) would see a new key.
Gating extraction itself keeps the dict's shape for a markdown-backend repo identical in spirit to
today's two-key dict — a third key present but always empty is close enough that this is a
judgment call, not a hard requirement, but it costs nothing here since the scope read already has
to happen before verification anyway (§4).

## 4. `buildplan_refs.py` — verification (BLD5V8F-3, 5)

**Rejected alternative: change `_verify_chunk_refs`'s return type to `(missing, unchecked)`.**
This was the natural first reading of BLD5V8F-5's "a new field... vs. reusing `error`" — a second
return value alongside `missing`. Re-checked against the current test suite:
`tests/test_build_plan_resolution.py` has ~25 assertions of the shape
`_verify_chunk_refs(project, refs) == []` or `[m["ref"] for m in _verify_chunk_refs(...)]`, and
both production callers (`prawduct-hook:4038`, `record_lint.py:806`) bind the result to `missing`
and iterate it directly. A tuple return would require a mechanical edit to every one of those ~25
assertions plus both callers, for a feature that touches maybe 3 of them. That is a large,
noise-generating diff for an item whose own Scope-out says "this item adds a second, parallel
extraction pass" — changing what every existing test asserts about the *first* pass is the
opposite of parallel. **Chosen instead: the return type stays `list[dict]`.** A
`backlog_ref_unchecked` entry is a member of that same list, distinguished by `kind` — "distinct"
(BLD5V8F-5) is satisfied by the `kind` value and by both callers branching on it (§5), not by a
different container.

```python
# plugin/lib/buildplan_refs.py — _verify_chunk_refs, ~:2183 onward

def _verify_chunk_refs(project_dir: Path, refs: dict) -> list[dict]:
    """Verify each file-path and backlog-ref citation names something real.

    Returns a list of ``{"kind", "ref", "line_num", "reason"}`` for missing
    entries, plus at most one ``kind: "backlog_ref_unchecked"`` entry (``ref``
    and ``line_num`` both ``None``) when the backlog cache could not answer at
    all — a distinct, never-a-pass condition callers must not print or count
    as a missing deliverable (BLD5V8F-5). Empty list = everything resolved
    (or there was nothing to check).
    ...
    """
    missing: list[dict] = []
    ref_root = _ref_root(project_dir)
    for entry in refs.get("file_paths", []):
        ref = entry["ref"]
        target = project_dir / ref
        if not target.exists():
            if ref_root is not None and (ref_root / ref).exists():
                continue
            if gitstate.git_path_is_ignored(project_dir, ref):
                continue
            missing.append({
                "kind": "file_path", "ref": ref, "line_num": entry["line_num"],
                "reason": "file does not exist",
            })

    backlog_refs = refs.get("backlog_refs", [])
    if backlog_refs:
        prawduct_dir = gitstate.get_prawduct_dir(project_dir)
        scope = read_str_yaml_key(prawduct_dir / "project-state.yaml", "backlog_service_repo")
        if scope:
            from .backlog import cachequery  # noqa: PLC0415 — lazy: only the post-cutover arm
            default_owner = scope.split("/", 1)[0] if "/" in scope else None
            now = datetime.now(timezone.utc)
            for entry in backlog_refs:
                result = cachequery.resolve(
                    project_dir, scope=scope, id_raw=entry["ref"],
                    now=now, default_owner=default_owner,
                )
                if result.get("status") != "ok":
                    err = result.get("error") or {}
                    missing.append({
                        "kind": "backlog_ref_unchecked", "ref": None, "line_num": None,
                        "reason": err.get("message") or err.get("code")
                        or "backlog cache unavailable",
                    })
                    break  # every remaining lookup fails identically; report once, not N times
                if not result["data"].get("resolved"):
                    missing.append({
                        "kind": "backlog_ref", "ref": entry["ref"], "line_num": entry["line_num"],
                        "reason": result["data"].get("reason") or "does not resolve in the backlog",
                    })
    return missing
```

**Why `scope` is re-read here rather than threaded from `_parse_build_plan_chunk_refs`.** The two
functions are already independently callable with independently-supplied arguments (`project_dir`
vs. `prawduct_dir` — not even the same directory object), and both existing call sites invoke them
as two separate steps with a `refs["error"]` check between. Re-deriving `scope` costs one more
small file read, guarded by `if backlog_refs:` so it never runs when there is nothing to verify
(including every markdown-backend repo, since extraction already left the list empty there) — a
smaller, more local coupling than passing scope across a function boundary that has none today.

**Why `break` on the first `_CacheUnanswerable`-equivalent rather than trying each ref.** Mirrors
`norm_probes._scan_direction_citations` (`:640-654`), which does exactly this — stop at the first
unanswerable result rather than call the store once per citation, because an unreadable/unsynced
cache answers every subsequent lookup identically. `norm_probes.py`'s own `_CacheUnanswerable`
exception is not imported here: its docstring (`:498`) states "it never leaves this module," and
`cachequery.resolve`'s own `{"status": ..., "error": ...}` envelope already carries everything
needed to build the `backlog_ref_unchecked` entry without raising through a module boundary that
document says stays closed. This is the two modules independently wrapping the same public
`cachequery.resolve` primitive their own way, not a duplicated copy of `_resolve_citation`'s ~15
lines of docstring and reasoning — the wrapping here is 6 lines because it only needs one of
`_resolve_citation`'s two jobs (surface unavailability; the "resolved but dead" question
`_resolve_citation` also answers has no analog for a build-plan citation).

**Why `result["data"].get("reason")` over the generic string.** `cachequery.resolve` returns a
non-`None` `reason` exactly when the id's *spelling* was the problem (`nid.ok` is false —
`cachequery.py:722-727`), as opposed to a well-formed id that simply names nothing. Surfacing
that message when present (a malformed id) rather than always saying "does not resolve" gives a
chunk author "that's not a valid id shape" instead of "no such item" for the one case where they
differ — no new code path, just reading a field `resolve`'s response already carries.

## 5. Caller updates (BLD5V8F-8)

Both callers split `missing` into the unchecked entry (if any) and everything else, and route
the unchecked entry through their own existing "could not run" channel rather than their
missing-deliverable channel.

**`prawduct-hook:cmd_verify_chunk_refs`** (`:4038-4048`):

```python
missing = _buildplan_refs()._verify_chunk_refs(project_dir, refs)
if missing:
    for m in missing:
        if m["kind"] == "backlog_ref_unchecked":
            print(f"cannot-verify: backlog-ref check could not run: {m['reason']}", file=sys.stderr)
        else:
            print(
                f"missing-ref: {m['ref']} (line {m['line_num']}, {m['kind']}): {m['reason']}",
                file=sys.stderr,
            )
    return 1
count = len(refs["file_paths"]) + len(refs.get("backlog_refs", []))
print(f"ok: chunk {chunk_id} — {count} ref(s) verified")
return 0
```

Still returns 1 whenever `missing` is non-empty, unchecked-only included — matching the function's
own documented contract ("Exit 1 = at least one ref is missing, **or the gate cannot be
evaluated**," `:3989-3990`) without adding a new branch to the exit-code decision, only to the
print loop. The closing count line changes from "file ref(s)" to "ref(s)" and sums both lists —
reached only when `missing` is empty, so every backlog ref counted there did resolve.

**`record_lint.py:_check_chunk_refs`** (`:806-815`), which builds `findings` for the Critic and a
separate `gap` string for "could not run":

```python
missing = buildplan_refs._verify_chunk_refs(project_dir, refs)
unchecked = [m for m in missing if m["kind"] == "backlog_ref_unchecked"]
findings = [
    _finding(
        "chunk-ref-missing", f"chunk {chunk_id}", entry.get("line_num"),
        f"declared deliverable `{entry['ref']}` {entry['reason']}",
    )
    for entry in missing if entry["kind"] != "backlog_ref_unchecked"
]
assumptions = []
if assumed:
    assumptions.append(...)   # unchanged
if plan.source == buildplan_refs.SOURCE_ACTIVE_PLAN and plan.gap:
    assumptions.append(plan.gap)   # unchanged
for m in unchecked:
    assumptions.append(f"backlog-ref check could not run: {m['reason']}")
gap = None
if assumptions:
    gap = f"chunk-ref-missing graded chunk {chunk_id} of {plan.rel}: " + "; ".join(assumptions)
return findings, gap, chunk_id, plan.rel
```

This reuses the existing `assumptions`/`gap` join verbatim rather than adding a third return
channel — an unchecked backlog-ref pass is exactly the same *kind* of fact as "the chunk id was
inferred" or "the plan pointer carries a gap": a caveat on what was graded, not a defect the
Critic should quote as a finding. `chunk-ref-missing unchecked — ...` (the exact phrasing used a
few lines above, `:802-805`, for the whole-check-could-not-run case) is deliberately not reused
verbatim here — that phrasing means "nothing below this point was graded," which is false when
`file_paths` were graded and only the backlog half was unchecked; the new sentence names the
narrower scope instead of borrowing a wider one.

## 6. `norm_probes.py` — housekeeping only

No behavioral change. `_BACKLOG_ID_RE`/`_ISSUE_REF_RE` (`:162,176`) become imports from `core.py`
(§2); `_extract_ids`, `_resolve_citation`, `_CacheUnanswerable`, and every probe built on them are
untouched. A parity test (§7) pins that the aliased objects are identical to `core.py`'s, mirroring
this codebase's existing convention for an intentional inline-mirror-vs-shared-import split
(`core.py:293-295`'s comment on `read_bool_yaml_key` vs. `prawduct-hook`'s own inline copy is the
precedent for "pin the relationship with a test, don't just trust the diff").

## 7. Files touched

| File | Change |
| --- | --- |
| `plugin/lib/core.py` | new `BACKLOG_ID_RE`, `ISSUE_REF_RE`, `import re` (§2) |
| `plugin/lib/norm_probes.py` | `_BACKLOG_ID_RE`/`_ISSUE_REF_RE` become imports from `core` (§2, §6) |
| `plugin/lib/buildplan_refs.py` | `_parse_build_plan_chunk_refs` gains `backlog_refs` extraction (§3); `_verify_chunk_refs` gains backlog-ref resolution (§4); new `from datetime import datetime, timezone` import |
| `plugin/bin/prawduct-hook` | `cmd_verify_chunk_refs`'s print loop and closing count (§5) |
| `plugin/lib/record_lint.py` | `_check_chunk_refs`'s findings/gap split (§5) |
| `tests/` | new coverage — see §8 |

## 8. Testing strategy → acceptance mapping

- **`_parse_build_plan_chunk_refs` extraction** (`tests/test_build_plan_resolution.py`, beside the
  existing `file_paths` coverage): a chunk citing `` `#249` `` or `` `owner/repo#249` `` or a PFX
  id, with `backlog_service_repo` set, lands in `backlog_refs`; the same chunk with
  `backlog_service_repo` unset produces `backlog_refs == []` (BLD5V8F-4, and proves the gate is
  extraction-time, not just verification-time); a `` new `#249` `` declaration exempts a later
  `#249` citation the same way `new `path.py`` already does (BLD5V8F-6); a waived line
  (`prawduct:allow prawduct/chunk-ref-missing`) produces no `backlog_refs` entry either
  (BLD5V8F-6, the pragma is line-scoped and already runs before the kind branch).
- **`_verify_chunk_refs` resolution** (same file, monkeypatching
  `buildplan_refs.cachequery.resolve` — targeted unit coverage of the three branches this
  function's own logic adds, distinct from `test_backlog_cachequery.py`'s real-cache-fixture
  coverage of `resolve` itself, which this item does not re-test): a resolvable id produces no
  `missing` entry; an id resolving `resolved: False` produces one `kind: "backlog_ref"` entry,
  using the resolver's own `reason` when present; a `status != "ok"` response produces exactly one
  `kind: "backlog_ref_unchecked"` entry even when three backlog refs were queued, proving the
  break-on-first-failure short-circuit (BLD5V8F-5); a chunk with `backlog_refs == []` (gated off
  or none cited) calls `cachequery.resolve` zero times — proves BLD5V8F-4's "nothing new" is
  unconditional, not merely untested, the same discipline `623-design.md §7` used for its own
  no-op gate.
- **`cmd_verify_chunk_refs` regression** (`tests/test_hook_cli_regressions.py`, beside the existing
  `cannot-verify:` distinctness test named in that file's own module docstring): a
  `backlog_ref_unchecked` entry prints as `cannot-verify: backlog-ref check could not run: ...`,
  never as `missing-ref:`; exit is still 1; the closing `ok:` line's count includes resolved
  backlog refs.
- **`_check_chunk_refs` regression** (`tests/test_record_lint.py`): an unchecked backlog ref
  contributes to `gap`, not to `findings`; a real missing backlog ref contributes a
  `chunk-ref-missing` finding phrased identically to a missing file-path finding (BLD5V8F-8's "no
  other caller-specific `kind` handling").
- **`core.py`/`norm_probes.py` parity** (`tests/test_norm_probes.py`): `norm_probes._BACKLOG_ID_RE
  is core.BACKLOG_ID_RE` and the `_ISSUE_REF_RE` sibling — pins the alias relationship (§6) so a
  future edit to one copy cannot silently diverge from the other before this consolidation is
  itself finished.
- **Symbol citations unaffected** (BLD5V8F-7): existing `path::symbol` tests in
  `tests/test_build_plan_resolution.py` are re-run unmodified as a regression guard; no new symbol
  test is added, since none is claimed.

## 9. Scope-out (this item)

Carries the requirements doc's scope-out list forward verbatim: symbol (`path::symbol`) matching;
resolving issue #336 itself (this item avoids adding a *third* copy of the regex pair by
consolidating two call sites into one shared definition, but `release_readiness.py`'s independent
`_ITEM_ID_RE` is untouched — #336 remains open); markdown-backend backlog-id verification; any
change to `_looks_like_file_path`'s carveouts; a `backlog_id_pattern` project-state preference.

**Added by this design pass, carried to implementation:** none of the requirements doc's
deferrals needed a *new* deferral — BLD5V8F-5's wiring question (§4) and Decision 2's shared-home
question (§2) are both resolved here, not pushed further.

## 10. Evidence / references

- `documentation/issues/275-requirements.md` — Decisions 1–5, requirements BLD5V8F-1–8, this
  design's starting point; names the two questions (§2, §4) this document resolves.
- `plugin/lib/buildplan_refs.py:1750-1874` (`_parse_build_plan_chunk_refs`), `:2183-2219`
  (`_verify_chunk_refs`), `:1272-1329` (`_looks_like_file_path`), `:1332-1350`
  (`_ref_path_part`), `:1696-1717` (`_qualifier_scope_lines`), `:2145-2180` (`REF_ROOT_KEY`/
  `_ref_root`, the sibling `read_str_yaml_key(prawduct_dir / "project-state.yaml", ...)` idiom §3
  and §4 both reuse), `:56-58` (existing `core`/`read_str_yaml_key` imports).
- `plugin/lib/norm_probes.py:156-176` (`_BACKLOG_ID_RE`/`_ISSUE_REF_RE`, moving per §2),
  `:465-476` (`_extract_ids`, staying per §2), `:495-576` (`_CacheUnanswerable`/
  `_resolve_citation`, the pattern §4 independently mirrors rather than imports, and why),
  `:605-654` (`_live_scope`, `_scan_direction_citations`'s break-on-first-`_CacheUnanswerable`,
  the precedent §4's `break` reuses).
- `plugin/lib/backlog/cachequery.py:638-778` (`resolve`, its resolution order, and the
  `{"requested", "resolved", "id", "via", "reason", ...}` payload shape §4 reads), `:162-188`
  (`_serve`, the `{"status", "data"}` / `{"status", "error"}` envelope).
- `plugin/lib/backlog/core.py:46-63` (`ok`/`error`, the envelope constructors `_serve` calls).
- `plugin/bin/prawduct-hook:3985-4048` (`cmd_verify_chunk_refs`, its `refs["error"]` channel at
  `:4021-4037` and closing count at `:4046`, both cited to show current, not requirements-pass,
  line numbers).
- `plugin/lib/record_lint.py:717-834` (`_check_chunk_refs`), `:798-805` (the existing
  `chunk-ref-missing unchecked — ...` whole-check-failed phrasing §5 deliberately does not reuse
  for the narrower unchecked-backlog-half case).
- `tests/test_build_plan_resolution.py` — ~25 existing `_verify_chunk_refs(...)` call sites,
  the grounding fact behind §4's rejected-alternative note.
- `tests/test_backlog_cachequery.py:630-870` — existing `cachequery.resolve` test fixture
  conventions (real on-disk cache, not a monkeypatch), which §8 deliberately does not duplicate
  for `_verify_chunk_refs`'s own narrower branch coverage.
- `documentation/issues/623-design.md` — the sibling design doc §4/§7's "prove the no-op is
  unconditional, not merely untested" testing discipline, reused in §8.
- Issue #275 — problem statement, proposed change, and acceptance criteria this document and the
  requirements doc jointly ground.
