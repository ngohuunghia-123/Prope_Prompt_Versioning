"""A mock product that talks to Prope's OpenAI-compatible gateway.

Serves the two demo pages and relays two calls to Prope: `GET /v1/models` and
`POST /v1/chat/completions`. **It holds no configuration.** The gateway address
and the API key are typed into the page and travel with each request, so a
teammate copies this folder, runs one command, and configures everything in the
browser.

**Why a page needs a relay at all.** Prope configures no CORS anywhere — the SPA
and the API share one origin, which is what lets the session cookie work with no
CSRF token. A page opened from `file://` therefore fails its preflight against
`/v1/chat/completions`; the browser blocks it before the gateway is even asked.
Serving the page from the process that forwards its calls makes every request
same-origin, and needs no change to Prope.

    python server.py

Then open http://localhost:8090 and fill in the two fields. Stdlib only, nothing
to install, and a development toy: it binds to localhost and trusts whatever the
page tells it to call.
"""

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request

HERE = Path(__file__).parent

#: The two pages, and the only paths served from disk. `index.html` is the app
#: that has NOT adopted Prope — hardcoded prompts, a provider model name, no
#: `prope` block — and `integrated.html` is the same product after adoption.
#: Serving both from one origin is what lets you flip between the before and the
#: after picture against one gateway and one key.
PAGES = {
    "/": HERE / "index.html",
    "/index.html": HERE / "index.html",
    "/integrated.html": HERE / "integrated.html",
}

DEFAULT_PORT = 8090

#: The whole surface INT-022 implements, and the whole surface this app relays.
PROXIED = {("GET", "/v1/models"), ("POST", "/v1/chat/completions")}

#: The page sends its gateway address here rather than in the URL, so the path
#: stays the real one and the relay is a straight pass-through.
TARGET_HEADER = "x-prope-base-url"

#: Forwarded back so the page can show which revision served the answer. The
#: gateway sets these on both the JSON and the SSE response.
#:
#: `x-prope-call-id` is the one the agent mode cannot work without: it is what
#: the next step of a chain sends as `prope.parent_call_id`, and a relay that
#: dropped it would leave every step of the graph a root.
IDENTITY_HEADERS = (
    "x-prope-model",
    "x-prope-version-id",
    "x-prope-revision",
    "x-prope-pinned",
    "x-prope-fallback",
    "x-prope-call-id",
)

MAX_REQUEST_BYTES = 1_000_000

