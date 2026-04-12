"""
display_window.py  –  SC Signature Reader / Vargo Dynamics
VD-SFR1 cockpit signal display.

Two modes (config.json "display_mode"):
  "sfr1_slim"        – Model A, ultra-slim single row  (~44 px tall)
  "sfr1_instrument"  – Model C, cockpit instrument panel (~120 px tall)
  "off"              – display hidden

Both are transparent always-on-top Toplevel windows, draggable,
position saved to config.json on drag-end.
"""

import math
import random
import re
import tkinter as tk

from app_state import AppState

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------

C_BG      = "#1a1a2a"
C_SURFACE = "#08090e"   # inner screen / glass fill
C_BEZEL   = "#0a0c12"   # outer bezel + metal panels
C_SHELL   = "#1a1e2c"   # Model C shell background
C_BORDER  = "#1a2535"   # panel border
C_BEVEL_T = "#3a4a60"   # shell top bevel
C_BEVEL_B = "#060810"   # shell bottom bevel
C_CYAN    = "#4fc3c3"
C_GOLD    = "#c9a84c"
C_TEXT    = "#d8d8e8"
C_MUTED   = "#304050"
C_GREEN   = "#4fc97a"
C_GREEN_D = "#1a3828"   # dim green for LED off-state
C_RED     = "#c94f4f"
C_SHINE   = "#1c2e3a"   # glass top-edge shine  (was #b4dceb @gray12 stipple)
C_REFLECT = "#0d1a22"   # glass diagonal reflection (was #a0c8dc @gray6 stipple)
C_SHADOW  = "#020208"   # inset shadow overlay     (was #000000 @gray25 stipple)
C_SCAN    = "#1a4040"   # scan-line colour          (was #4fc3c3 @gray12 stipple)

FONT = "Courier New"

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

# Model A – slim
SLIM_H       = 44
SLIM_ID_W    = 70
SLIM_LED_W   = 28
SLIM_GLASS_W = 402
SLIM_W       = SLIM_ID_W + SLIM_GLASS_W + SLIM_LED_W   # 500

# Model C – instrument
INST_H       = 120
INST_W       = 480
INST_PAD     = 4    # shell padding on all sides
INST_HDR_H   = 24
INST_FTR_H   = 14
INST_BODY_H  = 70   # INST_H - 2*PAD - HDR - FTR - 2 gaps = 70
INST_MAT_W   = 52
INST_GLS_W   = 320
INST_REC_W   = 96   # 472 - 52 - 2 - 320 - 2 = 96

# Derived body positions (all relative to shell canvas)
_BDY_Y  = INST_PAD + INST_HDR_H + 2   # 30
_GLS_X  = INST_PAD + INST_MAT_W + 2   # 58
_REC_X  = _GLS_X + INST_GLS_W + 2     # 380
_FTR_Y  = _BDY_Y + INST_BODY_H + 2    # 102

GLASS_INSET  = 4     # bezel → inner screen inset

# Matrix
MAT_ROWS     = 4
MAT_COLS     = 5
MAT_DOT      = 5
MAT_GAP      = 4

# Animation timing (ms)
SCAN_TICK    = 50
SCAN_PERIOD  = 3500
LED_HALF     = 1000   # LED_PERIOD / 2
TICKER_CYCLE = 14000
MAT_TICK     = 50

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_signal(text: str):
    """
    Parse 'Mineral (Mx)  ·  Rarity' → (mineral, mult, rarity).
    Handles fuzzy prefix, collision entries (first only), empty text.
    Returns None when text is falsy.
    """
    if not text:
        return None
    clean = re.sub(r'^~\s*', '', text).strip()
    clean = re.sub(r'\s*\(Fuzzy[^)]*\)\s*$', '', clean).strip()
    first = clean.split('/')[0].strip()
    m = re.match(r'^(.+?)\s+\((\d+)x\)\s*[·.]\s*(.+)$', first)
    if m:
        return m.group(1).strip(), f"({m.group(2)}x)", m.group(3).strip()
    return first, "", ""


