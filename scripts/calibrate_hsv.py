"""
calibrate_hsv.py  –  SC Signature Reader / Vargo Dynamics
Click on a signature number in a screenshot to get the exact
HSV values for that HUD colour.

Usage:
    python calibrate_hsv.py
    python calibrate_hsv.py path/to/screenshot.png

Without an argument: captures the current screen (scan_region from config.json).
With a PNG argument:  opens that file directly.

Click on any pixel of the signature number text.
The script prints the HSV value and suggested hsv_low / hsv_high
range (+/- 10 on H, full S and V range).

Press Q or Escape to quit.
"""

import sys
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


BASE_DIR    = _base_dir()
CONFIG_PATH = BASE_DIR / "config.json"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("[ERROR] opencv-python is required: pip install opencv-python")
        sys.exit(1)

    config = _load_config()

    # --- Load or capture image ---
    if len(sys.argv) > 1:
        img_path = Path(sys.argv[1])
        if not img_path.exists():
            print(f"[ERROR] File not found: {img_path}")
            sys.exit(1)
        bgr = cv2.imread(str(img_path))
        if bgr is None:
            print(f"[ERROR] Could not read image: {img_path}")
            sys.exit(1)
        source = str(img_path)
    else:
        try:
            import mss
            import numpy as np
            region = config.get("scan_region") or config.get("roi", {
                "top": 0, "left": 0, "width": 1920, "height": 1080
            })
            print(f"Capturing screen region: {region}")
            with mss.mss() as sct:
                raw = sct.grab(region)
                img = np.frombuffer(raw.bgra, dtype=np.uint8)
                img = img.reshape((raw.height, raw.width, 4))
                bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            source = "live screen capture"
        except ImportError:
            print("[ERROR] mss is required for live capture: pip install mss")
            sys.exit(1)

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    print(f"\nSource: {source}")
    print("Click on a signature number pixel.")
    print("Press Q or Escape to quit.\n")

    results = []

    def on_click(event, x, y, flags, _):
        if event != cv2.EVENT_LBUTTONDOWN:
            return

        h, s, v = hsv[y, x]
        b, g, r  = bgr[y, x]

        h_low  = max(0,   int(h) - 10)
        h_high = min(179, int(h) + 10)

        print(f"Pixel ({x}, {y})")
        print(f"  BGR : B={b}  G={g}  R={r}")
        print(f"  HSV : H={h}  S={s}  V={v}")
        print(f"  → Suggested config values:")
        print(f'    "hsv_low":  [{h_low}, {max(0, int(s)-40)}, {max(0, int(v)-40)}]')
        print(f'    "hsv_high": [{h_high}, 255, 255]')
        print()

        results.append({
            "pixel": (x, y),
            "bgr":   (int(b), int(g), int(r)),
            "hsv":   (int(h), int(s), int(v)),
            "hsv_low":  [h_low,  max(0, int(s)-40), max(0, int(v)-40)],
            "hsv_high": [h_high, 255, 255],
        })

        # Draw a small crosshair on the image
        cv2.drawMarker(bgr, (x, y), (0, 255, 0),
                       cv2.MARKER_CROSS, 12, 1)
        cv2.imshow("SC Signature Reader – HSV Calibration", bgr)

    # Scale down large images for display
    h_img, w_img = bgr.shape[:2]
    scale = min(1.0, 1400 / w_img, 900 / h_img)
    display = cv2.resize(bgr, (int(w_img * scale), int(h_img * scale))) \
              if scale < 1.0 else bgr.copy()

    window_name = "SC Signature Reader – HSV Calibration"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.imshow(window_name, display)

    # Remap click coords if image was scaled
    def on_click_scaled(event, x, y, flags, param):
        if scale < 1.0:
            x = int(x / scale)
            y = int(y / scale)
        on_click(event, x, y, flags, param)

    cv2.setMouseCallback(window_name, on_click_scaled)

    print("Window open – click any signature number pixel.")
    print("Multiple clicks are fine – average the H values if they differ.\n")

    while True:
        key = cv2.waitKey(50) & 0xFF
        if key in (ord("q"), ord("Q"), 27):  # Q or Escape
            break
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            break

    cv2.destroyAllWindows()

    # --- Summary ---
    if results:
        print("─" * 50)
        print(f"Clicks recorded: {len(results)}")
        if len(results) > 1:
            avg_h = int(sum(r["hsv"][0] for r in results) / len(results))
            avg_s = int(sum(r["hsv"][1] for r in results) / len(results))
            avg_v = int(sum(r["hsv"][2] for r in results) / len(results))
            h_low  = max(0,   avg_h - 12)
            h_high = min(179, avg_h + 12)
            print(f"Average HSV: H={avg_h}  S={avg_s}  V={avg_v}")
            print(f"\nRecommended config (averaged over {len(results)} clicks):")
            print(f'  "hsv_low":  [{h_low}, {max(0, avg_s-50)}, {max(0, avg_v-50)}]')
            print(f'  "hsv_high": [{h_high}, 255, 255]')
        print("─" * 50)
    else:
        print("No pixels clicked.")


if __name__ == "__main__":
    main()
