# Issue #275 — Build-plan: Extend `verify-chunk-refs` Beyond File Paths: Requirements

`status: draft · stage: requirements · area: build-plan · added: 2026-08-28 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/275`

Related: `.prawduct/artifacts/buildplan-chunk-refs-discovery.md` (BLD-ZQ2V/BLD-5R7K, ruled
2026-07-29) grounds the sibling chunk-scoping question this item's extraction sits inside, but
explicitly scopes symbol/backlog-ID verification out as "already deferred, unchanged" — confirming
this item is still the open half. Issue #336 ("a standardized id pattern keeps acquiring narrow
copies") is a live coupling this item's design must not worsen.

## Problem

v1.4 Chunk 02 shipped `verify-chunk-refs` with file-path verification only; the original plan also
called for symbol and backlog-ID verification, both deferred at the time. The backlog-ID half's
deferral reason no longer holds: this repo had no formal backlog ids in 2026-05, then gained
`[PFX-XXXX]` ids, and has since cut over to a GitHub Issues backend where the canonical id is
`owner/repo#number`. A build-plan chunk that cites a backlog id — real or mistyped — gets no
verification today.

## Grounding facts

Re-verified against the current tree (2026-08-28):

- `_parse_build_plan_chunk_refs` (`plugin/lib/buildplan_refs.py:1626-1750`) extracts only
  `file_paths`. Its own docstring already states this in the present tense: "Symbol and backlog-ID
  verification remain deferred" (`:1650`).
- **A backlog citation in a chunk is invisible to the gate today, not merely unverified.**
  `_looks_like_file_path` (`:1268-1326`) excludes any token containing `#` from file-path
  classification (`:1320-1321`, the `owner/repo#12` / issue-anchor carveout) — correctly, since
  such a token never named a file. But nothing else extracts it either, so a chunk citing
  `` `owner/repo#249` `` or `` `#249` `` produces zero refs of any kind: a typo'd id passes the
  gate exactly as a correct one does.
- **The extraction and resolution machinery this item needs already exists, one module over, just
  not wired to build-plan parsing:**
  - `plugin/lib/norm_probes.py:162` `_BACKLOG_ID_RE` (`[A-Z]{2,4}-[A-Z0-9]{4}`, the PFX shape) and
    `:176` `_ISSUE_REF_RE` (`(?:[\w.-]+/[\w.-]+)?#\d+`, bare or `owner/repo`-qualified) — the two
    id spellings a citation can take, pre- and post-Issues-cutover.
  - `:465` `_extract_ids` — pulls both spellings from a line, de-duplicated, PFX-first.
  - `:552-577` `_resolve_citation`, calling `backlog.cachequery.resolve`
    (`plugin/lib/backlog/cachequery.py:638`) — resolves an id (stored alias, live, untagged
    historical, or `superseded_by` redirect) against the synced backlog cache. A miss is a
    legitimate `resolved: false` answer, not an error; an unreadable or unsynced cache raises
    `_CacheUnanswerable` (`:495`) rather than silently reporting a pass. `_resolve_citation`'s own
    import comment marks this "only the post-cutover arm" — it presumes `backlog_service_repo` is
    set.
- **Reusing that machinery matters beyond convenience: a third, independent id-shape regex would
  worsen an open, named problem.** `release_readiness.py:49`'s `_ITEM_ID_RE` and
  `norm_probes.py:162`'s `_BACKLOG_ID_RE` are already two separate copies of the same PFX shape —
  exactly the pattern issue #336 tracks as unresolved. A hand-rolled fourth copy in
  `buildplan_refs.py` adds to that debt rather than working around it.
- **Extending the return shape is low-risk: both existing callers are already generic over
  `kind`.** `_parse_build_plan_chunk_refs` has exactly two callers —
  `plugin/bin/prawduct-hook:3720` (`cmd_verify_chunk_refs`, the Critic Goal-2 gate) and
  `plugin/lib/record_lint.py:769` (`verify-records`). Both iterate `_verify_chunk_refs`'s `missing`
  list and print `{kind, ref, line_num, reason}` without assuming `file_path` is the only `kind`
  (`prawduct-hook:3736-3742`; `record_lint.py:780-785`). The one line needing an edit is
  `prawduct-hook:3746`, `count = len(refs["file_paths"])`, which currently counts only the
  file-path half for the closing `ok:` message.
