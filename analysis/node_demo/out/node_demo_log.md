# Headless node demo on a public OMOP CDM (Synthea27Nj, CDM 5.4)

python 3.14.3, duckdb 1.5.2, duckcdm 0.4.7; Windows-11-10.0.26300-SP0

1. node: 39 tables loaded into node_demo.duckdb in 2.0 s; persons 28; rows condition 470, drug 883, measurement 10,040, concept 2,294; file 2.8 MB
2a. cohort v205 (institutional CKD definition, ATLAS export): compiled by duckcdm.circe in 0.20 s (18,664 characters of DuckDB SQL), run in 0.07 s, persons 0
2b. cohort demo (first occurrence of "Viral sinusitis", generated definition demo_cohort.json): compiled in 0.04 s, run in 0.05 s, persons 23
3. achilles: 110 analyses, 0 failed, 4.0 s, small-cell 10
4. serve (not run here): duckcdm serve "C:\Users\mikes\Documents\[ACI] SNUH_FL_EGRESS_BENCHMARK\public_export\analysis\node_demo\out\node_demo.duckdb"  then open http://127.0.0.1:8000/atlas/ in a browser; the same file answers the WebAPI calls
5. next (public SynPUF benchmark, existing commands): federated = central: analysis/federated/run_batch.ps1 -Dataset synpuf -Seeds 42 -Configs plain,krcp -Reexec; export audit and canary benchmark: analysis/snuh_pilot/run_pilot.py --dataset synpuf --model xgb, analysis/run_canary.ps1 -Dataset synpuf -Quick
