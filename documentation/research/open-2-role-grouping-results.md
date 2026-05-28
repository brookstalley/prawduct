# Open 2 — Role grouping for `/llm-strategy detect`: Results

Tests whether the detect tool's role-grouping output is usable as a v0.1 `prompt-strategy.md` draft — specifically, whether a user with project domain knowledge would accept the draft with ≤30 min of edits, rather than rewrite it from scratch.

Success criteria from the empirical-testing-plan:
- Roles named usefully (a human reading the inventory understands the role's purpose)
- Related call sites grouped under the right role
- Vendor + model populated correctly where evidence exists
- User would accept draft with ≤30 min of edits, not require full rewrite

---

## Run 2026-05-28

### Test repo

metallm (`../metallm`, develop @ `ba26c59`). The Open 1 agent produced a 12-role draft inventory for this repo; this run reviews that inventory for ship-readiness against the §5.3 schema.

### Methodology

This is a desk review, not a fresh detection run. The agent's draft inventory (Section 2 of the metallm subsection in `open-1-detection-results.md`) was evaluated row-by-row against the §5.3 required fields, the new §5.3 schema additions from v0.2 (`kind`, `db:` Prompt location values, aggregator Vendor convention), and the practical question "would a metallm contributor sign off on this in ≤30 min?"

Per-row scoring rubric:
- **Accept**: ship as-is
- **Trivial edit (<2 min)**: rename, reword, add a missing trivial field
- **Lookup edit (2-5 min)**: requires a query, file read, or DB select but no judgment
- **Judgment edit (5-15 min)**: role-naming consolidation, splitting, or rethinking
- **Reject**: misidentified, would need rewrite

### Per-role review

| # | Agent's role name | Acceptance | Edit cost | Notes |
|---|---|---|---|---|
| 1 | Personality / Conversation | Trivial edit | 2 min | Likely rename to `main-chat` or `user-facing-conversation` for clarity. Vendor list (Anthropic/OpenAI/DeepSeek/OpenRouter) is the *configured option set*; user picks the primary or declares `aggregator: <name>` if truly varied per-user. |
| 2 | Tool Routing | Accept | <1 min | Name is clear; evidence at `tool_router.py:58-82` is concrete; `{tool_descriptions}` substitution noted correctly. |
| 3 | Tool Execution | Trivial edit | 2 min | Add `Prompt location: db:tool_llms.prompt_system` per the new v0.2 schema — the agent already identified the DB column but didn't use the new syntax. |
| 4 | Sycophancy Detection | Accept | <1 min | Clean role, single inline prompt, evidence concrete. |
| 5 | Memory Extraction (Worthiness Gate) | Judgment edit | 5 min | Whether this is its own role or a stage of role 6 is a user call. Defensible both ways — the cheap pre-gate has different best practices (small model, single-shot) than the full extraction. |
| 6 | Memory Extraction (Full) | Trivial edit | 2 min | Solid; delegation to `threetears.agent.memory.MemoryExtractor` is noted, which is important for the Critic to know — the actual prompt is in an external library. |
| 7 | Reasoning Extraction | Accept | <1 min | Clean role with `_EXTRACTION_PROMPT` as inline. |
| 8 | Self-Improvement Analysis | Judgment edit | 3 min | Two-stage (scan + update) packaged as one role; user may want to split. |
| 9 | Conversation Summarization | Accept | <1 min | Clear, single inline prompt, fallback heuristic noted. |
| 10 | Embedding (Vector Store) | Trivial edit | 2 min | Add `Pattern: embedding` so the Critic skips chat-completion failure modes for this role. The Vendor is "OpenAI-compatible" — could pin actual `text-embedding-3-small` or declare `Model: config:roles.embedding`. |
| 11 | Image Generation | Trivial edit | 2 min | Multi-backend (OpenAI, A1111, ComfyUI, HF, ModelLabs); declare `Pattern: vision` and `Vendor: multiple (backend-selected)`. |
| 12 | Speech-to-Text (Whisper) | Accept | <1 min | Clean — `whisper-1` pinned, single vendor, clear role. |

**Project-wide overview section** (separate from roles): the agent didn't draft the `Project-wide overview` (vendors-in-use list, cost & latency targets, cross-vendor coordination, security boundary, eval & regression strategy). The detect tool would either auto-populate skeletons from what it detected (vendor list, cross-vendor coordination via the `chat_model_factory.py` pattern) or leave them as TBD for the user. Either way, the user fills 5-10 minutes here.

### Total edit time

- Trivial + lookup edits: ~15 min
- Judgment edits: ~8 min
- Project-wide overview: ~5-10 min
- Subtotal: **~30 minutes**

This sits right at the ≤30 min threshold, with most of the budget going to (a) user judgment on role splitting/consolidation and (b) the project-wide overview that requires user-known information (cost targets, latency targets).

### What the inventory does NOT capture (and what the Critic provides later)

The inventory captures *what roles exist* and *where the prompts live*. It does NOT capture *which best practices are applied per role*. The agent observed evidence like "cache control on system + tools block" infrastructure in `prompt_caching.py` but didn't audit per-role whether each role actually uses it. The user fills `Best practices applied: TBD` per role, and the Critic's first pass surfaces the actual practices vs declared ones.

This is the right division of labor — detect proposes the skeleton, user fills the project-wide context and accepts/edits roles, Critic audits the role-level depth on the next chunk that touches each role.

---

## Verdict against Open 2 success criteria

| Criterion | Status | Notes |
|---|---|---|
| Roles named usefully | **PASS** | 10 of 12 names are clear; 2 (Personality, Self-Improvement) might benefit from rename or split but the names are *understandable*. |
| Related call sites grouped under the right role | **PASS** | The 1:1 mapping between `api/src/graph/nodes/*.py` files and roles makes grouping mechanically correct — the detect tool didn't have to make hard judgment calls. This may not generalize to projects without LangGraph-style explicit role files (see "Observations" below). |
| Vendor + model populated correctly where evidence exists | **PASS** | Vendor list correct; model identities deferred to `db:models.name_api` placeholders per the new v0.2 schema. Evidence cited concretely (file:line). |
| User accepts with ≤30 min edits | **PASS** (estimated) | Per-row edit costs sum to ~25-30 min including the project-wide overview fill-in. Not a rewrite. |

---

## Observations

1. **The 1:1 file-to-role mapping in metallm is a generosity of the codebase.** Each role corresponds to a single Python file in `api/src/graph/nodes/`. This made the detect tool's grouping step nearly mechanical. Codebases with less explicit role separation (call sites scattered across business-logic files, no graph node abstraction) will be harder. The Open 2 success rate on metallm is probably an *upper bound* — discodon-shape (DB-driven, persona-templated) would likely produce a slightly less ship-ready draft because role boundaries are blurrier.

2. **The "Best practices applied" field is the biggest unfilled gap.** None of the 12 roles got this field populated by the detect tool — that's the *correct* division of labor (Critic fills it after the inventory is accepted), but it means the v0.1 inventory looks thin until the first Critic pass produces findings. The detect tool should explicitly mark this as expected: `Best practices applied: TBD — to be discovered on first Critic pass`.

3. **The Pattern dimension (embedding, vision, STT vs chat) was inferable from role descriptions but the agent didn't fill it.** Adding `Pattern: <value>` to roles 10/11/12 specifically reduces Critic noise — the catalog's chat-prompt failure modes shouldn't fire on an embedding role. Worth adding to the detect tool's output template.

4. **The "Project-wide overview" section is the user's job, not the detect tool's.** Cost targets, latency targets, security boundary are project-specific knowledge that lives in the user's head (or in some other doc). The tool should leave these as labeled TBD placeholders with hints (e.g., "Suggested cost target: derive from current monthly spend on vendor APIs").

5. **The migration class (Shape α / β / γ) affects ship-readiness.** Shape β (metallm) ships near 30 min. Shape γ (discodon, content-out-of-scope) probably ships in ~20 min because more fields legitimately declare `db:` or `config:` placeholders. Shape α — both Category A simple and Category B runtime-instruction — ships fastest (10-15 min) because fewer fields apply.

---

## Outstanding work / next runs

- **Repeat on a Shape γ project** (discodon) to confirm the inventory-then-content-audit division of labor holds — specifically that `Prompt location: db:*` is recognized as ship-ready rather than as a gap.
- **Repeat on a Category B project** (prawduct's own skills) to confirm the simplified field set (no max_tokens, no temperature, no cost target) doesn't make the inventory feel hollow.
- **Open 2 status remains `[ ]` in the testing plan** — this is a desk review, not an end-to-end test with the actual detect tool (which doesn't exist yet). When the tool ships, re-run for real.

---

## Status

- [x] Open 2 desk-review run 2026-05-28 — metallm inventory judged ship-quality at ≤30 min edit cost. Tool-shipping run pending build plan completion.
