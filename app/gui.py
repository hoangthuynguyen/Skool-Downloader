#!/usr/bin/env python3
"""
Giao dien Skool Archiver - CustomTkinter (UI v2).
Mo bang: double-click SkoolArchiver.cmd
"""
import os, sys, time, queue, threading, subprocess
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import progress as P
import common as K

HERE = Path(__file__).resolve().parent
ARCHIVER = HERE.parent
PY = sys.executable.replace("pythonw.exe", "python.exe")
NO_WIN = 0x08000000 if os.name == "nt" else 0
SENTINEL = "\x00DONE\x00"

# ===== theme UI v2.1 — light / dark =====
LIGHT = dict(
    BG="#F0F2F5", SIDE="#0F172A", SIDE_HI="#1E293B", SIDE_ACTIVE="#334155",
    CARD="#FFFFFF", CARD2="#F1F5F9", PRIMARY="#0F172A", PRIMARY_H="#1E293B",
    ACCENT="#2563EB", ACCENT_H="#1D4ED8", ACCENT_SOFT="#EFF6FF",
    SUCCESS="#059669", SUCCESS_BG="#ECFDF5", WARNING="#D97706", WARNING_BG="#FFFBEB",
    DANGER="#DC2626", DANGER_BG="#FEF2F2", TEXT="#0F172A", TEXT2="#64748B",
    ON_SIDE="#94A3B8", BORDER="#E2E8F0", LOG_BG="#F8FAFC",
)
DARK = dict(
    BG="#0B1220", SIDE="#020617", SIDE_HI="#0F172A", SIDE_ACTIVE="#1E293B",
    CARD="#111827", CARD2="#1F2937", PRIMARY="#E5E7EB", PRIMARY_H="#F9FAFB",
    ACCENT="#3B82F6", ACCENT_H="#2563EB", ACCENT_SOFT="#1E3A5F",
    SUCCESS="#34D399", SUCCESS_BG="#064E3B", WARNING="#FBBF24", WARNING_BG="#78350F",
    DANGER="#F87171", DANGER_BG="#7F1D1D", TEXT="#F1F5F9", TEXT2="#94A3B8",
    ON_SIDE="#64748B", BORDER="#1F2937", LOG_BG="#0F172A",
)

# module-level (cap nhat boi apply_theme)
BG = SIDE = SIDE_HI = SIDE_ACTIVE = CARD = CARD2 = PRIMARY = PRIMARY_H = None
ACCENT = ACCENT_H = ACCENT_SOFT = SUCCESS = SUCCESS_BG = WARNING = WARNING_BG = None
DANGER = DANGER_BG = TEXT = TEXT2 = ON_SIDE = BORDER = LOG_BG = None
ICON = {}
THEME_MODE = "light"


def pick_font():
    if sys.platform == "darwin":
        return "Helvetica Neue"
    if os.name == "nt":
        return "Segoe UI"
    return "Sans"


FT = pick_font()
STEPS = ["Chọn khóa", "Lấy khóa", "Tùy chọn", "Tải về"]

# Nav items: (id, label, method_name)
NAV_ITEMS = (
    ("dashboard", "⌂   Dashboard", "show_dashboard"),
    ("queue", "☰   Hàng đợi", "show_queue"),
    ("chat", "💬   Chat RAG", "show_chat"),
    ("cloud", "☁   Cloud", "show_cloud"),
    ("web", "🌐   Web Viewer", "show_web_tools"),
    ("report", "📄   Xuất & Báo cáo", "show_report"),
    ("doctor", "🩺   Doctor", "show_doctor"),
)


def apply_theme(mode="light"):
    """Gan mau global + CTk appearance."""
    global BG, SIDE, SIDE_HI, SIDE_ACTIVE, CARD, CARD2, PRIMARY, PRIMARY_H
    global ACCENT, ACCENT_H, ACCENT_SOFT, SUCCESS, SUCCESS_BG, WARNING, WARNING_BG
    global DANGER, DANGER_BG, TEXT, TEXT2, ON_SIDE, BORDER, LOG_BG, ICON, THEME_MODE
    src = DARK if mode == "dark" else LIGHT
    THEME_MODE = "dark" if mode == "dark" else "light"
    for k, v in src.items():
        globals()[k] = v
    ICON = {"done": ("✓", SUCCESS), "loading": ("⏳", WARNING), "pending": ("•", TEXT2)}
    ctk.set_appearance_mode("dark" if THEME_MODE == "dark" else "light")


def load_theme_pref():
    try:
        import ai_tools
        return (ai_tools.load_settings().get("ui_theme") or "light").lower()
    except Exception:
        try:
            import json
            p = HERE / ".settings.json"
            return (json.loads(p.read_text(encoding="utf-8")).get("ui_theme") or "light").lower()
        except Exception:
            return "light"


def save_theme_pref(mode):
    try:
        import json
        p = HERE / ".settings.json"
        s = {}
        if p.exists():
            try:
                s = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                s = {}
        s["ui_theme"] = mode
        p.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


apply_theme(load_theme_pref())
ctk.set_default_color_theme("blue")

# ===== density (comfortable | compact) =====
DENSITY = "comfortable"
DENS = {
    "comfortable": {
        "btn_h": 38, "nav_h": 36, "nav_pad": 2, "log_h": 88,
        "head": 24, "sub": 13, "pad_x": 24, "pad_y": 18, "card_r": 16,
        "entry_h": 38, "font_btn": 13, "font_nav": 12,
    },
    "compact": {
        "btn_h": 32, "nav_h": 30, "nav_pad": 1, "log_h": 64,
        "head": 20, "sub": 12, "pad_x": 16, "pad_y": 12, "card_r": 12,
        "entry_h": 32, "font_btn": 12, "font_nav": 11,
    },
}


def dens(key, default=None):
    return DENS.get(DENSITY, DENS["comfortable"]).get(key, default)


def load_density_pref():
    try:
        import json
        p = HERE / ".settings.json"
        d = (json.loads(p.read_text(encoding="utf-8")).get("ui_density") or "comfortable").lower()
        return d if d in DENS else "comfortable"
    except Exception:
        return "comfortable"


def save_density_pref(mode):
    try:
        import json
        p = HERE / ".settings.json"
        s = {}
        if p.exists():
            try:
                s = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                s = {}
        s["ui_density"] = mode
        p.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def apply_density(mode="comfortable"):
    global DENSITY
    DENSITY = mode if mode in DENS else "comfortable"


apply_density(load_density_pref())


def btn(parent, text, cmd, kind="primary", **kw):
    pal = {
        "primary": (PRIMARY, PRIMARY_H, ("white" if THEME_MODE == "light" else "#0F172A")),
        "success": (SUCCESS, "#047857" if THEME_MODE == "light" else "#059669", "white"),
        "accent": (ACCENT, ACCENT_H, "white"),
        "danger": (DANGER, "#B91C1C" if THEME_MODE == "light" else "#DC2626", "white"),
        "secondary": (CARD2, BORDER, TEXT),
        "ghost": ("transparent", CARD2, TEXT),
        "warn": (WARNING, "#B45309" if THEME_MODE == "light" else "#D97706",
                 ("white" if THEME_MODE == "light" else "#0F172A")),
        "soft": (ACCENT_SOFT, ACCENT_SOFT, ACCENT),
    }
    fg, hov, tc = pal.get(kind, pal["primary"])
    opt = dict(corner_radius=10, height=dens("btn_h", 38),
               font=(FT, dens("font_btn", 13), "bold"),
               fg_color=fg, hover_color=hov, text_color=tc)
    if kind == "ghost":
        opt["border_width"] = 0
    elif kind == "secondary":
        opt["border_width"] = 1
        opt["border_color"] = BORDER
    opt.update(kw)
    return ctk.CTkButton(parent, text=text, command=cmd, **opt)


