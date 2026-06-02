# find_roi.py  – display live mouse position (no extra package required)
import time
import ctypes
import ctypes.wintypes

_user32 = ctypes.windll.user32

def _get_cursor_pos():
    pt = ctypes.wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

print("Move the mouse over the signature text. Ctrl+C to quit.")
try:
    while True:
        x, y = _get_cursor_pos()
        print(f"\r  x={x:<6} y={y:<6}", end="", flush=True)
        time.sleep(0.1)
except KeyboardInterrupt:
    pass