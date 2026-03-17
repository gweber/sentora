"""Unit tests for the tags matcher — covers glob, exact, and mixed pattern branches."""

from __future__ import annotations

import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.tags.entities import TagRule, TagRulePattern
from domains.tags.matcher import _is_exact_pattern, find_matching_agents


def _pat(pattern: str) -> TagRulePattern:
    """Shortcut to build a TagRulePattern for tests."""
    return TagRulePattern(pattern=pattern, display_name=pattern)


class TestIsExactPattern:
    def test_exact_no_metachar(self) -> None:
        assert _is_exact_pattern("Google Chrome") is True

    def test_glob_star(self) -> None:
        assert _is_exact_pattern("Chrome*") is False

    def test_glob_question(self) -> None:
        assert _is_exact_pattern("Chrome?") is False

    def test_empty_is_exact(self) -> None:
        assert _is_exact_pattern("") is True


class TestFindMatchingAgents:
    @pytest.mark.asyncio
    async def test_empty_patterns_returns_empty(self, test_db: AsyncIOMotorDatabase) -> None:
        rule = TagRule(tag_name="test", patterns=[])
        agents, total = await find_matching_agents(test_db, rule)
        assert agents == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_exact_pattern_match(self, test_db: AsyncIOMotorDatabase) -> None:
        await test_db["agents"].insert_one(
            {
                "source": "sentinelone",
                "source_id": "a1",
                "hostname": "host1",
                "group_name": "g1",
                "site_name": "s1",
                "os_type": "windows",
                "installed_app_names": ["Google Chrome", "Firefox"],
                "tags": [],
            }
        )
        rule = TagRule(tag_name="browser", patterns=[_pat("Google Chrome")])
        agents, total = await find_matching_agents(test_db, rule)
        assert total == 1
        assert agents[0].hostname == "host1"
        assert "Google Chrome" in agents[0].matched_patterns

    @pytest.mark.asyncio
    async def test_exact_pattern_case_insensitive(self, test_db: AsyncIOMotorDatabase) -> None:
        await test_db["agents"].insert_one(
            {
                "source": "sentinelone",
                "source_id": "a2",
                "hostname": "host2",
                "group_name": "g1",
                "site_name": "s1",
                "os_type": "windows",
                "installed_app_names": ["google chrome"],
                "tags": [],
            }
        )
        rule = TagRule(tag_name="browser", patterns=[_pat("Google Chrome")])
        agents, total = await find_matching_agents(test_db, rule)
        assert total == 1

    @pytest.mark.asyncio
    async def test_glob_pattern_match(self, test_db: AsyncIOMotorDatabase) -> None:
        await test_db["agents"].insert_one(
            {
                "source": "sentinelone",
                "source_id": "a3",
                "hostname": "host3",
                "group_name": "g1",
                "site_name": "s1",
                "os_type": "windows",
                "installed_app_names": ["Chrome 120.0", "Slack"],
                "tags": [],
            }
        )
        rule = TagRule(tag_name="browser", patterns=[_pat("Chrome*")])
        agents, total = await find_matching_agents(test_db, rule)
        assert total == 1
        assert "Chrome*" in agents[0].matched_patterns

    @pytest.mark.asyncio
    async def test_mixed_exact_and_glob(self, test_db: AsyncIOMotorDatabase) -> None:
        await test_db["agents"].insert_many(
            [
                {
                    "source": "sentinelone",
                    "source_id": "a4",
                    "hostname": "host4",
                    "group_name": "g1",
                    "site_name": "s1",
                    "os_type": "windows",
                    "installed_app_names": ["Slack"],
                    "tags": [],
                },
                {
                    "source": "sentinelone",
                    "source_id": "a5",
                    "hostname": "host5",
                    "group_name": "g1",
                    "site_name": "s1",
                    "os_type": "linux",
                    "installed_app_names": ["Chrome 120.0"],
                    "tags": [],
                },
            ]
        )
        rule = TagRule(
            tag_name="comms",
            patterns=[_pat("Slack"), _pat("Chrome*")],
        )
        agents, total = await find_matching_agents(test_db, rule)
        assert total == 2

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, test_db: AsyncIOMotorDatabase) -> None:
        await test_db["agents"].insert_one(
            {
                "source": "sentinelone",
                "source_id": "a6",
                "hostname": "host6",
                "group_name": "g1",
                "site_name": "s1",
                "os_type": "windows",
                "installed_app_names": ["Notepad"],
                "tags": [],
            }
        )
        rule = TagRule(tag_name="browser", patterns=[_pat("Firefox")])
        agents, total = await find_matching_agents(test_db, rule)
        assert total == 0
        assert agents == []

    @pytest.mark.asyncio
    async def test_cap_limits_results(self, test_db: AsyncIOMotorDatabase) -> None:
        for i in range(5):
            await test_db["agents"].insert_one(
                {
                    "source": "sentinelone",
                    "source_id": f"cap_{i}",
                    "hostname": f"host_cap_{i}",
                    "group_name": "g1",
                    "site_name": "s1",
                    "os_type": "windows",
                    "installed_app_names": ["TargetApp"],
                    "tags": [],
                }
            )
        rule = TagRule(tag_name="target", patterns=[_pat("TargetApp")])
        agents, total = await find_matching_agents(test_db, rule, cap=3)
        assert total == 5
        assert len(agents) == 3

    @pytest.mark.asyncio
    async def test_empty_installed_apps_skipped(self, test_db: AsyncIOMotorDatabase) -> None:
        await test_db["agents"].insert_one(
            {
                "source": "sentinelone",
                "source_id": "a_empty",
                "hostname": "host_empty",
                "group_name": "g1",
                "site_name": "s1",
                "os_type": "windows",
                "installed_app_names": [],
                "tags": [],
            }
        )
        rule = TagRule(tag_name="browser", patterns=[_pat("Chrome*")])
        agents, total = await find_matching_agents(test_db, rule)
        assert total == 0

    @pytest.mark.asyncio
    async def test_unlimited_cap(self, test_db: AsyncIOMotorDatabase) -> None:
        """cap=None returns all matching agents."""
        for i in range(3):
            await test_db["agents"].insert_one(
                {
                    "source": "sentinelone",
                    "source_id": f"unlim_{i}",
                    "hostname": f"host_unlim_{i}",
                    "group_name": "g1",
                    "site_name": "s1",
                    "os_type": "windows",
                    "installed_app_names": ["App"],
                    "tags": [],
                }
            )
        rule = TagRule(tag_name="all", patterns=[_pat("App")])
        agents, total = await find_matching_agents(test_db, rule, cap=None)
        assert total == 3
        assert len(agents) == 3
