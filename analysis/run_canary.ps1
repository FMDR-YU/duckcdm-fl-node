# Canary benchmark: do the release rules catch known leakage? One cohort per call, from your own PowerShell. Resumable.
# This PC blocks a direct .ps1 call (execution policy); start it with the full path, for example:
#   powershell -ExecutionPolicy Bypass -File "<repo>\analysis\run_canary.ps1" -Dataset eicu -Tag demo -Quick
#
#   .\run_canary.ps1 -Dataset mimic_ed -Tag s28k            MIMIC-IV-ED, 28,209-person sample; builds the matrix first if it is missing
#   .\run_canary.ps1 -Dataset eicu -Tag s28k                eICU-CRD (credentialed release in data\eicu\full-2.0, after the DUA)
#   .\run_canary.ps1 -Dataset snuh -Tag cdm -Irb E-...      SNUH CDM matrix (after run_snuh.ps1 -Stage cdm)
#   .\run_canary.ps1 -Dataset mimic_ed -Tag s28k -SummarizeOnly      only (re)write the summary of finished cells
#
# 141 cells = 7 named + 40 space-filling XGBoost settings x training sizes 2,000 / 6,000 / 19,746, 48 models per cell, one process
# per size with 2 threads each (the SynPUF run took about 95 min with the PC otherwise idle; keep the settings, a subsampled
# XGBoost model changes with the thread count). The summary applies the thresholds calibrated on SynPUF unchanged
# (analysis\snuh_pilot\out\synpuf_xgb_canary\canary_thresholds.json) and also recalibrates on this cohort for comparison.
#
# Results (aggregates only, Claude reads them): analysis\snuh_pilot\out\<dataset>[_<tag>]_xgb_canary\canary_summary.md
param(
    [Parameter(Mandatory = $true)][ValidateSet('synpuf', 'mimic_ed', 'eicu', 'snuh')][string]$Dataset,
    [string]$Tag = '',
    [string]$Irb = '',
    [ValidateSet('flip', 'shuffle')][string]$CanaryType = 'flip',
    [int[]]$Sizes = (2000, 6000, 19746),
    [int]$Threads = 2,
    [string]$Thresholds = '',
    [string]$Venv = '<home>\.venvs\egress-pilot',
    [switch]$SummarizeOnly,
    [switch]$Quick                  # smoke test of this script: 6 models per cell, two named settings, no space-filling ones; use with -Dataset eicu -Tag demo
)
$ErrorActionPreference = 'Stop'
$Sizes = [int[]]@($Sizes | ForEach-Object { "$_" -split '[,\s]+' } | Where-Object { $_ })
if ($Dataset -eq 'snuh' -and $Irb -notmatch '^E-\d{4}-\d{3}-\d{4}$') { throw 'SNUH: give this study''s IRB exemption number, e.g. -Irb E-2610-123-4567' }
$a = $PSScriptRoot
# -LiteralPath everywhere: this folder's name has [ ] in it, which Windows PowerShell reads as a wildcard (Resolve-Path returns nothing,
# Test-Path says False, redirection and Start-Process -RedirectStandardOutput cannot write there)
$root = (Resolve-Path -LiteralPath (Join-Path $a '..')).Path
$py = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py)) { throw "python not found: $py" }
$script = Join-Path $a 'snuh_pilot\canary_benchmark.py'

# Long runs must not be cut short by idle sleep. Ask Windows to stay awake while this script runs; the request ends with the
# script and no power setting is changed.
try {
    Add-Type -Namespace SnuhFl -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);' -ErrorAction Stop
    [void][SnuhFl.Power]::SetThreadExecutionState([uint32]2147483649)     # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
} catch { Write-Warning "could not ask Windows to stay awake: $($_.Exception.Message)" }

function Step([string]$name, [scriptblock]$body) {
    $t = Get-Date
    Write-Host ("[{0:HH:mm}] {1}" -f $t, $name)
    $global:LASTEXITCODE = 0
    & $body
    if ($LASTEXITCODE -ne 0) { throw "$name stopped (exit $LASTEXITCODE). Fix and run this call again; finished work is kept." }
    Write-Host ("[{0:HH:mm}] {1} done in {2:N1} min" -f (Get-Date), $name, ((Get-Date) - $t).TotalMinutes)
}

