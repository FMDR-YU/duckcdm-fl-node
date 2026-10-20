# SNUH stages in order, one stage per call, with this study's IRB exemption number. Stops where Claude is needed.
# This PC blocks a direct .ps1 call (execution policy); start it with the full path, for example:
#   powershell -ExecutionPolicy Bypass -File "<repo>\analysis\run_snuh.ps1" -Irb E-2610-060-1785 -Stage p1
# Run from your own PowerShell (the SNUH extract is never opened by Claude). Each stage is resumable.
#
#   .\run_snuh.ps1 -Irb E-2610-123-4567 -Stage p1       profile the extract (schema, code catalogues, counts >= 11)
#                                                       -> tell Claude; Claude writes the P2 mapping tables (maps\*.csv)
#   .\run_snuh.ps1 -Irb ... -Stage cdm                  P3 build the CDM and the 7 site DuckDBs, then P4 twice: cohort of the published
#                                                       rules (first visit as index; the main matrix, PILOT_TAG cdmv) and the v205 cohort
#                                                       (first CKD diagnosis as index; sensitivity matrix, tag cdm), each with features,
#                                                       matrix and agreement with the v1.3 matrix
#   .\run_snuh.ps1 -Irb ... -Stage fl                   federated jobs: krcp and regularized, seeds 42-51 x B1/B2 (re-execution check on
#                                                       the first job), then one leaky job (seed 42, B1) as the positive control
#                                                       (Docker Desktop running)
#   .\run_snuh.ps1 -Irb ... -Stage pilot                pilot on the CDM matrix: xgb family first (with the federated
#                                                       models), then the ensemble family (about 5-6 h)
#   .\run_snuh.ps1 -Irb ... -Stage canary               canary benchmark on the CDM matrix: do the release rules catch planted leakage?
#                                                       141 cells, about 95 min (after -Stage cdm; not part of -Stage all); thresholds
#                                                       calibrated on SynPUF are applied unchanged. Details: run_canary.ps1
#   .\run_snuh.ps1 -Irb ... -Stage all                  cdm, fl, pilot in a row (after p1 and the P2 tables)
#
# -Cohort visit (default) runs fl / pilot / canary on the first-visit matrix (tag cdmv); -Cohort ckd runs them on the v205 matrix (tag cdm).
#
# Outputs the next step reads: analysis\snuh_cdm\out\ and analysis\snuh_pilot\out\ (aggregates only).
param(
    [Parameter(Mandatory = $true)][string]$Irb,
    [ValidateSet('p1', 'cdm', 'fl', 'pilot', 'canary', 'all')][string]$Stage = 'all',
    [ValidateSet('visit', 'ckd')][string]$Cohort = 'visit',
    [string]$Venv = '<home>\.venvs\egress-pilot'
)
$ErrorActionPreference = 'Stop'
if ($Irb -notmatch '^E-\d{4}-\d{3}-\d{4}$') { throw "IRB number looks wrong: $Irb (expected E-NNNN-NNN-NNNN, this study's exemption number)" }
$a = $PSScriptRoot
$root = (Resolve-Path -LiteralPath (Join-Path $a '..')).Path      # -LiteralPath: the folder name has [ ] in it (a wildcard to PowerShell)
$py = Join-Path $Venv 'Scripts\python.exe'
$tag = $(if ($Cohort -eq 'ckd') { 'cdm' } else { 'cdmv' })      # matrix variant for fl / pilot / canary
if (-not (Test-Path -LiteralPath $py)) { throw "python not found: $py" }

# The CDM build (-Stage cdm: P3 + P4) is inside the exemption E-2610-060-1785 (user decision 2026-10-14: the change review has nothing to do
# with it). The stages that only exist in the change review v1.1 -- federated learning, the pilot on the CDM matrix, the canary benchmark
# (and -Stage all, which contains them) -- wait for its approval (notice conditions 2 and 5): create the marker file below by hand when the
# approval has arrived; the runner does not create it.
$approval = Join-Path $root 'governance\CHANGE_REVIEW_v1.1_APPROVED.txt'
if ($Stage -in 'fl', 'pilot', 'canary', 'all' -and -not (Test-Path -LiteralPath $approval)) {
    throw "Stage '$Stage' belongs to the change review v1.1, which is not approved yet. When it is, create $approval (one line: approval date and number) and run this again. -Stage p1 and -Stage cdm need nothing."
}

