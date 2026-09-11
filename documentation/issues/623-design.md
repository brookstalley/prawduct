# Issue #623 — Add `gh` Auth Preflight to Doctor for the Issues Backend: Design

`status: draft · stage: design · area: backlog · added: 2026-08-24 · source:
scheduled backlog session · issue: https://github.com/brookstalley/prawduct/issues/623`

Builds on `documentation/issues/623-requirements.md` (Decisions 1–6, requirements GHA-1–GHA-8).
That document scoped one item out to design: *"Exact wording/format of `gh auth status`'s output
across `gh` CLI versions — this environment has no `gh` binary to re-verify against; the design
pass should re-confirm current output shape against an installed `gh` before parsing it."* No
`gh` binary is available in this environment either (confirmed again during this pass), so this
document specifies a **parser tolerant of both plausible output shapes** rather than asserting
one, and names the exact empirical check the implementing chunk must run first — the same
posture 221-design.md's §2 used for its own unverified harness-event precondition.

Grounding facts re-verified against current `develop` (2026-08-24, twelve days after the
requirements pass): `RETRYABLE_DEFAULTS` (`transport.py:73-83`), `build_env()` (`:232-244`,
pass-through of `GH_TOKEN`/`GITHUB_TOKEN` unchanged), `GhTransport._spawn`
(`:854-877`, `FileNotFoundError` → `TransportError("unavailable", …)`), `_map_failure`'s `auth`
mapping (`:891-935`), `_parse_head` (`:134-153`), `learnings_obligation.py`'s status-constant /
`check()` shape, `cmd_learnings_obligation` (`prawduct-hook:5358-5419`), Health Check #12's
`gh`-unavailable skip wording (`doctor/SKILL.md:57`, one line later than the requirements doc's
citation — no content drift, only the file grew above it), and `read_str_yaml_key` call sites
(`briefing.py:681,933`). No material drift found; line numbers below are current.

## 1. Summary of what ships

1. **GHA-1, GHA-3, GHA-4** — a new module `plugin/lib/gh_preflight.py`, one function `check()`,
   returning three independent findings (`gh`, `auth`, `scope`) rather than one collapsed status —
   mirroring `learnings_obligation.py`'s shape (small module → one subcommand → one doctor line)
   per the requirements doc's Decision 1, but with a wider return shape because this check reports
   three orthogonal conditions instead of one.
2. **GHA-2, GHA-5** — the check reads `backlog_service_repo` via the existing
   `read_str_yaml_key` helper and is a no-op when unset; every non-skip finding carries a
   concrete remedy string.
3. **GHA-3** — detection reuses `GhTransport._spawn` directly (not a second subprocess wrapper),
   so the missing-binary path is the exact code path `reconcile-labels` already exercises.
4. **New top-level command** `prawduct-hook gh-auth-preflight [--json]`, wired the same way
   `learnings-obligation` is: a `cmd_gh_auth_preflight` function, one `elif` dispatch line, one
   `_HELP` usage line, one `_EPHEMERAL_SAFE_COMMANDS` entry (read-only, no `--apply` — GHA-7 rules
   out auto-remediation, so this command never needs the apply-gated set).
5. **Doctor Health Check #19** — a new numbered check in `plugin/skills/doctor/SKILL.md`, relaying
   the command's three findings, following Check #12's and #13's existing prose pattern.

## 2. `plugin/lib/gh_preflight.py`

**Statuses** — three small closed sets, one per finding, rather than `learnings_obligation`'s
single five-way status, because GHA-1 requires the three conditions stay **distinct** (a caller
must be able to say "gh is fine, you're just under-scoped" without inferring it from a combined
enum):

```python
# plugin/lib/gh_preflight.py

GH_PRESENT = "present"
GH_MISSING = "missing"

AUTH_OK = "authenticated"
AUTH_MISSING = "unauthenticated"
AUTH_UNKNOWN = "unknown"       # gh itself missing — nothing to ask

SCOPE_OK = "ok"
SCOPE_INSUFFICIENT = "insufficient"
SCOPE_UNCHECKED = "unchecked"  # fine-grained PAT / App token / GITHUB_TOKEN / not reachable
```

