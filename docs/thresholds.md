# Threshold 값 정리 (Thresholds)

> **개정 이력**: 최초 버전은 Notion 기록만으로 작성했으나, 이후 팀이 실제 코드 3종
> (`src/posture_feedback/benchpress/benchpress_feedback_v4.py`,
> `src/posture_feedback/deadlift/deadlift_feedback_v2_CLEAN.py`,
> `src/posture_feedback/unified/unified_feedback_v4.py`)과 `종목별_threshold_값.pdf`
> 원본을 제공해 이를 근거로 전면 갱신했습니다. **코드와 문서가 다를 경우 코드를
> 기준으로 삼는다**는 작업 원칙에 따라, 세 코드 파일의 실제 threshold 값을
> 우선하고 문서(PDF)는 "왜 그 값이 나왔는지"의 근거 자료로 사용했습니다.

> **중요**: 이 문서에 기록된 모든 threshold는 "절대적인 의학적/운동역학적 기준"이 아닙니다. `종목별_threshold_값.pdf` 서두에 팀이 직접 남긴 문구를 그대로 인용합니다.
>
> "springer nature, ipf powerlifting rulebook, e-science sports 등을 보면 발너비 = 몸통길이 대비 0.10 이와같이 정확한 수치를 알려주지는 않음... 굉장히 애매하다"
>
> 즉 IPF 규정집이나 논문은 **정성적인 지침만 제공**하며, 아래 표의 실제 숫자는 팀이 그 지침을 해석해서 정한 값입니다. "논문에서 도출된 값"처럼 표현하지 않도록 주의하십시오.

## 0. 핵심 발견: 세 코드 파일의 threshold가 서로 다르다

같은 지표(예: `knee_angle`, `elbow_angle`)에 대해 세 코드 파일이 서로 다른 threshold 값을 쓰고 있습니다. 문서화 이전에는 이 사실이 어디에도 정리되어 있지 않았습니다.

| 지표 | `unified_feedback_v4.py` | `deadlift_feedback_v2_CLEAN.py`* | `benchpress_feedback_v4.py` |
|---|---|---|---|
| `knee_angle` (delta, deg) | squat 18.0 / deadlift 18.0 | squat 12.0 / deadlift 12.0 | (해당 지표 없음) |
| `hip_angle` (delta, deg) | squat 18.0 / deadlift 18.0 | squat 12.0 / deadlift 12.0 | (해당 지표 없음) |
| `trunk_lean` (delta, deg) | squat 10.0 / deadlift 10.0 | squat 8.0 / deadlift 8.0 | (해당 지표 없음) |
| `elbow_angle` / `elbow_angle_avg` (delta, deg) | deadlift 20.0 / bench 18.0 | 12.0 (공통) | 12.0 |
| `wrist_elbow_x_diff` (delta) | bench 0.08 | bench 0.08 | 0.08 |
| `bench_line_diff` (delta) | bench **0.20**, 게다가 ADVISORY로 강등(오류 판정 제외) | bench 0.08 (head_hip_line과 동일 취급) | 0.08 |
| `lockout_angle_min` (절대 기준, deg) | bench 18.0 (delta 방식으로 다르게 처리) | — | **165.0** (절대 기준) |

\* `deadlift_feedback_v2_CLEAN.py`는 `EXERCISE_DELTA_THRESHOLDS` 딕셔너리에 squat/deadlift/bench 3종 값을 모두 정의해 두고 있으나, 실제로 검증된 것은 deadlift 실행뿐입니다.

**원인 추정**: `종목별_threshold_값.pdf`는 발/손/어깨/머리-엉덩이 정렬 등 "공통·보조 지표"만 값을 제공하며, `knee_angle`/`hip_angle`/`trunk_lean`처럼 스쿼트·데드리프트의 핵심 판정에 쓰이는 관절각 threshold는 **PDF에 아예 포함되어 있지 않습니다.** 즉 이 값들은 각 코드 파일 작성자가 별도로, 서로 다른 시점에 경험적으로 정한 값이며 한 번도 통일된 적이 없습니다. 2학기 P0/P1 과제로 반드시 하나로 정리해야 합니다([`second_semester_plan.md`](./second_semester_plan.md) 참고).

