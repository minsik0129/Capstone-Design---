# 전체 시스템 파이프라인 (System Pipeline)

> **개정 이력**: 최초 버전은 저장소에 코드가 없어 Notion 기록만으로 추정 작성했습니다. 이후 팀이 실제 코드를 순차적으로 제공해(1차: benchpress/deadlift/unified 3종, 2차: `phase_labeling.py`, `realtime_compare_side.py`, `feedback_overlay.py`), 이번 버전은 그 코드를 직접 읽고 검증한 내용으로 갱신했습니다. **squat 전용 스크립트와 ST-GCN 등 학습 코드는 여전히 이 저장소에 없습니다**(ST-GCN은 다른 팀원 담당이라 아직 제공되지 않음). `pose_landmarker_lite.task`는 크기·정책상 저장소에 커밋하지 않았습니다(6절 참고).

## 1. 실행 가능한 세 갈래 구조

코드를 모두 확인한 결과, "하나의 통일된 파이프라인"이 아니라 **서로 다른 시기에 서로 다르게 구현된 세 갈래**가 존재합니다.

### 갈래 A — `unified_feedback_v4.py` (자기완결형, 3종목 지원)

외부 모듈 없이 단독으로 squat/deadlift/benchpress 3종목을 모두 처리합니다. `--exercise squat|deadlift|benchpress|bench|sq|dl|bp`, `--all` CLI를 지원합니다(`normalize_exercise_name()`이 별칭을 모두 `"benchpress"`/`"squat"`/`"deadlift"`로 정규화). 전문가 JSON이 없으면 **자동으로 전처리해서 생성**합니다.

### 갈래 B — 벤치프레스 단독 스크립트 (`benchpress_feedback_v4.py`)

벤치프레스 전용. 외부 모듈 의존 없음. 전문가 JSON은 **사전에 준비되어 있어야** 하며 자동 생성하지 않습니다.

### 갈래 C — `deadlift_feedback_v2_CLEAN.py` + `realtime_compare_side.py` + `feedback_overlay.py`

`squat_feedback_v5_UPGRADE.ipynb`(스쿼트용 원본 노트북, 이 저장소에는 아직 없음)에서 파생된 계열로, 구조상 squat/deadlift/bench 3종을 모두 지원하도록 설계되어 있지만 현재는 `EXERCISE = 'deadlift'`로 고정되어 있습니다. `realtime_compare_side.py`(as `rt`)와 `feedback_overlay.py`(as `fo`) 두 모듈을 import해서 동작합니다 — 이번에 두 파일 모두 저장소에 반영되었지만, **아래 2절에서 설명하는 JSON 스키마 불일치로 인해 여전히 실제 실행은 되지 않습니다.**

세 갈래는 통합되지 않았고, 서로 다른 threshold·계산식·smoothing 알고리즘·종목명 표기(`benchpress` vs `bench`)를 씁니다([`thresholds.md`](./thresholds.md), [`exercise_metrics.md`](./exercise_metrics.md) 참고). 이를 하나로 합치는 것이 2학기 P0 과제입니다([`second_semester_plan.md`](./second_semester_plan.md)).

## 2. 중요한 미해결 비호환: 전문가 JSON `total_frames` 필드

`realtime_compare_side.py`의 `load_expert()`는 다음과 같이 JSON을 읽습니다.

```python
data['total_frames']   # 없으면 KeyError로 즉시 실패
data['fps']
data['frames']
```

반면 `unified_feedback_v4.py`의 `save_expert_profile()`이 생성하는 JSON(예: `src/posture_feedback/benchpress/expert_benchpress.json`)의 최상위 키는 `version`, `fps`, `source_video`, `frames`뿐이며 **`total_frames`가 없습니다.** 즉:

- `unified_feedback_v4.py`로 만든 전문가 JSON을 `deadlift_feedback_v2_CLEAN.py`(→`rt.load_expert()`)에 그대로 넣으면 `KeyError: 'total_frames'`로 실패합니다.
- 반대로 `expert_deadlift.json`을 `rt.load_expert()`가 기대하는 형식(`total_frames` 포함)으로 직접 준비하면 `deadlift_feedback_v2_CLEAN.py` 자체는 동작할 가능성이 있으나, 이번 조사에서는 검증하지 못했습니다.

**2학기 해결 방법 후보**: ①`rt.load_expert()`를 `data.get('total_frames', len(data['frames']))`처럼 방어적으로 수정 ②JSON 생성 스크립트(`save_expert_profile`)가 `total_frames` 필드도 함께 쓰도록 수정 ③아예 하나의 JSON 스키마로 통일. 셋 중 어느 것도 이번 문서화 작업에서는 코드를 임의로 고치지 않았습니다(팀 확인 없이 동작을 바꾸지 않기 위함).

