# Issue #197 — Terminal-Markdown Backlog State: Design

`status: draft · stage: design · area: backlog-service · added: 2026-08-14 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/197`

Builds on `documentation/issues/197-requirements.md` (TM1–TM7, the Decision section). That document
settled the product question — terminal-markdown is a first-class state, declared as a committed
`backlog_backend: markdown` scalar, silencing only `probe_migration_required` — and deliberately left
three things to design: the exact code change, the CLI/skill surface for setting the field (TM5), and
the "why" capture mechanism (TM7). This document resolves all three.

## Summary of what ships

1. **TM1, TM6** — a new top-level `backlog_backend` scalar in `project-state.yaml`, documented in
   `plugin/templates/project-state.yaml`'s existing BACKLOG block. Only defined value: `markdown`.
2. **TM2, TM4** — `probe_migration_required` (`plugin/lib/backlog_probes.py`) gains one new
   early-return line, ordered *after* the existing `post_cutover(state)` check — which is what gives
   TM4's precedence rule (`backlog_service_repo` beats a stale `backlog_backend: markdown`) for free,
   with no separate conflict-resolution code.
3. **TM3** — no code change. The other three `post_cutover()`-gated probes, and `norm_probes`' two
   backend-selecting readers, are confirmed unaffected by inspection (see "Why no change" below).
4. **TM5, TM7** — a new `/prawduct:backlog decline-migration <reason>` subcommand, prose-only (no
   new `prawduct-hook` command), following the same "skill edits `project-state.yaml` directly"
   pattern `migrate`'s step 5 already uses for `backlog_format_version`. The reason is captured as a
   YAML comment written directly above the field — the same convention already visible above
   `backlog_service_repo` in a cut-over product's `project-state.yaml`.

## Decisions resolved

### Where the new resolution condition lives (TM2)

`probe_migration_required`'s current body:

```python
def probe_migration_required(state: ProjectState, codebase: Codebase):
    if post_cutover(state):
        return []
    text = _read_text(_backlog_path(codebase))
    ...
```

Gains one line, directly under the existing `post_cutover` check:

```python
    if post_cutover(state):
        return []
    if state.get("backlog_backend") == "markdown":
        return []
    text = _read_text(_backlog_path(codebase))
    ...
```

This is deliberately **not** folded into `post_cutover()` itself — the requirements doc's "Scope of
the silence" section is explicit that `post_cutover()` is shared by four other call sites
(`legacy-backlog-format`, `legacy-section-schema`, `backlog-overdue-grooming`, `norm_probes`'
`revisit-due`, plus `dead-why`/`stalled-transition`'s backend-selection use), and widening it would
silence all of them for a product that has merely declared it will never migrate — exactly the
"second-class, worse-nudged" outcome TM3 rules out. A second, narrower predicate inline in the one
probe it applies to is the smallest change that satisfies TM2 without touching any of the other five
readers.

**Why checking `post_cutover` first gives TM4 for free.** `probe_migration_required` already returns
on the first true condition. Once `backlog_service_repo` is set, `post_cutover(state)` is `True` and
the function returns before ever reading `backlog_backend` — so a stale `backlog_backend: markdown`
left over from before a later migration is simply never consulted. No `if both set, prefer X`
branch is needed; the existing early-return shape already encodes "cutover wins" as an ordering
fact, not a new comparison. This is the same reasoning the module's own `post_cutover` docstring
already applies to its other callers (checked first, retire-or-select second) — TM4 is a
consequence of that established shape, not a new one.

### Why no change is needed elsewhere (TM3)

Traced each of the requirements doc's named siblings against the current code (all in
`plugin/lib/backlog_probes.py` and `plugin/lib/norm_probes.py`) to confirm "unaffected" is actually
true today, not just asserted:

- `probe_legacy_backlog_format`, `probe_legacy_section_schema`, `probe_overdue_grooming` — each
  guards on `post_cutover(state)` alone (unchanged by this item) and has no reference to
  `backlog_backend` anywhere in its body. A terminal-markdown product still gets these nudges about
  the file it has committed to keeping, exactly as TM3 requires.
