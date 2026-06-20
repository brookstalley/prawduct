---
artifact: build-plan
version: 2
scope: upstream-bug-reporting
depends_on: []
last_validated: 2026-06-20
---

# Build Plan — Upstream Bug Reporting (formalize the `incoming-bugs/` channel)

**Problem.** Products that consume prawduct discover bugs in *prawduct itself*.
Today they file reports by hand into the prawduct checkout's gitignored
`incoming-bugs/` drop-box, and framework sessions triage them by hand. The method
is **undocumented** (the product session-digest never mentions it), has **no
path-discovery** (a product must "just know" where the checkout is), **no inert
behavior** for plugin-only users (who have no local writable checkout), and **no
formalized triage** on the receiving side (reports sit unarchived — today's
worktree-compat report is still in `incoming-bugs/` after the fix shipped).

**Success.**
- A `/prawduct:report-bug` skill files an upstream report when an inbox is
  reachable, and degrades gracefully when it isn't.
- `prawduct-hook bug-inbox` resolves the inbox from `PRAWDUCT_BUG_INBOX` → a
  gitignored `.prawduct/.bug-inbox` file → **none**, validating that the resolved
  directory exists and is writable.
- A bundled template standardizes the existing de-facto report format.
- A terse session-digest pointer makes the channel discoverable. Nothing fires
  automatically; no gate.
- **Inert for plugin-only users:** no inbox ⇒ no upstream write, no error, no
  nag — instead capture an `upstream:prawduct` item in the product's *own*
  backlog and print the canonical GitHub issues URL.
- **Receiving side:** a session-start advisory fires only where
  `incoming-bugs/` exists and is non-empty (naturally absent → inert in product
  repos), nudging triage; the triage→backlog→archive flow is documented.

**Out of scope.**
- No change to how the plugin is installed or updated.
- No automated cross-repo git operations — filing is a plain local file write
  into a gitignored drop-box on the same machine.
- No GitHub API integration — the inert fallback prints the issues URL; it does
  not open issues programmatically.
- Auto-deriving the inbox from the plugin-cache path (decided: fragile — the
  managed cache is not the writable dev checkout).
- Committing the inbox path to shared project state (decided: a non-portable
  absolute path must not travel to other clones/CI).

## Requirements Confidence

**Level:** High — the three decisions (path source, inert fallback, both-sides
scope) were locked with the user, and every mechanism mirrors an existing pattern
(the `prawduct-hook` subcommand dispatch, the `lib/*_probes.py` advisory pattern,
the markdown-skill pattern).

**Open assumptions:**
- [ASSUMPTION: the receiving advisory is gated purely by presence + non-emptiness
  of `<repo-root>/incoming-bugs/`, which is naturally absent in product repos, so
  no explicit "is this the framework repo" marker is needed | LOW impact | add a
  marker gate later if a product coincidentally uses that dir name]
- [ASSUMPTION: the inert fallback captures the bug by having the agent call
  `/prawduct:backlog add` with an `area=prawduct-upstream` tag — not a new hook
  subcommand | LOW impact | user can prefer a dedicated mechanism]
- [ASSUMPTION: the canonical issues URL is
  `https://github.com/brookstalley/prawduct/issues` (from `origin`) | LOW impact |
  override if the public repo differs]

**Persisted-format note (lock-in).** `.prawduct/.bug-inbox` is a one-line local
file holding a filesystem path; the report `.md` follows the existing de-facto
template. Both are low lock-in (local, gitignored, trivially evolved). The one
durable interface is the `bug-inbox` resolver **contract** (precedence
env→file→none; exit 0 + path vs. exit 1; validate exists+writable) — pinned by
tests so the skill can rely on it.

## Surfaces (cascade enumeration — planning.md "enumerate the surfaces")

1. `bin/prawduct-hook` — new `cmd_bug_inbox` + dispatch; register the new probe in `cmd_clear`.
2. new `lib/bug_inbox.py` — pure resolver (env → gitignored file → none; validate).
3. new `lib/upstream_probes.py` — the `untriaged-upstream-reports` probe + `register()`.
4. new `skills/report-bug/SKILL.md` — the filing skill (decide upstream-vs-product, write-or-fallback, triage section).
5. new `templates/incoming-bug-report.md` — the report template.
6. `methodology/session-digest.md` + `methodology/session-digest-slim.md` — ONE terse pointer (char-budget bound: slim ≤ 50% of full).
7. `.gitignore` — add `.prawduct/.bug-inbox`.
8. `CLAUDE.md` — extend the existing "Reviewing product feedback" route to name `incoming-bugs/` triage (governance-protected; keep terse).
9. Tests — new `tests/test_bug_inbox.py`, new `tests/test_upstream_probes.py`, a digest-pointer assertion in `tests/test_plugin_methodology_digest.py`, skill+template existence/content.

## Status

