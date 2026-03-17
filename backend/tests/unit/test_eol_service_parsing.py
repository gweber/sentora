"""Tests for EOL service parsing functions (_parse_date_field, _parse_cycles, get_sync_status)."""

from __future__ import annotations

from datetime import date

from domains.eol.service import _parse_cycles, _parse_date_field, get_sync_status


class TestParseDateField:
    def test_none_returns_none(self) -> None:
        assert _parse_date_field(None) is None

    def test_false_returns_none(self) -> None:
        assert _parse_date_field(False) is None

    def test_true_returns_none(self) -> None:
        assert _parse_date_field(True) is None

    def test_valid_iso_string(self) -> None:
        assert _parse_date_field("2025-06-30") == date(2025, 6, 30)

    def test_invalid_string_returns_none(self) -> None:
        assert _parse_date_field("not-a-date") is None

    def test_date_object_passthrough(self) -> None:
        d = date(2024, 1, 15)
        assert _parse_date_field(d) is d

    def test_empty_string_returns_none(self) -> None:
        assert _parse_date_field("") is None

    def test_numeric_returns_none(self) -> None:
        assert _parse_date_field(12345) is None  # type: ignore[arg-type]


class TestParseCycles:
    def test_empty_releases(self) -> None:
        assert _parse_cycles([]) == []

    def test_basic_release(self) -> None:
        raw = [
            {
                "name": "3.12",
                "releaseDate": "2023-10-02",
                "eolFrom": "2028-10-02",
                "eoasFrom": "2025-04-02",
                "isLts": False,
                "isEol": False,
                "isEoas": False,
            }
        ]
        result = _parse_cycles(raw)
        assert len(result) == 1
        assert result[0]["cycle"] == "3.12"
        assert result[0]["release_date"] == "2023-10-02"
        assert result[0]["eol_date"] == "2028-10-02"
        assert result[0]["support_end"] == "2025-04-02"
        assert result[0]["lts"] is False
        assert result[0]["is_eol"] is False

    def test_legacy_field_names(self) -> None:
        """Falls back to legacy field names (eol, support, date)."""
        raw = [
            {
                "cycle": "2.7",
                "date": "2010-07-03",
                "eol": "2020-01-01",
                "support": "2015-04-15",
                "lts": True,
            }
        ]
        result = _parse_cycles(raw)
        assert len(result) == 1
        assert result[0]["cycle"] == "2.7"
        assert result[0]["release_date"] == "2010-07-03"
        assert result[0]["eol_date"] == "2020-01-01"
        assert result[0]["support_end"] == "2015-04-15"
        assert result[0]["lts"] is True
        assert result[0]["is_eol"] is True  # 2020-01-01 < today

    def test_latest_as_dict(self) -> None:
        raw = [
            {
                "name": "22.04",
                "latest": {"name": "22.04.4", "date": "2024-02-22"},
            }
        ]
        result = _parse_cycles(raw)
        assert result[0]["latest_version"] == "22.04.4"
        assert result[0]["latest_version_date"] == "2024-02-22"

    def test_latest_as_string(self) -> None:
        raw = [{"name": "1.0", "latest": "1.0.5"}]
        result = _parse_cycles(raw)
        assert result[0]["latest_version"] == "1.0.5"
        assert result[0]["latest_version_date"] is None

    def test_latest_as_none(self) -> None:
        raw = [{"name": "1.0", "latest": None}]
        result = _parse_cycles(raw)
        assert result[0]["latest_version"] is None

    def test_skips_empty_cycle_name(self) -> None:
        raw = [{"name": ""}, {"name": "1.0"}]
        result = _parse_cycles(raw)
        assert len(result) == 1
        assert result[0]["cycle"] == "1.0"

    def test_is_eol_computed_from_dates(self) -> None:
        """When isEol is absent, computes from eol_date < today."""
        raw = [{"name": "old", "eolFrom": "2020-01-01"}]
        result = _parse_cycles(raw)
        assert result[0]["is_eol"] is True

    def test_is_eoas_computed_from_dates(self) -> None:
        """When isEoas absent, computes from support_end < today and eol_date >= today."""
        raw = [
            {
                "name": "security_only",
                "eoasFrom": "2020-01-01",
                "eolFrom": "2099-01-01",
            }
        ]
        result = _parse_cycles(raw)
        assert result[0]["is_security_only"] is True

    def test_api_provided_booleans_override(self) -> None:
        """isEol/isEoas from API override computed values."""
        raw = [
            {
                "name": "forced",
                "eolFrom": "2099-01-01",
                "isEol": True,
                "isEoas": True,
            }
        ]
        result = _parse_cycles(raw)
        assert result[0]["is_eol"] is True
        assert result[0]["is_security_only"] is True


class TestGetSyncStatus:
    def test_returns_dict(self) -> None:
        status = get_sync_status()
        assert isinstance(status, dict)
        assert "status" in status
