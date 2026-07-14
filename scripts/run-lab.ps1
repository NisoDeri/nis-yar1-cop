#Requires -Version 5.1
<#
.SYNOPSIS
    Run the self-play lab: best brains vs greedy baseline.

.DESCRIPTION
    Runs 200 games (seed 42) with InterceptorPoliceBrain vs SurvivorThiefBrain
    and prints a summary of results to the console.

.EXAMPLE
    ./scripts/run-lab.ps1
    ./scripts/run-lab.ps1 -Games 50
#>

param(
    [int]$Games = 200,
    [int]$Seed  = 42,
    [string]$PoliceBrain = "pursuit.strategy.police:InterceptorPoliceBrain",
    [string]$ThiefBrain  = "pursuit.strategy.thief:SurvivorThiefBrain"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "Self-Play Lab" -ForegroundColor Cyan
Write-Host "  Games : $Games" -ForegroundColor Gray
Write-Host "  Seed  : $Seed"  -ForegroundColor Gray
Write-Host "  Police: $PoliceBrain" -ForegroundColor Blue
Write-Host "  Thief : $ThiefBrain"  -ForegroundColor Red
Write-Host ""

$cmd = "uv run python -m pursuit lab --games $Games --seed $Seed --police $PoliceBrain --thief $ThiefBrain"
Write-Host "Running: $cmd" -ForegroundColor Yellow
Write-Host ""

Push-Location $repoRoot
try {
    $env:PYTHONUTF8 = "1"
    $env:PYTHONPATH = "src"
    & uv run python -m pursuit lab `
        --games $Games `
        --seed   $Seed `
        --police $PoliceBrain `
        --thief  $ThiefBrain
} finally {
    Pop-Location
}
