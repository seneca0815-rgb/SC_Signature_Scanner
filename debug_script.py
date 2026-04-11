# test_preprocess.py – zeigt wie Tesseract das Bild wirklich sieht
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import PIL.ImageChops as chops
import pytesseract, mss

ROI = {"top": 492, "left": 1270, "width": 35, "height": 18}

with mss.mss() as sct:
    raw = sct.grab(ROI)
    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

img.save("1_original.png")

# Preprocessing durchlaufen lassen
w, h = img.size
img = img.resize((w * 4, h * 4), Image.LANCZOS)
r, g, b = img.split()
orange = chops.add(r, g)
orange = chops.subtract(orange, b)
orange = ImageEnhance.Contrast(orange).enhance(3.0)
orange = orange.point(lambda p: 255 if p > 100 else 0)
orange = ImageOps.invert(orange)
orange = orange.filter(ImageFilter.SHARPEN)

orange.save("2_preprocessed.png")  # <-- so sieht Tesseract das Bild

text = pytesseract.image_to_string(
    orange,
    config=r"--psm 7 -c tessedit_char_whitelist=0123456789"
)
print(f"Erkannt: {text.strip()!r}")