---
artifact: build-plan
version: 1
scope: silent-clear-checks
branch: fix/silent-clear-checks
depends_on:
  - artifact: architecture
  - artifact: api-contract
  - artifact: data-model
governed_by:
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → LOAD-BEARING. Every chunk here turns a
         silent pass into a named outcome. Chunks 01/02 add a third state (`unknown` /
         `unreadable-queue`) that is neither pass nor fail, following the `run_sentinel`
         precedent: an unevaluable check reports UNCHECKED, never silently passes. The
         verdict-producing halves (02's queue gate, 03's verify pass) fail CLOSED; the
         advisory halves (01's onboarding report, 02's mode notice) fail SOFT but still name
         their consequence (L349)"
      - "prawduct is written in Python and must never be specific to Python → conforms; no
         chunk introduces a language-specific predicate"
      - "the plugin writes nothing into a governed repo except its own state → conforms;
         chunk 01 only READS the harness's `installed_plugins.json` and never writes it"
      - "every fact has one home → conforms; chunk 03 adds no new carrier, it checks a set
         prawduct already computes"
  - artifact: data-model
    dispositions:
      - "facts are keyed by git TREE SHA, not by branch or commit → LOAD-BEARING IN CHUNK 04.
         The first draft of that chunk folded the plugin checkout's COMMIT SHA into the cache
         key; the norm says tree. Two develop commits that produce an identical plugin tree
         are the same code and must share a key — commit-keying would invalidate the cache on
         every no-op commit. Corrected to tree SHA plus a dirty-tree fingerprint BEFORE any
         code was written"
      - "a resolution fact requires a `verify-resolutions` origin and a pre-existing target
         finding → LOAD-BEARING IN CHUNK 03, and it settles the design fork. Synthesising a
         fact from the reviewer's prose (the issue's option 1) would mint a resolution whose
         judgment was inferred rather than made. Option 2 — refuse — is the only route that
         does not violate this"
      - "derived views are disposable and never authoritative → conforms"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract; additive-first evolution, `--json` keys never
         repurposed → conforms; chunks 01 and 02 ADD exit codes and result keys and repurpose
         none. The ratified unevaluability split is honoured: `check-operator-verification` is
         an authority gate, so unevaluable fails CLOSED; `check-plugin-active` is advisory at
         onboarding, so an unreadable harness file exits 0 carrying `unknown`"
  - artifact: observability-strategy
    dispositions:
      - "stdout is agent-facing, stderr is user-and-diagnostics, with stable prefixes →
         conforms; the new signals use the existing prefix vocabulary and land on the channel
         matching their audience"
partition: >-
  serial — the six chunks touch six disjoint modules and would parallelise cleanly, but the
  operator directed this session to run without delegation. Recorded as the operator's call,
  not as an unexamined default.
last_validated: 2026-08-27
---

## Requirements Confidence

**Level:** High for chunks 02-06, Medium for chunk 01.

**Why:** Every mechanism was read this session, not recalled — `_key` in `verdict_cache.py`
folds `evidence._plugin_version()` and nothing else that varies on a checkout;
`parse_operator_verification` treats an unrecognised heading as preamble by design;
`_take_active_narrative` breaks on the FIRST exact title match; `banner.py:294` uses
`lstrip("-* ")`; `grep -rn installed_plugins plugin/` returns nothing, so no surface reads it.

**Open assumptions:**

- `[ASSUMPTION: ~/.claude/plugins/installed_plugins.json keeps its version-2 shape
  (plugins[<name>] -> list of records carrying scope/projectPath) | MED impact | user can
  veto]` — this is a Claude Code **internal** file, not a documented contract. Chunk 01
  therefore fails SOFT on every read error and on any unexpected shape: "could not verify"
  is a distinct outcome from "not installed", and only the latter is ever reported as a
  defect. That containment is what makes coupling to an internal surface acceptable.

**What would raise confidence:** confirming the file is a supported surface. Not blocking —
the fail-soft design is correct either way.

## Problem

One class: **a check reports clear when it never ran.** Four issues are instances, and two more
are the same shape one level down (a signal computed and then dropped). Prawduct exists to
prevent exactly this, and it is currently vulnerable to it in six places.

## Success

