# 전체 시스템 파이프라인 (System Pipeline)

> **개정 이력**: 최초 버전은 저장소에 코드가 없어 Notion 기록만으로 추정 작성했습니다. 이후 팀이 실제 코드 3종(`src/posture_feedback/{benchpress,deadlift,unified}/`)을 제공해, 이번 버전은 그 코드를 직접 읽고 검증한 내용으로 갱신했습니다. **`squat` 전용 스크립트와 `deadlift_feedback_v2_CLEAN.py`가 의존하는 `realtime_compare_side.py`/`feedback_overlay.py`는 여전히 이 저장소에 없습니다** — 아래 내용 중 이 두 파일에 의존하는 부분은 코드로 검증하지 못했습니다.

## 1. 실행 가능한 두 갈래 구조

코드를 확인한 결과, "하나의 통일된 파이프라인"이 아니라 **서로 다르게 구현된 두 갈래**가 존재합니다.

### 갈래 A — `unified_feedback_v4.py` (자기완결형, 3종목 지원)

외부 모듈 없이 단독으로 squat/deadlift/benchpress 3종목을 모두 처리합니다. `--exercise squat|deadlift|benchpress|bench|sq|dl|bp`, `--all` CLI를 지원합니다(`normalize_exercise_name()`으로 별칭 처리 — 과제에서 언급한 `bench` alias가 **실제로 존재함을 코드로 확인**했습니다).

### 갈래 B — 종목별 단독 스크립트 (`benchpress_feedback_v4.py`, `deadlift_feedback_v2_CLEAN.py`)

각 운동마다 별도 파일로 작성되어 있고, 서로 다른 threshold·계산식을 씁니다([`thresholds.md`](./thresholds.md), [`exercise_metrics.md`](./exercise_metrics.md) 참고). `deadlift_feedback_v2_CLEAN.py`는 자체 로직 없이 `realtime_compare_side.py`(as `rt`), `feedback_overlay.py`(as `fo`)를 import해서 동작하도록 되어 있는데, **이 두 파일이 저장소에 없어 현재 상태로는 실행할 수 없습니다.**

두 갈래는 통합되지 않은 상태이며, 이것이 2학기 P0 과제 중 하나입니다([`second_semester_plan.md`](./second_semester_plan.md)).

## 2. 갈래 A(`unified_feedback_v4.py`) 실제 처리 흐름

과제에서 제시한 11단계와 대응시키면 다음과 같습니다. 함수명은 모두 `src/posture_feedback/unified/unified_feedback_v4.py` 기준입니다.

| 단계 | 설명 | 실제 구현 |
|---|---|---|
| 1 | 영상 입력 | `process_exercise()`가 `VIDEO_CONFIG[exercise]`의 사용자/전문가 영상 경로를 읽음. `open_video_normalized()`가 `ffprobe`로 회전 메타데이터를 확인해 세로 영상을 보정 |
| 2 | pose landmark 추출 | `create_landmarker()` (MediaPipe Tasks `PoseLandmarker`, `num_poses=2`) → `extract_all_landmarks()`. 여러 명이 잡히면 `PersonSelector`가 운동 주체를 선택(벤치는 척추 수평 여부, 그 외는 크기+직전 프레임과의 근접성 기준) |
| 3 | landmark 저장 | `LandmarkSmoother`(EMA)로 스무딩 → 전문가 영상은 `frame_idx/timestamp_ms/side/landmarks/metrics` 구조의 JSON으로 저장(`save_expert_profile`). 스키마 상세는 [`pose_landmarks_and_csv.md`](./pose_landmarks_and_csv.md) |
| 4 | 전문가 기준 지표 계산 | `build_expert_profile()`이 JSON이 없으면 전문가 영상을 전처리해 `compute_metrics()`로 지표를 계산하고 캐시 저장. JSON이 있으면 그대로 로드(재계산 없음) |
| 5 | 사용자 지표 계산 | 동일한 `compute_metrics()`를 사용자 프레임에도 적용 |
| 6 | smoothing | landmark 좌표 자체는 `LandmarkSmoother`(EMA, alpha 0.35/0.30)로 안정화됨. 지표 값 자체에 대한 별도 window-average는 확인되지 않음 |
| 7 | rule 적용 → 오류 판단 | `choose_issue()`: ①`DELTA_THRESHOLDS` 기반 전문가-사용자 차이 판정(단, `ADVISORY_METRICS`는 제외) ②`ABSOLUTE_RULES` 기반 phase별 절대 기준 판정. 두 종류의 `Issue` 후보를 모아 `severity`(threshold 대비 초과 비율) 최댓값 하나만 채택 |
| 8 | rule 위반 우선 출력 | `FeedbackStabilizer`가 동일 `issue.key`가 `min_frames=3`회 이상 연속되어야 화면에 반영하고, 사라진 뒤에도 `hold_frames=9`프레임 동안 유지(깜빡임 방지). **여러 rule이 동시에 위반되면 `severity`가 가장 큰 것 하나만 표시**하는 방식으로 "우선순위"가 구현되어 있음 |
| 9 | 전문가와 차이 비교(rule 불명확 시) | 별도의 "불명확할 때만" 분기는 없고, **모든 프레임에서 항상 델타 비교(7번)와 절대 기준 판정을 함께 수행**한 뒤 severity로 우선순위를 매기는 단일 로직으로 처리됨. 과제가 상정한 "1차 rule, 2차 비교"라는 2단계 순차 구조와는 다름 |
| 10 | 시각화 | `draw_skeleton`, `draw_angle_arc`(관절 중심 true arc), `draw_trunk_corridor`, `draw_bar_proxy_layer`, `draw_wrist_elbow_guide`, `draw_hud` 등. USER + EXPERT skeleton + HUD 3분할 레이아웃 |
| 11 | 결과 저장 | `cv2.VideoWriter`로 `output/{exercise}_unified_feedback_v4.mp4` 저장 |

