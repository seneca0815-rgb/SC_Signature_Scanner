"""
save_test_fixture.py  –  SC Signature Reader
Captures the current screen via mss and saves it as a lossless PNG
to test_fixtures/ for use as OCR regression fixtures.

Usage (run in-game when a signature is visible):
    python save_test_fixture.py

The saved PNG is then imported with:
    python import_screenshots.py test_fixtures/
"""

from datetime import datetime
from pathlib import Path

import mss
import mss.tools

FIXTURES_DIR = Path(__file__).parent / "test_fixtures"


def main():
    FIXTURES_DIR.mkdir(exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = FIXTURES_DIR / f"capture_{ts}.png"

    with mss.mss() as sct:
        monitor = sct.monitors[1]          # primary monitor
        shot = sct.grab(monitor)
        mss.tools.to_png(shot.rgb, shot.size, output=str(out_path))

    print(f"Saved: {out_path}  ({shot.width}x{shot.height})")


if __name__ == "__main__":
    main()