**주목할 예외 — `bench_line_diff`의 의도적 재조정**: `unified_feedback_v4.py`에는 다음 코드 주석이 있습니다.

> "bench_line_diff(머리-어깨-엉덩이 라인)는 측면 벤치에서 nose-어깨-엉덩이 기하가 카메라 각도에 민감해 user/expert 비교가 불안정하다(expert가 user의 ~2배로 측정됨). PDF 0.08 절대 기준을 강제하면 거의 항상 '주의'가 되어 노이즈가 되므로 보조 지표로 둔다."

즉 이 항목만큼은 "PDF 문서값(0.08)을 그대로 코드에 넣었더니 실측에서 오탐이 너무 많아, 코드 작성자가 threshold를 0.20으로 완화하고 오류 판정에서도 제외했다"는 **실측 기반 조정 사례**입니다. 이런 조정 근거가 있는 항목과, 그냥 서로 다른 값을 썼을 뿐 이유가 남아있지 않은 항목(`knee_angle` 등)을 구분해서 이해해야 합니다.

## 1. PDF(`종목별_threshold_값.pdf`) 문서화 지표 — 발/손/어깨/정렬 계열

이 표의 지표들은 PDF에 종목별 값과 근거가 명시되어 있고, `benchpress_feedback_v4.py`와 `deadlift_feedback_v2_CLEAN.py`가 (거의) 그대로 코드에 반영했습니다. `unified_feedback_v4.py`는 이 계열 중 일부만 구현합니다(위 0절 표 참고).

### 1-1. 초기값 (팀 표기: "GPT가 임의로 선정한 초기 Threshold 값들")

| threshold | 의미 | 값 | 출처 |
|---|---|---|---|
| `foot_width` | 발너비 | 0.15 | GPT |
| `foot_x_asymmetry` | 발목 x좌표 차이(양발이 일자인지) | 0.10 | GPT |
| `foot_foreaft_asymmetry` | 발위치 전/후 차이 | 0.10 | GPT |
| `foot_flatness` / `left_foot_flatness` / `right_foot_flatness` | 발바닥밀착 | 0.04 | GPT |
| `hand_width` | 양손거리 | 0.20 | GPT |
| `hand_height_diff` | 손높이차 | 0.07 | GPT |
| `shoulder_height_diff` | 어깨높이차 | 0.05 | GPT |
| `head_hip_line` | 머리-어깨-엉덩이 일직선 | 0.10 | GPT |
| `neck_lean` | 목-머리각 | 10.0° | GPT |
| `wrist_shoulder_y_diff` | 손목-어깨높이 | 0.15 | GPT |
| `elbow_angle_avg` | 팔꿈치각 | 12.0° | GPT |

노란색 표기(원문 기준): 해당 종목에서 **타이트하게** 조정해야 하는 지표. 그 외는 느슨하게 허용범위를 늘려도 되는 지표.

### 1-2. 스쿼트용 (정제값)

