"""Register a reviewed migration manifest into Prope. **Draft only, never released.**

Phase 3 of ADR-0066. Reads `.prope/manifest.json`, creates one prompt and one
first revision per entry through prompt-registry's own routes — the same routes
the web application uses, subject to the same permissions.

    python register.py --manifest .prope/manifest.json --base-url https://prope.example.com
    python register.py --manifest .prope/manifest.json --base-url https://prope.example.com --apply

**A revision that binds no provider is not callable.** It registers, it can be
approved, it can even be released - and then the first call fails with
`provider_configuration_unusable`, in production, at the customer. So pass
`--provider-config-id` (and `--upstream-model` for the rows whose model this
repository does not name). Without it this script still runs, and says loudly
what it just made un-callable.

The provider configuration id is workspace state, not repository state, which is
why it is a flag and not a manifest field: a scan cannot know it and must not
guess it.

**Without `--apply` it prints a plan and exits.** The flag that protects a policy
has to be the one you type to bypass it, not the one you must remember to type to
honour it — and what this uploads is real prompt bodies, which A-020 governs.

**It does not approve and it does not release**, and there is no flag that makes
it. A bulk import that auto-approved would put every prompt in a repository into
production unreviewed with one recorded actor, which is precisely what the
approval chain exists to prevent. Nothing registered here is callable until a
person reviews and releases it, one at a time.

Standard library only, so it runs in a customer's repository with nothing
installed.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
from typing import Any
from urllib import error, request
from xml.etree import ElementTree

MANIFEST_VERSION = 1

#: `src/prope/canonical_prompt.py`. Duplicated rather than imported because this
#: script runs in the customer's repository, where Prope is not installed — and
#: validating locally is what turns a 422 from the eleventh prompt into a message
#: about the eleventh prompt before the first one is created.
ALLOWED_BLOCKS = frozenset(
    {"system", "context", "instructions", "output_format", "examples", "constraints"}
)
MAX_CANONICAL_CHARACTERS = 32_768

#: The nameless block: a body the author declined to restructure, stored whole
#: between these two markers. Nothing inside is escaped and nothing is parsed —
#: Prope removes the markers again before the body reaches a provider. Copied
#: from `canonical_prompt.py` for the same reason as everything else here.
VERBATIM_OPEN = "<>"
VERBATIM_CLOSE = "</>"

SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")

#: `prompt_conversion.service.SCHEMA_VERSION`. It describes the CANONICAL XML
#: contract - six blocks, no attributes, no nesting - and not whatever produced
#: it, so an agent-written body and a service-written one carry the same version.
#: `tests/contract/test_migrate_skill_agrees_with_canonical_xml.py` asserts this
#: copy still equals the original.
CONVERSION_SCHEMA_VERSION = "2"


class RefusedError(Exception):
    """A local check failed. Nothing has been sent."""


# --- validation -------------------------------------------------------------


def is_verbatim(body: str) -> bool:
    """Whether this body is one nameless `<>` block — the second canonical form."""
    text = body.strip()
    return (
        len(text) >= len(VERBATIM_OPEN) + len(VERBATIM_CLOSE)
        and text.startswith(VERBATIM_OPEN)
        and text.endswith(VERBATIM_CLOSE)
    )


def check_canonical(body: str) -> None:
    """The gateway's own rule, applied here so the failure names the prompt."""
    if len(body) > MAX_CANONICAL_CHARACTERS:
        raise RefusedError(f"body is {len(body)} characters; the limit is {MAX_CANONICAL_CHARACTERS}")
    # A verbatim body is never parsed, so none of the checks below apply to it —
    # including the DOCTYPE refusal, which guards a parser this form never meets.
    if is_verbatim(body):
        return
    if "<!DOCTYPE" in body.upper() or "<!ENTITY" in body.upper():
        raise RefusedError("DOCTYPE and entity declarations are not allowed")
    try:
        root = ElementTree.fromstring(f"<prompt>{body}</prompt>")
    except ElementTree.ParseError as malformed:
        raise RefusedError(f"body is not well-formed XML ({malformed})") from malformed
    if root.text and root.text.strip():
        raise RefusedError("text outside a block; every character must sit inside one")
    if not list(root):
        raise RefusedError("no blocks; a canonical body needs at least one")
    for block in root:
        if block.tag not in ALLOWED_BLOCKS:
            raise RefusedError(
                f"unsupported block <{block.tag}>; allowed: {', '.join(sorted(ALLOWED_BLOCKS))}"
            )
        if block.attrib:
            raise RefusedError(f"<{block.tag}> has attributes; canonical blocks may not")
        if list(block):
            raise RefusedError(f"<{block.tag}> contains a nested block; the form is flat")
        if block.tail and block.tail.strip():
            raise RefusedError(f"text after <{block.tag}>; every character must sit inside a block")


