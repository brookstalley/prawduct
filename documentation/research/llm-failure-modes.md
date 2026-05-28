# LLM Application Failure Modes — Static Detection Inventory

This inventory catalogs LLM-application failure modes that an independent code-reading reviewer can detect without executing the code under review. Each entry names a concrete static signal, the impact if shipped, the usage classes it applies to (model tier, single-shot vs. agentic, vendor, volume), the specific files and patterns the Critic should scan, vendor specificity, and what looks similar but is fine. Findings are drawn from OWASP LLM Top 10 (2025), Anthropic and OpenAI docs, the Failure Modes in LLM Systems taxonomy (arXiv 2511.19933), AppScale's 2026 root-cause guide, public post-mortems of multi-thousand-dollar runaway agent incidents, and 2025-2026 practitioner write-ups on prompt caching, context stuffing, and structured-output regressions.

## Prompt Engineering

### Dynamic content in the cache-stable region

- **Pattern** — String concatenation that injects timestamps, request IDs, `datetime.now()`, user IDs, or session UUIDs into a `system` prompt, tool definition, or other content placed *before* the most recently marked `cache_control` breakpoint. Often appears as f-strings or template substitution in the same module that constructs the request.
- **Impact** — Anthropic cache breakpoint silently misses on every request. The team pays cache *write* costs (1.25x or 2x base input) without ever getting cache *read* prices (0.1x base). 5x-10x overspend on a workload designed for caching, with no error or log.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — Anthropic Claude (any tier), high-volume or repeat-system-prompt workloads (chat, RAG, classification pipelines, agent loops). Less critical for single-shot calls with no expected reuse.
- **Detection** — In files that build Anthropic SDK requests (`anthropic`, `@anthropic-ai/sdk`), trace what flows into blocks at indices below the deepest `cache_control` marker. Flag any non-deterministic input: `datetime`, `time.time()`, `uuid`, `random`, request-scoped IDs, user-specific values. Also flag prompts where `cache_control` is set on the *final* message block (user input) — that breakpoint only caches what was written by an earlier request that also had a breakpoint at the same prefix.
- **Vendor specificity** — Anthropic-specific (explicit `cache_control` model). OpenAI's automatic caching is more forgiving but still requires a stable >=1024-token prefix. Google Gemini implicit caching has similar prefix requirements.
- **False-positive risk** — Dynamic content placed *after* the last `cache_control` breakpoint is correct and intentional. A dev environment that varies content for testing is fine if guarded by a flag.

### Instructions placed after long context

- **Pattern** — System prompt or task instructions appended at the end of a message that begins with a large document, transcript, or retrieved context. Often `f"{huge_document}\n\nNow do X"` rather than `f"Do X. Here is the document:\n{huge_document}"`.
- **Impact** — "Lost in the middle" degradation; published benchmarks show >30% accuracy drop when key instructions sit at depth-10 of a 20-document context. Worse on smaller models and on Claude/Gemini, which weight openings.
- **Applies-to (kind):** both — Applies to both API-call code paths and runtime-instruction artifacts (the failure mode is about prompt design / security / eval discipline, not the API surface).
- **Applies-to** — Any model when context exceeds ~8K tokens; pronounced for Haiku-class, Gemini Flash-class, and any open-weights small model. Less applicable to short-prompt single-shot calls.
- **Detection** — Search for prompt builders where a `document`, `chunks`, `retrieved`, `history`, or `context` variable is interpolated before the instruction/task text. Cross-check with token estimates in code (e.g., `tiktoken.encode`) or model `max_context` config. Also flag any prompt where instructions appear only at the end of a >32K-token payload.
- **Vendor specificity** — Vendor-agnostic, but Anthropic explicitly documents preference for instructions-first and XML-tagged structure; OpenAI is more permissive.
- **False-positive risk** — Some patterns deliberately put a brief recap instruction at both ends ("sandwich"). One trailing reminder after leading instructions is fine.

### Plain-text role/data mixing (Claude)

- **Pattern** — Claude prompts that concatenate untrusted user input, retrieved documents, and instructions as plain paragraphs without XML tags (`<document>`, `<user_query>`, `<instructions>`, etc.).
- **Impact** — Higher prompt-injection susceptibility (model cannot distinguish data from instruction); measurably worse output structure; degraded reliability on multi-document tasks.
- **Applies-to (kind):** both — Applies to both API-call code paths and runtime-instruction artifacts (the failure mode is about prompt design / security / eval discipline, not the API surface).
- **Applies-to** — Anthropic Claude across all tiers; the effect is documented as model-specific because Claude is trained on XML-tagged prompts. Less material for OpenAI/Gemini which use other conventions (markdown headers, role blocks).
- **Detection** — Files importing `anthropic` where prompt construction uses `+`, f-strings, or `.join()` against user/retrieved content without any `<` tag wrappers. Check `system=` and `messages=[{...}]` content fields specifically.
- **Vendor specificity** — Anthropic-specific best practice. For OpenAI, equivalent failure is missing `developer`/`system` role separation or stuffing retrieved data into the system prompt.
- **False-positive risk** — Very short prompts (single-instruction classifiers) do not benefit from XML and the tagging would be over-engineering.

