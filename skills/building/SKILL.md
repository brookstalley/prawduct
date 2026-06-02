---
description: The Prawduct build cycle — read this BEFORE writing any code against a build plan. Covers understand→plan→build→verify, work-scaled governance, test discipline, the Critic, and common traps. Invoke when starting implementation, building a chunk, or unsure how coding work should proceed here.
user-invocable: true
disable-model-invocation: false
---

**STOP — read the build cycle before writing code.** Proceeding straight to code without it is the #1 governance failure.

Read **`${CLAUDE_SKILL_DIR}/../../methodology/building.md`** now. It is the authoritative guide for turning a plan into working software: sessions vs. work cycles, work-scaled governance (size × type), the build cycle (clean baseline → read the spec → write tests → implement → verify → Critic → reflect), test discipline (tests are contracts — never weaken them), boundary investigation, decision research, and the common traps.

After reading, apply it to the work at hand. Match rigor to risk (Proportional Effort), and run `/prawduct:critic` after medium+ work as the plan's "Done when" steps direct.

Related on-demand guides: `/prawduct:discovery`, `/prawduct:planning`, `/prawduct:reflection`; the index is `/prawduct:methodology`.
