# bankmachine — 84 rules (Python server; the MEASURED evidence trail)

**Why this source matters:** four acceptance rounds run **black-box by a tester with no source
access**, plus four latency studies. Measurements and a defect progression, not design prose. Also
the only sibling that ships MCP **resources** as a first-class surface and can say why.

Distilled non-generic material ≈ 6–8k words out of ~34k read.

## A. The instructions-truncation finding — the most transferable measurement in the corpus

- **A client delivered 2,045 of 6,673 characters of handshake `instructions` to the model, cut
  mid-table, silently, with the surviving prefix reading complete.** Everything below follows.
- **Set a CHARACTER ceiling on `instructions` derived from a measured client truncation, and open
  with your resource URIs rather than closing with them** — a pointer a client would trim is a
  pointer that does not exist. `INSTRUCTIONS_BUDGET = 1800`, pinned by a test.
- **Serve deep reference material as MCP resources, not handshake prose** — a resource costs the
  session nothing until something reads it; every character of `instructions` is paid whether the
  question needs it or not.
- **Hold the UNION of handshake text and served resources against the live wire in a test**, so a
  field or warning kind cannot fall out of both as the budget pushes material between them.
- **When the budget will not fit a list, render the COUNT from the tuple rather than naming
  members** — naming both reconciliation kinds cost 55 of the ~80 characters left.

## B. Resources — tools-vs-resources done properly

- **Draw a tool's boundary where the ANSWER SHAPE changes, never where the question changes.** Both
  "one tool per question" and "one tool with an action enum" share the false premise that a boundary
  tracks the question. Shape-factoring took 10 specified tools to 8 with zero `outputSchema` loss.
  *Directly qualifies the naive reading of "minimize tools".*
- **Permit a merge only when ONE STRICT row schema covers every parameter value with no OPTIONAL
  fields** — nullable is fine (`["string","null"]`), absent is not, because absence-as-information
  only holds while absence is a property of the TOOL rather than of the answer. A proposed merge
  failed this guardrail as specified and was admitted only after a unifying nullable shape was found.
- **Enforce schema-strictness inside the ONE function that hands out a tool definition**, not at
  startup — registration is not an event an MCP server has (`tools/list`, derived docs and every
  test all build the surface).
