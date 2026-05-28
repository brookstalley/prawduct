# Open 6 — Model-Tier Registry: Draft + Coverage Check

The Critic's adaptive applicability reasoning depends on classifying each role's model by **tier** (small / mid / frontier). This file is the draft tier registry the framework will ship — per-vendor, including recently-retired models since real codebases continue to reference them through deprecation cycles. It is also the live target of Open 6's coverage check: ≥95% of models in the test repos must have a clear tier classification.

**Refresh cadence:** Per `prompt-management-requirements.md` §8.2, this file is on a quarterly refresh schedule. Vendor model lineups move fast — the spec accepts that the registry will lag practice and emits NOTE-level findings when a project's model ID isn't in the table.

**Last refreshed:** 2026-05-28 (informed by `documentation/research/vendor-prompt-sources.md`, fetched May 2026; Open 1 model-ID inventory from metallm + discodon).

---

## 1. Anthropic (Claude)

Lifecycle stages per Anthropic's policy: Active → Legacy → Deprecated → Retired (at least 60 days notice before retirement).

| Tier | Active (2026-05) | Recently retired / scheduled |
|---|---|---|
| **Frontier** (complex reasoning, agentic, frontier benchmarks) | `claude-opus-4-7`, `claude-opus-4-6`, Mythos Preview (limited — Project Glasswing) | `claude-opus-4-5` (Active but older), `claude-opus-4` (retires 2026-06-15), `claude-3-opus` (retired) |
| **Mid** (balanced cost/capability; production default) | `claude-sonnet-4-6`, `claude-sonnet-4-5` | `claude-sonnet-4` (retires 2026-06-15), `claude-3-7-sonnet` (retired 2026-05-11), `claude-3-5-sonnet` (retired) |
| **Small** (high-volume, classification, simple tasks) | `claude-haiku-4-5` (current; snapshot e.g., `claude-haiku-4-5-20251001`) | `claude-3-5-haiku` (retires 2026-07-05), `claude-3-haiku` (retires 2026-08-23) |

**Notes:**
- Anthropic's deprecation cadence is aggressive (~6-12 months per generation in 2025-2026). Tier classifications can shift mid-cycle as new generations land — e.g., when Opus 5.x ships, Opus 4.6/4.7 will likely move to Mid.
- Snapshotted IDs (`claude-haiku-4-5-20251001`) and base aliases (`claude-haiku-4-5`) are both valid for tier classification — the suffix is a determinism mechanism, not a tier signal. See FM-23 (floating-alias usage).
- Mythos Preview is currently limited-availability under Project Glasswing — not a production tier yet, but worth tracking.

---

## 2. OpenAI (GPT family)

Lifecycle: Deprecated (scheduled shutdown) vs Legacy (no updates, still working). Typical 6-12 month notice; Assistants API got 12 months.

| Tier | Active (2026-05) | Recently retired / scheduled |
|---|---|---|
| **Frontier** (reasoning-heavy, complex agents, long context) | `gpt-5.5`, `gpt-5.4` (best general default per docs as of April 2026), o-series reasoning models (e.g., `o5`, `o4-mini` if present in your codebase) | `gpt-4-turbo` and other `gpt-4-*` variants (sunset 2026-10-23) |
| **Mid** (balanced; default for most production work) | `gpt-5.4-mini`, `gpt-oss-120b` (Apache-2.0 open weights, frontier-quality benchmarks, run anywhere) | `gpt-4o` (still serviceable but plan migration), `gpt-4o-mini` |
| **Small** (high-volume, low-cost) | `gpt-5.4-nano`, `gpt-oss-20b` (Apache-2.0 open weights) | `gpt-3.5-turbo` (sunset 2026-10-23) |

**Notes:**
- The Responses API supersedes Chat Completions + Assistants. The **Assistants API shuts down 2026-08-26.** Codebases still using it need a migration path.
- `gpt-oss-120b` and `gpt-oss-20b` (open-weight Apache-2.0 releases from OpenAI) sit awkwardly across "OpenAI vendor" and "open/local" — host them anywhere. Tier classification follows benchmark performance, not the vendor relationship.
- Floating-alias risk: `gpt-4o` (unversioned) is a vendor alias; pin to a dated snapshot (`gpt-4o-2024-08-06`-style) when determinism matters. See FM-23.

### Non-chat modalities (OpenAI)

| Modality | Active (2026-05) | Recently retired / scheduled |
|---|---|---|
| Image generation | `gpt-image-1`, `gpt-image-1-mini`, `chatgpt-image-latest` (alias — avoid for determinism) | `dall-e-2`, `dall-e-3` (retire 2026-05-12 — **already past**, plan migration if still referenced) |
| Speech-to-text | `whisper-1` | (no deprecation announced) |
| Embeddings | `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002` (legacy) | — |

