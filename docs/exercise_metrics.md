# 운동 자세 지표 (Exercise Metrics)

> threshold(임계값)는 이 문서가 아니라 [`thresholds.md`](./thresholds.md)에 별도 정리했습니다. 이 문서는 "어떤 지표를 어떤 landmark로 어떻게 계산하는가"만 다룹니다.
>
> **개정 이력**: 최초 버전은 Notion "기준지표"/"공통지표" 문서만으로 작성했으나, 이후 실제 코드 3종(`benchpress_feedback_v4.py`, `deadlift_feedback_v2_CLEAN.py`, `unified_feedback_v4.py`)을 확인해 정확한 계산식으로 갱신했습니다. 세 파일이 **같은 이름의 지표를 서로 다른 공식으로 계산**하는 경우가 발견되어 5절에 별도 정리했습니다.

## 1. 계산 방식의 기본 원리

세 코드 파일에 공통으로 등장하는 두 가지 연산이 모든 지표의 기반입니다.

- **거리(정규화 거리)**: `distance(A,B) = sqrt((x1-x2)^2 + (y1-y2)^2 + (z1-z2)^2)`, 그리고 `normalized_distance = distance(A,B) / torso_length` (몸통 길이로 나눠 무차원화)
- **각도**: 세 점 A-B-C가 이루는 각(B가 꼭짓점)을 벡터 내적으로 계산 — `theta = arccos(dot(BA,BC) / (norm(BA)*norm(BC)))` (코드 함수명 `angle_abc(a, b, c)`)
- **수직 기준 기울기**: 두 점을 잇는 벡터가 수직축에서 얼마나 벗어났는지 — `unified_feedback_v4.py`는 `atan2(dx, -dy)`(부호 있는 각도), `deadlift_feedback_v2_CLEAN.py`는 `atan2(|dx|, |dy|)`(절대값, 0~90도)를 사용합니다. 두 공식은 부호 처리가 달라 완전히 같은 값을 주지 않습니다.

## 2. 공통 지표 (3개 종목 모두 적용 가능)

"공통지표 (3개 종목 모두 사용가능)" 문서 기준, 아래 지표들이 정리되어 있습니다. 계산식/landmark 세부사항까지 원문에서 전부 확인되지는 않아, 확인된 범위만 기록합니다.

| 지표명 | 적용 운동 | 설명 | 현재 코드 적용 여부 |
|---|---|---|---|
| `foot_width` | 공통 | 발 너비 (정규화 거리) | 문서화됨 — 실 코드 존재 여부는 저장소에 코드가 없어 확인 불가 |
| `foot_x_asymmetry` | 공통 | 좌우 발 위치 비대칭 | 상동 |
| `foot_foreaft_asymmetry` | 공통 | 앞뒤 발 위치 비대칭 | 상동 |
| `foot_flatness` / `left_foot_flatness` / `right_foot_flatness` | 공통 | 발이 지면에 평평하게 닿아있는 정도 | 상동 |
| `hand_width` | 공통(주로 벤치프레스) | 손 너비 | 상동 |
| `hand_height_diff` | 공통 | 좌우 손 높이 차이 | 상동 |
| `shoulder_height_diff` | 공통 | 좌우 어깨 높이 차이 | 상동 |
| `head_hip_line` | 공통 | 머리-엉덩이 정렬 기준선 (벤치프레스에서는 `bench_line_diff`로도 지칭) | 상동 |
| `neck_lean` | 공통(주로 데드리프트) | 목 기울기 | 상동 |

## 3. 운동별 세부 지표

### 스쿼트

| 지표명 | landmark | 설명 | 상태 |
|---|---|---|---|
| 무릎 각도 | `landmark[23,25,27]` 계열(엉덩이-무릎-발목) | 무릎 굽힘 각도 | 완료 (기준지표 문서에 계산식 존재) |
| trunk_lean(몸통 기울기) | 어깨-엉덩이 벡터 | `trunk_lean = degrees(atan2(abs(dx), abs(dy)))` | 완료 (0526 `squat_feedback_v5` 반영: `TRUNK_LEAN_TOL_DEG=8.0`) |
| squat depth 기준선 | 전문가 최저 힙 y좌표 | "시각" 문서의 `depth` 오버레이(전문가 최저점 힙 y좌표 수평 점선) | 완료 (시각화까지 구현) |
| 발 접지/위치 | 발목·발끝 landmark | `foot_flatness` 등 공통지표 재사용 | 완료(지표 정의) |
| 무릎-발 정렬 | 발목 x좌표 기준 수직선 | "시각" 문서의 `ktg`(무릎-발끝 정렬 경고) 오버레이 | 완료 |
| 좌우 비대칭 | 좌우 무릎 y좌표 차이 | "시각" 문서의 `symmetry` 오버레이 | 완료 |

