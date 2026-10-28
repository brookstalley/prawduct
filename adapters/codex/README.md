# Experimental Codex adapter

This Phase 1 spike registers Codex SessionStart and Stop hooks. SessionStart runs
`python3 "${PLUGIN_ROOT}/session_start.py"`; `PLUGIN_ROOT` identifies this adapter's
installed root. The adapter uses the canonical Prawduct `plugin/` tree without
copying governance files. When installed outside the Prawduct source checkout,
set `PRAWDUCT_CANONICAL_PLUGIN_ROOT` in the hook process environment to the
absolute path of the canonical `plugin/` directory. In the source checkout,
the adjacent `plugin/` tree is used when that variable is unset. An absent or
invalid canonical root fails the hook with an experimental unavailability notice
on stderr before any session state changes. `startup` and `clear` create a session boundary;
`resume` and `compact` continue it. Missing or other sources are refused before
session state changes. Stop runs `python3 "${PLUGIN_ROOT}/stop.py"` and evaluates
reflection only. Every Stop names six uncovered gates: `critic`, `pr`,
`learnings-unmigrated`, `learnings-budget`, `clear-verdict`, and `clear-reason`.
Those gates are not covered by the experimental Codex Phase 1 spike. A missing
reflection blocks with exit 2 and stderr until `.prawduct/.session-reflected`
contains the required reflection lines.

The hook emits an experimental briefing, the existing banner, governance digest,
session briefing, and `core.md` learnings. A context overflow notice is placed
first when the combined text exceeds the configured handler limit. This adapter
has fixture and disposable-repository live checks. Installed-plugin discovery,
trust, and supported status remain unverified.

The `methodology` skill accepts `building` and resolves the canonical
`plugin/skills/methodology/SKILL.md` overview and then
`plugin/methodology/building.md` at use time through `methodology.py`.
Read both in that order. It never bundles the canonical prose. In an
isolated installation, set `PRAWDUCT_CANONICAL_PLUGIN_ROOT` to the absolute
canonical `plugin/` directory before invoking the skill.

Run `"${PLUGIN_ROOT}/bin/doctor" --session-id <hook-session-id>`
from the governed repository for experimental diagnostics. The argument chooses
which receipts to inspect; doctor does not infer an ID from old receipts.
Hook observations are written under Codex's `PLUGIN_DATA` directory, outside
the repository, for a canonical Git identity and hook-supplied session ID.
Doctor exposes matching receipts no older than one day, but reports session
identity, SessionStart, Stop and D-9 overflow as `not-verified`: a caller-supplied
ID is not independent evidence of the current Codex session. The local
`hooks.json` declaration and pinned binary version are checked separately.
Effective registration and trust remain `not-verified` because this spike has
no independent read-only host registry or trust receipt. A local declaration
does not establish that Codex currently runs or trusts these hooks.
