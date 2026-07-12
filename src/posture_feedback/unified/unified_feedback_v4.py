# -*- coding: utf-8 -*-
"""
unified_feedback_v2.py

3대 운동(squat / deadlift / benchpress) 통합 자세 비교 + 시각적 피드백 코드 v2

반영 내용
- user / expert 영상 기반 비교. expert JSON이 없으면 expert 영상을 자동 전처리해서 JSON 캐시 생성
- squat / deadlift / benchpress 모두 같은 코드로 처리
- 출력 파일명: output/{종목명}_unified_feedback2.mp4
- landmark EMA smoothing 적용
- 측면영상 기준 visible side lock 적용
- generic 각도기 느낌 제거: 관절 중심 true arc 렌더러 적용
- expert skeleton bbox 정규화 후 중앙 배치
- deadlift / benchpress bar proxy confidence 적용
- 운동별 주요 레이어 분리

필요 패키지
    pip install "numpy<2" opencv-python mediapipe pillow

실행 예시
    python unified_feedback_v2.py --exercise squat
    python unified_feedback_v2.py --exercise deadlift
    python unified_feedback_v2.py --exercise benchpress
    python unified_feedback_v2.py --all

주의
- pose_landmarker_lite.task 파일이 현재 폴더에 있어야 합니다.
- 영상 파일명이 다르면 아래 VIDEO_CONFIG만 수정하면 됩니다.

파일명 안내:
    이 파일은 팀에서 "unified_feedback_v4.py"로 전달되었으나, 내부 docstring과
    save_expert_profile()의 version 필드는 "unified_feedback_v2"로 되어
    있다. 외부 파일명과 내부 버전 표기가 일치하지 않는 상태 그대로 보존했다
    (동작에는 영향 없음. 임의로 통일하지 않았다).

Purpose:
    스쿼트/데드리프트/벤치프레스 3종목을 하나의 CLI로 처리하는 통합
    사용자-전문가 비교 및 시각적 자세 피드백 코드. benchpress_feedback_v4.py,
    deadlift_feedback_v2_CLEAN.py와 달리 외부 rt/fo 모듈 없이 단일 파일로
    완결되어 있다.

Supported exercise:
    squat, deadlift, benchpress (그리고 CLI 별칭으로 bench, sq, dl, bp도
    normalize_exercise_name()에서 허용됨)

Input:
    - VIDEO_CONFIG[exercise]에 정의된 사용자/전문가 영상 파일명 (예:
      squat_15.mp4, user_deadlift_02.mp4, user_benchpress_v3.mp4)
    - 전문가 JSON이 없으면 전문가 영상에서 자동으로 전처리해 생성한다
      (build_expert_profile, save_expert_profile 참고) — 이는
      benchpress_feedback_v4.py가 JSON을 필수 사전 준비물로 요구하는 것과
      다른 점이다.
    - pose_landmarker_lite.task (이 저장소에는 미포함)

Output:
    output/{종목명}_unified_feedback_v4.mp4 (VIDEO_CONFIG의 output 값 기준)
    + (없었다면) expert JSON 캐시 파일

Main dependencies:
    opencv-python(cv2), mediapipe(mediapipe.tasks), numpy, Pillow(PIL)
    선택: ffprobe(영상 회전 메타데이터 확인용, subprocess로 호출 — 시스템에
    ffmpeg/ffprobe가 설치되어 있지 않으면 조용히 회전 보정을 건너뛴다)

Notes:
    - 측면 영상 전용. 3종목 모두 지원하는 유일한 자기완결형 스크립트.
    - 데드리프트는 바벨/원판에 가려지는 손목·팔꿈치 관련 landmark를
      STRUCTURAL_OCCLUSION으로 지정해 해당 지표를 ADVISORY(참고용, 오류
      판정 제외)로 강등한다 — MediaPipe가 바벨을 직접 인식하지 못하는
      한계에 대한 실제 코드 수준의 대응책이다.
    - 벤치프레스의 bench_line_diff는 카메라 각도에 민감해 "expert가 user의
      약 2배로 측정됨"이라는 코드 주석과 함께 ADVISORY로 강등되어 있고,
      threshold도 0.08(PDF/threshold 문서 값)이 아닌 0.20으로 완화되어
      있다 — 문서상 threshold를 실측 후 코드에서 재조정한 사례.
    - 팀이 "완전한 코드가 아니다"라고 밝혔으며, 이 저장소에서 직접 실행
      검증은 하지 못했다(pose_landmarker_lite.task, 실제 영상 파일 부재).
    - threshold 값이 benchpress_feedback_v4.py, deadlift_feedback_v2_CLEAN.py
      와 서로 다르다. 자세한 비교는 ../../../docs/thresholds.md 참고.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# ============================================================
# 0. 사용자 설정
# ============================================================

# 프로젝트 폴더. 기본값은 이 스크립트가 있는 폴더로 고정한다.
# (VS Code에서 다른 작업 디렉토리로 실행해도 파일을 정확히 찾도록)
# 필요하면 환경변수 HAND_PROJECT_DIR 로 덮어쓰거나 아래 경로를 직접 수정한다.
#   예: BASE_DIR = Path(r"C:\dev\hand_project")
BASE_DIR = Path(os.environ.get("HAND_PROJECT_DIR", Path(__file__).resolve().parent))
MODEL_PATH = BASE_DIR / "pose_landmarker_lite.task"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 새 벤치프레스 원본 반영 완료
# squat / deadlift 파일명은 본인 로컬 파일명에 맞게 필요 시 여기만 수정하세요.
VIDEO_CONFIG = {
    "squat": {
        "user_video": "squat_15.mp4",
        "expert_video": "expert_squat.mp4",
        "expert_json": "expert_squat.json",
        "output": "squat_unified_feedback_v4.mp4",
    },
    "deadlift": {
        "user_video": "user_deadlift_02.mp4",
        "expert_video": "expert_deadlift.mp4",
        "expert_json": "expert_deadlift.json",
        "output": "deadlift_unified_feedback_v4.mp4",
    },
    "benchpress": {
        "user_video": "user_benchpress_v3.mp4",
        "expert_video": "expert_benchpress_v3.mp4",
        "expert_json": "expert_benchpress.json",
        "output": "benchpress_unified_feedback_v4.mp4",
    },
}

# 화면 구성
EXPERT_W = 360
HUD_W = 360
MAX_OUTPUT_H = 720        # 너무 큰 원본이면 높이 기준으로 축소. 원본 크기 유지 원하면 None
MIN_PANEL_H = 620         # HUD 지표 행이 잘리지 않도록 하는 최소 패널 높이
MATCH_MODE = "ratio"     # "ratio" 권장. user/expert 길이가 달라도 진행률 기준 매칭

# MediaPipe / smoothing
VIS_THR = 0.45
OCCLUSION_THR = 0.50     # 이 값 미만이면 가려진 관절로 보고 해당 지표를 측정 불가 처리
LANDMARK_EMA_ALPHA = 0.35        # 낮을수록 부드러움, 높을수록 즉각 반응
EXPERT_EMA_ALPHA = 0.30
SIDE_SWITCH_MARGIN = 0.25
SIDE_SWITCH_HOLD = 6

# 색상(BGR)
C_BG = (18, 18, 24)
C_PANEL = (36, 36, 50)
C_LINE = (90, 220, 95)
C_LINE_DIM = (60, 130, 70)
C_OK = (90, 220, 120)
C_WARN = (80, 100, 255)
C_BAD = (40, 70, 255)
C_YELLOW = (0, 215, 255)
C_CYAN = (255, 210, 60)
C_WHITE = (235, 235, 235)
C_GRAY = (145, 145, 155)
C_DARKGRAY = (75, 75, 90)
C_ORANGE = (0, 155, 255)

# 한국어 폰트 후보
FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# 운동별 HUD 표시 지표
DISPLAY_METRICS = {
    "squat": ["knee_angle", "hip_angle", "trunk_lean", "foot_flatness", "head_hip_line"],
    "deadlift": ["knee_angle", "hip_angle", "trunk_lean", "elbow_angle", "head_hip_line", "bar_proxy_conf"],
    "benchpress": ["elbow_angle", "wrist_elbow_x_diff", "lockout_angle_min", "bench_line_diff", "bar_proxy_conf"],
}

METRIC_LABELS_KO = {
    "knee_angle": "무릎각",
    "hip_angle": "엉덩이각",
    "trunk_lean": "몸통기울기",
    "foot_flatness": "발바닥밀착",
    "head_hip_line": "머리-엉덩이",
    "neck_lean": "목-머리각",
    "elbow_angle": "팔꿈치각",
    "elbow_angle_avg": "팔꿈치각",
    "wrist_elbow_x_diff": "손목-팔꿈치",
    "lockout_angle_min": "락아웃각",
    "elbow_above_shoulder": "팔꿈치-어깨",
    "bench_line_diff": "벤치라인",
    "bar_proxy_conf": "바벨Proxy",
}

# 전문가와의 차이 허용치. angle은 degree, 비율 지표는 torso length 정규화값.
DELTA_THRESHOLDS = {
    "squat": {
        "knee_angle": 18.0,
        "hip_angle": 18.0,
        "trunk_lean": 10.0,
        "foot_flatness": 0.08,
        "head_hip_line": 0.18,
    },
    "deadlift": {
        "knee_angle": 18.0,
        "hip_angle": 18.0,
        "trunk_lean": 10.0,
        "elbow_angle": 20.0,
        "head_hip_line": 0.18,
        "bar_proxy_conf": 0.0,  # confidence는 delta 판단용이 아니라 HUD용
    },
    "benchpress": {
        "elbow_angle": 18.0,
        "wrist_elbow_x_diff": 0.08,
        "lockout_angle_min": 18.0,
        "bench_line_diff": 0.20,
        "bar_proxy_conf": 0.0,
    },
}

# 절대 기준. 전문가와 비교가 애매한 항목 보완용.
ABSOLUTE_RULES = {
    "squat": {
        "bottom_knee_too_open": 105.0,
        "trunk_lean_max": 35.0,
        "head_hip_line_max": 0.55,
    },
    "deadlift": {
        "top_knee_lockout_min": 155.0,
        "top_hip_lockout_min": 155.0,
        "elbow_lock_min": 155.0,
        "trunk_lean_max": 45.0,
    },
    "benchpress": {
        "lockout_min": 165.0,            # PDF: 상단에서 165도 이하면 락아웃 부족
        "bottom_elbow_min": 45.0,
        "wrist_elbow_x_diff_max": 0.10,  # PDF: 손목-팔꿈치 수직정렬 이탈 0.07~0.10 상한
    },
}


# ============================================================
# 경로 1: 종목별 구조적 가림(structural occlusion) 설정
# ------------------------------------------------------------
# MediaPipe의 visibility 점수는 바벨/원판에 의한 가림을 감지하지 못한다
# (가려진 관절도 높은 visibility로 추정해 버린다). 따라서 종목별로
# "구조적으로 신뢰하기 어려운 관절"을 명시한다.
#
# 처리 원칙:
# - STRUCTURAL_OCCLUSION에 속한 관절에 의존하는 지표는 ADVISORY로 강등한다.
# - ADVISORY 지표는 HUD에 값은 보여주되 '주의/오류'로 판정하지 않고(보조 지표),
#   파란 회색 톤으로 "참고"로 표시한다. PDF에서 데드 wrist_shoulder_y_diff를
#   보조 지표로만 쓰라고 한 것과 같은 취지.
# - bar proxy처럼 가려진 손목 추정에 의존하는 레이어는 해당 종목에서 끈다.
# ============================================================

# 손목(15,16)·손끝(17~22)·팔꿈치(13,14)는 데드/벤치에서 바벨·원판에 자주 가린다.
# 다만 측면영상에서는 카메라 쪽 팔이 보이는 경우가 많아, 일률적으로 막기보다
# 종목 특성에 맞춰 지정한다.
# - 데드리프트: 팔은 "바를 거는 고리"라 각도 자체가 판정 의미가 적고(PDF: 보조 지표),
#   손/손목이 바벨·원판과 겹쳐 신뢰도가 낮다 → 손/손목/팔꿈치를 구조적 가림으로 둔다.
# - 벤치프레스: 측면에서 카메라 쪽 팔(어깨-팔꿈치-손목)이 보이는 경우가 많으므로
#   구조적 가림으로 일괄 차단하지 않고, 프레임별 visibility gating에 맡긴다.
#   (가려진 쪽은 SideLock이 자동으로 반대쪽을 선택한다.)
STRUCTURAL_OCCLUSION = {
    "squat": set(),
    "deadlift": {13, 14, 15, 16, 17, 18, 19, 20, 21, 22},
    "benchpress": set(),
}

# 강등(보조)으로 표시할 지표: HUD에 값은 보이되 오류 판정에서 제외.
# STRUCTURAL_OCCLUSION 관절에 의존하는 지표를 여기에 둔다.
ADVISORY_METRICS = {
    "squat": set(),
    "deadlift": {"elbow_angle", "elbow_angle_avg", "wrist_elbow_x_diff", "bar_proxy_conf"},
    # bench_line_diff(머리-어깨-엉덩이 라인)는 측면 벤치에서 nose-어깨-엉덩이 기하가
    # 카메라 각도에 민감해 user/expert 비교가 불안정하다(expert가 user의 ~2배로 측정됨).
    # PDF 0.08 절대 기준을 강제하면 거의 항상 '주의'가 되어 노이즈가 되므로 보조 지표로 둔다.
    "benchpress": {"bar_proxy_conf", "bench_line_diff"},
}

# bar proxy 레이어를 그릴 종목(가려짐이 심하면 끈다).
# 벤치는 양손이 비교적 보여 grip center가 의미 있을 수 있으나,
# 데드는 손이 바벨/원판 뒤라 추정 신뢰도가 낮아 기본 비활성.
DRAW_BAR_PROXY = {
    "squat": False,
    "deadlift": False,
    "benchpress": True,
}

# expert 패널을 user 기준 방향으로 회전 정렬할지.
# - 스쿼트: user/expert 모두 서있어 정렬 불필요 → False.
# - 벤치: 누운 자세가 동작 내내 거의 고정(전신축 std 작음)이라 회전 정렬이 안정적 → True.
# - 데드: 동작 중 상체가 숙임→직립으로 전신축이 크게 변한다(std 큼).
#   회전을 한 번 고정하면 직립 구간에서 expert만 기울어 보이고, 매 프레임 돌리면
#   빙글빙글 돌아 더 어지럽다. 따라서 회전 정렬을 끄고 bbox 정규화에만 맡긴다.
ALIGN_EXPERT_ORIENTATION = {
    "squat": False,
    "deadlift": False,
    "benchpress": True,
}

POSE_CONNECTIONS = [
    (11, 12),
    (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
]

SIDE_IDS = {
    "left": {"shoulder": 11, "elbow": 13, "wrist": 15, "hip": 23, "knee": 25, "ankle": 27, "heel": 29, "foot": 31, "index": 19, "thumb": 21},
    "right": {"shoulder": 12, "elbow": 14, "wrist": 16, "hip": 24, "knee": 26, "ankle": 28, "heel": 30, "foot": 32, "index": 20, "thumb": 22},
}


@dataclass
class Issue:
    key: str
    message: str
    severity: float
    landmarks: List[int] = field(default_factory=list)


def find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for fp in FONT_CANDIDATES:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


_FONT_CACHE: Dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def get_font(size: int):
    if size not in _FONT_CACHE:
        _FONT_CACHE[size] = find_font(size)
    return _FONT_CACHE[size]


def bgr_to_rgb(c: Tuple[int, int, int]) -> Tuple[int, int, int]:
    return int(c[2]), int(c[1]), int(c[0])


def draw_text(
    img: np.ndarray,
    text: str,
    xy: Tuple[int, int],
    size: int = 22,
    color: Tuple[int, int, int] = C_WHITE,
    bold: bool = False,
) -> np.ndarray:
    """PIL 기반 한글 텍스트 렌더링."""
    if not text:
        return img
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    font = get_font(size + (2 if bold else 0))
    draw.text(xy, text, font=font, fill=bgr_to_rgb(color))
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def draw_round_rect(
    img: np.ndarray,
    p1: Tuple[int, int],
    p2: Tuple[int, int],
    color: Tuple[int, int, int],
    radius: int = 12,
    thickness: int = -1,
    alpha: Optional[float] = None,
) -> np.ndarray:
    """OpenCV rectangle fallback. radius는 단순 rectangle로 처리."""
    if alpha is None:
        cv2.rectangle(img, p1, p2, color, thickness)
        return img
    overlay = img.copy()
    cv2.rectangle(overlay, p1, p2, color, thickness)
    return cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def safe_float(v, default: float = 0.0) -> float:
    try:
        v = float(v)
        if math.isfinite(v):
            return v
    except Exception:
        pass
    return default


def angle_abc(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ba = a - b
    bc = c - b
    denom = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denom < 1e-9:
        return 0.0
    cosv = float(np.dot(ba, bc) / denom)
    cosv = clamp(cosv, -1.0, 1.0)
    return float(math.degrees(math.acos(cosv)))


def dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def normalize_exercise_name(name: str) -> str:
    n = name.lower().strip().replace("_", "").replace("-", "")
    if n in ["bench", "benchpress", "bp"]:
        return "benchpress"
    if n in ["squat", "sq"]:
        return "squat"
    if n in ["deadlift", "dl"]:
        return "deadlift"
    raise ValueError(f"알 수 없는 운동명: {name}")


# ============================================================
# 2. Landmark 처리
# ============================================================


def lms_to_np(lms) -> Optional[np.ndarray]:
    """MediaPipe landmark list -> (33,4) [x,y,z,visibility]."""
    if lms is None:
        return None
    arr = np.zeros((33, 4), dtype=np.float32)
    for i, p in enumerate(lms[:33]):
        arr[i, 0] = float(getattr(p, "x", 0.0))
        arr[i, 1] = float(getattr(p, "y", 0.0))
        arr[i, 2] = float(getattr(p, "z", 0.0))
        arr[i, 3] = float(getattr(p, "visibility", 1.0))
    return arr


def valid_lms(arr: Optional[np.ndarray]) -> bool:
    return arr is not None and isinstance(arr, np.ndarray) and arr.shape[0] >= 33


def get_xy(lms: np.ndarray, idx: int) -> np.ndarray:
    return np.array([float(lms[idx, 0]), float(lms[idx, 1])], dtype=np.float32)


def get_v(lms: np.ndarray, idx: int) -> float:
    return float(lms[idx, 3]) if lms is not None and idx < len(lms) else 0.0


def visible(lms: np.ndarray, idx: int, thr: float = VIS_THR) -> bool:
    return get_v(lms, idx) >= thr


def joint_ok(lms: np.ndarray, idx: int, thr: float = OCCLUSION_THR) -> bool:
    """occlusion gating: 이 관절이 가려지지 않고 신뢰 가능한지."""
    return get_v(lms, idx) >= thr


def all_ok(lms: np.ndarray, ids: Sequence[int], thr: float = OCCLUSION_THR) -> bool:
    """주어진 관절들이 모두 신뢰 가능하면 True. 하나라도 가려지면 False."""
    return all(joint_ok(lms, i, thr) for i in ids)


def mid(lms: np.ndarray, a: int, b: int) -> np.ndarray:
    pa, pb = get_xy(lms, a), get_xy(lms, b)
    va, vb = get_v(lms, a), get_v(lms, b)
    if va >= VIS_THR and vb >= VIS_THR:
        return (pa + pb) / 2.0
    return pa if va >= vb else pb


def vis_score(lms: np.ndarray, ids: Sequence[int]) -> float:
    if not valid_lms(lms):
        return 0.0
    return float(sum(max(0.0, min(1.0, get_v(lms, i))) for i in ids))


class LandmarkSmoother:
    """landmark 좌표 자체를 부드럽게 만드는 EMA smoother."""

    def __init__(self, alpha: float = 0.35, vis_thr: float = VIS_THR):
        self.alpha = float(alpha)
        self.vis_thr = float(vis_thr)
        self.prev: Optional[np.ndarray] = None

    def reset(self):
        self.prev = None

    def update(self, lms: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if not valid_lms(lms):
            return self.prev.copy() if self.prev is not None else None

        cur = lms.copy()
        if self.prev is None:
            self.prev = cur
            return cur

        out = self.prev.copy()
        for i in range(33):
            v = float(cur[i, 3])
            pv = float(self.prev[i, 3])
            if v >= self.vis_thr:
                out[i, :3] = self.alpha * cur[i, :3] + (1.0 - self.alpha) * self.prev[i, :3]
                out[i, 3] = max(v, 0.85 * pv)
            else:
                # 안 보이는 landmark는 갑자기 튀지 않게 이전 위치 유지, visibility만 감소
                out[i, :3] = self.prev[i, :3]
                out[i, 3] = 0.75 * pv
        self.prev = out
        return out


class SideLock:
    """측면영상에서 left/right 대표 side가 프레임마다 바뀌는 문제를 완화."""

    def __init__(self, exercise: str, margin: float = SIDE_SWITCH_MARGIN, hold: int = SIDE_SWITCH_HOLD):
        self.exercise = normalize_exercise_name(exercise)
        self.margin = margin
        self.hold = hold
        self.side: Optional[str] = None
        self.candidate: Optional[str] = None
        self.candidate_count = 0

    def _side_score(self, lms: np.ndarray, side: str) -> float:
        ids = SIDE_IDS[side]
        if self.exercise == "benchpress":
            key_ids = [ids["shoulder"], ids["elbow"], ids["wrist"], ids["index"], ids["thumb"]]
        else:
            key_ids = [ids["shoulder"], ids["hip"], ids["knee"], ids["ankle"], ids["foot"], ids["elbow"], ids["wrist"]]
        return vis_score(lms, key_ids)

    def update(self, lms: Optional[np.ndarray]) -> str:
        if not valid_lms(lms):
            return self.side or "right"

        ls = self._side_score(lms, "left")
        rs = self._side_score(lms, "right")
        best = "left" if ls >= rs else "right"

        if self.side is None:
            self.side = best
            return self.side

        cur_score = ls if self.side == "left" else rs
        alt_score = rs if self.side == "left" else ls
        alt_side = "right" if self.side == "left" else "left"

        if alt_score > cur_score + self.margin:
            if self.candidate == alt_side:
                self.candidate_count += 1
            else:
                self.candidate = alt_side
                self.candidate_count = 1
            if self.candidate_count >= self.hold:
                self.side = alt_side
                self.candidate = None
                self.candidate_count = 0
        else:
            self.candidate = None
            self.candidate_count = 0

        return self.side


# ============================================================
# 3. MediaPipe PoseLandmarker
# ============================================================


def create_landmarker(model_path: Path):
    if not model_path.exists():
        raise FileNotFoundError(f"PoseLandmarker 모델 파일이 없습니다: {model_path}")
    base_options = python.BaseOptions(model_asset_path=str(model_path))
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_poses=2,  # 보조자(스팟터)가 함께 잡히는 경우를 위해 2명까지 검출 후 선택
        min_pose_detection_confidence=0.45,
        min_pose_presence_confidence=0.45,
        min_tracking_confidence=0.45,
        output_segmentation_masks=False,
    )
    return vision.PoseLandmarker.create_from_options(options)


def extract_all_landmarks(landmarker, frame_bgr: np.ndarray, timestamp_ms: int) -> List[np.ndarray]:
    """검출된 모든 사람의 랜드마크 리스트를 반환(0~여러 명)."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect_for_video(mp_image, int(timestamp_ms))
    if not result.pose_landmarks:
        return []
    return [lms_to_np(p) for p in result.pose_landmarks]


