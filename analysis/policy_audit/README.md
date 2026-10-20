# analysis/policy_audit

플랫폼 반출 정책 매트릭스(정책감사)의 자료와 재현 스크립트. 해석과 사용 방법은 `docs/PLATFORM_EXPORT_MATRIX.md`.
환자 자료는 없다. 공개 정책 문서만 다룬다. NDA 문서(`docs/*SNUH*`)는 근거로 쓰지 않는다.

| 파일 | 내용 | 상태 |
|---|---|---|
| `workbook_v1_frozen.csv` | v1 코딩 30셀(6개 플랫폼 × D1–D5): 1차 코더, 2차 코더, 확정값, 2차 코더의 확신도, 근거 문서, 원문 발췌, 메모 | 동결. 수정하지 않는다 |
| `check_v1.py` | 동결본에서 κ와 일치율, 불일치 해소 방향, 확신도 분포, 모델 반출 입장, 근거 문서 목록을 다시 계산한다 | numpy만 필요 |
| `out/check_v1.md` | 위 스크립트의 출력(2026-10-12). 발표된 κ 0.77 [0.61, 0.92]를 재현했다 | 재생성 가능 |
| `update_layer_2026-10.csv` | 2025–26 갱신층 16행. 근거 문서, 표시된 날짜, 이번에 직접 확인했는지 | 잠정. 이중 코딩 전 |

## 동결본의 출처

`workbook_v1_frozen.csv`는 공개 저장소 `safe-model-bundle/poc/policy_audit_workbook.csv`(커밋 `9a547e5`)의 바이트 사본이다.

```
sha256  17af04fe3221443428668b9f50f2df7b320012d5a3bf30c8ca337acf6345baa5
```

`check_v1.py`는 이 해시가 다르면 실패로 끝난다. 병합본 `policy_audit_codings.csv`(κ 계산 입력)는 공개 저장소에서 gitignore이고 sha256은 `ac8adf99e3f023ea3e215832e9e88a45ba0a363e947289f08d9889496a3334d3`이다. 원래 κ 스크립트(`safe-model-bundle/poc/kappa_policy_audit.py`)가 같은 숫자(0.774 [0.606, 0.922])를 낸다.

## 열쇠

- 열 `coder_HY`는 1차 코더(연구책임자), `coder_JL`은 2차 코더이고 서로 모르는 상태에서 코딩했다. `reconciled_Table1`은 근거 원문을 함께 다시 읽고 확정한 값이다.
- 열 `confidence`는 2차 코더가 코딩할 때 적은 값이고 해소 뒤에 다시 매기지 않았다(분포 12/10/8이 2차 코더의 확인요청 2026-08-19와 같다).
- 근거 문서 번호 `S5-nn`의 제목은 `out/check_v1.md` 5절에 있다. 문서별 URL, 접속일, 파일 해시는 저장소에 없다(플랫폼 수준 URL과 접속일 2026-06-07만 S1 File S3에 있다).

## 원 자료의 위치

- 2차 코딩 지시서, 발췌 워크북, 코더 시트, 확인요청: `Archive/second_coder_2026-08/`
- PLOS ONE 투고본(단독 코딩판)과 반려 의견: `Archive/manuscript_versions/manuscript_reconstructed_from_docx_REJECT.md`, `Archive/PLOS_ONE_2026-08/REJECT/`
- PLOS ONE S1 File(UK Biobank 사건, 국가 간 이동 절): `Archive/supplement_versions/S1_File_supplement.docx`
- 코딩북, 출처표, κ 표(HIR판): `Supplement/S1_File_supplement.md` S3·S4
- HIR판 Table 1: `Manuscript/manuscript.md`

## 갱신층을 읽는 법

`update_layer_2026-10.csv`의 `verification_2026_10_12`가 "read through the fetch tool"인 행만 2026-10-12에 Claude가 해당 페이지를 직접 열었다. 가져오기 도구는 작은 모델이 페이지를 읽고 답한 결과를 돌려주므로 인용은 논문에 쓰기 전에 페이지에서 다시 확인한다. "agent-read only"는 문헌조사 에이전트가 읽은 것이고 Claude가 열지 않았다. 갱신층의 분류(prohibited, conditional 등)는 코딩이 아니라 읽은 내용의 요약이다.
