"""
deadlift_feedback_v2_CLEAN.py

이 파일은 사용자가 업로드한 squat_feedback_v5_UPGRADE.ipynb를 실제로 변환한 데드리프트용 로컬 실행 스크립트입니다.

변환/교체 내용
1. EXERCISE = 'deadlift' 로 고정
2. 사용자 영상 = user_deadlift_01.mp4
3. 전문가 JSON = expert_deadlift.json
4. 결과 영상 = output/deadlift_v1_feedback1.mp4
5. Colab/Drive/pip install 셀은 기존 노트북처럼 제거 상태 유지
6. 기존 v5 구조인 USER + EXPERT skeleton + HUD 패널 구조는 유지하되, 데드리프트용으로 USER 화면을 간소화

실행 위치
- 이 파일을 hand_project 폴더에 넣고 VS Code 터미널에서 실행:
  python deadlift_feedback_v2_CLEAN.py

Purpose:
    데드리프트 전용 사용자-전문가 비교 및 시각적 자세 피드백 생성.
    squat_feedback_v5_UPGRADE.ipynb(스쿼트용 노트북, 이 저장소에는 아직
    없음)를 데드리프트용으로 변환한 로컬 실행 스크립트.

Supported exercise:
    deadlift (단, 내부 EXERCISE_DELTA_THRESHOLDS 등은 squat/deadlift/bench
    3종 모두의 값을 정의하고 있어, EXERCISE 변수만 바꾸면 다른 종목에도
    쓸 수 있는 구조로 설계되어 있다. 다만 실제로 검증된 것은 deadlift뿐이다.)

Input:
    - USER_VIDEO_PATH: 사용자 데드리프트 영상 (기본값 user_deadlift_01.mp4)
    - EXPERT_JSON_PATH: 전문가 JSON (기본값 expert_deadlift.json — 이
      저장소에는 포함되어 있지 않다. expert_benchpress.json과 동일한
      스키마로 별도 생성해야 한다)
    - MODEL_PATH: pose_landmarker_lite.task (이 저장소에는 미포함)

Output:
    output/deadlift_v1_feedback_CLEAN.mp4

Main dependencies:
    opencv-python(cv2), mediapipe, numpy, Pillow(PIL), matplotlib(pip 설치
    안내에만 등장, 이 파일 내부에서 직접 import되지는 않음)
    그리고 반드시 로컬 모듈 realtime_compare_side.py(as rt), feedback_overlay.py
    (as fo)가 이 스크립트와 같은 폴더에 있어야 한다(Cell 4의 import 참고).

Notes:
    - **이 저장소에는 realtime_compare_side.py, feedback_overlay.py가 아직
      없다.** 두 모듈이 없으면 이 스크립트는 import 단계에서 즉시 실패한다.
      2학기(또는 팀 확인) 시 반드시 추가해야 실행 가능하다.
    - 측면 영상 전용, 전문가 JSON 필수(자동 전처리 로직은 이 파일이 아니라
      import되는 rt 모듈에 있을 가능성이 있으나, rt 모듈 자체가 없어 확인 불가.
    - Colab 전용 코드(Google Drive mount, !pip install 등)는 원 노트북에서
      이미 제거된 상태로 확인됨(주석에 명시).
    - FONT_PATH가 1차로 Windows 경로("C:/Windows/Fonts/malgun.ttf")로
      하드코딩되어 있으나, Cell 7의 find_korean_font()가 Linux/Nanum,
      NotoSansCJK 등 대체 경로를 탐색하도록 되어 있어 benchpress_feedback_v4.py
      보다 크로스플랫폼 대응이 더 되어 있다.
    - threshold 값이 unified_feedback_v4.py, benchpress_feedback_v4.py와
      서로 다르다. 자세한 비교는 ../../../docs/thresholds.md 참고.
    - 팀이 "완전한 코드가 아니다"라고 밝혔으며, 이 저장소에서 직접 실행
      검증은 하지 못했다(의존 모듈 부재로 애초에 실행 불가능한 상태).
"""

# %% [converted from squat_feedback_v5_UPGRADE.ipynb]


# %%
# ===== Original notebook cell 1 =====
# ── Cell 1: 로컬환경 안내 / Colab 코드 제거됨 ─────────────────────
# 삭제한 Colab 전용 코드:
# 1) from google.colab import drive
# 2) drive.mount('/content/drive')
# 3) !pip uninstall ...
# 4) !pip install ...
# 5) !apt-get -qq install fonts-nanum
#
# VS Code 로컬에서는 아래 명령을 노트북 셀이 아니라 터미널에서 1번만 실행하세요.
# pip install "numpy<2" opencv-python mediapipe pillow matplotlib

import os
import sys
import platform

print("로컬 실행 환경 확인")
print("Python :", sys.version.split()[0])
print("OS     :", platform.platform())
print("CWD    :", os.getcwd())


# %%
# ===== Original notebook cell 2 =====
# ── Cell 2: 버전 확인 ─────────────────────────────────────────────
import numpy as np
import cv2
import mediapipe as mp
from PIL import Image

print('numpy    :', np.__version__)
print('cv2      :', cv2.__version__)
print('mediapipe:', mp.__version__)
print('Pillow   :', Image.__version__)


# %%
# ===== Original notebook cell 3 =====
# ── Cell 3: 로컬 경로 설정 + 촬영 방향 설정 ───────────────────────
import os
import glob

# 현재 deadlift_feedback_v1.py 파일이 있는 폴더 기준
# VS Code에서 실행해도 현재 파일 위치를 기준으로 경로를 잡습니다.
BASE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()

# ✅ 1. 여기서 운동 종류만 바꾸면 됨: 'squat', 'deadlift', 'bench'
EXERCISE = 'deadlift'  # squat_feedback_v5_UPGRADE에서 데드리프트용으로 고정

# 현재 프로젝트는 측면영상만 사용한다고 가정
VIDEO_VIEW_MODE = 'side'

# ✅ 2. 실제 파일명에 맞게 여기만 수정
USER_VIDEO_FILES = {
    'squat':    'squat_15.mp4',
    'deadlift': 'user_deadlift_01.mp4',  # 사용자 데드리프트 영상으로 교체
    'bench':    'bench_15.mp4',      # <<-- 벤치프레스 원본 파일명이 다르면 여기 수정
}

EXPERT_JSON_FILES = {
    'squat':    'expert_squat.json',
    'deadlift': 'expert_deadlift.json',
    'bench':    'expert_bench.json',
}

USER_VIDEO_PATH  = os.path.join(BASE, USER_VIDEO_FILES[EXERCISE])
EXPERT_JSON_PATH = os.path.join(BASE, EXPERT_JSON_FILES[EXERCISE])
MODEL_PATH       = os.path.join(BASE, 'pose_landmarker_lite.task')

