#!/usr/bin/env python3
"""
Giao dien (GUI) wizard cho Skool Archiver - tung buoc, danh cho NGUOI DUNG.
Mo bang: double-click GiaoDien.cmd
"""
import os, sys, re, time, queue, threading, subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C

HERE = Path(__file__).resolve().parent
ARCHIVER = HERE.parent
PY = sys.executable.replace("pythonw.exe", "python.exe")
NO_WIN = 0x08000000 if os.name == "nt" else 0
SENTINEL = "\x00DONE\x00"

# ===== bang mau =====
BG = "#f4f6f9"; HEADER = "#1F4E79"; CARD = "#ffffff"
PRIMARY = "#2E75B6"; PRIM_DK = "#1F4E79"; ACCENT = "#ffd24d"
SUCCESS = "#1e7e34"; WARNING = "#e0a800"; DANGER = "#b02a37"
TEXT = "#1a1a1a"; TEXT2 = "#6b6b6b"; BORDER = "#dddddd"; TROUGH = "#E8F0F8"
FT = "Segoe UI"
BTN = {"primary": (PRIMARY, PRIM_DK), "success": (SUCCESS, "#14632a"),
       "danger": (DANGER, "#8f2230"), "secondary": (TEXT2, "#555555"),
       "dark": (PRIM_DK, "#143a5c"), "warn": (WARNING, "#b88a00")}

def big_btn(parent, text, cmd, variant="primary", **kw):
    bg, hov = BTN.get(variant, BTN["primary"])
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg="white",
                     activebackground=hov, activeforeground="white",
                     font=(FT, 11, "bold"), relief="flat", bd=0, padx=16, pady=9,
                     cursor="hand2", **kw)

def ghost(parent, text, cmd):
    return tk.Button(parent, text=text, command=cmd, bg=BG, fg=PRIMARY,
                     activebackground=BG, activeforeground=PRIM_DK,
                     font=(FT, 10, "bold"), relief="flat", bd=0, padx=10, pady=6, cursor="hand2")

def mk_card(parent):
    c = tk.Frame(parent, bg=CARD, relief="solid", bd=1,
                 highlightbackground=BORDER, highlightthickness=0)
    c.pack(fill="x", pady=6)
    return c

