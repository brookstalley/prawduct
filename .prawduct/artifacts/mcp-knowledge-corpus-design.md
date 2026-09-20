# MCP Knowledge Corpus — Design Notes

**Status:** discovery, in progress. Design decisions below are settled with the owner in
conversation on 2026-09-17; mining of source repos was dispatched the same day and had not
reported when this was written.
**Owner:** brooks@tangentry.com
**Parents:** `.prawduct/artifacts/data-model.md` § Direction, `.prawduct/artifacts/architecture.md`
§ Direction, `documentation/governance-artifact-lifecycle-requirements.md`

---

## 1. Goal

Prawduct becomes the single home for hard-won MCP server engineering knowledge, so that products
(cordyceps, hallucinote, bankmachine, discodon, and future ones) stop independently re-deriving the
same lessons.

Owner's **absolutes**:

1. Prawduct is the source of truth for collected MCP best-practice knowledge.
2. Prawduct *uses* that knowledge when consumers design, refine, test, plan and review MCP work.
3. The structure accommodates ongoing learning and changes to MCP itself.

Owner's **desirables**:

1. A centralization that can be handed to someone whole — "here is everything I know about writing
   great MCP servers."
2. A path to relocate sibling-repo research here, so improvement happens once.
3. A way to periodically revalidate the collected knowledge.

## 2. Constraints discovered

### 2.1 Derived views are a settled question — do not reopen

`data-model.md` § Direction: *derived views are disposable and never authoritative — no gate reads
a view to reach a verdict.* `regen-views` is deprecated and inert.

The retirement rationale (`documentation/governance-artifact-lifecycle-requirements.md`) is the
part that matters here: views were removed because **nothing they produced was read to reach a
decision**, at a cost of ~4,800 lines of machinery — and because **14 of 220 learnings encoded
nothing but the view format's own rules**. That last figure is the warning. Any mechanism that
generates duplicate rule text into other files rebuilds this.

**Decision: pointers, not copies.** The corpus has one authored home. Selection and routing may
reference it; nothing regenerates it. A human-handoff export (desirable 1) is generated at send
time and never committed, which keeps it disposable and unread-by-any-gate, so it conforms.

### 2.2 The routing mechanism that exists

`.claude/rules/learnings/<area>.md` carries `paths:` globs. The harness auto-loads an area file when
a matching path is read; the Critic reads the same set via `prawduct-hook learnings-files
--for-diff` (`plugin/lib/learnings_files.py`, `plugin/agents/critic-reviewer.md`,
`plugin/lib/gates.py`). One authored file, two automatic consumers, no reliance on recall.

Routing is **file-granular**. There is no section-level load.

### 2.3 The gap that makes this a framework feature, not a document

`.claude/rules/learnings/` is **product-owned and per-repo**; `init-product` scaffolds only a starter
`core.md` into a consumer repo. Everything the plugin ships (`docs/`, `methodology/`, `skills/`,
`templates/`, `agents/`) is **pull-based** — someone must invoke or open it.

So absolute 2 is not satisfiable with today's mechanisms. It requires a new capability:
**plugin-shipped, path-routed knowledge packs**. MCP would be pack #1; the capability is reusable
beyond MCP. (A mining agent was asked to confirm this absence with evidence; treat it as unverified
until that report lands.)

## 3. Structure

### 3.1 Layers — the subject axis, ordered by half-life

| Layer | Contents | Half-life |
|---|---|---|
| **L0 applicability** | whether to build a server at all; what to plumb MCP into | stable |
| **L1 agent-interface design** | tool naming/granularity, intent-shaped tools, teaching errors, result shaping, context budget | years; survives MCP itself |
| **L2 protocol semantics** | tools vs resources vs prompts, schemas, capability negotiation, versioning | spec revisions |
| **L3 transport & operations** | stdio/HTTP/SSE, timeouts, concurrency, lifecycle, secrets | transport churn |
| **L4 client/host integration** | per-client quirks, config, discovery, install UX | months; most volatile |

The layering exists so that a transport change cannot invalidate interface-paradigm knowledge, and
vice versa. Owner's test: "when MCP moves to Jabber or SOAP, L1 must be unaffected."

L0 was added after testing the taxonomy against a real rule ("plumb MCP into applications so agents
developing them can exercise capabilities") that fit nowhere in L1–L4.

### 3.2 Layer is a tag, not the filing key — fire-site is

Tested against nine real owner rules: **only one was single-layer.** The rest have their cause in
one layer and their remedy in another (a transport fact forcing a tool shape; a client caching
behavior forcing a version-reporting surface). Filing by cause hides a rule from the only person who
can act on it.

Because routing is `paths:`-based, the filing question is *"what files is someone editing when this
must fire?"* — not *"what is this about?"* A rule may have two fire-sites (design-time and
debug-time) without being copied.

### 3.3 Kind — the shape axis

`pattern` · `decision-point` · `diagnostic` · `constraint` · `permission` (myth-buster) · `stance`.

Kind determines phrasing and consumption moment. Diagnostics are phrased symptom-first so they are
findable while debugging — reusing prawduct's existing `Tell:` convention from
`.claude/rules/learnings/core.md`, which already encodes the observable signal and is read natively
by the Critic's cross-check.

### 3.4 Stances are separate from rules

A stance is a generative heuristic with no fire-site of its own — e.g. *design for the agent's
observability, not the human's*; *intent over mechanism*. Stances produce rules at multiple
fire-sites and belong in a short preamble, kept strictly separate from the rule corpus, as
principles are kept separate from learnings.

**A third shape was added 2026-09-18 — see §11.2.** An **ADJUDICATION** records a question the
corpus has not settled, where filing it as a rule would force a verdict that does not exist. So the
record shapes are rules, stances, and adjudications; the kind axis in §3.3 applies to rules only.

Validated: *intent over mechanism* generated both the tool-surface rule (R1) and the collateral rule
(R9), at two different fire-sites.

### 3.5 Dated facts are cited, not inlined

Rules routinely combine a stable shape with a volatile constant ("long operations return a handle" +
"the threshold is ~60s"; "prefer the transport with broadest client support" + "that's stdio").
Inlining the constant means revalidation re-litigates the stable half.

Ecosystem/client/spec constants live in one dated facts surface that rules cite. Revalidation
(absolute 3, desirable 3) then means re-checking a short facts list rather than re-reading the
corpus, and can ride prawduct's existing norm-lifecycle sweep and advisory machinery rather than
introducing a second clock (`architecture.md` § Direction: *never re-implements*).

