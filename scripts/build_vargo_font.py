"""
build_vargo_font.py  --  VargoMono font build script

Applies metadata and post-processing to a Share Tech Mono derivative
after all glyph edits have been done manually in FontForge.

Usage (run from FontForge's script interface or CLI):
    fontforge -script scripts/build_vargo_font.py

Requires FontForge with Python scripting support.
Download: https://fontforge.org/en-US/downloads/
"""

import os
import sys
from pathlib import Path

try:
    import fontforge
except ImportError:
    print("ERROR: This script must be run via FontForge's Python interpreter.")
    print("  fontforge -script scripts/build_vargo_font.py")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR   = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
FONTS_DIR    = PROJECT_ROOT / "fonts" / "VargoMono"

SOURCE_TTF = FONTS_DIR / "ShareTechMono-Regular.ttf"   # base font (download separately)
OUTPUT_TTF = FONTS_DIR / "VargoMono-Regular.ttf"

# ---------------------------------------------------------------------------
# Font metadata
# SIL OFL 1.1 requires renaming the font when distributing modifications.
# ---------------------------------------------------------------------------

META = {
    "fontname":     "VargoMono-Regular",
    "familyname":   "VargoMono",
    "fullname":     "VargoMono Regular",
    "weight":       "Regular",
    "copyright":    (
        "Original: Copyright 2013 Patrick Wagesreiter & Carrois Corporate GbR. "
        "Modifications: Vargo Dynamics (SC Signature Reader project). "
        "Licensed under SIL OFL 1.1."
    ),
    "version":      "1.000",
    "designer":     "Vargo Dynamics",
    "description":  (
        "VargoMono is a modified derivative of Share Tech Mono, "
        "customised for the Vargo Dynamics SC Signature Reader overlay. "
        "Modifications include slashed zero, crossbar seven, seriffed one, "
        "angular brand letters (V, A, M, W) and stencil-cut punctuation."
    ),
    "license":      "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
    "licenseurl":   "https://openfontlicense.org",
}

# ---------------------------------------------------------------------------
# Glyph post-processing
# These are simple programmatic tweaks applied AFTER the manual edits.
# Actual glyph shape changes must be done in FontForge's GUI — see
# fonts/VargoMono/glyph-spec.md for the full specification.
# ---------------------------------------------------------------------------

def set_metadata(font):
    font.fontname   = META["fontname"]
    font.familyname = META["familyname"]
    font.fullname   = META["fullname"]
    font.weight     = META["weight"]
    font.copyright  = META["copyright"]
    font.version    = META["version"]

    # Name table entries (OpenType)
    font.appendSFNTName("English (US)", "Family",      META["familyname"])
    font.appendSFNTName("English (US)", "SubFamily",   META["weight"])
    font.appendSFNTName("English (US)", "Fullname",    META["fullname"])
    font.appendSFNTName("English (US)", "Version",     "Version " + META["version"])
    font.appendSFNTName("English (US)", "Copyright",   META["copyright"])
    font.appendSFNTName("English (US)", "Designer",    META["designer"])
    font.appendSFNTName("English (US)", "Descriptor",  META["description"])
    font.appendSFNTName("English (US)", "License",     META["license"])
    font.appendSFNTName("English (US)", "License URL", META["licenseurl"])

    print(f"  Metadata set: {META['fullname']}")


def verify_critical_glyphs(font):
    """Warn if any Priority 1/2 glyphs are still at their original outlines."""
    critical = [
        (0x0030, "0 (zero)     — should have diagonal slash"),
        (0x0031, "1 (one)      — should have serif base"),
        (0x0037, "7 (seven)    — should have crossbar"),
        (0x0056, "V (brand)    — should have tick terminals"),
        (0x0041, "A            — should have stencil crossbar"),
        (0x00B7, "middle dot   — should be square/diamond"),
    ]
    print("\n  Glyph verification (manual check required):")
    for codepoint, description in critical:
        name = font[codepoint].glyphname if codepoint in font else "MISSING"
        print(f"    U+{codepoint:04X}  {description}  [{name}]")


def export(font):
    OUTPUT_TTF.parent.mkdir(parents=True, exist_ok=True)
    font.generate(str(OUTPUT_TTF))
    size_kb = OUTPUT_TTF.stat().st_size // 1024
    print(f"\n  Exported: {OUTPUT_TTF}  ({size_kb} KB)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("VargoMono font build")
    print("=" * 60)

    if not SOURCE_TTF.exists():
        print(f"\nERROR: Base font not found at {SOURCE_TTF}")
        print("\nDownload Share Tech Mono:")
        print("  https://github.com/googlefonts/ShareTechMono/raw/main/")
        print("  ShareTechMono-Regular.ttf")
        print(f"  -> save to {SOURCE_TTF}")
        sys.exit(1)

    print(f"\nOpening: {SOURCE_TTF}")
    font = fontforge.open(str(SOURCE_TTF))

    print("\n[1] Setting metadata...")
    set_metadata(font)

    print("\n[2] Glyph verification...")
    verify_critical_glyphs(font)

    print("\n[3] Exporting...")
    export(font)

    font.close()
    print("\nDone. Review the verification output above and confirm")
    print("all Priority 1 glyphs have been edited before releasing.")


if __name__ == "__main__":
    main()