**`check(project_dir)` → dict**, the shape `cmd_gh_auth_preflight` relays:

```python
def check(project_dir: Path) -> dict:
    """Read-only gh-auth preflight for the Issues backend. No write, ever (GHA-7).

    Returns a dict with a top-level ``skipped`` bool (GHA-2) and, when not
    skipped, three independent findings — ``gh``, ``auth``, ``scope`` — each a
    ``{"status": ..., "detail": ..., "remedy": str | None}`` triple. A later
    finding is only meaningful once an earlier one clears: ``auth`` is
    ``unknown`` when ``gh`` is ``missing``, and ``scope`` is ``unchecked``
    whenever ``auth`` is not ``authenticated``.
    """
    repo = core.read_str_yaml_key(
        project_dir / ".prawduct" / "project-state.yaml", "backlog_service_repo"
    )
    if not repo:
        return {"skipped": True, "reason": "backlog_service_repo unset"}

    transport = _gh_transport().GhTransport()
    try:
        proc = transport._spawn(["auth", "status", "--hostname", "github.com"])
    except _gh_transport().TransportError:
        # _spawn's own mapping: FileNotFoundError -> "unavailable", nothing
        # else escapes it (timeout is the other case; scope/auth are moot).
        return _result(gh=GH_MISSING, auth=AUTH_UNKNOWN, scope=SCOPE_UNCHECKED)

    # `gh` reached; combine both streams — output-placement (stdout vs stderr)
    # for `auth status` is not re-verified in this environment (no `gh`
    # binary), so the parser must not depend on which stream carries it.
    combined = f"{proc.stdout}\n{proc.stderr}"

    if proc.returncode != 0:
        return _result(gh=GH_PRESENT, auth=AUTH_MISSING, scope=SCOPE_UNCHECKED)

    scopes = _parse_token_scopes(combined)  # None when no "Token scopes:" line
    if scopes is None:
        return _result(gh=GH_PRESENT, auth=AUTH_OK, scope=SCOPE_UNCHECKED)
    if "repo" in scopes or "public_repo" in scopes:
        return _result(gh=GH_PRESENT, auth=AUTH_OK, scope=SCOPE_OK)
    return _result(gh=GH_PRESENT, auth=AUTH_OK, scope=SCOPE_INSUFFICIENT)
```

`_parse_token_scopes` looks for a line matching `Token scopes:` (case-sensitive, `gh`'s own
wording) and splits the quoted, comma-separated list after the colon into a set — returning
`None` when no such line is present anywhere in the combined output, which is the fine-grained
PAT / App token / `GITHUB_TOKEN` case GHA-4 requires reported as `unchecked`, never inferred as a
pass.

`_gh_transport()` is a lazy import of `lib.backlog.transport` (mirrors the existing lazy-import
convention `cmd_learnings_obligation` uses for `lib.learnings_obligation` — see §3), so
`gh_preflight.py` does not force-load the backlog adapter for products that never touch it.

**Why `scope: ok` accepts either `repo` or `public_repo`, unresolved against the target's actual
visibility.** Decision 2 restricts detection to `gh auth status` alone — no live repo-scoped API
call used as a probe. Determining whether `<target>` is public would need exactly that kind of
call. Reporting `insufficient` only when **neither** scope is granted is the conservative,
no-extra-call reading: a token holding only `public_repo` might still be enough for this specific
repo, so the check does not manufacture a false-insufficient finding it cannot back up, and GHA-5's
remedy wording (§4) states the caveat explicitly rather than resolving it.

## 3. `prawduct-hook gh-auth-preflight` command

New function, placed beside `cmd_learnings_obligation` (`prawduct-hook:5358-5419`) and following
its structure line for line — flag-only, `--json` optional, no `--apply` (GHA-7: this check never
writes):

