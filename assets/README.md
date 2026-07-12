# assets/

프로젝트의 그림, 다이어그램, 결과물(이미지/짧은 영상)을 보관하는 폴더입니다.

## 현재 상태

이 저장소에는 아직 실제 결과 이미지/영상 파일이 없습니다. Notion 문서에는 다음과 같은 결과물이 언급되어 있으나, 원본 파일 자체가 GitHub 저장소나 이번 조사 범위에서 확인되지 않았습니다.

- 종목 인식 confusion matrix (0428 등에서 결과 수치는 확인되나, 이미지 파일 자체는 미확인)
- epoch-loss graph (여러 실험에서 언급되나 이미지 파일 미확인)
- 시각적 피드백 오버레이 결과 화면 (`realtime_compare_side.py`, `feedback_overlay.py` 실행 결과로 추정)
- 과제에서 언급된 `squat_unified_feedback2.mp4`, `benchpress_unified_feedback2.mp4`, `deadlift_unified_feedback2.mp4` — 이번 조사(Notion + GitHub)에서 이 파일명들은 확인되지 않았습니다.

**이미지/영상이 존재하지 않는 상태에서 문서에 빈 링크나 가짜 경로를 만들지 않았습니다.** 실제 파일이 확보되면 아래 구조에 맞춰 추가하고, 관련 `docs/*.md` 문서에서 링크를 연결하십시오.

## 권장 구조

```text
assets/
├─ figures/     (지표 계산식, 시스템 구조도 등 문서 보조 이미지)
├─ diagrams/    (파이프라인/아키텍처 다이어그램)
└─ results/     (confusion matrix, epoch-loss graph, 자세 피드백 결과 캡처 등)
```

## 대용량 영상 처리 원칙

결과 영상은 원본 그대로 업로드하지 말고 다음 중 저장소 상황에 맞는 방법을 사용하십시오.

- 대표 결과만 짧은 샘플 클립으로 저장
- GIF 또는 정지 이미지 캡처로 변환
- 외부 저장 위치 링크만 문서에 기록
- 개인정보(얼굴 등)가 포함된 원본은 절대 업로드하지 않음
