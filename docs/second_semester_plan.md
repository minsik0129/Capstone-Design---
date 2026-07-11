# 2학기 개발 계획 (Second Semester Plan)

> 1학기 결과([`experiments_and_results.md`](./experiments_and_results.md), [`limitations.md`](./limitations.md))에서 도출된 계획입니다. 1학기에 이미 완료된 내용과 섞이지 않도록 이 문서는 "앞으로 할 일"만 다룹니다.

## P0 — 반드시 해결

1. **실제 소스 코드를 GitHub 저장소에 커밋** — 1학기 내내 Notion에만 기록되고 저장소에는 올라오지 않은 상태입니다. `unified_feedback_v4.py`, `phase_labeling.py`, `squat_feedback_v3~v5`, ST-GCN/CTR-GCN 학습 노트북 등을 이 저장소의 [권장 구조](../README.md#저장소-구조)에 맞춰 이관해야 합니다.
2. **데이터셋 수치 재확정** — [`dataset_history.md`](./dataset_history.md)에서 확인된 208개(0611) vs 209개(0428) 불일치, 특히 deadlift 25↔26개 차이의 원인을 실제 최신 라벨 CSV로 재검증
3. **deadlift 데이터 확충** — 3종목 중 지속적으로 최소·최저 성능. 0505 회의록 제안대로 30~60개 추가 수집

## P1 — 중요

4. **MediaPipe 대체/보완 모델 탐색** — 0618 지도교수 피드백("MediaPipe가 시퀀스를 안 본다")에 따른 시계열 처리 가능 모델 조사 (착수 전)
5. **Phase 경계 예측 정확도 개선** — boundary accuracy(0.576)가 middle(0.707)보다 크게 낮고, 전환 시점이 평균 11~13프레임 지연되는 문제 해결 (HMM/Viterbi 후처리, 라벨 스무딩 등 0521에서 제안되었으나 미구현)
6. **횟수 카운팅 정확도 추가 개선** — Count MAE가 1을 넘는 케이스가 남아있음. causal 실시간 추론, 자동 bottom-frame 검출 등 0505/0514의 제안 검토
7. **rule-based 방식과 학습 기반 방식 비교** — 현재 threshold(rule) 기반 오류판단과 ST-GCN/CTR-GCN 학습 기반 phase/count 예측이 병존. 두 접근의 장단점을 정리하고 통합 전략 수립
8. **threshold 데이터 기반 재조정** — 현재 threshold는 IPF 규정의 정성적 서술 + 팀 판단으로 정해진 값. validation set을 구성해 실측 기반으로 보정 ([`thresholds.md`](./thresholds.md))

## P2 — 개선

9. **벤치프레스·데드리프트 pose 인식 안정화** — 바벨/원판에 의한 관절 가림 문제 지속. 45도 다각도뷰 등 촬영 기준 표준화 완료 ([`capture_guidelines.md`](./capture_guidelines.md))
10. **전문가-사용자 영상 정규화 고도화** — 카메라 각도/회전 정규화는 아직 "향후 적용 예정" 단계
11. **YOLO 기반 바벨 검출 재검토** — 1차 실험(YOLO-World)에서는 6개 조합 중 최하위 성능이었으나, 모델/입력 방식을 바꿔 재시도할 가치가 있음
12. **feature 결합 방식 최적화** — 0609 실험에서 velocity/acceleration feature 추가가 항상 성능을 높이지는 않음을 확인. 종목별 최적 조합 탐색
13. **종목별 자세 피드백 고도화** — 특히 벤치프레스·데드리프트의 부분 구현 지표들을 완료 단계로 발전

## P3 — 장기 검토

14. **최종 통합 시스템 구성** — 0423~0507 교수 피드백에서 논의된 "모델 하나 + branch 구조" 방향의 아키텍처 확정 및 실제 구현
15. **성능 평가 기준 확립** — SRS의 비기능 요구사항(정확도 80%/90%, 응답 2초 이내 등)에 대한 공식 평가 프로토콜 수립
16. **LLM 기반 피드백/루틴 추천 검토** — API 비용 비교는 완료(월 $0.03~$5.40 수준), 실제 통합 여부는 미정
17. **데모 영상 및 최종 보고서 제작**

## 참고: 1학기 계획과의 관계

이 계획들은 모두 1학기 실험 결과에서 확인된 미해결 문제를 근거로 합니다. 1학기에 "실험/검토 단계"였던 항목을 2학기에 "구현 완료" 단계로 끌어올리는 것이 목표이며, 이미 완료된 항목(종목 인식 모델 학습, 시각화 오버레이 13종, 통합 CLI 등)을 재작업하는 것이 아닙니다.

관련 문서: [`limitations.md`](./limitations.md), [`experiments_and_results.md`](./experiments_and_results.md)
