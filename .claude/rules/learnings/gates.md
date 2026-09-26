---
paths:
  - "plugin/lib/gates.py"
  - "plugin/lib/coverage*.py"
  - "plugin/lib/evidence.py"
  - "plugin/lib/record_lint.py"
  - "plugin/lib/critic_*.py"
  - "plugin/lib/ledger.py"
  - "plugin/lib/telemetry.py"
  - "plugin/lib/review_dispatch.py"
  - "plugin/bin/prawduct-hook"
  - "plugin/hooks/**"
---
# Learnings — gates

- A message naming the caller's NEXT step must ask the gate that will judge that step, never a cheaper proxy — else promise and gate disagree. Applies on success paths too, not only refusals ("a remedy must reach the state")
- Editing a runtime that governs the current session (prawduct's hooks govern prawduct): run the changed detection against this repo first — a wrong signal can silently disable the very Stop gate enforcing this session, and no test fails
- A structural gate must watch every place the natural workflow puts its input — if something has two reasonable homes and the gate checks one, the gate is optional (the Critic gate watched build-plan.md while plans lived in project-state)
- Auto-enable belongs with visibility, not enforcement — a feature may flip on silently only if at worst it shows new output; anything that can BLOCK the next PR (Critic checks, gates, non-zero hooks) must be enabled explicitly
- Dogfooding the plugin on its own repo masks output-relative bugs: tree-relative reads resolve here because this checkout has the files. Prove self-containment by static audit for tree-relative reads plus a run in a real consumer
- For a coverage/forcing-function opt-out, make the resolution a first-class recorded artifact (even a one-line 'not relevant — <reason>' stub), not a suppression flag — a flag is inert, invisible and rubber-stampable
- Before predicting a per-minute rate ceiling will bind, check serial round-trip latency: requests/min ≤ 60/round-trip-seconds, so it never binds on total volume — only on concurrent/batched requests issued faster than one round-trip drains.
- Before choosing block-vs-warn for a gate, establish WHO is at the write — a refusal to a human is a stop, but to an AGENT it is an auto-fix: a silent mutation nobody reviewed. Tell: weighing 'strict vs lenient' without having named the caller.
- Swapping a mechanism's input for a COPY of a file: ask what the original's METADATA was load-bearing for — `copyfile` dropped the git index mtime, silencing git's racily-clean rule, so the tree capture vouched for content never on disk.
- "Fail closed" means the channel's BLOCKING value, not any non-zero — a generic error code fails OPEN where the contract reads a specific code as block. Check the exit-code table the refusal reaches. Tell: "a refused gate is a blocked gate"
- A refusal predicate is not a severity predicate — a gate folding conditions into one "cannot be trusted" must not also pick how hard to fail, or its mildest, ordinary case escalates. Split reasons at the call site. Tell: function picked by NAME
- A documented "clears when X"/"exempt when X" arm is NOT evidence X is implemented — grep the module first; unworkable compliance routes operators to the forbidden lever (stalled-transition's "stopgap"). Tell: the promised state change doesn't move
