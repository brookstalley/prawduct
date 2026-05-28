# Vendor Prompt Engineering & LLM Application Sources

A directory of *where* current authoritative prompt-engineering and LLM-application guidance lives, organized by vendor and topic. **This is a URL directory, not a content snapshot** — vendor guidance changes faster than this file can. Use these links to fetch fresh guidance at review time.

**How to use this directory:** When reviewing LLM-using code, look up the relevant `(vendor, topic)` cell. Each cell provides a canonical URL, a one-line summary of what's there, a recency signal, and a stability rating. Prefer entries marked `Stability: canonical` (durable platform docs); entries marked `Stability: ephemeral` are blog posts or changelogs that may move. Items tagged `(2025-2026 shift)` represent material changes to vendor guidance worth knowing.

All URLs were verified via web fetch/search in May 2026.

---

## Anthropic (Claude)

### 1. Prompt structure & engineering principles
- **URL:** https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- **What's there:** The single living reference for Claude prompting — clarity, examples, XML structuring, role prompting, extended thinking, prompt chaining, and model-specific tuning for Claude 4.x (Opus 4.7, Sonnet 4.6, Haiku 4.5).
- **Companion overview page:** https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview
- **Recency signal:** Actively maintained; references Opus 4.7 and Mythos Preview.
- **Stability:** canonical

### 2. Prompt caching
- **URL:** https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- **What's there:** Full mechanism (prefix-based, 5-min default / 1-hour extended TTL), cache_control breakpoints, automatic vs explicit caching, pricing multipliers (1.25x write, 0.1x read), pre-warming with `max_tokens: 0`, mixed-TTL strategies.
- **Tool-use caching variant:** https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-use-with-prompt-caching
- **Recency signal:** Workspace-level isolation rolled out Feb 5, 2026; automatic caching now supports TTL. **(2025-2026 shift)**
- **Stability:** canonical

### 3. Structured output
- **URL:** https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- **What's there:** Generally-available structured outputs on Sonnet 4.5+, Opus 4.5+, Haiku 4.5 — `output_format` for guaranteed-valid JSON, `strict: true` on tool definitions for schema-locked tool parameters; grammar-compiled, not prompt-coerced. Refusals take precedence over schema (`stop_reason: "refusal"`).
- **Agent SDK companion:** https://platform.claude.com/docs/en/agent-sdk/structured-outputs
- **Recency signal:** GA in late 2025/early 2026; no beta header required. **(2025-2026 shift)**
- **Stability:** canonical

### 4. Tool use / function calling
- **URL:** https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
- **What's there:** Client tools (you execute) vs server tools (Anthropic executes — `web_search`, `code_execution`, `web_fetch`, `tool_search`). Tool choice modes, error handling, parallel tool use.
- **Advanced features announcement:** https://www.anthropic.com/engineering/advanced-tool-use
- **Tool reference:** https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-reference
- **Recency signal:** 2026 added Tool Search Tool (thousands of tools without context bloat), Programmatic Tool Calling (code-sandbox tool orchestration), Tool Use Examples standard. **(2025-2026 shift)**
- **Stability:** canonical (overview); ephemeral (engineering blog)

### 5. Refusal & safety handling
- **URL:** https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/handle-streaming-refusals
- **What's there:** Starting with Claude 4, streaming responses can return `stop_reason: "refusal"` from streaming classifiers. Three refusal types: streaming classifier (`stop_reason: refusal`), input/copyright validation (400 errors), model-generated refusals (text). **You must reset conversation context after a refusal** or refusals will continue.
- **Sonnet 4.5 filter details:** https://support.claude.com/en/articles/12449294-understanding-sonnet-4-5-s-api-safety-filters
- **Constitution:** https://www.anthropic.com/constitution
- **Recency signal:** Refusal `stop_reason` pattern introduced with Claude 4; future API versions will unify refusal handling. **(2025-2026 shift)**
- **Stability:** canonical

### 6. Cost & latency optimization
- **URL:** https://platform.claude.com/docs/en/about-claude/pricing (pricing reference)
- **Batch API:** Message Batches API — 50% off list price, 24-hour async window; on Opus 4.7/4.6 and Sonnet 4.6 supports up to 300K output tokens with `output-300k-2026-03-24` beta header. **(2025-2026 shift)**
- **What's there:** Stack caching (≈90% read savings) with batch (50%) for up to ~95% reduction on eligible workloads.
- **Recency signal:** 300K output beta header dated March 24, 2026.
- **Stability:** canonical

