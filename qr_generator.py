"""QR 코드 생성기 (투명 배경 PNG).

필요 패키지: pip install qrcode pillow
실행: python qr_generator.py
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import qrcode
from qrcode.exceptions import DataOverflowError
from PIL import Image, ImageDraw, ImageTk

AUTO = "자동"

ERROR_LEVELS = {
    "L (약 7% 복원)": qrcode.constants.ERROR_CORRECT_L,
    "M (약 15% 복원)": qrcode.constants.ERROR_CORRECT_M,
    "Q (약 25% 복원)": qrcode.constants.ERROR_CORRECT_Q,
}
DEFAULT_LEVEL = "M (약 15% 복원)"

COLORS = {"검은색": (0, 0, 0, 255), "흰색": (255, 255, 255, 255)}

PREVIEW_SIZE = 320


def app_dir():
    """스크립트(또는 exe)가 있는 폴더."""
    if getattr(sys, "frozen", False):  # PyInstaller로 만든 exe
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(name):
    """exe에 함께 묶인 파일(아이콘 등)의 경로."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def fit_version(data, level, version=None):
    """data가 들어가는 버전을 반환. version을 지정하면 그 버전에 들어가는지만 확인.

    들어가지 않으면 None.
    """
    qr = qrcode.QRCode(version=version, error_correction=level, border=0)
    qr.add_data(data)
    try:
        qr.make(fit=version is None)
    except (DataOverflowError, ValueError):
        return None
    return qr.version


def resolve_settings(data, level_choice, version_choice):
    """Version 선택값(자동 포함)을 실제 (level 이름, version)으로 확정한다.

    Version이 자동이면 선택한 Level로 들어가는 가장 작은 Version을 고른다.
    """
    version = None if version_choice == AUTO else int(version_choice)
    v = fit_version(data, ERROR_LEVELS[level_choice], version)
    if v is None:
        where = f"Version {version}" if version else "QR 코드 최대 용량(Version 40)"
        raise ValueError(f"입력 값이 너무 깁니다. Level {level_choice[0]}, {where} 에 들어가지 않습니다.")
    return level_choice, v


def make_qr_image(data, level_name, version, color, box_size, border):
    """투명 배경 RGBA QR 이미지를 만든다."""
    qr = qrcode.QRCode(
        version=version,
        error_correction=ERROR_LEVELS[level_name],
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=False)
    matrix = qr.get_matrix()  # border 포함

    size = len(matrix) * box_size
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for y, row in enumerate(matrix):
        for x, filled in enumerate(row):
            if filled:
                x0, y0 = x * box_size, y * box_size
                draw.rectangle([x0, y0, x0 + box_size - 1, y0 + box_size - 1], fill=color)
    return img