### 3.6 Two relations the corpus must express

- **Tension pairs.** Rules that give opposite advice when read separately need their reconciliation
  stated, not just both filed. Example below: R3 vs R6.
- **Precondition chains.** A rule's remedy may be available only given another rule's decision.
  Example: R8's remedy requires R4's same-device deployment. Without this, the corpus hands remote
  deployments un-followable advice.

## 4. Packaging — DISCHARGED by §10.1 (directory of layer files); the reasoning below is retained

One file with headings, or a directory of layer files. **Deferred pending a size measurement**,
because the harness auto-load is file-granular and whole-file: one file is fine at ~30KB and a
context-budget problem at ~150KB (`.claude/rules/learnings/core.md` is ~100KB today; re-derive with
`wc -c .claude/rules/learnings/*.md`).

The outline is identical either way — layers are top-level headings or filenames — so splitting
later is mechanical and lossless. Addressing is **by reference** (a skill or review perspective
cites a section), never **by extraction** (a parser slicing the file), unless a measurement forces
otherwise: a slicer is a parser over hand-authored markdown whose format rules become their own
learnings, which is the failure recorded in §2.1.

If sections are ever cited by heading, those headings become machine-read identifiers and something
must verify the anchors resolve — a reworded heading otherwise degrades to a silent no-op
(`core.md`: *naming a thing freely writes into a machine-read field*).

## 5. Seed rules

Nine rules stated by the owner in conversation, 2026-09-17. **Evidence tier: owner-stated
experience** — real, but not independently verified against code or measurement; the mining pass
should corroborate, sharpen or contradict each. Numbering is local to this artifact and carries no
meaning outside it.

| # | Rule | Fires when | Layer (cause → remedy) | Kind |
|---|---|---|---|---|
| R1 | Minimize tool count; group capabilities under an `action` parameter (`gh_canvas(action="clear")` over `gh_canvas_clear()`) — separates verb from object and enables a contextual `action="help"` | designing the tool surface | L1 | pattern |
| R2 | Anything that could exceed ~60s returns quickly with an async handle for progress | shaping a handler | L3/L4 → L1 | pattern |
| R3 | Clients cache server capabilities, so updates are not immediately visible; expose version from both server and client so the model can detect a mismatch | writing version reporting; **also** debugging "my change isn't visible" | L4 → L2 | diagnostic |
| R4 | Prefer stdio for same-device servers (broadest client support); warn when moving to HTTP/network that compatibility narrows | choosing transport, at plan time | L4 → L3 | decision-point |
| R5 | A wedged host and a long-running action are hard to tell apart — emit progress, or failing that a sign of life; design for what the consuming agent will see | shaping a long-running handler | L4 → L1 | pattern |
| R6 | Agents hold no state across versions — refactor tools for efficiency rather than fearing breakage, while respecting users and doc accuracy | contemplating a breaking change | L4 → L1/L2 | permission |
| R7 | Plumb MCP into applications so agents developing them can exercise real capabilities — excellent at data/network layers, not for pixels | planning, before a server exists | **L0** | decision-point |
| R8 | **If** caller and server share access to the same storage, pass file paths rather than contents — MCP carries large binaries poorly over stdio *and* HTTP | designing a tool signature | L3 → L1 | optimization w/ precondition |
| R9 | Collateral describing a server should be intent-driven and must not assume tool names or params are immutable | authoring docs, skills, CLAUDE.md referencing a server | L1 (stance-derived) | constraint |

### Recorded reconciliations and dependencies

- **R3 ↔ R6 (tension).** Read separately these oppose. Reconciliation: refactor freely *across*
  sessions; the risk window is a live session holding a stale capability list, which is exactly what
  R3's version reporting exists to expose. R3 is R6's enabling condition, not its opponent.
- **R6 boundary.** Agents hold no state; their *configuration* does — CLAUDE.md, skills, saved
  prompts, memory, scripts naming tools. A rename breaks those silently (the agent calls a tool that
  no longer exists and improvises). R9 is the fix for the instructional half.
- **R9 exception.** Instructional collateral must be intent-driven; **authorization** collateral
  cannot be, because a permission grant must name what it grants (this repo's own
  `plugin/agents/critic-reviewer.md` carries a literal `tools:` list; MCP tools are granted by name,
  e.g. `mcp__<server>__<tool>`). A refactor's blast radius therefore shrinks to the permission layer
  rather than to zero — and that failure is silent, which is why it is worth naming.
- **R8 ← R4 (precondition).** R8's remedy requires the shared-storage condition, which holds for
  same-device subprocess servers and fails for daemons, containers with independent mounts, and
  anything remote. Where it fails, a client-named path is a privileged-access surface rather than a
  shared one — a different rule, not a caveat on this one.
- **R2 / R5 cluster.** Same fire-site, same cause; likely one rule with two facets.
- **R8 cost claim unresolved.** "More efficient" wants a number, and the dominant cost is likely
  *agent context* consumed by a large tool result rather than wire encoding. Unverified — flagged to
  the consumer-side mining pass, which was asked for the bridge's real size limits (§10.5).

### Candidate mechanization

R9 converts into a check: scan a repo's instructional collateral for literal MCP tool names,
exempting authorization surfaces. `core.md` holds that a rule requiring recall at the right moment is
its weakest form; rules that can become checks should.

## 6. Staging

Each stage stands alone if the next slips.

1. Mine and author the corpus + a skill to open it. Delivers desirable 1 immediately.
2. **Plugin-shipped path-routed knowledge packs.** The capability that satisfies absolute 2.
3. Critic review perspective for MCP surfaces, reading the same files.
4. Revalidation wiring + sibling intake.

**Sequencing constraint:** desirable 2 (relocating sibling research here) must not happen before
stage 2 exists. Today that knowledge fires locally in each sibling; removing it first makes four
repos worse to make one tidier, with no mechanism shipping it back.

## 7. Open questions

- ~~Packaging: one file or a directory (§4) — blocked on the size measurement from mining.~~
  **Discharged 2026-09-17 by §10.1: a directory of layer files, addressed by reference.**
- Is stage 2 in scope for this work, or a separate piece? Owner said in scope on 2026-09-17.
  **Now entangled with #343 (§12.4)** — stage 2 is that item's delivery mechanism generalized, so the
  two are built as one design or separated with a stated reason. Also open there: the three questions
  in §12.3.
