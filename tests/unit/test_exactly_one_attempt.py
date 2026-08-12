"""AC-7 — one upstream request per dispatch, whatever the error class (A-088).

The retry policy belongs to the caller, which is how A-084 (gateway: never) and
A-053 (evaluation: transport errors only) are both true at once. A retry here
would make one of them false without either module changing a line.
"""

import httpx
import pytest

from prope.provider_access import upstream
from tests.provider_access import _stub


async def _call(monkeypatch: pytest.MonkeyPatch, handler) -> _stub.Recorder:  # noqa: ANN001
    payload = upstream.compose_request(
        upstream_model="gpt-4o-mini",
        parameters={},
        messages=({"role": "user", "content": "hi"},),
        stream=False,
    )
    with _stub.stub_provider(monkeypatch, handler) as recorder:
        try:
            await upstream.call_json(
                _stub.endpoint(),
                "sk-test-secret",
                path=upstream.CHAT_COMPLETIONS_PATH,
                payload=payload,
                timeout_seconds=5.0,
            )
        except (httpx.HTTPError, TimeoutError):
            pass
    return recorder


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504, 401, 400])
async def test_a_refused_call_is_issued_exactly_once(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    recorder = await _call(monkeypatch, _stub.answers(status, {"error": {"message": "no"}}))

    assert recorder.count == 1


async def test_a_timeout_is_issued_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    def times_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    recorder = await _call(monkeypatch, times_out)

    assert recorder.count == 1


async def test_a_connection_failure_is_issued_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuses(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    recorder = await _call(monkeypatch, refuses)

    assert recorder.count == 1


async def test_the_one_client_this_module_builds_retries_nothing_and_follows_nothing() -> None:
    """A-088 by construction rather than by remembering to disable something,
    and ADR-0047's second half: a 302 is a resolution the guard never saw.

    Driven through the real ``_client``, not read off the source, because the
    property belongs to the object rather than to the text that built it.
    """
    async with upstream._client(5.0) as client:
        transport = client._transport

        assert client.follow_redirects is False
        assert isinstance(transport, httpx.AsyncHTTPTransport)
        assert transport._pool._retries == 0


async def test_a_redirect_is_not_followed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider that redirects its completions endpoint fails verification
    rather than being followed at dispatch time — the redirect target was never
    validated by the SSRF guard."""
    redirect = _stub.answers(302, {})

    def moved(request: httpx.Request) -> httpx.Response:
        response = redirect(request)
        response.headers["location"] = "https://169.254.169.254/v1/chat/completions"
        return response

    recorder = await _call(monkeypatch, moved)

    assert recorder.count == 1
    assert "169.254.169.254" not in str(recorder.last.url)
