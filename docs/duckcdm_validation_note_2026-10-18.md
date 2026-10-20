# duckcdm 0.4.7 독립 검증 기록 (2026-10-17 ~ 10-18)

대상: `vitaldb/duckcdm` 0.4.7 (PyPI, Apache-2.0). 환경: Windows 11, Python 3.14, DuckDB 1.5.2, 4 스레드 / 8 GB 제한.
자료: SNUH CKD 추출본(DRB-E(I)-2025-08-01)을 OMOP CDM v5.3으로 변환해 가상 3개 기관으로 나눈 DuckDB 7개(기관 6 + 홀드아웃). 이 문서에는 집계만 있다(11 미만 셀 없음).

## 1. circe 이식의 코호트 동일성

코호트 정의: 원내 ATLAS(circe-be 1.11.1)의 CKD v205 JSON. 비교 대상: 같은 JSON의 ATLAS 내보내기 SQL을 손으로 DuckDB 방언에 옮긴 고정본(원내 ATLAS 결과와 대조 완료).
방법: `duckcdm.circe.build_cohort_query` → `duckcdm.sqlrender.render/translate('duckdb')` → 실행. 두 결과를 같은 연결의 temp 테이블에 두고 사람·시작일·종료일 단위로 비교(`analysis/snuh_cdm/p4b_duckcdm_cohort.py`).

| DB | duckcdm | 손 번역 | 한쪽에만 | 시작일 다름 | 종료일 다름 | 초(duckcdm / 손 번역) |
|---|---|---|---|---|---|---|
| site_B1_0 | 4,449 | 4,449 | 0 | 0 | 0 | 0.2 / 0.1 |
| site_B1_1 | 4,603 | 4,603 | 0 | 0 | 0 | 0.2 / 0.1 |
| site_B1_2 | 4,508 | 4,508 | 0 | 0 | 0 | 0.2 / 0.1 |
| site_B2_0 | 6,988 | 6,988 | 0 | 0 | 0 | 0.3 / 0.2 |
| site_B2_1 | 3,875 | 3,875 | 0 | 0 | 0 | 0.2 / 0.1 |
| site_B2_2 | 2,697 | 2,697 | 0 | 0 | 0 | 0.1 / 0.1 |
| holdout | 5,497 | 5,497 | 0 | 0 | 0 | 0.2 / 0.1 |

생성된 SQL은 circe-be 1.11.1 텍스트와 네 곳이 다르다(개념집합 하위개념 질의의 괄호·WHERE 위치, 포함규칙 블록의 `{n != 0}?{}` 조건, 코호트 기간 병합의 윈도 함수 방식, `generateStats` 조건부 통계 블록). 모두 1.12 이후 circe-be의 변경이고 결과는 같다. 가짜 자료 시험(생성 자료 → P3 → 비교)에서도 동일.

## 2. `duckcdm serve` (ATLAS 3.0 + WebAPI)

기관 DB 사본 3개를 한 서버에 소스로 올림. Achilles `--small-cell 10`: 기관마다 110개 분석, 실패 0, 19–23초. Data Sources 대시보드(사람 수 9,792 / 9,803 / 9,827, 성비, 첫 관찰 연령, 누적 관찰기간, 월별 관찰 인원) 정상. v205 JSON을 `POST /WebAPI/cohortdefinition/`로 올리고 `generate`하면 1초 미만에 4,449명, Inclusion report(base 6,489 → 규칙 4개 → 4,449, 68.56%) 정상.

## 3. 걸린 것 (작성자에게 보고할 항목)

1. **소문자 열 이름.** WebAPI가 행 dict를 대문자 키(`r['CONCEPT_ID']`, `rows[0]['VOCABULARY_VERSION']`)로 읽는데 DuckDB는 표에 저장된 열 이름의 대소문자를 그대로 돌려준다. 열 이름이 소문자인 CDM(우리 P3, CommonDataModel DDL 기본)에서는 `/vocabulary/{key}/info`, `/domains`, concept 조회가 KeyError. 어휘 표 8개를 `SELECT col AS COL`로 다시 만들어 해결. 제안: `query_dicts`에서 키를 대문자로 정규화하거나 SQL에 별칭을 붙이기.
2. **어휘 표 부족.** `init_concept_hierarchy.sql`이 `vocabulary` 표를 요구한다. concept·concept_ancestor·concept_relationship만 있는 부분 어휘에서는 Achilles 보고서 초기화가 실패. VOCABULARY·DOMAIN·CONCEPT_CLASS·RELATIONSHIP·CONCEPT_SYNONYM을 넣어 해결. 제안: 필요한 표를 README에 명시하거나 없을 때 건너뛰기.
3. **Windows `mktime` 범위.** `/vocabulary/{key}/concept/{id}`가 1970-01-01 이전 `valid_start_date`에서 `OverflowError: mktime argument out of range`. `calendar.timegm` 또는 `datetime.timestamp()`로 바꾸면 된다.
4. **SNOMED 라이선스 창.** 동의/거부 상태가 저장되지 않아 페이지를 옮길 때마다 다시 뜬다(ATLAS가 WebAPI의 사용자 설정 엔드포인트에 기대는 듯).
5. **small-cell 옵션의 범위.** `achilles --small-cell 10`을 줘도 대시보드 JSON(ageAtFirstObservation, observedByMonth)에 11 미만 셀이 남는다(최소 6). 보고서 질의 쪽에도 적용되어야 반출 규칙에 맞는다.
6. **설치.** `pip install duckcdm`만으로는 `serve`가 `uvicorn` 없음으로 실패. `duckcdm[server]`를 CLI 오류 문구에 안내하면 좋겠다.
7. **빈 표.** Achilles가 참조하는 CDM 표가 없으면 분석이 실패하므로 CDM 5.3 표 전부를 빈 표로 만들어 두었다(`duckcdm.omop.cdm_fields`로 가능). `views --materialize`를 쓰지 않는 사용자를 위해 "없는 표는 빈 표로" 옵션이 있으면 편하다.

## 4. 그림

`Figures/v2/atlas/Fig_atlas_virtual_sites.png`(세 기관 Achilles 대시보드 지표, 11 미만 셀은 0), `Figures/v2/atlas/atlas_dashboard_SNUH_B1_0_screenshot.png`(ATLAS 화면).