| threshold | 값 | 출처 | 근거 요지 |
|---|---|---|---|
| `foot_width` | 0.10 | Escamilla et al. 2000 / IPF 2026 rulebook | 스쿼트 stance width를 좁은/중간/넓은 자세로 나눠 분석한 연구 기준, 타이트하게 |
| `foot_x_asymmetry` | 0.08~0.10 | IPF 2026 rulebook | IPF 규정상 발을 앞뒤·좌우로 움직이면 실패 사유. 0.10보다 엄격한 0.08 채택 |
| `foot_foreaft_asymmetry` | 0.08~0.10 | IPF 2026 rulebook | 위와 동일 취지로 0.08 채택 |
| `foot_flatness` | 0.04 | Springer Nature | MediaPipe 발끝·뒤꿈치 landmark 흔들림 고려, 0.02는 너무 엄격 |
| `left_foot_flatness` / `right_foot_flatness` | 0.04 | Springer Nature | 좌우 평균에 묻히는 편측 오류를 잡기 위해 개별 유지 |
| `hand_width` | 0.15~0.20 | IPF 2026 rulebook | 로우바/하이바 스타일 차이로 느슨하게 |
| `hand_height_diff` | 0.07 | IPF 2026 rulebook | 측면영상에서 한쪽 손이 가려질 수 있어 0.05보다 느슨하게 |
| `shoulder_height_diff` | 0.05 | IPF 2026 rulebook | 바벨이 어깨 위 수평이어야 한다는 규정 기준 |
| `head_hip_line` | 0.10 | IPF 2026 rulebook | 시작/완료 시 무릎 잠긴 upright position 요구 |
| `neck_lean` | 10.0° | NSCA deadlift guide | 실제 영상의 흔들림/가림 고려해 5°보다 여유 있게 |
| `wrist_shoulder_y_diff` | 0.15 | IPF 2026 rulebook | 로우바/하이바, 손목 유연성 차이 고려해 느슨하게 |
| `elbow_angle_avg` | 12.0° | IPF 2026 rulebook | 스쿼트 핵심 판정 지표는 아님, 개인차 고려 |

### 1-3. 데드리프트용 (정제값)

| threshold | 값 | 출처 | 근거 요지 |
|---|---|---|---|
| `foot_width` | 0.10 | Escamilla et al. 2000, IPF 2026 rulebook | conventional 기준 0.10 이상을 의미 있는 stance 차이로 봄 |
| `foot_x_asymmetry` | 0.08 | IPF 2026 rulebook | 순수 측면영상에서는 신뢰도가 낮아 보조 지표로만 사용 권장 |
| `foot_foreaft_asymmetry` | 0.08 | IPF 2026 rulebook | 측면영상에서 비교적 잘 보이는 지표 |
| `foot_flatness` / `left_foot_flatness` / `right_foot_flatness` | 0.04 | IPF 2026 rulebook, NSCA deadlift guide | 발 지지 안정성, MediaPipe 흔들림 고려 |
| `hand_width` | 0.12 | Escamilla et al. 2000, IPF 2026 rulebook | conventional/sumo 스타일 차이로 벤치보다 느슨 |
| `hand_height_diff` | 0.07 | NSCA deadlift guide | 손목 높이차를 바벨 기울기 proxy로 사용, 벤치보다 느슨 |
| `shoulder_height_diff` | 0.05 | IPF 2026 rulebook, NSCA deadlift guide | 완료 자세에서 어깨 정렬 필요 |
| `head_hip_line` | 0.08~0.10 | IPF 2026 rulebook, NSCA deadlift guide | 동작 중엔 자연스럽게 숙여지므로 기본 0.10, lockout 구간만 0.08까지 |
| `neck_lean` | 10.0° | NSCA deadlift guide | 시선 처리 개인차, landmark 흔들림 고려 |
| `wrist_shoulder_y_diff` | 0.15 | NSCA deadlift guide, IPF 2026 rulebook | 동작 단계별 변화가 커서 보조 지표로만 사용 |
| `elbow_angle_avg` | 12.0° | NSCA RDL guide, IPF 2026 rulebook | 팔은 바와 몸을 연결하는 고리로 유지되어야 함 |

### 1-4. 벤치프레스용 (정제값)

