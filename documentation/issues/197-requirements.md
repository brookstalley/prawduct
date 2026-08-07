# Issue #197 — Terminal-markdown backlog state: Requirements

`status: draft · stage: requirements · area: backlog-service · added: 2026-08-02 · source:
scheduled backlog session · issue: https://github.com/brookstalley/prawduct/issues/197`

Related: GV7/GV8 (`documentation/backlog-service-requirements.md`), `probe_migration_required` /
`post_cutover` (`plugin/lib/backlog_probes.py`), BKL-6J2X (the fleet-wide hold
on this same advisory), BKL-7D3V (the decision to ship the hold **lifted** — implementation is
that item's Chunk 07 done-when #5).

## Problem

`probe_migration_required` (GV7) has exactly one resolution condition: `backlog_service_repo`
being set in `project-state.yaml`. A product that will **never** cut over — no GitHub remote,
a non-GitHub forge, an air-gapped environment, or simply an owner who does not want an Issues
tracker — has no way to resolve the advisory, because its only exit is adopting the thing it will
never adopt. Today that failure mode is masked by BKL-6J2X's fleet-wide hold (the probe is
registered but wired to a no-op). The owner has since decided (BKL-7D3V) to ship the hold
**lifted**, which turns this from a hypothetical into a `warn`-priority nudge at every session
start, forever, for every product that has genuinely decided to stay on markdown. This item is the
precondition for that lift being survivable.

`stage: requirements` on the source issue is deliberate: the fix is a product decision, not code.

## Decision

Terminal-markdown **is a first-class supported state**, not an unsupported edge. GV4
(`backlog-service-requirements.md`) already commits prawduct to working for every adopter, and the
portfolio includes real, permanent reasons to stay on markdown (no GitHub remote, self-hosted
forge, air-gapped, or plain owner preference). Treating it as an edge case would mean the framework
has no honest answer for a real, recurring configuration.

It is declared with a new committed field, **`backlog_backend: markdown`** in
`project-state.yaml` — not a `backlog_service_repo: none` sentinel (overloading a field whose only
other value is a real `owner/repo` string is confusable with "unset"), and not inference from a
missing GitHub remote (a remote can appear for unrelated reasons — mirroring, a fork — and
inference conflates "haven't decided" with "decided never," which is exactly the ambiguity a
committed field is meant to remove). It is **not** a per-user advisory dismissal: the source issue
itself rules that out (a permanent architectural fact needs a recorded, shared, committed state,
not a per-clone nag every fresh checkout re-triggers).

Declaring `backlog_backend: markdown` is a **structural-characteristic flip** in the sense
`plugin/docs/norms.md` already uses that term (§ Ambient norms — structural characteristics): it is
a recorded decision about what kind of product this is, not a one-off dismissal, and it reopens the
same way any structural characteristic does — a later fact that contradicts it (the owner sets
`backlog_service_repo` after all) is handled by ordinary precedence (see TM4), not by a separate
un-declare ceremony.

## Scope of the silence

The source issue asks explicitly whether declaring terminal-markdown silences "the rest of the
migration-shaped surface" or only `probe_migration_required`. **Only `probe_migration_required`.**
The other three markdown probes gated by the shared `post_cutover()` predicate —
`legacy-backlog-format`, `legacy-section-schema`, `backlog-overdue-grooming` — are *quality* nudges
about the markdown file itself (structured ids, current section schema, grooming cadence). A
product that has decided to stay on markdown forever still benefits from all three; silencing them
would make the terminal-markdown path a second-class, worse-nudged backlog experience, which is the
opposite of "first-class." Folding the new predicate into `post_cutover()` would incorrectly
silence all four; it must gate `probe_migration_required` alone.

**GV8's advisory no longer exists** (`backlog-checks-dormant`, retired 2026-08-07 when the readers
it enumerated came back on the backlog cache), so this item has nothing to say to it either way. The
reasoning it displaced is kept because it still describes the shape: that advisory could only fire
when `post_cutover(state)` was true, and `backlog_backend: markdown` is meaningful only while it is
false (TM4 makes the two mutually exclusive), so the two states never overlapped.

The three `norm_probes` guarded by the same `post_cutover()` switch already do the right thing with
no change, though **two of them now use it to choose a backend rather than to retire** (W1, 2026-08-07):
`dead-why` and `stalled-transition` resolve citations against the markdown file before the cutover and
against the backlog cache after it, and `revisit-due` still retires outright. Either way a
terminal-markdown product never cuts over, so all three keep reading the file that remains its live
backlog.

## Requirements

MUST unless marked SHOULD.