### 7. Model selection guidance
- **URL:** https://platform.claude.com/docs/en/about-claude/models/overview
- **What's there:** Active model table (Opus 4.7, Opus 4.6, Sonnet 4.6, Sonnet 4.5, Haiku 4.5), context windows, pricing, primary use cases.
- **System cards:** https://www.anthropic.com/system-cards
- **Recency signal:** Updated with each model launch; Mythos Preview announced April 7, 2026 (limited availability — Project Glasswing).
- **Stability:** canonical

### 8. Migration / deprecation policy
- **URL:** https://platform.claude.com/docs/en/about-claude/model-deprecations
- **What's there:** Lifecycle stages (Active / Legacy / Deprecated / Retired), full deprecation history table with dates, recommended replacements. **At least 60 days notice** before retirement of publicly released models. Email + docs notification.
- **Preservation commitments:** https://www.anthropic.com/research/deprecation-commitments
- **Recency signal:** Most recent deprecation announcement April 14, 2026 (Sonnet 4 / Opus 4 → retire June 15, 2026).
- **Stability:** canonical

### 9. Eval methodology
- **URL:** https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- **What's there:** Anthropic's published playbook (Jan 9, 2026) — three grader types (code-based, model-based, human), pass@k / pass^k for non-determinism, matching graders to agent type (coding, conversational, research, computer use), balanced capability vs regression evals. **(2025-2026 shift)**
- **Companion: develop tests:** https://platform.claude.com/docs/en/test-and-evaluate/develop-tests
- **Recency signal:** Jan 2026 publication; this is the current reference cited across the platform docs.
- **Stability:** ephemeral (engineering blog) — but treated as canonical by Anthropic's own docs

---

## OpenAI

### 1. Prompt structure & engineering principles
- **URL:** https://developers.openai.com/api/docs/guides/prompt-engineering
- **What's there:** Developer/user/assistant message hierarchy, prompt section structure (identity, instructions, examples, context), Markdown headers + XML tags as delimiters, 3-5 example few-shot, GPT-5.x-specific guidance.
- **Prompt guidance (newer concise version):** https://developers.openai.com/api/docs/guides/prompt-guidance
- **Recency signal:** References GPT-5.5 as current recommended model; mentions Responses API and prompt caching.
- **Stability:** canonical

### 2. Prompt caching
- **URL:** https://developers.openai.com/api/docs/guides/prompt-caching
- **What's there:** Automatic caching at ≥1024 tokens, up to 80% latency / 90% cost reduction on cache reads, place static content first / variable content last. Typical eviction 5-10 minutes; up to 1 hour off-peak. Supports Extended Prompt Caching for longer retention.
- **Cookbook:** https://developers.openai.com/cookbook/examples/prompt_caching_201
- **Recency signal:** Available on gpt-4o and all newer models; extended retention policies added 2025.
- **Stability:** canonical

### 3. Structured output
- **URL:** https://developers.openai.com/api/docs/guides/structured-outputs
- **What's there:** Schema-enforced JSON (evolved from older JSON mode), two modes — `response_format` for response shaping and strict function calling for tool argument validation. Pydantic / Zod helpers in SDKs.
- **Recency signal:** GA since GPT-4o; reinforced as default pattern in 2025-2026 docs.
- **Stability:** canonical

### 4. Tool use / function calling
- **URL:** https://developers.openai.com/api/docs/guides/function-calling
- **Using tools (broader):** https://developers.openai.com/api/docs/guides/tools
- **What's there:** Function tools (JSON schema) plus custom tools (free-form text I/O). Tool search (`tool_search`) for large tool inventories on gpt-5.4+. Function calling is supported in the Responses API.
- **Recency signal:** Responses API supersedes Chat Completions/Assistants split; **Assistants API shuts down Aug 26, 2026**. **(2025-2026 shift)**
- **Stability:** canonical

