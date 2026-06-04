<!--
scope: waiver-pragma
-->
# Build Plan — Intentional-Waiver Pragma (`prawduct:allow`)

## Problem / Success / Scope

- **Problem.** Intentional principle violations are marked today with a single bespoke literal
  (`prawduct:ok-broad-except`). Every new waivable case would need its own magic token + canary
  rule. We need one durable, language-agnostic, semantic mechanism that works for prawduct
  self-hosting *and* consuming repos, distinguishes framework vs project principles, and carries a
  mandatory reason.
- **Success.** A `prawduct:allow <scope>/<rule-id> -- <reason>` pragma is recognized by a single
  shared recognizer (`lib/waivers.py`); the broad-except canary consumes it; existing
  `ok-broad-except` usages are migrated to the general form (legacy form still honored); the scheme
  is specified in `docs/waivers.md` and taught in the methodology + Critic protocol. Full suite green.
- **Out of scope (this plan).** The broader 2.0 rock-solid cleanup (the `agents/`→`skills/`
  file-set-gate fix, dangling-ref repairs, ship-blocker doc fixes, backlog hygiene). Captured
  separately as Wave 2 below; not built in this cycle. Region-form waivers (`-begin`/`-end`).

**Requirements confidence:** High. Design + two key decisions (keyword = `prawduct:allow`; migrate
in-repo usages now) confirmed with the owner 2026-06-03.

## Status

<!-- regen-views derives this from change-log; hand-maintained until first tagged entry. -->

- [x] **C1** — `lib/waivers.py` recognizer + `tests/test_waivers.py` (28 tests)
- [x] **C2** — Wire the canary to the recognizer + migrate 49 in-repo `ok-broad-except` usages
- [x] **C3** — Spec (`docs/waivers.md`) + methodology/Critic/digest prose generalization

**Context:** Wave 1 (the pragma system) is **complete** — recognizer + canary wiring + migration +
spec/prose all shipped, 680 tests green (+28). Awaiting Critic review, then commit on
`chore/2.0-rock-solid-cleanup`. Wave 2 (the 2.0 rock-solid cleanup, incl. the `agents/`→`skills/`
gate fix) is queued, not started. Version bump + CHANGELOG headline + tagged change-log entry are
release-time steps (develop→main), deferred.

---

## Wave 1 — the pragma system

### C1 — Recognizer (`lib/waivers.py`)
`**Critic mode:** chunk`

New module: `KEYWORD = "prawduct:allow"`; legacy map `{"prawduct:ok-broad-except": "prawduct/broad-except"}`.
- `Waiver` value object: `scope`, `rule_id`, `reason`, `ref`, `line`.
- `parse_waivers(line)`, `line_waives(line, ref)`, `waives(lines, i, ref)` (line or line-above),
  `invalid_waivers(lines)` (reason-less).
- Separators accepted: ` -- ` (canonical), ` — ` (legacy). Reason required (non-empty).
- Multiple comma-separated refs per line. Malformed/scopeless refs do not match (safe failure).
- Register in `lib/__init__.py` (`from . import waivers`).

**Done when:** module + value object implemented; `tests/test_waivers.py` covers general + legacy
parse, scope-matching (no cross-waive), multi-language comment leaders, reason-required/invalid,
line-above placement, multi-ref; full suite green; `/prawduct:critic chunk`.

### C2 — Wire the canary + migrate usages
`**Critic mode:** chunk`

- Rewrite `_check_broad_exceptions` (`bin/prawduct-hook`) to use `lib.waivers.waives(lines, i,
  "prawduct/broad-except")` via the established lazy-import idiom (`_plugin_root()` + `sys.path`).
- Add a canary finding for reason-less waivers (`invalid_waivers`) — the enforcement teeth.
- Migrate every in-repo `prawduct:ok-broad-except — r` → `prawduct:allow prawduct/broad-except -- r`
  (`bin/prawduct-hook` ~30, `lib/advisory_store.py`, `hooks/digest.py`, `hooks/banner.py`).
- Update/extend any test that pinned the old literal behavior.

**Done when:** canary recognizes both forms + flags reason-less waivers; all in-repo usages migrated;
full suite green; `/prawduct:critic chunk`.

### C3 — Spec + prose
`**Critic mode:** final`

- `docs/waivers.md` (done — authoritative spec).
- `methodology/building.md` "Exception Handling" → "Intentional Waivers" (broad-except as one example).
- `skills/critic/review-protocol.md` — generalize broad-except validation to any `prawduct:allow`.
- `methodology/session-digest.md` + the injected digest text in `bin/prawduct-hook` — general form.
- `README.md` — light touch where the pragma is mentioned.

**Done when:** prose teaches the general form, legacy noted; `docs/waivers.md` linked from building.md;
`/prawduct:critic final`.

---

## Wave 2 — 2.0 rock-solid cleanup (queued, not this cycle)

Surfaced by the 2026-06-03 audit; tracked here so it is not lost:
- **Governance gate:** `_classify_trivial_change` / `_is_trivial_fileset_eligible` / `check-pr-trivial`
  in `bin/prawduct-hook` still bound on the deleted `agents/` path and are **missing `skills/`** (a
  `trivial`/`doc-only` chunk could edit `skills/critic/SKILL.md` untripped). Add `skills/`, rename
  reason `agent-file-edited`→`skill-file-edited`, and add the **missing** regression tests (the
  path bounds have zero coverage today). Update prose: `methodology/planning.md`,
  `templates/build-plan.md`, `skills/pr/*`.
- **Dangling refs:** `lib/operator_verification.py:222` (`migrate_cmd.py`), `skills/backlog/SKILL.md`
  (retired `legacy-backlog-format` advisory framing).
- **Lost parity test:** restore the `_SESSION_GITIGNORED_PATHS`↔`GITIGNORE_ENTRIES` mirror test
  (deleted with M4's `test_coverage_gaps.py`); the comments at `bin/prawduct-hook:119,303` and
  `tests/test_build_plan_resolution.py:99` cite it as live.
- **Apply the new pragma:** `prawduct/legacy-ref` on the legit migration `tools/` refs;
  `prawduct/duplication` on the bin↔lib mirror comments.
- **Ship-blocker docs:** `README.md:278` "(in progress)"; `CLAUDE.md:97,107,109` bare `/critic`,`/pr`.
- **Stale specs:** `documentation/post-sync-advisory-spec.md`, `documentation/governance-tax-followups.md`.
- **Backlog hygiene:** archive 9 obsolete + 6 already-shipped items; re-path 18 live items; re-validate
  2 uncertain flaky-test items.
