"""Unit tests for the tags domain matcher.

These tests use a minimal async mock cursor to exercise the matching logic
without a real MongoDB connection.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from domains.tags.entities import TagRule, TagRulePattern
from domains.tags.matcher import find_matching_agents


def _make_rule(*patterns: str) -> TagRule:
    return TagRule(
        tag_name="test-tag",
        patterns=[TagRulePattern(pattern=p, display_name=p.replace("*", "")) for p in patterns],
    )


def _make_db(agent_docs: list[dict]) -> MagicMock:
    """Build a minimal Motor-like mock where find() returns an async iterator."""
    async_cursor = MagicMock()
    async_cursor.__aiter__ = AsyncMock(return_value=iter(agent_docs))

    # Make cursor itself async-iterable
    class _Cursor:
        def __init__(self, docs: list[dict]) -> None:
            self._docs = docs
            self._idx = 0

        def __aiter__(self) -> _Cursor:
            return self

        async def __anext__(self) -> dict:
            if self._idx >= len(self._docs):
                raise StopAsyncIteration
            doc = self._docs[self._idx]
            self._idx += 1
            return doc

    db = MagicMock()
    db.__getitem__ = MagicMock(
        return_value=MagicMock(find=MagicMock(return_value=_Cursor(agent_docs)))
    )
    return db


class TestFindMatchingAgents:
    @pytest.mark.asyncio
    async def test_empty_patterns_returns_nothing(self) -> None:
        rule = _make_rule()
        db = _make_db([{"s1_agent_id": "a1", "hostname": "h1", "installed_app_names": ["python"]}])
        agents, total = await find_matching_agents(db, rule)
        assert total == 0
        assert agents == []

    @pytest.mark.asyncio
    async def test_matching_agent_returned(self) -> None:
        rule = _make_rule("siemens*")
        db = _make_db(
            [
                {
                    "s1_agent_id": "a1",
                    "hostname": "host-mfg",
                    "group_name": "Mfg",
                    "site_name": "SiteA",
                    "os_type": "windows",
                    "installed_app_names": ["siemens wincc", "notepad++"],
                }
            ]
        )
        agents, total = await find_matching_agents(db, rule)
        assert total == 1
        assert agents[0].hostname == "host-mfg"
        assert "siemens*" in agents[0].matched_patterns

    @pytest.mark.asyncio
    async def test_non_matching_agent_excluded(self) -> None:
        rule = _make_rule("siemens*")
        db = _make_db(
            [
                {
                    "s1_agent_id": "a1",
                    "hostname": "host-lab",
                    "group_name": "Labs",
                    "site_name": "SiteB",
                    "os_type": "linux",
                    "installed_app_names": ["python", "jupyter"],
                }
            ]
        )
        agents, total = await find_matching_agents(db, rule)
        assert total == 0
        assert agents == []

    @pytest.mark.asyncio
    async def test_multiple_patterns_any_match_is_sufficient(self) -> None:
        rule = _make_rule("siemens*", "python*")
        db = _make_db(
            [
                {
                    "s1_agent_id": "a1",
                    "hostname": "host-a",
                    "group_name": "",
                    "site_name": "",
                    "os_type": "windows",
                    "installed_app_names": ["siemens wincc"],
                },
                {
                    "s1_agent_id": "a2",
                    "hostname": "host-b",
                    "group_name": "",
                    "site_name": "",
                    "os_type": "linux",
                    "installed_app_names": ["python 3.12"],
                },
                {
                    "s1_agent_id": "a3",
                    "hostname": "host-c",
                    "group_name": "",
                    "site_name": "",
                    "os_type": "windows",
                    "installed_app_names": ["notepad"],
                },
            ]
        )
        agents, total = await find_matching_agents(db, rule)
        assert total == 2
        hostnames = {a.hostname for a in agents}
        assert "host-a" in hostnames
        assert "host-b" in hostnames
        assert "host-c" not in hostnames

    @pytest.mark.asyncio
    async def test_cap_limits_returned_agents(self) -> None:
        rule = _make_rule("python*")
        docs = [
            {
                "s1_agent_id": f"a{i}",
                "hostname": f"host-{i:03d}",
                "group_name": "",
                "site_name": "",
                "os_type": "linux",
                "installed_app_names": ["python"],
            }
            for i in range(10)
        ]
        db = _make_db(docs)
        agents, total = await find_matching_agents(db, rule, cap=3)
        assert total == 10
        assert len(agents) == 3

    @pytest.mark.asyncio
    async def test_cap_none_returns_all(self) -> None:
        rule = _make_rule("python*")
        docs = [
            {
                "s1_agent_id": f"a{i}",
                "hostname": f"host-{i:03d}",
                "group_name": "",
                "site_name": "",
                "os_type": "linux",
                "installed_app_names": ["python"],
            }
            for i in range(10)
        ]
        db = _make_db(docs)
        agents, total = await find_matching_agents(db, rule, cap=None)
        assert total == 10
        assert len(agents) == 10

    @pytest.mark.asyncio
    async def test_results_sorted_by_hostname(self) -> None:
        rule = _make_rule("python*")
        docs = [
            {
                "s1_agent_id": "a3",
                "hostname": "zebra",
                "group_name": "",
                "site_name": "",
                "os_type": "linux",
                "installed_app_names": ["python"],
            },
            {
                "s1_agent_id": "a1",
                "hostname": "alpha",
                "group_name": "",
                "site_name": "",
                "os_type": "linux",
                "installed_app_names": ["python"],
            },
            {
                "s1_agent_id": "a2",
                "hostname": "mango",
                "group_name": "",
                "site_name": "",
                "os_type": "linux",
                "installed_app_names": ["python"],
            },
        ]
        db = _make_db(docs)
        agents, _ = await find_matching_agents(db, rule, cap=None)
        assert [a.hostname for a in agents] == ["alpha", "mango", "zebra"]

    @pytest.mark.asyncio
    async def test_pattern_not_double_counted(self) -> None:
        """A pattern should appear only once in matched_patterns even if multiple apps match it."""
        rule = _make_rule("python*")
        docs = [
            {
                "s1_agent_id": "a1",
                "hostname": "host",
                "group_name": "",
                "site_name": "",
                "os_type": "linux",
                "installed_app_names": ["python 3.11", "python 3.12"],
            }
        ]
        db = _make_db(docs)
        agents, total = await find_matching_agents(db, rule, cap=None)
        assert total == 1
        assert agents[0].matched_patterns.count("python*") == 1

    @pytest.mark.asyncio
    async def test_empty_agent_fleet(self) -> None:
        rule = _make_rule("siemens*")
        db = _make_db([])
        agents, total = await find_matching_agents(db, rule)
        assert total == 0
        assert agents == []
