# Capstone Design - CUK

MediaPipe와 ST-GCN을 활용한 3대 운동 인식·횟수 카운팅·자세 피드백 시스템

---

> **저장소 현황 안내**
> 문서화 작업 시작 시점에 GitHub 저장소에는 실제 소스 코드·데이터·결과 영상이 커밋되어 있지 않았습니다(README 2줄짜리 초기 커밋만 존재). 아래 내용은 1차로 팀이 1학기 동안 Notion에 기록한 회의록(20건)과 기술 문서(13건), 요구사항/발표 자료를 근거로 정리했고, 이후 팀이 실제 코드 3종(벤치프레스/데드리프트/통합)을 제공해 `src/posture_feedback/`에 반영했습니다. **여전히 스쿼트 전용 스크립트, 데드리프트 스크립트가 의존하는 일부 모듈, 학습 코드 등은 저장소에 없습니다** — 자세한 현황은 [`docs/system_pipeline.md`](docs/system_pipeline.md) 4절 참고. 2학기 최우선 과제는 나머지 코드 이관과 코드 파일 간 threshold/계산식 통일입니다 — [`docs/second_semester_plan.md`](docs/second_semester_plan.md) 참고.

## 1. 프로젝트 소개

### 시작한 이유 / 해결하려는 문제

헬스에 대한 관심은 많지만 동기부여 부족으로 오래 지속하기 어렵고, 잘못된 자세로 인한 부상 위험이 있습니다. 이 프로젝트는 운동 영상을 자동으로 분석해 기록을 남기고, 자세를 텍스트뿐 아니라 시각 자료로 직관적으로 설명하는 것을 목표로 합니다 (PRD).

### 대상 운동

`squat`(스쿼트) · `benchpress`(벤치프레스) · `deadlift`(데드리프트) 3대 운동. 벤치프레스는 코드/문서에서 `benchpress`로 표기를 통일합니다. `unified_feedback_v4.py`의 `normalize_exercise_name()`을 코드로 확인한 결과, CLI에서 `bench`/`sq`/`dl`/`bp`도 각각 `benchpress`/`squat`/`deadlift`/`benchpress`로 정규화되는 **별칭(alias)이 실제로 존재**합니다. 다만 파일명·내부 딕셔너리 키는 항상 `benchpress`로 통일되어 있고, `bench`는 CLI 입력 편의를 위한 별칭일 뿐입니다.

### 최종 목표

사용자 운동 영상에서 ①종목 인식 ②반복 횟수 카운팅 ③전문가 영상과의 자세 비교 ④시각적 피드백 제공을 하나의 시스템으로 통합하는 것입니다.

## 2. 주요 기능 (1학기 종료 시점 상태)

| 기능 | 상태 | 근거 |
|---|---|---|
| 운동 종목 인식 | 구현 및 실험 (ST-GCN 실측 accuracy 92.31%, 실제 영상 재검증에서 일부 오분류 발생) | 종목 인식 및 횟수 기록 |
| phase 기반 횟수 카운팅 | 실험 진행 (binary mask v1 실패 → Gaussian density v2 → 실시간 valley 기반 도입) | 0505, 0602 |
| 스쿼트 자세 피드백 | 구현 (`unified_feedback_v4.py`가 처리. 전용 단독 스크립트는 아직 미제공) | `src/posture_feedback/unified/`, 0526 |
| 벤치프레스 자세 피드백 | 구현 (단독 스크립트 `benchpress_feedback_v4.py` + 통합 스크립트 2종 존재, 서로 threshold 다름) | `src/posture_feedback/benchpress/`, `docs/thresholds.md` |
| 데드리프트 자세 피드백 | 부분 구현 (`deadlift_feedback_v2_CLEAN.py`는 미제공 모듈 2개에 의존해 현재 실행 불가) | `src/posture_feedback/deadlift/`, `docs/system_pipeline.md` |
| 3개 운동 통합 | 구현 (`unified_feedback_v4.py`, 자기완결형 CLI. 실행 검증은 못함) | `src/posture_feedback/unified/` |
| YOLO 기반 바벨 검출 | 실험 완료, 성능 미달로 미채택 (2학기 재검토 후보) | 0611 "yolo 모델 검출" |

