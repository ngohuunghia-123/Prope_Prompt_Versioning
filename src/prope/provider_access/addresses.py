"""ADR-0047 — validate the base URL, then connect to the address that was validated."""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

__all__ = [
    "ALLOWED_SCHEMES",
    "DEFAULT_PORTS",
    "BlockedAddress",
    "ValidatedEndpoint",
    "join",
    "pin",
    "validate_base_url",
]

ALLOWED_SCHEMES = frozenset({"https"})

DEFAULT_PORTS = {"https": 443}

BLOCKED_REASON_SCHEME = "blocked_scheme"
BLOCKED_REASON_MALFORMED = "malformed_url"
BLOCKED_REASON_UNRESOLVABLE = "unresolvable_host"
BLOCKED_REASON_PRIVATE_ADDRESS = "blocked_address"


class BlockedAddress(Exception):  # noqa: N818
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class ValidatedEndpoint:
    """The URL as given, plus the single address the connection must go to."""

    base_url: str
    scheme: str
    host: str
    port: int
    address: str

    @property
    def authority(self) -> str:
        literal = f"[{self.address}]" if ":" in self.address else self.address
        return f"{literal}:{self.port}"


def _refuses(address: str) -> bool:
    parsed = ipaddress.ip_address(address)
    return (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_multicast
        or parsed.is_reserved
        or parsed.is_unspecified
    )


def _resolve(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise BlockedAddress(
            BLOCKED_REASON_UNRESOLVABLE, f"the host in the base URL does not resolve: {host}"
        ) from error
    return list(dict.fromkeys(info[4][0] for info in infos))


def _validate(base_url: str) -> ValidatedEndpoint:
    parts = urlsplit(base_url)
    if parts.scheme not in ALLOWED_SCHEMES:
        raise BlockedAddress(
            BLOCKED_REASON_SCHEME,
            f"the base URL scheme {parts.scheme!r} is not on the allow-list "
            f"{sorted(ALLOWED_SCHEMES)}",
        )
    if not parts.hostname or parts.query or parts.fragment:
        raise BlockedAddress(
            BLOCKED_REASON_MALFORMED,
            "the base URL must carry a host and no query string or fragment",
        )

    host = parts.hostname
    port = parts.port or DEFAULT_PORTS[parts.scheme]

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        addresses = _resolve(host, port)
    else:
        addresses = [str(literal)]

    if not addresses:
        raise BlockedAddress(
            BLOCKED_REASON_UNRESOLVABLE, f"the host in the base URL resolves to nothing: {host}"
        )

    blocked = [address for address in addresses if _refuses(address)]
    if blocked:
        raise BlockedAddress(
            BLOCKED_REASON_PRIVATE_ADDRESS,
            "the base URL resolves to a loopback, link-local, reserved or private address",
        )

    return ValidatedEndpoint(
        base_url=urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", "")),
        scheme=parts.scheme,
        host=host,
        port=port,
        address=addresses[0],
    )


async def validate_base_url(base_url: str) -> ValidatedEndpoint:
    return await asyncio.to_thread(_validate, base_url)


def join(endpoint: ValidatedEndpoint, path: str) -> str:
    return f"{endpoint.base_url}/{path.lstrip('/')}"


def pin(endpoint: ValidatedEndpoint, url: str) -> tuple[str, dict[str, str], dict[str, str]]:
    """The URL rewritten onto the validated address, with the hostname preserved."""
    parts = urlsplit(url)
    pinned = urlunsplit((parts.scheme, endpoint.authority, parts.path, parts.query, ""))
    default_port = endpoint.port == DEFAULT_PORTS[endpoint.scheme]
    host_header = endpoint.host if default_port else f"{endpoint.host}:{endpoint.port}"
    return pinned, {"host": host_header}, {"sni_hostname": endpoint.host}
