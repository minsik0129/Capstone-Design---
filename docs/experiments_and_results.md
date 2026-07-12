# 1학기 실험 결과 (Experiments and Results)

> 이 문서의 모든 수치는 Notion 회의록/기술 문서에 실제로 기록된 값만 인용합니다. 임의로 만들어낸 성능 수치는 없습니다. 각 항목에 출처(날짜/문서명)를 표기했습니다. 실험에 사용된 코드/노트북은 GitHub 저장소에는 없으며 Notion에 파일명만 언급되어 있습니다.

## 1. 운동 종목 인식 (ActionRecognizer)

### 1-1. ST-GCN 기반 (메인 트랙, MediaPipe 33 landmark, x/y 좌표만 사용)

- 입력 형태: `(N, 2, 100, 33, 1)` — 채널 2(x,y), 프레임 100(고정 길이), 관절 33, 사람 1명
- 데이터: Kaggle "Workout/Exercises Video" 167개 영상 (benchpress 100 / deadlift 44 / squat 23)
- **결과: test loss 0.3300, test accuracy 0.9231, test macro F1 0.8944** (종목 인식 및 횟수 기록)
- 클래스별: benchpress precision 1.0000/recall 0.8750/F1 0.9333(support16), deadlift precision 0.6000/recall 1.0000/F1 0.7500(support3), squat precision/recall/F1 1.0000(support7)
- Confusion matrix: 총 26개 중 24개 정답. 오분류는 주로 benchpress → deadlift
- **실제 영상 재검증(스쿼트4/벤치1/데드2)에서는 벤치프레스·데드리프트가 스쿼트로 잘못 분류되는 문제가 발생** — 학습 데이터와 실사용 환경의 괴리로 판단
- 상태: **구현 완료 + 실사용 검증에서 한계 확인**

### 1-2. TCN 기반 (관절 각도 입력, 0428)

- Train/Val/Test: 146/31/32 (benchpress 66/14/14, deadlift 18/4/4, squat 62/13/14)
- test accuracy 87.50%, macro F1 0.8772, best epoch 20(val F1 0.8666)

### 1-3. 파일럿 비교 (Kaggle 22종목 652개 영상, 0413, 3대 운동 데이터셋 아님)

- MediaPipe/YOLOv8-pose × TCN/ST-GCN 4개 조합 비교: **YOLOv8+ST-GCN이 최고 성능 (Accuracy 78.18%, F1 0.7810)**
- 이 실험은 3대 운동 전용 데이터셋이 아니므로 위 1-1, 1-2와 직접 비교할 수 없습니다.

### 1-4. YOLOv8n-pose + TCN (별도 실험 트랙, "관절 각도 이용 운동 기록")

- Kaggle "Exercise Detection Dataset"(`exercise_angles.csv`, 31,033행, 5개 클래스)
- **Accuracy 99.03%, Macro-F1 98.97%** (파라미터 230,725개)
- 이 실험은 3대 운동 전용이 아닌 별도 데이터셋 기준이며, confusion matrix·training curve가 문서에 첨부되어 있습니다.

## 2. Phase(단계) 분석

### 2-1. ST-GCN action+phase 멀티태스크 (0512)

- 학습 윈도우 1830 / 검증 369, 파라미터 1,888,908개
- Best(epoch 41): Action F1 0.938(epoch33 최고), Phase Acc 0.705, Count MAE 0.430, Count OBO 0.950, Best score 2.511
- ST-GCN+LSTM 시도했으나 GPU 자원 부족으로 실패 (0512)

### 2-2. window 크기 실험 v5/v6/v7 (0514)

- v6: Action F1 0.957(epoch59, 최고), Count MAE 0.17(epoch53, 최고)
- 영상 단위 평가(val 42개): v6 Count MAE 1.40/OBO 0.79, v7 accuracy 1.000/MAE 1.62/OBO 0.76

### 2-3. CTR-GCN 앙상블 (0528, 0602)

- 구조: Action Head / Phase Head / Motion Head 멀티태스크
- 0528: Action Acc 1.000, Action F1 0.948, Phase Acc 0.836, Phase F1 0.793, Count MAE 3.07, OBO 0.69
- 0602: Count MAE **1.69**(개선), OBO **0.762**(개선)

### 2-4. Phase 성능 저하 정밀 분석 (0602, "phase 성능 저하 분석")

- GT phase 분포: ready 34.0% / down 34.7% / up 31.3% — 예측은 ready로 쏠림(39.8~40.3%)
- **deadlift up phase F1 0.336**으로 특히 낮음
- boundary(전환 경계 근처 5프레임) accuracy 0.576 vs middle accuracy 0.707 (약 13.1%p 차이)
- 전환 예측이 평균 +11.68~12.77프레임 늦게 나타남 (late rate 58.9~63.0%)
- 종목별 macro F1: squat 0.743, benchpress 0.491, deadlift 0.486
- 상태: **실험/디버깅 진행 중** — 원인 규명 단계이며 해결책은 미적용

## 3. 횟수 카운팅 (RepCounter)

### 3-1. Binary mask 기반 v1 (실패)

- 라벨의 99.8%가 "rep 중"으로 표시되어 학습 신호 부족, 1670프레임이 1rep으로 오인식되는 문제 (0505)

### 3-2. Gaussian density 기반 v2 (개선)

