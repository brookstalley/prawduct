"""Tests for lib/backlog/ids.py — ID normalization (ID-1, D4/DM4).

The four accepted spellings normalize to one canonical ``owner/repo#number``,
short/shell forms resolve same-owner only, and normalization is idempotent.
"""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from lib.backlog import ids  # noqa: E402


class TestNormalizeFourSpellings:
    """ID-1 — the four accepted spellings all normalize to canonical."""

    CANON = "octo/repo#123"

    @pytest.mark.parametrize(
        "spelling",
        [
            "octo/repo#123",  # canonical
            "repo#123",  # short, same-owner
            "repo/123",  # shell-friendly slash
            "repo-123",  # shell-friendly hyphen
        ],
    )
    def test_all_spellings_reach_one_canonical(self, spelling):
        result = ids.normalize_id(spelling, default_owner="octo")
        assert result.ok
        assert result.canonical == self.CANON
        assert result.owner == "octo"
        assert result.repo == "repo"
        assert result.number == 123

    @pytest.mark.parametrize(
        "spelling",
        ["octo/repo#123", "repo#123", "repo/123", "repo-123"],
    )
    def test_normalization_is_idempotent(self, spelling):
        once = ids.normalize_id(spelling, default_owner="octo")
        twice = ids.normalize_id(once.canonical, default_owner="octo")
        assert twice.canonical == once.canonical

    def test_canonical_needs_no_default_owner(self):
        result = ids.normalize_id("octo/repo#7")
        assert result.ok
        assert result.canonical == "octo/repo#7"


class TestRepoNamesWithHyphens:
    """A repo name may itself contain hyphens; the number is the trailing group."""

    def test_hyphenated_repo_splits_on_last_hyphen(self):
        result = ids.normalize_id("my-repo-42", default_owner="octo")
        assert result.ok
        assert result.canonical == "octo/my-repo#42"

    def test_hyphenated_repo_hash_form(self):
        result = ids.normalize_id("my-repo#42", default_owner="octo")
        assert result.canonical == "octo/my-repo#42"


class TestShortFormNeedsOwner:
    """Short/shell spellings are same-owner only — no owner is a validation error, not a guess."""

    @pytest.mark.parametrize("spelling", ["repo#5", "repo/5", "repo-5"])
    def test_missing_owner_is_validation(self, spelling):
        result = ids.normalize_id(spelling)  # no default_owner
        assert not result.ok
        assert result.error == "validation"
        assert result.message


class TestBareNumberResolvesAgainstDefaultRepo:
    """A bare `123` or `#123` is the spelling an operator reads off a GitHub URL.

    It carries neither owner nor repo, so it resolves only when a full
    ``default_repo`` is supplied — a ``default_owner`` alone is not enough, and
    that distinction is the reason this form is separate from the short ones
    above. Before this form existed, a fully-disambiguating ``--repo owner/repo``
    still could not resolve the number, and the two failures named different
    things: `123` fell through every form to "unrecognized ID spelling" while
    `#123` reached the short-form branch with an empty left side and reported
    "malformed repo", which is the wrong defect — the input contains no repo at
    all.
    """

    @pytest.mark.parametrize("spelling", ["123", "#123", "  #123  ", "  123  "])
    def test_bare_number_resolves_with_a_default_repo(self, spelling):
        result = ids.normalize_id(spelling, default_repo=("octo", "repo"))
        assert result.ok
        assert result.canonical == "octo/repo#123"
        assert result.owner == "octo"
        assert result.repo == "repo"
        assert result.number == 123

    @pytest.mark.parametrize("spelling", ["123", "#123"])
    def test_bare_number_is_idempotent(self, spelling):
        # ID-1 holds for the new form: normalizing the canonical output again
        # reproduces it, so a caller may re-normalize without special-casing.
        once = ids.normalize_id(spelling, default_repo=("octo", "repo"))
        twice = ids.normalize_id(once.canonical, default_repo=("octo", "repo"))
        assert twice.canonical == once.canonical

    @pytest.mark.parametrize("spelling", ["123", "#123"])
    def test_default_owner_alone_does_not_resolve_a_bare_number(self, spelling):
        # An owner without a repo cannot name an item. This is the boundary that
        # keeps the bare form from silently guessing a repo.
        result = ids.normalize_id(spelling, default_owner="octo")
        assert not result.ok
        assert result.error == "validation"

    @pytest.mark.parametrize("spelling", ["123", "#123"])
    def test_the_message_names_the_missing_repo_not_a_malformed_one(self, spelling):
        # The defect this replaces reported "malformed repo in '#123'" — naming a
        # repo the input never contained, which sends the reader to fix the wrong
        # thing. The message must say what is absent.
        result = ids.normalize_id(spelling)
        assert not result.ok
        assert "malformed" not in result.message
        assert "repo" in result.message

    def test_a_non_numeric_hash_form_still_reports_the_number_defect(self):
        # `#abc` is not a bare-number form at all; it must keep reporting the
        # number as the defect rather than being recast as a missing repo.
        result = ids.normalize_id("#abc", default_repo=("octo", "repo"))
        assert not result.ok
        assert result.error == "validation"
        assert "digits" in result.message

    def test_zero_and_leading_zeros_behave_like_any_other_number(self):
        result = ids.normalize_id("007", default_repo=("octo", "repo"))
        assert result.ok
        assert result.number == 7
        assert result.canonical == "octo/repo#7"

    def test_an_explicit_spelling_still_wins_over_the_default_repo(self):
        # The default is a fallback for what the input omits, never an override.
        result = ids.normalize_id("other/elsewhere#9", default_repo=("octo", "repo"))
        assert result.ok
        assert result.canonical == "other/elsewhere#9"