def _torso_horizontalness(lms: np.ndarray) -> float:
    """척추(엉덩이중심→어깨중심)가 수평에 가까울수록 1, 수직이면 0."""
    sh = mid(lms, 11, 12)
    hp = mid(lms, 23, 24)
    v = sh - hp
    n = float(np.hypot(v[0], v[1]))
    if n < 1e-6:
        return 0.0
    return abs(float(v[0])) / n  # |dx|/len: 수평이면 1


def _person_size(lms: np.ndarray) -> float:
    """화면상 사람 크기(주요 관절 bbox 대각선). 클수록 카메라에 가깝고 주피사체일 확률↑."""
    idxs = [0, 11, 12, 23, 24, 25, 26, 27, 28]
    pts = [get_xy(lms, i) for i in idxs if get_v(lms, i) >= 0.30]
    if len(pts) < 3:
        return 0.0
    p = np.stack(pts)
    d = p.max(axis=0) - p.min(axis=0)
    return float(np.hypot(d[0], d[1]))


def _person_center(lms: np.ndarray) -> Optional[np.ndarray]:
    idxs = [11, 12, 23, 24]
    pts = [get_xy(lms, i) for i in idxs if get_v(lms, i) >= 0.30]
    if len(pts) < 2:
        return None
    return np.stack(pts).mean(axis=0)


