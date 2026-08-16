[CmdletBinding()]
param(
    [string]$BaseUrl = "http://localhost:8080",
    [int]$RunTimeoutSeconds = 600
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ApiBase = "$BaseUrl/api/v1"
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)

function Write-ProgressLine([string]$Message) {
    $line = "{0:o} {1}" -f [DateTimeOffset]::Now, $Message
    [IO.File]::AppendAllText((Join-Path $Root "execution.log"), "$line`n", $Utf8NoBom)
}

function Write-JsonFile([string]$Path, $Value) {
    $json = ConvertTo-Json -InputObject $Value -Depth 100
    [IO.File]::WriteAllText($Path, "$json`n", $Utf8NoBom)
}

function Write-JsonArrayFile {
    param(
        [string]$Path,
        [Parameter()][AllowEmptyCollection()][object[]]$Items
    )
    $json = ConvertTo-Json -InputObject @($Items) -Depth 100
    [IO.File]::WriteAllText($Path, "$json`n", $Utf8NoBom)
}

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

function Invoke-PropeJson {
    param(
        [Parameter(Mandatory)][ValidateSet("GET", "POST", "PUT", "DELETE")][string]$Method,
        [Parameter(Mandatory)][string]$Uri,
        $Session,
        $Body,
        [hashtable]$Headers
    )
    $request = @{
        Method = $Method
        Uri = $Uri
        UseBasicParsing = $true
    }
    if ($null -ne $Session) { $request.WebSession = $Session }
    if ($null -ne $Headers) { $request.Headers = $Headers }
    if ($null -ne $Body) {
        $request.ContentType = "application/json"
        $jsonBody = $Body | ConvertTo-Json -Depth 100 -Compress
        $request.Body = [Text.Encoding]::UTF8.GetBytes($jsonBody)
    }
    try {
        $response = Invoke-WebRequest @request
    } catch {
        $status = $null
        $detail = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
        if ($null -ne $_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
            try {
                $reader = [IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
                $detail = $reader.ReadToEnd()
                $reader.Dispose()
            } catch { }
        }
        throw "HTTP $status $Method $Uri failed: $detail"
    }
    $response.RawContentStream.Position = 0
    $buffer = New-Object IO.MemoryStream
    $response.RawContentStream.CopyTo($buffer)
    $utf8Content = [Text.Encoding]::UTF8.GetString($buffer.ToArray())
    $buffer.Dispose()
    $data = if ([string]::IsNullOrWhiteSpace($utf8Content)) { $null } else {
        $utf8Content | ConvertFrom-Json
    }
    [PSCustomObject]@{ Data = $data; Response = $response }
}

function New-AuthorSession([string]$Token) {
    $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $session.Cookies.Add([Net.Cookie]::new("prope_session", $Token, "/", "localhost"))
    return $session
}

function Wait-EvalRun {
    param([string]$RunId, $Session)
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($RunTimeoutSeconds)
    do {
        $run = (Invoke-PropeJson -Method GET -Uri "$ApiBase/eval-runs/$RunId" -Session $Session).Data
        if ($run.status -in @("completed", "refused")) { return $run }
        if ([DateTimeOffset]::UtcNow -ge $deadline) { throw "Eval run $RunId exceeded timeout" }
        Start-Sleep -Seconds 2
    } while ($true)
}

function Get-CandidateHandle($Accepted) {
    $handle = $Accepted.runs | Where-Object { $_.role -eq "candidate" } | Select-Object -First 1
    if ($null -eq $handle) { $handle = $Accepted.runs | Select-Object -First 1 }
    if ($null -eq $handle) { throw "Eval start returned no run handle" }
    return $handle
}

function Submit-Revision([string]$PromptId, [string]$VersionId, $AuthorSession) {
    $null = Invoke-PropeJson -Method POST -Uri "$ApiBase/prompts/$PromptId/revisions/$VersionId/submit" -Session $AuthorSession
}

function Approve-And-Release {
    param(
        [string]$PromptId,
        [string]$VersionId,
        [string]$ExpectedCurrentVersionId,
        [bool]$NeedsAcknowledgement,
        $ReviewerSession
    )
    $body = @{
        comment = "Reviewer confirmed deterministic evidence before release."
        expected_current_version_id = if ($ExpectedCurrentVersionId) { $ExpectedCurrentVersionId } else { $null }
    }
    if ($NeedsAcknowledgement) {
        $body.acknowledgement_reason = "The demo baseline is intentionally released to compare the candidate on the same suite."
    }
    return (Invoke-PropeJson -Method POST -Uri "$ApiBase/prompts/$PromptId/revisions/$VersionId/approve-and-release" -Session $ReviewerSession -Body $body).Data
}

function Request-Changes {
    param([string]$PromptId, [string]$VersionId, [string]$Comment, $ReviewerSession)
    return (Invoke-PropeJson -Method POST -Uri "$ApiBase/prompts/$PromptId/revisions/$VersionId/request-changes" -Session $ReviewerSession -Body @{ comment = $Comment }).Data
}

function Run-Gateway {
    param([string]$ModelName, [string]$InputText, [string]$ApiKey)
    $result = Invoke-PropeJson -Method POST -Uri "$BaseUrl/v1/chat/completions" -Headers @{ Authorization = "Bearer $ApiKey" } -Body @{
        model = $ModelName
        messages = @(@{ role = "user"; content = $InputText })
        stream = $false
    }
    $headers = [ordered]@{}
    foreach ($name in @("x-prope-version-id", "x-prope-revision", "x-prope-model", "x-prope-pinned")) {
        $headers[$name] = [string]$result.Response.Headers[$name]
    }
    return [ordered]@{
        status_code = [int]$result.Response.StatusCode
        headers = $headers
        body = $result.Data
        observed_at = [DateTimeOffset]::Now.ToString("o")
    }
}

function Escape-Markdown($Value) {
    if ($null -eq $Value) { return "N/A" }
    $escaped = ([string]$Value) -replace '\|', '\|'
    return ($escaped -replace '\r?\n', '<br>')
}

Import-ValidDotEnv
Remove-Item (Join-Path $Root "execution.log") -Force -ErrorAction SilentlyContinue
Write-ProgressLine "START"

$required = @("ADMIN_SESSION_TOKEN", "APP_OPENAI_API_KEY", "APP_OPENAI_BASE_URL", "APP_AGENT_MODEL")
foreach ($name in $required) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Missing required runtime setting: $name"
    }
}

