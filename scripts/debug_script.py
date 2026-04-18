# debug_screenshots.py
# Teste die Farberkennung direkt auf deinen SC-Screenshots
import cv2, numpy as np
from pathlib import Path

HSV_LOW  = np.array([5,  80,  80], dtype=np.uint8)
HSV_HIGH = np.array([35, 255, 255], dtype=np.uint8)
MIN_AREA = 80

screenshot_dir = Path(r"E:\SW_Projekte\SC_Signature_Reader\screenshots")  # Pfad anpassen

for img_path in sorted(screenshot_dir.glob("ScreenShot*.jpg"))[:7]:
    bgr = cv2.imread(str(img_path))
    if bgr is None:
        continue

    h_img, w_img = bgr.shape[:2]

    # Nur mittlerer Bereich (wo die Signatur sitzt)
    x1, y1 = int(w_img * 0.35), int(h_img * 0.22)
    x2, y2 = int(w_img * 0.65), int(h_img * 0.40)
    roi = bgr[y1:y2, x1:x2]

    hsv  = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, HSV_LOW, HSV_HIGH)

    kernel   = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask     = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    print(f"\n{img_path.name}  ({w_img}x{h_img})")
    found = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < MIN_AREA:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = w / max(1, h)
        print(f"  Region: x={x+x1} y={y+y1} w={w} h={h}  area={area:.0f}  aspect={aspect:.1f}")
        found += 1

    if found == 0:
        print("  → Keine Regionen gefunden!")

        # HSV-Wert direkt am Bildmittelpunkt ausgeben zur Diagnose
        cy, cx = (y2-y1)//2, (x2-x1)//2
        h_val, s_val, v_val = hsv[cy, cx]
        print(f"  → HSV Bildmitte: H={h_val} S={s_val} V={v_val}")