"""INT-022's surface, asserted against the gateway application object.

`tests/architecture/test_route_table.py` asserts the MANAGEMENT table and cannot
reach this one: ADR-0050 makes the gateway a separate ASGI application mounted at
``/v1``, and a ``Mount`` carries neither ``effective_route_contexts`` nor a
``dependant``, so :func:`prope.session_auth.assembled_routes` walks straight past
it. That invisibility is the price of the isolation and it is paid once, named in
``SANCTIONED_MOUNTS`` there — this file is the other half of the trade, and
without it the gateway would be the one served surface in the repository no route
assertion covers.

The properties are the OPPOSITE of the management table's in every direction, and
each inversion is a decision rather than an omission:

* **No route declares a ``ManagementAction``.** The vocabulary is A-115's closed
  set for a *person* acting through the SPA. A consumer key holds no role and no
  grant; INT-004 applies its model-name scope instead, and declaring an action
  here would be declaring one nothing could resolve.
* **No route declares a session.** Sessions are cookies on a same-origin SPA
  (ADR-0029, ADR-0043). This surface authenticates a key through INT-003, and a
  cookie on the one internet-facing route would be a CSRF surface nobody asked
  for.
* **The paths are unversioned by Prope.** ``/v1`` is OpenAI's wire version and
  not ours to bump (INT-022), which is why it is the mount point rather than a
  prefix inside this application.
"""

from fastapi import FastAPI

from prope.gateway.app import ROUTE_LABELS, app
from prope.gateway.routes import IMPLEMENTED_PATHS
from prope.session_auth import assembled_routes, declared_action, declares_session
from tests.integration._asgi import call

#: Two implemented operations and one catch-all. Written as a literal for the
#: same reason ``EXPECTED_ROUTES`` is: a set computed from the application would
#: pass whatever the application happened to serve.
EXPECTED_ROUTES = frozenset(
    {
        ("POST", "/chat/completions"),
        ("GET", "/models"),
    }
)

#: A-026: *"Any OpenAI route beyond chat completions and /v1/models; others
#: return 501 in the OpenAI error shape"*. A 501 needs something to answer it,
#: and Starlette's own 404 for an unrouted path would be the wrong number in the
#: right shape — so the catch-all is a route rather than a handler, registered
#: last so it cannot shadow the two above.
CATCH_ALL = "/{unimplemented:path}"


def _table() -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in assembled_routes(app)
        if route.path != CATCH_ALL
        for method in route.methods
    }


def test_the_gateway_serves_exactly_two_operations() -> None:
    assert _table() == set(EXPECTED_ROUTES)


def test_the_catch_all_is_registered_last_so_it_shadows_nothing() -> None:
    """Starlette matches in registration order. A catch-all first would answer
    501 to every chat completion the gateway exists to serve, and no other
    assertion in this file would notice — both routes would still be *declared*.
    """
    paths = [route.path for route in assembled_routes(app)]

    assert paths[-1] == CATCH_ALL
    assert paths[:-1] == ["/chat/completions", "/models"]


def test_no_gateway_route_declares_a_session_or_a_management_action() -> None:
    """The inversion of the management table's central assertion, and not vacuous:
    the count is checked first, because a walk that found nothing would pass."""
    routes = list(assembled_routes(app))

    assert len(routes) == 3
    for route in routes:
        assert not declares_session(route), route.path
        assert declared_action(route) is None, route.path


def test_the_route_label_set_matches_what_is_served() -> None:
    """``prope_gateway_request_duration_seconds``'s ``route`` label is bounded by
    a literal set in source (ADR-0030), and a path served but not listed there
    would silently collapse into ``other`` — which is the one value that must
    mean *somebody asked for something we do not implement*."""
    assert ROUTE_LABELS == {path for _, path in EXPECTED_ROUTES}
    assert IMPLEMENTED_PATHS == ROUTE_LABELS


def test_the_gateway_serves_no_openapi_schema_of_its_own() -> None:
    """Two applications, two schemas, and this one is deliberately empty.

    ADR-0050: *"the OpenAI surface is documented by OpenAI's specification, not
    by ours"*. The management application already answers no ``/docs``,
    ``/redoc`` or ``/openapi.json``; serving them from inside the mount would put
    three unauthenticated paths behind Caddy's single ingress that no route
    assertion in either file lists.
    """
    assert isinstance(app, FastAPI)
    assert app.openapi_url is None
    assert app.docs_url is None
    assert app.redoc_url is None


async def test_an_unimplemented_openai_route_answers_501_in_the_openai_shape() -> None:
    """A-026, driven rather than declared. ``/v1/embeddings`` is the likeliest
    arrival: it is the second thing an OpenAI-shaped client reaches for."""
    response = await call(app, "POST", "/embeddings", json_body={"input": "x"})

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "not_implemented"
    assert response.json()["error"]["type"] == "invalid_request_error"


async def test_a_wrong_method_on_an_implemented_path_is_405_and_not_501() -> None:
    """The catch-all covers every path, so without this branch a ``GET`` on chat
    completions would be answered *not implemented* — which is false, and would
    send an integrator looking for a feature that is already there."""
    response = await call(app, "GET", "/chat/completions")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


async def test_a_malformed_body_is_an_openai_shaped_422() -> None:
    """AC-13. The first error a consumer meets while integrating, and it is
    produced by a framework default rather than by module code — which is
    exactly why it needs asserting.

    FastAPI's own answer is ``{"detail": [...]}`` and ADR-0003's would be the
    management envelope. Neither appears, and neither can: the handler is
    registered on this application object rather than on the parent, so no
    inspection of ``request.url.path`` decides which contract is served.
    """
    response = await call(app, "POST", "/chat/completions", json_body={"model": "a/b"})
    payload = response.json()

    assert response.status_code == 422
    assert "detail" not in payload
    assert set(payload) == {"error"}
    assert set(payload["error"]) == {"message", "type", "param", "code"}
    assert payload["error"]["type"] == "invalid_request_error"