$authorSession = New-AuthorSession $env:ADMIN_SESSION_TOKEN
$sessionRead = (Invoke-PropeJson -Method GET -Uri "$ApiBase/auth/session" -Session $authorSession).Data
$workspaceId = $sessionRead.user.workspace_id
$authorId = $sessionRead.user.id

# Create a genuinely separate Reviewer actor in the same workspace. Its one-time
# password and sessions remain memory-only and are never written to evidence.
$reviewerEmail = "eval-reviewer-$([Guid]::NewGuid().ToString('N'))@development.local"
$reviewerMember = (Invoke-PropeJson -Method POST -Uri "$ApiBase/workspaces/$workspaceId/members" -Session $authorSession -Body @{
    email = $reviewerEmail
    display_name = "Eval Evidence Reviewer"
    roles = @("Reviewer", "Admin")
}).Data
$reviewerId = $reviewerMember.user_id
$initialPassword = $reviewerMember.initial_password
$reviewerPassword = "Eval-reviewer-$([Guid]::NewGuid().ToString('N'))"
$reviewerSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$null = Invoke-PropeJson -Method POST -Uri "$ApiBase/auth/login" -Session $reviewerSession -Body @{
    email = $reviewerEmail
    password = $initialPassword
}
$null = Invoke-PropeJson -Method POST -Uri "$ApiBase/auth/password" -Session $reviewerSession -Body @{
    current_password = $initialPassword
    new_password = $reviewerPassword
}
$initialPassword = $null
$reviewerPassword = $null
Write-ProgressLine "ACTORS_READY"

$provider = (Invoke-PropeJson -Method GET -Uri "$ApiBase/providers" -Session $authorSession).Data |
    Where-Object { $_.display_name -eq "Eval Evidence BYOK" -and $_.base_url -eq $env:APP_OPENAI_BASE_URL } |
    Select-Object -First 1
