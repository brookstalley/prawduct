# Doc-vs-code drift found while mining — owed back to the source repos

**Not corpus material.** These are defects in the repos that were mined, found incidentally by
agents reading them for MCP rules. They are recorded here rather than in `.handoff-notes.md` because
that file is consumed at the next `/clear` and these obligations must outlive the session
(`core.md`: *a closing block asserting that state exists only in context is the trigger to write it
down* — and its bound, that the handoff carries state one hop, not indefinitely).

Each item is an agent's claim, read against the commit named. None has been re-verified from here,
and **none has been reported to the owning repo yet.**

**What this file holds, exactly — it is not uniformly complete, and reading it as a list would
undercount.** Corrected 2026-09-18 after counting rather than estimating:

| Repo | Enumerated here | Total reported | Where the rest are |
|---|---|---|---|
| cordyceps | 6 of 6, plus 1 governance note and 2 wrong-mechanism notes | 6 | complete here |
| hallucinote | 3 of 3 | 3 | complete here |
| discodon | **3 of 20** | 20 | that capture's own drift section |

So this file is the **complete** record for cordyceps and hallucinote and a **top-three** for discodon.
Before reporting anything to discodon, read its capture's drift section, which is its own top-level
heading (`# Doc-vs-code drift in discodon itself`). Anchor the search, because a bare `grep -n 'drift'`
returns the word from inside a dozen rule bodies and not the heading:

    grep -nE '^#{1,3} .*[Dd]rift' discodon-consumer-structured.md A total across all three is 29 claims, not the
12 enumerated below, and neither number should be quoted without running the count:

    grep -c '^[0-9]\+\. \*\*' drift-owed-upstream.md      # items enumerated here

## cordyceps — at `develop` `f07eb797`, mined 2026-09-18

Two re-confirmed from the first mining pass, four new.

1. **`McpTestingGuide.md` § Part 5 misclassifies a missing required parameter** as a JSON-RPC
   protocol error. The code returns a structured tool result — the `throw` is *inside* the
   converting try, and only unknown-tool is outside it. **A tester following the guide files a false
   regression.** (Re-confirmed.)
2. **`CLAUDE.md` § Architecture and `boundary-patterns.md` both describe an HTTP+SSE server managing
   SSE sessions. There is no SSE**; GET/DELETE return 405. These are the two files a new agent reads
   first. (Re-confirmed.)
3. **NEW — `StatusEnvelope` class summary and `McpServer.WithStatus` both say "19 tool files"; there
   are 18.** That number carries the argument for the choke-point design.
4. **NEW — `CHANGELOG.md` `## [1.4.5]` claims the knowledge-base reduction it did not ship.** Commit
   `02b800d` landed 21s *after* the release commit and is not an ancestor of the `v1.4.5` tag; the
   reduction first shipped in v1.4.6, and at the v1.4.5 tag the corpus is still 1636 lines.
5. **NEW — commit `306f35d` says "17 string params"; `CHANGELOG.md` `## [1.4.9]` enumerates 19
   names** for the same change.
6. **NEW — `boundary-patterns.md` cites "the pending `gh_script` language bug" as its live example of
   doc drift.** That bug shipped (GHS-7K2P plus #15, 28 tests and a `languageWarning`), so the
   example of drift is itself drift.

Governance-only, listed separately because it is documented rather than silent:
`build-plan-reliability.md` has six unticked chunks for work merged in PR #26, and the file,
`learnings.md` and two change-log entries all say so.

### Also worth telling cordyceps: two cited mechanisms do not do the job claimed

- The id-echo mechanism is `JsonElement.Clone()`, **not** raw-literal-text capture. The behaviour
  the rule asserts is right; the mechanism named for it is not.
- **`DeprecationRegistry`, which `boundary-patterns.md` names as the mechanism for evolving the
  action contract additively, actually tracks deprecated Grasshopper components.** The stance is
  sound; nothing implements it yet.

## hallucinote — at detached HEAD `3ed9ff07`, audited 2026-09-18

All three of the capture's "still wrong at HEAD" claims **confirmed still live**, so all three are
owed back.

1. **Two agent-facing surfaces still tell an agent a diagnostic call "always works"** while the host
   is fenced, against a measured 30s timeout. `actions/session.py` (the `session` action handler, at
   the cited line exactly) and `resources/guides/conventions.md` § the conventions guide's
   always-works claim; the measurement is in that repo's `operator-verification.md`. **Already filed
   there as #531 and unamended** — so the report owed is that it is still reproducible, not that it
   is unknown.
2. **A 120s ceiling's justifying comment still cites "tens of seconds"** for a device load
   re-measured at 1.95s cold / 0.89s warm. `client.py`, the comment above
   `_DEVICE_LOAD_READ_TIMEOUT = 120.0 + margin`, with `main_thread_timeout=120.0` in
   `actions/device.py`. The premise was disproved and the constant was never revisited.
3. **The design doc says UDP; the shipped code is TCP** — confirmed, with a correction that matters
   for whoever fixes it: **the design doc says UDP in two places**, not one, and the capture named
   only one. A later reader fixes that one and believes it closed.

### Correction to the capture's own wording, not a hallucinote defect

The capture said the shipped code *"names the doc as wrong."* It does not — `wire.py` says *"despite
some early scratch notes saying otherwise"* and names no document. Worth knowing before quoting the
capture at that repo.

## discodon — read across `9d54e8f8` → `77d10443`, mined 2026-09-18

**20 items, enumerated in that capture's own clearly-marked drift section.** The three highest-cost:

1. **`EVL-D2WN` does not exist.** Two records redirect a reader to a tracker item that was never
   filed — the unbuilt billed-vs-stored reconciliation, now invisible to `pick`. A pointer to nothing
   is worse than no pointer: it reads as tracked work.
2. **`ChannelBridge`'s re-evaluation trigger is on the wrong axis** — multi-principal token management
   sitting over a principal-blind notification fan-out, with the recorded trigger naming a second
   *source* rather than a second principal.
3. **The 1800s "client" abort is probably the server's own reaper.** If true, it changes the open
   diagnosis on that repo's `[MCP-H3ZP]`.

### A note on reading a tree that moves under you

discodon's HEAD advanced **four times mid-read**, under another session. The miner re-verified every
citation against the far end and recorded both SHAs in the capture's header; current HEAD matches its
end-of-read value. **One cited symbol survived while moving from line 1196 to line 1165** — so a
`:1196` citation would now be silently wrong and still look precise. That is the symbol-anchoring
requirement earning its keep in a single observation, and it is worth telling discodon only insofar as
it explains why this capture cites no line numbers.
