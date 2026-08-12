"""ADR-0014's envelope, and A-135's `PROPE_KEK_V<n>` selection."""

import base64
import os
import re
import secrets
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr

from prope.provider_access.domain import CredentialRecord
from prope.provider_access.observability import kek_unavailable

__all__ = [
    "KEK_ENVIRONMENT_PREFIX",
    "EncryptedCredential",
    "KeyUnavailable",
    "decrypt",
    "encrypt",
    "highest_kek_version",
    "load_keks",
    "refresh_kek_gauge",
    "rewrap",
]

KEK_ENVIRONMENT_PREFIX = "PROPE_KEK_V"

KEK_ENVIRONMENT_NAME = re.compile(rf"^{KEK_ENVIRONMENT_PREFIX}(\d+)$")

KEK_BYTES = 32

DEK_BYTES = 32

NONCE_BYTES = 12

LAST_FOUR = 4


class KeyUnavailable(Exception):  # noqa: N818
    """No key-encryption key is loadable, or the row names one that is absent."""


@dataclass(frozen=True, slots=True)
class EncryptedCredential:
    ciphertext: str = field(repr=False)
    nonce: str = field(repr=False)
    wrapped_dek: str = field(repr=False)
    kek_version: int
    last_four: str


def load_keks() -> dict[int, SecretStr]:
    keys: dict[int, SecretStr] = {}
    for name, value in os.environ.items():
        matched = KEK_ENVIRONMENT_NAME.match(name)
        if matched is None or not value:
            continue
        keys[int(matched.group(1))] = SecretStr(value)
    return keys


def refresh_kek_gauge() -> bool:
    available = bool(load_keks())
    kek_unavailable.set(0 if available else 1)
    return available


def highest_kek_version() -> int:
    keys = load_keks()
    if not keys:
        kek_unavailable.set(1)
        raise KeyUnavailable(
            "no PROPE_KEK_V<n> entry is present in this process's environment; "
            "no credential can be encrypted or decrypted"
        )
    kek_unavailable.set(0)
    return max(keys)


def _kek(version: int) -> bytes:
    keys = load_keks()
    if not keys:
        kek_unavailable.set(1)
        raise KeyUnavailable(
            "no PROPE_KEK_V<n> entry is present in this process's environment; "
            "no credential can be encrypted or decrypted"
        )
    kek_unavailable.set(0)
    if version not in keys:
        raise KeyUnavailable(
            f"the row names kek_version {version} and no {KEK_ENVIRONMENT_PREFIX}{version} "
            "entry is present"
        )
    material = base64.b64decode(keys[version].get_secret_value())
    if len(material) != KEK_BYTES:
        raise KeyUnavailable(
            f"{KEK_ENVIRONMENT_PREFIX}{version} decodes to {len(material)} bytes; "
            f"AES-256-GCM needs {KEK_BYTES}"
        )
    return material


def _wrap(dek: bytes, version: int) -> str:
    nonce = secrets.token_bytes(NONCE_BYTES)
    wrapped = AESGCM(_kek(version)).encrypt(nonce, dek, None)
    return base64.b64encode(nonce + wrapped).decode()


def _unwrap(wrapped_dek: str, version: int) -> bytes:
    raw = base64.b64decode(wrapped_dek)
    return AESGCM(_kek(version)).decrypt(raw[:NONCE_BYTES], raw[NONCE_BYTES:], None)


def encrypt(secret: str) -> EncryptedCredential:
    version = highest_kek_version()
    dek = secrets.token_bytes(DEK_BYTES)
    nonce = secrets.token_bytes(NONCE_BYTES)
    ciphertext = AESGCM(dek).encrypt(nonce, secret.encode(), None)
    return EncryptedCredential(
        ciphertext=base64.b64encode(ciphertext).decode(),
        nonce=base64.b64encode(nonce).decode(),
        wrapped_dek=_wrap(dek, version),
        kek_version=version,
        last_four=secret[-LAST_FOUR:].rjust(LAST_FOUR, "*"),
    )


def decrypt(record: CredentialRecord) -> str:
    dek = _unwrap(record.wrapped_dek, record.kek_version)
    plaintext = AESGCM(dek).decrypt(
        base64.b64decode(record.nonce), base64.b64decode(record.ciphertext), None
    )
    return plaintext.decode()


def rewrap(record: CredentialRecord) -> tuple[str, int]:
    version = highest_kek_version()
    dek = _unwrap(record.wrapped_dek, record.kek_version)
    return _wrap(dek, version), version
