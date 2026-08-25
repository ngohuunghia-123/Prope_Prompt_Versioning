"""Run the live chat lanes against one model, or several, and compare them.

The lanes live in `tests/live_chat` and are opted into with
`PROPE_RUN_CHAT_LIVE=1`. `make chat-live MODEL=...` runs them on a POSIX shell;
this is the same job for anyone whose shell is PowerShell — where `VAR=value
command` is parsed as a command name, not an assignment — and it does the thing
a shell one-liner cannot: run the suite once per model and put the results side
by side.

**Credentials come from `.env` and are never passed in or printed.**
`tests/live_chat/conftest.py` loads that file before anything imports `prope`,
because the provider settings are read into module constants at import time and
any later load is too late. This script only checks the keys are present, by
length, and refuses to start without them.

One trap it guards, which costs an afternoon when it bites: that loader uses
`os.environ.setdefault`, so **a variable already exported in your shell wins
over `.env`**. A stale `APP_OPENAI_API_KEY` from an earlier experiment silently
replaces the file's, and the failure reads like a bad model rather than a bad
environment. This warns when it finds one.

Standard library only; it shells out to the project's own `uv run pytest`.

    python playgrounds/chat-live-cli/main.py --model google/gemini-2.5-flash
    python playgrounds/chat-live-cli/main.py --router-only -k "slug or delete"
    python playgrounds/chat-live-cli/main.py --compare \\
        google/gemini-2.5-flash google/gemini-2.5-flash-lite qwen/qwen3.5-9b

Mixing tiers is a first-class case, because the drafter is what fails first as
models get smaller:

    python playgrounds/chat-live-cli/main.py \\
        --model google/gemini-2.5-flash --router google/gemini-2.5-flash-lite
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"
LANES = {
    "both": "tests/live_chat",
    "router": "tests/live_chat/test_router_conformance_live.py",
    "journeys": "tests/live_chat/test_chat_journeys_live.py",
}

#: Reaching a provider at all needs these three. The Langfuse keys are optional:
#: without them the managed instructions fall back to the compiled-in ones, which
#: is a different measurement but still a valid run.
REQUIRED = ("APP_OPENAI_API_KEY", "APP_OPENAI_BASE_URL", "APP_AGENT_MODEL")

#: Every program whose model this script can point somewhere. All four are set
#: for `--model`, not just `APP_AGENT_MODEL`: a `CHAT_ROUTER_MODEL` left in
#: `.env` would otherwise win, and the report would name a model that did not
#: route.
PROGRAM_VARS = {
    "model": ("APP_AGENT_MODEL", "CHAT_ROUTER_MODEL", "CHAT_REPLY_MODEL", "CHAT_DRAFT_MODEL"),
    "router": ("CHAT_ROUTER_MODEL",),
    "reply": ("CHAT_REPLY_MODEL",),
    "draft": ("CHAT_DRAFT_MODEL",),
}


# ---------------------------------------------------------------------------
# .env — presence, never a value
# ---------------------------------------------------------------------------


def read_dotenv() -> dict[str, str]:
    """The file's own pairs. Same parsing as the loader the tests use."""
    values: dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"')
    return values


def check_credentials() -> bool:
    """Report what `.env` carries, as lengths, and whether the shell overrides it."""
    if not ENV_FILE.exists():
        print(f"no .env at {ENV_FILE}", file=sys.stderr)
        print("it holds the provider credentials this lane spends; see .env.example", file=sys.stderr)
        return False

    values = read_dotenv()
    print("\ncredentials from .env")
    missing = []
    for name in REQUIRED:
        value = values.get(name, "")
        if not value:
            missing.append(name)
            print(f"  {name:<22} MISSING")
            continue
        shown = f"set ({len(value)} chars)" if "KEY" in name or "SECRET" in name else value
        print(f"  {name:<22} {shown}")

        live = os.environ.get(name)
        if live and live != value:
            print(f"  {'':<22} ^ your shell exports {name}; .env will NOT be used for it")

    if missing:
        print(f"\ncannot run: .env is missing {', '.join(missing)}", file=sys.stderr)
        return False
    return True


# ---------------------------------------------------------------------------
# One run
# ---------------------------------------------------------------------------


def overrides_for(args: argparse.Namespace, model: str | None) -> dict[str, str]:
    env = {"PROPE_RUN_CHAT_LIVE": "1"}
    if model:
        for name in PROGRAM_VARS["model"]:
            env[name] = model
    for program in ("router", "reply", "draft"):
        chosen = getattr(args, program)
        if chosen:
            for name in PROGRAM_VARS[program]:
                env[name] = chosen
    return env