def _lerp_color(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two #rrggbb hex colors."""
    def _p(c):
        c = c.lstrip('#')
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    r1, g1, b1 = _p(c1)
    r2, g2, b2 = _p(c2)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )


# ---------------------------------------------------------------------------
# DisplayWindow
# ---------------------------------------------------------------------------

class DisplayWindow:

    def __init__(self, root: tk.Tk, config: dict, state: AppState):
        self._root   = root
        self._config = config
        self._state  = state

        # Animation guard – set False to stop all loops
        self._anim_active = False

        # Canvas / item refs – populated by _build_*
        self._glass_canvas  = None   # canvas that owns the scan-line item
        self._led_canvas    = None   # canvas that owns the LED oval
        self._inst_canvas   = None   # full shell canvas (instrument only)
        self._scan_id       = None
        self._led_id        = None
        self._ticker_id     = None
        self._matrix_items  = []     # list of (item_id, phase, is_gold)
        self._recent_texts  = []     # instrument recent-log item IDs

        # Animation state
        self._scan_y        = 0.0
        self._scan_min_y    = 0.0
        self._scan_max_y    = 1.0
        self._led_state     = True
        self._ticker_x      = 0.0
        self._ticker_start  = 0.0
        self._ticker_y      = 0.0
        self._matrix_t      = 0.0

        # Drag
        self._drag_x = 0
        self._drag_y = 0

        self._win = tk.Toplevel(root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.configure(bg="black")
        self._win.wm_attributes("-transparentcolor", "black")

        self._mode = config.get("display_mode", "sfr1_slim")
        self._build()
        state.register_callback(self._on_state_change)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_mode(self, mode: str):
        """Switch display mode live. 'off' hides the window."""
        self._stop_animations()
        self._mode = mode
        self._config["display_mode"] = mode

        for child in self._win.winfo_children():
            child.destroy()
        self._glass_canvas = self._led_canvas = self._inst_canvas = None
        self._scan_id = self._led_id = self._ticker_id = None
        self._matrix_items = []
        self._recent_texts = []
        for attr in ("_hdr_dot", "_hdr_status", "_slim_mineral", "_slim_mult",
                     "_slim_rarity", "_slim_rarity_bg", "_slim_sig",
                     "_inst_mineral", "_inst_mineral_glow", "_inst_mult",
                     "_inst_rarity", "_inst_sig", "_footer_cursor"):
            if hasattr(self, attr):
                delattr(self, attr)

        self._build()

    # ------------------------------------------------------------------
    # Build – dispatch by mode
    # ------------------------------------------------------------------

    def _build(self):
        dx = self._config.get("display_x", 1030)
        dy = self._config.get("display_y", 1380)

        if self._mode == "off":
            self._win.withdraw()
            return

        if self._mode == "sfr1_slim":
            self._build_slim()
            self._win.geometry(f"{SLIM_W}x{SLIM_H}+{dx}+{dy}")
        else:
            self._build_instrument()
            self._win.geometry(f"{INST_W}x{INST_H}+{dx}+{dy}")

        self._setup_drag()
        self._win.deiconify()
        self._start_animations()
        self._refresh()

    # ------------------------------------------------------------------
    # Model A – Slim
    # ------------------------------------------------------------------

    def _build_slim(self):
        row = tk.Frame(self._win, bg="black")
        row.pack()

        # ── ID block ──────────────────────────────────────────────────
        id_cv = tk.Canvas(row, width=SLIM_ID_W, height=SLIM_H,
                          bg="black", highlightthickness=0)
        id_cv.pack(side="left")
        self._draw_metal_panel(id_cv, 0, 0, SLIM_ID_W, SLIM_H)
        id_cv.create_text(SLIM_ID_W // 2, SLIM_H // 2 - 7,
                          text="VARGO", fill=C_CYAN,
                          font=(FONT, 7, "bold"), anchor="center")
        id_cv.create_text(SLIM_ID_W // 2, SLIM_H // 2 + 7,
                          text="SFR-1", fill=C_GOLD,
                          font=(FONT, 10, "bold"), anchor="center")

        # ── Glass area ────────────────────────────────────────────────
        g_cv = tk.Canvas(row, width=SLIM_GLASS_W, height=SLIM_H,
                         bg="black", highlightthickness=0)
        g_cv.pack(side="left")
        self._glass_canvas = g_cv
        self._draw_glass_base(g_cv, 0, 0, SLIM_GLASS_W, SLIM_H)

        ix = GLASS_INSET
        iy = GLASS_INSET
        iw = SLIM_GLASS_W - GLASS_INSET * 2
        ih = SLIM_H - GLASS_INSET * 2
        cy = iy + ih // 2   # vertical center

        # Sig value
        self._slim_sig = g_cv.create_text(
            ix + 8, cy, text="", fill=C_MUTED,
            font=(FONT, 9), anchor="w")

        # Separator 1
        g_cv.create_line(ix + 52, iy + 4, ix + 52, iy + ih - 4,
                         fill=C_MUTED, width=1)

        # Mineral name
        self._slim_mineral = g_cv.create_text(
            ix + 60, cy, text="NO SIGNAL", fill=C_MUTED,
            font=(FONT, 11, "bold"), anchor="w")

        # Multiplier
        self._slim_mult = g_cv.create_text(
            ix + 214, cy, text="", fill=C_GOLD,
            font=(FONT, 11), anchor="w")

        # Separator 2
        g_cv.create_line(ix + 260, iy + 4, ix + 260, iy + ih - 4,
                         fill=C_MUTED, width=1)

        # Rarity badge
        rx0, rx1 = ix + 267, ix + 327
        self._slim_rarity_bg = g_cv.create_rectangle(
            rx0, cy - 7, rx1, cy + 7,
            fill=C_BEZEL, outline=C_MUTED, width=1)
        self._slim_rarity = g_cv.create_text(
            (rx0 + rx1) // 2, cy, text="",
            fill=C_MUTED, font=(FONT, 8), anchor="center")

        # Ticker (right-anchored, scrolls left)
        self._ticker_start = float(ix + iw - 4)
        self._ticker_x     = self._ticker_start
        self._ticker_y     = float(cy)
        self._ticker_id = g_cv.create_text(
            self._ticker_start, cy, text="",
            fill=C_MUTED, font=(FONT, 8), anchor="e")

        # Scan line (drawn last = on top of content)
        self._scan_min_y = float(iy + 1)
        self._scan_max_y = float(iy + ih - 1)
        self._scan_y     = self._scan_min_y
        self._scan_id = g_cv.create_line(
            ix, iy + 1, ix + iw, iy + 1,
            fill=C_SCAN, width=1)

        # ── LED ──────────────────────────────────────────────────────
        led_cv = tk.Canvas(row, width=SLIM_LED_W, height=SLIM_H,
                           bg="black", highlightthickness=0)
        led_cv.pack(side="left")
        lx, ly = SLIM_LED_W // 2, SLIM_H // 2
        self._led_canvas = led_cv
        self._led_id = led_cv.create_oval(
            lx - 4, ly - 4, lx + 4, ly + 4,
            fill=C_GREEN, outline=C_GREEN)

    # ------------------------------------------------------------------
    # Model C – Instrument
    # ------------------------------------------------------------------

    def _build_instrument(self):
        shell = tk.Canvas(self._win, width=INST_W, height=INST_H,
                          bg="black", highlightthickness=0)
        shell.pack()
        self._inst_canvas = shell
        self._glass_canvas = shell
        self._led_canvas   = shell

        # Shell background + bevel
        shell.create_rectangle(0, 0, INST_W, INST_H,
                               fill=C_SHELL, outline=C_BEVEL_T, width=1)
        shell.create_line(1, INST_H - 1, INST_W - 1, INST_H - 1,
                          fill=C_BEVEL_B, width=1)
        for sx, sy in [(7, 7), (INST_W - 7, 7),
                       (7, INST_H - 7), (INST_W - 7, INST_H - 7)]:
            self._draw_screw(shell, sx, sy)

        p  = INST_PAD
        hw = INST_W - p * 2   # 472

        # ── Header ────────────────────────────────────────────────────
        self._draw_metal_panel(shell, p, p, hw, INST_HDR_H)
        shell.create_text(p + 8, p + INST_HDR_H // 2,
                          text="VARGO", fill=C_TEXT,
                          font=(FONT, 8, "bold"), anchor="w")
        shell.create_text(p + 46, p + INST_HDR_H // 2,
                          text="SFR-1", fill=C_GOLD,
                          font=(FONT, 8, "bold"), anchor="w")

        # AUTO badge (right side of header)
        abx = p + hw - 4
        shell.create_rectangle(abx - 36, p + 4, abx, p + INST_HDR_H - 4,
                               fill=C_BEZEL, outline=C_MUTED, width=1)
        shell.create_text(abx - 18, p + INST_HDR_H // 2,
                          text="AUTO", fill=C_CYAN,
                          font=(FONT, 7), anchor="center")

        # Status LED + label
        dot_x = abx - 56
        dot_y = p + INST_HDR_H // 2
        self._hdr_dot = shell.create_oval(
            dot_x - 4, dot_y - 3, dot_x + 4, dot_y + 3,
            fill=C_GREEN, outline="")
        self._hdr_status = shell.create_text(
            dot_x + 8, dot_y, text="ACTIVE", fill=C_GREEN,
            font=(FONT, 7, "bold"), anchor="w")
        self._led_id = self._hdr_dot

        # ── Body ──────────────────────────────────────────────────────
        by, bh = _BDY_Y, INST_BODY_H

        # Matrix panel
        self._draw_metal_panel(shell, p, by, INST_MAT_W, bh)
        self._matrix_items = []
        dot_area_w = MAT_COLS * (MAT_DOT + MAT_GAP) - MAT_GAP   # 41
        dot_area_h = MAT_ROWS * (MAT_DOT + MAT_GAP) - MAT_GAP   # 32
        mat_x0 = p + (INST_MAT_W - dot_area_w) // 2             # 9
        mat_y0 = by + (bh - dot_area_h) // 2                    # 49
        for row in range(MAT_ROWS):
            for col in range(MAT_COLS):
                dx = mat_x0 + col * (MAT_DOT + MAT_GAP)
                dy = mat_y0 + row * (MAT_DOT + MAT_GAP)
                phase  = (row * MAT_COLS + col) / (MAT_ROWS * MAT_COLS)
                is_gold = (row + col) % 3 == 0
                item = shell.create_rectangle(
                    dx, dy, dx + MAT_DOT, dy + MAT_DOT,
                    fill=C_MUTED, outline="")
                self._matrix_items.append((item, phase, is_gold))

        # Glass
        gx, gy = _GLS_X, by
        self._draw_glass_base(shell, gx, gy, INST_GLS_W, bh)
        ix = gx + GLASS_INSET
        iy = gy + GLASS_INSET
        iw = INST_GLS_W - GLASS_INSET * 2
        ih = bh - GLASS_INSET * 2   # 62

        # Mineral name with glow (offset copies drawn first)
        self._inst_mineral_glow = []
        for ddx, ddy in [(-1,-1),(1,-1),(-1,1),(1,1),(0,-1),(0,1),(-1,0),(1,0)]:
            gid = shell.create_text(
                ix + 8 + ddx, iy + 15 + ddy, text="",
                fill="#1a5050", font=(FONT, 14, "bold"), anchor="w")
            self._inst_mineral_glow.append(gid)
        self._inst_mineral = shell.create_text(
            ix + 8, iy + 15, text="NO SIGNAL", fill=C_MUTED,
            font=(FONT, 14, "bold"), anchor="w")
        self._inst_mult = shell.create_text(
            ix + 8, iy + 35, text="", fill=C_GOLD,
            font=(FONT, 11), anchor="w")
        self._inst_rarity = shell.create_text(
            ix + 8, iy + 48, text="", fill=C_MUTED,
            font=(FONT, 8), anchor="w")
        self._inst_sig = shell.create_text(
            ix + 8, iy + ih - 4, text="", fill=C_MUTED,
            font=(FONT, 8), anchor="w")

        # Scan line (on top of glass content)
        self._scan_min_y = float(iy + 1)
        self._scan_max_y = float(iy + ih - 1)
        self._scan_y     = self._scan_min_y
        self._scan_id = shell.create_line(
            gx, iy + 1, gx + INST_GLS_W, iy + 1,
            fill=C_SCAN, width=1)

        # Recent log
        rx = _REC_X
        self._draw_metal_panel(shell, rx, by, INST_REC_W - 2, bh)
        shell.create_text(rx + (INST_REC_W - 2) // 2, by + 7,
                          text="RECENT", fill=C_MUTED,
                          font=(FONT, 6, "bold"), anchor="center")
        self._recent_texts = []
        for i in range(4):
            tid = shell.create_text(
                rx + 4, by + 18 + i * 13, text="",
                fill=C_MUTED, font=(FONT, 7), anchor="w")
            self._recent_texts.append(tid)

        # ── Footer ────────────────────────────────────────────────────
        self._draw_metal_panel(shell, p, _FTR_Y, hw, INST_FTR_H)
        shell.create_text(p + 8, _FTR_Y + INST_FTR_H // 2,
                          text="SCAN · PAUSE · LOG",
                          fill=C_MUTED, font=(FONT, 6), anchor="w")
        shell.create_text(p + hw - 32, _FTR_Y + INST_FTR_H // 2,
                          text="v1.1", fill=C_MUTED,
                          font=(FONT, 6), anchor="w")
        self._footer_cursor = shell.create_text(
            p + hw - 8, _FTR_Y + INST_FTR_H // 2, text="▮",
            fill=C_MUTED, font=(FONT, 6), anchor="e")

    # ------------------------------------------------------------------
    # Shared drawing primitives
    # ------------------------------------------------------------------

    def _draw_glass_base(self, cv: tk.Canvas, x, y, w, h):
        """Draw the layered glass effect on an existing canvas."""
        ix = x + GLASS_INSET
        iy = y + GLASS_INSET
        iw = w - GLASS_INSET * 2
        ih = h - GLASS_INSET * 2

        cv.create_rectangle(x, y, x + w, y + h, fill=C_BEZEL, outline="")
        cv.create_rectangle(ix, iy, ix + iw, iy + ih, fill=C_SURFACE, outline="")
        # Top-edge shine
        cv.create_line(ix + 2, iy, ix + iw - 2, iy,
                       fill=C_SHINE, width=1)
        # Inset shadow – top edge
        cv.create_rectangle(ix, iy, ix + iw, iy + 3,
                             fill=C_SHADOW, outline="")
        # Inset shadow – left edge
        cv.create_rectangle(ix, iy, ix + 3, iy + ih,
                             fill=C_SHADOW, outline="")
        # Diagonal reflection (subtle, drawn before text so text reads through it)
        pts = [ix, iy,
               ix + int(iw * 0.55), iy,
               ix, iy + int(ih * 0.50)]
        cv.create_polygon(pts, fill=C_REFLECT, outline="")

    def _draw_metal_panel(self, cv: tk.Canvas, x, y, w, h):
        """Dark metal panel with subtle alternating horizontal bands."""
        cv.create_rectangle(x, y, x + w, y + h,
                             fill=C_BEZEL, outline=C_BORDER, width=1)
        band = 4
        for i in range(0, h, band * 2):
            yy = y + i
            if yy + band > y + h:
                break
            cv.create_rectangle(x + 1, yy, x + w - 1, yy + band,
                                 fill="#0c0e16", outline="")

    def _draw_screw(self, cv: tk.Canvas, cx, cy, radius=3):
        r = radius
        cv.create_oval(cx - r, cy - r, cx + r, cy + r,
                       fill="#0d0f1a", outline="#2a3a4a", width=1)
        cv.create_oval(cx - r + 1, cy - r + 1, cx + 1, cy + 1,
                       fill="#253545", outline="")

    # ------------------------------------------------------------------
    # Drag-to-move
    # ------------------------------------------------------------------

    def _all_widgets(self):
        """Return self._win and all descendant widgets (recursive)."""
        result = [self._win]
        def _collect(w):
            for child in w.winfo_children():
                result.append(child)
                _collect(child)
        _collect(self._win)
        return result

    def _setup_drag(self):
        for widget in self._all_widgets():
            widget.bind("<ButtonPress-1>",   self._drag_start,  add="+")
            widget.bind("<B1-Motion>",       self._drag_motion, add="+")
            widget.bind("<ButtonRelease-1>", self._drag_end,    add="+")

    def _drag_start(self, event):
        self._drag_x = event.x_root - self._win.winfo_x()
        self._drag_y = event.y_root - self._win.winfo_y()

    def _drag_motion(self, event):
        self._win.geometry(
            f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _drag_end(self, event):
        self._config["display_x"] = self._win.winfo_x()
        self._config["display_y"] = self._win.winfo_y()
        self._state._save_config()

    # ------------------------------------------------------------------
    # Animation control
    # ------------------------------------------------------------------

    def _start_animations(self):
        self._anim_active = True
        self._scan_y = self._scan_min_y
        self._animate_scan()
        self._animate_led()
        self._animate_flicker()
        if self._mode == "sfr1_slim":
            self._ticker_x = self._ticker_start
            self._animate_ticker()
        if self._mode == "sfr1_instrument":
            self._matrix_t = 0.0
            self._animate_matrix()
            self._animate_cursor()

    def _stop_animations(self):
        self._anim_active = False

    # ------------------------------------------------------------------
    # Animation loops
    # ------------------------------------------------------------------

    def _animate_scan(self):
        if not self._anim_active or self._scan_id is None:
            return
        step = (self._scan_max_y - self._scan_min_y) / (SCAN_PERIOD / SCAN_TICK)
        self._scan_y += step
        if self._scan_y > self._scan_max_y:
            self._scan_y = self._scan_min_y
        try:
            c = self._glass_canvas.coords(self._scan_id)
            if c:
                self._glass_canvas.coords(
                    self._scan_id, c[0], self._scan_y, c[2], self._scan_y)
        except tk.TclError:
            return
        self._root.after(SCAN_TICK, self._animate_scan)

    def _animate_led(self):
        if not self._anim_active or self._led_id is None:
            return
        self._led_state = not self._led_state
        try:
            paused    = self._state.paused
            dot_color = (C_RED if paused
                         else (C_GREEN if self._led_state else C_GREEN_D))
            self._led_canvas.itemconfig(self._led_id, fill=dot_color)
            if hasattr(self, "_hdr_status"):
                fg   = C_RED if paused else C_GREEN
                text = "PAUSED" if paused else "ACTIVE"
                self._led_canvas.itemconfig(self._hdr_status,
                                            text=text, fill=fg)
        except tk.TclError:
            return
        self._root.after(LED_HALF, self._animate_led)

    def _animate_flicker(self):
        if not self._anim_active or self._scan_id is None:
            return
        try:
            self._glass_canvas.itemconfig(self._scan_id, fill=C_MUTED)
            self._root.after(60, self._flicker_restore)
        except tk.TclError:
            return
        self._root.after(random.randint(4000, 12000), self._animate_flicker)

    def _flicker_restore(self):
        if not self._anim_active or self._scan_id is None:
            return
        try:
            self._glass_canvas.itemconfig(self._scan_id, fill=C_SCAN)
        except tk.TclError:
            pass

    def _animate_ticker(self):
        if not self._anim_active or self._ticker_id is None:
            return
        step = (SLIM_GLASS_W * 1.5) / (TICKER_CYCLE / SCAN_TICK)
        self._ticker_x -= step
        if self._ticker_x < -SLIM_GLASS_W:
            self._ticker_x = self._ticker_start
        try:
            self._glass_canvas.coords(
                self._ticker_id, self._ticker_x, self._ticker_y)
        except tk.TclError:
            return
        self._root.after(SCAN_TICK, self._animate_ticker)

    def _animate_matrix(self):
        if not self._anim_active or not self._matrix_items:
            return
        self._matrix_t = (self._matrix_t + MAT_TICK / 2000.0) % 1.0
        try:
            for item, phase, is_gold in self._matrix_items:
                t = (self._matrix_t + phase) % 1.0
                b = 0.5 + 0.5 * math.sin(2 * math.pi * t)
                color = (_lerp_color("#1a1508", C_GOLD, b) if is_gold
                         else _lerp_color("#061010", C_CYAN, b))
                self._inst_canvas.itemconfig(item, fill=color)
        except tk.TclError:
            return
        self._root.after(MAT_TICK, self._animate_matrix)

    def _animate_cursor(self):
        if not self._anim_active or not hasattr(self, "_footer_cursor"):
            return
        try:
            cur = self._inst_canvas.itemcget(self._footer_cursor, "fill")
            self._inst_canvas.itemconfig(
                self._footer_cursor,
                fill=C_BEZEL if cur == C_MUTED else C_MUTED)
        except tk.TclError:
            return
        self._root.after(800, self._animate_cursor)

    # ------------------------------------------------------------------
    # State sync
    # ------------------------------------------------------------------

    def _on_state_change(self):
        self._root.after(0, self._refresh)

    def _refresh(self):
        if self._mode == "off":
            return
        parts  = _parse_signal(self._state.last_signal)
        recent = self._state.recent_signals
        if self._mode == "sfr1_slim":
            self._refresh_slim(parts, recent)
        else:
            self._refresh_instrument(parts, recent)

    def _refresh_slim(self, parts, recent):
        cv = self._glass_canvas
        if cv is None:
            return
        try:
            if parts:
                mineral, mult, rarity = parts
                cv.itemconfig(self._slim_mineral,
                              text=mineral[:18], fill=C_CYAN)
                cv.itemconfig(self._slim_mult,   text=mult,      fill=C_GOLD)
                cv.itemconfig(self._slim_rarity, text=rarity[:9], fill=C_TEXT)
                cv.itemconfig(self._slim_sig,    text="")
                ticker = "  ·  ".join(s[:20] for s in recent if s)
                cv.itemconfig(self._ticker_id,   text=ticker, fill=C_MUTED)
            else:
                cv.itemconfig(self._slim_mineral,
                              text="NO SIGNAL", fill=C_MUTED)
                cv.itemconfig(self._slim_mult,    text="")
                cv.itemconfig(self._slim_rarity,  text="")
                cv.itemconfig(self._slim_sig,     text="")
                cv.itemconfig(self._ticker_id,    text="")
        except tk.TclError:
            pass

    def _refresh_instrument(self, parts, recent):
        cv = self._inst_canvas
        if cv is None:
            return
        try:
            if parts:
                mineral, mult, rarity = parts
                for gid in self._inst_mineral_glow:
                    cv.itemconfig(gid, text=mineral[:22], fill="#1a5050")
                cv.itemconfig(self._inst_mineral,
                              text=mineral[:22], fill=C_CYAN)
                cv.itemconfig(self._inst_mult,   text=mult,    fill=C_GOLD)
                cv.itemconfig(self._inst_rarity, text=rarity,  fill=C_MUTED)
                cv.itemconfig(self._inst_sig,    text="")
            else:
                for gid in self._inst_mineral_glow:
                    cv.itemconfig(gid, text="")
                cv.itemconfig(self._inst_mineral,
                              text="NO SIGNAL", fill=C_MUTED)
                cv.itemconfig(self._inst_mult,    text="")
                cv.itemconfig(self._inst_rarity,  text="")
                cv.itemconfig(self._inst_sig,     text="")

            for i, tid in enumerate(self._recent_texts):
                text = recent[i][:14] if i < len(recent) else ""
                cv.itemconfig(tid, text=text)
        except tk.TclError:
            pass
