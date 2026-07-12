"""
phase_labeling.py

Purpose:
    Start/Bottom/Finish 3단계 phase를 사람이 직접 영상을 보면서 프레임
    단위로 라벨링하는 Tkinter GUI 도구. Notion 0512 회의록에서 언급된
    phase 라벨링 작업의 실제 코드.

Supported exercise:
    squat, benchpress, deadlift (EXERCISE_TYPES 상수로 정의된 하위 폴더 3개)

Input:
    `측면_수정본/{benchpress,squat,deadlift}/*.{mp4,avi,mov,mkv,wmv}`
    형태의 폴더 구조. 최상위 폴더는 실행 시 "측면_수정본 폴더 선택" 버튼으로
    직접 고를 수 있다(기본값: 이 스크립트와 같은 폴더).

Output:
    `phase_labels.csv` (선택한 최상위 폴더에 저장). 컬럼: `type`, `name`,
    `count`(반복 횟수), `L1`, `L2`, `L3`, ... — 3개씩 한 세트로
    L(3k+1)=k+1번째 반복의 Start 프레임, L(3k+2)=Bottom 프레임,
    L(3k+3)=Finish 프레임 번호(0-based, `FRAME_INDEX_BASE` 기준).

Main dependencies:
    opencv-python(cv2), Pillow(PIL), tkinter(표준 라이브러리)

Notes:
    - GUI 도구이므로 서버/헤드리스 환경에서는 실행 불가(로컬 데스크톱 전용).
    - 라벨 순서(Start→Bottom→Finish)를 어기고 기록하려 하면 확인 팝업이 뜬다.
    - 기존 CSV를 불러와 이어서 작업할 수 있다(load_csv).
"""

import cv2
import csv
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk


# =========================
# 기본 설정
# =========================

DEFAULT_BASE_DIR = Path(__file__).resolve().parent

EXERCISE_TYPES = ["benchpress", "squat", "deadlift"]
VIDEO_EXTS = [".mp4", ".avi", ".mov", ".mkv", ".wmv"]

OUTPUT_CSV_NAME = "phase_labels.csv"

# OpenCV 기준 0번 프레임부터 저장하려면 0
# 사람이 보기 편한 1번 프레임부터 저장하려면 1
FRAME_INDEX_BASE = 0

PHASES = ["Start", "Bottom", "Finish"]

# 영상 표시 크기 고정
DISPLAY_W = 960
DISPLAY_H = 540


