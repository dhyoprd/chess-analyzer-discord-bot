# PROTOTYPE — jalankan backend + Activity + tunnel.
#
# BUKAN skrip produksi. Menyalakan tiga hal sekaligus supaya pengujian di
# Discord tidak menuntut empat terminal manual.
#
# Pakai:
#   .\run-prototype.ps1                 # backend + Activity, tanpa tunnel
#   .\run-prototype.ps1 -Tunnel         # tambah cloudflared (untuk Discord)
#
# Tekan Ctrl+C sekali untuk mematikan semuanya.

param(
    [switch]$Tunnel,
    [switch]$NoBackend,
    [switch]$NoActivity
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Resolve-Path (Join-Path $here '..\..')
$backend = Join-Path $repo 'backend'
$activity = Join-Path $here 'activity\prototype'
$logs = Join-Path $here '.logs'

New-Item -ItemType Directory -Force -Path $logs | Out-Null

$procs = @()

function Start-Svc {
    param([string]$Name, [string]$WorkDir, [string[]]$Argv, [string]$Exe)

    $log = Join-Path $logs "$Name.log"
    Write-Host "  mulai $Name  ->  $log" -ForegroundColor Cyan

    $p = Start-Process -FilePath $Exe -ArgumentList $Argv `
        -WorkingDirectory $WorkDir -PassThru -NoNewWindow `
        -RedirectStandardOutput $log -RedirectStandardError "$log.err"
    $script:procs += $p
    return $p
}

Write-Host ""
Write-Host "PROTOTYPE — kerangka Activity catur" -ForegroundColor Yellow
Write-Host "===================================" -ForegroundColor Yellow
Write-Host ""

# ── backend ──────────────────────────────────────────────────────────────────
if (-not $NoBackend) {
    $venvPy = Join-Path $backend '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPy)) {
        Write-Host "Backend .venv belum ada. Jalankan dulu:" -ForegroundColor Red
        Write-Host "  cd backend; uv sync --all-extras" -ForegroundColor Red
        exit 1
    }
    # PYTHONPATH harus diset SEBELUM proses diluncurkan — Start-Process
    # mewarisi environment saat start, bukan sesudahnya.
    $env:PYTHONPATH = 'src'
    Start-Svc -Name 'backend' -WorkDir $backend -Exe $venvPy -Argv @(
        '-m', 'uvicorn', 'chessbot.prototype_activity:app',
        '--host', '127.0.0.1', '--port', '8000', '--reload'
    ) | Out-Null
}

# ── Activity ─────────────────────────────────────────────────────────────────
if (-not $NoActivity) {
    if (-not (Test-Path (Join-Path $activity 'node_modules'))) {
        Write-Host "node_modules belum ada. Jalankan dulu:" -ForegroundColor Red
        Write-Host "  cd activity\prototype; npm install" -ForegroundColor Red
        exit 1
    }
    # HMR harus menembak 443 saat lewat tunnel; 3000 saat lokal.
    if ($Tunnel) { $env:VITE_HMR_PORT = '443' } else { $env:VITE_HMR_PORT = '3000' }
    $npm = (Get-Command npm.cmd).Source
    Start-Svc -Name 'activity' -WorkDir $activity -Exe $npm -Argv @('run', 'dev') | Out-Null
}

# ── tunggu backend siap ──────────────────────────────────────────────────────
if (-not $NoBackend) {
    Write-Host "  menunggu backend siap..." -ForegroundColor DarkGray
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/sehat' -TimeoutSec 2 -UseBasicParsing
            if ($r.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if ($ready) {
        Write-Host "  backend siap: http://127.0.0.1:8000/api/sehat" -ForegroundColor Green
    } else {
        Write-Host "  backend belum menjawab — cek .logs\backend.log" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "UJI DI BROWSER (tanpa Discord):" -ForegroundColor Cyan
Write-Host "  http://localhost:3000/?debug=1&room=uji1&name=Putih"
Write-Host "  lalu buka jendela kedua dengan name=Hitam, room SAMA."
Write-Host "  Atau centang 'Lawan simulasi' untuk main sendiri."
Write-Host ""

# ── tunnel ───────────────────────────────────────────────────────────────────
if ($Tunnel) {
    $cf = Get-Command cloudflared -ErrorAction SilentlyContinue
    if (-not $cf) {
        Write-Host "cloudflared tidak ada di PATH." -ForegroundColor Red
        exit 1
    }
    $tlog = Join-Path $logs 'tunnel.log'
    Write-Host "  membuka tunnel ke http://localhost:3000" -ForegroundColor Cyan
    Write-Host "  (hostname butuh ~60-90 detik sebelum bisa di-resolve — ini normal)" -ForegroundColor DarkGray

    $tp = Start-Process -FilePath $cf.Source -ArgumentList @(
        'tunnel', '--url', 'http://localhost:3000'
    ) -PassThru -NoNewWindow -RedirectStandardOutput $tlog -RedirectStandardError "$tlog.err"
    $procs += $tp

    # Ambil hostname dari log — ia muncul sebagai https://xxx.trycloudflare.com
    $host_ = $null
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        $content = Get-Content $tlog -Raw -ErrorAction SilentlyContinue
        if ($content -match 'https://([a-z0-9-]+\.trycloudflare\.com)') {
            $host_ = $Matches[1]
            break
        }
    }

    Write-Host ""
    if ($host_) {
        Write-Host "  TUNNEL: https://$host_" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Langkah di Developer Portal (sekali per tunnel):" -ForegroundColor Yellow
        Write-Host "    Activities -> URL Mappings:"
        Write-Host "      PREFIX  /       TARGET  $host_"
        Write-Host "    (target TANPA protokol, dan harus direktori)"
        Write-Host ""
        Write-Host "  Lalu buka Activity dari Discord. URL berubah tiap restart tunnel." -ForegroundColor Yellow
    } else {
        Write-Host "  hostname tunnel belum terbaca — cek .logs\tunnel.log" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "Tekan Ctrl+C untuk mematikan semuanya." -ForegroundColor DarkGray
Write-Host ""

try {
    while ($true) {
        Start-Sleep -Seconds 1
        foreach ($p in $procs) {
            if ($p.HasExited) {
                Write-Host "  proses $($p.Id) berhenti (exit $($p.ExitCode))" -ForegroundColor Red
            }
        }
    }
} finally {
    Write-Host ""
    Write-Host "mematikan..." -ForegroundColor DarkGray
    foreach ($p in $procs) {
        if (-not $p.HasExited) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