- Whether the facts surface (§3.5) can ride the existing norm-lifecycle sweep unchanged, or needs
  its own probe.

---

## 8. Findings from the delivery-surface survey (2026-09-17)

### 8.1 BLOCKER — absolute 2 collides with a steady-state norm

`.prawduct/artifacts/architecture.md` § Direction, steady-state:

> The plugin writes nothing into a governed repo except its own `.prawduct/` state, the shared
> evidence store, and the files it must reconcile — `.gitignore`, `.claude/settings*.json`, and
> `CLAUDE.md`'s governance anchor — **never framework files.**

Combined with the confirmed absence of any plugin-side push channel, this forecloses shipping the
corpus as `.claude/rules/learnings/mcp.md` into a consumer repo. `paths:` routing is a **harness**
feature over repo-committed `.claude/rules/` only (`learnings_files.resolve()` roots at
`project_dir` and never consults `CLAUDE_PLUGIN_ROOT`). The one push channel is the SessionStart
digest: a single unrouted file under a hard 10,000-char harness limit with ~200 chars of practical
headroom — it cannot carry a corpus.

Re-derive the absence with: `grep -rn "additionalContext" plugin/` (one file: `hooks/digest.py`);
`find plugin -name "rules" -o -name "*.mdc"` (empty); `grep -rn "CLAUDE_PLUGIN_ROOT" plugin/`
(hook paths and root resolution only, no content loading).

**Three routes, for owner decision:**

- **(a) Pull-only.** Corpus ships under `plugin/`; a skill reads it on demand. Conforms fully, no
  ruling needed. Absolute 2 degrades to "when someone invokes it."
  **Corrected 2026-09-18 (§12.2): "degrades" is the wrong word.** #343's owner ruling of 2026-08-01
  decided that query-time reading from the plugin is the *correct* shape for framework knowledge,
  because a copy freezes at the adopting product's vintage. Route (a) is not a concession to a norm;
  it is the ruled-on answer. What (c) adds is *discoverability* at build time, not a better read.
- **(b) Critic-side routing.** A plugin-shipped review perspective consults the corpus when the diff
  is MCP-shaped. The Critic already computes its learnings read-set via `learnings-files
  --for-diff`. **No norm change**, and it fires automatically at review time.
- **(c) Minimal carve-out, requires an owner ruling.** The plugin scaffolds a small *product-owned*
  pointer file into `.claude/rules/learnings/` carrying `paths:` globs and a body that says "open
  the corpus at `<curated plugin path>`". Precedent: `scaffold_core()` already writes `core.md`
  (header only, never overwrites). The pointer is ~10 lines; framework content still stays in the
  plugin. This is the only route that reaches **build time** auto-load.

A governance change cannot supply its own authority — (c) needs the owner's ruling recorded
somewhere the amendment is not.

### 8.2 Prior art that must be reconciled, not re-derived

- **`documentation/prompt-management-requirements.md` §15** defers exactly this work by name: *"MCP
  is a Foreign API class with its own concerns… MCP-server review is a separate future concern."*
  There is no backlog item for MCP best practices.
- The same document is a **1,003-line design for this exact shape** — a framework-shipped catalog
  plus a pull-based filtering skill — that **shipped nothing**. Its decisions bind or must be
  overturned: D4 (checks adaptive, no fixed checklist), D7 (framework prescribes shape and
  guidelines, not vendor specifics), **D8 (ship comprehensive, filter by skill — pull, not push)**,
  D14 (`runtime-instruction` role kind, which is what an MCP server is), §9.3 (per-project extension
  at `.prawduct/<name>-local.md`, not by growing the framework catalog), Q6 (open: pin vs. latest).
- D8 independently reaches the same conclusion as 8.1's route (a). That convergence is evidence, not
  coincidence.

### 8.3 Packaging constraints

`tests/test_plugin_packaging.py`: `documentation/` is in `NOT_DISTRIBUTED_DIRS` and ships nowhere, so
the corpus must live under `plugin/`. `test_no_shipped_file_points_at_an_unshipped_plugin_root_path`
requires every reference in a shipped file to resolve inside the curated root. Plugin caches are
version-keyed and accumulate (~90 MB measured across versions), so corpus size carries a real
per-install cost.

Also binding: *never Python-specific* (`architecture.md`, in-transition, LNG-5W8R) — MCP servers are
TypeScript-first, so any language-keyed treatment must dispatch per file, and a language with no
rules is reported **unchecked**, never silently passed.

### 8.4 Early corroboration of the seed rules (cordyceps, 60 rules mined)

> **Two corrections from the 2026-09-18 re-mine of cordyceps** (`mcp-mining/cordyceps-server-structured.md`,
> 95 rules, all addressed at `develop` `f07eb797`):
> - **The 49% reduction is real and re-derivable — 1636 → 835 lines at commit `02b800d`, 49.0%.** The
>   "before" figure stated below as 1648 is wrong, and **the corpus has since grown back to 1361 at
>   HEAD, 63% of the way**. A one-off reduction is not a steady state, which changes what the number
>   is evidence *for*: the consolidation worked and nothing holds it.
> - **That reduction did not ship in v1.4.5**, whose change-log claims it. The commit landed 21s after
>   the release commit and is not an ancestor of the tag; it first shipped in v1.4.6. Owed back to
>   cordyceps as drift (`mcp-mining/drift-owed-upstream.md`).
>
> The re-mine also found the first pass had missed a whole layer: it captured liveness *detection*
> thoroughly and missed the *prevention* layer beneath it (the deferred host refresh that is the root
> of the incident the detection rules describe) — 27 new rules, 0 unaddressed.

- **R1 confirmed and bounded with numbers.** Cordyceps runs 7 tools / 100+ actions with a mandatory
  `action='help'`, measured at a **49% token reduction** on its docs. The cost is
  also measurable in its tree: `gh_canvas` declares **37** parameters and `rhino_render` **43**, all
  optional, in one `inputSchema`. The real saving is moving per-action detail out of `tools/list`
  into a runtime `help` call — which is exactly the owner's "the help action pays for the collapse."
- **R5 superseded by a stronger form.** Rather than progress on long calls only, cordyceps rides a
  compact **status block on every response**, injected at one choke point, so an agent never spends a
  call asking whether the host is alive — plus one probe answering from cache that never touches the
  host. Evidence: a read-only probe measured **~32 minutes of silence** during one solve; "a busy
  solver and a dead bridge were indistinguishable."
