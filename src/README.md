# src/

자세 피드백 소스 코드가 위치합니다. `posture_feedback/` 하위 3개 파일은 팀이 실제로 작성한 코드이며, 나머지 하위 구조(`preprocessing/`, `action_recognition/`, `rep_counting/`, `utils/`)는 아직 코드가 없어 권장안만 마련해 두었습니다.

## 현재 구조

```text
src/
├─ posture_feedback/
│  ├─ benchpress/
│  │  ├─ benchpress_feedback_v4.py   # 벤치프레스 단독 실행 스크립트
│  │  └─ expert_benchpress.json      # 전문가 landmark/지표 샘플 (215프레임)
│  ├─ deadlift/
│  │  └─ deadlift_feedback_v2_CLEAN.py  # 데드리프트 단독 실행 스크립트
│  │     ⚠ realtime_compare_side.py, feedback_overlay.py 없이는 실행 불가 (미제공)
│  └─ unified/
│     └─ unified_feedback_v4.py      # squat/deadlift/benchpress 통합 CLI (자기완결형)
└─ (preprocessing/ action_recognition/ rep_counting/ utils/ — 아직 코드 없음, 아래 권장 구조 참고)
```

각 파일의 목적/입출력/의존성은 파일 상단 docstring(Purpose/Supported exercise/Input/Output/Main dependencies/Notes)에 정리되어 있습니다. threshold·계산식이 세 파일 간에 서로 다른 부분이 있으니 반드시 [`../docs/thresholds.md`](../docs/thresholds.md), [`../docs/exercise_metrics.md`](../docs/exercise_metrics.md)를 함께 확인하십시오.

## 아직 없는 하위 구조 (권장안)

```text
src/
├─ preprocessing/        # landmark 추출, CSV/JSON 저장, 전문가 영상 전처리
├─ action_recognition/   # ST-GCN / TCN / CTR-GCN 등 종목 인식 학습·추론 코드
├─ rep_counting/         # 횟수 카운팅 (binary mask v1, Gaussian density v2, valley 기반 실시간 등)
├─ posture_feedback/
│  └─ squat/             # 스쿼트 전용 스크립트 — 아직 미제공. unified_feedback_v4.py가
│                          자기완결형으로 squat도 처리하므로 당장 실행에는 지장 없음
└─ utils/                 # 지표 계산 공식, 정규화 함수 등 공용 유틸(현재는 각 파일에 중복 구현됨)
```

## 2학기 정리 항목

- **의존성 확보**: `realtime_compare_side.py`, `feedback_overlay.py`(deadlift가 필요), squat 전용 스크립트를 팀에서 확보해 추가
- **threshold/계산식 통일**: `elbow_angle_avg`, `bench_line_diff` 등 파일마다 다른 계산식을 하나로 통일 ([`../docs/exercise_metrics.md`](../docs/exercise_metrics.md) 5절)
- **공용 유틸 추출**: `angle_abc`, `get_xy`/`get_xyv`, `midp`/`mid` 등 세 파일에 거의 동일하게 중복 구현된 함수를 `utils/`로 추출
- 하드코딩된 Windows 폰트 경로(`C:/Windows/Fonts/malgun.ttf`)를 크로스플랫폼 폰트 탐색 방식으로 통일 (`deadlift_feedback_v2_CLEAN.py`의 `find_korean_font()` 패턴이 이미 존재)
- 종목명 표기를 `squat` / `benchpress` / `deadlift`로 통일 (`bench`는 CLI 별칭으로만 유지, `unified_feedback_v4.py`의 `normalize_exercise_name()`이 이미 이렇게 처리 중)
