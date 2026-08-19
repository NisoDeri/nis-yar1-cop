#Requires -Version 5.1
<#
.SYNOPSIS
    Start the bestteam friendly or counted series in visible live-progress terminals.

.EXAMPLE
    .\scripts\start-bestteam-series.ps1 -Mode friendly
    .\scripts\start-bestteam-series.ps1 -Mode counted
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("friendly", "counted")]
    [string]$Mode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$policeConfig = Join-Path $repoRoot "config\bestteam_police"
$thiefConfig = Join-Path $repoRoot "config\bestteam_thief"
$reposRoot = Split-Path -Parent $repoRoot
$copRepo = Join-Path $reposRoot "nis-yar1-cop"
$thiefRepo = Join-Path $reposRoot "nis-yar1-thief"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found: $python"
}

$configFiles = @(
    (Join-Path $policeConfig "game.toml"),
    (Join-Path $thiefConfig "game.toml")
)
foreach ($configFile in $configFiles) {
    if (Select-String -LiteralPath $configFile -Pattern "replace-before-start" -Quiet) {
        throw "Live MCP URLs are still placeholders in $configFile. Open both tunnels and update both mcp_servers values before launch."
    }
}

function Assert-PublishedRoleRepo {
    param([string]$RoleRepo)

    if (-not (Test-Path -LiteralPath (Join-Path $RoleRepo ".git") -PathType Container)) {
        throw "Declared role repository is missing: $RoleRepo"
    }
    $head = (& git -c "safe.directory=$($RoleRepo.Replace('\', '/'))" -C $RoleRepo rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -notmatch '^[0-9a-f]{40}$') {
        throw "Cannot resolve role repository HEAD: $RoleRepo"
    }
    $dirty = & git -c "safe.directory=$($RoleRepo.Replace('\', '/'))" -C $RoleRepo status --porcelain
    if ($dirty) {
        throw "Role repository is dirty and cannot be declared: $RoleRepo"
    }
    $published = & git -c "safe.directory=$($RoleRepo.Replace('\', '/'))" -C $RoleRepo branch -r --contains $head
    if (-not $published) {
        throw "Role repository HEAD is not present on a remote branch: $RoleRepo ($head)"
    }
    return $head
}

$copHead = Assert-PublishedRoleRepo -RoleRepo $copRepo
$thiefHead = Assert-PublishedRoleRepo -RoleRepo $thiefRepo

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logDir = Join-Path $repoRoot ".tunnels\bestteam-$Mode-$stamp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function New-PeerCommand {
    param(
        [string]$Role,
        [string]$ConfigDir,
        [string]$LogFile
    )

    $roleRepo = Join-Path $reposRoot "nis-yar1-$Role"
    $roleSource = Join-Path $roleRepo "src"
    if (-not (Test-Path -LiteralPath $roleSource -PathType Container)) {
        throw "Declared role repository is missing: $roleRepo"
    }

    return @"
`$Host.UI.RawUI.WindowTitle = 'nis-yar1 vs bestteam | $Mode | $Role LIVE'
Set-Location '$repoRoot'
`$env:PYTHONUTF8 = '1'
`$env:PYTHONUNBUFFERED = '1'
`$env:PYTHONPATH = '$roleSource'
Write-Host 'LIVE: nis-yar1 vs bestteam | mode=$Mode | role=$Role' -ForegroundColor Cyan
Write-Host 'Do not close this window until all six sub-games and audits finish.' -ForegroundColor Yellow
Write-Host 'Log: $LogFile' -ForegroundColor DarkGray
& '$python' -m pursuit peer --role $Role --config-dir '$ConfigDir' --games 3 --fixed-role --scent-dialect reference --mode $Mode --series-gate-dir '$gateDir' --series-gate-timeout 1800 2>&1 | Tee-Object -FilePath '$LogFile' -Append
Write-Host "Peer exited with code `$LASTEXITCODE. Keep this window open for review." -ForegroundColor Yellow
"@
}

$thiefLog = Join-Path $logDir "thief-live.log"
$policeLog = Join-Path $logDir "police-live.log"
$gateDir = Join-Path $logDir "series-gate"
New-Item -ItemType Directory -Force -Path $gateDir | Out-Null
$thiefCommand = New-PeerCommand -Role "thief" -ConfigDir $thiefConfig -LogFile $thiefLog
$policeCommand = New-PeerCommand -Role "police" -ConfigDir $policeConfig -LogFile $policeLog

Write-Host "Starting visible live-progress terminals..." -ForegroundColor Cyan
Write-Host "Cop code commit:   $copHead" -ForegroundColor DarkGray
Write-Host "Thief code commit: $thiefHead" -ForegroundColor DarkGray
$thiefProcess = Start-Process -FilePath "powershell.exe" `
    -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $thiefCommand) `
    -WorkingDirectory $repoRoot `
    -WindowStyle Normal `
    -PassThru
Start-Sleep -Milliseconds 750
$policeProcess = Start-Process -FilePath "powershell.exe" `
    -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $policeCommand) `
    -WorkingDirectory $repoRoot `
    -WindowStyle Normal `
    -PassThru

Write-Host "Thief terminal PID: $($thiefProcess.Id)" -ForegroundColor Green
Write-Host "Police terminal PID: $($policeProcess.Id)" -ForegroundColor Green
Write-Host "Live logs: $logDir" -ForegroundColor Green
