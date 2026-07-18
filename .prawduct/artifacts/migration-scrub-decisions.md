# Migration scrub — owner decisions (recorded 2026-07-18)

Owner checkpoint held at the end of the 2026-07-18 session (BKL-8N5K shipped, Critic clean).
**The live migration itself is HELD** — owner decision, not a blocker. Everything below is
**confirmed** and carries forward to the owner-run migration session (BKL-6M4T), which should
execute against these decisions without re-asking, re-confirming only if the source has drifted.

## Decisions

1. **Live run: HELD** (2026-07-18). Target when it runs: `brookstalley/prawduct` (public — the
   owner has NOT yet given the explicit public-visibility yes; re-confirm sign-off at the top of
   the migration session).
2. **Restructure scope: open survivors only.** The ~78 keep-items get the issue-standard
   restructure (title + template body + `kind:` backfill via a v1 plan, `import --restructure`);
   the 121 archive items import verbatim. Note: zero source items carry `kind:` today.
3. **Dispositions: all 18 approved** (apply after import — import-then-dispose; nothing
   hard-deleted).
4. **MIG-M4-REMOVE: import as-is** (content-digest idempotency key, no alias; `get` won't
   resolve it — accepted for shipped history).

## Approved dispositions (owner-confirmed 2026-07-18)

Merges (fold duplicate → survivor via `merge`, redirect-before-close):

| Duplicate | Survivor | Reason |
|---|---|---|
| BKL-7M4Q | BKL-5D2C | superseded by the adapter's crash-safe CC1 mutation design |
| BKL-8T3W | BKL-5D2C | becomes GV3 reconciliation in the backlog service |
| CRT-6J4P | CRT-8H3R | same mode-inference ancestor-guard fix; bodies cross-reference |
| WMK-4Q9T | GOV-4C7X | owner-decided deletion; the kernel program carries it |
| STH-4D2X | STH-5D8J | same trivial-gate surface; 5D8J's patch-vs-retire decision moots it |

Drops (`status … dropped` after import; bodies preserved):

| Item | Reason |
|---|---|
| MIG-6B0R | file-sync-era strip list; premise self-obsoleted |
| TST-4P8H | 5/6 named tests deleted with the file-sync engine; no active flakes |
| CRT-9V4T | superseded by CRT-3X9D structural no-execution binding |
| ADR-7X2M | RFC targets removed pre-2.0 layout; self-flagged needs-rework (re-file fresh if wanted) |
| REL-5K8M | inert since reviewer tiering was removed (v3.0.1) |
| STH-4B7Q | no repro; operator-verification surface reworked in v2.0.0 |
| CRT-6T1V | discodon-sourced Apr 2026, no movement |
| CRT-1B6Q | discodon-sourced Apr 2026, no movement |
| CRT-5N3F | discodon-sourced Feb–Apr 2026, no movement |
| STH-7B5N | Apr 2026, no movement |
| CRT-8D2W | premise half-obsoleted (build plans now tracked; worktree flow exists) |
| WMK-1P4Q | mooted by the kernel program's index-machinery deletion |
| WMK-7D3R | mooted by the kernel program's index-machinery deletion |

Everything else (~78 open + 121 archive): **keep** (LRN-3F8K explicitly kept — its dangling-sentinel
error is live and small).

## Migration-session runbook pointer

`skills/backlog/migration-scrub.md` (steps 0–4, incl. 2b restructure pre-pass). Sequence:
re-confirm sign-off → author the v1 restructure plan for the keep set → `restructure-preview` →
owner batch approval → `export` backup → `import --restructure` → apply the merges/drops above →
verify counts + spot-check → BKL-8P2R briefing/gates repoint → retire `legacy.py` +
`incoming-bugs/` in lockstep with the report-bug MG5 repoint → `/prawduct:critic cumulative` →
slice PR. The full item survey (per-item gists, DUP clusters, staleness evidence) was produced
2026-07-18; regenerate it if the source drifts materially before the run.
