# 전체 시스템 파이프라인 (System Pipeline)

> **이 문서는 GitHub 저장소의 실제 코드를 읽고 검증한 것이 아니라, Notion에 기록된 코드 실행 방식·파일명·회의록 설명을 근거로 재구성한 것입니다.** 저장소에 코드가 커밋되면 이 문서를 실제 코드 기준으로 다시 검토·수정해야 합니다.

## 1. 개념적 파이프라인

과제에서 제시한 11단계 파이프라인과, Notion 기록으로 확인 가능한 실제 구현 상태를 대응시키면 다음과 같습니다.

| 단계 | 설명 | 확인된 상태 |
|---|---|---|
| 1 | 사용자/전문가 운동 영상 입력 | 확인됨 — `unified_feedback_v4.py --exercise {squat,deadlift,benchpress}` CLI로 실행 (0602) |
| 2 | MediaPipe pose landmark 추출 | 확인됨 — MediaPipe Pose 33 landmark 사용 (모션인식 study - kim) |
| 3 | landmark 좌표·visibility를 CSV/JSON/내부 자료구조로 저장 | **부분 확인** — 원본 landmark 저장 스키마는 문서에 명시되지 않음. 가공된 각도 CSV(`exercise_angles.csv`)는 별도 실험 트랙에서만 확인됨 (자세한 내용: [`pose_landmarks_and_csv.md`](./pose_landmarks_and_csv.md)) |
| 4 | 전문가 영상 기준 자세 지표 계산 | 확인됨 — "기준지표"/"공통지표" 문서에 계산식 존재 |
| 5 | 사용자 영상에서 동일 지표 계산 | 확인됨 — 동일 로직 재사용 구조로 기술됨 |
| 6 | 여러 프레임 smoothing/window average | **부분 확인** — window 크기 실험(96→32, 0514)은 phase 분류 모델의 시퀀스 길이 관련이며, 지표 자체의 프레임 간 smoothing 기법이 별도로 명시되어 있지는 않음 |
| 7 | 운동 종목별 rule 적용 → 자세 오류 판단 | 확인됨 — threshold 기반 rule ([`thresholds.md`](./thresholds.md)) |
| 8 | rule 위반 시 해당 피드백 우선 출력 | **명시적 기록 없음** — "우선순위" 로직이 문서화되어 있지는 않음(언급 없음) |
| 9 | rule 위반이 불명확할 때 전문가와 차이 비교 | **명시적 기록 없음** (언급 없음) — 다만 "시각" 문서의 `metricbar`(전문가 vs 사용자 비교 바)가 유사한 목적으로 보임 |
| 10 | HUD·기준선·관절 표시·메시지로 결과 시각화 | 확인됨 — 오버레이 13종 구현 ([`experiments_and_results.md`](./experiments_and_results.md) 6절) |
| 11 | 결과 영상 저장 | **명시적 기록 없음** — 저장 파일명 규칙 등은 확인되지 않음 |

**8, 9, 11번 단계는 이번 조사에서 명시적 근거를 찾지 못했습니다.** 실제 코드 로직이 이 단계들을 어떻게 처리하는지는 코드가 저장소에 없어 확인할 수 없었습니다. 실제 코드와 다를 경우, 코드를 기준으로 이 문서를 다시 수정해야 합니다.

## 2. 실제로 존재가 확인된 코드/도구 (Notion 언급 기준, 저장소에는 없음)

| 파일명 | 역할(추정) | 최초 언급 시점 |
|---|---|---|
| `ST_GCN_custom_dataset.ipynb` | 종목분류 ST-GCN 학습 | 0428 |
| `expert_preprocess_sideview.py` | 전문가 영상 측면 지표 전처리 | 0428 |
| `realtime_compare_sideview.py` | 실시간 사용자-전문가 비교 | 0428 |
| `phase_labeling.py` | phase 라벨링 도구 (로컬 실행 전용, "코랩 아님"으로 명시) | 0512 |
| `feedback_overlay.py` | 시각 피드백 오버레이 | 0519 |
| `realtime_compare_side.py` | 실시간 비교/오버레이 | 0519 |
| `squat_feedback_v3.ipynb` ~ `squat_feedback_v5.ipynb` | 스쿼트 피드백 코드 단계적 업그레이드 | 0526 |
| `unified_feedback_v4.py` | 3종목 통합 CLI | 0602 |
| `pose_landmarker_lite.task` | MediaPipe 모델 파일 (실행 필수) | 0602 |

과제에서 예시로 언급한 `squat_feedback_v5_UPGRADE.py`, `multi_exercise_feedback_v1.py`, `unified_feedback_v2.py`라는 정확한 파일명은 확인되지 않았습니다. 가장 근접한 실제 파일명은 `squat_feedback_v5.ipynb`(0526)와 `unified_feedback_v4.py`(0602)입니다 — 버전 번호와 확장자가 과제 지시문과 다르므로, 실제 코드를 확보한 뒤 정확한 파일명으로 이 문서를 갱신해야 합니다.

## 3. 왜 코드 구조(src/) 대신 이 문서만 존재하는가

과제 지시문은 저장소에 이미 존재하는 코드를 `src/preprocessing/`, `src/action_recognition/` 등으로 재배치하는 것을 전제로 합니다. 그러나 이 저장소는 README 2줄짜리 초기 커밋만 있는 빈 저장소였습니다([`../README.md`](../README.md)의 "저장소 현황" 절 참고). 따라서 이번 작업에서는:

- 존재하지 않는 코드를 새로 작성하지 않았습니다 (Notion 회의록에 언급된 알고리즘을 재구현하는 것은 "구현하지 않은 기능을 구현 완료로 표현하지 말 것"이라는 원칙에 위배되며, 팀이 실제로 작성한 코드와 다를 위험이 큽니다).
- 대신 Notion에 기록된 파이프라인/파일명/실험 결과를 문서로 보존했습니다.
- `src/`, `notebooks/`, `configs/` 디렉터리는 2학기에 실제 코드가 들어올 자리로 뼈대만 마련해 두었습니다(각 디렉터리의 `README.md` 참고).

관련 문서: [`../README.md`](../README.md), [`second_semester_plan.md`](./second_semester_plan.md)
