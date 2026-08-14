"""Tests for the CLI."""
from __future__ import annotations

import os

from prope_agent.cli import build_parser, main


def test_cli_parses_optimize():
    p = build_parser()
    args = p.parse_args(["optimize", "hello"])
    assert args.command == "optimize"
    assert args.prompt == "hello"


def test_cli_demo_runs(capsys):
    rc = main(["optimize", "--demo"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "IMPROVED" in captured.out
    assert "Constraints" in captured.out
