# Threshold 값 정리 (Thresholds)

> **중요**: 이 문서에 기록된 모든 threshold는 "절대적인 의학적/운동역학적 기준"이 아닙니다. "종목별 threshold 값" Notion 문서 서두에 팀이 직접 남긴 문구를 그대로 인용합니다.
>
> "springer nature, ipf powerlifting rulebook, e-science sports 등을 보면 발너비 = 몸통길이 대비 0.10 이와같이 정확한 수치를 알려주지는 않음... 굉장히 애매하다"
>
> 즉 IPF 규정집이나 논문은 **정성적인 지침만 제공**하며, 아래 표의 실제 숫자는 팀이 그 지침을 해석해서 정한 값입니다. "논문에서 도출된 값"처럼 표현하지 않도록 주의하십시오.

## 1. threshold의 두 가지 출처

### 1-1. 초기값 (경험적 초기값, 팀 표기: "GPT가 임의로 선정")

| 지표 | 값 |
|---|---|
| `foot_width` | 0.15 |
| `foot_x_asymmetry` | 0.10 |
| `foot_foreaft_asymmetry` | 0.10 |
| `foot_flatness` / `left_foot_flatness` / `right_foot_flatness` | 0.04 |
| `hand_width` | 0.20 |
| `hand_height_diff` | 0.07 |
| `shoulder_height_diff` | 0.05 |
| `head_hip_line` | 0.10 |
| `neck_lean` | 10.0° |
| `wrist_shoulder_y_diff` | 0.15 |
| `elbow_angle_avg` | 12.0° |

이 값들은 팀이 직접 "GPT가 임의로 선정한 초기 Threshold 값들"이라고 출처를 명시했습니다. **경험적 초기값**이며 실험적 검증을 거치지 않은 상태입니다.

### 1-2. 정제된 종목별 값 (문헌의 정성적 지침 + 팀 판단으로 조정)

| 지표 | 스쿼트 | 데드리프트 | 벤치프레스 | 참고 자료 |
|---|---|---|---|---|
| `foot_width` | 0.10 | 0.10 | (해당없음 — `foot_offset` 0.10로 대체) | Escamilla et al. 2000 / IPF 2026 rulebook |
| `foot_x_asymmetry` | 0.08~0.10 | 0.08 | — | IPF 2026 rulebook |
| `foot_flatness` | 0.04 | 0.04 | 0.04 | Springer Nature / NSCA |
| `hand_width` | — | 0.12 | 0.15~0.20 | IPF 2026 rulebook / Escamilla et al. 2000 |
| `shoulder_height_diff` | 0.05 | 0.05 | 0.07 | IPF 2026 rulebook |
| `head_hip_line` (`bench_line_diff`) | 0.10 | 0.08~0.10 | 0.08 | IPF 2026 rulebook |
| `neck_lean` | 10.0° | 10.0° | — | NSCA deadlift guide |
| `elbow_angle_avg` / lockout 각도 | 12.0° | 12.0° | lockout_angle_min 165° | IPF 2026 rulebook / NSCA |

각 값 옆에는 팀의 자체 조정 논리가 함께 기록되어 있습니다. 예:

> "IPF 규칙에서도... 발 위치 비대칭은 0.10보다 조금 엄격한 0.08이 적절" (스쿼트 `foot_x_asymmetry`)
>
> "MediaPipe의 발끝·뒤꿈치 랜드마크는 흔들림이 크기 때문에 0.02처럼 너무 엄격하면 오탐이 많다. 따라서 0.04가 적절" (`foot_flatness`)

노란색으로 강조 표시된 지표(`foot_width`, `foot_flatness`, `shoulder_height_diff`, `head_hip_line` 등)는 "해당 종목에서 타이트하게 조정해야 하는 지표"로 별도 구분되어 있었습니다.

## 2. threshold 상태 분류 기준

과제 지침에 따라, 이 프로젝트의 threshold는 다음 중 하나로 분류됩니다.

- **경험적 초기값**: 1-1의 GPT 제안 값
- **팀 내부 실험값 + 문헌의 정성적 지침 결합**: 1-2의 정제된 값 (전문가 영상의 통계적 분포를 측정해서 산출한 값이 아님 — "전문가 영상 분포 기반"이라고 표현하지 않도록 주의)
- **데이터 기반 보정 필요 / 향후 validation set으로 조정 예정**: 위 모든 threshold에 공통 적용됨. 0430, 0514 회의록에서 팀 스스로 "threshold 근거 부족"을 인정한 기록이 있습니다.

## 3. threshold별 요약 (지시된 10개 항목 기준)

아래는 과제에서 요청한 10개 항목(이름/적용운동/landmark/계산식/단위/정규화여부/threshold값/근거/코드적용여부/한계) 중, **Notion 문서에서 실제로 확인 가능한 항목만** 채운 예시입니다. 전체 지표에 대해 10개 항목을 모두 채우려면 실제 코드와 원본 threshold 산출 근거 문서(IPF rulebook 대조표 등)에 대한 추가 접근이 필요합니다.

| 항목 | `foot_flatness` (예시) |
|---|---|
| 지표 이름 | `foot_flatness` |
| 적용 운동 | squat, deadlift, benchpress (공통) |
| 계산에 사용하는 landmark | 발/발목 관련 landmark (정확한 인덱스는 문서에 별도 명시되지 않음) |
| 계산식 | 정규화 거리 기반 (구체적 수식은 "기준지표" 문서의 일반 공식만 확인됨) |
| 단위 | 무차원(정규화) |
| 정규화 여부 | 예 (`torso_length` 기준) |
| threshold 값 | 0.04 (전 종목 공통) |
| threshold 근거 | Springer Nature / NSCA의 정성적 서술 + "MediaPipe 랜드마크 흔들림 고려" 팀 판단 |
| 현재 코드 적용 여부 | 저장소에 코드가 없어 확인 불가 (Notion 문서상 정의는 존재) |
| 한계 | 전문가 영상 분포에 대한 통계적 검증 없음. 발끝/뒤꿈치 landmark 자체의 노이즈가 큼 |

## 4. 요약: 절대적 기준으로 오해하지 말아야 할 것

- 이 threshold들은 **IPF 파워리프팅 대회 판정 규정을 그대로 코드화한 것이 아니라**, 규정의 정성적 취지를 팀이 정량적 수치로 "해석"한 것입니다.
- 팀은 이 값들을 실제 전문가 영상 다수의 통계 분포로 검증하지 않았습니다(전문가 영상 분포 기반 산출 아님).
- 2학기에는 validation set을 구성해 이 threshold들을 데이터 기반으로 재조정할 것을 권장합니다([`second_semester_plan.md`](./second_semester_plan.md) 참고).

관련 문서: [`exercise_metrics.md`](./exercise_metrics.md)