def checkerboard(size, cell=10):
    """투명 영역이 보이도록 미리보기용 체크무늬 배경."""
    bg = Image.new("RGBA", (size, size), (200, 200, 200, 255))
    draw = ImageDraw.Draw(bg)
    for y in range(0, size, cell):
        for x in range(0, size, cell):
            if (x // cell + y // cell) % 2 == 0:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(150, 150, 150, 255))
    return bg


class QRGeneratorApp:
    def __init__(self, root):
        self.root = root
        root.title("QR 코드 생성기")
        root.resizable(False, False)
        try:
            root.iconbitmap(default=resource_path("icon.ico"))
        except tk.TclError:
            pass  # 아이콘 파일이 없으면 기본 아이콘 사용

        self.current_image = None
        self.preview_photo = None
        self._after_id = None

        main = ttk.Frame(root, padding=12)
        main.grid(sticky="nsew")

        # --- 입력 ---
        ttk.Label(main, text="QR 값").grid(row=0, column=0, sticky="nw", pady=(0, 4))
        self.text = tk.Text(main, width=42, height=5, wrap="word")
        self.text.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.text.bind("<<Modified>>", self._on_text_modified)

        # --- 옵션 ---
        opts = ttk.Frame(main)
        opts.grid(row=2, column=0, columnspan=2, sticky="ew", pady=10)

        ttk.Label(opts, text="Correction Level").grid(row=0, column=0, sticky="w")
        self.level_var = tk.StringVar(value=DEFAULT_LEVEL)
        ttk.Combobox(
            opts, textvariable=self.level_var, state="readonly", width=18,
            values=list(ERROR_LEVELS),
        ).grid(row=0, column=1, sticky="w", padx=6, pady=3)

        ttk.Label(opts, text="Version (복잡도)").grid(row=1, column=0, sticky="w")
        self.version_var = tk.StringVar(value=AUTO)
        ttk.Combobox(
            opts, textvariable=self.version_var, state="readonly", width=18,
            values=[AUTO] + [str(v) for v in range(1, 41)],
        ).grid(row=1, column=1, sticky="w", padx=6, pady=3)

        ttk.Label(opts, text="QR 색상").grid(row=2, column=0, sticky="w")
        self.color_var = tk.StringVar(value="검은색")
        color_frame = ttk.Frame(opts)
        color_frame.grid(row=2, column=1, sticky="w", padx=6, pady=3)
        for name in COLORS:
            ttk.Radiobutton(color_frame, text=name, value=name, variable=self.color_var).pack(
                side="left", padx=(0, 10)
            )

        ttk.Label(opts, text="모듈 크기(px)").grid(row=3, column=0, sticky="w")
        self.box_var = tk.IntVar(value=10)
        ttk.Spinbox(opts, from_=1, to=50, textvariable=self.box_var, width=6).grid(
            row=3, column=1, sticky="w", padx=6, pady=3
        )

        ttk.Label(opts, text="여백(모듈 수)").grid(row=4, column=0, sticky="w")
        self.border_var = tk.IntVar(value=4)
        ttk.Spinbox(opts, from_=0, to=20, textvariable=self.border_var, width=6).grid(
            row=4, column=1, sticky="w", padx=6, pady=3
        )

        for var in (self.level_var, self.version_var, self.color_var, self.box_var, self.border_var):
            var.trace_add("write", lambda *_: self.schedule_update())

        # --- 상태 표시 ---
        self.status_var = tk.StringVar(value="QR 값을 입력하세요.")
        ttk.Label(main, textvariable=self.status_var, foreground="#335").grid(
            row=3, column=0, columnspan=2, sticky="w"
        )

        # --- 미리보기 ---
        self.preview = tk.Label(main, width=PREVIEW_SIZE, height=PREVIEW_SIZE, relief="sunken")
        self.preview.grid(row=4, column=0, columnspan=2, pady=10)

        # --- 저장 ---
        ttk.Button(main, text="PNG로 저장", command=self.save).grid(
            row=5, column=0, columnspan=2, sticky="ew"
        )

        self.update_preview()

    def _on_text_modified(self, _event):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.schedule_update()

    def schedule_update(self):
        if self._after_id:
            self.root.after_cancel(self._after_id)
        self._after_id = self.root.after(200, self.update_preview)

    def get_data(self):
        return self.text.get("1.0", "end-1c")

    def build_image(self):
        """현재 설정으로 이미지를 생성. (image, level_name, version) 반환."""
        data = self.get_data()
        if not data:
            return None, None, None
        try:
            box = int(self.box_var.get())
            border = int(self.border_var.get())
        except (tk.TclError, ValueError):
            raise ValueError("모듈 크기와 여백은 숫자로 입력하세요.")
        if box < 1 or border < 0:
            raise ValueError("모듈 크기는 1 이상, 여백은 0 이상이어야 합니다.")

        level_name, version = resolve_settings(data, self.level_var.get(), self.version_var.get())
        img = make_qr_image(data, level_name, version, COLORS[self.color_var.get()], box, border)
        return img, level_name, version

    def update_preview(self):
        self._after_id = None
        bg = checkerboard(PREVIEW_SIZE)
        try:
            img, level_name, version = self.build_image()
        except ValueError as e:
            self.current_image = None
            self.status_var.set(f"⚠ {e}")
            self._show(bg)
            return

        self.current_image = img
        if img is None:
            self.status_var.set("QR 값을 입력하세요.")
            self._show(bg)
            return

        suffix = "  (Version 자동)" if self.version_var.get() == AUTO else ""
        modules = 17 + 4 * version
        self.status_var.set(
            f"Level {level_name[0]} / Version {version} ({modules}x{modules})"
            f" / {img.width}x{img.height}px{suffix}"
        )

        preview = img.resize((PREVIEW_SIZE, PREVIEW_SIZE), Image.NEAREST)
        bg.alpha_composite(preview)
        self._show(bg)

    def _show(self, img):
        self.preview_photo = ImageTk.PhotoImage(img)
        self.preview.configure(image=self.preview_photo, width=PREVIEW_SIZE, height=PREVIEW_SIZE)

    def save(self):
        if self._after_id:  # 대기 중인 갱신을 먼저 반영
            self.root.after_cancel(self._after_id)
            self.update_preview()
        if self.current_image is None:
            messagebox.showwarning("저장 불가", self.status_var.get())
            return
        path = filedialog.asksaveasfilename(
            title="QR 코드 저장",
            defaultextension=".png",
            filetypes=[("PNG 이미지", "*.png")],
            initialdir=app_dir(),
            initialfile="qrcode.png",
        )
        if not path:
            return
        self.current_image.save(path, "PNG")
        messagebox.showinfo("저장 완료", f"저장했습니다:\n{path}")


def main():
    root = tk.Tk()
    QRGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
