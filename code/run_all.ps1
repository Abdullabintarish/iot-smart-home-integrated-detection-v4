# End-to-end run on Windows: clean -> run manifest -> Stage 1 collection ->
# Stages 2-5 -> report + screenshots.
#
#   .\run_all.ps1 [raw-root] [extra run_pipeline args]
#
# Windows counterpart of run_all.sh. Defaults to data/raw_combined.
# Pass --skip-cv for a fast run, or nothing for full CV.
#
# Before Stage 1 the generated directories (data/interim, data/processed,
# results, models) are emptied so a stale intermediate from an earlier run
# cannot contaminate this one. The raw data under data/raw_combined is never
# touched. Back up results/ first if you need the previous run.
param(
    [string]$Root = "data/raw_combined",
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$PipelineArgs
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$Results = Join-Path $PSScriptRoot "results"
$TranscriptDir = Join-Path $Results "transcripts"
$Stage1Log = Join-Path $TranscriptDir "stage1_run.log"
$RunLog = Join-Path $TranscriptDir "run_pipeline_run.log"
$ReportLog = Join-Path $TranscriptDir "make_report_run.log"
$RunAllLog = Join-Path $TranscriptDir "run_all.log"
$env:PYTHONIOENCODING = "utf-8"

function Stamp { (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss 'UTC'") }

# Run python, echo every line and write it to $Log as UTF-8 (Tee-Object in
# Windows PowerShell 5.1 would write UTF-16). The log is framed by start/end
# times and the step's runtime.
function Invoke-Logged([string]$Log, [string[]]$CmdArgs) {
    $enc = New-Object System.Text.UTF8Encoding($false)
    $w = New-Object System.IO.StreamWriter($Log, $false, $enc)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    # Native stderr lines arrive as error records; do not let them abort.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $w.WriteLine("# start $(Stamp): python $($CmdArgs -join ' ')")
        & $Py -u @CmdArgs 2>&1 | ForEach-Object {
            $line = "$_"
            Write-Host $line
            $w.WriteLine($line)
            $w.Flush()
        }
        $code = $LASTEXITCODE
        $w.WriteLine("# end $(Stamp): exit $code, runtime $([math]::Round($sw.Elapsed.TotalSeconds, 1))s")
    }
    finally {
        $ErrorActionPreference = $prev
        $w.Close()
    }
    if ($code -ne 0) { throw "python $($CmdArgs -join ' ') failed (exit $code)" }
    return $sw.Elapsed.TotalSeconds
}

# ---- clean stale intermediates (never data/raw_combined) -------------------
$removed = @()
foreach ($d in @("data\interim", "data\processed", "results", "models")) {
    $dir = Join-Path $PSScriptRoot $d
    if (Test-Path $dir) {
        foreach ($item in Get-ChildItem -LiteralPath $dir -Force) {
            Remove-Item -LiteralPath $item.FullName -Recurse -Force -Confirm:$false
            $removed += (Join-Path $d $item.Name)
        }
    }
}
New-Item -ItemType Directory -Force $TranscriptDir | Out-Null
Start-Transcript -Path $RunAllLog | Out-Null
$t0 = Get-Date
Write-Host "==> run_all started $(Stamp)"
Write-Host "==> Cleaned stale outputs: $($removed.Count) item(s) removed"
foreach ($r in $removed) { Write-Host "    removed $r" }

$times = [ordered]@{}
try {
    Write-Host "==> Run manifest (host, code and dataset hashes, config)"
    $times["record_run_info"] = Invoke-Logged (Join-Path $TranscriptDir "record_run_info_run.log") `
        @("record_run_info.py", "--raw", $Root)

    Write-Host "==> Stage 1: collecting from $Root"
    $times["stage1_collect"] = Invoke-Logged $Stage1Log @("stage1_collect.py", "--root", $Root)

    Write-Host "==> Stages 2-5: preprocess, correlate, detect, evaluate"
    $times["run_pipeline"] = Invoke-Logged $RunLog (@("run_pipeline.py") + @($PipelineArgs | Where-Object { $_ }))

    Write-Host "==> Report + screenshots"
    $times["make_report"] = Invoke-Logged $ReportLog `
        @("make_report.py", "--run-log", $RunLog, "--stage1-log", $Stage1Log)
}
finally {
    Write-Host "==> Step runtimes"
    foreach ($k in $times.Keys) { Write-Host ("    {0,-16} {1,8:N1} s" -f $k, $times[$k]) }
    $total = ((Get-Date) - $t0).TotalSeconds
    Write-Host "==> run_all ended $(Stamp); total runtime $([math]::Round($total, 1)) s"
    Write-Host "==> Outputs"
    foreach ($p in @("results\run_manifest.json", "results\stage5_report.json",
                     "results\stage5_summary.txt", "results\baseline_vs_integrated.csv",
                     "results\fragmented_event_predictions.csv",
                     "results\integrated_event_predictions.csv",
                     "results\diagnostic_event_predictions.csv",
                     "results\report\REPORT.md", "results\transcripts")) {
        $full = Join-Path $PSScriptRoot $p
        $state = if (Test-Path $full) { "" } else { "  (missing)" }
        Write-Host "    $full$state"
    }
    Stop-Transcript | Out-Null
}
