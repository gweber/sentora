"""Unit tests for the CrowdStrike normalizer.

Tests cover host, application, and group normalization, including
OS type mapping, status normalization, group name resolution,
and graceful handling of missing fields.
"""

from __future__ import annotations

import pytest

from domains.sources.crowdstrike.normalizer import (
    _normalize_machine_type,
    _normalize_os_type,
    _normalize_status,
    normalize_application,
    normalize_group,
    normalize_host,
)
from domains.sources.identity import canonical_id

# ── Host normalization ──────────────────────────────────────────────────────


class TestNormalizeHost:
    """Tests for ``normalize_host``."""

    def _make_cs_host(self, **overrides: object) -> dict:
        """Build a minimal CrowdStrike host dict with sensible defaults."""
        base = {
            "device_id": "abc123",
            "hostname": "DESKTOP-XYZ",
            "platform_name": "Windows",
            "os_version": "Windows 10 Build 19045",
            "agent_version": "7.10.18110.0",
            "status": "normal",
            "last_seen": "2024-06-15T10:30:00Z",
            "local_ip": "10.0.0.5",
            "external_ip": "203.0.113.42",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "tags": ["Environment/Production"],
            "groups": ["grp001", "grp002"],
            "machine_domain": "corp.example.com",
            "ou": "OU=Workstations",
            "site_name": "HQ",
            "system_manufacturer": "Dell Inc.",
            "system_product_name": "Latitude 5530",
            "product_type_desc": "Workstation",
            "modified_timestamp": "2024-06-15T10:30:00Z",
            "first_seen_timestamp": "2024-01-10T08:00:00Z",
        }
        base.update(overrides)
        return base

    def test_basic_host_normalization(self) -> None:
        """All key fields are mapped correctly."""
        group_map = {"grp001": "Engineering", "grp002": "VPN Users"}
        doc = normalize_host(self._make_cs_host(), group_map)

        assert doc["source"] == "crowdstrike"
        assert doc["source_id"] == "abc123"
        assert doc["_id"] == canonical_id("crowdstrike", "agent:abc123")
        assert doc["hostname"] == "DESKTOP-XYZ"
        assert doc["os_type"] == "windows"
        assert doc["os_version"] == "Windows 10 Build 19045"
        assert doc["agent_version"] == "7.10.18110.0"
        assert doc["agent_status"] == "online"
        assert doc["last_active"] == "2024-06-15T10:30:00Z"
        assert doc["first_seen"] == "2024-01-10T08:00:00Z"
        assert doc["machine_type"] == "desktop"
        assert doc["domain"] == "corp.example.com"
        assert doc["ip_addresses"] == ["10.0.0.5", "203.0.113.42"]
        assert doc["mac_addresses"] == ["AA:BB:CC:DD:EE:FF"]
        assert doc["groups"] == ["Engineering", "VPN Users"]
        assert doc["tags"] == ["Environment/Production"]
        assert doc["group_id"] == "grp001"
        assert doc["group_name"] == "Engineering"
        assert doc["site_name"] == "HQ"

    def test_os_type_mac(self) -> None:
        """``platform_name: 'Mac'`` maps to ``'macos'``."""
        doc = normalize_host(self._make_cs_host(platform_name="Mac"), {})
        assert doc["os_type"] == "macos"

    def test_os_type_linux(self) -> None:
        """``platform_name: 'Linux'`` maps to ``'linux'``."""
        doc = normalize_host(self._make_cs_host(platform_name="Linux"), {})
        assert doc["os_type"] == "linux"

    def test_os_type_unknown(self) -> None:
        """Unknown platform lowercases gracefully."""
        doc = normalize_host(self._make_cs_host(platform_name="ChromeOS"), {})
        assert doc["os_type"] == "chromeos"

    def test_os_type_empty(self) -> None:
        """Empty platform maps to ``'unknown'``."""
        doc = normalize_host(self._make_cs_host(platform_name=""), {})
        assert doc["os_type"] == "unknown"

    def test_status_normal_is_online(self) -> None:
        """``status: 'normal'`` maps to ``'online'``."""
        doc = normalize_host(self._make_cs_host(status="normal"), {})
        assert doc["agent_status"] == "online"

    def test_status_contained(self) -> None:
        """Containment statuses map to ``'contained'``."""
        for cs_status in ("contained", "containment_pending", "lift_containment_pending"):
            doc = normalize_host(self._make_cs_host(status=cs_status), {})
            assert doc["agent_status"] == "contained", f"Failed for status={cs_status}"

    def test_status_unknown_is_offline(self) -> None:
        """Unknown statuses default to ``'offline'``."""
        doc = normalize_host(self._make_cs_host(status="something_weird"), {})
        assert doc["agent_status"] == "offline"

    def test_missing_fields_graceful(self) -> None:
        """Missing fields produce graceful defaults, no crash."""
        minimal = {"device_id": "min001"}
        doc = normalize_host(minimal, {})
        assert doc["source_id"] == "min001"
        assert doc["hostname"] == "min001"  # Falls back to device_id
        assert doc["os_type"] == "unknown"
        assert doc["agent_status"] == "offline"
        assert doc["ip_addresses"] == []
        assert doc["mac_addresses"] == []
        assert doc["groups"] == []
        assert doc["tags"] == []

    def test_duplicate_ip_not_added(self) -> None:
        """When local_ip == external_ip, only one entry appears."""
        doc = normalize_host(
            self._make_cs_host(local_ip="10.0.0.1", external_ip="10.0.0.1"), {}
        )
        assert doc["ip_addresses"] == ["10.0.0.1"]

    def test_group_id_resolution(self) -> None:
        """Unknown group IDs are kept as-is (not silently dropped)."""
        doc = normalize_host(
            self._make_cs_host(groups=["unknown_grp"]), {"known_grp": "Known"}
        )
        assert doc["groups"] == ["unknown_grp"]

    def test_deterministic_id(self) -> None:
        """Same ``device_id`` always produces the same canonical ``_id``."""
        doc1 = normalize_host(self._make_cs_host(), {})
        doc2 = normalize_host(self._make_cs_host(), {})
        assert doc1["_id"] == doc2["_id"]


