# Pose Landmark와 CSV 저장 방식

## 1. 왜 영상 대신 landmark 좌표를 저장하는가

초보자를 위해 먼저 원리를 설명합니다.

운동 자세를 분석하는 방법은 크게 두 가지입니다.

1. **영상(픽셀) 자체를 모델 입력으로 사용**: 매 프레임의 모든 픽셀 값을 그대로 딥러닝 모델에 넣는 방식입니다. 배경, 조명, 옷 색깔처럼 자세 판단과 무관한 정보까지 포함되어 있어 학습이 어렵고 계산량이 매우 큽니다.
2. **pose landmark 좌표만 추출해서 사용**: MediaPipe 같은 pose 추정 모델로 사람의 관절 위치(x, y, z, visibility)만 먼저 뽑아낸 뒤, 이 숫자들만 저장해서 사용하는 방식입니다.

이 프로젝트는 2번 방식을 기본으로 합니다. 장점은 다음과 같습니다.

- **반복 추출 불필요**: 한 번 영상에서 landmark를 뽑아 저장해 두면, 이후 종목 인식/횟수 카운팅/자세 비교 등 여러 모델을 학습할 때 매번 무거운 pose 추정을 다시 돌릴 필요가 없습니다.
- **학습 속도와 저장 공간**: 영상 파일(수십~수백 MB)보다 landmark 좌표 표(수십~수백 KB)가 훨씬 작아 저장과 학습이 빠릅니다.
- **배경/조명 영향 감소**: 좌표값만 남기므로 배경색, 조명 밝기, 카메라 기종 등 자세와 무관한 요소의 영향을 줄일 수 있습니다.
- **skeleton 기반 시계열 모델의 입력으로 사용 가능**: ST-GCN, TCN처럼 관절 좌표의 시간적 변화를 학습하는 모델은 애초에 이런 좌표 시계열을 입력으로 받도록 설계되어 있습니다.
- **프레임 단위/시계열 단위 분석 모두 가능**: 한 프레임의 좌표만 보면 정적 자세 분석(예: 특정 순간의 무릎 각도)에, 여러 프레임을 이어보면 동작 흐름 분석(예: 스쿼트 하강-상승 궤적)에 쓸 수 있습니다.

## 2. MediaPipe Pose Landmark 개요

"모션인식 study - kim" 문서에 다음과 같이 설명되어 있습니다.

> "MediaPipe에서 사람 몸을 0~32번까지 총 33개의 점으로 매핑해놓은 규칙"
> "관절위치(x,y)는 픽셀위치가 아니라 비율(0~1) 임"

즉, MediaPipe Pose는 사람의 몸을 33개의 landmark(관절점)로 표현하며, 각 landmark는 이미지의 가로/세로 크기에 대한 **상대적 비율(0~1 사이 정규화 좌표, x_norm/y_norm)** 로 표현됩니다. 픽셀 좌표로 바꾸려면 `(x_norm × 이미지 너비, y_norm × 이미지 높이)`를 계산하면 됩니다.

MediaPipe Pose Landmarker는 이 정규화 좌표 외에 다음 값도 함께 제공합니다(MediaPipe 공식 스펙 기준 — 이 프로젝트의 실제 CSV 컬럼으로 확인된 것은 아래 "3. 실제 확인된 CSV 스키마"를 참고하십시오).

- **z 좌표**: 카메라와의 상대적 깊이(depth). 값이 작을수록 카메라에 가깝습니다.
- **visibility**: 해당 관절이 화면에서 보일 확률(가려짐 여부의 신뢰도)
- **world coordinate**: 이미지 좌표계가 아니라 실제 3차원 공간(미터 단위)을 기준으로 한 좌표로, 카메라와의 거리에 영향을 덜 받는 값입니다.

## 3. 실제 확인된 저장 스키마

### 3-1. 메인 파이프라인: 전문가(expert) landmark/지표 JSON

