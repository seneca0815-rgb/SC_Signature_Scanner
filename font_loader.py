"""
font_loader.py  --  SC Signature Reader / Vargo Dynamics
Loads VargoMono-Regular.ttf into the Windows GDI font table so tkinter
can use it by name without a system-wide installation.

Call load_vargo_font() once before creating any tk.Tk() window.
Returns the resolved font-family name to use in tkinter font tuples.
"""

import sys
from pathlib import Path


_FONT_FAMILY = "VargoMono"
_FALLBACK    = "Consolas"


def _find_font_file() -> Path | None:
    """Locate VargoMono-Regular.ttf in both dev and frozen-exe environments."""
    candidates = [
        # Frozen exe: font bundled next to the executable
        Path(getattr(sys, "_MEIPASS", "")) / "fonts" / "VargoMono-Regular.ttf",
        # Development: relative to this source file
        Path(__file__).parent / "fonts" / "VargoMono" / "VargoMono-Regular.ttf",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def load_vargo_font() -> str:
    """Load VargoMono into GDI and return the font-family name for tkinter.

    On non-Windows or if the font file is missing, returns the Consolas fallback.
    Safe to call multiple times — GDI ignores duplicate loads.
    """
    if sys.platform != "win32":
        return _FALLBACK

    font_path = _find_font_file()
    if font_path is None:
        return _FALLBACK

    try:
        import ctypes
        # FR_PRIVATE (0x10): font is unloaded when the process exits
        result = ctypes.windll.gdi32.AddFontResourceExW(str(font_path), 0x10, 0)
        if result > 0:
            return _FONT_FAMILY
    except Exception:
        pass

    return _FALLBACK
