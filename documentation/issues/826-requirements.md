# Issue #826 — Plugin-Routed MCP Best-Practice Knowledge Corpus: Requirements

`status: draft · stage: requirements · area: learnings · added: 2026-10-06 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/826`

Related: #343 (the query-time delivery ruling this item must reconcile with, not re-answer),
`.prawduct/artifacts/mcp-knowledge-corpus-design.md` (taxonomy, schema, rulings §9 and §13 — not
re-derived here), `.prawduct/artifacts/mcp-mining/` (the evidence),
`documentation/prompt-management-requirements.md` §15 and D4/D7/D8/D14.

This document turns the issue's four stages into requirements an owner can accept, amend or
reject. It does **not** redo the design artifact. It states what each stage must deliver, what
"done" is observable as, and which decisions are still the owner's. Technical design (pack file
layout, resolver code, pointer text) is the next stage and is deliberately not here.

## Problem

Cordyceps, hallucinote, bankmachine and discodon each re-derive MCP server engineering lessons and
silently disagree. Prawduct has no home for that knowledge, and no mechanism that would put it in
front of a consumer at the moment they design, build or review MCP work. Everything the plugin
ships is pull-based; `.claude/rules/learnings/` path routing is product-owned and per-repo.

Observable problem to solve: *a consumer repo doing MCP work gets the same vetted MCP guidance at
design, build and review time, without prawduct copying framework content into that repo, and the
guidance can be revised when MCP itself changes.*

## Grounding facts

Measured on `develop`, 2026-10-06. Re-derive; do not copy the numbers.

- **The corpus input is large.** `cd .prawduct/artifacts/mcp-mining; grep -c '^\*\*RULE:\*\*'
  *-structured.md` gives 147 / 95 / 106 rules across three captures; `grep -ohE '^LAYER: L[0-4]'
  *-structured.md | sort | uniq -c` gives L0 27, L1 119, L2 82, L3 82, L4 38. The captures weigh
  about 433 KB (`cat *-structured.md | wc -cw`). The design artifact's §13.1 cites 34 L0 rules; the
  current tally is 27, so any figure carried into a pack must come from the command, not either
  document. That is an upper bound on input, not a size estimate for the authored corpus.
- **Routing is file-granular and harness-side.** `learnings_files.parse_frontmatter` treats a file
  with no `paths:` key as always-loaded and a file with `paths:` as loaded when a matching file is
  read. `learnings_files.resolve` roots at the project and never consults the plugin root.
- **The plugin ships nothing path-routed.** The SessionStart digest is the only push channel and it
  is size-capped. `scaffold_core` (`plugin/lib/learnings_files.py`) is the one existing scaffold
  into `.claude/rules/learnings/`, and writes only when the file is absent.
- **Distribution has constraints.** `documentation/` is not distributed, so the corpus lives under
  `plugin/`; shipped files may only reference paths inside the curated plugin root
  (`tests/test_plugin_packaging.py`).
- **Evidence tier is mixed.** One consumer-side capture (discodon) is withheld for privacy, so R1
  (tool-surface shape), R6 and the clamp-vs-refuse question lack consumer-side evidence. This is a
  stated property of stage 1, not a defect to hide.

## Rulings that bind

| Ruling | Source | Consequence for requirements |
|---|---|---|
| Packaging: a directory of layer files, addressed by reference | design §10.1 | R-1.2 |
| Framework knowledge is read at query time from the plugin, never copied at onboard; stays a distinct store; labelled by origin | #343 (a)–(c) | R-2.1, R-2.3 |
| A scaffolded product-owned pointer is approved as the **starting** shape, with the owner's reservation that it may not be sufficient | design §13 | R-2.2 |
| Pointer, not copy: nothing regenerates corpus text into other files | design §2.1 | R-2.1 |
| Live disagreements are stated as disagreements with evidence on each side, not resolved by majority | issue acceptance, design §10.2 | R-1.4 |

## Requirements

Each stage stands alone if the next slips (issue constraint). IDs are for reference in design and
review; "Done when" is the observable check.

### Stage 1 — Author the corpus and a skill to open it

- **R-1.1 Authored against the mined evidence.** Every rule carries the design §3 schema fields:
  layer tag, kind, fire-site, and addressed evidence. Rules whose evidence is unaddressed
  (`PROVENANCE: UNADDRESSED`) are not authored as settled rules.
  *Done when:* `grep -c 'PROVENANCE: UNADDRESSED'` over the authored corpus returns 0, and the
  command is run to see it return non-zero on a seeded violation.
