"""Tests for export service utility functions."""

from __future__ import annotations

from domains.export.service import _build_cache_key, _build_filter_info


class TestBuildCacheKey:
    def test_consistent_hashing(self) -> None:
        k1 = _build_cache_key(page=1, page_size=100)
        k2 = _build_cache_key(page=1, page_size=100)
        assert k1 == k2
        assert len(k1) == 64  # SHA256 hex digest

    def test_different_params_different_keys(self) -> None:
        k1 = _build_cache_key(page=1, page_size=100)
        k2 = _build_cache_key(page=2, page_size=100)
        assert k1 != k2

    def test_dict_ordering_stable(self) -> None:
        k1 = _build_cache_key(a=1, b=2, c=3)
        k2 = _build_cache_key(c=3, a=1, b=2)
        assert k1 == k2

    def test_none_values(self) -> None:
        k = _build_cache_key(scope_groups=None, classification=None)
        assert isinstance(k, str) and len(k) == 64

    def test_list_params(self) -> None:
        k = _build_cache_key(scope_groups=["group1", "group2"])
        assert isinstance(k, str) and len(k) == 64


class TestBuildFilterInfo:
    def test_no_filters(self) -> None:
        result = _build_filter_info(None, None, None)
        assert result == {}

    def test_groups_only(self) -> None:
        result = _build_filter_info(["group1", "group2"], None, None)
        assert result == {"scope_groups": ["group1", "group2"]}

    def test_tags_only(self) -> None:
        result = _build_filter_info(None, ["tag1"], None)
        assert result == {"scope_tags": ["tag1"]}

    def test_classification_only(self) -> None:
        result = _build_filter_info(None, None, "managed")
        assert result == {"classification": "managed"}

    def test_all_filters(self) -> None:
        result = _build_filter_info(["g1"], ["t1"], "unmanaged")
        assert "scope_groups" in result
        assert "scope_tags" in result
        assert "classification" in result
