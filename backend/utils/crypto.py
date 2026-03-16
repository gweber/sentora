"""Symmetric encryption for sensitive fields stored in MongoDB.

Uses the JWT secret key as the basis for deriving a Fernet encryption key.
This ensures webhook secrets are encrypted at rest without requiring a
separate key management system.

The encryption is transparent to callers — ``encrypt_field`` and
``decrypt_field`` handle the encoding/decoding.

Fields are prefixed with ``enc:`` so the code can detect whether a
stored value is encrypted (migration-safe for existing plaintext values).
"""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet key using HKDF with domain separation.

    Uses HKDF-SHA256 with a fixed salt and info parameter to derive
    a cryptographically proper key from the application secret.
    """
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    hkdf = HKDF(
        algorithm=SHA256(),
        length=32,
        salt=b"sentora-field-encryption-v1",
        info=b"fernet-key-derivation",
    )
    derived = hkdf.derive(secret.encode())
    return base64.urlsafe_b64encode(derived)


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string field for storage in MongoDB.

    Args:
        plaintext: The value to encrypt.

    Returns:
        An ``enc:``-prefixed ciphertext string.
    """
    from config import get_settings

    key = _derive_fernet_key(get_settings().field_encryption_key)
    f = Fernet(key)
    token = f.encrypt(plaintext.encode())
    return "enc:" + token.decode()


def decrypt_field(stored: str) -> str:
    """Decrypt a stored field value.

    If the value is not ``enc:``-prefixed (legacy plaintext), it is
    returned as-is for backwards compatibility.

    Args:
        stored: The stored value (encrypted or plaintext).

    Returns:
        The decrypted plaintext string.
    """
    if not stored.startswith("enc:"):
        return stored

    from config import get_settings

    key = _derive_fernet_key(get_settings().field_encryption_key)
    f = Fernet(key)
    try:
        return f.decrypt(stored[4:].encode()).decode()
    except InvalidToken as exc:
        logger.warning("Failed to decrypt field — key may have changed")
        raise ValueError("Failed to decrypt field — key may have changed") from exc