class TestOneCanonicalPerItem:
    """ID-1 says one canonical string per item, and two spellings quietly broke it.

    Both predate the bare form and both are reachable from every spelling; the bare
    form is what made them reachable from the commonest one there is.
    """

    @pytest.mark.parametrize(
        "spelling",
        ["007", "#007", "repo#007", "octo/repo#007", "repo/007", "repo-007"],
    )
    def test_a_zero_padded_number_reaches_the_same_canonical_as_its_bare_one(self, spelling):
        # Pasting the caller's digits through meant `#007` and `#7` — one issue —
        # normalized to two different canonical strings, and every consumer keyed
        # on that string (the cache's `item.id`, the alias table, the redirect
        # walk) would treat them as two items.
        result = ids.normalize_id(spelling, default_owner="octo", default_repo=("octo", "repo"))
        assert result.ok, result.message
        assert result.canonical == "octo/repo#7"
        assert result.number == 7

    @pytest.mark.parametrize("spelling", ["１２３", "#１２３", "repo#１２３", "octo/repo#１２３"])
    def test_non_ascii_digits_are_not_a_number(self, spelling):
        """Python's `\\d` matches every Unicode decimal digit, so full-width digits
        parsed as a number and `int()` accepted them — producing a canonical id
        whose glyphs go into `repos/{owner}/{repo}/issues/{n}` at the transport,
        an id GitHub cannot resolve, from an input that looked numeric to every
        check on the way in. Ids are parsed out of issue-body text, so the source
        is attacker-writable for the same reason `_valid_segment` guards its own.
        """
        result = ids.normalize_id(spelling, default_owner="octo", default_repo=("octo", "repo"))
        assert not result.ok
        assert result.error == "validation"

    def test_ascii_digits_still_normalize(self):
        # The guard must not cost the legitimate case it shares a pattern with.
        result = ids.normalize_id("42", default_repo=("octo", "repo"))
        assert result.ok
        assert result.canonical == "octo/repo#42"


class TestRejections:
    def test_non_numeric_issue_number_rejected(self):
        result = ids.normalize_id("octo/repo#abc")
        assert not result.ok
        assert result.error == "validation"

    def test_owner_repo_without_number_rejected(self):
        # 'owner/repo' with no '#number' is not an item ID.
        result = ids.normalize_id("octo/repo", default_owner="octo")
        assert not result.ok
        assert result.error == "validation"
        assert "no issue number" in result.message

    @pytest.mark.parametrize("spelling", ["", "   ", "garbage", "#123"])
    def test_malformed_rejected(self, spelling):
        result = ids.normalize_id(spelling, default_owner="octo")
        assert not result.ok
        assert result.error == "validation"


class TestDotOnlySegmentsAreTraversal:
    """A segment of nothing but dots is not a name — it is a path traversal.

    Dots are legal *inside* an owner or repo (`my.repo`), so the segment pattern
    admits them; `.` and `..` slipped through with them. These segments are
    interpolated straight into `repos/{owner}/{repo}/…` at the transport, and the
    reachable source is attacker-writable — a `superseded_by` block field carries
    an id parsed from issue-body text, chased by `core.resolve_survivor`.
    """

    @pytest.mark.parametrize("spelling", ["../..#1", "octo/..#1", "../repo#1", "./repo#1"])
    def test_dot_only_segment_rejected(self, spelling):
        result = ids.normalize_id(spelling, default_owner="octo")
        assert not result.ok
        assert result.error == "validation"

    def test_dots_inside_a_name_still_normalize(self):
        # The guard must not cost the legitimate case it shares a pattern with.
        result = ids.normalize_id("octo/my.repo#7", default_owner="octo")
        assert result.ok
        assert result.canonical == "octo/my.repo#7"