#: `urllib` otherwise announces `Python-urllib/3.13`, and a bot filter in front of
#: the gateway refuses that string by name — Cloudflare's Bot Fight Mode does,
#: which is how a working relay starts answering with an HTML block page carrying
#: a ray ID. An honest product name is the fix worth having: it can be allowlisted
#: in one WAF rule, and it stays true. Impersonating a browser would defeat the
#: filter by lying to it and leave nothing to allowlist.
USER_AGENT = "prope-chatbot-playground/1.0 (+playgrounds/chatbot-app)"


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 closes the connection at the end of the body, which is what lets a
    # streamed completion be relayed without a length or chunked framing.
    protocol_version = "HTTP/1.0"
    server_version = "prope-chatbot-playground"

    # -- responses ---------------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, code: str, message: str) -> None:
        """OpenAI's error shape, so the page renders our failures like the gateway's."""
        payload = {"error": {"message": message, "type": "api_error", "code": code}}
        self._send(status, json.dumps(payload).encode(), "application/json")

    # -- routes ------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's spelling
        page = PAGES.get(self.path)
        if page is not None:
            try:
                self._send(200, page.read_bytes(), "text/html; charset=utf-8")
            except OSError:
                self._error(500, "page_missing", f"{page.name} is not next to server.py.")
            return
        self._relay("GET", None)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length") or 0)
        if length > MAX_REQUEST_BYTES:
            self._error(413, "request_too_large", "That request is larger than this demo accepts.")
            return
        self._relay("POST", self.rfile.read(length) if length else b"")

    def _relay(self, method: str, body: bytes | None) -> None:
        if (method, self.path) not in PROXIED:
            self._error(404, "not_proxied", "This app relays /v1/models and /v1/chat/completions.")
            return

        base_url = (self.headers.get(TARGET_HEADER) or "").strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            self._error(400, "no_gateway", "Set the gateway address in the page's Settings.")
            return

        authorization = self.headers.get("authorization")
        if not authorization:
            self._error(401, "no_api_key", "Set the API key in the page's Settings.")
            return

        upstream = request.Request(base_url + self.path, data=body, method=method)
        upstream.add_header("authorization", authorization)
        upstream.add_header("accept", self.headers.get("accept", "*/*"))
        upstream.add_header("user-agent", USER_AGENT)
        if body:
            upstream.add_header("content-type", "application/json")

        try:
            response = request.urlopen(upstream, timeout=120)
        except error.HTTPError as refused:
            # A refusal is a real response — 401 for a bad key, 404 for a model
            # this key may not resolve, 400 naming a missing variable. Relay it
            # verbatim; its body is already the shape the page expects.
            #
            # Unless it is not from Prope at all. A CDN or bot filter in front of
            # the gateway answers with an HTML block page, and relaying that gets
            # the page a JSON parse error naming nothing. Say who actually
            # refused, since the fix is in the filter and not in Prope.
            if "json" in (refused.headers.get("content-type") or "").lower():
                self._forward(refused)
            else:
                self._interception(refused)
        except error.URLError as unreachable:
            self._error(502, "gateway_unreachable",
                        f"Could not reach {base_url}: {unreachable.reason}")
        else:
            self._forward(response)

    def _interception(self, refused) -> None:
        """A refusal that did not come from Prope, reported as one.

        Prope answers every refusal in JSON — INT-022's error shape for the
        gateway, RFC 9457 for the management API. A non-JSON body on a `/v1` call
        therefore means something in between answered instead: a CDN challenge
        page, a WAF block, a proxy's own 502. The ray ID or request ID in that
        page is the only thing that identifies the rule that fired, so it is
        carried through rather than swallowed.
        """
        try:
            page = refused.read(4000).decode("utf-8", "replace")
        except OSError:
            page = ""
        finally:
            refused.close()

        # The identifiers a block page puts in the body or the headers. Nothing is
        # parsed out of the HTML: whoever has to write the allowlist rule wants
        # the page, and 4 kB of it is enough to recognise which product produced
        # it without turning this into a scraper.
        stamped = " ".join(
            f"{name}={refused.headers[name]}"
            for name in ("cf-ray", "cf-mitigated", "x-request-id", "server")
            if refused.headers.get(name)
        )
        self._error(
            502,
            "upstream_intercepted",
            "Something between this relay and Prope refused the call — the reply "
            f"was {refused.headers.get('content-type') or 'untyped'}, not JSON, so it "
            f"is not Prope's. HTTP {refused.status}. {stamped}\n\n{page.strip()[:1500]}",
        )

    def _forward(self, response) -> None:
        self.send_response(response.status)
        self.send_header("content-type", response.headers.get("content-type", "application/json"))
        for name in IDENTITY_HEADERS:
            value = response.headers.get(name)
            if value is not None:
                self.send_header(name, value)
        self.send_header("cache-control", "no-store")
        self.end_headers()

        try:
            while True:
                # `read1` returns what has arrived rather than blocking for a full
                # buffer, which is the difference between a streamed answer that
                # appears word by word and one that lands all at once.
                chunk = response.read1(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # The reader navigated away mid-answer.
        finally:
            response.close()

    def log_message(self, fmt: str, *args) -> None:
        # Deliberately not the default: that one logs the raw request line, and
        # this keeps the console to method, path and status. No header is touched,
        # so the key cannot reach the console by accident.
        sys.stderr.write(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else '?'}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", DEFAULT_PORT)))
    parser.add_argument("--host", default="127.0.0.1",
                        help="use 0.0.0.0 to let a teammate on your network open it")
    arguments = parser.parse_args()

    httpd = ThreadingHTTPServer((arguments.host, arguments.port), Handler)
    print(f"chatbot playground   http://localhost:{arguments.port}")
    print(f"  the legacy app     http://localhost:{arguments.port}/            (prompts in its own source)")
    print(f"  after adoption     http://localhost:{arguments.port}/integrated.html")
    print("gateway and API key are set in the page under Settings")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