---

## 3. Google (Gemini)

Lifecycle: Stable / Latest stable / Preview / Experimental. 2-week notice on `latest` alias changes; 1-month "new access blocked" window before retirement.

| Tier | Active (2026-05) | Recently retired / scheduled |
|---|---|---|
| **Frontier** (reasoning, long context, agentic) | `gemini-3.5-pro`, `gemini-3.x-pro` (current production reasoning) | `gemini-2.5-pro` (deprecation target 2026-10) |
| **Mid** (high-volume default, default tier) | `gemini-3.5-flash` (announced Google I/O 2026-05-19), `gemini-3.x-flash` | `gemini-2.5-flash` (deprecation target 2026-10), `gemini-2.0-flash` variants (retired) |
| **Small** (cheapest hosted, edge use cases) | `gemini-flash-lite` (3.x), `gemini-nano` (on-device) | `gemini-2.5-flash-lite` |

### Non-chat modalities (Google)

| Modality | Active (2026-05) | Recently retired / scheduled |
|---|---|---|
| Embeddings | `text-embedding-005` (or successor) | `text-embedding-004` (retired 2026-01-14) |
| Vision | Built into Pro/Flash tiers; no separate model ID typically | — |

**Notes:**
- Google's tier nomenclature: Pro (most capable, agentic/reasoning), Flash (high-volume default), Flash-Lite (cheapest), Nano (on-device). Less granular than Anthropic or OpenAI.
- Implicit caching on Gemini 2.5+ means cost-control concerns differ from Anthropic (no explicit `cache_control` breakpoint to misplace). FM-6 still applies if the stable prefix isn't structured for cacheability.

---

## 4. Open / Local (Llama, Qwen, GLM, gpt-oss, Phi, Mistral)

Tier classification follows parameter count + benchmark performance, not vendor relationships. Open weights are never deprecated (HF retains all revisions).

| Tier | Representative (2026-05) | Notes |
|---|---|---|
| **Frontier** (70B+ active params, frontier benchmarks) | `llama-4-maverick` (~400B MoE), `qwen-3.6-70b`, `glm-5.1-70b`, `gpt-oss-120b` (also listed under OpenAI), `deepseek-v3-700b` (if present) | Often deployable on multi-GPU; cost calculus differs from hosted (server time, not per-token) |
| **Mid** (20-70B; production quality on most tasks) | `llama-4-scout` (~109B MoE), `qwen-3.6-32b`, `mistral-small-3`, `mistral-medium-3` | Common single-GPU deployment tier |
| **Small** (1-20B; classification, embeddings, edge) | `llama-3.2-8b`, `qwen-3.6-7b`, `phi-4-mini`, `mistral-tiny`, `gemma-3-7b` | Phi-class is Microsoft's open-weight competitor |
| **Tiny** (<1B; on-device, embedded) | `qwen-3.6-0.5b`, `phi-2`, `gemma-2b` (legacy) | Often fine-tuned for narrow tasks |

**Notes:**
- Tier is benchmark-driven, not parameter-driven strictly — `llama-4-scout` (109B MoE) is Mid because its *active* params are similar to dense Mid models, not because total parameter count is in the Mid range.
- Open weights have no deprecation; "active" here means "actively recommended by maintainers." A model from 2024 is still callable but may not be the best choice.

---

## 5. Aggregator-mediated (OpenRouter, LiteLLM, Portkey, Helicone)

Aggregators don't have their own tiers — the tier is determined by the upstream model ID. The Vendor convention is `<upstream> via <aggregator>` (e.g., `Anthropic via OpenRouter` with model `anthropic/claude-haiku-4-5-20251001` → Anthropic Small tier).

