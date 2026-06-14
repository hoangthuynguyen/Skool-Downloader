#!/usr/bin/env python3
"""
Giao dien (GUI) cho Skool Archiver - bam nut thay vi go lenh.
Chay: double-click GiaoDien.cmd (o thu muc Archiver).
"""
import os, sys, queue, threading, subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C

HERE = Path(__file__).resolve().parent                 # ...\Archiver\app
ARCHIVER = HERE.parent
PY = sys.executable.replace("pythonw.exe", "python.exe")  # dung python.exe cho subprocess
NO_WIN = 0x08000000 if os.name == "nt" else 0          # CREATE_NO_WINDOW
SENTINEL = "\x00__DONE__\x00"

def find_guide():
    d = ARCHIVER / "docs"
    for n in ("SkoolArchiver_Huong_Dan_Su_Dung_2_Cach.docx",):
        if (d / n).exists(): return d / n
    return d

class App:
    def __init__(self, root):
        self.root = root
        self.proc = None
        self.q = queue.Queue()
        root.title("Skool Archiver")
        root.geometry("780x560")
        root.minsize(680, 480)

        pad = {"padx": 8, "pady": 4}
        top = ttk.Frame(root); top.pack(fill="x", **pad)

        ttk.Label(top, text="Khóa:").grid(row=0, column=0, sticky="w")
        self.course_var = tk.StringVar()
        self.course_cb = ttk.Combobox(top, textvariable=self.course_var, width=42)
        self.course_cb.grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(top, text="↻", width=3, command=self.refresh_courses).grid(row=0, column=2)
        top.columnconfigure(1, weight=1)

        opt = ttk.Frame(root); opt.pack(fill="x", **pad)
        self.transcribe = tk.BooleanVar(value=False)
        self.dryrun = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="Kèm phụ đề (Whisper)", variable=self.transcribe).pack(side="left", padx=4)
        ttk.Checkbutton(opt, text="Chạy thử (không tải)", variable=self.dryrun).pack(side="left", padx=4)

        b1 = ttk.Frame(root); b1.pack(fill="x", **pad)
        self.btn_run = ttk.Button(b1, text="▶  Tải khóa", command=self.do_run)
        self.btn_run.pack(side="left", padx=4)
        self.btn_audit = ttk.Button(b1, text="🔍  Kiểm tra (audit)", command=self.do_audit)
        self.btn_audit.pack(side="left", padx=4)
        self.btn_stop = ttk.Button(b1, text="■  Dừng", command=self.do_stop, state="disabled")
        self.btn_stop.pack(side="left", padx=4)

        b2 = ttk.Frame(root); b2.pack(fill="x", **pad)
        self.btn_subon = ttk.Button(b2, text="🗒  Bật phụ đề chạy ngầm", command=self.do_sub_on)
        self.btn_subon.pack(side="left", padx=4)
        self.btn_suboff = ttk.Button(b2, text="✖  Tắt phụ đề ngầm", command=self.do_sub_off)
        self.btn_suboff.pack(side="left", padx=4)
        ttk.Button(b2, text="📁  Mở thư mục khóa", command=self.open_folder).pack(side="left", padx=4)
        ttk.Button(b2, text="❓  Hướng dẫn", command=self.open_guide).pack(side="left", padx=4)

        st = ttk.Frame(root); st.pack(fill="x", **pad)
        self.status = tk.StringVar(value="—")
        ttk.Label(st, textvariable=self.status, font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Button(st, text="Làm mới", command=self.refresh_status).pack(side="right")

        self.log = scrolledtext.ScrolledText(root, wrap="word", height=18, font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.log.configure(state="disabled")

        self.refresh_courses()
        self.refresh_status()
        self.root.after(120, self.poll)
        self.root.after(5000, self.auto_status)

    # ---------- helpers ----------
    def selected_course(self):
        v = self.course_var.get().strip()
        if not v or v.startswith("SkoolCourse"):
            return None
        return v

    def course_root(self):
        c = self.selected_course()
        return (C.BASE / "SkoolCourse") if not c else (C.BASE / "courses" / c)

    def course_args(self):
        c = self.selected_course()
        return ["--course", c] if c else []

    def refresh_courses(self):
        items = ["SkoolCourse (khóa hiện tại)"]
        cdir = C.BASE / "courses"
        if cdir.exists():
            items += sorted(p.name for p in cdir.iterdir() if p.is_dir())
        self.course_cb["values"] = items
        if not self.course_var.get():
            self.course_var.set(items[0])

    def counts(self):
        root = self.course_root()
        if not root.exists():
            return 0, 0
        vids = sum(1 for p in root.rglob("video.*")
                   if p.suffix.lower() in C.VIDEXT and p.stem == "video")
        txt = sum(1 for _ in root.rglob("video.txt"))
        return vids, txt

    def refresh_status(self):
        v, t = self.counts()
        name = self.selected_course() or "SkoolCourse"
        busy = " · ĐANG CHẠY" if self.proc else ""
        self.status.set(f"[{name}]   Video đã tải: {v}   |   Phụ đề: {t}{busy}")

    def auto_status(self):
        self.refresh_status()
        self.root.after(5000, self.auto_status)

    def write(self, s):
        self.log.configure(state="normal")
        self.log.insert("end", s)
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_busy(self, busy):
        for b in (self.btn_run, self.btn_audit, self.btn_subon, self.btn_suboff):
            b.configure(state="disabled" if busy else "normal")
        self.btn_stop.configure(state="normal" if busy else "disabled")

    # ---------- chay tien trinh ----------
    def start(self, cmd, title, cwd=None):
        if self.proc:
            messagebox.showinfo("Đang bận", "Một tác vụ đang chạy. Bấm Dừng trước.")
            return
        self.write(f"\n===== {title} =====\n$ {' '.join(str(c) for c in cmd)}\n")
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        try:
            self.proc = subprocess.Popen(cmd, cwd=cwd or HERE, env=env,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, encoding="utf-8", errors="replace",
                                         bufsize=1, creationflags=NO_WIN)
        except Exception as e:
            self.write(f"[LỖI khởi chạy] {e}\n"); self.proc = None; return
        self.set_busy(True)
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        for line in self.proc.stdout:
            self.q.put(line)
        self.proc.wait()
        self.q.put(SENTINEL)

    def poll(self):
        try:
            while True:
                s = self.q.get_nowait()
                if s == SENTINEL:
                    rc = self.proc.returncode if self.proc else 0
                    self.write(f"\n--- Kết thúc (mã {rc}) ---\n")
                    self.proc = None
                    self.set_busy(False)
                    self.refresh_status()
                else:
                    self.write(s)
        except queue.Empty:
            pass
        self.root.after(120, self.poll)

    def do_stop(self):
        if self.proc:
            try: self.proc.terminate()
            except Exception: pass
            self.write("\n[Đã yêu cầu dừng]\n")

    # ---------- nut ----------
    def do_run(self):
        args = self.course_args()
        if self.transcribe.get(): args.append("--transcribe")
        if self.dryrun.get(): args.append("--dry-run")
        self.start([PY, "main.py"] + args, "TẢI KHÓA")

    def do_audit(self):
        self.start([PY, "main.py"] + self.course_args() + ["--only", "audit"], "KIỂM TRA (AUDIT)")

    def do_sub_on(self):
        c = self.selected_course()
        ps = HERE / "install_transcribe_task.ps1"
        extra = ["-Course", c] if c else ["-All"]
        self.start(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ps)] + extra, "BẬT PHỤ ĐỀ NGẦM")

    def do_sub_off(self):
        ps = HERE / "uninstall_transcribe_task.ps1"
        self.start(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ps)], "TẮT PHỤ ĐỀ NGẦM")

    def open_folder(self):
        r = self.course_root()
        r.mkdir(parents=True, exist_ok=True)
        try: os.startfile(str(r))
        except Exception as e: messagebox.showerror("Lỗi", str(e))

    def open_guide(self):
        g = find_guide()
        try: os.startfile(str(g))
        except Exception as e: messagebox.showerror("Lỗi", str(e))

def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except Exception:
        pass
    App(root)
    if os.environ.get("GUI_SMOKE_TEST"):   # test: dung sau 800ms
        root.after(800, root.destroy)
    root.mainloop()

if __name__ == "__main__":
    main()