### 5. Refusal & safety handling
- **URL:** https://model-spec.openai.com/ (current spec; dated version: https://model-spec.openai.com/2025-12-18.html)
- **Safe completions explainer:** https://openai.com/index/gpt-5-safe-completions/
- **What's there:** Authority hierarchy (Root / System / Developer / User / Guideline). Shift from hard refusals to **safe completions** (output-centric safety, helpful refusals with alternatives) introduced with GPT-5. Three risk tiers: prohibited / restricted / sensitive. **(2025-2026 shift)**
- **Recency signal:** Model Spec dated 2025-12-18; safe-completions paradigm introduced August 2025 with GPT-5.
- **Stability:** canonical (Model Spec is versioned)

### 6. Cost & latency optimization
- **URL:** https://developers.openai.com/api/docs/guides/cost-optimization
- **What's there:** Reduce requests, minimize tokens, smaller models; Batch API (50% off, 24-hour async, no streaming); Flex Processing (lower cost / slower latency for non-prod).
- **Batch API:** https://platform.openai.com/docs/guides/batch
- **Recency signal:** Flex Processing is a 2025 addition. **(2025-2026 shift)**
- **Stability:** canonical

### 7. Model selection guidance
- **URL:** https://developers.openai.com/api/docs/models
- **Compare:** https://developers.openai.com/api/docs/models/compare
- **All models:** https://developers.openai.com/api/docs/models/all
- **What's there:** Current production models (GPT-5.5, GPT-5.4 / Mini / Nano, o-series reasoning, gpt-oss-120b / gpt-oss-20b Apache-2.0 open weights). Context windows, modalities, pricing.
- **Release notes:** https://help.openai.com/en/articles/9624314-model-release-notes
- **Recency signal:** GPT-5.4 noted as best general-purpose default as of April 2026.
- **Stability:** canonical

### 8. Migration / deprecation policy
- **URL:** https://developers.openai.com/api/docs/deprecations
- **What's there:** "Deprecated" (scheduled shutdown) vs "Legacy" (no updates, still working). Typical 6-12 month advance notice; Assistants API got 12 months. Email + docs notification.
- **Recency signal:** Assistants API shutdown Aug 26, 2026; gpt-3.5-turbo and gpt-4 variants sunset Oct 23, 2026; DALL-E 2/3 retire May 12, 2026.
- **Stability:** canonical

### 9. Eval methodology
- **URL:** https://developers.openai.com/api/docs/guides/evaluation-best-practices
- **Agent evals:** https://developers.openai.com/api/docs/guides/agent-evals
- **Learn evals overview:** https://developers.openai.com/learn/evals
- **Open-source registry:** https://github.com/openai/evals
- **Cookbook topic:** https://developers.openai.com/cookbook/topic/evals
- **What's there:** Hosted Evals product (recommended over open-source repo for new work) — datasets, graders, traces, eval runs. Best-practices doc covers objective definition, dataset collection, metric design.
- **Recency signal:** Hosted product is the actively recommended path; open-source `evals` repo remains for offline use.
- **Stability:** canonical

---

## Google (Gemini)

### 1. Prompt structure & engineering principles
- **URL:** https://ai.google.dev/gemini-api/docs/prompting-strategies
- **What's there:** Clear instructions, few-shot vs zero-shot, contextual grounding, prompt decomposition, parameter tuning, iterative refinement; Gemini-3-specific guidance on direct/well-structured prompts and prioritizing critical instructions for agentic workflows.
- **Vertex equivalent:** https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/prompts/prompt-design-strategies
- **Recency signal:** Last updated April 28, 2026.
- **Stability:** canonical

### 2. Prompt caching
- **URL:** https://ai.google.dev/gemini-api/docs/caching
- **API ref:** https://ai.google.dev/api/caching
- **Vertex equivalent:** https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/context-cache/context-cache-overview
- **What's there:** Two modes — **Implicit caching** (auto-enabled on Gemini 2.5+, no opt-in, no guarantee) and **Explicit caching** (manual cache objects, guaranteed savings, default 1-hour TTL, 90% discount on Gemini 2.5+). Caches are model-specific (cannot reuse across model IDs).
- **Recency signal:** Last updated May 18, 2026; implicit caching is the 2025-2026 shift. **(2025-2026 shift)**
- **Stability:** canonical