def fmt_size(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{int(n)} B" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def badge_colors(level):
    """level: ok|warn|danger|info|muted -> (fg, bg)"""
    return {
        "ok": (SUCCESS, SUCCESS_BG),
        "warn": (WARNING, WARNING_BG),
        "danger": (DANGER, DANGER_BG),
        "info": (ACCENT, ACCENT_SOFT),
        "muted": (TEXT2, CARD2),
    }.get(level or "muted", (TEXT2, CARD2))


class App:
    def __init__(self, root):
        self.root = root
        self.proc = None; self.sb = None; self.q = queue.Queue(); self.ui_q = queue.Queue()
        self.chapters = []; self.course_name = None; self.mode = None
        self.admin = False; self._dumping = False; self._prog = []; self._lastref = 0.0
        self.step = 1; self.chap_widgets = {}
        self.purpose = "import"          # import | update | rescue (muc dich phien trinh duyet)
        self.known_titles = set()        # ten chuong da luu (de danh dau MOI khi cap nhat)
        self.live_titles = []            # thu tu chuong day du tu lan list gan nhat
        self.target_titles = set()       # chuong can re-dump (cuu native het han)
        self.last_scan = None            # ket qua progress.scan gan nhat
        self.scan_cache = {}             # {display item -> scan} cho Buoc 1 (de hien dung luong khi xoa)
        self.dash_entries = []           # ket qua scan_all cho dashboard
        self.queue_runner = None         # queue_engine.QueueRunner
        self.queue_checks = {}           # id -> BooleanVar (chon job)
        self.chat_history = []           # [(role, text)]
        self._cfg_lock = threading.Lock()  # serialize khi tam set config.C (tao folder)
        self._in_err = False             # tranh de quy man hinh loi

        try:
            import version as V
            _ver = V.__version__
        except Exception:
            _ver = ""
        self.nav_page = "dashboard"
        self._nav_btns = {}
        self._web_proc = None
        root.title(f"Skool Archiver {_ver}".strip())
        root.geometry("980x720")
        root.minsize(720, 520)
        root.configure(fg_color=BG)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        # ---------- sidebar ----------
        self.side = ctk.CTkFrame(root, width=228, corner_radius=0, fg_color=SIDE)
        self.side.grid(row=0, column=0, sticky="nsw")
        self.side.grid_propagate(False)
        # brand
        brand = ctk.CTkFrame(self.side, fg_color="transparent")
        brand.pack(fill="x", padx=18, pady=(22, 8))
        logo = ctk.CTkFrame(brand, width=36, height=36, corner_radius=10, fg_color=ACCENT)
        logo.pack(side="left")
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="SA", font=(FT, 13, "bold"), text_color="white").place(relx=0.5, rely=0.5, anchor="center")
        bt = ctk.CTkFrame(brand, fg_color="transparent")
        bt.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(bt, text="Skool Archiver", font=(FT, 15, "bold"), text_color="white").pack(anchor="w")
        ctk.CTkLabel(bt, text=f"v{_ver}" if _ver else "Local archive",
                     font=(FT, 11), text_color=ON_SIDE).pack(anchor="w")

        ctk.CTkFrame(self.side, height=1, fg_color=SIDE_HI).pack(fill="x", padx=16, pady=(6, 10))

        # wizard steps (compact)
        self.step_box = ctk.CTkFrame(self.side, fg_color="transparent")
        self.step_box.pack(fill="x", padx=12)
        ctk.CTkLabel(self.side, text="ĐIỀU HƯỚNG", font=(FT, 10, "bold"),
                     text_color=ON_SIDE).pack(anchor="w", padx=20, pady=(14, 4))

        self.nav_box = ctk.CTkFrame(self.side, fg_color="transparent")
        self.nav_box.pack(fill="x", padx=10)
        self._build_nav()

        # footer
        foot = ctk.CTkFrame(self.side, fg_color="transparent")
        foot.pack(side="bottom", fill="x", padx=12, pady=(8, 14))
        self.badge = ctk.CTkLabel(foot, text="", font=(FT, 11, "bold"), text_color=ACCENT)
        self.badge.pack(anchor="w", padx=8, pady=(0, 6))
        self.theme_btn = btn(
            foot,
            "🌙  Dark mode" if THEME_MODE == "light" else "☀  Light mode",
            self.toggle_theme, kind="ghost",
            text_color="white", hover_color=SIDE_HI, anchor="w", height=34,
            font=(FT, 12))
        self.theme_btn.pack(fill="x", pady=(0, 2))
        self.density_btn = btn(
            foot,
            "▤  Compact" if DENSITY == "comfortable" else "▦  Comfortable",
            self.toggle_density, kind="ghost",
            text_color="white", hover_color=SIDE_HI, anchor="w", height=34,
            font=(FT, 12))
        self.density_btn.pack(fill="x", pady=(0, 4))
        btn(foot, "⚙  Kiểm tra môi trường", self.show_check, kind="ghost",
            text_color="white", hover_color=SIDE_HI, anchor="w", height=34,
            font=(FT, 12)).pack(fill="x")

        # ---------- main ----------
        main = ctk.CTkFrame(root, corner_radius=0, fg_color=BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.main_frame = main
        self.content = ctk.CTkScrollableFrame(
            main, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=TEXT2)
        self.content.grid(row=0, column=0, sticky="nsew",
                          padx=(dens("pad_x", 24), 10), pady=(dens("pad_y", 18), 6))

        # log panel
        logwrap = ctk.CTkFrame(main, fg_color=CARD, corner_radius=14,
                               border_width=1, border_color=BORDER)
        logwrap.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 14))
        ltop = ctk.CTkFrame(logwrap, fg_color="transparent")
        ltop.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(ltop, text="Nhật ký", font=(FT, 12, "bold"), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(ltop, text="pipeline · queue · cloud", font=(FT, 10),
                     text_color=TEXT2).pack(side="left", padx=8)
        self.logwrap = logwrap
        self.log = ctk.CTkTextbox(logwrap, height=dens("log_h", 88), font=("Consolas", 11),
                                  fg_color=LOG_BG, text_color=TEXT, corner_radius=10,
                                  border_width=0)
        self.log.pack(fill="x", padx=10, pady=(6, 10))
        self.log.configure(state="disabled")

        root.report_callback_exception = self._tk_err
        root.bind_all("<Control-Alt-t>", self.toggle_admin)
        root.bind_all("<Control-Alt-T>", self.toggle_admin)
        self.render_sidebar()
        self.show_dashboard()
        self.root.after(120, self.poll)

    def toggle_theme(self):
        """Dao light/dark, luu settings, ve lai man hien tai."""
        new = "dark" if THEME_MODE == "light" else "light"
        apply_theme(new)
        save_theme_pref(new)
        try:
            self.root.configure(fg_color=BG)
            self.side.configure(fg_color=SIDE)
            if hasattr(self, "logwrap") and self.logwrap.winfo_exists():
                self.logwrap.configure(fg_color=CARD, border_color=BORDER)
            if hasattr(self, "log") and self.log.winfo_exists():
                self.log.configure(fg_color=LOG_BG, text_color=TEXT)
            if hasattr(self, "theme_btn") and self.theme_btn.winfo_exists():
                self.theme_btn.configure(
                    text="🌙  Dark mode" if new == "light" else "☀  Light mode",
                    fg_color="transparent", hover_color=SIDE_HI, text_color="white")
        except Exception:
            pass
        # rebuild chrome that uses constants
        self._build_nav()
        self.render_sidebar()
        # refresh current page
        page = self.nav_page or "dashboard"
        method = next((m for i, _, m in NAV_ITEMS if i == page), "show_dashboard")
        try:
            getattr(self, method)()
        except Exception:
            self.show_dashboard()
        self.write(f"Giao diện: {new} mode")

    def toggle_density(self):
        """Dao comfortable / compact, luu settings, ve lai."""
        new = "compact" if DENSITY == "comfortable" else "comfortable"
        apply_density(new)
        save_density_pref(new)
        try:
            if hasattr(self, "content") and self.content.winfo_exists():
                self.content.grid_configure(padx=(dens("pad_x", 24), 10),
                                            pady=(dens("pad_y", 18), 6))
            if hasattr(self, "log") and self.log.winfo_exists():
                self.log.configure(height=dens("log_h", 88))
            if hasattr(self, "density_btn") and self.density_btn.winfo_exists():
                self.density_btn.configure(
                    text="▤  Compact" if new == "comfortable" else "▦  Comfortable",
                    fg_color="transparent", hover_color=SIDE_HI, text_color="white")
        except Exception:
            pass
        self._build_nav()
        self.render_sidebar()
        page = self.nav_page or "dashboard"
        method = next((m for i, _, m in NAV_ITEMS if i == page), "show_dashboard")
        try:
            getattr(self, method)()
        except Exception:
            self.show_dashboard()
        self.write(f"Density: {new}")

    def _build_nav(self):
        for w in self.nav_box.winfo_children():
            w.destroy()
        self._nav_btns = {}
        for nid, label, method in NAV_ITEMS:
            active = (self.nav_page == nid)
            b = ctk.CTkButton(
                self.nav_box, text=label, anchor="w", height=dens("nav_h", 36),
                corner_radius=10,
                font=(FT, dens("font_nav", 12), "bold" if active else "normal"),
                fg_color=(SIDE_ACTIVE if active else "transparent"),
                hover_color=SIDE_HI,
                text_color=("white" if active else ON_SIDE),
                command=lambda m=method, i=nid: self._nav_go(i, m),
            )
            b.pack(fill="x", pady=dens("nav_pad", 2))
            self._nav_btns[nid] = b

    def _nav_go(self, page_id, method_name):
        self.nav_page = page_id
        self._build_nav()
        getattr(self, method_name)()

    def set_nav(self, page_id):
        """Goi tu man hinh de highlight sidebar (khi vao page khong qua nav)."""
        if self.nav_page != page_id:
            self.nav_page = page_id
            self._build_nav()

    # ---------- bat MOI loi giao dien -> ghi log + man hinh phuc hoi (khong bao gio trang/ket) ----------
    def _tk_err(self, exc, val, tb):
        import traceback
        full = "".join(traceback.format_exception(exc, val, tb))
        try:
            (ARCHIVER / "logs").mkdir(parents=True, exist_ok=True)
            with (ARCHIVER / "logs" / "gui_error.log").open("a", encoding="utf-8") as f:
                f.write(full + "\n")
        except Exception: pass
        try: self.write("[LỖI GIAO DIỆN] " + (str(val) or exc.__name__))
        except Exception: pass
        if self._in_err: return            # dang hien man hinh loi -> dung de quy
        self._in_err = True
        try: self._show_error(str(val) or exc.__name__, full)
        except Exception: pass
        finally: self._in_err = False

    def _show_error(self, short, full):
        self.clear()
        self.head("Đã xảy ra lỗi", "App gặp trục trặc ở thao tác vừa rồi nhưng vẫn chạy bình thường. Bấm nút bên dưới để tiếp tục.")
        card = self.card()
        ctk.CTkLabel(card, text=short, font=(FT, 13, "bold"), text_color=DANGER,
                     wraplength=560, justify="left").pack(anchor="w", padx=16, pady=(12, 4))
        box = ctk.CTkTextbox(card, height=150, font=("Consolas", 10),
                             fg_color=DANGER_BG, text_color="#7F1D1D", corner_radius=10)
        box.pack(fill="x", padx=12, pady=(2, 12)); box.insert("end", full[-2500:]); box.configure(state="disabled")
        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", pady=10)
        btn(row, "←  Về Dashboard", self.show_dashboard, kind="ghost", width=150).pack(side="left")
        btn(row, "📁  Mở thư mục log", lambda: self._open_path(ARCHIVER / "logs"),
            kind="secondary", width=170).pack(side="left", padx=8)

    def _open_path(self, p):
        """Mo folder/file tren Windows / macOS / Linux."""
        p = Path(p)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            if os.name == "nt":
                os.startfile(str(p))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception as e:
            try: self.write(f"[mở folder] {e}")
            except Exception: pass

    # ---------- sidebar steps (wizard) ----------
    def render_sidebar(self):
        for w in self.step_box.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.step_box, text="WIZARD TẢI", font=(FT, 10, "bold"),
                     text_color=ON_SIDE).pack(anchor="w", padx=8, pady=(0, 4))
        row = ctk.CTkFrame(self.step_box, fg_color="transparent")
        row.pack(fill="x", padx=4)
        for i, name in enumerate(STEPS, 1):
            active = (i == self.step)
            done = i < self.step
            cell = ctk.CTkFrame(row, fg_color="transparent")
            cell.pack(side="left", expand=True, fill="x")
            dot_fg = ACCENT if active else (SUCCESS if done else SIDE_HI)
            dot = ctk.CTkLabel(cell, text=str(i), width=22, height=22, corner_radius=11,
                               fg_color=dot_fg, text_color="white", font=(FT, 10, "bold"))
            dot.pack()
            ctk.CTkLabel(cell, text=name.split()[0], font=(FT, 9),
                         text_color=("white" if active else ON_SIDE)).pack()

    def set_step(self, n):
        self.step = n
        self.render_sidebar()

    # ---------- helpers ----------
    def clear(self):
        for w in self.content.winfo_children():
            w.destroy()
        self.chap_widgets = {}
        for a in ("mgr_scroll", "mgr_status", "chap_scroll", "chap_hdr", "sum_lbl", "native_banner",
                  "status4", "pct_lbl", "pb4", "run_lbl", "done_row", "trans_lbl", "trans_pb", "tl_lbl",
                  "dump_status", "dump_pb", "b_start", "b_all", "b_dump", "b_list", "b_open", "chap_box", "dump_row",
                  "dash_list", "dash_summary", "dash_search_box", "q_list", "q_status", "chat_box", "chat_input", "chat_src",
                  "cloud_status", "mgr_fail_box", "doctor_box", "stat_row"):
            if hasattr(self, a):
                delattr(self, a)

    def toggle_admin(self, *_):
        self.admin = not self.admin
        self.badge.configure(text="🔧 TEST MODE" if self.admin else "")
        self.write("== Chế độ TEST: BẬT (tải sẽ KHÔNG tải thật) ==" if self.admin else "== Chế độ TEST: TẮT ==")

    def head(self, text, sub=""):
        wrap = ctk.CTkFrame(self.content, fg_color="transparent")
        wrap.pack(fill="x", pady=(0, 10 if DENSITY == "compact" else 14))
        ctk.CTkLabel(wrap, text=text, font=(FT, dens("head", 24), "bold"),
                     text_color=TEXT).pack(anchor="w")
        if sub:
            ctk.CTkLabel(wrap, text=sub, font=(FT, dens("sub", 13)), text_color=TEXT2,
                         justify="left", wraplength=640).pack(anchor="w", pady=(4, 0))
        ctk.CTkFrame(wrap, height=3, width=48, corner_radius=2, fg_color=ACCENT).pack(
            anchor="w", pady=(8 if DENSITY == "compact" else 10, 0))

    def card(self, **kw):
        opt = dict(fg_color=CARD, corner_radius=dens("card_r", 16),
                   border_width=1, border_color=BORDER)
        opt.update(kw)
        c = ctk.CTkFrame(self.content, **opt)
        c.pack(fill="x", pady=(4 if DENSITY == "compact" else 8))
        return c

    def pill(self, parent, text, level="muted"):
        """Badge pill mau theo level."""
        fg, bg = badge_colors(level)
        lab = ctk.CTkLabel(parent, text=text, font=(FT, 11, "bold"),
                           text_color=fg, fg_color=bg, corner_radius=999,
                           padx=10, pady=3)
        return lab

    def stat_card(self, parent, title, value, sub="", level="info"):
        """O thong ke nho tren dashboard."""
        fg, bg = badge_colors(level)
        box = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14,
                           border_width=1, border_color=BORDER)
        box.pack(side="left", expand=True, fill="both", padx=4)
        ctk.CTkLabel(box, text=title, font=(FT, 11), text_color=TEXT2).pack(anchor="w", padx=14, pady=(12, 0))
        ctk.CTkLabel(box, text=value, font=(FT, 20, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(2, 0))
        if sub:
            ctk.CTkLabel(box, text=sub, font=(FT, 11, "bold"), text_color=fg).pack(anchor="w", padx=14, pady=(0, 12))
        else:
            ctk.CTkFrame(box, height=12, fg_color="transparent").pack()
        return box

    def write(self, s):
        self._flush_log([s.rstrip("\n")])

    def _flush_log(self, lines):
        """Ghi NHIEU dong 1 lan (giam giat). Gop cac dong tien do '[download] x%' lien tiep
           thanh 1 dong (yt-dlp --newline phun hang tram dong/giay)."""
        merged = []
        for s in lines:
            prog = s.startswith("[download]") and "%" in s
            if prog and merged and merged[-1][1]:
                merged[-1] = (s, True)          # de len dong tien do truoc do
            else:
                merged.append((s, prog))
        self.log.configure(state="normal")
        for s, _ in merged:
            self.log.insert("end", s + "\n")
        # cat bot cho nhe (giu ~400 dong cuoi)
        try:
            n = int(self.log.index("end-1c").split(".")[0])
            if n > 600:
                self.log.delete("1.0", f"{n - 400}.0")
        except Exception:
            pass
        self.log.see("end"); self.log.configure(state="disabled")

    def course_root(self, name=None):
        name = name or self.course_name
        if not name or str(name).startswith("SkoolCourse"): return C.BASE / "SkoolCourse"
        return C.BASE / "courses" / name

    def existing_courses(self):
        items = []
        if (C.BASE / "SkoolCourse").exists(): items.append("SkoolCourse (đã có sẵn)")
        cdir = C.BASE / "courses"
        if cdir.exists(): items += sorted(p.name for p in cdir.iterdir() if p.is_dir())
        return items

    def item_course(self, item):
        """Display item -> ten khoa (None = SkoolCourse cu)."""
        return None if (not item or item.startswith("SkoolCourse")) else item

    def item_root(self, item):
        return self.course_root(self.item_course(item))

    # ---------- chay nen + tra ket qua ve luong giao dien ----------
    def run_async(self, fn, cb):
        """Chay fn() o thread phu, day cb(ket_qua) vao ui_q de poll() goi tren main thread."""
        def work():
            try: r = fn()
            except Exception as e: r = e
            self.ui_q.put(lambda: cb(r))
        threading.Thread(target=work, daemon=True).start()

    # ---------- tien do theo chuong ----------
    def _video_in(self, folder):
        for ext in C.VIDEXT:
            p = folder / ("video" + ext)
            try:
                if p.exists() and p.stat().st_size > 0: return p
            except OSError: pass
        return None

    def build_progress(self):
        import json, common as K
        self._prog = []; root = self.course_root()
        if not root.exists(): return
        def chap_folder(ct):
            for d in sorted([p for p in root.iterdir() if p.is_dir()]):
                nm = d.name.split(" - ", 1)[-1] if " - " in d.name else d.name
                if nm == ct: return d
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
            lessons = [fd for fd, n in K.walk(course.get("children") or [], chap) if n.get("url")]
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
            exp = len(ch["lessons"]); stt = "done" if (exp and done >= exp) else ("loading" if done > 0 else "pending")
            rows.append({"name": ch["name"], "done": done, "exp": exp, "status": stt}); dtot += done; etot += exp
        return rows, dtot, etot, size

    # ====================== KIỂM TRA MÔI TRƯỜNG ======================
    def _ffmpeg_ok(self):
        import shutil
        if shutil.which("ffmpeg"): return True
        try:
            import ffmpeg_downloader as ffdl
            return bool(getattr(ffdl, "ffmpeg_path", None))
        except Exception: return False

    def _chromium_ok(self):
        """Tim cache Chromium cua Playwright tren Windows / macOS / Linux."""
        home = Path.home()
        candidates = []
        la = os.environ.get("LOCALAPPDATA")
        if la:
            candidates.append(Path(la) / "ms-playwright")
        candidates += [
            home / "Library" / "Caches" / "ms-playwright",  # macOS
            home / ".cache" / "ms-playwright",              # Linux
            home / "AppData" / "Local" / "ms-playwright",
        ]
        for base in candidates:
            try:
                if base.exists() and any(base.glob("chromium-*")):
                    return True
            except Exception:
                pass
        # fallback: goi playwright API (co the cham)
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                exe = getattr(p.chromium, "executable_path", None)
                return bool(exe and Path(exe).exists())
        except Exception:
            return False

    def check_env(self):
        import shutil, importlib.util
        def has(m): return importlib.util.find_spec(m) is not None
        sc = Path(PY).parent
        items = [("Python", True, f"{sys.version_info.major}.{sys.version_info.minor}", None)]
        node = shutil.which("node")
        items.append(("Node.js (cho YouTube)", bool(node), node or "thiếu", None if node else ("Tải Node.js", "node")))
        ff = self._ffmpeg_ok(); items.append(("ffmpeg", ff, "OK" if ff else "thiếu", None if ff else ("Cài ffmpeg", [str(sc / "ffdl.exe"), "install", "--add-path"])))
        for mod, label, pn in [("yt_dlp", "yt-dlp", "yt-dlp"), ("faster_whisper", "faster-whisper", "faster-whisper"), ("playwright", "Playwright", "playwright"), ("customtkinter", "CustomTkinter", "customtkinter")]:
            ok = has(mod); items.append((label, ok, "OK" if ok else "thiếu", None if ok else (f"Cài {label}", [PY, "-m", "pip", "install", "-U", pn])))
        ch = self._chromium_ok(); items.append(("Trình duyệt Chromium", ch, "OK" if ch else "thiếu", None if ch else ("Cài Chromium", [PY, "-m", "playwright", "install", "chromium"])))
        return items

    def env_missing(self): return [i for i in self.check_env() if not i[1]]

    def show_check(self):
        self.clear()
        self.head("Kiểm tra môi trường", "Thành phần bắt buộc và tùy chọn. Mục thiếu có nút cài ngay (Node.js tải tay rồi mở lại app).")
        items = self.check_env()
        ok_n = sum(1 for i in items if i[1])
        miss_n = len(items) - ok_n
        # summary strip
        sumr = ctk.CTkFrame(self.content, fg_color="transparent")
        sumr.pack(fill="x", pady=(0, 10))
        self.stat_card(sumr, "Đạt", str(ok_n), "thành phần", "ok")
        self.stat_card(sumr, "Thiếu", str(miss_n), "cần xử lý" if miss_n else "ổn", "danger" if miss_n else "ok")

        card = self.card()
        for name, ok, detail, fix in items:
            row = ctk.CTkFrame(card, fg_color=CARD2 if not ok else "transparent", corner_radius=10)
            row.pack(fill="x", padx=10, pady=4)
            ir = ctk.CTkFrame(row, fg_color="transparent")
            ir.pack(fill="x", padx=10, pady=8)
            self.pill(ir, "OK" if ok else "THIẾU", "ok" if ok else "danger").pack(side="left", padx=(0, 10))
            ctk.CTkLabel(ir, text=name, font=(FT, 13, "bold"), text_color=TEXT, width=200, anchor="w").pack(side="left")
            ctk.CTkLabel(ir, text=detail if len(str(detail)) < 48 else str(detail)[:45] + "…",
                         font=(FT, 11), text_color=TEXT2).pack(side="left", padx=6)
            if (not ok) and fix:
                btn(ir, fix[0], (lambda p=fix[1]: self.do_fix(p)),
                    kind="accent", width=130, height=30).pack(side="right")
        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", pady=14)
        btn(row, "←  Dashboard", self.show_dashboard, kind="ghost", width=120).pack(side="left")
        btn(row, "↻  Kiểm tra lại", self.show_check, kind="secondary", width=130).pack(side="left", padx=6)
        if [i for i in items if not i[1] and i[3]]:
            btn(row, "⚙  Cài tất cả còn thiếu", self.fix_all, kind="accent").pack(side="right")

    def do_fix(self, payload):
        import webbrowser
        if payload == "node":
            webbrowser.open("https://nodejs.org/en/download"); messagebox.showinfo("Node.js", "Tải bản LTS, cài xong rồi MỞ LẠI app.")
        else: self.start(payload, "CÀI ĐẶT", on_done=self.show_check)

    def fix_all(self):
        import webbrowser
        cmds = []
        for name, ok, detail, fix in self.check_env():
            if ok or not fix: continue
            if fix[1] == "node": webbrowser.open("https://nodejs.org/en/download")
            else: cmds.append(fix[1])
        self._fix_queue = cmds; self.write("Đang cài các thành phần còn thiếu..."); self._run_next_fix()

    def _run_next_fix(self):
        if not getattr(self, "_fix_queue", None): self.show_check(); return
        self.start(self._fix_queue.pop(0), "CÀI ĐẶT", on_done=self._run_next_fix)

    # ====================== XUẤT & BÁO CÁO (Nhóm A) ======================
    def show_report(self):
        self.set_nav("report")
        self.clear()
        self.head("Xuất & Báo cáo", "Gộp nội dung khóa thành 1 file, dịch tiếng Việt, và tóm tắt + to-do bằng AI — để đọc hoặc gửi báo cáo.")
        items = self.existing_courses()
        card = self.card()
        if items:
            ctk.CTkLabel(card, text="Chọn khóa", font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=16, pady=(12, 4))
            self.rep_var = ctk.StringVar(value=items[0])
            for it in items:
                ctk.CTkRadioButton(card, text=it, variable=self.rep_var, value=it, font=(FT, 13), text_color=TEXT,
                                   fg_color=ACCENT, hover_color=ACCENT_H, border_color=BORDER).pack(anchor="w", padx=18, pady=4)
            ctk.CTkFrame(card, fg_color="transparent", height=6).pack()
        else:
            ctk.CTkLabel(card, text="(Chưa có khóa nào — hãy tải một khóa trước)", font=(FT, 12), text_color=TEXT2).pack(padx=16, pady=16)
            self.rep_var = ctk.StringVar(value="")

        self._render_apikey()

        try:
            import ai_tools; st = ai_tools.status()
        except Exception: st = {"claude": False, "google": False, "model": "", "source": None}
        tline = ("Dịch: " + ("Claude ✓" if st["claude"] else ("Google miễn phí ✓" if st["google"] else "✗ chưa có"))
                 + "    ·    Tóm tắt/To-do: " + ("Claude ✓" if st["claude"] else "✗ cần API key Claude (điền ở trên)"))
        ctk.CTkLabel(self.content, text=tline, font=(FT, 11), text_color=TEXT2, justify="left", wraplength=540).pack(anchor="w", pady=(2, 8))

        act = self.card()
        ctk.CTkLabel(act, text="Việc cần làm", font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=16, pady=(12, 6))
        r1 = ctk.CTkFrame(act, fg_color="transparent"); r1.pack(fill="x", padx=14, pady=(0, 4))
        btn(r1, "📄  Gộp & xuất Word", self.do_export, width=210).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(r1, text="Gộp mô tả + lời giảng → 1 file .md và .docx", font=(FT, 11), text_color=TEXT2).pack(side="left")
        r2 = ctk.CTkFrame(act, fg_color="transparent"); r2.pack(fill="x", padx=14, pady=4)
        btn(r2, "🌐  Dịch tiếng Việt", self.do_translate, kind="secondary", width=210).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(r2, text="Dịch file tổng hợp sang tiếng Việt", font=(FT, 11), text_color=TEXT2).pack(side="left")
        r3 = ctk.CTkFrame(act, fg_color="transparent"); r3.pack(fill="x", padx=14, pady=4)
        btn(r3, "📝  Tóm tắt + To-do (AI)", self.do_summary, kind="secondary", width=210).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(r3, text="Tóm tắt từng chương + to-do áp dụng", font=(FT, 11), text_color=TEXT2).pack(side="left")
        r4 = ctk.CTkFrame(act, fg_color="transparent"); r4.pack(fill="x", padx=14, pady=(4, 12))
        btn(r4, "📦  Knowledge pack (zip)", self.do_knowledge_pack, kind="accent", width=210).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(r4, text="Zip text/resources — gửi sếp / USB (không video)", font=(FT, 11), text_color=TEXT2).pack(side="left")

        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", pady=12)
        btn(row, "←  Dashboard", self.show_dashboard, kind="ghost", width=120).pack(side="left")
        btn(row, "📁  Mở thư mục khóa", self.open_report_folder, kind="secondary", width=190).pack(side="right")

    # ---------- API key Claude (điền sống trong app) ----------
    def _mask_key(self, k):
        if not k: return ""
        return (k[:10] + "…" + k[-4:]) if len(k) > 18 else "••••"

    def _render_apikey(self):
        import ai_tools
        card = self.card()
        ctk.CTkLabel(card, text="Khóa API Claude  (cho Dịch chất lượng cao & Tóm tắt/To-do)",
                     font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=16, pady=(12, 4))
        if ai_tools.api_key_source() == "env":
            ctk.CTkLabel(card, text="✓ Đang dùng API key từ biến môi trường ANTHROPIC_API_KEY.",
                         font=(FT, 12), text_color=SUCCESS).pack(anchor="w", padx=16, pady=(0, 12))
            return
        saved = ai_tools.get_api_key()
        if saved:
            ctk.CTkLabel(card, text=f"✓ Đã lưu trên máy này: {self._mask_key(saved)}",
                         font=(FT, 12), text_color=SUCCESS).pack(anchor="w", padx=16, pady=(0, 6))
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=14, pady=(0, 4))
        self.apikey_var = ctk.StringVar(value="")
        ent = ctk.CTkEntry(row, textvariable=self.apikey_var, font=("Consolas", 12), show="•",
                           placeholder_text="Dán API key (sk-ant-…) rồi bấm Lưu")
        ent.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn(row, "💾  Lưu", self.save_api_key, width=90).pack(side="left")
        if saved:
            btn(row, "Xóa", self.clear_api_key, kind="ghost", width=64).pack(side="left", padx=(6, 0))
        ctk.CTkLabel(card, text="Lấy ở console.anthropic.com → API Keys. Key chỉ lưu trên máy này (file .settings.json), chỉ gửi tới API Claude.",
                     font=(FT, 11), text_color=TEXT2, justify="left", wraplength=540).pack(anchor="w", padx=16, pady=(2, 12))

    def save_api_key(self):
        import ai_tools
        k = self.apikey_var.get().strip()
        if not k:
            messagebox.showinfo("Trống", "Hãy dán API key trước khi lưu."); return
        if not k.startswith("sk-") and not messagebox.askyesno("Khác thường", "Key không bắt đầu bằng “sk-”. Vẫn lưu?"):
            return
        ai_tools.save_setting("anthropic_api_key", k)
        self.write("✓ Đã lưu API key Claude (trên máy này).")
        self.show_report()

    def clear_api_key(self):
        import ai_tools
        if not messagebox.askyesno("Xóa key", "Xóa API key đã lưu trên máy này?"): return
        ai_tools.save_setting("anthropic_api_key", "")
        self.write("Đã xóa API key.")
        self.show_report()

    def _report_args(self):
        v = self.rep_var.get().strip() if hasattr(self, "rep_var") else ""
        if not v:
            messagebox.showinfo("Chưa chọn", "Hãy chọn một khóa."); return None, None
        course = self.item_course(v)
        return course, (["--course", course] if course else [])

    def open_report_folder(self):
        course, _ = self._report_args()
        if course is None and not (hasattr(self, "rep_var") and self.rep_var.get()): return
        self._open_path(self.course_root(course))

    def do_export(self):
        course, args = self._report_args()
        if args is None: return
        self.start([PY, "export.py"] + args + ["--docx"], "GỘP & XUẤT WORD")

    def do_translate(self):
        course, args = self._report_args()
        if args is None: return
        try:
            import ai_tools
            if not (ai_tools.have_api() or ai_tools.have_google()):
                messagebox.showinfo("Chưa có dịch vụ dịch",
                                    "Cần một trong hai:\n• Dán API key Claude vào ô bên trên rồi Lưu, hoặc\n• Cài bản miễn phí: pip install deep-translator"); return
        except Exception: pass
        self.start([PY, "ai_tools.py"] + args + ["--translate"], "DỊCH TIẾNG VIỆT")

    def do_summary(self):
        course, args = self._report_args()
        if args is None: return
        try:
            import ai_tools
            if not ai_tools.have_api():
                messagebox.showinfo("Cần API key Claude",
                                    "Tóm tắt + To-do cần API key Claude.\nDán API key vào ô bên trên rồi bấm Lưu."); return
        except Exception: pass
        self.start([PY, "ai_tools.py"] + args + ["--summary"], "TÓM TẮT + TO-DO")

    def do_knowledge_pack(self):
        v = self.rep_var.get().strip() if hasattr(self, "rep_var") else ""
        if not v:
            messagebox.showinfo("Chưa chọn", "Hãy chọn một khóa."); return
        self.export_knowledge_pack(v)

    # ====================== DASHBOARD (S1) ======================
    def show_step1(self):
        """Alias — màn hình chính là Dashboard."""
        self.show_dashboard()

    def show_dashboard(self):
        self.set_nav("dashboard")
        self.set_step(1); self.clear(); self.purpose = "import"
        self.head("Dashboard", "Tổng quan kho khóa — tiến độ, dung lượng, cảnh báo. Chọn khóa để tải tiếp, xếp hàng đợi, chat hoặc đồng bộ cloud.")
        try:
            bi = C.base_info()
            base_line = f"📁  {bi['base']}   ·   {bi['source']}"
        except Exception:
            base_line = f"📁  {C.BASE}"
        ctk.CTkLabel(self.content, text=base_line, font=("Consolas", 11), text_color=TEXT2,
                     wraplength=640, justify="left").pack(anchor="w", pady=(0, 8))

        try:
            miss = self.env_missing()
        except Exception:
            miss = []
        if miss:
            ban = ctk.CTkFrame(self.content, fg_color=WARNING_BG, corner_radius=14,
                               border_width=1, border_color="#FCD34D")
            ban.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(ban, text="⚠  Thiếu: " + ", ".join(m[0].split(" (")[0] for m in miss),
                         text_color="#92400E", font=(FT, 12, "bold")).pack(side="left", padx=14, pady=12)
            btn(ban, "Kiểm tra & cài", self.show_check, kind="warn", width=140).pack(side="right", padx=10, pady=8)

        # stat cards row
        self.stat_row = ctk.CTkFrame(self.content, fg_color="transparent")
        self.stat_row.pack(fill="x", pady=(0, 10))
        self._stat_courses = self.stat_card(self.stat_row, "Khóa học", "…", "đang quét", "info")
        self._stat_lessons = self.stat_card(self.stat_row, "Bài đã tải", "…", "", "ok")
        self._stat_size = self.stat_card(self.stat_row, "Dung lượng", "…", "", "muted")
        self._stat_alert = self.stat_card(self.stat_row, "Cảnh báo", "…", "", "warn")

        # hidden summary label for compat
        self.dash_summary = ctk.CTkLabel(self.content, text="", font=(FT, 1), text_color=BG)
        # search
        srow = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=14,
                            border_width=1, border_color=BORDER)
        srow.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(srow, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)
        self.dash_search_var = ctk.StringVar(value="")
        ent = ctk.CTkEntry(inner, textvariable=self.dash_search_var,
                           placeholder_text="🔍  Tìm trong toàn bộ khóa (transcript / mô tả)…",
                           font=(FT, 13), height=38, corner_radius=10,
                           border_color=BORDER, fg_color=CARD2)
        ent.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ent.bind("<Return>", lambda e: self.dash_run_search())
        btn(inner, "Tìm", self.dash_run_search, kind="accent", width=80, height=36).pack(side="left", padx=(0, 4))
        btn(inner, "Báo cáo", self.dash_export_report, kind="secondary", width=96, height=36).pack(side="left")

        self.dash_search_box = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=14,
                                            border_width=1, border_color=BORDER)

        # toolbar
        bar = ctk.CTkFrame(self.content, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        btn(bar, "➕  Thêm khóa mới", self.go_import, kind="accent", width=150).pack(side="left")
        btn(bar, "↻  Làm mới", self._dash_refresh, kind="secondary", width=110).pack(side="left", padx=6)
        btn(bar, "🔄  Quét cập nhật", self.batch_local_health, kind="secondary", width=140).pack(side="left", padx=2)
        btn(bar, "+ Hàng đợi", self.dash_enqueue_selected, kind="primary", width=130).pack(side="right")

        ctk.CTkLabel(self.content, text="KHÓA HỌC", font=(FT, 11, "bold"),
                     text_color=TEXT2).pack(anchor="w", pady=(6, 4))

        self.dash_list = ctk.CTkFrame(self.content, fg_color="transparent")
        self.dash_list.pack(fill="x")
        self.pick_var = ctk.StringVar(value="")
        self.dash_checks = {}
        self.prog_labels = {}
        self._dash_all_items = []
        items = self.existing_courses()
        if not items:
            empty = self.card()
            ctk.CTkLabel(empty, text="Chưa có khóa nào", font=(FT, 15, "bold"),
                         text_color=TEXT).pack(padx=20, pady=(20, 4))
            ctk.CTkLabel(empty, text="Bấm «Thêm khóa mới» để dump từ Skool.",
                         font=(FT, 12), text_color=TEXT2).pack(padx=20, pady=(0, 20))
        else:
            self.pick_var.set(items[0])
            self._dash_all_items = list(items)
            for it in items:
                self._dash_skeleton_card(it)
            self._dash_scan_async()

    def _dash_skeleton_card(self, item):
        card = ctk.CTkFrame(self.dash_list, fg_color=CARD, corner_radius=16,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=6)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 4))
        var = ctk.BooleanVar(value=False)
        self.dash_checks[item] = var
        ctk.CTkCheckBox(top, text="", variable=var, width=24,
                        fg_color=ACCENT, hover_color=ACCENT_H,
                        border_color=BORDER).pack(side="left")
        ctk.CTkRadioButton(top, text=item, variable=self.pick_var, value=item,
                           font=(FT, 14, "bold"), text_color=TEXT,
                           fg_color=ACCENT, hover_color=ACCENT_H,
                           border_color=BORDER).pack(side="left", padx=(4, 0))
        badge = ctk.CTkLabel(top, text="…", font=(FT, 11, "bold"),
                             text_color=TEXT2, fg_color=CARD2, corner_radius=999, padx=10, pady=3)
        badge.pack(side="right")
        prog = ctk.CTkLabel(card, text="đang tính…", font=(FT, 12), text_color=TEXT2, anchor="w")
        prog.pack(fill="x", padx=44, pady=(0, 4))
        pb = ctk.CTkProgressBar(card, height=8, corner_radius=4,
                                progress_color=ACCENT, fg_color=CARD2)
        pb.pack(fill="x", padx=44, pady=(0, 8))
        pb.set(0)
        acts = ctk.CTkFrame(card, fg_color="transparent")
        acts.pack(fill="x", padx=12, pady=(0, 12))
        btn(acts, "▶  Mở", lambda it=item: self._dash_open(it),
            kind="success", width=78, height=30).pack(side="left", padx=(0, 4))
        btn(acts, "Cập nhật", lambda it=item: self._dash_update(it),
            kind="secondary", width=88, height=30).pack(side="left", padx=2)
        btn(acts, "Chat", lambda it=item: self._dash_chat(it),
            kind="secondary", width=64, height=30).pack(side="left", padx=2)
        btn(acts, "Pack", lambda it=item: self.export_knowledge_pack(it),
            kind="secondary", width=64, height=30).pack(side="left", padx=2)
        btn(acts, "Sync", lambda it=item: self._dash_sync(it),
            kind="secondary", width=64, height=30).pack(side="left", padx=2)
        btn(acts, "+ Queue", lambda it=item: self._dash_enqueue_one(it),
            kind="soft", width=80, height=30).pack(side="left", padx=2)
        fail_btn = btn(acts, "Fail", lambda it=item: self._dash_show_fails(it),
                       kind="warn", width=64, height=30)
        fail_btn.pack_forget()
        btn(acts, "🗑", lambda it=item: self._dash_delete(it),
            kind="ghost", width=40, height=30).pack(side="right")
        self.prog_labels[item] = {"prog": prog, "badge": badge, "pb": pb, "card": card,
                                  "fail_btn": fail_btn, "acts": acts}

    def _dash_scan_async(self):
        def work():
            try:
                entries = P.scan_all()
            except Exception as e:
                entries = e
            self.ui_q.put(lambda: self._dash_apply(entries))
        threading.Thread(target=work, daemon=True).start()

    def _dash_apply(self, entries):
        if isinstance(entries, Exception):
            if hasattr(self, "dash_summary") and self.dash_summary.winfo_exists():
                self.dash_summary.configure(text=f"Lỗi quét: {entries}")
            return
        self.dash_entries = entries
        total_fails = 0
        try:
            import cleanup as CL
        except Exception:
            CL = None
        for e in entries:
            it = e["item"]
            s = e.get("scan") or {}
            self.scan_cache[it] = s
            w = self.prog_labels.get(it)
            if not w: continue
            try:
                if not w["prog"].winfo_exists(): continue
            except Exception:
                continue
            badge = e.get("badge") or P.status_badge(s)
            badge_txt = badge.get("label") or "?"
            n_fail = 0
            if CL:
                try:
                    n_fail = len(CL.load_fails(e["root"]))
                except Exception:
                    n_fail = 0
            total_fails += n_fail
            # uu tien: token het han (badge) · fail · update meta
            if n_fail and badge.get("code") != "token":
                badge_txt = f"⚠ {n_fail} fail"
            try:
                import updates as U
                meta = U.read_update_meta(e["root"])
                if meta and meta.get("has_updates") and n_fail == 0 and badge.get("code") != "token":
                    badge_txt = "🆕 " + (badge.get("label") or "Cập nhật")
            except Exception:
                pass
            # colored pill badge
            level = "muted"
            code = badge.get("code") or ""
            if n_fail or code == "token":
                level = "danger"
            elif code == "partial":
                level = "warn"
            elif code == "done":
                level = "ok"
            elif code in ("new", "info"):
                level = "info"
            fg, bg = badge_colors(level)
            try:
                w["badge"].configure(text=badge_txt, text_color=fg, fg_color=bg)
            except Exception:
                w["badge"].configure(text=badge_txt)
            prog_txt = self._fmt_prog(s)
            if n_fail:
                prog_txt += f" · ⚠ {n_fail} fail"
            w["prog"].configure(text=prog_txt)
            tot = s.get("total") or 0
            done = s.get("done") or 0
            pct = (done / tot) if tot else 0
            w["pb"].set(pct)
            try:
                w["pb"].configure(progress_color=(SUCCESS if pct >= 1 else ACCENT))
            except Exception:
                pass
            fb = w.get("fail_btn")
            if fb is not None:
                try:
                    if n_fail:
                        if not fb.winfo_ismapped():
                            fb.pack(side="left", padx=2)
                        fb.configure(text=f"⚠ {n_fail}")
                    else:
                        fb.pack_forget()
                except Exception:
                    pass
        st = P.warehouse_stats(entries)
        left = st["total"] - st["done"]
        nf = st.get("fails") or total_fails
        # update stat cards
        def _set_stat(box, value, sub=""):
            try:
                kids = box.winfo_children()
                if len(kids) >= 2:
                    kids[1].configure(text=value)
                if len(kids) >= 3 and sub:
                    kids[2].configure(text=sub)
            except Exception:
                pass
        if hasattr(self, "_stat_courses"):
            _set_stat(self._stat_courses, str(st["courses"]), "trong kho")
            _set_stat(self._stat_lessons, f"{st['done']}/{st['total']}",
                      "✓ đủ" if (st["total"] and left == 0) else f"còn {left}")
            _set_stat(self._stat_size, fmt_size(st["size"]), "video")
            alert_n = (st.get("expired") or 0) + nf
            _set_stat(self._stat_alert, str(alert_n),
                      f"🔑 {st.get('expired', 0)} · fail {nf}" if alert_n else "ổn định")

    def _dash_refresh(self):
        self.show_dashboard()

    def dash_run_search(self):
        q = (self.dash_search_var.get() if hasattr(self, "dash_search_var") else "").strip()
        if not q:
            messagebox.showinfo("Trống", "Nhập từ khóa để tìm trong kho khóa."); return
        self.write(f"🔍 Đang tìm: {q}…")
        def work():
            try:
                import search_lib as S
                return S.search_all(q, top_k=15, ensure_index=False)
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                messagebox.showerror("Tìm kiếm", str(r)); return
            self._dash_show_hits(q, r or [])
        self.run_async(work, cb)

    def _dash_show_hits(self, q, hits):
        if not (hasattr(self, "dash_search_box") and self.dash_search_box.winfo_exists()):
            return
        for w in self.dash_search_box.winfo_children():
            w.destroy()
        self.dash_search_box.pack(fill="x", pady=(0, 8), before=self.dash_list if hasattr(self, "dash_list") else None)
        ctk.CTkLabel(self.dash_search_box, text=f"Kết quả «{q}» — {len(hits)} bài",
                     font=(FT, 12, "bold"), text_color=PRIMARY).pack(anchor="w", padx=12, pady=(10, 4))
        if not hits:
            ctk.CTkLabel(self.dash_search_box, text="Không thấy. Thử Index lại trong Chat RAG rồi tìm lại.",
                         font=(FT, 12), text_color=TEXT2).pack(anchor="w", padx=12, pady=(0, 10))
            return
        for h in hits[:12]:
            row = ctk.CTkFrame(self.dash_search_box, fg_color="transparent"); row.pack(fill="x", padx=10, pady=2)
            label = f"[{h.get('course')}] {h.get('chapter')} / {h.get('title')}"
            ctk.CTkLabel(row, text=label if len(label) < 70 else label[:67] + "…",
                         font=(FT, 12), text_color=TEXT, anchor="w").pack(side="left", fill="x", expand=True)
            course = h.get("course")
            # map course name -> display item
            def open_hit(c=course):
                items = self.existing_courses()
                for it in items:
                    if self.item_course(it) == c or it == c or (c == "SkoolCourse" and it.startswith("SkoolCourse")):
                        self._dash_open(it); return
                messagebox.showinfo("Khóa", f"Không map được khóa: {c}")
            btn(row, "Mở", open_hit, kind="ghost", width=50, height=26).pack(side="right")
        ctk.CTkLabel(self.dash_search_box, text="", height=4).pack()

    def dash_export_report(self):
        self.write("Đang tạo báo cáo kho…")
        def work():
            try:
                import search_lib as S
                import config as C2
                md, entries = S.warehouse_report()
                out = C2.BASE / "courses" / "_Warehouse_Report.md"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(md, encoding="utf-8")
                return str(out), len(entries)
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                messagebox.showerror("Báo cáo", str(r)); return
            path, n = r
            self.write(f"✓ Báo cáo: {path} ({n} khóa)")
            messagebox.showinfo("Báo cáo", f"Đã ghi:\n{path}")
            self._open_path(Path(path).parent)
        self.run_async(work, cb)

    def _fmt_prog(self, s):
        if isinstance(s, Exception) or not s or not s.get("has_data"): return "chưa có dữ liệu"
        done, tot = s["done"], s["total"]
        if tot and done >= tot: return f"✓ đủ {tot} bài · {fmt_size(s['size'])}"
        nat = len(s.get("native_expired") or [])
        tag = f" · {nat} native hết hạn" if nat else ""
        return f"{done}/{tot} bài · còn {tot - done} · {fmt_size(s['size'])}{tag}"

    def _scan_all_async(self, items):
        """Giữ tương thích chỗ cũ (report…)."""
        for it in items:
            def cb(s, it=it):
                if not isinstance(s, Exception): self.scan_cache[it] = s
            self.run_async(lambda it=it: P.scan(self.item_root(it)), cb)

    def _dash_open(self, item):
        self.pick_var.set(item)
        self.mode = "existing"; self.course_name = self.item_course(item); self.show_manager()

    def _dash_show_fails(self, item):
        """Mo khoa + hien dialog fail (tu Dashboard)."""
        self.pick_var.set(item)
        self.course_name = self.item_course(item)
        fails = self._load_fails(self.course_name)
        if not fails:
            messagebox.showinfo("Fails", f"«{item}» không có video_fails.json."); return
        self._show_fails_dialog(fails)
        if messagebox.askyesno("Mở trình tải?", f"Mở «{item}» để tải lại / cứu native?"):
            self._dash_open(item)

    def _dash_update(self, item):
        self.pick_var.set(item); self.check_updates()

    def _dash_chat(self, item):
        self.pick_var.set(item)
        self.course_name = self.item_course(item)
        self.show_chat(preselect=item)

    def _dash_sync(self, item):
        self.pick_var.set(item)
        self.course_name = self.item_course(item)
        self._cloud_sync_course(item)

    def _dash_delete(self, item):
        self.pick_var.set(item); self.delete_course()

    def _dash_enqueue_one(self, item):
        try:
            import queue_engine as QE
            course = self.item_course(item)
            QE.add_jobs([course], kind="full", until_clean=True)
            self.write(f"✓ Đã thêm vào hàng đợi: {item}")
            messagebox.showinfo("Hàng đợi", f"Đã thêm «{item}» vào hàng đợi.\nMở Hàng đợi ở sidebar để chạy.")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def dash_enqueue_selected(self):
        items = [it for it, v in (self.dash_checks or {}).items() if v.get()]
        if not items:
            # fallback: khoa dang radio-chon
            v = self.pick_var.get().strip() if hasattr(self, "pick_var") else ""
            if v: items = [v]
        if not items:
            messagebox.showinfo("Chưa chọn", "Tick ít nhất 1 khóa (ô checkbox) hoặc chọn radio rồi thử lại."); return
        try:
            import queue_engine as QE
            courses = [self.item_course(it) for it in items]
            QE.add_jobs(courses, kind="full", until_clean=True)
            self.write(f"✓ Đã thêm {len(courses)} khóa vào hàng đợi.")
            if messagebox.askyesno("Hàng đợi", f"Đã thêm {len(courses)} khóa.\nMở màn Hàng đợi ngay?"):
                self.show_queue()
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def batch_local_health(self):
        """S3: quet local tat ca khoa, ghi badge / _update_diff nhe."""
        self.write("Đang quét sức khỏe local toàn kho…")
        def work():
            try:
                import updates as U
                results = []
                for meta in P.list_course_items():
                    h = U.local_health(meta["root"])
                    # ghi meta nhe de dashboard hien 🆕 khi con thieu
                    if h.get("needs_attention"):
                        s = h["scan"]
                        U.mark_update_meta(meta["root"], {
                            "summary": f"Còn {(s.get('total') or 0) - (s.get('done') or 0)} bài · "
                                       f"{len(s.get('native_expired') or [])} hết hạn",
                            "has_updates": True,
                            "new_chapters": [],
                            "missing_lessons": s.get("missing") or [],
                            "native_expired": s.get("native_expired") or [],
                            "scan": {"total": s.get("total"), "done": s.get("done"),
                                     "size": s.get("size"), "has_data": s.get("has_data")},
                        })
                    results.append((meta["item"], h))
                return results
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                messagebox.showerror("Lỗi", str(r)); return
            attn = sum(1 for _, h in r if h.get("needs_attention"))
            self.write(f"Quét xong: {attn}/{len(r)} khóa cần chú ý.")
            self.show_dashboard()
        self.run_async(work, cb)

    def use_existing(self):
        v = self.pick_var.get().strip()
        if not v: return
        self.mode = "existing"; self.course_name = self.item_course(v); self.show_manager()

    def go_import(self): self.mode = "new"; self.purpose = "import"; self.show_step2()

    # ---------- B3: kiem tra cap nhat khoa ----------
    def _saved_titles(self, root):
        """Ten chuong da luu (tu _chapters.json) -> de danh dau chuong MOI khi cap nhat."""
        import json
        titles = set(); cj = Path(root) / "_chapters.json"
        try:
            if cj.exists():
                for t in json.loads(cj.read_text(encoding="utf-8-sig")):
                    titles.add(K.san(t if isinstance(t, str) else t.get("title", "")))
        except Exception: pass
        return titles

    def check_updates(self):
        v = self.pick_var.get().strip()
        if not v: return
        self.mode = "existing"; self.course_name = self.item_course(v); self.purpose = "update"
        try:
            import updates as U
            self.known_titles = U.saved_chapter_titles(self.item_root(v))
        except Exception:
            self.known_titles = self._saved_titles(self.item_root(v))
        self.show_step2()

    # ---------- xoa khoa ----------
    def _trash_available(self):
        import importlib.util
        return importlib.util.find_spec("send2trash") is not None

    def delete_course(self):
        if self.proc:
            messagebox.showinfo("Đang bận", "Đang có tác vụ chạy — hãy dừng trước khi xóa."); return
        v = self.pick_var.get().strip()
        if not v:
            messagebox.showinfo("Chưa chọn", "Hãy chọn một khóa để xóa."); return
        root = self.item_root(v)
        if not root.exists():
            messagebox.showinfo("Không có", "Khóa này không còn thư mục trên máy."); self.show_step1(); return
        s = self.scan_cache.get(v)
        info = f"~{s['total']} bài · {fmt_size(s['size'])}" if s else "(chưa tính dung lượng)"
        trash = self._trash_available()
        where = "chuyển vào Thùng rác (khôi phục được)" if trash else "XÓA VĨNH VIỄN — KHÔNG hoàn tác được"
        if not messagebox.askyesno(
                "Xóa khóa",
                f"Xóa khóa:\n   {v}\n   {root}\n\n{info}\n\nApp sẽ {where}.\nTiếp tục?",
                icon="warning"):
            return
        self.write(f"Đang xóa khóa: {v} …")
        def work():
            try:
                if trash:
                    from send2trash import send2trash as s2t; s2t(str(root))
                else:
                    import shutil; shutil.rmtree(root, ignore_errors=False)
                self.ui_q.put(lambda: self._after_delete(v, True, ""))
            except Exception as e:
                self.ui_q.put(lambda e=e: self._after_delete(v, False, str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _after_delete(self, v, ok, err):
        if ok:
            self.write(f"✓ Đã xóa khóa: {v}")
            self.scan_cache.pop(v, None)
            messagebox.showinfo("Đã xóa", f"Đã xóa khóa: {v}")
        else:
            self.write(f"[LỖI xóa] {err}")
            messagebox.showerror("Lỗi", f"Không xóa được khóa:\n{err}")
        self.show_dashboard()

    # ====================== BƯỚC 2 ======================
    def show_step2(self):
        self.set_step(2); self.clear()
        cn = self.course_name or "SkoolCourse"
        heads = {
            "import": ("Lấy khóa mới từ Skool",
                       "Làm theo 3 bước. App mở trình duyệt riêng — đăng nhập, mở đúng khóa, app lấy danh sách chương."),
            "update": (f"Kiểm tra cập nhật: {cn}",
                       "Mở đúng khóa → Lấy danh sách. Chương MỚI được tick sẵn — chỉ dump/tải phần mới."),
            "rescue": (f"Cứu bài native hết hạn: {cn}",
                       "Mở đúng khóa → Lấy danh sách. App dump lại token các chương cần cứu rồi tải native."),
        }
        h, sub = heads.get(self.purpose, heads["import"])
        self.head(h, sub)

        # step guide cards
        guide = ctk.CTkFrame(self.content, fg_color="transparent")
        guide.pack(fill="x", pady=(0, 8))
        for i, (title, desc) in enumerate((
            ("1  Đăng nhập", "Mở Skool trong cửa sổ app"),
            ("2  Danh sách", "Đọc chương từ Classroom"),
            ("3  Dump", "Lưu JSON + tải về"),
        ), 1):
            g = ctk.CTkFrame(guide, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER)
            g.pack(side="left", expand=True, fill="both", padx=4)
            ctk.CTkLabel(g, text=title, font=(FT, 12, "bold"), text_color=ACCENT).pack(anchor="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(g, text=desc, font=(FT, 11), text_color=TEXT2).pack(anchor="w", padx=12, pady=(2, 12))

        f = self.card()
        fin = ctk.CTkFrame(f, fg_color="transparent")
        fin.pack(fill="x", padx=12, pady=12)
        self.b_open = btn(fin, "1.   Mở Skool & đăng nhập", self.do_open, kind="accent", height=44)
        self.b_open.pack(fill="x", pady=4)
        lbl2 = "2.   Lấy danh sách & " + ("cứu native" if self.purpose == "rescue" else "chương")
        self.b_list = btn(fin, lbl2, self.do_list, kind="secondary", height=44, state="disabled")
        self.b_list.pack(fill="x", pady=4)

        self.chap_box = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=16,
                                     border_width=1, border_color=BORDER)
        self.dump_row = ctk.CTkFrame(self.content, fg_color="transparent")
        btn(self.content, "←  Dashboard", self.show_dashboard, kind="ghost", width=120).pack(anchor="w", pady=10)

    def do_open(self):
        if self.sb is None:
            self.write("Đang mở trình duyệt (lần đầu hơi lâu)...")
            try:
                from skool_browser import SkoolBrowser; self.sb = SkoolBrowser()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không mở được trình duyệt: {e}")
        else:
            self.sb.open()

    def do_list(self):
        if self.sb:
            self.write("Đang đọc danh sách chương...")
            self.sb.list_chapters()

    def render_chapters(self, group, chapters):
        for w in self.chap_box.winfo_children():
            w.destroy()
        for w in self.dump_row.winfo_children():
            w.destroy()
        self.chap_box.pack(fill="x", pady=8)
        self.dump_row.pack(fill="x", pady=4)
        upd = (self.purpose == "update")
        self._last_update_diff = None
        if upd:
            try:
                import updates as U
                diff = U.diff_remote_chapters(self.course_root(self.course_name), chapters)
                U.mark_update_meta(self.course_root(self.course_name), diff)
                self._last_update_diff = diff
                self.write(f"Diff: {diff.get('summary')}")
            except Exception as e:
                self.write(f"[diff] {e}")
        n_new = sum(1 for c in chapters if K.san(c["title"]) not in self.known_titles) if upd else len(chapters)
        extra = ""
        if upd and self._last_update_diff:
            d = self._last_update_diff
            extra = f"  ·  {len(d.get('missing_lessons') or [])} thiếu  ·  {len(d.get('native_expired') or [])} hết hạn"
        hdr = ctk.CTkFrame(self.chap_box, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkLabel(hdr, text=f"Khóa: {group}", font=(FT, 13, "bold"), text_color=TEXT).pack(side="left")
        if upd:
            self.pill(hdr, f"{n_new} mới{extra}", "info" if n_new else "muted").pack(side="right")
        else:
            self.pill(hdr, f"{len(chapters)} chương", "muted").pack(side="right")

        self.chapters = []
        for c in chapters:
            is_new = (not upd) or (K.san(c["title"]) not in self.known_titles)
            var = ctk.BooleanVar(value=is_new)
            row = ctk.CTkFrame(self.chap_box, fg_color=(ACCENT_SOFT if (upd and is_new) else "transparent"),
                               corner_radius=8)
            row.pack(fill="x", padx=10, pady=2)
            label = c["title"] + ("   · MỚI" if (upd and is_new) else "")
            tc = ACCENT if (upd and is_new) else TEXT
            ctk.CTkCheckBox(row, text=label, variable=var, font=(FT, 13), text_color=tc,
                            fg_color=ACCENT, hover_color=ACCENT_H, border_color=BORDER).pack(
                anchor="w", padx=8, pady=6)
            self.chapters.append({"id": c["id"], "title": c["title"], "var": var})

        dump_card = ctk.CTkFrame(self.dump_row, fg_color=CARD, corner_radius=16,
                                 border_width=1, border_color=BORDER)
        dump_card.pack(fill="x", pady=6)
        nm = ctk.CTkFrame(dump_card, fg_color="transparent")
        nm.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(nm, text="Tên khóa", font=(FT, 12, "bold"), text_color=TEXT2).pack(side="left")
        self.name_var = ctk.StringVar(value=(self.course_name or group) if upd else group)
        ctk.CTkEntry(nm, textvariable=self.name_var, font=(FT, 13), height=36, corner_radius=10,
                     fg_color=CARD2, border_color=BORDER).pack(side="left", fill="x", expand=True, padx=(10, 0))
        dump_label = ("3.   Tải bổ sung các chương đã chọn  →" if upd else "3.   Tải dữ liệu các chương đã chọn  →")
        self.b_dump = btn(dump_card, dump_label, self.do_dump, kind="accent", height=44)
        self.b_dump.pack(fill="x", padx=14, pady=(4, 8))
        self.dump_status = ctk.CTkLabel(dump_card, text="", font=(FT, 12, "bold"), text_color=ACCENT)
        self.dump_status.pack(anchor="w", padx=14)
        self.dump_pb = ctk.CTkProgressBar(dump_card, height=10, corner_radius=6,
                                          progress_color=ACCENT, fg_color=CARD2)
        self.dump_pb.set(0)
        ctk.CTkFrame(dump_card, height=10, fg_color="transparent").pack()

    def do_dump(self):
        if self._dumping: return
        sel = [c for c in self.chapters if c["var"].get()]
        if not sel: messagebox.showinfo("Chưa chọn", "Hãy tick ít nhất 1 chương."); return
        name = self.name_var.get().strip()
        if not name: messagebox.showinfo("Thiếu tên", "Hãy đặt tên khóa."); return
        if self.purpose == "update":
            out = self.course_root(self.course_name)        # cap nhat -> ghi vao dung khoa cu
        else:
            self.course_name = name; out = C.BASE / "courses" / name
        self._dumping = True
        self.b_dump.configure(state="disabled", text="⏳   Đang lấy dữ liệu...")
        self.dump_status.configure(text=f"Đang lấy dữ liệu: 0/{len(sel)} chương")
        try:
            self.dump_pb.pack(fill="x", padx=14, pady=(2, 10))
        except Exception:
            self.dump_pb.pack(fill="x", pady=(2, 6))
        self.dump_pb.set(0)
        self.write(f"Đang lấy dữ liệu {len(sel)} chương vào: {out}")
        self.sb.dump([{"id": c["id"], "title": c["title"]} for c in sel], out, all_titles=self.live_titles or None)

    # ====================== BƯỚC 3 ======================
    def show_step3(self):
        self.set_step(3); self.clear(); self.purpose = "import"
        nm = self.course_name or "SkoolCourse (khóa hiện tại)"
        self.head(f"Tải khóa: {nm}", "Chỉ tải phần còn thiếu. Có thể bật phụ đề tiếng Anh chạy ngầm sau khi tải.")
        sumcard = self.card()
        self.sum_lbl = ctk.CTkLabel(sumcard, text="⏳  Đang kiểm tra tiến độ…", font=(FT, 13),
                                    text_color=TEXT2, justify="left", wraplength=560)
        self.sum_lbl.pack(anchor="w", padx=16, pady=14)
        self.native_banner = ctk.CTkFrame(self.content, fg_color="transparent")
        self.native_banner.pack(fill="x")
        card = self.card()
        self.opt_sub = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="Tạo phụ đề tiếng Anh (chạy ngầm sau khi tải xong)",
                        variable=self.opt_sub, font=(FT, 13), text_color=TEXT,
                        fg_color=ACCENT, hover_color=ACCENT_H, border_color=BORDER).pack(anchor="w", padx=16, pady=(14, 6))
        self.opt_clean = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="🔁 Tự thử lại đến khi tải đủ (chờ nếu bị giới hạn)",
                        variable=self.opt_clean, font=(FT, 13), text_color=TEXT,
                        fg_color=ACCENT, hover_color=ACCENT_H, border_color=BORDER).pack(anchor="w", padx=16, pady=(0, 14))
        self.opt_test = ctk.BooleanVar(value=self.admin)
        if self.admin:
            ctk.CTkCheckBox(card, text="🔧 TEST — dry-run, không tải thật",
                            variable=self.opt_test, font=(FT, 13, "bold"), text_color=WARNING,
                            fg_color=WARNING, hover_color="#B45309", border_color=BORDER).pack(anchor="w", padx=16, pady=(0, 14))
        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", pady=16)
        btn(row, "←  Quay lại", self.show_dashboard, kind="ghost", width=110).pack(side="left")
        self.b_start = btn(row, "▶   Bắt đầu tải", self.start_download, kind="success", width=210, height=46)
        self.b_start.pack(side="right")
        self._scan_current_async()

    def _scan_current_async(self):
        def cb(s):
            self.last_scan = None if isinstance(s, Exception) else s
            if hasattr(self, "sum_lbl") and self.sum_lbl.winfo_exists(): self.sum_lbl.configure(text=self._summary_text(s))
            self._update_start_btn(s); self._maybe_native_banner(s)
        self.run_async(lambda: P.scan(self.course_root(self.course_name)), cb)

    def _summary_text(self, s):
        if isinstance(s, Exception) or not s or not s.get("has_data"):
            return "Khóa chưa có dữ liệu chương. Dùng “Thêm khóa mới” hoặc “Kiểm tra cập nhật” để lấy danh sách trước."
        done, tot, left = s["done"], s["total"], s["total"] - s["done"]
        base = f"Đã tải {done}/{tot} bài  ·  {fmt_size(s['size'])}.  "
        if tot and done >= tot: return base + "✓ Đã tải đủ — bấm để kiểm tra/tải bổ sung."
        nat = len(s.get("native_expired") or [])
        tail = f"  ·  {nat} bài native hết hạn token (cần cứu)." if nat else ""
        return base + f"Còn {left} bài chưa tải." + tail

    def _update_start_btn(self, s):
        if not (hasattr(self, "b_start") and self.b_start.winfo_exists()): return
        if isinstance(s, Exception) or not s or not s.get("has_data"):
            self.b_start.configure(text="▶   Bắt đầu tải"); return
        done, tot, left = s["done"], s["total"], s["total"] - s["done"]
        if tot and done >= tot: self.b_start.configure(text="↻   Kiểm tra / tải bổ sung")
        elif done > 0:          self.b_start.configure(text=f"▶   Tải tiếp (còn {left} bài)")
        else:                   self.b_start.configure(text="▶   Bắt đầu tải")

    def _maybe_native_banner(self, s):
        if not (hasattr(self, "native_banner") and self.native_banner.winfo_exists()): return
        for w in self.native_banner.winfo_children(): w.destroy()
        if isinstance(s, Exception) or not s: return
        n = len(s.get("native_expired") or [])
        if not n: return
        ban = ctk.CTkFrame(self.native_banner, fg_color="#FFF7ED", corner_radius=12, border_width=1, border_color="#FDBA74")
        ban.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(ban, text=f"🔑  {n} bài native hết hạn token — cần lấy lại token mới rồi tải.",
                     text_color="#9A3412", font=(FT, 12, "bold")).pack(side="left", padx=14, pady=10)
        btn(ban, "Cứu bài native", self.rescue_native, kind="warn", width=140).pack(side="right", padx=10, pady=8)

    # ====================== BƯỚC 4 ======================
    def show_step4(self):
        self.set_step(4); self.clear()
        self.head("Đang tải khóa…", "Theo dõi tiến trình. Dừng bất cứ lúc nào — chạy lại sẽ resume. Mở thư mục để xem file ngay.")
        self.build_progress()
        ov = self.card()
        ctk.CTkLabel(ov, text=f"Khóa: {self.course_name or 'SkoolCourse'}",
                     font=(FT, 13, "bold"), text_color=ACCENT).pack(anchor="w", padx=18, pady=(14, 2))
        b = ctk.CTkFrame(ov, fg_color="transparent"); b.pack(fill="x", padx=18, pady=(2, 16))
        self.pct_lbl = ctk.CTkLabel(b, text="0%", font=(FT, 42, "bold"), text_color=TEXT)
        self.pct_lbl.pack(side="left")
        r = ctk.CTkFrame(b, fg_color="transparent"); r.pack(side="left", fill="x", expand=True, padx=18)
        self.pb4 = ctk.CTkProgressBar(r, height=14, corner_radius=8,
                                      progress_color=ACCENT, fg_color=CARD2)
        self.pb4.pack(fill="x", pady=(18, 6)); self.pb4.set(0)
        self.status4 = ctk.CTkLabel(r, text="", font=("Consolas", 12), text_color=TEXT2)
        self.status4.pack(anchor="w")
        self.chap_hdr = ctk.CTkLabel(self.content, text="Chương", font=(FT, 13, "bold"),
                                     text_color=TEXT2)
        self.chap_hdr.pack(anchor="w", pady=(10, 4))
        self.chap_scroll = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=16,
                                        border_width=1, border_color=BORDER)
        self.chap_scroll.pack(fill="x", pady=(0, 6))
        self.run_lbl = ctk.CTkLabel(self.content, text="⏳  Đang chạy…", font=(FT, 13, "bold"),
                                    text_color=WARNING)
        self.run_lbl.pack(anchor="w", pady=(10, 4))
        self.done_row = ctk.CTkFrame(self.content, fg_color="transparent")
        self.done_row.pack(fill="x", pady=8)
        btn(self.done_row, "📁  Mở thư mục", self.open_folder, kind="secondary", width=160).pack(side="left", padx=(0, 8))
        self.btn_stop = btn(self.done_row, "■  Dừng", self.do_stop, kind="danger", width=120)
        self.btn_stop.pack(side="left")
        self.build_chapter_rows(); self.refresh4()

    def build_chapter_rows(self):
        self.chap_widgets = {}; self._last4 = {}
        for w in self.chap_scroll.winfo_children(): w.destroy()
        if not self._prog:
            ctk.CTkLabel(self.chap_scroll, text="(Chưa có dữ liệu chương — bắt đầu tải để thấy tiến trình)", font=(FT, 12), text_color=TEXT2).pack(anchor="w", padx=10, pady=12); return
        for ch in self._prog:
            row = ctk.CTkFrame(self.chap_scroll, fg_color="transparent"); row.pack(fill="x", padx=4, pady=3)
            ic = ctk.CTkLabel(row, text="•", text_color=TEXT2, font=(FT, 15, "bold"), width=24); ic.pack(side="left")
            nm = ch["name"]; nm = nm if len(nm) <= 38 else nm[:37] + "…"
            ctk.CTkLabel(row, text=nm, font=(FT, 13), text_color=TEXT, width=270, anchor="w").pack(side="left")
            pb = ctk.CTkProgressBar(row, width=120, height=8, corner_radius=4, progress_color=PRIMARY); pb.pack(side="left", padx=8); pb.set(0)
            cnt = ctk.CTkLabel(row, text="0/0", font=("Consolas", 12), text_color=TEXT2, width=64, anchor="e"); cnt.pack(side="left", padx=6)
            pct = ctk.CTkLabel(row, text="0%", font=("Consolas", 12, "bold"), text_color=PRIMARY, width=48, anchor="e"); pct.pack(side="left")
            self.chap_widgets[ch["name"]] = {"ic": ic, "pb": pb, "cnt": cnt, "pct": pct}

    def refresh4(self):
        """Quet tien do o LUONG PHU (stat hang tram file) -> khong lam dung/giat giao dien."""
        if not hasattr(self, "pct_lbl"): return
        if getattr(self, "_refreshing", False): return
        self._refreshing = True
        def work():
            try: data = self.scan_progress()
            except Exception: data = None
            self.ui_q.put(lambda: self._apply_refresh4(data))
        threading.Thread(target=work, daemon=True).start()

    def _apply_refresh4(self, data):
        self._refreshing = False
        if data is None: return
        if not (hasattr(self, "pct_lbl") and self.pct_lbl.winfo_exists()): return
        rows, dtot, etot, size = data
        pct = round(dtot * 100 / etot) if etot else 0
        last = getattr(self, "_last4", {})
        def setc(key, fn, val):           # chi cap nhat khi GIA TRI doi -> bot ve lai (giat)
            if last.get(key) != val: fn(val); last[key] = val
        setc("pct", lambda v: self.pct_lbl.configure(text=v), f"{pct}%")
        setc("pb4", lambda v: self.pb4.set(v), pct / 100)
        setc("st", lambda v: self.status4.configure(text=v), f"{dtot}/{etot} video   ·   {fmt_size(size)}")
        setc("hdr", lambda v: self.chap_hdr.configure(text=v), f"Chương ({len(rows)})")
        for r in rows:
            w = self.chap_widgets.get(r["name"])
            if not w: continue
            ic, col = ICON.get(r["status"], ("•", TEXT2))
            p = round(r["done"] * 100 / r["exp"]) if r["exp"] else 0
            nm = r["name"]
            setc(("ic", nm), lambda v, w=w: w["ic"].configure(text=v[0], text_color=v[1]), (ic, col))
            setc(("pb", nm), lambda v, w=w: w["pb"].set(v), p / 100)
            setc(("cnt", nm), lambda v, w=w: w["cnt"].configure(text=v), f"{r['done']}/{r['exp']}")
            setc(("pct", nm), lambda v, w=w: w["pct"].configure(text=v), f"{p}%")
        self._last4 = last

    def show_done(self):
        for w in self.done_row.winfo_children(): w.destroy()
        self.refresh4()
        if hasattr(self, "run_lbl"): self.run_lbl.configure(text="✓  Hoàn tất", text_color=SUCCESS)
        if getattr(self, "opt_sub", None) and self.opt_sub.get(): self.write("Bật phụ đề chạy ngầm..."); self.run_sub_on()
        self._maybe_cloud_after(self.course_name)
        # auto index (Sprint A) — nen, khong block
        self._maybe_auto_index()
        self._show_fails_panel(self.content)
        btn(self.done_row, "📁  Mở thư mục", self.open_folder, kind="secondary", width=140).pack(side="left", padx=(0, 6))
        btn(self.done_row, "📦 Pack", lambda: self.export_knowledge_pack(), kind="soft", width=90).pack(side="left", padx=(0, 6))
        btn(self.done_row, "📄 Xuất", self.show_report, kind="secondary", width=100).pack(side="left", padx=(0, 6))
        btn(self.done_row, "↻ Dashboard", self.show_dashboard, kind="accent", width=130).pack(side="left")

    def _maybe_auto_index(self):
        """Index RAG sau tai neu AUTO_INDEX (khong hoi)."""
        try:
            if not getattr(C, "AUTO_INDEX", True):
                return
        except Exception:
            return
        root = self.course_root(self.course_name)
        self.write("📇 Auto-index RAG (nền)…")
        def work():
            try:
                from rag.index import build_catalog
                return build_catalog(root, log=lambda s: self.ui_q.put(lambda m=s: self.write(m)))
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                self.write(f"[index] {r}")
            else:
                self.write(f"📇 Index xong: {r.get('n_lessons', 0)} bài")
        self.run_async(work, cb)

    def _load_fails(self, course_name=None):
        try:
            import cleanup as CL
            return CL.load_fails(self.course_root(course_name if course_name is not None else self.course_name))
        except Exception:
            return []

    def _show_fails_panel(self, parent=None):
        """Hien panel bai that bai + goi y (token / bot / rate)."""
        parent = parent or self.content
        fails = self._load_fails()
        if not fails:
            return
        try:
            import cleanup as CL
            groups = CL.summarize_fails(fails)
        except Exception:
            groups = []
        card = ctk.CTkFrame(parent, fg_color=WARNING_BG, corner_radius=14,
                            border_width=1, border_color="#FCD34D")
        card.pack(fill="x", pady=8)
        ctk.CTkLabel(card, text=f"⚠  {len(fails)} bài tải thất bại",
                     font=(FT, 13, "bold"), text_color="#92400E").pack(anchor="w", padx=14, pady=(12, 4))
        for g in groups[:6]:
            line = f"• [{g['code']}] ×{g['count']} — {g['message']}"
            ctk.CTkLabel(card, text=line, font=(FT, 12), text_color="#78350F",
                         wraplength=560, justify="left").pack(anchor="w", padx=18, pady=1)
            if g.get("fix"):
                ctk.CTkLabel(card, text=f"   → {g['fix']}", font=(FT, 11), text_color=TEXT2,
                             wraplength=540, justify="left").pack(anchor="w", padx=18)
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=12, pady=(8, 12))
        codes = {g["code"] for g in groups}
        if "token" in codes:
            btn(row, "🔑 Cứu native", self.rescue_from_fails, kind="warn", width=130, height=32).pack(side="left", padx=2)
        if "bot" in codes:
            btn(row, "Node.js / cookies", self.show_check, kind="secondary", width=140, height=32).pack(side="left", padx=2)
        btn(row, "↻ Chỉ tải fail", self.retry_failed_only, kind="accent", width=120, height=32).pack(side="left", padx=2)
        btn(row, "↻ Tải thiếu", self._retry_download_after_fails, kind="secondary", width=100, height=32).pack(side="left", padx=2)
        btn(row, "🗑 Dọn dở", self.cleanup_partials, kind="ghost", width=90, height=32).pack(side="left", padx=2)
        self.write(f"⚠ {len(fails)} bài fail — xem panel phía trên / video_fails.json")

    def rescue_from_fails(self):
        """Cuu native: uu tien scan hien tai, fallback mo update flow."""
        root = self.course_root(self.course_name)
        def work():
            try:
                return P.scan(root)
            except Exception as e:
                return e
        def cb(s):
            if isinstance(s, Exception) or not s:
                messagebox.showinfo("Cứu native", "Không quét được. Dùng «Cập nhật» rồi dump lại chương."); return
            self.last_scan = s
            if s.get("native_expired"):
                self.rescue_native()
            else:
                # co fail token nhung scan chua danh dau — van mo dump update
                messagebox.showinfo(
                    "Cứu native",
                    "Mở trình duyệt để dump lại token chương còn thiếu.\n"
                    "Chọn các chương cần thiết rồi tải lại.")
                self.purpose = "update"
                try:
                    import updates as U
                    self.known_titles = U.saved_chapter_titles(root)
                except Exception:
                    self.known_titles = self._saved_titles(root)
                self.show_step2()
        self.run_async(work, cb)

    def _retry_download_after_fails(self):
        """Tai lai (until-clean) sau khi user da fix env/token."""
        if self.proc:
            messagebox.showinfo("Đang bận", "Đang có tác vụ chạy."); return
        args = self._course_args() + ["--until-clean"]
        self.write("↻ Tải lại các bài còn thiếu…")
        self.start([PY, "main.py"] + args, "TẢI LẠI", on_done=self.show_manager)

    def retry_failed_only(self, codes=None):
        """Chi tai lai folder trong video_fails.json (fail-driven)."""
        if self.proc:
            messagebox.showinfo("Đang bận", "Đang có tác vụ chạy."); return
        fails = self._load_fails()
        if not fails:
            messagebox.showinfo("Fails", "Không có video_fails.json."); return
        args = self._course_args() + ["--only", "videos", "--retry-failed", "--until-clean", "--skip-preflight"]
        if codes:
            args += ["--fail-codes", ",".join(codes)]
        n = len(fails)
        self.write(f"↻ Chỉ tải {n} bài fail…")
        self.start([PY, "main.py"] + args, "TẢI LẠI FAIL", on_done=self._after_retry_failed)

    def _after_retry_failed(self):
        self.show_manager()
        # goi y index
        if messagebox.askyesno("Index RAG?", "Tải fail xong. Build lại index chat (catalog + TF-IDF)?"):
            self._run_index_current()

    def _run_index_current(self):
        if self.proc:
            return
        args = self._course_args() + ["--only", "audit", "--index", "--skip-preflight"]
        # audit no-op-ish; dung main --index via only videos dry? better call knowledge path
        root = self.course_root(self.course_name)
        self.write("📇 Đang index RAG…")
        def work():
            try:
                from rag.index import build_catalog
                return build_catalog(root, log=lambda s: self.ui_q.put(lambda m=s: self.write(m)))
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                messagebox.showerror("Index", str(r))
            else:
                messagebox.showinfo("Index", f"Đã index {r.get('n_lessons', 0)} bài")
        self.run_async(work, cb)

    def export_knowledge_pack(self, item=None):
        """Zip knowledge pack (text) cho khoa."""
        if item:
            self.pick_var.set(item) if hasattr(self, "pick_var") else None
            course = self.item_course(item)
            root = self.item_root(item)
            name = item
        else:
            course = self.course_name
            root = self.course_root(course)
            name = course or "SkoolCourse"
        self.write(f"📦 Knowledge pack: {name}…")
        def work():
            try:
                import knowledge_pack as KP
                return str(KP.pack_course(root, course_name=course or name,
                                          log=lambda s: self.ui_q.put(lambda m=s: self.write(m))))
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                messagebox.showerror("Knowledge pack", str(r)); return
            if messagebox.askyesno("Xong", f"Đã tạo:\n{r}\n\nMở thư mục?"):
                self._open_path(Path(r).parent)
        self.run_async(work, cb)

    def cleanup_partials(self):
        root = self.course_root(self.course_name)
        def work():
            try:
                import cleanup as CL
                listed = CL.find_stale_downloads(root, min_age_sec=0)
                if not listed:
                    return {"found": 0}
                return CL.cleanup_stale(root, apply=True, min_age_sec=60,
                                        log=lambda s: self.ui_q.put(lambda m=s: self.write(m)))
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                messagebox.showerror("Dọn rác", str(r)); return
            if r.get("found") == 0:
                messagebox.showinfo("Dọn rác", "Không có file .part/.ytdl thừa."); return
            messagebox.showinfo("Dọn rác", f"Đã xóa {r.get('deleted', 0)}/{r.get('found', 0)} file · giải phóng {r.get('bytes', 0)} bytes")
        if not messagebox.askyesno("Dọn file dở", "Xóa các file tải dở (.part, .ytdl) cũ hơn 1 phút?\nKhông ảnh hưởng video đã tải xong."):
            return
        self.write("🗑 Đang dọn file tải dở…")
        self.run_async(work, cb)

    # ====================== TRÌNH TẢI (theo chương / bài) ======================
    def show_manager(self):
        self.set_step(4); self.clear(); self.purpose = "import"
        if not hasattr(self, "mgr_expanded"): self.mgr_expanded = set()
        self.mgr_tree = []; self.mgr_widgets = {}; self.mgr_busy = None
        nm = self.course_name or "SkoolCourse (khóa hiện tại)"
        self.head(f"Tải khóa: {nm}", "Mở chương ▸ · tải từng bài / cả chương / toàn bộ. Resume an toàn — Dừng bất cứ lúc nào.")
        bar = self.card()
        row = ctk.CTkFrame(bar, fg_color="transparent"); row.pack(fill="x", padx=14, pady=(14, 6))
        self.b_all = btn(row, "⬇  Tải toàn bộ", self.dl_all, kind="success", width=150)
        self.b_all.pack(side="left")
        btn(row, "■  Dừng", self.do_stop, kind="danger", width=100).pack(side="left", padx=8)
        self.opt_clean = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row, text="🔁 Thử lại đến khi đủ", variable=self.opt_clean,
                        font=(FT, 12), text_color=TEXT2, fg_color=ACCENT, hover_color=ACCENT_H,
                        border_color=BORDER).pack(side="left", padx=8)
        btn(row, "↻ Fail", self.retry_failed_only, kind="warn", width=80, height=32).pack(side="right", padx=4)
        btn(row, "📦 Pack", lambda: self.export_knowledge_pack(), kind="soft", width=80, height=32).pack(side="right", padx=4)
        btn(row, "🗑 Dọn dở", self.cleanup_partials, kind="secondary", width=96, height=32).pack(side="right", padx=4)
        self.mgr_status = ctk.CTkLabel(bar, text="⏳  Đang đọc danh sách chương…", font=(FT, 12),
                                       text_color=TEXT2, justify="left", wraplength=560)
        self.mgr_status.pack(anchor="w", padx=16, pady=(2, 12))
        self.mgr_fail_box = ctk.CTkFrame(self.content, fg_color="transparent")
        self.mgr_fail_box.pack(fill="x", pady=(0, 6))
        self.mgr_scroll = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=16,
                                       border_width=1, border_color=BORDER)
        self.mgr_scroll.pack(fill="x", pady=(2, 6))
        nav = ctk.CTkFrame(self.content, fg_color="transparent"); nav.pack(fill="x", pady=12)
        btn(nav, "←  Dashboard", self.show_dashboard, kind="ghost", width=120).pack(side="left")
        btn(nav, "Tạo phụ đề  →", self.show_transcribe, kind="accent", width=150).pack(side="right")
        self._mgr_scan_async()
        self._mgr_refresh_fails()

    def _mgr_scan_async(self):
        def cb(t):
            self.mgr_tree = [] if isinstance(t, Exception) else (t or [])
            self._mgr_render()
        def load():
            self._ensure_folders(self.course_name)   # tao folder chuong/bai truoc -> rel day du, on dinh
            return P.tree(self.course_root(self.course_name))
        self.run_async(load, cb)

    def _ensure_folders(self, course_name):
        """Tao cay folder chuong/bai cho khoa (idempotent) truoc khi liet ke, de duong dan bai (rel)
           luon day du & khop voi videos.py -> tai dung tu lan bam dau. Co lap config.C + chan print
           (pythonw khong co stdout)."""
        import io, sys as _sys
        import config as C2, folders
        with self._cfg_lock:
            saved = (C2.COURSE, C2.ROOT, C2.DUMP_ROOT)
            out = (_sys.stdout, _sys.stderr)
            try:
                if course_name:
                    C2.set_course(course_name)
                else:
                    C2.COURSE = None; C2.ROOT = C2.BASE / "SkoolCourse"; C2.DUMP_ROOT = C2.ROOT
                    C2.ROOT.mkdir(parents=True, exist_ok=True)
                _sys.stdout = _sys.stderr = io.StringIO()
                folders.run()
            except Exception:
                pass
            finally:
                _sys.stdout, _sys.stderr = out
                C2.COURSE, C2.ROOT, C2.DUMP_ROOT = saved

    def _mgr_render(self):
        if not (hasattr(self, "mgr_scroll") and self.mgr_scroll.winfo_exists()): return
        for w in self.mgr_scroll.winfo_children(): w.destroy()
        self.mgr_widgets = {}
        if not self.mgr_tree:
            ctk.CTkLabel(self.mgr_scroll, text="(Chưa có dữ liệu chương — dùng “Thêm khóa mới” hoặc “Kiểm tra cập nhật” để lấy danh sách trước.)",
                         font=(FT, 12), text_color=TEXT2, wraplength=520, justify="left").pack(anchor="w", padx=12, pady=12)
            self._mgr_update_status(); return
        for ch in self.mgr_tree:
            self._mgr_render_chapter(ch)
        self._mgr_update_status()

    def _mgr_render_chapter(self, ch):
        name = ch["name"]; exp = name in self.mgr_expanded
        crow = ctk.CTkFrame(self.mgr_scroll, fg_color=CARD2 if exp else "transparent", corner_radius=8); crow.pack(fill="x", padx=4, pady=(4, 1))
        btn(crow, ("▾" if exp else "▸"), (lambda n=name: self._mgr_toggle(n)), kind="ghost", width=26).pack(side="left", padx=(2, 0))
        full = ch["total"] and ch["done"] >= ch["total"]
        ic = ctk.CTkLabel(crow, text=("✓" if full else ("⏳" if ch["done"] else "•")), text_color=(SUCCESS if full else (WARNING if ch["done"] else TEXT2)), width=20, font=(FT, 14, "bold")); ic.pack(side="left")
        disp = name if len(name) <= 38 else name[:37] + "…"
        ctk.CTkLabel(crow, text=disp, font=(FT, 13, "bold"), text_color=TEXT, width=290, anchor="w").pack(side="left")
        cnt = ctk.CTkLabel(crow, text=f"{ch['done']}/{ch['total']}", font=("Consolas", 12), text_color=TEXT2, width=54, anchor="e"); cnt.pack(side="left", padx=4)
        btn(crow, "⬇ Chương", (lambda t=ch["title"], n=name: self.dl_chapter(t, n)), kind="secondary", width=92, height=30).pack(side="right", padx=4, pady=3)
        self.mgr_widgets[("chap", name)] = {"ic": ic, "cnt": cnt}
        if exp:
            for L in ch["lessons"]:
                self._mgr_render_lesson(L)
            if not ch["lessons"]:
                ctk.CTkLabel(self.mgr_scroll, text="    (chương trống)", font=(FT, 11), text_color=TEXT2).pack(anchor="w", padx=40)

    def _mgr_render_lesson(self, L):
        lrow = ctk.CTkFrame(self.mgr_scroll, fg_color="transparent"); lrow.pack(fill="x", padx=(38, 4), pady=0)
        ic = ctk.CTkLabel(lrow, text=("✓" if L["done"] else "•"), text_color=(SUCCESS if L["done"] else TEXT2), width=18, font=(FT, 13)); ic.pack(side="left")
        t = L["title"] or "(bài)"; t = t if len(t) <= 42 else t[:41] + "…"
        ctk.CTkLabel(lrow, text=t, font=(FT, 12), text_color=TEXT, width=300, anchor="w").pack(side="left")
        host = (L["host"] or "").replace("www.", "")[:16]
        ctk.CTkLabel(lrow, text=host, font=("Consolas", 10), text_color=TEXT2, width=120, anchor="w").pack(side="left")
        btn(lrow, "⬇", (lambda r=L["rel"], tt=(L["title"] or "bài"): self.dl_lesson(r, tt)), kind="ghost", width=32, height=26).pack(side="right", padx=4)
        self.mgr_widgets[("lesson", L["rel"])] = {"ic": ic}

    def _mgr_toggle(self, name):
        self.mgr_expanded.discard(name) if name in self.mgr_expanded else self.mgr_expanded.add(name)
        self._mgr_render()

    def _course_args(self):
        return (["--course", self.course_name] if self.course_name else [])

    def dl_all(self):
        if self.proc: messagebox.showinfo("Đang bận", "Đang tải — bấm Dừng trước đã."); return
        args = self._course_args()
        if getattr(self, "opt_clean", None) and self.opt_clean.get(): args.append("--until-clean")
        self.mgr_busy = "toàn bộ khóa"; self._mgr_busy_status()
        self.start([PY, "main.py"] + args, "TẢI TOÀN BỘ", on_done=self._mgr_after_dl)

    def dl_chapter(self, title, name):
        if self.proc: messagebox.showinfo("Đang bận", "Đang tải — bấm Dừng trước đã."); return
        args = self._course_args() + ["--only", "videos", "--chapter", title]
        if getattr(self, "opt_clean", None) and self.opt_clean.get(): args.append("--until-clean")
        self.mgr_busy = f"chương “{name}”"; self._mgr_busy_status()
        self.start([PY, "main.py"] + args, f"TẢI CHƯƠNG: {name}", on_done=self._mgr_after_dl)

    def dl_lesson(self, rel, title):
        if self.proc: messagebox.showinfo("Đang bận", "Đang tải — bấm Dừng trước đã."); return
        args = self._course_args() + ["--only", "videos", "--lesson", rel]
        self.mgr_busy = f"bài “{title}”"; self._mgr_busy_status()
        self.start([PY, "main.py"] + args, f"TẢI BÀI: {title}", on_done=self._mgr_after_dl)

    def _mgr_busy_status(self):
        if hasattr(self, "mgr_status") and self.mgr_status.winfo_exists():
            self.mgr_status.configure(text=f"⏳  Đang tải {self.mgr_busy}…  (bấm Dừng để ngừng — bài đã tải vẫn giữ)", text_color=WARNING)

    def _mgr_after_dl(self):
        self.mgr_busy = None; self._mgr_scan_async()
        self._mgr_refresh_fails()
        self._maybe_cloud_after(self.course_name)
        self._maybe_auto_index()

    def _mgr_refresh_fails(self):
        if not (hasattr(self, "mgr_fail_box") and self.mgr_fail_box.winfo_exists()):
            return
        for w in self.mgr_fail_box.winfo_children():
            w.destroy()
        fails = self._load_fails()
        if not fails:
            return
        try:
            import cleanup as CL
            groups = CL.summarize_fails(fails)
            parts = [f"{g['code']}×{g['count']}" for g in groups[:4]]
            summary = ", ".join(parts)
        except Exception:
            summary = f"{len(fails)} lỗi"
        ban = ctk.CTkFrame(self.mgr_fail_box, fg_color="#FFF7ED", corner_radius=10, border_width=1, border_color="#FDBA74")
        ban.pack(fill="x")
        ctk.CTkLabel(ban, text=f"⚠ {len(fails)} bài fail ({summary})", font=(FT, 12, "bold"),
                     text_color="#9A3412").pack(side="left", padx=12, pady=8)
        btn(ban, "Chi tiết", lambda: self._show_fails_dialog(fails), kind="warn", width=90, height=28).pack(side="right", padx=8, pady=6)
        btn(ban, "↻ Chỉ tải fail", self.retry_failed_only, kind="accent", width=120, height=28).pack(side="right", padx=4, pady=6)

    def _show_fails_dialog(self, fails=None):
        fails = fails if fails is not None else self._load_fails()
        if not fails:
            messagebox.showinfo("Fails", "Không có video_fails.json."); return
        try:
            import cleanup as CL
            groups = CL.summarize_fails(fails)
            lines = [f"{len(fails)} bài thất bại:\n"]
            for g in groups:
                lines.append(f"[{g['code']}] ×{g['count']} — {g['message']}\n→ {g['fix']}\n")
            messagebox.showwarning("Bài tải thất bại", "\n".join(lines)[:1500])
        except Exception as e:
            messagebox.showerror("Fails", str(e))

    def _mgr_update_status(self):
        if not (hasattr(self, "mgr_status") and self.mgr_status.winfo_exists()): return
        if self.mgr_busy: self._mgr_busy_status(); return
        if not self.mgr_tree:
            self.mgr_status.configure(text="Chưa có dữ liệu chương.", text_color=TEXT2); return
        done = sum(c["done"] for c in self.mgr_tree); tot = sum(c["total"] for c in self.mgr_tree)
        size = sum(L["size"] for c in self.mgr_tree for L in c["lessons"])
        msg = f"Đã tải {done}/{tot} bài  ·  {fmt_size(size)}." + (" ✓ Đủ." if (tot and done >= tot) else f"  Còn {tot - done} bài.")
        fails = self._load_fails()
        if fails:
            msg += f"  ·  ⚠ {len(fails)} fail"
        self.mgr_status.configure(text=msg, text_color=TEXT2 if not fails else WARNING)

    def refresh_manager(self):
        if getattr(self, "_mgr_refreshing", False): return
        self._mgr_refreshing = True
        def work():
            try: t = P.tree(self.course_root(self.course_name))
            except Exception: t = None
            self.ui_q.put(lambda: self._apply_mgr(t))
        threading.Thread(target=work, daemon=True).start()

    def _apply_mgr(self, t):
        self._mgr_refreshing = False
        if t is None or not (hasattr(self, "mgr_scroll") and self.mgr_scroll.winfo_exists()): return
        if len(t) != len(self.mgr_tree):   # cấu trúc đổi -> dựng lại
            self.mgr_tree = t; self._mgr_render(); return
        self.mgr_tree = t
        for ch in t:
            w = self.mgr_widgets.get(("chap", ch["name"]))
            if w and w["cnt"].winfo_exists():
                full = ch["total"] and ch["done"] >= ch["total"]
                w["cnt"].configure(text=f"{ch['done']}/{ch['total']}")
                w["ic"].configure(text=("✓" if full else ("⏳" if ch["done"] else "•")), text_color=(SUCCESS if full else (WARNING if ch["done"] else TEXT2)))
            for L in ch["lessons"]:
                lw = self.mgr_widgets.get(("lesson", L["rel"]))
                if lw and lw["ic"].winfo_exists():
                    lw["ic"].configure(text=("✓" if L["done"] else "•"), text_color=(SUCCESS if L["done"] else TEXT2))
        self._mgr_update_status()

    # ====================== TẠO PHỤ ĐỀ (transcript) ======================
    def _transcript_stats(self, root):
        root = Path(root); vids = txt = 0
        if not root.exists(): return (0, 0)
        for ext in C.VIDEXT:
            for p in root.rglob("video" + ext):
                if p.stem != "video" or any(x.lower() == "resources" for x in p.parts): continue
                vids += 1
                if (p.parent / "video.txt").exists(): txt += 1
        return (txt, vids)

    def show_transcribe(self):
        self.clear(); self.purpose = "import"
        nm = self.course_name or "SkoolCourse"
        self.head(f"Tạo phụ đề: {nm}", "Bóc lời giảng → .txt/.srt. Windows Task chạy ngầm (sống qua reboot); bài đã có phụ đề được bỏ qua.")
        card = self.card()
        self.trans_lbl = ctk.CTkLabel(card, text="⏳  Đang kiểm tra…", font=(FT, 13), text_color=TEXT2)
        self.trans_lbl.pack(anchor="w", padx=16, pady=(14, 6))
        self.trans_pb = ctk.CTkProgressBar(card, height=12, corner_radius=6,
                                           progress_color=ACCENT, fg_color=CARD2)
        self.trans_pb.set(0)
        self.trans_pb.pack(fill="x", padx=16, pady=(0, 14))
        act = self.card()
        r = ctk.CTkFrame(act, fg_color="transparent"); r.pack(fill="x", padx=14, pady=14)
        btn(r, "▶  Bắt đầu tạo phụ đề (ngầm)", self.start_transcribe, kind="accent", width=260).pack(side="left")
        ctk.CTkLabel(r, text="Độc lập — có thể đóng app.", font=(FT, 11), text_color=TEXT2).pack(side="left", padx=10)
        nav = ctk.CTkFrame(self.content, fg_color="transparent"); nav.pack(fill="x", pady=12)
        btn(nav, "←  Về trình tải", self.show_manager, kind="ghost", width=140).pack(side="left")
        btn(nav, "Dịch tiếng Việt  →", self.show_translate, kind="secondary", width=170).pack(side="right")
        self._trans_scan_async()

    def _trans_scan_async(self):
        def cb(rr):
            txt, vids = (0, 0) if isinstance(rr, Exception) else rr
            if hasattr(self, "trans_lbl") and self.trans_lbl.winfo_exists():
                pct = round(txt * 100 / vids) if vids else 0
                self.trans_lbl.configure(text=f"Đã có phụ đề: {txt}/{vids} video ({pct}%)" + (" — ✓ xong" if (vids and txt >= vids) else ""))
                if self.trans_pb.winfo_exists(): self.trans_pb.set((txt / vids) if vids else 0)
        self.run_async(lambda: self._transcript_stats(self.course_root(self.course_name)), cb)

    def start_transcribe(self):
        self.run_sub_on()
        self.write("Đã bật tạo phụ đề chạy ngầm (Windows Task) cho khóa.")
        if hasattr(self, "trans_lbl") and self.trans_lbl.winfo_exists():
            self.trans_lbl.configure(text="▶  Đã bật chạy ngầm — phụ đề sẽ xuất hiện dần. Quay lại trang này để xem tiến độ.")

    # ====================== DỊCH TIẾNG VIỆT ======================
    def show_translate(self):
        self.clear(); self.purpose = "import"
        nm = self.course_name or "SkoolCourse"
        self.head(f"Dịch sang tiếng Việt: {nm}", "Sau phụ đề: tạo Transcript_VI.md + phụ đề song ngữ Anh–Việt.")
        try:
            import ai_tools
            google = ai_tools.have_google()
        except Exception:
            google = False
        card = self.card()
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        self.pill(row, "Google ✓" if google else "Thiếu deep-translator",
                  "ok" if google else "danger").pack(side="left")
        ctk.CTkLabel(row, text=("Dịch miễn phí qua Google" if google else "pip install deep-translator"),
                     font=(FT, 12), text_color=TEXT2).pack(side="left", padx=10)
        self.tl_lbl = ctk.CTkLabel(card, text="", font=(FT, 12), text_color=TEXT2,
                                   justify="left", wraplength=560)
        self.tl_lbl.pack(anchor="w", padx=16, pady=(0, 12))
        act = self.card()
        r = ctk.CTkFrame(act, fg_color="transparent"); r.pack(fill="x", padx=14, pady=14)
        btn(r, "▶  Dịch sang tiếng Việt", self.start_translate, kind="accent", width=220).pack(side="left")
        ctk.CTkLabel(r, text="Transcript_VI.md + PhuDe_SongNgu.srt", font=(FT, 11),
                     text_color=TEXT2).pack(side="left", padx=10)
        nav = ctk.CTkFrame(self.content, fg_color="transparent"); nav.pack(fill="x", pady=12)
        btn(nav, "←  Về Phụ đề", self.show_transcribe, kind="ghost", width=130).pack(side="left")
        btn(nav, "📁  Mở thư mục", self.open_folder, kind="secondary", width=140).pack(side="right")

    def start_translate(self):
        if self.proc: messagebox.showinfo("Đang bận", "Một tác vụ đang chạy."); return
        try:
            import ai_tools
            if not ai_tools.have_google():
                messagebox.showinfo("Thiếu công cụ dịch", "Cần deep-translator để dịch.\nChạy: pip install deep-translator"); return
        except Exception: pass
        root = self.course_root(self.course_name)
        if hasattr(self, "tl_lbl"): self.tl_lbl.configure(text="⏳  Đang dịch… (theo dõi ở Nhật ký bên dưới)")
        self.start([PY, "report_bundle.py", "--root", str(root), "--out", str(root)], "DỊCH TIẾNG VIỆT", on_done=self._after_translate)

    def _after_translate(self):
        if hasattr(self, "tl_lbl") and self.tl_lbl.winfo_exists():
            self.tl_lbl.configure(text="✓  Xong — xem Transcript_VI.md + PhuDe_SongNgu.srt trong thư mục khóa.")

    # ---------- tien trinh ----------
    def start_download(self):
        args = ([] if not self.course_name else ["--course", self.course_name])
        test = bool(getattr(self, "opt_test", None) and self.opt_test.get())
        if test: args.append("--dry-run")
        if not test and getattr(self, "opt_clean", None) and self.opt_clean.get(): args.append("--until-clean")
        self.show_step4()
        if test and hasattr(self, "run_lbl"): self.run_lbl.configure(text="🔧  CHẾ ĐỘ TEST — chỉ kiểm tra, không tải thật", text_color="#9A6700")
        self.start([PY, "main.py"] + args, "TẢI KHÓA" + (" (TEST)" if test else ""), on_done=self.show_done)

    # ---------- B4: cuu bai native het han token ----------
    def rescue_native(self):
        s = self.last_scan
        if not s or not s.get("native_expired"):
            messagebox.showinfo("Không cần", "Không có bài native nào hết hạn token."); return
        self.target_titles = set(P.expired_native_chapter_titles(s))
        self.purpose = "rescue"; self.show_step2()

    def _rescue_dump(self, group, chapters):
        sel = [c for c in chapters if K.san(c["title"]) in self.target_titles]
        if not sel:
            messagebox.showinfo("Không khớp", "Không tìm thấy chương cần cứu trên Skool (có thể đã đổi tên).")
            self.show_manager(); return
        self.chap_box.pack(fill="x", pady=8); self.dump_row.pack(fill="x", pady=4)
        for w in self.dump_row.winfo_children(): w.destroy()
        self.dump_status = ctk.CTkLabel(self.dump_row, text=f"Đang lấy lại token {len(sel)} chương…", font=(FT, 12, "bold"), text_color=PRIMARY); self.dump_status.pack(anchor="w")
        self.dump_pb = ctk.CTkProgressBar(self.dump_row, height=12, corner_radius=6, progress_color=PRIMARY); self.dump_pb.set(0); self.dump_pb.pack(fill="x", pady=(2, 6))
        out = self.course_root(self.course_name); self._dumping = True
        self.write(f"Cứu native: lấy lại token {len(sel)} chương → {out}")
        self.sb.dump([{"id": c["id"], "title": c["title"]} for c in sel], out, all_titles=self.live_titles or None)

    def start_native_download(self):
        self.purpose = "import"
        args = (["--course", self.course_name] if self.course_name else []) + ["--only", "videos", "--native-only"]
        self.show_step4()
        if hasattr(self, "run_lbl"): self.run_lbl.configure(text="🔑  Đang tải lại video native (token mới)…", text_color=WARNING)
        self.start([PY, "main.py"] + args, "CỨU NATIVE", on_done=self.show_done)

    def run_sub_on(self):
        c = self.course_name; ps = HERE / "install_transcribe_task.ps1"; extra = ["-Course", c] if c else ["-All"]
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)] + extra, creationflags=NO_WIN)

    def start(self, cmd, title, cwd=None, on_done=None):
        if self.proc: messagebox.showinfo("Đang bận", "Một tác vụ đang chạy."); return
        self._on_done = on_done; self.write(f"\n===== {title} =====")
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
            if hasattr(self, "run_lbl") and self.run_lbl.winfo_exists(): self.run_lbl.configure(text="■  Đã dừng", text_color=DANGER)
            if hasattr(self, "mgr_status") and self.mgr_status.winfo_exists():
                self.mgr_busy = None; self.mgr_status.configure(text="■  Đã dừng. Bài đã tải vẫn được giữ.", text_color=DANGER)

    def open_folder(self):
        self._open_path(self.course_root())

    def _log_course_fails(self, course_name=None):
        """Ghi tom tat video_fails sau job queue (khong mo UI panel)."""
        try:
            import cleanup as CL
            root = self.course_root(course_name)
            fails = CL.load_fails(root)
            if not fails:
                return
            groups = CL.summarize_fails(fails)
            parts = [f"{g['code']}×{g['count']}" for g in groups[:5]]
            label = course_name or "SkoolCourse"
            self.write(f"⚠ [{label}] {len(fails)} fail: {', '.join(parts)}")
        except Exception:
            pass

    def _maybe_cloud_after(self, course_name=None):
        """Neu cloud.after_download bat + da cau hinh R2 -> sync knowledge nen."""
        try:
            from cloud.sync import load_cloud_settings, sync_course
            cfg = load_cloud_settings() or {}
            if not cfg.get("after_download"):
                return
            r2 = cfg.get("r2") or {}
            if not (r2.get("bucket") and r2.get("access_key")):
                return
            root = self.course_root(course_name)
            name = course_name if course_name is not None else (self.course_name or "SkoolCourse")
            self.write(f"☁ Auto-sync cloud: {name}…")
            def work():
                try:
                    return sync_course(root, course_name=name or "SkoolCourse",
                                      log=lambda s: self.ui_q.put(lambda m=s: self.write(m)))
                except Exception as e:
                    return e
            def cb(r):
                if isinstance(r, Exception):
                    self.write(f"[cloud auto] {r}")
                else:
                    self.write(f"☁ Auto-sync xong: up={r.get('uploaded')} skip={r.get('skipped')} fail={r.get('failed')}")
            self.run_async(work, cb)
        except Exception as e:
            self.write(f"[cloud auto] {e}")

    def poll(self):
        # TU CHUA LANH: bao boc toan bo + reschedule trong finally -> 1 loi le KHONG bao gio dung vong lap.
        try:
            try:
                while True: self.ui_q.get_nowait()()
            except queue.Empty: pass
            if self.sb:
                try:
                    while True:
                        ev = self.sb.evt_q.get_nowait()
                        try: self.on_browser_event(ev)
                        except Exception as e: self.write(f"[lỗi sự kiện trình duyệt] {e}")
                except queue.Empty: pass
            lines = []; done_cb = None
            try:
                while True:
                    tag, s = self.q.get_nowait()
                    if s == SENTINEL:
                        rc = self.proc.returncode if self.proc else 0
                        lines.append(f"--- Kết thúc (mã {rc}) ---"); self.proc = None
                        if getattr(self, "_on_done", None): done_cb = self._on_done; self._on_done = None
                    else: lines.append(s.rstrip("\n"))
            except queue.Empty: pass
            if lines: self._flush_log(lines)      # ghi 1 lan/chu ky (gom dong) -> bot giat
            if done_cb:
                try: done_cb()
                except Exception as e: self.write(f"[lỗi sau khi xong tác vụ] {e}")
            if time.time() - self._lastref > 1.5:
                if hasattr(self, "chap_scroll") and self.chap_scroll.winfo_exists():
                    self._lastref = time.time(); self.refresh4()
                elif hasattr(self, "mgr_scroll") and self.mgr_scroll.winfo_exists():
                    self._lastref = time.time(); self.refresh_manager()
                elif self.proc and hasattr(self, "trans_lbl") and self.trans_lbl.winfo_exists():
                    self._lastref = time.time(); self._trans_scan_async()
        except Exception as e:
            try: self.write(f"[lỗi vòng lặp] {e}")
            except Exception: pass
        finally:
            try: self.root.after(200, self.poll)   # luon lap lai; bo qua neu app dang dong
            except Exception: pass

    def on_browser_event(self, e):
        t = e.get("type")
        if t == "ready": self.write("Trình duyệt sẵn sàng."); self.sb.open()
        elif t == "opened":
            self.write("Đã mở Skool. Đăng nhập & mở trang Classroom, rồi bấm nút 2.")
            if hasattr(self, "b_list") and self.b_list.winfo_exists(): self.b_list.configure(state="normal")
        elif t == "log": self.write(e["msg"])
        elif t == "need_classroom": messagebox.showinfo("Mở trang Classroom", e["msg"])
        elif t == "chapters":
            self.live_titles = [c["title"] for c in e["chapters"]]
            self.write(f"Tìm thấy {len(e['chapters'])} chương.")
            if self.purpose == "rescue": self._rescue_dump(e["group"], e["chapters"])
            else: self.render_chapters(e["group"], e["chapters"])
        elif t == "dump_progress":
            self.write(f"[{e['i']}/{e['n']}] {e['title']}")
            if (hasattr(self, "dump_status") and self.dump_status.winfo_exists()
                    and hasattr(self, "dump_pb") and self.dump_pb.winfo_exists()):
                pct = round(e["i"] * 100 / max(1, e["n"]))
                self.dump_status.configure(text=f"Đang lấy: {e['i']}/{e['n']} chương ({pct}%) — {e['title']}"); self.dump_pb.set(pct / 100)
        elif t == "dumped":
            self._dumping = False; self.write(f"Đã lấy xong {e['ok']}/{e['total']} chương → {e['out_dir']}")
            if hasattr(self, "dump_status") and self.dump_status.winfo_exists():
                self.dump_status.configure(text=f"✓ Đã lấy {e['ok']}/{e['total']} chương")
            if hasattr(self, "dump_pb") and self.dump_pb.winfo_exists(): self.dump_pb.set(1)
            if self.purpose == "rescue":
                self.write("Token mới đã sẵn sàng — bắt đầu tải lại native…"); self.start_native_download(); return
            if self.purpose == "update":
                messagebox.showinfo("Xong", f"Đã cập nhật {e['ok']}/{e['total']} chương.\nChọn chương/bài để tải phần mới."); self.show_manager(); return
            messagebox.showinfo("Xong", f"Đã lấy dữ liệu khóa ({e['ok']}/{e['total']} chương).\nChọn chương/bài để tải."); self.show_manager()
        elif t == "error":
            self._dumping = False     # gỡ kẹt: nếu đang dump mà lỗi, mở lại nút
            if hasattr(self, "b_dump") and self.b_dump.winfo_exists():
                self.b_dump.configure(state="normal", text="3.   Tải dữ liệu các chương đã chọn  →")
            self.write(f"[LỖI trình duyệt] {e.get('msg', '')}"); messagebox.showerror("Lỗi", e.get("msg", "Lỗi trình duyệt"))

    # ====================== HÀNG ĐỢI (S2) ======================
    def show_queue(self):
        self.set_nav("queue")
        self.clear()
        self.head("Hàng đợi multi-course", "Xếp nhiều khóa — chạy song song (workers). Mỗi job = 1 subprocess main.py · queue_state.json.")
        import queue_engine as QE
        counts = QE.summary()
        qs = QE.load_queue_settings()
        # KPI row
        krow = ctk.CTkFrame(self.content, fg_color="transparent")
        krow.pack(fill="x", pady=(0, 10))
        for title, key, level in (
            ("Queued", "queued", "info"),
            ("Running", "running", "warn"),
            ("Done", "done", "ok"),
            ("Failed", "failed", "danger"),
        ):
            self.stat_card(krow, title, str(counts.get(key, 0)), f"workers={qs.get('max_workers',1)}" if key == "queued" else "", level)
        self.q_status = ctk.CTkLabel(self.content, text="", font=(FT, 1), text_color=BG)
        # controls card
        ctrl = self.card()
        wrow = ctk.CTkFrame(ctrl, fg_color="transparent"); wrow.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(wrow, text="Workers song song", font=(FT, 12, "bold"), text_color=TEXT).pack(side="left")
        self.q_workers = ctk.StringVar(value=str(qs.get("max_workers") or 1))
        ctk.CTkOptionMenu(wrow, variable=self.q_workers, values=["1", "2", "3", "4"], width=72,
                          fg_color=CARD2, button_color=ACCENT, button_hover_color=ACCENT_H,
                          text_color=TEXT, command=lambda _=None: self._queue_save_workers()).pack(side="left", padx=10)
        ctk.CTkLabel(wrow, text="transcribe vẫn serial", font=(FT, 11), text_color=TEXT2).pack(side="left")

        bar = ctk.CTkFrame(ctrl, fg_color="transparent"); bar.pack(fill="x", padx=14, pady=(4, 12))
        btn(bar, "▶  Chạy hàng đợi", self.queue_run, kind="success", width=150).pack(side="left")
        btn(bar, "■  Dừng", self.queue_stop, kind="danger", width=90).pack(side="left", padx=6)
        btn(bar, "Xóa đã xong", self.queue_clear_done, kind="secondary", width=120).pack(side="left", padx=4)
        btn(bar, "↺ Thử lại failed", self.queue_requeue_failed, kind="secondary", width=130).pack(side="left", padx=4)
        btn(bar, "↻", self.show_queue, kind="ghost", width=44).pack(side="right")

        add_card = self.card()
        ctk.CTkLabel(add_card, text="Thêm khóa vào hàng đợi", font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=14, pady=(12, 4))
        items = self.existing_courses()
        self.q_add_var = ctk.StringVar(value=items[0] if items else "")
        if items:
            ctk.CTkOptionMenu(add_card, variable=self.q_add_var, values=items, width=340,
                              fg_color=CARD2, button_color=ACCENT, button_hover_color=ACCENT_H,
                              text_color=TEXT).pack(anchor="w", padx=14, pady=4)
            row = ctk.CTkFrame(add_card, fg_color="transparent"); row.pack(fill="x", padx=14, pady=(6, 12))
            btn(row, "＋ Thêm", self.queue_add_current, kind="accent", width=100).pack(side="left")
            btn(row, "＋ Thêm tất cả", self.queue_add_all, kind="secondary", width=130).pack(side="left", padx=8)
        else:
            ctk.CTkLabel(add_card, text="(Chưa có khóa)", font=(FT, 12), text_color=TEXT2).pack(padx=14, pady=12)

        ctk.CTkLabel(self.content, text="JOBS", font=(FT, 11, "bold"), text_color=TEXT2).pack(anchor="w", pady=(4, 4))
        self.q_list = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=16, border_width=1, border_color=BORDER)
        self.q_list.pack(fill="x", pady=4)
        self._queue_render_jobs()

        btn(self.content, "←  Dashboard", self.show_dashboard, kind="ghost", width=120).pack(anchor="w", pady=12)

    def _queue_render_jobs(self):
        if not (hasattr(self, "q_list") and self.q_list.winfo_exists()): return
        for w in self.q_list.winfo_children(): w.destroy()
        import queue_engine as QE
        state = QE.load_state()
        jobs = state.get("jobs") or []
        if not jobs:
            ctk.CTkLabel(self.q_list, text="Hàng đợi trống — thêm khóa từ Dashboard hoặc form phía trên.",
                         font=(FT, 12), text_color=TEXT2).pack(padx=16, pady=20)
            return
        for j in jobs:
            row = ctk.CTkFrame(self.q_list, fg_color=CARD2, corner_radius=10)
            row.pack(fill="x", padx=10, pady=4)
            st = j.get("status") or "?"
            level = "ok" if st == "done" else ("danger" if st in ("failed", "stopped") else ("warn" if st == "running" else "muted"))
            pill = self.pill(row, st, level)
            pill.pack(side="left", padx=(10, 8), pady=8)
            ctk.CTkLabel(row, text=j.get("label") or j.get("course") or "SkoolCourse",
                         font=(FT, 12, "bold"), text_color=TEXT, anchor="w").pack(side="left", fill="x", expand=True, pady=8)
            jid = j.get("id")
            btn(row, "↓", lambda i=jid: self._queue_move(i, +1), kind="ghost", width=28, height=28).pack(side="right", padx=1, pady=6)
            btn(row, "↑", lambda i=jid: self._queue_move(i, -1), kind="ghost", width=28, height=28).pack(side="right", padx=1, pady=6)
            if st in ("failed", "stopped", "cancelled"):
                btn(row, "↺", lambda i=jid: self._queue_requeue_one(i), kind="soft", width=32, height=28).pack(side="right", padx=2, pady=6)
            if st == "queued":
                btn(row, "Hủy", lambda i=jid: self._queue_cancel(i), kind="ghost", width=50, height=28).pack(side="right", pady=6)
            btn(row, "✕", lambda i=jid: self._queue_remove(i), kind="ghost", width=32, height=28).pack(side="right", padx=(2, 8), pady=6)

    def queue_add_current(self):
        import queue_engine as QE
        v = self.q_add_var.get().strip() if hasattr(self, "q_add_var") else ""
        if not v: return
        QE.add_jobs([self.item_course(v)], kind="full", until_clean=True)
        self.write(f"Queue + {v}"); self.show_queue()

    def queue_add_all(self):
        import queue_engine as QE
        items = self.existing_courses()
        if not items: return
        QE.add_jobs([self.item_course(it) for it in items], kind="full", until_clean=True)
        self.write(f"Queue + {len(items)} khóa"); self.show_queue()

    def _queue_cancel(self, jid):
        import queue_engine as QE
        QE.cancel_job(jid); self.show_queue()

    def _queue_remove(self, jid):
        import queue_engine as QE
        QE.remove_job(jid); self.show_queue()

    def _queue_move(self, jid, delta):
        import queue_engine as QE
        QE.move_job(jid, delta)
        self._queue_render_jobs()

    def queue_clear_done(self):
        import queue_engine as QE
        QE.clear_done(); self.show_queue()

    def queue_requeue_failed(self):
        import queue_engine as QE
        n = QE.requeue_failed()
        self.write(f"↺ Requeue {n} job failed/stopped")
        self.show_queue()

    def _queue_requeue_one(self, jid):
        import queue_engine as QE
        if QE.requeue_job(jid):
            self.write(f"↺ Requeue {jid}")
        self._queue_render_jobs()

    def _queue_save_workers(self):
        try:
            import queue_engine as QE
            w = int(self.q_workers.get()) if hasattr(self, "q_workers") else 1
            QE.save_queue_settings(w)
            self.write(f"Queue workers = {w}")
        except Exception as e:
            self.write(f"[queue workers] {e}")

    def queue_run(self):
        import queue_engine as QE
        if self.proc:
            messagebox.showinfo("Đang bận", "Một tác vụ pipeline đang chạy. Dừng trước hoặc đợi xong."); return
        if self.queue_runner and self.queue_runner.is_running():
            messagebox.showinfo("Đang chạy", "Hàng đợi đang chạy."); return
        self._queue_save_workers()
        try:
            workers = int(self.q_workers.get()) if hasattr(self, "q_workers") else QE.load_queue_settings().get("max_workers", 1)
        except Exception:
            workers = 1
        def on_ev(ev):
            t = ev.get("type")
            if t == "start":
                self.ui_q.put(lambda: self.write(f"\n===== QUEUE: {ev['job'].get('label')} ====="))
            elif t == "log":
                line = ev.get("line") or ""
                jid = (ev.get("job_id") or "")[:6]
                prefix = f"[{jid}] " if jid and jid != "?" else ""
                self.ui_q.put(lambda s=prefix + line: self.write(s))
            elif t == "end":
                j = ev["job"]
                self.ui_q.put(lambda: self.write(f"--- job {j.get('status')} (rc={j.get('returncode')}) ---"))
                self.ui_q.put(self._queue_soft_refresh)
                if j.get("status") == "done":
                    self.ui_q.put(lambda c=j.get("course"): self._maybe_cloud_after(c))
                    self.ui_q.put(lambda c=j.get("course"): self._log_course_fails(c))
                elif j.get("status") == "failed":
                    self.ui_q.put(lambda c=j.get("course"): self._log_course_fails(c))
            elif t == "finished":
                self.ui_q.put(lambda: self.write(f"✓ Hàng đợi xong ({ev.get('ran')} job)"))
                self.ui_q.put(self._queue_soft_refresh)
            elif t == "config":
                self.ui_q.put(lambda: self.write(f"Queue workers={ev.get('max_workers')}"))
        self.queue_runner = QE.QueueRunner(on_event=on_ev, max_workers=workers)
        if self.queue_runner.start_async():
            self.write(f"▶ Bắt đầu hàng đợi (workers={workers})…")
            if hasattr(self, "q_status") and self.q_status.winfo_exists():
                self.q_status.configure(text=f"⏳ Đang chạy… workers={workers}")
        else:
            messagebox.showinfo("Đang chạy", "Runner đã bận.")

    def _queue_soft_refresh(self):
        """Cap nhat list job neu van o man queue."""
        if hasattr(self, "q_list") and self.q_list.winfo_exists():
            try:
                import queue_engine as QE
                counts = QE.summary()
                if hasattr(self, "q_status") and self.q_status.winfo_exists():
                    self.q_status.configure(
                        text=f"queued={counts.get('queued',0)}  running={counts.get('running',0)}  "
                             f"done={counts.get('done',0)}  failed={counts.get('failed',0)}")
                self._queue_render_jobs()
            except Exception:
                pass

    def queue_stop(self):
        if self.queue_runner:
            self.queue_runner.stop()
            self.write("[Queue] Đã gửi lệnh dừng")
        else:
            messagebox.showinfo("Không chạy", "Không có hàng đợi nào đang chạy.")

    # ====================== CLOUD R2 + GDrive (Phase 2) ======================
    def show_cloud(self):
        self.set_nav("cloud")
        self.clear()
        self.head("Cloud upload", "Đồng bộ knowledge (md/txt/srt/resources) — R2 · Drive · OneDrive. Mặc định không upload video.")
        # provider tips
        tip = ctk.CTkFrame(self.content, fg_color=ACCENT_SOFT, corner_radius=12)
        tip.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(tip, text="💡  Knowledge mode = text + resources. Full mode mới đẩy video (nặng).",
                     font=(FT, 12), text_color=ACCENT).pack(anchor="w", padx=14, pady=10)
        try:
            from cloud.sync import load_cloud_settings
            cfg = load_cloud_settings() or {}
        except Exception:
            cfg = {}
        r2 = cfg.get("r2") or {}
        gd = cfg.get("gdrive") or {}
        od = cfg.get("onedrive") or {}

        card = self.card()
        prow = ctk.CTkFrame(card, fg_color="transparent"); prow.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(prow, text="Provider", font=(FT, 12, "bold"), text_color=TEXT2, width=180, anchor="w").pack(side="left")
        self.cloud_provider = ctk.StringVar(value=cfg.get("provider") or "r2")
        ctk.CTkOptionMenu(prow, variable=self.cloud_provider, values=["r2", "gdrive", "onedrive"], width=160,
                          fg_color=CARD2, button_color=PRIMARY, button_hover_color=PRIMARY_H,
                          text_color=TEXT).pack(side="left")

        ctk.CTkLabel(card, text="Cloudflare R2", font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=14, pady=(8, 4))
        fields = [
            ("Account ID", "account_id", r2.get("account_id") or ""),
            ("Bucket", "bucket", r2.get("bucket") or ""),
            ("Access Key", "access_key", r2.get("access_key") or ""),
            ("Secret Key", "secret_key", r2.get("secret_key") or ""),
            ("Endpoint (để trống = auto)", "endpoint", r2.get("endpoint") or ""),
            ("Prefix (tuỳ chọn)", "prefix", cfg.get("prefix") or ""),
        ]
        self.cloud_vars = {}
        for label, key, val in fields:
            row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(row, text=label, font=(FT, 12), text_color=TEXT, width=180, anchor="w").pack(side="left")
            var = ctk.StringVar(value=val)
            show = "•" if "secret" in key or "access" in key else None
            ent = ctk.CTkEntry(row, textvariable=var, font=("Consolas", 11), show=show)
            ent.pack(side="left", fill="x", expand=True)
            self.cloud_vars[key] = var

        ctk.CTkLabel(card, text="Google Drive", font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(card, text="Service Account: share folder cho email SA. OAuth: client_secrets Desktop + lần đầu mở browser.",
                     font=(FT, 11), text_color=TEXT2, wraplength=520, justify="left").pack(anchor="w", padx=14, pady=(0, 4))
        gd_fields = [
            ("Auth (service_account|oauth)", "gd_auth", gd.get("auth") or "service_account"),
            ("Service account JSON path", "gd_sa", gd.get("service_account_json") or ""),
            ("Client secrets JSON path", "gd_secrets", gd.get("client_secrets_json") or ""),
            ("Folder ID (Drive)", "gd_folder", gd.get("folder_id") or ""),
        ]
        for label, key, val in gd_fields:
            row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(row, text=label, font=(FT, 12), text_color=TEXT, width=180, anchor="w").pack(side="left")
            var = ctk.StringVar(value=val)
            ctk.CTkEntry(row, textvariable=var, font=("Consolas", 11)).pack(side="left", fill="x", expand=True)
            self.cloud_vars[key] = var

        ctk.CTkLabel(card, text="OneDrive (Microsoft Graph)", font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(card, text="Azure App (public client) + device code lần đầu. pip install msal",
                     font=(FT, 11), text_color=TEXT2, wraplength=520, justify="left").pack(anchor="w", padx=14, pady=(0, 4))
        od_fields = [
            ("Client ID", "od_client", od.get("client_id") or ""),
            ("Tenant (consumers/common)", "od_tenant", od.get("tenant") or "consumers"),
            ("Folder name", "od_folder", od.get("folder") or "SkoolArchiver"),
        ]
        for label, key, val in od_fields:
            row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(row, text=label, font=(FT, 12), text_color=TEXT, width=180, anchor="w").pack(side="left")
            var = ctk.StringVar(value=val)
            ctk.CTkEntry(row, textvariable=var, font=("Consolas", 11)).pack(side="left", fill="x", expand=True)
            self.cloud_vars[key] = var

        mode_row = ctk.CTkFrame(card, fg_color="transparent"); mode_row.pack(fill="x", padx=14, pady=(8, 4))
        ctk.CTkLabel(mode_row, text="Mode", font=(FT, 12), text_color=TEXT, width=180, anchor="w").pack(side="left")
        self.cloud_mode = ctk.StringVar(value=cfg.get("mode") or "knowledge")
        ctk.CTkOptionMenu(mode_row, variable=self.cloud_mode, values=["knowledge", "full"], width=160,
                          fg_color=CARD2, button_color=PRIMARY, button_hover_color=PRIMARY_H,
                          text_color=TEXT).pack(side="left")

        self.cloud_after = ctk.BooleanVar(value=bool(cfg.get("after_download")))
        ctk.CTkCheckBox(card, text="Tự đồng bộ knowledge sau khi tải xong (download / queue)",
                        variable=self.cloud_after, font=(FT, 12), text_color=TEXT,
                        fg_color=PRIMARY, hover_color=PRIMARY_H).pack(anchor="w", padx=14, pady=(6, 4))

        brow = ctk.CTkFrame(card, fg_color="transparent"); brow.pack(fill="x", padx=14, pady=(8, 12))
        btn(brow, "💾  Lưu cấu hình", self.cloud_save, width=140).pack(side="left")
        btn(brow, "🔌  Test kết nối", self.cloud_test, kind="secondary", width=130).pack(side="left", padx=8)

        self.cloud_status = ctk.CTkLabel(self.content, text="", font=(FT, 12), text_color=TEXT2, wraplength=540, justify="left")
        self.cloud_status.pack(anchor="w", pady=4)

        sync_card = self.card()
        ctk.CTkLabel(sync_card, text="Đồng bộ khóa", font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=14, pady=(12, 4))
        items = self.existing_courses()
        self.cloud_course = ctk.StringVar(value=items[0] if items else "")
        if items:
            ctk.CTkOptionMenu(sync_card, variable=self.cloud_course, values=items, width=320,
                              fg_color=CARD2, button_color=PRIMARY, button_hover_color=PRIMARY_H,
                              text_color=TEXT).pack(anchor="w", padx=14, pady=4)
            srow = ctk.CTkFrame(sync_card, fg_color="transparent"); srow.pack(fill="x", padx=14, pady=(6, 12))
            btn(srow, "☁  Sync khóa này", self.cloud_sync_selected, kind="success", width=160).pack(side="left")
            btn(srow, "☁ Sync tất cả", self.cloud_sync_all, kind="secondary", width=130).pack(side="left", padx=6)
            btn(srow, "Dry-run", self.cloud_dry_run, kind="secondary", width=100).pack(side="left", padx=8)
        else:
            ctk.CTkLabel(sync_card, text="(Chưa có khóa)", font=(FT, 12), text_color=TEXT2).pack(padx=14, pady=12)

        btn(self.content, "←  Dashboard", self.show_dashboard, kind="ghost", width=120).pack(anchor="w", pady=10)

    def cloud_save(self):
        try:
            from cloud.sync import load_cloud_settings, save_cloud_settings
            cfg = load_cloud_settings() or {}
            r2 = dict(cfg.get("r2") or {})
            for k in ("account_id", "bucket", "access_key", "secret_key", "endpoint"):
                if k in self.cloud_vars:
                    r2[k] = self.cloud_vars[k].get().strip()
            gd = dict(cfg.get("gdrive") or {})
            if "gd_auth" in self.cloud_vars:
                gd["auth"] = self.cloud_vars["gd_auth"].get().strip() or "service_account"
            if "gd_sa" in self.cloud_vars:
                gd["service_account_json"] = self.cloud_vars["gd_sa"].get().strip()
            if "gd_secrets" in self.cloud_vars:
                gd["client_secrets_json"] = self.cloud_vars["gd_secrets"].get().strip()
            if "gd_folder" in self.cloud_vars:
                gd["folder_id"] = self.cloud_vars["gd_folder"].get().strip()
            od = dict(cfg.get("onedrive") or {})
            if "od_client" in self.cloud_vars:
                od["client_id"] = self.cloud_vars["od_client"].get().strip()
            if "od_tenant" in self.cloud_vars:
                od["tenant"] = self.cloud_vars["od_tenant"].get().strip() or "consumers"
            if "od_folder" in self.cloud_vars:
                od["folder"] = self.cloud_vars["od_folder"].get().strip() or "SkoolArchiver"
            cfg["provider"] = (self.cloud_provider.get() if hasattr(self, "cloud_provider") else "r2") or "r2"
            cfg["r2"] = r2
            cfg["gdrive"] = gd
            cfg["onedrive"] = od
            cfg["mode"] = self.cloud_mode.get() if hasattr(self, "cloud_mode") else "knowledge"
            cfg["after_download"] = bool(self.cloud_after.get()) if hasattr(self, "cloud_after") else False
            if "prefix" in self.cloud_vars:
                cfg["prefix"] = self.cloud_vars["prefix"].get().strip()
            save_cloud_settings(cfg)
            self.write(f"✓ Đã lưu cloud provider={cfg['provider']}")
            if hasattr(self, "cloud_status") and self.cloud_status.winfo_exists():
                self.cloud_status.configure(text=f"✓ Đã lưu (provider={cfg['provider']}).")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def cloud_test(self):
        self.cloud_save()
        def work():
            try:
                from cloud.sync import test_connection
                return test_connection(log=lambda s: self.ui_q.put(lambda m=s: self.write(m)))
            except Exception as e:
                return False, str(e)
        def cb(r):
            ok, msg = r if isinstance(r, tuple) else (False, str(r))
            self.write(("✓ " if ok else "✗ ") + msg)
            if hasattr(self, "cloud_status") and self.cloud_status.winfo_exists():
                self.cloud_status.configure(text=msg)
            if not ok:
                messagebox.showerror("Kết nối thất bại", msg)
            else:
                messagebox.showinfo("Kết nối OK", msg)
        self.run_async(work, cb)

    def cloud_sync_all(self):
        self.cloud_save()
        if not messagebox.askyesno("Sync tất cả", "Đồng bộ knowledge mọi khóa lên cloud?\n(Có thể lâu nếu nhiều file)"):
            return
        self.write("☁ Sync tất cả khóa…")
        def work():
            try:
                from cloud.sync import sync_all_courses
                return sync_all_courses(log=lambda s: self.ui_q.put(lambda m=s: self.write(m)))
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                messagebox.showerror("Cloud", str(r)); return
            ok = sum(1 for x in r if x.get("ok"))
            messagebox.showinfo("Cloud", f"Xong: {ok}/{len(r)} khóa OK")
        self.run_async(work, cb)

    def _cloud_sync_course(self, item, dry_run=False):
        root = self.item_root(item)
        course = self.item_course(item)
        self.write(f"{'[dry-run] ' if dry_run else ''}☁ Sync {item}…")
        def work():
            try:
                from cloud.sync import sync_course
                return sync_course(root, course_name=course or "SkoolCourse",
                                  dry_run=dry_run, log=lambda s: self.ui_q.put(lambda m=s: self.write(m)))
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                messagebox.showerror("Cloud", str(r)); self.write(f"[cloud] {r}"); return
            messagebox.showinfo("Cloud", f"upload={r.get('uploaded')} skip={r.get('skipped')} fail={r.get('failed')}")
        self.run_async(work, cb)

    def cloud_sync_selected(self):
        v = self.cloud_course.get().strip() if hasattr(self, "cloud_course") else ""
        if not v:
            messagebox.showinfo("Chưa chọn", "Chọn một khóa."); return
        self.cloud_save()
        self._cloud_sync_course(v, dry_run=False)

    def cloud_dry_run(self):
        v = self.cloud_course.get().strip() if hasattr(self, "cloud_course") else ""
        if not v: return
        self.cloud_save()
        self._cloud_sync_course(v, dry_run=True)

    # ====================== DOCTOR + BASE (Phase 6) ======================
    def show_doctor(self):
        self.set_nav("doctor")
        self.clear()
        self.head("Doctor", "Chẩn đoán môi trường, BASE path và module. Sửa BASE nếu khóa không hiện đúng.")
        try:
            bi = C.base_info()
        except Exception:
            bi = {"base": str(C.BASE), "source": "?", "courses": str(C.BASE / "courses")}

        # info strip
        info = ctk.CTkFrame(self.content, fg_color="transparent")
        info.pack(fill="x", pady=(0, 8))
        self.stat_card(info, "Theme", THEME_MODE, DENSITY, "info")
        self.stat_card(info, "BASE source", str(bi.get("source") or "?")[:16], "path", "muted")
        try:
            import version as V
            ver_short = V.__version__
        except Exception:
            ver_short = "?"
        self.stat_card(info, "Version", ver_short, "selftest OK", "ok")

        card = self.card()
        ctk.CTkLabel(card, text="Thư mục dữ liệu (BASE)", font=(FT, 13, "bold"),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(card, text=f"{bi.get('base')}\ncourses: {bi.get('courses')}",
                     font=("Consolas", 11), text_color=TEXT2, justify="left",
                     wraplength=600).pack(anchor="w", padx=16, pady=(0, 8))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 8))
        self.base_var = ctk.StringVar(value=str(bi.get("base") or ""))
        ctk.CTkEntry(row, textvariable=self.base_var, font=("Consolas", 12), height=dens("entry_h", 36),
                     corner_radius=10, fg_color=CARD2, border_color=BORDER).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        btn(row, "💾 Lưu BASE", self.doctor_save_base, kind="accent", width=120).pack(side="left")
        ctk.CTkLabel(card, text="Hoặc SKOOL_BASE env. Đổi BASE xong mở lại Dashboard.",
                     font=(FT, 11), text_color=TEXT2, wraplength=600,
                     justify="left").pack(anchor="w", padx=16, pady=(0, 14))

        brow = ctk.CTkFrame(self.content, fg_color="transparent")
        brow.pack(fill="x", pady=8)
        btn(brow, "▶  Chạy Doctor", self.doctor_run, kind="success", width=140).pack(side="left")
        btn(brow, "Self-test", self.run_selftest, kind="secondary", width=110).pack(side="left", padx=6)
        btn(brow, "Preflight", self.show_check, kind="secondary", width=110).pack(side="left", padx=6)
        btn(brow, "Mở BASE", lambda: self._open_path(C.BASE), kind="soft", width=100).pack(side="left", padx=6)

        out = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=dens("card_r", 16),
                           border_width=1, border_color=BORDER)
        out.pack(fill="x", pady=8)
        ctk.CTkLabel(out, text="KẾT QUẢ", font=(FT, 11, "bold"), text_color=TEXT2).pack(
            anchor="w", padx=14, pady=(10, 0))
        self.doctor_box = ctk.CTkTextbox(out, height=300 if DENSITY == "comfortable" else 220,
                                         font=("Consolas", 11), fg_color=LOG_BG, text_color=TEXT,
                                         corner_radius=10, border_width=0)
        self.doctor_box.pack(fill="x", padx=10, pady=(6, 12))
        self.doctor_box.insert("end", "Bấm «Chạy Doctor» để quét môi trường…")
        self.doctor_box.configure(state="disabled")

        btn(self.content, "←  Dashboard", self.show_dashboard, kind="ghost", width=120).pack(anchor="w", pady=10)

    def doctor_save_base(self):
        p = (self.base_var.get() if hasattr(self, "base_var") else "").strip()
        if not p:
            messagebox.showinfo("Trống", "Nhập đường dẫn BASE."); return
        try:
            C.set_base(p, persist=True)
            self.write(f"✓ Đã lưu BASE = {C.BASE}")
            messagebox.showinfo("BASE", f"Đã lưu:\n{C.BASE}\n\nMở lại Dashboard để quét khóa.")
            self.show_doctor()
        except Exception as e:
            messagebox.showerror("BASE", str(e))

    def doctor_run(self):
        self.write("🩺 Doctor…")
        def work():
            try:
                import doctor as D
                import io
                rep = D.run_doctor()
                buf = io.StringIO()
                # capture print
                import contextlib
                with contextlib.redirect_stdout(buf):
                    D.print_report(rep)
                return buf.getvalue(), rep
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                messagebox.showerror("Doctor", str(r)); return
            text, rep = r
            if hasattr(self, "doctor_box") and self.doctor_box.winfo_exists():
                self.doctor_box.configure(state="normal")
                self.doctor_box.delete("1.0", "end")
                self.doctor_box.insert("end", text)
                self.doctor_box.configure(state="disabled")
            self.write(f"Doctor: {rep.get('fail')} FAIL, {rep.get('warn')} WARN")
        self.run_async(work, cb)

    def run_selftest(self):
        if self.proc:
            messagebox.showinfo("Đang bận", "Đợi tác vụ hiện tại xong."); return
        self.write("🧪 Self-test (doctor --quick)…")
        self.start([PY, "selftest.py", "--quick"], "SELFTEST", on_done=lambda: self.write("✓ Self-test xong — xem Nhật ký"))

    # ====================== WEB VIEWER + HEALTH (Phase 4) ======================
    def show_web_tools(self):
        self.set_nav("web")
        self.clear()
        self.head("Web Viewer & Health", "Duyệt knowledge local · health check · lịch hàng ngày · xuất site tĩnh.")
        # Web
        card = self.card()
        ctk.CTkLabel(card, text="🌐 Local Web Viewer", font=(FT, 13, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(card, text="Duyệt khóa / bài (mô tả + transcript), tìm kiếm, health. Chỉ lắng nghe máy bạn (127.0.0.1).",
                     font=(FT, 12), text_color=TEXT2, wraplength=540, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(row, text="Port:", font=(FT, 12), text_color=TEXT).pack(side="left")
        self.web_port = ctk.StringVar(value="8765")
        ctk.CTkEntry(row, textvariable=self.web_port, width=80, font=("Consolas", 12)).pack(side="left", padx=8)
        brow = ctk.CTkFrame(card, fg_color="transparent"); brow.pack(fill="x", padx=14, pady=(6, 12))
        btn(brow, "▶  Mở Web Viewer", self.web_start, kind="success", width=160).pack(side="left")
        btn(brow, "■  Dừng", self.web_stop, kind="danger", width=90).pack(side="left", padx=8)
        btn(brow, "Mở trình duyệt", self.web_open_browser, kind="secondary", width=140).pack(side="left")
        self.web_status = ctk.CTkLabel(card, text=self._web_status_text(), font=(FT, 12), text_color=TEXT2)
        self.web_status.pack(anchor="w", padx=14, pady=(0, 12))

        # Health
        hcard = self.card()
        ctk.CTkLabel(hcard, text="❤ Health check", font=(FT, 13, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(hcard, text="Quét mọi khóa: bài thiếu, token hết hạn. Ghi courses/_health.json + _health.md.",
                     font=(FT, 12), text_color=TEXT2, wraplength=540, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        hrow = ctk.CTkFrame(hcard, fg_color="transparent"); hrow.pack(fill="x", padx=14, pady=(0, 12))
        btn(hrow, "▶  Chạy health ngay", self.health_run_now, kind="success", width=170).pack(side="left")
        btn(hrow, "Bật lịch hàng ngày", self.health_install_schedule, kind="secondary", width=160).pack(side="left", padx=8)
        btn(hrow, "Tắt lịch", self.health_uninstall_schedule, kind="ghost", width=100).pack(side="left")
        self.health_lbl = ctk.CTkLabel(hcard, text="", font=(FT, 12), text_color=TEXT2, wraplength=540, justify="left")
        self.health_lbl.pack(anchor="w", padx=14, pady=(0, 12))

        # Static site export (Phase 5)
        scard = self.card()
        ctk.CTkLabel(scard, text="📄 Xuất site tĩnh (offline HTML)", font=(FT, 13, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(scard, text="Tạo thư mục courses/_site với index + tìm kiếm offline — mở bằng trình duyệt, không cần server. Có thể copy sang USB / host tĩnh.",
                     font=(FT, 12), text_color=TEXT2, wraplength=540, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        srow = ctk.CTkFrame(scard, fg_color="transparent"); srow.pack(fill="x", padx=14, pady=(0, 12))
        btn(srow, "⬇  Xuất site", self.export_static_site, kind="success", width=140).pack(side="left")
        btn(srow, "Mở thư mục _site", self.open_static_site, kind="secondary", width=150).pack(side="left", padx=8)
        self.site_lbl = ctk.CTkLabel(scard, text="", font=(FT, 12), text_color=TEXT2)
        self.site_lbl.pack(anchor="w", padx=14, pady=(0, 12))

        # Embed status
        ecard = self.card()
        try:
            from rag.embed_local import available, model_name
            emb = available()
            emb_txt = f"Dense embed: ✓ sentence-transformers ({model_name()})" if emb else "Dense embed: ✗ chưa cài (pip install sentence-transformers) — đang dùng TF-IDF"
        except Exception:
            emb_txt = "Dense embed: ?"
        ctk.CTkLabel(ecard, text="🧠 RAG embeddings", font=(FT, 13, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(ecard, text=emb_txt, font=(FT, 12), text_color=TEXT2, wraplength=540, justify="left").pack(anchor="w", padx=14, pady=(0, 12))

        btn(self.content, "←  Dashboard", self.show_dashboard, kind="ghost", width=120).pack(anchor="w", pady=10)

    def export_static_site(self):
        self.write("📄 Đang xuất static site…")
        def work():
            try:
                import export_site as ES
                return str(ES.export_site(log=lambda s: self.ui_q.put(lambda m=s: self.write(m))))
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                messagebox.showerror("Xuất site", str(r)); return
            if hasattr(self, "site_lbl") and self.site_lbl.winfo_exists():
                self.site_lbl.configure(text=f"→ {r}")
            if messagebox.askyesno("Xong", f"Đã xuất:\n{r}\n\nMở index.html?"):
                try:
                    import webbrowser
                    webbrowser.open(Path(r).joinpath("index.html").as_uri())
                except Exception:
                    self._open_path(r)
        self.run_async(work, cb)

    def open_static_site(self):
        import config as C2
        p = C2.BASE / "courses" / "_site"
        if not p.exists():
            messagebox.showinfo("Chưa có", "Chưa xuất site. Bấm «Xuất site» trước."); return
        self._open_path(p)

    def _web_status_text(self):
        p = getattr(self, "_web_proc", None)
        if p and p.poll() is None:
            port = getattr(self, "_web_port_running", "8765")
            return f"● Đang chạy — http://127.0.0.1:{port}/"
        return "○ Chưa chạy"

    def web_start(self):
        if getattr(self, "_web_proc", None) and self._web_proc.poll() is None:
            messagebox.showinfo("Đang chạy", "Web Viewer đã chạy. Bấm Mở trình duyệt hoặc Dừng trước."); return
        try:
            port = int(self.web_port.get().strip() if hasattr(self, "web_port") else 8765)
        except Exception:
            port = 8765
        self._web_port_running = port
        cmd = [PY, "web_viewer.py", "--port", str(port), "--no-browser"]
        try:
            self._web_proc = subprocess.Popen(
                cmd, cwd=HERE, env=dict(os.environ, PYTHONUTF8="1"),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WIN,
            )
        except Exception as e:
            messagebox.showerror("Web Viewer", str(e)); return
        self.write(f"🌐 Web Viewer: http://127.0.0.1:{port}/")
        if hasattr(self, "web_status") and self.web_status.winfo_exists():
            self.web_status.configure(text=self._web_status_text())
        self.root.after(700, self.web_open_browser)

    def web_stop(self):
        p = getattr(self, "_web_proc", None)
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
            self.write("🌐 Đã dừng Web Viewer")
        self._web_proc = None
        if hasattr(self, "web_status") and self.web_status.winfo_exists():
            self.web_status.configure(text=self._web_status_text())

    def web_open_browser(self):
        port = getattr(self, "_web_port_running", None) or (
            self.web_port.get().strip() if hasattr(self, "web_port") else "8765")
        url = f"http://127.0.0.1:{port}/"
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Trình duyệt", str(e))

    def health_run_now(self):
        self.write("❤ Đang health check…")
        def work():
            try:
                import health_check as H
                r = H.run_health()
                H.write_health(r)
                return r
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                messagebox.showerror("Health", str(r)); return
            sm = r.get("summary") or {}
            msg = (f"{sm.get('n_courses')} khóa · {sm.get('done')}/{sm.get('total')} bài · "
                   f"thiếu {sm.get('missing')} · hết hạn {sm.get('expired')} · "
                   f"cần chú ý {sm.get('needs_attention')}")
            self.write(f"❤ {msg}")
            if hasattr(self, "health_lbl") and self.health_lbl.winfo_exists():
                self.health_lbl.configure(text=msg + "\n→ courses/_health.json · _health.md")
            messagebox.showinfo("Health", msg)
        self.run_async(work, cb)

    def health_install_schedule(self):
        if os.name == "nt":
            ps = HERE / "install_health_task.ps1"
            if not ps.exists():
                messagebox.showerror("Lịch", f"Thiếu {ps}"); return
            try:
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)],
                    creationflags=NO_WIN,
                )
                self.write("❤ Đã gọi cài Scheduled Task (Health hàng ngày 09:00)")
                messagebox.showinfo("Lịch", "Đã đăng ký task Windows: SkoolArchiver-Health (09:00 hàng ngày).")
            except Exception as e:
                messagebox.showerror("Lịch", str(e))
        else:
            sh = HERE / "install_health_launchd.sh"
            try:
                os.chmod(sh, 0o755)
                subprocess.check_call(["/bin/bash", str(sh)])
                self.write("❤ Đã cài LaunchAgent health (macOS 09:00)")
                messagebox.showinfo("Lịch", "Đã load LaunchAgent com.skoolarchiver.health (09:00).")
            except Exception as e:
                messagebox.showerror(
                    "Lịch",
                    f"Không cài auto được: {e}\n\nChạy tay:\n  bash app/install_health_launchd.sh\n"
                    "hoặc cron: 0 9 * * * python3 app/health_check.py --write",
                )

    def health_uninstall_schedule(self):
        if os.name == "nt":
            ps = HERE / "uninstall_health_task.ps1"
            try:
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)],
                    creationflags=NO_WIN,
                )
                messagebox.showinfo("Lịch", "Đã gỡ task SkoolArchiver-Health (nếu có).")
            except Exception as e:
                messagebox.showerror("Lịch", str(e))
        else:
            try:
                plist = Path.home() / "Library/LaunchAgents/com.skoolarchiver.health.plist"
                subprocess.call(["launchctl", "unload", str(plist)])
                if plist.exists():
                    plist.unlink()
                messagebox.showinfo("Lịch", "Đã unload LaunchAgent (nếu có).")
            except Exception as e:
                messagebox.showerror("Lịch", str(e))

    # ====================== RAG CHAT (S5 + Phase 2 vector/multi) ======================
    def show_chat(self, preselect=None):
        self.set_nav("chat")
        self.clear()
        self.head("Chat RAG", "Hỏi đáp trên mô tả + lời giảng — TF-IDF / dense / multi-khóa. Trả lời bằng Claude.")
        items = self.existing_courses()
        if preselect and preselect in items:
            cur = preselect
        elif self.course_name:
            cur = self.course_name if self.course_name in items else (
                "SkoolCourse (đã có sẵn)" if self.course_name is None and items else (items[0] if items else ""))
        else:
            cur = items[0] if items else ""
        top = self.card()
        row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=14, pady=(14, 6))
        ctk.CTkLabel(row, text="Khóa", font=(FT, 12, "bold"), text_color=TEXT2).pack(side="left")
        self.chat_course = ctk.StringVar(value=cur)
        if items:
            ctk.CTkOptionMenu(row, variable=self.chat_course, values=items, width=260,
                              fg_color=CARD2, button_color=ACCENT, button_hover_color=ACCENT_H,
                              text_color=TEXT).pack(side="left", padx=10)
        btn(row, "📇 Index", self.chat_reindex, kind="secondary", width=100).pack(side="left", padx=4)
        try:
            import ai_tools
            has = ai_tools.have_api()
        except Exception:
            has = False
        self.pill(row, "Claude ✓" if has else "Cần API key", "ok" if has else "danger").pack(side="right")

        row2 = ctk.CTkFrame(top, fg_color="transparent"); row2.pack(fill="x", padx=14, pady=(0, 12))
        self.chat_multi = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row2, text="Chat tất cả khóa", variable=self.chat_multi,
                        font=(FT, 12), text_color=TEXT, fg_color=ACCENT, hover_color=ACCENT_H,
                        border_color=BORDER).pack(side="left")
        ctk.CTkLabel(row2, text="Method", font=(FT, 11), text_color=TEXT2).pack(side="left", padx=(16, 4))
        self.chat_method = ctk.StringVar(value="auto")
        ctk.CTkOptionMenu(row2, variable=self.chat_method, values=["auto", "dense", "tfidf", "keyword"], width=110,
                          fg_color=CARD2, button_color=ACCENT, button_hover_color=ACCENT_H,
                          text_color=TEXT).pack(side="left")

        chat_card = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=16,
                                 border_width=1, border_color=BORDER)
        chat_card.pack(fill="x", pady=6)
        self.chat_box = ctk.CTkTextbox(chat_card, height=300, font=(FT, 13),
                                       fg_color=LOG_BG, text_color=TEXT, corner_radius=12, border_width=0)
        self.chat_box.pack(fill="x", padx=10, pady=10)
        self.chat_box.configure(state="disabled")
        for role, text in self.chat_history[-12:]:
            self._chat_append(role, text, persist=False)

        self.chat_src = ctk.CTkLabel(self.content, text="", font=(FT, 11), text_color=TEXT2,
                                    wraplength=640, justify="left")
        self.chat_src.pack(anchor="w", pady=(2, 6))

        inp = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=14,
                           border_width=1, border_color=BORDER)
        inp.pack(fill="x", pady=4)
        ir = ctk.CTkFrame(inp, fg_color="transparent")
        ir.pack(fill="x", padx=10, pady=10)
        self.chat_input = ctk.CTkEntry(ir, placeholder_text="Hỏi về nội dung khóa… (Enter để gửi)",
                                       font=(FT, 13), height=40, corner_radius=10,
                                       fg_color=CARD2, border_color=BORDER)
        self.chat_input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.chat_input.bind("<Return>", lambda e: self.chat_send())
        btn(ir, "Gửi  →", self.chat_send, kind="accent", width=100, height=40).pack(side="left")

        nav = ctk.CTkFrame(self.content, fg_color="transparent"); nav.pack(fill="x", pady=12)
        btn(nav, "←  Dashboard", self.show_dashboard, kind="ghost", width=120).pack(side="left")
        btn(nav, "Xóa lịch sử", self.chat_clear, kind="secondary", width=120).pack(side="right")

    def _chat_append(self, role, text, persist=True):
        if persist:
            self.chat_history.append((role, text))
        if not (hasattr(self, "chat_box") and self.chat_box.winfo_exists()):
            return
        self.chat_box.configure(state="normal")
        prefix = "Bạn: " if role == "user" else "Archiver: "
        self.chat_box.insert("end", prefix + text.strip() + "\n\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def chat_clear(self):
        self.chat_history = []
        if hasattr(self, "chat_box") and self.chat_box.winfo_exists():
            self.chat_box.configure(state="normal"); self.chat_box.delete("1.0", "end"); self.chat_box.configure(state="disabled")
        if hasattr(self, "chat_src") and self.chat_src.winfo_exists():
            self.chat_src.configure(text="")

    def chat_reindex(self):
        v = self.chat_course.get().strip() if hasattr(self, "chat_course") else ""
        if not v:
            messagebox.showinfo("Chưa chọn", "Chọn khóa."); return
        root = self.item_root(v)
        self.write(f"Đang index RAG: {v}…")
        def work():
            try:
                from rag.index import build_catalog
                return build_catalog(root, log=lambda s: self.ui_q.put(lambda m=s: self.write(m)))
            except Exception as e:
                return e
        def cb(r):
            if isinstance(r, Exception):
                messagebox.showerror("Index", str(r)); return
            messagebox.showinfo("Index", f"Đã index {r.get('n_lessons', 0)} bài · {r.get('n_chars', 0)} ký tự")
        self.run_async(work, cb)

    def chat_send(self):
        q = ""
        if hasattr(self, "chat_input") and self.chat_input.winfo_exists():
            q = self.chat_input.get().strip()
        if not q: return
        v = self.chat_course.get().strip() if hasattr(self, "chat_course") else ""
        if not v:
            messagebox.showinfo("Chưa chọn", "Chọn khóa."); return
        try:
            import ai_tools
            if not ai_tools.have_api():
                messagebox.showinfo("Cần API key", "Chat cần Claude API key.\nVào Xuất & Báo cáo để dán key."); return
        except Exception:
            pass
        self.chat_input.delete(0, "end")
        self._chat_append("user", q)
        multi = bool(self.chat_multi.get()) if hasattr(self, "chat_multi") else False
        method = self.chat_method.get() if hasattr(self, "chat_method") else "auto"
        self._chat_append("assistant", "⏳ Đang tìm" + (" multi-course" if multi else "") + " + gọi Claude…")
        root = self.item_root(v)
        def work():
            try:
                from pathlib import Path as _P
                from rag.index import build_catalog
                from rag.chat import answer, answer_multi
                if multi:
                    roots = [self.item_root(it) for it in self.existing_courses()]
                    for r in roots:
                        full = _P(r) / ".rag" / "catalog_full.json"
                        if r.exists() and not full.exists():
                            build_catalog(r, log=lambda s: self.ui_q.put(lambda m=s: self.write(m)))
                    return answer_multi(roots, q, log=lambda s: self.ui_q.put(lambda m=s: self.write(m)))
                full = _P(root) / ".rag" / "catalog_full.json"
                if not full.exists():
                    self.ui_q.put(lambda: self.write("RAG: chưa có index — đang index lần đầu…"))
                    build_catalog(root, log=lambda s: self.ui_q.put(lambda m=s: self.write(m)))
                return answer(root, q, method=method,
                              log=lambda s: self.ui_q.put(lambda m=s: self.write(m)))
            except Exception as e:
                return e
        def cb(r):
            if self.chat_history and self.chat_history[-1][0] == "assistant" and self.chat_history[-1][1].startswith("⏳"):
                self.chat_history.pop()
            if hasattr(self, "chat_box") and self.chat_box.winfo_exists():
                self.chat_box.configure(state="normal"); self.chat_box.delete("1.0", "end"); self.chat_box.configure(state="disabled")
                hist = list(self.chat_history)
                self.chat_history = []
                for role, text in hist:
                    self._chat_append(role, text)
            if isinstance(r, Exception):
                self._chat_append("assistant", f"Lỗi: {r}")
                return
            self._chat_append("assistant", r.get("answer") or "(trống)")
            srcs = r.get("sources") or []
            if hasattr(self, "chat_src") and self.chat_src.winfo_exists():
                if srcs:
                    lines = " · ".join(
                        f"[{s.get('course','')}] {s.get('chapter')}/{s.get('title')}" if s.get("course")
                        else f"{s.get('chapter')}/{s.get('title')}"
                        for s in srcs[:5])
                    self.chat_src.configure(
                        text=f"Nguồn ({r.get('method','')}): {lines}")
                else:
                    self.chat_src.configure(text=f"method={r.get('method')} · indexed={r.get('n_indexed', 0)}")
        self.run_async(work, cb)


def main():
    root = ctk.CTk()
    App(root)
    if os.environ.get("GUI_SMOKE_TEST"): root.after(900, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
