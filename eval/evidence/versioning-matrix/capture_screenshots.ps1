[CmdletBinding()]
param(
    [string]$BaseUrl = "http://localhost:8080",
    [int]$DebugPort = 9333
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$Utf8NoBom = [Text.UTF8Encoding]::new($false)
$script:CdpId = 0

function Import-ValidDotEnv {
    $envPath = Resolve-Path (Join-Path $Root "../../../.env")
    foreach ($line in [IO.File]::ReadAllLines($envPath, [Text.Encoding]::UTF8)) {
        if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { continue }
        $name = $matches[1]
        $value = $matches[2].Trim()
        if ($value.Length -ge 2) {
            $quoted = ($value[0] -eq '"' -and $value[-1] -eq '"') -or
                ($value[0] -eq "'" -and $value[-1] -eq "'")
            if ($quoted) { $value = $value.Substring(1, $value.Length - 2) }
        }
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Receive-CdpMessage($Socket) {
    $stream = New-Object IO.MemoryStream
    try {
        do {
            $buffer = New-Object byte[] 65536
            $segment = [ArraySegment[byte]]::new($buffer)
            $result = $Socket.ReceiveAsync($segment, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
            if ($result.MessageType -eq [Net.WebSockets.WebSocketMessageType]::Close) {
                throw "CDP socket closed unexpectedly"
            }
            $stream.Write($buffer, 0, $result.Count)
        } while (-not $result.EndOfMessage)
        return [Text.Encoding]::UTF8.GetString($stream.ToArray()) | ConvertFrom-Json
    } finally {
        $stream.Dispose()
    }
}

function Invoke-Cdp($Socket, [string]$Method, $Params = @{}) {
    $script:CdpId += 1
    $id = $script:CdpId
    $payload = @{ id = $id; method = $Method; params = $Params } | ConvertTo-Json -Depth 20 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
    $Socket.SendAsync(
        [ArraySegment[byte]]::new($bytes),
        [Net.WebSockets.WebSocketMessageType]::Text,
        $true,
        [Threading.CancellationToken]::None
    ).GetAwaiter().GetResult()
    do {
        $message = Receive-CdpMessage $Socket
    } while ($message.id -ne $id)
    if ($null -ne $message.error) { throw "CDP $Method failed: $($message.error.message)" }
    return $message.result
}

Import-ValidDotEnv
if ([string]::IsNullOrWhiteSpace($env:ADMIN_SESSION_TOKEN)) { throw "Missing ADMIN_SESSION_TOKEN" }
if (-not (Test-Path -LiteralPath $Edge)) { throw "Microsoft Edge was not found" }

$profile = Join-Path $env:TEMP ("prope-evidence-edge-" + [Guid]::NewGuid().ToString("N"))
$edgeProcess = Start-Process -FilePath $Edge -ArgumentList @(
    "--headless=new",
    "--disable-gpu",
    "--remote-debugging-port=$DebugPort",
    "--user-data-dir=$profile",
    "--window-size=1440,1000",
    "about:blank"
) -WindowStyle Hidden -PassThru

try {
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds(20)
    do {
        try {
            $version = Invoke-RestMethod -UseBasicParsing -Uri "http://localhost:$DebugPort/json/version"
            break
        } catch {
            if ([DateTimeOffset]::UtcNow -ge $deadline) { throw }
            Start-Sleep -Milliseconds 250
        }
    } while ($true)

    $target = Invoke-RestMethod -UseBasicParsing -Method Put -Uri "http://localhost:$DebugPort/json/new?about:blank"
    $socket = [Net.WebSockets.ClientWebSocket]::new()
    $socket.ConnectAsync([Uri]$target.webSocketDebuggerUrl, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
    try {
        $null = Invoke-Cdp $socket "Network.enable"
        $null = Invoke-Cdp $socket "Page.enable"
        $null = Invoke-Cdp $socket "Emulation.setDeviceMetricsOverride" @{
            width = 1440; height = 1000; deviceScaleFactor = 1; mobile = $false
        }
        $cookie = Invoke-Cdp $socket "Network.setCookie" @{
            name = "prope_session"
            value = $env:ADMIN_SESSION_TOKEN
            url = $BaseUrl
            httpOnly = $true
            sameSite = "Lax"
        }
        if ($cookie.success -ne $true) { throw "Could not set browser session cookie" }

        $context = [IO.File]::ReadAllText((Join-Path $Root "execution-context.json"), [Text.Encoding]::UTF8) | ConvertFrom-Json
        foreach ($scenario in @("S2", "S3", "S5", "S6", "S10")) {
            $item = $context.scenarios.$scenario
            $url = "$BaseUrl/app/prompts/$($item.prompt_id)/evaluation"
            $null = Invoke-Cdp $socket "Page.navigate" @{ url = $url }
            Start-Sleep -Seconds 7
            $shot = Invoke-Cdp $socket "Page.captureScreenshot" @{
                format = "png"; fromSurface = $true; captureBeyondViewport = $false
            }
            $path = Join-Path $Root "screenshots/$scenario-eval-result.png"
            [IO.File]::WriteAllBytes($path, [Convert]::FromBase64String($shot.data))
        }
    } finally {
        if ($socket.State -eq [Net.WebSockets.WebSocketState]::Open) {
            $socket.CloseAsync(
                [Net.WebSockets.WebSocketCloseStatus]::NormalClosure,
                "done",
                [Threading.CancellationToken]::None
            ).GetAwaiter().GetResult()
        }
        $socket.Dispose()
    }
} finally {
    Stop-Process -Id $edgeProcess.Id -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $profile -Recurse -Force -ErrorAction SilentlyContinue
}
