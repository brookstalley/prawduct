---
description: Prawduct governance overview and methodology guides — the map of how this repo is governed, and the reader for each guide. Invoke for first contact or to see what governance applies here; pass a topic (building|discovery|planning|reflection|session-hygiene|delegation|principles|norms) to open that guide directly — building BEFORE writing any code against a build plan, discovery before scoping requirements, planning before designing artifacts or a build plan, reflection at work boundaries and before /clear, delegation before splitting work across subagents, norms for the norm-lifecycle spec (what binds vs what tracks).
user-invocable: true
disable-model-invocation: false
argument-hint: "(omit for the overview) | building | discovery | planning | reflection | session-hygiene | delegation | principles | norms"
---

This repo is governed by **Prawduct** — it turns product ideas into well-built software through structured discovery, quality-governed building, and continuous learning. The full methodology ships with the plugin and is read on demand; this skill is the map and the reader.

**If `$ARGUMENTS` names a topic, open that guide with the Read tool, then apply it to the work at hand:**
- `building` → `${CLAUDE_SKILL_DIR}/../../methodology/building.md` — **STOP: read this before writing ANY code against a build plan** (skipping it is the #1 governance failure). Then match rigor to risk and run `/prawduct:critic` after medium+ work as the plan's "Done when" steps direct.
- `discovery` → `${CLAUDE_SKILL_DIR}/../../methodology/discovery.md` — ask the fewest questions that most change the outcome. If the repo has existing docs/code but a template-default `project-state.yaml` (the **DISCOVERY NOT CAPTURED** nudge), run the guide's reconciliation mode — backfill from the material, don't re-interview.
- `planning` → `${CLAUDE_SKILL_DIR}/../../methodology/planning.md` — artifact templates ship at `${CLAUDE_SKILL_DIR}/../../templates/`; generate in dependency order and validate intermediate outputs before building on them.
- `reflection` → `${CLAUDE_SKILL_DIR}/../../methodology/reflection.md` — reflect at work boundaries, not only session end; close the loop from observation to changed behavior.
- `session-hygiene` → `${CLAUDE_SKILL_DIR}/../../methodology/session-hygiene.md` — how a turn ends: the standing block (`STATE` / `RUNNING`·`YOUR TURN`·`COMPLETE` / `SAFE TO CLEAR`·`DO NOT CLEAR`), what a live review or an unreaped delegate does to the clear verdict, and the forward notes.
- `delegation` → `${CLAUDE_SKILL_DIR}/../../methodology/delegation.md` — before splitting work across subagents, and when a tangent arrives mid-chunk. When to delegate and when to stay serial; what a delegate verifies (what proves its own change, and nothing beyond it) while the coordinator owns integration and all governance; the anti-patterns each with its tell, what a brief must say, and the integration debt an ad-hoc delegate leaves you to pay.
- `principles` → `${CLAUDE_SKILL_DIR}/../../docs/principles.md`
- `norms` → `${CLAUDE_SKILL_DIR}/../../docs/norms.md` — norms bind; descriptions track. The authority rule, the normative-vs-descriptive test, the lifecycle (birth, rulings, amendments, exceptions, transitions), and the enforcement map. Read when work touches a `## Direction` section, a preferences norm row, or a structural-characteristic flip — every other surface that cites `docs/norms.md` reads it through this topic.

$ARGUMENTS

**Otherwise (no topic), give the overview:**

Every unit of work follows **understand → plan → build → verify → Critic → reflect**, scaled by size (trivial → build + verify; medium → + build plan + Critic; large → discovery + chunked build + Critic per chunk) and type. Read the guide for the phase you're entering — actually read it, don't work from memory:

- `/prawduct:methodology discovery` — before discovery (new product, or unfilled `project-state.yaml` sections)
- `/prawduct:methodology planning` — before designing artifacts or a build plan
- `/prawduct:methodology building` — **before writing any code** against a plan (the #1 thing not to skip)
- `/prawduct:methodology reflection` — at work boundaries and before `/clear`
- `/prawduct:methodology session-hygiene` — when closing a turn that ends a work cycle or leaves work outstanding
- `/prawduct:methodology delegation` — before splitting work across subagents

The principles guide every decision — read the full set, where the count and the groups are defined rather than restated, with `/prawduct:methodology principles`. How the agent communicates and acts while applying them — advisor first (expert take before compliance), verify don't guess, stress-test before agreeing, frame decisions — is the stance block in the always-injected session digest (`methodology/session-digest.md`). Governance is enforced structurally: the plugin's Stop hook runs the Critic + reflection gates at session end, so judgeable code changed this session with no shaped reflection blocks the session, as does a change against an active build plan with no review.

Operational procedures — runbooks for incident response, deploy/rollback, release, disaster
recovery, maintenance and field service — are authored with `/prawduct:runbook`, against the
canonical rules and evidence in `docs/runbook-authoring.md`.

Quality review runs through `/prawduct:critic` (independent review after medium+ work) and `/prawduct:pr` (release readiness). Project rules are `.claude/rules/learnings/` files the harness loads (`core.md` always, an `<area>.md` on a matching read); deferred work is `/prawduct:backlog`. Keep the repo healthy with `/prawduct:doctor` (prawduct governance/install conformance) and `/prawduct:janitor` (the product's own codebase craft); their split is `docs/doctor-vs-janitor.md`.