## 3. 전체 시스템 파이프라인

```text
Input Video
  → MediaPipe Pose Landmark Extraction (33 keypoints)
  → Landmark Preprocessing (위치/크기 정규화: 구현 완료, 좌우 side 잠금: 구현 완료, EMA smoothing: 구현 완료,
    카메라 회전 메타데이터 보정: 구현 완료, 전문가-사용자 화면 방향 정렬: 벤치프레스만 구현)
  → Exercise Recognition (ST-GCN, accuracy 92.31%)
  → Phase / Rep Analysis (phase 분류 + 실시간 valley 기반 카운팅)
  → Exercise-specific Posture Evaluation (threshold 기반 rule)
  → Expert Comparison (전문가 지표 대비 비교)
  → Visual Feedback (오버레이 13종: arc, HUD, depth line, phase 블록 등)
  → Output Video
```

각 단계의 실제 구현 상태와 근거는 [`docs/system_pipeline.md`](docs/system_pipeline.md)에 상세히 정리되어 있습니다.

## 4. 사용 기술

Notion에 명시적으로 언급된 기술만 기록합니다. 상세 근거는 [`docs/project_overview.md`](docs/project_overview.md) 참고.

- **포즈 추정**: MediaPipe Pose(33 keypoints, 메인 트랙), YOLOv8n-pose(COCO 17 keypoints, 비교 실험)
- **시계열/그래프 모델**: ST-GCN, TCN, CTR-GCN, Shift-GCN, 2s-AGCN
- **바벨 검출(실험)**: YOLO-World
- **실제 코드 import로 확인됨** (`src/posture_feedback/`): `mediapipe`(`mediapipe.tasks.python.vision`), `opencv-python`(`cv2`), `numpy`(`<2` 제약), `Pillow`(`PIL`)
- PyTorch는 ST-GCN/TCN/CTR-GCN 학습에 사실상 필요할 것으로 추정되나, 해당 학습 코드가 아직 저장소에 없어 import로 확인하지는 못했습니다.
- **LLM API 비교 검토(도입 여부 미정)**: OpenAI, Google Gemini, Anthropic Claude, xAI Grok, Cohere, DeepSeek

## 5. 저장소 구조

```text
Capstone-Design---/
├─ README.md
├─ requirements.txt        # src/posture_feedback/ 실제 import 기준으로 정리
├─ .gitignore
│
├─ docs/                    # 상세 기술 문서 (아래 "문서 목차" 참고)
├─ src/
│  └─ posture_feedback/
│     ├─ benchpress/        # benchpress_feedback_v4.py + expert_benchpress.json 샘플
│     ├─ deadlift/          # deadlift_feedback_v2_CLEAN.py (⚠ 의존 모듈 2개 미제공)
│     └─ unified/           # unified_feedback_v4.py (3종목 통합 CLI)
│     (preprocessing/ action_recognition/ rep_counting/ squat/ utils/ — 아직 코드 없음)
├─ notebooks/               # 2학기 실험 노트북 이관 예정 (현재 비어 있음)
├─ configs/                 # 2학기 threshold/하이퍼파라미터 설정 이관 예정 (현재 비어 있음)
├─ assets/                  # 그림/다이어그램/결과물 (현재 비어 있음, 업로드 원칙은 README 참고)
├─ data/                    # 데이터셋 구조 설명 (원본 영상은 미포함)
└─ archive/                 # 이전 버전 코드 보관용 (현재 옮길 파일 없음)
```

## 6. 문서 목차 (`docs/`)

