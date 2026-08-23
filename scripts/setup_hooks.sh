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

# Node is available in the frontend toolchain and avoids relying on the shell
# selected by the AI client.
git config --local alias.ai-log '!node scripts/log_hook.mjs'
echo "[ai-log] git alias 'ai-log' installed."

mkdir -p .ai-log
touch .ai-log/.gitkeep

echo "[ai-log] Setup complete. Configure AI_LOG_SERVER in your .env file."