- **Refuse at startup when two parameters share a NAME with different TYPES across the surface** —
  a SELECTION failure, not a validation one: an agent that learned `since` is a date string on one
  tool carries that to the next, and the rejection reads as its own mistake. (Types only,
  deliberately not descriptions — "forcing one wording would be a style rule wearing a guard's
  clothes".)
- **DERIVE every reference resource from the vocabulary or the published schemas** — never
  hand-author — and test the derivation with a positive control that ADDS a kind and fails if the
  document was typed rather than walked.
- **A reference resource must read NOTHING** — no datastore, no network — so it still answers on the
  one connection where the operator most needs to ask why the tools are broken.
- **Keep a resource's LIST metadata and READ text in one object** — a client that lists a URI it
  cannot read is the exact failure the capability declaration exists to prevent.
- **Publish `size` in bytes on every listing entry** — what lets a host estimate context cost before
  reading, which is the whole argument for resources over handshake prose.
- **Use your OWN URI scheme**, never `file://` or `https://` — a fetchable-looking scheme invites a
  client to fetch it itself and reach something other than your server.
- **Answer `resources/templates/list` with an empty array rather than refusing** — declaring the
  capability is what invites the call.
- **Declare in the served reference which specified tools are NOT BUILT, by name**, and say their
  absence is not a fault to work around — otherwise an agent improvises the missing capability over
  the tools that exist and presents an inference as a record.
- **Publish a "what this server cannot answer" section** listing each question with no data path
  that can still be given a plausible-looking answer by improvising.

## C. The acceptance-round defect progression (rounds 2→3→4→4a)

- **Refuse an out-of-range argument and QUOTE the ceiling; never clamp.** Clamping makes a trimmed
  answer byte-identical to a complete one; refusing means any ACCEPTED request is structurally known
  not to have been trimmed. `limit:0`→1 row and `limit:-5`→1 row against a true count of 16.
  *(Note this is in direct tension with the opposite policy held elsewhere in the corpus — see the synthesis
  question in the README.)*
- **Treat `limit:0` returning one row as a CLAMP hypothesis, not a coincidence** — the tester nearly
  filed it as fixed; only a second probe revealed the mechanism.
- **Enumerate every distinct condition that can produce an EMPTY result and make each
  distinguishable.** Four states shared one byte-identical `{"rows":[]}`: nonexistent id,
  real-but-empty, out-of-range id, and a transposed date window — "the one a real person hits, and
  '$0 spent' is a believable answer".
- **Fix an empty-answer ambiguity one arm at a time and expect the QUIETER arm to survive** — a
  range check catches ids below the floor and nothing catches above it, because the ceiling is DATA,
  not a constant.
- **When you refuse an unknown id, verify the fix did not OVER-REACH** — the control that matters is
  that an id which exists but is genuinely quiet still answers `rows: []` without a refusal.
- **A silently-truncating DEFAULT limit is the same defect class, on the other axis — over-asking is
  loud, under-asking is silent.** Measured: default `limit:100` over a 2-year window returned 100
  rows stopping **mid-month**, no truncation marker; **49.0% dropped** on a 365-day window, **74.2%**
  on full coverage. Summing understated a two-year card total by ~40%.
- **A match count or cursor is mandatory; a bigger default is NOT a fix** — a consumer holding 100
  rows had no reachable way to discover there were 388.
- **Ship `matching` / `remaining` / `returned` / `truncated` together and make `truncated` the loop
  condition** — never `returned < matching`, which stays true on the last page of every walk.
- **A warning that rides EVERY response carries zero information about the answer it is attached
  to.** The identical `gapped` notice appeared character-for-character on a window fully inside
  coverage, a window 8 months before coverage, a future window, and a nonexistent account. "It
  trains a consumer to ignore the field."
- **Split the warning vocabulary into CONNECTION-scoped (ride every answer) and REQUEST-scoped
  (fire only when this request crosses the boundary named)**, and state in the primer that a
  request-scoped kind's absence is information — naming the count of exceptions.
- **Name the warning whose absence is NOT information as the exception**, deriving the count from
  the tuple, because a hand-written exception goes stale "in the direction that tells an agent
  silence means clean on an answer that can be wrong by a residual".
- **CLASSIFY, do not filter.** An aggregate that silently drops a class of rows produces a precise,
  plausible, catastrophically wrong answer: `spending_summary` filtered `amount < 0` and called it
  spending — `TRANSFER_OUT` alone was **$164,400 of a $267,692.77 two-year total (61%)**, reaching
  **80%** with card payoffs, "none of it discretionary spending".
- **A filter-based aggregate is ALSO wrong in the netting direction, and fixing classification does
  not fix it** — TRAVEL netted to exactly $0 (24 × −$500 against 24 × +$500, ~17 days apart) while
  the tool reported **$12,000**, and still does. The two were deliberately cross-linked so a builder
  shipping the first and checking TRAVEL does not conclude the fix failed.
- **Measure a field's null rate BY VALUE, not by row** — `merchant` was null on 49.74% of rows but
  **89.94% of outflow by value**; the row figure is what a naive check produces and flatters by ~2×.
- **Changing the TOOL DESCRIPTION to steer away from an unreliable field is a real fix with a
  measurable delta** — rewording to prefer `description` moved a rollup from "(null) $240,768 /
  FUN $2,235" to a complete attribution summing exactly to the all-time outflow.
- **State explicitly which field wins against WHICH** — `description` is authoritative against
  `merchant` and is NOT evidence against `category` or `amount`. A tester with the category in its
  own quoted output still weighted free text over it, "which makes it a candidate defect in the
  *description* rather than only a tester error".
- **A fixed threshold is the wrong instrument for a cadence you did not measure** — "gaps > 7 days"
  over monthly accounts flagged **23 of 23 intervals** on two accounts, **~146 findings with zero
  signal**. Derive from each account's own median interval and report trailing silence against it.
- **A store-wide count in the envelope is NOT a completeness signal** — `coverage.transactions`
  reported 388 on every call regardless of window, suggesting truncation on every correct answer and
  saying nothing on a truncated one.

## D. Errors and refusals

- **Put the error object's compact JSON in the `content` TEXT as well as `structuredContent`.**
  Measured through a real client, only the error STRING was visible and `structuredContent.error.
  code` never reached the model at all — so recovery fields placed only in `structuredContent` are
  invisible to the agent they exist for. *Corroborates discodon independently.*
- **Do NOT shape a refusal to match the tool's `outputSchema`** — that schema describes an ANSWER;
  a client holds `structuredContent` to it only where `isError` is false, so dressing a refusal as
  an answer costs the `error` block a consumer branches on.
- **Carry the correction as FIELDS, not prose** — `arguments`, `required`, `optional`,
  `valid_values`, `minimum`, `maximum`, `example`, `see` — emitting each only when it applies, so
  its absence is information.
- **Test a refusal by CONSTRUCTING THE RETRY from the structured fields alone and asserting it
  succeeds** — "a test that only asserts the fields exist would pass on fields that do not actually
  lead anywhere".
- **Read `required`/`optional` off the tool's OWN published `inputSchema`** when building recovery,
  never a hand-kept list.
- **Require the recovery value in the refusal type's CONSTRUCTOR, and catch the BASE refusal class
  at the boundary** — a tuple of concrete classes lets a later-added refusal fall through to the
  broad catch and reach the caller as "internal error", a false statement about a mistake they could
  have corrected.
- **Give a FIXABLE unservable state its own error code ahead of `internal_error`** — before
  `datastore_unservable` existed, an unservable store answered every tool with zeroed coverage on
  the SUCCESS path, "and an agent that skipped `warnings` reported that the household owned nothing".
- **Never let an exception string cross the boundary** — a SQLAlchemy error stringifies to the
  failing SELECT and its bound parameters: your schema and the user's money.
- **Every refusal names the ARGUMENT, the RULE and the OFFENDING VALUE.** Independently verified
  across nine distinct refusals in one run.
- **Name the rule the value actually broke, not the format** — `2026-02-30` refused with "must be in
  YYYY-MM-DD form" tells a user whose format is right that it is wrong.
- **Resolve the tool NAME before dispatching**, so a `KeyError` beneath the query layer is not
  answered "no tool named X" — a false statement about a tool that exists.
- **Refuse an unknown TOOL NAME with `-32602`, never `-32601`** — the name is a *parameter* of
  `tools/call`, a method you do serve; `-32601` tells a code-classifying client that tool calls are
  unsupported here, so one bad name costs the whole surface.
- **Refuse an unknown RESOURCE URI with `-32602`, not the retired `-32002`** (reserved, never
  reused — a retired code is a refusal a current client cannot classify).
- **Close the error-code vocabulary BY TYPE** so the type checker refuses a fifth code at the call
  site.

## E. stdio transport and framing

- **START even when the datastore is missing or empty** — a client launches the server as a
  subprocess, so a server that exits at startup shows up as a tool that silently does not appear.
  "An earlier version refused, which INVERTED the requirement."
- **A malformed TOOL SURFACE is the opposite case and MUST refuse at startup** — otherwise the
  earliest it can fire is the client's first `tools/list`, outside the request handler's try, which
  ends the read loop and takes the session with it. (Exit 2 "could not run", not 1.)
- **Nothing may escape the request handler** — an unhandled exception closes the pipe mid-session and
  the operator sees their tool *disappear* rather than fail, "the one outcome worse than any wrong
  answer". Two nested boundaries, because `initialize`, `tools/list` and the resource methods each
  assemble replies that can raise.
- **Put RESULT RENDERING inside the guard** — SQLite's dynamic typing lets a BLOB sit in a TEXT
  column, so serializing the answer can raise on an ordinary question.
- **Implement JSON-RPC BATCH** — base JSON-RPC 2.0, mandatory in the two oldest revisions you offer.
  Refusing the array with one `id: null` error leaves every id inside it unanswered and the client's
  promises never settle.
- **Get the three batch edge cases right:** an EMPTY array is one non-array error under `id: null`;
  a batch of only NOTIFICATIONS is owed NO response (not `[]`); a bad ELEMENT rides inside the array.
- **Test for the PRESENCE of the `id` member, not `id is None`** — collapsing the two leaves a client
  waiting forever. *(Corroborates cordyceps independently.)*
- **Refuse by-position `params` (a JSON array) explicitly** — permitted by JSON-RPC, never sent by
  MCP, and every handler reads params as an object.
- **Catch `UnicodeDecodeError` around `readline()` ITSELF** — the decode happens one step before your
  JSON parsing, so a try around `json.loads` cannot reach it.
- **Catch `RecursionError` from `json.loads` separately** — deep nesting raises it, not
  `JSONDecodeError`, and the two share no base beyond `Exception`.
- **Put a CONSECUTIVE-failure ceiling on undecodable frames** (here 3) — "a HUNG server is less
  diagnosable than a dead one".
- **Treat a closed pipe as how a session ENDS, not a failure** — catch around the WHOLE loop, since
  the read loop writes too; catch both `BrokenPipeError` and `ValueError`.
- **Yield whatever decoded from the read loop** — deciding what a frame IS belongs to the frame
  handler, the one place that knows a top-level array is a batch.
- **Take stdin/stdout as ARGUMENTS** so the whole handshake is testable without a subprocess — it is
  the part most likely to be subtly wrong and should run on every commit.
- **Keep slow, network-bound work OFF the MCP surface entirely** — every tool here is a local read at
  18–300ms; sync and enrollment are CLI commands. Consequence: **no progress reporting, no
  cancellation, no per-tool timeout policy anywhere in 3,131 lines.** (L0 — the cheapest answer to
  the whole long-running problem is not to have one.)

## F. Capability negotiation and versioning — the strongest material here

- **Echo the CLIENT's requested protocol version when you recognize it** — the client is the half
  that cannot adapt.
- **Keep the OLDEST revision in your supported set on purpose** — the fallback only rescues a client
  that can speak something NEWER than it asked for, so dropping the oldest means counter-offering a
  revision a pinned client cannot speak, and the spec has such a client DISCONNECT rather than
  downgrade.
- **Do NOT advertise the SDK's `LATEST_PROTOCOL_VERSION`** — the registry is era-partitioned:
  `2026-07-28` uses a stateless per-request envelope reached by a `server/discover` probe, its
  `InitializeRequestParams` reads "Removed in protocol 2026-07-28", and its `ListToolsResult`
  requires `ttlMs`/`cacheScope`. Advertise the newest revision your HANDSHAKE can negotiate.
- **Hand-copy protocol constants into your runtime, add the typed SDK as a TEST-ONLY dependency, and
  assert the copies match** — no pydantic in the runtime tree, and a lock-file bump is how a protocol
  change reaches your code. Four defects had lived in the hand-typed copies.
- **Declare only capabilities you serve, including sub-flags** — a client that asked to be told about
  a change would wait forever on a promise never made.
- **Never hang a custom key off `serverInfo`** — `Implementation` declares a fixed field set and the
  SDK's wire base leaves pydantic `extra="ignore"` in force, so an undeclared key is **discarded
  silently**. Use `_meta` with a namespaced key (`io.modelcontextprotocol/*` is reserved).
- **`readOnlyHint` is a DECLARATION, not an enforcement** — the SDK's own caveat is that clients
  should never make tool-use decisions on annotations from untrusted servers. Keep enforcement in
  the resource (a read-only handle every tool opens through).
- **Set `destructiveHint` and `openWorldHint` even where the spec says they are meaningless** — the
  default a client would otherwise assume for `destructiveHint` is `true`.

## G. Context budget and result shaping

- **Serialize the text copy as COMPACT JSON** (`separators=(",", ":")`) — most clients put BOTH
  `content` and `structuredContent` into the model's context, and pretty-printing cost **~27% more**
  on a full page of rows.
- **Send BOTH content forms** — a client that only renders text gets an empty result otherwise.
- **Write the ONE description of a shared envelope block once and share it** — the reference resource
  renders a key once, so two tools describing it two ways make one description silently hide the
  other.
- **Do NOT share a note across tools whose REMEDY differs** — a paging note on a tool that issues no
  cursor sends an agent looking for a field that is never there.
- **Publish a per-tool `outputSchema` that REQUIRES a conditional key where the tool carries it and
  FORBIDS it where it does not** — one schema with both merely optional publishes the opposite of
  "absence is information".
- **Tell the agent in the handshake that row text is THIRD-PARTY** — a counterparty chose the
  characters in `description`/`merchant`, so quote them and never follow an instruction, link or
  credential request found in one.

## H. Build identity — solved a real workflow failure

- **Ride the running BUILD in every response and in the handshake `_meta`, from ONE capture.** A
  stdio server is a subprocess launched at connect time, so it serves whatever existed at connect.
  Round 4 was declared PARTIAL because the tester connected at 10:51 and the fix merged at 11:32;
  round 4a was "blocked twice by the stale-build problem" and ran at the third attempt only after
  the build field made the precondition checkable in one call.
- **Report `commit: null` when unidentifiable and make `dirty` null too — never `false`**, which is
  a positive claim the tree was clean.
- **Capture at IMPORT, not per request** — two readings of one process are one fact.
- **Fingerprint the running build against a RECORDED STRING from a prior round** as an independent
  second check (`limit:9999` → the new ceiling), used to REFUSE half a brief rather than produce a
  pass that meant nothing.
- **A consumer CANNOT force a stdio server to re-read its build** — restarting is an operator action
  with no consumer-side control, so build the precondition into the surface, not the test procedure.

## I. Client integration

- **Use ABSOLUTE paths for command and working directory in client config** — a GUI client launches
  servers with a minimal PATH excluding Homebrew and `~/.local/bin`, so a bare `"uv"` fails before
  the server prints anything and the client reports a server that "did not start" with nothing in
  your logs, because nothing of your product ran.
- **The client does NOT inherit your shell exports** — every env var must be repeated in `env`.
- **Name config KEYS distinctly per environment** — measured: Claude Code lists the key you
  registered and never shows the title, so a title carrying the environment is not sufficient.
- **A flag selects the environment; the ENVELOPE confesses it** — carry `environment` on every
  response, because sandbox and real-money servers return identically-shaped answers and the failure
  a flag cannot prevent is not picking wrong but not KNOWING you did.
- **Make PRODUCTION the unsuffixed default filename** so syncing fixture data into the real store
  takes an explicit override rather than a forgotten flag.
- **Let a read-only server start under a defaulted environment, but make every WRITE refuse** — a
  write on a defaulted environment lands wherever the fallback names, and for a secret it cannot be
  undone.

## J. Acceptance method (L0 — a distinct and valuable seam)

- **Run acceptance BLACK-BOX with no source access, and have the tester fix nothing.**
- **Record what the fixture CANNOT test as "untested, not passing" and spend no effort reaching it**
  — "silence is not a pass", carried verbatim across rounds.
- **Discount a clean acceptance result by the fixture's ABSURDITY.** Verdict, verbatim: *"the only
  reason three rounds of testing caught any of them is that the sandbox fixture was absurd enough to
  trip me. Real data will not be absurd. Every number will look like it could be true."*
- **Two tools reconciling EXACTLY proves only internal consistency** — agreement to the unit across
  8 categories says nothing about whether either matches the bank.
- **Enumerate the SANDBOX PROPERTIES production breaks, by name** — one connection, one sync with no
  incremental round (so the cursor boundary where duplicates live is never exercised), balances that
  cannot be reconciled, and 20×-too-small scale. The truncation finding was re-graded from "ship" to
  "block" purely on "sandbox is 20× too small to have shown it".
- **Rank findings by HOW BADLY THEY WOULD MISLEAD THE END USER**, not technical severity — that
  promoted "'Am I paying down debt?' gets a precise, plausible, entirely wrong answer" above every
  crash-class issue.
- **Write the acceptance brief from the RECORD, not from the fix's framing** — one brief told a
  tester that date-windowed questions "failed outright in round 3" when round 3 said the opposite.
- **A black-box tester's MECHANISM hypothesis can be correct in method and wrong in conclusion** —
  a proposed uniform negation was real, deliberate and documented, and removing it would have been
  wrong by twice the amount on every spend row.

## Doc-vs-code findings

1. **Resource inventory drift (live).** The API contract declares two MCP resources; the tree serves
   three. The contract's own norm names exactly this: *"A forgotten tool is a live risk on a surface
   that grows one tool at a time. The declared inventory above is the control."* Uncommitted WIP, so
   it may close before commit — but a new test reads the contract, so the gap is between two files
   both under edit.
2. `mcp-production-readiness.md` says "four tools"; the surface has 8. Carries a superseded banner,
   so disclosed staleness rather than silent drift.
