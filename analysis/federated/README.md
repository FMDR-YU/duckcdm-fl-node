# analysis/federated — 연합학습 arm (NVIDIA FLARE)

가상 3개 기관에서 FLARE로 수평 연합 XGBoost(histogram 기반)를 돌려, 같은 XGBoost 설정의 중앙·기관별·예측평균과 비교한다. 비열등 기준은 EGRESS 프로토콜과 같은 ΔAUROC > −0.02.

| arm | 내용 |
|---|---|
| A_x | 중앙: 훈련 행을 모아 XGBoost 하나 |
| B_k | 기관별: 자기 행만으로 XGBoost |
| B_avg | 세 기관 모델 예측의 평균 (EGRESS의 B_comb, 연합학습이 아님) |
| F | 연합: FLARE `XGBHorizontalRecipe`, 행은 기관 밖으로 나가지 않고 히스토그램 통계만 오간다 |

네 arm이 모델 종류와 하이퍼파라미터를 공유한다. 소프트 보팅 4모델 앙상블은 연합 집계가 안 되므로 연합 비교는 이 XGBoost 단일 모델로 한다.

## 왜 컨테이너인가

- Windows용 xgboost 휠은 연합 통신 모듈 없이 빌드되어 있다(`xgboost.build_info()['USE_FEDERATED']`가 False). Linux 휠은 True. 그래서 F arm은 Linux 이미지에서만 돈다. 나머지 arm은 어디서나 돈다(`--skip-fl`).
- xgboost는 3.2.0 고정이다. nvflare 2.9.0은 `xgboost<3.4`를 요구하고, 3.3부터 `DataSplitMode`가 `xgboost._typing`으로 옮겨져 FLARE 직렬화 허용목록(`xgboost.core.DataSplitMode`)에 걸린다.
- 컨테이너는 `--network none`이며 `analysis`(읽기 전용), `data/ckd_pilot`(읽기 전용), `data/federated`와 `analysis/federated/out`(쓰기)만 본다. 나머지 `data/`는 보이지 않는다.
- Docker Desktop은 Claude 셸이 아니라 사용자 터미널에서 켠다(Claude 셸에서 켜면 backend가 소켓 파일을 못 지워 죽는다).

## 실행

이미지는 한 번만 만든다.

    docker build -t snuh-fl-flare:0.1 "<repo>\analysis\federated"

사이트 파일을 만들고 연합 실험을 돌린다(공개 SynPUF 대역).

    powershell -ExecutionPolicy Bypass -File "<repo>\analysis\federated\run.ps1" python make_sites.py --dataset synpuf --scenario B1 --seed 42
    powershell -ExecutionPolicy Bypass -File "<repo>\analysis\federated\run.ps1" python run_fl_xgb.py --dataset synpuf --scenario B1 --seed 42 --config plain

SNUH 자료는 IRB 면제번호가 나온 뒤, CDM 행렬(`matrix_snuh_cdm.parquet`)이 만들어지면 `--dataset snuh --tag cdm`으로 같은 두 줄을 돌린다.

| 파일 | 내용 |
|---|---|
| `Dockerfile`, `requirements-fl.txt` | 이미지 정의, 고정 버전 |
| `run.ps1` | 필요한 폴더만 마운트해 컨테이너에서 명령 실행 |
| `make_sites.py` | `pilot_lib.scenarios`의 B1/B2 사이트 정의로 `data/federated/<ds>/<scn>_s<seed>/site-k/{train,valid}.parquet`와 `manifest.json`(개수만) 작성 |
| `fl_data.py` | FLARE 클라이언트가 자기 폴더만 읽는 `XGBDataLoader` |
| `run_fl_xgb.py` | 네 arm 학습, 공통 검증셋 점수, F−A_x 부트스트랩 구간, `out/<ds>/fl_*.json` |

`--config plain`은 서브샘플링 없는 설정(100라운드)으로 F와 A_x가 거의 같아야 하는 시험이다. `--config krcp`·`leaky`·`regularized`는 파일럿의 세 XGBoost 변형이며(`xgb_krcp` 등), 하이퍼파라미터를 `pilot_lib._xgb_kwargs`에서 그대로 가져온다. 그래서 연합 모델과 파일럿의 중앙·기관별 모델이 같은 설정을 쓴다.