- **R-1.2 Directory of layer files, split by cluster where a layer is too large.** L1 splits along
  the clusters the material produced (design §10.2), not by a new taxonomy. Dated ecosystem/client
  constants live in one facts file that rules cite, so revalidation re-checks the facts list rather
  than the corpus.
  *Done when:* no single corpus file exceeds a size cap the owner sets (see D-4), and no rule
  inlines a client or spec constant that the facts file also holds.
- **R-1.3 Preamble of stances kept separate from rules.** Stances are not rules.
- **R-1.4 Contested questions are filed as ADJUDICATIONS.** The R1 tool-surface question is filed
  with each position's evidence tier visible (measured / borrowed / reframing) and no verdict. The
  three disagreements that dissolve (progress notifications, rename policy, clamp-vs-refuse where
  evidence allows) are filed as ordinary rules with the precondition in the rule sentence. Clamp
  vs refuse stays **blocked** while its evidence is withheld; it is filed as an adjudication saying
  so.
  *Done when:* each adjudication has a `WHAT WOULD SETTLE IT` instrument, not an opinion.
- **R-1.5 A skill opens the corpus.** The skill reads from the plugin at query time and labels
  output as framework knowledge. It may filter by layer or fire-site but does not copy corpus text
  anywhere.
  *Done when:* invoking the skill against a consumer repo returns pack content with an origin
  label, and nothing is written to the consumer repo.
- **R-1.6 Citation verification is a precondition.** A corpus claim that cannot be located cannot
  be revalidated. Quoted source text declares itself as verbatim (the schema gap in design §10.4),
  and the verification tool is re-run at authoring time.
  *Done when:* `tools/verify-capture-quotations.py` (or its successor) runs clean on the authored
  evidence fields.
- **R-1.7 Third-party exposure check.** Before any mining pass is added, the source repo's
  visibility and ownership are checked (design §10.5). No private repo's internals enter the
  public corpus.
- **R-1.8 Non-Python neutrality.** MCP servers are TypeScript-first. Nothing in the corpus or its
  tooling keys on Python, and a language with no rules is reported unchecked, never passed.

### Stage 2 — Plugin-shipped, path-routed knowledge packs

This is the capability that satisfies owner absolute 2. It is generic: MCP is pack #1.

- **R-2.1 No framework content is copied into a consumer repo.** The corpus stays under `plugin/`.
  What reaches the repo, if anything, is a routing declaration (design §9, constraint 2).
