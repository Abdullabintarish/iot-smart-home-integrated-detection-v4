# Capture one full-page screenshot per demo page (needs demo\.venv with streamlit).
#
#   powershell -ExecutionPolicy Bypass -File tools\capture_screenshots.ps1 [-Port 8599] [-CdpPort 9222]
#
# Starts its own Streamlit server (headless, localhost) and its own headless
# Edge with a DevTools port, then runs tools\cdp_screenshot.py, which waits
# until each page has rendered real content (plain "msedge --screenshot" only
# captures Streamlit's loading skeleton). Writes PNGs to demo\screenshots\ and
# afterwards stops only the two process trees this script started.
param([int]$Port = 8599, [int]$CdpPort = 9222,
      [string]$Edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

$ErrorActionPreference = "Continue"
$Demo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Py = Join-Path $Demo ".venv\Scripts\python.exe"
$EdgeProfile = Join-Path $env:TEMP "thesis_demo_edge_profile_$CdpPort"   # throwaway, outside the project

foreach ($p in @($Port, $CdpPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue) {
        Write-Host "port $p is already in use; stop that process or pass another port" -ForegroundColor Red
        exit 2
    }
}

function Wait-Url([string]$u, [int]$tries) {
    # Python urllib, not Invoke-WebRequest: the latter stalled on localhost
    # (system proxy / name resolution) under Windows PowerShell 5.1.
    $probe = "import sys, urllib.request as u; u.urlopen(sys.argv[1], timeout=2)"
    for ($i = 0; $i -lt $tries; $i++) {
        & $Py -c $probe $u 2>$null
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

$st = $null; $br = $null
try {
    $stArgs = @("-m", "streamlit", "run", "app.py", "--server.headless", "true",
                "--server.port", "$Port", "--server.address", "localhost")
    $st = Start-Process -FilePath $Py -ArgumentList $stArgs -WorkingDirectory $Demo `
          -WindowStyle Hidden -PassThru
    if (-not (Wait-Url "http://127.0.0.1:$Port/_stcore/health" 120)) { throw "streamlit did not start" }

    $edgeArgs = @("--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                  "--remote-debugging-port=$CdpPort", "--user-data-dir=$EdgeProfile", "about:blank")
    $br = Start-Process -FilePath $Edge -ArgumentList $edgeArgs -WindowStyle Hidden -PassThru
    if (-not (Wait-Url "http://127.0.0.1:$CdpPort/json/version" 60)) { throw "Edge DevTools did not start" }

    Push-Location $Demo
    $env:CDP_PORT = "$CdpPort"
    & $Py -B tools\cdp_screenshot.py screenshots "http://localhost:$Port" `
        "/=1_overview" "replay=2_replay" "correlation=3_correlation" `
        "detection=4_detection" "evidence=5_evidence"
    Pop-Location
} finally {
    # Only the trees started above (/T: their child processes too).
    foreach ($p in @($br, $st)) {
        if ($p -and -not $p.HasExited) { & taskkill.exe /PID $p.Id /T /F | Out-Null }
    }
}
