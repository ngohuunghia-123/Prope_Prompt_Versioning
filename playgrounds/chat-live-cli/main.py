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

`--compare` runs the models one after another. `--parallel` runs them at once,
which is roughly N times faster and buys it with two caveats the table then
prints for itself: the runs share one gateway account and one rate limit, so a
refused call can masquerade as a bad model, and TIME becomes wall-clock under
contention rather than anything comparable. Reach for it to compare
*correctness* across models, and drop back to one at a time when latency is the
question. Each concurrent run also boots its own PostgreSQL container and
applies the whole migration chain, so the practical ceiling is the machine's.

    python playgrounds/chat-live-cli/main.py --parallel --compare \\
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
from concurrent.futures import ThreadPoolExecutor
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


def run_lane(
    args: argparse.Namespace,
    model: str | None,
    json_path: Path | None,
    *,
    stream: bool = True,
    log_path: Path | None = None,
) -> tuple[int, dict]:
    """One pytest invocation. Returns its exit code and whatever JSON it wrote.

    `stream=False` captures the output to `log_path` rather than the terminal,
    which is what a parallel comparison needs: three pytest processes writing to
    one console interleave mid-line and the tables become unreadable.
    """
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

    if stream:
        print(f"\n{'=' * 78}")
        print(f"model    {model or '(from .env)'}")
        print(f"lane     {LANES[args.lane]}")
        print(f"command  {' '.join(command)}")
        print("=" * 78, flush=True)

    started = time.monotonic()
    if stream:
        completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
        output = ""
    else:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = completed.stdout or ""
    elapsed = time.monotonic() - started

    if log_path is not None and output:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(output, encoding="utf-8")

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


def run_all(args: argparse.Namespace, models: list[str], out_dir: Path) -> list[tuple[str, dict]]:
    """Every model, sequentially or `--parallel` at a time.

    Sequential streams each run to the terminal as it goes. Parallel cannot —
    three pytest processes share one console and interleave mid-line — so it
    captures each to `runs/<model>.log` and prints one line per model as it
    finishes.
    """

    def one(model: str) -> tuple[str, dict]:
        slug = model.replace("/", "-").replace(":", "-")
        code, payload = run_lane(
            args,
            model,
            out_dir / f"{slug}.json",
            stream=args.parallel <= 1,
            log_path=out_dir / f"{slug}.log",
        )
        if args.parallel > 1:
            fulfilled = payload.get("fulfilled")
            total = payload.get("total")
            summary = f"{fulfilled}/{total} journeys" if total else f"exit {code}"
            print(f"  done  {model:<40} {summary}  {payload.get('seconds', 0):.0f}s", flush=True)
        return model, payload

    if args.parallel <= 1:
        return [one(model) for model in models]

    print(f"\nrunning {len(models)} models, {args.parallel} at a time")
    print(f"output captured to {out_dir}{os.sep}<model>.log")
    # Threads rather than processes: every worker spends its life inside one
    # `subprocess.run`, which releases the GIL, and the results have to come
    # back into one address space to be compared anyway.
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = {pool.submit(one, model): model for model in models}
        return [future.result() for future in futures]


def compare(results: list[tuple[str, dict]], *, parallel: int = 1) -> None:
    """The table the whole `--compare` mode exists for."""
    print(f"\n{'=' * 96}")
    print("COMPARISON")
    print("-" * 96)
    time_header = "TIME*" if parallel > 1 else "TIME"
    print(f"{'MODEL':<38}{'INTENT':<12}{'TOOL':<12}{'JOURNEYS':<12}{'WRITES':<10}{time_header}")
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

    # ---- when the comparison is not a comparison --------------------------
    #
    # A refused call and a bad answer look identical in every column above, and
    # only one of them is a fact about the model. `tests/golden/` learned this
    # the expensive way: ten adjudications issued back to back all returned
    # `LMServerError` in two seconds each while the same call alone succeeded.
    # Parallel runs share one account and one rate limit, so they make exactly
    # that failure more likely — and a lane that reports "this model is worse"
    # when the model was throttled is worse than no lane, because it reads as a
    # finding. Say so where the numbers are, not in a docstring nobody opens.
    throttled = [(model, (payload.get("conformance") or {}).get("errors") or []) for model, payload in results]
    throttled = [(model, errors) for model, errors in throttled if errors]
    if throttled:
        print("-" * 96)
        print("GATEWAY REFUSED CALLS — these rows may be measuring throttling, not the model:")
        for model, errors in throttled:
            print(f"  {model}: {len(errors)} ({', '.join(errors[:4])})")
        if parallel > 1:
            print("  re-run the affected models with --parallel 1 before believing the table.")

    if parallel > 1:
        print("-" * 96)
        print(f"* TIME is wall-clock under {parallel}-way contention and is NOT comparable")
        print("  across models. Run with --parallel 1 when latency is what you are measuring.")
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
    parser.add_argument(
        "--parallel",
        nargs="?",
        type=int,
        const=0,
        default=1,
        metavar="N",
        help=(
            "run --compare models concurrently, N at a time (bare --parallel runs all). "
            "Faster, but they share one gateway account and one rate limit, so a refused "
            "call can read as a bad model; TIME stops being comparable too."
        ),
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
        # A bare `--parallel` means all of them; anything else is a cap, and one
        # is the sequential path. Each concurrent run also boots its own
        # PostgreSQL container and applies the whole migration chain, so the
        # ceiling is the machine's, not the gateway's.
        if args.parallel == 0:
            args.parallel = len(args.compare)
        args.parallel = max(1, min(args.parallel, len(args.compare)))

        results = run_all(args, list(args.compare), out_dir)
        compare(results, parallel=args.parallel)
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
