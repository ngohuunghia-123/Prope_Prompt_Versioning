"""CLI for prope-agent.

Designed to match the user's stated contract:
    Input  — a system prompt (string or @file).
    Output — an improved system prompt (the agent's `final_prompt`).

Usage:
    prope-agent optimize "You are a helpful assistant."
    prope-agent optimize --file ./my_prompt.txt
    prope-agent optimize "..." --provider openai --model gpt-4o-mini
    prope-agent optimize "..." --json     # full structured result
    prope-agent demo                      # run on a built-in fixture
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from ..agents import run_workflow
from ..core.config import ProviderKind, get_settings
from ..core.logging import setup_logging
from ..providers import build_provider


async def _run(args: argparse.Namespace) -> int:
    setup_logging("INFO")

    prompt_text: str
    if args.file:
        prompt_text = Path(args.file).read_text(encoding="utf-8")
    elif args.demo:
        prompt_text = (
            "You are a customer support assistant. "
            "You answer questions about orders, refunds, and shipping. "
            "Be friendly and helpful."
        )
    else:
        prompt_text = args.prompt or ""

    if not prompt_text.strip():
        print(
            "error: empty prompt. Pass --prompt, --file, or --demo.",
            file=sys.stderr,
        )
        return 2

    settings = get_settings()
    if args.provider:
        settings.provider = ProviderKind(args.provider)
    if args.model:
        settings.openai_model = args.model
    if args.api_key:
        os.environ["PROPE_AGENT_OPENAI_API_KEY"] = args.api_key
        # Re-read settings so provider picks up the new key.
        from ..core.config import Settings
        settings = Settings()

    provider = build_provider(settings)
    initial = {
        "workflow_id": "cli",
        "workspace_id": "cli",
        "original_prompt": prompt_text,
        "prompt_metadata": {"source": "cli", "use_case": args.use_case or ""},
    }
    final = await run_workflow(initial_state=initial, provider=provider)

    if args.json:
        print(json.dumps(final, indent=2, default=str))
        return 0

    final_prompt = (
        final.get("final_prompt")
        or final.get("candidate_prompt")
        or prompt_text
    )

    if args.explain:
        print("=" * 78)
        print("ANALYSIS")
        print("=" * 78)
        print(
            json.dumps(final.get("analysis", {}), indent=2, default=str)[:2000]
        )
        print()
        print("=" * 78)
        print("CHANGES")
        print("=" * 78)
        for c in final.get("changes", []):
            print(
                f"- [{c.get('type')}] {c.get('reason')} "
                f"(expected: {c.get('expected_effect')})"
            )
        print()
        print("=" * 78)
        print("COMPARISON")
        print("=" * 78)
        print(json.dumps(final.get("comparison", {}), indent=2, default=str))
        print()
        print("=" * 78)
        print("EXPLANATION")
        print("=" * 78)
        print(final.get("explanation") or "(no explanation)")

    print()
    print("=" * 78)
    print("ORIGINAL")
    print("=" * 78)
    print(prompt_text)
    print()
    print("=" * 78)
    print("IMPROVED")
    print("=" * 78)
    print(final_prompt)
    print("=" * 78)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="prope-agent",
        description=(
            "Optimize a system prompt. "
            "Input: a prompt string (or --file / --demo). "
            "Output: the improved prompt."
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    opt = sub.add_parser("optimize", help="Run the optimization workflow.")
    opt.add_argument("prompt", nargs="?", help="System prompt to improve.")
    opt.add_argument("--file", help="Read prompt from a file.")
    opt.add_argument(
        "--demo",
        action="store_true",
        help="Run on a built-in customer-support fixture.",
    )
    opt.add_argument(
        "--provider", choices=[k.value for k in ProviderKind], default=None
    )
    opt.add_argument("--model", default=None)
    opt.add_argument(
        "--api-key",
        default=None,
        help="API key override (otherwise reads PROPE_AGENT_OPENAI_API_KEY).",
    )
    opt.add_argument("--use-case", default=None)
    opt.add_argument(
        "--explain",
        action="store_true",
        help="Print analysis / changes / comparison / explanation.",
    )
    opt.add_argument(
        "--json", action="store_true", help="Print full structured state as JSON."
    )
    opt.set_defaults(func=_run)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
