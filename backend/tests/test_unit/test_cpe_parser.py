"""Unit tests for the NIST CPE parser and pattern generator."""

from __future__ import annotations

from domains.library.adapters.nist_cpe import cpe_to_patterns, parse_cpe_uri


class TestParseCpeUri:
    def test_valid_application_cpe(self) -> None:
        result = parse_cpe_uri("cpe:2.3:a:google:chrome:120.0:*:*:*:*:*:*:*")
        assert result is not None
        assert result["vendor"] == "google"
        assert result["product"] == "chrome"
        assert result["version"] == "120.0"

    def test_vendor_with_underscores(self) -> None:
        result = parse_cpe_uri("cpe:2.3:a:siemens:wincc_runtime:7.5:*:*:*:*:*:*:*")
        assert result is not None
        assert result["vendor"] == "siemens"
        assert result["product"] == "wincc runtime"

    def test_wildcard_version(self) -> None:
        result = parse_cpe_uri("cpe:2.3:a:mozilla:firefox:*:*:*:*:*:*:*:*")
        assert result is not None
        assert result["version"] == ""

    def test_dash_version(self) -> None:
        result = parse_cpe_uri("cpe:2.3:a:oracle:java:-:*:*:*:*:*:*:*")
        assert result is not None
        assert result["version"] == ""

    def test_os_cpe_returns_none(self) -> None:
        result = parse_cpe_uri("cpe:2.3:o:microsoft:windows_10:*:*:*:*:*:*:*:*")
        assert result is None

    def test_hardware_cpe_returns_none(self) -> None:
        result = parse_cpe_uri("cpe:2.3:h:cisco:catalyst_9300:*:*:*:*:*:*:*:*")
        assert result is None

    def test_wildcard_vendor_returns_none(self) -> None:
        result = parse_cpe_uri("cpe:2.3:a:*:something:*:*:*:*:*:*:*:*")
        assert result is None

    def test_wildcard_product_returns_none(self) -> None:
        result = parse_cpe_uri("cpe:2.3:a:vendor:*:*:*:*:*:*:*:*:*")
        assert result is None

    def test_short_uri_returns_none(self) -> None:
        result = parse_cpe_uri("cpe:2.3:a")
        assert result is None

    def test_cpe_23_only(self) -> None:
        result = parse_cpe_uri("cpe:2.2:a:vendor:product:1.0:*:*:*:*:*:*:*")
        assert result is None


class TestCpeToPatterns:
    def test_generates_multiple_patterns(self) -> None:
        patterns = cpe_to_patterns("cpe:2.3:a:google:chrome:*:*:*:*:*:*:*:*")
        assert len(patterns) >= 2

        # Vendor-qualified pattern
        vendor_pattern = patterns[0]
        assert vendor_pattern["pattern"] == "*google*chrome*"
        assert vendor_pattern["weight"] == 1.0
        assert "cpe:" in str(vendor_pattern["source_detail"])

        # Broad pattern
        broad_pattern = patterns[1]
        assert broad_pattern["pattern"] == "*chrome*"
        assert broad_pattern["weight"] == 0.8

    def test_short_product_skips_broad(self) -> None:
        patterns = cpe_to_patterns("cpe:2.3:a:vendor:abc:*:*:*:*:*:*:*:*")
        # "abc" is only 3 chars — should skip broad pattern
        assert len(patterns) == 1
        assert "*vendor*abc*" in patterns[0]["pattern"]  # type: ignore[operator]

    def test_invalid_cpe_returns_empty(self) -> None:
        patterns = cpe_to_patterns("not-a-cpe")
        assert patterns == []

    def test_display_name_generated(self) -> None:
        patterns = cpe_to_patterns("cpe:2.3:a:adobe:acrobat_reader:*:*:*:*:*:*:*:*")
        assert patterns[0]["display_name"] == "Adobe Acrobat Reader"