def fmt_size(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB": return f"{n:.1f} {u}" if u != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"

ICON = {"done": ("✓", SUCCESS), "loading": ("⏳", WARNING), "pending": ("○", TEXT2)}


class App:
    def __init__(self, root):
        self.root = root
        self.proc = None
        self.sb = None
        self.q = queue.Queue()
        self.chapters = []
        self.course_name = None
        self.mode = None
        self.admin = False
        self._dumping = False
        self._prog = []
        self._lastref = 0.0

        root.title("Skool Archiver")
        root.geometry("820x720"); root.minsize(740, 640)
        root.configure(bg=BG)
        st = ttk.Style()
        try: st.theme_use("clam")
        except Exception: pass
        st.configure("Skool.Horizontal.TProgressbar", troughcolor=TROUGH,
                     background=PRIMARY, bordercolor=TROUGH, lightcolor=PRIMARY, darkcolor=PRIMARY, thickness=16)
        st.configure("Mini.Horizontal.TProgressbar", troughcolor=TROUGH,
                     background=PRIMARY, bordercolor=TROUGH, lightcolor=PRIMARY, darkcolor=PRIMARY, thickness=7)

        head = tk.Frame(root, bg=HEADER, height=64); head.pack(fill="x"); head.pack_propagate(False)
        tk.Label(head, text="  📦  Skool Archiver", bg=HEADER, fg="white", font=(FT, 16, "bold")).pack(side="left", pady=12)
        self.step_lbl = tk.Label(head, text="", bg=HEADER, fg="#cfe0f3", font=(FT, 10)); self.step_lbl.pack(side="right", padx=16)
        self.badge = tk.Label(head, text="", bg=HEADER, fg=ACCENT, font=(FT, 10, "bold")); self.badge.pack(side="right", padx=4)
        root.bind_all("<Control-Alt-t>", self.toggle_admin)
        root.bind_all("<Control-Alt-T>", self.toggle_admin)

        self.body = tk.Frame(root, bg=BG); self.body.pack(fill="both", expand=True, padx=18, pady=12)

        logf = tk.Frame(root, bg=BG); logf.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(logf, text="Nhật ký", bg=BG, fg=TEXT2, font=(FT, 9, "bold")).pack(anchor="w")
        self.log = scrolledtext.ScrolledText(logf, height=7, font=("Consolas", 9), relief="solid", bd=1)
        self.log.pack(fill="x"); self.log.configure(state="disabled")

        self.show_step1()
        self.root.after(120, self.poll)

    # ---------- tien ich ----------
    def clear_body(self):
        for w in self.body.winfo_children(): w.destroy()

    def set_step(self, n, name):
        self.step_lbl.config(text=f"Bước {n}/4  ·  {name}")

    def toggle_admin(self, *_):
        self.admin = not self.admin
        self.badge.config(text="🔧 TEST MODE" if self.admin else "")
        self.write("== Chế độ TEST: BẬT (tải sẽ KHÔNG tải thật, chỉ kiểm tra) ==" if self.admin
                   else "== Chế độ TEST: TẮT ==")

    def title(self, text, sub=""):
        tk.Label(self.body, text=text, bg=BG, fg=PRIM_DK, font=(FT, 15, "bold")).pack(anchor="w")
        if sub:
            tk.Label(self.body, text=sub, bg=BG, fg=TEXT2, font=(FT, 10), justify="left", wraplength=740).pack(anchor="w", pady=(2, 10))

    def write(self, s):
        if not s.endswith("\n"): s += "\n"
        self.log.configure(state="normal"); self.log.insert("end", s)
        self.log.see("end"); self.log.configure(state="disabled")

    def course_root(self, name=None):
        name = name or self.course_name
        if not name or str(name).startswith("SkoolCourse"):
            return C.BASE / "SkoolCourse"
        return C.BASE / "courses" / name

    def existing_courses(self):
        items = []
        if (C.BASE / "SkoolCourse").exists(): items.append("SkoolCourse (đã có sẵn)")
        cdir = C.BASE / "courses"
        if cdir.exists(): items += sorted(p.name for p in cdir.iterdir() if p.is_dir())
        return items

    # ---------- tinh tien do theo chuong (tu JSON) ----------
    def _video_in(self, folder):
        for ext in C.VIDEXT:
            p = folder / ("video" + ext)
            try:
                if p.exists() and p.stat().st_size > 0: return p
            except OSError: pass
        return None

    def build_progress(self):
        """Doc vid_*.json cua khoa -> ke hoach: moi chuong + danh sach folder bai co video."""
        import json, common as K
        self._prog = []
        root = self.course_root()
        if not root.exists(): return
        def chap_folder(ct):
            for d in sorted([p for p in root.iterdir() if p.is_dir()]):
                nm = d.name.split(" - ", 1)[-1] if " - " in d.name else d.name
                if nm == ct: return d
            return None
        def cu(ns):
            c = 0
            for n in ns: c += (1 if n.get("url") else 0) + cu(n.get("children") or [])
            return c
        best = {}
        for f in sorted(root.rglob("vid_*.json")):
            try: d = json.loads(f.read_bytes().decode("utf-8-sig"))
            except Exception: continue
            if isinstance(d, dict): d = [d]
            course = K.one_chapter(d); ct = K.san(course["title"]); sc = cu(course.get("children") or [])
            if ct not in best or sc > best[ct][0]: best[ct] = (sc, course)
        for ct, (sc, course) in sorted(best.items()):
            chap = chap_folder(ct)
            if not chap: continue
            lessons = [folder for folder, n in K.walk(course.get("children") or [], chap) if n.get("url")]
            self._prog.append({"name": chap.name, "lessons": lessons})

    def scan_progress(self):
        rows = []; dtot = etot = 0; size = 0
        for ch in self._prog:
            done = 0
            for folder in ch["lessons"]:
                v = self._video_in(folder)
                if v:
                    done += 1
                    try: size += v.stat().st_size
                    except OSError: pass
            exp = len(ch["lessons"])
            stt = "done" if (exp and done >= exp) else ("loading" if done > 0 else "pending")
            rows.append({"name": ch["name"], "done": done, "exp": exp, "status": stt})
            dtot += done; etot += exp
        return rows, dtot, etot, size

    # ====================== KIỂM TRA MÔI TRƯỜNG ======================
    def _ffmpeg_ok(self):
        import shutil
        if shutil.which("ffmpeg"): return True
        try:
            import ffmpeg_downloader as ffdl
            return bool(getattr(ffdl, "ffmpeg_path", None))
        except Exception:
            return False

    def _chromium_ok(self):
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        try: return base.exists() and any(base.glob("chromium-*"))
        except Exception: return False

    def check_env(self):
        import shutil, importlib.util
        def has(m): return importlib.util.find_spec(m) is not None
        sc = Path(PY).parent
        items = [("Python", True, f"{sys.version_info.major}.{sys.version_info.minor}", None)]
        node = shutil.which("node")
        items.append(("Node.js (cho YouTube)", bool(node), node or "thiếu", None if node else ("Tải Node.js", "node")))
        ff = self._ffmpeg_ok()
        items.append(("ffmpeg", ff, "OK" if ff else "thiếu", None if ff else ("Cài ffmpeg", [str(sc / "ffdl.exe"), "install", "--add-path"])))
        for mod, label, pn in [("yt_dlp", "yt-dlp", "yt-dlp"), ("faster_whisper", "faster-whisper", "faster-whisper"), ("playwright", "Playwright", "playwright")]:
            ok = has(mod)
            items.append((label, ok, "OK" if ok else "thiếu", None if ok else (f"Cài {label}", [PY, "-m", "pip", "install", "-U", pn])))
        ch = self._chromium_ok()
        items.append(("Trình duyệt Chromium", ch, "OK" if ch else "thiếu", None if ch else ("Cài Chromium", [PY, "-m", "playwright", "install", "chromium"])))
        return items

    def env_missing(self):
        return [i for i in self.check_env() if not i[1]]

    def show_check(self):
        self.set_step(1, "Kiểm tra môi trường"); self.clear_body()
        self.title("Kiểm tra môi trường", "App cần các thành phần dưới đây. Cái nào thiếu có nút cài ngay bên cạnh (Node.js phải tải tay rồi mở lại app).")
        items = self.check_env()
        card = mk_card(self.body)
        for name, ok, detail, fix in items:
            row = tk.Frame(card, bg=CARD); row.pack(fill="x", padx=12, pady=5)
            tk.Label(row, text=("✓" if ok else "✗"), fg=(SUCCESS if ok else DANGER), bg=CARD, font=(FT, 13, "bold"), width=2).pack(side="left")
            tk.Label(row, text=f"  {name}", bg=CARD, fg=TEXT, font=(FT, 11), width=24, anchor="w").pack(side="left")
            tk.Label(row, text=detail, bg=CARD, fg=TEXT2, font=(FT, 9)).pack(side="left")
            if (not ok) and fix:
                big_btn(row, fix[0], (lambda p=fix[1]: self.do_fix(p)), variant="primary").pack(side="right")
        row = tk.Frame(self.body, bg=BG); row.pack(fill="x", pady=12)
        ghost(row, "←  Quay lại", self.show_step1).pack(side="left")
        ghost(row, "↻  Kiểm tra lại", self.show_check).pack(side="left", padx=6)
        if [i for i in items if not i[1] and i[3]]:
            big_btn(row, "⚙  Cài tất cả còn thiếu", self.fix_all, variant="dark").pack(side="right")

    def do_fix(self, payload):
        import webbrowser
        if payload == "node":
            webbrowser.open("https://nodejs.org/en/download")
            messagebox.showinfo("Node.js", "Tải bản LTS, cài xong rồi MỞ LẠI app.")
        else:
            self.start(payload, "CÀI ĐẶT", on_done=self.show_check)

    def fix_all(self):
        import webbrowser
        cmds = []
        for name, ok, detail, fix in self.check_env():
            if ok or not fix: continue
            if fix[1] == "node": webbrowser.open("https://nodejs.org/en/download")
            else: cmds.append(fix[1])
        self._fix_queue = cmds
        self.write("Đang cài các thành phần còn thiếu..."); self._run_next_fix()

    def _run_next_fix(self):
        if not getattr(self, "_fix_queue", None):
            self.show_check(); return
        self.start(self._fix_queue.pop(0), "CÀI ĐẶT", on_done=self._run_next_fix)

    # ====================== BƯỚC 1 ======================
    def show_step1(self):
        self.set_step(1, "Chọn khóa"); self.clear_body()
        self.title("Bạn muốn tải khóa nào?", "Chọn một khóa đã có sẵn bên dưới, hoặc thêm khóa mới trực tiếp từ tài khoản Skool của bạn.")
        try: miss = self.env_missing()
        except Exception: miss = []
        if miss:
            ban = tk.Frame(self.body, bg="#fff3cd", relief="solid", bd=1); ban.pack(fill="x", pady=(0, 8))
            tk.Label(ban, text="⚠  Thiếu: " + ", ".join(m[0].split(" (")[0] for m in miss), bg="#fff3cd", fg="#8a6d00", font=(FT, 10, "bold")).pack(side="left", padx=10, pady=6)
            big_btn(ban, "Kiểm tra & cài", self.show_check, variant="warn").pack(side="right", padx=6, pady=4)
        items = self.existing_courses()
        card = mk_card(self.body)
        if items:
            tk.Label(card, text="Khóa đã có:", bg=CARD, fg=TEXT2, font=(FT, 10)).pack(anchor="w", padx=12, pady=(10, 2))
            self.pick_var = tk.StringVar(value=items[0])
            for it in items:
                tk.Radiobutton(card, text="   " + it, variable=self.pick_var, value=it, bg=CARD, font=(FT, 11), anchor="w", selectcolor=CARD, activebackground=CARD).pack(fill="x", padx=12)
            tk.Frame(card, bg=CARD, height=8).pack()
        else:
            tk.Label(card, text="(Chưa có khóa nào — hãy thêm khóa mới)", bg=CARD, fg=TEXT2, font=(FT, 10, "italic")).pack(padx=12, pady=12)
            self.pick_var = tk.StringVar(value="")
        row = tk.Frame(self.body, bg=BG); row.pack(fill="x", pady=14)
        big_btn(row, "➕  Thêm khóa mới từ Skool", self.go_import, variant="dark").pack(side="left")
        if items:
            big_btn(row, "Tiếp tục khóa đã chọn  →", self.use_existing, variant="primary").pack(side="right")
        foot = tk.Frame(self.body, bg=BG); foot.pack(side="bottom", fill="x", pady=6)
        ghost(foot, "⚙  Kiểm tra môi trường", self.show_check).pack(side="left")

    def use_existing(self):
        v = self.pick_var.get().strip()
        if not v: return
        self.mode = "existing"
        self.course_name = None if v.startswith("SkoolCourse") else v
        self.show_step3()

    def go_import(self):
        self.mode = "new"; self.show_step2()

    # ====================== BƯỚC 2 ======================
    def show_step2(self):
        self.set_step(2, "Lấy khóa từ Skool"); self.clear_body()
        self.title("Lấy khóa mới từ Skool", "Làm theo 3 nút dưới đây. App sẽ mở một cửa sổ trình duyệt riêng — bạn đăng nhập và mở đúng khóa, app tự lấy danh sách.")
        f = tk.Frame(self.body, bg=BG); f.pack(fill="x", pady=4)
        self.b_open = big_btn(f, "1.  Mở Skool & đăng nhập", self.do_open, variant="dark"); self.b_open.pack(fill="x", pady=4)
        self.b_list = big_btn(f, "2.  Lấy danh sách chương", self.do_list, variant="primary"); self.b_list.pack(fill="x", pady=4); self.b_list.config(state="disabled")
        self.chap_box = tk.Frame(self.body, bg=CARD, relief="solid", bd=1)
        self.dump_row = tk.Frame(self.body, bg=BG)
        back = tk.Frame(self.body, bg=BG); back.pack(side="bottom", fill="x", pady=8)
        ghost(back, "←  Quay lại", self.show_step1).pack(side="left")

    def do_open(self):
        if self.sb is None:
            self.write("Đang mở trình duyệt (lần đầu hơi lâu)...")
            try:
                from skool_browser import SkoolBrowser
                self.sb = SkoolBrowser()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không mở được trình duyệt: {e}"); return
        else:
            self.sb.open()

    def do_list(self):
        if self.sb: self.write("Đang đọc danh sách chương từ trang hiện tại..."); self.sb.list_chapters()

    def render_chapters(self, group, chapters):
        for w in self.chap_box.winfo_children(): w.destroy()
        for w in self.dump_row.winfo_children(): w.destroy()
        self.chap_box.pack(fill="both", expand=True, pady=8); self.dump_row.pack(fill="x", pady=4)
        tk.Label(self.chap_box, text=f"Khóa: {group} — chọn chương cần tải:", bg=CARD, fg=PRIM_DK, font=(FT, 10, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        canvas = tk.Canvas(self.chap_box, bg=CARD, height=170, highlightthickness=0)
        sb = ttk.Scrollbar(self.chap_box, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=CARD)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw"); canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=6); sb.pack(side="right", fill="y")
        self.chapters = []
        for c in chapters:
            var = tk.BooleanVar(value=True)
            tk.Checkbutton(inner, text="  " + c["title"], variable=var, bg=CARD, font=(FT, 10), anchor="w", selectcolor=CARD, activebackground=CARD).pack(fill="x", anchor="w")
            self.chapters.append({"id": c["id"], "title": c["title"], "var": var})
        nm = tk.Frame(self.dump_row, bg=BG); nm.pack(fill="x")
        tk.Label(nm, text="Đặt tên khóa:", bg=BG, font=(FT, 10)).pack(side="left")
        self.name_var = tk.StringVar(value=group)
        tk.Entry(nm, textvariable=self.name_var, font=(FT, 11), width=30).pack(side="left", padx=8)
        self.b_dump = big_btn(self.dump_row, "3.  Tải dữ liệu các chương đã chọn  →", self.do_dump, variant="dark"); self.b_dump.pack(pady=8)
        self.dump_status = tk.Label(self.dump_row, text="", bg=BG, fg=PRIM_DK, font=(FT, 10, "bold")); self.dump_status.pack()
        self.dump_pb = ttk.Progressbar(self.dump_row, style="Skool.Horizontal.TProgressbar", maximum=100, length=420)

    def do_dump(self):
        if self._dumping: return
        sel = [c for c in self.chapters if c["var"].get()]
        if not sel: messagebox.showinfo("Chưa chọn", "Hãy tick ít nhất 1 chương."); return
        name = self.name_var.get().strip()
        if not name: messagebox.showinfo("Thiếu tên", "Hãy đặt tên khóa."); return
        self.course_name = name; self._dumping = True
        self.b_dump.config(state="disabled", text="⏳  Đang lấy dữ liệu...")
        self.dump_status.config(text=f"Đang lấy dữ liệu: 0/{len(sel)} chương")
        self.dump_pb.pack(pady=(0, 6)); self.dump_pb["value"] = 0
        out = C.BASE / "courses" / name
        self.write(f"Đang lấy dữ liệu {len(sel)} chương vào: {out}")
        self.sb.dump([{"id": c["id"], "title": c["title"]} for c in sel], out)

    # ====================== BƯỚC 3 ======================
    def show_step3(self):
        self.set_step(3, "Tùy chọn"); self.clear_body()
        nm = self.course_name or "SkoolCourse (khóa hiện tại)"
        self.title(f"Sẵn sàng tải: {nm}", "Bấm Bắt đầu để tải toàn bộ video + tài liệu. Có thể bật tạo phụ đề tiếng Anh chạy ngầm sau khi tải.")
        card = mk_card(self.body)
        self.opt_sub = tk.BooleanVar(value=True)
        tk.Checkbutton(card, text="  Tạo phụ đề tiếng Anh (chạy ngầm sau khi tải xong)", variable=self.opt_sub, bg=CARD, font=(FT, 11), selectcolor=CARD, activebackground=CARD).pack(anchor="w", padx=12, pady=10)
        self.opt_test = tk.BooleanVar(value=self.admin)
        if self.admin:
            tk.Checkbutton(card, text="  🔧 Chế độ TEST — chỉ kiểm tra, KHÔNG tải thật (dry-run)", variable=self.opt_test, bg=CARD, fg="#9a6700", font=(FT, 11, "bold"), selectcolor=CARD, activebackground=CARD).pack(anchor="w", padx=12, pady=(0, 10))
        row = tk.Frame(self.body, bg=BG); row.pack(fill="x", pady=16)
        ghost(row, "←  Quay lại", self.show_step1).pack(side="left")
        big_btn(row, "▶  Bắt đầu tải", self.start_download, variant="success").pack(side="right")

    # ====================== BƯỚC 4 ======================
    def show_step4(self):
        self.set_step(4, "Đang tải"); self.clear_body()
        self.title("Đang tải khóa…", "Theo dõi tiến trình bên dưới. Bạn có thể bấm Dừng bất cứ lúc nào (chạy lại sẽ tiếp tục), hoặc mở thư mục xem ngay không cần chờ.")
        self.build_progress()
        # --- tong quan ---
        ov = mk_card(self.body)
        tk.Label(ov, text=f"Khóa: {self.course_name or 'SkoolCourse'}", bg=CARD, fg=PRIM_DK, font=(FT, 11, "bold")).pack(anchor="w", padx=14, pady=(10, 0))
        b = tk.Frame(ov, bg=CARD); b.pack(fill="x", padx=14, pady=(2, 12))
        self.pct_lbl = tk.Label(b, text="0%", bg=CARD, fg=PRIM_DK, font=(FT, 30, "bold")); self.pct_lbl.pack(side="left")
        r = tk.Frame(b, bg=CARD); r.pack(side="left", fill="x", expand=True, padx=16)
        self.pb4 = ttk.Progressbar(r, style="Skool.Horizontal.TProgressbar", maximum=100); self.pb4.pack(fill="x", pady=(16, 5))
        self.status4 = tk.Label(r, text="", bg=CARD, fg=TEXT2, font=("Consolas", 10)); self.status4.pack(anchor="w")
        # --- danh sach chuong ---
        cc = mk_card(self.body)
        self.chap_hdr = tk.Label(cc, text="Chương", bg=CARD, fg=PRIM_DK, font=(FT, 11, "bold")); self.chap_hdr.pack(anchor="w", padx=12, pady=(10, 4))
        wrap = tk.Frame(cc, bg=CARD); wrap.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        self.chap_canvas = tk.Canvas(wrap, bg=CARD, height=200, highlightthickness=0)
        csb = ttk.Scrollbar(wrap, orient="vertical", command=self.chap_canvas.yview)
        self.chap_inner = tk.Frame(self.chap_canvas, bg=CARD)
        self.chap_inner.bind("<Configure>", lambda e: self.chap_canvas.configure(scrollregion=self.chap_canvas.bbox("all")))
        self.chap_canvas.create_window((0, 0), window=self.chap_inner, anchor="nw"); self.chap_canvas.configure(yscrollcommand=csb.set)
        self.chap_canvas.pack(side="left", fill="both", expand=True); csb.pack(side="right", fill="y")
        # --- run + nut ---
        self.run_lbl = tk.Label(self.body, text="⏳  Đang chạy…", bg=BG, fg=WARNING, font=(FT, 10, "bold")); self.run_lbl.pack(anchor="w", pady=(6, 2))
        self.done_row = tk.Frame(self.body, bg=BG); self.done_row.pack(fill="x", pady=8)
        big_btn(self.done_row, "📁  Mở thư mục dự án", self.open_folder, variant="secondary").pack(side="left", padx=(0, 6))
        self.btn_stop = big_btn(self.done_row, "■  Dừng", self.do_stop, variant="danger"); self.btn_stop.pack(side="left")
        self.refresh4()

    def refresh4(self):
        rows, dtot, etot, size = self.scan_progress()
        pct = round(dtot * 100 / etot) if etot else 0
        if hasattr(self, "pct_lbl"): self.pct_lbl.config(text=f"{pct}%")
        if hasattr(self, "pb4"): self.pb4["value"] = pct
        if hasattr(self, "status4"): self.status4.config(text=f"{dtot}/{etot} video  ·  {fmt_size(size)}")
        if hasattr(self, "chap_hdr"): self.chap_hdr.config(text=f"Chương ({len(rows)})")
        self.render_chapter_rows(rows)

    def render_chapter_rows(self, rows):
        if not hasattr(self, "chap_inner"): return
        for w in self.chap_inner.winfo_children(): w.destroy()
        if not rows:
            tk.Label(self.chap_inner, text="(Chưa có dữ liệu chương — bắt đầu tải để thấy tiến trình)", bg=CARD, fg=TEXT2, font=(FT, 10, "italic")).pack(anchor="w", padx=8, pady=10); return
        for r in rows:
            ic, col = ICON.get(r["status"], ("○", TEXT2))
            row = tk.Frame(self.chap_inner, bg=CARD); row.pack(fill="x", padx=8, pady=3)
            tk.Label(row, text=ic, bg=CARD, fg=col, font=(FT, 11, "bold"), width=2).pack(side="left")
            nm = r["name"]; nm = nm if len(nm) <= 40 else nm[:39] + "…"
            tk.Label(row, text=nm, bg=CARD, fg=TEXT, font=(FT, 10), anchor="w", width=34).pack(side="left")
            pct = round(r["done"] * 100 / r["exp"]) if r["exp"] else 0
            pb = ttk.Progressbar(row, style="Mini.Horizontal.TProgressbar", maximum=100, length=110); pb.pack(side="left", padx=6); pb["value"] = pct
            tk.Label(row, text=f"{r['done']}/{r['exp']}", bg=CARD, fg=TEXT2, font=("Consolas", 10), width=7, anchor="e").pack(side="left", padx=4)
            tk.Label(row, text=f"{pct}%", bg=CARD, fg=PRIM_DK, font=("Consolas", 10, "bold"), width=5, anchor="e").pack(side="left")

    def show_done(self):
        self.set_step(4, "Hoàn tất")
        for w in self.done_row.winfo_children(): w.destroy()
        self.refresh4()
        if hasattr(self, "run_lbl"): self.run_lbl.config(text="✓  Hoàn tất", fg=SUCCESS)
        if getattr(self, "opt_sub", None) and self.opt_sub.get():
            self.write("Bật phụ đề chạy ngầm..."); self.run_sub_on()
        big_btn(self.done_row, "📁  Mở thư mục dự án", self.open_folder, variant="secondary").pack(side="left", padx=(0, 6))
        big_btn(self.done_row, "↻  Làm khóa khác", self.show_step1, variant="primary").pack(side="left")

    # ---------- chay tien trinh ----------
    def start_download(self):
        args = ([] if not self.course_name else ["--course", self.course_name])
        test = bool(getattr(self, "opt_test", None) and self.opt_test.get())
        if test: args.append("--dry-run")
        self.show_step4()
        if test and hasattr(self, "run_lbl"):
            self.run_lbl.config(text="🔧  CHẾ ĐỘ TEST — chỉ kiểm tra, không tải thật", fg="#9a6700")
        self.start([PY, "main.py"] + args, "TẢI KHÓA" + (" (TEST)" if test else ""), on_done=self.show_done)

    def run_sub_on(self):
        c = self.course_name
        ps = HERE / "install_transcribe_task.ps1"
        extra = ["-Course", c] if c else ["-All"]
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)] + extra, creationflags=NO_WIN)

    def start(self, cmd, title, cwd=None, on_done=None):
        if self.proc:
            messagebox.showinfo("Đang bận", "Một tác vụ đang chạy."); return
        self._on_done = on_done
        self.write(f"\n===== {title} =====")
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        try:
            self.proc = subprocess.Popen(cmd, cwd=cwd or HERE, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=NO_WIN)
        except Exception as e:
            self.write(f"[LỖI] {e}"); self.proc = None; return
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        for line in self.proc.stdout: self.q.put(("out", line))
        self.proc.wait(); self.q.put(("out", SENTINEL))

    def do_stop(self):
        if self.proc:
            try: self.proc.terminate()
            except Exception: pass
            self.write("[Đã dừng]")
            if hasattr(self, "run_lbl"): self.run_lbl.config(text="■  Đã dừng", fg=DANGER)

    def open_folder(self):
        r = self.course_root(); r.mkdir(parents=True, exist_ok=True)
        try: os.startfile(str(r))
        except Exception as e: messagebox.showerror("Lỗi", f"Không mở được thư mục: {e}")

    # ---------- vong lap su kien ----------
    def poll(self):
        if self.sb:
            try:
                while True: self.on_browser_event(self.sb.evt_q.get_nowait())
            except queue.Empty: pass
        try:
            while True:
                tag, s = self.q.get_nowait()
                if s == SENTINEL:
                    rc = self.proc.returncode if self.proc else 0
                    self.write(f"--- Kết thúc (mã {rc}) ---"); self.proc = None
                    if getattr(self, "_on_done", None): self._on_done(); self._on_done = None
                else:
                    self.write(s.rstrip("\n"))
        except queue.Empty: pass
        if hasattr(self, "chap_inner") and (time.time() - self._lastref > 1.5):
            self._lastref = time.time(); self.refresh4()
        self.root.after(150, self.poll)

    def on_browser_event(self, e):
        t = e.get("type")
        if t == "ready": self.write("Trình duyệt sẵn sàng."); self.sb.open()
        elif t == "opened":
            self.write("Đã mở Skool. Đăng nhập & mở trang Classroom của khóa, rồi bấm nút 2.")
            if hasattr(self, "b_list"): self.b_list.config(state="normal")
        elif t == "log": self.write(e["msg"])
        elif t == "need_classroom": messagebox.showinfo("Mở trang Classroom", e["msg"])
        elif t == "chapters":
            self.write(f"Tìm thấy {len(e['chapters'])} chương."); self.render_chapters(e["group"], e["chapters"])
        elif t == "dump_progress":
            self.write(f"[{e['i']}/{e['n']}] {e['title']}")
            if hasattr(self, "dump_status"):
                pct = round(e["i"] * 100 / max(1, e["n"]))
                self.dump_status.config(text=f"Đang lấy dữ liệu: {e['i']}/{e['n']} chương ({pct}%) — {e['title']}")
                self.dump_pb["value"] = pct
        elif t == "dumped":
            self._dumping = False
            self.write(f"Đã lấy xong {e['ok']}/{e['total']} chương → {e['out_dir']}")
            if hasattr(self, "dump_status"):
                self.dump_status.config(text=f"✓ Đã lấy {e['ok']}/{e['total']} chương"); self.dump_pb["value"] = 100
            messagebox.showinfo("Xong", f"Đã lấy dữ liệu khóa ({e['ok']}/{e['total']} chương).\nTiếp tục để tải video.")
            self.show_step3()
        elif t == "error":
            self.write(f"[LỖI trình duyệt] {e['msg']}"); messagebox.showerror("Lỗi", e["msg"])


def main():
    root = tk.Tk()
    App(root)
    if os.environ.get("GUI_SMOKE_TEST"):
        root.after(800, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
