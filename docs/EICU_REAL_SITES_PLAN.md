# eICU 실제 병원을 기관으로 쓰는 연합 실험: 설계 (2026-10-19)

목적: IRB v1.1 승인을 기다리지 않고 실자료 다기관 연합 결과를 만든다. eICU-CRD(DUA 서명 완료, `data/eicu/full-2.0/`)의 실제 병원을 기관으로 두고 연합 XGBoost(F) = 중앙(A) 여부, 기관별 모델(B)의 효용과 노출, 반출 감사(3-gate, 캐너리)를 SynPUF·SNUH 가상 기관과 같은 파이프라인으로 돌린다. ACI 원고의 "실제 다기관" 절이 된다.

## 1. 지금 코드가 전제하는 것

- 기관 수 3이 고정이다: `pilot_lib.scenarios`의 `B1_k`/`B2_k`(k = 0..2), `size_classes`, `COMBINED`, `FEDERATED`, `make_sites.N_SITES`, `run_fl_xgb.N_SITES`, 캐너리 칸 설계.
- 행렬 메타에 `fixed_sites: true`와 열 `site_b1`, `site_b2`(0..2, 없으면 -1)가 있으면 `scenarios()`가 무작위 분할 대신 그 열을 쓴다(SNUH P3·P4가 쓰는 경로). 이 경로를 그대로 쓰면 `make_sites.py`, `run_fl_xgb.py`, `run_pilot.py`, `run_canary.ps1`은 바꾸지 않아도 된다.
- eICU 어댑터(`analysis/eicu/matrix_eicu.py`)는 `hospital_id`를 특성이 아닌 열로 이미 남긴다. full 점검(2026-10-12): 분석 행 132,251명, 병원 207개, 2,000명 이상 14개(39,722명).

## 2. 설계: 1단계 (3개 실제 병원, 코드 변경 최소)

태그 두 개를 추가한다. 각 태그는 병원 세 곳의 환자만 담은 행렬이다(중앙 A = 세 기관의 합집합이라는 현재 정의를 지키기 위해 다른 병원의 행은 넣지 않는다).

| 태그 | 병원 선택 규칙(사전 지정) | 뜻 |
|---|---|---|
| `h3a` | 분석 행 기준 가장 큰 병원 3곳 | 크기가 비슷한 실제 기관(B1에 대응) |
| `h3b` | 2,000명 이상 14곳 중 가장 큰 곳, 중앙값 순위 곳, 가장 작은 곳 | 크기가 다른 실제 기관(B2에 대응) |

- `site_b1 = site_b2 = 병원 순위(0..2)`로 둔다. 코드 경로가 두 열을 요구해서이고, 보고에서는 F_B1 하나만 쓴다(F_B2는 같은 값이라 생략).
- 훈련/검증 분리는 병원 안에서 30% 층화(`train_test_split(stratify=y)`를 병원별로). 공통 검증 집합 = 세 병원의 검증 행 합집합. 사람 단위(첫 ICU 입실 1건)는 그대로.
- 결과변수·특성 47개·stratum(병동 유형군)은 s28k와 같다.
- 병원 ID는 반출물에 쓰지 않는다. 보고는 "병원 1·2·3(크기순)"과 사람 수(11 이상 집계)만.

코드 변경:
1. `analysis/eicu/matrix_eicu.py`: `build(..., hospitals=None)` 인자. `hospitals`가 주어지면 그 병원 행만 남기고 `site` 열(0..k-1)을 만든 뒤 병원 안에서 분할. 병원 고르는 함수 `pick_hospitals(df, rule)` (`top3` / `spread3`).
2. `analysis/snuh_pilot/00_build_matrix.py`의 `build_eicu`: `L.TAG in ('h3a', 'h3b')`이면 위 인자를 넘기고 `meta['fixed_sites'] = True`, 열 `site_b1`, `site_b2` 기록, `meta['eicu']['hospital_sizes']`에 기관별 사람 수(집계)만.
3. 시험: `analysis/snuh_cdm/tests/run_tests.py --only eicu`에 가짜 release로 `h3a`·`h3b` 행렬을 만들어 (a) 세 기관이 서로소이고 훈련 행을 덮는지, (b) 기관 안 분할 비율, (c) `scenarios()`가 fixed_sites를 따르는지 확인. 공개 demo(1,742명)는 병원이 작아 규칙 시험에만 쓴다.
4. 실행기: `analysis/run_canary.ps1 -Dataset eicu -Tag h3a`와 `analysis/federated/run.ps1`의 `--dataset eicu --tag h3a`가 그대로 돈다(태그를 행렬 이름에 쓰는 기존 규칙).

실행(사용자 PowerShell, Docker는 사용자 터미널에서 켬):
- 행렬 2개: `00_build_matrix.py --dataset eicu --tag h3a`, `--tag h3b` (각 1분 안쪽).
- 연합: `make_sites.py` + `run_fl_xgb.py --dataset eicu --tag h3a --scenario B1 --seed s --config c` (SynPUF 기준 plain 약 1분, krcp 4–5분, regularized 2–3분; 기관 크기가 비슷하므로 비슷할 것). 시드 10 × 태그 2 × 설정 3(plain, krcp, regularized) ≈ 2–3시간. leaky는 시드 42만(17분).
- 파일럿: `run_pilot.py --dataset eicu --tag h3a --model xgb` (A, A′, B1_k, B_avg, F와 3-gate). 캐너리: `run_canary.ps1 -Dataset eicu -Tag h3a`(141칸 × 2종; s28k 때와 같은 규모, 사용자 실행 시간 기준 반나절).

산출물(집계만, `analysis/snuh_pilot/out/eicu_h3a_xgb*/`, `analysis/federated/out/`): H5(F − A 비열등), 기관별 효용·노출, 캐너리 민감도·특이도의 SynPUF 임계 전이. 그림: 기존 Fig6 형식에 "eICU 실제 병원" 열 추가.

## 3. 2단계 (선택): 병원 14곳 연합

`N_SITES`를 매개변수로 바꾸는 일(scenarios 키, size_classes, COMBINED/FEDERATED, run_fl_xgb, 캐너리 칸 설계, 보고서 표). 1–2일. 얻는 것: "기관 수에 따른 F − A와 노출" 그림 한 장. 심사자가 요구하거나 1단계 결과가 뚜렷할 때 한다. 1단계만으로도 "실제 다기관" 문장은 선다.

## 4. 하지 않는 것

- 병원 ID·이름을 결과에 쓰지 않는다(eICU DUA, 집계 규칙).
- SNUH 자료는 건드리지 않는다(승인 뒤 `run_snuh.ps1 -Stage fl|pilot|canary`로 같은 파이프라인).
- 사전등록(OSF)은 1단계 병원 선택 규칙을 포함해 행렬을 만들기 전에 올린다(분석계획 v2 §7 6항과 함께 사용자 결정).