FLARE가 낸 전역 모델은 `data/federated/<ds>/<B1|B2>_s<seed>/F_xgb_<config>.model.json`으로 복사된다. 이 파일이 반출되는 산출물이고, 파일럿 `run_pilot.py --model xgb`가 이것을 읽어 효용 비교(H5)와 3-gate 심사에 넣는다(`analysis/snuh_pilot/README.md`의 모델 계열 절). 순서는 시드·시나리오·설정마다 `make_sites.py` + `run_fl_xgb.py`(컨테이너), 그다음 `run_pilot.py --model xgb`다. 추가 옵션: `--reexec`는 연합 작업을 새 작업공간에서 한 번 더 돌려 예측이 같은지 본다(Gate 3 대응), `--quick`은 빠른 행렬로 시험한다.

## 자료 규칙

- 사이트 파일, FLARE 작업공간(`data/federated/workspace/`), 학습된 모델은 환자 유래 파생물이므로 `data/`에만 둔다.
- `out/`에는 집계만 쓴다(AUROC·AUPRC, 11 미만 개수는 `<11`). 행·ID·원값은 쓰지 않고 오류는 예외 종류와 위치만 보인다(`pilot_lib.guard`).
- `scale_pos_weight`는 풀링한 훈련 라벨의 음성/양성 비율이다. 실제 연합에서는 기관별 양성·음성 개수를 합산하는 질의 한 번에 해당한다.

여러 실행을 한 표로 모으려면(`out/<ds>/SUMMARY.md`, 시드가 둘 이상이면 시드 평균과 t 구간도 낸다):

    python "<repo>\analysis\federated\summarize.py" synpuf

## 결과 (SynPUF 대역, 시드 42, 2026-10-10)

공통 검증셋 8,463명의 AUROC. NI는 F−A_x 구간의 하한이 −0.02보다 큰지 여부.

| 시나리오 | 설정 | A_x | 기관별 | B_avg | F | F − A_x [95% CI] | NI |
|---|---|---|---|---|---|---|---|
| B1 (균등 3기관) | plain | 0.8963 | 0.8908–0.8922 | 0.8971 | 0.8963 | −0.0000 [−0.0000, +0.0000] | 예 |
| B1 | krcp | 0.8938 | 0.8831–0.8864 | 0.8933 | 0.8932 | −0.0005 [−0.0019, +0.0008] | 예 |
| B1 | regularized | 0.8982 | 0.8934–0.8960 | 0.8977 | 0.8979 | −0.0003 [−0.0009, +0.0002] | 예 |
| B1 | leaky | 0.8789 | 0.8756–0.8770 | 0.8866 | 0.8777 | −0.0009 [−0.0019, +0.0000] | 예 |
| B2 (50/30/20%) | plain | 0.8963 | 0.8870–0.8922 | 0.8961 | 0.8963 | −0.0000 [−0.0000, +0.0000] | 예 |
| B2 | krcp | 0.8938 | 0.8824–0.8868 | 0.8939 | 0.8916 | −0.0022 [−0.0034, −0.0008] | 예 |

- plain(서브샘플링 없음): F와 A_x의 예측 차이는 최대 1.2×10⁻⁷(float32 반올림 수준)이고 AUROC 차이는 10⁻¹⁶이다. 연합 히스토그램 학습은 풀링 학습과 같은 모델을 만든다. 세 기관이 받은 모델도 서로 같다.
- krcp(행·열 80% 추출): 기관별 행 추출이 달라 모델은 같지 않지만(예측 상관 0.994) F − A_x는 B1 −0.0005, B2 −0.0022로 비열등 기준 −0.02에 한참 못 미친다. B2 구간은 0을 포함하지 않는다. 시드 하나이므로 10시드에서 다시 본다.
- 기관별 단독 모델은 중앙보다 0.003–0.011 낮고 B2에서는 작은 기관일수록 낮다. 세 기관 예측평균은 중앙과 같은 수준이다.
- regularized(깊이 4, 300라운드)와 leaky(깊이 12, 1,000라운드, 서브샘플링 없음)도 비열등 기준을 만족한다(B1, 시드 42). leaky에서는 과적합된 중앙 모델(A_x 0.879)보다 기관별 모델의 예측평균(B_avg 0.887)이 높다. 분산을 줄이는 평균의 효과이고, 연합 모델 F(0.878)는 중앙 모델을 따라간다.
- 소요(B1, 시드 42, WSL2 22 vCPU, 시뮬레이터, 중앙·기관별 학습과 부트스트랩 포함): regularized 136초, krcp 270초, leaky 1,027초(약 17분). 3기관 100라운드(plain)는 약 1분. `--reexec`는 연합 작업을 한 번 더 돌리므로 그 작업은 시간이 두 배가 된다(일괄 실행기는 첫 시드에만 쓴다). 중앙 학습은 1초 미만. leaky 컨테이너는 최대 약 7 GiB 메모리를 썼다.
- SynPUF 대역의 AUROC는 SNUH 실데이터(KRCP v1.3 약 0.93)와 다르다. 논문 수치는 SNUH CDM 행렬로 다시 낸다.

