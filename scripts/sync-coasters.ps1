# sync-coasters.ps1
# Copies updated profile JSONs from coaster-data submodule into data/coasters/,
# commits, and pushes. Run this after logging credits in the coaster tracker.
#
# Usage (from jt630.github.io root):
#   .\scripts\sync-coasters.ps1
#   .\scripts\sync-coasters.ps1 -DryRun       # preview only, no git ops

param([switch]$DryRun)

$root   = Split-Path $PSScriptRoot -Parent
$src    = Join-Path $root "coaster-data\profiles"
$dst    = Join-Path $root "data\coasters"

Write-Host "`nCoaster sync" -ForegroundColor Cyan

# Pull latest submodule commit
Write-Host "Updating submodule..." -ForegroundColor Gray
git -C $root submodule update --remote coaster-data

# Copy profiles
foreach ($file in @("jay.json", "kay.json")) {
    $from = Join-Path $src $file
    $to   = Join-Path $dst $file
    if (Test-Path $from) {
        if ($DryRun) {
            Write-Host "  [dry-run] would copy $file" -ForegroundColor Yellow
        } else {
            Copy-Item $from $to -Force
            Write-Host "  copied $file" -ForegroundColor Green
        }
    } else {
        Write-Host "  WARNING: $from not found" -ForegroundColor Red
    }
}

if ($DryRun) {
    Write-Host "`nDry run complete — no changes made." -ForegroundColor Yellow
    exit 0
}

# Check if anything changed
$changed = git -C $root status --porcelain data/coasters/
if (-not $changed) {
    Write-Host "`nNo profile changes detected — nothing to commit." -ForegroundColor Yellow
    exit 0
}

# Commit and push on current branch
$branch = git -C $root rev-parse --abbrev-ref HEAD
Write-Host "`nCommitting on branch: $branch" -ForegroundColor Gray

git -C $root add data/coasters/jay.json data/coasters/kay.json
git -C $root commit -m "sync: update coaster profiles from tracker"
git -C $root push

Write-Host "`nDone — GitHub Actions will rebuild the site." -ForegroundColor Cyan
