"""Extended tests for EOL matching — _direct_name_match, _match_to_doc, _normalize_for_fuzzy."""

from __future__ import annotations

from datetime import date

from domains.eol.entities import EOLCycle, EOLMatch
from domains.eol.matching import (
    _direct_name_match,
    _match_to_doc,
    _normalize_for_fuzzy,
    compute_eol_match,
    cpe_to_eol_product,
    extract_cycle_match,
    fuzzy_match_product,
)


class TestDirectNameMatch:
    """Tests for _direct_name_match covering all branches."""

    PRODUCTS = {
        "chrome": True,
        "firefox": True,
        "python": True,
        "nodejs": True,
        "office": True,
        "microsoft-edge": True,
        "dotnet": True,
        "redis": True,
        "apache": True,
        "elasticsearch": True,
    }

    def test_exact_match_from_builtin(self) -> None:
        assert _direct_name_match("google chrome", self.PRODUCTS) == "chrome"

    def test_exact_match_not_in_products(self) -> None:
        """Match found in map but product doesn't exist."""
        result = _direct_name_match("google chrome", {"not-chrome": True})
        assert result is None

    def test_prefix_match(self) -> None:
        """Versioned name matches via prefix."""
        result = _direct_name_match(
            "microsoft 365 apps for enterprise - en-us",
            self.PRODUCTS,
        )
        assert result == "office"

    def test_user_mapping_overrides_builtin(self) -> None:
        user_map = {"google chrome": "custom-chrome-product"}
        products = {**self.PRODUCTS, "custom-chrome-product": True}
        result = _direct_name_match("google chrome", products, user_mappings=user_map)
        assert result == "custom-chrome-product"

    def test_auto_derive_slug(self) -> None:
        """App name starting with a long-enough product slug auto-matches."""
        result = _direct_name_match("redis server 7.2", self.PRODUCTS)
        assert result == "redis"

    def test_auto_derive_slug_with_dash(self) -> None:
        result = _direct_name_match("elasticsearch-oss", self.PRODUCTS)
        assert result == "elasticsearch"

    def test_auto_derive_skip_short_slug(self) -> None:
        """Short slugs (<4 chars) are not auto-derived to avoid false positives."""
        products = {"go": True, "qt": True}
        result = _direct_name_match("go programming", products)
        assert result is None  # "go" is too short

    def test_no_match_at_all(self) -> None:
        result = _direct_name_match("completely unknown app", self.PRODUCTS)
        assert result is None

    def test_longest_prefix_wins(self) -> None:
        """When multiple prefixes match, longest wins."""
        result = _direct_name_match("microsoft .net framework 4.8", self.PRODUCTS)
        # "microsoft .net framework" maps to "dotnetfx" but that's not in products
        # "microsoft .net" maps to "dotnet" which IS in products
        assert result == "dotnet"

    def test_empty_user_mappings(self) -> None:
        result = _direct_name_match("mozilla firefox", self.PRODUCTS, user_mappings={})
        assert result == "firefox"


class TestMatchToDoc:
    def test_basic_conversion(self) -> None:
        match = EOLMatch(
            eol_product_id="python",
            matched_cycle="3.12",
            match_source="cpe",
            match_confidence=0.95,
            is_eol=False,
            eol_date=date(2028, 10, 2),
            is_security_only=False,
            support_end=date(2025, 4, 2),
        )
        doc = _match_to_doc(match)
        assert doc["eol_product_id"] == "python"
        assert doc["matched_cycle"] == "3.12"
        assert doc["eol_date"] == "2028-10-02"
        assert doc["support_end"] == "2025-04-02"
        assert doc["is_eol"] is False

    def test_null_dates(self) -> None:
        match = EOLMatch(
            eol_product_id="chrome",
            matched_cycle="120",
            match_source="fuzzy",
            match_confidence=0.7,
            is_eol=False,
            eol_date=None,
            is_security_only=False,
            support_end=None,
        )
        doc = _match_to_doc(match)
        assert doc["eol_date"] is None
        assert doc["support_end"] is None


