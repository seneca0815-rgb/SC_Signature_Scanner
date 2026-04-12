"""
setup_wizard.py  –  SC Signature Reader
First-run configuration wizard.
Called automatically by the installer, or manually via:
    SCSigReader.exe --setup
"""

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

from PIL import Image, ImageTk

# ---------------------------------------------------------------------------
# Base directory – works both as plain Python and PyInstaller frozen exe
# ---------------------------------------------------------------------------

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR     = get_base_dir()
CONFIG_PATH  = BASE_DIR / "config.json"
PREVIEW_PATH = BASE_DIR / "theme_preview.png"
THEMES_PATH  = BASE_DIR / "themes.py"

# ---------------------------------------------------------------------------
# Load themes dynamically from themes.py
# ---------------------------------------------------------------------------

def load_themes() -> dict:
    """Import THEMES from themes.py without a hard dependency."""
    import importlib.util
    spec   = importlib.util.spec_from_file_location("themes", THEMES_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.THEMES


THEMES = load_themes()

# ---------------------------------------------------------------------------
# Resolution presets
# ---------------------------------------------------------------------------

RESOLUTIONS = {
    "1920 × 1080":  {"top": 230, "left":  860, "width": 200, "height": 220},
    "2560 × 1440":  {"top": 300, "left": 1100, "width": 300, "height": 300},
    "3440 × 1440":  {"top": 300, "left": 1420, "width": 400, "height": 300},
    "Custom (edit config.json manually)": None,
}

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

C_BG       = "#1a1f2e"
C_SURFACE  = "#252b3b"
C_BORDER   = "#3a4155"
C_TEXT     = "#e2e8f0"
C_MUTED    = "#8892a4"
C_ACCENT   = "#e2c97e"
C_BTN_BG   = "#2d3448"
C_BTN_HOV  = "#3a4155"


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------

class SetupWizard:
    STEPS = ["welcome", "resolution", "theme", "finish"]

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SC Signature Reader – Setup")
        self.root.geometry("620x520")
        self.root.resizable(False, False)
        self.root.configure(bg=C_BG)
        self.root.eval("tk::PlaceWindow . center")

        self._step       = 0
        self._res_var    = tk.StringVar(value="2560 × 1440")
        self._theme_var  = tk.StringVar(value=list(THEMES.keys())[0])
        self._preview_tk = None   # keep reference so GC doesn't collect it

        self._build_header()
        self._frame = tk.Frame(self.root, bg=C_BG)
        self._frame.pack(fill="both", expand=True, padx=32, pady=0)
        self._build_nav()
        self._render_step()

        # Fenster-X-Button abfangen
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Persistent chrome
    # ------------------------------------------------------------------

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=C_BG)
        hdr.pack(fill="x", padx=32, pady=(28, 0))
        tk.Label(hdr, text="SC Signature Reader",
                 bg=C_BG, fg=C_ACCENT,
                 font=("Consolas", 18, "bold")).pack(anchor="w")
        tk.Label(hdr, text="Setup Wizard",
                 bg=C_BG, fg=C_MUTED,
                 font=("Consolas", 11)).pack(anchor="w")
        tk.Frame(hdr, bg=C_BORDER, height=1).pack(fill="x", pady=(12, 0))

    def _build_nav(self):
        nav = tk.Frame(self.root, bg=C_BG)
        nav.pack(fill="x", side="bottom", padx=32, pady=20)
        tk.Frame(nav, bg=C_BORDER, height=1).pack(fill="x", pady=(0, 14))

        row = tk.Frame(nav, bg=C_BG)
        row.pack(fill="x")

        self._btn_back = tk.Button(
            row, text="← Back",
            bg=C_BTN_BG, fg=C_TEXT, relief="flat",
            activebackground=C_BTN_HOV, activeforeground=C_TEXT,
            font=("Consolas", 11), padx=16, pady=6,
            command=self._back)
        self._btn_back.pack(side="left")

        self._btn_next = tk.Button(
            row, text="Next →",
            bg=C_ACCENT, fg="#111827", relief="flat",
            activebackground="#c9b368", activeforeground="#111827",
            font=("Consolas", 11, "bold"), padx=20, pady=6,
            command=self._next)
        self._btn_next.pack(side="right")

        self._step_label = tk.Label(
            row, text="", bg=C_BG, fg=C_MUTED,
            font=("Consolas", 10))
        self._step_label.pack(side="right", padx=16)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _next(self):
        if self._step < len(self.STEPS) - 1:
            self._step += 1
            self._render_step()
        else:
            self._save_and_close()

    def _back(self):
        if self._step > 0:
            self._step -= 1
            self._render_step()

    def _render_step(self):
        for w in self._frame.winfo_children():
            w.destroy()

        name = self.STEPS[self._step]
        getattr(self, f"_page_{name}")()

        total = len(self.STEPS)
        self._step_label.config(
            text=f"Step {self._step + 1} of {total}")
        self._btn_back.config(
            state="normal" if self._step > 0 else "disabled")
        self._btn_next.config(
            text="Finish" if self._step == total - 1 else "Next →")

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    def _page_welcome(self):
        f = self._frame
        tk.Label(f, text="Welcome", bg=C_BG, fg=C_TEXT,
                 font=("Consolas", 15, "bold")).pack(anchor="w", pady=(24, 8))
        body = (
            "This wizard will configure SC Signature Reader\n"
            "for your system.\n\n"
            "You will be asked to select your screen resolution\n"
            "and a display theme for the overlay.\n\n"
            "Settings are saved to config.json and can be\n"
            "changed at any time."
        )
        tk.Label(f, text=body, bg=C_BG, fg=C_MUTED,
                 font=("Consolas", 11), justify="left").pack(anchor="w")

    def _page_resolution(self):
        f = self._frame
        tk.Label(f, text="Screen resolution", bg=C_BG, fg=C_TEXT,
                 font=("Consolas", 15, "bold")).pack(anchor="w", pady=(24, 4))
        tk.Label(f,
                 text="Select the resolution you play Star Citizen at.",
                 bg=C_BG, fg=C_MUTED,
                 font=("Consolas", 11)).pack(anchor="w", pady=(0, 20))

        for label in RESOLUTIONS:
            row = tk.Frame(f, bg=C_BG)
            row.pack(fill="x", pady=3)
            tk.Radiobutton(
                row,
                text=label,
                variable=self._res_var,
                value=label,
                bg=C_BG, fg=C_TEXT,
                selectcolor=C_SURFACE,
                activebackground=C_BG,
                activeforeground=C_ACCENT,
                font=("Consolas", 12),
            ).pack(anchor="w")

        tk.Label(f,
                 text=(
                     "Not sure? Check Display Settings → Resolution.\n"
                     "The scan region can be fine-tuned in config.json later."
                 ),
                 bg=C_BG, fg=C_MUTED,
                 font=("Consolas", 10), justify="left").pack(
                     anchor="w", pady=(20, 0))

    def _page_theme(self):
        f = self._frame
        tk.Label(f, text="Overlay theme", bg=C_BG, fg=C_TEXT,
                 font=("Consolas", 15, "bold")).pack(anchor="w", pady=(16, 4))
        tk.Label(f,
                 text="Choose how the overlay looks in-game.",
                 bg=C_BG, fg=C_MUTED,
                 font=("Consolas", 11)).pack(anchor="w", pady=(0, 12))

        # ---- theme radio buttons + live preview side by side ----
        content = tk.Frame(f, bg=C_BG)
        content.pack(fill="both", expand=True)

        left = tk.Frame(content, bg=C_BG)
        left.pack(side="left", anchor="n", padx=(0, 24))

        # Preview box
        right = tk.Frame(content, bg=C_SURFACE,
                         highlightbackground=C_BORDER,
                         highlightthickness=1)
        right.pack(side="left", fill="both", expand=True)

        self._preview_label = tk.Label(right, bg=C_SURFACE)
        self._preview_label.pack(expand=True)

        # Radio buttons – one per theme
        for name, theme in THEMES.items():
            tk.Radiobutton(
                left,
                text=name,
                variable=self._theme_var,
                value=name,
                bg=C_BG, fg=C_TEXT,
                selectcolor=C_SURFACE,
                activebackground=C_BG,
                activeforeground=C_ACCENT,
                font=("Consolas", 12),
                command=self._update_theme_preview,
            ).pack(anchor="w", pady=4)

        # Initial preview
        self._update_theme_preview()

    def _update_theme_preview(self):
        """Render a live overlay pill for the currently selected theme."""
        name  = self._theme_var.get()
        theme = THEMES[name]

        bg  = theme["bg_color"]
        fg  = theme["fg_color"]
        ex  = theme.get("example", "ℹ  Example text")
        fs  = theme.get("font_size", 13)

        # Destroy previous canvas before creating a new one
        for child in self._preview_label.winfo_children():
            child.destroy()

        # Build a tiny canvas that mimics the real overlay
        canvas = tk.Canvas(
            self._preview_label,
            bg=C_SURFACE, highlightthickness=0,
            width=280, height=80)
        canvas.pack()

        # Pill background
        canvas.create_rectangle(20, 20, 260, 60,
                                 fill=bg, outline=C_BORDER, width=1)

        # Text
        try:
            fnt = tkfont.Font(family="Consolas", size=fs, weight="bold")
        except Exception:
            fnt = tkfont.Font(size=fs, weight="bold")
        canvas.create_text(140, 40, text=ex, fill=fg,
                            font=fnt, anchor="center")

        # Alpha note
        alpha_txt = f"alpha {theme.get('alpha', 1.0):.2f}"
        canvas.create_text(260, 72, text=alpha_txt,
                            fill=C_MUTED,
                            font=tkfont.Font(family="Consolas", size=9),
                            anchor="e")

    def _page_finish(self):
        f = self._frame
        tk.Label(f, text="All done!", bg=C_BG, fg=C_ACCENT,
                 font=("Consolas", 15, "bold")).pack(anchor="w", pady=(24, 8))

        res   = self._res_var.get()
        theme = self._theme_var.get()

        summary = (
            f"Resolution : {res}\n"
            f"Theme      : {theme}\n\n"
            "Click Finish to save your settings\n"
            "and launch SC Signature Reader."
        )
        tk.Label(f, text=summary, bg=C_BG, fg=C_TEXT,
                 font=("Consolas", 12), justify="left").pack(anchor="w")

        tk.Label(f,
                 text="You can reopen this wizard anytime with:  --setup",
                 bg=C_BG, fg=C_MUTED,
                 font=("Consolas", 10)).pack(anchor="w", pady=(24, 0))

    # ------------------------------------------------------------------
    # Save & launch
    # ------------------------------------------------------------------
    def _on_close(self):
        """Roter X-Button – Config nicht speichern, Prozess beenden."""
        self.root.destroy()
        sys.exit(0)


    def _save_and_close(self):
        # Load existing config
        try:
            with open(CONFIG_PATH, encoding="utf-8") as fh:
                cfg = json.load(fh)
        except FileNotFoundError:
            cfg = {}

        # Resolution
        res_label = self._res_var.get()
        region    = RESOLUTIONS.get(res_label)
        if region:
            cfg["scan_region"] = region
        # Theme
        cfg["theme"] = self._theme_var.get()

        # Write back
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)

        self.root.destroy()
        sys.exit(0)      # ← Prozess explizit beenden
        
    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--setup" in sys.argv or len(sys.argv) == 1:
        SetupWizard().run()