- **R8 independently rediscovered, precondition included.** Binaries return `{filePath, hint}`, never
  base64 — and cordyceps records the same boundary unprompted: *"sound for a localhost server and
  wrong for a remote one."* Two repos converging on both the rule and its precondition.
- **R2 refined.** Cordyceps deliberately does **not** use MCP progress notifications; it exposes a
  pollable progress reading plus a bounded wait returning `timedOut: true` with partial progress.
  Whether that choice is still right is a dated-fact question (§3.5).

---

## 9. RULING (knowledge-may-be-routed-into-a-consumer-repo), 2026-09-17

> **§13 (2026-09-18) rules on the route below: the pointer is approved as the STARTING shape**, with
> the owner's explicit reservation that it may not be sufficient. §13.1 shows the pointer this section
> describes is the *globbed* variant, which cannot reach L0's 34 rules by construction.
>
> **§12 (2026-09-18) found a parent ruling this section does not cite** — #343's owner ruling of
> 2026-08-01 already settled that a framework corpus is read at query time from the plugin, stays a
> distinct store, and is surfaced labelled by origin. The conclusion below **stands and is
> strengthened** by it; two of #343's three clauses are **unaddressed here** and are owed an owner
> answer before stage 2 is designed. Read §12 with this section.

**Owner ruled: yes to route (c)** — the plugin may scaffold a small product-owned pointer file into
a consumer's `.claude/rules/learnings/` so that plugin-shipped domain knowledge auto-loads at build
time. Confirmation is the owner's message in the 2026-09-17 session, recorded here rather than in
the norm it amends.

Owner's stated reasoning: *"Best practices for MCP are no different from best practices for testing
or anything else. That's the core value prawduct brings. We can't be shy about that. We won't write
a C# scaffold for an MCP server, but we'll build MCP expertise in, and critic and others will
leverage it."*

**The conclusion stands; one premise in its support does not, and the corrected warrant is
narrower.** The owner's argument included *"prawduct already writes `.prawduct/` and critic and
janitor and lots of other framework files into consuming repos."* That is **false for the current
architecture and true only of the retired pre-2.0 file-sync model** (engine removed in M4/v2.0.3).
Today `/prawduct:critic`, `/prawduct:janitor` and every other skill live in the version-keyed
plugin cache; a governed repo commits its own `.prawduct/` state plus a small install reference and
**no framework files** (`plugin/skills/onboard/SKILL.md`; `init_product._SCAFFOLD_DIRS` /
`_STATE_TEMPLATES`). `.prawduct/` is the product's own state — its backlog, change log and
decisions — not framework content.

Recording the false premise would set a precedent licensing framework-file writes generally, which
is not what was asked for and not what is needed.

**The accurate warrant, which is sufficient:**

1. The knowledge itself ships in the plugin, exactly as testing and review expertise already does.
   Nothing about the corpus is written into a consumer repo.
2. What is scaffolded is a **routing declaration** (~10 lines of `paths:` frontmatter plus a
   pointer), not framework content. The distinction the norm turns on — *framework code stays in
   the plugin, read-only from the repo's perspective* — is preserved.
3. **There is already precedent in exactly this directory.** `learnings_files.scaffold_core()`
   writes `.claude/rules/learnings/core.md` at `init-product`. Route (c) extends an accepted
   practice rather than opening a new class of write.
4. Route (b) — the Critic consulting the corpus — needs no amendment at all and delivers the
   owner's stated goal ("critic and others will leverage it") on its own. (c) buys **build-time**
   auto-load, which (b) cannot reach.

**Mechanism constraints for the build plan:**

- Never overwrite: the directory is the product's own authored corpus, and `scaffold_core` already
  establishes absence as the only trigger.
- A distinct filename, so it cannot collide with a product's own area file.
- Reaching **already-onboarded** repos requires a migrate/doctor refresh step, not a template edit
  (`core.md`: *a format's schema legend lives in `templates/` — an addition reaches onboarded repos
  only via a refresh step*).
- `record_lint` flags an area file whose globs match nothing tracked; a pointer in a repo with no
  MCP server would trip it. The globs, or that lint, need an answer.
- `architecture.md` § Direction needs the amendment recorded beneath its clause, citing this ruling.

---

## 10. Mining complete (2026-09-17) — measurement and synthesis questions

### 10.1 Size measurement settles the packaging question: DIRECTORY, not one file

**Measured 2026-09-17, on bytes rather than on a rule count.** The compressed captures were weighed
with `wc -cw` against `.claude/rules/learnings/core.md` (`wc -c .claude/rules/learnings/*.md`) —
the file whose size the advisories already complain about, and which the harness auto-loads
**whole**. Even compressed and unaddressed, the captures were within an order of magnitude of it.
**Run both commands rather than quoting a figure from this paragraph**: the set has since lost a
source (§10.5) and gained addressed rewrites, so every number once written here has moved.

That floor is firm in one direction only, and both directions point the same way: it is measured
*before* the prawduct rules (§8) are folded in, *before* each rule is expanded from a terse capture
bullet into the corpus form carrying its own evidence and provenance — and only dedup pulls the
other way. A one-file corpus lands in the same size class as the file whose size is already a
standing complaint.

Rule *counts* were deliberately not the basis for this, because at the time **no count of this
corpus reproduced**: each capture's headline disagreed with the command cited to re-derive it, and
one disagreed a third way. See `mcp-mining/README.md` § *The headline counts do not reproduce*,
which records those readings as the history they are. Fixing it needed a shared rule marker across
the captures before it needed a better estimator — which the structured rewrites supplied, and the
re-measurement below uses.

**Therefore: a directory of layer files, addressed by reference.** §4's deferral is discharged. The
outline is unchanged — layers become filenames instead of top-level headings — so nothing authored
against the one-file plan is lost. The single shippable artifact (desirable 1) is produced by
concatenating at send time, never committed.

L1 is the layer every capture returned most of, and will likely still be too large as one file; if
it needs splitting, split along the clusters the material produced rather than by a further
taxonomy. Re-measure at authoring time — no rule count here is trustworthy enough to size it now.

**Re-measured after the sources were addressed, and again after one was withdrawn (§10.5). The
ruling holds and its margin grew; the L1 question is answered.**

