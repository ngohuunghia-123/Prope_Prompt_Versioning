#!/usr/bin/env bash
# Install git pre-push hook for AI log submission (POSIX / Git Bash).
# Run once after cloning: bash scripts/setup_hooks.sh
set -e

HOOK_FILE=".git/hooks/pre-push"

cat > "$HOOK_FILE" <<'EOF'
#!/usr/bin/env bash
# Pre-push: sweep recent Antigravity / Gemini prompts, then submit AI logs.
# Uses the cross-platform Python launcher so it works whether the user
# has python3, python, or only the `py` launcher (Windows).
bash scripts/_pyrun.sh scripts/log_antigravity.py --auto || true
bash scripts/_pyrun.sh scripts/submit_log.py || true
exit 0  # Never block push, even if either step fails
EOF

chmod +x "$HOOK_FILE"
chmod +x scripts/_pyrun.sh scripts/ai_log.sh 2>/dev/null || true
echo "[ai-log] Git pre-push hook installed."

# `git ai-log` is the entry point used by the Codex / Cursor / Gemini hook
# configs. Going through git buys two things no plain command string can:
# git runs `!` aliases from the repo root (so the tool's working directory
# stops mattering) and it uses its own bundled shell, which on Windows means
# Git Bash rather than the WSL bash.exe that PowerShell resolves.
git config --local alias.ai-log '!bash scripts/ai_log.sh'
echo "[ai-log] git alias 'ai-log' installed."

mkdir -p .ai-log
touch .ai-log/.gitkeep

echo "[ai-log] Setup complete. Configure AI_LOG_SERVER in your .env file."