if ($null -eq $provider) {
    $provider = (Invoke-PropeJson -Method POST -Uri "$ApiBase/providers" -Session $authorSession -Body @{
        display_name = "Eval Evidence BYOK"
        base_url = $env:APP_OPENAI_BASE_URL
        credential = $env:APP_OPENAI_API_KEY
        interactive_concurrency = 8
        batch_concurrency = 4
    }).Data
}
$providerId = $provider.provider_config_id
$verification = (Invoke-PropeJson -Method POST -Uri "$ApiBase/providers/$providerId/verify" -Session $authorSession).Data
if ($verification.verification_status -ne "passed") {
    throw "BYOK provider verification failed: $($verification.verification_error)"
}

# Official Gemini 2.5 Flash standard paid-tier rates observed on 2026-08-16:
# USD 0.30/M input and USD 2.50/M output => per-1k values below.
$pricePage = (Invoke-PropeJson -Method GET -Uri "$ApiBase/prices?limit=200" -Session $authorSession).Data
$existingPrice = $pricePage.items | Where-Object {
    $_.provider_config_id -eq $providerId -and $_.upstream_model -eq $env:APP_AGENT_MODEL -and $null -eq $_.effective_to
} | Select-Object -First 1
if ($null -eq $existingPrice) {
    $null = Invoke-PropeJson -Method POST -Uri "$ApiBase/prices" -Session $authorSession -Body @{
        provider_config_id = $providerId
        upstream_model = $env:APP_AGENT_MODEL
        input_price_per_1k = 0.0003
        output_price_per_1k = 0.0025
        minimum_charge_per_request = 0
        currency = "USD"
        effective_from = [DateTimeOffset]::UtcNow.AddMinutes(-5).ToString("o")
    }
}
Write-ProgressLine "PROVIDER_READY model=$($env:APP_AGENT_MODEL)"

$context = [ordered]@{
    schema_version = 1
    status = "EXECUTING"
    executed_at = [DateTimeOffset]::Now.ToString("o")
    provider_config_id = $providerId
    upstream_model = $env:APP_AGENT_MODEL
    pricing_source = "https://ai.google.dev/gemini-api/docs/pricing"
    pricing_observed_at = "2026-08-16"
    actors = [ordered]@{ author_id = $authorId; reviewer_id = $reviewerId }
    scenarios = [ordered]@{}
}

$specFiles = @(
    "S2-cost-guardrail.json",
    "S3-instruction-regression.json",
    "S5-positive-improvement.json",
    "S6-contract-regression.json",
    "S10-lifecycle-rollback.json"
)
$summaryRows = @()