`src/posture_feedback/unified/unified_feedback_v4.py`의 `save_expert_profile()` / `build_expert_profile()`과, 실제 샘플 파일 `src/posture_feedback/benchpress/expert_benchpress.json`(215 프레임, 원본 그대로 저장소에 포함)을 통해 **실제 저장 포맷을 코드 수준으로 확인**했습니다. 영상 자체가 아니라 이 JSON 하나가 "landmark를 저장해서 반복 추출을 피한다"는 1절의 설명이 실제로 구현된 결과물입니다.

최상위 구조:

```json
{
  "version": "unified_feedback_v2",
  "fps": 20.975609756097562,
  "source_video": "expert_benchpress_v3.mp4",
  "frames": [ { ... }, { ... }, ... ]
}
```

| 필드 | 설명 |
|---|---|
| `version` | 코드 버전 태그. 실제 파일명(`unified_feedback_v4.py`)과 내부 버전 문자열(`unified_feedback_v2`)이 일치하지 않는 상태 그대로입니다 — [`system_pipeline.md`](./system_pipeline.md) 참고 |
| `fps` | 원본 영상의 초당 프레임 수 |
| `source_video` | 전처리에 사용한 원본 영상 파일명(문서화 과정에서 팀의 로컬 Windows 절대경로를 상대 파일명으로 정리함) |
| `frames` | 프레임별 데이터 배열. 길이 = 영상 총 프레임 수(예시 파일은 215개) |

`frames[i]` (프레임 1개) 구조:

| 필드 | 타입 | 설명 |
|---|---|---|
| `frame_idx` | int | 프레임 순번(0부터) |
| `timestamp_ms` | int | 영상 시작 기준 타임스탬프(ms) |
| `side` | str | `"left"` / `"right"` — 이 프레임에서 대표 side로 선택된 쪽 (`SideLock` 클래스가 결정) |
| `landmarks` | `number[33][4]` 또는 `null` | MediaPipe 33개 landmark × `[x, y, z, visibility]`. 검출 실패 프레임은 `null` |
| `metrics` | object | 이 프레임에서 계산된 자세 지표 값(딕셔너리). 예시 파일 기준 키: `knee_angle, hip_angle, elbow_angle, elbow_angle_avg, lockout_angle_min, trunk_lean, trunk_lean_signed, trunk_theta, neck_lean, foot_flatness, head_hip_line, wrist_elbow_x_diff, bench_line_diff, elbow_above_shoulder, bar_proxy_conf` |

`x`, `y`는 MediaPipe의 이미지 정규화 좌표(0~1, 이미지 가로/세로 크기에 대한 상대값)이고, `z`는 카메라 기준 상대 깊이, `visibility`는 해당 관절이 보일 확률입니다(2절 참고). **world coordinate(미터 단위 실좌표)는 이 JSON에는 저장되어 있지 않습니다** — 코드가 `pose_landmarks`(정규화 좌표)만 사용하고 `pose_world_landmarks`는 사용하지 않는 것으로 확인됩니다. 과제에서 예시로 든 `x_world_m` 등의 컬럼은 이 프로젝트에는 존재하지 않습니다.

`benchpress_feedback_v4.py`(단독 실행 스크립트)도 동일한 `expert_benchpress.json` 포맷을 그대로 읽어 사용하며(`load_expert_json`), 자체적으로 JSON을 생성하지는 않습니다 — JSON이 없으면 즉시 오류를 냅니다. 반면 `unified_feedback_v4.py`는 JSON이 없을 때 전문가 영상에서 **자동으로 전처리해 JSON을 생성**합니다(`build_expert_profile`).

### 3-2. 별도 실험 트랙: `exercise_angles.csv`

"관절 각도 이용 운동 기록" Notion 문서에서 확인된 CSV로, **MediaPipe가 아니라 YOLOv8-pose(COCO 17 keypoint) 기반의 별도 실험 트랙**에서 사용되었으며 위 3-1의 메인 파이프라인과는 무관합니다.

| 컬럼명 | 설명 |
|---|---|
| `Side` | 좌/우 측면 구분으로 추정 (원문에 상세 설명 없음) |
| `Shoulder_Angle`, `Elbow_Angle`, `Hip_Angle`, `Knee_Angle`, `Ankle_Angle` | 관절 각도 |
| `*_Ground_Angle` 계열 (5개) | 지면 기준 각도로 추정 |
| `Label` | 운동 종목/동작 라벨 |

