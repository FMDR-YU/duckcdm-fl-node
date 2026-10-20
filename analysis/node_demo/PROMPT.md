# Headless use case: the prompt an agent receives, and what it runs

The node has no screen to click. Every step is a Python call or a file, so a coding agent (or a shell script) can carry out the
whole validation on an institution's own CDM from one instruction. The prompt below is the one used for the demo of Additional
file 7; the commands are what the agent executes. Nothing in it needs ATLAS, WebAPI, Java or a database server.

## Prompt

> You are working on a hospital that keeps its OMOP CDM as one DuckDB file. Using duckcdm (pure Python), (1) build the node from
> the CDM export in `data/cdm/Synthea27Nj`, (2) compile the ATLAS cohort definition `analysis/cohort/Cohort_OHDSI_CKD_v205.json`
> and run it on the file, (3) run the Achilles characterization, and (4) write a log with aggregates only (no cells below 11).
> Then run the federated-versus-central check and the export audit on the public SynPUF benchmark with the project's existing
> runners. Do not open the ATLAS interface; everything must run headless.

## What the agent runs

```bash
"python" "<repo>\analysis\node_demo\node_demo.py"
```

(steps 1 to 3 of the prompt: node file, two cohort definitions compiled by duckcdm, Achilles; log in `analysis/node_demo/out/node_demo_log.md`)

```bash
powershell -ExecutionPolicy Bypass -File "<repo>\analysis\federated\run_batch.ps1" -Dataset synpuf -Seeds 42 -Configs plain,krcp -Reexec
```

(federated = central on the public benchmark, with the re-execution check; Docker Desktop must be running)

```bash
"python" "<repo>\analysis\snuh_pilot\run_pilot.py" --dataset synpuf --model xgb
```

(export audit: the three gates on every route, hypotheses evaluated by code, summary in `analysis/snuh_pilot/out/synpuf_xgb/06_summary.md`)

```bash
powershell -ExecutionPolicy Bypass -File "<repo>\analysis\run_canary.ps1" -Dataset synpuf -Quick
```

(canary benchmark in quick mode; the full 141-setting run is the same command without `-Quick`)

## Where the ATLAS screen comes in

Only if a person wants to look: `duckcdm serve <file>` opens the ATLAS 3.0 interface on the same file. The validation above does
not depend on it.
