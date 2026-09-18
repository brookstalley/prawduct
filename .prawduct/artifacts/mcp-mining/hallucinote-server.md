# hallucinote — compressed reading (Python/FastMCP stdio server, the most sophisticated sibling)

**Topology that generates most of its knowledge:** 13 action-dispatch tools + 13 resources, a
length-prefixed TCP bridge into a **vendored second copy of the same source tree** running inside
Ableton Live's embedded Python, a content-fingerprint version handshake, async start+poll jobs, and
a Claude Code plugin install path. *Two deployed halves, two runtimes, one source tree.*

## ⚠ This file is a LOSSY compression, and its own counts are wrong

Two things found 2026-09-18, both checkable in one command each. Read them before quoting anything
here or authoring from this file alone.

**1. Every per-layer count this file stated was wrong against its own body.** The header claimed
`L0 3 · L1 30 · L2 25 · L3 22 · L4 12` (= 92, the count that was also in the title). Measured
2026-09-18: `L0 3 · L1 29 · L2 22 · L3 23 · L4 17` (= 94), plus 5 bullets in the dated-facts
section. Four of the five rows disagreed; L4 was off by five. The section headings below still
carry the old claimed number in parentheses — left in place deliberately, because the command
prints the claim and the reading side by side:

    awk '/^## /{s=$0} /^- \*\*/{c[s]++} END{for(k in c) printf "%3d  %s\n", c[k], k}' hallucinote-server.md

**2. This file is not a superset of its structured twin, in either direction.** Measured against
`hallucinote-server-structured.md` (106 rule blocks, `L0 4 · L1 29 · L2 21 · L3 24 · L4 28`,
re-derive with `grep -o '^LAYER: L[0-9]' hallucinote-server-structured.md | sort | uniq -c`):

- **Roughly eight rules are absent here**, including the whole **L0 observability** rule (*for a
  single-user local server, decide explicitly there is no fleet to observe, then name the
  substitutes*); `os.walk` swallowing errors inside a completeness check; fingerprinting installed
  binaries by raw bytes to skip a spurious overwrite prompt; post-install hooks and `register`
  console scripts being degraded in modern Python packaging; conservative uninstall env cleanup;
  pinning an environment *before Python starts*; the two-channel CLI seam (JSON on stdout, human
  text on stderr); and the declarative-action-fraction rule.

  Verified by keyword probe. **Scope the probe to the rule body, not the whole file** — this section
  names those same terms, so a whole-file grep now matches its own description of the gap and
  returns 1 for each:

      for p in preflight 'os.walk' 'raw bytes' 'console script' declarative 'env cleanup' 'before Python starts'; do
        printf '%-22s body:%s structured:%s\n' "$p" \
          "$(sed -n '/^## ⚠ The dated facts/,$p' hallucinote-server.md | grep -ic "$p")" \
          "$(grep -ic "$p" hallucinote-server-structured.md)"
      done

  Reading 2026-09-18 — body 0 for all seven; structured 7 / 2 / 1 / 2 / 2 / 1 / 1 respectively.
- **Three rules were re-filed to better layers than the structured capture gave them** — "schema in
  one module imported by both halves" and "an action-surface change is a fan-out edit" moved L4→L2,
  and "a version mismatch has three causes" moved L4→L3. Those calls look right and are worth
  keeping.

**So: author from the structured twin for CONTENT; read this file for PHRASING and for its layer
assignments.** The earlier guidance that this is "the better read" holds and is not the same claim
as "the complete one."

Read ~110–120k words.

## ⚠ The dated facts that change other people's designs

