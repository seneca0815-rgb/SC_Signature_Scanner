# test_ocr.py
import mss, pytesseract
from PIL import Image

ROI = {"top": 542, "left": 1250, "width": 60, "height": 20}  # deine Werte

with mss.mss() as sct:
    raw = sct.grab(ROI)
    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

img.save("debug_roi.png")  # Screenshot speichern zum Nachschauen
text = pytesseract.image_to_string(img)
print(f"Erkannt: {text!r}")