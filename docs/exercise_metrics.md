# 운동 자세 지표 (Exercise Metrics)

> threshold(임계값)는 이 문서가 아니라 [`thresholds.md`](./thresholds.md)에 별도 정리했습니다. 이 문서는 "어떤 지표를 어떤 landmark로 어떻게 계산하는가"만 다룹니다.

## 1. 계산 방식의 기본 원리

"기준지표"/"공통지표" 문서에 공통으로 등장하는 두 가지 연산이 모든 지표의 기반입니다.

- **거리(정규화 거리)**: `distance(A,B) = sqrt((x1-x2)^2 + (y1-y2)^2 + (z1-z2)^2)`, 그리고 `normalized_distance = distance(A,B) / torso_length` (몸통 길이로 나눠 무차원화)
- **각도**: 세 점(또는 두 벡터) 사이의 각도를 벡터 내적으로 계산 — `theta = arccos(dot(u,v) / (norm(u)*norm(v)))`

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

> **주의**: 위 "상태" 열은 Notion 문서에 계산식/threshold가 정의되어 있는지를 기준으로 판단한 것이며, 실제 코드가 정상 동작하는지를 검증한 것은 아닙니다(저장소에 코드가 없어 실행 검증 불가). "완료"는 "수식/threshold까지 문서화 완료"를 의미하고, 실제 배포 가능한 수준의 완성도를 의미하지 않습니다.

## 4. 바벨 관련 지표의 한계 (중요)

다음 지표들은 **MediaPipe Pose만으로는 정확히 구현할 수 없습니다.** MediaPipe는 사람의 관절만 검출하며 바벨/원판을 직접 검출하지 못합니다.

- 바벨과 어깨 사이의 실제 거리
- 바벨과 정강이 사이의 실제 거리
- 어깨와 바벨의 수직선 관계
- 정확한 bar path(바벨 이동 궤적)
- 원판의 위치와 이동 궤적

현재는 손목/손 landmark를 바벨 위치의 **proxy(근사값)** 로 사용하고 있으며, 이는 실제 바벨 검출이 아닙니다. YOLO 기반 바벨 검출은 실험이 진행되었으나 채택되지 않았습니다 — 자세한 내용은 [`limitations.md`](./limitations.md)와 [`experiments_and_results.md`](./experiments_and_results.md)를 참고하십시오.

관련 문서: [`thresholds.md`](./thresholds.md), [`pose_landmarks_and_csv.md`](./pose_landmarks_and_csv.md), [`limitations.md`](./limitations.md)
