"""Unit tests for EOL matching engine.

Tests CPE-based matching, fuzzy matching, version extraction, and
EOL match computation.
"""

from __future__ import annotations

from datetime import date

import pytest

from domains.eol.entities import EOLCycle
from domains.eol.matching import (
    _normalize_for_fuzzy,
    compute_eol_match,
    cpe_to_eol_product,
    extract_cycle_match,
    fuzzy_match_product,
)

# ---------------------------------------------------------------------------
# CPE-based matching
# ---------------------------------------------------------------------------


class TestCpeToEolProduct:
    """Tests for the static CPE vendor:product → EOL product mapping."""

    def test_known_mapping_chrome(self) -> None:
        """Google Chrome maps to 'chrome'."""
        assert cpe_to_eol_product("google", "chrome") == "chrome"

    def test_known_mapping_python(self) -> None:
        """Python Software Foundation Python maps to 'python'."""
        assert cpe_to_eol_product("python_software_foundation", "python") == "python"

    def test_known_mapping_case_insensitive(self) -> None:
        """Lookup is case-insensitive."""
        assert cpe_to_eol_product("Google", "Chrome") == "chrome"

    def test_unknown_mapping_returns_none(self) -> None:
        """Unknown CPE vendor:product returns None."""
        assert cpe_to_eol_product("unknown_vendor", "unknown_product") is None

    def test_windows_10_maps_to_windows(self) -> None:
        """Microsoft Windows 10 maps to 'windows'."""
        assert cpe_to_eol_product("microsoft", "windows_10") == "windows"

    def test_office_maps_correctly(self) -> None:
        """Microsoft Office maps to 'office'."""
        assert cpe_to_eol_product("microsoft", "office") == "office"

    def test_oracle_jdk_mapping(self) -> None:
        """Oracle Java SE maps to 'oracle-jdk'."""
        assert cpe_to_eol_product("oracle", "java_se") == "oracle-jdk"

    def test_nodejs_mapping(self) -> None:
        """Node.js maps to 'nodejs'."""
        assert cpe_to_eol_product("nodejs", "node.js") == "nodejs"


# ---------------------------------------------------------------------------
# Version extraction
# ---------------------------------------------------------------------------


class TestExtractCycleMatch:
    """Tests for matching app version strings to EOL release cycles."""

    @pytest.fixture()
    def python_cycles(self) -> list[EOLCycle]:
        """Python release cycles (major.minor format)."""
        return [
            EOLCycle(cycle="3.12", eol_date=date(2028, 10, 2)),
            EOLCycle(cycle="3.11", eol_date=date(2027, 10, 4)),
            EOLCycle(cycle="3.8", eol_date=date(2024, 10, 7)),
        ]

    @pytest.fixture()
    def chrome_cycles(self) -> list[EOLCycle]:
        """Chrome release cycles (major-only format)."""
        return [
            EOLCycle(cycle="123", eol_date=date(2024, 6, 12)),
            EOLCycle(cycle="122", eol_date=date(2024, 5, 1)),
        ]

    @pytest.fixture()
    def office_cycles(self) -> list[EOLCycle]:
        """Office release cycles (year format)."""
        return [
            EOLCycle(cycle="2021", eol_date=date(2026, 10, 13)),
            EOLCycle(cycle="2019", eol_date=date(2025, 10, 14)),
        ]

    def test_major_minor_match_python(self, python_cycles: list[EOLCycle]) -> None:
        """Python 3.8.19 matches cycle 3.8."""
        result = extract_cycle_match("3.8.19", python_cycles)
        assert result is not None
        assert result.cycle == "3.8"

    def test_major_minor_match_python_312(self, python_cycles: list[EOLCycle]) -> None:
        """Python 3.12.3 matches cycle 3.12."""
        result = extract_cycle_match("3.12.3", python_cycles)
        assert result is not None
        assert result.cycle == "3.12"

    def test_major_only_match_chrome(self, chrome_cycles: list[EOLCycle]) -> None:
        """Chrome 123.0.6312.86 matches cycle 123."""
        result = extract_cycle_match("123.0.6312.86", chrome_cycles)
        assert result is not None
        assert result.cycle == "123"

    def test_year_format_match_office(self, office_cycles: list[EOLCycle]) -> None:
        """Office 2021 matches cycle 2021."""
        result = extract_cycle_match("2021", office_cycles)
        assert result is not None
        assert result.cycle == "2021"

    def test_no_match_returns_none(self, python_cycles: list[EOLCycle]) -> None:
        """Unrecognized version returns None."""
        result = extract_cycle_match("99.99.99", python_cycles)
        assert result is None

    def test_empty_version_returns_none(self, python_cycles: list[EOLCycle]) -> None:
        """Empty version string returns None."""
        result = extract_cycle_match("", python_cycles)
        assert result is None

    def test_no_cycles_returns_none(self) -> None:
        """Empty cycle list returns None."""
        result = extract_cycle_match("3.8.19", [])
        assert result is None

    def test_non_numeric_version_returns_none(self, python_cycles: list[EOLCycle]) -> None:
        """Non-numeric version string returns None."""
        result = extract_cycle_match("abc-def", python_cycles)
        assert result is None


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------


