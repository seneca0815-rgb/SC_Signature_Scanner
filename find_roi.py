# find_roi.py  – Mausposition live anzeigen (kein extra Package nötig)
import time
import ctypes
import ctypes.wintypes

_user32 = ctypes.windll.user32

def _get_cursor_pos():
    pt = ctypes.wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

print("Maus über den Signatur-Text bewegen. Ctrl+C zum Beenden.")
try:
    while True:
        x, y = _get_cursor_pos()
        print(f"\r  x={x:<6} y={y:<6}", end="", flush=True)
        time.sleep(0.1)
except KeyboardInterrupt:
    pass