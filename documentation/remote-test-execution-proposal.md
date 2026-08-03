# Remote Test Execution — Proposal

**Status:** v0.1 (2026-08-03) — proposal only, nothing built in prawduct. A working
reference implementation exists in **discodon** on branch `perf/remote-test-lane`
(unmerged), which is the thing this proposes to generalize.

**Audience:** Future-you (or future-Claude) picking this up after `/clear`. Self-contained —
read it cold and resume without the chat history that produced it.

**Scope:** Whether and how prawduct should carry an opt-in mechanism for dispatching a
repo's test suite to a remote host, across the growing set of prawduct-managed repos.

**Out of scope:** The discodon lane itself (already built, already documented in that repo's
`documentation/TESTING.md` § Remote Stage 3). Anything about *which* tests run — this is
about where they execute, not what.

---

## 1. The problem

Test suites are slow on the laptop, and there is one fast Linux box available. Several
repos want to use it. The constraint that shapes everything: **other contributors must be
unaffected**. A contributor who clones a repo and runs its test script must see identical
behaviour, with no new dependency, no new configuration, and no awareness that remoting
exists.

This is not hypothetical. `scriob`'s majority contributor is Mark Pace (1015 commits to
Brooks' 315).

### The hardware

`gpu-bozeman` — Ubuntu 26.04, 32 threads, 60 GB RAM, RTX 3080, Docker 29.6.2, running a
long-lived `discodon-test` container. Reachable at `gpu-bozeman.zt.tangentry.com` (a public
A record pointing at the ZeroTier address `10.230.170.20`; also on the LAN at
`10.23.17.20`). An `ssh gpu-bozeman` alias with connection multiplexing is configured in
`~/.ssh/config` on the M5 laptop.

---

## 2. What exists today (discodon)

Branch `perf/remote-test-lane`, three files:

| File | Content |
|---|---|
| `tools/remote-setup.sh` | Provisions the container on the remote host (~101 lines) |
| `tools/remote-test.sh` | Executes inside the container, in the synced tree (~142 lines) |
| `tools/test.sh` | Adds `remote_key`, `remote_reachable`, `remote_stage_commit`, `stage_commit_dispatch` (+144 lines) |

**The split that matters:** roughly **40 lines are generalizable dispatch** — probe, rsync,
exec, concurrency slot. The remaining **~100 lines are discodon-specific tree preparation**
and cannot be shared with any other repo:

- A synthetic git repo, because three separate Stage 3 concerns each need a *different* git
  property: `_detect_git_branch` shells out to `git rev-parse` (needs a real commit — an
  unborn branch exits 128); `run_lint` scopes to `git ls-files '*.py'` and fails loud on an
  empty set (needs a populated index); `tools/testlock.py` needs a git common dir. The real
  `.git` is excluded from the rsync deliberately — 700 MB, and a linked worktree's `.git` is
  a *file* holding an absolute host path that dangles remotely.
- A placeholder `.env` for `DD_MCP_PROD_TOKEN`, because a unit test calls `sys.exit(1)`
  without it.
- A Style Dictionary rebuild (`npm ci && npm run tokens`), because 37 assertions read
  gitignored build products that never arrive over rsync.

**This is the central finding of the whole investigation.** The valuable, reusable part is
small. The part that would rot is repo-specific and was never shareable. Copy-pasting 40
lines across repos is not the problem people assume it is.

### Concurrency design

Three slots of eight workers rather than one of twenty-four. Measured on the 16c/32t host,
full Stage 3, all green:

```
-n8     130.7s wall    12m05 CPU
-n16    110.8s wall    21m17 CPU
-n24    124.3s wall    22m06 CPU   <- slower than -n16
```

Past ~8 workers the extra CPU buys nothing. Throughput comes from concurrency *across*
agents, not width *within* a run. Slots are `flock`-based, in `/testruns/.slots`.

**Untested:** the semaphore has never been exercised under real concurrency. The all-busy
fallback queues on `slot.1` specifically, so a run can wait behind a long holder while slots
2 and 3 free up first — a fairness wart, not a bug. This is still the open item.

---

## 3. The proposal: generalize the contract, not the script

Three properties made the discodon lane safe. They are the whole reusable design, and they
are about ten lines of thinking, not 142 of shell:

