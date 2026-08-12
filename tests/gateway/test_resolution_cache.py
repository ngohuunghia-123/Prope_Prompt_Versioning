"""ADR-0012 / A-080 — the cache expires, nothing invalidates it, and an expired
entry is never served.

The last clause is the one that changed on 2026-08-09. ADR-0012 originally
carried a five-minute stale-if-error window for *"when prompt-registry is
unreachable"*, and ADR-0026 and ADR-0033 removed the state that sentence
describes: the registry is an in-process call, and A-114 puts two UNCACHEABLE
access-control reads ahead of this cache on every request, so authentication
fails on the same database first. The window is deleted rather than retained, and
what asserts the deletion is that there is no argument, flag or branch below by
which an expired entry could come back.
"""

from prope.gateway.cache import MAX_ENTRIES, TTL_SECONDS, CacheKey, ResolutionCache
from prope.prompt_registry.domain import RevisionBinding

WORKSPACE = "wsp_01J00000000000000000000A"


def _binding(version_id: str = "rev_1", revision_number: int = 1) -> RevisionBinding:
    return RevisionBinding(
        prompt_id="prm_1",
        version_id=version_id,
        revision_number=revision_number,
        body="You are a helpful assistant.",
        provider_config_id="prv_1",
        upstream_model="gpt-4o-mini",
        parameters={},
        fallback_answer=None,
    )


def _key(model_name: str = "support/refund", pin: str | None = None) -> CacheKey:
    return CacheKey(workspace_id=WORKSPACE, model_name=model_name, pin=pin)


def test_the_declared_shape_is_the_shipped_shape() -> None:
    """*"a bounded LRU of at most 5,000 entries, TTL 30 s"* — the two numbers the
    lock states, and the 30 is also the gateway's share of the ≤ 5 min restore
    target (H-05), which is roughly 10x headroom."""
    assert MAX_ENTRIES == 5_000
    assert TTL_SECONDS == 30.0


def test_a_stored_binding_is_served_inside_the_ttl() -> None:
    cache = ResolutionCache()
    cache.put(_key(), _binding(), now=1000.0)

    assert cache.get(_key(), now=1029.9) is not None


def test_an_expired_entry_is_never_served_and_is_dropped() -> None:
    """The deleted stale-if-error window, asserted as an absence: at the TTL the
    entry is gone, and there is no second call that could return it."""
    cache = ResolutionCache()
    cache.put(_key(), _binding(), now=1000.0)

    assert cache.get(_key(), now=1030.0) is None
    assert len(cache) == 0
    assert cache.get(_key(), now=1030.1) is None


def test_the_key_is_the_workspace_the_name_and_the_pin() -> None:
    """Three fields, and each one dropped is a different disclosure.

    Without the workspace, one tenant's released revision answers another's call.
    Without the pin, `name` and `name@7` share an entry and a pinned consumer
    starts receiving the released revision — which is the restore guarantee
    applying to somebody who opted out of it.
    """
    cache = ResolutionCache()
    cache.put(_key(), _binding("rev_released"), now=1000.0)
    cache.put(_key(pin="7"), _binding("rev_pinned"), now=1000.0)

    assert cache.get(_key(), now=1000.0).version_id == "rev_released"
    assert cache.get(_key(pin="7"), now=1000.0).version_id == "rev_pinned"
    assert cache.get(CacheKey("wsp_other", "support/refund", None), now=1000.0) is None


def test_a_release_does_not_invalidate_anything_and_the_ttl_is_the_mechanism() -> None:
    """ADR-0012's whole decision, and the only mechanism there is.

    prompt-registry -> gateway is a forbidden edge and nothing subscribes to a
    broker, so *"invalidates itself on someone else's write"* is not something a
    cache can do. A release becomes visible when the entry expires — within 30
    seconds, always, with no coordination between processes.
    """
    cache = ResolutionCache()
    cache.put(_key(), _binding("rev_old", 7), now=1000.0)

    assert cache.get(_key(), now=1020.0).version_id == "rev_old"
    assert cache.get(_key(), now=1031.0) is None

    cache.put(_key(), _binding("rev_new", 8), now=1031.0)
    assert cache.get(_key(), now=1031.0).revision_number == 8


def test_the_bound_evicts_the_least_recently_used_entry() -> None:
    """Bounded, because this lives in the process serving the response path on an
    8 GB host and an unbounded map of revision bindings is a memory leak with a
    prompt body in every entry."""
    cache = ResolutionCache(maxsize=3)
    for index in range(3):
        cache.put(_key(f"ns/name-{index}"), _binding(), now=1000.0)

    cache.get(_key("ns/name-0"), now=1000.0)
    cache.put(_key("ns/name-3"), _binding(), now=1000.0)

    assert len(cache) == 3
    assert cache.get(_key("ns/name-1"), now=1000.0) is None
    assert cache.get(_key("ns/name-0"), now=1000.0) is not None


def test_a_read_does_not_extend_the_lifetime_of_an_entry() -> None:
    """A TTL measured from the last READ would let a hot prompt hold a withdrawn
    release open indefinitely — precisely the prompt where that matters most."""
    cache = ResolutionCache()
    cache.put(_key(), _binding(), now=1000.0)

    assert cache.get(_key(), now=1020.0) is not None
    assert cache.get(_key(), now=1031.0) is None
