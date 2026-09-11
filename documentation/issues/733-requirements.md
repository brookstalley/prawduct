# Issue #733 — Governance: Let a Product Declare Its Consumer Release Digest: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-09-03 · source:
scheduled backlog session · issue: https://github.com/brookstalley/prawduct/issues/733`

Related: #576 / `release_version_files:` (the declaration-shape precedent this item follows and
departs from), #259 and #702 (prawduct-side digest checks — explicitly out of scope here), PR
#734 / `fix/release-gate-blindness` (shipped the two prawduct-only checks this item generalizes).

## Problem

`check_releasability`'s two digest checks — does the release's open section carry a real
headline, and does it name every shipping scope — are prawduct-only. `_DIGEST_REL_PATH` is
literally `plugin/CHANGELOG.md`, and both checks are gated behind `_ships_the_plugin_tree`
(`plugin/lib/release_readiness.py:415-438`), which is true only for prawduct's own repo. A
governed product gets the suite verdict and the build-plan coverage check, but nothing verifies
its own consumer-facing release notes — exactly the gap prawduct itself shipped through twice
(v2.1.6: tagged with no digest section at all; v3.4.0: section present but still carrying the
previous cut's placeholder headline — both named in `_headline_advisory`'s docstring).

The fix is not a new path parameter. `release_version_files:` (#576) already proves a product can
declare a **path**; what a consumer digest needs in addition is a **keying rule** — a way of
saying "this is the section of the file currently being written for the next release" — because
prawduct's own procedure ("the topmost `## ` heading, renamed to the release number at the cut")
is one specific editorial convention, not a property every changelog has. A declaration that
named only a path would silently impose that convention on a product that doesn't follow it, and
the failure mode is a **false all-clear**: the check would locate the wrong section, find it has
a real (old) headline and real (old) scope mentions, and report the release ready when the actual
pending section — wherever it really lives in the file — was never examined at all. That is the
exact shape both existing checks exist to catch, just moved one layer up.

## Grounding facts

Re-verified against the current tree (v3.4.1-dev, 2026-09-03):

- **The two checks and their subject, precisely.** `_headline_advisory` (`release_readiness.py:
  542-579`) flags an open section with no non-heading, non-empty first line, or one still
  carrying `_SEEDED_HEADLINE` (the scaffold placeholder). `_coverage_advisory` (`:582-620`) flags
  a release-pending scope whose slug (or de-hyphenated words) does not appear in the open
  section's text (`_digest_mentions`, `:483-516` — deliberately bounded matching, not substring,
  because a false *pass* here is the failure this whole mechanism exists to prevent). Both read
  from one call to `_read_digest` + `_open_digest_section` (`:441-480`), so the shared subject is
  a single `(heading, body)` pair — "the open section" — not two independent reads.
- **"The open section" is found by pure position today, and the module's own docstring already
  names the generalization gap.** `_open_digest_section` returns the **topmost** `## ` heading
  found, full stop (`:455-480`) — no check that the heading is *unshipped* rather than a stale
  leftover. `_digest_advisories`'s docstring states the reason this stayed prawduct-only outright:
  *"these checks ask about the section this release is being written into, and 'the topmost `## `,
  renamed to the release number at the cut' is prawduct's own release procedure rather than a
  property of changelogs. A declaration carrying only a path would silently impose that procedure
  on every product that set it, and the failure would be a false all-clear"* (`:641-652`). This
  item's whole job is answering the question that docstring poses.