The corpus has a count that reproduces, because it has a marker every capture shares. **Run these
rather than quoting a total from this section** — every figure once written here went stale the day
a source was withdrawn, which is the defect this document spends §10.4 on:

    cd .prawduct/artifacts/mcp-mining
    grep -c '^\*\*RULE:\*\*' *-structured.md                   # rules per capture
    grep -ohE '^LAYER: L[0-4]' *-structured.md | sort | uniq -c   # layout-agnostic layer tally
    cat *-structured.md | wc -cw                                  # words / bytes
    grep -c 'PROVENANCE: UNADDRESSED' *-structured.md             # what is still unaddressed

Two consequences, neither of which depends on the exact figures:

- **The packaging ruling is safe by a far wider margin than it was made on.** §10.1 above decided
  "directory, not one file" by comparing *compressed, unaddressed* captures against `core.md`. The
  addressed captures are several times both, so the direction does not change and the one-file
  option is not merely inadvisable but absurd. Re-derive the ratio with the `wc` above against
  `wc -c .claude/rules/learnings/core.md`.
- **L1 splits.** §10.1 predicted it and deferred it; the layer tally answers it — L1 is by a wide
  margin the largest layer and too large for one file. Split along the clusters the material
  produced (wire-format, error-as-next-turn's-input, round-trip economics, teaching the gaps,
  correctness traps) rather than by a further taxonomy.

**These are capture bytes, not corpus bytes, and the distinction is load-bearing.** A capture
carries its full evidence quotation and provenance apparatus per rule; the authored corpus will be
terser and will dedup across sources. So the byte figure is an upper bound on the *input*, never a
prediction of the output. What it bounds firmly is the reading cost of authoring — the word count is
the material a corpus author must get through, and it is a planning number for stage 1 rather than a
size estimate for the artifact. **Take it from the command, not from this paragraph:** the figure
that stood here was ~46% high once a source was withdrawn, and a planning number that wrong is worse
than none.

### 10.2 The seed rules after contact with the evidence

- **R1 (minimize tools, use action params) — CONTESTED, and this is the corpus's biggest
  disagreement.** cordyceps did it and measured a 49% docs-token reduction, at a cost also visible in
  its tree (37 and 43 parameters in single schemas). hallucinote did it — *and its every
  consolidation number is borrowed from published benchmarks, with its own design doc's requirement
  for a baseline measurement never performed.* bankmachine **rejects the framing outright**: both
  "one tool per question" and "one tool with an action enum" share the false premise that a boundary
  tracks the *question*; draw it where the **answer shape** changes, which took 10 tools to 8 with no
  `outputSchema` loss. A consumer-side source supplied evidence for why width matters at all, and
  that evidence is **not available to this corpus** (§10.5), so R1 ships with its server-side positions
  only. **The corpus must state this as a live disagreement with the evidence on each side, not
  resolve it by majority.**
