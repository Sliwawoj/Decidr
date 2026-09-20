# Start ngrok HTTPS tunnel to Decidr (localhost:5173), sync .env, recreate backend.
# Prerequisites: ngrok on PATH, authtoken configured, `docker compose up` already running.
# Usage:  .\scripts\ngrok-tunnel.ps1
# Auth:   ngrok config add-authtoken <TOKEN>   # from https://dashboard.ngrok.com/get-started/your-authtoken

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Get-NgrokPublicUrl {
  try {
    $payload = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
    $https = $payload.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
    return $https.public_url
  } catch {
    return $null
  }
}

$ngrokCmd = "$env:LOCALAPPDATA\Programs\ngrok\ngrok.exe"
if (-not (Test-Path $ngrokCmd)) {
  $ngrokCmd = (Get-Command ngrok -ErrorAction SilentlyContinue)?.Source
}
if (-not $ngrokCmd) {
  throw "ngrok not found. Download from https://ngrok.com/download (need 3.20+)."
}

$existing = Get-NgrokPublicUrl
if (-not $existing) {
  Start-Process -FilePath $ngrokCmd -ArgumentList @("http", "127.0.0.1:5173", "--log=stdout") -WindowStyle Minimized
  Write-Host "Starting ngrok..."
  for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $existing = Get-NgrokPublicUrl
    if ($existing) { break }
  }
}

if (-not $existing) {
  throw "Could not read ngrok public URL from http://127.0.0.1:4040. Check authtoken: ngrok config add-authtoken <TOKEN>"
}

$envPath = Join-Path $root ".env"
if (-not (Test-Path $envPath)) {
  Copy-Item (Join-Path $root ".env.example") $envPath
}

$content = Get-Content $envPath -Raw
function Set-EnvLine([string]$text, [string]$key, [string]$value) {
  $line = "$key=$value"
  if ($text -match "(?m)^$key=") {
    return [regex]::Replace($text, "(?m)^$key=.*$", $line)
  }
  return $text.TrimEnd() + "`r`n$line`r`n"
}

$content = Set-EnvLine $content "FRONTEND_URL" $existing
$content = Set-EnvLine $content "GOOGLE_REDIRECT_URI" "$existing/api/oauth/gmail/callback"
# Leave COOKIE_SECURE alone — true breaks session cookies on http://localhost.
Set-Content -Path $envPath -Value $content -NoNewline

Write-Host "FRONTEND_URL=$existing"
Write-Host "Recreating backend so it picks up .env..."
docker compose up -d --force-recreate backend

Write-Host ""
Write-Host "Open on phone: $existing"
Write-Host "Local dashboard: http://127.0.0.1:4040"
Write-Host "Gmail OAuth: add redirect URI $existing/api/oauth/gmail/callback in Google Cloud."
Write-Host "To stop tunnel: close the ngrok window or Stop-Process -Name ngrok"