- **Prawduct's own convention is self-verifying in a way pure position is not, and the mechanism
  is visible in the file today.** `plugin/CHANGELOG.md`'s open heading currently reads `##
  v3.4.1-dev.2` — the `-dev.N` suffix is what marks it *not yet cut*; the heading a release
  actually ships under has no such suffix (confirmed against the file's own second line: "this
  section is renamed to the release number at the cut"). The current code does not check this
  suffix at all — it trusts positional-topmost unconditionally — but the suffix is the latent
  signal that makes prawduct's own case safe in practice: a repo that forgets to rename at cut
  would show a `-dev.N`-suffixed heading in a *tagged* release, which is a different, detectable
  defect (out of scope here — #702/#259 own prawduct-side checks).
- **`release_version_files:` is the shape precedent, and its own module explains exactly why
  "declare a path" was sufficient there but is not sufficient here.**
  `plugin/lib/release_verification.py:69-90` (`VersionFile` NamedTuple: `path`, `fmt` — a
  *structural shape*, `bare`/`json`/`toml` — plus `key`, a dotted path descended literally).
  Version files need no keying rule because the value being checked (a version string) is
  identified by *structure* (a key path into a parsed document) — there is no "which of several
  candidate sections is the live one" question, because a version file has exactly one version
  field at a time. A changelog has exactly the opposite shape: one file, many headings, and the
  question is which one is *live right now* — structure alone (path + format) cannot answer that,
  which is the keying rule this item must add on top of the path.
- **The declaration is read from the release's own tree for version files, and the same rule
  must govern the digest declaration for the same reason.**
  `release_verification.py:14-24`: "what a release shipped is a fact about the tree that release
  names… that rule governs the `release_version_files:` declaration too... so the declaration is
  read from `<tag>:.prawduct/project-state.yaml`." A digest-keying declaration is exactly the same
  kind of fact — which convention a *given release* followed — so it must be read the same way:
  from the release's own tree, not the working tree, with an undeclared-at-that-tag release
  falling back to "unverifiable" rather than guessed.
- **A live false positive is already recorded and is informative, not disqualifying.** Issue
  comment (2026-09-01): against prawduct's own repo, the coverage check reports 1 of 14 scopes
  covered, and one of the 13 "misses" is a scope (`release-gate-blindness`) whose notes exist but
  don't contain the slug or its words — the documented fuzzy-match limitation
  (`_digest_mentions`'s own docstring), tolerable only because the check is advisory and never
  touches the exit code. This item's generalized version inherits the same advisory posture and
  the same known limitation — it is not asked to fix fuzzy matching, only to let another product
  opt in to the same imperfect-but-useful check.
- **No declaration mechanism exists today.** `project-state.yaml` has no key for this; the two
  checks are reachable only through the hardcoded `_DIGEST_REL_PATH` + `_ships_the_plugin_tree`
  gate. This is greenfield wiring onto the `release_version_files:` precedent, not a rework of an
  existing declaration reader.

## Decisions

**1. The keying rule is a declared strategy, not an inferred one — and "positional topmost" is
not offered as a general strategy.** Two named strategies, because two real conventions were
found in the wild during grounding, and both are checkable without parsing prose:

   - **`sentinel-heading`** — the product declares a fixed heading text (e.g. `## [Unreleased]`,
     the Keep a Changelog convention) that is never renamed; the open section is whatever
     currently sits under the first heading matching that text (case-insensitive, exact after
     stripping the `## ` marker). This is self-verifying by construction: the sentinel text is
     reserved and can never coincide with a shipped version heading, so there is no position for a
     stale section to hide in — either the sentinel exists (an open section is unambiguously
     found) or it does not (falls through to the existing "no section to read" NOTE path,
     `_digest_advisories:658`).
   - **`open-heading-pattern`** — the product declares a regex that only an *unshipped* heading
     satisfies (prawduct's own case, generalized: `-dev\.\d+$` or similar), and the open section is
     the **topmost** heading matching that pattern. This generalizes prawduct's own convention
     correctly *because* the pattern itself is the self-verifying signal the current code lacks —
     the positional topmost-heading behavior stays prawduct's own hardcoded path (Decision 2
     below), but a product opting in through this strategy gets the same shape with its check made
     structural instead of assumed.

   Plain positional-topmost with **no** distinguishing pattern is not offered as a declarable
   option: it is exactly the shape the problem statement rejects, since nothing would stop it from
   silently keying onto an already-shipped section the moment a product's editorial discipline
   lapses even once.

