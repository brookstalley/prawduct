---
schema: 1
type: feature
scope: host-seam
date: 2026-10-26
title: One host seam for hook payloads, roots and responses
closes: [brookstalley/prawduct#1037]
---

#1037, the first build step of #928's portable host adapters. What a hook reads from its
harness, and what it writes back, now lives in one module, `plugin/lib/host.py`. Before this, it
was spread across the Stop and SubagentStop handlers, the gates, the banner, the digest and two
config-home readers. A second host (Codex, #1038) becomes a second implementation of that module
rather than a patch at each site. Claude Code's behaviour is unchanged.

### Chunk 01: goldens first

- `tests/test_host_seam_golden.py` runs the real entry points the way the harness does, one
  subprocess per case, in a sealed environment: `banner.py`, `digest.py`, `clear --session-start`
  with and without `--brief-only`, `stop` (clean, blocking, and advisory at exit 0, across seven
  payload shapes), and `subagent-stop`. It compares stdout, stderr and the exit code byte for byte
  against goldens recorded from the code before the refactor.
- Five exact run facts are normalized, and the docstring names them: the temp path, the plugin
  root, the plugin version, the checkout's `ref@sha[+dirty]` and the digest text.
- A case with `CLAUDE_CONFIG_DIR` pointing at a populated config home pins the briefing's
  transcript scan. Its control checks that the line comes from the config home and nothing else.

### Chunk 02: the seam

- `host.read_event` turns a parsed payload into a `HostEvent`, and it is the only reader of payload
  keys. `fields_present` keeps an absent field apart from one sent as `null`. Background tasks
  arrive as `<type>:<ident>` labels, because the task entries' field names are part of Claude's
  payload shape too.
- `host.plugin_root`, `project_dir_hint`, `config_home` and `config_roots` are the only readers of
  `CLAUDE_*` variables. `host.emit_session_context`, `emit_stop_advisory` and `block` are the only
  writers of structured hook responses and of the Stop hook's blocking exit.
- Plain text the hooks print in place is not routed yet: the briefing and the banner on stdout,
  and the notes the Stop writes to stderr ahead of its block. Claude Code reads both channels, so
  this text is part of its response too. A host that reads them differently moves them into the
  seam; that is #1038's work.
- `PRAWDUCT_HOST` names the host and defaults to `claude`. A host adapter's hook registration sets
  it, rather than prawduct detecting the host, because Codex exports `CLAUDE_PLUGIN_ROOT` for
  compatibility. An unknown value blocks `stop`, with a reason that names the variable, and records
  the block like any gate's (gate `host`, registered as `unknown-host` since 3.8.0). The hooks
  that cannot block (`clear --session-start`, `subagent-stop`, the banner, the digest) print a note
  and do nothing.
- The entry points load the seam by file path from their own plugin tree, before `lib` is
  importable. A seam that fails to load is not left half-built for the next caller.
- The gate readers take a `HostEvent` instead of the raw dict.
- One behaviour change, deliberate: the banner's managed-install check now expands `~` in
  `CLAUDE_CONFIG_DIR`, as the other config readers already did.
- `tests/test_host_seam.py` scans `plugin/bin`, `plugin/lib` and `plugin/hooks` for a host variable,
  payload key or response key outside the seam. It also checks, with a spy, that a blocking Stop
  exits through `host.block`, and it covers an unknown `PRAWDUCT_HOST` on every hook.
- `928-requirements.md` § "Next step" records R-8(a) as satisfied by the receipt posted on #928,
  and names this item and then #1038 as the next work.

### Chunk 03: parity on real repos

- `tools/host-seam-parity.py` makes copy-on-write copies of each governed repo beside this
  checkout. It runs the same hook events through the base and head plugins (both exported from
  git), and compares every step's output.
- Run on 2026-10-26 against the owner's machine (`b9d9489d` against `17f84cd6`): every repo it
  could copy matched on all ten events. It skipped linked worktrees, directories that aren't git
  repos, and one repo over 20 GB. Re-derive with
  `tools/host-seam-parity.py --work <dir> --base b9d9489d --head 17f84cd6`. A run
  against a plugin 25 commits older reports its banner, digest and briefing differences, so a clean
  result is not the tool going blind.
- The sweep names its noise instead of hiding it. The Stop gate's working-tree id and the backlog
  snapshot's age vary with the clock. In a repo whose `.gitignore` misses `.advisories.json`, the
  hooks' second-resolution timestamps land in the working tree. Those two facts are normalized,
  and nothing else is beyond the copy path and the plugin root.

## Consumer note
Nothing changes in a Claude Code session: the hooks print the same bytes and exit with the same
codes. One edge case moves: if `CLAUDE_CONFIG_DIR` holds a literal `~`, the banner now expands it,
as the rest of prawduct already did. Host adapters set the new `PRAWDUCT_HOST` variable in their
hook registration. Leave it unset under Claude Code, because an unrecognised value makes the Stop
hook block until it is fixed.