- **TM1** `project-state.yaml` gains a `backlog_backend` field. The only currently defined value is
  `markdown`, meaning "this product has decided to keep its backlog on markdown permanently, by
  informed choice." Absence of the field (today's default for every existing product) means
  undecided — `probe_migration_required` keeps firing as it does today. No `github-issues` (or
  similar) value is needed: `backlog_service_repo` being set already encodes that state
  unambiguously (DM per `backlog-service-requirements.md`), and duplicating it here would create
  two fields that can disagree.
- **TM2** `probe_migration_required` (`plugin/lib/backlog_probes.py`) gains a second resolution
  condition alongside `post_cutover(state)`: return no candidates when
  `state.get("backlog_backend") == "markdown"`. This is a new, narrow predicate — it must not be
  folded into `post_cutover()`, which the three other markdown probes and `revisit-due` also read
  (see Scope of the silence). `dead-why` and `stalled-transition` read it too but use it to select a
  backend rather than to retire (W1).
- **TM3** The other three `post_cutover()`-gated markdown probes (`legacy-backlog-format`,
  `legacy-section-schema`, `backlog-overdue-grooming`) are unchanged by this item — they continue
  to fire for a terminal-markdown product exactly as they do for an undecided one.
- **TM4** Precedence when both are set: `backlog_service_repo` (i.e. `post_cutover(state)` true)
  always wins over a stale `backlog_backend: markdown`. A product that declared terminal-markdown
  and later migrated anyway is not a contradiction the framework needs to police — it is simply
  outdated metadata once cutover happens, and every currently-firing probe already treats
  `post_cutover()` as authoritative. No new validation, error, or forced cleanup is required; a
  `doctor` note that the two facts disagree is a SHOULD, not a MUST, and can be scoped at design
  time.
- **TM5** Declaring `backlog_backend: markdown` is reversible: removing (or changing) the field is
  a normal, unceremonious edit to a committed file — the same mechanism the field itself uses to
  exist. No dedicated "undo" command is required by this item; a `/prawduct:backlog` verb pair for
  discoverability (e.g. `decline-migration` / an explicit unset) is a SHOULD, left to design.
- **TM6** The declaration is committed and shared (a `project-state.yaml` fact), not gitignored,
  per-clone, or per-user — every checkout and every teammate sees the same resolved state on next
  sync, matching how every other advisory-resolving fact in this file already behaves.
- **TM7** Setting `backlog_backend: markdown` requires a stated reason at the point of decision
  (mirrors the `why` discipline `norms.md` already requires of every norm birth) — captured
  wherever the field is set (a skill prompt, a CLI flag, or free-text in the same commit), not
  enforced as a second machine-checked field. This item does not mandate a specific mechanism; it
  mandates that the decision is not silently machine-written with no owner-visible rationale.

## Acceptance

- [ ] A product that will never host on GitHub has a recorded, committed way to permanently resolve
      `backlog-service-migration-required`, without adopting the thing it declined.
- [ ] That resolution does not also silence `legacy-backlog-format`, `legacy-section-schema`, or
      `backlog-overdue-grooming` for the same product.
- [x] ~~`backlog-checks-dormant` is unaffected~~ — moot: that advisory was retired 2026-08-07.
- [ ] The declaration is shared across checkouts and survives a fresh clone (i.e. lives in
      `project-state.yaml`, not `.advisories.json`).

## Scope-out (this item)

- The exact CLI/skill surface for setting or unsetting `backlog_backend` (TM5/TM7's "SHOULD"
  ergonomics) — a design-stage decision, not a requirement.
- `doctor` reconciliation behavior when `backlog_backend: markdown` and `backlog_service_repo` are
  both set (TM4 already defines the correct runtime behavior; a `doctor` note is optional polish).
- Re-deriving whether BKL-6J2X's hold should lift — that is BKL-7D3V's decision, already made; this
  item exists to make that decision's consequences survivable, not to revisit it.
- Any change to the `norm_probes` trio — already correct for this case with no change (see Scope of
  the silence). `probe_checks_dormant` was also named here and no longer exists.

## Evidence / references

- `plugin/lib/backlog_probes.py:106-122` — `post_cutover()`, the single shared resolution predicate
  for four markdown probes plus `revisit-due`, and a backend selector for `dead-why` /
  `stalled-transition` (W1); this item adds a second, narrower predicate rather than widening this
  one.
- `plugin/lib/backlog_probes.py:240-290` — `probe_migration_required` (GV7), the probe this item
  gives a second resolution condition.
- `plugin/lib/backlog_probes.py:367-411` — the BKL-6J2X hold (`_probe_migration_required_held`)
  this item's fix must outlive once BKL-7D3V lifts it.
- `documentation/backlog-service-requirements.md` GV4 (adopter-reproducible — the reason
  terminal-markdown must be a first-class state, not an edge case), GV7, GV8.
- `plugin/docs/norms.md` § Ambient norms — structural characteristics (the "flipping a structural
  characteristic is a norm [birth] event" framing TM1/TM7 borrow rather than inventing a parallel
  mechanism).
