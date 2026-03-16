"""Unit tests for API key generation, hashing, scope expansion, and validation."""

from __future__ import annotations

import hashlib

from domains.api_keys.entities import (
    AVAILABLE_SCOPES,
    READ_SCOPES,
    WRITE_SCOPES,
    expand_scopes,
)
from domains.api_keys.service import generate_api_key, hash_key


class TestKeyGeneration:
    """Tests for the API key generation function."""

    def test_key_format_has_correct_prefix(self) -> None:
        full_key, prefix, key_hash = generate_api_key()
        assert full_key.startswith("sentora_sk_live_")

    def test_key_has_sufficient_entropy(self) -> None:
        """192 bits of entropy = 48 hex characters after the prefix."""
        full_key, _, _ = generate_api_key()
        random_part = full_key.removeprefix("sentora_sk_live_")
        assert len(random_part) == 48
        # Verify it's valid hex
        int(random_part, 16)

    def test_key_prefix_is_first_20_chars(self) -> None:
        full_key, prefix, _ = generate_api_key()
        assert prefix == full_key[:20]
        assert len(prefix) == 20

    def test_key_hash_matches_sha256(self) -> None:
        full_key, _, key_hash = generate_api_key()
        expected = hashlib.sha256(full_key.encode()).hexdigest()
        assert key_hash == expected

    def test_generated_keys_are_unique(self) -> None:
        keys = {generate_api_key()[0] for _ in range(100)}
        assert len(keys) == 100

    def test_hash_key_matches_generation(self) -> None:
        full_key, _, expected_hash = generate_api_key()
        assert hash_key(full_key) == expected_hash

    def test_key_is_grepable(self) -> None:
        """Keys should be detectable by secret scanners."""
        full_key, _, _ = generate_api_key()
        assert "sentora_sk_" in full_key


class TestScopeExpansion:
    """Tests for scope convenience group expansion."""

    def test_expand_read_all(self) -> None:
        expanded = expand_scopes(["read:all"])
        assert expanded == READ_SCOPES

    def test_expand_write_all(self) -> None:
        expanded = expand_scopes(["write:all"])
        assert READ_SCOPES.issubset(expanded)
        assert WRITE_SCOPES.issubset(expanded)

    def test_expand_individual_scope(self) -> None:
        expanded = expand_scopes(["agents:read"])
        assert expanded == {"agents:read"}

    def test_expand_mixed(self) -> None:
        expanded = expand_scopes(["agents:read", "sync:trigger"])
        assert expanded == {"agents:read", "sync:trigger"}

    def test_expand_empty_list(self) -> None:
        expanded = expand_scopes([])
        assert expanded == set()

    def test_all_read_scopes_end_with_read(self) -> None:
        for scope in READ_SCOPES:
            assert scope.endswith(":read")

    def test_write_scopes_do_not_include_convenience(self) -> None:
        assert "read:all" not in WRITE_SCOPES
        assert "write:all" not in WRITE_SCOPES

    def test_available_scopes_has_descriptions(self) -> None:
        for _scope, desc in AVAILABLE_SCOPES.items():
            assert isinstance(desc, str)
            assert len(desc) > 0