### Few-shot examples mis-placed or unordered

- **Pattern** — Few-shot examples placed at the very end of the user message (after the actual query), or shuffled/randomized per request, or 8+ near-identical examples included by default.
- **Impact** — Up to ±15% accuracy swing from order alone; trailing-example placement flips >30% of predictions in QA per recent benchmarks; diminishing returns past 4-5 examples and degradation past 10 on small models.
- **Applies-to (kind):** both — Applies to both API-call code paths and runtime-instruction artifacts (the failure mode is about prompt design / security / eval discipline, not the API surface).
- **Applies-to** — Classification, extraction, and structured-output tasks; effect is strongest on Haiku/Flash/Mini-class models. Less significant on Opus/GPT-5/Gemini-Pro frontier tiers.
- **Detection** — Look for example lists (`examples = [...]`, `EXAMPLES = ...`) that are `random.shuffle`'d, sliced inconsistently, or interpolated after the user query in the prompt template. Count examples — flag >5 unless the task is complex synthesis.
- **Vendor specificity** — Vendor-agnostic; effect documented across QWEN, LLAMA, MISTRAL, COHERE families.
- **False-positive risk** — Intentional shuffling for an A/B eval is fine if gated by a flag. Long curated example lists (>5) are defensible for code synthesis and complex reasoning tasks.

## Cost & Efficiency

### Frontier model used for trivial work

- **Pattern** — Opus 4.x / GPT-5 / Gemini-Pro hard-coded as the only model for low-complexity tasks: classification, sentiment, language detection, entity extraction with a small schema, format conversion, "does this match a pattern" booleans.
- **Impact** — 10x-60x cost premium vs. Haiku/Mini/Flash on tasks where the small model meets quality. Compounds in any high-volume pipeline; Anthropic's deprecation of Claude 4 Opus three months after launch demonstrates how quickly the cost calculus shifts.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — All vendors. Most acute in high-volume single-shot pipelines (classification, moderation, routing); less critical in low-volume premium-quality work.
- **Detection** — Grep for `claude-opus`, `gpt-5` (not `-mini`/`-nano`), `gemini-pro` (not `-flash`/`-lite`) and check the surrounding task description in code comments, prompt text, and function names. Flag if the task is classification/extraction/routing and there is no cascade or fallback to a smaller tier.
- **Vendor specificity** — Vendor-agnostic anti-pattern; the substitution candidate differs (Haiku 4.5, GPT-5 mini/nano, Gemini Flash/Flash-Lite).
- **False-positive risk** — Cascade-pattern code where Opus is the *escalation* target after Haiku low-confidence is correct. Genuinely hard tasks (complex synthesis, long-context reasoning) defensibly use frontier tiers.

### No prompt caching where workload is repetitive

- **Pattern** — Anthropic SDK requests with a multi-KB stable system prompt, tool list, or RAG context, called repeatedly, with no `cache_control` parameter anywhere. Or OpenAI Chat Completions where the same system prompt is sent on every request without leveraging implicit cache (i.e., the stable prefix is shorter than the 1024-token threshold or is constructed differently per call).
- **Impact** — Direct 4x-10x overspend on input tokens for the cacheable portion. For a 10K-token system prompt at 1 req/sec, ~$50K/month avoidable spend at Sonnet pricing.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — Chat assistants, RAG, agentic loops, coding agents, any pipeline that re-sends a large stable prefix. Not applicable for one-off calls.
- **Detection** — In Anthropic clients, count `cache_control` occurrences; if zero and the system prompt or tools block exceeds ~2KB, flag. In OpenAI clients, look for system prompts constructed differently per call (timestamps, random ordering of tools, dict iteration over an unordered structure) that would defeat implicit caching.
- **Vendor specificity** — Anthropic (explicit), OpenAI (implicit, automatic), Google (implicit/explicit hybrid). Detection differs per vendor.
- **False-positive risk** — Genuinely one-off batch jobs, fine-tuned models with short prompts, or research scripts do not need caching.

### Streaming used for non-display consumers

