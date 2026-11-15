---
name: methodology
description: Use Prawduct's canonical methodology for work in a Prawduct-governed repository. Pass building to read the building guide before implementing a build.
argument-hint: building
---

# Methodology

For `methodology building`, resolve the real path of this `SKILL.md` first.
A repository `.agents/skills/methodology` entry may be a symlink. Run
`methodology.py` from the adapter root, two directories above the **resolved**
skill file. It resolves the canonical Prawduct `plugin/` directory at use time
through the adapter's explicit root contract and prints two absolute paths:
the canonical `skills/methodology/SKILL.md` overview, then
`methodology/building.md`.
If it exits nonzero, report the experimental adapter as unavailable and stop.

Read the printed canonical overview in full first, then read the printed
building guide in full. Apply their guidance within the user's authorization
and the current project's governance.
