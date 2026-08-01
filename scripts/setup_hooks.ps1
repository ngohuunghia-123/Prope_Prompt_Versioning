# Install git pre-push hook for AI log submission (Windows PowerShell).
# Run once after cloning: powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1

$ErrorActionPreference = 'Stop'

$HookFile = '.git/hooks/pre-push'

# Git on Windows runs hooks via Git Bash, so the hook body must be bash.
$HookBody = @'
#!/usr/bin/env bash
# Pre-push: sweep recent Antigravity / Gemini prompts, then submit AI logs.
bash scripts/_pyrun.sh scripts/log_antigravity.py --auto || true
bash scripts/_pyrun.sh scripts/submit_log.py || true
exit 0
'@

# Write the hook by hand rather than with Set-Content: PowerShell 5.1's
# "-Encoding UTF8" emits a BOM, and a BOM in front of the shebang makes git
# fail with "cannot spawn .git/hooks/pre-push: No such file or directory".
# CRLF has to go too — the shebang line would end up as "…/env bash\r".
$HookBody = $HookBody -replace "`r`n", "`n"
[System.IO.File]::WriteAllText(
    (Join-Path (Get-Location) $HookFile),
    $HookBody + "`n",
    (New-Object System.Text.UTF8Encoding $false)
)
Write-Host "[ai-log] Git pre-push hook installed."

# `git ai-log` is the entry point used by the Codex / Cursor / Gemini hook
# configs. Going through git buys two things no plain command string can:
# git runs `!` aliases from the repo root (so the tool's working directory
# stops mattering) and it uses its own bundled shell, which on Windows means
# Git Bash rather than the WSL `bash.exe` that PowerShell resolves.
git config --local alias.ai-log '!bash scripts/ai_log.sh'
Write-Host "[ai-log] git alias 'ai-log' installed."

if (-not (Test-Path .ai-log)) { New-Item -ItemType Directory -Path .ai-log | Out-Null }
if (-not (Test-Path .ai-log/.gitkeep)) { New-Item -ItemType File -Path .ai-log/.gitkeep | Out-Null }

Write-Host "[ai-log] Setup complete. Configure AI_LOG_SERVER in your .env file."