def check_entry(entry: dict[str, Any], index: int) -> list[str]:
    """Everything wrong with one row, all of it, rather than the first thing."""
    problems: list[str] = []
    where = f"prompts[{index}]"

    for field in ("namespace", "name", "title", "body"):
        if not entry.get(field):
            problems.append(f"{where}: {field} is required")

    for field in ("namespace", "name"):
        value = entry.get(field)
        if value and not SLUG.match(value):
            problems.append(
                f"{where}: {field} {value!r} must be lower case letters, digits, dot, dash or "
                "underscore, starting with a letter or digit"
            )

    if entry.get("body"):
        try:
            check_canonical(entry["body"])
        except RefusedError as refused:
            problems.append(f"{where} ({entry.get('namespace')}/{entry.get('name')}): {refused}")

    declared = {variable["name"] for variable in entry.get("variables") or [] if variable.get("name")}
    used = set(re.findall(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", entry.get("body") or ""))
    for missing in sorted(used - declared):
        problems.append(
            f"{where}: the body uses {{{{{missing}}}}} but the manifest does not declare it. "
            "A caller that does not know to send it gets `missing_variable` at run time."
        )
    for unused in sorted(declared - used):
        problems.append(f"{where}: variable {unused!r} is declared but never used in the body")

    return problems


def load(path: pathlib.Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RefusedError(f"no manifest at {path}. Run the scan phase first.") from None
    except json.JSONDecodeError as broken:
        raise RefusedError(f"{path} is not valid JSON ({broken})") from broken

    if manifest.get("version") != MANIFEST_VERSION:
        raise RefusedError(
            f"manifest version {manifest.get('version')!r}; this script writes and reads "
            f"version {MANIFEST_VERSION}. Refusing rather than guessing what changed."
        )
    if not isinstance(manifest.get("prompts"), list):
        raise RefusedError("manifest has no `prompts` array")
    return manifest


def provenance_for(entry: dict[str, Any], conversion_model: str | None) -> dict[str, Any]:
    """What this body was converted from, in the fields the API already has.

    A migration reorganises a prompt into blocks, and that is a conversion
    performed by a model - the same thing `prompt_conversion` does inside Prope,
    which records `original_body`, `conversion_model` and
    `conversion_schema_version` on every revision it writes. A bulk import that
    recorded none of it would leave the reviewer holding canonical XML and a
    file path, and the question they actually have is *is this the same prompt?*

    It also outlives the source: the file gets edited, the branch gets deleted,
    and the only surviving copy of what the application was really running is
    the one stored here.
    """
    original_format = entry.get("original_format", "xml")
    if original_format == "xml":
        # Not a conversion. `ck_revision_binding_is_whole` requires
        # `original_body == body` in that case, so the filename is the only
        # thing worth carrying.
        return (
            {"original_filename": entry["original_filename"]}
            if entry.get("original_filename")
            else {}
        )
    return {
        "original_body": entry["original_body"],
        "original_format": original_format,
        "conversion_model": conversion_model,
        "conversion_schema_version": CONVERSION_SCHEMA_VERSION,
        **(
            {"original_filename": entry["original_filename"]}
            if entry.get("original_filename")
            else {}
        ),
    }


def check_provenance(manifest: dict[str, Any], conversion_model: str | None) -> list[str]:
    """Refuse before sending, because the API refuses after the prompt exists."""
    problems: list[str] = []
    converted = []
    for index, entry in enumerate(manifest["prompts"]):
        where = f"prompts[{index}] ({entry.get('namespace')}/{entry.get('name')})"
        original_format = entry.get("original_format", "xml")

        if original_format != "xml" and not entry.get("original_body"):
            problems.append(
                f"{where}: original_format is {original_format!r} but original_body is missing. "
                "A converted revision has to carry what it was converted from."
            )
        if original_format == "xml" and entry.get("original_body") not in (None, entry.get("body")):
            problems.append(
                f"{where}: original_format is 'xml' but original_body differs from body. "
                "Either the source was already canonical - in which case they are the same "
                "text - or it was converted, and original_format should say from what."
            )
        if entry.get("original_filename") and (
            "/" in entry["original_filename"] or "\\" in entry["original_filename"]
        ):
            problems.append(f"{where}: original_filename must be a basename, not a path")
        if original_format != "xml":
            converted.append(f"{entry.get('namespace')}/{entry.get('name')}")

    if converted and not conversion_model:
        problems.append(
            f"{len(converted)} prompt(s) record a conversion and --conversion-model was not "
            "given: " + ", ".join(converted[:5]) + ("..." if len(converted) > 5 else "") + ". "
            "Name the model that did the reorganising, so the revision records who wrote the "
            "XML rather than leaving it anonymous."
        )
    return problems


def binding_for(
    entry: dict[str, Any], provider_config_id: str | None, fallback_model: str | None
) -> tuple[str | None, str | None]:
    """The pair the API demands whole, or neither half.

    `RevisionCreate` refuses one half without the other, so a manifest row
    carrying `upstream_model` and nothing else is a 422 - after the prompt row
    has already been created, and prompt names are immutable.
    """
    if provider_config_id is None:
        return None, None
    model = entry.get("upstream_model") or fallback_model
    if not model:
        return None, None
    return provider_config_id, model


def check_bindings(
    manifest: dict[str, Any], provider_config_id: str | None, fallback_model: str | None
) -> list[str]:
    """Refuse the whole run rather than half-register it."""
    problems: list[str] = []
    if provider_config_id is None:
        named = [
            f"{entry.get('namespace')}/{entry.get('name')}"
            for entry in manifest["prompts"]
            if entry.get("upstream_model")
        ]
        if named:
            problems.append(
                f"{len(named)} prompt(s) record an upstream_model and no --provider-config-id "
                "was given: " + ", ".join(named[:5]) + ("..." if len(named) > 5 else "") + ". "
                "Prope refuses a model without the provider configuration it belongs to. "
                "Pass --provider-config-id, or remove upstream_model from those rows."
            )
        return problems

    unbound = [
        f"{entry.get('namespace')}/{entry.get('name')}"
        for entry in manifest["prompts"]
        if not entry.get("upstream_model") and not fallback_model
    ]
    if unbound:
        problems.append(
            f"--provider-config-id was given but {len(unbound)} prompt(s) name no model and "
            "--upstream-model was not set: " + ", ".join(unbound[:5])
            + ("..." if len(unbound) > 5 else "")
            + ". Every revision would bind a provider to nothing, which Prope refuses. "
            "Pass --upstream-model to bind them all to one model."
        )
    return problems


# --- the API ----------------------------------------------------------------


class Api:
    """The management API, with the same `prope_session` cookie the web app uses."""

    def __init__(self, base_url: str, session: str) -> None:
        self._base = base_url.rstrip("/")
        self._session = session

    def __call__(self, method: str, path: str, payload: Any = None) -> Any:
        body = json.dumps(payload).encode() if payload is not None else None
        call = request.Request(self._base + path, data=body, method=method)
        call.add_header("cookie", f"prope_session={self._session}")
        call.add_header("accept", "application/json")
        call.add_header("user-agent", "prope-migrate/1.0")
        if body:
            call.add_header("content-type", "application/json")
        try:
            with request.urlopen(call, timeout=60) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except error.HTTPError as refused:
            detail = refused.read().decode(errors="replace")
            raise RefusedError(f"{method} {path} -> {refused.code} {detail[:400]}") from refused
        except error.URLError as unreachable:
            raise RefusedError(f"cannot reach {self._base}: {unreachable.reason}") from unreachable


def find_prompt(api: Api, namespace: str, name: str) -> str | None:
    """The prompt this row would create, if a previous run already created it.

    A run that failed between the prompt and its revision left a prompt with no
    revision, and `namespace/name` is immutable with no delete - so "re-run after
    fixing the manifest" only works if the second run adopts what the first one
    made. Without this the recovery from any partial import is manual.
    """
    model_name = f"{namespace}/{name}"
    for row in api("GET", f"/api/v1/prompts?q={model_name}&limit=100") or []:
        if row.get("model_name") == model_name:
            return row["prompt_id"]
    return None


def register_one(
    api: Api,
    entry: dict[str, Any],
    provider_config_id: str | None = None,
    fallback_model: str | None = None,
    conversion_model: str | None = None,
) -> tuple[str, str, bool]:
    """Create the prompt if it is new, then a revision. `(prompt_id, version_id, adopted)`.

    `access_level` is left at the API's own default - private (BR-01). A
    migration is not the moment to widen who can see forty prompts, and the
    person who owns each one can share it afterwards.
    """
    prompt_id = find_prompt(api, entry["namespace"], entry["name"])
    adopted = prompt_id is not None
    if prompt_id is None:
        prompt = api(
            "POST",
            "/api/v1/prompts",
            {
                "namespace": entry["namespace"],
                "name": entry["name"],
                "title": entry["title"],
                "purpose": entry.get("purpose", ""),
            },
        )
        prompt_id = prompt["prompt_id"] if "prompt_id" in prompt else prompt["id"]

    provider, model = binding_for(entry, provider_config_id, fallback_model)

    revision = api(
        "POST",
        f"/api/v1/prompts/{prompt_id}/revisions",
        {
            "body": entry["body"],
            # A-050 requires a summary and this is the honest one: it says where
            # the text came from, which is what somebody reading the history in a
            # year needs in order to trust the first revision at all.
            "change_summary": "Imported from source by prope-migrate. "
            + ", ".join(
                f"{source['file']}:{source.get('line', '?')}" for source in entry["sources"][:3]
            ),
            **({"provider_config_id": provider, "upstream_model": model} if provider else {}),
            **({"parameters": entry["parameters"]} if entry.get("parameters") else {}),
            **provenance_for(entry, conversion_model),
        },
    )
    return prompt_id, revision.get("version_id", ""), adopted


# --- the command ------------------------------------------------------------


def plan(
    manifest: dict[str, Any], provider_config_id: str | None, fallback_model: str | None
) -> None:
    prompts = manifest["prompts"]
    print(f"{len(prompts)} prompt(s) would be created as Draft:\n")
    for entry in prompts:
        provider, model = binding_for(entry, provider_config_id, fallback_model)
        variables = ", ".join(v["name"] for v in entry.get("variables") or []) or "none"
        flag = "" if entry.get("name_confidence", "medium") == "high" else "  <- CHECK THE NAME"
        print(f"  {entry['namespace']}/{entry['name']}{flag}")
        print(f"      {entry.get('title', '')}")
        print(f"      variables: {variables}")
        print(f"      from:      {entry['sources'][0]['file']}:{entry['sources'][0].get('line', '?')}")
        print(f"      binds:     {model + ' on ' + provider if provider else 'NOTHING'}")
        converted = entry.get("original_format", "xml") != "xml"
        print(f"      original:  {entry.get('original_format', 'xml')}"
              f"{', converted by a model' if converted else ', already canonical'}")
        for warning in entry.get("warnings") or []:
            print(f"      warning:   {warning}")
        print()
    print("Nothing has been sent. Re-run with --apply to create these.")
    print("They will be Draft: not approved, not released, and not callable.")
    if provider_config_id is None:
        print()
        print("NOTHING WILL BE BOUND TO A PROVIDER.")
        print("A revision with no provider binding can be approved and released and")
        print("still fails every call with `provider_configuration_unusable`. Pass")
        print("--provider-config-id and --upstream-model unless somebody is going to")
        print("bind each revision by hand in the web application afterwards.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", default=".prope/manifest.json", type=pathlib.Path)
    parser.add_argument("--base-url", default=os.environ.get("PROPE_BASE_URL", ""))
    parser.add_argument(
        "--session",
        default=os.environ.get("PROPE_SESSION", ""),
        help="value of the prope_session cookie (or PROPE_SESSION)",
    )
    parser.add_argument(
        "--conversion-model",
        default=os.environ.get("PROPE_CONVERSION_MODEL", "") or None,
        help="the model that reorganised the prompts into canonical XML "
        "(or PROPE_CONVERSION_MODEL). Required when any row records a conversion.",
    )
    parser.add_argument(
        "--provider-config-id",
        default=os.environ.get("PROPE_PROVIDER_CONFIG_ID", "") or None,
        help="the workspace provider configuration to bind every revision to "
        "(or PROPE_PROVIDER_CONFIG_ID). Without it nothing registered here is callable.",
    )
    parser.add_argument(
        "--upstream-model",
        default=os.environ.get("PROPE_UPSTREAM_MODEL", "") or None,
        help="the provider model to bind where the manifest row does not name one "
        "(or PROPE_UPSTREAM_MODEL)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually create the prompts. Without this, prints a plan and exits.",
    )
    arguments = parser.parse_args()

    try:
        manifest = load(arguments.manifest)

        problems = [
            problem
            for index, entry in enumerate(manifest["prompts"])
            for problem in check_entry(entry, index)
        ]
        problems += check_bindings(
            manifest, arguments.provider_config_id, arguments.upstream_model
        )
        problems += check_provenance(manifest, arguments.conversion_model)
        if problems:
            print(f"{len(problems)} problem(s) in the manifest. Nothing has been sent.\n")
            for problem in problems:
                print(f"  - {problem}")
            return 1

        if not arguments.apply:
            plan(manifest, arguments.provider_config_id, arguments.upstream_model)
            return 0

        if not arguments.base_url:
            raise RefusedError("--base-url is required to apply (or set PROPE_BASE_URL)")
        if not arguments.session:
            raise RefusedError("--session is required to apply (or set PROPE_SESSION)")

        api = Api(arguments.base_url, arguments.session)
        created: list[str] = []
        # No transaction spans these, so a failure halfway leaves the earlier
        # prompts created. That is recoverable — remove them from the manifest and
        # re-run — and it is why what has been done so far is printed before the
        # error rather than after it.
        try:
            for entry in manifest["prompts"]:
                prompt_id, version_id, adopted = register_one(
                    api,
                    entry,
                    arguments.provider_config_id,
                    arguments.upstream_model,
                    arguments.conversion_model,
                )
                created.append(f"{entry['namespace']}/{entry['name']}")
                verb = "revised" if adopted else "created"
                print(f"{verb}  {entry['namespace']}/{entry['name']}  {prompt_id}  {version_id}")
        except RefusedError:
            if created:
                print(f"\n{len(created)} prompt(s) were created before this failed:")
                for name in created:
                    print(f"  {name}")
                print("Remove those rows from the manifest before re-running.")
            raise

        print(f"\n{len(created)} prompt(s) registered, every revision Draft.")
        print("None of them is callable yet. Each needs a review and a release,")
        print("performed by a person in the web application, one at a time.")
        if arguments.provider_config_id is None:
            print()
            print("None of them binds a provider either, so releasing one is not enough:")
            print("the first call will fail with `provider_configuration_unusable`. Bind a")
            print("provider and model on each revision before releasing it.")
        return 0

    except RefusedError as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