1. **Opt-in through an env var that is unset by default.** Unset ⇒ byte-identical
   behaviour. Contributors are unaffected *by construction*, not by care.
2. **Bounded probe, fall back to local, never fail the gate on unreachability.** Being
   offline is a normal operating condition, not an error. Costs one 5s check and a printed
   line.
3. **Anything that writes the real working tree stays local.** In discodon that is lint —
   `run_lint` fixes `openapi.json` by rewriting it in place, so it must see the real tree.

### Why prawduct is the right home

Not because prawduct needs a test-runner feature, but because the distribution problem is
already solved there and nowhere else:

- **Presence.** Of nine repos sampled, **seven** have `.prawduct/`: discodon, scriob,
  samsung-frame-art-loader, hallucinote, prawduct itself, trenchant, worldground. (3tears
  and recco do not.)
- **A per-repo config format that already describes how to run tests.** `project-state.yaml`
  carries `test_command`, which `prawduct-hook test-evidence record` already invokes.
- **A binary that already runs it**, and versioned plugin distribution for shipping changes.

Dagger's module system is attractive precisely *because* it solves distribution. That
problem is already solved here.

### It closes an existing gap rather than adding one

discodon's `documentation/TESTING.md` records that `prawduct-hook test-evidence record` runs
a bare `pytest`, takes no cross-run lock, and is a **frequent** full-suite entry point —
tracked there as **TST-Q7ZK**. Putting dispatch in prawduct means that entry point inherits
the lane and the arbitration instead of bypassing both.

### Sketch

Each repo declares its own prep beside its existing `test_command` — sync excludes, container
image, prep commands. discodon's `remote-test.sh` becomes the *reference example* of a prep
block, not a thing to copy.

---

## 4. Alternatives evaluated and rejected

Recorded so these are not reconsidered from scratch. **All findings verified 2026-08-03.**

### Earthly — dead, do not consider

Earthly Cloud shut down **2025-07-16**. The company's own post-mortem is titled *"We built
the fastest CI in the world. It failed."* — they concluded compute-as-commodity could not be
monetized. Earthly Technologies pivoted entirely to **Earthly Lunar** (software
governance/compliance); builds and CI are no longer their business. The OSS project is **not
actively maintained** — they stopped reviewing PRs and accepting contributions, committing
only to critical bug fixes, and pointed the community at a fork. This is an exit, not
maintenance mode.

### Dagger — good tool, but the load-bearing feature is the unsupported one

Genuine wins: modules solve multi-repo distribution; content-addressed caching would eat the
per-run prep cost; **dirty trees are native** (it takes a host directory, not a git ref, so
unlike GitHub Actions it does not convert a pre-commit gate into a different gate); service
containers are a clean answer to scriob's testcontainers problem.

What rules it out:

- Remote execution is `_EXPERIMENTAL_DAGGER_RUNNER_HOST`, documented verbatim as
  *"experimental and may change in future."*