class TestParseRepo:
    def test_valid_owner_repo(self):
        assert ids.parse_repo("octo/repo") == ("octo", "repo")

    @pytest.mark.parametrize("spec", ["", "norepo", "a/b/c", "octo/", "/repo"])
    def test_invalid_owner_repo(self, spec):
        assert ids.parse_repo(spec) is None


class TestPfxAliases:
    """The PFX-alias machinery (D4/DM4/§5): a hand-minted ``PFX-XXXX`` ↔ its
    permanent ``id:PFX-XXXX`` alias label. No new PFX is ever minted."""

    @pytest.mark.parametrize(
        "pfx",
        [
            "BKL-7M4Q",
            "ADR-12",
            "A-1",
            "DIS-0001",
            "P00-2001",
            # Multi-segment ids are ordinary hand-minted ids (~21% of real backlogs
            # carry one). ``is_pfx`` gates alias minting, so rejecting them here is
            # what leaves an item with no permanent identity at all.
            "MIG-M4-REMOVE",
            "AUD-TIMBRE-CALIB",
            "ENG-9V2K-F",
        ],
    )
    def test_wellformed_pfx_accepted(self, pfx):
        assert ids.is_pfx(pfx)

    @pytest.mark.parametrize(
        "token",
        [
            "",
            None,
            "nodash",
            "-1234",
            "BKL",
            "  ",
            "a b-1",
            # A bracketed date is exactly what the leading-letter rule keeps out —
            # multi-segment acceptance must not reach it.
            "2026-07-28",
            "FOO-",
            "FOO--BAR",
        ],
    )
    def test_malformed_pfx_rejected(self, token):
        assert not ids.is_pfx(token)

    def test_alias_label_roundtrips(self):
        assert ids.alias_label("BKL-7M4Q") == "id:BKL-7M4Q"
        assert ids.pfx_from_alias_label("id:BKL-7M4Q") == "BKL-7M4Q"

    def test_alias_label_tolerates_whitespace(self):
        assert ids.alias_label(" BKL-1 ") == "id:BKL-1"

    @pytest.mark.parametrize("name", ["stage:ready", "id:not a pfx", "id:", "notid:BKL-1"])
    def test_non_alias_label_returns_none(self, name):
        assert ids.pfx_from_alias_label(name) is None