## T0: 노드를 나눈 운영 구성 (SynPUF 대역, B1 시드 42, plain, 2026-10-10)

시뮬레이터는 서버와 클라이언트를 한 컨테이너 안의 프로세스로 돌려서 "집계 노드는 자료를 못 보고 기관끼리 닿지 않는다"를 보여 주지 못한다. T0는 같은 작업을 운영 모드(FLARE 시작 키트, 상호 TLS)로 컨테이너 5개에 나눠 돌린다(`t0/`).

| 컨테이너 | 마운트 | 네트워크 |
|---|---|---|
| `t0-server1` (집계) | 자기 키트만 | 기관 네트워크 3개와 제어망에 연결, IP 전달 끔 |
| `t0-site-k` (기관) | 자기 키트 + 자기 사이트 폴더(읽기 전용) | 자기 internal 네트워크 하나 |
| `t0-admin` (연구자) | 키트 + 코드(읽기 전용), 자료 없음 | 제어망 |

실행(Docker를 켠 뒤, 약 2분):

    python "<repo>\analysis\federated\t0\t0.py" all --dataset synpuf --scenario B1 --seed 42 --config plain

`t0.py`가 `nvflare provision`으로 키트를 만들고, 각 기관이 `local/resources.json`의 `class_allow_list`에 자기 로더(`fl_data.ParquetSiteLoader`)를 넣은 뒤(운영 키트는 허용 목록을 강제한다), 컨테이너를 올리고, 관리자 컨테이너에서 작업을 제출하고, 점검한 뒤 모두 내린다. 점검 결과는 `out/t0/t0_check.json`(집계만).

| 점검 | 결과 |
|---|---|
| 집계 컨테이너의 마운트 | `/fl/server1`만. `/data` 없음, parquet·행렬 파일 0개, IP 전달 0 |
| 기관 컨테이너가 보는 자료 | 자기 폴더 하나(`site-k`: train, valid)뿐 |
| 기관 → 집계 | 연결됨(상호 TLS) |
| 기관 → 다른 기관 | 이름 해석 불가, IP는 ENETUNREACH |
| 기관 → 인터넷 | ENETUNREACH |
| 작업 | 약 1분 정상 종료. 세 기관이 가진 모델 파일이 바이트 단위로 같음 |
| 내보낸 모델 | 시뮬레이터의 연합 모델과 예측 차이 0, 검증 AUROC 0.8963(중앙 모델과 같음) |
| 통신량 | 기관당 수신 47.1 MB / 송신 47.9 MB, 집계 144 / 148 MB (100라운드, 등록·하트비트 포함) |

이 구성에서 기관 밖으로 나가는 것은 최종 모델과 학습 통계(그래디언트·헤시안 히스토그램, 분위수 요약)뿐이다. 학습 통계는 TLS로 집계 노드를 거치며 암호화 집계는 아니다. 같은 노트북 안의 컨테이너이므로 물리적 분리가 아니라 Docker internal 네트워크에 기댄 분리다.

## 한계

- SimEnv는 서버와 클라이언트를 한 컨테이너 안의 프로세스로 돌린다. 노드를 나눈 구성은 T0에서 따로 시험했고(위), 시뮬레이터와 같은 모델이 나왔다. 대규모 일괄 실행(`run_batch.ps1`)은 시뮬레이터로 한다.
- 오가는 것은 그래디언트·헤시안 히스토그램 합과 분위수 요약이다. 암호화 집계(`secure=True`)는 플러그인이 없어 쓰지 않았다. 이 중간 통계에 대한 멤버십 추론 감사는 하지 않았고, 3-gate는 반출되는 최종 모델에만 걸린다. plain 설정에서는 최종 모델이 중앙 모델과 같으므로 Gate 2 위험도 같다.
- 라운드 수 고정(100, 500), 조기 종료 없음, 하이퍼파라미터 조정 없음. 기관별 `valid.parquet`은 모니터링 전용이다.
- `scale_pos_weight`는 풀링한 훈련 라벨에서 계산했다. 실제 연합에서는 기관별 양성·음성 수를 합산하는 질의 한 번이다.
- 시드 1개, 데이터 대역 1종.
