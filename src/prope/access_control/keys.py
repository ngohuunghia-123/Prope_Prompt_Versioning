"""`prope_<key_id>_<secret>` — minted once, hashed fast, parsed without the secret.

**The other hash in this module, and deliberately not the one in `passwords.py`.**
A password is human-chosen and low-entropy, so it is hashed slowly to make
guessing expensive. A consumer key's secret is 256 bits from a CSPRNG, so there
is nothing to guess and a slow KDF would buy nothing while spending tens of
milliseconds of the gateway's 50 ms budget on every single request. Worse, a
salted hash **cannot be indexed**, so authentication would become a scan of every
key in the workspace. ADR-0021 is the record of why one module holds two secrets
under two primitives; anybody reading these two files together will assume one is
a mistake, which is why the reason is on both.

**The id is embedded in the presented string, and that is what makes the lookup a
primary-key read.** `key_id` is the row's own `key_`-prefixed ULID, so
verification is one indexed `access.lookup_api_key` call plus one
`hmac.compare_digest`.

**The parse discards the secret before it returns.** A-046 forbids logging a key
secret in any form, and the format makes logging *the whole presented string* the
easiest possible mistake — it looks like an identifier and it starts with one.
:func:`parse_presented_key` therefore returns a :class:`KeyPresentation`, which
carries the loggable `key_id` and the digest, and has no field the secret could
survive in. The rule is structural rather than remembered.

**Nothing here reads the database or decides anything.** Comparison lives in
`bootstrap.authenticate_api_key`, which holds the stored hash; ADR-0042 keeps the
security decision out of the `SECURITY DEFINER` function, and this module keeps
it out of the parser too.
"""

import hashlib
import hmac
import secrets

from ulid import ULID

from prope.access_control.domain import KeyPresentation

__all__ = [
    "KEY_ID_PREFIX",
    "LAST_FOUR_LENGTH",
    "PRESENTED_PREFIX",
    "SECRET_BYTES",
    "MintedKey",
    "hash_secret",
    "mint_key",
    "parse_presented_key",
    "secrets_match",
]

#: A-045 / ADR-0003's typed prefix for the row, and revision 0006 enforces it.
KEY_ID_PREFIX = "key_"

#: The literal every presented key opens with. Fixed rather than configurable: a
#: consumer's client library will hard-code it, and the format is the thing
#: ADR-0021 says changing costs every consumer a re-key.
PRESENTED_PREFIX = "prope"

#: 256 bits (A-113). This number is what makes the fast hash correct — the whole
#: argument for SHA-256 here is that the secret has nothing guessable in it.
SECRET_BYTES = 32

#: What the dashboard shows so a person can tell two keys apart. Four characters
#: of a 43-character base64url secret is ~24 bits, which identifies a key among a
#: workspace's handful and is nowhere near enough to shorten a search of 2^256.
LAST_FOUR_LENGTH = 4

#: `_` is the separator, and the id contains one of its own — `key_01H...`. So the
#: split is bounded at three, giving exactly four parts, and the fourth keeps any
#: separator the secret might contain. `ck_api_key_id_has_no_separator` in
#: revision 0006 is what guarantees the third part is the whole ULID, so the
#: reassembly below cannot be ambiguous.
_PARTS = 4


class MintedKey:
    """A freshly created key: the row's columns, plus the one-time plaintext.

    Not frozen and not a dataclass, deliberately. `__slots__` with no `__repr__`
    and no `__eq__` means the plaintext cannot reach a log line through a repr, a
    pytest assertion diff, or a `structlog` value — the three routes by which a
    "temporary" debugging line has historically leaked a secret. A frozen
    dataclass would have given all three away for free.

    The plaintext appears in exactly one response body, the creation one, and is
    never recoverable (A-113, AC-7). Losing it means issuing a new key, which is
    a two-click operation and the correct outcome.
    """

    __slots__ = ("key_id", "key_hash", "last_four", "plaintext")

    def __init__(self, key_id: str, key_hash: str, last_four: str, plaintext: str) -> None:
        self.key_id = key_id
        self.key_hash = key_hash
        self.last_four = last_four
        self.plaintext = plaintext

    def __repr__(self) -> str:
        """The id and nothing else. A default repr here is AC-7's failure."""
        return f"<MintedKey {self.key_id}>"


def hash_secret(secret: str) -> str:
    """SHA-256 hex of the secret. Unsalted, and the entropy is why that is fine.

    A salt defends against precomputation over a small candidate space. There is
    no candidate space here: the secret is 32 bytes from `secrets.token_urlsafe`,
    so a rainbow table over it is a table over 2^256 values. What a salt *would*
    cost is the index — a salted digest differs per row, so `key_hash` could not
    be compared without first reading the row, and reading the row is what the
    embedded `key_id` already does. The two designs meet at the same place and
    this one is one round of SHA-256 instead of a KDF.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def mint_key() -> MintedKey:
    """A new key: its id, its stored hash, its display tail, and the plaintext.

    The caller writes the first three to `access.api_key` and returns the fourth
    exactly once. There is no path that recovers the plaintext afterwards, and
    that absence is asserted by
    `tests/security/test_key_secret_shown_once_only.py` over the whole surface
    rather than promised here.
    """
    key_id = f"{KEY_ID_PREFIX}{ULID()}"
    secret = secrets.token_urlsafe(SECRET_BYTES)
    return MintedKey(
        key_id=key_id,
        key_hash=hash_secret(secret),
        last_four=secret[-LAST_FOUR_LENGTH:],
        plaintext=f"{PRESENTED_PREFIX}_{key_id}_{secret}",
    )


def parse_presented_key(presented: str) -> KeyPresentation | None:
    """Split a presented key into its id and its digest. **The secret does not escape.**

    Returns `None` for anything malformed — a wrong prefix, too few parts, an
    id without the `key_` prefix, an empty secret. `None` is an authentication
    failure at the caller and never an error: a gateway request carrying a
    garbled `Authorization` header must get the same answer as one carrying a
    key that was revoked yesterday, and an exception here would be a 500 among
    401s.

    The digest is computed here rather than at the comparison site so that the
    only object crossing this function's boundary is one that cannot hold the
    plaintext. That is the whole design of :class:`KeyPresentation`.
    """
    parts = presented.split("_", _PARTS - 1)
    if len(parts) != _PARTS:
        return None

    prefix, id_prefix, id_body, secret = parts
    if prefix != PRESENTED_PREFIX or f"{id_prefix}_" != KEY_ID_PREFIX or not id_body or not secret:
        return None

    return KeyPresentation(key_id=f"{id_prefix}_{id_body}", secret_hash=hash_secret(secret))


def secrets_match(presented_hash: str, stored_hash: str) -> bool:
    """Constant-time comparison of two hex digests (A-113).

    `hmac.compare_digest` rather than `==`. Both values are already hashes, so an
    early-exit comparison leaks how many *leading digest characters* an attacker
    guessed — which is not directly a secret, but it is a hill to climb, and
    climbing it produces a hash whose preimage is the key. The constant-time
    form removes the hill and costs nothing measurable.
    """
    return hmac.compare_digest(presented_hash, stored_hash)
