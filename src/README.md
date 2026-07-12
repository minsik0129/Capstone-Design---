# src/

자세 피드백·전처리 소스 코드가 위치합니다. `posture_feedback/`, `preprocessing/phase_labeling.py`는 팀이 실제로 작성한 코드이며, 나머지 하위 구조(`action_recognition/`, `rep_counting/`, `utils/`)는 아직 코드가 없어 권장안만 마련해 두었습니다.

## 현재 구조

```text
src/
├─ preprocessing/
│  └─ phase_labeling.py              # Start/Bottom/Finish 라벨링 GUI, phase_labels.csv 생성
├─ posture_feedback/
│  ├─ benchpress/
│  │  ├─ benchpress_feedback_v4.py   # 벤치프레스 단독 실행 스크립트
│  │  └─ expert_benchpress.json      # 전문가 landmark/지표 샘플 (215프레임)
│  ├─ deadlift/
│  │  ├─ deadlift_feedback_v2_CLEAN.py  # 구조상 squat/deadlift/bench 지원, 현재 deadlift로 고정
│  │  ├─ realtime_compare_side.py       # deadlift 스크립트가 import(as rt) — 함수만 재사용
│  │  └─ feedback_overlay.py            # deadlift 스크립트가 import(as fo) — 시각 오버레이 라이브러리
│  └─ unified/
│     └─ unified_feedback_v4.py      # squat/deadlift/benchpress 통합 CLI (자기완결형)
└─ (action_recognition/ rep_counting/ utils/ — 아직 코드 없음, 아래 권장 구조 참고)
```

⚠ `deadlift_feedback_v2_CLEAN.py`는 이제 import는 되지만, 의존 모듈 `realtime_compare_side.py`가 요구하는 전문가 JSON 스키마(`total_frames` 필드 필수)와 `unified_feedback_v4.py`가 생성하는 JSON 스키마가 달라 **여전히 실행되지 않습니다**. 자세한 내용은 [`../docs/system_pipeline.md`](../docs/system_pipeline.md) 2절 참고.

각 파일의 목적/입출력/의존성은 파일 상단 docstring(Purpose/Supported exercise/Input/Output/Main dependencies/Notes)에 정리되어 있습니다. threshold·계산식이 파일 간에 서로 다른 부분이 있으니 반드시 [`../docs/thresholds.md`](../docs/thresholds.md), [`../docs/exercise_metrics.md`](../docs/exercise_metrics.md)를 함께 확인하십시오.

## 아직 없는 하위 구조 (권장안)

```text
src/
├─ action_recognition/   # ST-GCN / TCN / CTR-GCN 등 종목 인식 학습·추론 코드 (다른 팀원 담당, 아직 미보유)
├─ rep_counting/         # 횟수 카운팅 (binary mask v1, Gaussian density v2, valley 기반 실시간 등)
├─ posture_feedback/
│  └─ squat/             # 스쿼트 전용 스크립트 — 아직 미제공. unified_feedback_v4.py가
│                          자기완결형으로 squat도 처리하므로 당장 실행에는 지장 없음
└─ utils/                 # 지표 계산 공식, 정규화 함수 등 공용 유틸(현재는 각 파일에 중복 구현됨)
```

## 2학기 정리 항목

- **전문가 JSON 스키마 통일(최우선)**: `total_frames` 필드 유무 불일치로 `deadlift_feedback_v2_CLEAN.py`가 여전히 실행되지 않음
- **의존성 확보**: squat 전용 스크립트, ST-GCN/TCN/CTR-GCN 학습 코드를 팀에서 확보해 추가
- **threshold/계산식/종목명 통일**: `elbow_angle_avg`, `bench_line_diff` 계산식과 `benchpress`/`bench` 종목명 표기를 하나로 통일 ([`../docs/exercise_metrics.md`](../docs/exercise_metrics.md) 5절, [`../docs/thresholds.md`](../docs/thresholds.md) 0-1절)
- **smoothing 알고리즘 통일**: EMA(`LandmarkSmoother`) vs OneEuroFilter(`feedback_overlay.py`) 중 하나로 정리
- **공용 유틸 추출**: `angle_abc`, `get_xy`/`get_xyv`, `midp`/`mid` 등 여러 파일에 거의 동일하게 중복 구현된 함수를 `utils/`로 추출
- 하드코딩된 Windows 폰트 경로(`C:/Windows/Fonts/malgun.ttf`)를 크로스플랫폼 폰트 탐색 방식으로 통일 (`deadlift_feedback_v2_CLEAN.py`/`feedback_overlay.py`/`realtime_compare_side.py`의 fallback 후보 목록 패턴이 이미 존재)
- 종목명 표기를 `squat` / `benchpress` / `deadlift`로 통일 (`unified_feedback_v4.py`는 이미 `normalize_exercise_name()`으로 처리 중. `deadlift_feedback_v2_CLEAN.py`는 내부적으로 `"bench"` 키를 그대로 쓰고 있어 통일 필요)