- **Pattern** — `stream=True` set on calls whose only consumer is a backend parser, database writer, or another LLM. Often accompanied by code that simply collects the stream into a string before processing.
- **Impact** — Slightly higher cost (some providers), increased complexity, and lost ability to use server-side features (structured outputs, batch endpoints) that conflict with streaming. Worse: streaming partials may be parsed as truncated JSON.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — All vendors. Backend pipelines, async workers, eval harnesses.
- **Detection** — Find `stream=True` (Python) or `stream: true` (TS) and trace the consumer; flag if there is no user-facing surface (no SSE handler, no WebSocket, no console print) consuming the chunks incrementally.
- **Vendor specificity** — Vendor-agnostic; OpenAI structured outputs and some batch features explicitly disallow streaming.
- **False-positive risk** — Streaming for cancellation/early-exit semantics is legitimate even with a backend consumer.

### `max_tokens` set too low or unset

- **Pattern** — Hard-coded `max_tokens=512` or similar in a path that may legitimately produce long outputs (summaries, code generation, multi-item extractions). Or `max_tokens` unset on providers that default low (some self-hosted, some Bedrock-routed paths).
- **Impact** — Silent truncation. `finish_reason == "length"` returns are often unhandled; downstream parsers see invalid JSON or partial text and either crash or — worse — accept truncated data.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — All vendors; especially open-source / self-hosted endpoints where defaults vary. High impact on long-form summarization, code gen, and multi-step extraction.
- **Detection** — Grep for `max_tokens=` and compare to the schema / expected output length. Flag any output-parsing code path that does not branch on `finish_reason` (or vendor equivalent — Anthropic `stop_reason`, Gemini `finishReason`).
- **Vendor specificity** — Vendor-agnostic. OpenAI uses `max_completion_tokens` on newer endpoints; check both names.
- **False-positive risk** — Deliberately bounded outputs (one-line classifier, single-token logprob extraction) are correct with low `max_tokens`. The flag is about *unhandled* truncation, not the limit itself.

## Output Handling

### Regex/string parsing of LLM JSON output

- **Pattern** — `re.search(r"\{.*\}", output, re.DOTALL)` or substring slicing between `` ```json `` and `` ``` `` fences to extract structured data, instead of using vendor-native structured outputs (OpenAI `response_format`, Anthropic tool-use schemas, Gemini `responseSchema`).
- **Impact** — Brittle parser breaks the first time the model nests an object, omits a key, adds explanatory prose, switches fence languages, or hits a `content_filter`/`refusal` path. Common failure mode behind "it worked yesterday."
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — All extraction, classification, and tool-call routing tasks. Single-shot or agentic.
- **Detection** — Grep for `re\.(search|match|findall)` and `json.loads` paired in the same module that calls an LLM SDK. Flag if the model supports structured outputs and they are not being used.
- **Vendor specificity** — Vendor-agnostic anti-pattern; the replacement differs (OpenAI `response_format={"type": "json_schema", ...}`, Anthropic tool-use, Gemini `responseSchema`).
- **False-positive risk** — Free-form outputs that genuinely don't fit a schema (creative writing, explanations) are correctly parsed loosely. Some legacy models lack structured-output support.

### No handling for `finish_reason="content_filter"` / `refusal`

- **Pattern** — Code that reads `response.choices[0].message.content` (OpenAI) or `response.content[0].text` (Anthropic) without first inspecting `finish_reason` / `stop_reason` / `refusal` field.
- **Impact** — Refused responses are silently treated as empty or partial outputs. In OpenAI's structured outputs, the `refusal` field is a *separate* attribute — code that assumes `.content` is always present crashes or writes nulls.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — All vendors; especially impactful on safety-sensitive workloads (medical, legal, moderation) and on multi-step agents where a refused step poisons later steps.
- **Detection** — Trace response handlers in SDK consumers. Flag any access to `.content` / `.text` / `.choices[0].message.content` that is not preceded by a check on `finish_reason`, `stop_reason`, or `refusal`.
- **Vendor specificity** — Field names differ: OpenAI `finish_reason` + `refusal`; Anthropic `stop_reason`; Gemini `finishReason` + `safetyRatings`. Detection logic must be vendor-aware.
- **False-positive risk** — Wrappers (LangChain, LiteLLM) may abstract these fields; check the wrapper's docs. Internal tools with disabled safety filters won't trigger.

### Schema drift between code and prompt