When the upstream varies per-call (e.g., discodon's `config.openrouter.default_model` is set per-entity), the Critic falls back to cross-vendor checks rather than tier-specific reasoning.

**Common aggregator model-ID format** (OpenRouter convention):
- `<vendor>/<model-id>` — e.g., `anthropic/claude-haiku-4-5-20251001`, `openai/gpt-4o-mini`, `google/gemini-flash-3.5`, `meta/llama-4-scout`

---

## 6. Coverage check against Open 1 test repos

Per the Open 6 success criterion (≥95% of models in the test repos have a clear tier classification), evaluate models found by the Open 1 detection survey.

### metallm

| Model ID | Tier classification | Notes |
|---|---|---|
| `claude-opus-4-5` | Anthropic Frontier (active, older) | Reference example from the agent's report — actual production model is DB-resolved |
| `gpt-4o` | OpenAI Mid (Legacy candidate) | Plan migration; sunset announcements pending generation-wide |
| `dall-e-2`, `dall-e-3` | OpenAI Image (retired 2026-05-12) | **Past retirement date** — any code still calling these will fail; flag in migration advisory |
| `gpt-image-1` | OpenAI Image (current) | — |
| `chatgpt-image-latest` | OpenAI Image (alias) | Avoid for determinism — see FM-23 |
| `whisper-1` | OpenAI STT (current) | — |
| (config-driven model identities) | N/A — DB-resolved | Per Q10 in `prompt-management-requirements.md`, declared as `Model: db:models.name_api` |

**metallm coverage: 6/6 specific IDs classified.** 100%. The config-driven entries aren't single models and don't count toward coverage.

### discodon

| Model ID | Tier classification | Notes |
|---|---|---|
| `anthropic/claude-haiku-4-5-20251001` | Anthropic Small (via OpenRouter) | Snapshot pinning — good practice |
| `openai/gpt-4o-mini` | OpenAI Mid (via OpenRouter) | — |
| `gpt-image-1-mini` | OpenAI Image (current) | — |
| `config.aria.frontier_model` | N/A — config-driven | Resolves to a specific frontier ID at runtime; declare as `Model: config:aria.frontier_model` |
| `config.aria.c4_judge_model` (default `openai/gpt-4o-mini`) | OpenAI Mid (via OpenRouter, when default) | Default is classifiable; per-project overrides require lookup |
| `config.openrouter.default_model` | N/A — config-driven | — |

**discodon coverage: 3/3 specific IDs classified, plus the default of `c4_judge_model`.** 100% on explicit IDs.

### Aggregate coverage

- **9/9 specific model IDs** referenced in the two test repos have a clear tier classification. **100%, well above the 95% threshold.**
- Config-driven references (4) are correctly handled by the new `Model: config:<path>` / `Model: db:<table>.<column>` convention from §5.3 D16 — not a coverage gap because they don't denote a single model.

---

## Verdict against Open 6 success criterion

| Criterion | Status | Notes |
|---|---|---|
| ≥95% of models in test repos have a clear tier classification | **PASS (100%)** | All 9 specific IDs in metallm + discodon mapped to a tier. Config-driven references are handled by the schema's `config:` / `db:` placeholder convention rather than the tier table. |

---

## Observations

1. **Image-gen, STT, and embeddings need their own classification axis, not "tier".** Lumping `gpt-image-1` into "small/mid/frontier" doesn't fit — those tiers are about chat-completion capability. The registry handles this by putting non-chat modalities in dedicated sub-tables (§2, §3). The Critic's adaptive reasoning already considers `Pattern: vision / embedding / STT` as a classification dimension (Appendix A Guideline 1); the failure-mode subset narrows automatically (image-gen roles don't get FM-2 instructions-after-context applied — there's no chat context).

2. **Recently-retired models are a real coverage requirement, not optional.** metallm references `dall-e-2/3` (retired 2026-05-12 — *past retirement date* as of this run). A tier table that only covers current models would miss this. The registry must keep deprecated/retired entries until they're truly gone from real codebases (~12-18 months post-retirement).

3. **Aggregator-mediated calls don't need their own tier table.** Just parse the upstream from the model ID (`anthropic/...` → Anthropic; `openai/...` → OpenAI) and look up there. This was the spec's intent (D17) and it holds empirically.

4. **Floating aliases appear in real code.** discodon uses `config.openrouter.default_model` which resolves to a specific ID at runtime — not technically a floating alias (FM-23) but functionally similar from the Critic's perspective. The new `Model: config:<path>` convention (Q10) lets the artifact declare this honestly rather than pretending it's pinned.

5. **The "active, older" classification is useful.** `claude-opus-4-5` is still Active per Anthropic's published lifecycle, but it's a generation behind Opus 4.7. Real codebases will keep using it for months after a newer generation ships, since switching has its own cost. The registry should signal "Active but consider upgrade path" rather than treating it as deprecated.

6. **Refresh cadence in practice:** between the May 2026 vendor-sources snapshot and today (also May 2026), Gemini 3.5 Flash was announced (Google I/O May 19). The registry is only 9 days behind on that line and already mentions it. Quarterly refresh (per §8.2) is enough cadence as long as the Critic is explicit when it doesn't recognize a model ID — "this ID isn't in the registry; refresh may be due."

---

## Status

- [x] Open 6 first run 2026-05-28. Coverage 100% against current test repo set (metallm + discodon). Registry shipping-ready as v1; quarterly refresh schedule begins.