Each of the six can no longer report a clean state it did not verify. Specifically: an
onboarded repo cannot look governed while the plugin never loaded; a verification queue that
could not be read does not read as drained; a verify pass cannot leave a blocking finding
unrecorded; a verdict cache cannot serve a verdict computed by different code; a learnings
retirement cannot orphan a duplicate; and two operator-facing signals stop being dropped.

## Out of scope

- #716 / #723 — overlap #722, which just shipped; #723 is a refactor deserving its own cycle.
- #684 — its design fork is owned by #167.
- #666 / #682 / #702 / #613 — real, lower frequency.
- The `installed_plugins.json` schema itself. Chunk 01 reads it defensively; it does not
  pin it.

## Status

- [ ] Chunk 01: An onboarded repo proves governance is live, or says it could not tell (#710)
- [ ] Chunk 02: An input that could not be read or recognised says so (#681, #664)
- [ ] Chunk 03: A verify pass records every blocking finding it discharges (#711)
- [ ] Chunk 04: The verdict cache keys on the code that computed the verdict (#668)
- [ ] Chunk 05: The learnings pair is graded, and a duplicate heading refuses (#717)
- [ ] Chunk 06: The version-delta headline renders as one sentence (#703)

---

### Chunk 01: An onboarded repo proves governance is live, or says it could not tell

- **Description:** Close #710. A repo can carry a correct `.claude/settings.json` install
  reference and still have the plugin never load, because *project-scope enablement is not
  installation*: `~/.claude/plugins/installed_plugins.json` must also hold a
  `prawduct@prawduct` record whose `projectPath` is that repo. Nothing in the plugin reads
  that file (`grep -rn installed_plugins plugin/` → no hits), so nothing can notice.

  **The detector cannot live in `/prawduct:doctor` for the failing repo, and this is the
  design point.** `doctor` *is* a plugin skill — if the plugin never loaded, the operator
  cannot invoke it there. So the check must fire from the **onboarding** session, which runs
  outside the target and can see it. Doctor gets the *residual* case only: the plugin loaded
  but its hooks did not (stale/absent `.prawduct/.session-start` marker), which is a real and
  distinct failure it *can* observe about itself.
- **Depends on:** none
- **Artifacts consumed:** `architecture.md` (the plugin writes nothing into a governed repo
  except its own state — this chunk only *reads* the harness file)
- **Deliverables:** new `plugin/lib/plugin_activation.py` (fail-soft reader returning
  `active` / `inactive` / `unknown`); a `prawduct-hook check-plugin-active [--path P]`
  subcommand; a final verification step in `plugin/skills/onboard/SKILL.md` that runs it
  against the target and prints the exact remediation command on `inactive`; a doctor health
  check for hook liveness
- **Tests:** unit — an entry matching the target path → `active`; entries for other paths only
  → `inactive`; a user-scope entry → `active`; missing file, undecodable JSON, unexpected
  schema, and a non-list value each → `unknown` **and never `inactive`**; the CLI maps
  `unknown` to a distinct exit code from `inactive`
- **Acceptance criteria:** onboarding a repo whose plugin is not installed for that path ends
  with a named, actionable failure instead of a success message; every read error reports
  "could not verify", never "not installed"
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: An input that could not be read or recognised says so

- **Description:** Two instances of one rule — *a present input that yielded nothing must not
  read as absent*.

  **#681:** `parse_operator_verification` treats any heading that is not `## VRF-<id>` as
  preamble. That leniency is deliberate and correct for a trailing `## Notes` section, and it
  stays. What is wrong is downstream: `run_check_operator_verification` reports
  `pending: 0` / "queue is empty" for a file it parsed **zero** entries out of, so a queue
  written in another format (32 entries as bullets, in the reported case) leaves the gate
  permanently inert. Fix: when the gate is **required** and the queue file exists with
  substantive content but zero entries parsed, return a distinct `unreadable-queue` status and
  fail **closed**. Scoping it to `operator_verification_required: true` is what makes it safe —
  only a repo that opted into the gate can be blocked by it, and being blocked is correct
  there.

  **Two constraints from `learnings.md` that shape the build, not just the description.**
  *L485 — find the frame that actually discards:* the symptom shows at
  `run_check_operator_verification`, but `_load_queue` is one layer below it and may be the
  real discard site. Establish which frame loses the information before writing the check
  there; a report added at the wrong call site is empty by construction and its test passes on
  a healthy repo. *L431 — establish who is at the write:* an agent meeting this refusal will
  reach for the queue file and rewrite it into the recognised format, which is a silent
  mutation of an operator-authored record performed to satisfy a gate. **The refusal text must
  say, in the imperative, that the queue is not to be rewritten — report the format mismatch
  to the operator.** Without that sentence this fix converts a silent no-op into a silent
  data loss, which is worse.

  **#664:** `infer_mode` silently discards a `Critic mode:` value that is present but
  unrecognised. Fail-open-to-inference is right and is **not** changing; the ignore just says
  so once, naming the value. Where the value is a valid `Type:` token (`cumulative-final` is
  the natural trap), the line names the right field.
- **Depends on:** none
- **Artifacts consumed:** `api-contract.md` (additive-first: new keys, no repurposing; exit
  codes are the contract)
- **Deliverables:** `plugin/lib/operator_verification.py` — new status on the check result;
  `plugin/lib/critic_mode.py` — one notice on unrecognised-but-present;
  `plugin/templates/operator-verification.md` — state the expected entry format where
  operators write entries
- **Tests:** a non-empty queue yielding zero entries fails closed with the new status; **the
  shipped template read through `core.TEMPLATES_DIR`** (not a fixture copy — L63: a predicate
  whose job is to classify real artifacts must be pinned against the real artifact) still
  reports empty and passes; a `## Notes` section alongside real entries still parses;
  not-required short-circuits before the new check; the refusal text carries the
  do-not-rewrite imperative; unrecognised mode emits exactly one line and still infers; absent
  and blank stay silent; `cumulative-final` names `Type:`. Preference-enforcement tests go
  under `tests/preferences/` — `testpaths` silently skips them anywhere else.
- **Acceptance criteria:** the reported 32-entry bullet file no longer reports a clear queue;
  no existing passing case changes verdict
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: A verify pass records every blocking finding it discharges

- **Description:** Close #711. A `verify-resolutions` pass can discharge finding B in prose
  ("implicitly closed by A") without writing B's resolution fact. B then blocks forever, and
  because it sits on a superseded round no later verify pass names it — the only exit is a
  full `cumulative`, a whole review round spent on bookkeeping for work already fixed and
  already confirmed.

  **Taking the issue's option (2), not (1), and the reason is worth recording.** Option (1)
  parses the reviewer's prose for referential closure forms; that is an open-ended set, and a
  parser that misses a phrasing fails silently in the same direction as the bug. Option (2) is
  a set comparison over data prawduct already has: `coverage_algebra.unresolved_blocking`
  already computes the prior round's blocking findings. At consolidate time, every one of them
  must be **named** — resolved, or explicitly deferred. Any that is neither makes the pass
  refuse rather than return 0 blocking. That is deterministic, closes the class rather than the
  instance, and surfaces at the review instead of at the gate one round later.

  **`data-model.md` settles it rather than merely favouring it:** a resolution fact *requires*
  a `verify-resolutions` origin and a pre-existing target finding. Option (1) would mint a
  resolution whose reviewer judgment was inferred from prose rather than made — a fact the
  invariant does not permit. Option (2) is the only route that conforms.
- **Depends on:** none
- **Artifacts consumed:** `api-contract.md`, `architecture.md` (a reviewer never mutates the
  session it reviews)
- **Deliverables:** `plugin/lib/critic_consolidate.py` — the named-set check at verify
  consolidation, plus the dispatch directive telling the reviewer every prior blocking finding
  must appear in `resolutions` or be explicitly deferred
- **Tests:** a verify pass naming every prior blocker consolidates unchanged; one leaving a
  blocker unnamed refuses, naming the finding id; an explicit deferral satisfies the check
  without weakening the gate; a pass with no prior blockers is unaffected
- **Acceptance criteria:** the #711 sequence (two ids, one fix) can no longer end with a
  silently unrecorded blocker
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: The verdict cache keys on the code that computed the verdict

- **Description:** Close #668. `verdict_cache._key` folds `CACHE_SCHEMA`, the trees, the
  fingerprint, and `evidence._plugin_version()` — which reads the bundled `VERSION` file. On a
  git checkout tracking `develop`, that string is constant across pushes **by construction**,
  so a verdict computed under older code is served as current. Its own docstring states the
  invariant this violates: the key covers "every input the verdict is a function of —
  including the CODE that computed it."

  Fix: when the plugin runs from a git checkout, fold in the checkout's **tree** SHA
  (`git rev-parse HEAD^{tree}` over the plugin directory) plus a dirty-tree fingerprint.
  **Tree, not commit** — `data-model.md`'s tree-keying Direction is the canonical answer here,
  and it is the difference between a correct fix and a cache that misses on every no-op
  commit: two develop commits producing an identical plugin tree are the same code and must
  share a key. Memoise per process — the docstring advertises a 0.01 s warm cost and a
  `git rev-parse` per lookup would spend it. Not a checkout (an installed copy) → the version
  alone, exactly as today.
- **Depends on:** none
- **Artifacts consumed:** `api-contract.md`
- **Deliverables:** `plugin/lib/verdict_cache.py` — code-identity component; memoisation
- **Tests:** two different plugin-checkout SHAs produce different keys for identical trees; a
  dirty checkout keys apart from the same SHA clean; a non-checkout install keys exactly as
  today (no cache invalidation for installed users); the git probe runs once per process; a
  git failure degrades to the version alone rather than raising
- **Acceptance criteria:** a develop pull invalidates cached verdicts; installed-copy users
  see no key change and no mass cache miss
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: The learnings pair is graded, and a duplicate heading refuses

- **Description:** Close #717. `learnings.md` and `learnings-detail.md` must mirror each
  other's headings in the same order, and nothing grades that. Separately,
  `_take_active_narrative` resolves a heading by exact title and takes the **first** match, so
  two same-titled blocks mean a retirement cuts one and orphans the other — in a file whose
  stated invariant is "never delete an entry here". Its docstring guards a *drifted* title and
  never a *duplicated* one.

  Load-bearing right now: the session briefing is asking for exactly the `learnings.md` →
  `learnings-detail.md` split this check would guard, and doing that split unguarded is how a
  duplicate gets introduced.

  **L431 applies here as it does in chunk 02.** An agent meeting a duplicate-heading refusal
  will reach for the obvious fix — delete one of the duplicates — in a file whose stated
  invariant is *never delete an entry here*. The refusal names both line numbers and says the
  resolution is the operator's; it must not read as an instruction to dedupe.
- **Depends on:** none
- **Artifacts consumed:** `architecture.md`
- **Deliverables:** `plugin/lib/audit_learnings_cmd.py` — `_take_active_narrative` scans all
  exact-title matches and refuses on a second, naming both line numbers; a pairing check
  (duplicate headings within either file, missing counterpart, order mismatch) surfaced through
  the existing doctor/janitor health-check route
- **Tests:** a duplicate heading is reported rather than cut; `--apply` refuses on a double
  match naming both line numbers; a missing `learnings-detail.md` counterpart is reported; an
  ordering mismatch is reported; a clean corpus produces no finding; this repo's own live
  corpus is graded in the suite
- **Acceptance criteria:** a duplicate heading is reported by a check rather than by nothing,
  and `--apply` cannot orphan an entry
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 06: The version-delta headline renders as one sentence

- **Description:** Close #703. `banner.py:294` strips a headline's leading `-`/`*` with
  `lstrip("-* ")`, so the **closing** `**` of a bolded lead-in survives into the rendered line:
  `Less waiting on the gates, fewer rounds in review.** Gate checks stop timing out, …`.
  Cosmetic, but it lands on the single most-read surface prawduct has — the one line every
  upgrading repo sees — and it has rendered that way since at least v3.3.2.
- **Depends on:** none
- **Deliverables:** `plugin/hooks/banner.py` — strip the paired emphasis markers rather than
  only the leading list/emphasis characters
- **Tests:** `tests/test_plugin_version_banner.py` — a bolded lead-in renders with no stray
  marker; an unbolded headline is unchanged; a headline containing legitimate mid-sentence
  emphasis is not mangled; the real `plugin/CHANGELOG.md` renders clean for every entry
- **Acceptance criteria:** rendering the live CHANGELOG produces no headline containing `**`
- **Type:** trivial
- **Trivial because:** a single-expression change to one headline parser in one file, bounded
  by a test that renders the whole live CHANGELOG; no new files, no `skills/`, `methodology/`,
  `templates/` or `CLAUDE.md` edits, no behavioural surface beyond the rendered string.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status
