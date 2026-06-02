"""
build_vargo_font_ft.py  --  VargoMono font build (fonttools version)

Applies metadata and exports VargoMono-Regular.ttf using fonttools.
Does NOT require FontForge.  Glyph shape edits must be done separately
in FontForge or another font editor before running this script.

Usage:
    python scripts/build_vargo_font_ft.py
"""

import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._n_a_m_e import NameRecord

SCRIPT_DIR   = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
FONTS_DIR    = PROJECT_ROOT / "fonts" / "VargoMono"

SOURCE_TTF = FONTS_DIR / "ShareTechMono-Regular-edited.ttf"
OUTPUT_TTF = FONTS_DIR / "VargoMono-Regular.ttf"

# ---------------------------------------------------------------------------
# Name table IDs (OpenType spec)
# ---------------------------------------------------------------------------
# fmt: off
NAME_COPYRIGHT   = 0
NAME_FAMILY      = 1
NAME_SUBFAMILY   = 2
NAME_UNIQUE_ID   = 3
NAME_FULLNAME    = 4
NAME_VERSION     = 5
NAME_POSTSCRIPT  = 6
NAME_TRADEMARK   = 7
NAME_MANUFACTURER= 8
NAME_DESIGNER    = 9
NAME_DESCRIPTION = 10
NAME_LICENSE     = 13
NAME_LICENSE_URL = 14
NAME_PREF_FAMILY = 16
# fmt: on

META = {
    NAME_COPYRIGHT:   (
        "Original: Copyright 2013 Patrick Wagesreiter & Carrois Corporate GbR. "
        "Modifications: Vargo Dynamics (SC Signature Reader project). "
        "Licensed under SIL OFL 1.1."
    ),
    NAME_FAMILY:      "VargoMono",
    NAME_SUBFAMILY:   "Regular",
    NAME_UNIQUE_ID:   "VargoMono Regular; 1.000",
    NAME_FULLNAME:    "VargoMono Regular",
    NAME_VERSION:     "Version 1.000",
    NAME_POSTSCRIPT:  "VargoMono-Regular",
    NAME_DESIGNER:    "Vargo Dynamics",
    NAME_DESCRIPTION: (
        "VargoMono is a modified derivative of Share Tech Mono, "
        "customised for the Vargo Dynamics SC Signature Reader overlay. "
        "Modifications include slashed zero, crossbar seven, seriffed one, "
        "angular brand letters (V, A, M, W) and stencil-cut punctuation."
    ),
    NAME_LICENSE:     "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
    NAME_LICENSE_URL: "https://openfontlicense.org",
    NAME_PREF_FAMILY: "VargoMono",
}


def set_name(name_table, name_id: int, value: str,
             platform_id: int = 3, plat_enc_id: int = 1, lang_id: int = 0x0409):
    name_table.setName(value, name_id, platform_id, plat_enc_id, lang_id)


def apply_metadata(font: TTFont) -> None:
    name_table = font["name"]

    # Remove all existing name records for the IDs we're replacing
    for name_id in META:
        name_table.removeNames(nameID=name_id)

    # Write new values (Windows Unicode BMP, English US)
    for name_id, value in META.items():
        set_name(name_table, name_id, value)

    # Also write Mac Roman variants for broader compatibility
    for name_id, value in META.items():
        set_name(name_table, name_id, value,
                 platform_id=1, plat_enc_id=0, lang_id=0)

    # Update OS/2 and head table family name
    if "OS/2" in font:
        pass  # subfamily handled via name table

    print("  Metadata applied:")
    for name_id, value in META.items():
        short = value[:60] + "..." if len(value) > 60 else value
        print(f"    [{name_id:2d}] {short}")


def verify_glyphs(font: TTFont) -> None:
    cmap = font.getBestCmap()
    priorities = [
        (0x0030, "0  (zero)     — should have diagonal slash"),
        (0x0031, "1  (one)      — should have serif base"),
        (0x0037, "7  (seven)    — should have crossbar"),
        (0x0056, "V  (brand)    — should have tick terminals"),
        (0x0041, "A             — should have stencil crossbar"),
        (0x00B7, "middle dot    — should be square/diamond"),
    ]
    print("\n  Priority glyph presence check:")
    for codepoint, description in priorities:
        glyph_name = cmap.get(codepoint, "MISSING")
        status = "OK" if glyph_name != "MISSING" else "MISSING"
        print(f"    [{status}] U+{codepoint:04X}  {description}  -> {glyph_name}")
    print("  (Shape edits must be verified visually in a font viewer)")


def main():
    sep = "=" * 60
    print(sep)
    print("VargoMono font build  (fonttools)")
    print(sep)

    if not SOURCE_TTF.exists():
        print(f"\nERROR: Base font not found: {SOURCE_TTF}")
        print("\nDownload Share Tech Mono and save as:")
        print(f"  {SOURCE_TTF}")
        sys.exit(1)

    print(f"\nSource : {SOURCE_TTF}")
    print(f"Output : {OUTPUT_TTF}")

    print("\n[1] Loading font...")
    font = TTFont(str(SOURCE_TTF))
    print(f"  Tables: {', '.join(sorted(font.keys()))}")

    print("\n[2] Applying metadata...")
    apply_metadata(font)

    print("\n[3] Glyph verification...")
    verify_glyphs(font)

    print("\n[4] Saving...")
    OUTPUT_TTF.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(OUTPUT_TTF))
    size_kb = OUTPUT_TTF.stat().st_size // 1024
    print(f"  Saved: {OUTPUT_TTF.name}  ({size_kb} KB)")

    print(f"\n{sep}")
    print("Build complete.")
    print("Next: open VargoMono-Regular.ttf in a font viewer to verify")
    print("the glyph shape edits from fonts/VargoMono/glyph-spec.md.")
    print(sep)


if __name__ == "__main__":
    main()