- **Pattern** — A Pydantic / Zod / dataclass schema in code defines fields A, B, C; the prompt text instructs the model to return A, B, D; the structured-output `response_format` (if any) declares yet a different shape. Often arises after a partial refactor.
- **Impact** — Silent data loss (D is parsed and discarded; C is missing and defaults applied); validation errors at runtime; eval datasets that no longer match production output.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — All vendors. Common in long-lived codebases where prompt and schema evolve in different PRs.
- **Detection** — For each LLM call, locate (a) the schema class, (b) the prompt text describing fields, and (c) the `response_format` / tool-use schema. Diff the three field sets. Flag mismatches.
- **Vendor specificity** — Vendor-agnostic.
- **False-positive risk** — Intentional supersets (prompt describes more fields than schema captures, schema has computed fields not in prompt) are common and may be deliberate.

## Security

### Untrusted input concatenated into system/instruction context

- **Pattern** — User-supplied text (chat message, uploaded document body, web-scraped content, retrieved RAG chunk) interpolated directly into the system prompt or into an instruction-bearing position, without delimiting, escaping, or `<untrusted>` tagging.
- **Impact** — OWASP LLM01 prompt injection. In agent contexts, a single poisoned document can hijack tool-call sequences. Documented commercial-LLM injection success rates of 94%+ in adversarial trials.
- **Applies-to (kind):** both — Applies to both API-call code paths and runtime-instruction artifacts (the failure mode is about prompt design / security / eval discipline, not the API surface).
- **Applies-to** — All vendors; highest risk in agentic systems with tools, multi-tenant chat, and any RAG-over-web pipeline. Lower risk in fully closed-corpus systems with vetted content.
- **Detection** — Trace the data flow from request body / DB read / web fetch to LLM call. Flag any path where untrusted content is appended to `system=` content or to a message that *precedes* the actual user turn. Look for missing delimiter patterns (`<user_input>`, `[BEGIN UNTRUSTED]`, etc.).
- **Vendor specificity** — Vendor-agnostic. Anthropic recommends `<document>` / `<source>` tagging; OpenAI recommends explicit role separation.
- **False-positive risk** — Trusted-by-policy content (your own KB articles, vetted templates) may legitimately appear in system context.

### Tool/function execution without confirmation gate

- **Pattern** — Agent loops where `tool_use` responses from the model are executed directly (file write, shell command, API call, DB mutation) with no allowlist, no human-in-the-loop, and no per-call cost/scope check.
- **Impact** — OWASP LLM06 Excessive Agency. Combined with prompt injection: arbitrary code execution, data exfiltration. The July 2025 Claude Code incident burned 1.67B tokens / ~$16K-$50K in one runaway loop.
- **Applies-to (kind):** both — Applies to both API-call code paths and runtime-instruction artifacts (the failure mode is about prompt design / security / eval discipline, not the API surface).
- **Applies-to** — Any agentic system (tool-use loop, MCP server, coding agent). Especially dangerous for tools with side effects (file system, shell, network, paid APIs).
- **Detection** — Find tool dispatch code (typically a `switch`/`match` on `tool.name` or a `tools_map[name](args)` pattern). For each branch, check whether the action is destructive/side-effectful and whether there is an allowlist, dry-run mode, or confirmation step. Flag side-effectful tools with no guard.
- **Vendor specificity** — Vendor-agnostic. Anthropic and OpenAI tool-use schemas are syntactically different but the failure is identical.
- **False-positive risk** — Read-only tools (DB SELECT, file read, web fetch within an allowlist) can be safely auto-executed. Sandboxed environments lower the bar.

### Prompts and full payloads logged to general-purpose logs

- **Pattern** — `logger.info(f"Calling LLM with prompt: {prompt}")` or `print(messages)` in handler code, where prompts contain user PII, credentials pasted from chat, or sensitive document text. Logs flow to a non-segregated sink (stdout, Splunk, CloudWatch, Sentry).
- **Impact** — OWASP LLM02 Sensitive Information Disclosure. Logs become a PII sink subject to GDPR/HIPAA constraints they were never designed for. Anecdotal reports of 12K+ live API keys found in a single training-data crawl illustrate the propagation risk.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — Any deployed service. Most acute for healthcare, finance, legal, HR.
- **Detection** — Grep for logger / print calls in modules that build LLM requests; flag any that interpolate `messages`, `prompt`, `system`, `content`, or `user_input` without an explicit redaction step. Cross-check against documented PII fields in the project's data dictionary if present.
- **Vendor specificity** — Vendor-agnostic.
- **False-positive risk** — Logging redacted hashes, request IDs, or token counts is fine. Debug-mode logs gated by `DEBUG`/`if dev` may be acceptable in dev only.

### System prompt embedded in client-side or returnable surface