class TestStoredRefsTakeNoDefault:
    """#754 — a ref parsed out of issue-body text resolves only when fully
    qualified. ``normalize_stored_ref`` owns that rule by signature, and the
    ``default_*`` keywords of ``normalize_id`` are confined to the operator-input
    functions by an AST allow-list, so a new body-reading site that passes a
    default fails here rather than relying on a reviewer to remember."""

    #: (module stem, top-level function) — the operator-input paths, where a
    #: caller-supplied default is correct.
    OPERATOR_INPUT = {("core", "resolve_ref"), ("cachequery", "resolve")}

    #: The sites whose input is never operator text.
    STORED_REF_SITES = {
        ("cachequery", "_redirect_fetch"),
        ("core", "resolve_survivor"),
        ("ids", "parse_provider_alias"),
        ("ids", "provider_alias"),
    }

    @staticmethod
    def _calls(name: str):
        """Every call to ``name`` (bare or attribute) across lib/backlog, as
        ``(module stem, enclosing top-level function, ast.Call)``."""
        found = []
        for path in sorted(Path(ids.__file__).parent.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for top in tree.body:
                if not isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(top):
                    if not isinstance(node, ast.Call):
                        continue
                    fn = node.func
                    called = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
                    if called == name:
                        found.append((path.stem, top.name, node))
        return found

    def test_the_helper_takes_exactly_one_positional_parameter(self):
        params = list(inspect.signature(ids.normalize_stored_ref).parameters.values())
        assert len(params) == 1
        assert params[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD

    @pytest.mark.parametrize("spelling", ["repo#7", "#7", "7"])
    def test_the_helper_refuses_short_and_bare_spellings(self, spelling):
        assert not ids.normalize_stored_ref(spelling).ok

    def test_the_helper_accepts_the_canonical_spelling(self):
        assert ids.normalize_stored_ref("octo/repo#7").canonical == "octo/repo#7"

    def test_defaults_are_passed_only_from_operator_input_functions(self):
        defaulted = {
            (mod, fn)
            for mod, fn, call in self._calls("normalize_id")
            # `arg is None` is a `**kwargs` splat — it could carry a default, so
            # it counts as one (fail closed).
            if any(kw.arg in (None, "default_owner", "default_repo") for kw in call.keywords)
        }
        # Equality, not subset: a scanner that reached nothing would pass a
        # subset check vacuously.
        assert defaulted == self.OPERATOR_INPUT, defaulted

    def test_stored_ref_sites_route_through_the_helper(self):
        via_helper = {(m, f) for m, f, _ in self._calls("normalize_stored_ref")}
        direct = {(m, f) for m, f, _ in self._calls("normalize_id")}
        assert self.STORED_REF_SITES <= via_helper, self.STORED_REF_SITES - via_helper
        assert not (self.STORED_REF_SITES & direct), self.STORED_REF_SITES & direct


class TestProviderAliases:
    """The tagged alias spelling (Cache Spec §4) — the cross-migration half.

    A migration mints no new id: the surviving record carries the old one as an
    alias, so every historical citation keeps resolving. The two spellings are
    asymmetric on purpose — a live ref is untagged because it inherits the
    configured backend, an alias is tagged because ``owner/repo#number`` is not
    GitHub-unique (GitLab and Gitea share the shape) and shape-parsing is what
    §4's rule 3 forbids.
    """

    def test_a_canonical_id_becomes_a_tagged_alias(self):
        assert ids.provider_alias("octo/repo#249") == "github:octo/repo#249"

    def test_the_tag_is_open_because_a_reader_meets_other_backends(self):
        """The spellings this has to *read* are written by whatever backend a
        product migrated away from, so a closed tag set would make an alias minted
        by a future adapter unreadable by the reader whose whole job is old
        spellings."""
        assert ids.parse_provider_alias("gitlab:group/project#123") == (
            "gitlab",
            "group/project#123",
        )

    def test_it_round_trips(self):
        assert ids.parse_provider_alias(ids.provider_alias("octo/repo#7")) == (
            "github",
            "octo/repo#7",
        )

    @pytest.mark.parametrize(
        "token",
        [
            # The question at this seam is not *is this well-formed* but *what else
            # could this successfully resolve*: an alias comes from issue-body text
            # and the canonical id it yields is interpolated into
            # `repos/{owner}/{repo}/…` at the transport. Each of these parses fine
            # as three tokens and points somewhere else entirely.
            "github:../../x#1",
            "github:octo/..#1",
            "github:./repo#1",
            # A short spelling has no owner, so accepting one would make the same
            # stored string resolve to different items in different repos.
            "github:repo#7",
            "github:repo-7",
            # Not tagged at all — that is a live ref, and reading it as an alias is
            # exactly the shape-parsing the tag exists to prevent.
            "octo/repo#7",
            "BKL-7M4Q",
            # A tag that is not a provider token.
            "GitHub:octo/repo#1",
            "2:octo/repo#1",
            ":octo/repo#1",
            "",
            None,
        ],
    )
    def test_a_token_that_could_resolve_elsewhere_is_not_an_alias(self, token):
        assert ids.parse_provider_alias(token) is None

    @pytest.mark.parametrize("bad", ["octo/repo", "../x#1", "", "octo/repo#x"])
    def test_a_malformed_id_mints_no_alias(self, bad):
        assert ids.provider_alias(bad) is None

    def test_both_spellings_are_alias_tokens_and_nothing_else_is(self):
        """The filter on what reaches the cache's alias index: an ``id_aliases``
        entry that is neither is a hand-editing artifact, and indexing it would let
        a typo claim a resolution."""
        assert ids.is_alias_token("BKL-7M4Q")
        assert ids.is_alias_token("github:octo/repo#249")
        assert not ids.is_alias_token("octo/repo#249")
        assert not ids.is_alias_token("not-an-alias!")


class TestResolveRedirect:
    """The pure redirect-follow (merge/transfer): a ref to a merged-away source
    resolves to its survivor, with a cycle guard so it never loops (CRASH-2)."""

    def test_follows_a_chain_to_the_end(self):
        chain = {"o/r#1": "o/r#2", "o/r#2": "o/r#3"}
        assert ids.resolve_redirect("o/r#1", fetch=chain.get) == "o/r#3"

    def test_no_redirect_is_self(self):
        assert ids.resolve_redirect("o/r#9", fetch=lambda _c: None) == "o/r#9"

    def test_self_redirect_terminates(self):
        assert ids.resolve_redirect("o/r#1", fetch=lambda _c: "o/r#1") == "o/r#1"

    def test_cycle_terminates_fail_open(self):
        cycle = {"o/r#1": "o/r#2", "o/r#2": "o/r#1"}
        assert ids.resolve_redirect("o/r#1", fetch=cycle.get) in ("o/r#1", "o/r#2")
