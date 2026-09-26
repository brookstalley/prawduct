---
paths:
  - "plugin/lib/backlog/**"
  - "plugin/skills/backlog/**"
---
# Learnings — backlog

- Reconciling a backlog item a PR partly shipped: read ALL that PR's build-plan chunks (or `git show --stat <merge>`) before calling a leg open — docs/skill legs often land in a later chunk than the code
- Advisory/audit data threaded through a success envelope must reach EVERY error return too — error paths use a different constructor (`core.from_transport_error`) that drops it, fatally for one-shot data. Grep error returns
- A backlog item's `refs:` are candidate surfaces: implement only where the condition can manifest (grep existing coverage first) and descope dead refs explicitly in the item note, not silently
- A filed item's stated MECHANISM is a hypothesis, not a finding — reproduce it on live data before designing the fix; the reporter saw a correlation and wrote a cause, and the item's own evidence often disproves it. Run it, reconcile, then re-read.
- Search the backlog before proposing to ADD to it — the existing item is often a better-framed one, and adopting its framing beats re-deriving a worse one.
- Archiving an unmerged branch as "intent captured in the backlog" must verify the IMPLEMENTATION landed, not that an item exists — nine branches, ~11,000 reviewed lines lost. Tell: you are closing or archiving from a description rather than a diff
- A precondition recorded only in PROSE is never re-evaluated — wire it as `blocked_by`, which `pick` re-checks every call; items sat for weeks behind blockers that had closed. Tell: you are writing "GATED by X" into a body only a human will re-read
