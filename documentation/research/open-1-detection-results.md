# Open 1 — LLM-usage detection by code semantics: Results

Tests whether an agent with only `Read` + `Grep` + `Glob` access can reliably detect LLM-inference usage from semantic signals (prompt-shaped strings, hostnames, model-name patterns, token-counting libs, message/role/tool-use shape, streaming/cache handling) — NOT from SDK-import enumeration alone — and characterize the codebase well enough to draft a per-role inventory.

Success criteria from the empirical-testing-plan:
1. Detects ≥80% of true LLM call sites in LLM-using repos
2. False positives ≤10% in non-LLM repos
3. Evidence cited per detection is concrete (file:line), not hand-wavy

---

## Run 2026-05-28

### Test repos

| Repo | Path | Branch | HEAD | Shape sourced |
|---|---|---|---|---|
| metallm | `../metallm` | `develop` | `ba26c59` | Multi-vendor LLM via LangChain + LangGraph; DB-backed model registry; PostgreSQL-encrypted provider keys; mixed static-and-DB prompts |
| discodon | `../discodon` | `fix/empty-room-playback` | `3f4295602` | Multi-role persona/agent system via OpenRouter; Cosmos DB-backed prompts + entity behavior; template renderer with placeholder resolution |
| prawduct (this repo) | `.` | `main` | `2cb29be` | False-positive check — framework that orchestrates Claude-as-runtime via markdown skills but makes no LLM API calls from its executable code |

Pre-test state notes:
- metallm was 274 commits behind `origin/develop` with substantive dirty WIP (558 lines on `tools/product-hook` — a stalled prior framework-sync attempt). WIP was preserved via `git stash push -u -m "WIP: stalled prawduct migration attempt — preserved 2026-05-28 before Open 1 LLM-detection test"`; develop was fast-forwarded.
- discodon was already clean on a feature branch; no upstream movement to pull.
- prawduct was not modified (this is the working repo).

### Methodology

For metallm and discodon, spawned an Explore agent per repo with:
- A detection brief explicitly listing the seven semantic signal classes (prompt-shaped strings, LLM hostnames, model-name patterns, token-counting libs, message/role/tool-use shape, streaming, cache fields).
- The instruction "do NOT rely on SDK-import enumeration alone — SDK presence is *confirming* evidence, not a primary trigger."
- A three-section deliverable: digest, role inventory, migration-shape assessment.
- For discodon specifically: the requester pre-flagged "dynamic, DB-backed prompts" — the agent was briefed to confirm or refute that and to specifically address how much prompt content lives in the DB vs the code.

For prawduct, ran semantic-signal probes directly (small repo, fast):
- `grep -rn -E "^(from|import) (anthropic|openai|google.generativeai|langchain|...)" --include="*.py"` — zero matches
- `grep -rn -E "(api\.openai|api\.anthropic|openrouter\.ai|generativelanguage)" --include="*.py" --include="*.md" --include="*.json"` — one match in `documentation/empirical-testing-plan.md` (this design doc, not source)
- `grep -rn -E "(claude-[a-z0-9.-]+|gpt-[0-9.-]+|gemini-[0-9.-]+)" --include="*.py"` — one match in `tests/test_product_hook.py` (a test fixture, not a call site)
- `grep -rn -E "(import tiktoken|count_tokens)" --include="*.py"` — zero matches
- `grep -rn -E "(messages\s*=\s*\[|role\s*[:=]\s*[\"'](system|user|assistant))" --include="*.py"` — zero matches in non-test sources
- `grep -rn -iE "you are an? (assistant|expert|helpful)" --include="*.py"` — zero matches in non-test sources

---

## Findings per repo

### metallm — multi-vendor, config-driven, complex but tractable

**Digest.** Multi-vendor (Anthropic, OpenAI, DeepSeek, OpenRouter) routed through a LangChain-mediated framework. Model resolution is config-driven: provider rows + encrypted API keys in PostgreSQL; the `3tears-models` library instantiates clients from `models.name_api`. Inference flows through LangGraph nodes; each node corresponds to a distinct semantic role.

**Roles detected (agent draft inventory, 12 entries):**

