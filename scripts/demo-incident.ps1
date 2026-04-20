param(
    [string]$ApiBase = "http://localhost:8080",
    [ValidateSet("order", "payment", "inventory")]
    [string]$Service = "order",
    [string]$FaultType = "cache_stampede",
    [ValidateRange(1, 100)]
    [int]$Intensity = 82,
    [string]$Severity = "SEV2",
    [string]$Symptom = "Order checkout latency is rising and users report intermittent failures.",
    [int]$PollSeconds = 45,
    [switch]$ApproveAction,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function ConvertTo-JsonBody {
    param([hashtable]$Body)
    return ($Body | ConvertTo-Json -Depth 8 -Compress)
}

function Invoke-IncidentPilotApi {
    param(
        [ValidateSet("GET", "POST")]
        [string]$Method,
        [string]$Path,
        [hashtable]$Body,
        [hashtable]$Headers = @{}
    )

    $uri = "$ApiBase$Path"
    if ($DryRun) {
        Write-Host "$Method $uri"
        if ($Body) {
            Write-Host (ConvertTo-JsonBody $Body)
        }
        return $null
    }

    if ($Body) {
        return Invoke-RestMethod -Method $Method -Uri $uri -Headers $Headers -ContentType "application/json" -Body (ConvertTo-JsonBody $Body)
    }
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $Headers
}

Write-Step "Check API health"
Invoke-IncidentPilotApi -Method GET -Path "/api/healthz" | Out-Host

Write-Step "List indexed runbooks"
Invoke-IncidentPilotApi -Method GET -Path "/api/knowledge/documents?limit=5" | ConvertTo-Json -Depth 8 | Out-Host

Write-Step "Inject simulated fault"
$fault = Invoke-IncidentPilotApi -Method POST -Path "/api/simulations/faults" -Body @{
    service = $Service
    fault_type = $FaultType
    intensity = $Intensity
    details = @{}
}
$fault | ConvertTo-Json -Depth 8 | Out-Host

Write-Step "Create incident"
$headers = @{ "Idempotency-Key" = [guid]::NewGuid().ToString() }
$detail = Invoke-IncidentPilotApi -Method POST -Path "/api/incidents" -Headers $headers -Body @{
    service = $Service
    symptom = $Symptom
    severity = $Severity
}
$detail | ConvertTo-Json -Depth 10 | Out-Host

if ($DryRun) {
    Write-Step "Dry run complete"
    Write-Host "Run without -DryRun after docker compose is ready."
    exit 0
}

$incidentId = $detail.incident.id
if (-not $incidentId) {
    throw "Incident response did not include incident.id"
}

Write-Step "Poll incident until report or timeout"
$deadline = (Get-Date).AddSeconds($PollSeconds)
do {
    Start-Sleep -Seconds 3
    $detail = Invoke-IncidentPilotApi -Method GET -Path "/api/incidents/$incidentId"
    $status = $detail.incident.status
    $evidenceCount = @($detail.evidence).Count
    $stepCount = @($detail.steps).Count
    Write-Host ("status={0} evidence={1} steps={2}" -f $status, $evidenceCount, $stepCount)
} while (-not $detail.report -and (Get-Date) -lt $deadline)

if ($detail.report) {
    Write-Step "Root cause report"
    $detail.report | ConvertTo-Json -Depth 10 | Out-Host
} else {
    Write-Host "Report is not ready yet. You can keep watching the dashboard or rerun GET /api/incidents/$incidentId." -ForegroundColor Yellow
}

$pendingActions = @($detail.actions | Where-Object { $_.status -eq "pending_approval" })
if ($ApproveAction -and $pendingActions.Count -gt 0) {
    Write-Step "Approve first pending action"
    $approved = Invoke-IncidentPilotApi -Method POST -Path "/api/incidents/$incidentId/approve-action" -Body @{
        action_id = $pendingActions[0].id
        operator = "powershell-demo"
    }
    $approved | ConvertTo-Json -Depth 10 | Out-Host
} elseif ($pendingActions.Count -gt 0) {
    Write-Step "Pending action"
    Write-Host "Use -ApproveAction to approve the first pending action from this script."
    $pendingActions | ConvertTo-Json -Depth 10 | Out-Host
} else {
    Write-Step "No pending action"
}

Write-Step "Recent incidents"
Invoke-IncidentPilotApi -Method GET -Path "/api/incidents?limit=6&service=$Service" | ConvertTo-Json -Depth 8 | Out-Host
