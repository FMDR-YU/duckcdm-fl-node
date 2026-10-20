# v204 JSON 복원 → v205 JSON 생성 (2026-10-02)

ATLAS JSON을 직접 내려받지 않고, v204 SQL에서 cohort JSON을 역산한 뒤 **circe로 다시 렌더해 원본과 대조**하는 방식으로 검증했다.

## 1. 파일

| 파일 | 내용 |
|---|---|
| `Cohort_OHDSI_CKD_v204_restored.json` | ATLAS 코호트 #204(`CKD_REPRO_KRCP26055_CDM2024_v2`)의 정의 복원본 |
| `Cohort_OHDSI_CKD_v205.json` | v204 + RRT 창 수정 + 변경 메모(260921)의 A~D. **ATLAS에 붙여넣을 파일** |
| `Cohort_OHDSI_CKD_v205_circe1.11.1.sql` | v205.json을 circe 1.11.1로 렌더한 SQL (원내 ATLAS export와 같은 엔진) |
| `render_cohort_json.R` | `Rscript render_cohort_json.R in.json out.sql [CirceR_lib]` — JSON→SQL. 원내 ATLAS와 같게 렌더하려면 3번째 인자로 `<home>\AppData\Local\R\CirceR-1.3.1_circe-1.11.1` (JAVA_HOME = Temurin 17 필요) |
| `compare_sql.py` | 공백 무시 SQL 대조 |

## 2. 검증 결과

- **원내 ATLAS = circe 1.11.1** (CirceR 1.3.1). 1.10.1·1.11.2는 서식이 다르다.
- `v204_restored.json` → 렌더 결과가 **ATLAS 원본 #204 SQL과 517줄 전부 일치**(공백 무시).
  - 주의: 로컬 `Cohort_OHDSI_CKD_v204.sql`은 순수 ATLAS export가 아니다. `v204_window_fixed.sql`(8/31)과 바이트 동일하며, 8/30 메일의 RRT 창 손수정이 들어가 있다. 대조 기준은 이 손수정을 8/30 메일의 원래 줄로 되돌린 SQL을 썼다.
  - ATLAS 원본의 RRT 창은 `index +0일 ~ index −730일`로 **뒤집혀 있었다**(성립 불가 → RRT 제외가 아무도 걸러내지 못함). `IgnoreObservationPeriod = true`.
- `v205.json` → `v205_draft.sql`과 비교해 차이는 두 가지뿐:
  1. draft 머리 주석
  2. RRT 두 줄에 `A.START_DATE >= P.OP_START_DATE AND A.START_DATE <= P.OP_END_DATE`가 추가로 붙음. "관찰기간 시작 ~ index" 조건과 겹쳐 결과는 같다. GUI로 이 창을 설정하면 circe가 항상 이렇게 만든다.

## 3. v205에 반영한 변경

| # | 위치 | v204 | v205 |
|---|---|---|---|
| RRT | Rule 2 Proc·Cond 창 | +0 ~ −730일, 관찰기간 무시 | 전체 이전 ~ +0일, 관찰기간 적용 (8/30 손수정 의도) |
| A | Entry continuous observation | after 0 | **after 730** |
| B | Rule 1 Cr ≥2 창 | 전체 관찰기간 | **index +0 ~ +730일** |
| C | Rule 3 관찰기간 ≥730 | 있음 | **삭제** (A로 대체, mask `POWER(2,4)-1`) |
| D | 불가능값 규칙 단위 | 4121402 / 4121395 | **8753 / 8713** |
| E | RRT Codeset 2 | 4144749 (Intravenous nutrition agent) | **4322471 Transplant of kidney** |
| — | Codeset 3 | 결번 | 없음 |

D 근거: OHDSI 공개 vocabulary 조회 결과 4121402(mmol/L)·4121395(g/dL)는 **SNOMED 비표준(N) 단위**, 8753·8713은 UCUM 표준.

## 4. RRT 개념집합(Codeset 2) — E로 반영 완료 (2026-10-02)

| concept_id | 이름 | 도메인 |
|---|---|---|
| 4032243 | Dialysis procedure | Procedure |
| 4146536 | Renal dialysis | Procedure |
| **4144749** | **Intravenous nutrition agent** | **Device** ← RRT와 무관 |
| 199991 | Disorder of transplanted kidney | Condition |

- 4144749는 오입력으로 보인다. Rule 2는 Procedure·Condition 테이블만 보므로 결과에 해는 없지만, **신장이식 시술 개념이 빠져 있다**.
- 후보: **4322471 Transplant of kidney** (SNOMED 70536003, Procedure, 하위개념 포함 시 cadaveric 등 포괄).
- **사용자 결정으로 4144749 → 4322471 교체.** 재렌더 결과는 이전 v205 SQL과 비교해 Codeset 2의 개념 ID 두 곳만 다르다(공백 무시 시 나머지 동일).
- 신장이식 시술 이력자가 추가로 제외되므로 N이 v204 대비 줄 수 있다 → Inclusion Report에서 Rule 2 감소율 확인.

## 5. ATLAS 반영 절차

1. 원내 ATLAS → **New Cohort** (기존 #204에 덮어쓰지 말 것)
2. Export → JSON 탭에 `Cohort_OHDSI_CKD_v205.json` 전체 붙여넣기 → **Reload**
3. Save → Generate → Inclusion Report 확인 (Rule 3 감소 0.000%면 단위 불일치)
4. Export → SQL이 `Cohort_OHDSI_CKD_v205_circe1.11.1.sql`과 같아야 한다 (`compare_sql.py`로 대조)
