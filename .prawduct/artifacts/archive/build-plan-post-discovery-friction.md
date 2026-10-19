---
artifact: build-plan
version: 2
scope: post-discovery-friction
branch: fix/post-discovery-friction
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms: one chunk, one boundary review; no review step is added"
      - "proportionality ratchets both ways; new controls emit their yield → inapplicable because no control is added; the change removes ~20KB every product session reads"
      - "state-file growth is advisory only → conforms: the oversized probe stays an info advisory; it gains a bullet, never a block"
      - "review rigor is stage-keyed → inapplicable because no review is touched"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session → inapplicable because no reviewer is touched"
      - "authority fails closed; advice fails soft → conforms: the handoff pointer and the oversized bullet are advice; an unreadable handoff still yields the pointer"
      - "the plugin writes nothing into a governed repo but its own state → conforms: the template change reaches new repos only; existing repos are told what can go, never edited"
      - "local-first governance, no third-party governance dependencies → conforms: stdlib only"
      - "prawduct guides and reviews; it never implements → inapplicable because no product code is touched"
      - "never specific to Python → conforms: the moved key reference is language-neutral as before"
      - "goals and verification bind; prescribed method is advice → inapplicable because no gate changes"
      - "every fact has one home → conforms: the opt-in key prose moves to one doc and the template points at it; the no-forward-note heading becomes one constant both writer and briefing read"
partition: serial — one chunk; four small fixes across disjoint files, too small to brief out
last_validated: 2026-10-16
lifecycle: completed
archived: 2026-10-19
released_in: v3.7.1
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build Plan: First governed session after onboarding discovery

## Goals

**Response taken:** Proceed. The owner reported two field issues from `../testrouter` (onboarded
at 3.7.1-dev.2) on 2026-10-16, I diagnosed four causes, and the owner said "yes fix all issues",
choosing the template move over the cheaper count-only-settings probe for (1a).

**Product.** The first governed session after an onboarding discovery opens on an accurate
picture: no size warning caused by prawduct's own boilerplate, a handoff that says what comes
next, and guides whose cross-references resolve.

The four causes, from the testrouter evidence:
1. **(1a)** `templates/project-state.yaml` is 29KB, of which 26.6KB is comment text, mostly
   mechanism documentation for opt-in keys. A fresh repo starts at ~30KB of the 40KB
   `oversized-project-state` threshold, so one discovery trips it (testrouter: 48KB).
2. **(1b)** `strategy-artifact-missing` fires right after discovery. It is correct: planning
   writes those artifacts. It reads as an alarm only because nothing framed it (cause 3).
3. **(1c)** The discovery session started before `.prawduct/` existed, so it never received the
   digest's forward-note rule. The onboard skill tells it to recommend `/clear` but not to leave
   a note, and the briefing then pointed at the empty "No Forward Note" handoff as "Previous
   session context available".
4. **(2)** The guides carry bare plugin-relative paths (`methodology/planning.md`,
   `templates/…`, `docs/…`) and nothing states their root. An agent rooting them at a full repo
   checkout lands one level above `plugin/`.

**Level:** High. The testrouter files reproduce each cause, and each fix is checked against them.

**Inferred decisions (for the boundary):**
- *Inferred:* the moved prose lives in `plugin/docs/project-state-keys.md` and is reached as a new
  `/prawduct:methodology project-state` topic, the established route for plugin docs read from a
  product repo. The discovery-time comments (classification, product definition and the other
  sections discovery fills) stay in the template: they are read at the moment they are needed.
- *Inferred:* already-onboarded repos are not rewritten. The oversized probe gains a gated bullet
  that names the template-copied key documentation as removable, consistent with the module's
  "advice names only what is actually in the file" design.
- *Inferred:* (1b) is fixed by the onboard note's content, not by changing the probe.

**Decisions made mid-build:**
- The `project-state` topic is not added to the session digest's topic roster. Adding it took
  the digest 7 characters past its reserved headroom (`test_the_digest_keeps_its_reserved_headroom`),
  and the reserve is held for defaults that must fire unprompted. This topic is a lookup, reached
  from the template line that names it and from the skill's own listing. Settled by the digest
  reserve policy and the owner's standing preference against adding per-session tax.
- The record check read `${CLAUDE_SKILL_DIR}/../..` in this plan as a missing file (review
  finding). Fixed in the shared path predicate: a token interpolating a variable is not a repo
  path, so every plan citing a variable-rooted path benefits.
- `test_commands:` gained a template hint. The new reference/template agreement test caught that
  it was documented but not hinted.

## Status

- [x] Chunk 01: Template slimmed, oversized advice, onboard forward note, handoff pointer, guide path root

## Build Chunks

### Chunk 01: Template slimmed, oversized advice, onboard forward note, handoff pointer, guide path root

- **Type:** code
- **Depends on:** none
- **Deliverables:**
  - `plugin/docs/project-state-keys.md`: the opt-in key reference, moved from the template (content kept, recast as markdown sections)
    (active_build_plan through the backlog keys).
  - `plugin/templates/project-state.yaml`: each opt-in section reduced to a one-line purpose, its
    commented example or live default, and a pointer to the reference.
  - `plugin/skills/methodology/SKILL.md`: a `project-state` topic; one line stating that bare
    `methodology/`, `templates/`, `docs/` paths in the guides resolve against
    `${CLAUDE_SKILL_DIR}/../..`.
  - `plugin/lib/oversized_state_probes.py`: a bullet for template-copied key documentation.
  - `plugin/lib/briefing.py`: the no-forward-note heading as one constant; the boundary pointer says
    when the handoff carries no forward note.
  - `plugin/skills/onboard/SKILL.md`: the discovery close writes `.prawduct/.handoff-notes.md`
    (discovery done, planning next, the strategy advisory is that step) before recommending `/clear`.
  - Tests: template size bound; carrier map moved to the doc; probe bullet present/absent; pointer
    for both handoff shapes; the skill topic and path-root line.
  - Records: `plugin/CHANGELOG.md`, `.prawduct/change-log.md`.
- **Acceptance criteria:** a freshly scaffolded `project-state.yaml` is under 12KB; the testrouter
  file (48KB) gets the new bullet; a no-forward-note handoff yields a pointer that says so; the
  methodology skill names the topic and the path root.
- **Done when:** criteria met, tests pass, committed, cumulative Critic clean, ticked.
