---
description: Prawduct governance overview and methodology index — the map of how this repo is governed (principles, the agent stance, the build cycle, the on-demand guides). Invoke for first contact, to see what governance applies here, or pass a topic (building|discovery|planning|reflection|principles|stance) to open that guide directly.
user-invocable: true
disable-model-invocation: false
argument-hint: (omit for the overview) | building | discovery | planning | reflection | principles | stance
---

This repo is governed by **Prawduct** — it turns product ideas into well-built software through structured discovery, quality-governed building, and continuous learning. The full methodology ships with the plugin and is read on demand; this skill is the map.

**If `$ARGUMENTS` names a topic, open that guide with the Read tool and stop:**
- `building` → `${CLAUDE_SKILL_DIR}/../../methodology/building.md`
- `discovery` → `${CLAUDE_SKILL_DIR}/../../methodology/discovery.md`
- `planning` → `${CLAUDE_SKILL_DIR}/../../methodology/planning.md`
- `reflection` → `${CLAUDE_SKILL_DIR}/../../methodology/reflection.md`
- `principles` → `${CLAUDE_SKILL_DIR}/../../docs/principles.md`
- `stance` → `${CLAUDE_SKILL_DIR}/../../methodology/agent-stance.md`

$ARGUMENTS

**Otherwise (no topic), give the overview:**

Every unit of work follows **understand → plan → build → verify → Critic → reflect**, scaled by size (trivial → build + verify; medium → + build plan + Critic; large → discovery + chunked build + Critic per chunk) and type. Read the guide for the phase you're entering — actually read it, don't work from memory:

- `/prawduct:discovery` — before discovery (new product, or unfilled `project-state.yaml` sections)
- `/prawduct:planning` — before designing artifacts or a build plan
- `/prawduct:building` — **before writing any code** against a plan (the #1 thing not to skip)
- `/prawduct:reflection` — at work boundaries and before `/clear`

The 23 principles (Quality · Product · Process · Learning · Judgment) guide every decision — read the full set with `/prawduct:methodology principles`. How the agent should communicate and act — the working voice that operationalizes them (verify don't guess, stress-test before agreeing, frame decisions, research fast-moving domains) — is the agent stance: `/prawduct:methodology stance`. Governance is enforced structurally: the plugin's Stop hook runs the Critic + reflection gates at session end, so a code change against an active build plan with no review or reflection blocks the session.

Quality review runs through `/prawduct:critic` (independent review after medium+ work) and `/prawduct:pr` (release readiness). Look up project rules with `/prawduct:learnings <topic>` and deferred work with `/prawduct:backlog`. Keep the repo healthy with `/prawduct:doctor` (prawduct governance/install conformance — reports and guides) and `/prawduct:janitor` (the product's own codebase craft — surveys and fixes); their split is `docs/doctor-vs-janitor.md`.