| threshold | 값 | 출처 | 근거 요지 |
|---|---|---|---|
| `wrist_elbow_x_diff` | 0.07~0.10 | IPF 2026 rulebook, bench press coaching guide | `abs(wrist_x - elbow_x)/torso_length`가 범위를 넘으면 정렬 이탈 |
| `lockout_angle_min` | **165°** (절대 기준) | IPF 2026 rulebook, NSCA bench press guide | 상단에서 wrist-elbow-shoulder 각도 165° 이하면 락아웃 부족 |
| `hand_height_diff` | 0.08 | bench press coaching guide, 프로젝트 실험 기준 | 양손 비대칭/바벨 기울어짐 탐지 |
| `shoulder_height_diff` | 0.07 | IPF 2026 rulebook, bench setup guide | 몸통 비틀림/어깨 비대칭 탐지 |
| `bench_line_diff` | 0.08 | IPF 2026 rulebook, 프로젝트 실험 기준 | 머리-어깨-엉덩이 정렬 이탈. **단, `unified_feedback_v4.py`는 실측 결과 0.20으로 완화 + 오류판정 제외 처리(위 0절 참고)** |
| `foot_offset` | 0.10 | IPF 2026 rulebook | `abs(left_ankle_x - right_ankle_x)/torso_length` 비대칭 |
| `foot_flatness` | 0.04 | IPF 2026 rulebook, bench press setup guide | 발이 지면을 안정적으로 눌러야 함 |
| `elbow_above_shoulder` | 0.00 기준(boolean) | bench press coaching guide | 팔꿈치 y좌표가 어깨보다 위로 오면 어깨 부담 증가 후보 |

## 2. threshold 상태 분류

- **경험적 초기값(GPT)**: 1-1
- **문헌의 정성적 지침 + 팀 판단으로 조정**: 1-2~1-4 (전문가 영상의 통계적 분포를 측정해 산출한 값이 아님 — "전문가 영상 분포 기반"이라고 표현하지 않도록 주의)
- **코드에만 존재하고 문서 근거가 없는 값**: `knee_angle`, `hip_angle`, `trunk_lean` 등 핵심 관절각 threshold. 위 0절 표 참고. 파일마다 다른 값을 쓰고 있어 **데이터 기반 재조정이 시급**함
- **실측 후 코드에서 재조정된 값**: `bench_line_diff` (0.08 → 0.20, `unified_feedback_v4.py`만 해당)

## 3. 코드에서 확인되는 절대 기준(ABSOLUTE_RULES / ABS_THRESHOLDS)

델타(전문가 대비 차이) 방식과 별개로, 세 코드 파일 모두 phase(구간)에 따라 적용하는 절대 기준을 갖고 있습니다.

| 종목 | 절대 기준 | 값 | 파일 |
|---|---|---|---|
| squat | 최저점에서 무릎각이 이 값보다 크면 깊이 부족 | 105° | `unified_feedback_v4.py` |
| squat | 몸통 기울기 과도 | 35°(unified) | `unified_feedback_v4.py` |
| deadlift | lockout 구간 무릎/엉덩이 각 최소값 | 155° | `unified_feedback_v4.py` |
| deadlift | 팔꿈치 lockout 최소값 | 155° | `unified_feedback_v4.py` |
| deadlift | 몸통 기울기 과도 | 45° | `unified_feedback_v4.py` |
| benchpress | 상단 락아웃 최소 각도 | 165° | `unified_feedback_v4.py`, `benchpress_feedback_v4.py` (두 파일 값 일치) |
| benchpress | 손목-팔꿈치 정렬 이탈 최대값 | 0.10 | `unified_feedback_v4.py` |

## 4. 요약: 절대적 기준으로 오해하지 말아야 할 것

- 이 threshold들은 **IPF 파워리프팅 대회 판정 규정을 그대로 코드화한 것이 아니라**, 규정의 정성적 취지를 팀이 정량적 수치로 "해석"한 것입니다.
- 팀은 이 값들을 실제 전문가 영상 다수의 통계 분포로 검증하지 않았습니다(전문가 영상 분포 기반 산출 아님). 유일한 예외는 `bench_line_diff`로, 실측 후 완화된 기록이 코드 주석으로 남아 있습니다.
- 세 코드 파일 간 threshold 불일치(0절)는 2학기 P0/P1 과제입니다 — [`second_semester_plan.md`](./second_semester_plan.md) 참고.

관련 문서: [`exercise_metrics.md`](./exercise_metrics.md), [`system_pipeline.md`](./system_pipeline.md)
