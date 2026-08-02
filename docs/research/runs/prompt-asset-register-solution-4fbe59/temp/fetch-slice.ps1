param([string]$ListFile, [string]$LogFile)
$tag = "prompt-asset-register-solution-4fbe59"
$lines = Get-Content $ListFile
foreach ($line in $lines) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $parts = $line.Split('|')
    $url = $parts[0].Trim()
    $score = $parts[1].Trim()
    $attempt = 0
    $ok = $false
    while (-not $ok -and $attempt -lt 2) {
        $attempt++
        try {
            $out = & hyperresearch fetch $url --tag $tag --utility-score $score -j 2>&1 | Out-String
            if ($out -match '"ok": true') {
                Add-Content -Path $LogFile -Value "OK   $url" -Encoding utf8
                $ok = $true
            } else {
                if ($attempt -ge 2) {
                    Add-Content -Path $LogFile -Value "FAIL $url :: $($out -replace "`r?`n",' ' )" -Encoding utf8
                } else {
                    Start-Sleep -Seconds 3
                }
            }
        } catch {
            if ($attempt -ge 2) {
                Add-Content -Path $LogFile -Value "ERR  $url :: $($_.Exception.Message)" -Encoding utf8
            } else {
                Start-Sleep -Seconds 3
            }
        }
    }
}
Add-Content -Path $LogFile -Value "SLICE-DONE $ListFile" -Encoding utf8
