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

## Wave 2 — 2.0 rock-solid cleanup

- [x] **W2-C1 — Governance-gate fix.** `_classify_trivial_change` now bounds `skills/` (not the
  deleted `agents/`); reason `agent-file-edited`→`skill-file-edited`; **new `tests/test_trivial_fileset_gate.py`**
  (12 tests — the coverage the bound never had); prose cascade (planning.md, build-plan.md, pr SKILL/protocol).
- [x] **W2-C2 — Markers + dangling refs + parity test.** `prawduct/legacy-ref` on `lib/core.py`
  migration literals; `prawduct/duplication` on the two parity-tested bin↔lib mirrors; restored the
  `_SESSION_GITIGNORED_PATHS`↔`GITIGNORE_ENTRIES` parity test; fixed `operator_verification.py`
  (`migrate_cmd.py`→`core.read_bool_yaml_key`) and `skills/backlog/SKILL.md` (retired-advisory framing).
- [x] **W2-C3 — Ship-blocker docs.** README "(in progress)" dropped; CLAUDE.md bare `/critic`,`/pr`
  namespaced; `pyproject.toml` version 1.3.7→2.0.3.
- [x] **W2-C4 — Backlog hygiene.** Archived 16 items from `## Open` (Open 60→44, Archive 4→20):
  9 obsolete file-sync items + TST-1M6V (both named tests deleted in M4) dropped with reasons;
  6 already-shipped items moved retaining their resolution notes. Re-pathed kept items
  (`tools/product-hook`→`bin/prawduct-hook`, `agents/critic|pr`→`skills/…/review-protocol.md`,
  `tools/lib/project_state`→`lib/core.py`, `tools/lib/backlog_probes`→`lib/`). TST-4P8H narrowed
  (5 of 6 named tests gone; only `TestStopPrReviewGate` survives — that's the re-validation result).
- [x] **Deferred work filed:** `DOC-2W9P` (`documentation/` internal-spec stale `tools/lib/` paths);
  `STH-4D2X` (the `.claude/skills/` consumer-own-skill trivial-gate question).

**Wave 2 complete.** 694 tests green. Branch ready to PR — re-run `/prawduct:critic cumulative`
before `/prawduct:pr create` (HEAD advanced past the last cumulative record with the doc/backlog commits).
