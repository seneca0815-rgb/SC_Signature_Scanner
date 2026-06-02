"""Inspect glyph metrics — run via: fontforge -script ff_inspect_glyphs.py"""
import fontforge, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
font = fontforge.open(str(ROOT / "fonts/VargoMono/ShareTechMono-Regular.ttf"))
print(f"em={font.em}  ascent={font.ascent}  descent={font.descent}")
print(f"advance_width of '0' = {font[0x30].width}")
for cp, name in [(0x30,'0'),(0x31,'1'),(0x37,'7'),(0x56,'V'),(0x41,'A'),(0xB7,'middot')]:
    g  = font[cp]
    bb = g.boundingBox()  # xmin,ymin,xmax,ymax
    print(f"U+{cp:04X} {name:8s}  bb=({bb[0]:.0f},{bb[1]:.0f},{bb[2]:.0f},{bb[3]:.0f})"
          f"  w={bb[2]-bb[0]:.0f}  h={bb[3]-bb[1]:.0f}  adv={g.width}")
font.close()