- **SSH is not among the documented transports** — the list is `container://`, `image://`,
  `kube-pod://`, `unix://`, `tcp://`. The `ssh://` form people use is undocumented, with a
  reported CLI timeout against it (dagger#5852).
- Issue **dagger#9516** — *"Stabilize the Engine remote protocol?"* — framed the choice as
  binary (stabilize properly, or discontinue the hatch) and **closed without remote
  connections becoming officially supported**, despite heavy production use.
- `tcp://` is plaintext; Dagger sets up no encryption itself.
- **It does not fix the shim class.** You still get a container holding a synced directory
  with no `.git`. Zero improvement on the part most likely to rot.
- Contributor story gets worse: Dagger CLI + Docker daemon become prerequisites.

Worth revisiting *only* as a **local** containerized test environment — caching and modules,
default runner, nothing touching the escape hatch. That is a different project.

### `pytest-xdist --tx ssh=host --rsyncdir` — the purpose-built standard, still a worse fit

Closest thing to a real standard answer for a pytest suite. Three reasons against: no
container isolation (needs matching Python and the full dep set already installed remotely);
`--rsyncdir` is far dumber than a curated exclusion list; and the decider — discodon's own
backlog **TST-6KQD** already hypothesizes *non-serializable content crossing the execnet
boundary* as a flake cause. `--tx ssh` routes **every** test across that boundary.

### `docker context` / `DOCKER_HOST=ssh://` — adopt the plumbing, it changes nothing else

First-class Docker; would delete the `ssh … docker exec` plumbing and the SSH options
string. **Does not delete the rsync** — bind mounts resolve on the *remote* daemon's
filesystem, so a dirty local tree still has to get there. Shrinks the script; does not
change the design. Worth folding in.

### Self-hosted GitHub Actions runner — for later stages only

Structurally cannot serve a pre-commit gate: **that gate exists to check a dirty tree.**
Requiring a push first does not relocate it, it converts it into a different gate
(commit → push → pickup → checkout → sync → test → read result in a browser). It also
collides with the never-force-push rule, forcing WIP-commit churn. Appropriate for
push-time stages (discodon's Stage 4/5), where discodon's own test-loop plan already ruled
the payoff insufficient: *"Stage 4 runs ~5% as often as Stage 3; the payoff is not there."*

---

## 5. Per-repo assessment

### discodon — reference implementation, ready

Lane extracted to `perf/remote-test-lane` (0 behind, 2 ahead of develop; diff is exactly the
lane, 6 files, +447/−2). Ready to PR. Not yet run end-to-end since extraction.

### scriob — real candidate, three genuine blockers

- **testcontainers.** The integration tier spins NATS + Postgres per run via
  `threetears.core.testing.fixtures`. Running the suite *inside* a container on a remote host
  needs a Docker daemon there — DinD or socket passthrough, plus a network path to whatever
  it spawns. discodon's lane has no analogue, so nothing built so far answers this.
  **This must be settled before the scriob design is decidable.** It is an experiment, not a
  discussion.
- **The `.3tears` symlink.** `scripts/test.sh` calls `link-3tears.sh` because editable path
  deps resolve through a per-machine link. This is the *same class* as discodon's git shim —
  a host-shaped assumption that will not survive rsync into a container. A second independent
  instance is evidence the shim class is inherent to this approach, not a discodon accident.
- **Fan-out.** engine + server + frontend, each with its own venv and pytest config. The unit
  of remoting is three lanes, not "the suite."

Also: CI runs on `ubuntu-latest` / `ubuntu-24.04-arm`, no self-hosted runners.

### samsung-frame-art-loader — skip entirely

236 commits, all Brooks. No CI, no Dockerfile, no `tools/` or `scripts/`. Runtime deps are
`python-dotenv`; dev is pytest/ruff/black. Its own `pyproject.toml` says these modules are
"retired once the two planes are built." A remote lane costs more than the suite does.

### hallucinote, trenchant, worldground — unassessed

Have `.prawduct/`, but **no test entrypoint script at all**. For these, "standardize remote
test dispatch" is partly the easier prior problem of "give this repo a test command" — which
prawduct already has a slot for.

---

## 6. Open questions

1. **Can scriob's integration tier run under DinD on gpu-bozeman?** Blocks the scriob design
   entirely. ~30 minutes to answer empirically.
2. **Does the 3×8 semaphore hold under real concurrency**, and do concurrent runs reproduce
   the ephemeral-port collisions that failed one of discodon's Stage 4 runs? One experiment
   answers both.
3. **How does a repo declare its prep?** Inline in `project-state.yaml`, or a referenced
   script the repo owns (discodon's `remote-test.sh` shape)? The latter keeps shell out of
   YAML and stays lintable/testable — discodon deliberately made the executor a repo file
   rather than a heredoc for exactly that reason.
4. **Per-machine config has no home yet.** `DD_TEST_REMOTE` is currently an ad-hoc export;
   it appears in no shell rc and no `.env`. Needs a real answer before a second repo, let
   alone one with another contributor.

---

## 7. Recommended sequence

1. Run discodon's lane end-to-end from `perf/remote-test-lane` (never done since extraction).
2. The semaphore concurrency experiment (Q2).
3. PR `perf/remote-test-lane` into discodon's develop.
4. Generalize the ~40 dispatch lines into prawduct, discodon as first consumer.
5. Answer Q1 for scriob, then decide scriob on its own merits.