### 3. Structured output
- **URL:** https://ai.google.dev/gemini-api/docs/structured-output
- **Vertex:** https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/control-generated-output
- **What's there:** Schema-enforced JSON (Google calls it "controlled generation"). 2025 added full JSON Schema support and implicit property ordering across all actively supported Gemini models — Pydantic/Zod work out-of-the-box.
- **Announcement:** https://blog.google/technology/developers/gemini-api-structured-outputs/
- **Recency signal:** JSON Schema support announced 2025; preserved-key-ordering on Gemini 2.5+. **(2025-2026 shift)**
- **Stability:** canonical

### 4. Tool use / function calling
- **URL:** https://ai.google.dev/gemini-api/docs/function-calling
- **Tools overview:** https://ai.google.dev/gemini-api/docs/tools
- **Tool combination:** https://ai.google.dev/gemini-api/docs/tool-combination
- **Vertex:** https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/tools/function-calling
- **What's there:** Parallel and compositional function calling. **March 2026 update:** combine built-in tools (Google Search, Maps grounding) with custom functions in a single call; context circulation across tool calls; Maps grounding extended to Gemini 3. **(2025-2026 shift)**
- **Announcement:** https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-tooling-updates/
- **Recency signal:** Tool combination announcement March 17, 2026.
- **Stability:** canonical

### 5. Refusal & safety handling
- **Status:** No single canonical refusal-handling page comparable to Anthropic's streaming refusals doc.
- **Closest:** Safety settings + filter categories are in the Gemini API safety docs; for self-hosting Gemma-class open models, see Llama Guard / model-side guardrails under Open/Local below.
- **Stability:** N/A

### 6. Cost & latency optimization
- **URL:** https://ai.google.dev/gemini-api/docs/caching (caching is the main optimization lever Google documents)
- **Batch:** Gemini Batch Mode — https://ai.google.dev/gemini-api/docs/batch-mode — 50% off, 24-hour SLA.
- **What's there:** Caching + batch + Flash-Lite tier are the documented levers. Implicit caching means no code change for many workloads.
- **Recency signal:** Batch Mode GA; implicit caching active on 2.5+.
- **Stability:** canonical

### 7. Model selection guidance
- **URL:** https://ai.google.dev/gemini-api/docs/models
- **Vertex equivalent:** https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models
- **What's there:** Pro (most capable, agentic/reasoning), Flash (high-volume default), Flash-Lite (cheapest), Nano (on-device). Current generation Gemini 3.x Pro and Gemini 3.5 Flash (announced Google I/O May 19, 2026).
- **Recency signal:** Gemini 3.5 Flash announced May 2026; 3.1 Pro is current production reasoning model.
- **Stability:** canonical

### 8. Migration / deprecation policy
- **URL:** https://ai.google.dev/gemini-api/docs/deprecations
- **Versions/lifecycle (Vertex):** https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions
- **What's there:** Stable / Latest stable / Preview / Experimental versions; 2-week notice before `latest` alias changes. One month before retirement, new access blocked; retired models return 404. Announcements via Release Notes page.
- **Release notes:** https://ai.google.dev/gemini-api/docs/changelog
- **Recency signal:** Gemini 2.5 Pro/Flash deprecation targets October 2026; embedding model `text-embedding-004` retires Jan 14, 2026.
- **Stability:** canonical

### 9. Eval methodology
- **URL:** https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/evaluation (Gen AI Evaluation Service API)
- **Run an evaluation:** https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/run-evaluation
- **Playbook:** https://googlecloudplatform.github.io/applied-ai-engineering-samples/genai-on-vertex-ai/gemini/evals_playbook/
- **What's there:** Rapid Eval SDK — built-in pointwise/pairwise model-based metrics, in-memory metrics (rouge, bleu, tool function-call), custom metric definition. `run_inference()` + `evaluate()` client pattern.
- **Recency signal:** Native Gemini 2.5+ support; actively documented through 2026.
- **Stability:** canonical

---

## Open / Local (Llama, Hugging Face, Ollama, open-weight deployment)

### 1. Prompt structure & engineering principles
- **URL (Meta):** https://www.llama.com/docs/how-to-guides/prompting/
- **Llama 4 prompt format:** https://www.llama.com/docs/model-cards-and-prompt-formats/llama4/
- **Llama 3.1 prompt format:** https://www.llama.com/docs/model-cards-and-prompt-formats/llama3_1/
- **What's there:** Zero/few-shot, role prompts, chain-of-thought, self-consistency, RAG patterns, hallucination reduction. **Model-card pages are the authoritative source for special tokens and turn delimiters** required by each Llama generation.
- **Recency signal:** Llama 4 cards current; no explicit "last updated" timestamp on the prompting guide.
- **Stability:** canonical (vendor docs)

