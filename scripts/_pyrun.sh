#!/usr/bin/env bash
# Cross-platform Python launcher for AI log hooks.
# Tries python3 → python → py -3 on PATH; on Windows, falls back to common
# Python install locations because Git Bash launched by some hooks gets a
# stripped PATH that omits the Windows Python directory.
# Designed to be sourced or called as: bash scripts/_pyrun.sh <script> [args...]
#
# Exits 0 silently if no Python is found — hooks must never block the AI tool.
set -u

# A candidate counts only if it actually runs. Being on PATH is not enough:
# Windows ships app-execution-alias stubs at
# ~/AppData/Local/Microsoft/WindowsApps/python3(.exe) that resolve via
# `command -v` but exit 49 with "Python was not found" when invoked.
# stdin is redirected from /dev/null: the hook payload is sitting on our stdin
# and some candidates (notably the WindowsApps python3 stub) drain it, which
# would leave the real interpreter with nothing to read.
works() {
  "$@" -c "" </dev/null >/dev/null 2>&1
}

PY=()
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_VENV_PY="$SCRIPT_DIR/../.venv/Scripts/python.exe"

if [ -x "$REPO_VENV_PY" ] && works "$REPO_VENV_PY"; then
  PY=("$REPO_VENV_PY")
elif command -v python3 >/dev/null 2>&1 && works python3; then
  PY=(python3)
elif command -v python >/dev/null 2>&1 && works python; then
  PY=(python)
elif command -v py >/dev/null 2>&1 && works py -3; then
  PY=(py -3)
else
  # PATH lookup failed (or every entry on it was a stub) — probe standard
  # Windows install locations.
  shopt -s nullglob 2>/dev/null || true
  for cand in \
    /c/Users/*/AppData/Local/Programs/Python/Python*/python.exe \
    "/c/Program Files/Python"*/python.exe \
    "/c/Program Files (x86)/Python"*/python.exe \
    /c/Python*/python.exe; do
    if [ -x "$cand" ] && works "$cand"; then PY=("$cand"); break; fi
  done
  shopt -u nullglob 2>/dev/null || true
  [ ${#PY[@]} -gt 0 ] || exit 0
fi

exec "${PY[@]}" "$@"