### 벤치프레스

| 지표명 | landmark | 설명 | 상태 |
|---|---|---|---|
| 팔꿈치 각도(`elbow_angle_avg`) | `landmark[11,13,15]` 계열 | 팔꿈치 굽힘/폄 각도 | 완료 |
| 손목-팔꿈치 x 정렬(`wrist_elbow_x_diff`) | 손목/팔꿈치 landmark | 수직 정렬 확인 | 완료(지표 정의) |
| `bench_line_diff` | 머리-엉덩이 라인 | 벤치 라인 기준 정렬 | 완료(지표 정의) |
| 양손 높이차(`hand_height_diff`) | 좌우 손목 | 공통지표 재사용 | 완료 |
| bar proxy 이동 | 좌우 손 중심 | `bar_proxy_center = (left_hand_center + right_hand_center) / 2` — **실제 바벨이 아니라 손 위치로 근사(proxy)** | 부분 구현 — 정확한 bar path는 [`limitations.md`](./limitations.md) 참고 |
| 좌우 팔 비대칭 | 좌우 팔꿈치 각도 | 공통 좌우 비대칭 로직 재사용 | 완료(지표 정의) |

### 데드리프트

| 지표명 | landmark | 설명 | 상태 |
|---|---|---|---|
| 몸통 기준선 | 어깨-엉덩이 | 공통 trunk 로직 재사용 | 완료 |
| 고관절 각도 | 어깨-엉덩이-무릎 | 힙 힌지 각도 | 완료 |
| 무릎 각도(락아웃 판정) | 엉덩이-무릎-발목 | `angle(landmark[23], landmark[25], landmark[27])`, 165~175도 이상이면 "펴짐"으로 판단 | 완료 |
| 팔꿈치 각도 | 어깨-팔꿈치-손목 | 공통 로직 재사용 | 완료(지표 정의) |
| 손목 기반 bar proxy | 손목 landmark | 벤치프레스와 동일한 proxy 방식 | 부분 구현 — 정확한 바벨 검출 아님 |
| 엉덩이-어깨 상승 순서 | 엉덩이/어깨 y좌표 시계열 | "엉덩이가 어깨보다 먼저 상승"하는 오류 패턴 탐지용으로 논의됨 | 검토 단계 — 정량적 threshold는 확인되지 않음 |
| 정강이 기울기 | 무릎-발목 | 원판이 정강이를 가리는 문제와 연결 | 부분 구현 — [`limitations.md`](./limitations.md) 참고 |
| 등/목 정렬 | `neck_lean` 등 | 공통지표 재사용 | 완료(지표 정의) |

> **주의**: 위 "상태" 열은 1차로 Notion 문서 기준이었으나, 이제 실제 코드(`unified_feedback_v4.py`의 `compute_metrics()` 등)로 검증되었습니다. "완료"는 코드에 해당 지표의 계산 로직이 실제로 존재함을 의미합니다. 다만 코드가 실제 영상에서 정확히 동작하는지(모델 파일·원본 영상 부재로) 실행 검증은 하지 못했습니다.

## 4. 바벨 관련 지표의 한계 (중요)

다음 지표들은 **MediaPipe Pose만으로는 정확히 구현할 수 없습니다.** MediaPipe는 사람의 관절만 검출하며 바벨/원판을 직접 검출하지 못합니다.

- 바벨과 어깨 사이의 실제 거리
- 바벨과 정강이 사이의 실제 거리
- 어깨와 바벨의 수직선 관계
- 정확한 bar path(바벨 이동 궤적)
- 원판의 위치와 이동 궤적