```python
def cmd_gh_auth_preflight(project_dir: Path, argv: list[str]) -> int:
    """Read-only gh-auth preflight for the Issues backend (doctor Health Check #19).

    Reports three distinct findings — gh installed, authenticated, scope
    sufficient-or-unverifiable — never one collapsed status (#623/GHA-1).
    Exit 0 whenever the check ran, including every degraded finding: a
    finding is not a failure, matching learnings-obligation's dry-run
    convention. Exit 1 only when the check itself could not run (lib not
    importable). Unknown flags are 2.
    """
    rejected = _reject_unknown_args("gh-auth-preflight", argv, {"--json"})
    if rejected is not None:
        return rejected
    as_json = "--json" in argv

    lib_root = _plugin_root()
    if lib_root not in sys.path:
        sys.path.insert(0, lib_root)
    try:
        from lib import gh_preflight  # noqa: PLC0415 — lazy keeps top-level cheap
    except ImportError as exc:
        print(f"error: gh-auth-preflight could not import the plugin lib/ ({exc})", file=sys.stderr)
        return 1

    result = gh_preflight.check(project_dir)
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        _print_gh_preflight_human(result)
    return 0
```

`_print_gh_preflight_human` prints one line for `skipped` and, otherwise, one labelled line per
finding plus its remedy when the finding is not the healthy value — same "status line + indented
detail" shape `cmd_learnings_obligation` uses (`prawduct-hook:5405-5406`).

**Wiring (three sites, matching `learnings-obligation`'s exactly):**

- Dispatch (`prawduct-hook:6969-6970`'s neighborhood): add
  `elif command == "gh-auth-preflight": return cmd_gh_auth_preflight(project_dir, sys.argv[2:])`
- `_HELP` usage block: add a line beside `learnings-obligation`'s —
  `"  gh-auth-preflight [--json]   (Issues-backend gh CLI/auth/scope check; no-op if "
  "backlog_service_repo is unset; read-only, no --apply)\n"`
- `_EPHEMERAL_SAFE_COMMANDS` (`prawduct-hook:6329-6367`): add `"gh-auth-preflight"` — this is the
  **fail-closed allowlist of reads** for the ephemeral-worktree guard (§ comment at
  `:6310-6321`: an unlisted command defaults to refused-inside-an-ephemeral-worktree). Missing
  this entry does not break the check outside an ephemeral worktree, but silently refuses it
  inside one — a real doctor call this check must not regress, since doctor itself can run from a
  disposable subagent worktree.

`gh-auth-preflight` does **not** join `_EPHEMERAL_APPLY_GATED_COMMANDS` (`:6371-6378`) — that set
is for commands with an `--apply` mutation branch, and GHA-7 rules that out entirely for this
command.

## 4. Remedy wording (GHA-5, Decision 4)

Each non-healthy finding's `remedy` string, computed in `check()` (not deferred to the caller, so
`--json` consumers get the same wording doctor relays):

- **`gh: missing`** → `"install the gh CLI and ensure it is on PATH (https://cli.github.com)"`.
- **`auth: unauthenticated`** — branches on whether `GH_TOKEN`/`GITHUB_TOKEN` is set in
  `os.environ` (Decision 4; `build_env()` passes both through unchanged, so their presence in the
  ambient environment is exactly what `gh` itself will honor):
  - neither set → `"run: gh auth login"`
  - either set → `"GH_TOKEN/GITHUB_TOKEN is set but gh reports unauthenticated — check or rotate "
    "the token that variable points at (an interactive 'gh auth login' will not change what an "
    "automated session uses)"`
- **`scope: insufficient`** →
  `f"grant the repo scope: gh auth refresh -h github.com -s repo (public_repo may already be "
  f"enough if {repo} is public, but this check does not look up the repo's visibility)"`.
- **`scope: unchecked`** → no actionable remedy; `detail` states the reason
  (`"this token type exposes no scope signal to gh auth status (fine-grained PAT, GitHub App "
  "installation token, or GITHUB_TOKEN) — scope cannot be verified from here"`), matching GHA-4's
  "never coalesced with, or reported as, a passing scope check."

## 5. Doctor Health Check #19

Inserted in `plugin/skills/doctor/SKILL.md` immediately after Check #18 (the file's current last
check, "Delegation policy unrecorded" — `SKILL.md:71`), following Check #12's own paragraph
shape and its `backlog_service_repo` skip-rule wording (Decision 5/GHA-2 — same gate, same
phrasing, not a re-derived rule):

