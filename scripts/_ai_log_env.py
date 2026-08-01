#!/usr/bin/env python3
"""Shared environment handling for the AI logging scripts.

Hooks are spawned by the AI tools (Claude Code, Codex, Cursor, Gemini) with an
arbitrary working directory and without the project's .env loaded, so every
entry point has to resolve paths against the repo root and read .env itself.

Exposes three things:
  PROJECT_ROOT      absolute repo root, derived from this file's location
  logging_enabled() the AI_LOG master switch
  resolve_log_dir() AI_LOG_DIR, anchored to PROJECT_ROOT when relative
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Values accepted as "on" for AI_LOG. Anything else — including unset — is off.
_TRUTHY = {"1", "true", "yes", "on"}


def load_env(path: Path | None = None) -> None:
    """Load KEY=value pairs from .env into os.environ.

    Dependency-free on purpose: hooks run before (and independently of) the
    project virtualenv, so python-dotenv may not be importable. Real
    environment variables win over .env, which keeps one-off overrides like
    `AI_LOG=false claude` working.
    """
    env_file = path or (PROJECT_ROOT / ".env")
    try:
        text = env_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def logging_enabled() -> bool:
    """True only when AI_LOG is explicitly truthy — the master on/off switch."""
    return os.environ.get("AI_LOG", "").strip().strip("\"'").lower() in _TRUTHY


def resolve_log_dir() -> Path:
    """AI_LOG_DIR as an absolute path.

    A relative AI_LOG_DIR (the default, `.ai-log`) is anchored to the repo root
    rather than the current directory, so a session started in a subfolder
    doesn't scatter stray .ai-log/ directories through the tree.
    """
    raw = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
    return raw if raw.is_absolute() else PROJECT_ROOT / raw