- **Symbol verification's deferral rationale is unchanged.** The original reason — `parse_func` in
  prose vs. an implementation's `_parse_func`, so a strict grep produces false positives without
  fuzzy matching — is restated in the module docstring today (`:1334-1335`, "verified by its file
  half; symbol verification stays deferred") and in this issue's own Scope-out. Nothing in the
  current tree changes that calculus; the issue's own Evidence section confirms only the
  backlog-ID half is "newly actionable."

## Decisions

1. **Scope this item to backlog-ID verification only; re-defer symbol verification, unchanged.**
   The issue's Evidence section says the backlog-ID half's blocking reason changed twice (no
   formal ids → `[PFX-XXXX]` → Issues-backend `owner/repo#N`) while the symbol half's blocking
   reason (fuzzy matching) never changed. Bundling a still-blocked half into this item's acceptance
   would either ship weak, false-positive-prone symbol matching against the item's own scope-out,
   or hold the now-actionable half hostage to a problem this item cannot solve. A later item can
   reopen symbol matching against real fuzzy-match tooling, as the original 2026-05-18 deferral
   already anticipated.

2. **Reuse `norm_probes`'s id regexes and `cachequery.resolve`; no new `backlog_id_pattern`
   preference.** The issue's proposed change predates the Issues cutover and imagined a
   project-configurable regex for an as-yet-unspecified convention. That convention is now fixed
   and cross-repo — PFX-style or `(owner/repo)?#N` — and both spellings are already extracted by
   one function and resolvable through one cache query. A configurable pattern would both
   duplicate `_BACKLOG_ID_RE`/`_ISSUE_REF_RE` (worsening #336) and reopen a question the repo has
   already answered. The design pass should place the extraction regexes somewhere both
   `norm_probes` and `buildplan_refs` import rather than adding a third copy of either — narrower
   than resolving #336 itself, but this item must not make that open problem worse.

3. **Gate backlog-ref verification on `backlog_service_repo` being set — a no-op on a
   markdown-only repo, mirroring #623's own `backlog_service_repo` skip rule (its Decision 5).**
   `cachequery.resolve`'s post-cutover-only import guard already presumes this precondition; a
   markdown-backend repo has no cache to query, and reporting "unchecked" everywhere would be
   noise on every such repo forever.

4. **This item adds a second, parallel extraction pass; it does not touch
   `_looks_like_file_path`'s existing carveouts.** The `#` exclusion (and every other carveout —
   glob, URL, placeholder, git-ref-prefix) stays exactly as documented. A token that is neither
   path-shaped nor backlog-id-shaped remains unchecked, exactly as before this item.

5. **A cache-unavailable answer (`_CacheUnanswerable`) is reported distinctly from a genuinely
   missing id — never silently a pass, never conflated with a real miss.** This mirrors
   `refs["error"]`'s existing "cannot-verify, not a finding" channel and the BLD-5J8N concern
   `cmd_verify_chunk_refs` already names in its own comments: a can't-parse exit dismissed as noise
   would mask a real missing-ref finding. The exact wiring (a new field alongside `file_paths` /
   `backlog_refs`, vs. reusing `error`) is a design-stage question; what's pinned here is the
   posture — unreadable cache reports "unchecked," not "passed," and not "missing."

## Requirements

MUST unless marked SHOULD.

- **BLD5V8F-1** `_parse_build_plan_chunk_refs` additionally extracts `backlog_refs`: every
  citation-shaped token in a chunk section matching `_BACKLOG_ID_RE` or `_ISSUE_REF_RE`, returned
  alongside the existing `file_paths` list in the same dict, using the module's existing
  backtick/line-scan convention.
- **BLD5V8F-2** Extraction reuses `norm_probes`'s existing id regexes (or a shared successor both
  modules import), not a new pattern local to `buildplan_refs.py` (Decision 2).
- **BLD5V8F-3** Each extracted backlog ref is resolved via `backlog.cachequery.resolve`, scoped to
  this repo's `backlog_service_repo`; an id that resolves to no real item (`resolved: false`) is
  reported as a missing-ref finding — `kind: "backlog_ref"` — in the same `{line_num, ref, reason}`
  shape `_verify_chunk_refs` already returns for `file_path` misses.
- **BLD5V8F-4** Backlog-ref verification is a no-op — extracts and reports nothing new — when
  `backlog_service_repo` is unset (Decision 3), read via the existing `read_str_yaml_key` helper.
- **BLD5V8F-5** A `_CacheUnanswerable` result is surfaced as a distinct cannot-verify condition,
  never folded into the missing-ref list and never silently treated as a pass (Decision 5).
