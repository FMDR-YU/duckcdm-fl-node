# Runs one command inside the FLARE image with only the folders it needs mounted:
#   analysis            read-only (code)
#   data\ckd_pilot      read-only (pilot matrices)
#   data\federated      read-write (site files, FLARE workspace)
#   analysis\federated\out   read-write (aggregate results)
# Nothing else under data\ is visible to the container. No network is needed after the image is built.
#
#   .\run.ps1 python make_sites.py --dataset synpuf --scenario B1 --seed 42
#   .\run.ps1 python run_fl_xgb.py --dataset synpuf --scenario B1 --seed 42 --config plain
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Cmd)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path      # -LiteralPath: the folder name has [ ] in it (a wildcard to PowerShell)
$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
if (-not (Test-Path -LiteralPath $docker)) { $docker = 'docker' }

$out = Join-Path $root 'analysis\federated\out'
$fed = Join-Path $root 'data\federated'
New-Item -ItemType Directory -Force -Path $out, $fed | Out-Null

& $docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 `
    -v "${root}\analysis:/work/analysis:ro" `
    -v "${out}:/work/analysis/federated/out" `
    -v "${root}\data\ckd_pilot:/work/data/ckd_pilot:ro" `
    -v "${fed}:/work/data/federated" `
    snuh-fl-flare:0.1 @Cmd
exit $LASTEXITCODE
