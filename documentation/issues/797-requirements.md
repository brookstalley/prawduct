# Issue #797 — Probes: Nothing Surfaces a Stale or Over-Promising `PRAWDUCT:ANCHOR`: Requirements

`status: draft · stage: requirements · area: probes · added: 2026-09-12 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/797`

Related: #714 (closed 2026-09-11, `closed-by: plugin-absent-governance-anchor`) — ships the
in-place anchor *refresh* mechanism this item's own Scope-out defers to; this item covers only the
*nudge* that a refresh is needed. Doctor Health Check #4 (`plugin/skills/doctor/SKILL.md`) is the
operator-invoked grader this item must reuse, never re-derive.

## Problem

A stale or absent `PRAWDUCT:ANCHOR` in a product's `CLAUDE.md` surfaces today only when someone
runs `/prawduct:doctor` — which nobody does on a repo that looks fine, and a repo with a stale
anchor looks exactly fine: no hook fails, no gate fires, the session banner still reports a version.
The anchor's text became load-bearing for a reader the plugin cannot reach (a clone opened on a
machine without the plugin loads only `CLAUDE.md`), so an anchor shipped before that became true can
actively mislead such a reader — it claims a Stop hook will block them when none is running, and
never names the one command that would fix it.

## Grounding facts

Re-verified against the current tree (2026-09-12):

- **The grader already exists and already answers the right question, read-only.**
  `anchor_repair.check()` (`plugin/lib/anchor_repair.py:203-311`) returns one of six statuses —
  `ok`, `stale`, `stale-modified`, `absent`, `legacy-block`, `unreadable` (constants at
  `anchor_repair.py:62-67`) — from a single `CLAUDE.md` read, no git and no subprocess
  (`anchor_repair.py:33-38`, "Reads only; writes nothing"). `unwritable` (`:68`) is a seventh
  status, but it is reachable only through `repair(..., apply=True)`'s write path (`:312-390`),
  never through `check()` — not relevant to a probe, which only ever reads. This is cheap enough
  for an ambient, every-session check.
- **Detection is already by substance, not a version tag** — `anchor_repair.py`'s own module
  docstring: "the question asked is 'does this anchor tell a plugin-less reader how to end the
  condition?', answered by looking for the install command." This item's probe must consume that
  answer, not add a second one.
