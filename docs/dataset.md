# 데이터셋 (Dataset)

> 숫자가 시점마다 다르게 기록된 이유는 [`dataset_history.md`](./dataset_history.md)에 별도로 정리했습니다. 이 문서는 1학기 종료 시점 기준 최신 상태만 다룹니다.
>
> **원본 영상 파일은 개인정보(촬영자 얼굴 등)를 포함할 수 있어 이 GitHub 저장소에 업로드되어 있지 않습니다.** 아래 내용은 모두 Notion 기록을 근거로 한 구조 설명이며, 실제 데이터 파일은 팀 내부 저장소(로컬/Google Drive/Colab 등, 정확한 위치는 Notion에 명시되어 있지 않음)에 있는 것으로 추정됩니다.

## 1. 데이터셋 구성

### 1-1. 자체 촬영 데이터셋 (메인 파이프라인용)

0611 "yolo 모델 검출" 기록 기준, 종목별 영상 개수는 다음과 같습니다.

| 종목 | 영상 개수 | 비고 |
|---|---|---|
| squat | 89 | |
| benchpress | 94 | |
| deadlift | 25 | 3종목 중 가장 적음 — [`limitations.md`](./limitations.md)의 한계로 반복 언급됨 |
| **합계** | **208** | 총 138,892프레임, 검출율(frame-weighted) 99.74% |

파일 경로에 `data/측면/...` 형태가 반복 등장하고 `stu4`, `stu6`, `stu7`, `stu8` 등 학생 코드로 추정되는 문자열이 포함되어 있어, 팀이 직접 촬영한 자체 데이터셋으로 추정됩니다(명시적으로 "자체 촬영"이라고 쓴 문장은 확인되지 않아 추정임을 밝혀둡니다).

0611 회의록에는 "데드리프트 개인 크롤링 6개 추가"라는 기록도 있어, 자체 촬영 외에 일부 크롤링(공개 영상 수집)도 병행된 것으로 보입니다.

### 1-2. 학습/검증/평가 split (0428 기준, ST-GCN/TCN 종목 분류 실험)

| 종목 | train | val | test | 합계 |
|---|---|---|---|---|
| benchpress | 66 | 14 | 14 | 94 |
| deadlift | 18 | 4 | 4 | 26 |
| squat | 62 | 13 | 14 | 89 |
| **합계** | **146** | **31** | **32** | **209** |

이 split은 4월 28일 시점의 스냅샷이며, 위 1-1의 6월 11일 수치(208개, deadlift 25개)와 deadlift 항목에서 1개 차이가 있습니다. 최신 split 파일이 저장소에 없어 현재 기준 split을 다시 확인할 수 없습니다.

### 1-3. 외부 공개 데이터셋 (검토/보조 실험용)

| 데이터셋 | 용도 | 실사용 여부 |
|---|---|---|
| Kaggle "Workout/Exercises Video" (167개 영상: benchpress 100/deadlift 44/squat 23) | ST-GCN 종목 분류 초기 학습 | 실사용 (종목 인식 및 횟수 기록 실험) |
| Kaggle "Exercise Detection Dataset" (`exercise_angles.csv`, 31,033행) | YOLOv8-pose+TCN 별도 실험 트랙 | 실사용 (관절 각도 이용 운동 기록 실험) |
| Kaggle "LSTM Exercise Classification: Push Up Videos" | LSTM 푸시업 분류 테스트 | 실사용 (모션인식 모델 test) |
| Kaggle "Workout Dataset" (22종목, 652개 영상) | MediaPipe/YOLOv8 × TCN/ST-GCN 4파이프라인 비교 | 실사용 (파일럿 비교, 3대 운동 데이터셋 아님) |
| Fit3D, Kinetics-skeleton, AI-Hub 크로스핏 데이터, RepCount Dataset(Part-A/B), RepNet 논문 데이터 | 후보 조사 | **검토 단계** — 실제 학습에 사용했다는 기록 없음 |

## 2. 라벨 구조

