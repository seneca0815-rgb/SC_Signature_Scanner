# find_roi.py  – Mausposition live anzeigen
import time
import pyautogui  # pip install pyautogui

print("Maus über den Signatur-Text bewegen. Ctrl+C zum Beenden.")
try:
    while True:
        x, y = pyautogui.position()
        print(f"\r  x={x:<6} y={y:<6}", end="", flush=True)
        time.sleep(0.1)
except KeyboardInterrupt:
    pass