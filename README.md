# SC Overlay – Installations- & Bedienungsanleitung

Transparentes Always-on-Top-Overlay für Star Citizen.  
Liest einen konfigurierbaren UI-Bereich per OCR aus und blendet  
Zusatzinfos aus einer Lookup-Tabelle ein. **Kein Memory-Reading, kein DLL-Inject – ToS-konform.**

---

## Schnellstart

### 1. Tesseract installieren
Windows: https://github.com/UB-Mannheim/tesseract/wiki  
Linux:   `sudo apt install tesseract-ocr`  
macOS:   `brew install tesseract`

### 2. Python-Abhängigkeiten
```bash
pip install mss pillow pytesseract
```

### 3. config.json anpassen

| Schlüssel | Bedeutung |
|---|---|
| `roi` | Pixel-Bereich, der gescannt wird (top/left/width/height) |
| `interval_ms` | Scan-Frequenz (Standard 400 ms) |
| `ocr_confidence` | Mindestkonfidenz von Tesseract (0–100) |
| `tesseract_cmd` | Vollpfad zur tesseract.exe (Windows) |
| `overlay_x/y` | Position des Overlay-Fensters |
| `alpha` | Transparenz des Overlays (0.0–1.0) |

**ROI ermitteln:** Nutze ein Screenshot-Tool (z.B. ShareX) mit Koordinatenanzeige,  
um den genauen Pixel-Bereich des SC-UI-Texts zu bestimmen.

### 4. lookup.json befüllen
```json
{
  "Drake Cutlass Black": "46 SCU · empf. Crew: 2 · Bewaffnung: 4× S3",
  "Laranite": "Mineral · hoch wertvoll · oft auf Yela/Calliope"
}
```
Schlüssel = genauer Text wie er im Spiel erscheint.  
Partial-Matches funktionieren ebenfalls (Substring-Suche).

### 5. Starten
```bash
python overlay.py
```

---

## Architektur

```
[SC-Bildschirm]
      │  Screenshot des ROI alle 400ms
      ▼
[mss Screen Capture]
      │
      ▼
[Preprocessing]  ← Graustufen + 2× Upscale
      │
      ▼
[pytesseract OCR]  ← nur Wörter ≥ confidence
      │  erkannter Text
      ▼
[Lookup Table (lookup.json)]
      │  Info-String oder None
      ▼
[tkinter Overlay]  ← transparentes Always-on-Top-Fenster
```

---

## Tipps

- **ROI genau setzen:** Je kleiner und gezielter der ROI, desto schneller und genauer die OCR.
- **Font anpassen:** SC nutzt eine klare, serifenlose Schrift → Tesseract kommt gut damit klar.
- **Weißer Hintergrund:** Falls der Text auf dunklem Hintergrund schlecht erkannt wird,  
  Bild per Pillow invertieren: `img = PIL.ImageOps.invert(img)` in `preprocess()` einfügen.
- **Mehrere ROIs:** Für mehrere UI-Bereiche einfach mehrere `scan_loop`-Threads mit  
  unterschiedlichen ROI-Configs starten.
- **Performance:** `interval_ms: 600` spart CPU ohne merkbaren Unterschied im Spielgefühl.
