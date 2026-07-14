#Requires -Version 5.1
<#
.SYNOPSIS
    Run a local Cops & Robbers game for testing.

.DESCRIPTION
    --fake   Single-process demo using fake-opponent mode (default).
    --local  Two PowerShell windows on 127.0.0.1 (ports 8801 / 8802).

.EXAMPLE
    ./scripts/run-game.ps1
    ./scripts/run-game.ps1 --fake
    ./scripts/run-game.ps1 --local
#>

param(
    [switch]$fake,
    [switch]$local
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Default to --fake if no flag given
if (-not $fake -and -not $local) { $fake = $true }

# Check Ollama
Write-Host "Checking Ollama..." -ForegroundColor Cyan
try {
    $null = & ollama list 2>&1
    Write-Host "  Ollama is running." -ForegroundColor Green
} catch {
    Write-Warning "Ollama does not appear to be running (ollama list failed). AI brains may fail."
}

# Resolve repo root (parent of scripts/)
$repoRoot = Split-Path -Parent $PSScriptRoot

if ($fake) {
    Write-Host ""
    Write-Host "Mode: FAKE-OPPONENT (single process)" -ForegroundColor Yellow
    $cmd = "PYTHONUTF8=1 PYTHONPATH=src uv run python -m pursuit peer --role police --fake-opponent"
    Write-Host "Running: $cmd" -ForegroundColor Cyan
    Write-Host ""
    Push-Location $repoRoot
    try {
        $env:PYTHONUTF8 = "1"
        $env:PYTHONPATH = "src"
        & uv run python -m pursuit peer --role police --fake-opponent
    } finally {
        Pop-Location
    }
}
elseif ($local) {
    Write-Host ""
    Write-Host "Mode: LOCAL (two windows, 127.0.0.1 ports 8801 / 8802)" -ForegroundColor Yellow
    Write-Host "Starting police peer on port 8801 ..." -ForegroundColor Cyan

    $policeCmd = @"
Set-Location '$repoRoot'
`$env:PYTHONUTF8 = '1'
`$env:PYTHONPATH = 'src'
Write-Host 'Police peer starting on 127.0.0.1:8801' -ForegroundColor Green
uv run python -m pursuit peer --role police --host 127.0.0.1 --port 8801 --peer-host 127.0.0.1 --peer-port 8802
Read-Host 'Press Enter to close'
"@

    $thiefCmd = @"
Set-Location '$repoRoot'
`$env:PYTHONUTF8 = '1'
`$env:PYTHONPATH = 'src'
Write-Host 'Thief peer starting on 127.0.0.1:8802' -ForegroundColor Red
Start-Sleep -Seconds 2
uv run python -m pursuit peer --role thief --host 127.0.0.1 --port 8802 --peer-host 127.0.0.1 --peer-port 8801
Read-Host 'Press Enter to close'
"@

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $policeCmd
    Start-Sleep -Milliseconds 500
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $thiefCmd

    Write-Host "Two PowerShell windows launched." -ForegroundColor Green
    Write-Host "Police: 127.0.0.1:8801   Thief: 127.0.0.1:8802" -ForegroundColor Cyan
}