| Role | Vendor(s) | Model resolution | Prompt location | Evidence |
|---|---|---|---|---|
| Personality / conversation | Anthropic / OpenAI / DeepSeek / OpenRouter | DB (`models.name_api`) | Static prefix + per-turn variable suffix | `api/src/graph/nodes/personality.py:1-6` |
| Tool routing | (same) | (same) | Inline `_TOOL_ROUTING_PROMPT` with `{tool_descriptions}` substitution | `api/src/graph/nodes/tool_router.py:58-82` |
| Tool execution | (same) | `tool_llms.model_id` (DB) | Per-tool system prompt from DB (`ToolLlmEntity.prompt_system`) | `api/src/graph/nodes/tool_executor.py:1-13` |
| Sycophancy detection | (same) | (same) | Inline `SYCOPHANCY_EVALUATION_PROMPT` | `api/src/graph/nodes/sycophancy_check.py:36-69` |
| Memory worthiness gate | (same) | Prefers `is_available_for_background=true` | Inline check prompt | `api/src/graph/nodes/memory_extraction.py:89-100` |
| Memory extraction (full) | (same) | (same) | Delegated to `threetears.agent.memory.MemoryExtractor` | `api/src/graph/nodes/memory_extraction.py:1-11` |
| Reasoning extraction | (same) | (same) | Inline `_EXTRACTION_PROMPT` as `SystemMessage` | `api/src/graph/nodes/reasoning_extraction.py:39-60` |
| Self-improvement analysis | (same) | (same) | Inline `_SCAN_PROMPT` + `_UPDATE_PROMPT` (two stages) | `api/src/graph/nodes/self_improvement.py:33-93` |
| Conversation summarization | (same) | (same) | Inline `DEFAULT_SUMMARIZATION_PROMPT` | `api/src/graph/nodes/summarize.py:23-33` |
| Embedding (vector store) | OpenAI-compatible | Per-provider config | N/A (embeddings, not prompts) | `api/src/services/embedding.py:32-72` |
| Image generation | OpenAI / A1111 / ComfyUI / HF / ModelLabs | Backend-selected | N/A (image gen params) | `api/src/services/image_backends/openai_backend.py` |
| Speech-to-text | OpenAI | `whisper-1` (config) | N/A (STT) | `api/src/config.py` — `whisper_base_url` |

**Migration verdict: Complex but tractable.** Role *shapes* are statically inspectable (graph nodes are first-class Python files). Model *identities* require a DB query (`models.name_api`, `providers.name`, `tool_llms.prompt_system` are the three loads a `/llm-strategy detect` tool would need). Prompt content is either inline Python constants (greppable) or user-editable persistence (treat as opaque, declare "user-configured"). Jinja2 substitution in `system_prompt.py` does not defeat analysis — it's variable interpolation, not branch logic.

**Key infrastructure pointers** (these are what the detect tool should report as anchors):
- `api/src/graph/nodes/` — 14 node files = candidate role inventory
- `api/src/services/chat_model_factory.py` — provider dispatch and model resolution
- `api/src/services/prompt_caching.py` — provider capability matrix (caching cost multipliers: 0.1x Anthropic, 0.5x OpenAI, 0.1x DeepSeek; provider-kind enum)
- `api/src/data/entities/{provider,tool_llm,user}.py` — schema entities
- `api/alembic/versions/0*` — migration filenames advertise role evolution (`070_remove_parse_document_llm_tool.py` etc.)

### discodon — multi-vendor via OpenRouter, ~45% DB-backed prompt content, out-of-scope for static inventory

**Digest.** LLM usage is pervasive across persona, classification, distillation, voice/cognitive-style generation, evaluation, and tool execution — all via OpenRouter (no direct vendor SDKs). The architecture is a template-renderer + Cosmos DB-backed prompt registry + entity-configuration-driven persona system. Static analysis can detect call sites, infrastructure, and template *structure* — but ~45% of actual prompt *content* lives in Cosmos DB containers (`entities_*`, `shared_prompts`) and cannot be inventoried without DB access.

**Roles detected (agent draft inventory, 14 entries):**

