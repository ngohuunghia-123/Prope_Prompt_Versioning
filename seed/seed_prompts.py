"""Seed a workspace with the prompt library from ``playgrounds/prompts``.

What it does, end to end:

1. Authenticates with an email + password exactly the way the app does
   (``access_control.sessions.sign_in``), which resolves the person to their
   workspace — the "company" the prompts are imported into.
2. Converts every ``*.txt`` prompt into canonical XML offline and deterministically
   (see ``seed/converter.py``); no LLM, no network, reproducible.
3. Inserts each as a ``registry.prompt_property`` plus one ``Draft``
   ``registry.revision`` through the real command layer, inside the
   ``workspace_transaction`` tenant seam — the same path the API uses, so history
   events and the search index are maintained.

Deliberately leaves every revision as ``Draft``. Prope's whole reason to exist is
that *no prompt reaches production without a recorded human approval*; a seed that
auto-released would break the one guarantee a spreadsheet cannot give. Approval
and release stay a human step in the app.

Re-running is safe: a prompt whose ``namespace/name`` already exists is skipped,
not duplicated.

Run it inside the compose network (Postgres is not exposed to the host), as the
``prope_app`` role the ``app`` service already uses::

    docker compose run --rm \\
      -v "$(pwd)/seed:/work/seed" \\
      -v "$(pwd)/playgrounds:/work/playgrounds" \\
      -w /work \\
      app \\
      python seed/seed_prompts.py --email owner@acme.com --password 'secret'

Credentials may also come from ``SEED_EMAIL`` / ``SEED_PASSWORD`` to keep the
password out of the process list.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

# Make `import converter` (this folder) and `import prope` (src layout) work
# whether the package is pip-installed in the image or only on disk.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
_SRC = _HERE.parent / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))

import converter  # noqa: E402

from prope.access_control.sessions import sign_in  # noqa: E402
from prope.db.engine import Settings, build_engine, build_sessionmaker  # noqa: E402
from prope.db.session import workspace_transaction  # noqa: E402
from prope.prompt_registry import commands  # noqa: E402
from prope.prompt_registry.domain import (  # noqa: E402
    MAX_BODY_CHARACTERS,
    MAX_PURPOSE_CHARACTERS,
    MAX_TITLE_CHARACTERS,
    RevisionDraft,
)
from prope.property_history.registry import (  # noqa: E402
    install_registry,
    load_action_registry,
)
from prope.session_auth import ManagementRefusal  # noqa: E402

#: The canonical XML contract version recorded on each revision as
#: ``conversion_schema_version``. Kept in step with
#: ``prope.prompt_conversion.service.SCHEMA_VERSION`` ("2"); defined locally so a
#: seed run does not drag in the langfuse/DSPy import chain just for a constant.
SCHEMA_VERSION = "2"

#: Marks the model rows this script created, so they read as one import.
CONVERSION_MODEL = "deterministic-seed-v1"
CHANGE_SUMMARY = "Imported from playgrounds/prompts"
_NAME_CLEAN = re.compile(r"[^a-z0-9._-]+")
_NAME_TRIM = re.compile(r"^[^a-z0-9]+|[^a-z0-9]+$")


def _slug(stem: str) -> str:
    """A filename stem as an A-021 model name: ``^[a-z0-9][a-z0-9._-]{0,62}$``."""
    slug = _NAME_CLEAN.sub("-", stem.lower())
    slug = re.sub(r"-{2,}", "-", slug)
    slug = _NAME_TRIM.sub("", slug)[:63]
    slug = _NAME_TRIM.sub("", slug)  # re-trim after truncation
    return slug or "prompt"


def _pretty_title(stem: str) -> str:
    words = re.split(r"[_\-\s]+", stem.strip())
    titled = " ".join(w[:1].upper() + w[1:] for w in words if w)
    return titled[:MAX_TITLE_CHARACTERS] or stem[:MAX_TITLE_CHARACTERS]


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    marker = "\n[... truncated ...]"
    return text[: max(1, limit - len(marker))].rstrip() + marker


class Deduper:
    """Keeps ``namespace/name`` unique across the batch by suffixing collisions."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def unique(self, base: str) -> str:
        candidate = base
        counter = 2
        while candidate in self._seen:
            suffix = f"-{counter}"
            candidate = f"{base[: 63 - len(suffix)]}{suffix}"
            counter += 1
        self._seen.add(candidate)
        return candidate


async def _resolve_workspace(sessionmaker, *, email: str, password: str) -> tuple[str, str]:
    """Return ``(user_id, workspace_id)`` for the given credentials, or exit."""
    result = await sign_in(
        sessionmaker,
        email=email,
        password=password,
        source_address="seed-script",
        user_agent="prope-seed",
    )
    if result.session is None:
        sys.exit(
            f"authentication failed ({result.metric_result}); check the email and "
            "password, and that the account has an active workspace membership"
        )
    return result.session.user_id, result.session.workspace_id