## 3. 갈래 A(`unified_feedback_v4.py`) 실제 처리 흐름

과제에서 제시한 11단계와 대응시키면 다음과 같습니다. 함수명은 모두 `src/posture_feedback/unified/unified_feedback_v4.py` 기준입니다.

| 단계 | 설명 | 실제 구현 |
|---|---|---|
| 1 | 영상 입력 | `process_exercise()`가 `VIDEO_CONFIG[exercise]`의 사용자/전문가 영상 경로를 읽음. `open_video_normalized()`가 `ffprobe`로 회전 메타데이터를 확인해 세로 영상을 보정 |
| 2 | pose landmark 추출 | `create_landmarker()` (MediaPipe Tasks `PoseLandmarker`, `num_poses=2`) → `extract_all_landmarks()`. 여러 명이 잡히면 `PersonSelector`가 운동 주체를 선택(벤치는 척추 수평 여부, 그 외는 크기+직전 프레임과의 근접성 기준) |
| 3 | landmark 저장 | `LandmarkSmoother`(EMA)로 스무딩 → 전문가 영상은 `frame_idx/timestamp_ms/side/landmarks/metrics` 구조의 JSON으로 저장(`save_expert_profile`, `total_frames` 필드는 쓰지 않음 — 2절 참고). 스키마 상세는 [`pose_landmarks_and_csv.md`](./pose_landmarks_and_csv.md) |
| 4 | 전문가 기준 지표 계산 | `build_expert_profile()`이 JSON이 없으면 전문가 영상을 전처리해 `compute_metrics()`로 지표를 계산하고 캐시 저장. JSON이 있으면 그대로 로드(재계산 없음) |
| 5 | 사용자 지표 계산 | 동일한 `compute_metrics()`를 사용자 프레임에도 적용 |
| 6 | smoothing | landmark 좌표 자체는 `LandmarkSmoother`(EMA, alpha 0.35/0.30)로 안정화됨. 지표 값 자체에 대한 별도 window-average는 확인되지 않음 |
| 7 | rule 적용 → 오류 판단 | `choose_issue()`: ①`DELTA_THRESHOLDS` 기반 전문가-사용자 차이 판정(단, `ADVISORY_METRICS`는 제외) ②`ABSOLUTE_RULES` 기반 phase별 절대 기준 판정. 두 종류의 `Issue` 후보를 모아 `severity`(threshold 대비 초과 비율) 최댓값 하나만 채택 |
| 8 | rule 위반 우선 출력 | `FeedbackStabilizer`가 동일 `issue.key`가 `min_frames=3`회 이상 연속되어야 화면에 반영하고, 사라진 뒤에도 `hold_frames=9`프레임 동안 유지(깜빡임 방지). **여러 rule이 동시에 위반되면 `severity`가 가장 큰 것 하나만 표시**하는 방식으로 "우선순위"가 구현되어 있음 |
| 9 | 전문가와 차이 비교(rule 불명확 시) | 별도의 "불명확할 때만" 분기는 없고, **모든 프레임에서 항상 델타 비교(7번)와 절대 기준 판정을 함께 수행**한 뒤 severity로 우선순위를 매기는 단일 로직으로 처리됨 |
| 10 | 시각화 | `draw_skeleton`, `draw_angle_arc`(관절 중심 true arc), `draw_trunk_corridor`, `draw_bar_proxy_layer`, `draw_wrist_elbow_guide`, `draw_hud` 등. USER + EXPERT skeleton + HUD 3분할 레이아웃 |
| 11 | 결과 저장 | `cv2.VideoWriter`로 `output/{exercise}_unified_feedback_v4.mp4` 저장 |

## 4. 데이터 준비(전처리) 단계 — `phase_labeling.py`

Notion에만 언급되어 있던 phase 라벨링 도구의 실제 코드가 이번에 확인되었습니다(`src/preprocessing/phase_labeling.py`). Tkinter GUI로 영상을 재생하며 Start/Bottom/Finish 프레임을 사람이 직접 지정하고, `phase_labels.csv`(컬럼: `type`, `name`, `count`, `L1`, `L2`, `L3`, ...)로 저장합니다. 기대하는 원본 폴더 구조는 `측면_수정본/{benchpress,squat,deadlift}/*.mp4`입니다 — [`dataset.md`](./dataset.md), [`pose_landmarks_and_csv.md`](./pose_landmarks_and_csv.md)에서 이 스키마를 데이터셋 문서와 연결합니다. 이 도구는 종목 인식·자세 피드백 코드와는 별개로, 라벨 생성 전용입니다.