- **Pattern** — System prompt stored in a frontend asset (React bundle, mobile app), returned in an API response field, or echoed in error messages. Also: prompts that *invite* the model to print its own instructions ("respond with your role").
- **Impact** — OWASP LLM07 System Prompt Leakage. Competitive IP loss, jailbreak engineering surface, and accidental disclosure of credentials or business rules embedded in the prompt.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — All user-facing applications.
- **Detection** — Search frontend code, OpenAPI specs, and error handlers for the system prompt text or known marker strings. In agent code, check whether the model can be asked to dump its instructions and whether the response is returned verbatim.
- **Vendor specificity** — Vendor-agnostic.
- **False-positive risk** — Open-source projects that intentionally publish their prompts. Marketing examples in docs.

## Evaluation & Regression

### No pinned-fixture eval set for each LLM-using function

- **Pattern** — A function that calls an LLM has unit tests that either (a) mock the LLM response entirely (testing only the wrapper logic), (b) call the live LLM with no recorded expected output, or (c) assert on `len(output) > 0` / `"yes" in output.lower()`.
- **Impact** — Model version drift, prompt edits, and provider behavior changes produce silent quality regressions. No basis for comparing models when evaluating substitution.
- **Applies-to (kind):** both — Applies to both API-call code paths and runtime-instruction artifacts (the failure mode is about prompt design / security / eval discipline, not the API surface).
- **Applies-to** — All LLM-using code paths. Most material where model selection is contested or where models will be migrated as deprecation deadlines hit.
- **Detection** — For each LLM-calling function, locate its tests. Flag if tests do not include (a) a fixed input set, (b) an expected-output set or scoring rubric, and (c) a deterministic comparison (exact match, regex, embedding similarity threshold, LLM-as-judge with a pinned judge model).
- **Vendor specificity** — Vendor-agnostic.
- **False-positive risk** — Pure prompt-routing or pre-processing functions may legitimately not need an output fixture. Genuinely creative tasks may use rubric-based or human eval only.

### Assertions on free-text substrings

- **Pattern** — `assert "approved" in response.lower()` or `assert response.startswith("yes")` as the only check on model output. Often paired with a temperature >0 in the call.
- **Impact** — Tests pass on rephrased "Approved." / "Yes," and fail on equally correct "I would say yes," — yielding both false confidence and flaky CI.
- **Applies-to (kind):** both — Applies to both API-call code paths and runtime-instruction artifacts (the failure mode is about prompt design / security / eval discipline, not the API surface).
- **Applies-to** — Classification, decision routing, and any task where the model's "answer" is a token but the parser looks at prose.
- **Detection** — In test files (`test_*.py`, `*.test.ts`, `*.spec.ts`), grep for `assert ... in ...` and string-prefix/suffix assertions against LLM outputs. Cross-check whether structured outputs would eliminate the ambiguity.
- **Vendor specificity** — Vendor-agnostic.
- **False-positive risk** — Substring assertions on *structured* sections (extracted JSON field values, regex on tool-call args) are fine. Some assertions are intentionally loose.

### Eval temperature mismatched to production

- **Pattern** — Eval harness calls the model with `temperature=0` while production code uses `temperature=0.7` (or vice versa). Sometimes the temperature is implicit (default differs between SDKs).
- **Impact** — Eval results do not predict production behavior. False green CI on a model that is in fact flaky at production temperature.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — Any project with a separate eval entry point. Especially deceptive on classification tasks where temperature=0 hides true variance.
- **Detection** — Compare the kwargs at LLM call sites in `tests/`, `evals/`, or `benchmarks/` against the production call sites. Flag temperature, `top_p`, `seed`, and (for OpenAI) `reasoning_effort` mismatches.
- **Vendor specificity** — Vendor-agnostic.
- **False-positive risk** — A team deliberately running eval at temp=0 for determinism *and* sampling production at temp=0 with `n=5` to measure variance is fine.

## Multi-LLM Coordination

### Hard-coded model names across N files

- **Pattern** — Literal model IDs (`"claude-sonnet-4-5"`, `"gpt-5"`, `"gemini-2.5-pro"`) appear directly in business-logic files rather than being resolved through a single config / registry / role-to-model mapping.
- **Impact** — Migration on deprecation (Claude 3.7 Sonnet shutdown 2026-05-11; Claude 3.5 Haiku 2026-07-05; Claude 3 Haiku 2026-08-23; multiple Gemini 2.0 deprecations) becomes a multi-file change. Pricing changes can't be assessed. A/B testing of model substitutions is impossible without code edits.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — Any multi-LLM project. Severity scales with number of distinct LLM call sites.
- **Detection** — Grep for known model-ID substrings across the repo. Count distinct files. Flag if model IDs appear in more than ~2 places without a registry/config indirection (e.g., `models.yaml`, `ModelRegistry`, `settings.MODEL_CLASSIFIER`).
- **Vendor specificity** — Vendor-agnostic.
- **False-positive risk** — A single config file or registry module that intentionally lists all model IDs is correct. Tests pinning specific models for regression purposes are fine.

