"""AC-2 — the whole database yields nothing; the database plus the KEK yields the secret.

ADR-0014's envelope is what makes "a stolen pg_dump is ciphertext and nothing
else" a fact about the schema rather than about the code (T-027), and ADR-0032
is what keeps the KEK out of the dump: `.env` is backed up separately from and
never alongside it.
"""

import base64
import os
import secrets

import pytest

from prope.provider_access import crypto
from prope.provider_access.domain import CredentialRecord

SECRET = "sk-live-0123456789abcdef"


def _key() -> str:
    return base64.b64encode(secrets.token_bytes(crypto.KEK_BYTES)).decode()


@pytest.fixture
def kek(monkeypatch: pytest.MonkeyPatch) -> str:
    for name in list(os.environ):
        if name.startswith(crypto.KEK_ENVIRONMENT_PREFIX):
            monkeypatch.delenv(name, raising=False)
    material = _key()
    monkeypatch.setenv(f"{crypto.KEK_ENVIRONMENT_PREFIX}1", material)
    return material


def _record(encrypted: crypto.EncryptedCredential) -> CredentialRecord:
    return CredentialRecord(
        id="crd_01TEST",
        provider_config_id="prv_01TEST",
        ciphertext=encrypted.ciphertext,
        nonce=encrypted.nonce,
        wrapped_dek=encrypted.wrapped_dek,
        kek_version=encrypted.kek_version,
        last_four=encrypted.last_four,
    )


def test_a_credential_encrypts_and_decrypts_with_the_key(kek: str) -> None:
    encrypted = crypto.encrypt(SECRET)

    assert crypto.decrypt(_record(encrypted)) == SECRET


def test_the_stored_columns_hold_no_part_of_the_secret(kek: str) -> None:
    """Everything a dump would contain, checked against the plaintext."""
    encrypted = crypto.encrypt(SECRET)

    stored = " ".join(
        [encrypted.ciphertext, encrypted.nonce, encrypted.wrapped_dek, str(encrypted.kek_version)]
    )

    assert SECRET not in stored
    assert SECRET[:-4] not in stored
    assert encrypted.last_four == SECRET[-4:]


def test_the_database_alone_recovers_nothing(kek: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole of AC-2's first half: an attacker holds every row and no other
    material. `.env` is the material they do not have."""
    record = _record(crypto.encrypt(SECRET))

    monkeypatch.delenv(f"{crypto.KEK_ENVIRONMENT_PREFIX}1")

    with pytest.raises(crypto.KeyUnavailable):
        crypto.decrypt(record)


def test_the_wrong_key_recovers_nothing(kek: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A second install's key is not this install's key, and the failure is a
    cryptographic one rather than a wrong answer."""
    record = _record(crypto.encrypt(SECRET))

    monkeypatch.setenv(f"{crypto.KEK_ENVIRONMENT_PREFIX}1", _key())

    with pytest.raises(Exception) as failure:
        crypto.decrypt(record)

    assert not isinstance(failure.value, AssertionError)


def test_two_encryptions_of_one_secret_share_no_ciphertext(kek: str) -> None:
    """A per-credential data key and a fresh nonce, so two workspaces holding
    the same provider key are not visibly holding the same provider key."""
    first = crypto.encrypt(SECRET)
    second = crypto.encrypt(SECRET)

    assert first.ciphertext != second.ciphertext
    assert first.nonce != second.nonce
    assert first.wrapped_dek != second.wrapped_dek


def test_a_row_naming_an_absent_key_version_fails_loudly(
    kek: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A-135's realistic failure: a deploy that dropped an old
    `PROPE_KEK_V<n>` before every row had been re-wrapped."""
    record = _record(crypto.encrypt(SECRET))
    monkeypatch.setenv(f"{crypto.KEK_ENVIRONMENT_PREFIX}2", _key())
    monkeypatch.delenv(f"{crypto.KEK_ENVIRONMENT_PREFIX}1")

    with pytest.raises(crypto.KeyUnavailable) as failure:
        crypto.decrypt(record)

    assert "kek_version 1" in str(failure.value)


def test_a_rotation_rewraps_every_row_without_touching_a_plaintext_credential(
    kek: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-13. The highest present version wraps; the old one can then be
    removed and every credential still decrypts."""
    original = _record(crypto.encrypt(SECRET))
    assert original.kek_version == 1

    monkeypatch.setenv(f"{crypto.KEK_ENVIRONMENT_PREFIX}2", _key())
    wrapped_dek, version = crypto.rewrap(original)

    rewrapped = CredentialRecord(
        id=original.id,
        provider_config_id=original.provider_config_id,
        ciphertext=original.ciphertext,
        nonce=original.nonce,
        wrapped_dek=wrapped_dek,
        kek_version=version,
        last_four=original.last_four,
    )

    assert version == 2
    assert rewrapped.ciphertext == original.ciphertext

    monkeypatch.delenv(f"{crypto.KEK_ENVIRONMENT_PREFIX}1")

    assert crypto.decrypt(rewrapped) == SECRET


def test_the_gauge_reads_one_when_no_key_is_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gauge `ProviderKekUnavailable` pages on, and it must never be
    confused with a provider outage."""
    for name in list(os.environ):
        if name.startswith(crypto.KEK_ENVIRONMENT_PREFIX):
            monkeypatch.delenv(name, raising=False)

    assert crypto.refresh_kek_gauge() is False

    monkeypatch.setenv(f"{crypto.KEK_ENVIRONMENT_PREFIX}1", _key())

    assert crypto.refresh_kek_gauge() is True