- **MCP progress notifications are RECEIVED but do NOT reset or extend the tool-call timeout**
  (Claude Code #58687), and there is no wake-on-done for MCP tools. *This single verified fact is
  what forced start+poll.* Progress rides inside the `status` payload and on disk, never as a
  protocol notification. **Directly qualifies seed rule R2.**
- **Transport is NOT a lever for timeouts** — the tool-call timeout is "confirmed identical across
  stdio, HTTP+SSE, and Streamable HTTP", and HTTP/SSE even imposes a 60s first-byte minimum.
- **MCP prompts are not assistant-callable in Claude Code** — they surface only as user-typed slash
  commands. All 7 prompts shipped in v0.9.0 were deleted in the next release. "There is no
  assistant-callable `prompts/get` path." Cross-client path would be resources, not prompts.
- **Client tool-count caps: Cursor 40 (silent drops above), Copilot 128.** Selection accuracy
  "degrades sharply past roughly ten to twenty". *Reconcile with the consumer-side cap evidence, which is withheld — see the design notes §10.5.*
- **A plugin manifest's `timeout` governs TOOL EXECUTION, not the startup handshake.** The startup
  window is `MCP_TIMEOUT` (env, ms, default **30000**), a plugin manifest cannot set it, and the
  only channel reaching a plugin-provided server's spawn is `env` in user settings. Cold dependency
  build exceeded 30s and **silently dropped the server's tools** (CC#60224). Measured: log said
  `timeout of 30000ms` / `Connection timeout triggered after 30004ms` against a config asserting
  60000. Warm handshake ~2.3s.

## The three highest-value rules

**1. The timeout ladder must be monotonic OUTWARD; a caller-side timeout that merely MATCHES the
callee's ceiling makes the callee's teaching message provably unreachable.** Matching 120/120 and
90/90 meant the agent got a bare `FrameError` instead of *"IT IS STILL RUNNING… Do not retry
immediately"* — "losing the one instruction that stops it deepening the queue behind an operation
Live cannot cancel." **They got it right at the inner boundary and still violate it at the outer
one**: three actions carry 95–180s socket ceilings and 90–120s host ceilings under a 60s tool-call
timeout, so for those the entire escalation machinery is unreachable by construction.

**2. A watchdog can only fire on paths that REACH it — verify your fence against the condition in
the original report, not the condition your fakes can model.** The fence is beautifully built
(runner-releases-not-waiter, no timed auto-clear, refuse-don't-queue, recycled-ident handling) and
passes every fake. A real export walked straight through it: **one 61.5s gap in served calls, four
times the 15s ceiling**; two in-flight calls died as bare socket timeouts — no `work_escalated`, no
job id, no busy error. Inference: had a bout been taken, the wait would have escalated ~45s before
the block lifted; it did not, so the worker never reaches the wait. Verdict: *"real for the case it
models, inert for the case in the original report."* Four of six verification boxes came back
**UNREACHABLE** — a mechanism can outlive its own falsifiability.

**3. A write that returns `ok` AND READS BACK at the new value is still not evidence of effect.**
EQ Eight's `B` band is only in circuit in L/R or M/S mode; in the default Stereo a write "returns
`ok: true`, returns the new value and a correct `value_display`, reads back at the new value on a
subsequent read, **has zero effect on the audio**." Expected ≈ −2.3 dB, measured **+0.08 dB**. Cost:
3 renders, ~30 min of realtime capture, one confidently wrong causal theory that fit the numbers.
**The design consequence is sharper than the bug: the controlled parameter was exposed and the mode
parameter deciding whether it is in circuit was not** — the agent could not even check.

## L0 — whether to build

- **Name the ONE forced constraint your topology descends from** and derive every awkward downstream
  step from it rather than treating each as its own problem.
- **Keep pure-math transforms off the MCP surface when you own a source of truth** — wrapping the
  host's version buys an untestable black box and per-document state, and costs cross-target
  uniformity.
- **Do not move large binaries through the protocol** — write to disk, exchange paths plus a small
  JSON summary. *A deliberate non-decision: they never tried.* Renders are ~23 MB per surface-minute.
  **Precondition for the whole "summary in, payload on disk" family: agent and server share a
  filesystem.** (Independent third arrival at seed rule R8, with the same precondition.)

## L1 — agent-interface design (30)

**Surface size and shape**
- **Ratify the tool BAND, not the tool COUNT** — "thirteen tools" decays; "inside the band where
  selection accuracy holds; adding a tool is a decision, not a default" survives. *The budget leaked:
  a documented ≤10 shipped as 13, as the next three capabilities arrived.*
- **State a consolidation as a reduction in SELECTION WIDTH and separately admit what happened to the
  ACTION count** — 52 tools → 10 tools but **94 actions**. A reader taking "84% reduction" as a
  capability-surface number is wrong.
- ⚠ **Every consolidation number in this repo is BORROWED, not self-measured.** The design doc's own
  success criterion asked for a baseline and post-migration measurement on a fixed benchmark; no
  baseline, benchmark file or measurement exists anywhere in the corpus. Treat "95% smaller
  tool-list response" as a sibling-project claim. *(Bears directly on seed rule R1.)*
- **Name the three failure modes of a wide surface and LEAD WITH THE MIDDLE ONE** — wrong-twin
  selected, **parameters hallucinated onto a near-match tool**, per-turn context bloat. The middle
  one corrupts data instead of failing.

**Errors as the next turn's input**
- **Every error carries `valid_actions`, the attempted action's required/optional, a runnable
  `example`, and a `hint` naming the self-service next call** — for an LLM consumer the error is not
  a log line, it is the next turn's input.
- **Generate `action='help'` from the same metadata layer the dispatcher validates against.**
- **An error must carry the state that makes the DIAGNOSTIC call unnecessary** — a hint said "may not
  be loadable on this parent"; the real cause was a matching class already present. The
  plausible-but-wrong hint cost a round-trip *and* misdirected the diagnosis.
- **Open your error-recovery guide with "retrying the same call with the same params will fail the
  same way", then enumerate the exceptions by name** — agents default to retry, and an un-annotated
  error reads as transient.
- **When a tool's verb misdescribes its semantics, the RESPONSE MESSAGE is lying too** — fix both and
  repeat the correction in four places. `add_notes_to_clip` called a full replace and answered
  "Added N notes": "Name + response message both lie… **I only avoided the trap by reading the remote
  script source.**" Design principle: *repetition beats subtle.*

**Round-trip economics**
- **Every create/duplicate/load returns the identity of what it made** — prose confirmation costs one
  follow-up per object; measured "for a 49-clip rebuild: 49 wasted round-trips".
- **Cost your round-trips in real numbers before designing a batch action.** Measured: 13 note
  replacements forced 95 extra round-trips; 30 clips at 3 calls each = 90 calls. *The batch principle
  landed only where it was measured — a promised generic `updates=[...]` never shipped.*
- **Give any read returning a large fixed set a single-item form and a filter** — the verify step
  sits in the inner measure-adjust-measure loop. ~420 parameter rows read to want 6; an EQ Eight has
  84 parameters and `detail='summary'` still returns all of them.
- **A capped read returns an explicit `truncated` flag plus the parameter that subdivides the walk,
  and says in its own description when NOT to call it.**
- **Put a soft cap with a non-blocking `warning` on any inline payload channel that costs agent
  context, and name the out-of-band route in the same warning** (threshold ~32 items).
- **Once an operation is start+poll, delegate the poll loop to a subagent that returns only the
  terminal summary** — otherwise the pattern's cost is `running…` statuses filling the caller's
  context.
- **For a bulk operation whose per-item results the agent does not need, dispatch out-of-context
  through a CLI that talks to your backend directly** — "so bytes never enter the agent's context".

**Teaching the gaps**
- **Publish a machine-readable capability matrix as a resource, TRI-STATE** — SUPPORTED /
  NOT_IMPLEMENTED (host can, you haven't) / UNSUPPORTED_IN_HOST (hard wall) — because "supported /
  not" does not tell the agent whether to wait or route around. Cells carry `static` vs `probe` so
  device-specific verdicts are re-probed and "a Live update isn't permanently blocked by a frozen
  verdict."
- **Publish known gaps as an addressable resource and point every teaching error at it** — "don't
  waste a turn discovering them."
- **Keep a blocked capability PRESENT as a tool returning a teaching 'blocked' response** rather than
  omitting it — omission "surprises agents who don't read the gap doc."

**Correctness traps**
- **Refuse a call whose underlying host primitive is a destructive TOGGLE** — never pass it through.
- **Never position a host for an operation by writing the property you can READ BACK** — verify the
  realized state when write and effect live on different properties. A handler seeks to beat 8, reads
  it back as 8.0 (an honest read), starts playback, and the transport rolls from beat 351. Cost: "a
  perform pass that recorded nothing across three sessions in one day while reporting success at
  every step."
- **In a handler performing more than one write from separate validations, resolve and validate
  everything before writing anything.** A reroute applied, then an unknown channel raised: "the MCP
  response was an error, but the session's output was now silently pointing at the new bus." Test
  discipline: assert the **first object is untouched** — "a response-only assertion passes even when
  the session half-mutated." Tell: a `setattr` textually before a later `raise` in the same handler.
- **Never persist a provider-local opaque id as the portable identity of a resource** — on replay it
  fails to find the thing, **or loads something different**.
- **Scope a display-name lookup to the canonical category root and fail loudly naming the collision**
  — a user preset named "Drum Rack" matched first and loaded the wrong device class; a GM-default
  pitch collision "silently substituted the wrong sound."
- **Accept the host's own internal class name as valid input** — rejecting the platform's canonical
  identifier is a bug the agent cannot reason around.
- **Probe the capability rather than allow-listing the class** whenever you must work across a
  third-party plugin ecosystem.
- **Pin idempotency per PHASE of a sync tool and test push→edit→push** — an append-only placement
  phase doubles the target on every re-run.
- **If a host edit rotates an object's synthetic id, warn at the point the round-trip happens.**
- **When the host exposes only point-sampling, reconstruct the read by sampling at a declared
  resolution and emitting a point at each transition — and make the resolution a parameter.**
- **A server that injects its own infrastructure into the user's document must make it invisible to
  the document model, and detect a saved document carrying a mis-placed copy** — theirs goes stale
  when authored devices load after the tap, "emitting silently-wrong numbers."

## L2 — protocol semantics (25)

**Schema generation — the FastMCP/pydantic cluster**
- **Never annotate a polymorphic MCP parameter as `typing.Any`** — it emits `anyOf: [{}, {"type":
  "null"}]`, and the empty `{}` branch gives the *client* no type to serialize against, so the
  payload dies in the client's own JSON parse **before a request ever leaves it**. Reproduced 6/6;
  device renaming had no working path at all. Fix is an explicit union over every JSON type — "the
  point is explicitness, not narrowing."
- **In that union order `bool` before `int`, and keep `int` its own branch** so an integer is never
  widened to float (native setters reject a float where the signature wants an int).
- **When a param is schema-typed `any`, assume some clients send every scalar as a string** — recover
  the JSON type by parsing as a JSON literal, **gated on the target's current type** so a
  string-valued property is not corrupted (a track named `"808"` keeps its name).
- **Synthesize a unified tool's schema as `action` plus the FLATTENED union of every action's
  params**, keyword-only and optional — never a `params={...}` envelope, which pydantic's
  `extra='ignore'` silently demanded while the docs showed the flat form.
- **Reject unknown params loudly** — under a flattened union the default turns both a typo and a
  wrong-action param into a silently dropped argument.
- **Push description, min/max and enum into the generated JSONSchema via `Annotated[..., Field(...)]`**
  — the constraints existed internally and never reached the wire, so pruning impossible calls
  happened only after the dispatcher's error.

**Resources vs tools vs prompts**
- **Move to RESOURCES anything taking no per-call parameter or only a slow-changing identifier** —
  resources are model-*pulled*, not model-*selected*, so they cost nothing in the selection space.
- **Let a resource fan out into multiple internal handler calls** — composition at the resource layer
  costs the agent no turns.
- **Ship a reference resource whose only job is letting the agent spell an identifier correctly** —
  "'Filter Freq' vs 'Cutoff' — both are real on different devices."
- **Check your framework actually plumbs resource templates before speccing one** — theirs ships an
  empty template tuple with the plumbing retained.

**Versioning — the deepest material here**
- **Version by CONTENT FINGERPRINT, not semver, when both halves are the same source tree deployed
  twice by your own installer.** "Semver communicates compatibility between a library and a consumer
  who chose their version. That is the wrong model… the only question worth asking is **are these
  byte-identical?** A human-maintained version number answers that badly, because it is exactly the
  thing a contributor forgets to bump. **The fingerprint cannot be forgotten.**" Cost accepted: any
  wire-shape edit forces re-vendor + full host restart.
- **The fingerprint set must equal code that is BOTH shipped to AND executed in the remote runtime.**
  Over-inclusion trains users to ignore re-vendor demands (a read-side fix nagged every user); a
  contract-only hash under-prompts exactly when they need it (Live keeps running the old buggy
  handler with no prompt) — "a correctness regression in the *opposite* direction."
- **Ship TWO fingerprints with different blocking postures** — a narrow hard one over the executed
  wire shape that refuses, and a wide advisory one over the whole shipped tree that only recommends.
  *The cleanest resolution of a genuine tension in the whole corpus: narrowing a staleness hash to
  stop false alarms is what creates the silent-ship hole.*
- **Both must hash through one shared normalizer** — CRLF→LF, and skip normalization for files
  containing a NUL byte so a future binary entry is not silently corrupted.
- **Carry a version on every request**, and treat an ABSENT version field as "too old to handshake",
  not as a pass.
- **Give a strict handshake a per-call opt-in bypass that attaches a loud warning to its own
  response, and name the flag in the refusing error's hint** — a strict gate with no escape hatch is
  poisonous for the dev loop, where every source edit invalidates the fingerprint.
- **Give the response a stable machine-readable `code` and serialize it on BOTH ok and error paths**
  — an `ok=True` carrying a handle to unfinished work is otherwise indistinguishable from a completed
  one, "and the difference is whether the thing it asked for has happened yet."
- **Internal control-flow flags must not serialize to the wire.**
- **Treat tool and action names as permanently stable — alias, never rename.** *TENSION: this repo's
  shipped policy is the opposite ("no deprecation aliases — we control all consumers"), which is
  legitimate ONLY because one installer deploys both halves and the handshake makes "old client meets
  new server" unreachable. Delete the handshake and the permission evaporates.*
- **Treat an action-surface change as a fan-out edit with a fixed checklist, and pin every COUNT you
  state in prose with a test against the registry.** Four prose surfaces are pinned; the one that
  drifted was `marketplace.json` — "the tool count a user reads BEFORE installing, in the install
  dialog, and the one count no guard pinned."
- **Put the tool/action schema in ONE module imported by both halves** — drift becomes structurally
  impossible rather than test-detected.
- **Reject the single mega-tool with a free-form query DSL** — it pushes host-API expertise onto the
  LLM and destroys schema validation. "State in the wire. No session tokens, no opaque cursors."

## L3 — transport and operations (22)

- **TCP with 4-byte length-prefixed framing for a local bridge, never UDP** — a 64KB datagram cap
  cannot carry a session snapshot — and cap the declared length (16 MiB) so a corrupt prefix cannot
  allocate the process to death. *The shipped code names the design doc, which still says UDP, as
  wrong.*
- **Open a fresh connection per request when latencies are local** — no connection state, no
  reconnect logic, no head-of-line blocking; also what makes concurrent dispatch safe.
- **When you intend an unbounded read, clear the socket timeout explicitly** — `create_connection`'s
  *connect* timeout carries over to reads.
- **Put the per-(tool, action) read-timeout policy at the lowest chokepoint EVERY recv route shares**
  — a policy installed at one call site leaves every other route on the bare default.
- **FastMCP runs a synchronous tool function INLINE on the event-loop thread**, so one blocking `def`
  freezes every other in-flight call. A long-poll "blocked the entire MCP event loop for the wait
  window". Ratified as an availability norm: "Reverting a handler to plain `def` is a whole-server
  availability bug, not a style preference."
- **Know your next ceiling after fixing the event loop** — `anyio.to_thread` draws from a default
  pool of **40**; raise the limiter rather than re-architect.
- **The moment dispatch becomes concurrent, a "busy" guard written as check-then-create is a real
  race** — make the claim atomic under one lock.
- **An in-memory job registry is per-process and dies with the process** — back the handle with a
  disk heartbeat, and make the unknown-job error distinguish "wrong id" from "the server restarted".
- **Mirror only RUNNING heartbeats into progress**; the terminal write is reflected via state+result.
- **Keep the wire state vocabulary distinct from any legacy on-disk vocabulary and map at the
  boundary.**
- **Build the terminal payload with one explicit branch per job kind and NO bare `else`** — an
  unnamed default hands one kind's key names to the next kind someone adds.
- **When a call outruns its ceiling on an UNCANCELLABLE backend, reply `ok=true` with a job handle
  and a discriminator code — not a failure.** Say the call has NOT failed and NOT finished, forbid
  retry, and name the consequence: "another call now queues behind the one still executing, which is
  how a slow operation becomes an unresponsive host."
- **The admission gate for an uncancellable operation is released by the RUNNER, never by the
  waiter's timeout — and there is deliberately NO timed auto-clear**, because clearing on a timer is
  the same defect on a delay. If the schedule call itself throws, release first then re-raise — "a
  callback that was never scheduled would fence the main thread permanently."
- **Refuse a concurrent caller after a short bounded wait rather than queueing** (2.0s; refusals
  measured at 2.3–2.8s across 12 concurrent calls, no queue formed). **Clear the owner ident on
  abandon — thread idents are RECYCLED** and a later connection thread would inherit re-entry rights.
- **An agent-facing claim that a diagnostic "always works while fenced" must be tested against BOTH
  fence conditions — yours and the host's.** *Still shipped wrong in two surfaces at HEAD:* during a
  real bout, 6 concurrent callers answered in <0.9s; during the export block **the same call timed
  out at 30s**. "Only the first condition was ever tested."
- **Keep the server package stdlib-only at module-import time and machine-check the load chain with
  an AST scan.** A **dead** `import sqlite3` under `from __future__ import annotations` aborted the
  entire Control Surface load — the host's embedded Python ships without `_sqlite3` — with no UI
  trace, only a log file. "It cost nothing and broke everything." The guard uses AST, not runtime
  import, "precisely because the host Python's sqlite3 is the reason the bug is invisible at normal
  test time", and ships a counter-test proving the scan can go red.
- **On stdio, stdout IS the protocol** — logging to stderr, and route any subprocess's stdout into
  your stderr too (uv's own stdout would otherwise land in the model's context).
- **Resolve paths and identities in the process that HAS that context, before forwarding** — the far
  half runs with a different cwd (theirs is `/` on macOS, read-only) and a different environment.
- **Guard a destination-resolving default with a refusal when the resolved target does not exist** —
  `mkdir(parents=True)` "happily invents the whole tree and fills it", parking ~290 MB where nobody
  looks, "so nothing downstream looks wrong until analysis reports the song isn't built."
- **A long-lived server serves the code it imported at spawn** — stamp every result with a content
  signature of the LOADED pipeline plus a `stale` flag computed against disk. The signature must be
  frozen at import; "hashing only on-disk source would report fresh while the process runs old code,"
  and a hand-bumped number has the identical defect.
- **A version mismatch has THREE causes and the detecting side can usually only guess** — have the
  side holding the extra fact (its own on-disk source vs the code it loaded) refine the remediation
  before the message reaches the user.
- **Never format a content fingerprint so it reads like a VCS identifier, and TEST any recovery
  recipe your error prints by EXECUTING it against a fixture.** A refusal told users to
  `git worktree add <sha>`; `git cat-file -t` rejects it — "no checkout of it exists."
- **When a knob rescales an operation's wall-clock cost, audit every timeout constant in that file
  for whether it is scaled by the same knob** — a flat 15s stall timeout justified as "1-2 bars"
  against two bars at 31 BPM taking 15.5s, while the ceiling *beside it in the same file* was scaled.

## L4 — client/host integration (12)

- **Do not treat a SessionStart pre-warm hook as the mitigation for slow startup — it RACES the
  server spawn and cannot block it.** Keep it best-effort, never failing the session.
- **When tools vanish at startup, read the CLIENT's connection log before theorizing** — it states
  the timeout actually in force. "The project's only named answer to how you observe a stdio server
  you cannot print to."
- **Launch a distributed server through a locked, project-pinned runner from the distribution root**
  — never a bare console-script on PATH, which decouples the running server from the installed
  version.
- **Redirect the runtime's environment into the writable persistent plugin data dir** — the payload
  dir is read-only and ephemeral.
- **Verify your lockfile is actually GIT-TRACKED before claiming a pinned install works** — theirs
  generated and launched perfectly locally while `.gitignore` excluded it, so a real install would
  ship without it. "A contract test asserting `X.exists()` passes locally until X is committed."
- **For any format the HARNESS parses, take ground truth from a known-working example in the
  installed plugin cache, not from docs or a research agent** — a wrong hook fails **silently**,
  "the worst failure mode to debug". An agent's confidence about an environment-specific format is
  *uncorrelated* with the client version you target.
- **Make your installer read the RUNNING server's own identity from a no-dependency resource** — the
  install shell's `sys.path` may resolve a different copy than the one the host launched. The failure
  has a name (`coexistence_divergence`) and the report **withholds** a verdict rather than compare
  against the wrong reference: "a comparison whose reference the report itself flags as the wrong one
  is worse than no comparison: it is the shape an operator acts on."
- **Have the server report its own interpreter path** so the agent's shell commands run in the same
  environment as the bridge.
- **Perform every install/uninstall mutation in tested atomic Python invoked as a CLI subcommand —
  never hand-authored shell in a skill body.** A correctly-returned `--exclude=*.pyc` pasted unquoted
  glob-expanded with no match and **zsh aborted the whole line AFTER the preceding `rm -rf` + `mkdir`
  had run**, leaving a half-installed surface. "Only the agent's vigilance caught it." Fix: stage →
  verify → move-aside-then-move-in with rollback, on every platform.
- **Anchor a vendor-exclude to the source root when the same filename exists at two levels.**
- **When the install replaces the code the calling bridge runs, the agent CANNOT verify its own
  work** — the completion gate is a user-performed reconnect. "Do not report the install as working
  until they have. The completion gate is a `/mcp` reconnect, not a vibe."
- **Document which failures a client RECONNECT fixes and which need a full HOST restart** — for code
  injected into an app that caches modules at launch, "reconnect the MCP server" is not "reload the
  code."
- **Ship a three-state re-vendor verdict with every release** (`required`/`recommended`/`not
  required`), derived mechanically from a diff against both fingerprint sets.
- **Batch every pending host-gated verification into one sitting** — "batching saved 3 restart cycles
  in one session; three independent sessions that day rediscovered the same rule." Until the far copy
  is replaced the verdicts are **unknowable, not passing**.
- **An uninstaller must know EVERY scope a server can be registered in**, plus the plugin-provided
  case where there is no entry at all.
- **Choose your repro instrument by which layer the bug lives in** — drive the RAW WIRE for a
  wire-typing defect (the MCP client coerces JSON types and structurally cannot produce the shape),
  and the REAL CLIENT when the failure is the client's own serializer. "The two are mirror images and
  the choice of instrument is the whole finding."
- **Check who actually READS each surface** — an install skill printed "try: `ableton_session(action=
  'help')`" to a human who "can't type MCP calls. She types English."

## Source disagreements this repo carries (all unresolved at its HEAD)

- Design doc says **UDP**; shipped code says **TCP** and names the doc as wrong.
- `mcp-tool-design.md` contradicts itself three times (NOTICE file, prompts, post-install hook).
- Tool budget **≤10 documented vs 13 shipped**; generic batching promised, two batch actions shipped.
- Two surfaces still tell the agent a diagnostic call "always works" when a blocked host times it out
  at 30s.
- A 120s ceiling's justifying comment cites "tens of seconds" for a load **re-measured at 1.95s cold
  / 0.89s warm**. The premise was disproved; the constant was not revisited.