### No "role" abstraction across providers

- **Pattern** — Code dispatches by raw model name (`if model.startswith("claude"): ...`) rather than by *role* (`classifier`, `extractor`, `summarizer`, `vision`). Provider differences (prompt format, structured-output API, tool-use schema) leak into business logic.
- **Impact** — Vendor lock-in; difficulty swapping providers for cost or capability; multi-model failover impossible. Each new model requires touching every call site.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — Multi-vendor projects, especially those using Claude + OpenAI + Gemini in different roles per the constraint in this research.
- **Detection** — Look for SDK imports (`from anthropic import ...`, `from openai import ...`, `from google import genai`) co-located in the same business-logic modules. Absence of a `LLMClient` / `Provider` / `chat()` adapter interface is the signal.
- **Vendor specificity** — Vendor-agnostic anti-pattern.
- **False-positive risk** — Single-vendor projects don't need this abstraction. Research/eval code legitimately calls multiple SDKs directly.

### Cross-model identity assumed in agent handoff

- **Pattern** — One model's tool-call output (Anthropic `input` field with structured args) is passed directly to another model's expected input format (OpenAI `arguments` JSON string), without transformation. Or: model A's reasoning trace is fed to model B as ground truth without provenance tagging.
- **Impact** — Subtle field-name and serialization mismatches; loss of safety signal (refusal from model A becomes empty input to model B); reasoning hallucinations from model A treated as facts by model B.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — Multi-model agent pipelines (e.g., Haiku classifier → GPT-4o extractor → Sonnet summarizer).
- **Detection** — Trace data flow between LLM calls. Flag where the *raw* response object of one provider's SDK is passed to another provider's call without an intermediate normalized type or schema.
- **Vendor specificity** — Cross-vendor pipelines specifically.
- **False-positive risk** — Normalized hand-off types (a project-defined `LLMResult` dataclass) are correct.

## Migration & Drift

### No deprecation watch on pinned model IDs

- **Pattern** — A pinned model ID with no comment, no associated `deprecation_date` config, and no scheduled review. The `.prawduct/project-state.yaml`, `pyproject.toml`, or equivalent has no record of which models the project depends on.
- **Impact** — On the model's shutdown date, requests return 400 errors with no warning beyond vendor email. Production incident on a known timer.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — All projects pinning specific model versions. Especially acute for Anthropic (aggressive 6-12 month deprecation cycles in 2025-2026) and Google (frequent 2.x Flash variant churn).
- **Detection** — Cross-reference all model IDs found in the codebase against published deprecation dates (Anthropic, OpenAI, Google docs). Flag any that are deprecated, will be in <6 months, or have no documented end-of-life check.
- **Vendor specificity** — Vendor-agnostic; deprecation cadence varies by vendor.
- **False-positive risk** — Open-source models hosted internally have no vendor deprecation but may have other lifecycle concerns (security patches).

### Floating model alias used where determinism matters

- **Pattern** — `model="claude-sonnet-latest"`, `model="gpt-4"` (alias, not a snapshot), `model="gemini-pro"` (no version) in code paths that have pinned-fixture evals, regulatory output, or contract-bound behavior.
- **Impact** — Provider rolls the alias to a new snapshot; eval suite passes (locally pinned) but production silently shifts. Hardest class of regression to attribute.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — Regulated workloads, contract-locked outputs, eval-pinned pipelines. Less critical for chat experiences where minor drift is acceptable.
- **Detection** — Grep for known floating aliases (`-latest`, base names without dates/versions). Compare against vendor docs for alias semantics.
- **Vendor specificity** — Anthropic (`-latest` suffix), OpenAI (`gpt-4o` as alias), Google (base names roll). Per-vendor pattern.
- **False-positive risk** — Chat-style features intentionally tracking the latest model are correct using aliases.

## Observability

### No per-call token / cost / latency logging

- **Pattern** — LLM calls without surrounding telemetry: no token-count log, no model attribution, no `user_id` / `feature` / `request_id` tag, no latency timer. Cost shows up as a single line on the vendor's monthly invoice.
- **Impact** — Cannot diagnose cost spikes, cannot attribute spend to features or users, cannot detect a runaway loop (the 1.67B-token / $16K-$50K Claude Code incident went unnoticed for 5 hours).
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — All deployed LLM applications. Severity scales with volume and unit cost.
- **Detection** — In each LLM call site, look for surrounding spans / metrics. Specifically: extraction of `usage.input_tokens`, `usage.output_tokens`, `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens` (Anthropic) or equivalent OpenAI `usage.prompt_tokens`/`completion_tokens` and Gemini `usageMetadata`. Flag if not captured. Check for OpenTelemetry / Langfuse / Helicone / custom span instrumentation.
- **Vendor specificity** — Field names differ; the failure pattern is universal.
- **False-positive risk** — Low-volume internal tools may legitimately defer instrumentation.