**2. Prawduct's own checks are unchanged, per the issue's own acceptance criterion.** The
hardcoded `_DIGEST_REL_PATH` / `_ships_the_plugin_tree` path stays exactly as it is — it is not
migrated onto the new declaration mechanism, so prawduct's own release process carries zero risk
from this change. This item is additive: a *second*, declaration-driven path that other products
opt into; "declaring gets both checks; others unchanged" (the issue's own acceptance bullet) is
satisfied literally, not just in spirit.

**3. The declaration lives in `project-state.yaml`, keyed and read the same way
`release_version_files:` is — from the release's own tree, not the working tree.** Shape:

   ```yaml
   consumer_digest:
     path: CHANGELOG.md
     keying: sentinel-heading        # or: open-heading-pattern
     heading: "Unreleased"           # sentinel-heading: literal text (marker stripped, case-insensitive)
     pattern: '-dev\.\d+$'           # open-heading-pattern: regex tested against the heading text
   ```

   Exactly one of `heading` / `pattern` is required, matching the declared `keying` value; the
   other is rejected as a conflicting declaration rather than silently ignored (an operator who
   sets both meant something, and guessing which one wins is how a keying rule quietly stops
   matching what the operator thought they declared). Read via `<tag>:.prawduct/project-state.yaml`
   for a specific release, mirroring `release_verification.py`'s existing rule exactly (Grounding
   facts) — a release cut before the key existed reports the digest checks as unverifiable for
   that release, never guessed.

**4. Coverage and headline logic are reused verbatim; only section-location changes.**
`_headline_advisory` and `_coverage_advisory` (and `_digest_mentions`, `_section_headline`) take
`(heading, body)` today and stay unaware of how that pair was found — a declared product's
`(heading, body)` is produced by a new locator function selected on `keying`, not by a rewritten
copy of the existing checks. This is the same "don't reinvent the containment guard" posture the
715 (artifacts-dir) work applies to `plan_archive`'s guard — reuse the already-correct logic,
change only what genuinely varies.

**5. An undeclared product gets exactly what it gets today: nothing, silently.** No `NOTE` fires
for a product that never sets `consumer_digest:` — this is opt-in, and the issue's problem
statement is that the check should *exist* for a product that wants it, not that every product
must have consumer notes. `_ships_the_plugin_tree`'s prawduct-only gate is replaced, for the
generalized path, by "declaration present" as the equivalent gate — the same "no subject, no
check" shape, just keyed on a config presence test instead of a hardcoded file existence test.

## Requirements

MUST unless marked SHOULD.

- **DIG1** `project-state.yaml` supports a `consumer_digest:` mapping: `path` (repo-relative),
  `keying` (`sentinel-heading` | `open-heading-pattern`), and exactly one of `heading` / `pattern`
  matching the declared `keying`. Both required fields absent, or `keying` naming neither
  supported strategy → the declaration is invalid; invalid is reported (a WARNING at the point the
  digest checks would otherwise run), never silently treated as "undeclared."
- **DIG2** The declaration is read from the **release's own tree** — `<tag-or-candidate-ref>:
  .prawduct/project-state.yaml` — the same rule `release_verification.py` already applies to
  `release_version_files:`, not the working tree. A release cut before `consumer_digest:` existed
  reports the digest checks as **unverifiable** for that release, never inferred from the current
  declaration.
- **DIG3** A `sentinel-heading` locator finds the first `## `-prefixed heading whose stripped text
  matches the declared `heading` (case-insensitive, exact match after stripping the marker and
  surrounding whitespace) and returns `(heading, body)` for everything up to the next `## `
  heading or end of file — same shape `_open_digest_section` already returns, so downstream logic
  is untouched. No match → treated identically to today's "no `## ` section to read" case (a NOTE,
  not a crash, not a false pass).
- **DIG4** An `open-heading-pattern` locator finds the **topmost** `## `-prefixed heading whose
  stripped text matches the declared `pattern` (a regex, applied to the whole heading text) and
  returns the same `(heading, body)` shape. No match → same "no section to read" NOTE.
