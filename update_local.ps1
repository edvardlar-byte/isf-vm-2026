# Local fallback for running the morning update on this Windows PC instead of
# (or in addition to) the GitHub Action. Schedule it with Task Scheduler:
#
#   Program/script:  powershell.exe
#   Arguments:       -ExecutionPolicy Bypass -File "C:\Claude Access\ISF World Cup Predictions Project\update_local.ps1"
#   Trigger:         Daily, 07:30
#
# It runs the pipeline and (if this folder is a git repo) commits & pushes so
# GitHub Pages updates. Set your API token once for your user account with:
#   setx FOOTBALL_DATA_TOKEN "your-token-here"

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

python run_update.py

if (Test-Path ".git") {
    git add data docs
    git commit -m "Update standings" 2>$null
    git push 2>$null
    Write-Host "Pushed to GitHub."
} else {
    Write-Host "Not a git repo yet — site files are in docs\. See README to publish."
}