행 수는 31,033행이며, YOLOv8n-pose + TCN 실험(정확도 99.03%, macro-F1 98.97%)에 사용되었습니다. 이 CSV의 원본 파일은 이번 조사에서 확보하지 못했습니다.

## 4. 정규화 관련 확인된 사항

Notion "사용자/기준 영상 정규화 및 판단지표" 문서와 실제 `unified_feedback_v4.py` 코드를 함께 확인한 결과는 다음과 같습니다.

- **위치·크기 정규화**: 구현 완료. `torso_length`(어깨중심-엉덩이중심 거리)로 나누는 방식이 모든 거리 지표에 일관 적용됩니다.
- **landmark 좌표 자체의 프레임 간 smoothing**: 구현 완료. `LandmarkSmoother` 클래스가 EMA(지수이동평균, `alpha=0.35`, 전문가 쪽은 `0.30`)를 적용하며, 특정 관절의 visibility가 낮아지면 좌표를 직전 값으로 유지하고 visibility만 점진적으로 낮추는 방식으로 "튀는" 것을 방지합니다.
- **좌우 side 선택 안정화**: 구현 완료. `SideLock` 클래스가 프레임마다 더 잘 보이는 쪽(left/right)의 visibility 합을 비교하되, 일정 프레임(`SIDE_SWITCH_HOLD=6`) 이상 반대쪽이 우세해야만 전환하는 히스테리시스를 적용해 좌우가 매 프레임 깜빡이며 바뀌는 문제를 완화합니다.
- **카메라 회전 메타데이터 보정**: 구현 완료(부분적). `get_video_rotation()`이 `ffprobe`로 영상의 회전 메타데이터(0/90/180/270도)를 읽어 `apply_rotation()`으로 픽셀에 적용합니다. 단 시스템에 `ffmpeg/ffprobe`가 없으면 조용히 회전 보정을 건너뜁니다.
- **전문가-사용자 화면 방향(각도) 정렬**: **종목별로 다르게 구현**되어 있습니다. `ALIGN_EXPERT_ORIENTATION`이 벤치프레스만 `True`(전신축 방향을 사용자 기준으로 회전시켜 정렬), 스쿼트·데드리프트는 `False`입니다. 코드 주석은 그 이유를 다음과 같이 설명합니다: "데드는 동작 중 상체가 숙임→직립으로 전신축이 크게 변한다... 회전을 한 번 고정하면 직립 구간에서 expert만 기울어 보이고, 매 프레임 돌리면 빙글빙글 돌아 더 어지럽다." 즉 데드리프트/스쿼트의 회전 정규화는 "향후 적용 예정"이 아니라 **"동작 특성상 단순 회전 정렬은 오히려 역효과라고 판단해 의도적으로 껐다"**는 것이 정확한 서술입니다.
- 참고 논문(Liu et al., 2021, ICCV *Normalized Human Pose Features*)의 정규화 기법은 Notion 기록상 "상당히 별로라서 굳이 쓸 필요가 없어보임"이라는 이유로 채택되지 않았다고 기록되어 있으며, 실제 코드에서도 이 논문 기법은 확인되지 않습니다.

거리/각도 계산의 기본 공식은 다음과 같이 문서화되어 있습니다("기준지표").

```
distance = sqrt((x1-x2)^2 + (y1-y2)^2 + (z1-z2)^2)
shoulder_center = (landmark[11] + landmark[12]) / 2
hip_center = (landmark[23] + landmark[24]) / 2
torso_length = distance(shoulder_center, hip_center)
normalized_distance = distance(landmark[A], landmark[B]) / torso_length
```

몸통 길이(`torso_length`)로 나누어 무차원화함으로써, 촬영 거리/사용자 체형 차이에 따른 절대 좌표 값의 편차를 줄이는 방식입니다.

관련 문서: [`exercise_metrics.md`](./exercise_metrics.md), [`thresholds.md`](./thresholds.md)