class TestNormalizeForFuzzy:
    def test_strips_version_numbers(self) -> None:
        assert "chrome" in _normalize_for_fuzzy("Chrome 120.0.6099.130")

    def test_strips_parentheticals(self) -> None:
        result = _normalize_for_fuzzy("Firefox (x64 en-US)")
        assert "(" not in result

    def test_strips_noise_words(self) -> None:
        result = _normalize_for_fuzzy("Microsoft Visual Studio Professional Edition")
        assert "microsoft" not in result
        assert "professional" not in result
        assert "edition" not in result

    def test_empty_string(self) -> None:
        assert _normalize_for_fuzzy("") == ""


class TestComputeEolMatch:
    def _make_cycles(self) -> list[EOLCycle]:
        return [
            EOLCycle(
                cycle="3.8",
                eol_date=date(2024, 10, 7),
                support_end=date(2021, 5, 3),
            ),
            EOLCycle(
                cycle="3.12",
                eol_date=date(2028, 10, 2),
                support_end=date(2025, 4, 2),
            ),
        ]

    def test_matching_cycle_returns_eol_match(self) -> None:
        result = compute_eol_match(
            eol_product_id="python",
            version_string="3.8.19",
            cycles=self._make_cycles(),
            match_source="cpe",
            match_confidence=0.95,
            reference_date=date(2025, 1, 1),
        )
        assert result is not None
        assert result.matched_cycle == "3.8"
        assert result.is_eol is True  # 2024-10-07 < 2025-01-01

    def test_no_matching_cycle(self) -> None:
        result = compute_eol_match(
            eol_product_id="python",
            version_string="2.6",
            cycles=self._make_cycles(),
            match_source="cpe",
            match_confidence=0.95,
        )
        assert result is None

    def test_security_only_detection(self) -> None:
        result = compute_eol_match(
            eol_product_id="python",
            version_string="3.12.0",
            cycles=self._make_cycles(),
            match_source="cpe",
            match_confidence=0.9,
            reference_date=date(2026, 1, 1),
        )
        assert result is not None
        assert result.is_security_only is True
        assert result.is_eol is False


class TestCpeToEolProduct:
    def test_known_mapping(self) -> None:
        assert cpe_to_eol_product("google", "chrome") == "chrome"

    def test_case_insensitive(self) -> None:
        assert cpe_to_eol_product("Google", "Chrome") == "chrome"

    def test_unknown_returns_none(self) -> None:
        assert cpe_to_eol_product("unknown", "product") is None


class TestExtractCycleMatch:
    def _cycles(self) -> list[EOLCycle]:
        return [
            EOLCycle(cycle="120"),
            EOLCycle(cycle="119"),
            EOLCycle(cycle="3.8"),
        ]

    def test_matches_version(self) -> None:
        result = extract_cycle_match("120.0.6099.130", self._cycles())
        assert result is not None
        assert result.cycle == "120"

    def test_no_version_returns_none(self) -> None:
        assert extract_cycle_match("", self._cycles()) is None

    def test_no_cycles_returns_none(self) -> None:
        assert extract_cycle_match("120", []) is None

    def test_non_numeric_returns_none(self) -> None:
        assert extract_cycle_match("abc", self._cycles()) is None

    def test_dot_version_match(self) -> None:
        result = extract_cycle_match("3.8.19", self._cycles())
        assert result is not None
        assert result.cycle == "3.8"


class TestFuzzyMatchProduct:
    PRODUCTS = {
        "python": "Python",
        "nodejs": "Node.js",
        "redis": "Redis",
        "qt": "Qt",
    }

    def test_slug_match(self) -> None:
        result = fuzzy_match_product("Python 3.12", self.PRODUCTS)
        assert result is not None
        assert result[0] == "python"

    def test_no_match_returns_none(self) -> None:
        result = fuzzy_match_product("Completely Unknown App", self.PRODUCTS)
        assert result is None

    def test_short_slug_requires_exact_token(self) -> None:
        """Short slugs like 'qt' need exact token match."""
        result = fuzzy_match_product("Qt Creator 5.0", self.PRODUCTS)
        assert result is not None
        assert result[0] == "qt"

    def test_empty_app_name(self) -> None:
        result = fuzzy_match_product("", self.PRODUCTS)
        assert result is None