def run_lane(args: argparse.Namespace, model: str | None, json_path: Path | None) -> tuple[int, dict]:
    """One pytest invocation. Returns its exit code and whatever JSON it wrote."""
    env = dict(os.environ)
    env.update(overrides_for(args, model))
    if json_path is not None:
        env["PROPE_CHAT_LIVE_JSON"] = str(json_path)

    command = [
        "uv",
        "run",
        "pytest",
        LANES[args.lane],
        "-q",
        "-s",  # what lets the tables out of pytest's capture
        "-p",
        "no:randomly",  # journeys in file order, so the table reads as a walkthrough
        "--tb=line",
    ]
    if args.k:
        command += ["-k", args.k]

    print(f"\n{'=' * 78}")
    print(f"model    {model or '(from .env)'}")
    print(f"lane     {LANES[args.lane]}")
    print(f"command  {' '.join(command)}")
    print("=" * 78, flush=True)

    started = time.monotonic()
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    elapsed = time.monotonic() - started

    payload: dict = {}
    if json_path is not None and json_path.exists():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except ValueError:
            payload = {}
    payload["seconds"] = round(elapsed, 1)
    payload["exit_code"] = completed.returncode
    return completed.returncode, payload


# ---------------------------------------------------------------------------
# Several runs, side by side
# ---------------------------------------------------------------------------


def compare(results: list[tuple[str, dict]]) -> None:
    """The table the whole `--compare` mode exists for."""
    print(f"\n{'=' * 96}")
    print("COMPARISON")
    print("-" * 96)
    print(f"{'MODEL':<38}{'INTENT':<12}{'TOOL':<12}{'JOURNEYS':<12}{'WRITES':<10}TIME")
    print("-" * 96)

    for model, payload in results:
        conformance = payload.get("conformance") or {}
        cases = conformance.get("cases") or 0
        intent = f"{conformance['intent_hits']}/{cases}" if cases else "-"
        tool = f"{conformance['tool_hits']}/{cases}" if cases else "-"
        writes = (
            f"{conformance['writes_reached']}/{conformance['writes_total']}" if conformance.get("writes_total") else "-"
        )
        total = payload.get("total") or 0
        journeys = f"{payload.get('fulfilled', 0)}/{total}" if total else "-"
        print(f"{model[:37]:<38}{intent:<12}{tool:<12}{journeys:<12}{writes:<10}{payload.get('seconds', 0):.0f}s")

    # Which journeys a model got wrong matters more than how many, because the
    # failures are rarely the same ones twice.
    print("-" * 96)
    for model, payload in results:
        gaps = [row["journey"] for row in payload.get("journeys", []) if row.get("verdict") != "ok"]
        misrouted = (payload.get("conformance") or {}).get("misrouted") or []
        if gaps:
            print(f"{model}: journeys {', '.join(gaps)}")
        if misrouted:
            print(f"{model}: routing  {', '.join(misrouted)}")
    print("=" * 96)


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the live chat lanes against one model, or compare several.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--model", help="point every chat program at this model for the run")
    parser.add_argument("--router", help="override the router's model only")
    parser.add_argument("--reply", help="override the responder's model only")
    parser.add_argument("--draft", help="override the drafter's model only")
    parser.add_argument(
        "--compare",
        nargs="+",
        metavar="MODEL",
        help="run the lane once per model and print a comparison table",
    )
    parser.add_argument("--router-only", action="store_true", help="the routing sweep alone (fast)")
    parser.add_argument("--journeys-only", action="store_true", help="the end-to-end journeys alone")
    parser.add_argument("-k", help='a pytest -k expression, e.g. "slug or delete"')
    parser.add_argument(
        "--out-dir",
        default="runs",
        help="where the per-run JSON goes (default: runs/)",
    )
    args = parser.parse_args()

    if args.router_only and args.journeys_only:
        parser.error("pick one of --router-only / --journeys-only, or neither for both")
    args.lane = "router" if args.router_only else "journeys" if args.journeys_only else "both"

    if not check_credentials():
        return 2

    out_dir = (ROOT / args.out_dir).resolve()

    if args.compare:
        results: list[tuple[str, dict]] = []
        worst = 0
        for model in args.compare:
            slug = model.replace("/", "-").replace(":", "-")
            code, payload = run_lane(args, model, out_dir / f"{slug}.json")
            results.append((model, payload))
            worst = max(worst, code)
        compare(results)
        print(f"\nper-run JSON in {out_dir}")
        # A failing journey is a finding, not a broken tool. Report it, do not
        # make the comparison itself look like a crash.
        return 0

    code, payload = run_lane(args, args.model, out_dir / "last.json")
    if code != 0:
        print(f"\npytest exited {code} — see the GAPS and NOTES sections above for why.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
