# VargoMono

Modified derivative of **Share Tech Mono** (SIL OFL 1.1).
Customised for the Vargo Dynamics SC Signature Reader overlay.

## Setup

1. Download the base font (not committed — too large for git):
   https://github.com/googlefonts/ShareTechMono/raw/main/ShareTechMono-Regular.ttf
   Save to: `fonts/VargoMono/ShareTechMono-Regular.ttf`

2. Open `ShareTechMono-Regular.ttf` in FontForge

3. Follow `glyph-spec.md` for the glyph modifications

4. Run the build script to apply metadata and export:
   `fontforge -script scripts/build_vargo_font.py`

5. Output: `fonts/VargoMono/VargoMono-Regular.ttf`

## Files

| File | Description |
|------|-------------|
| `glyph-spec.md` | Which glyphs to modify and how |
| `VargoMono-Regular.ttf` | Built font (committed after build) |
| `ShareTechMono-Regular.ttf` | Base font — download separately, not committed |

## License

SIL Open Font License 1.1.
Original copyright: Patrick Wagesreiter & Carrois Corporate GbR.
Modifications: Vargo Dynamics (SC Signature Reader project).
