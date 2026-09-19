# hallucinote — verification of `hallucinote-server-structured.md`

**Source repo HEAD verified against:** `3ed9ff07df4ba6cbccfbc88358fab6fd75b8571f` (`/Users/brookstalley/source/hallucinote`, detached, working tree clean before and after this pass — nothing in it was modified, staged, committed or branched, and its test suite was not run).

**Artifact under verification:** `.prawduct/artifacts/mcp-mining/hallucinote-server-structured.md` — 106 `**RULE:**` blocks, 106 `LAYER:` lines, 106 `PROVENANCE:` lines (re-derived here, not quoted). That file was **not edited**; it is the record under audit.

**Every verdict below is relative to that SHA and means nothing without it.**

---

## What was done, and what the instrument can and cannot see

Three passes, in this order:

1. **Path existence.** Every backticked path in every `PROVENANCE:` line was resolved against the tree. All of them exist. The apparent misses (`dispatcher.py`, `schema.py`, `server.py`, `client.py`, `handlers/jobs.py`, `actions/device.py`, `remote_script/dispatch.py`, `cli/preflight.py`, `test_plugin_manifest.py`) are bare-basename shorthands used after a full path earlier in the same line; each resolves unambiguously inside `hallucinote_mcp/`.
2. **Quotation resolution.** Every `*"..."*` run inside every `EVIDENCE:` field was extracted (202 fragments after splitting on the capture's own ellipses), whitespace- and punctuation-normalised, and searched case-insensitively across all 1,009 readable text files in the tree, with a binary search for the longest matching prefix so a divergence point could be located rather than merely reported as absent. **170 of 202 matched exactly.** Every one of the remaining 32 was then chased by hand against the source region.
3. **Re-anchoring.** Every cited `file:line` was resolved to its enclosing `def`/`class` (Python) or heading (Markdown), so a corpus row can carry a symbol instead of a digit.

**Instrument controls.** A nonsense string returned zero hits (the search is not matching everything); 170 fragments returned hits (it is not dead). Three false-miss classes were found and fixed during the pass — trailing punctuation, case, and periods being stripped before ellipsis-splitting — and two of my own intermediate greps were truncated by `head` and reported absences that were present (the 400 ms Copilot figure and the ~290 MB in `server.py`). Both are corrected below. The instrument still cannot see a quotation the capture *stitched* across two non-adjacent sentences without marking an ellipsis; those show as prefix matches and were resolved by reading.

**Verdict conventions.** The verdict answers the question this pass exists for — *does the thing the rule claims live at the address given?* So:

- **RESOLVED** — the cited path exists and holds the claim; the durable anchor is recorded.
- **MOVED** — the claim is true of the tree but not at the cited address. The real one is given.
- **NOT-FOUND** — the path is absent, or present and holds nothing resembling the claim.
- **CONTRADICTED** — the tree says something incompatible with the rule as written.
- **UNVERIFIABLE** — the load-bearing fact is external or runtime and *nothing in the tree instantiates it*; the tree only records someone asserting it.

A rule whose evidence is externally-dependent but which the tree *does* instantiate (a deleted subsystem, a shipped constant, a committed settings file) is marked RESOLVED with an **EXT** note naming the external half. That distinction is stated here rather than collapsed, because collapsing it in either direction is the failure this pass exists to catch: calling an external fact verified, or calling a resolvable address unverifiable. Rules where I applied it: R034, R040, R055, R065, R066, R079, R081, R085, R101, and R058's anyio figure.

## Verdict tally

| Verdict | Count |
|---|---|
| RESOLVED | 95 |
| MOVED | 7 |
| NOT-FOUND | 0 |
| CONTRADICTED | 2 |
| UNVERIFIABLE | 2 |
| **Total** | **106** |

Counts are derived from the per-rule table below, not asserted alongside it.

**NOT-FOUND is zero, and that is a real result, not a courtesy.** Every path this capture names exists, and every rule's substance is somewhere in the tree. The defects are of address and of wording, not of invention. What that costs is set out in the closing assessment.

---

## The three flagged claims, and the tool count

### 1. Two agent-facing surfaces still say a diagnostic call "always works" while fenced — **CONFIRMED, BOTH STILL PRESENT AT HEAD**

- `hallucinote_mcp/src/hallucinote_mcp/actions/session.py:358` — the third `tips` entry of `register(Action(tool="ableton_session", name="bout_status", ...))`: *"Safe to call while the main thread is fenced: this action runs on the worker thread and never takes a bout."* The capture's cited line number is exact.
- `hallucinote_mcp/src/hallucinote_mcp/resources/guides/conventions.md:227` — *"`bout_status` and `abandon_bout` run on the worker thread, so they answer while the main thread is fenced — they are the two calls that always work."*

Against `.prawduct/operator-verification.md:196`: *"**`bout_status` itself timed out (30 s) inside the block.** Its action docstring promises … That holds against a *bout-fenced* main thread and fails against a *genuinely blocked* one. Only the first condition was ever tested."* Filed as **#531** (L232). Neither surface has been amended; the over-claim reaches agents today. The capture is teaching a live lesson, not a stale one.

### 2. A 120 s ceiling justified by "tens of seconds" for a load re-measured at 1.95 s — **CONFIRMED**

- The constant: `hallucinote_mcp/src/hallucinote_mcp/client.py:96` — `_DEVICE_LOAD_READ_TIMEOUT: float = 120.0 + _LIVE_REPLY_MARGIN_S`, and the Live-side ceiling `main_thread_timeout=120.0` at `actions/device.py:216`.
- The comment: `client.py:53-59`, the `ableton_device(load)` bullet of the `_READ_TIMEOUTS` policy block — *"HallucinoteAnalyzer.amxd is ~490 KB and Live blocks for tens of seconds instantiating it… (measured: a single master-track analyzer load severed the socket twice at the 15s default)"*.
- The re-measurement: `.prawduct/operator-verification.md:169-174` — *"the analyzer loads in **1.95 s cold, 0.89 s warm** against a 120 s `device.load` ceiling… The \"tens of seconds\" premise in `client.py`'s comment is stale for this hardware."*

The comment is unchanged at HEAD. One correction to the capture: it renders the comment as *"Live blocks for tens of seconds instantiating [the .amxd]"* — the bracket is the miner's insertion, and it matters here because the sentence's own subject (`HallucinoteAnalyzer.amxd`, one clause earlier) is what makes the staleness specific to that instrument.

### 3. The design doc says UDP; the shipped code is TCP — **CONFIRMED, with one over-claim**

- Shipped: `hallucinote_mcp/src/hallucinote_mcp/wire.py:1-14` — *"TCP (not UDP, despite some early scratch notes saying otherwise)"*, with the 64KB-datagram reason and the length-prefix rationale.
- Doc: `docs/archive/mcp-tool-design.md:528`, in **§10.2 "Both layers, both ours"** — the Remote Script *"Registers as a Control Surface, opens a UDP server"*. **And at `:518` as well**, a second instance the capture does not name ("Infrastructure (Live Control Surface registration, UDP server, threading model, dispatcher pattern)"). A corpus row should carry both, or the next reader will fix one and believe it closed.
- **The over-claim:** the capture says the code *"names the doc as wrong"*. It does not. It names *"some early scratch notes"*. That is why R073 is CONTRADICTED rather than RESOLVED: as written, the rule tells a reader the tree contains a citation it does not contain, and the useful lesson — a shipped module correcting an unnamed prior artifact leaves the artifact itself uncorrected in two places — is the opposite of the one stated.

### The tool count — **13, counted**

`hallucinote_mcp/src/hallucinote_mcp/schema.py:16-30` (R007's cited range, exactly):

`ableton_session`, `ableton_track`, `ableton_return`, `ableton_clip`, `ableton_note`, `ableton_device`, `ableton_automation`, `ableton_arrangement`, `ableton_scene`, `ableton_browser`, `ableton_render`, `ableton_analysis`, `ableton_probe` — **13**.

Counted twice: statically from the tuple literal, and by importing `schema` and taking `len(schema.TOOLS)`. Corroborated in three independent prose surfaces that a test pins: `server.py:1` ("13 unified tools + 13 resources"), `.claude-plugin/marketplace.json:14` ("13 Ableton Live tools"), and the PRIMER via `test_primer_tool_count_matches_actual_registry`. The design-doc budget of **10** is at `mcp-tool-design.md:175`/`:400`/`:433`/`:756`/`:776`. `ableton_probe` appears in neither archive design doc — only in `docs/research/audio-first-class/`. The capture's 13-vs-10 finding holds in full.

---

## Constants audit

Every measured figure in the capture, classified as the brief asks: a **constant in the tree** (checkable, and checked) or an **observation from a run** (unverifiable by reading, instrument named). Cheap to check, so all of it was checked.

| Figure | Value as the capture states it | Verdict | Where it actually lives |
|---|---|---|---|
| `"timeout": 60000` | 60000 ms | **CONFIRMED** | `.claude-plugin/plugin.json:32` — line-exact as cited. |
| `_ENSURE_LOADED_READ_TIMEOUT` | 180.0 s | **CONFIRMED** | `client.py:94`. Cited as "180 s". |
| `_STATUS_READ_TIMEOUT` | 60.0 s | **CONFIRMED** | `client.py:95`. |
| `_DEVICE_LOAD_READ_TIMEOUT` | 120.0 + margin = **125.0 s** | **CONFIRMED** | `client.py:96` — the capture's "125 s" is the evaluated value, not a literal. Worth noting for a re-derivation: the literal in the tree is `120.0 + _LIVE_REPLY_MARGIN_S`. |
| `_GET_PARAMETERS_READ_TIMEOUT` | 90.0 + margin = **95.0 s** | **CONFIRMED** | `client.py:97`; same composed-literal caveat. |
| `_LIVE_MAIN_THREAD_DEFAULT_S` | 15.0 s | **CONFIRMED** | `client.py:69`. The "implicit 15/15 default" the margin docstring names. |
| `_LIVE_REPLY_MARGIN_S` | 5.0 s | **CONFIRMED** | `client.py:74`. |
| `_BUSY_ADMIT_WAIT_S` | 2.0 s | **CONFIRMED** | `remote_script/dispatch.py:44` (pinned by `test_live_context_bout.py:454`). **Note the address**: R065 cites `dispatch.py:145-160`, which holds the *rationale*, not the constant. |
| `main_thread_timeout` (device get_parameters) | 90.0 s | **CONFIRMED** | `actions/device.py:169` — line-exact as cited. |
| `main_thread_timeout` (device load) | 120.0 s | **CONFIRMED** | `actions/device.py:216` — line-exact as cited. |
| `DEFAULT_STATUS_LONG_POLL_S` | 45.0 s | **CONFIRMED** | `handlers/jobs.py:50` — the last line of R056's cited 36-50. |
| `_MAX_MESSAGE_BYTES` | 16 MiB (`16 * 1024 * 1024`) | **CONFIRMED** | `wire.py:30` — the last line of R073's cited 1-30. |
| `DEFAULT_PORT` / legacy fork port | 9878 / 9877 | **CONFIRMED** | `wire.py:24-26`. |
| `DEFAULT_LIVE_VERSION` | "12.4" | **CONFIRMED** | `node_features.py:75` — **outside** R038's cited 1-60. |
| `STARTUP_TIMEOUT_FLOOR_MS` / `MCP_TIMEOUT` floor | 180000 ms | **CONFIRMED** | `mcp_config.py:36` comment + `.claude/settings.json:3` `"MCP_TIMEOUT": "180000"`. |
| `MCP_TIMEOUT` host default | 30000 ms | **ASSERTED IN TREE, EXTERNAL** | `mcp_config.py:20` states it; `.prawduct/learnings-detail.md:506` records the measured log line "Connection timeout triggered after 30004ms". Not a constant this repo owns — instrument: the client's own connection log, which is exactly what R081 recommends. |
| `schema.TOOLS` length | **13** | **CONFIRMED** | `schema.py:16-30`, cited exactly. Counted statically and by import. Names listed in the Tool count section below. |
| Resource count | 13 | **CONFIRMED** | `server.py:1` docstring — "13 unified tools + 13 resources (all static)". |
| Design-doc tool budget | 10 tools, ≤200 tokens/description | **CONFIRMED** | `mcp-tool-design.md:175`, `:400`, `:433`, `:756`, `:776`. The per-description criterion appears nowhere as a measurement — the capture's "appears never to have been measured" holds. |
| Consolidation headline | ~94 actions in 10 tools; ~84% width reduction | **CONFIRMED** | `mcp-tool-design.md:175`, same sentence. |
| Token band | ~10K → ~2K; 95% smaller tool-list response | **CONFIRMED (as a doc claim)** | `mcp-tool-design.md:85`. Third-party/projected, not measured here. |
| Cursor / Copilot caps | 40 / 128; AbletonMCP 52 | **ASSERTED IN TREE, EXTERNAL** | `mcp-tool-design.md:61`. |
| Speakeasy Pet Store | 10 perfect / 20 → 19-20 / 107 collapse | **ASSERTED IN TREE, EXTERNAL** | `mcp-tool-design.md:57`. |
| Copilot reduction | 40 → 13; 2-5 pp; 400 ms | **ASSERTED IN TREE, EXTERNAL** | `mcp-tool-design.md:59`. The 400 ms figure **is** in the tree (an earlier sweep of mine missed it to a `head` truncation). |
| `anyio.to_thread` pool | 40 (41st queues) | **ASSERTED IN TREE, EXTERNAL** | `.prawduct/artifacts/plans/MCP-ASYNC-RENDER-ANALYZE/archive/api-notes.md:207-209`. Not defined anywhere in this repo — it is anyio's default. Instrument: `anyio.to_thread.current_default_thread_limiter().total_tokens`, or read the pinned anyio in the venv. |
| `mcp` version for the inline-sync finding | 1.26.0 | **CONFIRMED (as a recorded verification)** | `api-notes.md:181`, `build-plan.md:186`. |
| Render size | ~23 MB per surface-minute | **CONFIRMED, WRONG ADDRESS** | `docs/running-the-engine.md:63`, `CHANGELOG.md:437`, `.prawduct/change-log-archive.md:1186`. **Not** at R003's cited `server.py _sweep_stale_takes` / `handlers/jobs.py status_result`. |
| Phantom-directory spill | ~290 MB | **CONFIRMED** | `server.py:428`, inside `_refuse_render_into_phantom_song_dir` — R077's cited 424-490. (Also `.prawduct/change-log-archive.md:968` and three other records.) |
| Inline-array soft cap | ~32 notes | **CONFIRMED** | `resources/guides/conventions.md:108`, in the section heading itself. |
| EQ Eight parameter count | 84 | **CONFIRMED** | `incoming-bugs/2026-09-11-get-parameters...md:16`; also `.prawduct/operator-verification.md:271`. |
| One mixing pass' read cost | ~420 parameter rows, wanted ~6 | **CONFIRMED** | same file, L20-21. |
| EQ Eight B-band write | expected ≈ −2.3 dB, measured **+0.08 dB** | **CONFIRMED** | `incoming-bugs/2026-09-11-eq-eight-b-band...md:32`. The sibling row (−2.5 dB → −0.15 dB) is also there and the capture does not use it. |
| B-band diagnosis cost | three renders, ~30 min realtime | **CONFIRMED** | same file, L4. |
| Analyzer patch size | ~490 KB | **CONFIRMED** | `client.py:55` (the `ableton_device(load)` bullet). |
| Analyzer load, re-measured | **1.95 s cold / 0.89 s warm**; worst load 2.38 s | **CONFIRMED (a live measurement)** | `.prawduct/operator-verification.md:169-174` — inside R062's cited 168-176. UNVERIFIABLE by reading; instrument is a Live 12.4.x sitting. |
| Blocked-host gap | **61.5 s**, 09:45:05 → 09:46:06 | **CONFIRMED (a live measurement)** | `.prawduct/operator-verification.md:182-183`. The tree says "four times the 15 s **default** ceiling"; the capture drops "default". |
| Victim socket timeouts | bare `FrameError` at 20.0 s | **CONFIRMED** | same section, L184-185 (20 s = the 15 s ceiling + 5 s margin). |
| `bout_status` inside a real block | timed out at **30 s** | **CONFIRMED (a live measurement)** | `.prawduct/operator-verification.md:196`. |
| Busy-refusal arrival | **2.3-2.8 s** (5 of 12 calls) | **CONFIRMED (a live measurement)** | `.prawduct/operator-verification.md:215-217`. |
| Verification boxes | "four of six UNREACHABLE" | **DOES NOT MATCH THE TREE** | The box list at `operator-verification.md:206-232` has three UNREACHABLE, one FAILS, two `[x]`. The section header (L155) does say four; the capture copied the header. See R066 (CONTRADICTED). |
| Cold-build payload | ~70 MiB (numpy/scipy/librosa) | **CONFIRMED** | `mcp_config.py:16`, `skills/ableton-mcp-install/SKILL.md:175`, `learnings-detail.md:504`. |
| Warm handshake | ~2.3 s | **CONFIRMED (a live measurement)** | `.prawduct/operator-verification.md:1226`, inside R079's cited range. |
| Startup failure measured | "Connection timeout triggered after 30004ms" | **CONFIRMED** | `.prawduct/learnings-detail.md:506`. |
| Prompts deleted | 7 | **CONFIRMED** | `CHANGELOG.md:1057` ("The 7 MCP prompts shipped in…"); and zero prompts are registered in the tree today. |
| Pre-warm hook tests | 9 | **CONFIRMED** | `hallucinote_mcp/tests/unit/test_prewarm_hook.py` — 9 test functions counted. |
| Atomicity test width | 32 threads | **CONFIRMED** | `test_handlers_jobs.py:92` `test_create_if_idle_is_atomic_under_concurrent_starts`, `n = 32` at L97. |
| `Any`-param reproduction | 6/6 | **CONFIRMED (as a recorded measurement)** | `.prawduct/change-log.md:644`. EXT — it is a client-serializer behaviour. |
| Duplicate-clip round-trips | 49 for a 49-clip rebuild | **CONFIRMED** | `docs/archive/mcp-requirements.md:686`. |
| Corpus size | 71,328 words core / ~95,000 read | **UNVERIFIABLE AS STATED** | This is a measurement of the miner's own reading set, and the set is not enumerated precisely enough to re-run `wc -w`. Not a claim about the tree. |
| Rule count | 78 (summary) vs 106 (blocks) vs 92 (sibling file) | **RE-DERIVED: 106** | `grep -c '^LAYER: '` = 106, `grep -c '^\*\*RULE:\*\*'` = 106, `grep -c '^PROVENANCE:'` = 106 on the capture. The capture's own preamble already flags this and says not to quote the 78; that stands. |

**No constant in the tree disagrees with the value the capture states.** Every literal — 60000, 180, 60, 125, 95, 15, 5, 2.0, 120, 90, 45, 16 MiB, 9878/9877, "12.4", 180000, 13, 10, ~94, ~84%, 84, ~420, +0.08, ~490 KB, ~23 MB, ~290 MB, ~32, ~70 MiB, 7, 9, 32, 49 — matches. That is the capture's strongest suit and it should be said plainly.

Two figures are not right, and neither is a constant:

1. **"Four of six verification boxes were UNREACHABLE"** — the cited box list has three UNREACHABLE and one FAILS. The capture copied the section header instead of counting the list, and the header is itself loose (its "TWO BOXES PASS" includes a box labelled "NOT REPRODUCIBLE AS WRITTEN, and the escalation half FAILS"). See R066.
2. **"~23 MB per surface-minute"** — correct, but not at the two symbols R003 cites. Its homes are `docs/running-the-engine.md:63` and `CHANGELOG.md:437`.

**Out of scope, and worth saying so:** the brief asks about "37 and 43 parameter counts". Those figures appear nowhere in `hallucinote-server-structured.md` or in `hallucinote-server.md`. `.prawduct/artifacts/mcp-mining/README.md:72` attributes them to the *other* captures (cordyceps / bankmachine), alongside "a 49% docs-token reduction" and "~32 minutes of observed silence" — and those four files carry zero `PROVENANCE:` lines, so nothing in them is addressed at all. They are a separate debt, not this file's.

---

## Quotations that are not verbatim

Distinct from the verdicts, and the finding a later author most needs, because a `*"..."*` run in this schema reads as a transcription. Nineteen of the capture's quotations are not what the tree says. Most are harmless compressions. Four change meaning or invent text:

- **R075** — *"so it cost nothing and broke everything"* is **nowhere in the tree**. It is the miner's own sentence in quotation marks.
- **R011** — the api-contract's error-model *Why* is rewritten: "hours later" for "later", "its structure decides" for "its quality directly determines", plus a trailing sentence that is not in either cited section.
- **R095** — *"will the host refuse the call?"* substitutes "the host" for the tree's "Live". In a corpus about host/server boundaries that substitution is exactly the kind that later gets reasoned from.
- **R028** — *"silently substituted the wrong sound"* is presented as a quotation from `v11-requirements.md`, which says the case should "fail loudly instead of silently substituting".

The full list:

- **R002** — clause (c) drops "and round-trippable" with no ellipsis.
- **R004** — "No telemetry… there is no fleet to observe" joins two separate sentences (legitimately marked with an ellipsis).
- **R006** — "…SWEbench-Verified, plus a 400ms latency reduction" drops the word "benchmarks" present in the tree.
- **R011** — **Substantially rewritten.** Tree: "An error is not a log line **to be read** by a human later; … its **quality** directly determines whether the agent recovers or flails." Capture: "read by a human **hours** later … its **structure** decides…". The trailing sentence about "a defect here in a way it wouldn't be in a human-operated system" is not in either cited section.
- **R028** — "silently substituted the wrong sound" is not in `v11-requirements.md`; the tree says the case should "fail loudly instead of silently substituting".
- **R031** — "emits silently-wrong numbers" — tree says "emitting".
- **R032** — elides "(`ableton://guides/getting-started`)" without an ellipsis.
- **R039** — "Alternative:" is prefixed onto a decision-table column; the column text itself is verbatim.
- **R045** — both quotations are stitches across `mcp-fingerprint-design.md:46-48` and `:80-83`, not verbatim runs.
- **R060** — tree: a socket cutoff "**would discard** the only verification…"; capture: "discarding…".
- **R062** — "Live blocks for tens of seconds instantiating **[the .amxd]**" — the bracket is the miner's editorial insertion; the tree says "instantiating it", with the `.amxd` named one clause earlier.
- **R070** — "**keep** `warning` whenever the status carries it" — "keep" is added.
- **R073** — "despite some early scratch notes saying otherwise" is verbatim, but the capture's gloss that the code "names the doc as wrong" is not what the code does. See CONTRADICTED.
- **R075** — **"so it cost nothing and broke everything" is nowhere in the tree.** The substance (dead code under `from __future__ import annotations`) is at `CHANGELOG.md:731`.
- **R076** — the cwd sentence is compressed and reworded from `server.py:495-501`.
- **R094** — two markdown table rows rendered as prose with the middle column silently dropped.
- **R095** — **"will the host refuse the call?" — the tree says "will Live *refuse* the call?"** ("the host" is substituted for "Live").
- **R098** — "because" prefixed onto `mcp_config.py:190`.
- **R105** — a markdown table rendered as inline prose inside quotation marks.

---

## Mis-anchored citations (the re-anchoring work)

Seven rules carry an address that does not resolve to what it is cited for. All seven are fixable by symbol name, which is the point of the exercise.

| Rule | Cited | Holds instead | Re-anchor on |
|---|---|---|---|
| R012 | `dispatcher.py:245-290`; `schema.py:290-310` | L455 / L316 respectively | **`help_for_tool`** (dispatcher L259), the "Help is special-cased" comment (dispatcher L455), **`register_help_actions`** (schema L316) |
| R036 | `resources/__init__.py:113-131` | `_read_reference_json` / `_node_feature_matrix` | **`_session_snapshot`** (L136; the quoted comment at L140-142) |
| R057 | `server.py:786-812`; `api-notes §"Dispatch fix"` (**no path**) | code anchor is right; all four quotes are elsewhere | **`async def wrapper`** (server L787) + `.prawduct/artifacts/plans/MCP-ASYNC-RENDER-ANALYZE/archive/api-notes.md` §"Dispatch fix — async tool wrapper" (L178) |
| R058 | `api-notes §"Forward-note"` (**no path at all**) | — | `.prawduct/artifacts/plans/MCP-ASYNC-RENDER-ANALYZE/archive/api-notes.md` L206-215, the bold "Forward-note" lead-in |
| R059 | `handlers/jobs.py:230-260` | `Job.get` / `_finish` | **`JobRegistry.create_if_idle`** (L199) + api-notes L198-204 for the quote + **`test_create_if_idle_is_atomic_under_concurrent_starts`** (`test_handlers_jobs.py:92`) |
| R083 | `.claude-plugin/plugin.json:30` | `],` | L31, the `env` / `UV_PROJECT_ENVIRONMENT` line |
| R090 | `resources/__init__.py:200-240` | the quoted sentence is at L192-193 | **`_server_info`** (L183) |

Two further address defects that did not change a verdict but must not survive into a corpus:

- **R022's `PROVENANCE:` is the literal string `as above`.** It resolves for a human reading the file top-to-bottom and for nothing else. Spell out `incoming-bugs/2026-09-11-eq-eight-b-band-writes-are-silent-no-ops.md`.
- **R038's `DEFAULT_LIVE_VERSION`** (its own VOLATILE field) is at `node_features.py:75`, outside the cited `1-60`.

---

## Per-rule verdicts

Rule numbers are positional: **R001 is the first `**RULE:**` block in the file, R106 the last.** The opening clause is given verbatim so a later author can match rows without counting.

### L0 — whether/when to build one

**R001 — RESOLVED**  
*“Before committing to an MCP server for a desktop app, check whether the app is scriptable only from inside its own process…”*  
`.prawduct/artifacts/architecture.md` **§"Why this topology and not a simpler one"** (heading at L51; cited 50-58 brackets it). Quote verbatim.

**R002 — RESOLVED**  
*“Keep pure computation out of the MCP surface when you own a source of truth for it…”*  
`docs/archive/mcp-tool-design.md` **§4.2, para "Quantize / swing / groove are deliberately NOT MCP actions"** (L238). Quote verbatim except the capture drops "and round-trippable" from clause (c) with no ellipsis.

**R003 — RESOLVED**  
*“Do not move large binaries through the protocol — write them to disk and exchange paths plus a JSON summary…”*  
Both cited symbols exist and do what the rule says: `server.py` **`_sweep_stale_takes`**, `handlers/jobs.py` **`Job.status_result`** (L116). BUT the *measured figure* "~23 MB per surface-minute" is not at either symbol — see Constants (real home: `docs/running-the-engine.md:63`).

**R004 — RESOLVED**  
*“For a single-user local server, decide explicitly that there is no fleet to observe…”*  
`.prawduct/artifacts/observability-strategy.md` **§"No telemetry, by decision."** (L11-12, restated L46-48) + `.prawduct/artifacts/api-contract.md` **§"The CLI"** (heading L149; the preflight sentence is at L162 as cited).

### L1 — agent-interface design

**R005 — UNVERIFIABLE**  
*“Check your target clients' tool caps before choosing a tool count — Cursor caps at 40…”*  
The *address* resolves exactly: `docs/archive/mcp-tool-design.md:61` (§1.2) says verbatim "Cursor caps at 40 tools (silent drops above); Copilot caps at 128. AbletonMCP at 52 exceeds Cursor's cap." But whether Cursor/Copilot actually cap there is an external-client fact no read of this tree can settle. Instrument: register 41+ tools against each client and count what the model is offered, or the vendors' published limits at a dated version.

**R006 — UNVERIFIABLE**  
*“Treat ~10K tokens of tool definitions as a hard ceiling and collapse to an action-dispatch surface below it…”*  
Address resolves: `mcp-tool-design.md:55` (>10K guidance), `:57` (Speakeasy 10/20/107), `:59` (Copilot 40→13, "2 to 5 percentage point improvement across SWE-Lancer and SWEbench-Verified benchmarks, plus a 400ms latency reduction"), `:85` (~10K→~2K). Every figure is third-party and borrowed; the doc's own footnote [2] cites a blog post. Instrument: run the benchmark. The capture's own Summary already says no benchmark was ever run here — confirmed, no baseline/benchmark file exists.

**R007 — RESOLVED**  
*“Ratify the tool count as a *band*, not a number, and expect the budget to leak…”*  
`hallucinote_mcp/src/hallucinote_mcp/schema.py` **`TOOLS`** at L16-30 — cited range is exact. **13 tools, counted.** Design budget of 10 at `mcp-tool-design.md:175` (§4.1), `:400`, `:433`, `:756`, and the ≤200-token-per-description criterion at `:776` (§16). `ableton_probe` appears in neither archive design doc (only in `docs/research/audio-first-class/`) — confirmed.

**R008 — RESOLVED**  
*“When you report "N tools became M", state the reduction in *tool-list width* separately from the *action count*…”*  
`docs/archive/mcp-tool-design.md:175` (§4.1) — "Total: ~94 actions in 10 tools" and "~84% reduction in selection-space width vs status quo" are on the same line, verbatim.

**R009 — RESOLVED**  
*“Do not put action parameters behind a `params={...}` envelope — synthesize each tool's schema as `action` plus the flattened union…”*  
`server.py` **module docstring L1-17** (cited range exact) + **`_register_tool`** (L735). The `extra='ignore'` sentence is verbatim at L14-16.

**R010 — RESOLVED**  
*“Once the schema is a flattened union, the dispatcher must reject params unknown *for the chosen action*…”*  
`server.py` **`_collect_tool_params`** (def L703; the collision message "rename one to avoid a flat-schema collision" at L729 — inside the cited 703-733) + `dispatcher.py` **`validate_params`** (def L189; the "fail loudly on typos" comment at L193 as cited).

**R011 — RESOLVED**  
*“Give every error four recovery fields — `valid_actions`, `required`/`optional`, a runnable `example`, and a `hint`…”*  
`api-contract.md` **§"Recorded decision: error model"** (L63, the *Why* at L73) and **§"Direction"** (L172, restated L187) + `dispatcher.py` **`dispatch`** (L419-538). **The quotation is not verbatim**: the tree says "An error is not a log line **to be read** by a human **later**; it is the next turn's input, and its **quality** directly determines whether the agent recovers or flails." The capture wrote "read by a human **hours** later" and "its **structure** decides". The closing sentence ("A bare error string is a defect here in a way it wouldn't be in a human-operated system") is not in either cited section.

**R012 — MOVED**  
*“Generate `action='help'` from the same metadata object the dispatcher validates against…”*  
Two of three anchors are outside their cited ranges. `dispatcher.py` **`help_for_tool`** is at L259 (inside cited 245-290 ✓), but the "Help is special-cased: pure metadata, no Live access required" comment is at **L455**, not 245-290. `schema.py` **`register_help_actions`** is at **L316**, not the cited 290-310 (which is `node_addr_spec`/`register`). Re-anchor on the symbol names, not the lines.

**R013 — RESOLVED**  
*“An error must carry the state that makes the follow-up diagnostic call unnecessary…”*  
`docs/archive/v11-requirements.md` **Arc 1 "A2-resid"**. Quote verbatim.

**R014 — RESOLVED**  
*“Lead your error-recovery guide with "retrying this call with the same params will fail the same way"…”*  
`hallucinote_mcp/src/hallucinote_mcp/resources/guides/error-recovery.md` **§"Error recovery"** opening paragraph (heading L1; cited 1-10 exact). Quote verbatim.

**R015 — RESOLVED**  
*“Return the identity of whatever a mutating action created…”*  
`docs/archive/mcp-requirements.md` §6/§10 — the "49-clip rebuild: 49 wasted round-trips" sentence is verbatim at **L686**.

**R016 — RESOLVED**  
*“Ship a single-item read and a filter parameter alongside every bulk read…”*  
`incoming-bugs/2026-09-11-get-parameters-has-no-single-param-read-and-no-band-filter.md` — title line, `unknown action 'get_parameter'` at L13, **84 parameters** at L16, **~420 parameter rows** at L20, "and I wanted about **six**" at L21. All verbatim.

**R017 — RESOLVED**  
*“A capped read returns an explicit `truncated` flag plus the parameter that subdivides the walk…”*  
`actions/browser.py` **`register(Action(tool="ableton_browser", name="inventory"))`** (L204-220; cited 205-220 lands inside it). Both quotes verbatim in the description string.

**R018 — RESOLVED**  
*“Put a soft cap with a non-blocking `warning` on any payload channel whose cost is the agent's context…”*  
`resources/guides/conventions.md` **§"Inline note arrays: soft cap (~32 notes)"** (heading at L108; cited 108-117 exact). The ~32 threshold is in the heading itself.

**R019 — RESOLVED**  
*“Dispatch a bulk plan out of the agent's context — a CLI that talks to your backend directly…”*  
`CHANGELOG.md` **§"`push_cli execute`" bullet** at L1048-1053 (cited 1047-1053 ✓). Both quotes verbatim.

**R020 — RESOLVED**  
*“Delegate a start+poll loop to a subagent that returns only the terminal summary…”*  
`skills/render-analyze/SKILL.md`. Quote verbatim.

**R021 — RESOLVED**  
*“A write that returns `ok`, returns the new value, and reads back correct is still not evidence of effect…”*  
`incoming-bugs/2026-09-11-eq-eight-b-band-writes-are-silent-no-ops.md` — cost sentence L4, Mode/L-R/M-S L11, the results table **L29-33** (row: "≈ −2.3 dB at 65-95 Hz" → "**+0.08 dB**"), the Mode fix at L62-63. All verbatim.

**R022 — RESOLVED**  
*“Never expose a parameter without exposing the parameter that decides whether it is in circuit…”*  
Same file as R021, **fix #2 at L62-63**. NOTE: the PROVENANCE line reads only `as above`, which is not a durable address — a corpus row must spell out the path.

**R023 — RESOLVED**  
*“In a handler that performs more than one write from separate validations, resolve and validate everything before writing anything…”*  
`.prawduct/learnings-detail.md` **§"Multi-write Live handlers resolve everything before writing anything"** (heading at L539; cited 539-543 exact). Quotes verbatim.

**R024 — RESOLVED**  
*“Refuse a call whose underlying primitive is a destructive toggle…”*  
`resources/guides/error-recovery.md` — the `cue_create` / `set_or_delete_cue` entry. Quote verbatim.

**R025 — RESOLVED**  
*“When a tool's name misdescribes its semantics, the response message is lying too…”*  
`docs/archive/mcp-requirements.md` §1 + `docs/archive/mcp-tool-design.md` §3 principle 8. All four quoted strings verbatim.

**R026 — RESOLVED**  
*“Put your own scars in the agent-facing docs as an explicit anti-pattern gallery…”*  
`docs/archive/mcp-tool-design.md` §2.5. Quote verbatim.

**R027 — RESOLVED**  
*“Never persist a provider-local opaque id as the portable identity of a resource…”*  
`docs/archive/pre-v1-walkthrough.md` §7/§9 item 9. Quote verbatim (including `query:Drums#FileId_5418`).

**R028 — RESOLVED**  
*“Scope a display-name lookup to the canonical category root, and fail loudly naming the collision…”*  
`docs/archive/v11-requirements.md` **Arc 4 D3** at L126 — "empirically loaded an `InstrumentGroupDevice`" verbatim — plus `device_names.py:13` (cited line is exact, a comment about the canonical root). **The Arc 1 A3 quote is not verbatim**: the tree (L61) says the case should "fail loudly instead of silently substituting"; the capture renders it as a quotation "silently substituted the wrong sound", which appears nowhere in that file.

**R029 — RESOLVED**  
*“Accept the host's own internal class name as valid input…”*  
`docs/archive/v11-requirements.md` **Arc 4 D1**. Quote verbatim.

**R030 — RESOLVED**  
*“Pin idempotency per *phase* of a sync tool and test the push→edit→push loop…”*  
`docs/archive/pre-v1-walkthrough.md` §4.3. Quotes verbatim.

**R031 — RESOLVED**  
*“An MCP server that injects its own infrastructure into the user's document must make that infrastructure invisible…”*  
`src/hallucinote/analyzer_staleness.py:7` — "under-measure every device past the tap, **emitting** silently-wrong numbers" (the capture writes "emits"); plus `src/hallucinote/analyzer_identity.py`. Both cited files exist and hold the claim.

**R032 — RESOLVED**  
*“Check who reads each discovery surface — a message aimed at a human must not be written in call syntax…”*  
`docs/archive/pre-v1-walkthrough.md` §1.2/§1.4; the getting-started finding is at **L78**. The second quote elides "(`ableton://guides/getting-started`)" without an ellipsis; otherwise verbatim.

**R033 — RESOLVED**  
*“Pin every count you state about your own surface with a test — including the one in the install dialog…”*  
`hallucinote_mcp/tests/unit/test_server.py` **`test_primer_tool_count_matches_actual_registry`** (L59) and **`test_marketplace_manifest_tool_count_matches_actual_registry`** (L119-143) — cited 59-143 brackets both. `.claude-plugin/marketplace.json:14` currently reads "13 Ableton Live tools", matching `schema.TOOLS`. The "verified by mutating the manifest to 99" quote lives in `.prawduct/change-log-archive.md`, not the test file.

### L2 — protocol semantics

**R034 — RESOLVED**  
*“Do not ship agent-facing workflows as MCP prompts in Claude Code…”*  
`CHANGELOG.md` **§"Changed" → "Workflow skills replace MCP prompts"** (L1055-1057; cited 1057-1072 ✓) + `mcp-tool-design.md` §6/§6.2. In-tree corroboration: **zero prompts are registered anywhere in `hallucinote_mcp/src/`** (no `@mcp.prompt`, no `add_prompt`). The host-behaviour half is external (EXT). One quote is split mid-word by the capture ("...autonomously. There is no assistant-callable `prompts/get` path") but the sentence is present.

**R035 — RESOLVED**  
*“Move to resources anything taking no per-call parameter or only a slow-changing identifier…”*  
`docs/archive/mcp-tool-design.md` §2.3/§5.3 conversion table. Quote verbatim.

**R036 — MOVED**  
*“Let a resource fan out into several handler calls…”*  
The quote is real and verbatim, but at `resources/__init__.py` **`_session_snapshot`** (def **L136**, comment L140-142) — not the cited **113-131**, which is `_read_reference_json` / `_node_feature_matrix`. Re-anchor: `_session_snapshot`.

**R037 — RESOLVED**  
*“Publish a known-gaps resource…”*  
`resources/guides/gaps.md`. Quote verbatim.

**R038 — RESOLVED**  
*“Publish capability as a tri-state matrix (SUPPORTED / NOT_IMPLEMENTED / UNSUPPORTED_IN_HOST)…”*  
`node_features.py` **module docstring L1-60** (cited range exact). NOTE: the VOLATILE field's `DEFAULT_LIVE_VERSION = "12.4"` is at **L75**, outside the cited range — value confirmed.

**R039 — RESOLVED**  
*“Keep a blocked capability present in the surface as a tool returning a teaching "blocked" response…”*  
`docs/archive/mcp-tool-design.md:759` (§15 decision table row) + `server.py:187` — `_register_tool(mcp, "ableton_note", "Within-clip note operations (gap #4 blocked).")`, the cited line exactly. The capture prefixes "Alternative:" onto the table's third column; the column text itself is verbatim.

**R040 — RESOLVED**  
*“Never annotate a polymorphic MCP parameter as `typing.Any`…”*  
`server.py` **`_JSON_VALUE`** and its comment block at **L37-53** — cited range is exact, and the `anyOf: [{}, {"type":"null"}]` reasoning is there verbatim. Test `test_annotated_param_type_any_is_explicit_not_fallback` exists at `test_server.py:940`. "Reproduced 6/6" is at `.prawduct/change-log.md:644` (EXT: a client-serializer behaviour).

**R041 — RESOLVED**  
*“In that union, order `bool` before `int` (bool is an int subclass) and keep `int` as its own branch…”*  
`server.py:46-51` — cited range exact: "``bool`` leads because bool is an int subclass; ``int`` stays in the union so an integer is never widened to float (Live's C++ setters reject a float where the signature wants an int)". Mirror guard at `dispatcher.py:207-213` inside `validate_params` ✓.

**R042 — RESOLVED**  
*“Recover the JSON type of a string-valued arg by parsing it as a JSON literal…”*  
`handlers/probe.py` **`coerce_wire_value`** (def at **L221**; cited 221-244 exact). Quotes verbatim.

**R043 — RESOLVED**  
*“Push `description`, `minimum`/`maximum` and `enum` into the generated JSON Schema via `Annotated[..., Field(...)]`…”*  
`server.py` **`_annotated_param_type`** (def L69; cited 68-96 brackets it), including the `json_schema_extra`-not-`Literal` rationale. The quoted "Agents saw `Optional[int]` for `cc_number`..." sentence lives in `.prawduct/change-log-archive.md`, not `server.py`.

**R044 — RESOLVED**  
*“Version two halves of one source tree by a **content fingerprint**, never semver…”*  
`hallucinote_mcp/src/hallucinote_mcp/__init__.py:1-16` + `api-contract.md` **§"Recorded decision: versioning"** (heading L39; cited 39-56 exact). Two of the quotes live elsewhere: "the worst debugging session in this project's history" is in `architecture.md`, "structurally cannot detect staleness" in `.prawduct/learnings-detail.md`.

**R045 — RESOLVED**  
*“The hashed path set must equal the code that is **both shipped to and executed in** the remote runtime…”*  
`.prawduct/artifacts/mcp-fingerprint-design.md:46-48` (the MCP-7F2K read-side-fix scenario) and **L80-83** (the rejected contract-only hash) + `__init__.py:24-52` (`_FINGERPRINT_PATHS`, cited range exact). Both quoted strings are faithful *stitches* of those passages rather than verbatim runs. `tests/unit/test_server_side_isolation.py` exists.

**R046 — RESOLVED**  
*“Run **two** fingerprints with different blocking postures…”*  
`install_paths.py` **`vendored_content_fingerprint`** (def at **L144**; cited 144-166 exact) + `.prawduct/learnings.md:331` **§"A Live-side change OUTSIDE `_FINGERPRINT_PATHS` ships silently"**. The "a recommendation, never a refusal" quote is in `skills/ableton-mcp-install/SKILL.md`, which the PROVENANCE does not name.

**R047 — RESOLVED**  
*“Normalize line endings before hashing (and skip normalization for files containing a NUL byte)…”*  
`__init__.py` **`_compute_content_fingerprint`** (L56) and **`hash_path_into`** (L99) — cited 96-131 spans both. Quotes verbatim.

**R048 — RESOLVED**  
*“Never format a content fingerprint so it reads like a VCS identifier…”*  
`incoming-bugs/archives/2026-09-09-version-pin-recovery-sha-is-a-content-fingerprint.md`. All three quotes verbatim. `test_version_mismatch_recovery_pin_recipe_actually_pins` exists at `tests/unit/sync/test_push_cli.py:3177`.

**R049 — RESOLVED**  
*“Carry your version on every request so a stale counterpart reports as version drift…”*  
`wire.py` **`Request`** docstring (class L34; cited 35-52 exact) + **`check_version_compat`** (def L219; cited 216-290 spans it). Quotes verbatim.

**R050 — RESOLVED**  
*“Give a strict version handshake a per-call, opt-in bypass…”*  
`wire.py` **`check_version_compat_with_override`** (def **L295**; cited 293-340 brackets it) + `.prawduct/change-log-archive.md:3855-3866` §"Arc 2: ... dev-loop dispatcher bypass". The "every server-side Python edit currently requires reinstall + Live restart" quote is in `docs/archive/v11-requirements.md`, not either cited source.

**R051 — RESOLVED**  
*“Return still-running work as `ok=True` plus a machine-readable `code` discriminator and a job handle…”*  
`wire.py` **`Response.code`** field + its comment (L126-144; cited 130-150 overlaps) and **`error`** (L173; cited 205-213) + `client.py` **`_response_from_dict`** (L185), whose L194 comment reads "`code` rides the OK path too, and dropping it here would strand the..." — the symbol citation is exact.

**R052 — RESOLVED**  
*“Signal internal control flow with a structured flag that is deliberately *not* serialized to the wire…”*  
`wire.py` **`Response`** (class L99; `needs_remote` at L129, cited 100-112 covers the docstring) + `dispatcher.py:565` inside **`run_executor`** (def L549) — cited line exact.

**R053 — RESOLVED**  
*“Stamp every result with the content identity of the code that produced it plus a `stale` flag versus disk…”*  
`server_side/analysis.py` **`_analysis_code_status`** (def at **L247**, returns `{"signature": ..., "stale": ...}` at L256 — cited 247-256 is exact) + `.prawduct/learnings-detail.md` **§"A staleness/version signature must be content-derived, never hand-bumped"** (L121-126 as cited). The "run `/mcp` to respawn before trusting the report" tip lives in `server_side/analysis_actions.py`, not `analysis.py`.

**R054 — RESOLVED**  
*“Tool names and action names are permanently stable — alias, never rename…”*  
`docs/archive/mcp-tool-design.md` §3/§8.2 + `api-contract.md` **§"Recorded decision: deprecation and compatibility"** (heading L87; cited 88-100 exact). Quotes verbatim.

### L3 — transport & operations

**R055 — RESOLVED**  
*“Anything that can exceed the host's tool-call timeout gets `start` + `status`…”*  
`.prawduct/artifacts/plans/MCP-ASYNC-RENDER-ANALYZE/archive/build-plan.md` **§"Design Pivot — what the research changed (READ FIRST)"** (heading exists at **L26**) + `handlers/jobs.py:1-20` module docstring (cited range exact). The "false failure" quote lives in `resources/guides/conventions.md`. EXT: transport-invariance and CC#58687 are external facts (CC#58687 recorded at `.prawduct/backlog.md:1527`).

**R056 — RESOLVED**  
*“Size the long-poll window comfortably under the host tool-call timeout…”*  
`handlers/jobs.py` **`DEFAULT_STATUS_LONG_POLL_S = 45.0`** at **L50** — the cited range 36-50 ends exactly on it — with the "~15s for forward + serialize" and "one knob, not two that drift" reasoning in the comment above. `client.py` **`_STATUS_READ_TIMEOUT = 60.0`** at L95. The "so the socket never severs the wait" phrasing is in api-notes, not `client.py`.

**R057 — MOVED**  
*“Make every tool wrapper `async` and push the blocking dispatch through `anyio.to_thread`…”*  
The code anchor is right: `server.py` **`_register_tool`** → **`async def wrapper`** at **L787** (cited 786-812 ✓). But every quoted string is elsewhere, and the second citation "api-notes §\"Dispatch fix\"" carries **no path**. Re-anchor the evidence to `.prawduct/artifacts/plans/MCP-ASYNC-RENDER-ANALYZE/archive/api-notes.md` **§"Dispatch fix — async tool wrapper"** (heading L178); the `func_metadata.call_fn_with_arg_validation` finding and `mcp==1.26.0` are at L181; "Reverting a handler to plain `def` is a whole-server availability bug" is in `.prawduct/artifacts/architecture.md`. Tests exist: `test_tool_wrappers_are_async_to_keep_event_loop_free` (`test_server.py:693`), `test_status_longpoll_does_not_block_concurrent_tool_calls` (`test_server.py:712`).

**R058 — MOVED**  
*“The next ceiling after the event loop is the thread-pool limiter, not the loop…”*  
PROVENANCE is `api-notes §"Forward-note"` with **no path at all** — unresolvable as written. Re-anchor: `.prawduct/artifacts/plans/MCP-ASYNC-RENDER-ANALYZE/archive/api-notes.md` **bold lead-in "Forward-note — the next ceiling is `anyio`'s thread limiter, not the event loop."** at **L206-215**; both quoted strings are verbatim there, and the doc names the remedy `anyio.to_thread.current_default_thread_limiter().total_tokens`. EXT: that anyio's default capacity is 40 is a third-party fact this tree only asserts.

**R059 — MOVED**  
*“The moment your dispatch becomes concurrent, a check-then-create busy guard becomes a real race…”*  
Cited `handlers/jobs.py:230-260` holds `Job.get`/`_finish`. **`JobRegistry.create_if_idle` is at L199**, and the quoted sentence is in `.prawduct/artifacts/plans/.../api-notes.md:198-204`. The "32-thread atomicity test" is real: **`test_create_if_idle_is_atomic_under_concurrent_starts`** at `hallucinote_mcp/tests/unit/test_handlers_jobs.py:92` with `n = 32` (L97) and `threading.Barrier`. `def active` no longer exists in `jobs.py` — the deletion claim holds.

**R060 — RESOLVED**  
*“Put the per-(tool, action) read-timeout policy at the lowest chokepoint every receive route shares…”*  
`client.py` **`_READ_TIMEOUTS` / `read_timeout_for`** and the policy comment block at **L27-64** (cited 30-120 covers it) + `.prawduct/learnings-detail.md` **§"A realtime / long-playback MCP action needs a read-timeout policy entry"** (heading L527; cited 527-531 exact). One quote is not verbatim: the tree (L42-43) says a socket cutoff "**would discard** the only verification this write-only surface has"; the capture renders it as "discarding...".

**R061 — RESOLVED**  
*“A caller-side read timeout must **exceed** the callee's own ceiling by a real margin…”*  
`client.py` **`_LIVE_REPLY_MARGIN_S = 5.0`** docstring at **L74-89** (cited 63-84 overlaps it). The 120/120, 90/90, 15/15 sentence is verbatim at L85-88 (the capture capitalises its leading "The"). `_BUSY_ADMIT_WAIT_S` 2.0 is referenced there and defined at `remote_script/dispatch.py:44`.

**R062 — RESOLVED**  
*“The timeout ladder must be monotonic *all the way out to the host*…”*  
**Every anchor is line-exact.** `.claude-plugin/plugin.json:32` → `"timeout": 60000`. `client.py:100-112` → the `_READ_TIMEOUTS` table; `_ENSURE_LOADED_READ_TIMEOUT = 180.0` (L94), `_DEVICE_LOAD_READ_TIMEOUT = 120.0 + _LIVE_REPLY_MARGIN_S` = 125 (L96), `_GET_PARAMETERS_READ_TIMEOUT = 90.0 + margin` = 95 (L97). `actions/device.py:169` → `main_thread_timeout=90.0`; `actions/device.py:216` → `main_thread_timeout=120.0`. `.prawduct/operator-verification.md:168-176` → §"What the sitting found", 1.95 s cold / 0.89 s warm. The finding stands at HEAD.

**R063 — RESOLVED**  
*“A timeout on an uncancellable operation is not a cancellation — hold the admission gate with the **runner**…”*  
`remote_script/dispatch.py` module docstring (L1-35) and **`_escalate`** (def L438; cited 400-470 spans it). "clearing on a timer is the same defect on a delay" is in `resources/guides/conventions.md:224`, not `dispatch.py`.

**R064 — RESOLVED**  
*“Return a slow call as a **handle, not a failure**…”*  
`dispatcher.py` inside **`run_executor`** (def L549); the "Kept ahead of the broad catch so it never reads as 'the action is broken'" comment is at **L620** — inside the cited 590-630. The shipped refusal text (do-not-retry) is at `resources/guides/conventions.md`, which the PROVENANCE does not name.

**R065 — RESOLVED**  
*“Refuse a concurrent caller after a bounded admission wait rather than queueing it…”*  
`.prawduct/operator-verification.md:209-217` (§"Box results" — 12 concurrent `device.load`, 5 `LiveBusyError` refusals, 2.3-2.8 s, "consistent with the 2.0 s `_BUSY_ADMIT_WAIT_S`", "No queue formed; the other 7 completed normally") + `remote_script/dispatch.py:146` — "The TCP server spawns a thread per connection with no admission..." is inside the cited 145-160. EXT: the numbers are a live measurement.

**R066 — CONTRADICTED**  
*“A watchdog in your own code can only fire on paths that reach it…”*  
The **rule** is fully supported at `.prawduct/operator-verification.md` **§"#322 — does the fence hold against a real Live, and does it ever wedge?"** (heading L155; cited 155-240 exact): the 61.5 s gap 09:45:05→09:46:06, the bare `FrameError` at 20 s, "the worker never reaches the wait, **and** the ceiling is unreachable by construction rather than mis-tuned" (L191-192, the capture writes "so"), "From the client the shipped fix is invisible", and "Filed as #531". **But the capture's "Four of six verification boxes were UNREACHABLE" is contradicted by the box list it cites**: of the six boxes at L206-232, three are labelled UNREACHABLE, one is labelled **FAILS** ("R9 over a real socket — FAILS"), and two are `[x]`. The document's own section header does say "TWO BOXES PASS, THE OTHER FOUR ARE UNREACHABLE", so the capture copied the header rather than counting the list — and the first `[x]` box is itself labelled "NOT REPRODUCIBLE AS WRITTEN, and the escalation half FAILS". Do not ship the "four UNREACHABLE" figure; say "three UNREACHABLE, one FAILS" or drop the count.

**R067 — RESOLVED**  
*“Back an in-memory job registry with a crash-resilient on-disk heartbeat…”*  
`handlers/render.py` **`_write_status_json`** (def L198; cited 186-215 spans it) and **`render_status_handler`** (def L1262; cited 1276-1290 inside it). All four quotes verbatim.

**R068 — RESOLVED**  
*“Keep the running heartbeat out of the terminal payload…”*  
`hallucinote_mcp/tests/unit/test_async_render.py` **`test_terminal_heartbeat_does_not_leak_into_progress`** (def at **L169**; the `"manifest_path" not in job.progress` assertion at L192 — cited 169-192 is exact).

**R069 — RESOLVED**  
*“Name every job kind explicitly in the terminal-payload branch…”*  
`handlers/jobs.py` **`Job.status_result`** (def at **L116**; the "Every kind is named: a bare ``else`` would hand one kind's key names to the next kind that gets added" comment at L127-129 — cited 116-160 exact). `test_main_thread_status_does_not_borrow_analyzes_terminal_keys` exists at `test_handlers_jobs.py:180`.

**R070 — RESOLVED**  
*“An advisory the backend raised without refusing must be allowlisted onto the status payload…”*  
`handlers/jobs.py:136-145` inside `Job.status_result` — "This allowlist is the ONLY path from a render result to a caller, so a handler that adds an advisory and stops here has added nothing" is verbatim, inside the cited 135-152 + `skills/render-analyze/SKILL.md:60`. That line reads "**and `warning` whenever the status carries it**"; the capture prefixes "keep".

**R071 — RESOLVED**  
*“Know that going start+poll moves input-validation errors from the call's return to the poll…”*  
`server_side/analysis_actions.py:281-284` — cited range exact; the tip string begins on L281.

**R072 — RESOLVED**  
*“Explicitly clear the socket timeout when you mean "block indefinitely"…”*  
`wire.py` **`recv_message`** (def L397); the docstring sentence "Without the explicit clear, ``socket.create_connection``'s connect timeout would carry over and bound the read at 15 s..." is at **L411**, and `sock.settimeout(timeout)` at L415 — both inside the cited 400-425.

**R073 — CONTRADICTED**  
*“Use TCP with 4-byte length-prefixed JSON for a local bridge, not UDP…”*  
The primary anchors are exact and the disagreement is real: `wire.py` **module docstring L1-14** says "TCP (not UDP, despite some early scratch notes saying otherwise)" and gives the 64KB reason; `_MAX_MESSAGE_BYTES = 16 * 1024 * 1024  # 16 MiB — generous; guards runaway prefixes` is at **L30**, the last line of the cited 1-30; `DEFAULT_PORT = 9878` with "Different from the legacy fork's 9877 so both can coexist while a user migrates" at L24-26. `docs/archive/mcp-tool-design.md` **§10.2 "Both layers, both ours"** (heading L523) says the Remote Script "opens a **UDP** server" at **L528** — and also at **L518**, a second instance the capture does not name. **What is contradicted:** the capture says the code "names the doc as wrong" (and its TENSION line says "the design doc says UDP"). The code names "some early scratch notes", never the design doc. The correction in the tree is not a citation of the document, so the rule must not be shipped claiming the code calls the doc out by name.

**R074 — RESOLVED**  
*“Use short-lived per-request connections rather than a pooled one…”*  
`client.py` **module docstring L1-11** (cited 1-13) — "Short-lived connections (per request) keep the model simple" verbatim. The "De-risked before adopting" sentence is at api-notes.md:196-197, under §"Dispatch fix"; the citation for it again gives no path.

**R075 — RESOLVED**  
*“Keep the server stdlib-only **at module import time** and lazy-import the heavy engine at call time…”*  
`CHANGELOG.md:731` (§"Fixed", v1.2.0-era) carries the whole story verbatim: `sqlite3` at module top, Live 12.x's missing `_sqlite3`, the aborted Control Surface load, `127.0.0.1:9878` never starting, dead code under `from __future__ import annotations`, and the new AST test. `hallucinote_mcp/tests/unit/test_remote_script_import_safety.py` exists (its own L15 repeats the dead-code point). **"so it cost nothing and broke everything" appears nowhere in the tree** — it is the miner's phrasing set in quotation marks.

**R076 — RESOLVED**  
*“Resolve paths, defaults and identifiers on the side that has the context, *before* forwarding…”*  
`server.py` **`_absolutize_render_output_dir`** (def L492) and **`_attach_render_db_seq`** (def L544) — cited 493-560 spans both; `OSError [Errno 30]` at **L501**. The tree says "the render handler runs on the Remote Script side (inside Live), whose cwd is ``/`` on macOS — a read-only filesystem"; the capture's quotation compresses this into one sentence about "the render worker". The vendored-env sentence is in the MCP-ASYNC build-plan.

**R077 — RESOLVED**  
*“Put a seatbelt in front of any large-output write whose destination came from a resolver…”*  
`server.py` **`_refuse_render_into_phantom_song_dir`** (def at **L424**, refusal returned by L490 — the cited 424-490 is exact). The "~290 MB parked in a phantom ``songs/<slug>/``" sentence and the three narrowing clauses are all verbatim in that docstring.

**R078 — RESOLVED**  
*“On stdio, stdout is the wire — route your own logging, and any subprocess you spawn, to stderr…”*  
`cli/serve.py:33-38` inside **`run_serve`** (def L23) + `hooks/prewarm_mcp_env.py` (docstring 1-30 and the `subprocess.run(..., stdout=sys.stderr)` at 85-92). Cited ranges land correctly.

### L4 — client/host integration

**R079 — RESOLVED**  
*“A plugin manifest's per-server `timeout` governs **tool execution**, not the startup handshake…”*  
`mcp_config.py:14-20` — "that's ``MCP_TIMEOUT`` (env var, ms, default 30000)" at **L20**, inside the cited 1-40; the ~70 MiB numpy/scipy/librosa note at L16 + `.prawduct/learnings-detail.md` **§"A plugin MCP server's STARTUP timeout is `MCP_TIMEOUT`..."** (heading L501; the `30000ms` log line and CC#60224 at L504-516, cited 501-518 exact) + `.prawduct/operator-verification.md` **§"INS-7V2D follow-up..."** (heading **L1216**; warm handshake "~2.3 s" at L1226, the 180000 floor at L1224 — cited 1216-1243 exact). In-tree instantiation: `.claude/settings.json:3` sets `"MCP_TIMEOUT": "180000"`. EXT: the host's 30000 ms default and the silent-tool-drop behaviour.

**R080 — RESOLVED**  
*“A SessionStart pre-warm hook is not the mitigation for a slow startup…”*  
`hooks/prewarm_mcp_env.py` + `.prawduct/learnings.md:247-257`. "Belt-and-suspenders, not load-bearing" and "NEVER fails the session" are both in the hook (the capture joins them across an ellipsis). **`test_prewarm_hook.py` contains exactly 9 test functions**, matching "Pinned by 9 tests", and both named ones exist (`test_missing_uv_never_fails_the_session` L171, `test_failed_sync_never_fails_the_session_and_retries_next_time` L199).

**R081 — RESOLVED**  
*“When tools vanish or misbehave at startup, read the client's own connection log before theorizing…”*  
`.prawduct/learnings-detail.md:515-516` — CC#60224 and the literal path `~/Library/Caches/claude-cli-nodejs/<proj>/mcp-logs-*/` are inside the cited 513-518. EXT: what the log prints is host behaviour; nothing in the repo reads that path.

**R082 — RESOLVED**  
*“Launch a distributed MCP server through a locked, project-pinned runner from the distribution root…”*  
`.claude-plugin/plugin.json:25-33` — `"command": "uv"` at L25, args `run --frozen --all-packages --project ${CLAUDE_PLUGIN_ROOT}` at L26-30 — cited range exact + `test_plugin_manifest.py` **`test_launch_uses_uv_not_a_bare_path_binary`** (def **L32**) and `test_launch_runs_the_bundled_workspace_from_plugin_root` (L40) — cited 32-54 spans both.

**R083 — MOVED**  
*“Redirect the runner's environment into the host's writable plugin-data directory…”*  
Off by one: `.claude-plugin/plugin.json:30` is `],`; the `"env": { "UV_PROJECT_ENVIRONMENT": "${CLAUDE_PLUGIN_DATA}/venv" }` line is **L31**. The test anchor is exact — `test_plugin_manifest.py` **`test_env_redirects_venv_into_persistent_plugin_data`** (def L56, the "read-only ROOT, persistent DATA" message at L63; cited 56-65 ✓).

**R084 — RESOLVED**  
*“Before claiming a lockfile-pinned install works, verify the lockfile is actually git-tracked…”*  
`.prawduct/learnings-detail.md` **§"A distribution artifact the product needs at install time must be TRACKED"** (heading L489; cited 489-493 exact) + `docs/release-process.md` **§"7. Commit the release on `develop` and push"** (heading L209; the "lock still recording 0.9.0" / `uv lock --check` sentence at L226 — cited 219-226 ✓).

**R085 — RESOLVED**  
*“For any format the *harness* parses, take ground truth from a known-working example in the installed plugin cache…”*  
`.prawduct/learnings-detail.md` **§"A Claude Code plugin's hook/manifest format: verify against the installed plugin cache, not a docs/research..."** (heading L495; cited 495-499 exact). In-tree instantiation: `hooks/hooks.json` exists in shell form. The "a wrong hook silently never fires" sentence also appears in `.prawduct/learnings.md`. EXT: the harness's accepted manifest form.

**R086 — RESOLVED**  
*“Perform every install/uninstall filesystem mutation in tested, atomic Python invoked as a CLI subcommand…”*  
`.prawduct/artifacts/install-hardening-design.md` (the `.staging`/`.backup` sentence verbatim) + `skills/ableton-mcp-install/SKILL.md`. `test_install_skill_has_no_handauthored_mutation_shell` exists at `test_install_skill_consistency.py:102`.

**R087 — RESOLVED**  
*“Anchor a copy-exclude to the source root when the same filename exists at two levels…”*  
`install_paths.py` — the `server.py`-at-two-levels rationale and **`_ignore`** (def L82) are inside the cited 30-95; `vendor_ignore` exists. The "so adding an exclude changes all three at once" clause is a stitch across the module's own prose rather than one verbatim run.

**R088 — RESOLVED**  
*“Re-raise on directory-walk errors in anything that feeds a completeness or drift check…”*  
`install_paths.py` **`vendored_files`** (def L100) and **`_reraise`** (def L111) — cited 110-126 spans both; the "an unreadable directory present on BOTH sides makes the two fingerprints agree" sentence is verbatim there.

**R089 — RESOLVED**  
*“Fingerprint binary artifacts you install by raw bytes and skip the overwrite prompt when they match…”*  
`skills/ableton-mcp-install/SKILL.md` §3d + `hallucinote_mcp/tests/unit/test_ins_4h8m.py` — **`test_fingerprint_does_not_normalize_line_endings`** at **L50**.

**R090 — MOVED**  
*“Have the installer read the **running** server's identity from a no-backend-dependency resource…”*  
The `ableton://server/info` anchor is off: `resources/__init__.py` **`_server_info`** is def **L183**, and the "Deliberately NO Live dependency: install runs with Live closed" sentence is at **L192-193** — *before* the cited 200-240. `cli/preflight.py:19-52` is correct: **`_content_reference`** (def L23) holds "A ``None`` root **withholds** the verdict" and "one is worse than no comparison: it is the shape an operator acts on" (L43-46). The INS-3W8P coexistence quote lives in `skills/ableton-mcp-install/SKILL.md`, not either cited file.

**R091 — RESOLVED**  
*“Expose the server's own `sys.executable` so the agent runs your CLI in the *same* environment as the bridge…”*  
`resources/__init__.py` **`_server_info`**'s `python` field documentation (cited 225-233 falls inside the function, def L183) + `docs/running-the-engine.md`. The quotation joins two sentences across an ellipsis; both halves are present.

**R092 — RESOLVED**  
*“An agent that installs an update *through* the MCP connection it just replaced cannot verify its own work…”*  
`skills/ableton-mcp-install/SKILL.md` §5a. Both quoted runs present (the capture joins them across an ellipsis).

**R093 — RESOLVED**  
*“Diagnose a version mismatch from the side that holds the third fact…”*  
`hallucinote_mcp/src/hallucinote_mcp/__init__.py` **`stale_server_process_hint`** (def at **L169**; "there is a third fact only the server side holds: its **on-disk source**" at L177 — cited 170-210 exact) + `server.py` **`_refine_version_mismatch`** (def **L404**, called at L288) — the symbol citation resolves. "re-vendoring ... and restarting Live will NOT help a stale process" is a stitch, not one verbatim run.

**R094 — RESOLVED**  
*“Document which failures a client reconnect fixes and which need a full host restart…”*  
`.prawduct/artifacts/architecture.md` **§"Failure independence — what breaks when each runtime dies"** (heading L67; the table row at **L73** reads "| MCP server | Tools vanish from the agent's surface. | `/mcp` respawns the subprocess. Sufficient for engine changes; **not** for Live-side changes. |") — inside the cited 66-76 + `.prawduct/operator-verification.md:147-153`. The capture renders two table rows as prose, eliding the middle column without an ellipsis; the "Requires an MCP server restart, NOT a re-vendor" sentence is in operator-verification.

**R095 — RESOLVED**  
*“Ship a three-state re-vendor verdict with every release…”*  
`docs/release-process.md` **§"5. Determine the re-vendor impact (do not skip — it's the consumer-facing fact)"** (heading at **L159**; the section runs to L196, cited 159-194 ✓). "A release that changes only those leaves the fingerprint still and the vendored copy stale, so a `not required` verdict derived from the grep alone would be wrong" is verbatim (L174-177); the `server_side/` exception is at L186-188. **The other quotation is altered**: the tree says "will Live *refuse* the call?" (L172); the capture writes "will the host refuse the call?".

**R096 — RESOLVED**  
*“Batch every pending live-gated check into one re-vendor/restart sitting…”*  
`.prawduct/operator-verification.md:43-46` (§"RENDERGUARD-0910" — "**Fingerprint flip: YES.**") and **§"The open-bug sweep's re-vendor sitting (2026-09-10)"** (heading **L425**; cited 425-435 inside it) + `.prawduct/learnings.md` **§"An expensive restart/reload cycle only pays off if you batch every fix into it"** (heading L339 as cited).

**R097 — RESOLVED**  
*“Enumerate every config *scope* a server can be registered in before writing an uninstaller…”*  
`skills/ableton-mcp-uninstall/SKILL.md` (the plugin-provided / `removed: []` case verbatim) + `mcp_config.py` (temp-file + `os.replace`, malformed-file refusal).

**R098 — RESOLVED**  
*“Make the uninstaller's symmetric env cleanup conservative…”*  
`mcp_config.py` **`ensure_startup_timeout`** (def L120) / **`unset_startup_timeout`** (def L173) — cited 160-205 spans both; "a value below the floor is exactly the cold-start-timeout failure this package exists to prevent" is at **L190**, inside the range. The capture prefixes "because" onto it. The manual-cleanup recipe is in the uninstall SKILL.

**R099 — RESOLVED**  
*“Do the engine work in a git worktree and leave the checkout your remote half was installed from alone…”*  
`docs/known-issues.md` **§"Switching branches in the engine checkout breaks the push CLI's bridge"** (heading L17; cited 17-23 exact) + `.prawduct/learnings.md:309` §"In a git worktree, pin `pythonpath` in pytest config".

**R100 — RESOLVED**  
*“Pin an environment *before Python starts* — there is no `--pin` flag possible…”*  
`resources/guides/error-recovery.md` **§"Engine version drift"** — "There is no `--pin` flag." verbatim, with the copy-vendored-package / copy-back-`cli/`-and-`server.py` / `PYTHONPATH` recipe.

**R101 — RESOLVED**  
*“To reproduce a wire-typing bug, drive the raw wire; to reproduce a schema-serialization bug, drive the real client…”*  
`.prawduct/operator-verification.md:147-153` (§"RELBLK-0910", heading L101 — "6/6 client-side failures, so the only honest test is the real MCP client" at L147) and 425-445 (§"The open-bug sweep's re-vendor sitting"). EXT: the client-coercion behaviour itself.

**R102 — RESOLVED**  
*“For a two-channel CLI seam behind an agent skill, declare whether each stderr message is **contract** or **diagnostic**…”*  
`.prawduct/artifacts/boundary-patterns.md` **§"Pull Planner / Result API"** (heading L86; the two-channel bullet at L123) and **§"When changing this surface:"** (L144; the add-a-stderr-message rule at L153) — cited 123-153 brackets both.

**R103 — RESOLVED**  
*“Skip post-install hooks and `register` console scripts…”*  
`docs/archive/mcp-tool-design.md` **§10.5 "Distribution + Install (LLM-mediated)"** (heading L593); the rule's sentence is verbatim at **L604**. The TENSION is real — the fenced "End-user experience" block at **L616** reads `pip install hallucinote-mcp          # post-install hook runs \`hallucinote-mcp register\` automatically`, contradicting L604 on both counts. Correction to the capture: that block is **12 lines later**, not "three lines later".

**R104 — RESOLVED**  
*“Put the tool/action schema in one module imported by *both* halves…”*  
`docs/archive/mcp-tool-design.md` §10.1/§10.2 — both quotes verbatim (§10.2 heading "Both layers, both ours" at L523).

**R105 — RESOLVED**  
*“Make ~60-70% of actions declarative (navigation path + op kind + value schema) with a handler escape hatch…”*  
`docs/archive/mcp-tool-design.md:538` (§10.3) — "Most Live operations are one of three shapes:" followed by a **table** whose rows are Property read / Property write / Method call; the capture renders the table as inline prose inside the quotation marks. Rejected-alternatives quote verbatim. Code anchor exact: `schema.py` **`LiveOp`** (class L56; cited 57-94).

**R106 — RESOLVED**  
*“Treat an action-surface change as a fan-out edit with a fixed checklist…”*  
`docs/archive/mcp-tool-design.md` §2.6. Quote verbatim. NOTE an internal inconsistency the capture inherits: the rule's clause lists **six** targets while the quote it cites says "all **seven** targets get updated together".

---

## Does the evidence support the coordinator's claim that it "verified their flagged claims against the tree"?

**Partly, and the part that is false is the part the sentence was read as promising.**

What the evidence supports:

- **Every path is real.** 52 distinct tree paths, zero fabrications, across the server package, the archived design docs, the incoming-bug files and the repo's own governance state. Nothing was invented.
- **Every constant is right.** Thirty-odd measured figures, every one matching the tree. A coordinator that had not opened `client.py` could not have produced `180 s`, `125 s`, `95 s`, `120 s`, `90 s` and `5.0` together, because three of those are *composed* literals (`120.0 + _LIVE_REPLY_MARGIN_S`) whose stated values only exist once you have read the margin.
- **Line-exactness where it counted most.** `plugin.json:32`, `actions/device.py:169` and `:216`, `schema.py:16-30`, `server.py:37-53`, `server.py:424-490`, `session.py:358`, `handlers/jobs.py:36-50`, `test_server.py:59`/`:143` — these are not the numbers of someone recalling a file. The three claims the capture flags as still-wrong-at-HEAD are all three still wrong at HEAD, which is a genuinely load-bearing verification.
- **The word "verified" is used sparingly and correctly.** It appears in R007's `PROVENANCE` ("verified: 13") — and 13 is right.

What the evidence contradicts:

- **The quotations were not verified as quotations.** Nineteen of them are not what the tree says, and one (R075) is absent from the tree entirely. In a schema whose whole purpose is that a rule can be re-derived from its address, a `*"..."*` run is a transcription claim, and transcription is precisely where a claim degrades while reading exactly like a faithful copy. The two cases that matter — R011's rewritten error-model rationale and R095's "the host" for "Live" — are both substitutions *toward* the generalisation the corpus wants, which is the direction that will never look wrong to a later reader.
- **Seven addresses do not resolve, and two of those cite no path at all.** `api-notes §"Dispatch fix"` and `api-notes §"Forward-note"` are unresolvable as written; there are three `api-notes*.md` files in the repo and the right one is four directories deep in an archived plan. R059 points at a line range that holds two unrelated methods while the symbol it names sits 30 lines earlier. Nobody who resolved those citations would have left them in that state.
- **The one count the capture derives for itself is wrong** (R066's "four of six UNREACHABLE"), and it is wrong in the specific way that betrays the method: it copied a section *header* rather than counting the *list* the header summarises — one line above the list, in a file it demonstrably had open, since the 61.5 s gap and the 1.95 s re-measurement both come out of that same section verbatim. The header and the list disagree in the source; a verification pass is exactly what finds that, and this one reported the header.
- **Its own three-way rule-count disagreement was never reconciled** — the capture says so honestly in its preamble, which is to its credit, but it also means the coordinator's summary figure (78) is a number it never re-derived from its own output.

**The honest reading.** The coordinator verified *facts* — the constants, the tool count, the symbols, the three still-live defects — and did not verify *transcriptions* or *addresses*. Both halves are consistent with an agent that read the files carefully and then wrote up from a summary rather than from the open file: the numbers survive that, because they were the thing being looked for; the wording and the line ranges do not, because they were incidental to the look. So "I verified their flagged claims against the tree" should be read as a claim about the claims that were *flagged*, not about the report. It does not license the rest of the block, and the corpus schema treats the whole block as addressed.

**What that means for the corpus.** The addressing debt here is the small end of the problem. This file is the only one of five with any addresses at all, and it needed 7 re-anchors, 19 quotation corrections, 2 substantive contradictions and 1 bad count out of 106 rules. The other four captures carry **zero** `PROVENANCE:` lines while stating hard measured figures — so the pass that produced these numbers has not yet been run anywhere it would find more.