# one environment for every process: xgb family, fixed thread count, no debug messages (they could carry values of restricted data)
$env:PILOT_MODEL = 'xgb'
$env:PILOT_THREADS = "$Threads"
foreach ($v in 'PILOT_DEBUG', 'PILOT_OUT_DIR', 'PILOT_QUICK') { Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
if ($Quick) { $env:PILOT_QUICK = '1' }
if ($Tag) { $env:PILOT_TAG = $Tag } else { Remove-Item Env:PILOT_TAG -ErrorAction SilentlyContinue }
if ($Irb) { $env:PILOT_IRB = $Irb }

$suffix = $(if ($Tag) { "_$Tag" } else { '' })
$matrix = Join-Path $root "data\ckd_pilot\matrix_$Dataset$suffix.parquet"
$out = Join-Path $root ("analysis\snuh_pilot\out\{0}{1}_xgb{2}_canary{3}" -f $Dataset, $suffix, $(if ($Quick) { '_quick' } else { '' }), $(if ($CanaryType -ne 'flip') { "_$CanaryType" } else { '' }))

if (-not $SummarizeOnly) {
    if (-not (Test-Path -LiteralPath $matrix)) {
        if ($Dataset -eq 'snuh') { throw "$matrix not found -- run run_snuh.ps1 -Stage cdm first" }
        if ($Dataset -eq 'eicu') {
            # the three files must be in data\eicu\full-2.0 (data\eicu\demo-2.0.1 for -Tag demo) and match SHA256SUMS.txt
            $rel = $(if ($Tag -eq 'demo') { 'demo' } else { 'full' })
            Step "eICU release check ($rel)" { & $py (Join-Path $a 'eicu\01_check_release.py') --release $rel }
            $chk = Get-Content -Raw -LiteralPath (Join-Path $a "eicu\out\01_check_release_$rel.txt")
            # -cmatch: -match ignores case, and the normal line "0 bad" would match BAD
            if ($chk -notmatch 'required files     : 3 of 3 present' -or $chk -cmatch 'BAD or not listed' -or $chk -cmatch 'adapter            : FAILED') {
                throw "eICU release check failed -- read analysis\eicu\out\01_check_release_$rel.txt (files: patient, apacheApsVar, apachePredVar in data\eicu\)"
            }
            if ($chk -match 'SHA256SUMS.txt not found') { Write-Warning 'SHA256SUMS.txt is not in the release folder; the files were not checksummed.' }
        }
        Step "matrix for $Dataset$suffix (step 00)" { & $py (Join-Path $a 'snuh_pilot\00_build_matrix.py') --dataset $Dataset }
    }
    # training sizes are capped so that a quarter of the rows stay outside every model (the same rule as canary_benchmark.py)
    $metaPath = $matrix -replace '\.parquet$', '.meta.json'
    if (Test-Path -LiteralPath $metaPath) {
        $meta = Get-Content -Raw -LiteralPath $metaPath | ConvertFrom-Json
        if ($meta.PSObject.Properties['n']) {
            $cap = [int][math]::Floor(0.75 * ([int]$meta.n - 400))
            $capped = @($Sizes | ForEach-Object { [math]::Min($_, $cap) } | Select-Object -Unique)
            if (($capped -join ',') -ne ($Sizes -join ',')) {
                Write-Host "The matrix has $($meta.n) rows: training sizes are capped at $cap -> $($capped -join ', ')"
                $Sizes = [int[]]$capped
            }
        }
    }
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $ids = @()
    foreach ($n in $Sizes) {
        # cmd.exe does the redirection: PowerShell's own redirection and Start-Process -RedirectStandardOutput fail on a path with [ ]
        $log = Join-Path $out "run_n$n.log"; $err = Join-Path $out "run_n$n.err"
        $one = '"{0}" "{1}" --dataset {2} --canary-type {3}' -f $py, $script, $Dataset, $CanaryType
        $line = "$one --sizes $n --out-tag named_n$n"
        if ($Quick) { $line += ' --configs d2_r100 regularized --models 6 --targets 2' }
        $line += " > `"$log`" 2> `"$err`""
        if (-not $Quick) { $line += " & $one --lhs --sizes $n --out-tag lhs_n$n >> `"$log`" 2>> `"$err`"" }
        $p = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d', '/s', '/c', ('"' + $line + '"')) -PassThru -WindowStyle Hidden
        $ids += $p.Id
    }
    Write-Host ("[{0:HH:mm}] started {1} processes for sizes {2}; progress in {3}\run_n<size>.log" -f (Get-Date), $ids.Count, ($Sizes -join ', '), $out)
    Wait-Process -Id $ids
    Write-Host ("[{0:HH:mm}] cells finished" -f (Get-Date))
    foreach ($n in $Sizes) {
        $e = Join-Path $out "run_n$n.err"
        if ((Test-Path -LiteralPath $e) -and (Get-Item -LiteralPath $e).Length -gt 0) { Write-Warning "run_n$n.err is not empty (code location of an error; run this call again to resume): $e" }
    }
}

# the development thresholds belong to the canary type: flipped-label canaries -> synpuf_xgb_canary, synthetic -> synpuf_xgb_canary_shuffle
$devDir = $(if ($CanaryType -ne 'flip') { "synpuf_xgb_canary_$CanaryType" } else { 'synpuf_xgb_canary' })
$thr = $(if ($Thresholds) { $Thresholds } else { Join-Path $root "analysis\snuh_pilot\out\$devDir\canary_thresholds.json" })
$sumArgs = @('--dataset', $Dataset, '--canary-type', $CanaryType, '--summarize')
if ($Dataset -ne 'synpuf' -and (Test-Path -LiteralPath $thr)) { $sumArgs += @('--thresholds', $thr) }
Step 'summary' { & $py $script @sumArgs }
Write-Host "Finished. Tell Claude; it reads $out\canary_summary.md."
