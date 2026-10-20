# Federated jobs for every seed x scenario x config, one after another (resumable): make_sites.py + run_fl_xgb.py
# in the container. Afterwards run the pilot on the xgb family, which picks the FLARE models up:
#   python analysis\snuh_pilot\run_pilot.py --dataset synpuf --model xgb
#
#   powershell -ExecutionPolicy Bypass -File analysis\federated\run_batch.ps1                       # synpuf, seeds 42-51
#   powershell -ExecutionPolicy Bypass -File analysis\federated\run_batch.ps1 -Seeds 42,43 -Configs krcp,leaky
#   powershell -ExecutionPolicy Bypass -File analysis\federated\run_batch.ps1 -Dataset snuh -Tag cdm     (after the IRB number)
#
# A job is skipped when its model file already exists in data\federated\...; -Force reruns. -Reexec repeats the first
# job of each config in a fresh workspace and compares (Gate 3 analogue). Docker Desktop must be running (start it from
# your own terminal). Only aggregates are printed; per-job logs go to out\<ds>\batch\ (ignored, UTF-16).
# Lists may be comma-separated: with "-File", Windows PowerShell hands "42,43" over as one string, which is split below.
param(
    [string]$Dataset = 'synpuf',
    [string]$Tag = '',
    [string[]]$Seeds = (42..51),
    [string[]]$Scenarios = @('B1', 'B2'),
    [string[]]$Configs = @('krcp', 'regularized'),      # leaky (positive control, slow) only on request: -Configs krcp,regularized,leaky
    [switch]$Reexec,
    [switch]$Quick,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
function Split-List($v) { @($v | ForEach-Object { "$_" -split '[,\s]+' } | Where-Object { $_ }) }
$Seeds = [int[]](Split-List $Seeds); $Scenarios = Split-List $Scenarios; $Configs = Split-List $Configs
foreach ($c in $Configs) { if ($c -notin 'plain', 'krcp', 'leaky', 'regularized') { throw "unknown config: $c" } }
foreach ($s in $Scenarios) { if ($s -notin 'B1', 'B2') { throw "unknown scenario: $s" } }
$here = $PSScriptRoot
$root = (Resolve-Path -LiteralPath (Join-Path $here '..\..')).Path      # -LiteralPath (also below): the folder name has [ ] in it, a wildcard to PowerShell
$run = Join-Path $here 'run.ps1'
$base = $Dataset; if ($Tag) { $base = "${Dataset}_${Tag}" }; if ($Quick) { $base = "${base}_quick" }
$logDir = Join-Path $here "out\$base\batch"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$extra = @(); if ($Tag) { $extra += @('--tag', $Tag) }; if ($Quick) { $extra += '--quick' }

function Invoke-Job([string]$name, [string[]]$cmd) {
    $log = Join-Path $logDir "$name.log"
    # Windows PowerShell 5.1 turns every stderr line of a redirected native command into a terminating error under 'Stop'
    # (Docker and Python both write to stderr); the exit code below is what decides success.
    $ErrorActionPreference = 'Continue'
    # "*> $log" cannot write into a path with [ ] in it; Out-File -LiteralPath can (the exit code of the native command is kept)
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $run @cmd 2>&1 | Out-File -LiteralPath $log
    return $LASTEXITCODE
}

$t0 = Get-Date
$done = 0; $skipped = 0
foreach ($seed in $Seeds) {
    foreach ($scn in $Scenarios) {
        $site = Join-Path $root "data\federated\$base\${scn}_s$seed"
        $need = $Configs | Where-Object { $Force -or -not (Test-Path -LiteralPath (Join-Path $site "F_xgb_$_.model.json")) }
        if (-not $need) { $skipped += $Configs.Count; continue }
        Write-Host ("[{0:HH:mm}] seed {1} {2}: sites" -f (Get-Date), $seed, $scn)
        $rc = Invoke-Job "sites_${scn}_s$seed" (@('python', 'make_sites.py', '--dataset', $Dataset, '--scenario', $scn, '--seed', "$seed") + $extra)
        if ($rc -ne 0) { throw "make_sites failed for $scn seed $seed (see $logDir)" }
        foreach ($cfg in $need) {
            $args2 = @('python', 'run_fl_xgb.py', '--dataset', $Dataset, '--scenario', $scn, '--seed', "$seed", '--config', $cfg) + $extra
            if ($Reexec -and $seed -eq $Seeds[0]) { $args2 += '--reexec' }
            $t = Get-Date
            $rc = Invoke-Job "fl_${scn}_s${seed}_$cfg" $args2
            if ($rc -ne 0) { throw "run_fl_xgb failed: $scn seed $seed $cfg (see $logDir)" }
            $done++
            Write-Host ("[{0:HH:mm}]   {1} {2} s{3} {4}: {5:N0} s" -f (Get-Date), $scn, $cfg, $seed, 'done', ((Get-Date) - $t).TotalSeconds)
        }
    }
}
Write-Host ("finished {0} jobs ({1} already done) in {2:N0} min" -f $done, $skipped, ((Get-Date) - $t0).TotalMinutes)
