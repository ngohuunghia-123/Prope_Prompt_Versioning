"""Register, release and key the six prompts the agent playground calls.

The agent mode in `index.html` is a chain: a guardrail, a planner, a query
rewriter, a billing specialist, an answer writer and a second guardrail — six
released prompts, six gateway calls, one conversation. Setting that up by hand is
several dozen clicks, and several dozen clicks is enough friction that the
feature never gets looked at.

    python seed.py --list-providers
    python seed.py --provider prv_... --key

It talks to the **management** API with the same `prope_session` cookie the web
app uses, exactly as `playgrounds/prompt-conversion-cli` does, and it reads
`ADMIN_SESSION_TOKEN` out of the repository `.env` so there is nothing to export.

**It approves its own prompts and says so.** Prope records self-approval rather
than refusing it, and every revision here is released through
`approve-and-release` carrying an acknowledgement that names this script. That is
what a seeded prompt should look like in the history — obviously machine-made,
obviously not reviewed by a second person. Do not point it at anything real:
A-020 says that about the pilot, and it applies with more force to a script whose
whole job is to rubber-stamp.

Stdlib only, like `server.py`. Re-running is safe: a prompt that already exists is
found rather than duplicated, and a fresh revision is released over the old one.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib import error, request

HERE = Path(__file__).parent

#: The namespace every seeded prompt lands in. It doubles as the first half of
#: the model name — `acme-support/planner` — which is what the page's role
#: auto-assignment matches on, so changing it here means changing it there.
NAMESPACE = "acme-support"

#: `name` → the title and purpose a person will see in Prope. The body comes from
#: `prompts/<name>.xml`. The order is the order they are created in, which is the
#: order the chain runs.
PROMPTS = (
    ("input-guardrail", "Input guardrail", "Decides whether the assistant may handle a message."),
    ("planner", "Planner", "Chooses the next tool, or decides there is enough to answer."),
    ("retriever", "Search query writer", "Turns a customer message into one help-centre query."),
    ("billing-specialist", "Billing specialist", "The sub-agent for refunds, charges and disputes."),
    ("answer-writer", "Answer writer", "Writes the customer-facing reply from the gathered notes."),
    ("output-guardrail", "Output guardrail", "Last check before a reply reaches the customer."),
)

CHANGE_SUMMARY = "Seeded by playgrounds/chatbot-app/seed.py for the agent chain demo."

ACKNOWLEDGEMENT = (
    "Seeded playground prompt, approved by the script that wrote it. No eval suite is "
    "attached and no second person reviewed this."
)

DEFAULT_BASE_URL = os.environ.get("PROPE_API_URL", "http://localhost:8080")

DEFAULT_UPSTREAM_MODEL = "gpt-4o-mini"


def _dotenv(name: str) -> str:
    """One value out of the repository `.env`, without exporting the rest."""
    try:
        for line in (HERE.parents[1] / ".env").read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == name:
                return value.strip()
    except OSError:
        pass
    return ""


class RefusalError(RuntimeError):
    """A refusal from Prope, carried with its body so the message names the cause."""

    def __init__(self, status: int, path: str, body: str) -> None:
        super().__init__(f"HTTP {status} from {path}\n{body}")
        self.status = status
        self.body = body


class Api:
    def __init__(self, base_url: str, session: str) -> None:
        self._base = base_url.rstrip("/")
        self._session = session

    def __call__(self, method: str, path: str, payload: dict | None = None) -> object:
        body = json.dumps(payload).encode() if payload is not None else None
        call = request.Request(self._base + path, data=body, method=method)
        call.add_header("cookie", f"prope_session={self._session}")
        call.add_header("accept", "application/json")
        if body is not None:
            call.add_header("content-type", "application/json")
        try:
            with request.urlopen(call, timeout=60) as response:
                raw = response.read()
        except error.HTTPError as refused:
            raise RefusalError(refused.status, path, refused.read().decode("utf-8", "replace")) from None
        except error.URLError as unreachable:
            raise SystemExit(f"could not reach {self._base}: {unreachable.reason}") from None
        return json.loads(raw) if raw else None


def _find_prompt(api: Api, model_name: str) -> dict | None:
    """The already-registered prompt with this model name, or nothing.

    Searched rather than assumed, because a second run must not try to create a
    second `acme-support/planner` — `POST /prompts` would refuse it, and the run
    would stop on a conflict that is not a problem.
    """
    for row in api("GET", f"/api/v1/prompts?q={model_name}") or ():
        if row["model_name"] == model_name:
            return row
    return None


def _release(api: Api, prompt: dict, body: str, provider: str, upstream: str) -> int:
    prompt_id = prompt["prompt_id"]
    revision = api(
        "POST",
        f"/api/v1/prompts/{prompt_id}/revisions",
        {
            "body": body,
            "change_summary": CHANGE_SUMMARY,
            "provider_config_id": provider,
            "upstream_model": upstream,
        },
    )
    version_id = revision["version_id"]

    api("POST", f"/api/v1/prompts/{prompt_id}/revisions/{version_id}/submit")
    api(
        "POST",
        f"/api/v1/prompts/{prompt_id}/revisions/{version_id}/approve-and-release",
        {"comment": CHANGE_SUMMARY, "acknowledgement_reason": ACKNOWLEDGEMENT},
    )
    return revision["revision_number"]


def _providers(api: Api) -> int:
    rows = api("GET", "/api/v1/providers") or ()
    if not rows:
        # Said out loud rather than printed as nothing. An empty list and a
        # working call that found nothing look identical on a terminal, and the
        # next thing that happens either way is a confusing refusal from
        # `--provider`.
        print("no provider configurations in this workspace.")
        print("Add one under Providers in Prope — it needs a base URL and an API")
        print("key, and it must pass verification before the gateway will use it.")
        return 1
    for row in rows:
        status = f"{row['status']}/{row['verification_status']}"
        print(f"{row['provider_config_id']}  {row['display_name']}  {status}")
    return 0


#: Where the legacy mode's observations are filed. A folder nobody has been
#: granted, which is the point of ADR-0061: undiscovered prompts land somewhere
#: private by default, and whoever triages them is granted that one folder rather
#: than the whole registry.
OBSERVE_NAMESPACE = "observed"


def _observe_key(api: Api, arguments: argparse.Namespace) -> int:
    """Mint a key that forwards what the registry cannot resolve. ADR-0059.

    **Two calls, and it has to be two.** `POST /keys` deliberately has no
    `observe_*` fields — the pair travels on `PUT .../scope`, which replaces the
    whole reach rather than patching it. So the key is minted with no scope at
    all and then given one, which is also the honest shape for this demo: an
    observing key needs no `scope_model_names`, because every name it will be
    asked for is a name Prope does not know yet.
    """
    session = api("GET", "/api/v1/auth/session")
    workspace_id = session["user"]["workspace_id"]
    if not workspace_id:
        print("that session is in no workspace — sign in to one and retry", file=sys.stderr)
        return 1

    minted = api(
        "POST",
        f"/api/v1/workspaces/{workspace_id}/keys",
        {"name": "chatbot playground legacy app", "scope_model_names": []},
    )
    api(
        "PUT",
        f"/api/v1/workspaces/{workspace_id}/keys/{minted['key_id']}/scope",
        {
            "scope_model_names": [],
            "scope_namespaces": [],
            "observe_provider_config_id": arguments.provider,
            "observe_namespace": arguments.observe_namespace,
        },
    )
    print(f"key  {minted['secret']}")
    print("Copy it now — it is shown once and cannot be recovered.")
    print()
    print("Paste it into the page under Settings (index.html — the app that has")
    print("not adopted Prope), type the provider's own model name, and send.")
    print("Observations land in")
    print(f"the '{arguments.observe_namespace}' folder — read them back with:")
    print("    python seed.py --observations")
    return 0


def _observations(api: Api, arguments: argparse.Namespace) -> int:
    """What the gateway filed. The read this playground exists to make checkable.

    Prope has no inbox screen yet, so this is the only way to see the result
    without opening a psql prompt. It prints the two properties worth checking by
    eye: that repeated calls **collapse into one group** rather than one row per
    call, and that a body whose only difference is an interpolated date lands in
    that same group with the date reported as an inferred variable.
    """
    query = f"?namespace={arguments.observe_namespace}" if arguments.observe_namespace else ""
    rows = api("GET", f"/api/v1/observations{query}") or ()
    if not rows:
        print("no observations.")
        print()
        print("If the legacy app has been sending, check in order:")
        print("  - the key is the observing one (`--observe-key`), not the agent one")
        print("  - the model name it sends is one Prope does NOT know; a name the")
        print("    registry resolves is served normally and never observed")
        print("  - the request carried a `system` message; there is no prompt to")
        print("    observe in a call that has none")
        return 0

    for row in rows:
        excerpt = " ".join(row["body_excerpt"].split())
        print(f"{row['observation_id']}  {row['namespace']}  {row['status']}")
        print(f"  seen {row['sighting_count']}x  "
              f"{row['first_seen_at'][:19]} -> {row['last_seen_at'][:19]}")
        print(f"  upstream  {', '.join(row['upstream_models']) or '—'}")
        print(f"  variables {', '.join(row['inferred_variables']) or 'none'}")
        print(f"  body      {excerpt[:160]}{'…' if len(excerpt) > 160 else ''}")
        print()
    print(f"{len(rows)} group(s). One group per distinct prompt, not per call —")
    print("bodies differing only where a variable was interpolated share a group.")
    return 0


def _seed(api: Api, arguments: argparse.Namespace) -> int:
    session = api("GET", "/api/v1/auth/session")
    workspace_id = session["user"]["workspace_id"]
    if not workspace_id:
        print("that session is in no workspace — sign in to one and retry", file=sys.stderr)
        return 1

    model_names = []
    for name, title, purpose in PROMPTS:
        model_name = f"{NAMESPACE}/{name}"
        model_names.append(model_name)

        prompt = _find_prompt(api, model_name)
        if prompt is None:
            prompt = api(
                "POST",
                "/api/v1/prompts",
                {
                    "namespace": NAMESPACE,
                    "name": name,
                    "title": title,
                    "purpose": purpose,
                    # Workspace-visible on purpose. The conversation graph drops
                    # steps whose prompt the reader may not see, and a demo whose
                    # chain silently fragments teaches the wrong lesson about a
                    # control that is working exactly as designed.
                    "access_level": "workspace",
                    "tags": ["playground", "agent-chain"],
                },
            )

        body = (HERE / "prompts" / f"{name}.xml").read_text(encoding="utf-8")
        number = _release(api, prompt, body, arguments.provider, arguments.upstream_model)
        print(f"released  {model_name}  (rev {number})")

    if arguments.key:
        minted = api(
            "POST",
            f"/api/v1/workspaces/{workspace_id}/keys",
            {"name": "chatbot playground agent", "scope_model_names": model_names},
        )
        print(f"\nkey  {minted['secret']}")
        print("Copy it now — it is shown once and cannot be recovered.")
    else:
        print("\nScope a key to these six model names, then paste it into the page:")
        for model_name in model_names:
            print(f"  {model_name}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--session",
        default=os.environ.get("PROPE_SESSION")
        or os.environ.get("ADMIN_SESSION_TOKEN")
        or _dotenv("ADMIN_SESSION_TOKEN"),
        help="value of the prope_session cookie (or PROPE_SESSION / ADMIN_SESSION_TOKEN)",
    )
    parser.add_argument("--provider", help="provider_config_id the revisions bind to")
    parser.add_argument("--upstream-model", default=DEFAULT_UPSTREAM_MODEL)
    parser.add_argument(
        "--list-providers", action="store_true", help="print this workspace's providers and stop"
    )
    parser.add_argument(
        "--key", action="store_true", help="also mint a consumer key scoped to the six prompts"
    )
    parser.add_argument(
        "--observe-key",
        action="store_true",
        help="mint an observing key for index.html: forwards and records what it cannot resolve",
    )
    parser.add_argument(
        "--observations",
        action="store_true",
        help="print the observations the legacy app has produced, and stop",
    )
    parser.add_argument(
        "--observe-namespace",
        default=OBSERVE_NAMESPACE,
        help=f"folder observations are filed in (default: {OBSERVE_NAMESPACE})",
    )
    arguments = parser.parse_args()

    if not arguments.session:
        parser.error("no session. Pass --session, or set ADMIN_SESSION_TOKEN in the repo .env")

    api = Api(arguments.base_url, arguments.session)

    try:
        if arguments.list_providers:
            return _providers(api)
        if arguments.observations:
            return _observations(api, arguments)
        if arguments.observe_key:
            if not arguments.provider:
                parser.error(
                    "--observe-key needs --provider: an observed call is forwarded to a "
                    "provider configuration, and there is no default for where traffic goes"
                )
            return _observe_key(api, arguments)
        if not arguments.provider:
            parser.error("--provider is required. Run --list-providers to find one")
        return _seed(api, arguments)
    except RefusalError as refused:
        print(refused, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
