# Build plan — Upgrade discovery: make a shipped capability reachable by the human

**Critic mode:** cumulative-final
**Branch:** `feature/upgrade-discovery-relay`

## Problem

An auto-updating product never learns that a new prawduct capability exists. Traced end to end on
`develop@ddb6dd1`:

1. The update lands silently — no release page visited, no changelog read.
2. On the next session the version-delta banner renders `↑ Prawduct updated: vA → vB` plus the
   release headline and any newly-active gates — to **stdout**, which the ratified observability norm
   defines as the *agent-facing* channel (`observability-strategy.md` § Direction).
3. `write_marker()` runs immediately after, so the banner **never renders again**
   (`plugin/hooks/banner.py`).
4. **Nothing instructs the agent to pass it on.** No relay directive exists in either digest variant
   or in the digest hook.
5. The one advisory that would route an un-migrated repo to the backlog migration is registered as a
   no-op (`_probe_migration_required_held`).

Net: the capability is announced once, on a channel the human does not read, and then never again.
The backlog service ships to a fleet that cannot discover it.

**The narrow reading is wrong and must not be built.** "Migrate automatically" is a worse product —
it writes 100–250 irreversible issues into a repo nobody asked to migrate. Requiring a human decision
is correct. The defect is that *the decision is never offered*.

## Success

1. On the first session after a version crossing, the human is told what changed **in conversation** —
   the one channel they reliably read.
2. An un-migrated repo with a structured backlog surfaces the migration advisory, and it reaches the
   human through (1) rather than dying in agent context.
3. `observability-strategy.md` no longer claims the briefing answers the owner's questions on a
   channel its own norm reserves for the agent — it states how the owner actually learns.

## Out of scope

- **Routing advisories to stderr by consequence.** Considered and deliberately not built: the relay
  is the general mechanism and covers advisories, headlines and gate activations at once. A second
  channel-level mechanism would be redundant until the relay is shown insufficient. Revisit if it is.
- Any change to the auto-update mechanism itself.
- A notification surface outside the conversation.
- Migrating anything. This plan makes migration *discoverable*, never automatic.

## Requirements confidence

**High** on the problem — every link in the chain was read, not inferred, and the file/function for
each is named above. **High** on success criteria 1 and 3. **Medium** on criterion 2's blast radius:
lifting the advisory executes a recorded owner ruling (2026-07-24) whose two stated conditions are
both discharged, but it is the first release in which any consuming repo is routed toward an
irreversible bulk write. The relay is what makes that safe — it is the reason the two ship together,
and neither should land without the other.

---

## Chunk 01 — Relay at both emission sites

**Two sites, because one does not cover the case.** The version banner fires **once, ever** — the
marker advances immediately after it renders. A standing advisory fires **every session** until it
resolves. Relaying only the banner would mean that if the agent fails to pass on the news during the
single session where the upgrade landed, the capability is unreachable forever, while the advisory
that exists precisely to nudge it goes on firing into agent context unread. Criterion 2 of this plan
is false unless both sites relay.

**Design decision — why not the session digest.** The digest was the obvious home and is the wrong
one, on grounds that are not about budget:

- Both directives fire **only when there is something to say** — a version crossing, or an active
  consequential advisory. A digest block is re-read on every session forever to cover the minority
  that have news.
- Each sits **immediately next to the content it refers to**, so the agent reads the headline (or the
  advisory) and the instruction to pass it on in one breath, rather than matching a general rule from
  session start against a block further down.
- It is the same principle as this release's own headline — *deliver the rule where it applies, not
  in a file to be read later*. A relay directive parked in the digest is the exact pattern that
  headline exists to retire.

The digest's 44 characters of remaining inline headroom (9,956 of 10,000, measured) is what prompted
the re-examination, but it is **not** the reason: the owner offered to raise the limit and the design
did not move. Recorded so the next reader does not "fix" this by consolidating into the digest once
the budget looks roomy.

**Proportionality — `warn`/`urgent` only.** The advisory relay fires only when an active advisory
carries `warn` or `urgent` priority. `info` advisories are FYI and relaying them every session is
nagging, which trains the user to ignore the channel and costs more than it buys.

**Done when:**
1. `render_delta()` emits a trailing directive telling the agent to surface the change to the user in
   conversation, and stating why (the user does not see this channel).
2. The banner directive appears **only** when there is a delta — never on a same-version session,
   never on first contact where the marker is being written for the first time.
3. The briefing's advisory block emits a directive when any active advisory is `warn`/`urgent`; no
   directive on an `info`-only set, and none when there are no active advisories.
4. Neither directive names a prawduct-internal identifier (§ Direction, emitted-text norm).
5. Tests, banner: directive present on a crossing; absent when `last == current`; absent on
   first-marker write; present alongside both headline-only and new-gate deltas.
6. Tests, advisories: directive present with a `warn`; present with an `urgent`; absent on `info`-only;
   absent with no active advisories; unaffected by the 5-item display cap (a `warn` ranked past the cap
   still triggers it — the cap is a display limit, not a relevance filter).
7. Offline suite green.

## Chunk 02 — Lift the migration advisory hold

**Depends on:** Chunk 01. The relay is the precondition, not a nicety: without it the advisory routes
the *agent* toward an irreversible bulk write with no human necessarily informed. Do not land this
chunk alone.

**Done when:**
1. `register()` wires `probe_migration_required` into the live roster in place of
   `_probe_migration_required_held`; the held wrapper and its explanatory comment are removed rather
   than left as dead code.
2. `test_held_out_of_live_roster` is replaced by its inverse — a structured, un-migrated backlog
   surfaces the advisory *through the live roster*, with the recommended action intact.
3. The lift is recorded as a decision (owner ruling 2026-07-24; both stated conditions discharged),
   not left to read as a default flip.
4. Offline suite green.

## Chunk 03 — Make the observability strategy honest about audience

**Done when:**
1. § What You Get no longer implies the owner reads the briefing directly; it names the relay as how
   a material change reaches them, and the briefing as the agent's state surface.
2. The § Direction channel norm is unchanged — it was right; the description was what drifted
   (norms bind, descriptions track).
3. The rejected alternative (stderr routing by consequence) is recorded with its reasoning, so the
   next reader does not re-litigate it from scratch.

---

## Status

- [ ] Chunk 01 — Relay the upgrade to the human, from the banner
- [ ] Chunk 02 — Lift the migration advisory hold
- [ ] Chunk 03 — Make the observability strategy honest about audience