- 종목 인식 정확도 92.86%, MAE 2.972, OBO 0.5
- ST-GCN backbone: v1 macro-F1 0.920/acc 0.923(epoch28), v2 macro-F1 0.857/acc 0.875(epoch23)
- Val MAE 0.60~0.90 / OBO 0.78~0.85 (v1은 MAE 0.62~1.23 / OBO 0.62~0.87 — v2가 개선)
- deadlift 26개 영상 · 69개 rep으로 학습 (0505)

### 3-3. 실시간 valley 기반 카운팅 (0602, 신규 도입)

- density/phase 그래프의 valley(골)를 이용해 실시간으로 반복 횟수 카운트
- 처리 속도 **17.0 fps**로 보고됨
- 상태: **신규 구현, 실시간성 확보** — 정확도(오차)에 대한 정량 지표는 CTR-GCN 앙상블 결과(위 2-3)와 함께 참고

### 3-4. Savitzky-Golay + find_peaks (별도 트랙, "관절 각도 이용 운동 기록")

- `scipy.signal.find_peaks` + Savitzky-Golay Filter(`window_length=11, polyorder=3`)
- 종목별 파라미터(예: Squats — Knee_Angle 추적, Valley, prominence 15, distance 30)
- 실제 검증: squat02는 1회 실제/1회 예측(정확), squat01은 2회 감지(실제 1회, MAE=0.5) — **과제 지시문이 예로 든 "스쿼트 3회를 2회로 계산" 유형의 오류와 유사한 패턴**

### 3-5. 종합 판단

과제 지시문에서 언급한 "실제 횟수와 예측 횟수 불일치" 문제는 위 3-1(binary mask 실패), 3-4(YOLOv8-pose 트랙 오차)에서 구체적으로 확인됩니다. 3-3(valley 기반)과 CTR-GCN count head(3-2, 2-3)는 개선된 결과를 보이나 여전히 MAE > 1인 경우가 있어 **완전히 해결된 문제는 아닙니다.**

## 4. YOLO 기반 모델 비교 (Ablation, 0611 "yolo 모델 검출")

| 순위 | 입력 조합 | Phase F1 | Action F1 | Count MAE | Count OBO |
|---|---|---|---|---|---|
| 1 | MediaPipe full pose + derivative | 0.662 | 0.961 | 2.048 | 0.714 |
| 2 | MediaPipe full pose MLP grid | — | 1.000 | 2.000 | — |
| 3 | YOLO-pose COCO17 | 0.587 | — | — | — |
| 6(최하위) | YOLO-World barbell center(단일입력) | 0.506 | 0.692 | 4.619 | — |

**결론: MediaPipe 전신 pose 기반이 실측 최고 성능이며, YOLO-pose·YOLO-World 바벨 검출 기반 입력은 모두 하위권입니다.** 바벨 검출은 실험까지 완료되었으나 채택되지 않았습니다.

같은 문서의 검출률 통계: 전체 208개 영상(squat 89/benchpress 94/deadlift 25), 138,892프레임 중 138,537 검출(99.74%), 최저 검출율 82.75%(benchpress).

## 5. Feature 결합 비교 (0609)

- pose(3채널) macro-F1 0.6625
- velocity(5채널) macro-F1 0.6534 (deadlift F1은 오히려 최고 0.5240, MAE 최저 1.7619)
- velocity+acceleration(7채널) macro-F1 0.6480 (가장 낮음)
- yolo_pose(17kp) macro-F1 0.5868 (MediaPipe보다 저조)

속도/가속도 feature를 추가한다고 항상 성능이 좋아지는 것은 아니며, deadlift에서만 velocity feature가 도움이 되는 등 종목별로 다른 경향을 보였습니다.

## 6. 자세 피드백 시각화 (구현 완료, "시각" 문서)

`realtime_compare_side.py`, `feedback_overlay.py`에 구현된 오버레이 13종:

1. heatmap (스켈레톤 델타 히트맵)
2. rom (가동범위 게이지)
3. score_bar (자세 점수 바)
4. ktg (무릎-발끝 정렬 경고선)
5. arc (관절 각도 반원 게이지, 사용자 흰색 vs 전문가 파란 테두리)
6. depth (스쿼트 깊이 기준선)
7. metricbar (지표별 사용자 vs 전문가 비교 바)
8. phase (준비→하강→최저점→상승 색상 블록)
9. symmetry (좌우 비대칭 바)
10. tempo (속도 파형 + 적정속도 점선)
11. acl (ACL 부상위험도 SAFE/CAUTION/RISK)
12. time trail (최근 4초 궤적)
13. height trail (구간별 누적 평균 궤적)

## 7. 통합 코드

`unified_feedback_v4.py`가 0602 회의록에 "완성"으로 기록되어 있으며, 실행 예시는 다음과 같이 인용되어 있습니다.

```
python unified_feedback_v4.py --exercise squat
python unified_feedback_v4.py --exercise deadlift
python unified_feedback_v4.py --exercise benchpress
```

**이 파일은 GitHub 저장소에는 존재하지 않으며, Notion 기록으로만 확인됩니다.** 2학기에 실제 코드를 저장소에 커밋하는 것이 최우선 과제입니다([`second_semester_plan.md`](./second_semester_plan.md) 참고).

관련 문서: [`limitations.md`](./limitations.md), [`second_semester_plan.md`](./second_semester_plan.md)
