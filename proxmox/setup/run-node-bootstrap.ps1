#requires -Version 3
# One-time Proxmox node bootstrap runner (Windows / PowerShell).
# Sends proxmox/setup/node-bootstrap.sh to the node over SSH and runs it there
# (creates cloud-init snippets + the golden Ubuntu template 9000).
# You will be prompted for the node's root password once.
#
# Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File proxmox\setup\run-node-bootstrap.ps1
$ErrorActionPreference = 'Stop'

$node      = 'root@proxmox.flamingo-banjo.ts.net'
$bootstrap = Join-Path $PSScriptRoot 'node-bootstrap.sh'
$envFile   = Join-Path $PSScriptRoot '..\.env'

if (-not (Test-Path $bootstrap)) { throw "Missing $bootstrap" }
if (-not (Test-Path $envFile))   { throw "Missing $envFile (copy .env.example to .env)" }

# Pull TS_AUTHKEY from .env (kept out of this script so it stays commit-safe).
$line = Select-String -Path $envFile -Pattern '^\s*TS_AUTHKEY\s*=' | Select-Object -First 1
if (-not $line) { throw "TS_AUTHKEY not set in $envFile" }
$tsKey = ($line.Line -split '=', 2)[1].Trim().Trim('"').Trim("'")
if ([string]::IsNullOrWhiteSpace($tsKey)) { throw "TS_AUTHKEY is empty in $envFile" }

# Base64-encode the script (force LF) so quoting/newlines survive the trip intact.
$text   = (Get-Content -Raw $bootstrap) -replace "`r`n", "`n" -replace "`r", "`n"
$b64    = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($text))
$remote = "echo '$b64' | base64 -d | TS_AUTHKEY='$tsKey' bash"

Write-Host "==> Bootstrapping $node (enter the root password when prompted)..." -ForegroundColor Cyan
ssh -o StrictHostKeyChecking=accept-new $node $remote
$code = $LASTEXITCODE
if ($code -ne 0) { Write-Host "ssh exited with code $code" -ForegroundColor Red }
exit $code
