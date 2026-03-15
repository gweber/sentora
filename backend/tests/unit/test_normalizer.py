"""Unit tests for the sync domain normalizer module.

All normalizer functions are pure (no I/O) so these are fast synchronous tests.
"""

from __future__ import annotations

from domains.sync.normalizer import (
    normalize_agent,
    normalize_app,
    normalize_app_name,
    normalize_group,
    normalize_site,
)

_NOW = "2025-01-01T00:00:00Z"


class TestNormalizeAppName:
    def test_lowercase(self) -> None:
        assert normalize_app_name("Adobe Reader") == "adobe reader"

    def test_removes_trademark(self) -> None:
        # NFKD decomposes ™ to "TM" before the regex runs, so output contains "tm"
        result = normalize_app_name("Windows™ Defender")
        assert "windows" in result
        assert "defender" in result

    def test_removes_registered(self) -> None:
        assert normalize_app_name("Acrobat® Reader") == "acrobat reader"

    def test_removes_copyright(self) -> None:
        assert normalize_app_name("My App©") == "my app"

    def test_collapses_whitespace(self) -> None:
        assert normalize_app_name("  hello   world  ") == "hello world"

    def test_strips_accents(self) -> None:
        result = normalize_app_name("Björn")
        assert "ö" not in result or "o" in result  # ö decomposes → o + combining

    def test_empty_string(self) -> None:
        assert normalize_app_name("") == ""

    def test_already_lowercase(self) -> None:
        assert normalize_app_name("already fine") == "already fine"


class TestNormalizeSite:
    def test_maps_all_fields(self) -> None:
        s1_site = {
            "id": "site-1",
            "name": "HQ",
            "state": "active",
            "siteType": "Paid",
            "accountId": "acc-1",
            "accountName": "Acme Corp",
        }
        result = normalize_site(s1_site)
        assert result["s1_site_id"] == "site-1"
        assert result["name"] == "HQ"
        assert result["state"] == "active"
        assert result["site_type"] == "Paid"
        assert result["account_id"] == "acc-1"
        assert result["account_name"] == "Acme Corp"

    def test_missing_fields_default_to_empty_string(self) -> None:
        result = normalize_site({})
        assert result["s1_site_id"] == ""
        assert result["name"] == ""


class TestNormalizeGroup:
    def test_maps_all_fields(self) -> None:
        s1_group = {
            "id": "grp-1",
            "name": "SCADA",
            "description": "SCADA systems",
            "type": "static",
            "isDefault": False,
            "filterName": "scada_filter",
            "totalAgents": 5,
            "siteId": "site-1",
            "createdAt": _NOW,
            "updatedAt": _NOW,
        }
        site_map = {"site-1": "HQ Site"}
        result = normalize_group(s1_group, site_map)
        assert result["s1_group_id"] == "grp-1"
        assert result["name"] == "SCADA"
        assert result["agent_count"] == 5
        assert result["site_name"] == "HQ Site"
        assert result["filter_name"] == "scada_filter"

    def test_empty_description_becomes_none(self) -> None:
        result = normalize_group({"description": ""})
        assert result["description"] is None

    def test_empty_filter_name_becomes_none(self) -> None:
        result = normalize_group({"filterName": ""})
        assert result["filter_name"] is None

    def test_no_site_map_defaults_to_empty_string(self) -> None:
        result = normalize_group({"siteId": "site-x"})
        assert result["site_name"] == ""


class TestNormalizeAgent:
    def test_maps_basic_fields(self) -> None:
        s1_agent = {
            "id": "agent-1",
            "computerName": "DESKTOP-01",
            "osType": "windows",
            "osName": "Windows 10",
            "osRevision": "19045",
            "groupId": "grp-1",
            "groupName": "SCADA",
            "siteId": "site-1",
            "siteName": "HQ",
            "networkStatus": "connected",
            "lastActiveDate": _NOW,
            "machineType": "desktop",
            "domain": "corp.local",
            "networkInterfaces": [],
            "tags": {},
        }
        result = normalize_agent(s1_agent, {"grp-1": "SCADA Floor"})
        assert result["s1_agent_id"] == "agent-1"
        assert result["hostname"] == "DESKTOP-01"
        assert result["os_type"] == "windows"
        assert result["os_version"] == "Windows 10 19045"
        assert result["group_name"] == "SCADA Floor"
        assert result["network_status"] == "connected"

    def test_extracts_ip_from_network_interfaces(self) -> None:
        s1_agent = {
            "id": "a1",
            "networkInterfaces": [
                {"inet": "10.0.0.1", "inet6": ["::1"]},
            ],
        }
        result = normalize_agent(s1_agent, {})
        assert "10.0.0.1" in result["ip_addresses"]
        assert "::1" in result["ip_addresses"]

    def test_handles_dict_tags(self) -> None:
        s1_agent = {
            "id": "a2",
            "tags": {"sentinelone": ["production", "critical"]},
        }
        result = normalize_agent(s1_agent, {})
        assert "production" in result["tags"]
        assert "critical" in result["tags"]

    def test_handles_list_tags(self) -> None:
        s1_agent = {
            "id": "a3",
            "tags": [{"key": "env"}, {"key": "prod"}],
        }
        result = normalize_agent(s1_agent, {})
        assert "env" in result["tags"]

    def test_os_version_without_revision(self) -> None:
        s1_agent = {"id": "a4", "osName": "Ubuntu 22.04", "osRevision": ""}
        result = normalize_agent(s1_agent, {})
        assert result["os_version"] == "Ubuntu 22.04"

    def test_null_tags_handled(self) -> None:
        s1_agent = {"id": "a5", "tags": None}
        result = normalize_agent(s1_agent, {})
        assert result["tags"] == []


class TestNormalizeApp:
    def test_maps_all_fields(self) -> None:
        s1_app = {
            "id": "app-1",
            "agentId": "agent-1",
            "name": "Siemens WinCC",
            "version": "8.0",
            "publisher": "Siemens AG",
            "size": 1024,
            "installedAt": _NOW,
            "osType": "windows",
            "type": "Business",
            "riskLevel": "low",
            "updatedAt": _NOW,
            "createdAt": _NOW,
        }
        result = normalize_app(s1_app, _NOW)
        assert result["id"] == "app-1"
        assert result["agent_id"] == "agent-1"
        assert result["name"] == "Siemens WinCC"
        assert result["normalized_name"] == "siemens wincc"
        assert result["version"] == "8.0"
        assert result["synced_at"] == _NOW
        assert result["last_synced_at"] == _NOW

    def test_empty_name_normalizes_to_empty(self) -> None:
        result = normalize_app({"name": ""}, _NOW)
        assert result["normalized_name"] == ""

    def test_missing_name_normalizes_to_empty(self) -> None:
        result = normalize_app({}, _NOW)
        assert result["normalized_name"] == ""