# Long stages must not be cut short by idle sleep (this PC sleeps after 30 min without input on AC power). Ask Windows to stay
# awake while this script runs; the request ends with the script and no power setting is changed.
try {
    Add-Type -Namespace SnuhFl -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);' -ErrorAction Stop
    [void][SnuhFl.Power]::SetThreadExecutionState([uint32]2147483649)     # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
} catch { Write-Warning "could not ask Windows to stay awake: $($_.Exception.Message)" }

function Step([string]$name, [scriptblock]$body) {
    $t = Get-Date
    Write-Host ("[{0:HH:mm}] {1}" -f $t, $name)
    $global:LASTEXITCODE = 0
    & $body
    if ($LASTEXITCODE -ne 0) { throw "$name stopped (exit $LASTEXITCODE). Fix and run this stage again; finished work is kept." }
    Write-Host ("[{0:HH:mm}] {1} done in {2:N1} min" -f (Get-Date), $name, ((Get-Date) - $t).TotalMinutes)
}

# run_batch.ps1 runs in this process: a nested "powershell.exe -File" call splits array parameters into stray positional arguments.
$batch = Join-Path $a 'federated\run_batch.ps1'
function Invoke-Batch([hashtable]$p) { $global:LASTEXITCODE = 0; & $batch @p }

if ($Stage -eq 'p1') {
    Step 'P1 profile' { & $py (Join-Path $a 'snuh_cdm\p1_profile_extract.py') --irb $Irb }
    Write-Host 'Next: tell Claude P1 is done. Claude reads analysis\snuh_cdm\out\p1_* and writes the P2 mapping tables.'
    return
}
if ($Stage -in 'cdm', 'all') {
    # the map files exist as seeds from the start; Claude adds P2_DONE.txt when the tables are finished against the P1 output
    foreach ($m in 'lab_map.csv', 'dx_map.csv', 'drug_map.csv', 'P2_DONE.txt') {
        if (-not (Test-Path -LiteralPath (Join-Path $a "snuh_cdm\maps\$m"))) { throw "P2 not finished: snuh_cdm\maps\$m missing -- run -Stage p1 and let Claude write the maps first" }
    }
    # --site-scope mapped: the site databases keep only the measurement / drug rows that have a concept (the LAB files hold 143 million rows);
    # the central database keeps everything
    Step 'P3 build CDM' { & $py (Join-Path $a 'snuh_cdm\p3_build_cdm.py') --irb $Irb --site-scope mapped }
    # the main matrix first; the v205 matrix last, so the site databases end with the cohort table of the v205 definition
    Step 'P4 cohort and features, first visit (main matrix)' { & $py (Join-Path $a 'snuh_cdm\p4_site_features.py') --irb $Irb --agreement --entry visit }
    Step 'P4 cohort and features, first CKD diagnosis (sensitivity matrix)' { & $py (Join-Path $a 'snuh_cdm\p4_site_features.py') --irb $Irb --agreement }
}
if ($Stage -in 'fl', 'all') {
    & cmd.exe /c 'docker info >nul 2>nul'
    if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop is not running. Start it from your own terminal (auto-start is off), then run this stage again.' }
    Step 'federated jobs krcp + regularized' { Invoke-Batch @{ Dataset = 'snuh'; Tag = $tag; Configs = @('krcp', 'regularized'); Reexec = $true } }
    Step 'federated job leaky (positive control)' { Invoke-Batch @{ Dataset = 'snuh'; Tag = $tag; Seeds = @(42); Scenarios = @('B1'); Configs = @('leaky') } }
    Write-Host 'Federated jobs finished. Docker Desktop is not needed any more; free its memory with: docker desktop stop'
}
if ($Stage -in 'pilot', 'all') {
    Step 'pilot, xgb family' { & $py (Join-Path $a 'snuh_pilot\run_pilot.py') --dataset snuh --tag $tag --model xgb --irb $Irb }
    Step 'pilot, ensemble family' { & $py (Join-Path $a 'snuh_pilot\run_pilot.py') --dataset snuh --tag $tag --irb $Irb }
}
if ($Stage -eq 'canary') {
    & (Join-Path $a 'run_canary.ps1') -Dataset snuh -Tag $tag -Irb $Irb
    return
}
Write-Host "All requested stages finished. Tell Claude: results are in analysis\snuh_pilot\out\snuh_${tag}_xgb\ and analysis\snuh_pilot\out\snuh_${tag}\."
