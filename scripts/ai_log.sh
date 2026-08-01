#!/usr/bin/env bash
# Single entry point for the per-tool AI logging hooks.
#
# Self-locating: a hook config only has to get the path to *this* file right —
# the Python launcher and the logger next to it are resolved from $BASH_SOURCE,
# so nothing downstream depends on the directory the AI tool was started in.
#
# Usage from a hook config:  bash <repo>/scripts/ai_log.sh --tool=<name>
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$HERE/_pyrun.sh" "$HERE/log_hook.py" "$@"