# ✅ 3. 출력 폴더와 저장 파일명
OUTPUT_DIR = os.path.join(BASE, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_BASENAME = 'deadlift_v1_feedback_CLEAN.mp4'  # 요청한 결과 영상 파일명으로 고정
OUTPUT_PATH = os.path.join(OUTPUT_DIR, OUTPUT_BASENAME)

# 윈도우 한글 폰트. 다른 폰트를 쓰고 싶으면 여기 수정
FONT_PATH = 'C:/Windows/Fonts/malgun.ttf'

# 파일 존재 확인
for p, name in [
    (USER_VIDEO_PATH,  '사용자영상'),
    (EXPERT_JSON_PATH, '전문가JSON'),
    (MODEL_PATH,       'PoseLandmarker모델'),
]:
    ok = os.path.exists(p)
    print(f'{"OK" if ok else "없음"} | {name}: {p}')

if not os.path.exists(FONT_PATH):
    # 폰트가 없으면 이후 Cell 7의 영어 fallback이 동작함
    print(f'폰트 없음 | FONT_PATH: {FONT_PATH}')
else:
    print(f'OK | 폰트: {FONT_PATH}')

print(f'출력 저장 위치: {OUTPUT_PATH}')


# %%
# ===== Original notebook cell 4 =====
# ── Cell 4: rt / fo import (로컬 .py 파일) ──────────────────────
import sys
import importlib
import time
import math

if BASE not in sys.path:
    sys.path.insert(0, BASE)

import realtime_compare_side as rt
import feedback_overlay as fo

importlib.reload(rt)
importlib.reload(fo)

rt.EXERCISE         = EXERCISE
rt.EXPERT_JSON_PATH = EXPERT_JSON_PATH
rt.MODEL_PATH       = MODEL_PATH
rt.MIRROR_CAMERA    = False   # 저장 영상은 반전 없음

print('rt / fo import 완료')
print(f'  VISIBILITY_THRESHOLD = {rt.VISIBILITY_THRESHOLD}')
print(f'  WINDOW_SIZE          = {rt.WINDOW_SIZE}')
print(f'  EXPERT_ALPHA         = {rt.EXPERT_ALPHA}')


# %%
# ===== Original notebook cell 5 =====
# ── Cell 5: 문서 기준 공통지표 + fallback 기본지표 계산 함수 ───────
# 반영 기준:
# - 3대운동 공통지표.pdf
# - 종목별_threshold값.pdf
#
# 이름 원칙:
# - 문서명 기준
# - 띄어쓰기는 '_'로 변환
# - 예: foot width → foot_width
# - 기존 Gemini식 이름인 wrist_elbow_x_ratio, body_line_ratio는 사용하지 않고
#   문서 기준 wrist_elbow_x_diff, bench_line_diff를 사용

import math
import numpy as np

VIS_THR = getattr(rt, 'VISIBILITY_THRESHOLD', 0.4)


def get_xyv(lms, idx):
    """
    user lms(MediaPipe 객체 list) 또는 expert lms_raw(JSON list [[x,y,z,vis],...]) 양쪽 처리.
    반환: (np.array([x,y]), visibility)
    """
    p = lms[idx]
    if hasattr(p, 'x'):
        return (
            np.array([float(p.x), float(p.y)], dtype=np.float32),
            float(getattr(p, 'visibility', 1.0))
        )

    x, y = float(p[0]), float(p[1])
    v    = float(p[3]) if len(p) > 3 else 1.0
    return np.array([x, y], dtype=np.float32), v


def midp(lms, a, b):
    """두 landmark 중점. 한쪽 visibility가 낮으면 더 잘 보이는 점 사용."""
    pa, va = get_xyv(lms, a)
    pb, vb = get_xyv(lms, b)

    if va >= VIS_THR and vb >= VIS_THR:
        return (pa + pb) / 2.0
    return pa if va >= vb else pb


def dist2d(a, b):
    return float(np.linalg.norm(a - b))


def angle_abc(a, b, c):
    """세 점 A-B-C가 만드는 각도. B가 꼭짓점."""
    ba = a - b
    bc = c - b
    n = np.linalg.norm(ba) * np.linalg.norm(bc)

    if n < 1e-9:
        return 0.0

    cosv = float(np.dot(ba, bc) / n)
    cosv = float(np.clip(cosv, -1.0, 1.0))
    return float(math.degrees(math.acos(cosv)))


def angle_to_vertical(a, b):
    """
    b -> a 벡터와 수직축 사이 각도.
    0도 = 수직에 가까움, 90도 = 수평에 가까움.
    """
    dx = float(a[0] - b[0])
    dy = float(a[1] - b[1])
    return abs(math.degrees(math.atan2(abs(dx), abs(dy) + 1e-9)))


def _vis_sum(lms, ids):
    total = 0.0
    for i in ids:
        try:
            _, v = get_xyv(lms, i)
            total += float(v)
        except Exception:
            pass
    return total


def _pick_visible_side(lms):
    """
    측면 영상에서는 한쪽 관절이 더 잘 잡히는 경우가 많으므로
    hip-knee-ankle visibility 합이 큰 쪽을 대표 side로 사용.
    """
    left_score  = _vis_sum(lms, [11, 13, 15, 23, 25, 27, 31])
    right_score = _vis_sum(lms, [12, 14, 16, 24, 26, 28, 32])

    if right_score > left_score:
        return {
            'shoulder': 12, 'elbow': 14, 'wrist': 16,
            'hip': 24, 'knee': 26, 'ankle': 28, 'foot': 32
        }

    return {
        'shoulder': 11, 'elbow': 13, 'wrist': 15,
        'hip': 23, 'knee': 25, 'ankle': 27, 'foot': 31
    }


def compute_base_sideview_metrics_local(lms, exercise='squat'):
    """
    rt.compute_sideview_metrics가 없거나 실패할 때 쓰는 fallback.
    측면영상에서 3대운동 공통 판단에 필요한 기본 각도/정렬 지표를 직접 계산한다.
    """
    side = _pick_visible_side(lms)

    sh, _ = get_xyv(lms, side['shoulder'])
    el, _ = get_xyv(lms, side['elbow'])
    wr, _ = get_xyv(lms, side['wrist'])
    hp, _ = get_xyv(lms, side['hip'])
    kn, _ = get_xyv(lms, side['knee'])
    an, _ = get_xyv(lms, side['ankle'])
    ft, _ = get_xyv(lms, side['foot'])

    shoulder_c = midp(lms, 11, 12)
    hip_c      = midp(lms, 23, 24)
    torso_len  = max(dist2d(shoulder_c, hip_c), 1e-6)

    knee_angle  = angle_abc(hp, kn, an)
    hip_angle   = angle_abc(sh, hp, kn)
    ankle_angle = angle_abc(kn, an, ft)
    elbow_angle = angle_abc(sh, el, wr)

    trunk_lean  = angle_to_vertical(shoulder_c, hip_c)
    spine_lean  = trunk_lean

    # 기존 코드 호환용 보조 지표
    hip_knee_angle = angle_to_vertical(kn, hip_c)

    # 문서 기준 벤치 핵심 지표
    wrist_elbow_x_diff = abs(float(wr[0] - el[0])) / torso_len

    # lockout_angle_min은 threshold 이름이지만, 코드에서는 현재 팔꿈치각 값을 넣고
    # Cell 7.5에서 165도 미만인지 절대조건으로 판단한다.
    lockout_angle_min = float(elbow_angle)

    # elbow_above_shoulder: 화면 좌표계에서는 y가 작을수록 위쪽.
    elbow_above_shoulder = 1.0 if float(el[1]) < float(sh[1]) else 0.0

    return {
        'knee_angle':             float(knee_angle),
        'hip_angle':              float(hip_angle),
        'ankle_angle':            float(ankle_angle),
        'elbow_angle':            float(elbow_angle),
        'spine_lean':             float(spine_lean),
        'trunk_lean':             float(trunk_lean),
        'hip_knee_angle':         float(hip_knee_angle),

        # 문서 기준 벤치 지표
        'wrist_elbow_x_diff':     float(wrist_elbow_x_diff),
        'lockout_angle_min':      float(lockout_angle_min),
        'elbow_above_shoulder':   float(elbow_above_shoulder),
    }


def compute_common_metrics(lms, exercise='squat'):
    """
    문서 기준 공통지표 계산.
    모든 값은 2D normalized coordinate 기반 proxy.
    """
    nose,   _  = get_xyv(lms, 0)
    l_sh,   _  = get_xyv(lms, 11); r_sh,  _  = get_xyv(lms, 12)
    l_el,   _  = get_xyv(lms, 13); r_el,  _  = get_xyv(lms, 14)
    l_wr,   _  = get_xyv(lms, 15); r_wr,  _  = get_xyv(lms, 16)
    l_an,   _  = get_xyv(lms, 27); r_an,  _  = get_xyv(lms, 28)
    l_heel, _  = get_xyv(lms, 29); r_heel,_  = get_xyv(lms, 30)
    l_foot, _  = get_xyv(lms, 31); r_foot,_  = get_xyv(lms, 32)

    shoulder_c = midp(lms, 11, 12)
    hip_c      = midp(lms, 23, 24)
    torso_len  = max(dist2d(shoulder_c, hip_c), 1e-6)

    left_foot_center  = (l_heel + l_foot) / 2.0
    right_foot_center = (r_heel + r_foot) / 2.0
    wrist_c           = (l_wr + r_wr) / 2.0

    # 1. 발 너비 / 발 방향
    foot_width             = dist2d(l_an, r_an) / torso_len
    foot_x_asymmetry       = abs(float(l_an[0] - r_an[0])) / torso_len
    foot_foreaft_asymmetry = abs(float(left_foot_center[0] - right_foot_center[0])) / torso_len

    # 벤치 문서명: foot_offset
    foot_offset = abs(float(l_an[0] - r_an[0])) / torso_len

    # 2. 발바닥 밀착
    left_foot_flatness     = abs(float(l_heel[1] - l_foot[1])) / torso_len
    right_foot_flatness    = abs(float(r_heel[1] - r_foot[1])) / torso_len
    foot_flatness          = max(left_foot_flatness, right_foot_flatness)

    # 3. 손/어깨 비대칭
    hand_width           = dist2d(l_wr, r_wr) / torso_len
    hand_height_diff     = abs(float(l_wr[1] - r_wr[1])) / torso_len
    shoulder_height_diff = abs(float(l_sh[1] - r_sh[1])) / torso_len

    # 4. 머리-어깨-엉덩이 정렬
    # 스쿼트/데드: x좌표 정렬, 벤치: y좌표 정렬
    if exercise in ('squat', 'deadlift'):
        xs = [float(nose[0]), float(shoulder_c[0]), float(hip_c[0])]
        head_hip_line = (max(xs) - min(xs)) / torso_len
        bench_line_diff = head_hip_line
    else:
        ys = [float(nose[1]), float(shoulder_c[1]), float(hip_c[1])]
        head_hip_line = (max(ys) - min(ys)) / torso_len
        bench_line_diff = head_hip_line

    # 5. 목-머리각 / 손목-어깨 높이
    neck_lean             = angle_to_vertical(nose, shoulder_c)
    wrist_shoulder_y_diff = (float(wrist_c[1]) - float(shoulder_c[1])) / torso_len

    # 6. 팔꿈치각
    left_elbow_angle      = angle_abc(l_sh, l_el, l_wr)
    right_elbow_angle     = angle_abc(r_sh, r_el, r_wr)
    elbow_angle_avg       = (left_elbow_angle + right_elbow_angle) / 2.0

    # 7. 몸통 기울기
    trunk_lean = angle_to_vertical(shoulder_c, hip_c)

    return {
        'foot_width':              float(foot_width),
        'foot_x_asymmetry':        float(foot_x_asymmetry),
        'foot_foreaft_asymmetry':  float(foot_foreaft_asymmetry),
        'foot_offset':             float(foot_offset),

        'foot_flatness':           float(foot_flatness),
        'left_foot_flatness':      float(left_foot_flatness),
        'right_foot_flatness':     float(right_foot_flatness),

        'hand_width':              float(hand_width),
        'hand_height_diff':        float(hand_height_diff),
        'shoulder_height_diff':    float(shoulder_height_diff),

        'head_hip_line':           float(head_hip_line),
        'bench_line_diff':         float(bench_line_diff),

        'neck_lean':               float(neck_lean),
        'wrist_shoulder_y_diff':   float(wrist_shoulder_y_diff),
        'elbow_angle_avg':         float(elbow_angle_avg),
        'trunk_lean':              float(trunk_lean),
    }


def _call_rt_compute_sideview_metrics(lms, exercise='squat'):
    """
    rt.compute_sideview_metrics가 있으면 사용하되,
    없거나 signature가 달라도 notebook이 멈추지 않도록 처리.
    """
    fn = getattr(rt, 'compute_sideview_metrics', None)

    if not callable(fn):
        return {}

    for args in [(lms, exercise), (lms,)]:
        try:
            out = fn(*args)
            return dict(out) if isinstance(out, dict) else {}
        except TypeError:
            continue
        except Exception as e:
            print(f'[경고] rt.compute_sideview_metrics 실패 → fallback 사용: {e}')
            return {}

    return {}


def compute_user_metrics_plus(lms, exercise='squat'):
    """기존 rt 지표 + fallback 기본지표 + 문서 기준 공통지표 합산."""
    local_base = compute_base_sideview_metrics_local(lms, exercise)
    rt_base    = _call_rt_compute_sideview_metrics(lms, exercise)
    common     = compute_common_metrics(lms, exercise)

    merged = {}
    merged.update(local_base)
    merged.update(rt_base)
    merged.update(common)
    return merged


def compute_expert_metrics_plus(ex_lms_raw, ex_metrics_json=None, exercise='squat'):
    """전문가 JSON 지표 + fallback 기본지표 + 문서 기준 공통지표 합산."""
    local_base = compute_base_sideview_metrics_local(ex_lms_raw, exercise)
    common     = compute_common_metrics(ex_lms_raw, exercise)

    json_base = {}
    if isinstance(ex_metrics_json, dict):
        json_base = dict(ex_metrics_json)

    merged = {}
    merged.update(local_base)
    merged.update(json_base)
    merged.update(common)
    return merged


print('문서 기준 공통지표 + fallback 기본지표 계산 함수 로드 완료')


# %%
# ===== Original notebook cell 6 =====
# ── Cell 6: 문서 기준 지표/threshold/landmark 설정 ───────────────
# rt 모듈의 EXERCISE_METRICS / DELTA_THRESHOLDS / DELTA_TO_LM /
# DISPLAY_LABELS / METRIC_LABELS 를 문서 기준 이름으로 확장.
#
# 주의:
# - 계산 자체는 가능한 공통지표를 모두 반영.
# - 현재는 측면영상만 사용하므로 오류판정 활성 지표는 SIDE_RELIABLE_METRICS만 사용.
# - foot_width, hand_width처럼 측면에서 불안정한 지표는 계산은 되지만 핵심 오류판정에서는 제외.

if not hasattr(rt, 'DELTA_THRESHOLDS'):
    rt.DELTA_THRESHOLDS = {}
if not hasattr(rt, 'DELTA_TO_LM'):
    rt.DELTA_TO_LM = {}
if not hasattr(rt, 'DISPLAY_LABELS'):
    rt.DISPLAY_LABELS = {}
if not hasattr(rt, 'METRIC_LABELS'):
    rt.METRIC_LABELS = {}
if not hasattr(rt, 'EXERCISE_METRICS'):
    rt.EXERCISE_METRICS = {'squat': [], 'deadlift': [], 'bench': []}
if not hasattr(rt, 'ABSOLUTE_THRESHOLDS'):
    rt.ABSOLUTE_THRESHOLDS = {}

print("구버전 realtime_compare_side.py 보정 완료")

# 문서 기준으로 계산 가능한 전체 지표 목록
DOCUMENT_METRICS_ALL = {
    'squat': [
        'knee_angle', 'hip_angle', 'trunk_lean',
        'foot_width', 'foot_x_asymmetry', 'foot_foreaft_asymmetry',
        'foot_flatness', 'left_foot_flatness', 'right_foot_flatness',
        'hand_width', 'hand_height_diff', 'shoulder_height_diff',
        'head_hip_line', 'neck_lean', 'wrist_shoulder_y_diff',
        'elbow_angle_avg',
    ],
    'deadlift': [
        'knee_angle', 'hip_angle', 'trunk_lean',
        'foot_width', 'foot_x_asymmetry', 'foot_foreaft_asymmetry',
        'foot_flatness', 'left_foot_flatness', 'right_foot_flatness',
        'hand_width', 'hand_height_diff', 'shoulder_height_diff',
        'head_hip_line', 'neck_lean', 'wrist_shoulder_y_diff',
        'elbow_angle_avg',
    ],
    'bench': [
        'elbow_angle', 'elbow_angle_avg', 'wrist_elbow_x_diff',
        'lockout_angle_min', 'elbow_above_shoulder',
        'bench_line_diff', 'foot_offset', 'foot_flatness',
        'left_foot_flatness', 'right_foot_flatness',
        'hand_width', 'hand_height_diff', 'shoulder_height_diff',
        'head_hip_line', 'neck_lean', 'wrist_shoulder_y_diff',
        'knee_angle',
    ],
}

# 측면영상 기준 실제 오류판정에 사용할 지표
SIDE_RELIABLE_METRICS = {
    'squat': [
        'knee_angle', 'hip_angle', 'trunk_lean',
        'foot_flatness', 'left_foot_flatness', 'right_foot_flatness',
        'foot_foreaft_asymmetry', 'head_hip_line', 'neck_lean',
    ],
    'deadlift': [
        # 데드리프트 측면영상에서는 발바닥 밀착/발 전후차가 오탐을 많이 만들고
        # USER 화면과 HUD를 지저분하게 만들 수 있어 핵심 판정에서 제외한다.
        'knee_angle', 'hip_angle', 'trunk_lean',
        'head_hip_line', 'neck_lean', 'elbow_angle_avg',
    ],
    'bench': [
        'elbow_angle', 'elbow_angle_avg', 'wrist_elbow_x_diff',
        'lockout_angle_min', 'elbow_above_shoulder',
        'bench_line_diff', 'foot_offset', 'foot_flatness',
    ],
}

# 전체 목록은 보관
rt.DOCUMENT_METRICS_ALL = DOCUMENT_METRICS_ALL

# 현재는 측면영상만 사용
rt.EXERCISE_METRICS[EXERCISE] = SIDE_RELIABLE_METRICS.get(EXERCISE, SIDE_RELIABLE_METRICS['squat'])

# 종목별 delta threshold
EXERCISE_DELTA_THRESHOLDS = {
    'squat': {
        'knee_angle': 12.0,
        'hip_angle': 12.0,
        'trunk_lean': 8.0,

        'foot_width': 0.10,
        'foot_x_asymmetry': 0.08,
        'foot_foreaft_asymmetry': 0.08,
        'foot_flatness': 0.04,
        'left_foot_flatness': 0.04,
        'right_foot_flatness': 0.04,

        'hand_width': 0.15,
        'hand_height_diff': 0.07,
        'shoulder_height_diff': 0.05,
        'head_hip_line': 0.10,
        'neck_lean': 10.0,
        'wrist_shoulder_y_diff': 0.15,
        'elbow_angle_avg': 12.0,
    },
    'deadlift': {
        'knee_angle': 12.0,
        'hip_angle': 12.0,
        'trunk_lean': 8.0,

        'foot_width': 0.10,
        'foot_x_asymmetry': 0.08,
        'foot_foreaft_asymmetry': 0.08,
        'foot_flatness': 0.04,
        'left_foot_flatness': 0.04,
        'right_foot_flatness': 0.04,

        'hand_width': 0.12,
        'hand_height_diff': 0.07,
        'shoulder_height_diff': 0.05,
        'head_hip_line': 0.10,
        'neck_lean': 10.0,
        'wrist_shoulder_y_diff': 0.15,
        'elbow_angle_avg': 12.0,
    },
    'bench': {
        'elbow_angle': 12.0,
        'elbow_angle_avg': 12.0,
        'wrist_elbow_x_diff': 0.08,

        'hand_height_diff': 0.08,
        'shoulder_height_diff': 0.07,
        'bench_line_diff': 0.08,
        'foot_offset': 0.10,
        'foot_flatness': 0.04,
        'left_foot_flatness': 0.04,
        'right_foot_flatness': 0.04,
    },
}

rt.DELTA_THRESHOLDS.update(EXERCISE_DELTA_THRESHOLDS.get(EXERCISE, {}))

# 절대조건 threshold
# lockout_angle_min: 현재 팔꿈치각이 165도 미만이면 락아웃 부족
# elbow_above_shoulder: 1.0이면 팔꿈치가 어깨보다 위로 올라간 상태
rt.ABSOLUTE_THRESHOLDS.update({
    'lockout_angle_min': 165.0,
    'elbow_above_shoulder': 0.0,
})

# 관련 landmark 인덱스
rt.DELTA_TO_LM.update({
    'knee_angle':              [23, 24, 25, 26, 27, 28],
    'hip_angle':               [11, 12, 23, 24, 25, 26],
    'trunk_lean':              [11, 12, 23, 24],

    'foot_width':              [27, 28],
    'foot_x_asymmetry':        [27, 28],
    'foot_foreaft_asymmetry':  [27, 28, 29, 30, 31, 32],
    'foot_offset':             [27, 28],
    'foot_flatness':           [29, 30, 31, 32],
    'left_foot_flatness':      [29, 31],
    'right_foot_flatness':     [30, 32],

    'hand_width':              [15, 16],
    'hand_height_diff':        [15, 16],
    'shoulder_height_diff':    [11, 12],
    'head_hip_line':           [0, 11, 12, 23, 24],
    'bench_line_diff':         [0, 11, 12, 23, 24],

    'neck_lean':               [0, 11, 12],
    'wrist_shoulder_y_diff':   [11, 12, 15, 16],

    'elbow_angle':             [11, 12, 13, 14, 15, 16],
    'elbow_angle_avg':         [11, 12, 13, 14, 15, 16],
    'wrist_elbow_x_diff':      [13, 14, 15, 16],
    'lockout_angle_min':       [11, 12, 13, 14, 15, 16],
    'elbow_above_shoulder':    [11, 12, 13, 14],
})

DISPLAY_LABELS_KR = {
    'knee_angle':              '무릎각',
    'hip_angle':               '엉덩이각',
    'trunk_lean':              '몸통기울기',

    'foot_width':              '발너비',
    'foot_x_asymmetry':        '발목X차',
    'foot_foreaft_asymmetry':  '발위치전후차',
    'foot_offset':             '양발앞뒤위치차',
    'foot_flatness':           '발바닥밀착',
    'left_foot_flatness':      '왼발밀착',
    'right_foot_flatness':     '오른발밀착',

    'hand_width':              '양손거리',
    'hand_height_diff':        '양손높이차',
    'shoulder_height_diff':    '어깨높이차',
    'head_hip_line':           '머리-어깨-엉덩이정렬',
    'bench_line_diff':         '벤치라인이탈',

    'neck_lean':               '목머리각',
    'wrist_shoulder_y_diff':   '손목어깨높이',

    'elbow_angle':             '팔꿈치각',
    'elbow_angle_avg':         '평균팔꿈치각',
    'wrist_elbow_x_diff':      '손목팔꿈치수직정렬차이',
    'lockout_angle_min':       '팔꿈치락아웃부족',
    'elbow_above_shoulder':    '팔꿈치어깨보다높음',
}

rt.DISPLAY_LABELS.update(DISPLAY_LABELS_KR)
rt.METRIC_LABELS.update(rt.DISPLAY_LABELS)

print('문서 기준 지표 설정 완료')
print('계산 가능한 문서 지표:', rt.DOCUMENT_METRICS_ALL.get(EXERCISE, []))
print('측면영상 오류판정 활성 지표:', rt.EXERCISE_METRICS.get(EXERCISE, []))
print('현재 종목 threshold:', EXERCISE_DELTA_THRESHOLDS.get(EXERCISE, {}))


# %%
# ===== Original notebook cell 7 =====
# ── Cell 7: 시각화 헬퍼 v4 ───────────────────────────────────────
# 목표:
# 1) 몸통 기울기 텍스트를 사람 몸 위에 작게 쓰지 않고, HUD에서 크게 설명
# 2) 한글 폰트가 없으면 네모(□□□)로 깨지지 않도록 영어 fallback 사용
# 3) 측면영상에서는 발너비를 오류판정/표시에서 제외
# 4) 기존 레이어와 새 레이어가 겹쳐서 지저분해지는 문제 완화

from PIL import Image as PilImage, ImageDraw, ImageFont
import glob
import os
import textwrap

# Skeleton 연결 정의
SKEL_CONNS = [
    (0,11),(0,12),(11,12),
    (11,13),(13,15),(12,14),(14,16),
    (11,23),(12,24),(23,24),
    (23,25),(25,27),(24,26),(26,28),
    (27,29),(29,31),(28,30),(30,32),
]

# 색상 팔레트 (BGR)
C_EXP_BONE  = (80, 220, 120)
C_EXP_JOINT = (180, 255, 180)
C_BRACKET   = (0, 215, 255)
C_TRUNK_OK  = (80, 220, 100)
C_TRUNK_ERR = (60, 60, 255)
C_TRUNK_REF = (170, 170, 170)
C_ERR_CIR   = (0, 0, 255)

# ✅ 몸통 기울기 허용 오차
TRUNK_LEAN_TOL_DEG = 8.0

# 발너비 브라켓 표시 대상 뷰
FOOT_BRACKET_VIEW_MODES = {'front', '45deg', '45', 'diagonal', 'oblique', '정면', '45도', '사선'}


# ────────────────────────────────────────────────────────────────
# [한글 폰트 탐색]
# ────────────────────────────────────────────────────────────────
def find_korean_font():
    candidates = []

    # Cell 3에서 FONT_PATH를 지정했다면 먼저 확인
    try:
        if FONT_PATH:
            candidates.append(FONT_PATH)
    except NameError:
        pass

    # Colab / Ubuntu에서 자주 쓰는 경로들
    candidates += [
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    ]

    # 혹시 경로가 달라도 찾기
    patterns = [
        '/usr/share/fonts/**/*Nanum*.ttf',
        '/usr/share/fonts/**/*NotoSansCJK*.ttc',
        '/content/**/*Nanum*.ttf',
        '/content/**/*NotoSansCJK*.ttc',
    ]
    for pat in patterns:
        candidates.extend(glob.glob(pat, recursive=True))

    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


KOREAN_FONT_PATH = find_korean_font()
FONT_KR_OK = KOREAN_FONT_PATH is not None

def _fnt(size):
    try:
        if FONT_KR_OK:
            return ImageFont.truetype(KOREAN_FONT_PATH, size)
    except Exception:
        pass
    return ImageFont.load_default()

def _ko(kr, en):
    """한글 폰트가 없으면 영어로 표시해서 네모 깨짐을 방지."""
    return kr if FONT_KR_OK else en


def draw_text_box_bgr(frame, lines, xy=(16, 16), font_size=20,
                      fg=(255,255,255), bg=(20,20,30), pad=8,
                      alpha=0.72):
    """
    BGR frame 위에 PIL로 읽기 쉬운 박스형 텍스트를 그림.
    lines: str 또는 list[str]
    fg/bg: RGB 기준
    """
    if isinstance(lines, str):
        lines = [lines]

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    base = PilImage.fromarray(rgb).convert('RGBA')
    overlay = PilImage.new('RGBA', base.size, (0,0,0,0))
    drw = ImageDraw.Draw(overlay)

    font = _fnt(font_size)
    line_h = font_size + 6
    widths = []
    for line in lines:
        try:
            bbox = drw.textbbox((0,0), line, font=font)
            widths.append(bbox[2] - bbox[0])
        except Exception:
            widths.append(len(line) * font_size * 0.6)

    box_w = int(max(widths) + pad*2)
    box_h = int(len(lines)*line_h + pad*2)
    x, y = xy
    x = max(0, min(int(x), frame.shape[1] - box_w - 2))
    y = max(0, min(int(y), frame.shape[0] - box_h - 2))

    bg_rgba = (bg[0], bg[1], bg[2], int(255*alpha))
    try:
        drw.rounded_rectangle([x, y, x+box_w, y+box_h], radius=10, fill=bg_rgba)
    except Exception:
        drw.rectangle([x, y, x+box_w, y+box_h], fill=bg_rgba)

    for i, line in enumerate(lines):
        drw.text((x+pad, y+pad+i*line_h), line, font=font, fill=fg+(255,))

    composed = PilImage.alpha_composite(base, overlay).convert('RGB')
    return cv2.cvtColor(np.array(composed), cv2.COLOR_RGB2BGR)


# ────────────────────────────────────────────────────────────────
# [전문가 skeleton -> 별도 canvas]
# ────────────────────────────────────────────────────────────────
def draw_expert_on_canvas(canvas_w, canvas_h, ex_lms_raw, bad_indices=None):
    if bad_indices is None:
        bad_indices = set()

    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

    if ex_lms_raw is None or len(ex_lms_raw) < 33:
        cv2.putText(canvas, 'NO EXPERT DATA',
                    (canvas_w//2-80, canvas_h//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80,80,80), 2)
        return canvas

    def to_px(idx):
        p = ex_lms_raw[idx]
        if hasattr(p, 'x'):
            x, y, v = float(p.x), float(p.y), float(getattr(p, 'visibility', 1.0))
        else:
            x, y = float(p[0]), float(p[1])
            v = float(p[3]) if len(p) > 3 else 1.0
        return (int(x * canvas_w), int(y * canvas_h)), v

    for (a, b) in SKEL_CONNS:
        pa, va = to_px(a)
        pb, vb = to_px(b)
        if va < VIS_THR or vb < VIS_THR:
            continue
        cv2.line(canvas, pa, pb, C_EXP_BONE, 2, cv2.LINE_AA)

    for idx in range(33):
        pt, v = to_px(idx)
        if v < VIS_THR:
            continue
        is_bad = idx in bad_indices
        r  = 6 if is_bad else 4
        c  = C_ERR_CIR if is_bad else C_EXP_JOINT
        cv2.circle(canvas, pt, r, c, -1, cv2.LINE_AA)
        if is_bad:
            cv2.circle(canvas, pt, r + 5, C_ERR_CIR, 2, cv2.LINE_AA)

    cv2.putText(canvas, 'EXPERT', (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, C_EXP_BONE, 2, cv2.LINE_AA)
    return canvas


# ── 발너비 bracket 표시 여부 판단 ────────────────────────────────
def infer_view_mode_from_pose(lms):
    """양발목 x거리/torso 비율로 정면/측면을 아주 거칠게 추정."""
    try:
        la, va = get_xyv(lms, 27)
        ra, vr = get_xyv(lms, 28)
        sc = midp(lms, 11, 12)
        hc = midp(lms, 23, 24)
        torso = max(dist2d(sc, hc), 1e-6)
        foot_x_gap = abs(float(la[0] - ra[0])) / torso
        if foot_x_gap > 0.45:
            return 'front'
        if foot_x_gap > 0.22:
            return '45deg'
        return 'side'
    except Exception:
        return 'side'


def should_draw_foot_bracket(lms=None, view_mode=None):
    vm = str(view_mode or globals().get('VIDEO_VIEW_MODE', 'side')).lower()
    if vm == 'auto':
        vm = infer_view_mode_from_pose(lms) if lms is not None else 'side'
    return vm in FOOT_BRACKET_VIEW_MODES


# ── 발너비 bracket 시각화 ────────────────────────────────────────
def draw_foot_bracket(frame, lms, metrics, view_mode=None):
    """
    정면/45도에서만 양발목 아래에 bracket 표시.
    측면영상에서는 발이 겹쳐 보이기 때문에 표시하지 않는다.
    """
    if not should_draw_foot_bracket(lms, view_mode=view_mode):
        return frame

    H, W = frame.shape[:2]
    la, va = get_xyv(lms, 27)
    ra, vr = get_xyv(lms, 28)
    if va < VIS_THR or vr < VIS_THR:
        return frame

    lx = int(la[0] * W);  ly = int(la[1] * H)
    rx = int(ra[0] * W);  ry = int(ra[1] * H)
    y   = min(H - 16, max(ly, ry) + 20)
    lx2 = min(lx, rx);  rx2 = max(lx, rx)

    if rx2 - lx2 < 12:
        return frame

    h = 8
    cv2.line(frame, (lx2, y),   (rx2, y),   C_BRACKET, 3)
    cv2.line(frame, (lx2, y-h), (lx2, y+h), C_BRACKET, 3)
    cv2.line(frame, (rx2, y-h), (rx2, y+h), C_BRACKET, 3)
    cv2.arrowedLine(frame, (lx2+18, y), (lx2, y), C_BRACKET, 2, tipLength=0.35)
    cv2.arrowedLine(frame, (rx2-18, y), (rx2, y), C_BRACKET, 2, tipLength=0.35)

    fw = metrics.get('foot_width')
    txt = _ko(f'발너비 {fw:.2f}' if fw is not None else '발너비',
              f'Foot width {fw:.2f}' if fw is not None else 'Foot width')
    frame = draw_text_box_bgr(frame, txt, (max(5, (lx2+rx2)//2 - 70), max(16, y - 50)),
                              font_size=16, fg=(255,230,80), bg=(10,10,20), alpha=0.65)
    return frame


# ── 몸통 기울기 부족/과도 판정 ───────────────────────────────────
def evaluate_trunk_lean_issue(user_metrics, expert_metrics=None, tol_deg=None):
    tol = float(tol_deg if tol_deg is not None else TRUNK_LEAN_TOL_DEG)
    u = user_metrics.get('trunk_lean') if isinstance(user_metrics, dict) else None
    e = expert_metrics.get('trunk_lean') if isinstance(expert_metrics, dict) else None

    if u is None or not np.isfinite(u):
        return None

    if e is None or not np.isfinite(e):
        lo, hi = 5.0, 35.0
        if u < lo:
            return {'key': 'trunk_lean', 'message': _ko('몸통 기울기 부족', 'Trunk lean too small'), 'landmarks': [11,12,23,24], 'delta': u - lo}
        if u > hi:
            return {'key': 'trunk_lean', 'message': _ko('몸통 기울기 과도', 'Trunk lean too large'), 'landmarks': [11,12,23,24], 'delta': u - hi}
        return None

    diff = float(u) - float(e)
    if diff > tol:
        return {'key': 'trunk_lean', 'message': _ko('몸통 기울기 과도', 'Trunk lean too large'), 'landmarks': [11,12,23,24], 'delta': diff}
    if diff < -tol:
        return {'key': 'trunk_lean', 'message': _ko('몸통 기울기 부족', 'Trunk lean too small'), 'landmarks': [11,12,23,24], 'delta': diff}
    return None


def trunk_status_text(user_metrics, expert_metrics=None, tol_deg=None):
    u = user_metrics.get('trunk_lean') if isinstance(user_metrics, dict) else None
    e = expert_metrics.get('trunk_lean') if isinstance(expert_metrics, dict) else None
    tol = float(tol_deg if tol_deg is not None else TRUNK_LEAN_TOL_DEG)

    if u is None or not np.isfinite(u):
        return _ko('몸통: 측정불가', 'Trunk: N/A'), (150,150,150), None, e

    issue = evaluate_trunk_lean_issue(user_metrics, expert_metrics, tol)
    if issue is None:
        return _ko('몸통: 정상 범위', 'Trunk: OK'), (80,220,100), u, e
    return issue['message'], (80,80,255), u, e


def _point_from_vertical_angle(origin_px, length_px, angle_deg, sign):
    theta = math.radians(float(angle_deg))
    dx = sign * math.sin(theta) * length_px
    dy = -math.cos(theta) * length_px
    return (int(origin_px[0] + dx), int(origin_px[1] + dy))


# ── 몸통 기울기 zone 시각화 ──────────────────────────────────────
def draw_trunk_lean_zone(frame, lms, user_metrics, expert_metrics=None, bad_indices=None, tol_deg=None):
    """
    사람 몸 위에는 숫자 텍스트를 쓰지 않는다.
    - 초록/빨강 zone + 현재 몸통선만 표시
    - 자세한 숫자 설명은 오른쪽 HUD에서 크게 표시
    """
    if bad_indices is None:
        bad_indices = set()

    H, W = frame.shape[:2]
    sc_n = midp(lms, 11, 12)
    hc_n = midp(lms, 23, 24)
    sc   = (int(sc_n[0]*W), int(sc_n[1]*H))
    hc   = (int(hc_n[0]*W), int(hc_n[1]*H))

    torso_px = max(int(math.sqrt((sc[0]-hc[0])**2 + (sc[1]-hc[1])**2)), 40)
    guide_len = int(torso_px * 1.35)

    u = user_metrics.get('trunk_lean') if isinstance(user_metrics, dict) else None
    e = expert_metrics.get('trunk_lean') if isinstance(expert_metrics, dict) else None
    if u is None or not np.isfinite(u):
        return frame
    if e is None or not np.isfinite(e):
        e = u

    tol = float(tol_deg if tol_deg is not None else TRUNK_LEAN_TOL_DEG)
    lo  = max(0.0, float(e) - tol)
    hi  = min(85.0, float(e) + tol)

    issue = evaluate_trunk_lean_issue(user_metrics, expert_metrics, tol)
    is_bad = issue is not None
    color = C_TRUNK_ERR if is_bad else C_TRUNK_OK

    sign = 1 if (sc[0] - hc[0]) >= 0 else -1

    p_lo  = _point_from_vertical_angle(hc, guide_len, lo, sign)
    p_hi  = _point_from_vertical_angle(hc, guide_len, hi, sign)
    p_mid = _point_from_vertical_angle(hc, guide_len, float(e), sign)

    overlay = frame.copy()
    poly = np.array([hc, p_lo, p_hi], dtype=np.int32)
    cv2.fillPoly(overlay, [poly], color)
    frame = cv2.addWeighted(overlay, 0.14, frame, 0.86, 0)

    cv2.line(frame, hc, p_lo, color, 2, cv2.LINE_AA)
    cv2.line(frame, hc, p_hi, color, 2, cv2.LINE_AA)
    cv2.line(frame, hc, p_mid, C_TRUNK_REF, 1, cv2.LINE_AA)

    # 현재 사용자 몸통 중심선
    cv2.line(frame, hc, sc, color, 5, cv2.LINE_AA)
    cv2.circle(frame, hc, 6, color, -1, cv2.LINE_AA)
    cv2.circle(frame, sc, 6, color, -1, cv2.LINE_AA)
    return frame


# 이전 함수명 호환용 alias
def draw_trunk_lean_line(frame, lms, metrics, bad_indices=None):
    return draw_trunk_lean_zone(frame, lms, metrics, None, bad_indices)


# ── threshold 초과 관절에 빨간 원 ────────────────────────────────
def draw_issue_markers(frame, lms, deltas, max_items=3):
    """
    현재 view에서 실제 오류판정에 쓰는 지표만 표시한다.
    측면영상에서 foot_width 같은 정면용 지표가 빨간 원을 만드는 문제를 방지.
    """
    H, W = frame.shape[:2]
    active = set(rt.EXERCISE_METRICS.get(EXERCISE, []))

    items = sorted(
        [
            (abs(d) / max(rt.DELTA_THRESHOLDS.get(k, 999), 1e-6), k, d)
            for k, d in deltas.items()
            if k in active
        ],
        reverse=True
    )[:max_items]

    for ratio, key, delta in items:
        if ratio < 1.0:
            continue
        for idx in rt.DELTA_TO_LM.get(key, []):
            p = lms[idx]
            v = float(getattr(p, 'visibility', 1.0))
            if v < VIS_THR:
                continue
            cx = int(p.x * W)
            cy = int(p.y * H)
            cv2.circle(frame, (cx, cy), 13, C_ERR_CIR, 2, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy),  4, C_ERR_CIR, -1, cv2.LINE_AA)
    return frame


# ── 상단 피드백 배너 ─────────────────────────────────────────────
def draw_feedback_banner(frame, feedback_text, issue_key=None,
                         user_metrics=None, expert_metrics=None):
    if not feedback_text:
        feedback_text = _ko('정상 범위', 'OK')

    is_ok = any(w in str(feedback_text) for w in ['정상', 'OK', '좋', 'safe'])
    fg = (120, 245, 150) if is_ok else (255, 130, 130)

    # 몸통 상태는 HUD에서 충분히 설명하므로 배너는 한 줄만
    return draw_text_box_bgr(
        frame,
        str(feedback_text),
        xy=(16, 52),
        font_size=20,
        fg=fg,
        bg=(18, 18, 28),
        alpha=0.74
    )


# ── PIL 기반 HUD 패널 ────────────────────────────────────────────
HUD_METRICS_SIDE = [
    # (한글명, 영어명, metric key, unit)
    ('무릎각',        'Knee angle',      'knee_angle',     'deg'),
    ('엉덩이각',      'Hip angle',       'hip_angle',      'deg'),
    ('몸통기울기',    'Trunk lean',      'trunk_lean',     'deg'),
    ('머리-골반정렬', 'Head-hip line',   'head_hip_line',  ''),
    ('발바닥밀착',    'Foot flatness',   'foot_flatness',  ''),
]

HUD_METRICS_FRONT45 = HUD_METRICS_SIDE + [
    ('발너비',        'Foot width',      'foot_width',     ''),
    ('양손높이차',    'Hand height diff','hand_height_diff',''),
]

def _fmt_val(v, unit):
    if v is None or not isinstance(v, (int, float, np.floating)) or not np.isfinite(v):
        return 'N/A'
    return f'{float(v):.1f}°' if unit == 'deg' else f'{float(v):.2f}'


def make_hud_panel(panel_w, panel_h, user_metrics, deltas, count,
                   feedback_text, issue_key, fps, ex_idx, ex_total,
                   exercise='squat'):
    img  = PilImage.new('RGB', (panel_w, panel_h), (18, 18, 28))
    drw  = ImageDraw.Draw(img)

    fTITLE = _fnt(28)
    fBIG   = _fnt(24)
    fMD    = _fnt(17)
    fSM    = _fnt(14)

    y = 14
    EX = {'squat':'SQUAT','deadlift':'DEADLIFT','bench':'BENCH PRESS'}

    # 제목
    drw.text((14, y), EX.get(exercise, exercise.upper()), font=fTITLE, fill=(240, 205, 80))
    y += 42

    # 횟수
    drw.text((14, y), _ko('현재 횟수', 'Reps'), font=fMD, fill=(180,180,190))
    drw.text((panel_w-70, y-8), str(count), font=fTITLE, fill=(80, 220, 255))
    y += 42

    # 몸통 상태 요약
    trunk_msg, trunk_col_bgr, u_tr, e_tr = trunk_status_text(user_metrics, None, TRUNK_LEAN_TOL_DEG)
    # expert값은 deltas에서 복원
    if u_tr is None:
        u_tr = user_metrics.get('trunk_lean') if isinstance(user_metrics, dict) else None
    if u_tr is not None and 'trunk_lean' in deltas:
        e_tr = u_tr - deltas.get('trunk_lean', 0)

    trunk_col_rgb = (trunk_col_bgr[2], trunk_col_bgr[1], trunk_col_bgr[0])
    drw.rounded_rectangle([10, y, panel_w-10, y+68], radius=12,
                          fill=(34,34,48), outline=trunk_col_rgb, width=2)
    drw.text((22, y+8), trunk_msg, font=fBIG, fill=trunk_col_rgb)

    detail = f"U {_fmt_val(u_tr, 'deg')}  |  E {_fmt_val(e_tr, 'deg')}  |  ±{TRUNK_LEAN_TOL_DEG:.0f}°"
    drw.text((22, y+42), detail, font=fSM, fill=(205,205,215))
    y += 82

    # 진행 정보
    prog = _ko(f'전문가 프레임 {ex_idx+1}/{ex_total}   FPS {fps:.1f}',
               f'Expert {ex_idx+1}/{ex_total}   FPS {fps:.1f}')
    drw.text((14, y), prog, font=fSM, fill=(120,120,130))
    y += 25
    drw.line([(10,y),(panel_w-10,y)], fill=(60,60,80), width=1)
    y += 14

    # 지표 목록: 측면에서는 측면 신뢰 지표만 표시
    vm = str(globals().get('VIDEO_VIEW_MODE', 'side')).lower()
    metric_list = HUD_METRICS_FRONT45 if vm not in ['side', '측면'] else HUD_METRICS_SIDE
    active = set(rt.EXERCISE_METRICS.get(EXERCISE, []))

    for kr_label, en_label, key, unit in metric_list:
        if key not in active and key not in ['knee_angle', 'hip_angle', 'trunk_lean']:
            continue
        if y > panel_h - 125:
            break

        label = _ko(kr_label, en_label)
        val = user_metrics.get(key) if isinstance(user_metrics, dict) else None
        delta = deltas.get(key) if isinstance(deltas, dict) else None
        thr = rt.DELTA_THRESHOLDS.get(key)

        if val is not None and delta is not None:
            ex_val = val - delta
        else:
            ex_val = None

        bad = False
        if delta is not None and thr is not None:
            bad = abs(float(delta)) > float(thr)

        col = (255,130,130) if bad else (120,245,150)
        drw.text((14, y), label, font=fMD, fill=(225,225,230))
        drw.text((panel_w-100, y), _ko('주의', 'WARN') if bad else 'OK',
                 font=fMD, fill=col)

        y += 22
        val_line = f"U {_fmt_val(val, unit)}  /  E {_fmt_val(ex_val, unit)}"
        if delta is not None:
            val_line += f"  Δ {_fmt_val(delta, unit)}"
        drw.text((22, y), val_line, font=fSM, fill=(170,170,180))

        # delta 기준 bar
        y += 20
        if delta is not None and thr is not None and float(thr) > 0:
            bw = panel_w - 44
            ratio = min(abs(float(delta)) / float(thr), 1.5) / 1.5
            drw.rectangle([22, y, 22+bw, y+6], fill=(48,48,60))
            drw.rectangle([22, y, 22+int(bw*ratio), y+6], fill=col)
        y += 22

    # 하단 피드백
    drw.line([(10, panel_h-90),(panel_w-10, panel_h-90)], fill=(60,60,80), width=1)
    fb = feedback_text or _ko('정상 범위', 'OK')
    fb_col = (120,245,150) if any(w in str(fb) for w in ['정상','OK','좋','safe']) else (255,130,130)
    drw.text((14, panel_h-78), _ko('피드백', 'Feedback'), font=fMD, fill=(180,180,190))

    max_ch = max(1, (panel_w - 28) // (15 if FONT_KR_OK else 9))
    lines = textwrap.wrap(str(fb), width=max_ch)[:2]
    if not lines:
        lines = [str(fb)[:max_ch]]
    for i, line in enumerate(lines):
        drw.text((14, panel_h-52 + i*22), line, font=fMD, fill=fb_col)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


print('시각화 헬퍼 v4 로드 완료')
print(f'  VIDEO_VIEW_MODE = {globals().get("VIDEO_VIEW_MODE", "side")}')
print(f'  한글 폰트 = {KOREAN_FONT_PATH if FONT_KR_OK else "없음 → 영어 fallback"}')
print(f'  발너비 bracket 표시 모드 = {sorted(FOOT_BRACKET_VIEW_MODES)}')
print(f'  몸통기울기 허용오차 = ±{TRUNK_LEAN_TOL_DEG}도')


# %%
# ===== Original notebook cell 8 =====
# ── Cell 7.5: v5 업그레이드 오버라이드 / 3대운동 측면영상 ───────
# 목표:
# 1) 문서 기준 지표명 사용
# 2) squat / deadlift / bench별 phase, priority, HUD 목록 분리
# 3) delta 기준과 절대조건 기준을 분리
# 4) 피드백 안정화 유지

import textwrap
from collections import deque

# 측면영상에서 실제 핵심 오류 후보 우선순위
V5_PRIORITY_MAP = {
    'squat': [
        'trunk_lean', 'knee_angle', 'hip_angle',
        'foot_flatness', 'left_foot_flatness', 'right_foot_flatness',
        'foot_foreaft_asymmetry', 'head_hip_line', 'neck_lean',
    ],
    'deadlift': [
        # 데드리프트 v2: 핵심 피드백만 남겨 화면 복잡도 감소
        'trunk_lean', 'hip_angle', 'knee_angle',
        'head_hip_line', 'neck_lean', 'elbow_angle_avg',
    ],
    'bench': [
        'wrist_elbow_x_diff', 'elbow_angle', 'elbow_angle_avg',
        'lockout_angle_min', 'elbow_above_shoulder',
        'bench_line_diff', 'foot_flatness', 'foot_offset',
    ],
}
V5_PRIORITY_KEYS = V5_PRIORITY_MAP.get(EXERCISE, V5_PRIORITY_MAP['squat'])

V5_LABELS = {k: _ko(v, k) for k, v in {
    'trunk_lean': '몸통 기울기',
    'knee_angle': '무릎각',
    'hip_angle': '엉덩이각',
    'foot_flatness': '발바닥 밀착',
    'left_foot_flatness': '왼발 밀착',
    'right_foot_flatness': '오른발 밀착',
    'foot_foreaft_asymmetry': '발 위치 전후 차이',
    'head_hip_line': '머리-어깨-엉덩이 정렬',
    'neck_lean': '목-머리각',
    'elbow_angle': '팔꿈치각',
    'elbow_angle_avg': '평균 팔꿈치각',
    'wrist_elbow_x_diff': '손목-팔꿈치 수직 정렬',
    'lockout_angle_min': '팔꿈치 락아웃',
    'bench_line_diff': '벤치 라인',
    'foot_offset': '양발 앞뒤 위치',
    'elbow_above_shoulder': '팔꿈치-어깨 높이',
}.items()}


def _safe_float(x, default=None):
    try:
        x = float(x)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def phase_from_metrics(metrics):
    """3대운동 측면영상용 간단 phase 인식."""
    if not isinstance(metrics, dict):
        return _ko('구간 인식 중', 'Detecting phase')

    k = _safe_float(metrics.get('knee_angle'))
    h = _safe_float(metrics.get('hip_angle'))
    e = _safe_float(metrics.get('elbow_angle'))
    ea = _safe_float(metrics.get('elbow_angle_avg'))
    if e is None:
        e = ea

    if EXERCISE == 'squat':
        if k is None:
            return _ko('구간 인식 중', 'Detecting phase')
        if k >= 150:
            return _ko('준비/상승완료', 'Ready / top')
        if k <= 90:
            return _ko('최저점', 'Bottom')
        if k <= 120:
            return _ko('하강·상승 중간', 'Mid phase')
        return _ko('하강/상승 전환', 'Transition')

    if EXERCISE == 'deadlift':
        if k is None or h is None:
            return _ko('구간 인식 중', 'Detecting phase')
        if k >= 155 and h >= 155:
            return _ko('락아웃/상승완료', 'Lockout / top')
        if h <= 115 or k <= 135:
            return _ko('시작/바닥구간', 'Start / bottom')
        return _ko('당기는 중간구간', 'Pulling / mid')

    if EXERCISE == 'bench':
        if e is None:
            return _ko('구간 인식 중', 'Detecting phase')
        if e >= 150:
            return _ko('준비/락아웃', 'Ready / lockout')
        if e <= 100:
            return _ko('가슴터치/최저점', 'Bottom')
        return _ko('하강·상승 중간', 'Mid phase')

    return _ko('구간 인식 중', 'Detecting phase')


def _is_top_phase(metrics):
    txt = str(phase_from_metrics(metrics))
    return any(w in txt for w in ['상승완료', '락아웃', 'top', 'Lockout'])


def explain_delta_feedback(key, delta, user_metrics=None, expert_metrics=None):
    """자세 의미 중심 피드백."""
    d = _safe_float(delta, 0.0)

    if key == 'trunk_lean':
        return _ko('몸통 기울기 과도' if d > 0 else '몸통 기울기 부족',
                   'Trunk lean issue')
    if key == 'knee_angle':
        return _ko('무릎이 전문가보다 덜 굽혀짐' if d > 0 else '무릎이 전문가보다 많이 굽혀짐',
                   'Knee angle issue')
    if key == 'hip_angle':
        return _ko('엉덩이 접힘이 전문가와 다름', 'Hip angle issue')
    if key in ['foot_flatness', 'left_foot_flatness', 'right_foot_flatness']:
        return _ko('발바닥/뒤꿈치 접지 확인', 'Check foot contact')
    if key == 'foot_foreaft_asymmetry':
        return _ko('양발 앞뒤 위치 확인', 'Check foot position')
    if key == 'head_hip_line':
        return _ko('머리-어깨-엉덩이 정렬 확인', 'Check head-shoulder-hip line')
    if key == 'neck_lean':
        return _ko('목-머리 각도 확인', 'Check neck/head angle')
    if key in ['elbow_angle', 'elbow_angle_avg']:
        return _ko('팔꿈치 각도 확인', 'Check elbow angle')
    if key == 'wrist_elbow_x_diff':
        return _ko('손목과 팔꿈치가 수직선상에 있지 않음', 'Wrist not above elbow')
    if key == 'bench_line_diff':
        return _ko('머리-어깨-엉덩이 라인 이탈', 'Bench body line issue')
    if key == 'foot_offset':
        return _ko('벤치프레스 양발 앞뒤 위치 확인', 'Check foot offset')

    label = V5_LABELS.get(key, rt.DISPLAY_LABELS.get(key, key))
    return _ko(f'{label} 차이 확인', f'Check {label}')


def explain_absolute_feedback(key, value):
    if key == 'lockout_angle_min':
        return _ko('팔꿈치 락아웃 부족', 'Insufficient elbow lockout')
    if key == 'elbow_above_shoulder':
        return _ko('팔꿈치가 어깨보다 높음', 'Elbow above shoulder')
    return _ko(f'{V5_LABELS.get(key, key)} 확인', f'Check {key}')


rt.delta_feedback = explain_delta_feedback


def choose_v5_issue(metrics_now, ex_metrics, deltas, rule_issue=None):
    """
    현재 프레임에서 가장 설명하기 좋은 오류 하나만 선택.
    delta 기준과 absolute 기준을 분리한다.
    """
    active = set(rt.EXERCISE_METRICS.get(EXERCISE, []))

    # 1) 벤치프레스 절대조건 먼저 확인
    if EXERCISE == 'bench':
        # lockout_angle_min: 상단 구간에서 팔꿈치각이 165도보다 작으면 락아웃 부족
        e = _safe_float(metrics_now.get('lockout_angle_min'))
        lock_thr = _safe_float(getattr(rt, 'ABSOLUTE_THRESHOLDS', {}).get('lockout_angle_min'), 165.0)
        if 'lockout_angle_min' in active and e is not None and e >= 140 and e < lock_thr:
            return {
                'key': 'lockout_angle_min',
                'message': explain_absolute_feedback('lockout_angle_min', e),
                'landmarks': rt.DELTA_TO_LM.get('lockout_angle_min', []),
                'delta': e - lock_thr,
                'ratio': abs(e - lock_thr) / 20.0,
                'priority': 98,
            }

        # elbow_above_shoulder: boolean 조건
        above = _safe_float(metrics_now.get('elbow_above_shoulder'), 0.0)
        if 'elbow_above_shoulder' in active and above >= 0.5:
            return {
                'key': 'elbow_above_shoulder',
                'message': explain_absolute_feedback('elbow_above_shoulder', above),
                'landmarks': rt.DELTA_TO_LM.get('elbow_above_shoulder', []),
                'delta': above,
                'ratio': 1.0,
                'priority': 92,
            }

    # 2) 몸통 기울기: 스쿼트/데드에서 최우선
    if EXERCISE in ['squat', 'deadlift'] and 'trunk_lean' in active:
        trunk_issue = evaluate_trunk_lean_issue(metrics_now, ex_metrics, TRUNK_LEAN_TOL_DEG)
        if trunk_issue:
            trunk_issue['priority'] = 100
            trunk_issue['ratio'] = abs(_safe_float(trunk_issue.get('delta'), 0.0)) / max(TRUNK_LEAN_TOL_DEG, 1e-6)
            return trunk_issue

    # 3) delta 기반 핵심 후보
    candidates = []
    for key in V5_PRIORITY_KEYS:
        if key not in active or key not in deltas:
            continue

        thr = _safe_float(rt.DELTA_THRESHOLDS.get(key))
        d = _safe_float(deltas.get(key))
        if thr is None or thr <= 0 or d is None:
            continue

        ratio = abs(d) / max(thr, 1e-6)
        if ratio < 1.0:
            continue

        top_phase = _is_top_phase(metrics_now)
        base_priority = {
            'trunk_lean': 100,
            'wrist_elbow_x_diff': 90,
            'elbow_angle': 85,
            'elbow_angle_avg': 82,
            'knee_angle': 80,
            'hip_angle': 76,
            'bench_line_diff': 74,
            'foot_flatness': 60 if not top_phase else 38,
            'left_foot_flatness': 58 if not top_phase else 36,
            'right_foot_flatness': 58 if not top_phase else 36,
            'foot_foreaft_asymmetry': 55,
            'foot_offset': 55,
            'head_hip_line': 48 if top_phase else 35,
            'neck_lean': 30,
        }.get(key, 40)

        candidates.append({
            'key': key,
            'message': explain_delta_feedback(key, d, metrics_now, ex_metrics),
            'landmarks': rt.DELTA_TO_LM.get(key, []),
            'delta': d,
            'ratio': ratio,
            'priority': base_priority + min(ratio, 2.0) * 5,
        })

    if candidates:
        return sorted(candidates, key=lambda x: x.get('priority', 0), reverse=True)[0]

    if rule_issue:
        out = dict(rule_issue)
        out.setdefault('priority', 30)
        out.setdefault('ratio', 1.0)
        return out

    return None


class FeedbackStabilizer:
    """같은 오류가 몇 프레임 연속 나올 때만 피드백을 바꿔 깜빡임을 줄인다."""
    def __init__(self, min_frames=3, hold_frames=8):
        self.min_frames = int(min_frames)
        self.hold_frames = int(hold_frames)
        self.candidate_key = None
        self.candidate_msg = None
        self.candidate_count = 0
        self.stable_issue = None
        self.hold_left = 0

    def update(self, issue):
        if issue is None:
            self.candidate_key = None
            self.candidate_msg = None
            self.candidate_count = 0
            if self.stable_issue is not None and self.hold_left > 0:
                self.hold_left -= 1
                return self.stable_issue
            self.stable_issue = None
            return None

        key = issue.get('key')
        msg = issue.get('message')
        same = (key == self.candidate_key and msg == self.candidate_msg)
        if same:
            self.candidate_count += 1
        else:
            self.candidate_key = key
            self.candidate_msg = msg
            self.candidate_count = 1

        if self.stable_issue is None or self.candidate_count >= self.min_frames:
            self.stable_issue = issue
            self.hold_left = self.hold_frames
        return self.stable_issue


def draw_feedback_banner(frame, feedback_text, issue_key=None,
                         user_metrics=None, expert_metrics=None, phase_text=None):
    fb = feedback_text or _ko('정상 범위', 'OK')
    phase = phase_text or phase_from_metrics(user_metrics or {})
    is_ok = any(w in str(fb) for w in ['정상', 'OK', '좋', 'safe'])
    fg = (120, 245, 150) if is_ok else (255, 130, 130)
    line1 = f'{phase}  |  {fb}'
    return draw_text_box_bgr(
        frame, line1, xy=(16, 52), font_size=21,
        fg=fg, bg=(18, 18, 28), alpha=0.78
    )


def draw_issue_markers(frame, lms, deltas, max_items=2):
    """핵심 오류 후보 관절만 표시."""
    H, W = frame.shape[:2]
    active = set(rt.EXERCISE_METRICS.get(EXERCISE, []))
    allowed = [k for k in V5_PRIORITY_KEYS if k in active]

    items = []
    for k in allowed:
        # absolute condition keys are handled through stable_issue/bad_indices,
        # but this marker function only uses delta-based ranking.
        if k in ['lockout_angle_min', 'elbow_above_shoulder']:
            continue

        if k not in deltas:
            continue
        thr = _safe_float(rt.DELTA_THRESHOLDS.get(k))
        d = _safe_float(deltas.get(k))
        if thr is None or thr <= 0 or d is None:
            continue
        ratio = abs(d) / max(thr, 1e-6)
        if ratio >= 1.0:
            items.append((ratio, k, d))

    items = sorted(items, reverse=True)[:max_items]

    for ratio, key, delta in items:
        for idx in rt.DELTA_TO_LM.get(key, []):
            p = lms[idx]
            v = float(getattr(p, 'visibility', 1.0))
            if v < VIS_THR:
                continue
            cx = int(p.x * W)
            cy = int(p.y * H)
            cv2.circle(frame, (cx, cy), 14, C_ERR_CIR, 2, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy),  4, C_ERR_CIR, -1, cv2.LINE_AA)
    return frame


def make_hud_panel(panel_w, panel_h, user_metrics, deltas, count,
                   feedback_text, issue_key, fps, ex_idx, ex_total,
                   exercise='squat', expert_metrics=None, phase_text=None):
    """v5 HUD: 종목별 핵심 문서 지표 표시."""
    img  = PilImage.new('RGB', (panel_w, panel_h), (18, 18, 28))
    drw  = ImageDraw.Draw(img)

    fTITLE = _fnt(28)
    fMD    = _fnt(16)
    fSM    = _fnt(13)

    y = 14
    EX = {'squat':'SQUAT','deadlift':'DEADLIFT','bench':'BENCH PRESS'}

    drw.text((14, y), EX.get(exercise, exercise.upper()), font=fTITLE, fill=(240, 205, 80))
    drw.text((panel_w-72, y+2), str(count), font=fTITLE, fill=(80, 220, 255))
    drw.text((panel_w-118, y+12), _ko('횟수', 'rep'), font=fSM, fill=(165,165,175))
    y += 44

    phase = phase_text or phase_from_metrics(user_metrics or {})
    drw.rounded_rectangle([10, y, panel_w-10, y+38], radius=10, fill=(31,31,45), outline=(65,65,85), width=1)
    drw.text((22, y+9), phase, font=fMD, fill=(230,230,235))
    y += 48
    drw.text((14, y), _ko('U=사용자  E=전문가  Δ=차이', 'U=user E=expert Δ=diff'),
             font=fSM, fill=(145,145,155))
    y += 25

    fb = feedback_text or _ko('정상 범위', 'OK')
    ok = any(w in str(fb) for w in ['정상', 'OK', '좋', 'safe'])
    card_col = (95, 220, 120) if ok else (255, 115, 115)
    drw.rounded_rectangle([10, y, panel_w-10, y+70], radius=13,
                          fill=(34,34,50), outline=card_col, width=2)
    drw.text((22, y+9), _ko('현재 핵심 피드백', 'Main feedback'), font=fSM, fill=(180,180,190))
    lines = textwrap.wrap(str(fb), width=max(8, (panel_w-44)//15))[:2]
    if not lines:
        lines = [str(fb)]
    for i, line in enumerate(lines):
        drw.text((22, y+31+i*21), line, font=fMD, fill=card_col)
    y += 84

    prog = _ko(f'전문가 프레임 {ex_idx+1}/{ex_total}   FPS {fps:.1f}',
               f'Expert {ex_idx+1}/{ex_total} FPS {fps:.1f}')
    drw.text((14, y), prog, font=fSM, fill=(115,115,125))
    y += 24
    drw.line([(10,y),(panel_w-10,y)], fill=(60,60,80), width=1)
    y += 14

    if exercise == 'bench':
        metric_list = [
            ('손목-팔꿈치', 'Wrist-Elbow', 'wrist_elbow_x_diff', ''),
            ('팔꿈치각', 'Elbow angle', 'elbow_angle', 'deg'),
            ('락아웃각', 'Lockout angle', 'lockout_angle_min', 'deg'),
            ('벤치라인', 'Bench line', 'bench_line_diff', ''),
            ('발바닥밀착', 'Foot contact', 'foot_flatness', ''),
            ('양발위치', 'Foot offset', 'foot_offset', ''),
        ]
    elif exercise == 'deadlift':
        # 요청 반영: 데드리프트 HUD에서 발바닥 밀착 여부는 표시하지 않는다.
        metric_list = [
            ('무릎각', 'Knee angle', 'knee_angle', 'deg'),
            ('엉덩이각', 'Hip angle', 'hip_angle', 'deg'),
            ('몸통기울기', 'Trunk lean', 'trunk_lean', 'deg'),
            ('머리-엉덩이', 'Head-hip line', 'head_hip_line', ''),
            ('목-머리각', 'Neck lean', 'neck_lean', 'deg'),
            ('팔꿈치각', 'Elbow angle', 'elbow_angle_avg', 'deg'),
        ]
    else:
        metric_list = [
            ('무릎각', 'Knee angle', 'knee_angle', 'deg'),
            ('엉덩이각', 'Hip angle', 'hip_angle', 'deg'),
            ('몸통기울기', 'Trunk lean', 'trunk_lean', 'deg'),
            ('발바닥밀착', 'Foot contact', 'foot_flatness', ''),
            ('발위치전후', 'Foot fore/aft', 'foot_foreaft_asymmetry', ''),
            ('머리-엉덩이', 'Head-hip line', 'head_hip_line', ''),
        ]

    active = set(rt.EXERCISE_METRICS.get(EXERCISE, []))
    for kr_label, en_label, key, unit in metric_list:
        if key not in active and key not in ['knee_angle', 'hip_angle', 'trunk_lean', 'elbow_angle']:
            continue
        if y > panel_h - 80:
            break

        label = _ko(kr_label, en_label)
        val = user_metrics.get(key) if isinstance(user_metrics, dict) else None

        # absolute condition display
        if key == 'lockout_angle_min':
            ex_val = rt.ABSOLUTE_THRESHOLDS.get('lockout_angle_min', 165.0)
            delta = None if val is None else float(val) - float(ex_val)
            bad = val is not None and float(val) < float(ex_val)
        elif key == 'elbow_above_shoulder':
            ex_val = 0.0
            delta = val
            bad = val is not None and float(val) >= 0.5
        else:
            ex_val = None
            if isinstance(expert_metrics, dict):
                ex_val = expert_metrics.get(key)
            if ex_val is None and isinstance(deltas, dict) and key in deltas and val is not None:
                ex_val = val - deltas.get(key, 0)

            delta = None
            if val is not None and ex_val is not None:
                try:
                    delta = float(val) - float(ex_val)
                except Exception:
                    delta = None
            elif isinstance(deltas, dict):
                delta = deltas.get(key)

            thr = rt.DELTA_THRESHOLDS.get(key)
            bad = False
            if delta is not None and thr is not None:
                bad = abs(float(delta)) > float(thr)

        col = (255,130,130) if bad else (120,245,150)

        drw.text((14, y), label, font=fMD, fill=(225,225,230))
        drw.text((panel_w-74, y), _ko('주의', 'WARN') if bad else 'OK', font=fMD, fill=col)
        y += 21

        val_line = f"U {_fmt_val(val, unit)} / E {_fmt_val(ex_val, unit)}"
        if delta is not None:
            val_line += f" / Δ {_fmt_val(delta, unit)}"
        drw.text((22, y), val_line, font=fSM, fill=(172,172,182))
        y += 19

        thr = rt.DELTA_THRESHOLDS.get(key)
        if delta is not None and thr is not None and float(thr) > 0:
            bw = panel_w - 44
            ratio = min(abs(float(delta)) / float(thr), 1.5) / 1.5
            drw.rectangle([22, y, 22+bw, y+5], fill=(48,48,60))
            drw.rectangle([22, y, 22+int(bw*ratio), y+5], fill=col)
        y += 18

    drw.line([(10, panel_h-64),(panel_w-10, panel_h-64)], fill=(60,60,80), width=1)
    note = _ko('빨간 원 = 현재 우선 확인 관절', 'Red circle = joint to check first')
    drw.text((14, panel_h-48), note, font=fSM, fill=(165,165,175))
    note2 = _ko('데드리프트: 핵심 각도/정렬만 표시', 'Deadlift: core angle/alignment only')
    drw.text((14, panel_h-28), note2, font=fSM, fill=(115,115,125))

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)




# ────────────────────────────────────────────────────────────────
# [deadlift v2 clean overlay]
# 기존 squat용 renderer의 depth/arc/acl/ktg 레이어를 그대로 쓰면
# 데드리프트 USER 화면이 과하게 복잡해지므로, deadlift에서는 아래 간소화 overlay를 사용한다.
# ────────────────────────────────────────────────────────────────
C_USER_BONE = (70, 225, 110)
C_USER_JOINT = (120, 255, 150)
C_USER_WARN = (0, 0, 255)
C_USER_BAR = (0, 215, 255)

DEADLIFT_CLEAN_CONNS = [
    (11, 12), (23, 24),
    (11, 23), (12, 24),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (23, 25), (25, 27), (27, 31),
    (24, 26), (26, 28), (28, 32),
]


def _lm_px_user(lms, idx, W, H):
    p = lms[idx]
    v = float(getattr(p, 'visibility', 1.0))
    return (int(float(p.x) * W), int(float(p.y) * H)), v


def _draw_dashed_vertical(frame, x, y1, y2, color, dash=10, gap=8, thickness=1):
    y1, y2 = sorted([int(y1), int(y2)])
    for y in range(y1, y2, dash + gap):
        cv2.line(frame, (int(x), y), (int(x), min(y + dash, y2)), color, thickness, cv2.LINE_AA)
    return frame


def draw_clean_deadlift_overlay(frame, lms, metrics_now=None, stable_issue=None):
    """
    데드리프트 전용 간소화 overlay.
    표시하는 것:
    1) 기본 skeleton
    2) 몸통선 shoulder-center ↔ hip-center
    3) 손목 세로 점선 = 바벨 위치 proxy
    4) 현재 핵심 issue 관절만 빨간 원
    """
    H, W = frame.shape[:2]
    bad_indices = set()
    issue_key = None
    if isinstance(stable_issue, dict):
        bad_indices = set(stable_issue.get('landmarks', []))
        issue_key = stable_issue.get('key')

    # 1) skeleton bone
    for a, b in DEADLIFT_CLEAN_CONNS:
        pa, va = _lm_px_user(lms, a, W, H)
        pb, vb = _lm_px_user(lms, b, W, H)
        if va < VIS_THR or vb < VIS_THR:
            continue
        cv2.line(frame, pa, pb, C_USER_BONE, 3, cv2.LINE_AA)

    # 2) joints: 작게, 핵심 오류 관절만 빨간색으로
    for idx in [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 31, 32]:
        pt, v = _lm_px_user(lms, idx, W, H)
        if v < VIS_THR:
            continue
        if idx in bad_indices:
            cv2.circle(frame, pt, 12, C_USER_WARN, 2, cv2.LINE_AA)
            cv2.circle(frame, pt, 4, C_USER_WARN, -1, cv2.LINE_AA)
        else:
            cv2.circle(frame, pt, 4, C_USER_JOINT, -1, cv2.LINE_AA)

    # 3) 몸통 중심선: 데드리프트 핵심. 오류일 때만 빨강.
    try:
        sh_c = midp(lms, 11, 12)
        hp_c = midp(lms, 23, 24)
        sh = (int(sh_c[0] * W), int(sh_c[1] * H))
        hp = (int(hp_c[0] * W), int(hp_c[1] * H))
        trunk_color = C_USER_WARN if issue_key in ['trunk_lean', 'head_hip_line', 'neck_lean'] else C_USER_BONE
        cv2.line(frame, hp, sh, trunk_color, 5, cv2.LINE_AA)
    except Exception:
        pass

    # 4) 손목 세로 점선: 바벨 위치 proxy. 너무 튀지 않게 얇게 표시.
    try:
        side = _pick_visible_side(lms)
        wr, vw = _lm_px_user(lms, side['wrist'], W, H)
        an, va = _lm_px_user(lms, side['ankle'], W, H)
        if vw >= VIS_THR and va >= VIS_THR:
            _draw_dashed_vertical(frame, wr[0], min(wr[1], an[1]) - 20, H - 24, C_USER_BAR, thickness=1)
            cv2.circle(frame, wr, 6, C_USER_BAR, -1, cv2.LINE_AA)
    except Exception:
        pass

    return frame


EXPERT_MATCH_KEYS = ['hip_angle', 'knee_angle', 'trunk_lean']
EXPERT_MATCH_WEIGHTS = {'hip_angle': 1.0, 'knee_angle': 0.9, 'trunk_lean': 0.8}


def build_expert_metric_cache(ex_frames_data, exercise):
    cache = []
    for pack in ex_frames_data:
        try:
            cache.append(compute_expert_metrics_plus(pack['landmarks'], pack.get('metrics', {}), exercise))
        except Exception:
            cache.append(pack.get('metrics', {}) if isinstance(pack.get('metrics', {}), dict) else {})
    return cache


def match_expert_frame_by_metrics(user_metrics, expert_metric_cache, fallback_idx=0):
    """
    시간 기반 매칭만 쓰면 전문가/사용자가 서로 다른 속도로 움직일 때 따로 노는 것처럼 보인다.
    deadlift에서는 hip/knee/trunk 값이 가장 가까운 전문가 프레임을 찾아 비교한다.
    """
    if EXERCISE != 'deadlift' or not isinstance(user_metrics, dict) or not expert_metric_cache:
        return int(fallback_idx)

    best_i = int(fallback_idx)
    best_score = float('inf')
    for i, em in enumerate(expert_metric_cache):
        score = 0.0
        n = 0
        for k in EXPERT_MATCH_KEYS:
            uv = _safe_float(user_metrics.get(k))
            ev = _safe_float(em.get(k)) if isinstance(em, dict) else None
            if uv is None or ev is None:
                continue
            w = EXPERT_MATCH_WEIGHTS.get(k, 1.0)
            score += w * abs(uv - ev)
            n += 1
        if n == 0:
            continue
        score /= n
        if score < best_score:
            best_score = score
            best_i = i
    return int(best_i)


print('v5 피드백 업그레이드 로드 완료 - 문서 기준 3대운동 측면형')
print(f'  핵심 오류 후보: {V5_PRIORITY_KEYS}')
print(f'  현재 활성 지표: {rt.EXERCISE_METRICS.get(EXERCISE)}')


# %%
# ===== Original notebook cell 9 =====
# ── Cell 8: 모델 / 전문가 JSON / 영상 로드 & 레이아웃 계산 ────────
# 핵심 수정:
# - 원본 영상을 HALF_W로 찌그러뜨리지 않음.
# - USER 영역은 원본 W×H 그대로 유지.
# - EXPERT skeleton과 HUD는 오른쪽에 별도 영역으로 추가.
# - 따라서 출력 영상 폭은 넓어지지만 원본 비율은 자연스럽게 유지됨.

rt.ensure_model(MODEL_PATH)
expert = rt.load_expert(EXERCISE, EXPERT_JSON_PATH)

ex_total       = expert['total_frames']
ex_frames_data = expert['frames']
print(f'[전문가] {ex_total}프레임, {expert.get("fps",24):.1f}fps')

# deadlift v2: 시간 기반이 아니라 자세 지표 기반으로 전문가 프레임을 매칭하기 위한 캐시
EXPERT_METRIC_CACHE = build_expert_metric_cache(ex_frames_data, EXERCISE)
print(f'[전문가 매칭] metric cache 생성 완료: {len(EXPERT_METRIC_CACHE)} frames')

print('[PoseLandmarker] 로딩 중...')
landmarker = rt.build_landmarker(MODEL_PATH)
print('[PoseLandmarker] 완료')

# probe용으로만 영상 정보 읽기
cap_probe = cv2.VideoCapture(USER_VIDEO_PATH)
if not cap_probe.isOpened():
    raise RuntimeError(f'영상 열기 실패: {USER_VIDEO_PATH}')

fps = cap_probe.get(cv2.CAP_PROP_FPS)
if fps <= 0:
    fps = 30.0

W = int(cap_probe.get(cv2.CAP_PROP_FRAME_WIDTH))
H = int(cap_probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
cap_probe.release()

print(f'[영상] {W}x{H}, {fps:.2f}fps')

# ── 출력 레이아웃 ─────────────────────────────────────────────────
# 기존 문제:
#   HALF_W = (W-PW)//2 로 사용자 영상을 강제 축소 → 화면이 세로로 찌그러짐.
# 수정:
#   USER_W = W, USER_H = H 그대로 사용.
#   오른쪽에 EXPERT_W와 HUD_W를 추가.

USER_W = W
USER_H = H

# 전문가 skeleton 영역 폭. 너무 작으면 skeleton이 답답하고, 너무 크면 출력이 과도하게 넓어짐.
EXPERT_W = min(520, max(420, int(W * 0.40)))
PW       = 410   # v5 HUD 카드/설명 공간 확보

OUT_W = USER_W + EXPERT_W + PW
OUT_H = H

print(f'[레이아웃] USER:{USER_W}x{USER_H} | EXPERT:{EXPERT_W}x{OUT_H} | HUD:{PW}x{OUT_H}')
print(f'[출력 크기] {OUT_W}x{OUT_H}')
print(f'[출력 경로] {OUTPUT_PATH}')


# %%
# ===== Original notebook cell 10 =====
# ── Cell 9: 상태 객체 & 렌더러 설정 ─────────────────────────────
# 핵심 수정:
# - 3대운동 공통용 side-view rep counter를 로컬에서 명시적으로 사용
# - realtime_compare_side.py에 관련 객체가 없어도 notebook이 멈추지 않게 fallback 유지

import numpy as np

if not hasattr(rt, 'WINDOW_SIZE'):
    rt.WINDOW_SIZE = 5

if not hasattr(rt, 'PoseLandmarksConns'):
    rt.PoseLandmarksConns = SKEL_CONNS


# MetricsBuffer 없을 경우 fallback
if not hasattr(rt, 'MetricsBuffer'):
    class MetricsBuffer:
        def __init__(self, window=5):
            self.window = int(window)
            self.buf = []

        def push(self, metrics):
            self.buf.append(dict(metrics))
            if len(self.buf) > self.window:
                self.buf.pop(0)

        def get_avg(self):
            if not self.buf:
                return {}

            keys = set()
            for m in self.buf:
                keys.update(m.keys())

            out = {}
            for k in keys:
                vals = []
                for m in self.buf:
                    v = m.get(k)
                    if isinstance(v, (int, float, np.floating)) and np.isfinite(v):
                        vals.append(float(v))
                if vals:
                    out[k] = float(np.mean(vals))
            return out

    rt.MetricsBuffer = MetricsBuffer
    print('보정: rt.MetricsBuffer 임시 생성 완료')


# RuleState 없을 경우 fallback
if not hasattr(rt, 'RuleState'):
    class RuleState:
        def __init__(self, exercise='squat'):
            self.exercise = exercise

        def evaluate(self, metrics):
            return []

    rt.RuleState = RuleState
    print('보정: rt.RuleState 임시 생성 완료')


# 3대운동 측면영상용 rep counter
class SideViewRepCounter3Lift:
    def __init__(self, exercise='squat', min_hold_frames=3, cooldown_frames=8):
        self.exercise = exercise
        self.count = 0
        self.state = 'top'
        self.bottom_hold = 0
        self.top_hold = 0
        self.cooldown = 0
        self.min_hold_frames = int(min_hold_frames)
        self.cooldown_frames = int(cooldown_frames)

    def _num(self, metrics, key):
        try:
            v = float(metrics.get(key))
            return v if np.isfinite(v) else None
        except Exception:
            return None

    def update(self, metrics):
        if not isinstance(metrics, dict):
            return False

        if self.cooldown > 0:
            self.cooldown -= 1

        if self.exercise == 'squat':
            k = self._num(metrics, 'knee_angle')
            if k is None:
                return False
            bottom = k <= 95
            top = k >= 150

        elif self.exercise == 'deadlift':
            k = self._num(metrics, 'knee_angle')
            h = self._num(metrics, 'hip_angle')
            if k is None or h is None:
                return False
            bottom = (h <= 115) or (k <= 135)
            top = (h >= 155) and (k >= 155)

        elif self.exercise == 'bench':
            e = self._num(metrics, 'elbow_angle')
            if e is None:
                e = self._num(metrics, 'elbow_angle_avg')
            if e is None:
                return False
            bottom = e <= 100
            top = e >= 155

        else:
            return False

        if bottom:
            self.bottom_hold += 1
        else:
            self.bottom_hold = 0

        if top:
            self.top_hold += 1
        else:
            self.top_hold = 0

        # bottom 상태를 확실히 거친 뒤 top으로 돌아오면 1회
        if self.state != 'bottom' and self.bottom_hold >= self.min_hold_frames:
            self.state = 'bottom'
            return False

        if (
            self.state == 'bottom'
            and self.top_hold >= self.min_hold_frames
            and self.cooldown == 0
        ):
            self.count += 1
            self.state = 'top'
            self.cooldown = self.cooldown_frames
            return True

        return False


# 기존 rt.SideViewRepCounter가 있어도 3대운동 공통 카운터로 통일
rt.SideViewRepCounter = SideViewRepCounter3Lift


if not hasattr(rt, 'pick_worst_issue'):
    def pick_worst_issue(issues):
        if not issues:
            return None
        return issues[0]

    rt.pick_worst_issue = pick_worst_issue
    print('보정: rt.pick_worst_issue 임시 생성 완료')


if not hasattr(rt, 'compute_deltas'):
    def compute_deltas(user_metrics, expert_metrics, exercise='squat'):
        deltas = {}
        keys = rt.EXERCISE_METRICS.get(exercise, list(user_metrics.keys()))

        for k in keys:
            if k not in user_metrics or k not in expert_metrics:
                continue

            uv = user_metrics.get(k)
            ev = expert_metrics.get(k)

            if uv is None or ev is None:
                continue

            try:
                deltas[k] = float(uv) - float(ev)
            except Exception:
                pass

        return deltas

    rt.compute_deltas = compute_deltas
    print('보정: rt.compute_deltas 임시 생성 완료')


if not hasattr(rt, 'select_worst_delta'):
    def select_worst_delta(deltas):
        if not deltas:
            return None

        worst_key = None
        worst_delta = None
        worst_ratio = 0.0

        for k, d in deltas.items():
            thr = rt.DELTA_THRESHOLDS.get(k)
            if thr is None or thr <= 0:
                continue

            ratio = abs(float(d)) / max(float(thr), 1e-6)
            if ratio > worst_ratio:
                worst_ratio = ratio
                worst_key = k
                worst_delta = d

        if worst_key is None or worst_ratio < 1.0:
            return None

        return worst_key, worst_delta

    rt.select_worst_delta = select_worst_delta
    print('보정: rt.select_worst_delta 임시 생성 완료')


if not hasattr(rt, 'delta_feedback'):
    def delta_feedback(key, delta):
        label = rt.DISPLAY_LABELS.get(key, key)

        if delta > 0:
            return f'{label} 값이 전문가보다 큽니다'
        return f'{label} 값이 전문가보다 작습니다'

    rt.delta_feedback = delta_feedback
    print('보정: rt.delta_feedback 임시 생성 완료')


# 상태 객체 생성
buf         = rt.MetricsBuffer(window=rt.WINDOW_SIZE)
rules       = rt.RuleState(EXERCISE)
rep_counter = rt.SideViewRepCounter(EXERCISE)

renderer = fo.FeedbackRenderer(fps=fps)


# ── 기존 시각화 레이어 복구 ─────────────────────────────────────
# deadlift는 squat용 depth/arc/acl/ktg 레이어를 그대로 켜면 화면이 매우 지저분해진다.
# 따라서 deadlift에서는 기존 renderer를 사실상 끄고, 아래의 clean deadlift overlay만 사용한다.
if EXERCISE == 'deadlift':
    CORE_LAYERS = []
    OPTIONAL_LAYERS = []
else:
    CORE_LAYERS = ['phase', 'tempo', 'depth', 'arc', 'acl', 'ktg']
    OPTIONAL_LAYERS = ['bar_proxy', 'heatmap', 'trail']

available_layers = None
for attr in ['layers', 'layer_map', 'registry', 'renderers', 'available_layers']:
    obj = getattr(renderer, attr, None)
    if isinstance(obj, dict):
        available_layers = set(obj.keys())
        break
    if isinstance(obj, (set, list, tuple)):
        available_layers = set(obj)
        break

if available_layers is None:
    VISIBLE_LAYERS = CORE_LAYERS
else:
    VISIBLE_LAYERS = [x for x in CORE_LAYERS + OPTIONAL_LAYERS if x in available_layers]

enabled_layers = []
skipped_layers = []

for layer in VISIBLE_LAYERS:
    try:
        renderer.enable(layer)
        enabled_layers.append(layer)
    except Exception as e:
        skipped_layers.append((layer, str(e)))

# depth 목표선 설정
try:
    expert_target_y_norm = fo.extract_expert_depth_target(ex_frames_data, EXERCISE)
    renderer.depth_line.set_expert_target(expert_target_y_norm, OUT_H)
except Exception as e:
    print(f'[참고] depth 목표선 설정 skip: {e}')

print('상태 객체 / 렌더러 설정 완료')
print(f'  종목: {EXERCISE} | MetricsBuffer 윈도우: {rt.WINDOW_SIZE}')
print(f'  ON 레이어: {enabled_layers}')
if skipped_layers:
    print(f'  SKIP 레이어: {[x[0] for x in skipped_layers]}')


# %%
# ===== Original notebook cell 11 =====
# ── Cell 10: 메인 처리 루프 v5 ───────────────────────────────────
# v5 핵심:
# - 오류 후보를 1개로 안정화해서 피드백 깜빡임 감소
# - '값이 큼/작음' 대신 의미 있는 문장으로 표시
# - HUD에 현재 구간, U/E/Δ 의미, 핵심 피드백을 크게 표시

# Cell 10만 다시 실행해도 되도록 cap/out을 여기서 새로 연다.
cap = cv2.VideoCapture(USER_VIDEO_PATH)
if not cap.isOpened():
    raise RuntimeError(f'영상 열기 실패: {USER_VIDEO_PATH}')

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out    = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (OUT_W, OUT_H))

if not out.isOpened():
    raise RuntimeError(f'VideoWriter 열기 실패: {OUTPUT_PATH}')

frame_idx = 0
t_start   = time.perf_counter()
feedback_stabilizer = FeedbackStabilizer(min_frames=3, hold_frames=8)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    if rt.MIRROR_CAMERA:
        frame = cv2.flip(frame, 1)

    # 원본 비율 유지
    user_canvas = frame.copy()

    elapsed_ms = int(frame_idx * 1000 / fps)

    # 전문가 프레임 인덱스 & 지표
    ex_idx     = rt.get_expert_frame_idx(elapsed_ms, expert)
    ex_pack    = ex_frames_data[ex_idx]
    ex_lms_raw = ex_pack['landmarks']
    ex_metrics = compute_expert_metrics_plus(
        ex_lms_raw,
        ex_pack.get('metrics', {}),
        EXERCISE
    )

    # 사용자 landmark 추출: 원본 frame 기준
    lms = rt.extract_landmarks(landmarker, user_canvas, elapsed_ms)

    feedback    = ''
    issue_key   = None
    bad_indices = set()
    deltas      = {}
    user_avg    = {}
    raw         = {}
    metrics_now = {}
    phase_text  = _ko('구간 인식 중', 'Detecting phase')
    stable_issue = None

    if lms:
        try:
            raw = compute_user_metrics_plus(lms, EXERCISE)
            buf.push(raw)
            user_avg = buf.get_avg()
        except Exception as e:
            feedback = f'지표 계산 오류: {e}'
            print('[지표 계산 오류]', e)
            user_avg = {}

        metrics_now = user_avg if user_avg else raw
        phase_text  = phase_from_metrics(metrics_now)

        if metrics_now:
            # deadlift v2: 전문가와 사용자가 따로 노는 느낌을 줄이기 위해
            # 현재 사용자 자세와 가장 비슷한 전문가 프레임으로 재매칭한다.
            if EXERCISE == 'deadlift':
                matched_idx = match_expert_frame_by_metrics(metrics_now, EXPERT_METRIC_CACHE, ex_idx)
                if matched_idx != ex_idx:
                    ex_idx = matched_idx
                    ex_pack = ex_frames_data[ex_idx]
                    ex_lms_raw = ex_pack['landmarks']
                    ex_metrics = EXPERT_METRIC_CACHE[ex_idx]

            # 횟수 카운트
            if rep_counter.update(metrics_now):
                print(f'[{EXERCISE.upper()}] {rep_counter.count}회')

            # 전문가 delta 계산 후 현재 view에서 실제 사용하는 지표만 유지
            deltas = rt.compute_deltas(metrics_now, ex_metrics, EXERCISE)
            active_keys = set(rt.EXERCISE_METRICS.get(EXERCISE, []))
            deltas = {k: v for k, v in deltas.items() if k in active_keys}

            # 기존 rule 기반 issue는 fallback으로만 사용
            rule_issues = rules.evaluate(metrics_now)
            rule_issue  = rt.pick_worst_issue(rule_issues)

            # v5: 가장 설명하기 좋은 issue 1개 선택 후 안정화
            candidate_issue = choose_v5_issue(metrics_now, ex_metrics, deltas, rule_issue)
            stable_issue = feedback_stabilizer.update(candidate_issue)

            if stable_issue:
                issue_key   = stable_issue.get('key')
                feedback    = stable_issue.get('message', '')
                bad_indices = set(stable_issue.get('landmarks', []))
            else:
                feedback = _ko('정상 범위', 'OK')

        if EXERCISE == 'deadlift':
            # deadlift v2: squat용 레이어를 제거하고 핵심 skeleton/몸통선/손목 proxy만 표시
            user_canvas = draw_clean_deadlift_overlay(
                user_canvas, lms, metrics_now, stable_issue
            )
        else:
            # 기존 feedback_overlay 렌더
            try:
                user_canvas = renderer.render(
                    frame            = user_canvas,
                    user_metrics_raw = metrics_now,
                    expert_metrics   = ex_metrics,
                    deltas           = deltas,
                    lms              = lms,
                    connections      = rt.PoseLandmarksConns,
                    metric_to_lm     = rt.DELTA_TO_LM,
                    exercise         = EXERCISE
                )
            except Exception as e:
                # renderer 하나가 실패해도 전체 영상 생성은 계속 진행
                print(f'[renderer 오류] frame={frame_idx}: {e}')

            # 추가 레이어 1: 발너비 bracket
            # 측면이면 VIDEO_VIEW_MODE='side'라서 자동으로 숨김.
            user_canvas = draw_foot_bracket(
                user_canvas, lms, metrics_now, view_mode=VIDEO_VIEW_MODE
            )

            # 추가 레이어 2: 몸통기울기 허용범위 zone
            user_canvas = draw_trunk_lean_zone(
                user_canvas, lms,
                metrics_now,
                ex_metrics,
                bad_indices,
                tol_deg=TRUNK_LEAN_TOL_DEG
            )

            # 추가 레이어 3: threshold 초과 핵심 관절 원 표시
            user_canvas = draw_issue_markers(
                user_canvas, lms, deltas, max_items=2
            )

        # 공통: 큰 피드백 배너
        user_canvas = draw_feedback_banner(
            user_canvas, feedback, issue_key, metrics_now, ex_metrics, phase_text=phase_text
        )

    else:
        feedback = _ko('자세를 인식할 수 없습니다. 전신이 보이게 해주세요.',
                       'Pose not detected. Show full body.')

    # 사용자 레이블
    cv2.putText(
        user_canvas, 'USER',
        (10, 28),
        cv2.FONT_HERSHEY_SIMPLEX, 0.75,
        (60, 210, 255), 2, cv2.LINE_AA
    )

    # 전문가 skeleton canvas
    expert_canvas = draw_expert_on_canvas(
        EXPERT_W, OUT_H, ex_lms_raw, bad_indices
    )

    # HUD
    elapsed = time.perf_counter() - t_start
    cur_fps = (frame_idx + 1) / max(elapsed, 1e-6)

    hud_panel = make_hud_panel(
        panel_w        = PW,
        panel_h        = OUT_H,
        user_metrics   = user_avg if user_avg else raw,
        deltas         = deltas,
        count          = rep_counter.count,
        feedback_text  = feedback,
        issue_key      = issue_key,
        fps            = cur_fps,
        ex_idx         = ex_idx,
        ex_total       = ex_total,
        exercise       = EXERCISE,
        expert_metrics = ex_metrics,
        phase_text     = phase_text
    )

    # 최종 합성: [원본 USER | EXPERT | HUD]
    final_frame = np.hstack([user_canvas, expert_canvas, hud_panel])

    # 영역 구분선
    cv2.line(final_frame, (USER_W, 0), (USER_W, OUT_H), (50, 50, 70), 2)
    cv2.line(final_frame, (USER_W + EXPERT_W, 0), (USER_W + EXPERT_W, OUT_H), (50, 50, 70), 2)

    out.write(final_frame)
    frame_idx += 1

    if frame_idx % 30 == 0:
        print(f'[처리 중] {frame_idx}f | rep={rep_counter.count} | feedback={feedback} | fps={cur_fps:.1f}')

cap.release()
out.release()

try:
    landmarker.close()
except Exception:
    pass

print(f'\n완료! 총 {frame_idx} frames')
print(f'총 횟수: {rep_counter.count}회')
print(f'출력: {OUTPUT_PATH}')


# %%
# ===== Original notebook cell 12 =====
# ── Cell 11: 저장 확인만 하기 ─────────────────────────
import os

if not os.path.exists(OUTPUT_PATH):
    print('출력 파일 없음 -- Cell 10 정상 실행 여부 확인')
else:
    size_mb = os.path.getsize(OUTPUT_PATH) / 1024 / 1024
    print(f'저장 완료!')
    print(f'파일 크기: {size_mb:.1f} MB')
    print(f'저장 위치: {OUTPUT_PATH}')
