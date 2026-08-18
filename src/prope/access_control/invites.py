"""Six characters, one hour, and a hash. The code an invitation is redeemed with.

**This is the third secret in the module and the weakest of the three on purpose**
(ADR-0021 records the first two; ADR-0057 records this one). A password is
human-chosen and hashed slowly; a consumer key is 256 bits and hashed fast. An
invite code is *read aloud in a meeting and typed on a phone*, so it is six
characters from a 62-symbol alphabet — about 35.7 bits — and everything that makes
that acceptable is somewhere else:

* it expires in **one hour** (:data:`INVITE_LIFETIME`), so an offline search has a
  window rather than a lifetime;
* redemption is **rate-limited per actor and per source address**
  (`limiter.redeem_limiter`), so an online search gets ten guesses a quarter hour;
* redemption requires a **signed-in account**, so a guesser must first register,
  which is itself rate-limited and leaves a row;
* and a correct guess buys a **pending** membership, which sees nothing and waits
  for an Admin (:class:`~prope.access_control.domain.MemberStatus`). The prize for
  winning the search is being asked to knock.

The alternative — a long self-describing code carrying the workspace id — was
recommended and **the six-character form was chosen deliberately**, because the
code has to survive being spoken. What that costs is written here rather than
argued away: `O`/`0` and `l`/`1`/`I` are all in the alphabet and all mistypeable,
so a wrong-character mistake is a refusal rather than a near-miss, and a one-hour
life means a shared code is usually regenerated per person.

**Nothing here reads the database.** The lookup is `commands.redeem_invite`, under
`invite_lookup_transaction`, whose policy names the digest this module computes —
so the code itself never reaches a `WHERE` clause in plaintext.
"""

import hashlib
import secrets
import string
from datetime import timedelta

from ulid import ULID

__all__ = [
    "CODE_ALPHABET",
    "CODE_LENGTH",
    "INVITE_ID_PREFIX",
    "INVITE_LIFETIME",
    "MintedInvite",
    "hash_code",
    "mint_invite",
    "normalise_code",
]

#: A-045 / ADR-0003's typed prefix, enforced by `ck_workspace_invite_id_prefix`.
INVITE_ID_PREFIX = "inv_"

#: Digits and both cases (62 symbols). **Case-sensitive**, which is the decision
#: that costs the most and was made anyway: 62^6 is 5.7e10 where 36^6 is 2.2e9, a
#: factor of 26 for one property somebody has to get right when typing.
CODE_ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase

#: Six. Short enough to read out, and the reason the expiry below is an hour.
CODE_LENGTH = 6

#: One hour, chosen by the user. Short lives make a code a per-occasion thing
#: rather than a credential that accumulates: an admin who wants to add five
#: people generates a code while they are in the room, and one found in a chat
#: log three days later opens nothing.
INVITE_LIFETIME = timedelta(hours=1)


class MintedInvite:
    """A freshly created invitation: the row's columns, plus the one-time code.

    Not a dataclass and not frozen, for :class:`~prope.access_control.keys.MintedKey`'s
    reason exactly — `__slots__` with a hand-written `__repr__` means the plaintext
    cannot reach a log line through a repr, a pytest assertion diff or a
    `structlog` value. Six characters are easier to leak than forty-three, not
    harder, because they look like nothing.

    The code appears in exactly one response body, the creation one. It is not
    recoverable afterwards: only its digest is stored, and an admin who loses it
    creates another, which is one click and the correct outcome.
    """

    __slots__ = ("code", "code_hash", "invite_id")

    def __init__(self, invite_id: str, code_hash: str, code: str) -> None:
        self.invite_id = invite_id
        self.code_hash = code_hash
        self.code = code

    def __repr__(self) -> str:
        """The id and nothing else. A default repr here would print the code."""
        return f"<MintedInvite {self.invite_id}>"


def hash_code(code: str) -> str:
    """SHA-256 hex of the code, and the salt-free choice is forced rather than lazy.

    `uq_workspace_invite_code_hash` is what resolves a code to a workspace with no
    tenant context to start from, and `invite_redeem`'s policy compares this exact
    value to `app.invite_code_hash`. A per-row salt would make both impossible —
    the lookup would become a scan of every live invitation in the install, run by
    a caller who has not yet proved they belong anywhere.

    What normally justifies a salt is a small candidate space, and this space *is*
    small. The compensation is the window and the limiter named in the module
    docstring, not the primitive.
    """
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def normalise_code(presented: str) -> str:
    """Trim surrounding whitespace and nothing else. **Case is preserved.**

    Somebody pasting a code out of a chat message brings spaces with them, and
    refusing that is a support conversation about an invisible character. Case is
    not touched, because :data:`CODE_ALPHABET` is case-sensitive and folding here
    would silently divide the space by 26 — the cost of the alphabet without the
    benefit.
    """
    return presented.strip()


def mint_invite() -> MintedInvite:
    """A new invitation id, its stored digest, and the code, once.

    `secrets.choice` per character rather than `token_urlsafe`: the alphabet is
    fixed by what a person can type, and slicing a base64url string would
    reintroduce `-` and `_` — two characters that are indistinguishable from a
    hyphen somebody added themselves.
    """
    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    return MintedInvite(
        invite_id=f"{INVITE_ID_PREFIX}{ULID()}",
        code_hash=hash_code(code),
        code=code,
    )