```markdown
19. **`gh` auth preflight (post-cutover only)** — run `prawduct-hook gh-auth-preflight` and relay
    its three findings. **Unset `backlog_service_repo` → skip** (same rule as Check #12: the repo
    is on the markdown backend, nothing to preflight; this is healthy, not a finding). Report
    **degraded** on any of: `gh` missing, unauthenticated, or scope `insufficient` — each names its
    own remedy (install gh; `gh auth login` or check/rotate a `GH_TOKEN`/`GITHUB_TOKEN`, depending
    on which is set; `gh auth refresh -h github.com -s repo`). `scope: unchecked` is **not** a
    finding on its own — report it as a note beside a healthy `gh`/`auth` pair, never as degraded:
    a fine-grained PAT, GitHub App installation token, or `GITHUB_TOKEN` simply exposes no scope
    signal to `gh auth status`, and grading the absence of a signal as unhealthy would make an
    entire class of legitimate credentials permanently degraded. This check performs no write and
    does not require `reconcile-labels` (Check #12) to have run — the two are independent reads
    over the same `gh` identity.
```

## 6. Files touched

| File | Change |
| --- | --- |
| `plugin/lib/gh_preflight.py` | new — `check()`, status constants, scope parsing (§2) |
| `plugin/bin/prawduct-hook` | add `cmd_gh_auth_preflight`, `_print_gh_preflight_human`; wire dispatch, `_HELP`, `_EPHEMERAL_SAFE_COMMANDS` (§3) |
| `plugin/skills/doctor/SKILL.md` | new Health Check #19 (§5) |
| `tests/` | new coverage — see §7 |

No change to `plugin/lib/backlog/transport.py` or any other adapter file — `GhTransport._spawn`
is called, not modified (Decision 2/GHA-3: reused, not duplicated).

## 7. Testing strategy → acceptance mapping

- **`check()` unit tests** (`test_gh_preflight.py`, fake/monkeypatched `GhTransport._spawn`
  rather than a real `gh` call): missing binary → `gh=missing, auth=unknown, scope=unchecked`;
  non-zero exit → `gh=present, auth=unauthenticated, scope=unchecked`; zero exit with a
  `Token scopes: 'repo', 'gist'` line → `scope=ok`; zero exit with `'public_repo'` only →
  `scope=ok`; zero exit with `'gist'` only (no repo scope) → `scope=insufficient`; zero exit with
  no `Token scopes:` line at all → `scope=unchecked`; `backlog_service_repo` unset →
  `{"skipped": True, ...}` and `_spawn` never called (proves GHA-2's no-op is unconditional, not
  just untested).
- **Remedy-branch tests**: `GH_TOKEN` set vs unset vs `GITHUB_TOKEN` set, each producing the
  correct unauthenticated-remedy string (Decision 4/§4).
- **`cmd_gh_auth_preflight` tests** (`test_prawduct_hook.py`, beside the existing
  `learnings-obligation` tests): unknown flag → exit 2; `--json` emits the dict verbatim; human
  output prints one line per finding; exit is always 0 when `check()` returns (import failure is
  the only 1).
- **`_EPHEMERAL_SAFE_COMMANDS` membership test**: `gh-auth-preflight` is classified read-only by
  the ephemeral-worktree guard (a regression here silently refuses a real doctor check inside a
  disposable subagent worktree — the exact class of bug `_EPHEMERAL_SAFE_COMMANDS`'s own comment,
  `:6324-6328`, says is verified by reading each implementation, not inferred from its name).
- **Acceptance criterion "no write, ever"** is not a unit-testable negative in the usual sense;
  it is satisfied by construction (`check()` calls only `_spawn`, never `_run`'s write paths, and
  the module imports no write-capable adapter method) and should be recorded as a design-time
  guarantee in the implementing chunk's Critic review, the same treatment 221-design.md §6 gives
  its own by-construction acceptance criterion.