- [ ] Chunk 01: Filing path end to end (resolver + skill + template + gitignore + tests)
- [ ] Chunk 02: Receiving advisory + discoverability (probe + digest pointer + triage docs + tests)

Context: new work cycle, 2026-06-20, branch carries this scope alongside the
small `backlog-ship-in-pr` docs fix (one PR, two change-log scopes — to minimize
review wall-clock per the CRT-4J8W single-cumulative gate). `views_enabled: true`
— checkboxes flip at release via the `scope=upstream-bug-reporting` change-log tag.

## Chunks

### Chunk 01: Filing path end to end (thin vertical slice)

Proves the architecture: **resolve → write-or-fallback**, the whole filing flow.

- `lib/bug_inbox.py`: `resolve_inbox(environ, project_dir) -> Path | None`.
  Precedence: `PRAWDUCT_BUG_INBOX` env → first line of gitignored
  `<project_dir>/.prawduct/.bug-inbox` → `None`. Expand `~` and resolve relative
  to the file's repo. Return `None` (not raise) when the resolved path doesn't
  exist or isn't a writable directory — so a stale config fails soft.
- `bin/prawduct-hook bug-inbox`: prints the resolved inbox path + exit 0, or
  prints nothing + exit 1 when there is no inbox. This exit code IS the signal the
  skill branches on.
- new `skills/report-bug/SKILL.md`: (1) confirm the bug is in *prawduct*, not the
  product; (2) run `prawduct-hook bug-inbox`; (3a) exit 0 → fill
  `templates/incoming-bug-report.md` and write `<inbox>/<kebab-slug>.md`; (3b)
  exit 1 → `/prawduct:backlog add` an item tagged `area=prawduct-upstream` in the
  product's own backlog AND print `https://github.com/brookstalley/prawduct/issues`.
  Never error on the no-inbox path.
- new `templates/incoming-bug-report.md`: title → `Severity / Component /
  Reported / Found in / Reporter` → `Summary / Context / Symptoms / Root cause (if
  known) / Suggested fix` (codifies the existing de-facto shape).
- `.gitignore`: add `.prawduct/.bug-inbox`.
- **Type:** code.
- **Done when:**
  1. `tests/test_bug_inbox.py` covers: env set+valid → path; env set+stale →
     None; file set+valid → path; file set+stale/unwritable → None; neither set →
     None; and the `bug-inbox` subcommand's exit-0/1 contract. Skill + template
     exist with the asserted sections. Full suite green.
  2. `/prawduct:critic` (inference picks `chunk` — fast Goals 1-3 over the
     resolver + skill) run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 02: Receiving advisory + discoverability

- `lib/upstream_probes.py`: `probe_untriaged_upstream_reports(state, codebase)`
  fires when `codebase.root / "incoming-bugs"` exists and holds ≥1 `*.md`
  (excluding a bundled template/README, if any) → an `info` advisory recommending
  `/prawduct:backlog` triage. Evidence is the report count's qualitative form
  (count-independent id, live count in the summary — D14). `register()` it.
- `bin/prawduct-hook` `cmd_clear`: call `upstream_probes.register()` alongside the
  backlog probes.
- new `skills/report-bug/SKILL.md` gains a **Receiving side** section: triage each
  report into committed backlog items (`/prawduct:backlog add`), then move the
  processed report to `incoming-bugs/archive/` (the backlog item is the durable
  record; `incoming-bugs/` is gitignored).
- `CLAUDE.md` "Reviewing product feedback" route: name `incoming-bugs/` triage.
- `methodology/session-digest.md` + `session-digest-slim.md`: ONE terse pointer —
  e.g. "Hit a bug in prawduct itself? `/prawduct:report-bug` files it upstream
  when a local checkout is configured, else captures it locally." Keep the slim
  variant ≤ 50% of full (existing budget test).
- **Type:** cumulative-final (the chunk's own review IS the single
  `/prawduct:critic cumulative` over `merge-base...HEAD` that gates the PR —
  covers Chunk 01's code + this chunk, one review run).
- **Done when:**
  1. `tests/test_upstream_probes.py`: fires when non-empty; inert (returns `[]`)
     when `incoming-bugs/` is absent (the product-repo case) or empty. Digest
     pointer present in both files; slim still ≤ 50%. Full suite green.
  2. `/prawduct:critic cumulative` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

## Verification Strategy

The resolver and probe are pure functions — unit tests cover every
env/file/none branch and the fire/inert split (the inert cases ARE the
plugin-user and product-repo guarantees, so they are first-class tests, not
afterthoughts). The skill is agent-driven prose: content assertions guard its
structure, and the `bug-inbox` subcommand lets me exercise resolution live
against a temp inbox (set `PRAWDUCT_BUG_INBOX` to a tmpdir → confirm a report
lands; unset everything → confirm exit 1 and the local-capture fallback). The
cumulative Critic reviews coherence across the skill, template, digest pointer,
and CLAUDE.md route — that they tell one story about when filing is active vs.
inert.
