# Brief: Opus 5.5 prompt audit of prawduct (one slice)

You are auditing one slice of prawduct's **prompt surface**: text that reaches a model as instructions. That means skills, methodology guides, templates, agent definitions, the always-injected session digest, learnings rules, and strings that hooks or gates print to the model. Prawduct is a Claude Code plugin. Its repo is `/Users/brookstalley/source/prawduct`, checked out on branch `feature/opus-55-prompt-audit`. **Read only; do not edit any repo file.**

## What you are producing, and what you are not

The owner rejected a conventional audit that files findings: the last one, a seven-agent sweep, filed items and the surface grew 3.4x anyway. **Your output is a keep/delete/rewrite decision list with the proposed replacement text.** It is not a list of concerns, and it files nothing. Every entry must end in a concrete edit the owner can take or reject. If a line is fine, don't list it. A slice that is clean says so in one line. An empty result beats a manufactured one.

## The standard you judge against

Read these three files in full before reading your slice:

- `guide-prompt-audit.md`: Anthropic's prompt-audit method. Use its pattern groups (1a–1f, 2, 3), its **keep list**, its confidence rubric, and its flag-versus-fix threshold. This is the primary rubric.
- `guide-opus5-behavioral-shifts.md`: Opus 5 behavior that carries to 5.5. It covers over-verification (delete verify-your-work scaffolding), over-delegation to subagents, scope expansion, verbosity, self-correction narration, and severity filters depressing review recall.
- `guide-opus55-behavioral-shifts.md`: the Opus 5.5 deltas.

(The three guide files were excerpts of Anthropic's material bundled with Claude Code's `claude-api` skill, v2.1.282: `shared/prompt-audit.md`, and the "Behavioral shifts" sections of `shared/model-migration.md` for Claude Opus 5 and Claude Opus 5.5. They were given to the auditors from a scratch directory and are not committed here. Read them from that skill, or see Anthropic's published prompting guides.)

The Opus 5.5 prompting guide (platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5) adds these points relevant to prawduct:

- Opus 5.5 is stronger at agentic coding and code review, with more bugs caught and fewer false alarms. It sustains long autonomous work and explains its changes in plain language.
- It ends turns early on long tasks. It announces the next step instead of taking it, offers to carry on, or lists non-blocking decisions for the user. Naming the specific early stops to avoid helps; so does naming the stops you do want, when nothing can move without the user.
- Instructions telling it to think carefully can be removed; effort controls thinking.
- It pays close attention to elapsed-time signals in multi-agent setups.

**Target model:** Opus 5.5. Prawduct's consumers may also run Sonnet 5 or Fable 5.1. For any finding whose removal depends on Opus-5-class capability (for example, deleting scaffolding a weaker model might need), set `model_dependent: yes` so the owner can decide separately.

## Prawduct-specific keep list (binding, in addition to the guide's)

These are owner-accepted decisions. Do not propose removing them. You may propose rewording them.

1. **Independent review stays.** The Critic, and a PR reviewer independent of it, are load-bearing. The owner's 2026-07-02 review found they catch real ship-blockers. Anthropic's "don't use subagents for verification" targets *self*-checking. Distinguish the two:
   - Independent review machinery is kept.
   - Prose telling the *builder* to re-check its own work, re-run queries, or "verify before writing" is a legitimate over-verification candidate.
2. **Verification structure that constrains the output contract binds:** mutation-proof, mechanical enumeration, and the gates. Prescribed *method* (step orderings, named call sites, `Deliverables:` phrased as contract) is a candidate for advisory phrasing (backlog #341).
3. **Fragile operations keep exact scripts:** git and merge procedures, destructive commands, the backlog migration, and anything the prawduct-hook CLI parses.
4. **Machine-read text is not prose.** Build-plan field markers, `prawduct-hook` flags, parsed comments and status markers are read by code. Before proposing an edit to any text a parser or test reads, say so and set `machine_read: yes`.
5. **Token budgets are pinned by tests.** Several files have size ceilings in `tests/`. A trim is fine, but note the file so the integrator can lower its ceiling. Never propose moving prose between files to fit a budget.
6. **Skill `description:` frontmatter is trigger text.** It may carry calibrated urgency (guide Group 3's split). Judge skill bodies, not their routing lines.
7. **The session digest (`plugin/methodology/session-digest.md`) is the only surface every onboarded repo re-reads.** Its size limit is 10,000 characters. Cuts there have the highest leverage, and a default removed there disappears everywhere.

## Prawduct-specific patterns to look for (beyond the guide)

- **Self-verification prose aimed at the builder:** "re-run", "verify before", "falsify first", "check again", "Tell:" clauses that prescribe a re-check. Guide: Opus 5 row "Over-verification".
- **Delegation pushes:** anything that makes delegation the default or offers it first. Opus 5+ over-delegates.
- **Early-stop invitations:** closing rituals that end a turn to hand decisions to the user when nothing blocks.
- **Emphasis in bold rather than caps:** runs of `**...**` doing the job of CAPS, or bold on most sentences of a paragraph. Group 1a applies to bold as much as to caps.
- **Incident archaeology:** issue numbers, dates, "retired 2026-…", chunk numbers, and "an earlier draft said" inside *instructions*. Group 2's history narratives and recency trap apply. Rationale belongs with the rule; the incident story does not.
- **Migration-relative phrasing:** "now", "no longer", "used to", "was retired". Group 1d.
- **Duplicated facts (backlog #342):** the same rule or number stated as authoritative in two or more places. For each one, name the other location(s) and propose which home keeps it; every other copy becomes a one-line pointer or is deleted. Only copied *prose* is in scope. Duplicated *derivations* in Python code are out of scope.
- **Binding method (backlog #341):** text asserting *how* as binding where it should be advice.
- **Size:** whole paragraphs the model already knows, or that restate another file (Group 2, "Verbose SKILL.md").

## Output: write ONE file

Write your results to `.prawduct/artifacts/opus-55-prompt-audit-2026-09/slice-<LETTER>.md`, using exactly this structure:

```
# Slice <LETTER>: <files covered>

## Inventory
<every file you audited, with its word count; confirm you read each one in full>

## Summary
<3–6 sentences: the highest-impact decisions, and the counts per action>

## Decisions
### <LETTER>-<n>: <short name>
- location: `path:line` or `path:line-line`
- evidence: "<exact quote from the file, copied verbatim; at least 8 words so it greps uniquely>"
- pattern: <guide group/row, or prawduct pattern name>
- why: <one or two sentences tying it to documented Opus 5/5.5 behavior>
- confidence: high | medium | low
- action: remove | rewrite | move | add | flag
- replacement: <the exact new text, or "(delete)", or for move: the destination>
- model_dependent: yes | no
- machine_read: yes | no
- dup_of: <other path:line holding the same fact, if a #342 duplicate; else omit>
```

Rules for the output:

- **Evidence must be verbatim.** A script will check that each quote appears in the cited file. Do not paraphrase inside the quotes.
- Order decisions by confidence, then impact.
- Low-confidence items are `flag` and carry no replacement.
- **Cluster instead of listing instances.** Where one pattern recurs across many lines in a file, give one decision with a line range and a rewrite approach, plus two or three worked examples. Do not write one decision per line.
- Stay within your slice's files. If you notice something outside your slice, put one line under a final `## Outside my slice` heading, and nothing more.
- Your final message back should be three lines: the file path, the decision count, and the single highest-impact decision. The file is the deliverable.