- **Doctor Health Check #19's prose** is verified by reading the diff against §5, plus one live
  manual run of `/prawduct:doctor` against a real post-cutover repo with a real `gh` identity —
  the same category of live-harness check issue #183 is separately trying to keep from silently
  never draining, so file it there rather than inventing a second deferred-verification queue.

## 8. Scope-out (unchanged from requirements, plus the resolved item)

Carries the requirements doc's scope-out list forward verbatim (no new `TransportError` code, no
touch to `refresh_counts`, no auto-remediation, no onboarding-time addition, #622 stays a sibling
not a merge target). The one item requirements scoped to design — exact output-format handling
across `gh` versions — is resolved by §2's dual-stream, tolerant-of-either-shape parser rather
than by empirical confirmation, since no `gh` binary exists in this environment to confirm
against (stated at both passes, not newly discovered here).

**Added by this design pass, carried to implementation:**

- **Empirical verification of `gh auth status`'s actual output shape is a precondition of
  merging, not of this design.** The implementing chunk's first done-when step must run
  `gh auth status --hostname github.com` for real, on at least one classic-PAT identity and one
  fine-grained-PAT-or-`GITHUB_TOKEN` identity, and confirm: (a) which stream(s) carry the
  `Token scopes:` line, (b) the exact line format `_parse_token_scopes` must match, (c) that a
  fine-grained/App/`GITHUB_TOKEN` identity really does omit the line as Grounding facts assumed
  from GitHub's documentation rather than a live run. If any of the three differs from what §2
  assumes, `_parse_token_scopes` is the only function that needs to change — `check()`'s
  three-finding contract and the command/doctor wiring around it do not depend on the exact
  regex.
- **Repo-visibility resolution for the `public_repo`-only case** (§2's "Why `scope: ok` accepts
  either" paragraph) — deliberately not resolved by an extra live call; a future item may add one
  if the caveat in the remedy text (§4) proves confusing in practice, but that is new scope.

## 9. Evidence / references

- `documentation/issues/623-requirements.md` — Decisions 1–6, requirements GHA-1–GHA-8, this
  design's starting point; names the exact scope-out item (output format) this document resolves.
- `plugin/lib/backlog/transport.py:73-83` (`RETRYABLE_DEFAULTS`), `:232-244` (`build_env`),
  `:393-396` (`GhTransport.__init__` — no required args), `:854-877` (`_spawn`, reused directly
  per Decision 2/GHA-3), `:885-935` (`_run`/`_map_failure`, the write-path pattern this check
  deliberately does not call into), `:134-153` (`_parse_head`, the header-parsing precedent for a
  scope check, though this design's scope check reads `gh auth status` text rather than HTTP
  headers, per Decision 2's "no live repo-scoped API call").
- `plugin/lib/learnings_obligation.py:15-73` and `plugin/bin/prawduct-hook:5358-5419`
  (`cmd_learnings_obligation`) — the shape this design's module and command mirror throughout
  (status constants, lazy import, flag-only `_reject_unknown_args`, human/`--json` dual output).
- `plugin/bin/prawduct-hook:6310-6328` (`_EPHEMERAL_SAFE_COMMANDS`'s own comment — verified by
  reading each implementation, never inferred from its name) — grounds §3's wiring requirement
  and §7's regression test.
- `plugin/skills/doctor/SKILL.md:57` (Check #12's `gh`-unavailable / `backlog_service_repo`-unset
  skip wording, the precedent §5 mirrors), `:71` (Check #18, the current last check — §5 inserts
  immediately after it as #19).
- `plugin/lib/briefing.py:681,933` — existing `read_str_yaml_key(…, "backlog_service_repo")`
  call sites, the precedent GHA-2/§2 reuse.
- Issue #623 — problem statement, "not the bug it looks like" analysis, and acceptance criteria
  this document and the requirements doc jointly ground.