- **R-2.2 Coverage by moment.** The mechanism reaches all three moments, or states which it does
  not (design §13.2):
  - *design time* (L0, no server file exists yet): needs an always-loaded pointer or a skill the
    user invokes;
  - *build time* (editing a server's files): globbed pointer;
  - *review time*: Critic perspective (stage 3).
  The globbed pointer alone cannot reach L0 by construction. This item therefore **requires an
  owner decision on D-1** before stage 2 design starts.
- **R-2.3 Origin label.** A reader can always tell a pack rule from a product rule: the pointer or
  skill output says the content is framework-shipped and names its pack and plugin version (#343
  (c), open question 2 in design §12.3).
- **R-2.4 Reaches onboarded repos.** A pointer is delivered to already-onboarded repos by a
  migrate or doctor refresh step, not a template edit, and it reports an outcome (created /
  already present / skipped) rather than silently passing.
- **R-2.5 Never overwrites.** Absence of the pointer file is the only trigger to write it; a
  product-edited pointer is left alone and reported if stale.
- **R-2.6 Pointer globs do not trip `record_lint`.** A pointer in a repo with no MCP surface must
  not raise the "glob matches nothing tracked" finding, or the lint must be taught the pointer
  exemption explicitly.
- **R-2.7 Reusable beyond MCP.** A second pack can be added by adding a directory and a registry
  row, with no code change to the resolver. The requirement is checked by a test that registers a
  throwaway second pack.
- **R-2.8 Cost is bounded and measured.** The per-session cost of the always-loaded variant, if
  chosen, is stated in lines and tokens and applies to every governed repo (see D-1). The query-time
  cost of the skill is checked against a corpus several times the authored size (#343 acceptance).
- **R-2.9 Architecture amendment recorded.** The steady-state clause in `architecture.md`
  § Direction is amended beneath itself citing the owner's ruling, recorded somewhere the amendment
  is not its own only witness.

### Stage 3 — Critic review perspective for MCP surfaces

- **R-3.1 MCP-shaped diffs draw the corpus into review.** The Critic's learnings read-set
  (`learnings-files --for-diff`) includes the relevant pack files when the diff touches an MCP
  surface, using the same files the skill reads.
- **R-3.2 "MCP surface" is defined by a checkable predicate.** Candidates: server-SDK imports,
  tool-registration calls, `tools/list` handlers, config files naming MCP servers. The predicate
  is language-neutral (R-1.8) and its false-positive and false-negative behaviour is tested on
  fixtures from at least a TypeScript and a Python repo.
  *Done when:* a fixture diff with an MCP surface adds pack files to the read-set and a fixture
  without one adds none.
- **R-3.3 Adjudications reviewed as such.** A finding that depends on an OPEN adjudication is
  reported as contested, not as a violation.

### Stage 4 — Revalidation and sibling intake

- **R-4.1 Revalidation path.** When MCP itself changes, a defined procedure re-checks the facts
  file and the rules citing it, and records the outcome and date. It rides the existing
  norm-lifecycle sweep and advisory machinery if that can express a dated-facts check; otherwise
  the gap is named (design §7, third open question).
- **R-4.2 Staleness is surfaced.** A facts entry past its review horizon surfaces as an advisory;
  it never blocks.
- **R-4.3 Sibling intake.** Sibling repos can contribute new rules by a named path that applies the
  R-1.7 exposure check and the R-1.1 provenance rule.
- **R-4.4 Relocation is gated on stage 2.** Removing sibling-repo research from a sibling must not
  happen before stage 2 ships and is verified to reach that sibling (issue sequencing constraint).
  *Done when:* the relocation step cannot be marked done while the stage 2 acceptance is open.

### Cross-stage

- **R-X.1 Mechanize what can be mechanized.** Rules that can become checks do (for example a scan
  of instructional collateral for literal MCP tool names, exempting authorization surfaces).
  Recall-dependent rules are the weakest form (core learnings).
- **R-X.2 Heading anchors that are cited are verified.** If a skill or review perspective cites a
  corpus section by heading, something verifies the anchor still resolves.
- **R-X.3 Packaging tests keep passing.** No shipped corpus file references a path outside the
  curated plugin root.

## Out of scope

- Re-deriving the L0–L4 taxonomy, the rule schema, the directory-not-file ruling or §9.
- Shipping stage 1 as a document and calling absolute 2 met.
- A C# (or any language) MCP server scaffold. Prawduct supplies expertise, not templates.
- Resolving the R1 disagreement by majority.
- Mechanical promotion of general learnings (#343's derived-view fork) — this item takes the
  hand-authored side of that fork.

## Decisions needed (owner)

| # | Decision | Recommendation |
|---|---|---|
| **D-1** | Stage 2 pointer shape: globbed only, always-loaded only, or both. | Both, split by moment: a small globbed pointer for build time, plus an always-loaded L0 *skill invocation hint* only if the per-session cost measured in R-2.8 is under an owner-set budget. Until measured, start globbed-only, as ruled, and record that L0 is unreached. |
| **D-2** | Build #343's delivery mechanism and stage 2 as one design, or separate with a stated reason. | One design: stage 2 is #343's mechanism generalized, and two designs would answer the origin-label question twice. |
| **D-3** | Origin labelling form (design §12.3 q2) and whether build-time auto-load of a *pointer* is intended (q3). | Label in the pointer body and in skill output with pack name and plugin version; confirm q3 yes, since the pointer is not the corpus. |
| **D-4** | Per-file size cap for corpus files, and the always-loaded budget. | Set after the first authored layer is measured; do not pick a number from the capture sizes. |
| **D-5** | Whether stage 1 may ship before D-1/D-2 are answered. | Yes. Stage 1 stands alone and delivers the hand-off desirable; it is not a claim that absolute 2 is met. |

## Open for design

1. Pack registry shape and how the resolver finds packs without a hard-coded MCP name (R-2.7).
2. Where the L0 content lives so it can be reached before any server file exists.
3. The MCP-surface predicate's exact signals (R-3.2).
4. Whether the facts file fits the existing norm-lifecycle sweep or needs its own probe (R-4.1).
5. How the pointer refresh reports on a repo where the user deleted the pointer on purpose (R-2.4,
   R-2.5).
6. Test plan with red-verify checks for each "Done when" above.

## Risks

- **Scope.** Four stages and a new framework capability make this effort L at best. Each stage
  should become its own backlog item once D-1 and D-2 are answered; this document should be split
  then rather than grown.
- **Evidence gap.** The withheld consumer-side capture limits R1, R6 and clamp-vs-refuse. The
  corpus must say so in the rules affected.
- **Verification debt.** Citations are agent-reported; R-1.6 makes verification a gate for stage 1,
  which may be the largest hidden cost.
- **Per-session cost.** An always-loaded pointer taxes every governed repo, MCP or not.
