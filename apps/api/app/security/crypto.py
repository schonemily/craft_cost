from __future__ import annotations
import os
from base64 import b64decode, b64encode
from typing import Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Minimal AES‑GCM helpers for field‑level encryption.
# KEY: 32‑byte base64 string in env AES_GCM_KEY; dev only here, use KMS in prod.


def _get_key() -> bytes:
    key_b64 = os.getenv("AES_GCM_KEY")
    if not key_b64:
        # Development fallback: DO NOT use in production.
        # Keeping deterministic key for dev containers.
        key_b64 = b64encode(b"0" * 32).decode()
    return b64decode(key_b64)


def encrypt_field(plaintext: str) -> str:
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return b64encode(nonce + ct).decode("utf-8")


def decrypt_field(token: str) -> str:
    raw = b64decode(token)
    nonce, ct = raw[:12], raw[12:]
    aesgcm = AESGCM(_get_key())
    pt = aesgcm.decrypt(nonce, ct, None)
    return pt.decode("utf-8")
