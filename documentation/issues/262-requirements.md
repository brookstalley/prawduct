# Issue #262 — Cross-product governance stats: Requirements

`status: revised 2026-10-03 · stage: ready · area: governance/telemetry · added: 2026-08-03 ·
issue: https://github.com/brookstalley/prawduct/issues/262`

Related: `.prawduct/artifacts/roi-audit-2026-10-02.md` (the program this closes), #950 (the
collector, whose ingestion criterion moved here), `collector/README.md` § Bundle format (the
contributed data's input contract), `plugin/docs/governance-telemetry.md` (`stats` and
`contribute`, whose definitions this reuses).

## Problem

Whether a plugin release cost more or protected more than the last one is decided per product
today, because nothing pools governance stats across products. Two kinds of data now exist to
pool: each product's own clone-shared evidence store, which `prawduct-hook stats` reads per plugin
version, and the anonymous weekly reports contributors send to the collector, published as daily
bundles. Nothing reads the bundles, so the contribution channel has no consumer.

## Grounding facts

- The evidence store, not the ledger, is the version-aware source: every fact carries
  `actor.plugin`, and ledger lines carry no plugin version (audit § What was read).
- A contributed report is one ISO week of one product for one plugin `major.minor` (plus a `dev`
  flag), coarsened to the allowlist in `plugin/lib/contribution_schema.json`. It has no mode, model
  or product axis, by design.
- `contribution.build_report` already turns one product-week of evidence into exactly that shape.
- Bundle lines carry no identity, so duplicates are distinct contributions and poisoning cannot be
  detected (collector README).

## Decisions

**1. One shape, keyed by plugin version (owner, 2026-10-03).** Local products are converted into
the same weekly reports the contribution client would build, and pooled with contributed reports.
That makes local and contributed data commensurable by construction, with one definition of every
metric. This replaces the August design, which read ledgers and broke review cost down by mode and
model after adding a `plugin` field to ledger lines. That field had no reader once the evidence
store became the version-aware source, and `review-stats` already gives the mode and model breakdown
per product.

**2. Where it lives.** A `prawduct-hook aggregate-stats` command, surfaced from `/prawduct:janitor`
Step 1, generated on demand. Not a committed document and not a separate skill.

**3. Local products are named, never discovered.** The command reads only product directories the
operator names at invocation, as arguments or in a `--from-file` list. No list of an owner's
products is committed anywhere.

**4. Contributed data leaves only as consented.** The audit amended the August posture ("the
ledger never leaves the machine"): only the coarsened, allowlisted report may leave, and only with
the product's consent (#949). The aggregator reads what was published; it sends nothing.

## Requirements

MUST unless marked SHOULD.

- **AGG1** For each named product, build one report per settled ISO week and plugin version from
  its evidence store, with the contribution client's own builder, floors and coarsening.
- **AGG2** Read contributed reports from local bundle files or directories, or fetch every bundle
  from the collector when asked to. Opening a socket happens only on that explicit request.
- **AGG3** Re-validate every bundle line against the allowlist, and count refused lines rather than
  trusting the publisher. Duplicate lines are kept.
- **AGG4** Group by plugin version (`major.minor`, with dev builds apart) and report each metric's
  sample size, median and trimmed mean, plus how many reports came from local products and how many
  were contributed. No single line decides a number.
- **AGG5** When contributed data is included, a local window that clone has already sent is left
  out, so it is not counted twice.
- **AGG6** A named product that cannot be read is skipped with a reason, and the rest still report.
  Two paths sharing one clone's store count once.
- **AGG7** `--json` output has a versioned top-level shape (`schema_version`).

## Acceptance

- [ ] Local products and collector reports render in one view (the criterion carried from #950).
- [ ] The view reads no product the operator did not name, and opens no socket unless asked to.
- [ ] Every number is labelled with its plugin version, and none pools versions.
- [ ] A refused or duplicate bundle line is counted, never silently dropped or merged.

## Scope-out

- A mode or model axis across products: `review-stats` covers it per product.
- Persisting aggregated results or trends.
- Weighting reports by product volume. Each report is one product-week, and the view says so.
- Escape attribution (B5, #951).
