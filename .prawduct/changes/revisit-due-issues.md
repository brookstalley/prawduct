---
schema: 1
type: fix
scope: revisit-due-issues
date: 2026-11-10
title: A dated revisit on a GitHub Issues backlog item now raises the revisit-due advisory
---
On a product whose backlog is on GitHub Issues, a `revisit: YYYY-MM-DD` clock never fired. The
`revisit-due` probe was switched off at the move to Issues because the field had no write path
there. #564 then shipped one (`backlog update --revisit`), but the probe stayed off. Items carried
dated clocks that nothing raised. In this repo there were six, including #987's escape re-run,
due 2026-11-10, whose plan named this advisory as the prompt.

After the move, the probe now reads `revisit:` from each open issue's `prawduct` block, served by
the backlog cache (`plugin/lib/norm_probes.py`). The rules are the same as the markdown arm's: a
date strictly before today, on an open item, fires; event-trigger text is the janitor's job. When
the cache cannot be read, the probe raises the shared `backlog-cache-unreadable` advisory instead
of reporting nothing due, as `dead-why` and `stalled-transition` already do. The cache spec
(§2.1, consumer 13), the post-sync advisory spec (§8.2) and the backlog-service API contract
record the restoration.

`TestSilentAgainstThisRepo` no longer counts `revisit-due` in its claim that this repo raises
no norm advisory. The probe's input is now the live tracker's dates, not committed state, so a
date passing would otherwise turn the suite red on a calendar day.

## Consumer note
If your backlog is on GitHub Issues, a dated `revisit:` on an open item now raises an advisory
in the session briefing once the date passes. Renew it with a fresh date, act on it, or close the
item. Items that already carry a past date will raise one advisory at your next session start.
Because the check now reads the backlog cache at every session start, a clone whose cache has
never been synced now sees the `backlog-cache-unreadable` advisory even with no norm citations;
`prawduct-hook backlog sync --repo <owner/repo>` clears it. Its wording changed, so an
earlier dismissal of it does not carry over.