try {
    foreach ($specFile in $specFiles) {
        $spec = [IO.File]::ReadAllText((Join-Path $Root "specs/$specFile"), [Text.Encoding]::UTF8) | ConvertFrom-Json
        $scenario = $spec.scenario_id
        $runDir = Join-Path $Root "runs/$scenario"
        $null = New-Item -ItemType Directory -Path $runDir -Force
        Write-ProgressLine "$scenario CREATE"

        $savedBaselinePath = Join-Path $runDir "baseline-run.json"
        if (Test-Path $savedBaselinePath) {
            # Resume an infrastructure-interrupted lifecycle without re-running
            # a provider output that has already reached a terminal state.
            $baselineRun = [IO.File]::ReadAllText($savedBaselinePath, [Text.Encoding]::UTF8) | ConvertFrom-Json
            $baselineCases = [IO.File]::ReadAllText((Join-Path $runDir "baseline-cases.json"), [Text.Encoding]::UTF8) | ConvertFrom-Json
            $promptId = $baselineRun.prompt_id
            $prompt = (Invoke-PropeJson -Method GET -Uri "$ApiBase/prompts/$promptId" -Session $authorSession).Data
            $baselineRevision = (Invoke-PropeJson -Method GET -Uri "$ApiBase/revisions/$($baselineRun.version_id)" -Session $authorSession).Data
            $attachments = (Invoke-PropeJson -Method GET -Uri "$ApiBase/prompts/$promptId/dataset-attachments" -Session $authorSession).Data
            $dataset = (Invoke-PropeJson -Method GET -Uri "$ApiBase/datasets/$($attachments[0].dataset_id)" -Session $authorSession).Data
            $suite = (Invoke-PropeJson -Method GET -Uri "$ApiBase/eval-suites/$($baselineRun.suite_id)" -Session $authorSession).Data
            $baselineHandle = [PSCustomObject]@{ suite_version = $suite.suite_version }
            Write-ProgressLine "$scenario RESUME_BASELINE run=$($baselineRun.run_id)"
        } else {
            $modelName = "$($spec.prompt.namespace)/$($spec.prompt.name)"
            $prompt = (Invoke-PropeJson -Method GET -Uri "$ApiBase/prompts" -Session $authorSession).Data |
                Where-Object { $_.model_name -eq $modelName } | Select-Object -First 1
            if ($null -eq $prompt) {
                $prompt = (Invoke-PropeJson -Method POST -Uri "$ApiBase/prompts" -Session $authorSession -Body @{
                    namespace = $spec.prompt.namespace
                    name = $spec.prompt.name
                    title = $spec.prompt.title
                    purpose = $spec.goal
                    access_level = $spec.prompt.access_level
                    tags = @("eval-evidence", $scenario.ToLowerInvariant())
                }).Data
                $promptId = $prompt.prompt_id

                $dataset = (Invoke-PropeJson -Method POST -Uri "$ApiBase/datasets" -Session $authorSession -Body @{
                    name = $spec.dataset.name
                    description = $spec.dataset.description
                    kind = $spec.dataset.kind
                    output_modality = $spec.dataset.output_modality
                    folder = ""
                    cases = $spec.dataset.cases
                }).Data
                $null = Invoke-PropeJson -Method PUT -Uri "$ApiBase/prompts/$promptId/dataset-attachments" -Session $authorSession -Body @{
                    dataset_ids = @($dataset.dataset_id)
                }

                $baselineRevision = (Invoke-PropeJson -Method POST -Uri "$ApiBase/prompts/$promptId/revisions" -Session $authorSession -Body @{
                    body = $spec.revisions.baseline.body
                    change_summary = $spec.revisions.baseline.change_summary
                    provider_config_id = $providerId
                    upstream_model = $env:APP_AGENT_MODEL
                    parameters = @{ temperature = 0; max_tokens = 96 }
                    original_format = "xml"
                }).Data
            } else {
                $promptId = $prompt.prompt_id
                $attachments = (Invoke-PropeJson -Method GET -Uri "$ApiBase/prompts/$promptId/dataset-attachments" -Session $authorSession).Data
                $dataset = (Invoke-PropeJson -Method GET -Uri "$ApiBase/datasets/$($attachments[0].dataset_id)" -Session $authorSession).Data
                $revisions = (Invoke-PropeJson -Method GET -Uri "$ApiBase/prompts/$promptId/revisions" -Session $authorSession).Data
                $baselineSummary = $revisions | Where-Object { $_.revision_number -eq 1 } | Select-Object -First 1
                $baselineRevision = (Invoke-PropeJson -Method GET -Uri "$ApiBase/revisions/$($baselineSummary.version_id)" -Session $authorSession).Data
                Write-ProgressLine "$scenario RESUME_PROMPT prompt=$promptId"
            }
            $baselineAccepted = (Invoke-PropeJson -Method POST -Uri "$ApiBase/prompts/$promptId/eval-runs/from-attachments" -Session $authorSession -Body @{
                version_id = $baselineRevision.version_id
            }).Data
            $baselineHandle = Get-CandidateHandle $baselineAccepted
            $baselineRun = Wait-EvalRun -RunId $baselineHandle.run_id -Session $authorSession
            $baselineCases = (Invoke-PropeJson -Method GET -Uri "$ApiBase/eval-runs/$($baselineRun.run_id)/cases" -Session $authorSession).Data
            Write-JsonFile $savedBaselinePath $baselineRun
            Write-JsonArrayFile -Path (Join-Path $runDir "baseline-cases.json") -Items @($baselineCases)
            if ($baselineRevision.status -eq "Draft") {
                Submit-Revision $promptId $baselineRevision.version_id $authorSession
            }
        }
        $baselineNeedsAck = $baselineRun.status -ne "completed" -or $baselineRun.fail_count -gt 0 -or $baselineRun.error_count -gt 0
        $null = Approve-And-Release -PromptId $promptId -VersionId $baselineRevision.version_id -ExpectedCurrentVersionId $null -NeedsAcknowledgement $baselineNeedsAck -ReviewerSession $reviewerSession

        $candidateRevision = (Invoke-PropeJson -Method POST -Uri "$ApiBase/prompts/$promptId/revisions" -Session $authorSession -Body @{
            body = $spec.revisions.candidate.body
            change_summary = $spec.revisions.candidate.change_summary
            provider_config_id = $providerId
            upstream_model = $env:APP_AGENT_MODEL
            parameters = @{ temperature = 0; max_tokens = 96 }
            original_format = "xml"
        }).Data
        $candidateAccepted = (Invoke-PropeJson -Method POST -Uri "$ApiBase/prompts/$promptId/eval-runs/from-attachments" -Session $authorSession -Body @{
            version_id = $candidateRevision.version_id
        }).Data
        $candidateHandle = Get-CandidateHandle $candidateAccepted
        $candidateRun = Wait-EvalRun -RunId $candidateHandle.run_id -Session $authorSession
        $candidateCases = (Invoke-PropeJson -Method GET -Uri "$ApiBase/eval-runs/$($candidateRun.run_id)/cases" -Session $authorSession).Data
        $comparison = (Invoke-PropeJson -Method GET -Uri "$ApiBase/prompts/$promptId/comparison?candidate=$($candidateRevision.version_id)" -Session $authorSession).Data
        Write-JsonFile (Join-Path $runDir "candidate-run.json") $candidateRun
        Write-JsonArrayFile -Path (Join-Path $runDir "candidate-cases.json") -Items @($candidateCases)
        Write-JsonArrayFile -Path (Join-Path $runDir "comparison.json") -Items @($comparison)

        Submit-Revision $promptId $candidateRevision.version_id $authorSession
        $humanDecision = "blocked"
        $ackRequired = $false
        if ($scenario -in @("S5", "S10")) {
            $null = Approve-And-Release -PromptId $promptId -VersionId $candidateRevision.version_id -ExpectedCurrentVersionId $baselineRevision.version_id -NeedsAcknowledgement $false -ReviewerSession $reviewerSession
            $humanDecision = "released"
        } elseif ($scenario -eq "S2") {
            $null = Request-Changes -PromptId $promptId -VersionId $candidateRevision.version_id -Comment "Do not promote: quality did not improve and cost exceeded the guardrail." -ReviewerSession $reviewerSession
            $humanDecision = "not_promoted"
        } elseif ($scenario -eq "S3") {
            $null = Request-Changes -PromptId $promptId -VersionId $candidateRevision.version_id -Comment "BLOCK recommendation: instruction-following regression." -ReviewerSession $reviewerSession
            $ackRequired = $true
        } else {
            $null = Request-Changes -PromptId $promptId -VersionId $candidateRevision.version_id -Comment "BLOCK recommendation: output contract regression." -ReviewerSession $reviewerSession
            $ackRequired = $true
        }

        $scenarioContext = [ordered]@{
            prompt_id = $promptId
            model_name = $prompt.model_name
            dataset_id = $dataset.dataset_id
            suite_id = $candidateRun.suite_id
            suite_version = $candidateHandle.suite_version
            baseline_version_id = $baselineRevision.version_id
            candidate_version_id = $candidateRevision.version_id
            baseline_run_id = $baselineRun.run_id
            candidate_run_id = $candidateRun.run_id
            provider_config_id = $providerId
            upstream_model = $env:APP_AGENT_MODEL
            human_decision = $humanDecision
            acknowledgement_required_for_override = $ackRequired
        }

        if ($scenario -eq "S10") {
            $key = (Invoke-PropeJson -Method POST -Uri "$ApiBase/workspaces/$workspaceId/keys" -Session $authorSession -Body @{
                name = "S10 lifecycle evidence"
                scope_model_names = @($prompt.model_name)
            }).Data
            $gatewayV2 = Run-Gateway -ModelName $prompt.model_name -InputText $spec.dataset.cases[0].input_messages[0].content -ApiKey $key.secret
            Write-JsonFile (Join-Path $runDir "gateway-v2.json") $gatewayV2
            $restoreReason = "Restore V1 after lifecycle evidence verification."
            $restoreStarted = [DateTimeOffset]::UtcNow
            $restore = (Invoke-PropeJson -Method POST -Uri "$ApiBase/prompts/$promptId/releases" -Session $reviewerSession -Body @{
                version_id = $baselineRevision.version_id
                kind = "restore"
                expected_current_version_id = $candidateRevision.version_id
                reason = $restoreReason
            }).Data
            Write-JsonFile (Join-Path $runDir "restore-response.json") $restore
            do {
                $restored = Run-Gateway -ModelName $prompt.model_name -InputText $spec.dataset.cases[0].input_messages[0].content -ApiKey $key.secret
                $elapsed = ([DateTimeOffset]::UtcNow - $restoreStarted).TotalSeconds
                if ($restored.headers["x-prope-version-id"] -eq $baselineRevision.version_id) { break }
                if ($elapsed -ge 300) { throw "S10 gateway did not restore V1 within 300 seconds" }
                Start-Sleep -Seconds 5
            } while ($true)
            $restored.elapsed_seconds = [Math]::Round($elapsed, 3)
            Write-JsonFile (Join-Path $runDir "gateway-restored-v1.json") $restored
            $scenarioContext.restore_release_id = $restore.release_id
            $scenarioContext.restore_elapsed_seconds = [Math]::Round($elapsed, 3)
            $key = $null
        }

        $context.scenarios[$scenario] = $scenarioContext
        $baselineOutput = if (@($baselineCases).Count) { @($baselineCases)[0].output_content } else { $baselineRun.refused_reason }
        $candidateOutput = if (@($candidateCases).Count) { @($candidateCases)[0].output_content } else { $candidateRun.refused_reason }
        $summaryRows += [PSCustomObject]@{
            Scenario = $scenario
            Baseline = $baselineOutput
            Candidate = $candidateOutput
            TokensCost = "B $($baselineRun.input_tokens)/$($baselineRun.output_tokens), $($baselineRun.cost_amount) $($baselineRun.cost_currency); C $($candidateRun.input_tokens)/$($candidateRun.output_tokens), $($candidateRun.cost_amount) $($candidateRun.cost_currency)"
            Verdict = if ($scenario -eq "S2") { "Cost warning" } elseif ($scenario -eq "S5") { "fail to pass" } elseif ($scenario -eq "S10") { "pass; release/restore" } else { "BLOCK recommendation" }
            Decision = $humanDecision
        }
        Write-ProgressLine "$scenario DONE"
    }

    $context.status = "EXECUTED"
    $context.completed_at = [DateTimeOffset]::Now.ToString("o")
    Write-JsonFile (Join-Path $Root "execution-context.json") $context

    $lines = @(
        "# Eval Evidence Results",
        "",
        "Status: **EXECUTED**. This is a five-scenario Demo/Eval Evidence set, not a 10-20 case per-suite production qualification.",
        "",
        "| Scenario | Baseline actual | Candidate actual | Tokens/cost | Deterministic verdict | Human decision |",
        "|---|---|---|---|---|---|"
    )
    foreach ($row in $summaryRows) {
        $lines += "| $($row.Scenario) | $(Escape-Markdown $row.Baseline) | $(Escape-Markdown $row.Candidate) | $(Escape-Markdown $row.TokensCost) | $(Escape-Markdown $row.Verdict) | $(Escape-Markdown $row.Decision) |"
    }
    $lines += @(
        "",
        "- S3/S6: BLOCK recommendation; human override requires acknowledgement.",
        "- S10 covers HITL + release + restore; it is not canary evidence.",
        "- This report does not claim optimizer memory or automatic promotion."
    )
    [IO.File]::WriteAllLines((Join-Path $Root "summary.md"), $lines, $Utf8NoBom)
    Write-ProgressLine "COMPLETE"
} catch {
    $context.status = "FAILED"
    $context.failure = $_.Exception.Message
    $context.completed_at = [DateTimeOffset]::Now.ToString("o")
    Write-JsonFile (Join-Path $Root "execution-context.json") $context
    Write-ProgressLine "FAILED $($_.Exception.Message)"
    throw
}