## 3. 실제 코드 파일 (저장소 반영 완료)

| 파일 | 위치 | 종목 | 비고 |
|---|---|---|---|
| `unified_feedback_v4.py` | `src/posture_feedback/unified/` | squat, deadlift, benchpress | 자기완결형. 내부 `version` 문자열은 `"unified_feedback_v2"`로 되어 있어 파일명과 불일치(팀 확인 필요) |
| `benchpress_feedback_v4.py` | `src/posture_feedback/benchpress/` | benchpress | 단독 실행. `expert_benchpress.json` 필수(자동 생성 안 함) |
| `expert_benchpress.json` | `src/posture_feedback/benchpress/` | benchpress | 215프레임 실제 전처리 결과 샘플. `benchpress_feedback_v4.py`와 `unified_feedback_v4.py` 양쪽이 참조 가능한 스키마 |
| `deadlift_feedback_v2_CLEAN.py` | `src/posture_feedback/deadlift/` | deadlift | **`realtime_compare_side.py`, `feedback_overlay.py` 없이는 실행 불가** |

## 4. 아직 저장소에 없는 파일 (2학기/추가 확인 필요)

| 파일 | 필요한 이유 | 확인 방법 |
|---|---|---|
| `realtime_compare_side.py`, `feedback_overlay.py` | `deadlift_feedback_v2_CLEAN.py`가 import해서 사용 | 팀이 보유 중이면 추가 제공 필요 |
| squat 전용 스크립트(`squat_feedback_v5_UPGRADE` 계열) | `deadlift_feedback_v2_CLEAN.py`의 docstring에 "squat_feedback_v5_UPGRADE.ipynb를 변환했다"고 명시되어 있어 원본이 존재하는 것으로 보이나 미제공 | 팀이 보유 중이면 추가 제공 필요 |
| `pose_landmarker_lite.task` | 세 코드 모두 실행에 필수인 MediaPipe 모델 파일 | [`requirements.txt`](../requirements.txt) 안내에 따라 별도 다운로드 |
| 원본 영상 파일(`user_*.mp4`, `expert_*.mp4`) | 실행에 필요하나 개인정보 이슈로 저장소에 커밋하지 않음 | [`data/README.md`](../data/README.md) 참고 |
| 종목 인식(ST-GCN/TCN/CTR-GCN) 학습 코드, phase 분류 코드, RepCounter 코드 | Notion 회의록에 다수 언급되었으나 실제 파일은 아직 미제공 | [`experiments_and_results.md`](./experiments_and_results.md) 참고 |

## 5. Colab / 로컬 실행 구분

세 파일 모두 **로컬(VS Code) 실행 전용**으로 작성되어 있습니다. `deadlift_feedback_v2_CLEAN.py`의 상단 주석에 Colab 전용 코드(Google Drive mount, `!pip install`, `!apt-get install fonts-nanum`)를 명시적으로 제거했다고 기록되어 있습니다. 세 파일 모두 코드 내부에 `pip install`/`apt install`/`wget` 등 자동 설치 구문은 없습니다(설치 안내는 docstring 주석에만 있음).

관련 문서: [`../README.md`](../README.md), [`exercise_metrics.md`](./exercise_metrics.md), [`thresholds.md`](./thresholds.md), [`pose_landmarks_and_csv.md`](./pose_landmarks_and_csv.md), [`second_semester_plan.md`](./second_semester_plan.md)