class PhaseLabeler:
    def __init__(self, root):
        self.root = root
        self.root.title("Phase Labeler - Start / Bottom / Finish")

        self.base_dir = DEFAULT_BASE_DIR
        self.output_csv_path = self.base_dir / OUTPUT_CSV_NAME

        self.video_items = []
        self.video_idx = -1

        self.cap = None
        self.fps = 30
        self.total_frames = 0
        self.current_frame_idx = 0
        self.playing = False

        # key = (type, name)
        # value = [(phase, frame_idx), ...]
        self.annotations = {}
        self.current_events = []

        self.refreshing_video_list = False

        # Seek bar 관련 변수
        self.seek_var = tk.IntVar(value=FRAME_INDEX_BASE)
        self.slider_updating = False
        self.was_playing_before_seek = False

        self.build_ui()
        self.bind_keys()
        self.load_default_dataset()

    # =========================
    # UI 구성
    # =========================

    def build_ui(self):
        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True)

        # -------------------------
        # 왼쪽: 영상 목록
        # -------------------------
        left = tk.Frame(main, width=330)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        tk.Button(
            left,
            text="측면_수정본 폴더 선택",
            command=self.choose_base_folder
        ).pack(fill=tk.X, pady=2)

        tk.Button(
            left,
            text="기존 CSV 불러오기",
            command=self.load_csv
        ).pack(fill=tk.X, pady=2)

        tk.Button(
            left,
            text="CSV 저장 [Ctrl+S]",
            command=self.save_csv
        ).pack(fill=tk.X, pady=2)

        tk.Label(left, text="영상 목록").pack(anchor="w", pady=(10, 0))

        list_frame = tk.Frame(left)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.video_listbox = tk.Listbox(list_frame, width=48, height=35)
        self.video_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.video_scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.video_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.video_listbox.config(yscrollcommand=self.video_scrollbar.set)
        self.video_scrollbar.config(command=self.video_listbox.yview)

        self.video_listbox.bind("<<ListboxSelect>>", self.on_video_select)

        nav_frame = tk.Frame(left)
        nav_frame.pack(fill=tk.X, pady=5)

        tk.Button(nav_frame, text="이전 영상 [P]", command=self.prev_video).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=2
        )
        tk.Button(nav_frame, text="다음 영상 [N]", command=self.next_video).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=2
        )

        # -------------------------
        # 가운데: 정보 + 영상 + 바 + 컨트롤
        # -------------------------
        center = tk.Frame(main)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.info_label = tk.Label(
            center,
            text="",
            anchor="w",
            justify=tk.LEFT,
            font=("맑은 고딕", 10),
            bg="#f2f2f2",
            padx=8,
            pady=6
        )
        self.info_label.pack(fill=tk.X, pady=(0, 5))

        self.video_container = tk.Frame(
            center,
            width=DISPLAY_W,
            height=DISPLAY_H,
            bg="black"
        )
        self.video_container.pack(pady=5)
        self.video_container.pack_propagate(False)

        self.video_label = tk.Label(self.video_container, bg="black")
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # 프레임 이동 바
        seek_frame = tk.Frame(center)
        seek_frame.pack(fill=tk.X, pady=(5, 2))

        self.seek_scale = tk.Scale(
            seek_frame,
            from_=FRAME_INDEX_BASE,
            to=FRAME_INDEX_BASE,
            orient=tk.HORIZONTAL,
            variable=self.seek_var,
            showvalue=False,
            length=DISPLAY_W,
            command=self.on_seek_drag
        )
        self.seek_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.time_label = tk.Label(
            seek_frame,
            text="0 / 0",
            width=18,
            anchor="e"
        )
        self.time_label.pack(side=tk.RIGHT, padx=5)

        self.seek_scale.bind("<ButtonPress-1>", self.on_seek_press)
        self.seek_scale.bind("<ButtonRelease-1>", self.on_seek_release)

        control = tk.Frame(center)
        control.pack(fill=tk.X, pady=3)

        tk.Button(control, text="<< 1프레임 [←]", command=self.step_back).pack(side=tk.LEFT, padx=2)

        self.play_button = tk.Button(
            control,
            text="▶ 재생 [Space]",
            command=self.toggle_play
        )
        self.play_button.pack(side=tk.LEFT, padx=2)

        tk.Button(control, text="1프레임 >> [→]", command=self.step_forward).pack(side=tk.LEFT, padx=2)

        tk.Button(control, text="<< 10프레임 [Shift+←]", command=lambda: self.jump_frames(-10)).pack(side=tk.LEFT, padx=2)
        tk.Button(control, text="10프레임 >> [Shift+→]", command=lambda: self.jump_frames(10)).pack(side=tk.LEFT, padx=2)

        phase_frame = tk.Frame(center)
        phase_frame.pack(fill=tk.X, pady=5)

        tk.Button(
            phase_frame,
            text="Start 기록 [S]",
            bg="#d8f5d0",
            command=lambda: self.record_phase("Start")
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            phase_frame,
            text="Bottom 기록 [B]",
            bg="#f5e6c8",
            command=lambda: self.record_phase("Bottom")
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            phase_frame,
            text="Finish 기록 [F]",
            bg="#d8e9ff",
            command=lambda: self.record_phase("Finish")
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            phase_frame,
            text="마지막 기록 취소 [Z]",
            command=self.undo_last
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            phase_frame,
            text="선택 기록 삭제 [Del]",
            command=self.delete_selected_event
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            phase_frame,
            text="선택 기록 현재 프레임으로 수정 [R]",
            command=self.update_selected_event_frame
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            phase_frame,
            text="현재 영상 기록 전체 삭제 [C]",
            command=self.clear_current_events
        ).pack(side=tk.LEFT, padx=3)

        # -------------------------
        # 오른쪽: 현재 영상 라벨 목록
        # -------------------------
        right = tk.Frame(main, width=360)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)

        tk.Label(right, text="현재 영상 라벨").pack(anchor="w")

        self.event_listbox = tk.Listbox(right, width=52, height=35)
        self.event_listbox.pack(fill=tk.BOTH, expand=True)

        help_text = (
            "단축키\n"
            "Space : 재생 / 정지\n"
            "← / → : 1프레임 이동\n"
            "Shift+← / Shift+→ : 10프레임 이동\n"
            "S : Start 기록\n"
            "B : Bottom 기록\n"
            "F : Finish 기록\n"
            "Z : 마지막 기록 취소\n"
            "R : 선택 라벨을 현재 프레임으로 수정\n"
            "Delete : 선택 라벨 삭제\n"
            "C : 현재 영상 라벨 전체 삭제\n"
            "P / N : 이전 / 다음 영상\n"
            "Ctrl+S : CSV 저장\n\n"
            "라벨 의미\n"
            "L1 = 1회차 Start\n"
            "L2 = 1회차 Bottom\n"
            "L3 = 1회차 Finish\n"
            "L4 = 2회차 Start ..."
        )

        tk.Label(right, text=help_text, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=5)

    # =========================
    # 키보드 입력
    # =========================

    def bind_keys(self):
        self.root.bind_all("<space>", lambda e: self.toggle_play())
        self.root.bind_all("<Left>", lambda e: self.step_back())
        self.root.bind_all("<Right>", lambda e: self.step_forward())
        self.root.bind_all("<Shift-Left>", lambda e: self.jump_frames(-10))
        self.root.bind_all("<Shift-Right>", lambda e: self.jump_frames(10))

        self.root.bind_all("s", lambda e: self.record_phase("Start"))
        self.root.bind_all("S", lambda e: self.record_phase("Start"))

        self.root.bind_all("b", lambda e: self.record_phase("Bottom"))
        self.root.bind_all("B", lambda e: self.record_phase("Bottom"))

        self.root.bind_all("f", lambda e: self.record_phase("Finish"))
        self.root.bind_all("F", lambda e: self.record_phase("Finish"))

        self.root.bind_all("z", lambda e: self.undo_last())
        self.root.bind_all("Z", lambda e: self.undo_last())

        self.root.bind_all("r", lambda e: self.update_selected_event_frame())
        self.root.bind_all("R", lambda e: self.update_selected_event_frame())

        self.root.bind_all("<Delete>", lambda e: self.delete_selected_event())

        self.root.bind_all("c", lambda e: self.clear_current_events())
        self.root.bind_all("C", lambda e: self.clear_current_events())

        self.root.bind_all("p", lambda e: self.prev_video())
        self.root.bind_all("P", lambda e: self.prev_video())

        self.root.bind_all("n", lambda e: self.next_video())
        self.root.bind_all("N", lambda e: self.next_video())

        self.root.bind_all("<Control-s>", lambda e: self.save_csv())

    # =========================
    # 데이터셋 로드
    # =========================

    def load_default_dataset(self):
        if not self.base_dir.exists():
            messagebox.showwarning(
                "폴더 없음",
                f"기본 폴더를 찾을 수 없습니다:\n{self.base_dir}\n\n측면_수정본 폴더를 직접 선택하세요."
            )
            self.choose_base_folder()
            return

        self.scan_videos(self.base_dir)

    def choose_base_folder(self):
        folder = filedialog.askdirectory(title="측면_수정본 폴더 선택")

        if not folder:
            return

        self.base_dir = Path(folder)
        self.output_csv_path = self.base_dir / OUTPUT_CSV_NAME
        self.scan_videos(self.base_dir)

    def scan_videos(self, base_dir):
        self.save_current_to_memory()

        self.video_items = []

        for exercise_type in EXERCISE_TYPES:
            type_dir = base_dir / exercise_type

            if not type_dir.exists():
                continue

            for path in sorted(type_dir.iterdir()):
                if path.suffix.lower() in VIDEO_EXTS:
                    self.video_items.append({
                        "type": exercise_type,
                        "name": path.name,
                        "path": path
                    })

        if not self.video_items:
            messagebox.showerror(
                "영상 없음",
                f"영상 파일을 찾지 못했습니다.\n\n확인한 폴더:\n{base_dir}"
            )
            return

        self.video_idx = -1
        self.refresh_video_listbox()
        self.load_video_by_index(0)

    # =========================
    # 영상 목록 갱신
    # =========================

    def refresh_video_listbox(self):
        try:
            yview_pos = self.video_listbox.yview()[0]
        except Exception:
            yview_pos = 0.0

        current_idx = self.video_idx

        self.refreshing_video_list = True
        self.video_listbox.delete(0, tk.END)

        for i, item in enumerate(self.video_items):
            key = (item["type"], item["name"])
            label_count = len(self.annotations.get(key, []))
            rep_count = label_count // 3

            if label_count == 0:
                mark = ""
            elif label_count % 3 == 0:
                mark = "✓"
            else:
                mark = "!"

            text = f"{i + 1:03d}. [{item['type']}] {item['name']} | count={rep_count} {mark}"
            self.video_listbox.insert(tk.END, text)

        if 0 <= current_idx < len(self.video_items):
            self.video_listbox.selection_clear(0, tk.END)
            self.video_listbox.selection_set(current_idx)
            self.video_listbox.activate(current_idx)

        self.video_listbox.yview_moveto(yview_pos)
        self.refreshing_video_list = False

    def on_video_select(self, event):
        if self.refreshing_video_list:
            return

        selection = self.video_listbox.curselection()

        if not selection:
            return

        idx = selection[0]

        if idx != self.video_idx:
            self.load_video_by_index(idx)

    # =========================
    # 영상 로드
    # =========================

    def load_video_by_index(self, idx):
        if idx < 0 or idx >= len(self.video_items):
            return

        self.save_current_to_memory()
        self.playing = False
        self.update_play_button_text()

        if self.cap is not None:
            self.cap.release()

        self.video_idx = idx
        item = self.video_items[idx]
        video_path = item["path"]

        self.cap = cv2.VideoCapture(str(video_path))

        if not self.cap.isOpened():
            messagebox.showerror("오류", f"영상을 열 수 없습니다:\n{video_path}")
            return

        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps is None or self.fps <= 1:
            self.fps = 30

        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.current_frame_idx = 0

        seek_min = FRAME_INDEX_BASE
        seek_max = max(FRAME_INDEX_BASE, self.total_frames - 1 + FRAME_INDEX_BASE)
        self.seek_scale.config(from_=seek_min, to=seek_max)
        self.seek_var.set(seek_min)

        key = (item["type"], item["name"])
        self.current_events = list(self.annotations.get(key, []))

        self.refresh_video_listbox()
        self.show_frame(0)
        self.refresh_event_listbox()
        self.update_info_text()

    def save_current_to_memory(self):
        if 0 <= self.video_idx < len(self.video_items):
            item = self.video_items[self.video_idx]
            key = (item["type"], item["name"])
            self.annotations[key] = list(self.current_events)

    # =========================
    # 프레임 표시
    # =========================

    def show_frame(self, frame_idx):
        if self.cap is None:
            return

        if self.total_frames <= 0:
            return

        frame_idx = max(0, min(frame_idx, self.total_frames - 1))

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = self.cap.read()

        if not ret:
            return

        self.current_frame_idx = frame_idx

        self.render_frame(frame)
        self.update_info_text()
        self.update_seekbar()

    def render_frame(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        h, w = frame_rgb.shape[:2]

        scale = min(DISPLAY_W / w, DISPLAY_H / h)
        new_w = int(w * scale)
        new_h = int(h * scale)

        resized = cv2.resize(frame_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

        img = Image.fromarray(resized)
        imgtk = ImageTk.PhotoImage(image=img)

        self.video_label.imgtk = imgtk
        self.video_label.configure(image=imgtk)

    # =========================
    # 프레임 바
    # =========================

    def update_seekbar(self):
        if self.cap is None or self.total_frames <= 0:
            return

        self.slider_updating = True

        current_display = self.current_frame_idx + FRAME_INDEX_BASE
        total_display = self.total_frames - 1 + FRAME_INDEX_BASE

        self.seek_var.set(current_display)
        self.time_label.config(text=f"{current_display} / {total_display}")

        self.slider_updating = False

    def on_seek_drag(self, value):
        if self.slider_updating:
            return

        if self.cap is None:
            return

        try:
            display_frame = int(float(value))
        except ValueError:
            return

        internal_frame = display_frame - FRAME_INDEX_BASE
        internal_frame = max(0, min(internal_frame, self.total_frames - 1))

        self.playing = False
        self.update_play_button_text()
        self.show_frame(internal_frame)

    def on_seek_press(self, event):
        self.was_playing_before_seek = self.playing
        self.playing = False
        self.update_play_button_text()

    def on_seek_release(self, event):
        if self.cap is None:
            return

        display_frame = self.seek_var.get()
        internal_frame = display_frame - FRAME_INDEX_BASE
        internal_frame = max(0, min(internal_frame, self.total_frames - 1))

        self.show_frame(internal_frame)

        if self.was_playing_before_seek:
            self.playing = True
            self.update_play_button_text()
            self.play_loop()

    # =========================
    # 재생 / 이동
    # =========================

    def toggle_play(self):
        if self.cap is None:
            return

        self.playing = not self.playing
        self.update_play_button_text()

        if self.playing:
            self.play_loop()

    def update_play_button_text(self):
        if not hasattr(self, "play_button"):
            return

        if self.playing:
            self.play_button.config(text="⏸ 정지 [Space]")
        else:
            self.play_button.config(text="▶ 재생 [Space]")

    def play_loop(self):
        if not self.playing:
            self.update_play_button_text()
            return

        if self.current_frame_idx >= self.total_frames - 1:
            self.playing = False
            self.update_play_button_text()
            return

        self.show_frame(self.current_frame_idx + 1)

        delay = int(1000 / self.fps)
        delay = max(1, delay)

        self.root.after(delay, self.play_loop)

    def step_forward(self):
        self.playing = False
        self.update_play_button_text()
        self.show_frame(self.current_frame_idx + 1)

    def step_back(self):
        self.playing = False
        self.update_play_button_text()
        self.show_frame(self.current_frame_idx - 1)

    def jump_frames(self, n):
        self.playing = False
        self.update_play_button_text()
        self.show_frame(self.current_frame_idx + n)

    # =========================
    # 라벨 기록
    # =========================

    def get_expected_phase(self):
        return PHASES[len(self.current_events) % 3]

    def record_phase(self, phase):
        if self.cap is None:
            return

        expected = self.get_expected_phase()

        if phase != expected:
            ok = messagebox.askyesno(
                "라벨 순서 확인",
                f"다음 예상 라벨은 [{expected}] 입니다.\n"
                f"그래도 현재 프레임을 [{phase}]로 기록할까요?"
            )

            if not ok:
                return

        self.current_events.append((phase, self.current_frame_idx))
        self.save_current_to_memory()

        self.refresh_event_listbox()
        self.update_info_text()
        self.refresh_video_listbox()

    def undo_last(self):
        if not self.current_events:
            return

        self.current_events.pop()
        self.save_current_to_memory()

        self.refresh_event_listbox()
        self.update_info_text()
        self.refresh_video_listbox()

    def delete_selected_event(self):
        selection = self.event_listbox.curselection()

        if not selection:
            messagebox.showinfo("선택 없음", "삭제할 라벨을 선택하세요.")
            return

        idx = selection[0]
        del self.current_events[idx]
        self.save_current_to_memory()

        self.refresh_event_listbox()
        self.update_info_text()
        self.refresh_video_listbox()

    def update_selected_event_frame(self):
        selection = self.event_listbox.curselection()

        if not selection:
            messagebox.showinfo("선택 없음", "수정할 라벨을 선택하세요.")
            return

        idx = selection[0]
        phase, _ = self.current_events[idx]

        self.current_events[idx] = (phase, self.current_frame_idx)
        self.save_current_to_memory()

        self.refresh_event_listbox()
        self.event_listbox.selection_set(idx)
        self.event_listbox.see(idx)

        self.update_info_text()
        self.refresh_video_listbox()

    def clear_current_events(self):
        if not self.current_events:
            return

        ok = messagebox.askyesno(
            "전체 삭제 확인",
            "현재 영상의 라벨을 전부 삭제할까요?"
        )

        if not ok:
            return

        self.current_events = []
        self.save_current_to_memory()

        self.refresh_event_listbox()
        self.update_info_text()
        self.refresh_video_listbox()

    def refresh_event_listbox(self):
        self.event_listbox.delete(0, tk.END)

        for i, (phase, frame_idx) in enumerate(self.current_events):
            label_name = f"L{i + 1}"
            rep_no = i // 3 + 1
            saved_frame = frame_idx + FRAME_INDEX_BASE

            line = f"{label_name:>3} | rep {rep_no:>2} | {phase:<6} | frame = {saved_frame}"
            self.event_listbox.insert(tk.END, line)

    # =========================
    # 이전 / 다음 영상
    # =========================

    def next_video(self):
        if not self.video_items:
            return

        next_idx = self.video_idx + 1

        if next_idx >= len(self.video_items):
            messagebox.showinfo("끝", "마지막 영상입니다.")
            return

        self.load_video_by_index(next_idx)

    def prev_video(self):
        if not self.video_items:
            return

        prev_idx = self.video_idx - 1

        if prev_idx < 0:
            messagebox.showinfo("처음", "첫 번째 영상입니다.")
            return

        self.load_video_by_index(prev_idx)

    # =========================
    # CSV 저장 / 불러오기
    # =========================

    def save_csv(self):
        if not self.video_items:
            messagebox.showwarning("저장 불가", "불러온 영상이 없습니다.")
            return

        self.save_current_to_memory()

        rows = []
        max_labels = 0

        for item in self.video_items:
            key = (item["type"], item["name"])
            events = self.annotations.get(key, [])

            if len(events) == 0:
                continue

            max_labels = max(max_labels, len(events))

            row = {
                "type": item["type"],
                "name": item["name"],
                "count": len(events) // 3
            }

            for i, (_, frame_idx) in enumerate(events):
                row[f"L{i + 1}"] = frame_idx + FRAME_INDEX_BASE

            rows.append(row)

        if not rows:
            messagebox.showwarning("저장 불가", "저장할 라벨이 없습니다.")
            return

        fieldnames = ["type", "name", "count"] + [f"L{i + 1}" for i in range(max_labels)]

        with open(self.output_csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for row in rows:
                writer.writerow(row)

        messagebox.showinfo(
            "저장 완료",
            f"CSV 저장 완료:\n{self.output_csv_path}"
        )

    def load_csv(self):
        file_path = filedialog.askopenfilename(
            title="기존 라벨 CSV 선택",
            initialdir=str(self.base_dir) if self.base_dir.exists() else ".",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            return

        file_path = Path(file_path)

        loaded = {}

        with open(file_path, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            for row in reader:
                exercise_type = row.get("type", "").strip()
                name = row.get("name", "").strip()

                if not exercise_type or not name:
                    continue

                events = []
                i = 1

                while f"L{i}" in row:
                    value = row.get(f"L{i}", "")

                    if value is None or str(value).strip() == "":
                        i += 1
                        continue

                    try:
                        saved_frame = int(float(value))
                    except ValueError:
                        i += 1
                        continue

                    internal_frame = saved_frame - FRAME_INDEX_BASE
                    phase = PHASES[(i - 1) % 3]

                    events.append((phase, internal_frame))
                    i += 1

                loaded[(exercise_type, name)] = events

        self.annotations.update(loaded)
        self.output_csv_path = file_path

        if 0 <= self.video_idx < len(self.video_items):
            item = self.video_items[self.video_idx]
            key = (item["type"], item["name"])
            self.current_events = list(self.annotations.get(key, []))

        self.refresh_event_listbox()
        self.update_info_text()
        self.refresh_video_listbox()

        messagebox.showinfo(
            "불러오기 완료",
            f"CSV를 불러왔습니다:\n{file_path}"
        )

    # =========================
    # 정보 표시
    # =========================

    def get_current_item(self):
        if 0 <= self.video_idx < len(self.video_items):
            return self.video_items[self.video_idx]

        return None

    def update_info_text(self):
        item = self.get_current_item()

        if self.cap is None or item is None:
            self.info_label.config(text="영상을 불러오세요.")
            return

        saved_frame_no = self.current_frame_idx + FRAME_INDEX_BASE
        total_display = self.total_frames - 1 + FRAME_INDEX_BASE

        expected = self.get_expected_phase()

        text = (
            f"type: {item['type']}    |    "
            f"name: {item['name']}\n"
            f"현재 프레임: {saved_frame_no} / {total_display}    |    "
            f"FPS: {self.fps:.2f}    |    "
            f"다음 예상 라벨: {expected}\n"
            f"기록된 라벨 수: {len(self.current_events)}    |    "
            f"count: {len(self.current_events) // 3}    |    "
            f"CSV 저장 위치: {self.output_csv_path}"
        )

        self.info_label.config(text=text)


def main():
    root = tk.Tk()
    root.geometry("1650x900")

    app = PhaseLabeler(root)

    def on_close():
        app.save_current_to_memory()

        ok = messagebox.askyesnocancel(
            "종료",
            "종료하기 전에 CSV를 저장할까요?\n\n"
            "예: 저장 후 종료\n"
            "아니오: 저장하지 않고 종료\n"
            "취소: 종료 취소"
        )

        if ok is None:
            return

        if ok:
            app.save_csv()

        if app.cap is not None:
            app.cap.release()

        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()