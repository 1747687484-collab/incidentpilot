param(
    [string]$ComposeProject = "incidentpilot",
    [string]$DbService = "postgres",
    [string]$RedisService = "redis",
    [string]$DbName = "incidentpilot",
    [string]$DbUser = "incidentpilot",
    [string]$SqlPath = ".\db\maintenance\reset_demo_data.sql",
    [switch]$FlushRedis,
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Resolve-ScriptPath {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return Join-Path (Get-Location) $Path
}

$resolvedSqlPath = Resolve-ScriptPath $SqlPath
if (-not (Test-Path $resolvedSqlPath)) {
    throw "SQL file not found: $resolvedSqlPath"
}

$sql = Get-Content -Raw -Encoding UTF8 $resolvedSqlPath

Write-Step "Reset target"
Write-Host "Compose project : $ComposeProject"
Write-Host "Database service: $DbService"
Write-Host "Database        : $DbName"
Write-Host "SQL file        : $resolvedSqlPath"
Write-Host "Flush Redis     : $FlushRedis"

if ($DryRun) {
    Write-Step "Dry run SQL"
    Write-Host $sql
    if ($FlushRedis) {
        Write-Step "Dry run Redis"
        Write-Host "docker compose -p $ComposeProject exec -T $RedisService redis-cli FLUSHDB"
    }
    exit 0
}

if (-not $Force) {
    Write-Host ""
    Write-Host "This will delete demo incidents, evidence, agent steps, reports, actions, faults, and tool audit rows." -ForegroundColor Yellow
    Write-Host "Knowledge documents and chunks will be kept."
    $answer = Read-Host "Type RESET to continue"
    if ($answer -ne "RESET") {
        Write-Host "Canceled."
        exit 0
    }
}

Write-Step "Apply database reset"
$sql | docker compose -p $ComposeProject exec -T $DbService psql -U $DbUser -d $DbName -v ON_ERROR_STOP=1

if ($FlushRedis) {
    Write-Step "Flush Redis demo cache"
    docker compose -p $ComposeProject exec -T $RedisService redis-cli FLUSHDB
}

Write-Step "Done"
Write-Host "Demo runtime data has been reset. Seed and uploaded Runbooks are still available."