class PersonSelector:
    """여러 명이 검출될 때 운동 주체(리프터)를 일관되게 선택한다.

    - 벤치: 누운 사람(척추 수평)을 우선. 보조자는 보통 서 있다.
    - 데드/스쿼트: 가장 큰(카메라에 가까운) 사람을 우선.
    - 공통: 직전 프레임에서 고른 사람과 가까운 후보를 선호(깜빡임 방지).
    """

    def __init__(self, exercise: str):
        self.exercise = normalize_exercise_name(exercise)
        self._prev_center: Optional[np.ndarray] = None

    def select(self, candidates: List[np.ndarray]) -> Optional[np.ndarray]:
        if not candidates:
            return None
        if len(candidates) == 1:
            best = candidates[0]
            c = _person_center(best)
            if c is not None:
                self._prev_center = c
            return best

        scored = []
        for lms in candidates:
            score = 0.0
            if self.exercise == "benchpress":
                # 누운 자세 강하게 선호
                score += 3.0 * _torso_horizontalness(lms)
            # 크기(주피사체) 선호
            score += 1.0 * _person_size(lms)
            # 연속성: 직전 선택과 가까우면 가점
            c = _person_center(lms)
            if c is not None and self._prev_center is not None:
                dist_prev = float(np.hypot(*(c - self._prev_center)))
                score += 1.5 * max(0.0, 1.0 - dist_prev / 0.5)
            scored.append((score, lms, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_lms, best_c = scored[0]
        if best_c is not None:
            self._prev_center = best_c
        return best_lms


def extract_landmarks(landmarker, frame_bgr: np.ndarray, timestamp_ms: int) -> Optional[np.ndarray]:
    """하위호환: 단일 사람 반환(첫 번째). 새 코드는 extract_all_landmarks + PersonSelector 사용."""
    allp = extract_all_landmarks(landmarker, frame_bgr, timestamp_ms)
    return allp[0] if allp else None


# ============================================================
# 4. 지표 계산
# ============================================================


def torso_len(lms: np.ndarray) -> float:
    s = mid(lms, 11, 12)
    h = mid(lms, 23, 24)
    return max(dist(s, h), 1e-5)


def signed_trunk_theta(lms: np.ndarray) -> float:
    """hip_center -> shoulder_center 벡터의 화면좌표계 angle rad."""
    sh = mid(lms, 11, 12)
    hp = mid(lms, 23, 24)
    v = sh - hp
    return float(math.atan2(float(v[1]), float(v[0])))


def angle_to_vertical_signed(top: np.ndarray, bottom: np.ndarray) -> float:
    """
    bottom -> top 벡터가 수직축에서 얼마나 기울었는지 signed degree.
    오른쪽으로 기울면 +, 왼쪽으로 기울면 -에 가깝게 사용.
    """
    dx = float(top[0] - bottom[0])
    dy = float(top[1] - bottom[1])
    # 화면에서 위쪽은 dy < 0. 수직 위쪽 벡터 대비 x 편차를 각도로 변환.
    return float(math.degrees(math.atan2(dx, -dy + 1e-9)))


def get_side_points(lms: np.ndarray, side: str) -> Dict[str, np.ndarray]:
    ids = SIDE_IDS[side]
    return {name: get_xy(lms, idx) for name, idx in ids.items() if name in ids}


def hand_grip_point(lms: np.ndarray, side: str) -> Tuple[Optional[np.ndarray], float]:
    """
    손목만 쓰지 않고 wrist/index/thumb를 visibility weighted 평균.
    confidence가 낮으면 None에 가깝게 처리하여 엉뚱한 bar proxy 방지.
    """
    ids = SIDE_IDS[side]
    candidates = [ids["wrist"], ids["index"], ids["thumb"]]
    pts = []
    weights = []
    for idx in candidates:
        v = get_v(lms, idx)
        if v >= OCCLUSION_THR:
            pts.append(get_xy(lms, idx))
            weights.append(v)
    if not pts:
        return None, 0.0
    w = np.array(weights, dtype=np.float32)
    p = np.sum(np.stack(pts, axis=0) * w[:, None], axis=0) / max(float(np.sum(w)), 1e-6)
    conf = float(np.mean(weights))
    return p.astype(np.float32), conf


def bar_proxy(lms: np.ndarray) -> Tuple[Optional[np.ndarray], float]:
    lp, lc = hand_grip_point(lms, "left")
    rp, rc = hand_grip_point(lms, "right")
    pts = []
    ws = []
    if lp is not None and lc >= VIS_THR:
        pts.append(lp); ws.append(lc)
    if rp is not None and rc >= VIS_THR:
        pts.append(rp); ws.append(rc)
    if not pts:
        return None, 0.0
    w = np.array(ws, dtype=np.float32)
    p = np.sum(np.stack(pts, axis=0) * w[:, None], axis=0) / max(float(np.sum(w)), 1e-6)
    return p.astype(np.float32), float(np.mean(ws))


def compute_metrics(lms: Optional[np.ndarray], exercise: str, side: str) -> Dict[str, float]:
    exercise = normalize_exercise_name(exercise)
    if not valid_lms(lms):
        return {}

    ids = SIDE_IDS[side]
    sh = get_xy(lms, ids["shoulder"])
    el = get_xy(lms, ids["elbow"])
    wr = get_xy(lms, ids["wrist"])
    hp = get_xy(lms, ids["hip"])
    kn = get_xy(lms, ids["knee"])
    an = get_xy(lms, ids["ankle"])
    heel = get_xy(lms, ids["heel"])
    foot = get_xy(lms, ids["foot"])

    shoulder_c = mid(lms, 11, 12)
    hip_c = mid(lms, 23, 24)
    nose = get_xy(lms, 0)
    tlen = torso_len(lms)

    # ── occlusion gating ──
    # 각 지표는 의존하는 관절이 모두 신뢰 가능할 때만 값을 넣는다.
    # 가려지면 None으로 두어 HUD에 "측정 불가"로 표시되고, 비정상값으로 오판하지 않는다.
    sid = ids["shoulder"]; eid = ids["elbow"]; wid = ids["wrist"]
    hid = ids["hip"]; kid = ids["knee"]; aid = ids["ankle"]
    heid = ids["heel"]; fid = ids["foot"]
    torso_core = [11, 12, 23, 24]  # torso_len / mid 계산 신뢰성

    out: Dict[str, float] = {}
    struct_occ = STRUCTURAL_OCCLUSION.get(exercise, set())
    advisory = ADVISORY_METRICS.get(exercise, set())

    def put(key: str, value: float, req_ids: Sequence[int]):
        occluded = any(i in struct_occ for i in req_ids)
        if occluded and key not in advisory:
            # 구조적 가림 + 보조 지표도 아님 → 신뢰 불가, 아예 제외.
            return
        if occluded and key in advisory:
            # 보조 지표는 값은 표시하되(choose_issue에서 판정 제외), 그대로 넣는다.
            out[key] = float(value)
            return
        if all_ok(lms, list(req_ids)):
            out[key] = float(value)
        # 아니면 키 자체를 넣지 않음 → user_m.get(key) == None

    knee_angle = angle_abc(hp, kn, an)
    hip_angle = angle_abc(sh, hp, kn)
    elbow_angle = angle_abc(sh, el, wr)
    trunk_lean = abs(angle_to_vertical_signed(shoulder_c, hip_c))
    neck_lean = abs(angle_to_vertical_signed(nose, shoulder_c))
    foot_flatness = abs(float(heel[1] - foot[1])) / tlen
    head_hip_line = abs(float(nose[0] - hip_c[0])) / tlen
    wrist_elbow_x_diff = abs(float(wr[0] - el[0])) / tlen

    v = shoulder_c - hip_c
    n = np.linalg.norm(v)
    bench_line_diff = 0.0 if n < 1e-6 else abs(float(np.cross(v, nose - hip_c))) / (float(n) * tlen)

    put("knee_angle", knee_angle, [hid, kid, aid])
    put("hip_angle", hip_angle, [sid, hid, kid])
    put("elbow_angle", elbow_angle, [sid, eid, wid])
    put("elbow_angle_avg", elbow_angle, [sid, eid, wid])
    put("lockout_angle_min", elbow_angle, [sid, eid, wid])
    put("trunk_lean", trunk_lean, torso_core)
    put("trunk_lean_signed", angle_to_vertical_signed(shoulder_c, hip_c), torso_core)
    put("trunk_theta", signed_trunk_theta(lms), torso_core)
    put("neck_lean", neck_lean, [0, 11, 12])
    put("foot_flatness", foot_flatness, [heid, fid] + torso_core)
    put("head_hip_line", head_hip_line, [0] + torso_core)
    put("wrist_elbow_x_diff", wrist_elbow_x_diff, [eid, wid] + torso_core)
    put("bench_line_diff", bench_line_diff, [0] + torso_core)
    if all_ok(lms, [sid, eid]):
        out["elbow_above_shoulder"] = 1.0 if float(el[1]) < float(sh[1]) else 0.0

    bp, bconf = bar_proxy(lms)
    out["bar_proxy_conf"] = float(bconf)

    return out


def compute_deltas(user_m: Dict[str, float], expert_m: Dict[str, float]) -> Dict[str, float]:
    out = {}
    for k, uv in user_m.items():
        if k in expert_m:
            out[k] = safe_float(uv) - safe_float(expert_m[k])
    return out


def phase_from_metrics(exercise: str, m: Dict[str, float]) -> str:
    exercise = normalize_exercise_name(exercise)
    if not m:
        return "자세 인식 중"
    if exercise == "squat":
        k = m.get("knee_angle", 180.0)
        if k <= 100:
            return "최저점"
        if k >= 150:
            return "상단"
        return "하강/상승 중간"
    if exercise == "deadlift":
        k = m.get("knee_angle", 180.0)
        h = m.get("hip_angle", 180.0)
        if k >= 155 and h >= 155:
            return "락아웃/상단"
        if h <= 120 or k <= 135:
            return "시작/하단"
        return "당기는 중간구간"
    if exercise == "benchpress":
        e = m.get("elbow_angle", 180.0)
        if e <= 100:
            return "가슴터치/최저점"
        if e >= 155:
            return "락아웃/상단"
        return "프레스 중간구간"
    return "구간 인식 중"


# ============================================================
# 5. 피드백 판단 / 안정화 / 카운터
# ============================================================


class FeedbackStabilizer:
    def __init__(self, min_frames: int = 3, hold_frames: int = 9):
        self.min_frames = min_frames
        self.hold_frames = hold_frames
        self.candidate_key: Optional[str] = None
        self.candidate_count = 0
        self.current: Optional[Issue] = None
        self.hold_left = 0

    def update(self, issue: Optional[Issue]) -> Optional[Issue]:
        if issue is None:
            if self.hold_left > 0 and self.current is not None:
                self.hold_left -= 1
                return self.current
            self.current = None
            self.candidate_key = None
            self.candidate_count = 0
            return None

        if self.current is not None and issue.key == self.current.key:
            self.current = issue
            self.hold_left = self.hold_frames
            return self.current

        if self.candidate_key == issue.key:
            self.candidate_count += 1
        else:
            self.candidate_key = issue.key
            self.candidate_count = 1

        if self.candidate_count >= self.min_frames:
            self.current = issue
            self.hold_left = self.hold_frames
            return self.current

        if self.current is not None and self.hold_left > 0:
            self.hold_left -= 1
            return self.current
        return None


class RepCounter:
    def __init__(self, exercise: str, min_hold: int = 3, cooldown: int = 8):
        self.exercise = normalize_exercise_name(exercise)
        self.count = 0
        self.state = "top"
        self.bottom_hold = 0
        self.top_hold = 0
        self.cooldown = 0
        self.min_hold = min_hold
        self.cooldown_frames = cooldown

    def update(self, m: Dict[str, float]) -> bool:
        if not m:
            return False
        if self.cooldown > 0:
            self.cooldown -= 1

        if self.exercise == "squat":
            k = m.get("knee_angle")
            if k is None:
                return False
            bottom = k <= 95
            top = k >= 150
        elif self.exercise == "deadlift":
            k = m.get("knee_angle")
            h = m.get("hip_angle")
            if k is None or h is None:
                return False
            bottom = h <= 120 or k <= 135
            top = h >= 155 and k >= 155
        else:
            e = m.get("elbow_angle")
            if e is None:
                return False
            bottom = e <= 100
            top = e >= 155

        self.bottom_hold = self.bottom_hold + 1 if bottom else 0
        self.top_hold = self.top_hold + 1 if top else 0

        if self.state != "bottom" and self.bottom_hold >= self.min_hold:
            self.state = "bottom"
            return False

        if self.state == "bottom" and self.top_hold >= self.min_hold and self.cooldown == 0:
            self.count += 1
            self.state = "top"
            self.cooldown = self.cooldown_frames
            return True
        return False


def issue_from_metric(exercise: str, key: str, delta: float, severity: float) -> Optional[Issue]:
    exercise = normalize_exercise_name(exercise)
    if exercise == "squat":
        if key == "knee_angle":
            msg = "무릎이 전문가보다 많이 굽혀짐" if delta < 0 else "무릎을 더 깊게 굽혀야 함"
            return Issue(key, msg, severity, [23, 24, 25, 26, 27, 28])
        if key == "hip_angle":
            msg = "엉덩이각/힙힌지 확인"
            return Issue(key, msg, severity, [11, 12, 23, 24, 25, 26])
        if key == "trunk_lean":
            msg = "몸통 기울기 확인"
            return Issue(key, msg, severity, [11, 12, 23, 24])
        if key == "foot_flatness":
            msg = "발바닥 밀착 확인"
            return Issue(key, msg, severity, [27, 28, 29, 30, 31, 32])
        if key == "head_hip_line":
            msg = "머리-엉덩이 라인 확인"
            return Issue(key, msg, severity, [0, 23, 24])
    elif exercise == "deadlift":
        if key == "hip_angle":
            msg = "엉덩이각/힙힌지 확인"
            return Issue(key, msg, severity, [11, 12, 23, 24, 25, 26])
        if key == "knee_angle":
            msg = "무릎각 확인"
            return Issue(key, msg, severity, [23, 24, 25, 26, 27, 28])
        if key == "trunk_lean":
            msg = "몸통 기울기 확인"
            return Issue(key, msg, severity, [11, 12, 23, 24])
        if key == "elbow_angle":
            msg = "팔꿈치 각도 확인"
            return Issue(key, msg, severity, [11, 12, 13, 14, 15, 16])
        if key == "head_hip_line":
            msg = "머리-엉덩이 라인 확인"
            return Issue(key, msg, severity, [0, 23, 24])
    else:
        if key in ["elbow_angle", "lockout_angle_min"]:
            msg = "팔꿈치 각도 확인"
            return Issue(key, msg, severity, [11, 12, 13, 14, 15, 16])
        if key == "wrist_elbow_x_diff":
            msg = "손목-팔꿈치 정렬 확인"
            return Issue(key, msg, severity, [13, 14, 15, 16])
        if key == "bench_line_diff":
            msg = "벤치라인/상체 고정 확인"
            return Issue(key, msg, severity, [0, 11, 12, 23, 24])
    return None


def choose_issue(exercise: str, user_m: Dict[str, float], expert_m: Dict[str, float], deltas: Dict[str, float], phase: str) -> Optional[Issue]:
    exercise = normalize_exercise_name(exercise)
    issues: List[Issue] = []
    thr = DELTA_THRESHOLDS.get(exercise, {})
    advisory = ADVISORY_METRICS.get(exercise, set())

    def um(key, default=None):
        """user metric 안전 조회. None(측정 불가)이면 default."""
        v = user_m.get(key)
        return default if v is None else v

    # 전문가 비교 기반 issue (보조 지표는 제외)
    for key, d in deltas.items():
        if key in advisory:
            continue
        if key not in thr or thr[key] <= 0:
            continue
        if d is None:
            continue
        sev = abs(float(d)) / float(thr[key])
        if sev >= 1.0:
            issue = issue_from_metric(exercise, key, float(d), sev)
            if issue:
                issues.append(issue)

    # 절대 기준 보완 (측정 불가 지표는 건너뜀)
    if exercise == "squat":
        kn = um("knee_angle")
        if phase == "최저점" and kn is not None and kn > ABSOLUTE_RULES["squat"]["bottom_knee_too_open"]:
            issues.append(Issue("knee_depth", "최저점 깊이 확인", 1.3, [23, 24, 25, 26, 27, 28]))
        tl = um("trunk_lean")
        if tl is not None and tl > ABSOLUTE_RULES["squat"]["trunk_lean_max"]:
            issues.append(Issue("trunk_lean_abs", "상체가 과도하게 숙여짐", 1.2, [11, 12, 23, 24]))
    elif exercise == "deadlift":
        if phase == "락아웃/상단":
            kn = um("knee_angle")
            if kn is not None and kn < ABSOLUTE_RULES["deadlift"]["top_knee_lockout_min"]:
                issues.append(Issue("deadlift_knee_lockout", "무릎 락아웃 확인", 1.2, [23, 24, 25, 26, 27, 28]))
            hpa = um("hip_angle")
            if hpa is not None and hpa < ABSOLUTE_RULES["deadlift"]["top_hip_lockout_min"]:
                issues.append(Issue("deadlift_hip_lockout", "엉덩이 락아웃 확인", 1.2, [11, 12, 23, 24, 25, 26]))
        # 데드 팔꿈치는 구조적 가림 대상 → 절대 기준 판정에서 제외(보조 지표).
    else:  # benchpress
        ea = um("elbow_angle")
        if phase == "락아웃/상단" and ea is not None and ea < ABSOLUTE_RULES["benchpress"]["lockout_min"]:
            issues.append(Issue("bench_lockout", "락아웃 각도 확인", 1.25, [11, 12, 13, 14, 15, 16]))
        we = um("wrist_elbow_x_diff")
        if we is not None and we > ABSOLUTE_RULES["benchpress"]["wrist_elbow_x_diff_max"]:
            issues.append(Issue("bench_wrist_elbow", "손목-팔꿈치 정렬 확인", 1.2, [13, 14, 15, 16]))

    if not issues:
        return None
    issues.sort(key=lambda x: x.severity, reverse=True)
    return issues[0]


# ============================================================
# 6. 좌표 변환 / 렌더링 함수
# ============================================================


def make_user_transform(w: int, h: int):
    def tr(p: np.ndarray) -> Tuple[int, int]:
        return int(round(float(p[0]) * w)), int(round(float(p[1]) * h))
    return tr


def _bbox_from_lms(lms: Optional[np.ndarray]) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """visibility가 충분한 점들의 (min, max) bbox. 없으면 None."""
    if not valid_lms(lms):
        return None
    pts = []
    for i in range(33):
        if get_v(lms, i) >= max(0.25, VIS_THR * 0.6):
            pts.append(get_xy(lms, i))
    if len(pts) < 5:
        return None
    pts_np = np.stack(pts, axis=0)
    return pts_np.min(axis=0), pts_np.max(axis=0)


def _body_axis_angle(lms: Optional[np.ndarray]) -> Optional[float]:
    """전신 주축 방향 각도(rad). 화면 위쪽 기준 atan2(dx, -dy).

    부호 모호성이 있는 PCA 대신, 방향이 명확한 '발목중심 → 머리(코)' 벡터를 쓴다.
    이렇게 하면 회전 정렬 시 머리 방향까지 user와 일치한다.
    누운 자세면 ±90도 부근, 서있으면 0도 부근.
    """
    if not valid_lms(lms):
        return None
    # 머리 끝점: nose(0). 발 끝점: 양 발목(27,28) 중심(없으면 무릎).
    if get_v(lms, 0) < 0.30:
        return None
    head = get_xy(lms, 0)
    foot_ids = [27, 28]
    fpts = [get_xy(lms, i) for i in foot_ids if get_v(lms, i) >= 0.30]
    if len(fpts) < 1:
        foot_ids = [25, 26]
        fpts = [get_xy(lms, i) for i in foot_ids if get_v(lms, i) >= 0.30]
    if len(fpts) < 1:
        return None
    foot = np.stack(fpts).mean(axis=0)
    v = head - foot  # 발 -> 머리 방향
    if float(np.hypot(v[0], v[1])) < 1e-5:
        return None
    return float(math.atan2(float(v[0]), -float(v[1])))


def _spine_axis_angle(lms: Optional[np.ndarray]) -> Optional[float]:
    """전신 주축 각도. (이름은 호환 유지, 내부는 PCA 주축 사용)"""
    return _body_axis_angle(lms)


def _rotate_pts(pts: np.ndarray, pivot: np.ndarray, ang_rad: float) -> np.ndarray:
    c, s = math.cos(ang_rad), math.sin(ang_rad)
    R = np.array([[c, -s], [s, c]], dtype=np.float32)
    return (pts - pivot) @ R.T + pivot


def _prescan_user_axis(user_video_path: str, model_path: Path, max_frames: int = 40) -> Optional[float]:
    """user 영상 앞쪽 일부를 빠르게 훑어 전신축(rad) 중앙값을 구한다.
    회전 정렬의 기준 방향으로 쓴다."""
    cap, rot = open_video_normalized(str(user_video_path))
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    sm = LandmarkSmoother(LANDMARK_EMA_ALPHA, VIS_THR)
    selector = PersonSelector("benchpress")  # prescan은 벤치에서만 쓰이므로 누운사람 우선
    angs: List[float] = []
    try:
        with create_landmarker(model_path) as lm:
            i = 0
            while i < max_frames:
                ok, fr = cap.read()
                if not ok:
                    break
                fr = apply_rotation(fr, rot)
                fr = resize_frame_if_needed(fr)
                raw = selector.select(extract_all_landmarks(lm, fr, int(i * 1000 / fps)))
                s = sm.update(raw)
                if valid_lms(s):
                    a = _body_axis_angle(s)
                    if a is not None:
                        angs.append(a)
                i += 1
    finally:
        cap.release()
    if not angs:
        return None
    return float(np.median(angs))


class ExpertPaneNormalizer:
    """
    expert skeleton을 expert pane에 고정 배치한다.

    스쿼트 노트북의 anchor-lock 아이디어를 별도 패널 버전으로 이식한 것.
    - 매 프레임 bbox를 새로 계산하면 expert가 출렁이고 크기가 변한다.
    - 대신 첫 lock_frames개의 유효 프레임에서 동작 전체를 감싸는 bbox를
      누적(union)한 뒤 스케일/중심을 한 번 고정한다.
    - 고정 후에는 관절만 그 안에서 움직이므로 안정적으로 보인다.

    경로 2(방향 정규화):
    - expert와 user의 "기준 척추축 방향"이 다르면(예: user는 누워있는데
      expert는 서있는 영상) 두 골격이 제각각 방향으로 보인다.
    - lock 구간 동안 expert의 기준 척추각 중앙값을 구해, user의 기준 척추각에
      맞추는 회전량(align_rot)을 한 번 고정한다.
    - 이후 expert 좌표를 그 회전량만큼 돌려서 그린다. 동작 중 상대적 변화
      (데드의 숙임→직립 등)는 그대로 보존된다.
    """

    def __init__(self, w: int, h: int, pad: int = 42, lock_frames: int = 25,
                 align_orientation: bool = False):
        self.w = w
        self.h = h
        self.pad = pad
        self.lock_frames = lock_frames
        self.align_orientation = align_orientation
        self._seen = 0
        self._acc_mn: Optional[np.ndarray] = None
        self._acc_mx: Optional[np.ndarray] = None
        self._locked = False
        self._scale = 1.0
        self._center = np.array([0.5, 0.5], dtype=np.float32)
        # 회전 정렬
        self._user_angles: List[float] = []
        self._expert_angles: List[float] = []
        self._align_rot = 0.0          # expert에 적용할 회전량(rad)
        self._pivot = np.array([0.5, 0.5], dtype=np.float32)
        self._rot_finalized = not align_orientation  # 회전 안 쓰면 처음부터 확정 상태

    def observe_user(self, user_lms: Optional[np.ndarray]):
        """user의 기준 전신축을 warmup 동안 수집(회전 정렬용)."""
        if not self.align_orientation or self._rot_finalized:
            return
        a = _body_axis_angle(user_lms)
        if a is not None:
            self._user_angles.append(a)

    def _fit(self, mn: np.ndarray, mx: np.ndarray):
        center = (mn + mx) / 2.0
        size = mx - mn
        sx = (self.w - 2 * self.pad) / max(float(size[0]), 1e-4)
        sy = (self.h - 2 * self.pad) / max(float(size[1]), 1e-4)
        scale = min(sx, sy)
        scale = min(scale, self.h * 1.9)
        self._scale = scale
        self._center = center.astype(np.float32)

    def _rotated(self, lms: np.ndarray) -> np.ndarray:
        """회전 정렬이 확정됐으면 회전 적용한 좌표를, 아니면 원좌표를 반환."""
        if not (self.align_orientation and self._rot_finalized and abs(self._align_rot) > 1e-4):
            return lms[:, :2]
        return _rotate_pts(lms[:, :2].copy(), self._pivot, self._align_rot)

    def update(self, lms: Optional[np.ndarray]):
        """현재 expert lms를 반영하고, 화면좌표 변환 함수를 반환한다.

        2단계 처리:
        - warmup(회전 정렬 ON일 때): lock_frames 동안 expert/user 전신축만 모은다.
          이 구간에는 bbox를 쌓지 않는다(회전이 아직 안 정해져 좌표 기준이 흔들리므로).
        - warmup 끝나는 순간 회전량/피벗을 한 번 확정(_rot_finalized=True)한다.
        - 이후 회전 적용된 좌표로 bbox를 누적하고 _fit으로 스케일/중심을 정한다.
        - 회전 정렬 OFF면 warmup 없이 바로 bbox를 누적한다(기존 동작).
        """
        # 1) warmup: 회전용 각 수집
        if self.align_orientation and not self._rot_finalized:
            ea = _body_axis_angle(lms)
            if ea is not None:
                self._expert_angles.append(ea)
            self._seen += 1
            # warmup 종료 → 회전량/피벗 확정
            if self._seen >= self.lock_frames and self._expert_angles and self._user_angles:
                ua = float(np.median(self._user_angles))
                ea_med = float(np.median(self._expert_angles))
                self._align_rot = ua - ea_med
                if valid_lms(lms):
                    cidx = [0, 11, 12, 23, 24, 25, 26, 27, 28]
                    cpts = [get_xy(lms, i) for i in cidx if get_v(lms, i) >= 0.30]
                    if cpts:
                        self._pivot = np.stack(cpts).mean(axis=0).astype(np.float32)
                self._rot_finalized = True
                self._seen = 0  # bbox 누적 단계 카운터 재사용
            # warmup 중에는 원좌표로 임시 변환 반환(화면엔 대략 위치만)
            return self._make_tr()

        # 2) bbox 누적 단계 (회전 OFF면 처음부터 여기로 들어옴)
        if valid_lms(lms) and not self._locked:
            pts2d = self._rotated(lms)
            # visibility 필터로 bbox 계산
            vis = lms[:, 3]
            mask = vis >= max(0.25, VIS_THR * 0.6)
            if int(mask.sum()) >= 5:
                sel = pts2d[mask]
                mn = sel.min(axis=0); mx = sel.max(axis=0)
                if self._acc_mn is None:
                    self._acc_mn, self._acc_mx = mn.copy(), mx.copy()
                else:
                    self._acc_mn = np.minimum(self._acc_mn, mn)
                    self._acc_mx = np.maximum(self._acc_mx, mx)
                self._seen += 1
                self._fit(self._acc_mn, self._acc_mx)
                if self._seen >= self.lock_frames:
                    self._locked = True

        return self._make_tr()

    def prefit(self, expert_lms_list: List[Optional[np.ndarray]], user_ref_angle: Optional[float]):
        """expert 전체 프레임 + user 기준 전신축으로 회전량/피벗/bbox를 한 번에 확정한다.

        실시간 warmup의 한계(첫 lock_frames 동작 범위만 보는 문제)를 없앤다.
        expert 프로파일(JSON)이 전체 프레임을 갖고 있을 때 사용한다.
        """
        valids = [l for l in expert_lms_list if valid_lms(l)]
        if not valids:
            return

        # 1) 회전량: expert 전신축 중앙값 → user 기준으로
        if self.align_orientation and user_ref_angle is not None:
            ex_angs = [_body_axis_angle(l) for l in valids]
            ex_angs = [a for a in ex_angs if a is not None]
            if ex_angs:
                ea_med = float(np.median(ex_angs))
                self._align_rot = float(user_ref_angle) - ea_med
                # 피벗: 첫 유효 프레임의 전신 중심
                cidx = [0, 11, 12, 23, 24, 25, 26, 27, 28]
                l0 = valids[0]
                cpts = [get_xy(l0, i) for i in cidx if get_v(l0, i) >= 0.30]
                if cpts:
                    self._pivot = np.stack(cpts).mean(axis=0).astype(np.float32)
        self._rot_finalized = True

        # 2) 회전 적용한 좌표로 전체 bbox 계산
        mn = None; mx = None
        for l in valids:
            pts2d = self._rotated(l)
            vis = l[:, 3]
            mask = vis >= max(0.25, VIS_THR * 0.6)
            if int(mask.sum()) < 5:
                continue
            sel = pts2d[mask]
            cmn = sel.min(axis=0); cmx = sel.max(axis=0)
            mn = cmn if mn is None else np.minimum(mn, cmn)
            mx = cmx if mx is None else np.maximum(mx, cmx)
        if mn is not None:
            self._acc_mn, self._acc_mx = mn, mx
            self._fit(mn, mx)
            self._locked = True

    def _make_tr(self):
        scale = self._scale
        center = self._center
        align_rot = self._align_rot
        pivot_fixed = self._pivot
        dst_center = np.array([self.w / 2.0, self.h / 2.0], dtype=np.float32)
        do_rot = self.align_orientation and self._rot_finalized and abs(align_rot) > 1e-4

        if self._acc_mn is None:
            def tr_raw(p: np.ndarray) -> Tuple[int, int]:
                pp = p
                if do_rot:
                    pp = _rotate_pts(np.asarray(p, dtype=np.float32).reshape(1, 2), pivot_fixed, align_rot)[0]
                return int(float(pp[0]) * self.w), int(float(pp[1]) * self.h)
            return tr_raw

        def tr(p: np.ndarray) -> Tuple[int, int]:
            pp = p
            if do_rot:
                pp = _rotate_pts(np.asarray(p, dtype=np.float32).reshape(1, 2), pivot_fixed, align_rot)[0]
            q = (pp - center) * scale + dst_center
            return int(round(float(q[0]))), int(round(float(q[1])))

        return tr


def draw_skeleton(
    img: np.ndarray,
    lms: Optional[np.ndarray],
    transform,
    bad_indices: Optional[Sequence[int]] = None,
    line_color: Tuple[int, int, int] = C_LINE,
    point_color: Tuple[int, int, int] = (160, 235, 170),
    bad_color: Tuple[int, int, int] = C_BAD,
    thickness: int = 3,
    occ_thr: float = OCCLUSION_THR,
):
    if not valid_lms(lms):
        return img
    bad = set(bad_indices or [])
    for a, b in POSE_CONNECTIONS:
        va, vb = get_v(lms, a), get_v(lms, b)
        # 둘 중 하나라도 occlusion 임계값 미만이면 신뢰 불가 → 골격선 안 그림(귀신 방지)
        if va < occ_thr or vb < occ_thr:
            continue
        pa = transform(get_xy(lms, a))
        pb = transform(get_xy(lms, b))
        color = bad_color if (a in bad or b in bad) else line_color
        cv2.line(img, pa, pb, color, thickness, cv2.LINE_AA)

    for i in range(33):
        v = get_v(lms, i)
        if v < 0.30:
            continue
        p = transform(get_xy(lms, i))
        if v < occ_thr:
            # 가려진 관절: 작은 회색 빈 원으로만 표시(불확실 신호)
            cv2.circle(img, p, 3, C_DARKGRAY, 1, cv2.LINE_AA)
            continue
        if i in bad:
            cv2.circle(img, p, 10, bad_color, 3, cv2.LINE_AA)
            cv2.circle(img, p, 3, bad_color, -1, cv2.LINE_AA)
        else:
            cv2.circle(img, p, 4, point_color, -1, cv2.LINE_AA)
    return img


def shortest_arc_points(center: Tuple[int, int], p1: Tuple[int, int], p2: Tuple[int, int], radius: float, n: int = 48) -> np.ndarray:
    cx, cy = center
    a1 = math.atan2(p1[1] - cy, p1[0] - cx)
    a2 = math.atan2(p2[1] - cy, p2[0] - cx)
    da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
    angles = np.linspace(a1, a1 + da, n)
    pts = np.stack([cx + radius * np.cos(angles), cy + radius * np.sin(angles)], axis=1)
    return pts.astype(np.int32)


def draw_angle_arc(
    img: np.ndarray,
    lms: Optional[np.ndarray],
    ids: Tuple[int, int, int],
    transform,
    label: Optional[str] = None,
    color: Tuple[int, int, int] = C_YELLOW,
    warn: bool = False,
    radius_scale: float = 0.36,
    min_radius: int = 28,
    max_radius: int = 82,
    thickness: int = 5,
):
    """A-B-C 각도를 B 중심 true arc로 표시."""
    if not valid_lms(lms):
        return img
    a, b, c = ids
    if min(get_v(lms, a), get_v(lms, b), get_v(lms, c)) < 0.25:
        return img

    pa = transform(get_xy(lms, a))
    pb = transform(get_xy(lms, b))
    pc = transform(get_xy(lms, c))
    angle = angle_abc(get_xy(lms, a), get_xy(lms, b), get_xy(lms, c))
    la = math.dist(pb, pa)
    lc = math.dist(pb, pc)
    radius = int(clamp(min(la, lc) * radius_scale, min_radius, max_radius))
    use_color = C_BAD if warn else color

    arc = shortest_arc_points(pb, pa, pc, radius, n=60)
    cv2.polylines(img, [arc], False, use_color, thickness, cv2.LINE_AA)

    # arc 양 끝 작은 원
    if len(arc) > 2:
        cv2.circle(img, tuple(arc[0]), 4, use_color, -1, cv2.LINE_AA)
        cv2.circle(img, tuple(arc[-1]), 4, use_color, -1, cv2.LINE_AA)

    # 중심 관절 강조
    cv2.circle(img, pb, 12, use_color, 3, cv2.LINE_AA)

    # 텍스트 위치: arc 중간점에서 바깥쪽
    mid_idx = len(arc) // 2
    tx, ty = arc[mid_idx]
    vx = tx - pb[0]
    vy = ty - pb[1]
    norm = math.sqrt(vx * vx + vy * vy) + 1e-6
    tx = int(tx + 18 * vx / norm)
    ty = int(ty + 18 * vy / norm)
    txt = label if label is not None else f"{int(round(angle))}deg"
    img = draw_text(img, txt, (tx, ty - 12), size=22, color=use_color, bold=True)
    return img


def draw_dashed_line(img, p1, p2, color, thickness=2, dash=12, gap=8):
    x1, y1 = p1
    x2, y2 = p2
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 1:
        return img
    dx = (x2 - x1) / length
    dy = (y2 - y1) / length
    t = 0
    while t < length:
        s = t
        e = min(t + dash, length)
        ps = (int(x1 + dx * s), int(y1 + dy * s))
        pe = (int(x1 + dx * e), int(y1 + dy * e))
        cv2.line(img, ps, pe, color, thickness, cv2.LINE_AA)
        t += dash + gap
    return img


def draw_trunk_corridor(
    img: np.ndarray,
    user_lms: Optional[np.ndarray],
    expert_lms: Optional[np.ndarray],
    user_m: Dict[str, float],
    issue: Optional[Issue],
    transform,
    tol_deg: float = 10.0,
):
    if not valid_lms(user_lms):
        return img
    hp = mid(user_lms, 23, 24)
    sh = mid(user_lms, 11, 12)
    hp_px = transform(hp)
    sh_px = transform(sh)
    tlen_px = max(math.dist(hp_px, sh_px), 40.0)

    # expert trunk 방향을 user hip 위치에 얹어서 corridor 표시
    if valid_lms(expert_lms):
        theta = signed_trunk_theta(expert_lms)
    else:
        theta = signed_trunk_theta(user_lms)
    tol = math.radians(tol_deg)
    length = tlen_px * 1.25

    def endpoint(th):
        return (int(hp_px[0] + math.cos(th) * length), int(hp_px[1] + math.sin(th) * length))

    p_mid = endpoint(theta)
    p_lo = endpoint(theta - tol)
    p_hi = endpoint(theta + tol)

    overlay = img.copy()
    poly = np.array([hp_px, p_lo, p_hi], dtype=np.int32)
    cv2.fillConvexPoly(overlay, poly, (40, 120, 60))
    img = cv2.addWeighted(overlay, 0.18, img, 0.82, 0)
    draw_dashed_line(img, hp_px, p_mid, C_OK, thickness=2, dash=10, gap=8)
    cv2.line(img, hp_px, sh_px, C_BAD if issue and "trunk" in issue.key else C_LINE, 5, cv2.LINE_AA)
    return img


def draw_bar_proxy_layer(
    img: np.ndarray,
    lms: Optional[np.ndarray],
    exercise: str,
    transform,
):
    if not valid_lms(lms):
        return img
    exercise = normalize_exercise_name(exercise)
    bp, conf = bar_proxy(lms)
    if bp is None or conf < 0.55:
        return img
    p = transform(bp)
    h, w = img.shape[:2]
    if exercise == "deadlift":
        # 손 위치 기반 proxy임을 명확히: vertical dashed + 짧은 grip line
        draw_dashed_line(img, (p[0], max(0, p[1] - 120)), (p[0], min(h - 1, p[1] + 160)), C_YELLOW, 2, 12, 8)
        cv2.line(img, (p[0] - 55, p[1]), (p[0] + 55, p[1]), C_YELLOW, 3, cv2.LINE_AA)
        cv2.circle(img, p, 7, C_YELLOW, -1, cv2.LINE_AA)
        img = draw_text(img, "bar proxy", (p[0] + 8, p[1] - 30), 17, C_YELLOW)
    elif exercise == "benchpress":
        # 양손이 모두 보이면 wrist/grip 연결선을 표시. 아니면 grip center만 표시.
        lp, lc = hand_grip_point(lms, "left")
        rp, rc = hand_grip_point(lms, "right")
        if lp is not None and rp is not None and lc >= 0.55 and rc >= 0.55:
            pl = transform(lp)
            pr = transform(rp)
            cv2.line(img, pl, pr, C_YELLOW, 4, cv2.LINE_AA)
            cv2.circle(img, pl, 7, C_YELLOW, -1, cv2.LINE_AA)
            cv2.circle(img, pr, 7, C_YELLOW, -1, cv2.LINE_AA)
        else:
            cv2.circle(img, p, 7, C_YELLOW, -1, cv2.LINE_AA)
    return img


def draw_wrist_elbow_guide(img: np.ndarray, lms: Optional[np.ndarray], side: str, transform, warn: bool):
    if not valid_lms(lms):
        return img
    ids = SIDE_IDS[side]
    el = transform(get_xy(lms, ids["elbow"]))
    wr = transform(get_xy(lms, ids["wrist"]))
    color = C_BAD if warn else C_CYAN
    # 손목-팔꿈치 수직 정렬 guide
    draw_dashed_line(img, (el[0], min(el[1], wr[1]) - 35), (el[0], max(el[1], wr[1]) + 35), color, 2, 8, 6)
    cv2.line(img, el, wr, color, 3, cv2.LINE_AA)
    return img


def draw_exercise_layers(
    img: np.ndarray,
    lms: Optional[np.ndarray],
    expert_lms: Optional[np.ndarray],
    exercise: str,
    side: str,
    user_m: Dict[str, float],
    issue: Optional[Issue],
    transform,
    is_expert: bool = False,
):
    if not valid_lms(lms):
        return img
    exercise = normalize_exercise_name(exercise)
    ids = SIDE_IDS[side]
    issue_key = issue.key if issue else ""

    # 공통: 운동별 true arc
    if exercise == "squat":
        warn_knee = issue is not None and ("knee" in issue_key or issue.key == "knee_angle")
        warn_hip = issue is not None and ("hip" in issue_key or issue.key == "hip_angle")
        img = draw_angle_arc(img, lms, (ids["hip"], ids["knee"], ids["ankle"]), transform, color=C_YELLOW, warn=warn_knee)
        # hip arc는 핵심 오류일 때만 크게 표시해서 화면 복잡도 줄임
        if warn_hip:
            img = draw_angle_arc(img, lms, (ids["shoulder"], ids["hip"], ids["knee"]), transform, color=C_CYAN, warn=True, radius_scale=0.30)
        if not is_expert:
            img = draw_trunk_corridor(img, lms, expert_lms, user_m, issue, transform, tol_deg=10.0)

    elif exercise == "deadlift":
        warn_hip = issue is not None and ("hip" in issue_key or issue.key == "hip_angle")
        warn_knee = issue is not None and ("knee" in issue_key or issue.key == "knee_angle")
        img = draw_angle_arc(img, lms, (ids["shoulder"], ids["hip"], ids["knee"]), transform, color=C_BAD if warn_hip else C_CYAN, warn=warn_hip)
        img = draw_angle_arc(img, lms, (ids["hip"], ids["knee"], ids["ankle"]), transform, color=C_YELLOW, warn=warn_knee, radius_scale=0.30)
        # 데드 팔꿈치/손목은 바벨에 가려져 신뢰 불가 → arc/bar proxy 표시 안 함.
        if not is_expert:
            img = draw_trunk_corridor(img, lms, expert_lms, user_m, issue, transform, tol_deg=10.0)
            if DRAW_BAR_PROXY.get(exercise, False):
                img = draw_bar_proxy_layer(img, lms, exercise, transform)

    elif exercise == "benchpress":
        warn_elbow = issue is not None and ("elbow" in issue_key or "lockout" in issue_key)
        warn_we = issue is not None and "wrist" in issue_key
        img = draw_angle_arc(img, lms, (ids["shoulder"], ids["elbow"], ids["wrist"]), transform, color=C_CYAN, warn=warn_elbow, radius_scale=0.40)
        if not is_expert:
            img = draw_wrist_elbow_guide(img, lms, side, transform, warn=warn_we)
            if DRAW_BAR_PROXY.get(exercise, False):
                img = draw_bar_proxy_layer(img, lms, exercise, transform)
            # bench line: 머리-어깨-엉덩이 라인
            p0 = transform(get_xy(lms, 0))
            ps = transform(mid(lms, 11, 12))
            ph = transform(mid(lms, 23, 24))
            line_color = C_BAD if issue and "bench" in issue.key else C_LINE
            cv2.line(img, p0, ps, line_color, 2, cv2.LINE_AA)
            cv2.line(img, ps, ph, line_color, 2, cv2.LINE_AA)
    return img


def draw_feedback_banner(img: np.ndarray, exercise: str, phase: str, issue: Optional[Issue]):
    h, w = img.shape[:2]
    main = issue.message if issue else "정상 범위"
    color = C_BAD if issue else C_OK
    bg = (38, 38, 48) if issue else (30, 48, 36)
    img = draw_round_rect(img, (10, 54), (min(w - 10, 520), 104), bg, alpha=0.78)
    img = draw_text(img, f"{phase}  |  {main}", (20, 66), 24, color, bold=True)
    return img


def draw_metric_row(
    img: np.ndarray,
    x: int,
    y: int,
    w: int,
    label: str,
    u: Optional[float],
    e: Optional[float],
    d: Optional[float],
    warn: bool,
    advisory: bool = False,
):
    measurable = u is not None
    if advisory:
        color = C_CYAN  # 보조 지표는 파란 톤으로 구분
    else:
        color = C_GRAY if not measurable else (C_BAD if warn else C_OK)
    img = draw_text(img, label, (x, y), 18, C_WHITE, bold=True)
    if not measurable:
        status = "측정 불가"
    elif advisory:
        status = "참고"
    else:
        status = "주의" if warn else "OK"
    img = draw_text(img, status, (x + w - 78, y), 17, color, bold=True)

    def fmt(v):
        if v is None:
            return "-"
        if abs(v) >= 10:
            return f"{v:.1f}"
        return f"{v:.2f}"

    txt = f"U {fmt(u)} / E {fmt(e)} / Δ {fmt(d)}"
    img = draw_text(img, txt, (x, y + 22), 14, C_GRAY)
    bar_x = x
    bar_y = y + 44
    bar_w = w - 22
    cv2.line(img, (bar_x, bar_y), (bar_x + bar_w, bar_y), C_DARKGRAY, 5, cv2.LINE_AA)
    if measurable and d is not None:
        # delta bar는 절대값 클수록 길게. 최대 1로 clamp.
        ratio = clamp(abs(d) / (abs(d) + 1.0), 0.08, 1.0)
        bar_color = C_CYAN if advisory else color
        cv2.line(img, (bar_x, bar_y), (bar_x + int(bar_w * ratio), bar_y), bar_color, 5, cv2.LINE_AA)
    return img


def draw_hud(
    img: np.ndarray,
    exercise: str,
    phase: str,
    rep_count: int,
    user_m: Dict[str, float],
    expert_m: Dict[str, float],
    deltas: Dict[str, float],
    issue: Optional[Issue],
    fps_now: float,
    frame_info: str,
):
    h, w = img.shape[:2]
    exercise = normalize_exercise_name(exercise)
    cv2.rectangle(img, (0, 0), (w, h), C_BG, -1)

    title = {"squat": "SQUAT", "deadlift": "DEADLIFT", "benchpress": "BENCH PRESS"}[exercise]
    img = draw_text(img, title, (18, 18), 29, C_YELLOW, bold=True)
    img = draw_text(img, f"횟수  {rep_count}", (w - 112, 24), 18, C_GRAY)
    img = draw_text(img, str(rep_count), (w - 42, 18), 30, C_CYAN, bold=True)

    img = draw_round_rect(img, (18, 66), (w - 18, 106), C_PANEL, alpha=0.95)
    img = draw_text(img, phase, (30, 76), 18, C_WHITE)

    fb_text = issue.message if issue else "정상 범위"
    fb_color = C_BAD if issue else C_OK
    img = draw_round_rect(img, (18, 126), (w - 18, 202), C_PANEL, alpha=0.95)
    cv2.rectangle(img, (18, 126), (w - 18, 202), fb_color, 2)
    img = draw_text(img, "현재 핵심 피드백", (30, 136), 15, C_GRAY)
    img = draw_text(img, fb_text, (30, 164), 20, fb_color, bold=True)

    img = draw_text(img, f"{frame_info}   FPS {fps_now:.1f}", (18, 222), 14, C_GRAY)
    cv2.line(img, (18, 248), (w - 18, 248), C_DARKGRAY, 1, cv2.LINE_AA)

    y = 264
    metrics = DISPLAY_METRICS.get(exercise, [])
    thr = DELTA_THRESHOLDS.get(exercise, {})
    advisory_set = ADVISORY_METRICS.get(exercise, set())
    for key in metrics:
        if y > h - 90:
            break
        label = METRIC_LABELS_KO.get(key, key)
        u = user_m.get(key)
        e = expert_m.get(key)
        d = deltas.get(key)
        is_adv = key in advisory_set
        warn = False
        if not is_adv:
            if key in thr and thr[key] > 0 and d is not None:
                warn = abs(d) >= thr[key]
            if issue and (issue.key == key or key in issue.key):
                warn = True
        img = draw_metric_row(img, 28, y, w - 46, label, u, e, d, warn, advisory=is_adv)
        y += 66

    cv2.line(img, (18, h - 55), (w - 18, h - 55), C_DARKGRAY, 1, cv2.LINE_AA)
    img = draw_text(img, "빨간 원 = 현재 우선 확인 관절", (20, h - 42), 14, C_GRAY)
    img = draw_text(img, "arc = 관절 중심 실제 각도", (20, h - 22), 14, C_GRAY)
    return img


# ============================================================
# 7. Expert profile 로드/생성
# ============================================================


def save_expert_profile(path: Path, frames: List[dict], fps: float, source_video: str):
    data = {
        "version": "unified_feedback_v2",
        "fps": fps,
        "source_video": source_video,
        "frames": frames,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def load_expert_profile(path: Path) -> Optional[Tuple[List[dict], float]]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "frames" in data:
            frames = data["frames"]
            fps = safe_float(data.get("fps", 30.0), 30.0)
            return frames, fps
        if isinstance(data, list):
            return data, 30.0
    except Exception as e:
        print(f"[경고] expert JSON 로드 실패: {path} | {e}")
    return None


def frame_landmarks_to_list(lms: Optional[np.ndarray]) -> Optional[List[List[float]]]:
    if not valid_lms(lms):
        return None
    return [[float(x) for x in row] for row in lms.tolist()]


def list_to_lms(x) -> Optional[np.ndarray]:
    if x is None:
        return None
    arr = np.asarray(x, dtype=np.float32)
    if arr.ndim == 2 and arr.shape[0] >= 33 and arr.shape[1] >= 4:
        return arr[:33, :4].copy()
    return None


def build_expert_profile(exercise: str, config: dict) -> Tuple[List[dict], float]:
    exercise = normalize_exercise_name(exercise)
    json_path = BASE_DIR / config["expert_json"]

    loaded = load_expert_profile(json_path)
    if loaded is not None:
        frames, fps = loaded
        print(f"[EXPERT] 캐시 로드: {json_path} ({len(frames)} frames)")
        return frames, fps

    video_path = BASE_DIR / config["expert_video"]
    if not video_path.exists():
        raise FileNotFoundError(
            f"전문가 영상/JSON이 없습니다. expert_video 또는 expert_json을 확인하세요.\n"
            f"  video: {video_path}\n  json : {json_path}"
        )

    cap, exp_rot = open_video_normalized(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"전문가 영상 열기 실패: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    smoother = LandmarkSmoother(EXPERT_EMA_ALPHA, VIS_THR)
    side_lock = SideLock(exercise)
    expert_selector = PersonSelector(exercise)
    frames: List[dict] = []

    print(f"[EXPERT] 전처리 시작: {video_path} | fps={fps:.2f}, frames={total}")
    with create_landmarker(MODEL_PATH) as landmarker:
        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = apply_rotation(frame, exp_rot)
            timestamp_ms = int(idx * 1000 / fps)
            raw = expert_selector.select(extract_all_landmarks(landmarker, frame, timestamp_ms))
            lms = smoother.update(raw)
            side = side_lock.update(lms)
            metrics = compute_metrics(lms, exercise, side) if valid_lms(lms) else {}
            frames.append({
                "frame_idx": idx,
                "timestamp_ms": timestamp_ms,
                "side": side,
                "landmarks": frame_landmarks_to_list(lms),
                "metrics": metrics,
            })
            idx += 1
            if idx % 50 == 0:
                print(f"  expert preprocess {idx}/{total if total else '?'}")
    cap.release()

    if not frames:
        raise RuntimeError(f"전문가 전처리 결과가 비어 있습니다: {video_path}")

    save_expert_profile(json_path, frames, fps, str(video_path))
    print(f"[EXPERT] 캐시 저장: {json_path} ({len(frames)} frames)")
    return frames, fps


def get_expert_frame(expert_frames: List[dict], frame_idx: int, user_total: int, timestamp_ms: int, expert_fps: float) -> dict:
    if not expert_frames:
        return {}
    if MATCH_MODE == "time":
        ex_idx = int(round((timestamp_ms / 1000.0) * expert_fps))
    else:
        denom = max(user_total - 1, 1)
        ratio = clamp(frame_idx / denom, 0.0, 1.0)
        ex_idx = int(round(ratio * (len(expert_frames) - 1)))
    ex_idx = max(0, min(ex_idx, len(expert_frames) - 1))
    return expert_frames[ex_idx]


# ============================================================
# 8. 메인 처리
# ============================================================


def get_video_rotation(video_path: str) -> int:
    """영상의 회전 메타데이터(0/90/180/270)를 읽는다.

    핸드폰 등에서 세로로 찍은 영상을 '재생 시 회전' 메타데이터로만 가로처럼
    보이게 저장하는 경우가 있다. OpenCV는 환경(빌드)에 따라 이 메타데이터를
    적용하기도/무시하기도 해서, 같은 파일이 PC마다 가로/세로로 다르게 읽힌다.
    이를 코드에서 직접 보정해 어디서나 동일한 방향이 되도록 한다.

    ffprobe가 있으면 그것으로, 없으면 0을 반환(보정 안 함)."""
    try:
        import subprocess, json
        out = subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", str(video_path)],
            stderr=subprocess.DEVNULL,
        ).decode()
        d = json.loads(out)
        for s in d.get("streams", []):
            if s.get("codec_type") != "video":
                continue
            tag = s.get("tags", {}).get("rotate")
            if tag is not None:
                return int(tag) % 360
            for sd in s.get("side_data_list", []):
                if "rotation" in sd:
                    # ffmpeg side_data rotation은 부호가 반대 관례일 수 있음
                    return (-int(sd["rotation"])) % 360
    except Exception:
        pass
    return 0


def apply_rotation(frame: np.ndarray, rotation: int) -> np.ndarray:
    """회전 메타데이터(시계방향 deg)를 프레임 픽셀에 적용해 의도된 방향으로 만든다."""
    if rotation == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if rotation == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


def open_video_normalized(video_path: str):
    """VideoCapture와 함께, 프레임을 의도된 방향으로 보정하기 위한 회전값을 반환.

    핵심: OpenCV가 이미 메타데이터를 적용해 가로로 읽고 있는지(=프레임이 이미
    가로인지) 확인해서, 이중 회전을 피한다.
    반환: (cap, need_rotation)  need_rotation은 픽셀에 추가로 적용할 회전(deg)."""
    cap = cv2.VideoCapture(str(video_path))
    meta_rot = get_video_rotation(video_path)
    if meta_rot in (90, 270):
        # 메타데이터상 세로→가로 회전이 필요한 영상.
        # OpenCV가 읽은 첫 프레임이 이미 가로면(=메타 적용됨) 추가 회전 불필요.
        ok, fr = cap.read()
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        if ok:
            h, w = fr.shape[:2]
            if w >= h:
                return cap, 0          # 이미 가로로 읽힘 → 보정 불필요
            return cap, meta_rot       # 세로로 읽힘 → 메타 회전 적용 필요
    return cap, 0


def resize_frame_if_needed(frame: np.ndarray) -> np.ndarray:
    if MAX_OUTPUT_H is None:
        return frame
    h, w = frame.shape[:2]
    if h <= MAX_OUTPUT_H:
        return frame
    scale = MAX_OUTPUT_H / float(h)
    return cv2.resize(frame, (int(w * scale), MAX_OUTPUT_H), interpolation=cv2.INTER_AREA)


def process_exercise(exercise: str):
    exercise = normalize_exercise_name(exercise)
    config = VIDEO_CONFIG[exercise]
    user_video = BASE_DIR / config["user_video"]
    if not user_video.exists():
        raise FileNotFoundError(f"사용자 영상이 없습니다: {user_video}")

    expert_frames, expert_fps = build_expert_profile(exercise, config)

    cap, user_rot = open_video_normalized(str(user_video))
    if not cap.isOpened():
        raise RuntimeError(f"사용자 영상 열기 실패: {user_video}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    user_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    ret, first_frame = cap.read()
    if not ret:
        cap.release()
        raise RuntimeError(f"첫 프레임 읽기 실패: {user_video}")
    first_frame = apply_rotation(first_frame, user_rot)
    first_frame = resize_frame_if_needed(first_frame)
    user_h, user_w = first_frame.shape[:2]
    # HUD가 모든 지표 행을 표시하려면 충분한 높이가 필요하다.
    # user 영상이 짧으면(예: 가로 벤치 378px) HUD가 잘리므로 패널 높이에 하한을 둔다.
    out_h = max(user_h, MIN_PANEL_H)
    out_w = user_w + EXPERT_W + HUD_W

    output_path = OUTPUT_DIR / config["output"]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, src_fps, (out_w, out_h))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"VideoWriter 열기 실패: {output_path}")

    # 첫 프레임 다시 처리하기 위해 위치 0으로 복귀
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    smoother = LandmarkSmoother(LANDMARK_EMA_ALPHA, VIS_THR)
    side_lock = SideLock(exercise)
    feedback_stabilizer = FeedbackStabilizer(min_frames=3, hold_frames=9)
    rep_counter = RepCounter(exercise)
    expert_norm = ExpertPaneNormalizer(
        EXPERT_W, out_h, pad=42, lock_frames=25,
        align_orientation=ALIGN_EXPERT_ORIENTATION.get(exercise, False),
    )

    # 회전 정렬 종목(벤치)은 expert 전체 프레임 + user 기준 전신축으로 한 번에 prefit한다.
    # 실시간 warmup이 첫 구간 동작 범위만 보는 한계를 없애, expert가 패널을 벗어나지 않게 한다.
    if ALIGN_EXPERT_ORIENTATION.get(exercise, False):
        # 1) user 기준 전신축: 앞쪽 일부 프레임을 빠르게 스캔해 중앙값을 구한다.
        user_ref_angle = _prescan_user_axis(str(user_video), MODEL_PATH, max_frames=40)
        # 2) expert 전체 landmark 리스트
        expert_lms_all = [list_to_lms(f.get("landmarks")) for f in expert_frames]
        expert_norm.prefit(expert_lms_all, user_ref_angle)
        print(f"[ALIGN] {exercise}: user축={None if user_ref_angle is None else round(math.degrees(user_ref_angle),1)}도, "
              f"회전={round(math.degrees(expert_norm._align_rot),1)}도")

    frame_idx = 0
    t0 = time.perf_counter()
    last_time = t0
    fps_now = 0.0
    user_selector = PersonSelector(exercise)

    print(f"[RUN] {exercise} 시작")
    print(f"  user   : {user_video}")
    print(f"  output : {output_path}")
    print(f"  fps={src_fps:.2f}, frames={user_total}, size={user_w}x{user_h}")

    with create_landmarker(MODEL_PATH) as landmarker:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = apply_rotation(frame, user_rot)
            frame = resize_frame_if_needed(frame)
            timestamp_ms = int(frame_idx * 1000 / src_fps)

            raw_lms = user_selector.select(extract_all_landmarks(landmarker, frame, timestamp_ms))
            user_lms = smoother.update(raw_lms)
            user_side = side_lock.update(user_lms)
            user_m = compute_metrics(user_lms, exercise, user_side) if valid_lms(user_lms) else {}

            ex_pack = get_expert_frame(expert_frames, frame_idx, user_total, timestamp_ms, expert_fps)
            expert_lms = list_to_lms(ex_pack.get("landmarks")) if ex_pack else None
            expert_side = ex_pack.get("side", user_side) if ex_pack else user_side
            expert_m = ex_pack.get("metrics", {}) if ex_pack else {}
            if valid_lms(expert_lms) and not expert_m:
                expert_m = compute_metrics(expert_lms, exercise, expert_side)

            deltas = compute_deltas(user_m, expert_m) if user_m and expert_m else {}
            phase = phase_from_metrics(exercise, user_m)
            rep_counter.update(user_m)

            raw_issue = choose_issue(exercise, user_m, expert_m, deltas, phase) if user_m else None
            issue = feedback_stabilizer.update(raw_issue)
            bad = issue.landmarks if issue else []

            # USER panel
            user_canvas = frame.copy()
            user_tr = make_user_transform(user_w, user_h)
            user_canvas = draw_text(user_canvas, "USER", (8, 8), 25, C_YELLOW, bold=True)
            user_canvas = draw_skeleton(user_canvas, user_lms, user_tr, bad_indices=bad, line_color=C_LINE, thickness=3)
            user_canvas = draw_exercise_layers(user_canvas, user_lms, expert_lms, exercise, user_side, user_m, issue, user_tr, is_expert=False)
            user_canvas = draw_feedback_banner(user_canvas, exercise, phase, issue)

            # out_h가 user_h보다 크면(짧은 영상) 위아래 레터박스로 패널 높이를 맞춘다.
            if user_canvas.shape[0] != out_h:
                pad_total = out_h - user_canvas.shape[0]
                pad_top = max(0, pad_total // 2)
                pad_bot = max(0, pad_total - pad_top)
                user_canvas = cv2.copyMakeBorder(
                    user_canvas, pad_top, pad_bot, 0, 0,
                    cv2.BORDER_CONSTANT, value=C_BG,
                )

            # EXPERT panel
            expert_canvas = np.zeros((out_h, EXPERT_W, 3), dtype=np.uint8)
            expert_canvas[:] = C_BG
            expert_canvas = draw_text(expert_canvas, "EXPERT", (14, 8), 25, C_OK, bold=True)
            expert_norm.observe_user(user_lms)
            ex_tr = expert_norm.update(expert_lms)
            expert_canvas = draw_skeleton(expert_canvas, expert_lms, ex_tr, bad_indices=bad, line_color=C_LINE, thickness=3)
            expert_canvas = draw_exercise_layers(expert_canvas, expert_lms, None, exercise, expert_side, expert_m, issue, ex_tr, is_expert=True)

            # HUD panel
            now = time.perf_counter()
            dt = now - last_time
            if dt > 1e-6:
                fps_now = 0.9 * fps_now + 0.1 * (1.0 / dt) if fps_now > 0 else (1.0 / dt)
            last_time = now
            frame_info = f"프레임 {frame_idx + 1}/{user_total if user_total else '?'}"
            hud = np.zeros((out_h, HUD_W, 3), dtype=np.uint8)
            hud = draw_hud(hud, exercise, phase, rep_counter.count, user_m, expert_m, deltas, issue, fps_now, frame_info)

            # vertical separators
            sep1 = np.full((out_h, 2, 3), (72, 60, 66), dtype=np.uint8)
            sep2 = np.full((out_h, 2, 3), (72, 60, 66), dtype=np.uint8)
            combined = np.hstack([user_canvas, sep1, expert_canvas[:, :EXPERT_W - 2], sep2, hud[:, :HUD_W - 2]])
            if combined.shape[1] != out_w:
                combined = cv2.resize(combined, (out_w, out_h), interpolation=cv2.INTER_AREA)
            writer.write(combined)

            frame_idx += 1
            if frame_idx % 50 == 0:
                elapsed = time.perf_counter() - t0
                print(f"  {exercise}: {frame_idx}/{user_total if user_total else '?'} frames | elapsed {elapsed:.1f}s")

    cap.release()
    writer.release()
    elapsed = time.perf_counter() - t0
    size_mb = output_path.stat().st_size / 1024 / 1024 if output_path.exists() else 0
    print(f"[DONE] {exercise}: {output_path} | {size_mb:.1f} MB | {elapsed:.1f}s")


# ============================================================
# 9. CLI
# ============================================================


def main():
    parser = argparse.ArgumentParser(description="3대운동 통합 자세 피드백 v2")
    parser.add_argument("--exercise", default="squat", help="squat / deadlift / benchpress / bench")
    parser.add_argument("--all", action="store_true", help="squat, deadlift, benchpress 모두 처리")
    args = parser.parse_args()

    if args.all:
        targets = ["squat", "deadlift", "benchpress"]
    else:
        targets = [normalize_exercise_name(args.exercise)]

    for ex in targets:
        try:
            process_exercise(ex)
        except Exception as e:
            print(f"[ERROR] {ex}: {e}")
            raise


if __name__ == "__main__":
    main()
