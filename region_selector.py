"""
region_selector.py  –  SC Signature Reader / Vargo Dynamics
Full-screen interactive picker for the OCR scan region.

Usage (from main thread only):
    from region_selector import open_region_selector
    region = open_region_selector(root, current_region=config.get("scan_region"))
    # region → {"top": y, "left": x, "width": w, "height": h}  or  None if cancelled
"""

import tkinter as tk
from typing import Optional

C_CYAN   = "#4fc3c3"
C_GOLD   = "#c9a84c"
C_BG     = "#000011"
C_RED    = "#c94f4f"


def open_region_selector(
    root: tk.Tk,
    current_region: Optional[dict] = None,
) -> Optional[dict]:
    """
    Opens a full-screen semi-transparent overlay; user drags a rectangle.
    Blocks the tkinter main loop until the user confirms or cancels.

    Returns {"top", "left", "width", "height"} on confirmation,
    or None if the user pressed ESC or drew a region smaller than 20×20 px.
    """
    result: list[Optional[dict]] = [None]
    done = tk.BooleanVar(value=False)

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.40)

    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{sw}x{sh}+0+0")
    win.configure(bg=C_BG)

    canvas = tk.Canvas(
        win,
        bg=C_BG,
        highlightthickness=0,
        width=sw,
        height=sh,
        cursor="crosshair",
    )
    canvas.pack(fill="both", expand=True)

    # ── Static UI labels ────────────────────────────────────────────────────
    canvas.create_text(
        sw // 2, 32,
        text="Drag to select scan region  ·  ESC to cancel",
        fill=C_CYAN,
        font=("Courier New", 14, "bold"),
        anchor="center",
    )
    info_id = canvas.create_text(
        sw // 2, 60,
        text="",
        fill=C_GOLD,
        font=("Courier New", 12),
        anchor="center",
    )

    # ── Current region indicator ────────────────────────────────────────────
    if current_region:
        cx = current_region.get("left", 0)
        cy = current_region.get("top", 0)
        cw = current_region.get("width", 0)
        ch = current_region.get("height", 0)
        if cw > 0 and ch > 0:
            canvas.create_rectangle(
                cx, cy, cx + cw, cy + ch,
                outline=C_GOLD, width=1, dash=(6, 4),
            )
            canvas.create_text(
                cx + cw // 2, cy + ch // 2,
                text=f"current  {cw} × {ch}",
                fill=C_GOLD,
                font=("Courier New", 10),
                anchor="center",
            )

    # ── Drag state ──────────────────────────────────────────────────────────
    _state: dict = {"start": None, "rect_id": None}

    def _on_press(ev: tk.Event) -> None:
        _state["start"] = (ev.x, ev.y)
        if _state["rect_id"] is not None:
            canvas.delete(_state["rect_id"])
            _state["rect_id"] = None
        canvas.itemconfig(info_id, text="")

    def _on_drag(ev: tk.Event) -> None:
        if _state["start"] is None:
            return
        x0, y0 = _state["start"]
        x1, y1 = ev.x, ev.y
        if _state["rect_id"] is not None:
            canvas.delete(_state["rect_id"])
        _state["rect_id"] = canvas.create_rectangle(
            x0, y0, x1, y1,
            outline=C_CYAN, width=2,
            fill=C_CYAN, stipple="gray12",
        )
        w = abs(x1 - x0)
        h = abs(y1 - y0)
        left = min(x0, x1)
        top  = min(y0, y1)
        canvas.itemconfig(
            info_id,
            text=f"left={left}  top={top}  {w} × {h} px",
        )

    def _on_release(ev: tk.Event) -> None:
        if _state["start"] is None:
            return
        x0, y0 = _state["start"]
        x1, y1 = ev.x, ev.y
        left   = min(x0, x1)
        top    = min(y0, y1)
        width  = abs(x1 - x0)
        height = abs(y1 - y0)
        if width > 20 and height > 20:
            result[0] = {
                "top":    top,
                "left":   left,
                "width":  width,
                "height": height,
            }
        done.set(True)

    def _on_cancel(_ev: tk.Event = None) -> None:
        done.set(True)

    canvas.bind("<ButtonPress-1>",   _on_press)
    canvas.bind("<B1-Motion>",       _on_drag)
    canvas.bind("<ButtonRelease-1>", _on_release)
    win.bind("<Escape>", _on_cancel)
    win.focus_force()

    root.wait_variable(done)

    try:
        win.destroy()
    except tk.TclError:
        pass

    return result[0]
