"""Unit tests for regex denial-of-service safety in the fingerprint matcher.

Verifies that glob_to_regex() properly escapes metacharacters, handles
extreme-length patterns, and avoids catastrophic backtracking from nested
wildcards. Also validates that the DTO layer enforces the 500-char max_length
on pattern fields.

All tests run in-memory -- no DB, no fixtures, no async required.
"""

from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from domains.fingerprint.dto import MarkerCreateRequest, MarkerUpdateRequest
from domains.fingerprint.matcher import glob_to_regex


class TestMetacharacterEscaping:
    """Verify that all regex metacharacters are properly escaped by glob_to_regex."""

    @pytest.mark.parametrize(
        "meta",
        [".", "+", "^", "$", "{", "}", "(", ")", "|", "\\", "[", "]"],
    )
    def test_regex_metacharacters_are_literal(self, meta: str) -> None:
        """Each regex metacharacter in a pattern must match only its literal self."""
        pattern = f"app{meta}name"
        regex = glob_to_regex(pattern)
        # Must match the literal string
        assert regex.match(f"app{meta}name") is not None
        # Must NOT match a substitution (except '.' which is special-cased below)
        if meta != "\\":
            assert regex.match("appXname") is None, (
                f"Metacharacter {meta!r} was not escaped — matched arbitrary char"
            )

    def test_dot_does_not_match_arbitrary_char(self) -> None:
        """A literal dot in the pattern must not behave as regex '.' (any char)."""
        regex = glob_to_regex("v1.2.3")
        assert regex.match("v1.2.3") is not None
        assert regex.match("v1X2Y3") is None

    def test_pipe_does_not_create_alternation(self) -> None:
        """A literal pipe must not create a regex alternation."""
        regex = glob_to_regex("a|b")
        assert regex.match("a|b") is not None
        assert regex.match("a") is None
        assert regex.match("b") is None

    def test_parentheses_do_not_create_group(self) -> None:
        """Literal parentheses must not create a regex capture group."""
        regex = glob_to_regex("func(x)")
        assert regex.match("func(x)") is not None
        assert regex.match("funcx") is None

    def test_brackets_do_not_create_char_class(self) -> None:
        """Literal square brackets must not create a regex character class."""
        regex = glob_to_regex("arr[0]")
        assert regex.match("arr[0]") is not None
        assert regex.match("arr0") is None


class TestLongPatterns:
    """Verify that extremely long patterns compile and match in reasonable time."""

    def test_500_char_pattern_compiles(self) -> None:
        """A 500-character pattern (at the DTO max_length) must compile without error."""
        pattern = "a" * 500
        regex = glob_to_regex(pattern)
        assert regex.match("a" * 500) is not None
        assert regex.match("a" * 499) is None

    def test_500_char_wildcard_pattern_compiles(self) -> None:
        """A 500-char pattern mixing literals and wildcards compiles quickly."""
        # 490 literal chars + a few wildcards scattered in = ~500 chars total
        pattern = "a" * 245 + "*" + "b" * 245 + "*" + "c" * 8
        assert len(pattern) == 500
        start = time.monotonic()
        regex = glob_to_regex(pattern)
        compile_time = time.monotonic() - start
        assert compile_time < 1.0, f"Compilation took {compile_time:.2f}s — too slow"
        # Should match a string with the right prefix and suffix
        test_str = "a" * 245 + "ANYTHING" + "b" * 245 + "MORE" + "c" * 8
        start = time.monotonic()
        result = regex.match(test_str)
        match_time = time.monotonic() - start
        assert result is not None
        assert match_time < 1.0, f"Matching took {match_time:.2f}s — too slow"

    def test_long_literal_pattern_match_performance(self) -> None:
        """Matching a 500-char literal pattern against a 500-char string is fast."""
        pattern = "x" * 500
        regex = glob_to_regex(pattern)
        start = time.monotonic()
        for _ in range(1000):
            regex.match("x" * 500)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"1000 matches took {elapsed:.2f}s — too slow"


class TestNestedWildcards:
    """Verify that nested/repeated wildcards do not cause exponential backtracking."""

    def test_triple_star_does_not_backtrack(self) -> None:
        """'***' (three consecutive stars) must not cause catastrophic backtracking.

        Three consecutive '*' globs degenerate to a single '.*' in the compiled
        regex, so matching should be linear.
        """
        regex = glob_to_regex("***")
        start = time.monotonic()
        # Try matching a moderately long non-matching string
        text = "a" * 1000
        result = regex.match(text)
        elapsed = time.monotonic() - start
        assert result is not None  # '***' matches anything
        assert elapsed < 0.5, f"Triple-star match took {elapsed:.2f}s — possible backtracking"

    def test_alternating_star_question_marks(self) -> None:
        """Patterns like '*?*?*?*' must not cause exponential backtracking."""
        pattern = "*?*?*?*?*?*"
        regex = glob_to_regex(pattern)
        start = time.monotonic()
        text = "abcdef" + "x" * 200
        result = regex.match(text)
        elapsed = time.monotonic() - start
        assert result is not None
        assert elapsed < 0.5, f"Alternating wildcards took {elapsed:.2f}s — possible backtracking"

    def test_many_stars_non_matching(self) -> None:
        """Many consecutive wildcards on a non-matching anchored pattern stay fast."""
        # Pattern: 'z' followed by 20 stars — must start with 'z'
        pattern = "z" + "*" * 20
        regex = glob_to_regex(pattern)
        start = time.monotonic()
        # Non-matching string (doesn't start with 'z')
        result = regex.match("a" * 500)
        elapsed = time.monotonic() - start
        assert result is None
        assert elapsed < 0.5, f"Non-match with many stars took {elapsed:.2f}s"

    def test_star_produces_dotstar_in_regex(self) -> None:
        """Verify that consecutive stars collapse into '.*' segments (no nesting)."""
        regex = glob_to_regex("a***b")
        # The regex should be equivalent to ^a.*.*.*b$ which simplifies to ^a.*b$
        # Verify it matches correctly
        assert regex.match("a---b") is not None
        assert regex.match("ab") is not None
        assert regex.match("b---a") is None


class TestPatternMaxLength:
    """Verify the 500-char max_length on MarkerCreateRequest.pattern."""

    def test_pattern_at_max_length_accepted(self) -> None:
        """A 500-character pattern must be accepted by the DTO."""
        req = MarkerCreateRequest(
            pattern="a" * 500,
            display_name="Test",
        )
        assert len(req.pattern) == 500

    def test_pattern_over_max_length_rejected(self) -> None:
        """A 501-character pattern must be rejected by the DTO."""
        with pytest.raises(ValidationError):  # Pydantic ValidationError
            MarkerCreateRequest(
                pattern="a" * 501,
                display_name="Test",
            )

    def test_empty_pattern_rejected(self) -> None:
        """An empty pattern must be rejected by the DTO (min_length=1)."""
        with pytest.raises(ValidationError):
            MarkerCreateRequest(
                pattern="",
                display_name="Test",
            )

    def test_update_pattern_over_max_length_rejected(self) -> None:
        """MarkerUpdateRequest also enforces max_length=500 on pattern."""
        with pytest.raises(ValidationError):
            MarkerUpdateRequest(pattern="b" * 501)