`phase_labeling.py`(`src/preprocessing/`)의 실제 코드를 확인해 정확한 라벨 스키마를 검증했습니다. "start-bottom-finish" 3단계 phase 라벨이 사용되며(0512 회의록의 "ready-down-up" 표기는 이후 문서에서 이름이 다르게 정착된 것으로 보임 — 같은 3단계 개념), 도구가 기대하는 폴더 구조와 산출물은 다음과 같습니다.

- **입력 폴더 구조**: `측면_수정본/{benchpress,squat,deadlift}/*.{mp4,avi,mov,mkv,wmv}`
- **출력 CSV**: `phase_labels.csv`, 컬럼은 `type`, `name`, `count`, `L1`, `L2`, `L3`, ... — 3개씩 한 세트로 `L(3k+1)`=k+1번째 반복의 Start 프레임, `L(3k+2)`=Bottom 프레임, `L(3k+3)`=Finish 프레임(0-based)

과거 회의록에 등장한 `squat_labels.csv`, `labels_deadlift.csv`, `benchpress_lables.csv`(오타 포함), `labels_squat.csv` 등의 파일명은 `phase_labeling.py`가 실제로 생성하는 `phase_labels.csv`와 다릅니다 — 종목별로 별도 CSV를 만들던 이전 방식에서, 하나의 CSV에 `type` 컬럼으로 종목을 구분하는 현재 방식으로 정리된 것으로 추정됩니다(정확한 이력은 확인되지 않음).

0611 회의록에는 "데이터 재라벨링(상/중/하 분류·편집·start-bottom-finish 라벨)"이라는 기록이 있어, 라벨 품질 재검토 작업이 1학기 말에 진행되었습니다.

## 3. 데이터셋 품질 등급

Notion에 "상/중/하" 3단계 품질 등급 체계가 명시적으로 정의된 페이지는 확인되지 않았습니다(검토 단계). 다만 다음과 같은 품질 관련 이슈가 실험 기록에서 확인됩니다.

- 사람 검출/추적: 다인물 영상에서 잘못된 사람을 추적하는 문제 (0505)
- 주요 관절 가림: 바벨·원판이 손목·정강이를 가리는 문제 (0430, 0602)
- 반복 횟수 판별: binary mask 라벨의 99.8%가 "rep 중"으로 표시되어 학습 신호 부족 (0505)
- phase 판별: ready phase로 예측이 쏠리는 현상, 전환 시점 지연 평균 +11.68~12.77 프레임 (0602 "phase 성능 저하 분석")

이 항목들은 "상/중/하 등급 기준"으로 공식화되지는 않았으나, 2학기에 등급 체계를 만들 때 참고할 수 있는 실측 근거로 [`limitations.md`](./limitations.md)에도 정리해 두었습니다.

## 4. 확인된 라벨링 이슈

- 종목명 오타: `bechpress`, `beachpress`, `sqaut` (0428 결과 해설 텍스트) — 코드/폴더명 자체의 오타인지 해설 텍스트의 오타인지는 원문만으로 구분되지 않음
- 파일명 규칙 불일치: `benchpress_lables.csv`(labels 오타 포함) 등 라벨 파일명이 종목별로 통일되어 있지 않음 (0512)
- deadlift 데이터 부족: 3종목 중 가장 적은 수(25~26개)로 지속적으로 지적됨 (0428, 0505, 0602)
- split 미지정 데이터: 0611 이후 재라벨링된 데이터의 train/val/test 재분할 여부는 이번 조사에서 확인되지 않음 (언급 없음)

## 5. 2학기 권장 조치

1. 실제 최신 라벨 CSV를 저장소(또는 접근 가능한 위치)에서 확보하여 정확한 개수/분포를 재집계
2. deadlift 데이터 25→31개 이상으로 확충 (0505 회의록에서 "30~60개 추가 수집" 제안)
3. 종목별 라벨 파일명 규칙 통일 (`{exercise}_labels.csv` 등)
4. 품질 등급(상/중/하) 기준을 공식 문서화

관련 문서: [`dataset_history.md`](./dataset_history.md), [`capture_guidelines.md`](./capture_guidelines.md), [`pose_landmarks_and_csv.md`](./pose_landmarks_and_csv.md)
