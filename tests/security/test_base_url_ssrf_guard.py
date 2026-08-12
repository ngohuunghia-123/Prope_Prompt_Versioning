"""AC-11 as ADR-0047 restated it, plus T-025.

The old form asserted that a private-resolving base URL is refused at save time
and again at dispatch time. That passes under an implementation with the TOCTOU
still open. The meaningful version uses a resolver that answers a PUBLIC address
on the validation call and a PRIVATE one immediately after, then asserts the
connection went to the first — proving the pinning rather than the checking.
"""

import socket

import httpx
import pytest

from prope.provider_access import upstream
from prope.provider_access.addresses import (
    ALLOWED_SCHEMES,
    BlockedAddress,
    pin,
    validate_base_url,
)
from tests.provider_access import _stub

PUBLIC = "93.184.216.34"


def _resolver(*addresses: str):  # noqa: ANN202
    answers = list(addresses)

    def getaddrinfo(host, port, *args, **kwargs):  # noqa: ANN001, ANN202, ARG001
        answer = answers.pop(0) if len(answers) > 1 else answers[0]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (answer, port))]

    return getaddrinfo


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.5",
        "192.168.1.7",
        "172.16.4.4",
        "169.254.169.254",
        "0.0.0.0",
        "224.0.0.1",
    ],
)
async def test_a_base_url_resolving_to_a_refused_range_is_refused(
    monkeypatch: pytest.MonkeyPatch, address: str
) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _resolver(address))

    with pytest.raises(BlockedAddress) as blocked:
        await validate_base_url("https://provider.example/v1")

    assert blocked.value.reason == "blocked_address"


async def test_a_literal_private_address_is_refused_without_a_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """169.254.169.254 typed straight into the field is the whole attack in its
    simplest form, and it never reaches the resolver."""

    def never(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202, ARG001
        raise AssertionError("a literal address must not be resolved")

    monkeypatch.setattr(socket, "getaddrinfo", never)

    with pytest.raises(BlockedAddress):
        await validate_base_url("https://169.254.169.254/v1")


@pytest.mark.parametrize("url", ["http://provider.example/v1", "file:///etc/passwd", "gopher://x/"])
async def test_a_scheme_outside_the_allow_list_is_refused(url: str) -> None:
    with pytest.raises(BlockedAddress) as blocked:
        await validate_base_url(url)

    assert blocked.value.reason == "blocked_scheme"
    assert ALLOWED_SCHEMES == frozenset({"https"})


async def test_a_public_base_url_is_accepted_and_carries_its_resolved_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _resolver(PUBLIC))

    endpoint = await validate_base_url("https://provider.example/v1/")

    assert endpoint.address == PUBLIC
    assert endpoint.host == "provider.example"
    assert endpoint.base_url == "https://provider.example/v1"


async def test_the_connection_goes_to_the_address_that_was_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The DNS answer CHANGES between the check and the connect. Re-validating
    and then handing the HOSTNAME to an HTTP client would let the client resolve
    it again — which moves the window rather than closing it."""
    monkeypatch.setattr(socket, "getaddrinfo", _resolver(PUBLIC, "169.254.169.254"))

    endpoint = await validate_base_url("https://provider.example/v1")

    with _stub.stub_provider(
        monkeypatch, lambda request: httpx.Response(200, json=_stub.completion())
    ) as recorder:
        await upstream.call_json(
            endpoint,
            "sk-test-secret",
            path=upstream.CHAT_COMPLETIONS_PATH,
            payload={"model": "m", "messages": []},
            timeout_seconds=5.0,
        )

    assert recorder.last.url.host == PUBLIC
    assert "169.254.169.254" not in str(recorder.last.url)


async def test_the_hostname_survives_for_sni_and_certificate_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Connecting to a bare IP with certificate checking relaxed would trade an
    SSRF hole for a TLS one, so the hostname is preserved in the `Host` header
    and in the `sni_hostname` extension the TLS handshake verifies against."""
    monkeypatch.setattr(socket, "getaddrinfo", _resolver(PUBLIC))
    endpoint = await validate_base_url("https://provider.example/v1")

    with _stub.stub_provider(
        monkeypatch, lambda request: httpx.Response(200, json=_stub.model_list())
    ) as recorder:
        await upstream.call_json(
            endpoint,
            "sk-test-secret",
            path=upstream.MODELS_PATH,
            method="GET",
            timeout_seconds=5.0,
        )

    assert recorder.last.headers["host"] == "provider.example"
    assert recorder.last.extensions["sni_hostname"] == "provider.example"


async def test_the_pinning_rewrites_only_the_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _resolver(PUBLIC))
    endpoint = await validate_base_url("https://provider.example:8443/v1")

    url, host_header, extensions = pin(endpoint, "https://provider.example:8443/v1/models")

    assert url == f"https://{PUBLIC}:8443/v1/models"
    assert host_header == {"host": "provider.example:8443"}
    assert extensions == {"sni_hostname": "provider.example"}


async def test_no_request_carrying_the_credential_is_issued_when_the_address_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal happens before anything is composed, so there is no request
    with a bearer token on it to be sent anywhere."""
    monkeypatch.setattr(socket, "getaddrinfo", _resolver("10.1.2.3"))

    with _stub.stub_provider(
        monkeypatch, lambda request: httpx.Response(200, json={})
    ) as recorder:
        with pytest.raises(BlockedAddress):
            await validate_base_url("https://provider.example/v1")

    assert recorder.count == 0