`unified_feedback_v4.py`의 `bar_proxy()` / `hand_grip_point()` 함수로 실제 구현을 확인했습니다: 손목(15/16) · 검지(19/20) · 엄지(21/22) landmark 중 visibility가 `OCCLUSION_THR(0.50)` 이상인 것만 골라 **visibility 가중 평균**을 내고, 그 신뢰도(`bar_proxy_conf`)를 함께 반환합니다. 좌우 손 모두 신뢰도가 `VIS_THR(0.45)` 이상일 때만 두 손의 가중 평균을 "바벨 위치"로 씁니다. `bar_proxy_conf < 0.55`이면 화면에 아예 표시하지 않습니다(`draw_bar_proxy_layer`). 즉 이는 실제 바벨 검출이 아니라 **"양손이 신뢰 가능하게 보일 때만 손 위치로 근사"**하는 명시적 안전장치가 있는 proxy입니다. YOLO 기반 바벨 검출은 실험이 진행되었으나 채택되지 않았습니다 — 자세한 내용은 [`limitations.md`](./limitations.md)와 [`experiments_and_results.md`](./experiments_and_results.md)를 참고하십시오.

## 5. 코드 파일 간 계산식 불일치 (중요)

`thresholds.md`에서 threshold 값이 파일마다 다름을 확인한 것과 마찬가지로, **일부 지표는 이름은 같지만 계산식 자체가 파일마다 다릅니다.**

### 5-1. `elbow_angle_avg`가 실제로는 "평균"이 아닌 경우

| 파일 | 계산식 |
|---|---|
| `benchpress_feedback_v4.py` | `(left_elbow_angle + right_elbow_angle) / 2.0` — 좌우 팔꿈치각의 실제 평균 |
| `deadlift_feedback_v2_CLEAN.py` (`compute_common_metrics`) | `(left_elbow_angle + right_elbow_angle) / 2.0` — 동일하게 실제 평균 |
| `unified_feedback_v4.py` (`compute_metrics`) | `put("elbow_angle_avg", elbow_angle, ...)` — **대표 side 하나의 `elbow_angle`을 그대로 복사**. 좌우 평균이 아님 |

`unified_feedback_v4.py`만 이름과 실제 계산 내용이 일치하지 않습니다. 좌우 비대칭이 있는 사용자의 경우 이 차이가 실제 판정 결과에 영향을 줄 수 있습니다.

### 5-2. `bench_line_diff`의 계산 방식 자체가 다름

| 파일 | 계산식 |
|---|---|
| `benchpress_feedback_v4.py` | `(max(nose_y, shoulder_c_y, hip_c_y) - min(...)) / torso_len` — 세 점의 y좌표 최대-최소 스프레드 |
| `deadlift_feedback_v2_CLEAN.py` (`compute_common_metrics`, bench 분기) | 위와 동일한 max-min 스프레드 방식 |
| `unified_feedback_v4.py` | `abs(cross(shoulder_c - hip_c, nose - hip_c)) / (\|shoulder_c - hip_c\| * torso_len)` — **어깨-엉덩이 직선에서 코(nose)까지의 수직 거리**(외적 기반 점-직선 거리 공식) |

두 방식은 기하학적으로 다른 값을 냅니다(스프레드 vs 수직거리). [`thresholds.md`](./thresholds.md) 0절에서 다룬 "`unified_feedback_v4.py`만 `bench_line_diff` threshold를 0.08→0.20으로 완화하고 ADVISORY로 강등한" 이유가 단순 threshold 차이가 아니라 **애초에 다른 공식으로 다른 값을 계산하고 있었기 때문일 가능성**이 있습니다. 2학기에 두 공식 중 하나로 통일할 것을 권장합니다.

### 5-3. 데드리프트 팔 관련 지표의 처리 차이

`unified_feedback_v4.py`는 데드리프트에서 손목·손끝·팔꿈치 landmark(13~22번)를 `STRUCTURAL_OCCLUSION`으로 지정해 `elbow_angle`, `elbow_angle_avg`, `wrist_elbow_x_diff`, `bar_proxy_conf`를 `ADVISORY`(참고용, 오류 판정에서 제외)로 강등합니다. 반면 `deadlift_feedback_v2_CLEAN.py`의 `SIDE_RELIABLE_METRICS['deadlift']`는 `elbow_angle_avg`를 핵심 판정 지표 목록에 포함시킵니다. 즉 **팔꿈치 각도를 데드리프트 오류 판정에 쓸지 말지가 두 파일에서 다르게 결정**되어 있습니다. `unified_feedback_v4.py` 쪽의 판단 근거(바벨에 가려져 신뢰도가 낮다는 것)가 코드 주석으로 명확히 남아 있어 더 설득력이 있으나, 어느 쪽이 최종 채택되어야 하는지는 팀 확인이 필요합니다.

관련 문서: [`thresholds.md`](./thresholds.md), [`pose_landmarks_and_csv.md`](./pose_landmarks_and_csv.md), [`limitations.md`](./limitations.md)