| 문서 | 내용 |
|---|---|
| [`project_overview.md`](docs/project_overview.md) | 프로젝트 배경, 목표, 팀원 및 역할 |
| [`system_pipeline.md`](docs/system_pipeline.md) | 전체 파이프라인 단계별 구현 상태 |
| [`dataset.md`](docs/dataset.md) | 데이터셋 구성, split, 라벨링 이슈 |
| [`dataset_history.md`](docs/dataset_history.md) | 영상 개수 등 수치 변경 이력 및 불일치 해소 근거 |
| [`pose_landmarks_and_csv.md`](docs/pose_landmarks_and_csv.md) | landmark/CSV 저장 이유와 실제 확인된 스키마 |
| [`capture_guidelines.md`](docs/capture_guidelines.md) | 촬영 각도/방향 기준 |
| [`exercise_metrics.md`](docs/exercise_metrics.md) | 운동별 자세 지표와 계산 방식 |
| [`thresholds.md`](docs/thresholds.md) | threshold 값과 그 근거(경험적 초기값 vs 문헌+팀 판단) |
| [`experiments_and_results.md`](docs/experiments_and_results.md) | 1학기 실험 수치 전체 (종목인식/phase/횟수카운팅/YOLO 비교 등) |
| [`limitations.md`](docs/limitations.md) | 확인된 문제점과 한계 |
| [`second_semester_plan.md`](docs/second_semester_plan.md) | 2학기 우선순위별 계획 |

## 7. 데이터셋 (요약)

1학기 종료 시점(2026-06-11 기준) 총 **208개** 영상: squat 89 / benchpress 94 / deadlift 25. 과거 시점에는 209개(deadlift 26개)로 기록된 적이 있어, 정확한 변경 경위는 [`docs/dataset_history.md`](docs/dataset_history.md)에서 다룹니다. 원본 영상은 개인정보 포함 가능성으로 이 저장소에 업로드되어 있지 않으며, 구조와 사용 방법만 [`data/README.md`](data/README.md)에 문서화했습니다.

## 8. 운동별 자세 평가 (요약)

- **스쿼트**: 무릎 각도, 몸통 기울기(`TRUNK_LEAN_TOL_DEG=8.0`), squat depth 기준선, 무릎-발 정렬, 좌우 비대칭 — 구현
- **벤치프레스**: 팔꿈치 각도, `bench_line_diff`, bar proxy(손 위치 근사), 좌우 팔 비대칭 — 부분 구현 (바벨 실제 검출 아님)
- **데드리프트**: 고관절/무릎 락아웃 각도, 정강이 기울기, 등/목 정렬 — 부분 구현 (데이터 부족)

자세한 지표 정의와 threshold는 [`docs/exercise_metrics.md`](docs/exercise_metrics.md), [`docs/thresholds.md`](docs/thresholds.md)를 참고하십시오.

## 9. 실행 방법

**주의**: 아래는 실제 코드(`src/posture_feedback/`)를 읽고 확인한 CLI이지만, `pose_landmarker_lite.task` 모델 파일과 원본 영상이 이 저장소에 없어 **직접 실행해 검증하지는 못했습니다.**

```bash
pip install -r requirements.txt
```

준비물(모두 실행 스크립트와 같은 폴더에 필요, 이 저장소에는 미포함): `pose_landmarker_lite.task`, 사용자 영상, 전문가 영상 또는 전문가 JSON.

### 3종목 통합 실행 (`unified_feedback_v4.py`, 권장)

```bash
cd src/posture_feedback/unified
python unified_feedback_v4.py --exercise squat
python unified_feedback_v4.py --exercise deadlift
python unified_feedback_v4.py --exercise benchpress
python unified_feedback_v4.py --exercise bench   # bench는 benchpress의 CLI 별칭 (코드로 확인됨)
python unified_feedback_v4.py --all               # 3종목 모두 처리
```

전문가 JSON이 없으면 `VIDEO_CONFIG`에 지정된 전문가 영상에서 **자동으로 전처리**해 JSON 캐시를 생성합니다(별도 preprocess 스크립트 실행 불필요).

### 벤치프레스 단독 실행 (`benchpress_feedback_v4.py`)

```bash
cd src/posture_feedback/benchpress
# expert_benchpress.json이 이 폴더에 이미 포함되어 있음 (실제 전처리 결과 샘플, 215프레임)
# user_benchpress.mp4, pose_landmarker_lite.task를 준비한 뒤:
python benchpress_feedback_v4.py
```

이 스크립트는 `unified_feedback_v4.py`와 달리 **전문가 JSON을 자동 생성하지 않습니다.** JSON이 없으면 즉시 오류가 발생하므로, 반드시 JSON을 먼저 준비(원 팀 워크플로 기준 별도 preprocess)해야 합니다.

### 데드리프트 단독 실행 (`deadlift_feedback_v2_CLEAN.py`) — 현재 실행 불가