- **BLD5V8F-6** The `new`-qualifier forward-reference exemption and the
  `prawduct/chunk-ref-missing` waiver pragma — both already honored for `file_paths` — apply
  identically to `backlog_refs`: a plan legitimately cites a not-yet-filed follow-up id the same
  way it cites a not-yet-created file.
- **BLD5V8F-7** Symbol (`path::symbol`) verification remains deferred, unchanged from its current
  behavior — verified by its file half only (Decision 1).
- **BLD5V8F-8** Both existing callers (`cmd_verify_chunk_refs`, `verify-records`) surface
  backlog-ref findings through their existing generic missing-ref reporting; `prawduct-hook:3746`'s
  closing count is updated to include `backlog_refs`, and no other caller-specific `kind` handling
  is added.

## Acceptance

- [ ] A build-plan chunk citing a backlog id (PFX-style or `(owner/repo)?#N`) that does not
      resolve in the synced backlog cache is reported as a missing ref.
- [ ] A build-plan chunk citing a real, resolvable backlog id is not reported.
- [ ] Nothing changes for a markdown-backend repo (`backlog_service_repo` unset) — zero new output.
- [ ] An unsynced/unreadable cache is reported distinctly from a missing id — never a silent pass,
      never indistinguishable from a genuine miss.
- [ ] Symbol citations remain unaffected — no new checking, no new false positives.
- [ ] `verify-chunk-refs` and `verify-records` both surface backlog-ref findings without additional
      per-caller wiring beyond the one count-line update.

## Scope-out (this item)

- Symbol (`path::symbol`) matching — re-deferred (Decision 1); still blocked on fuzzy-match
  tooling, unchanged from the original 2026-05-18 deferral.
- Resolving issue #336 (the standardized id-pattern problem) itself — this item must not add a
  fourth narrow copy of the id regex, but consolidating the existing copies is separate work.
- Markdown-backend (pre-cutover) backlog-id verification — no cache exists to resolve against;
  scoped identically to #623's own `backlog_service_repo`-gated skip.
- Any change to `_looks_like_file_path`'s existing carveouts (the `#` exclusion, the
  git-ref-prefix exclusion, etc.) — this item adds a second, parallel extraction pass, not a
  change to the first.
- A new `project-state.yaml` preference for id shape (`backlog_id_pattern`, as the original issue
  text proposed) — superseded by Decision 2; the shape is fixed, not per-product configurable.

## Evidence / references

- `plugin/lib/buildplan_refs.py:1626-1750` — `_parse_build_plan_chunk_refs`, the function this
  item extends; its docstring already states "Symbol and backlog-ID verification remain deferred"
  (`:1650`).
- `plugin/lib/buildplan_refs.py:1268-1326` — `_looks_like_file_path`, whose `#` carveout
  (`:1320-1321`) is why a backlog citation currently produces no ref at all.
- `plugin/lib/buildplan_refs.py:2059-2095` — `_verify_chunk_refs`, the missing-ref reporting
  function both callers share; already generic over `kind`.
- `plugin/lib/norm_probes.py:162,176` — `_BACKLOG_ID_RE`, `_ISSUE_REF_RE`, the two id spellings to
  reuse.
- `plugin/lib/norm_probes.py:465-476` — `_extract_ids`, the existing dual-spelling extraction to
  reuse or share.
- `plugin/lib/norm_probes.py:495-577` — `_CacheUnanswerable` and `_resolve_citation`, the existing
  `cachequery.resolve` call and cache-unavailable handling to mirror.
- `plugin/lib/backlog/cachequery.py:638-720` — `resolve`, the alias-table resolution this item
  calls.
- `plugin/bin/prawduct-hook:3685-3750` — `cmd_verify_chunk_refs`, one of the two callers; line
  `:3746` (`count = len(refs["file_paths"])`) is the one line needing an edit.
- `plugin/lib/record_lint.py:755-785` — the other caller (`verify-records`), already generic over
  the `missing` dict shape.
- Issue #336 — "a standardized id pattern keeps acquiring narrow copies," the open coupling
  Decision 2 avoids worsening.
- `.prawduct/artifacts/buildplan-chunk-refs-discovery.md` — the sibling discovery doc
  (BLD-ZQ2V/BLD-5R7K) that explicitly scoped symbol/backlog-ID verification out as "already
  deferred, unchanged," confirming this item is still the open half.
- Issue #275 — problem statement, proposed change, and original deferral evidence this document
  grounds.