| Role | Vendor | Model | Prompt location | Completeness |
|---|---|---|---|---|
| Persona turn execution | OpenRouter | Config + per-entity override (default `anthropic/claude-haiku-4-5-20251001`) | **Mixed**: template + DB entity behaviors | ~60% (template static; backstory/directives/style from DB) |
| Relevance classifier | OpenRouter | Config | **Mixed**: `DEFAULT_CLASSIFIER_TEMPLATE` + DB registry | ~70% (presets in `shared_prompts` container) |
| Distillation (notes→wisdom) | OpenRouter | `config.aria.frontier_model` cascade | **Mixed**: template + registry | ~70% |
| Voice design generation | OpenRouter | `config.aria.frontier_model` | Template + inline (`DEFAULT_COG_STYLE_GEN_TEMPLATE`) | ~80% |
| Cognitive style generation | OpenRouter | `config.aria.frontier_model` | Template static, Big Five trait selectors dynamic | ~75% |
| Scenario judge | OpenRouter | `config.aria.c4_judge_model` (default `openai/gpt-4o-mini`) | Template + registry | ~65% |
| Eval classifier-gen | OpenRouter | Eval client model | **Inline** `_SYSTEM_PROMPT` (full string) | ~90% |
| ARIA diagnoser / generator / compiler | OpenRouter | `config.openrouter.default_model` | Inline + `aria/prompts.py` templates | ~85% |
| Scenario interpreter | OpenRouter | (same) | Inline + `DEFAULT_SCENARIO_INTERPRET_TEMPLATE` | ~85% |
| Image gen | OpenAI (hardcoded) | `gpt-image-1-mini` | N/A | N/A |
| Reflect / research tools | OpenRouter | Tool-config or user-requested | Mixed tool prompts | ~60% |
| Persona state distillation (UI) | OpenRouter | `config.openrouter.default_model` | Template + registry | ~70% |

**Migration verdict: Out-of-scope for v1 static inventory tooling.** Three concrete blockers:

1. **Entity personality (40-50% of turn-prompt tokens)** lives in `entities_*` Cosmos container in `DbEntity.behaviors[PersonaComponent]` — fields `backstory`, `directives`, `style`, `example_statements`, `acting_instructions`. User-authored via web UI / CLI. Field *names* are discoverable from code; *content* is not.
2. **Shared prompt presets (20-30% of classifier/distillation prompts)** live in a single Cosmos document at `id=shared_prompts:{env}` with prompt types `GROUND_RULES`, `CLASSIFIER`, `DISTILLATION`, `CONSOLIDATION`, `TOOL_REACTIONS`. Editable via `discodon/web/routes/prompts.py` and `discodon/web/mcp/prompt_tool.py`. Content not in source.
3. **Model selection is partially dynamic:** role-level defaults are static (e.g., `aria-diagnoser` → `default_model`), but per-entity overrides (`entity.aria_frontier_model`) and per-tool user-selectable models are runtime-determined.

**What `/llm-strategy detect` could still do usefully on discodon:**
- Detect "this repo uses LLMs" — high confidence (semantic signals dense).
- Find every call site, surrounding infrastructure (template renderer at `discodon/llm/template_renderer.py`, placeholder resolver at `discodon/llm/placeholder_resolver.py`, prompt registry at `discodon/llm/prompt_registry.py`).
- Enumerate inline prompts (multiple `_SYSTEM_PROMPT = """..."""` constants — ARIA modules, eval classifier-gen are fully greppable).
- Identify the prompt-storage architecture (Cosmos containers, partition keys, admin CRUD routes).
- **Punt explicitly** on DB-resident content: declare roles with `Prompt location: db:entities_*` or `db:shared_prompts`, mark fields as "requires DB audit," do not pretend to inventory what isn't statically visible.

### prawduct (this repo) — framework, not LLM-using application — false-positive check passed