async def _seed_one(
    sessionmaker,
    *,
    path: Path,
    workspace_id: str,
    user_id: str,
    namespace: str,
    name: str,
    access_level: str,
    tags: list[str],
) -> str:
    """Create one prompt + Draft revision. Returns an outcome word for the tally."""
    raw = path.read_text(encoding="utf-8")
    conversion = converter.convert_file(raw, fallback_title=_pretty_title(path.stem))

    body = conversion.xml
    if len(body) > MAX_BODY_CHARACTERS:  # converter guards this, belt and braces
        return "skipped:oversized"

    now = datetime.now(UTC)
    try:
        async with workspace_transaction(sessionmaker, workspace_id) as db:
            prompt = await commands.create_prompt(
                db,
                workspace_id=workspace_id,
                actor_id=user_id,
                namespace=namespace,
                name=name,
                title=conversion.title,
                purpose=_truncate(f"Imported prompt library entry ({path.name}).", MAX_PURPOSE_CHARACTERS),
                owner_id=user_id,
                access_level=access_level,
                tags=tags,
                now=now,
            )
            await commands.create_revision(
                db,
                workspace_id=workspace_id,
                actor_id=user_id,
                prompt_id=prompt.id,
                draft=RevisionDraft(
                    body=body,
                    change_summary=CHANGE_SUMMARY,
                    original_body=_truncate(raw, MAX_BODY_CHARACTERS),
                    original_format="txt",
                    original_filename=path.name,
                    conversion_model=CONVERSION_MODEL,
                    conversion_schema_version=SCHEMA_VERSION,
                    parameters={},
                ),
                now=now,
            )
    except ManagementRefusal as refusal:
        # 409 == a prompt with this namespace/name already exists → idempotent skip.
        if refusal.status_code == 409:
            return "skipped:exists"
        raise
    return "created"


async def run(args: argparse.Namespace) -> None:
    email = args.email or os.environ.get("SEED_EMAIL")
    password = args.password or os.environ.get("SEED_PASSWORD")
    if not email or not password:
        sys.exit("provide --email/--password (or SEED_EMAIL/SEED_PASSWORD)")

    prompts_dir = Path(args.prompts_dir)
    files = sorted(prompts_dir.glob("*.txt"))
    if args.limit:
        files = files[: args.limit]
    if not files:
        sys.exit(f"no .txt prompts found in {prompts_dir}")

    settings = Settings()
    engine = build_engine(settings.database_url)
    sessionmaker = build_sessionmaker(engine)

    try:
        # ADR-0038: the history-event appends that create_prompt/create_revision
        # make require the action registry to be installed in this process, just
        # as prope.app's lifespan and the worker do at startup. Read with NO
        # tenant context (D-56).
        async with sessionmaker() as session:
            install_registry(await load_action_registry(session))

        user_id, workspace_id = await _resolve_workspace(
            sessionmaker, email=email, password=password
        )
        print(f"authenticated as {email} → workspace {workspace_id}")

        if args.dry_run:
            print(f"[dry-run] would import {len(files)} prompts into namespace "
                  f"'{args.namespace}' (access={args.access_level})")
            return

        deduper = Deduper()
        tags = [tag for tag in (args.tags or "").split(",") if tag.strip()] or ["seed"]
        tally: dict[str, int] = {}
        for index, path in enumerate(files, start=1):
            name = deduper.unique(_slug(path.stem))
            try:
                outcome = await _seed_one(
                    sessionmaker,
                    path=path,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    namespace=args.namespace,
                    name=name,
                    access_level=args.access_level,
                    tags=tags,
                )
            except Exception as error:  # noqa: BLE001 — one bad file must not stop the batch
                outcome = "error"
                print(f"  ! {path.name}: {error!r}", file=sys.stderr)
            tally[outcome] = tally.get(outcome, 0) + 1
            if index % 25 == 0 or index == len(files):
                done = ", ".join(f"{k}={v}" for k, v in sorted(tally.items()))
                print(f"  [{index}/{len(files)}] {done}")

        print("done:", ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a workspace with the prompt library.")
    parser.add_argument("--email", help="account email (or SEED_EMAIL)")
    parser.add_argument("--password", help="account password (or SEED_PASSWORD)")
    parser.add_argument(
        "--prompts-dir",
        default=str(_HERE.parent / "playgrounds" / "prompts"),
        help="directory of *.txt prompts (default: playgrounds/prompts)",
    )
    parser.add_argument("--namespace", default="library", help="model-name namespace (default: library)")
    parser.add_argument(
        "--access-level",
        default="workspace",
        choices=["private", "workspace"],
        help="visibility of imported prompts (default: workspace)",
    )
    parser.add_argument("--tags", default="seed", help="comma-separated tags (default: seed)")
    parser.add_argument("--limit", type=int, default=0, help="only import the first N files")
    parser.add_argument("--dry-run", action="store_true", help="authenticate and count, write nothing")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