### 2. Prompt caching
- **Status:** No vendor-published prompt caching guidance — this is a runtime/server concern for open weights.
- **Closest:** vLLM prefix caching docs (https://docs.vllm.ai/) and SGLang RadixAttention (https://docs.sglang.ai/) — automatic prefix caching is built into both.
- **Stability:** canonical (server docs), but not vendor-level model guidance

### 3. Structured output
- **Ollama:** https://docs.ollama.com/capabilities/structured-outputs — pass JSON Schema via `format` param; works with Pydantic via `model_json_schema()`.
- **vLLM:** https://docs.vllm.ai/en/latest/features/structured_outputs/ — `guided_json`, `guided_regex`, `guided_choice`, `guided_grammar`. XGrammar default backend.
- **Hugging Face / TGI:** schema-guided generation via Outlines or XGrammar backends.
- **What's there:** Token-level grammar constraints (GBNF in llama.cpp; XGrammar / LLGuidance in vLLM/SGLang) guarantee schema adherence regardless of model.
- **Recency signal:** Ollama structured outputs launched late 2024; XGrammar default in vLLM 2025.
- **Stability:** canonical

### 4. Tool use / function calling
- **Meta Llama API tool calling:** https://llama.developer.meta.com/docs/features/tool-calling/
- **Ollama:** https://docs.ollama.com/capabilities/tool-calling — single, parallel, multi-turn agent loop; streaming support.
- **llama.cpp:** https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md — OpenAI-style function calling; supports Llama 3.1/3.2/3.3 built-in tools (wolfram_alpha, web_search, code_interpreter).
- **Hugging Face chat templates + tools:** https://huggingface.co/docs/transformers/chat_extras — pass functions to `apply_chat_template(tools=...)`; Python type hints + Google-style docstrings auto-generate schemas.
- **Stability:** canonical
- **Recency signal:** Hugging Face Tools+RAG chat template docs current to transformers v4.5x (2026).

### 5. Refusal & safety handling
- **Llama Guard 4:** https://www.llama.com/docs/model-cards-and-prompt-formats/llama-guard-4/
- **Llama Guard 3:** https://www.llama.com/docs/model-cards-and-prompt-formats/llama-guard-3/
- **Prompt Guard 2:** https://www.llama.com/docs/model-cards-and-prompt-formats/prompt-guard/
- **What's there:** Llama Guard runs as a separate classifier model on input AND output; expects role-tagged prompts and returns `safe` / `unsafe + <category list>`. Categories follow MLCommons taxonomy. Prompt Guard is a jailbreak/injection classifier. Llama Stack bundles both as built-in guardrails.
- **Llama Stack guardrails:** https://developers.redhat.com/articles/2026/05/04/guardrails-enterprise-safety-shields-llama-stack
- **Recency signal:** Llama Guard 4 is current generation.
- **Stability:** canonical (model cards); ephemeral (Red Hat tutorial)

### 6. Cost & latency optimization
- **Status:** Open-weight cost optimization is server-side — not a vendor guidance topic in the way it is for hosted APIs.
- **Closest canonical sources:**
  - vLLM performance tuning: https://docs.vllm.ai/en/latest/performance/optimization.html
  - SGLang: https://docs.sglang.ai/
  - Quantization (Ollama / llama.cpp GGUF formats) is the main lever.
- **Stability:** canonical (server docs)

### 7. Model selection guidance
- **Hugging Face model hub:** https://huggingface.co/models (filter by task, license, parameters)
- **Llama model card hub:** https://www.llama.com/docs/model-cards-and-prompt-formats/
- **What's there:** HF Hub for browsing 2M+ models with task filters and benchmark leaderboards. Meta's model card pages are the authoritative source for each Llama variant's prompt format, license, and capabilities.
- **Recency signal:** Llama 4 (Scout/Maverick) is the current Meta generation; Qwen 3.6, GLM-5.1, gpt-oss-120b are strong 2026 open-weight alternatives.
- **Stability:** canonical

### 8. Migration / deprecation policy
- **Status:** **No vendor deprecation policy for open weights** — once published, weights remain available (HF hub retains old revisions). This is a structural advantage of open-weight deployment.
- **Closest:** Hugging Face revisions/branches give you immutable snapshots. Meta announces new Llama generations but does not retire prior weights from HF.
- **Stability:** N/A (no deprecation by design)

### 9. Eval methodology
- **Hugging Face Open LLM Leaderboard:** https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard
- **lm-evaluation-harness (EleutherAI, de-facto standard):** https://github.com/EleutherAI/lm-evaluation-harness
- **Meta Llama evals:** scattered across model card pages and the llama-cookbook repo.
- **What's there:** lm-evaluation-harness is the canonical benchmark runner for open weights. HF leaderboard ranks models on a curated benchmark suite.
- **Stability:** canonical (community-de-facto)

---

## Cross-vendor patterns

### Where vendors AGREE
- **Schema-enforced structured output is the new default.** Anthropic, OpenAI, and Google all converged on grammar-compiled JSON schema enforcement in 2025-2026 (Anthropic `output_format` + `strict: true`, OpenAI Structured Outputs, Gemini "controlled generation"). All three recommend it over prompting-for-JSON. Open/local matches via XGrammar / LLGuidance / GBNF.
- **Prompt caching with a static-prefix layout.** All three hosted vendors recommend the same pattern: place static content (system, tools, large context) at the start; place variable content at the end. Cache reads run at ~10% of input cost across all three.
- **Batch APIs are 50% off with 24-hour SLAs.** Anthropic, OpenAI, and Google all offer this — same discount, same window, same no-streaming constraint.
- **Few-shot examples and clear instructions** remain the unanimous baseline advice.
- **Reasoning/thinking models** (Anthropic extended thinking, OpenAI o-series, Gemini Pro adaptive thinking) all warn against over-prompting — the model reasons better with less hand-holding.

### Where vendors DIVERGE
- **Prompt structuring syntax:** Anthropic strongly prefers **XML tags** (`<example>`, `<context>`); OpenAI recommends **Markdown headers and/or XML**; Google emphasizes **delimiters generally** with no strong preference. Open/local depends on the model's chat template.
- **Refusal semantics:** Anthropic introduced a dedicated `stop_reason: "refusal"` requiring explicit context reset (Claude 4+). OpenAI shifted to **safe completions** (helpful refusals with alternatives — output-centric rather than input-centric) with GPT-5. Google has no equivalent canonical doc. Open/local models rely on external classifiers (Llama Guard).
- **Deprecation notice periods:** Anthropic = at least 60 days. OpenAI = typically 6-12 months, sometimes 12+ for major APIs. Google = no fixed period but 2-week notice on `latest` aliases; 1-month "new access blocked" window. Open weights = never deprecated.
- **System prompt model:** OpenAI uses a four-level authority hierarchy (Root/System/Developer/User/Guideline). Anthropic uses a flatter system/user split with strong adherence. Gemini uses system instructions but with less rigid hierarchy.
- **Tool-call inventory scaling:** Anthropic and OpenAI both shipped "tool search" features in 2026 to handle thousands of tools without context bloat — but with different mechanics (Anthropic server-side `tool_search` tool; OpenAI `tool_search` parameter on gpt-5.4+).

### What each vendor uniquely emphasizes
- **Anthropic:** XML structuring, extended thinking as a first-class feature, model welfare and deprecation preservation commitments, very explicit `stop_reason: refusal` handling contract, server-tools (`web_search`, `code_execution`) as a first-class API surface.
- **OpenAI:** Model Spec as a versioned governance document (transparent, dated revisions); safe completions as a refusal paradigm; the Responses API as the unified surface replacing Chat Completions + Assistants; hosted Evals product with traces and graders.
- **Google:** Implicit caching (zero-effort cost savings); built-in tools (Google Search, Maps grounding) composable with custom functions in a single call; massive context windows (1M+); tight Vertex/Gen AI Evaluation SDK integration.
- **Open/Local:** Immutable weights (no deprecation by design); model-card pages as the authoritative prompt-format source per generation; safety as a swappable classifier layer (Llama Guard) rather than baked into the model; grammar-enforced structured output independent of model capability.
