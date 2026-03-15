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
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet key from the JWT secret.

    Uses SHA-256 to hash the secret and base64-encodes the result
    to produce a valid Fernet key.

    Args:
        secret: The JWT secret key string.

    Returns:
        A 44-byte base64-encoded Fernet key.
    """
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string field for storage in MongoDB.

    Args:
        plaintext: The value to encrypt.

    Returns:
        An ``enc:``-prefixed ciphertext string.
    """
    from config import get_settings

    key = _derive_fernet_key(get_settings().jwt_secret_key)
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

    key = _derive_fernet_key(get_settings().jwt_secret_key)
    f = Fernet(key)
    try:
        return f.decrypt(stored[4:].encode()).decode()
    except InvalidToken:
        logger.warning("Failed to decrypt field — returning empty string")
        return ""