- **R2 (>60s → async handle) — QUALIFIED, hard.** MCP progress notifications are received but **do
  not reset or extend the tool-call timeout** (Claude Code #58687), and transport choice is not a
  lever (identical across stdio/HTTP+SSE/Streamable HTTP; HTTP/SSE imposes a 60s first-byte
  minimum). So the remedy is not "report progress" but start+poll with progress *inside* the status
  payload. cordyceps reached the same design independently without recording the reason.
- **R5 (sign of life) — SUPERSEDED BY A STRONGER FORM.** cordyceps rides a status block on *every*
  response so the agent never spends a call asking, plus one cached-only probe. Evidence: ~32 minutes
  of measured silence during one solve.
- **R8 (shared storage → paths) — CONFIRMED THREE TIMES INDEPENDENTLY**, precondition included, by
  cordyceps, hallucinote and bankmachine's absence of any binary path. Strongest-attested rule here.
- **R6 (refactor freely) — the precondition is now explicit.** hallucinote may skip back-compat
  entirely *because one installer deploys both halves and a handshake makes "old client meets new
  server" unreachable*. The converse case — what a client does with a schema it has already
  registered — was evidenced only by the withheld capture (§10.5), so R6's precondition is stated here
  without the consumer-side half that motivated it.

### 10.3 Cross-repo disagreements to adjudicate (the most valuable output)

> **Qualified by §11.3 (2026-09-18).** The list below is the right list; "disagreements" overstates
> what three of the four are. Read §11 before acting on this section: #1, #3 and #4 dissolve into a
> single rule with a stated precondition, #2 is a dated fact rather than an adjudication, and the
> corpus's one genuinely open disagreement is R1 in §10.2 above.

1. **Clamp vs refuse an out-of-range value.** bankmachine: *refuse and quote the ceiling, never
   clamp* — clamping makes a trimmed answer byte-identical to a complete one. hallucinote takes the
   other side: *clamp and say you clamped* — a bare refusal costs a round-trip the agent spends
   guessing. Candidate synthesis: refuse where silence would be indistinguishable from completeness
   (row/data reads); clamp-and-announce where the parameter is a resource budget (duration, wait) and
   every value is semantically valid. **A third position sat in the withheld capture and is not
   reproduced** (§10.5).
2. **Tool-count ceiling.** hallucinote cites Cursor 40 (silent drops) and Copilot 128, plus a 10–20
   selection-accuracy band. One dated-facts entry, not three rules. A directly-observed client cap
   was evidenced only by the withheld capture and is not reproduced (§10.5).
3. **Progress notifications.** cordyceps declined them without recording why; hallucinote verified
   they do not affect the timeout. A third source contributed to this item and is withheld (§10.5),
   so nothing from it is reproduced. What survives is that the two remaining positions compose.
4. **Rename policy.** hallucinote's design doc says never rename/always alias; its shipped policy
   says no aliases at all. Both are right under different preconditions, and the precondition is the
   rule.

### 10.4 Verification debt

Every citation in `mcp-mining/` is agent-reported. Before anything ships: re-derive each number and
path against its source repo, and re-anchor on symbols and headings rather than line numbers
(`core.md`: *a `file:line` you did not resolve yourself is a claim, not a citation*).

**Corrected 2026-09-18 — the debt was larger than this section described, and different in kind.
The following describes the state BEFORE the re-mine; it is kept because it is why the re-mine
happened.** At that point the compressed captures carried **no provenance at all** — zero
`PROVENANCE:` lines and a handful of distinct source paths each, across ~20KB of rules apiece,
while stating hard measured figures — and only one capture was addressed. Re-derive the current
state with the command in `mcp-mining/README.md`; **the structured captures that shipped are all
addressed**, and what remains unaddressed is countable with
`grep -c 'PROVENANCE: UNADDRESSED' *-structured.md`.

So for those sources it was not "re-check the citations" — there were none to re-check, and
*verifying* an unaddressed claim is re-mining with extra steps. Re-mines and a citation audit were
dispatched 2026-09-18; the dispatch record is in that README.

**This makes the debt a precondition rather than hygiene.** Desirable 3 is periodic revalidation,
and a claim that cannot be located cannot be revalidated — so an unaddressed corpus forecloses the
absolute that keeps it true as MCP moves. It also absorbs the marker-unification blocker: the target
marker is this document's own §3 schema, so addressing a capture and unifying its marker are one
pass. Two miners
already found doc-vs-code drift in their own repos, which is worth reporting back to cordyceps
(a testing guide that would make a tester file a false regression; an architecture doc describing an
SSE server that does not exist) and hallucinote (two surfaces telling agents a call "always works"
that a blocked host times out at 30s).

**Quotation half PAID 2026-09-18 for the two published re-mined captures.** The debt had two
halves — the *address* and the *quotation* — and only the first was ever named here. cordyceps and
bankmachine have now had their quoted evidence searched against their source trees at their declared
SHAs, and **no fabrication was found in the drift-signature bucket**, which was chased by hand in
full. One capture was corrected (a shortened placeholder inside a quoted shell command). **Counts,
per-source resolve rates, verdicts, method and what is still owed all live in
`mcp-mining/capture-quotation-verification.md`** — deliberately not restated here, because a copy of
them in this section went stale within a day of being written (it is one home per fact, and this is
the section that broke the rule). Re-derive with `tools/verify-capture-quotations.py`, committed so
the numbers are falsifiable rather than transcribed.

Two consequences for authoring rather than for the debt ledger:

- **A miss is not drift, and the resolve rate must not be read as a drift rate.** The clear majority
  of misses are text that is not in the source tree at all, which for a plain-quoted span is
  usually the capture author's own words rather than a corrupted quotation.
- **A schema gap, which is the durable finding.** `italic-quote` fragments resolve markedly higher
  than `plain-quote` ones, and the plain-quote rate is near-identical across three
  independently-written captures — that consistency is the signal. cordyceps uses
  `*"…"*` as a verbatim-quotation convention; the other two use plain quotes for **both** source
  quotations and their own emphasis. So §3's schema specifies the `EVIDENCE:` field but not **how a
  quotation inside it declares itself as a claim of verbatim source text** — and without that
  marker, two of three captures are not auditable at the fragment level by any instrument. If the
  corpus is to carry evidence that revalidation (desirable 3) can re-check, the schema owes that
  distinction.

Still owed on the quotation half: the fragments in the shallower miss buckets, the `code-span` class,
and hallucinote's own 19 known-wrong quotations, which its audit reported without editing.

### 10.5 discodon's capture is withdrawn from this repository (2026-09-18)

The fourth capture — `discodon`, a client/bridge consumer and the only consumer-side source in the
corpus — was mined and audited in the same pass and is **not published here.** Neither are its
findings: §10.2 and §10.3 name where its evidence would have sat and do not reproduce it.

**Why.** This repository is public. `discodon` is a **private repository owned by a different
account**, and the capture was a verbatim record of its internals — source, docstrings, internal
paths and tracker ids — together with a drift section the capture itself described as bug reports
owed back to that repo, none of which had been reported. Publishing it would have disclosed a third
party's private code, including unfixed defects, through a governance artifact. Caught by a PR
reviewer before the branch was ever pushed.

**Why the source IS named here, and the findings are not.** An earlier draft of this section
withheld the name as well. That was incoherent: this repository already names `discodon` across
dozens of tracked files, and the public backlog item that tracks this corpus names it too, so
anonymity was never available and could not be what protects anyone. What is actually withheld is
the thing that was never public — **its code and the defects found in it.** Naming a repository
whose existence is already public costs nothing; reproducing a private repository's internals is the
whole exposure, and no amount of not saying its name would have changed that.

**What it costs the corpus, stated rather than glossed.** It was the *only* consumer-side source —
the only evidence of how an arbitrary client actually treats a server's declared surface — so the
loss is not proportional to its rule count:

- §10.2's **R1** loses the consumer-side reason tool-surface width matters at all, and ships with
  its server-side positions only.
- §10.2's **R6** keeps its precondition and loses the converse case that motivated it.
- §10.3 item 1 (**clamp vs refuse**) loses one side's evidence and is **BLOCKED**, not awaiting.
- §10.3 items 2 and 3 lose a directly-observed client cap and a third position respectively.
- §11.3's triage stands as reasoning, but several rows now rest on evidence a reader of this
  repository cannot check.

**What is NOT lost.** The work exists; it is unpublishable from here, not wrong. Its drift items are
still owed to their owner and are **not** discharged by being removed from this repo
(`mcp-mining/drift-owed-upstream.md`).

**The governance lesson, because it generalises past this corpus.** The build plan's `governed_by`
disposition for the security-model norm *a product's content leaves its repo only through a pinned,
owner-approved surface* read **"inapplicable because nothing leaves this repo."** That was true of
the sibling working trees and false of the direction that mattered: mining brings a third party's
content **into** a public repo. An exposure boundary does not care which way content crosses it, and
a disposition written from the norm's example rather than its predicate will read the wrong
direction as settled. **Any future mining pass asks, before the first read: is the source repo
public, and is it ours?**

---

## 11. How a disagreement is filed (2026-09-18)

§10.3 lists four "cross-repo disagreements to adjudicate" and calls them the most valuable output of
the mining pass. That is right, and it leaves a structural question unanswered: **the corpus has no
shape to put them in.** §3.4 separates stances from rules; §3.6 names tension pairs and precondition
chains. A cross-repo disagreement is none of those.

- A **tension pair** is two rules *in the corpus* whose reconciliation is known and stated.
- A **cross-repo disagreement** is two repos' shipped *practices* in conflict, where the corpus may
  not yet know which is right — and §10.2's owner-facing commitment for R1 is explicitly *state it
  as a live disagreement with the evidence on each side, not resolved by majority.*

An unresolved disagreement therefore **cannot be filed as a rule**, because a rule is a single
imperative and filing one would force a verdict the corpus does not have. That is the whole failure
mode the commitment exists to prevent.

### 11.1 Three outcomes, and the filing decision is which one applies

- **(a) DISSOLVED.** The disagreement was never one: it is a single rule whose precondition nobody
  had stated. Both repos were right locally. Files as an ordinary rule, with the precondition
  promoted into the rule sentence rather than trailing it as a caveat (`core.md`: *a spec that deltas
  a parent reads complete*; a caveat reads as optional, a precondition does not).
- **(b) TENSION PAIR.** Both rules are real, both stay, and the reconciliation is stated. §3.6's
  existing shape.
- **(c) OPEN.** No coherent answer is in evidence. Files as a fourth record shape — an
  **ADJUDICATION** — beside rules and stances.

### 11.2 The ADJUDICATION shape

An open adjudication still has to **fire at the fire-site**: someone designing a clamp policy needs
to know the question is contested *while they design it*, not later. So it carries the same routing
apparatus a rule does — `paths:` reach and a layer tag — and adds the slots a rule has no room for:

```
**ADJUDICATION:** the question, stated so that both answers are visibly answers to it.
FIRE-SITE: where someone meets this question.
LAYER: L0–L4
POSITION A: <repo> does X — <evidence, addressed>
POSITION B: <repo> does Y — <evidence, addressed>
PRECONDITION IF DISSOLVABLE: the condition under which each is right, or "none found".
VERDICT: dissolved → <rule> | tension-pair | OPEN
WHAT WOULD SETTLE IT: the instrument, not an opinion.
```

`WHAT WOULD SETTLE IT` is the field that keeps this honest and makes revalidation (desirable 3)
mechanical: an adjudication with no named instrument is an opinion wearing a schema, and one with an
instrument becomes a check somebody can run later (`core.md`: *a rule you must recall at the right
moment is its weakest form*).

### 11.3 Triage of the four — and most of them are not disagreements

Applying 11.1 to §10.3's list, reading only what §10.3 itself already states:

| # | Question | Outcome implied by §10.3's own words | Verdict slot |
|---|---|---|---|
| 1 | Clamp vs refuse an out-of-range value | **(a)** — §10.3 supplies the candidate precondition itself: refuse where silence would be indistinguishable from completeness; clamp-and-announce where the parameter is a resource budget | **BLOCKED, not awaiting** — one side's evidence sat in the withheld capture (§10.5), so this adjudication cannot be settled from what this repository holds |
| 2 | Tool-count ceiling (20 / 40 / 128 / a 10–20 band) | **Not an adjudication at all.** §10.3: *"One dated-facts entry, not three rules."* These are client constants, which §3.5 already routes to the dated-facts surface | **awaiting** both audits for the real numbers; the filing decision needs nothing further |
| 3 | Progress notifications | **(a)** — §10.3: *"One coherent answer exists that no single repo held."* That is a dissolution by definition | **narrowed 2026-09-18** — hallucinote's timeout fact RESOLVED against its tree; a third source's contribution is withheld (§10.5). Still awaiting whether cordyceps recorded a reason |
| 4 | Rename policy | **(a)** — §10.3: *"Both are right under different preconditions, and the precondition is the rule"* | **awaiting** the hallucinote audit of design-doc-vs-shipped-policy |

**So §10.3's framing overstates the disagreement.** Three of its four dissolve into one rule with a
precondition, and the fourth is a dated fact. That is not a downgrade of §10.3's value — a
dissolution is the *most* valuable outcome, because it produces a rule no single repo could have
written. It does mean the corpus's **one genuinely open disagreement lives in §10.2, not §10.3:**

> **R1 — the shape of the tool surface.** cordyceps consolidated and measured a 49% docs-token
> reduction; hallucinote consolidated on borrowed benchmarks with its own required baseline
> measurement never performed; bankmachine **rejects the framing outright** — both "one tool per
> question" and "one tool with an action enum" share the false premise that a boundary tracks the
> *question*, where it should be drawn where the **answer shape** changes. The consumer-side reason
> width matters at all was evidenced only by the withheld capture (§10.5).

That is the corpus's flagship ADJUDICATION, and §10.2 already commits to filing it as one. Note the
asymmetry that makes it genuinely open rather than merely contested: of the three positions, **one is
measured, one is borrowed, and one is a reframing** — so a majority here would be counting
evidence tiers as though they were equal.

### 11.4 What is deliberately not settled here

Every `VERDICT` above says *awaiting*, because three of the four rest on citations under audit as of
2026-09-18 (`mcp-mining/README.md` § *Re-mining in flight*). Writing verdicts from the compressed
captures would derive a durable record from unaddressed claims, which is the defect §10.4 exists to
prevent. **The structure is settled; the verdicts are not, and the distinction is the point** —
`core.md`: *a filed item's stated mechanism is a hypothesis, not a finding.*

---

## 12. §9's ruling has a parent ruling it never cites — OWNER DECISION NEEDED

Found 2026-09-18 while filing this work as a backlog item (#826). Searching the *mechanism* rather
than the subject surfaced **#343 `learnings: ship a framework corpus products read at query time`**,
open at `stage: design`, carrying an **owner ruling of 2026-08-01** on exactly the question §8.1 and
§9 treated as needing a fresh one.

Read from the issue directly, not from a report about it.

### 12.1 What #343 already ruled

> *"Hoist at onboard is clearly wrong. Learnings should be a corpus that gets updated and which
> stays distinct from per-project learnings so they can update."*

Three things decided:

- **(a) The framework-shipped corpus is READ AT QUERY TIME from the plugin — never copied into the
  product at onboard.** A copy freezes at that product's adoption date, so every product runs a
  different vintage and none ever gets a correction.
- **(b) It stays a DISTINCT store** — the reader presents both together; the *stores* stay separate.
  "Design against the store boundary, not the reader's presentation."
- **(c) Both are surfaced LABELLED BY ORIGIN**, so a reader can always tell a framework rule from a
  local one.

And the asymmetry that reconciles it with the norms ruling MET-8K4R: **norms are ratifiable, so a
copy is the point; learnings are knowledge, so a copy is pure staleness.**

### 12.2 This strengthens §9 rather than overturning it — but §9's framing was wrong in one place

§9's conclusion survives intact: route (c) scaffolds a **pointer**, not corpus content, so nothing
prohibited by (a) happens. And 12.1's asymmetry is a *better warrant than the one §9 built*: MCP
engineering knowledge is **knowledge**, not a ratifiable norm, so it must not be copied — which is
precisely why pointer-not-copy is the right shape. §9 reached that by analogy to `scaffold_core()`;
#343 reaches it from the principle.

**What §9 got wrong:** it presented route (a) as a concession — *"Conforms fully… Absolute 2 degrades
to 'when someone invokes it'."* #343 ruled query-time reading is **correct**, not a degradation. The
`core.md` rule about deriving an answer without its constraints attached fires here exactly as
written: the ruling existed, in this repo, six weeks earlier, and §9's survey did not find it because
it searched the subject (MCP, knowledge packs) and not the mechanism (a plugin-shipped corpus).

### 12.3 The constraint §9 does not answer — this is the owner's call

**#343's ruling (b) and (c) are not addressed by §9 at all.** Route (c) scaffolds a framework-authored
pointer file *into* `.claude/rules/learnings/` — which is the product's own learnings store. So:

1. ~~**Does a framework-scaffolded pointer inside the product's own learnings directory respect the
   store boundary (b) requires?**~~ **ANSWERED 2026-09-18 — see §13.** Owner ruled yes, with the
   explicit reservation that it may not be sufficient. §13.1 shows why that reservation is
   well-founded: the pointer §9 describes cannot reach L0's 34 rules by construction.
2. **How is the pointer labelled by origin (c)?** §9's mechanism constraints require "a distinct
   filename, so it cannot collide with a product's own area file" — that is collision-avoidance, not
   origin-labelling. They are different requirements and only one is currently specified.
3. **§9 buys build-time auto-load; #343 ruled the corpus is read at query time.** Not a
   contradiction — the pointer is not the corpus, and what auto-loads is ten lines telling the agent
   where to look. But the owner should confirm build-time auto-load of a *pointer* is what was
   intended, given the corpus itself was ruled query-time.

**A governance change cannot supply its own authority, and this is a ruling amending the scope of an
earlier ruling. It is recorded here and owed an answer before stage 2 is designed, not resolved by
this artifact.** — *Question 1 answered 2026-09-18 (§13); questions 2 and 3 still owed.*

### 12.4 The convergence worth taking

#343's own closing says: *"If the owner is content to build a hand-authored corpus first and defer
the mechanical-promotion half, this item is immediately `ready` — one word moves it."* Its open fork
is a hand-authored corpus versus a rendered derived view.

**This work already takes that fork, and for an independently-reached reason** — §2.1 rules derived
views out entirely (`regen-views` deprecated and inert; 14 of 220 learnings once encoded nothing but
the view format's own rules). So the MCP corpus *is* the hand-authored path #343 says would move it
to `ready`, and stage 2's "plugin-shipped path-routed knowledge packs" is #343's delivery mechanism
generalized beyond learnings. **Stage 2 should reconcile with #343's ruling rather than re-answer
it**, and the two items should be built as one design or explicitly separated with a stated reason.

---

## 13. RULING (the-pointer-is-the-starting-shape), 2026-09-18

**Owner ruled on §12.3 question 1: yes, the pointer is good** — a framework-scaffolded pointer file
inside a consumer's `.claude/rules/learnings/` respects the store boundary #343's ruling (b)
requires, because it carries a routing declaration and no framework content.

**The ruling carries an explicit reservation, and the reservation is part of it, not a hedge:**
*"I am not sure it's sufficient but let's start there."*

So this is a decision to **begin** with the pointer, taken in the open expectation that it may not
reach far enough. Recording it without the reservation would convert a provisional start into a
settled answer, which is the shape a later reader acts on.

**Questions 2 and 3 of §12.3 are NOT answered by this ruling** — how the pointer is labelled by
origin, and whether build-time auto-load of a pointer is intended given the corpus itself was ruled
query-time. They stay open.

### 13.1 The reservation is well-founded, and the mechanism says exactly why

Verified against `plugin/lib/learnings_files.py` rather than against §2.2's summary of it:

> *"`core.md` carries no `paths:` frontmatter and is in context from launch; every `<area>.md`
> declares `paths:` globs and arrives when Claude **reads a file those globs match**."*

And, decisively, from `parse_frontmatter`'s contract:

> *"It is empty for a file with no frontmatter and for one whose frontmatter declares no `paths:`;
> **both cases mean the same thing to the harness, which loads such a file unconditionally**."*

**Always-loaded is a property of an absent `paths:` key, not of the filename `core.md`.** So route (c)
is not one mechanism. It is two, and §9 described only the first:

| Shape | Fires when | Reaches | Costs |
|---|---|---|---|
| **(c-globbed)** — pointer with `paths:` | someone reads a file matching the globs | build-time work inside an existing MCP server | nothing when it does not match |
| **(c-always)** — pointer with no `paths:` | every session, unconditionally | design-time, including L0 | a fixed ~10 lines in **every** governed repo forever, MCP or not |

**The gap is specific and countable.** L0 is *"whether to build a server at all; what to plumb MCP
into"* — **34 rules** in the addressed corpus. Those fire at a moment when there is no server file in
the repo to match a glob against, so **(c-globbed) cannot reach them, by construction rather than by
tuning.** A second, softer instance: §9's own mechanism constraints already note that `record_lint`
flags an area file whose globs match nothing tracked, so a globbed pointer in a repo with no MCP
server trips a lint — the same fact seen from the other side.

### 13.2 The honest coverage map — no single route covers it

Route (b) from §8.1 (the Critic consulting the corpus when the diff is MCP-shaped) needs **no
amendment at all** and was never in competition with (c); it covers a third moment.

| Moment | Route that reaches it |
|---|---|
| **Design-time / L0** — before any server file exists | **(c-always)**, or a skill the user invokes |
| **Build-time** — editing an existing server's files | **(c-globbed)** |
| **Review-time** — the diff is MCP-shaped | **(b)**, already conforming |

They compose rather than compete, and that is the sufficiency answer in one line: **the pointer as
§9 describes it is (c-globbed), which covers the middle row only.** Starting there is a coherent
decision — it is the cheapest of the three and the one the ruling now authorises — and what makes it
provisional is that the corpus's most reusable layer is in the row it cannot reach.

### 13.3 What this does not decide

Stage 2 is not designed here. Choosing between (c-globbed) and (c-always) is a real cost decision
(a permanent per-session charge in every repo against unreachable design-time rules) and it belongs
in stage 2's requirements alongside §12.3's open questions 2 and 3 and #343's own reconciliation.
Recorded so the next reader inherits the fork rather than re-deriving it.
