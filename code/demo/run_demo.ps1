# Research Demonstration Lab - launcher (Windows PowerShell 5.1).
#
#   powershell -ExecutionPolicy Bypass -File run_demo.ps1 [-Port 8501]
#
# Uses demo\.venv\Scripts\python.exe directly (nothing is activated), checks
# that the verified evidence exists, builds the derived cache (demo\cache)
# if it is missing or stale, then starts Streamlit on localhost and opens the
# browser. Streamlit runs headless on purpose: in non-headless mode it asks
# for an e-mail address on first start and writes ~\.streamlit\credentials.toml;
# headless mode avoids both, and this script opens the browser itself once the
# server answers. Stop with Ctrl+C.
param([int]$Port = 8501)

$ErrorActionPreference = "Continue"
$Demo = Split-Path -Parent $MyInvocation.MyCommand.Path
$Code = Split-Path -Parent $Demo
$Py = Join-Path $Demo ".venv\Scripts\python.exe"

$required = @(
    "results\stage5_report.json", "results\run_manifest.json",
    "results\fragmented_event_predictions.csv", "results\integrated_event_predictions.csv",
    "results\diagnostic_event_predictions.csv",
    "data\processed\stage3_incidents\incidents_0000.parquet",
    "data\processed\stage3_incident_diagnostics\diagnostics_0000.parquet",
    "data\processed\stage2_feature_plan.csv",
    "models\rf_integrated.joblib", "models\rf_integrated_features.csv")
$missing = @($required | Where-Object { -not (Test-Path (Join-Path $Code $_)) })
foreach ($d in @("data\interim", "data\processed\stage2", "data\processed\stage3_events")) {
    if (-not (Get-ChildItem (Join-Path $Code $d) -Filter *.parquet -ErrorAction SilentlyContinue)) {
        $missing += "$d\*.parquet"
    }
}
if ($missing.Count -gt 0) {
    Write-Host "Verified evidence is missing:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "   $_" }
    Write-Host "Run the pipeline first (from $Code):  powershell -ExecutionPolicy Bypass -File run_all.ps1"
    exit 2
}

if (-not (Test-Path $Py)) {
    Write-Host "demo\.venv not found. Create it (from $Demo):" -ForegroundColor Red
    Write-Host "   py -3.15 -m venv .venv"
    Write-Host "   .venv\Scripts\python.exe -m pip install -r requirements-demo.txt"
    exit 2
}
& $Py -c "import streamlit, altair, sklearn, pyarrow" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "demo\.venv lacks the demo packages. Install them (from $Demo):" -ForegroundColor Red
    Write-Host "   .venv\Scripts\python.exe -m pip install -r requirements-demo.txt"
    exit 2
}

Push-Location $Demo
try {
    & $Py build_cache.py --check | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Building the derived cache (demo\cache) from verified outputs ..."
        & $Py build_cache.py
        if ($LASTEXITCODE -ne 0) { throw "cache build failed" }
    }
    # Re-checked on every launch (about 2 s) so the result always refers to the
    # current saved predictions and model, even after a new run_all.ps1.
    Write-Host "Verifying live inference of the saved integrated model on all test incidents ..."
    & $Py verify_live_inference.py | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "verify_live_inference.py failed" }
    $busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($busy) {
        throw "Port $Port is already in use (process $($busy[0].OwningProcess)). " +
              "Close that program or start the demo with: .\run_demo.ps1 -Port 8502"
    }
    $url = "http://localhost:$Port"
    $stArgs = @("-m", "streamlit", "run", "app.py", "--server.headless", "true",
              "--server.port", "$Port", "--server.address", "localhost")
    $proc = Start-Process -FilePath $Py -ArgumentList $stArgs -NoNewWindow -PassThru
    $ok = $false
    # Python urllib, not Invoke-WebRequest: the latter stalled on localhost
    # (system proxy / name resolution) under Windows PowerShell 5.1.
    $probe = "import sys, urllib.request as u; u.urlopen(sys.argv[1], timeout=2)"
    for ($i = 0; $i -lt 120 -and -not $proc.HasExited; $i++) {
        & $Py -c $probe "http://127.0.0.1:$Port/_stcore/health" 2>$null
        if ($LASTEXITCODE -eq 0) { $ok = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if ($ok) {
        Write-Host "Research Demonstration Lab running at $url  (Ctrl+C to stop)"
        Start-Process $url
    }
    Wait-Process -Id $proc.Id
} finally {
    Pop-Location
}
