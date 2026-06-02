# Skill: vargo-brand-style

Visual and verbal identity for Vargo Dynamics — the in-universe manufacturer behind SC Signature Reader.
Apply whenever generating or editing assets, QSS stylesheets, Spectrum posts, or installer graphics.

## Brand identity

**Company:** Vargo Dynamics  
**Division:** Field Intelligence Division  
**Founder / character:** E. Vargo (Elena Vargo), based in Orison, Crusader  
**Tagline:** "Precision. Technology. Independence."  
**Tone:** Retro-futuristic military. Field-built, not lab-polished. Terse, direct, functional.

The brand is *not* corporate-clean. It feels like a comms terminal on a mining vessel —
monospace text, structural rings, gold serif details, cyan signal colour.

---

## Colour palette

Source: `scripts/generate_assets.py`

| Role | Hex | RGB | Usage |
|------|-----|-----|-------|
| Primary background | `#1a1a2a` | (26, 26, 42) | All backgrounds, overlay pills |
| Deep dark | `#0e0e18` | (14, 14, 24) | Inner cutouts, shadow fills |
| Structural / dim | `#2a3a4a` | (42, 58, 74) | Rings, dividers, borders |
| **Cyan accent** | `#4fc3c3` | (79, 195, 195) | Primary brand colour — rings, V-mark, text accent, borders |
| **Gold accent** | `#c9a84c` | (201, 168, 76) | Serif ticks, cardinal dots, horizontal rule centre, tagline text |
| Neutral text | `#d8d8e8` | (216, 216, 232) | Body text, company name |

### Rarity colours (overlay / QSS only)

Source: `overlay_window.py`

| Rarity | Hex |
|--------|-----|
| Legendary | `#cc44ff` |
| Epic | `#ffa030` |
| Rare | `#ffdd00` |
| Uncommon | `#4488ff` |
| Common | `#e2e2e2` |

---

## Typography

- **Primary font:** VargoMono — custom derivative of Share Tech Mono (SIL OFL 1.1)
  - File: `fonts/VargoMono/VargoMono-Regular.ttf`
  - Modifications: slashed zero, crossbar seven, seriffed one, square middle dot
  - Rebuild: `fontforge -script scripts/ff_edit_glyphs.py` → `python scripts/build_vargo_font_ft.py`
- **Fallback chain:** `"VargoMono", "Consolas", "Courier New", monospace`
- **Monospace only** — no proportional fonts anywhere in the brand
- **Sizes in use:** 18 px (company name), 13 px (overlay body), 11 px (labels), 9–10 px (info lines), 8 px (sub-labels), 6 px (tagline fine print)
- **QSS / PySide6:** `font-family: "VargoMono", "Consolas", "Courier New", monospace`

---

## Visual elements (V-mark logo)

The logo is a stylised **V** with:

| Element | Colour | Notes |
|---------|--------|-------|
| V body | `#4fc3c3` (cyan) | Outer polygon |
| Inner cutout | `#1a1a2a` (bg) | Creates hollow V shape |
| Horizontal bar | `#1a1a2a` (bg) | Detail cut across V stem |
| Serif ticks (top corners) | `#c9a84c` (gold) | Two short rectangles at upper-left and upper-right |
| Bottom dot | `#c9a84c` (gold) | Small circle at V tip |

Surrounding ring system:

| Ring | Colour | Notes |
|------|--------|-------|
| Outer ring | `#2a3a4a` (structural) | Thin (1 px) |
| Primary ring | `#4fc3c3` (cyan) | Bold (2 px), this is where cardinal ticks land |
| Inner ring | `#2a3a4a` (structural) | Thin (1 px) |
| Cardinal ticks | `#4fc3c3` (cyan) | N/S/E/W lines extending outward from primary ring |
| Cardinal dots | `#c9a84c` (gold) | Small circles at N/S/E/W on primary ring |

Horizontal rule pattern (used in installer sidebar):

```
─────── [gold dash] ·  [gold dot]  · [gold dash] ───────
        (dim)                                    (dim)
```

Corner tick marks in cyan at all four corners of rectangular layouts.

---

## Overlay themes (`themes.py`)

Six themes — `vargo` is canonical and the default.

| Theme | bg | fg | alpha | Character |
|-------|----|----|-------|-----------|
| **vargo** | `#1a1a2a` | `#4fc3c3` | 0.90 | Canonical brand — dark navy, cyan text |
| dark-gold | `#111827` | `#e2c97e` | 0.88 | Warm gold variant |
| dark-blue | `#0d1b2a` | `#7eb8e2` | 0.88 | Cool blue variant |
| cockpit | `#071a07` | `#39ff14` | 0.88 | Green phosphor terminal |
| minimal | `#0d0d1a` | `#ffffff` | 0.72 | Maximum readability |
| ghost | `#000000` | `#ffffff` | 0.55 | Near-invisible, floating text |

In the overlay, the rarity keyword in each result line is coloured with its rarity colour
(overriding the theme fg). Everything else uses the theme fg.

---

## Asset inventory

| File | Size | Generator |
|------|------|-----------|
| `vargo_icon.ico` | multi-size 16/32/48/256 | `scripts/generate_assets.py` |
| `vargo_icon_256.png` | 256×256 | `scripts/generate_assets.py` |
| `vargo_installer.bmp` | 164×314 | `scripts/generate_assets.py` |
| `vargo_installer_header.bmp` | 497×58 | `scripts/generate_assets.py` |
| `theme_preview.png` | dynamic grid | `scripts/generate_theme_preview.py` |

Regenerate all assets: `python scripts/generate_assets.py`

---

## Spectrum / community voice

The brand speaks **in-universe** for forum posts and release announcements.

Structure of a Spectrum post:
1. ASCII transmission header (═══ borders, VARGO DYNAMICS · FIELD INTELLIGENCE DIVISION)
2. Lore intro in first person from E. Vargo — field perspective, no marketing fluff
3. Functional `//`-prefixed sections (WHAT IT DOES, HOW IT WORKS, DOWNLOAD, DISCLAIMER)
4. Footer: `VARGO DYNAMICS  ·  "Precision. Technology. Independence."`

See `spectrum_post.md` (project root) for the v1.0 release post as the canonical reference.

**Voice rules:**
- Short paragraphs. Active voice.
- No corporate superlatives ("best-in-class", "revolutionary").
- Mention real limitations honestly (tested hardware, known gaps).
- The character E. Vargo is the narrator — not "we" as a corporation.
- ASCII art / monospace decoration is on-brand; markdown headers use `## //` prefix.

---

## QSS guidelines (PySide6 migration)

When writing QSS for PySide6 components, follow these rules:

- Background: `#1a1a2a`
- Borders / separators: `1px solid #2a3a4a`
- Primary interactive elements (buttons, active tabs): `background: #2a3a4a; color: #4fc3c3`
- Hover state: `background: #2a3a4a; border: 1px solid #4fc3c3`
- Focus / selected: `border: 1px solid #4fc3c3; color: #4fc3c3`
- Accent text / icons: `#4fc3c3`
- Secondary accent (gold details): `#c9a84c` — use sparingly, for emphasis only
- Body text: `#d8d8e8`
- Disabled / dim text: `#2a3a4a`
- Font: `font-family: "Consolas", "Courier New", monospace; font-size: 13px`

Never use system accent colours or platform-default stylesheet elements — explicitly set everything.