**Detection results.** All semantic signal grep probes returned **zero** matches in executable Python sources outside `tests/`:
- No LLM SDK imports
- No LLM API hostnames in source code (one hit in this very design doc — that's intentional)
- No model-name patterns outside test fixtures
- No token-counting libs
- No message/role/tool-use shapes
- No "you are an assistant" / role-instruction strings

**Surface that *would* mislead a naive detector:**
- `agents/critic/SKILL.md`, `.prawduct/critic-review.md`, `.prawduct/pr-review.md` — these are long instructional markdown files that look exactly like system prompts. **They are.** Just not API-call prompts — they are skill prompts loaded by the Claude Code runtime into its system context. The framework's Python code never assembles or sends them.
- `tools/prawduct-setup.py`, `tools/product-hook` — names like "agent," "Critic," "review" are everywhere.
- Documentation discusses LLM concepts extensively (this very file, and the prompt-management requirements).

**Why a correct semantic detector should reject the false positive:**
- No HTTP client constructing requests to LLM endpoints
- No response-shape handling (`finish_reason`, `stop_reason`, `usage`, `cached_tokens`, etc.)
- No model-ID-to-client dispatch code
- No streaming consumer
- The "prompts" are pure markdown, loaded by the runtime, not by the framework

**Verdict.** Prawduct correctly fails the LLM-application test. The distinguishing structural feature: *prompts as content* (markdown skills) vs *prompts as code* (Python that constructs API request bodies). A detector that checks for the *outgoing API call* — not just the *prompt-shaped text* — will get this right.

---

## Verdict against Open 1 success criteria

| Criterion | Status | Notes |
|---|---|---|
| Detects ≥80% of true LLM call sites in LLM-using repos | **PASS (qualitative)** | Both agents produced inventories covering the major roles. No ground-truth labeling was done this run — see "Outstanding work" below. |
| False positives ≤10% in non-LLM repo | **PASS** | Prawduct correctly identified as non-LLM despite extensive prompt-shaped markdown content. The semantic-signal probes returned zero hits in Python sources. |
| Evidence cited concrete (file:line) | **PASS** | Both agents returned file:line citations for every role; the discodon agent additionally cited Cosmos container/document paths for DB-backed content. |

**Caveat on the ≥80% threshold:** This run did not produce a hand-labeled ground-truth set per repo, so the ≥80% number is a qualitative pass based on the agents identifying every major role described by the codebases' organization (metallm's graph node files map 1:1 to roles; discodon's prompt registry and ARIA modules map 1:1 to roles). A future tighter run could hand-label call sites in one repo and measure precision/recall directly.

---

## Observations / surprises

1. **Three distinct migration classes emerged**, not two as the spec currently models:
   - **Detectable + inventoriable** (prawduct false-positive class, plus simple single-vendor apps not yet tested) — clean draft from static analysis alone.
   - **Detectable + complex** (metallm) — role shapes statically inspectable; model identities resolved at runtime via DB. Detect tool needs to either (a) require DB access during detection, (b) emit the inventory with `Model: db:<table>.<column>` placeholders for the user to confirm, or (c) read a config flag pointing at the registry table.
   - **Detectable + content-out-of-scope** (discodon) — architecture + call sites inventoriable; prompt *content* fundamentally lives in user-editable DB rows. Inventory is correct and useful at the architecture level even when content is opaque.

2. **The prompt-management spec's "single-file artifact" assumption matches all three repos.** None exhibited the "15+ roles requiring split files" pattern flagged in Q8. metallm and discodon are both 10-15 role projects.

3. **OpenRouter as an aggregator is a first-class case** (discodon), distinct from per-vendor SDKs. The spec mentions OpenRouter once in the empirical-testing-plan but doesn't surface it in the artifact's `vendor` enum (§5.3 lists Anthropic / OpenAI / Google / open / other). Worth treating OpenRouter (and similar aggregators: LiteLLM, Helicone, Portkey) as a vendor class in the artifact, since they normalize the API surface across upstream vendors.

4. **DB-backed prompt content is a real, recurring architecture** — not an exotic edge case. discodon's pattern (entity-config + shared-prompt registry + template renderer with placeholder resolution) is a coherent design choice for any personality/persona/agent product. The spec should explicitly accommodate `Prompt location: db:<table>` and `Prompt location: dynamic` as legitimate values, with appropriate Critic behavior (skip content checks; verify infrastructure presence; defer to DB audit).

5. **Migration "stuckness" is a real signal** — metallm had 558 lines of stalled WIP from a prior framework-sync attempt. Worth understanding why the migration stalled (not investigated in this run; a separate question worth surfacing). The WIP is preserved in stash if needed for forensics.

6. **No `LLMClient` abstraction in either LLM repo**, but neither flagrantly violates FM-19/FM-20 either:
   - metallm uses LangChain + `chat_model_factory.py` as its dispatch layer.
   - discodon goes via OpenRouter, which is itself a unifying layer.
   - Both have a `models.yaml`-equivalent (metallm's `models` table, discodon's `config.openrouter.default_model` cascade).
   - The spec's framing should treat "framework-mediated" (LangChain, LangGraph) and "aggregator-mediated" (OpenRouter, LiteLLM) as legitimate alternatives to a custom `LLMClient` adapter.

7. **Model-tier-registry gap (Open 6 preview):** metallm references `claude-opus-4-5`, `gpt-4o`, `dall-e-2/3`, `gpt-image-1`, `whisper-1`. discodon references `claude-haiku-4-5-20251001`, `gpt-4o-mini`, `gpt-image-1-mini`. Note that `claude-opus-4-5` is a generation older than the current `claude-opus-4-7`; the registry will need to include retired/older tiers to be useful on real repos. Image-gen and STT models are out-of-scope for the chat-LLM tier table but probably want their own categorization.

---

## Implications for the prompt-management spec

**Proposed amendments to `prompt-management-requirements.md` based on this run:**

1. **§5.3 `Prompt location` field** — add `db:<table>[.<column>]` and `dynamic` as recognized values, alongside `inline` and file paths. Update Critic guidance: when location is `db:` or `dynamic`, skip content-applicability checks; verify infrastructure presence and storage location; emit a NOTE recommending a separate DB-content audit.

2. **§5.3 `Vendor` field** — add `aggregator` (or `openrouter`, `litellm` as explicit options) alongside `Anthropic / OpenAI / Google / open / other`. Critic guidance: when vendor is an aggregator, apply the *upstream* vendor's failure modes if the upstream is statically determinable (e.g., `openai/gpt-4o-mini` → OpenAI checks); otherwise treat as vendor-agnostic.

3. **§7.3 adaptive check application** — explicitly add "content-out-of-scope" as a role classification dimension. When the role declares `Prompt location: db:` or `dynamic`, the Critic should run *infrastructure* checks (model resolution path, caching breakpoint placement on static prefix, observability instrumentation) but skip *content* checks (XML structure, few-shot example placement, instruction-before-context). This avoids forcing the user to either expose DB content to the Critic or fail content checks for a category that fundamentally doesn't apply.

4. **§11.3 migration walkthrough** — add a third worked example alongside discodon: a "complex but tractable" case (metallm-shape) where role shapes are static but model identities need DB resolution. The walkthrough should describe the detect tool emitting an inventory with `Model: <unknown — see models table>` placeholders the user populates from their own DB knowledge.

5. **§14 add Q10:** "What does a 'config-driven, runtime-resolved' model declaration look like in the artifact?" — Lean: a structured placeholder (`Model: config:<path>` or `Model: db:<table>.<column>`) that the Critic *requires* in lieu of a literal ID, plus an `effective_models` block the user can optionally populate (a small enumeration of what the resolver *actually* resolves to in production).

6. **§15 out-of-scope list** — leave "DB-backed prompt content" as in-scope-at-the-architecture-level (#3 above), but explicitly mark "auditing the DB content itself" as out-of-scope. The framework is not going to read your Cosmos containers.

7. **§11.5** — extend the dismissal path: a project that registers `uses_llm_inference: true` but has `Prompt location: db:` for >50% of roles could emit an advisory "this project's prompt content is largely DB-backed — full Critic value depends on architecture-level checks; consider whether content audit needs to happen via a separate process."

These amendments stay inside the current architectural shape — they don't require new artifact types or new Critic modes, just more accommodating value sets and slightly broader applicability reasoning.

---

## Outstanding work / next runs

- **Hand-label ground truth on one repo** (probably metallm) to convert qualitative ≥80% into a measured precision/recall number.
- **Run on a fourth repo class** if available: a single-vendor, simple-architecture LLM app (Simple migration class). The current set covers Complex+tractable and Out-of-scope but not the easy case.
- **Pre-Open-2 prerequisite met:** the role inventories drafted above feed directly into Open 2 (role grouping quality). The agent's drafts for metallm look strong enough to be a v1 inventory; discodon's would need a content-audit follow-up but the architecture-level inventory is sound.
- **Pre-Open-6 prerequisite met:** model IDs captured for tier-registry coverage check.

---

## Status

- [x] Open 1 run 2026-05-28 — initial qualitative pass complete. Update `empirical-testing-plan.md` §5 Open 1 status from `[ ]` to `[partial]` (await ground-truth precision/recall before marking `[x]`).