- **DIG5** `_headline_advisory` and `_coverage_advisory` are called unchanged (same function
  signatures, same `(heading, body)` input) for a declared product's located section — no
  duplicated or forked copy of either check.
- **DIG6** Prawduct's own `_DIGEST_REL_PATH` / `_ships_the_plugin_tree` path is untouched by this
  item — verified by the existing test suite for `release_readiness.py` passing unmodified.
- **DIG7** No declaration shape can cause the checks to silently examine the wrong section: an
  invalid or conflicting declaration (DIG1) refuses to run the checks and says why, rather than
  falling back to a guess; a `sentinel-heading` declaration can never match a shipped version
  heading (the sentinel text is a fixed literal, disjoint from any version string by construction);
  an `open-heading-pattern` declaration is the operator's own assertion of which headings are
  "still open," so its correctness is the operator's to get right when they write the pattern — the
  same trust boundary `VersionFile.key` already accepts for `release_version_files:`.
- **DIG8** A product with no `consumer_digest:` declared sees no new advisory output — behavior is
  byte-identical to today for every repo that has not opted in.

## Acceptance

- [ ] The keying rule is stated as a requirement (discovery) before any code — this document
      (Decision 1, DIG1/DIG3/DIG4).
- [ ] Declaring gets both checks; others unchanged (Decision 2/5, DIG5/DIG6/DIG8).
- [ ] No declaration shape can yield a false all-clear (Decision 1/3, DIG1/DIG2/DIG7).

## Scope-out (this item)

- The prawduct-side checks themselves (#702, #259) — not touched, per the issue's own scope-out.
- Any code — this item is requirements only, per the issue's own acceptance bullet ("no code ahead
  of the requirement").
- A third keying strategy beyond the two named in Decision 1. If a product's convention fits
  neither `sentinel-heading` nor `open-heading-pattern`, that is new discovery for a future item,
  not a gap this one silently papers over with a catch-all "positional" fallback.
- Retiring `_coverage_advisory`'s fuzzy-match false-positive rate — inherited as-is (Grounding
  facts), tracked separately per the linked issue comment's own framing ("retirable on its own
  emitted evidence").
- Validating an `open-heading-pattern` declaration's regex against the product's actual history at
  declaration time (e.g., "does this pattern ever match more than the intended headings") — DIG7
  places that correctness burden on the operator, the same way `release_version_files:`'s `key`
  path already does; a linting pass over the declared pattern is a reasonable follow-on, not
  required here.

## Evidence / references

- `plugin/lib/release_readiness.py:415-438` (`_ships_the_plugin_tree`), `:441-480`
  (`_read_digest`, `_open_digest_section`), `:483-620` (`_digest_mentions`, `_section_headline`,
  `_headline_advisory`, `_coverage_advisory`), `:623-659` (`_digest_advisories`, whose own
  docstring states the keying-rule gap this item resolves).
- `plugin/lib/release_verification.py:1-100` — `VersionFile`, `_DECLARATION_KEY`
  (`release_version_files`), and the module docstring's rule that a release's declaration is read
  from that release's own tagged tree — the precedent DIG2 copies directly.
- `plugin/CHANGELOG.md:1-19` — confirms prawduct's live convention in the current tree (`##
  v3.4.1-dev.2`, "this section is renamed to the release number at the cut") and the latent
  `-dev.N` distinguishing signal Decision 1's `open-heading-pattern` strategy generalizes.
- Issue #733, comment 2026-09-01 — the live 1-of-14 coverage baseline and the one documented
  false positive, carried into Scope-out as inherited, not fixed, behavior.
- Issue #576 / `release_version_files:` — the shape precedent (`path` + structural descriptor)
  this item extends with a keying field, and the reason the extension is a new field rather than
  reusing `fmt`/`key` unchanged (a changelog's "which section" question has no analog in a
  version file's "which key" question).
