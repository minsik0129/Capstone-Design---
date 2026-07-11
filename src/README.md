# src/

2학기부터 실제 소스 코드가 들어올 폴더입니다. 1학기 종료 시점에는 이 저장소에 코드가 커밋되어 있지 않아, Notion 기록을 근거로 한 권장 하위 구조만 마련해 두었습니다.

## 권장 하위 구조

```text
src/
├─ preprocessing/        # landmark 추출, CSV/JSON 저장, 전문가 영상 전처리
├─ action_recognition/   # ST-GCN / TCN / CTR-GCN 등 종목 인식 학습·추론 코드
├─ rep_counting/         # 횟수 카운팅 (binary mask v1, Gaussian density v2, valley 기반 실시간 등)
├─ posture_feedback/
│  ├─ squat/             # squat_feedback_v3~v5 계열
│  ├─ benchpress/
│  ├─ deadlift/
│  └─ unified/           # unified_feedback_v4.py 등 3종목 통합 코드
└─ utils/                 # 지표 계산 공식(기준지표/공통지표), 정규화 함수 등 공용 유틸
```

이 구조는 [`../docs/system_pipeline.md`](../docs/system_pipeline.md)에 정리된 Notion 상 확인된 파일명 목록을 참고해 설계했습니다. 실제 코드를 옮길 때는 다음을 함께 점검하십시오(2학기 작업 항목).

- 하드코딩된 로컬 절대경로, 사용자 이름 포함 경로, Google Drive 경로 제거
- Windows 전용 경로와 Colab 전용 경로 구분
- 로컬 실행용 코드와 Colab 실행용 코드 구분 (`phase_labeling.py`는 Notion에 "로컬 전용, 코랩 아님"으로 명시된 바 있음 — 0512)
- import 경로/상대경로가 새 폴더 구조에서도 깨지지 않는지 확인
- 종목명 표기를 `squat` / `benchpress` / `deadlift`로 통일 (`bench`, `bechpress` 등 혼용 정리)