```bash
cd src/posture_feedback/deadlift
python deadlift_feedback_v2_CLEAN.py   # realtime_compare_side.py, feedback_overlay.py가 없어 import 단계에서 실패함
```

두 의존 모듈이 저장소에 추가되기 전까지는 데드리프트는 **`unified_feedback_v4.py --exercise deadlift`로만 실행 가능**합니다.

## 10. 결과 예시

이번 조사에서 실제 결과 이미지/영상 파일(confusion matrix, epoch-loss graph, 자세 피드백 결과 화면 등)은 GitHub 저장소나 접근 가능한 Notion 첨부파일에서 확보하지 못했습니다. 존재하지 않는 이미지에 대해 빈 링크를 만들지 않았습니다. 관련 수치는 [`docs/experiments_and_results.md`](docs/experiments_and_results.md)에 텍스트로 정리되어 있으며, 실제 이미지 파일이 확보되면 `assets/results/`에 추가하고 이 절에 링크하십시오.

## 11. 1학기 주요 결과

**구현한 내용**: MediaPipe 33 landmark 추출 파이프라인, ST-GCN 종목 인식(accuracy 92.31%), phase 분류 멀티태스크 모델, CTR-GCN 앙상블(Action F1 0.948), 실시간 valley 기반 횟수 카운팅(17fps), 시각 피드백 오버레이 13종, 3종목 통합 CLI(`unified_feedback_v4.py`).

**실험한 내용**: TCN/CTR-GCN/Shift-GCN/2s-AGCN 등 대안 모델 비교, YOLOv8-pose 및 YOLO-World 바벨 검출 비교 실험, feature 결합(속도/가속도) 비교, window 크기 실험.

**미완성 기능**: 정확한 바벨 검출(현재는 손목 proxy로 대체), phase 경계 예측 정확도, deadlift 데이터 부족 해소, threshold의 데이터 기반 검증, 카메라 회전 정규화.

자세한 수치는 [`docs/experiments_and_results.md`](docs/experiments_and_results.md), 문제점은 [`docs/limitations.md`](docs/limitations.md)를 참고하십시오.

## 12. 현재 한계

- landmark 가림 (바벨/원판이 손목·팔꿈치·정강이를 가림)
- 촬영 각도 민감성 (정측면에서는 바벨 검출 자체가 불가능해 45도 다각도뷰 필요)
- bar proxy 한계 (실제 바벨이 아닌 손 위치 근사값 사용)
- 횟수 카운팅 정확도 (Count MAE가 1을 넘는 경우 존재)
- 데이터셋 불균형 (deadlift가 3종목 중 가장 적고 성능도 가장 낮음)
- threshold 일반화 문제 (전문가 영상 통계 기반 검증 없음, **게다가 코드 3개 파일이 서로 다른 threshold·계산식을 사용** — `docs/thresholds.md`)
- 전문가 영상 정규화 문제 (화면 방향 정렬은 벤치프레스만 구현, 스쿼트·데드리프트는 의도적으로 미적용)
- 코드 완성도 문제 (스쿼트 전용 스크립트·데드리프트 의존 모듈 미제공, 세 코드 파일 간 미통합)

상세 내용: [`docs/limitations.md`](docs/limitations.md)

## 13. 2학기 개발 계획

P0(데이터/코드 이관) → P1(모델 정확도 개선) → P2(안정화) → P3(장기 통합)로 우선순위를 나눴습니다. 전체 목록은 [`docs/second_semester_plan.md`](docs/second_semester_plan.md)를 참고하십시오.

## 14. 팀원 및 역할

개인정보(전화번호, 학번, 이메일)는 정책상 공개하지 않으며, 회의록에서 확인된 담당 업무만 기록합니다.

| 이름 | 담당 업무 | 근거 |
|---|---|---|
| 강완석 | 스쿼트 자세 피드백 | 0430 |
| 유영진 | 벤치프레스 자세 피드백 | 0430 |
| 김민식 | 자세 지표 계산 공식 정리, GitHub 저장소 관리 | 0430 |
| 고준영 | 초기 아이디어 제안 | 아이디어 논의 |

데드리프트 담당자는 회의록에서 특정되지 않았습니다.
