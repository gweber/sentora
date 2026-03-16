"""Tests for the symmetric field encryption utility."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestCrypto:
    """Test encrypt/decrypt round-trip and legacy plaintext handling."""

    def _mock_settings(self, key: str = "test-secret-key-for-unit-tests-only"):  # noqa: ANN202
        """Return a mock settings object with a fixed encryption key."""
        from unittest.mock import MagicMock

        s = MagicMock()
        s.field_encryption_key = key
        return s

    def test_round_trip(self) -> None:
        """Encrypting then decrypting should return the original value."""
        with patch("config.get_settings", return_value=self._mock_settings()):
            from utils.crypto import decrypt_field, encrypt_field

            original = "my-webhook-secret-abc123"
            encrypted = encrypt_field(original)
            assert encrypted.startswith("enc:")
            assert encrypted != original
            decrypted = decrypt_field(encrypted)
            assert decrypted == original

    def test_decrypt_plaintext_passthrough(self) -> None:
        """Legacy plaintext values (no enc: prefix) should pass through unchanged."""
        with patch("config.get_settings", return_value=self._mock_settings()):
            from utils.crypto import decrypt_field

            assert decrypt_field("plain-secret") == "plain-secret"

    def test_encrypt_produces_different_ciphertext(self) -> None:
        """Each encryption should produce different ciphertext (Fernet uses random IV)."""
        with patch("config.get_settings", return_value=self._mock_settings()):
            from utils.crypto import encrypt_field

            a = encrypt_field("same-input")
            b = encrypt_field("same-input")
            assert a != b  # different IVs

    def test_decrypt_wrong_key_raises(self) -> None:
        """Decrypting with a different key should raise ValueError."""
        with patch("config.get_settings", return_value=self._mock_settings("key-one")):
            from utils.crypto import encrypt_field

            encrypted = encrypt_field("secret")

        with (
            patch("config.get_settings", return_value=self._mock_settings("key-two")),
            pytest.raises(ValueError, match="Failed to decrypt"),
        ):
            from utils.crypto import decrypt_field

            decrypt_field(encrypted)

    def test_decrypt_none_returns_none(self) -> None:
        """decrypt_field(None) should return None without crashing (AUDIT-032)."""
        from utils.crypto import decrypt_field

        assert decrypt_field(None) is None

    def test_decrypt_empty_string_returns_empty(self) -> None:
        """decrypt_field('') should return '' without crashing (AUDIT-032)."""
        from utils.crypto import decrypt_field

        assert decrypt_field("") == ""