- `norm_probes.probe_revisit_due` — same `post_cutover()` guard, no change.
- `dead-why` / `stalled-transition` (`norm_probes.py`) — read `post_cutover()` to **choose** a
  reader (markdown file vs. backlog cache), not to retire. A terminal-markdown product never
  satisfies `post_cutover()`, so these two keep reading the markdown file, which remains that
  product's only backlog — correct with no change, and not something `backlog_backend` needs to
  influence.

No test in `tests/test_backlog_probes.py` or `tests/test_norm_probes.py` currently exercises
`backlog_backend`, so the test plan below adds roster-level coverage proving these stay silent on
the new field rather than relying on code inspection alone.

### The CLI/skill surface (TM5)

A new subcommand, **not** added to the summary/menu list (`SKILL.md`'s "(no args)" section) —
declining migration forever is a rare, one-time, high-consequence decision, unlike the everyday
verbs already listed there (`pick`, `add`, `find`, `list`, `update`, `dedup`, `import`, `migrate`).
Keeping it out of the default menu matches how `scrub` (also high-consequence, also one-time) is
documented as its own subcommand section without appearing in the menu enumeration.

`plugin/skills/backlog/SKILL.md`, a new subsection after `migrate` (mirrors that subcommand's own
"read the precondition, write the field, report" shape) and before `import`:

```markdown
### decline-migration <reason>
Permanently record that this product is staying on the markdown backlog (TM1, issue #197) — for a
product with no GitHub remote, on a non-GitHub forge, air-gapped, or whose owner simply does not
want an Issues tracker. Requires a reason; if none is given, ask for one rather than writing the
field with no rationale (TM7).

1. **Precondition.** Read `backlog_service_repo` from `.prawduct/project-state.yaml`. If it is
   already set, this product has cut over — say so and stop; there is nothing to decline (TM4 already
   makes a stale `backlog_backend: markdown` harmless if it somehow existed, but writing one now over
   an active migration would be misleading).
2. **Write.** Add, as a top-level scalar in `.prawduct/project-state.yaml` (create the field if
   absent; if already `markdown`, report "already declined" and stop):

   ```yaml
   # <reason, verbatim from the caller> — recorded <today's date>
   backlog_backend: markdown
   ```

   The comment directly above the field is the record of *why* (TM7) — the same convention this
   file already uses above `backlog_service_repo` once a product cuts over. Do not invent a reason if
   the caller didn't give one; ask instead.
3. **Report.** Confirm the field was written and that `backlog-service-migration-required` will no
   longer fire for this product. Note that `legacy-backlog-format`, `legacy-section-schema`, and
   `backlog-overdue-grooming` are unaffected and will continue as normal (TM3) — the product is
   staying on markdown, so its format/schema/grooming hygiene still matters.

**Reversing the decision.** TM5 requires this to be reversible but not through a dedicated command:
removing the `backlog_backend` line (or setting `backlog_service_repo` once the product does decide
to migrate, which wins outright per TM4) is a normal, unceremonious edit to a committed file — the
same mechanism that set it. No `undecline-migration` verb is added; adding one would be scope beyond
what TM5 asks for ("a normal, unceremonious edit... No dedicated 'undo' command is required").
```

**Why prose-only, no new `prawduct-hook` command.** Every comparable one-shot `project-state.yaml`
write already documented in this skill — `migrate`'s `backlog_format_version: 2` (step 5),
`import`'s `backlog_external_imports` append — is done by the skill editing the file directly with
its own `Read`/`Edit`/`Write` tool grants, not by shelling out to a `prawduct-hook` subcommand. This
item follows the same established pattern rather than introducing a second write path for the same
kind of fact.

## Files touched

| File | Change |
|---|---|
| `plugin/lib/backlog_probes.py` | `probe_migration_required` gains the `backlog_backend == "markdown"` early return (TM2/TM4); one added line to its docstring naming the new resolution condition |
| `plugin/templates/project-state.yaml` | BACKLOG block gains `backlog_backend` documentation, alongside `backlog_format_version`/`backlog_prefixes` |
| `plugin/skills/backlog/SKILL.md` | New `decline-migration` subcommand section |
| `tests/test_backlog_probes.py` | See test plan below |

## Test plan (`tests/test_backlog_probes.py`)

Extends the existing `TestMigrationRequiredProbe` class (same fixtures — `_write_backlog`,
`_structured_backlog`, `_cb`, `ProjectState`, `run_all_probes` — no new fixtures needed):

1. **Declared markdown, unmigrated structured backlog → stays quiet.**
   `ProjectState({"backlog_backend": "markdown"})` against a structured, pending backlog →
   `probe_migration_required` returns `[]` where it would otherwise fire (mirrors
   `test_stays_quiet_post_cutover_through_the_roster`'s shape, run through `run_all_probes` so the
   roster path is proven, not just the direct call).
2. **Undeclared value does not resolve.** `ProjectState({"backlog_backend": "something-else"})`
   against the same backlog → probe still fires. Only the literal string `"markdown"` resolves
   (TM1: "the only currently defined value").
3. **Absent field behaves exactly as today.** `ProjectState({})` (already covered by the existing
   `test_fires_on_structured_unmigrated_backlog`) — included here only as a comment cross-reference,
   not a new test, so the "absence means undecided" claim in TM1 stays pinned somewhere obvious.
4. **`backlog_service_repo` wins over a stale `backlog_backend: markdown` (TM4).**
   `ProjectState({"backlog_service_repo": "acme/widgets", "backlog_backend": "markdown"})` against a
   structured backlog → probe stays quiet, same as `backlog_service_repo` alone
   (`test_stays_quiet_post_cutover_through_the_roster`) — proving the combination isn't itself a
   distinct code path that could regress independently of the `post_cutover`-first ordering.
5. **Sibling probes are unaffected (TM3).** With `backlog_backend: markdown` set and a legacy
   (pre-structured) backlog present, `probe_legacy_backlog_format`,
   `probe_legacy_section_schema`, and `probe_overdue_grooming` (via `run_all_probes`) still fire
   exactly as they would with the field absent — asserting the roster surfaces all three, not just
   that `probe_migration_required` alone stays quiet.

## Open items for the build chunk (not resolved here)

- Exact wording of the docstring addition to `probe_migration_required` — cosmetic; the test plan
  above is what actually pins the behavior.
- `doctor` reconciliation note when both `backlog_backend: markdown` and `backlog_service_repo` are
  set (requirements TM4's SHOULD, explicitly scoped out of both the requirements and this design as
  optional polish) — left for a future item if it proves worth doing; TM4's runtime behavior does not
  depend on it.

## Acceptance (carried from requirements, now with an implementation path)

- [ ] A product that will never host on GitHub has a recorded, committed way to permanently resolve
      `backlog-service-migration-required` — pinned by test 1, wired through `decline-migration`.
- [ ] That resolution does not also silence `legacy-backlog-format`, `legacy-section-schema`, or
      `backlog-overdue-grooming` for the same product — pinned by test 5.
- [ ] The declaration is shared across checkouts and survives a fresh clone — satisfied by
      construction (`project-state.yaml` is committed; `decline-migration` never touches
      `.advisories.json`).

## Evidence / references

- `documentation/issues/197-requirements.md` — TM1–TM7, the Decision section, and the "Scope of the
  silence" reasoning this design's TM3 section verifies against current code.
- `plugin/lib/backlog_probes.py:115-140` (`post_cutover`), `:258-308` (`probe_migration_required`) —
  the two functions this item touches.
- `plugin/lib/norm_probes.py` — `dead-why`/`stalled-transition` (backend selection, unaffected) and
  `probe_revisit_due` (retirement, unaffected) — traced in "Why no change is needed elsewhere."
- `.prawduct/project-state.yaml:31-36` — the existing free-text-comment-above-a-committed-field
  convention this item's TM7 mechanism reuses (the comment above `backlog_service_repo`).
- `plugin/templates/project-state.yaml:401-426` — the BACKLOG documentation block this item extends,
  and the precedent for how `backlog_format_version`/`backlog_prefixes` are documented.
- `plugin/skills/backlog/SKILL.md:130-145` (`migrate`, step 5) — the "skill writes a top-level
  project-state.yaml scalar directly, no `prawduct-hook` command" precedent `decline-migration`
  follows; `:164-169` (`scrub`) — the precedent for a high-consequence subcommand documented outside
  the default menu.
- `tests/test_backlog_probes.py:182-246` (`TestMigrationRequiredProbe`) — the existing test class and
  fixtures this item's test plan extends.
