# Release Plan — v3.7.2, Whole-Develop Promotion

**Status:** COMPLETE as measured 2026-10-24: `main` promoted at `eea2be2d`, tag and Release `v3.7.2` published in one call, `check-released v3.7.2` verified 3 of 3, develop reopened on `3.7.3-dev`. Re-derive rather than reading this as a measurement:
`prawduct-hook check-released v3.7.2`, `git log --oneline origin/main -1`.

**Version:** v3.7.2, a **patch**, by owner decision (2026-10-24: "yes to all of your
recommendations"). This follows the ratified conservative-versioning norm (`operational-spec.md` §
Direction). No gate in `plugin/hooks/gates.json` is new in this release. The new surfaces are opt-in
or advisory: the `tidy-available` advisory changes nothing until the owner approves a dry run, and
the move onto change fragments happens only through `/prawduct:doctor` with approval.

**Why now:** the change-log collisions seen in governed products on 2026-10-23 and 24 are fixed
on develop by change-log-fragments-wave-2. That fix cannot reach a product before this cut,
because the wave-2 migration refuses until `.claude/settings.json` pins prawduct v3.7.2 or later.
The collisions were in testament (three archive moves in two days, with merge conflicts and a
session-negotiated "single mover") and in discodon (a 41KB change-log that needed a manual
archive pass).

## Release classification

Every release-pending scope ships. No open issue is a release blocker. #1003 (an untracked file
blocks verbatim-commit coverage) is the next fix by owner decision, and it ships after this cut,
not as part of it. It has no fragment, so it has no row here.

| Scope | Disposition | Blocker |
|---|---|---|
| backlog-burndown | ships | |
| change-log-fragments | ships | |
| change-log-fragments-wave-2 | ships | |
| git-hygiene | ships | |
| goal-grounding | ships | |
| goal-grounding-discovery | ships | |
| network-git-budget | ships | |
| payload-fragment-closes | ships | |
| release-v3.7.1 | ships | |
| retired-claim-survives | ships | |
| testament-evidence | ships | |

**Nothing is withheld, so `K = 0`**, which means a standard whole-develop promotion.

## Consumer notes

Before the cut, three fragments carry a `none:` note, and each reason holds:
- `goal-grounding-discovery`: a design artifact only.
- `release-v3.7.1`: release mechanics.
- `testament-evidence`: prawduct's own test recording.

The `change-log-fragments` (wave 1) note was corrected at this cut. As written, it said
`migrate-change-log` "is not yet part of `/prawduct:migrate` or `/prawduct:doctor`", and that
moving onboarded repos was "a later release". Wave 2 ships in this same release and makes both
statements false: `plugin/skills/doctor/SKILL.md` and `plugin/skills/migrate/SKILL.md` both drive
it. Left alone, one digest would have told consumers two contradictory things.

## Plans

Live build plans declaring a shipping scope: `change-log-fragments`,
`change-log-fragments-wave-2`, `git-hygiene`, `goal-grounding` and `retired-claim-survives`. All
had zero unticked boxes at Phase 0, and `plan-backfill --apply` archived all five as shipped in
v3.7.2. `goal-grounding-discovery.md` declares `scope: goal-grounding`, but the sweep left it in
place: it is a discovery artifact, not a build plan, so it stays live as the design record.
`active_build_plan` was already `null`.