# ── Application normalization ───────────────────────────────────────────────


class TestNormalizeApplication:
    """Tests for ``normalize_application``."""

    def _make_cs_app(self, **overrides: object) -> dict:
        """Build a minimal CrowdStrike Discover application dict."""
        base = {
            "id": "app001",
            "name": "Google Chrome",
            "version": "125.0.6422.60",
            "vendor": "Google LLC",
            "installation_timestamp": "2024-03-01T00:00:00Z",
            "host": {"aid": "host001", "platform_name": "Windows"},
            "category": "Browser",
            "last_updated_timestamp": "2024-06-01T00:00:00Z",
        }
        base.update(overrides)
        return base

    def test_basic_app_normalization(self) -> None:
        """All key fields are mapped correctly."""
        doc = normalize_application(self._make_cs_app(), "2024-06-15T00:00:00Z")
        assert doc["source"] == "crowdstrike"
        assert doc["source_id"] == "app001"
        assert doc["_id"] == canonical_id("crowdstrike", "app:app001")
        assert doc["agent_id"] == "host001"
        assert doc["name"] == "Google Chrome"
        assert doc["version"] == "125.0.6422.60"
        assert doc["publisher"] == "Google LLC"
        assert doc["installed_at"] == "2024-03-01T00:00:00Z"
        assert doc["os_type"] == "windows"
        assert doc["app_type"] == "Browser"
        assert doc["active"] is True
        assert doc["synced_at"] == "2024-06-15T00:00:00Z"

    def test_normalized_name_strips_version(self) -> None:
        """``normalized_name`` strips the version suffix."""
        doc = normalize_application(self._make_cs_app(), "2024-06-15T00:00:00Z")
        assert "125.0.6422.60" not in doc["normalized_name"]
        assert "google chrome" in doc["normalized_name"]

    def test_missing_host_info(self) -> None:
        """Missing ``host`` dict falls back gracefully."""
        app = self._make_cs_app()
        del app["host"]
        app["aid"] = "direct_aid"
        doc = normalize_application(app, "2024-06-15T00:00:00Z")
        assert doc["agent_id"] == "direct_aid"

    def test_empty_app(self) -> None:
        """Empty app dict produces valid document without crash."""
        doc = normalize_application({}, "2024-06-15T00:00:00Z")
        assert doc["source"] == "crowdstrike"
        assert doc["name"] == ""
        assert doc["active"] is True


# ── Group normalization ─────────────────────────────────────────────────────


class TestNormalizeGroup:
    """Tests for ``normalize_group``."""

    def test_basic_group_normalization(self) -> None:
        """Key fields are mapped correctly."""
        raw = {
            "id": "grp001",
            "name": "Engineering Workstations",
            "description": "Eng team desktops",
            "group_type": "static",
            "assignment_rule": "",
            "created_timestamp": "2024-01-01T00:00:00Z",
            "modified_timestamp": "2024-06-01T00:00:00Z",
        }
        doc = normalize_group(raw)
        assert doc["source"] == "crowdstrike"
        assert doc["source_id"] == "grp001"
        assert doc["_id"] == canonical_id("crowdstrike", "group:grp001")
        assert doc["name"] == "Engineering Workstations"
        assert doc["description"] == "Eng team desktops"
        assert doc["type"] == "static"
        assert doc["is_default"] is False

    def test_empty_group(self) -> None:
        """Empty group dict produces valid document."""
        doc = normalize_group({})
        assert doc["source"] == "crowdstrike"
        assert doc["name"] == ""


# ── Helper functions ────────────────────────────────────────────────────────


class TestHelperFunctions:
    """Tests for normalizer helper functions."""

    @pytest.mark.parametrize(
        ("input_val", "expected"),
        [
            ("Windows", "windows"),
            ("Linux", "linux"),
            ("Mac", "macos"),
            ("WINDOWS", "windows"),
            ("mac", "macos"),
            ("ChromeOS", "chromeos"),
            ("", "unknown"),
        ],
    )
    def test_normalize_os_type(self, input_val: str, expected: str) -> None:
        assert _normalize_os_type(input_val) == expected

    @pytest.mark.parametrize(
        ("input_val", "expected"),
        [
            ("normal", "online"),
            ("contained", "contained"),
            ("containment_pending", "contained"),
            ("lift_containment_pending", "contained"),
            ("", "offline"),
            ("unknown_status", "offline"),
        ],
    )
    def test_normalize_status(self, input_val: str, expected: str) -> None:
        assert _normalize_status(input_val) == expected

    @pytest.mark.parametrize(
        ("input_val", "expected"),
        [
            ("Workstation", "desktop"),
            ("Server", "server"),
            ("Domain Controller Server", "server"),
            ("Laptop", "desktop"),
            ("Desktop", "desktop"),
            ("", "unknown"),
            ("IoT Gateway", "unknown"),
        ],
    )
    def test_normalize_machine_type(self, input_val: str, expected: str) -> None:
        assert _normalize_machine_type(input_val) == expected