class TestFuzzyMatchProduct:
    """Tests for name-based fuzzy product matching."""

    @pytest.fixture()
    def product_names(self) -> dict[str, str]:
        """Sample product name map."""
        return {
            "chrome": "Google Chrome",
            "firefox": "Mozilla Firefox",
            "python": "Python",
            "nodejs": "Node.js",
            "office": "Microsoft Office",
        }

    def test_direct_slug_match(self, product_names: dict[str, str]) -> None:
        """App name containing the product slug matches."""
        result = fuzzy_match_product("Google Chrome Browser", product_names)
        assert result is not None
        product_id, confidence = result
        assert product_id == "chrome"
        assert confidence >= 0.4

    def test_token_overlap_match(self, product_names: dict[str, str]) -> None:
        """Token overlap produces a match."""
        result = fuzzy_match_product("Mozilla Firefox ESR", product_names)
        assert result is not None
        product_id, _ = result
        assert product_id == "firefox"

    def test_no_match_for_unrelated(self, product_names: dict[str, str]) -> None:
        """Completely unrelated app name returns None."""
        result = fuzzy_match_product("Adobe Photoshop CC 2024", product_names)
        assert result is None

    def test_empty_name_returns_none(self, product_names: dict[str, str]) -> None:
        """Empty app name returns None."""
        result = fuzzy_match_product("", product_names)
        assert result is None

    def test_fuzzy_confidence_capped(self, product_names: dict[str, str]) -> None:
        """Fuzzy match confidence is capped below CPE confidence."""
        result = fuzzy_match_product("Python Runtime", product_names)
        if result:
            _, confidence = result
            assert confidence <= 0.7  # Capped below CPE threshold


class TestNormalizeForFuzzy:
    """Tests for app name normalization."""

    def test_removes_version_numbers(self) -> None:
        """Version patterns are stripped."""
        assert "chrome" in _normalize_for_fuzzy("Chrome 123.0.6312.86")

    def test_removes_noise_words(self) -> None:
        """Noise words like 'Professional' are removed."""
        result = _normalize_for_fuzzy("Microsoft Office Professional Plus")
        assert "professional" not in result

    def test_lowercases(self) -> None:
        """Output is lowercase."""
        result = _normalize_for_fuzzy("Google CHROME")
        assert result == result.lower()


# ---------------------------------------------------------------------------
# EOL match computation
# ---------------------------------------------------------------------------


class TestComputeEolMatch:
    """Tests for full EOL match computation."""

    @pytest.fixture()
    def python_cycles(self) -> list[EOLCycle]:
        """Python cycles with known EOL dates."""
        return [
            EOLCycle(
                cycle="3.12",
                eol_date=date(2028, 10, 2),
                support_end=date(2025, 4, 2),
            ),
            EOLCycle(
                cycle="3.8",
                eol_date=date(2024, 10, 7),
                support_end=date(2021, 5, 3),
            ),
        ]

    def test_eol_app_detected(self, python_cycles: list[EOLCycle]) -> None:
        """Python 3.8 is detected as EOL (past 2024-10-07)."""
        result = compute_eol_match(
            eol_product_id="python",
            version_string="3.8.19",
            cycles=python_cycles,
            match_source="cpe",
            match_confidence=0.9,
            reference_date=date(2025, 1, 1),
        )
        assert result is not None
        assert result.is_eol is True
        assert result.matched_cycle == "3.8"
        assert result.eol_date == date(2024, 10, 7)

    def test_security_only_detected(self, python_cycles: list[EOLCycle]) -> None:
        """Python 3.12 in security-only phase (support ended, EOL not yet)."""
        result = compute_eol_match(
            eol_product_id="python",
            version_string="3.12.3",
            cycles=python_cycles,
            match_source="cpe",
            match_confidence=0.9,
            reference_date=date(2026, 1, 1),
        )
        assert result is not None
        assert result.is_eol is False
        assert result.is_security_only is True
        assert result.support_end == date(2025, 4, 2)

    def test_supported_app_not_flagged(self, python_cycles: list[EOLCycle]) -> None:
        """Python 3.12 is fully supported before support_end."""
        result = compute_eol_match(
            eol_product_id="python",
            version_string="3.12.3",
            cycles=python_cycles,
            match_source="cpe",
            match_confidence=0.9,
            reference_date=date(2024, 1, 1),
        )
        assert result is not None
        assert result.is_eol is False
        assert result.is_security_only is False

    def test_no_version_match_returns_none(self, python_cycles: list[EOLCycle]) -> None:
        """Unrecognized version returns None."""
        result = compute_eol_match(
            eol_product_id="python",
            version_string="99.99",
            cycles=python_cycles,
            match_source="cpe",
            match_confidence=0.9,
        )
        assert result is None

    def test_match_preserves_metadata(self, python_cycles: list[EOLCycle]) -> None:
        """Match preserves source and confidence metadata."""
        result = compute_eol_match(
            eol_product_id="python",
            version_string="3.8.19",
            cycles=python_cycles,
            match_source="fuzzy",
            match_confidence=0.6,
            reference_date=date(2025, 1, 1),
        )
        assert result is not None
        assert result.match_source == "fuzzy"
        assert result.match_confidence == 0.6
        assert result.eol_product_id == "python"
