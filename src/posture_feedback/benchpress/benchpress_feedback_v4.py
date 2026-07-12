"""
benchpress_feedback_v4_ARC_LAYER_CLEAN.py
=========================================================
벤치프레스 전용 시각적 피드백 코드 (VS Code / 로컬 실행용)

준비 파일(이 파일과 같은 폴더):
  - user_benchpress.mp4
  - expert_benchpress.json
  - pose_landmarker_lite.task

실행:
  python benchpress_feedback_v4_ARC_LAYER_CLEAN.py

출력:
  output/benchpress_v4_feedback1.mp4

v1 설계 방향:
  - EXPERT skeleton 패널을 표시함.
  - expert_benchpress.json은 수치 비교 기준 + EXPERT skeleton 표시 기준으로 사용.
  - USER 화면 + EXPERT skeleton + 오른쪽 HUD 구조.
  - v2 추가: 팔꿈치각을 USER 화면과 EXPERT skeleton에 arc 레이어로 표시.
  - 핵심 지표: 손목-팔꿈치 수직 정렬, 팔꿈치각/락아웃, 양손 높이차,
              어깨 높이차, 벤치라인(머리-어깨-엉덩이)

Purpose:
    벤치프레스 전용 사용자-전문가 비교 및 시각적 자세 피드백 생성.
    unified_feedback_v4.py와 별개로 개발된 벤치프레스 단독 실행 스크립트.

Supported exercise:
    benchpress

Input:
    - USER_VIDEO_PATH: 사용자 벤치프레스 영상 (기본값 user_benchpress.mp4)
    - EXPERT_JSON_PATH: 전문가 landmark/지표 JSON (기본값 expert_benchpress.json,
      이 저장소에는 src/posture_feedback/benchpress/expert_benchpress.json 샘플 포함)
    - MODEL_PATH: MediaPipe pose_landmarker_lite.task (이 저장소에는 미포함,
      requirements.txt 안내에 따라 별도 다운로드 필요)
    이 스크립트는 unified_feedback_v4.py와 달리 expert JSON을 자동 생성하지
    않는다. EXPERT_JSON_PATH가 없으면 FileNotFoundError로 즉시 종료된다
    (load_expert_json 참고) — 반드시 사전 preprocess로 JSON을 먼저 만들어야 한다.

Output:
    output/benchpress_v4_feedback1.mp4 (USER + EXPERT skeleton + HUD 3분할 영상)

Main dependencies:
    opencv-python(cv2), mediapipe(mediapipe.tasks.python.vision), numpy, Pillow(PIL)

Notes:
    - 측면 영상 전용, 전문가 JSON 필수(자동 전처리 없음).
    - FONT_PATH가 Windows 시스템 폰트 경로("C:/Windows/Fonts/malgun.ttf")로
      하드코딩되어 있다. Windows 외 환경에서는 해당 경로가 없으므로 한글이
      깨지지 않고 자동으로 영어 라벨(_ko 함수)로 대체되지만, 폰트 자체는
      로드되지 않는다. unified_feedback_v4.py의 FONT_CANDIDATES 방식(여러
      OS 경로 후보 탐색)과 다르다 — 동작 방식을 바꾸는 수정은 이번 문서화
      작업 범위에서 하지 않았다.
    - threshold 값이 unified_feedback_v4.py, deadlift_feedback_v2_CLEAN.py와
      서로 다르다. 자세한 비교는 ../../../docs/thresholds.md 참고.
    - 실제 완전한 코드인지 여부는 팀(원 제작자)이 "unified 코드도 완전한
      코드가 아니다"라고 밝혔으므로, 이 파일 역시 동작을 100% 보증하지
      않는다. 문서화 시점 기준으로 직접 실행 검증은 하지 못했다.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import types
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import cv2
import numpy as np
from PIL import Image as PilImage, ImageDraw, ImageFont

# ══════════════════════════════════════════════════════════════
# [설정] 여기만 필요시 수정
# ══════════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).resolve().parent

EXERCISE = "benchpress"
USER_VIDEO_PATH = BASE_DIR / "user_benchpress.mp4"
EXPERT_JSON_PATH = BASE_DIR / "expert_benchpress.json"
MODEL_PATH = BASE_DIR / "pose_landmarker_lite.task"

OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "benchpress_v4_feedback1.mp4"

FONT_PATH = Path("C:/Windows/Fonts/malgun.ttf")
MIRROR_CAMERA = False
VISIBILITY_THRESHOLD = 0.35
SMOOTH_WINDOW = 5

# EXPERT skeleton 패널 표시.
# 단, 실제 expert 원본영상이 아니라 expert_benchpress.json의 landmark skeleton을 표시함.
SHOW_EXPERT_PANEL = True

# 발바닥 지표는 계산은 하되, v1 HUD/핵심 피드백에서는 기본적으로 제외.
USE_FOOT_FEEDBACK = False

# 벤치프레스 threshold
# ratio 계열은 torso_length로 정규화된 값.
DELTA_THRESHOLDS: Dict[str, float] = {
    "wrist_elbow_x_diff": 0.08,
    "elbow_angle": 12.0,
    "elbow_angle_avg": 12.0,
    "hand_height_diff": 0.08,
    "shoulder_height_diff": 0.07,
    "bench_line_diff": 0.08,
    "foot_offset": 0.10,
    "foot_flatness": 0.04,
}

ABS_THRESHOLDS: Dict[str, float] = {
    "lockout_angle_min": 165.0,  # 상단 구간에서 팔꿈치각이 이 값보다 작으면 락아웃 부족
    "elbow_above_shoulder": 0.0, # boolean 지표: 1이면 주의 후보
}

# HUD에 보여줄 핵심 지표. foot은 v1에서 숨김.
HUD_METRICS = [
    ("손목-팔꿈치", "Wrist-Elbow", "wrist_elbow_x_diff", ""),
    ("팔꿈치각", "Elbow angle", "elbow_angle", "deg"),
    ("락아웃각", "Lockout angle", "lockout_angle_min", "deg"),
    ("양손높이차", "Hand height diff", "hand_height_diff", ""),
    ("어깨높이차", "Shoulder height", "shoulder_height_diff", ""),
    ("벤치라인", "Bench line", "bench_line_diff", ""),
]

# 핵심 오류 우선순위
PRIORITY_KEYS = [
    "wrist_elbow_x_diff",
    "lockout_angle_min",
    "elbow_angle",
    "elbow_angle_avg",
    "hand_height_diff",
    "bench_line_diff",
    "shoulder_height_diff",
]
if USE_FOOT_FEEDBACK:
    PRIORITY_KEYS += ["foot_flatness", "foot_offset"]

# MediaPipe landmark 연결선: 벤치프레스 화면을 너무 지저분하지 않게 핵심만 그림
SKEL_CONNS = [
    (0, 11), (0, 12), (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (27, 31),
    (24, 26), (26, 28), (28, 32),
]

# BGR colors
C_BONE = (70, 220, 115)
C_JOINT = (135, 255, 170)
C_WARN = (0, 0, 255)
C_YELLOW = (0, 215, 255)
C_WHITE = (245, 245, 245)
C_GRAY = (150, 150, 160)
C_PANEL = (18, 18, 28)

# ══════════════════════════════════════════════════════════════
# MediaPipe Tasks import
# ══════════════════════════════════════════════════════════════
for _n in ["mediapipe.tasks.python.genai", "mediapipe.tasks.python.genai.bundler"]:
    sys.modules.setdefault(_n, types.ModuleType(_n))

from mediapipe.tasks.python.vision import pose_landmarker as _pl
from mediapipe.tasks.python.vision.core import vision_task_running_mode as _vtm
from mediapipe.tasks.python.core import base_options as _bo


def _find_image_classes():
    try:
        from mediapipe.tasks.python.vision.core import image as m
        return m.Image, m.ImageFormat
    except (ImportError, AttributeError):
        pass
    try:
        from mediapipe.python._framework_bindings import image as _img
        from mediapipe.python._framework_bindings import image_frame as _imgf
        return _img.Image, _imgf.ImageFormat
    except (ImportError, AttributeError):
        pass
    raise ImportError("mediapipe Image 클래스를 찾을 수 없습니다. mediapipe 설치를 확인하세요.")


_MpImage, _ImageFormat = _find_image_classes()
PoseLandmarker = _pl.PoseLandmarker
PoseLandmarkerOptions = _pl.PoseLandmarkerOptions
BaseOptions = _bo.BaseOptions
RunningMode = _vtm.VisionTaskRunningMode
MpImage = _MpImage
ImageFormat = _ImageFormat


def build_landmarker():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"모델 파일 없음: {MODEL_PATH}")
    opts = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return PoseLandmarker.create_from_options(opts)


def extract_landmarks(landmarker, bgr: np.ndarray):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    mp_img = MpImage(image_format=ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_img)
    return result.pose_landmarks[0] if result.pose_landmarks else None

# ══════════════════════════════════════════════════════════════
# Font / text helpers
# ══════════════════════════════════════════════════════════════
FONT_KR_OK = FONT_PATH.exists()


def _font(size: int):
    try:
        if FONT_KR_OK:
            return ImageFont.truetype(str(FONT_PATH), size)
    except Exception:
        pass
    return ImageFont.load_default()


def _ko(kr: str, en: str) -> str:
    return kr if FONT_KR_OK else en


def draw_text_box_bgr(frame: np.ndarray, lines, xy=(16, 16), font_size=20,
                      fg=(255, 255, 255), bg=(18, 18, 28), pad=8, alpha=0.76) -> np.ndarray:
    if isinstance(lines, str):
        lines = [lines]

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    base = PilImage.fromarray(rgb).convert("RGBA")
    overlay = PilImage.new("RGBA", base.size, (0, 0, 0, 0))
    drw = ImageDraw.Draw(overlay)
    font = _font(font_size)
    line_h = font_size + 7

    widths = []
    for line in lines:
        try:
            bbox = drw.textbbox((0, 0), str(line), font=font)
            widths.append(bbox[2] - bbox[0])
        except Exception:
            widths.append(len(str(line)) * font_size * 0.6)

    box_w = int(max(widths, default=80) + pad * 2)
    box_h = int(len(lines) * line_h + pad * 2)
    x, y = int(xy[0]), int(xy[1])
    x = max(0, min(x, frame.shape[1] - box_w - 2))
    y = max(0, min(y, frame.shape[0] - box_h - 2))

    bg_rgba = (bg[0], bg[1], bg[2], int(255 * alpha))
    try:
        drw.rounded_rectangle([x, y, x + box_w, y + box_h], radius=10, fill=bg_rgba)
    except Exception:
        drw.rectangle([x, y, x + box_w, y + box_h], fill=bg_rgba)

    for i, line in enumerate(lines):
        drw.text((x + pad, y + pad + i * line_h), str(line), font=font, fill=fg + (255,))

    out = PilImage.alpha_composite(base, overlay).convert("RGB")
    return cv2.cvtColor(np.array(out), cv2.COLOR_RGB2BGR)

# ══════════════════════════════════════════════════════════════
# Geometry helpers
# ══════════════════════════════════════════════════════════════
Point2 = np.ndarray


def get_xyv(lms, idx: int) -> Tuple[Point2, float]:
    p = lms[idx]
    if hasattr(p, "x"):
        return np.array([float(p.x), float(p.y)], dtype=np.float32), float(getattr(p, "visibility", 1.0))
    x, y = float(p[0]), float(p[1])
    v = float(p[3]) if len(p) > 3 else 1.0
    return np.array([x, y], dtype=np.float32), v


def midp(lms, a: int, b: int) -> Point2:
    pa, va = get_xyv(lms, a)
    pb, vb = get_xyv(lms, b)
    if va >= VISIBILITY_THRESHOLD and vb >= VISIBILITY_THRESHOLD:
        return (pa + pb) / 2.0
    return pa if va >= vb else pb


def dist2d(a: Point2, b: Point2) -> float:
    return float(np.linalg.norm(a - b))


def angle_abc(a: Point2, b: Point2, c: Point2) -> float:
    ba = a - b
    bc = c - b
    n = np.linalg.norm(ba) * np.linalg.norm(bc)
    if n < 1e-9:
        return 0.0
    cosv = float(np.dot(ba, bc) / n)
    cosv = float(np.clip(cosv, -1.0, 1.0))
    return float(math.degrees(math.acos(cosv)))


def _vis_sum(lms, ids: List[int]) -> float:
    total = 0.0
    for i in ids:
        try:
            _, v = get_xyv(lms, i)
            total += float(v)
        except Exception:
            pass
    return total


def pick_visible_upper_side(lms) -> Dict[str, int]:
    """벤치 측면영상에서 더 잘 보이는 팔/상체 쪽을 대표 side로 사용."""
    left = _vis_sum(lms, [11, 13, 15, 23, 25, 27, 31])
    right = _vis_sum(lms, [12, 14, 16, 24, 26, 28, 32])
    if right > left:
        return {"shoulder": 12, "elbow": 14, "wrist": 16, "hip": 24, "knee": 26, "ankle": 28, "heel": 30, "foot": 32}
    return {"shoulder": 11, "elbow": 13, "wrist": 15, "hip": 23, "knee": 25, "ankle": 27, "heel": 29, "foot": 31}


def compute_bench_metrics(lms) -> Dict[str, float]:
    side = pick_visible_upper_side(lms)

    sh, _ = get_xyv(lms, side["shoulder"])
    el, _ = get_xyv(lms, side["elbow"])
    wr, _ = get_xyv(lms, side["wrist"])
    hp, _ = get_xyv(lms, side["hip"])
    kn, _ = get_xyv(lms, side["knee"])
    an, _ = get_xyv(lms, side["ankle"])
    heel, _ = get_xyv(lms, side["heel"])
    foot, _ = get_xyv(lms, side["foot"])

    l_sh, _ = get_xyv(lms, 11); r_sh, _ = get_xyv(lms, 12)
    l_el, _ = get_xyv(lms, 13); r_el, _ = get_xyv(lms, 14)
    l_wr, _ = get_xyv(lms, 15); r_wr, _ = get_xyv(lms, 16)
    l_hip, _ = get_xyv(lms, 23); r_hip, _ = get_xyv(lms, 24)
    l_an, _ = get_xyv(lms, 27); r_an, _ = get_xyv(lms, 28)
    l_heel, _ = get_xyv(lms, 29); r_heel, _ = get_xyv(lms, 30)
    l_foot, _ = get_xyv(lms, 31); r_foot, _ = get_xyv(lms, 32)

    shoulder_c = midp(lms, 11, 12)
    hip_c = midp(lms, 23, 24)
    torso_len = max(dist2d(shoulder_c, hip_c), 1e-6)

    elbow_angle = angle_abc(sh, el, wr)
    left_elbow = angle_abc(l_sh, l_el, l_wr)
    right_elbow = angle_abc(r_sh, r_el, r_wr)
    elbow_angle_avg = (left_elbow + right_elbow) / 2.0

    # 측면 기준: 손목이 팔꿈치 수직선에서 얼마나 벗어났는가
    wrist_elbow_x_diff = abs(float(wr[0] - el[0])) / torso_len

    # lockout은 현재 대표 팔꿈치각 값을 저장하고, 판단은 phase에서 별도 수행
    lockout_angle_min = elbow_angle

    # 이미지 좌표계: y가 작을수록 위쪽
    elbow_above_shoulder = 1.0 if float(el[1]) < float(sh[1]) else 0.0

    hand_height_diff = abs(float(l_wr[1] - r_wr[1])) / torso_len
    shoulder_height_diff = abs(float(l_sh[1] - r_sh[1])) / torso_len

    # 벤치라인: 누운 자세에서 머리/어깨/엉덩이 높이 방향 spread
    nose, _ = get_xyv(lms, 0)
    ys = [float(nose[1]), float(shoulder_c[1]), float(hip_c[1])]
    bench_line_diff = (max(ys) - min(ys)) / torso_len

    foot_offset = abs(float(l_an[0] - r_an[0])) / torso_len
    left_foot_flatness = abs(float(l_heel[1] - l_foot[1])) / torso_len
    right_foot_flatness = abs(float(r_heel[1] - r_foot[1])) / torso_len
    foot_flatness = max(left_foot_flatness, right_foot_flatness)

    # 보조 지표
    knee_angle = angle_abc(hp, kn, an)

    return {
        "elbow_angle": float(elbow_angle),
        "elbow_angle_avg": float(elbow_angle_avg),
        "wrist_elbow_x_diff": float(wrist_elbow_x_diff),
        "lockout_angle_min": float(lockout_angle_min),
        "elbow_above_shoulder": float(elbow_above_shoulder),
        "hand_height_diff": float(hand_height_diff),
        "shoulder_height_diff": float(shoulder_height_diff),
        "bench_line_diff": float(bench_line_diff),
        "foot_offset": float(foot_offset),
        "foot_flatness": float(foot_flatness),
        "left_foot_flatness": float(left_foot_flatness),
        "right_foot_flatness": float(right_foot_flatness),
        "knee_angle": float(knee_angle),
    }


class MetricsBuffer:
    def __init__(self, window: int = 5):
        self.window = int(window)
        self.buf: List[Dict[str, float]] = []

    def push(self, metrics: Dict[str, float]) -> None:
        self.buf.append(dict(metrics))
        if len(self.buf) > self.window:
            self.buf.pop(0)

    def avg(self) -> Dict[str, float]:
        if not self.buf:
            return {}
        keys = set().union(*(m.keys() for m in self.buf))
        out = {}
        for k in keys:
            vals = [float(m[k]) for m in self.buf if k in m and isinstance(m[k], (int, float, np.floating)) and np.isfinite(m[k])]
            if vals:
                out[k] = float(np.mean(vals))
        return out

# ══════════════════════════════════════════════════════════════
# Expert JSON
# ══════════════════════════════════════════════════════════════

def load_expert_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"전문가 JSON 없음: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "frames" not in data or not data["frames"]:
        raise ValueError("expert JSON에 frames 데이터가 없습니다.")
    return data


def compute_expert_metrics(frame_pack: Dict[str, Any]) -> Dict[str, float]:
    lms = frame_pack.get("landmarks")
    if not lms or len(lms) < 33:
        return dict(frame_pack.get("metrics", {}))
    # 전처리 JSON의 기존 metrics보다 현재 코드 기준 metrics를 우선 계산
    try:
        out = compute_bench_metrics(lms)
        # 혹시 추가 저장된 metric이 있으면 뒤에 보강
        saved = frame_pack.get("metrics", {})
        if isinstance(saved, dict):
            for k, v in saved.items():
                out.setdefault(k, v)
        return out
    except Exception:
        return dict(frame_pack.get("metrics", {}))


def build_expert_cache(expert: Dict[str, Any]) -> List[Dict[str, float]]:
    return [compute_expert_metrics(pack) for pack in expert["frames"]]


def match_expert_frame(user_metrics: Dict[str, float], expert_cache: List[Dict[str, float]], fallback_idx: int = 0) -> int:
    """벤치프레스 v1: elbow angle 중심으로 가장 비슷한 전문가 프레임 선택."""
    keys = ["elbow_angle", "wrist_elbow_x_diff", "bench_line_diff"]
    weights = {"elbow_angle": 1.0, "wrist_elbow_x_diff": 45.0, "bench_line_diff": 35.0}
    best_i = int(fallback_idx)
    best_score = float("inf")
    for i, em in enumerate(expert_cache):
        score = 0.0
        n = 0
        for k in keys:
            if k not in user_metrics or k not in em:
                continue
            try:
                score += weights.get(k, 1.0) * abs(float(user_metrics[k]) - float(em[k]))
                n += 1
            except Exception:
                pass
        if n == 0:
            continue
        score /= n
        if score < best_score:
            best_score = score
            best_i = i
    return best_i


def compute_deltas(user_metrics: Dict[str, float], expert_metrics: Dict[str, float]) -> Dict[str, float]:
    deltas = {}
    for k in set(user_metrics.keys()) & set(expert_metrics.keys()):
        try:
            deltas[k] = float(user_metrics[k]) - float(expert_metrics[k])
        except Exception:
            pass
    return deltas

# ══════════════════════════════════════════════════════════════
# Feedback / phase / rep count
# ══════════════════════════════════════════════════════════════

def _safe_float(x, default=None):
    try:
        x = float(x)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def phase_from_metrics(metrics: Dict[str, float]) -> str:
    e = _safe_float(metrics.get("elbow_angle"), None)
    if e is None:
        e = _safe_float(metrics.get("elbow_angle_avg"), None)
    if e is None:
        return _ko("구간 인식 중", "Detecting phase")
    if e >= 150:
        return _ko("준비/락아웃", "Ready / lockout")
    if e <= 100:
        return _ko("가슴터치/최저점", "Bottom")
    return _ko("하강·상승 중간", "Mid phase")


def is_top_phase(metrics: Dict[str, float]) -> bool:
    e = _safe_float(metrics.get("elbow_angle"), None)
    if e is None:
        e = _safe_float(metrics.get("elbow_angle_avg"), None)
    return e is not None and e >= 140


def feedback_for_key(key: str, delta: Optional[float] = None) -> str:
    if key == "wrist_elbow_x_diff":
        return _ko("손목이 팔꿈치 수직선에서 벗어남", "Wrist not stacked over elbow")
    if key in ["elbow_angle", "elbow_angle_avg"]:
        return _ko("팔꿈치 각도 차이 확인", "Check elbow angle")
    if key == "lockout_angle_min":
        return _ko("팔꿈치 락아웃 부족", "Insufficient elbow lockout")
    if key == "hand_height_diff":
        return _ko("양손 높이 차이 확인", "Check uneven hand height")
    if key == "shoulder_height_diff":
        return _ko("어깨 높이 차이 확인", "Check shoulder height")
    if key == "bench_line_diff":
        return _ko("머리-어깨-엉덩이 라인 이탈", "Bench body line issue")
    if key == "foot_flatness":
        return _ko("발바닥 접지 확인", "Check foot contact")
    if key == "foot_offset":
        return _ko("양발 앞뒤 위치 확인", "Check foot offset")
    if key == "elbow_above_shoulder":
        return _ko("팔꿈치가 어깨보다 높음", "Elbow above shoulder")
    return _ko("자세 차이 확인", "Check form")


def choose_issue(metrics: Dict[str, float], deltas: Dict[str, float]) -> Optional[Dict[str, Any]]:
    # 1) 상단 구간에서 lockout 부족 먼저 체크
    e = _safe_float(metrics.get("lockout_angle_min"), None)
    lock_thr = ABS_THRESHOLDS["lockout_angle_min"]
    if is_top_phase(metrics) and e is not None and e < lock_thr:
        return {"key": "lockout_angle_min", "message": feedback_for_key("lockout_angle_min"), "ratio": abs(e - lock_thr) / 20.0}

    # 2) 팔꿈치가 어깨보다 위: 주의 후보. 너무 강하면 오탐이 많아 우선순위는 낮게 둠.
    above = _safe_float(metrics.get("elbow_above_shoulder"), 0.0)
    elbow_phase = _safe_float(metrics.get("elbow_angle"), 180.0)
    if above >= 0.5 and elbow_phase is not None and elbow_phase < 145:
        # 하강/전환 구간에서만 표시
        return {"key": "elbow_above_shoulder", "message": feedback_for_key("elbow_above_shoulder"), "ratio": 1.0}

    # 3) delta 기반 후보
    candidates = []
    for key in PRIORITY_KEYS:
        if key not in deltas:
            continue
        thr = DELTA_THRESHOLDS.get(key)
        d = _safe_float(deltas.get(key), None)
        if thr is None or d is None or thr <= 0:
            continue
        ratio = abs(d) / max(thr, 1e-6)
        if ratio < 1.0:
            continue
        base = {
            "wrist_elbow_x_diff": 100,
            "lockout_angle_min": 95,
            "elbow_angle": 85,
            "elbow_angle_avg": 80,
            "hand_height_diff": 76,
            "bench_line_diff": 72,
            "shoulder_height_diff": 65,
            "foot_flatness": 45,
            "foot_offset": 40,
        }.get(key, 30)
        candidates.append({
            "key": key,
            "message": feedback_for_key(key, d),
            "ratio": ratio,
            "priority": base + min(ratio, 2.0) * 5,
        })
    if candidates:
        return sorted(candidates, key=lambda x: x["priority"], reverse=True)[0]
    return None


class FeedbackStabilizer:
    def __init__(self, min_frames: int = 3, hold_frames: int = 8):
        self.min_frames = min_frames
        self.hold_frames = hold_frames
        self.candidate_key = None
        self.candidate_count = 0
        self.stable_issue = None
        self.hold_left = 0

    def update(self, issue: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if issue is None:
            self.candidate_key = None
            self.candidate_count = 0
            if self.stable_issue is not None and self.hold_left > 0:
                self.hold_left -= 1
                return self.stable_issue
            self.stable_issue = None
            return None

        key = issue.get("key")
        if key == self.candidate_key:
            self.candidate_count += 1
        else:
            self.candidate_key = key
            self.candidate_count = 1

        if self.stable_issue is None or self.candidate_count >= self.min_frames:
            self.stable_issue = issue
            self.hold_left = self.hold_frames
        return self.stable_issue


class BenchRepCounter:
    def __init__(self, min_hold_frames: int = 3, cooldown_frames: int = 8):
        self.count = 0
        self.state = "top"
        self.bottom_hold = 0
        self.top_hold = 0
        self.cooldown = 0
        self.min_hold_frames = min_hold_frames
        self.cooldown_frames = cooldown_frames

    def update(self, metrics: Dict[str, float]) -> bool:
        e = _safe_float(metrics.get("elbow_angle"), None)
        if e is None:
            e = _safe_float(metrics.get("elbow_angle_avg"), None)
        if e is None:
            return False

        bottom = e <= 100
        top = e >= 155

        if self.cooldown > 0:
            self.cooldown -= 1

        self.bottom_hold = self.bottom_hold + 1 if bottom else 0
        self.top_hold = self.top_hold + 1 if top else 0

        if self.state != "bottom" and self.bottom_hold >= self.min_hold_frames:
            self.state = "bottom"
            return False

        if self.state == "bottom" and self.top_hold >= self.min_hold_frames and self.cooldown == 0:
            self.count += 1
            self.state = "top"
            self.cooldown = self.cooldown_frames
            return True
        return False

# ══════════════════════════════════════════════════════════════
# Drawing
# ══════════════════════════════════════════════════════════════

def lm_px(lms, idx: int, W: int, H: int) -> Tuple[Tuple[int, int], float]:
    p, v = get_xyv(lms, idx)
    return (int(p[0] * W), int(p[1] * H)), v



def draw_skeleton(frame: np.ndarray, lms, issue_key: Optional[str] = None) -> np.ndarray:
    """
    벤치프레스 USER skeleton을 깔끔하게 그린다.
    v2에서는 issue_key가 elbow/hand 계열이면 상체 선이 전부 빨갛게 변해 화면이 지저분했다.
    v4에서는 기본 skeleton은 항상 초록색으로 유지하고,
    실제 확인해야 할 관절만 작은 빨간 원으로 표시한다.
    팔꿈치각 자체는 draw_elbow_angle_arc()에서 스쿼트처럼 arc로 강조한다.
    """
    H, W = frame.shape[:2]

    # 문제 관절만 최소 표시
    warn_indices = set()
    side = None
    try:
        side = pick_visible_upper_side(lms)
    except Exception:
        side = None

    if side is not None:
        if issue_key == "wrist_elbow_x_diff":
            warn_indices.update([side["wrist"], side["elbow"]])
        elif issue_key in ["elbow_angle", "elbow_angle_avg", "lockout_angle_min", "elbow_above_shoulder"]:
            warn_indices.update([side["shoulder"], side["elbow"], side["wrist"]])

    if issue_key == "bench_line_diff":
        warn_indices.update([0, 11, 12, 23, 24])
    elif issue_key == "hand_height_diff":
        warn_indices.update([15, 16])
    elif issue_key == "shoulder_height_diff":
        warn_indices.update([11, 12])
    elif issue_key in ["foot_flatness", "foot_offset"]:
        warn_indices.update([27, 28, 29, 30, 31, 32])

    # 기본 skeleton: 항상 초록색 계열
    for a, b in SKEL_CONNS:
        pa, va = lm_px(lms, a, W, H)
        pb, vb = lm_px(lms, b, W, H)
        if va < VISIBILITY_THRESHOLD or vb < VISIBILITY_THRESHOLD:
            continue
        cv2.line(frame, pa, pb, C_BONE, 3, cv2.LINE_AA)

    # 관절점: 오류 관절만 빨간 링, 나머지는 작게
    for idx in [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32]:
        pt, v = lm_px(lms, idx, W, H)
        if v < VISIBILITY_THRESHOLD:
            continue
        if idx in warn_indices:
            cv2.circle(frame, pt, 13, C_WARN, 2, cv2.LINE_AA)
            cv2.circle(frame, pt, 4, C_WARN, -1, cv2.LINE_AA)
        else:
            cv2.circle(frame, pt, 4, C_JOINT, -1, cv2.LINE_AA)
    return frame



def draw_wrist_elbow_guide(frame: np.ndarray, lms, metrics: Dict[str, float], issue_key: Optional[str]) -> np.ndarray:
    """
    손목-팔꿈치 수직 정렬 가이드.
    너무 두껍게 그리면 팔꿈치 arc와 겹쳐 지저분하므로 v4에서는 얇은 점선 + 짧은 수평선만 표시.
    """
    H, W = frame.shape[:2]
    side = pick_visible_upper_side(lms)
    wr, vw = lm_px(lms, side["wrist"], W, H)
    el, ve = lm_px(lms, side["elbow"], W, H)
    if min(vw, ve) < VISIBILITY_THRESHOLD:
        return frame

    color = C_WARN if issue_key == "wrist_elbow_x_diff" else (0, 190, 255)

    y1 = max(0, min(wr[1], el[1]) - 45)
    y2 = min(H - 1, max(wr[1], el[1]) + 45)

    # elbow x 기준 점선
    for y in range(y1, y2, 10 + 8):
        cv2.line(frame, (el[0], y), (el[0], min(y + 10, y2)), color, 2, cv2.LINE_AA)

    # wrist가 elbow 수직선에서 벗어난 정도
    cv2.line(frame, wr, (el[0], wr[1]), color, 2, cv2.LINE_AA)
    cv2.circle(frame, wr, 5, color, -1, cv2.LINE_AA)
    cv2.circle(frame, el, 5, color, -1, cv2.LINE_AA)
    return frame




def _shortest_angle_sweep(a1: float, a2: float) -> float:
    """a1에서 a2까지 가장 짧은 방향의 sweep 각도(-180~180)."""
    return (float(a2) - float(a1) + 180.0) % 360.0 - 180.0



def _draw_elbow_arc_on_points(frame: np.ndarray,
                              sh: Tuple[int, int],
                              el: Tuple[int, int],
                              wr: Tuple[int, int],
                              angle_value: Optional[float],
                              color: Tuple[int, int, int],
                              thickness: int = 5,
                              label: bool = True) -> np.ndarray:
    """
    스쿼트 무릎 arc처럼 팔꿈치 주변에 굵은 각도 arc를 그리는 공통 함수.
    """
    H, W = frame.shape[:2]

    a1 = math.degrees(math.atan2(sh[1] - el[1], sh[0] - el[0]))
    a2 = math.degrees(math.atan2(wr[1] - el[1], wr[0] - el[0]))
    sweep = _shortest_angle_sweep(a1, a2)

    upper_len = math.hypot(sh[0] - el[0], sh[1] - el[1])
    lower_len = math.hypot(wr[0] - el[0], wr[1] - el[1])
    radius = int(max(30, min(82, min(upper_len, lower_len) * 0.50)))

    n = max(18, int(abs(sweep) / 5))
    pts = []
    for i in range(n + 1):
        t = i / max(n, 1)
        ang = math.radians(a1 + sweep * t)
        pts.append((int(el[0] + radius * math.cos(ang)), int(el[1] + radius * math.sin(ang))))

    if len(pts) >= 2:
        arr = np.array(pts, dtype=np.int32)
        # 검은 외곽선을 먼저 그려 배경과 분리
        cv2.polylines(frame, [arr], False, (15, 15, 20), thickness + 3, cv2.LINE_AA)
        cv2.polylines(frame, [arr], False, color, thickness, cv2.LINE_AA)

    # arc 양끝점과 팔꿈치 중심 강조
    if pts:
        cv2.circle(frame, pts[0], 5, color, -1, cv2.LINE_AA)
        cv2.circle(frame, pts[-1], 5, color, -1, cv2.LINE_AA)
    cv2.circle(frame, el, 7, color, -1, cv2.LINE_AA)

    # 팔꿈치 주변 팔 segment도 살짝 강조
    cv2.line(frame, sh, el, color, 4, cv2.LINE_AA)
    cv2.line(frame, el, wr, color, 4, cv2.LINE_AA)

    if label and angle_value is not None and isinstance(angle_value, (int, float, np.floating)) and np.isfinite(angle_value):
        txt = f"{float(angle_value):.0f}deg"

        # label 위치: arc 중간점 바깥쪽
        mid_i = len(pts) // 2 if pts else 0
        if pts:
            mx, my = pts[mid_i]
        else:
            mx, my = el
        vx = mx - el[0]
        vy = my - el[1]
        norm = math.hypot(vx, vy) or 1.0
        tx = int(mx + 14 * vx / norm)
        ty = int(my + 14 * vy / norm)

        tx = max(5, min(tx, W - 85))
        ty = max(24, min(ty, H - 8))

        cv2.putText(frame, txt, (tx + 1, ty + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, txt, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2, cv2.LINE_AA)

    return frame


def draw_elbow_angle_arc(frame: np.ndarray, lms, metrics: Dict[str, float], issue_key: Optional[str]) -> np.ndarray:
    """
    벤치프레스용 팔꿈치각 arc 레이어 v4.
    스쿼트 v5의 무릎 arc처럼:
    - 대표 팔의 어깨-팔꿈치-손목 각도를 굵은 arc로 표시
    - 팔꿈치 관련 오류일 때 빨간색
    - 평상시에는 노란색
    """
    H, W = frame.shape[:2]
    side = pick_visible_upper_side(lms)
    sh, vs = lm_px(lms, side["shoulder"], W, H)
    el, ve = lm_px(lms, side["elbow"], W, H)
    wr, vw = lm_px(lms, side["wrist"], W, H)

    if min(vs, ve, vw) < VISIBILITY_THRESHOLD:
        return frame

    elbow_issue_keys = {"elbow_angle", "elbow_angle_avg", "lockout_angle_min", "elbow_above_shoulder"}
    color = C_WARN if issue_key in elbow_issue_keys else C_YELLOW

    ang_val = metrics.get("elbow_angle")
    if ang_val is None:
        ang_val = metrics.get("elbow_angle_avg")

    return _draw_elbow_arc_on_points(frame, sh, el, wr, ang_val, color, thickness=5, label=True)


def draw_bench_line(frame: np.ndarray, lms, issue_key: Optional[str]) -> np.ndarray:
    H, W = frame.shape[:2]
    nose, vn = lm_px(lms, 0, W, H)
    sh_c = midp(lms, 11, 12)
    hp_c = midp(lms, 23, 24)
    sh = (int(sh_c[0] * W), int(sh_c[1] * H))
    hp = (int(hp_c[0] * W), int(hp_c[1] * H))
    color = C_WARN if issue_key == "bench_line_diff" else (80, 220, 120)
    # 머리-어깨-엉덩이 라인
    cv2.line(frame, nose, sh, color, 2, cv2.LINE_AA)
    cv2.line(frame, sh, hp, color, 2, cv2.LINE_AA)
    # 기준선: 세 점의 평균 y에 수평선
    y_ref = int((nose[1] + sh[1] + hp[1]) / 3)
    cv2.line(frame, (max(0, min(nose[0], sh[0], hp[0]) - 40), y_ref),
             (min(W - 1, max(nose[0], sh[0], hp[0]) + 40), y_ref),
             (110, 110, 130), 1, cv2.LINE_AA)
    return frame


def draw_banner(frame: np.ndarray, feedback: str, phase: str) -> np.ndarray:
    ok = feedback in [_ko("정상 범위", "OK"), "OK"] or "정상" in feedback
    fg = (120, 245, 150) if ok else (255, 130, 130)
    text = f"{phase}  |  {feedback}"
    return draw_text_box_bgr(frame, text, xy=(16, 52), font_size=21, fg=fg, bg=(18, 18, 28), alpha=0.78)


def _fmt_val(v, unit: str) -> str:
    if v is None or not isinstance(v, (int, float, np.floating)) or not np.isfinite(v):
        return "N/A"
    return f"{float(v):.1f}°" if unit == "deg" else f"{float(v):.2f}"


def make_hud(panel_w: int, panel_h: int, metrics: Dict[str, float], expert_metrics: Dict[str, float],
             deltas: Dict[str, float], rep_count: int, feedback: str, phase: str,
             fps_now: float, ex_idx: int, ex_total: int) -> np.ndarray:
    img = PilImage.new("RGB", (panel_w, panel_h), C_PANEL)
    drw = ImageDraw.Draw(img)
    f_title = _font(28)
    f_md = _font(16)
    f_sm = _font(13)

    y = 14
    drw.text((14, y), "BENCH PRESS", font=f_title, fill=(240, 205, 80))
    drw.text((panel_w - 74, y + 2), str(rep_count), font=f_title, fill=(80, 220, 255))
    drw.text((panel_w - 118, y + 12), _ko("횟수", "rep"), font=f_sm, fill=(165, 165, 175))
    y += 44

    drw.rounded_rectangle([10, y, panel_w - 10, y + 38], radius=10, fill=(31, 31, 45), outline=(65, 65, 85), width=1)
    drw.text((22, y + 9), phase, font=f_md, fill=(230, 230, 235))
    y += 48

    drw.text((14, y), _ko("U=사용자  E=전문가  Δ=차이", "U=user E=expert Δ=diff"), font=f_sm, fill=(145, 145, 155))
    y += 25

    ok = feedback in [_ko("정상 범위", "OK"), "OK"] or "정상" in feedback
    card_col = (95, 220, 120) if ok else (255, 115, 115)
    drw.rounded_rectangle([10, y, panel_w - 10, y + 70], radius=13, fill=(34, 34, 50), outline=card_col, width=2)
    drw.text((22, y + 9), _ko("현재 핵심 피드백", "Main feedback"), font=f_sm, fill=(180, 180, 190))
    # 간단 wrap
    fb = str(feedback)
    max_ch = max(8, (panel_w - 44) // (15 if FONT_KR_OK else 9))
    lines = [fb[i:i + max_ch] for i in range(0, len(fb), max_ch)][:2] or [fb]
    for i, line in enumerate(lines):
        drw.text((22, y + 31 + i * 21), line, font=f_md, fill=card_col)
    y += 84

    prog = _ko(f"전문가 프레임 {ex_idx+1}/{ex_total}   FPS {fps_now:.1f}",
               f"Expert {ex_idx+1}/{ex_total} FPS {fps_now:.1f}")
    drw.text((14, y), prog, font=f_sm, fill=(115, 115, 125))
    y += 24
    drw.line([(10, y), (panel_w - 10, y)], fill=(60, 60, 80), width=1)
    y += 14

    for kr, en, key, unit in HUD_METRICS:
        if y > panel_h - 80:
            break
        label = _ko(kr, en)
        val = metrics.get(key)

        if key == "lockout_angle_min":
            ex_val = ABS_THRESHOLDS["lockout_angle_min"]
            delta = None if val is None else float(val) - float(ex_val)
            bad = is_top_phase(metrics) and val is not None and float(val) < ex_val
        else:
            ex_val = expert_metrics.get(key)
            delta = deltas.get(key)
            thr = DELTA_THRESHOLDS.get(key)
            bad = False
            if delta is not None and thr is not None:
                bad = abs(float(delta)) > float(thr)

        col = (255, 130, 130) if bad else (120, 245, 150)
        drw.text((14, y), label, font=f_md, fill=(225, 225, 230))
        drw.text((panel_w - 74, y), _ko("주의", "WARN") if bad else "OK", font=f_md, fill=col)
        y += 21

        line = f"U {_fmt_val(val, unit)} / E {_fmt_val(ex_val, unit)}"
        if delta is not None:
            line += f" / Δ {_fmt_val(delta, unit)}"
        drw.text((22, y), line, font=f_sm, fill=(172, 172, 182))
        y += 19

        thr = DELTA_THRESHOLDS.get(key)
        if delta is not None and thr is not None and float(thr) > 0:
            bw = panel_w - 44
            ratio = min(abs(float(delta)) / float(thr), 1.5) / 1.5
            drw.rectangle([22, y, 22 + bw, y + 5], fill=(48, 48, 60))
            drw.rectangle([22, y, 22 + int(bw * ratio), y + 5], fill=col)
        y += 18

    drw.line([(10, panel_h - 64), (panel_w - 10, panel_h - 64)], fill=(60, 60, 80), width=1)
    drw.text((14, panel_h - 48), _ko("빨간 원 = 현재 우선 확인 관절", "Red circle = joint to check first"), font=f_sm, fill=(165, 165, 175))
    drw.text((14, panel_h - 28), _ko("EXPERT skeleton = JSON 기준자세", "Expert skeleton = JSON reference"), font=f_sm, fill=(115, 115, 125))

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)




def draw_expert_panel(panel_w: int, panel_h: int, ex_lms_raw, issue_key: Optional[str] = None) -> np.ndarray:
    """
    expert_benchpress.json에 저장된 landmark를 별도 검은 canvas에 그린다.
    v4에서는 EXPERT도 팔꿈치 arc를 굵게 표시해서 USER arc와 비교하기 쉽게 한다.
    """
    canvas = np.zeros((panel_h, panel_w, 3), dtype=np.uint8)
    if ex_lms_raw is None or len(ex_lms_raw) < 33:
        cv2.putText(canvas, "NO EXPERT", (20, panel_h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (90, 90, 100), 2, cv2.LINE_AA)
        return canvas

    def ex_px(idx: int):
        p = ex_lms_raw[idx]
        if hasattr(p, "x"):
            x, y = float(p.x), float(p.y)
            v = float(getattr(p, "visibility", 1.0))
        else:
            x, y = float(p[0]), float(p[1])
            v = float(p[3]) if len(p) > 3 else 1.0
        return (int(x * panel_w), int(y * panel_h)), v

    warn_indices = set()
    if issue_key == "wrist_elbow_x_diff":
        warn_indices.update([13, 14, 15, 16])
    elif issue_key in ["elbow_angle", "elbow_angle_avg", "lockout_angle_min", "elbow_above_shoulder"]:
        warn_indices.update([11, 12, 13, 14, 15, 16])
    elif issue_key == "bench_line_diff":
        warn_indices.update([0, 11, 12, 23, 24])
    elif issue_key == "hand_height_diff":
        warn_indices.update([15, 16])
    elif issue_key == "shoulder_height_diff":
        warn_indices.update([11, 12])

    exp_bone = (80, 220, 120)
    exp_joint = (180, 255, 180)

    # 기본 expert skeleton은 항상 초록색. 빨간 선으로 도배하지 않는다.
    for a, b in SKEL_CONNS:
        pa, va = ex_px(a)
        pb, vb = ex_px(b)
        if va < VISIBILITY_THRESHOLD or vb < VISIBILITY_THRESHOLD:
            continue
        cv2.line(canvas, pa, pb, exp_bone, 2, cv2.LINE_AA)

    for idx in [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32]:
        pt, v = ex_px(idx)
        if v < VISIBILITY_THRESHOLD:
            continue
        if idx in warn_indices:
            cv2.circle(canvas, pt, 10, C_WARN, 2, cv2.LINE_AA)
            cv2.circle(canvas, pt, 4, C_WARN, -1, cv2.LINE_AA)
        else:
            cv2.circle(canvas, pt, 4, exp_joint, -1, cv2.LINE_AA)

    # EXPERT 팔꿈치 arc
    try:
        _, v_ls = ex_px(11); _, v_le = ex_px(13); _, v_lw = ex_px(15)
        _, v_rs = ex_px(12); _, v_re = ex_px(14); _, v_rw = ex_px(16)
        if (v_rs + v_re + v_rw) > (v_ls + v_le + v_lw):
            s_idx, e_idx, w_idx = 12, 14, 16
        else:
            s_idx, e_idx, w_idx = 11, 13, 15

        sh, vs = ex_px(s_idx)
        el, ve = ex_px(e_idx)
        wr, vw = ex_px(w_idx)
        if min(vs, ve, vw) >= VISIBILITY_THRESHOLD:
            # expert angle 직접 계산
            sh_n = np.array([sh[0] / panel_w, sh[1] / panel_h], dtype=np.float32)
            el_n = np.array([el[0] / panel_w, el[1] / panel_h], dtype=np.float32)
            wr_n = np.array([wr[0] / panel_w, wr[1] / panel_h], dtype=np.float32)
            ex_angle = angle_abc(sh_n, el_n, wr_n)
            arc_color = C_WARN if issue_key in ["elbow_angle", "elbow_angle_avg", "lockout_angle_min", "elbow_above_shoulder"] else C_YELLOW
            canvas = _draw_elbow_arc_on_points(canvas, sh, el, wr, ex_angle, arc_color, thickness=4, label=True)
    except Exception:
        pass

    cv2.putText(canvas, "EXPERT", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, exp_bone, 2, cv2.LINE_AA)
    cv2.putText(canvas, "matched skeleton", (10, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (130, 130, 145), 1, cv2.LINE_AA)
    return canvas


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

def validate_files() -> None:
    for path, name in [
        (USER_VIDEO_PATH, "사용자 영상"),
        (EXPERT_JSON_PATH, "전문가 JSON"),
        (MODEL_PATH, "PoseLandmarker 모델"),
    ]:
        if not path.exists():
            raise FileNotFoundError(f"{name} 없음: {path}")
        print(f"OK | {name}: {path}")
    print(f"출력: {OUTPUT_PATH}")


def main() -> None:
    print("[BENCHPRESS FEEDBACK v4 - ARC LAYER CLEAN]")
    validate_files()

    expert = load_expert_json(EXPERT_JSON_PATH)
    ex_frames = expert["frames"]
    expert_cache = build_expert_cache(expert)
    ex_total = len(ex_frames)
    print(f"[전문가] {ex_total} frames loaded")

    print("[PoseLandmarker] 로딩 중...")
    landmarker = build_landmarker()
    print("[PoseLandmarker] 완료")

    cap = cv2.VideoCapture(str(USER_VIDEO_PATH))
    if not cap.isOpened():
        raise RuntimeError(f"영상 열기 실패: {USER_VIDEO_PATH}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    HUD_W = 420
    EXPERT_W = min(520, max(360, int(W * 0.42))) if SHOW_EXPERT_PANEL else 0
    OUT_W = W + EXPERT_W + HUD_W
    OUT_H = H

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(OUTPUT_PATH), fourcc, fps, (OUT_W, OUT_H))
    if not out.isOpened():
        raise RuntimeError(f"VideoWriter 열기 실패: {OUTPUT_PATH}")

    print(f"[영상] {W}x{H}, fps={fps:.2f}, frames={total}")
    print(f"[레이아웃] USER:{W}x{H} | EXPERT:{EXPERT_W}x{H} | HUD:{HUD_W}x{H}")
    print(f"[출력 크기] {OUT_W}x{OUT_H}")

    buf = MetricsBuffer(SMOOTH_WINDOW)
    stabilizer = FeedbackStabilizer(min_frames=3, hold_frames=8)
    rep_counter = BenchRepCounter()

    frame_idx = 0
    t_start = time.perf_counter()

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if MIRROR_CAMERA:
            frame = cv2.flip(frame, 1)

        user_canvas = frame.copy()
        lms = extract_landmarks(landmarker, user_canvas)

        feedback = _ko("자세를 인식할 수 없습니다", "Pose not detected")
        phase = _ko("구간 인식 중", "Detecting phase")
        metrics = {}
        deltas = {}
        expert_metrics = {}
        ex_idx = min(frame_idx * ex_total // max(total, 1), ex_total - 1)
        ex_lms_raw = ex_frames[ex_idx].get("landmarks")
        issue = None
        stable_issue = None
        issue_key = None

        if lms:
            try:
                raw = compute_bench_metrics(lms)
                buf.push(raw)
                metrics = buf.avg() or raw
                phase = phase_from_metrics(metrics)

                # 가장 비슷한 전문가 프레임으로 수치 비교. 화면에는 expert를 표시하지 않음.
                ex_idx = match_expert_frame(metrics, expert_cache, ex_idx)
                expert_metrics = expert_cache[ex_idx]
                ex_lms_raw = ex_frames[ex_idx].get("landmarks")
                deltas = compute_deltas(metrics, expert_metrics)

                if rep_counter.update(metrics):
                    print(f"[BENCH] {rep_counter.count}회")

                issue = choose_issue(metrics, deltas)
                stable_issue = stabilizer.update(issue)
                feedback = stable_issue["message"] if stable_issue else _ko("정상 범위", "OK")

                issue_key = stable_issue.get("key") if isinstance(stable_issue, dict) else None
                user_canvas = draw_skeleton(user_canvas, lms, issue_key)
                user_canvas = draw_wrist_elbow_guide(user_canvas, lms, metrics, issue_key)
                user_canvas = draw_elbow_angle_arc(user_canvas, lms, metrics, issue_key)
                user_canvas = draw_bench_line(user_canvas, lms, issue_key)
                user_canvas = draw_banner(user_canvas, feedback, phase)

            except Exception as e:
                feedback = f"지표 계산 오류: {e}"
                user_canvas = draw_text_box_bgr(user_canvas, feedback, xy=(16, 52), font_size=18, fg=(255, 130, 130))
        else:
            user_canvas = draw_text_box_bgr(user_canvas, feedback, xy=(16, 52), font_size=20, fg=(255, 130, 130))

        cv2.putText(user_canvas, "USER", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (60, 210, 255), 2, cv2.LINE_AA)

        elapsed = time.perf_counter() - t_start
        cur_fps = (frame_idx + 1) / max(elapsed, 1e-6)
        hud = make_hud(
            panel_w=HUD_W,
            panel_h=OUT_H,
            metrics=metrics,
            expert_metrics=expert_metrics,
            deltas=deltas,
            rep_count=rep_counter.count,
            feedback=feedback,
            phase=phase,
            fps_now=cur_fps,
            ex_idx=ex_idx,
            ex_total=ex_total,
        )

        if SHOW_EXPERT_PANEL:
            expert_canvas = draw_expert_panel(EXPERT_W, OUT_H, ex_lms_raw, issue_key if 'issue_key' in locals() else None)
            final_frame = np.hstack([user_canvas, expert_canvas, hud])
            cv2.line(final_frame, (W, 0), (W, OUT_H), (50, 50, 70), 2)
            cv2.line(final_frame, (W + EXPERT_W, 0), (W + EXPERT_W, OUT_H), (50, 50, 70), 2)
        else:
            final_frame = np.hstack([user_canvas, hud])
            cv2.line(final_frame, (W, 0), (W, OUT_H), (50, 50, 70), 2)
        out.write(final_frame)

        frame_idx += 1
        if frame_idx % 30 == 0:
            pct = frame_idx * 100 / max(total, 1)
            print(f"[처리 중] {frame_idx}/{total} ({pct:.1f}%) | rep={rep_counter.count} | feedback={feedback} | fps={cur_fps:.1f}")

    cap.release()
    out.release()
    try:
        landmarker.close()
    except Exception:
        pass

    size_mb = OUTPUT_PATH.stat().st_size / 1024 / 1024 if OUTPUT_PATH.exists() else 0
    print("\n[완료]")
    print(f"  총 프레임: {frame_idx}")
    print(f"  총 횟수  : {rep_counter.count}회")
    print(f"  저장 위치: {OUTPUT_PATH}")
    print(f"  파일 크기: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