## 5. 실제 코드 파일 (저장소 반영 완료)

| 파일 | 위치 | 종목 | 비고 |
|---|---|---|---|
| `unified_feedback_v4.py` | `src/posture_feedback/unified/` | squat, deadlift, benchpress | 자기완결형. 내부 `version` 문자열은 `"unified_feedback_v2"`로 되어 있어 파일명과 불일치 |
| `benchpress_feedback_v4.py` | `src/posture_feedback/benchpress/` | benchpress | 단독 실행. `expert_benchpress.json` 필수(자동 생성 안 함) |
| `expert_benchpress.json` | `src/posture_feedback/benchpress/` | benchpress | 215프레임 실제 전처리 결과 샘플 |
| `deadlift_feedback_v2_CLEAN.py` | `src/posture_feedback/deadlift/` | squat/deadlift/bench(구조상), 현재 deadlift로 고정 | import는 이제 성공하지만 JSON `total_frames` 불일치로 실행은 안 됨(2절) |
| `realtime_compare_side.py` | `src/posture_feedback/deadlift/` | squat, pushup(원래 용도) | deadlift 스크립트가 함수만 재사용. 원래는 웹캠 실시간 데모(현재는 로컬 영상 파일로 하드코딩됨) + Anthropic Claude 기반 LLM 피드백 포함 |
| `feedback_overlay.py` | `src/posture_feedback/deadlift/` | squat, deadlift, pushup | 시각 오버레이 레이어 라이브러리. `class FeedbackRenderer`가 3번 재정의되어 있고 마지막 정의만 유효 |
| `phase_labeling.py` | `src/preprocessing/` | squat, benchpress, deadlift | Start/Bottom/Finish 라벨링 GUI 도구 |

## 6. 아직 저장소에 없는 것 (2학기/추가 확인 필요)

| 항목 | 필요한 이유 | 상태 |
|---|---|---|
| squat 전용 스크립트(`squat_feedback_v5_UPGRADE` 계열) | `deadlift_feedback_v2_CLEAN.py`가 파생된 원본. squat은 현재 `unified_feedback_v4.py`로만 실행 가능 | 미제공 |
| ST-GCN/TCN/CTR-GCN 등 종목 인식·phase 분류 학습 코드 | Notion 회의록에 다수 언급되었으나 코드 미제공 | **다른 팀원 담당 — 아직 보유하지 않음(팀 확인)** |
| `pose_landmarker_lite.task` | 모든 자세 피드백 코드 실행에 필수인 MediaPipe 모델 파일 | 팀이 파일을 제공했으나, 대용량 바이너리 커밋 지양 원칙에 따라 저장소에는 커밋하지 않음. 공식 다운로드 URL이 `realtime_compare_side.py`의 `_MODEL_URL` 상수로 코드에 남아 있음: `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task` |
| 원본 영상 파일(`user_*.mp4`, `expert_*.mp4`) | 실행에 필요하나 개인정보 이슈로 저장소에 커밋하지 않음 | [`data/README.md`](../data/README.md) 참고 |

## 7. Colab / 로컬 실행 구분

모든 파일이 **로컬(VS Code) 실행 전용**으로 작성되어 있습니다. `deadlift_feedback_v2_CLEAN.py`의 상단 주석에 Colab 전용 코드(Google Drive mount, `!pip install`, `!apt-get install fonts-nanum`)를 명시적으로 제거했다고 기록되어 있습니다. 코드 내부에 `pip install`/`apt install`/`wget` 등 자동 설치 구문은 없습니다(설치 안내는 docstring 주석에만 있음). `realtime_compare_side.py`의 `ensure_model()`만 예외적으로 `urllib.request.urlretrieve()`로 모델 파일을 자동 다운로드하는 로직을 갖고 있습니다(단, `deadlift_feedback_v2_CLEAN.py`가 이 함수를 호출하려면 `rt.ensure_model(MODEL_PATH)`을 거쳐야 하므로 간접적으로 재사용 가능).

관련 문서: [`../README.md`](../README.md), [`exercise_metrics.md`](./exercise_metrics.md), [`thresholds.md`](./thresholds.md), [`pose_landmarks_and_csv.md`](./pose_landmarks_and_csv.md), [`second_semester_plan.md`](./second_semester_plan.md)
