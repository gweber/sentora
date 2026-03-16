"""Tests for the symmetric field encryption utility."""

from __future__ import annotations

from unittest.mock import patch


class TestCrypto:
    """Test encrypt/decrypt round-trip and legacy plaintext handling."""

    def _mock_settings(self):  # noqa: ANN202
        """Return a mock settings object with a fixed JWT secret."""
        from unittest.mock import MagicMock

        s = MagicMock()
        s.jwt_secret_key = "test-secret-key-for-unit-tests-only"
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

    def test_decrypt_wrong_key_returns_empty(self) -> None:
        """Decrypting with a different key should return empty string (not crash)."""
        mock1 = self._mock_settings()
        mock2 = self._mock_settings()
        mock2.jwt_secret_key = "different-secret-key"

        with patch("config.get_settings", return_value=mock1):
            from utils.crypto import encrypt_field

            encrypted = encrypt_field("secret")

        with patch("config.get_settings", return_value=mock2):
            from utils.crypto import decrypt_field

            result = decrypt_field(encrypted)
            assert result == ""
