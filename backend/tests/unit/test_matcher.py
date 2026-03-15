"""Unit tests for the fingerprint glob matcher.

Tests run entirely in-memory — no DB, no fixtures, no async setup required.
"""

from __future__ import annotations

from domains.fingerprint.matcher import glob_to_regex, matches_pattern

# ── TestGlobToRegex ───────────────────────────────────────────────────────────


class TestGlobToRegex:
    """Unit tests for glob_to_regex — pattern compilation."""

    def test_star_matches_any_chars(self) -> None:
        """A trailing '*' must match any sequence of characters after the prefix."""
        regex = glob_to_regex("wincc*")
        assert regex.match("wincc runtime 3.0") is not None

    def test_star_at_start(self) -> None:
        """A leading '*' wrapped around a term must match anywhere in the string."""
        regex = glob_to_regex("*wincc*")
        assert regex.match("siemens wincc 8.0") is not None

    def test_no_wildcard(self) -> None:
        """A pattern with no wildcards must only match the exact string."""
        regex = glob_to_regex("wincc")
        assert regex.match("wincc") is not None
        assert regex.match("wincc runtime") is None

    def test_case_insensitive(self) -> None:
        """Pattern matching must be case-insensitive."""
        regex = glob_to_regex("WinCC*")
        assert regex.match("wincc runtime") is not None

    def test_special_chars_escaped(self) -> None:
        """A literal dot in the pattern must not match arbitrary characters."""
        regex = glob_to_regex("test.app")
        assert regex.match("testXapp") is None
        assert regex.match("test.app") is not None


# ── TestMatchesPattern ────────────────────────────────────────────────────────


class TestMatchesPattern:
    """Unit tests for matches_pattern — the public glob-matching helper."""

    def test_simple_glob_match(self) -> None:
        """A simple 'prefix*' glob must match strings that start with the prefix."""
        assert matches_pattern("chrome*", "chrome 120.0") is True

    def test_no_match(self) -> None:
        """A pattern for a different product must not match an unrelated string."""
        assert matches_pattern("firefox*", "chrome 120.0") is False

    def test_empty_app_name(self) -> None:
        """A non-trivial pattern must not match an empty string."""
        assert matches_pattern("chrome*", "") is False

    def test_pattern_with_spaces(self) -> None:
        """Patterns that contain spaces must match strings with the same spacing."""
        assert matches_pattern("google chrome*", "google chrome 120") is True