- **Doctor Health Check #4 is the only current consumer, and it is operator-invoked.**
  `plugin/skills/doctor/SKILL.md` step 4 maps each status to doctor prose (`stale` → "Prawduct's to
  fix: offer the repair"; `stale-modified` → "Yours to reword, not prawduct's... the repair declines
  it by design"; `absent` → "The repair inserts one"; `unreadable` → "say the check declined, never
  that it passed"). Nothing calls `anchor_repair.check()` outside `/prawduct:doctor` and
  `prawduct-hook reanchor` (`plugin/bin/prawduct-hook:5903-5954`, `cmd_reanchor`) — both operator-run,
  never ambient.
- **A sibling probe already checks anchor *presence*, not staleness, and the two do not overlap.**
  `onboarding_probes.probe_never_onboarded` (`plugin/lib/onboarding_probes.py:157-190`) fires only
  when a repo carries **no** onboarding marker at all — `ANCHOR_SENTINEL` absent **and**
  `distribution: plugin` unset **and** no pre-2.0 sync manifest (`onboarding_markers`,
  `:110-149`). A repo that *is* recorded as onboarded (`distribution: plugin` set) but whose
  `CLAUDE.md` separately lost its anchor block — `anchor_repair.check()`'s own `absent` status,
  reachable independently of `never_onboarded()` — passes `probe_never_onboarded` silently and gets
  no ambient nudge from anywhere today. This is the concrete gap behind this issue's acceptance
  criterion, not a hypothetical.
- **The template to copy is fully specified in code, not just named in the issue.**
  `install_reference_probes.py` (`FEATURE = "install-reference"` at `:69`,
  `probe_install_reference_drift(state, codebase)` at `:115-183`, `register()` at `:186-189`) is
  cause-agnostic (checked as state, never as an event — `:24-31`), self-resolving (re-fires every
  session until the condition clears; no special code needed — `:176-180`), and `priority="info"`
  (`AdvisoryCandidate`'s field, `plugin/lib/advisory_store.py:93-135`; `VALID_PRIORITIES = ("info",
  "warn", "urgent")` at `:79`). `AdvisoryCandidate` carries `type`, `evidence: tuple[str, ...]`,
  `trigger_summary`, `recommended_action`, `owner_action`, `priority` (`advisory_store.py:123-135`).
  Registration is `register_probe(FEATURE, probe_type, PROBE_VERSION, fn)`
  (`advisory_store.py:253`), added to the roster in `plugin/lib/probe_families.py`'s
  `register_all()` (the composition root every probe family is listed in, `:33-67`).
- **The roster already runs at session start, fail-soft, with no doctor invocation required.**
  `plugin/bin/prawduct-hook:1563-1584` calls `probe_families.register_all()` then
  `advisory_store.run_sync_advisories(...)` inside a bare `except Exception` guard ("advisory probes
  must never block session start") — this is the existing ambient-delivery path this item's new
  probe slots into; no new wiring is needed beyond registering the probe and adding it to
  `register_all()`.
- **#714 (closed 2026-09-11) is the live, current owner of in-place repair**, and this item's own
  Scope-out ("Refreshing the anchor in place — #714 owns that") is accurate against the current
  tracker, not stale: #714 closed `closed-by: plugin-absent-governance-anchor`, and `reanchor
  --apply` (`prawduct-hook:5903-5954`) is the operator-run repair this probe recommends, never
  performs.
- **`stale-modified` is explicitly not prawduct's to fix** (`anchor_repair.py` module docstring,
  `SKILL.md` step 4: "Yours to reword, not prawduct's — the repair declines it by design"). A nudge
  recommending a repair prawduct cannot perform would misdirect the owner toward a dry-run that
  reports "declined."
- **`legacy-block`** means the repo has not cut over to the plugin at all (`anchor_repair.py:236-254`)
  — its remedy is `/prawduct:migrate`, a distinct, larger action already covered by doctor's own
  migration-detection checks (Health Check #2, `SKILL.md:49`) and outside a same-issue's narrow
  "anchor" framing.
- **`unreadable`** means `CLAUDE.md` could not be decoded — "degraded because ungraded," per
  `SKILL.md` step 4's own instruction to report it as declined, never as a finding. A probe firing
  an advisory that asserts a graded defect over content it could not read would be asserting
  something the check itself disclaims.

## Decisions

**1. The probe fires on exactly two of the six statuses: `stale` and `absent`.** Both are
`repairable: True` in `anchor_repair.check()`'s own return value, both are prawduct's to fix (the
dry-run prints the exact replacement/insertion), and both are the cases the issue's problem
statement actually describes — an anchor that lies, or no anchor at all on an otherwise-onboarded
repo. `stale-modified`, `legacy-block`, and `unreadable` are excluded for the reasons in Grounding
facts: the first two have remedies that are not this probe's (the owner's own wording; a migration
sitting behind a different, larger command), and the third cannot be graded at all.

**2. `absent` fires only when the repo is otherwise onboarded** (mirrors the condition
`probe_never_onboarded` already uses to stay silent: `distribution: plugin` set, or another
onboarding marker present). A repo that has genuinely never onboarded is `probe_never_onboarded`'s
territory exclusively — firing both probes for the same un-onboarded repo would duplicate the
nudge under two different `type` values for one root cause. This probe's `absent` branch is
specifically the complementary case Grounding facts found missing: an onboarded repo whose
`CLAUDE.md` separately lost its anchor.

**3. The probe calls `anchor_repair.check()` directly and recommends `prawduct-hook reanchor`, not
`/prawduct:doctor`.** Unlike `install-reference` drift (whose probe recommends `/prawduct:doctor`
because Health Check #1 names *every* drifted field across a multi-field contract), the anchor
grader and its repair command are already a matched, narrow pair (`anchor_repair.check` /
`anchor_repair.repair`, both wrapped by the single `reanchor` subcommand) — routing through doctor
would add a hop for no added information. `owner_action` names `reanchor` to preview
(`prawduct-hook reanchor`) and `reanchor --apply` to write, consistent with `reanchor`'s own
documented informed-confirmation contract (`prawduct-hook:5950-5954`).

**4. Priority is `info`, unconditionally.** Per the issue's own acceptance criterion and consistent
with every existing probe in this state-not-event family: the condition costs the *current* session
nothing (this machine has the plugin loaded and is reading `CLAUDE.md` fine) — it is a future clone
or a plugin-less reader who pays, which is exactly `install-reference`'s own `info` rationale
(Grounding facts) applied to a different contract.

**5. The probe is self-resolving with no additional code** — re-registering and re-running every
session is already how every probe in this family clears itself once the underlying condition
(the anchor text) changes; nothing here needs a dismiss-tracking or re-surface timer beyond what
`advisory_store` already provides for every probe.

## Requirements

MUST unless marked SHOULD.

- **ANC-1** A new probe module (mirroring `install_reference_probes.py`'s shape: `FEATURE`
  constant, one `probe_*(state, codebase)` function returning `list[AdvisoryCandidate]`, a
  `register()` calling `register_probe`) calls `anchor_repair.check(codebase.root)` and returns a
  non-empty list only when the status is `stale` or `absent` (Decision 1).
- **ANC-2** The `absent` branch fires only when the repo carries an onboarding marker other than
  the anchor itself (`distribution: plugin`, or another marker `onboarding_probes.onboarding_markers`
  already recognizes) — never for a repo `probe_never_onboarded` already covers (Decision 2).
- **ANC-3** `stale-modified`, `legacy-block`, and `unreadable` produce no advisory from this probe
  (Decision 1); this item adds no new handling for any of them.
- **ANC-4** The advisory's `recommended_action` names `prawduct-hook reanchor` (preview) and
  `prawduct-hook reanchor --apply` (write), never `/prawduct:doctor` (Decision 3).
- **ANC-5** `priority` is `"info"` on every firing of this probe (Decision 4).
- **ANC-6** The probe performs no write and no subprocess call — it calls only
  `anchor_repair.check()`, which is read-only by its own contract (Grounding facts).
- **ANC-7** The probe is registered into `plugin/lib/probe_families.py`'s `register_all()`
  alongside the existing roster, so it runs at session start through the existing fail-soft
  `cmd_clear`/session-start path with no new wiring (Grounding facts).
- **ANC-8** The advisory's `evidence` names the concrete condition (which status fired, and — for
  `stale` — that prawduct's own previously-shipped anchor text is what is now superseded) so the
  owner does not have to run `reanchor --json` just to learn why the nudge appeared.
- **ANC-9 (SHOULD)** The advisory's `evidence` states, for `stale` specifically, what the old text
  gets wrong for a plugin-less reader (it claims a Stop hook will block when the plugin may not be
  running) — the concrete harm named in the issue's Problem, not just "this text is old."

## Acceptance

- [ ] A repo whose anchor is `stale` raises an `info`-priority advisory at session start, with no
      `/prawduct:doctor` invocation required.
- [ ] A repo that is onboarded (carries another onboarding marker) but whose `CLAUDE.md` lost its
      anchor (`absent`) raises the same class of advisory; a repo that has never onboarded at all
      does not get this advisory in addition to `probe_never_onboarded`'s.
- [ ] A repo with `stale-modified`, `legacy-block`, or `unreadable` gets no advisory from this
      probe.
- [ ] The advisory self-resolves (stops firing) once the anchor is refreshed, with no additional
      code beyond the existing probe-roster re-run-every-session behavior.
- [ ] The probe performs no write and no subprocess call.

## Scope-out (this item)

- Refreshing the anchor in place — #714's mechanism (`reanchor --apply`), already shipped and
  closed; this item only nudges toward running it.
- Any committed hook or framework file in a consumer repo (per the issue's own Scope-out).
- `stale-modified` (owner's own edit — not prawduct's to re-word or nudge about), `legacy-block`
  (a larger migration, already covered by doctor's separate migration checks), and `unreadable`
  (cannot be graded at all) — Decision 1.
- Changing `anchor_repair.check()`'s grading logic, its status set, or doctor Health Check #4's
  existing prose — this item only adds a new, read-only consumer of the grader that already exists.
- Designing the exact `evidence`/`trigger_summary`/`owner_action` prose strings — ANC-8/ANC-9 state
  the content they must carry; exact wording is a design-time concern, consistent with how the
  `install-reference` probe's prose was written (Grounding facts), not fixed here.

## Evidence / references

- `plugin/lib/anchor_repair.py:1-38` (module docstring: substance-based detection, read-only
  contract), `:52-60` (the six/seven status constants), `:203-290`-ish (`check()`'s full branch set)
  — the grader this item's probe must reuse, never re-derive.
- `plugin/skills/doctor/SKILL.md` step 4 — the per-status operator prose and the `stale` /
  `stale-modified` split this item's Decision 1 mirrors.
- `plugin/lib/onboarding_probes.py:110-190` (`onboarding_markers`, `never_onboarded`,
  `probe_never_onboarded`) — the sibling probe whose silent gap (an onboarded repo with a lost
  anchor) motivates the `absent` branch, and whose non-overlap condition Decision 2 reuses.
- `plugin/lib/install_reference_probes.py:1-70,115-189` — the exact template this item copies:
  `FEATURE`, `probe_*(state, codebase)` shape, `register()`, the cause-agnostic/self-resolving/
  `info`-priority rationale.
- `plugin/lib/advisory_store.py:79,93-135,253` — `VALID_PRIORITIES`, the `AdvisoryCandidate`
  dataclass fields, `register_probe`'s signature.
- `plugin/lib/probe_families.py:1-57` — the composition root `register_all()` this item's probe
  must be added to.
- `plugin/bin/prawduct-hook:1563-1584` — the existing session-start, fail-soft call site
  (`register_all()` + `run_sync_advisories`) this item's probe rides with no new wiring.
- `plugin/bin/prawduct-hook:5903-5954` (`cmd_reanchor`) — the operator-run repair command this
  item's advisory recommends, never performs.
- GitHub issue #714 (closed 2026-09-11, `closed-by: plugin-absent-governance-anchor`) — confirms
  this item's Scope-out of in-place repair is current, not stale.
- Issue #797 — problem statement, proposed change, and acceptance criteria this document grounds.
