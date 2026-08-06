# Issue #183 — operator-verification.md is a write-only queue: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-08-06 · source:
scheduled backlog session · issue: https://github.com/brookstalley/prawduct/issues/183`

Related: GOV-2W7Q (this item's id alias), CRT-2J8N (the bug VRF-002 named 17 days early —
the escape analysis this item exists to close), CRT-6B9M (the review heuristic that
generalizes VRF-002's lesson).

## Problem

`.prawduct/operator-verification.md` is an append-only queue of pre-merge human/live-harness
checks. `operator_verification_required: false` in `project-state.yaml` means the queue is
currently a **tracked reminder, not a gate** — `cmd_check_operator_verification` short-circuits
to exit 0 whenever `required` is false (`plugin/lib/operator_verification.py:284-295`), so
nothing enforces draining it.

Work is deferred *into* the queue conscientiously — entries are detailed, dated, and carry
explicit verification steps — and then does not reliably come back out. Re-counted at the
source **2026-08-06** (the issue's 2026-07-27 count is stale; four entries have drained since):
14 entries total, **6 pending** — VRF-002 (added 2026-07-10, now **27 days** pending), VRF-003
(07-16), VRF-005 (07-17), VRF-007 (07-19), VRF-008 (07-19), VRF-013 (07-31) — against 8
verified/discharged (VRF-001, 004, 006, 009, 010, 011, 012, 014). The queue **does** drain when
someone runs the live check; the defect is that nothing prompts or requires that to happen, so
drainage is opportunistic rather than routine. VRF-002 is the load-bearing case: it named
`critic-reviewer` vs. `prawduct:critic-reviewer` as the suspect matcher string on 2026-07-10,
and CRT-2J8N found the same defect independently 17 days later. The system that was supposed to
catch this did catch it, on paper, and then never ran.

Two sub-problems, both `stage: requirements` because each is a decision, not an edit:

1. **The gate is off, and the stated reason for the default no longer describes the queue's
   contents.** `project-state.yaml:547-552` justifies `operator_verification_required: false`
   as "Prawduct has no human-facing UI surface to verify pre-merge." But every one of the 14
   entries is a **live-harness integration check** — does a hook fire, does a matcher match,
   does a CLI round-trip against real GitHub, does a briefing advance a coverage layer — not a
   visual check. The comment's rationale is true and answers a question the queue does not ask.
2. **The deferral test that populates the queue is too coarse.** VRF-002 originally deferred
   *all three* of its integration facts to a live check on the grounds that "matcher-anchoring
   semantics vary by Claude Code version." That was true of delivery (fact 3) and orchestration
   (fact 1); it was **false** of the static half of fact 2 — whether a matcher pattern *can*
   match a given `agent_type` is pure static analysis, decidable the day the entry was filed, and
   it was broken. Bundling a statically-decidable claim with genuinely-live facts moved a false
   assertion into a queue that (per sub-problem 1) never drains on its own.

## Decisions

### D1 — What question the flag actually poses

`operator_verification_required` is renamed, in meaning if not yet in name, from "does this
product have a human-facing UI to eyeball" to **"does this product's next PR require a
live/networked verification pass before merge."** That is the question the queue's actual
14/14 entries have always asked. This item does not rename the YAML key (a breaking change to
every product's `project-state.yaml` is out of proportion to a comment fix) — it corrects the
comment at `project-state.yaml:547-552` to state the real criterion, so a future reader deciding
whether to opt in evaluates the right question.

**A consequence worth surfacing rather than silently adopting:** re-reading the queue under this
corrected question reveals that most entries do not actually require a *human* — they require a
*live, networked Claude Code session* (real `gh` auth, a real hook firing, a real API round-trip).
An ordinary agent session can drive `gh`, read output, and compare it against a stated PASS/FAIL
criterion exactly as well as a person can for a mechanical check (VRF-013's three read-only
Python snippets are the clearest instance — no judgment call, just "does this raise / do the
counts match"). A minority genuinely need a *person* — owner sign-off on a scope tradeoff
(VRF-014's items), or eyeballing that migrated content reads correctly (VRF-006). **OV3 below
requires the queue to record this distinction per entry**, because it changes who can drain a
given item and therefore what "the gate is on" would actually block on.

### D2 — The split-the-deferral rule, formalized and homed

When an entry is filed, its "why a human/live check" reasoning MUST separate two questions:
**"can this be true in principle"** (a claim decidable by reading code today — static) from
**"does the harness actually do it"** (only observable by running something — live). Only the
second half may be deferred into the queue as `pending`. A static half must be resolved (checked,
and if wrong, fixed and pinned by a test) *before* filing, not bundled into the same entry.

**Home:** `plugin/templates/operator-verification.md`'s existing HTML-comment guidance (currently
lines 3–20, ending at "To opt the project in…") gains a short paragraph stating this rule
immediately after the "Drain entries via…" sentence — the template is where every new entry's
shape is authored, so this is where the coarse-deferral defect actually gets prevented, not
after the fact. `plugin/methodology/building.md`'s existing "Operator verification (F10)" line
(currently `building.md:106`, one sentence pointing at the file and the gate) gains a
cross-reference to the template's rule rather than restating it — building.md is where a builder
decides *whether* to enqueue at all, so it needs the pointer, not a second copy of the text.

### D3 — The drain plan (sequenced ahead of any flip)

The plan is a **disposition for every currently-pending entry**, decided now, with genuinely-live
work explicitly left for a live session rather than faked:

| ID | Filed | What's live-only vs. static | Disposition |
|---|---|---|---|
| VRF-002 | 07-10 | Already correctly narrowed 2026-07-27 (D2's rule applied retroactively): the static half (fact 2, matcher-can-match) is resolved and pinned by `tests/test_critic_reviewer_agent.py::TestSubagentStopMatcherMatchesRuntimeAgentType`. Remaining: delivery (does the hook actually fire) + attribution (which trigger consolidated). | **Stays pending** — genuinely live-only, correctly scoped. Needs a real session with the fixed matcher, isolated `CLAUDE_CONFIG_DIR`, and consolidation-attribution recorded on the `review.critic` event before the check means anything. |
| VRF-003 | 07-16 | Half already discharged this session (CLI `coverage-status` before/after, recorded in-entry). Remaining: whether the SessionStart *briefing text* — not the underlying data — has actually dropped the Layer 0 block and shows the Layer 1 line. | **Stays pending** — the untested half is specifically the rendered advisory a person reads, which only a fresh `clear`-hook session start exercises. |
| VRF-005 | 07-17 | All three facts (label-remove URL encoding, `state_reason` clearing on reopen, additive `add_labels`) are real-GitHub-behavior facts with no static half to split out — the entry's own "why" already says so correctly. Checked against every live run since filing (VRF-006, 009, 010, 011, 012): none of them exercised a `status --to in-progress` transition or a reopen, so none discharges this by coincidence. | **Stays pending**, correctly scoped as pure-live. No static residual to extract. |
| VRF-007 | 07-19 | The adapter substrate is pre-verified live (2026-07-19, recorded in-entry). Remaining: the *skill* — prose a model executes — actually driving the adapter end-to-end in a sibling repo via `--plugin-dir`. | **Stays pending, with an open question flagged rather than assumed:** VRF-014 Item 1 (discharged 2026-08-02) attests a general "sibling-repo exercise" of "the candidate" covering drift-burndown and Health Check #13 by name, but its own record explicitly declines to enumerate every surface checked. It must not be read as covering the backlog-skill repoint specifically without that being said — this item is not silently marked verified on that inference (Principle 5, Honest Confidence). |
| VRF-008 | 07-19 | Same shape as VRF-007: an 11-step live skill-execution check (Critic, PR, janitor, dormancy advisory) against a cut-over sibling repo. No static half — it is a prose-execution question by construction. | **Stays pending**, same open question as VRF-007 re: whether VRF-014 Item 1's attested exercise happened to cover it. Do not infer coverage; ask or re-run. |
| VRF-013 | 07-31 | Three read-only Python snippets against the real `brookstalley/prawduct` repo, each with a stated PASS/FAIL criterion requiring no judgment call. | **Stays pending, but reclassified under D1**: this is the clearest instance of a check that needs a *live session*, not a *human* — any agent session with `gh` authenticated against this repo can run it and report the printed values. Flag as a same-day-drainable candidate the next time such a session runs (not this one — see Scope-out). |

No entry is verified or accepted by this item. **A requirements-stage session does not have the
live/networked, `gh`-authenticated conditions any of the six entries call for**, and manufacturing
a verification here would be exactly the laundering VRF-002's postmortem warns against — recording
"verified" without having actually run the check. The value this item adds is the disposition
table above (nothing left unexamined or silently assumed) and the corrected classification (D1)
that tells a future live session which of the six it can drain solo (VRF-013, plausibly VRF-002/
VRF-003) versus which need the owner present (the open VRF-007/VRF-008 question) or a specific
environment (VRF-005, VRF-002 delivery half).

## Requirements

MUST unless marked SHOULD.

- **OV1** `project-state.yaml`'s `operator_verification_required` comment (currently
  `:547-552`) is corrected to state the queue's real criterion — live/networked verification
  before merge — not "human-facing UI," per D1. The flag itself, its default (`false`), and its
  read path (`is_operator_verification_required`) are unchanged; this is a documentation
  correction, not a behavior change.
- **OV2** `plugin/templates/operator-verification.md` gains the split-the-deferral rule (D2) in
  its HTML-comment guidance: when filing an entry, separate "can this be true in principle"
  (resolve now, statically) from "does the harness do it" (defer). Only the second belongs in a
  new `pending` entry.
- **OV3** Every *new* queue entry filed from this point forward states, in its "Why a
  human/live check" section, whether it needs a **person** (owner judgment, visual/content
  eyeballing) or only a **live/networked session** (an agent can drive it, given the right
  environment and auth) — per D1's reclassification. This is a template-guidance requirement
  (extends OV2's home), not a schema change to `VerificationEntry`: the distinction lives in the
  entry's prose, the same way "Where to verify" and "Why a human check" already do, not as a new
  parsed field.
- **OV4** The six entries pending as of this item's filing (VRF-002, 003, 005, 007, 008, 013)
  each carry the disposition recorded in D3's table, appended to the live
  `.prawduct/operator-verification.md` as a dated groom note per entry (mirroring VRF-002's own
  2026-07-27 in-entry `===` groom-note convention) — not silently left as bare `pending` with no
  record that this drain plan considered them.
- **OV5** `operator_verification_required` is **not** flipped to `true` by this item. Flipping
  is explicitly deferred until either (a) the queue reaches zero pending entries, or (b) every
  remaining pending entry is classified live-session-only (OV3) and the flip is paired with a
  documented plan for who runs that class of check routinely (a release-prep step, a periodic
  live-session pass, or similar) — flipping onto an undrainable queue reproduces sub-problem 1
  with the roles reversed (a gate that blocks a PR that has no path to unblock it). This
  decision is recorded here so a future session does not need to re-derive it.
- **OV6** The `[ ]` "drain plan" acceptance item on the source issue is satisfied by D3's table
  plus OV4 — a plan **exists and is committed**; it does not require this item to have actually
  run any of the six live checks (Scope-out).

## Acceptance

- [ ] Each of the six currently-pending entries has a recorded disposition (verify-now,
      accept-with-rationale, or re-scope-and-stay-pending) rather than sitting untouched.
- [ ] The split-the-deferral rule is written where new deferral decisions are made — the
      operator-verification template — not only implied by VRF-002's retroactive example.
- [ ] `operator_verification_required`'s stated rationale matches what the queue actually
      contains (live-harness checks, not visual/UI checks).
- [ ] The flag's flip is not attempted until the drain-plan precondition (OV5) is met.

## Scope-out (this item)

- **Actually running any of the six live checks.** This item is `stage: requirements`, written
  in a docs-only, non-networked session; none of D3's dispositions claim a check ran here. VRF-013
  in particular is flagged as agent-drainable *by a future live session*, deliberately not this
  one — running it now, outside the task this session was given, would be scope creep into a
  different kind of work (Principle 12, Scope Discipline) even though it is mechanically easy.
- **The exact wording/placement diff for OV1's corrected comment and OV2's template addition.**
  Left to design, per the existing project convention (compare 197-requirements.md's identical
  split between requirements and design-stage wording).
- **A schema change to `VerificationEntry`/`_STATUS_LINE_RE` to machine-parse the
  person-vs-session distinction (OV3).** Requirements only asks that it appear in prose; whether
  a future item wants to make it structured is a separate, smaller item if the prose convention
  proves insufficient.
- **Whether VRF-014 Item 1's attested sibling-repo exercise in fact covered VRF-007/VRF-008.**
  D3 deliberately leaves this an open question rather than resolving it by inference — resolving
  it means asking the owner or re-running the check, either of which is live-session work, not a
  documentation decision.
- **Renaming the `operator_verification_required` YAML key itself.** D1 corrects what the flag
  is documented to mean; renaming the key is a breaking change to every onboarded product's
  `project-state.yaml` and is out of proportion to what this item's evidence supports.

## Evidence / references

- `.prawduct/operator-verification.md` — the live queue; 14 entries, 6 pending, re-counted
  2026-08-06 (VRF-001 through VRF-014).
- `plugin/lib/operator_verification.py` — parser/serializer/mutators (`VerificationEntry`,
  `mark_verified`, `mark_accepted`, `run_check_operator_verification`,
  `is_operator_verification_required:220-241`).
- `plugin/bin/prawduct-hook:3445-3474` (`cmd_check_operator_verification`) — the gate `/pr
  create` Step 2b calls; fail-open on a broken plugin `lib/` import, fail-closed (return 1) on
  any pending entry when the flag is true.
- `plugin/skills/pr/SKILL.md:82-87, :169` — Step 2b, the blocking caller; already documents both
  drain paths (`verify-operator-verification`, `accept-operator-verification`) this item reuses
  rather than replacing.
- `plugin/templates/operator-verification.md` — the template OV2/OV3 extend.
- `.prawduct/project-state.yaml:547-554` — `operator_verification_required: false` and the
  comment OV1 corrects.
- VRF-002's 2026-07-27 in-entry groom note — the precedent D2/D3 generalize: the first instance
  of the split-the-deferral rule being applied, done by hand, to one entry, after the fact.
