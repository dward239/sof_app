<#
.SYNOPSIS
  Offline posture check: hash + flag ONLY external endpoints (non-loopback).
#>
param(
  [Parameter(Mandatory=$true)][string]$ExePath,
  [string]$OutDir = "$(Split-Path -Parent $ExePath)\..",
  [int]$WaitSeconds = 6
)

$ErrorActionPreference = "Stop"
$exe = Resolve-Path $ExePath
if (-not (Test-Path $OutDir)) { New-Item -Type Directory -Force $OutDir | Out-Null }
$out = Resolve-Path $OutDir

# Hash
Get-FileHash $exe -Algorithm SHA256 | Tee-Object -FilePath (Join-Path $out "SOF-Calculator.sha256.txt") | Out-Null

# Launch briefly
$p = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds $WaitSeconds

# Gather
$tcp_all = Get-NetTCPConnection -OwningProcess $p.Id -ErrorAction SilentlyContinue
$udp_all = Get-NetUDPEndpoint  -OwningProcess $p.Id -ErrorAction SilentlyContinue

Stop-Process -Id $p.Id -ErrorAction SilentlyContinue

# External-only filters
$loopbacks = @('127.0.0.1','::1')
$tcp_external = $tcp_all | Where-Object {
  $_.State -eq 'Established' -and
  $_.RemoteAddress -and
  $_.RemoteAddress -notin $loopbacks -and
  $_.RemoteAddress -ne '0.0.0.0'
}
$udp_external = $udp_all | Where-Object {
  $_.LocalAddress -and
  $_.LocalAddress -notin ($loopbacks + @('0.0.0.0','::'))
}

$report = [pscustomobject]@{
  exe = $exe.Path
  timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
  summary = [pscustomobject]@{
    tcp_external_established_count = @($tcp_external).Count
    udp_external_bound_count       = @($udp_external).Count
    note = "Loopback-only/unspecified-local bindings allowed; only external endpoints are flagged."
  }
  tcp_external_established = $tcp_external | Select LocalAddress,LocalPort,RemoteAddress,RemotePort,State
  udp_external_bound       = $udp_external | Select LocalAddress,LocalPort
  tcp_all                  = $tcp_all | Select LocalAddress,LocalPort,RemoteAddress,RemotePort,State
  udp_all                  = $udp_all | Select LocalAddress,LocalPort
}

$report | ConvertTo-Json -Depth 6 | Out-File (Join-Path $out "runtime_offline_report.json") -Encoding utf8

# hard fail if any external endpoint seen
if (@($tcp_external).Count -gt 0 -or @($udp_external).Count -gt 0) {
  Write-Error "External network endpoints detected. See runtime_offline_report.json."
  exit 1
} else {
  Write-Host "Offline posture OK (no external endpoints)."
  exit 0
}