### Cache hit rate not measured

- **Pattern** — Anthropic-using code captures `input_tokens` and `output_tokens` but ignores `cache_read_input_tokens` and `cache_creation_input_tokens`. OpenAI-using code does not log `cached_tokens` from `usage.prompt_tokens_details`.
- **Impact** — Cache regressions (caused, e.g., by the "dynamic content in cache region" failure above) are invisible. Team assumes caching is working because the code has `cache_control` markers, but read rate is 0.
- **Applies-to (kind):** api-call — Applies only when the project makes the LLM API call itself; runtime-instruction artifacts (skills, rules, agent configs) do not control this surface.
- **Applies-to** — Any project relying on caching for cost control.
- **Detection** — Look for `usage` field extraction; flag if cache-related sub-fields are not pulled, logged, or graphed.
- **Vendor specificity** — Anthropic (most detailed cache fields), OpenAI (single `cached_tokens`), Google (varies).
- **False-positive risk** — Projects with no caching strategy don't need these metrics.

### No agent step-count / token-budget circuit breaker

- **Pattern** — Agent loop with no `max_steps` / `max_iterations` ceiling; or one that is set absurdly high (`max_steps=1000`); or no cumulative token budget per task with hard termination on breach.
- **Impact** — Resource-exhaustion incidents. The July 2025 Claude Code incident's proximate cause was a recursion the loop limits did not catch. OWASP LLM10 Unbounded Consumption.
- **Applies-to (kind):** both — Applies to both API-call code paths and runtime-instruction artifacts (the failure mode is about prompt design / security / eval discipline, not the API surface).
- **Applies-to** — Any agentic system. Risk scales with tool count, tool side-effects, and per-call cost.
- **Detection** — Locate the agent loop (typically `while`, recursive `run()`, or `for step in range(N)`). Inspect `N` and any token-budget accumulation. Flag if `N` is unbounded, >50 without justification, or absent. Also flag if a token counter is incremented but never compared to a budget.
- **Vendor specificity** — Vendor-agnostic.
- **False-positive risk** — Genuinely long-horizon agents (research agents) may legitimately need higher ceilings — but should have a token budget even if step count is high.

## Small-vs-Large Model Anti-Patterns

### Chain-of-thought prompting on small models

- **Pattern** — Haiku/Mini/Nano/Flash-Lite class models prompted with "think step by step," `<thinking>` blocks, or extensive reasoning scaffolds; or used in a `reasoning_effort=high` mode that does not exist for the tier.
- **Impact** — Small models produce verbose reasoning that *doesn't* improve accuracy (and often hurts it on simple classification), inflating cost and latency 3x-10x with no quality gain.
- **Applies-to (kind):** both — Applies to both API-call code paths and runtime-instruction artifacts (the failure mode is about prompt design / security / eval discipline, not the API surface).
- **Applies-to** — Small-tier models on simple tasks. Inverse problem (no CoT on a reasoning-heavy task with a frontier model) is also worth flagging.
- **Detection** — Cross-reference model tier (from model ID) against prompt content. Flag CoT scaffolds + Haiku/Mini/Nano/Flash-Lite. Conversely, flag terse "just answer" prompts to Opus/o-series for genuinely hard reasoning tasks.
- **Vendor specificity** — Vendor-agnostic.
- **False-positive risk** — Some small-model tasks (light arithmetic, simple multi-hop) do benefit from CoT. Domain judgement applies.

### Frontier-model prompt patterns ported to small models

- **Pattern** — A prompt designed for Opus/GPT-5 (10+ instructions, nested role/context/format XML, 5+ few-shot examples, complex output schema) re-used verbatim with `model="haiku"` for cost reasons, with no re-design.
- **Impact** — Small model under-performs the original benchmark; team concludes "Haiku can't do this" when in fact the prompt is mis-calibrated. False migration failure.
- **Applies-to (kind):** both — Applies to both API-call code paths and runtime-instruction artifacts (the failure mode is about prompt design / security / eval discipline, not the API surface).
- **Applies-to** — Cost-optimization PRs that swap model IDs without revisiting the prompt.
- **Detection** — Look at PRs / git history for model-ID swaps where the prompt template was untouched. Flag long, multi-stage prompts being pointed at a small-tier model. Check whether a small-model-specific prompt variant exists.
- **Vendor specificity** — Vendor-agnostic.
- **False-positive risk** — Genuinely simple prompts work across tiers without modification. The flag is about *complex* prompts.

## Research Notes & Sources

Most authoritative (vendor docs, peer-reviewed taxonomies, primary post-mortems):

- Anthropic prompt caching docs — https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Anthropic prompt engineering / XML structure — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- Anthropic XML tags guide — https://console.anthropic.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags
- OpenAI structured outputs guide — https://platform.openai.com/docs/guides/structured-outputs
- Google Gemini deprecations — https://ai.google.dev/gemini-api/docs/deprecations
- Google Gemini models — https://ai.google.dev/gemini-api/docs/models
- OWASP Top 10 for LLM Applications 2025 — https://genai.owasp.org/llm-top-10/ and https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf
- "Failure Modes in LLM Systems: A System-Level Taxonomy" (arXiv 2511.19933) — https://arxiv.org/abs/2511.19933
- "Where to show Demos in Your Prompt: A Positional Bias of In-Context Learning" (arXiv 2507.22887) — https://arxiv.org/pdf/2507.22887
- "How Do LLMs Fail In Agentic Scenarios?" (arXiv 2512.07497) — https://arxiv.org/pdf/2512.07497

Practitioner / industry write-ups (recent, concrete, generally credible):

- AppScale, "LLM Failure Modes in Production: Complete Root Cause Guide 2026" — https://appscale.blog/en/blog/llm-failure-modes-in-production-the-complete-root-cause-guide-2026
- Datadog, "State of AI Engineering" — https://www.datadoghq.com/state-of-ai-engineering/
- TianPan, "The Context Stuffing Antipattern" — https://tianpan.co/blog/2026-04-09-context-stuffing-antipattern-llm-production
- Mager, "Claude: How prompt caching actually works" — https://www.mager.co/blog/2026-04-29-claude-prompt-caching/
- InstaTunnel, "Agentic Resource Exhaustion: The Infinite Loop Attack" — https://medium.com/@instatunnel/agentic-resource-exhaustion-the-infinite-loop-attack-of-the-ai-era-76a3f58c62e3
- Yamishift, "LLM Tool-Calling in Production: Rate Limits, Retries, and Infinite Loop" — https://medium.com/@komalbaparmar007/llm-tool-calling-in-production-rate-limits-retries-and-the-infinite-loop-failure-mode-you-must-2a1e2a1e84c8
- Knight Li, "Claude Opus 4.7, Sonnet 4.6, and Haiku 4.5: Model Selection Guide" — https://knightli.com/en/2026/05/08/anthropic-claude-model-lineup/
- Keysight, "When Prompts Leak Secrets" — https://www.keysight.com/blogs/en/tech/nwvs/2025/08/04/pii-disclosure-in-user-request
- Promptfoo, "Sensitive Information Disclosure in LLMs" — https://www.promptfoo.dev/blog/sensitive-information-disclosure/
- OpenAI Dev Community (multiple threads on structured-output regressions) — https://community.openai.com/t/invalid-json-response-when-using-structured-output/1121650 and https://community.openai.com/t/chat-completion-responses-suddenly-returning-malformed-or-inconsistent-json/1368077

More marketing-flavored (used sparingly, cross-checked against primary sources):

- Vendor blog posts from observability / gateway products (Langfuse, Traceloop, Helicone, Braintrust, Maxim) — useful for typical instrumentation patterns but biased toward their own SKU.
- Several "Top 10 X Tools 2026" listicles surfaced in search; treated as signal-of-existence only, not as primary evidence.

Cross-cutting themes worth deeper follow-up:

1. **Cache integrity as a first-class concern.** Multiple distinct failures (dynamic content in cache region, no cache-hit telemetry, breakpoint on user message) all converge on the same root: caching is opaque, and teams ship it without measurement. A Critic rule that checks *both* breakpoint placement and usage-field logging covers most of the surface.
2. **Field-name asymmetry across vendors** (`finish_reason` vs. `stop_reason`; `refusal` field separate vs. embedded; cache-token sub-fields) drives a class of bugs that vendor-agnostic wrappers paper over without fixing. Detection rules must be vendor-aware.
3. **Agent step-count and token budgets are absent from most projects** that adopt agentic patterns. This is the cheapest-to-detect, highest-impact gap surfaced in this research.
4. **Migration readiness is structurally weak.** Hard-coded model IDs + no deprecation watch + no role abstraction = compound brittleness as the 2025-2026 deprecation cadence accelerates.
