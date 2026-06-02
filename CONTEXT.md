# SC Signature Reader – Project Context

## What this project is
A transparent always-on-top overlay for Star Citizen.
Detects mining signature numbers in the HUD via screen capture + OCR
and displays the mineral name + multiplier from a lookup table.
ToS-compliant – no memory reading, no DLL injection.

## Tech stack
- Python 3.11+
- mss (screen capture)
- OpenCV + numpy (colour-based region detection)
- Pillow (image preprocessing)
- pytesseract / Tesseract OCR
- tkinter (overlay windows + control panel + setup wizard)
- pystray (system tray icon)
- keyboard (global hotkey)
- PyInstaller (build exe)
- Inno Setup (Windows installer)

## Key files
| File | Role |
|------|------|
| `main.py` | Entry point – creates AppState, starts threads, opens ControlPanel, runs tkinter mainloop |
| `overlay.py` | Full OCR pipeline (capture → detect → preprocess → OCR → normalize → lookup → vote) |
| `app_state.py` | Thread-safe shared state (paused flag, last_signal, history, theme, config persistence) |
| `control_panel.py` | Main control window (history, theme switcher, overlay position, help text) |
| `overlay_window.py` | Transparent always-on-top result window; rarity colour coding; named position presets |
| `setup_wizard.py` | First-run wizard (resolution preset, theme, hotkey, audio) |
| `tray_icon.py` | System tray icon via pystray (daemon thread) |
| `audio_manager.py` | WAV/beep audio feedback (signal detected, activate, deactivate, init) |
| `themes.py` | 6 built-in themes: vargo (default), dark-gold, dark-blue, cockpit, minimal, ghost |
| `lookup.json` | 163 signature entries – signature number → mineral name + multiplier |
| `config.example.json` | Template config (copy to config.json before first run) |

## Test suite
- **430 tests** (+ 815 subtests) — all pass
- `tests/test_core.py` – unit tests for OCR pipeline and overlay logic
- `tests/test_ui_acceptance.py` – acceptance tests for AppState, OverlayWindow, ControlPanel
- `tests/test_setup_wizard.py` – acceptance tests for SetupWizard
- `tests/test_audio.py` – AudioManager (WAV loading, volume, winsound fallback)
- `tests/test_tray_icon.py` – TrayIcon (run/stop/callbacks/fallback icon)
- `tests/test_main.py` – main.py integration (startup, scan loop, hotkey, installer)
- `tests/test_logger.py` – logger_setup (Windows/Linux paths, rotation)
- `tests/test_integration.py` – file/config structure integrity

## Coverage (key modules)
| Module | Coverage |
|--------|----------|
| `app_state.py` | 100% |
| `audio_manager.py` | 100% |
| `control_panel.py` | 100% |
| `logger_setup.py` | 100% |
| `tray_icon.py` | 100% |
| `main.py` | 99% |
| `overlay.py` | 98% |
| `setup_wizard.py` | 98% |

Remaining uncovered lines are `if __name__ == "__main__"` guards and live-display tkinter drawing.

## Branch strategy (as of 2026-06-02)

| Branch | Purpose | Status |
|--------|---------|--------|
| `main` | V1.x legacy — frozen at v1.4.4 | No new features; critical hotfixes only |
| `v2`   | V2.0 development — PySide6, new features | Active development |

**All new work goes on `v2`.** `main` is the stable reference for the tkinter baseline.

## Current status (as of 2026-06-02)
- V1.4.4 released — frozen on `main`
- VargoMono font created (`fonts/VargoMono/VargoMono-Regular.ttf`)
- V2 branch created — ready for PySide6 migration and new features
- CI runs on both branches via GitHub Actions

## V1.0 Roadmap
1. ✅ Fix unit tests
2. ✅ MIT LICENSE + DISCLAIMER.md
3. ✅ Integration tests
4. ✅ GitHub Actions CI + Release workflow (Inno Setup installer, Tesseract via GitHub API)
5. ✅ Desktop control app (main.py, control_panel, overlay_window, tray_icon, app_state)
6. ✅ Hotkey toggle (Scroll Lock default, configurable)
7. ✅ Corporate design (Vargo Dynamics brand, 6 themes)
8. ✅ Setup wizard (5-step: welcome → resolution → theme → hotkey → finish)
9. ✅ Full test coverage (430 tests, all modules ≥ 98%)
10. ❌ Spectrum post + CIG community verification

## How to run
```bash
# First-time setup
cp config.example.json config.json

# Run application
python main.py

# First-run setup wizard
python main.py --setup

# Run all tests
python -m pytest tests/ -v

# Run a single module's tests
python -m pytest tests/test_core.py -v
```

## How to build
```bash
pyinstaller --onefile --noconsole --name SCSigReader main.py \
  --add-data "config.example.json;." --add-data "lookup.json;." \
  --add-data "themes.py;." --add-data "overlay_window.py;." \
  --add-data "control_panel.py;." --add-data "setup_wizard.py;." \
  --add-data "tray_icon.py;." --add-data "app_state.py;." \
  --add-data "overlay.py;."
# then run Inno Setup with SCSigReader.iss
```

---

## V2.0 Roadmap (draft 2026-06-02)

### Guiding principles
- Use Claude Code skills throughout development (skills-first, see 2026-05-19 decisions)
- Qt-Migration with Qt MCP for widget introspection and live testing

### Features

| # | Feature | Priority | Notes |
|---|---------|----------|-------|
| 1 | **Qt migration** (tkinter → PySide6) | Core | Use Qt MCP for dev loop; see migration open questions below |
| 2 | **Scan region setup improvements** | High | Adapt to display resolution, FOV setting, headtracking active/inactive |
| 3 | **Vargo sci-fi font** | High | Custom `.ttf` for brand-consistent typography across app, overlay, installer |
| 4 | **Improved logging UX** | High | Easy access to logs from UI; currently hidden in `%APPDATA%` folder |
| 5 | **Smarter resource log** | High | Parsed logfile or optional API integration; persistent history of found minerals |
| 6 | **Cockpit Scanner Mode** | High | Permanent slim overlay; replaces/extends the existing `display_window.py` VD-SFR1 |
| 7 | **Animations** | Medium | Scan-active indicator, signal-found notification animation |
| 8 | **Better sounds** | Medium | More sci-fi; ship-speaker/radio effect filter on voice output |
| 9 | **Additional app themes** | Medium | New PySide6 QSS themes; cockpit mode gets its own visual profile |
| 10 | **Further improve detection rate** | Optional | New ship manufacturers, unusual FOV/lighting conditions |
| 11 | **Ship radio function** | Optional | Spotify/Apple Music/online radio with ship-speaker effect — possibly separate app |

### Open questions carried forward from 2026-05-19
- Migrationsstrategie tkinter → PySide6: Big Bang vs. inkrementell?
  Aktuell: AppState, OverlayWindow, ControlPanel, SetupWizard in tkinter.
  Empfehlung: erst Overlay, dann ControlPanel, dann Wizard (inkrementell).
- `.claude/` bereits im Repo — ✅ erledigt.

---

## 2026-05-19 – Agentic Approach & Qt Migration: Architecture Decisions

### Decisions made (claude.ai planning session)

**Qt binding: PySide6** (LGPL). Saubere Lizenzkompatibilität mit MIT.
PyQt6 ist damit raus.

**Agentic strategy: Skills-first, no subagents in phase 1.**
Begründung: Subagents zu früh aufzusetzen führt zu Overhead ohne
Gegenwert. Erst 2–3 Wochen Skill-Nutzung sammeln, dann entscheiden,
welche Subagents sich tatsächlich aufdrängen.

### Skills layout

Projekt-lokale Skills unter `.claude/skills/<skill-name>/SKILL.md`,
optional mit `reference/`-Unterordner für umfangreichere Skills
(Claude liest nur SKILL.md initial, greift bei Bedarf auf reference/ zu).

```
.claude/skills/
├── pill-detection/
│   ├── SKILL.md
│   └── reference/
│       ├── threshold-calibration.md
│       └── fixture-examples.md
└── vargo-brand-style/
    └── SKILL.md
```

### Skills roadmap

**Phase 1 (jetzt – höchster Hebel):**
- [ ] `pill-detection` – Detection-Pipeline, Geometrie-Schwellen,
      Fuzzy-Matching, Performance-Budget (sub-400ms), Designentscheidung
      "color → geometry" als explizit dokumentierte Rationale
- [ ] `vargo-brand-style` – Farbpalette (`#1a1a2a`, `#4fc3c3`, `#c9a84c`,
      `#d8d8e8`), Typografie, retro-futuristisch-militärisch.
      Wird in Asset-Generation, QSS-Styling und Spectrum-Visuals gebraucht.

**Phase 2 (wenn Qt-Migration läuft):**
- [ ] `sc-fixture-format` – Fixture-Naming, Annotation, Verzeichnisstruktur
- [ ] `release-process` – Version-Bump, Changelog, Tag, GHA-Trigger,
      Inno-Setup-Verifikation, Smoke-Test

**Phase 3 (Content/Community):**
- [ ] `elena-vargo-voice` – Charakterstimme, ElevenLabs-Profil-Konventionen,
      Vokabular
- [ ] `spectrum-post-style` – Modding-Forum-Konventionen, MIT/Disclaimer-Posture

### Subagent candidates (zur späteren Evaluation)

Nach Phase 1 prüfen, ob folgende Subagents sich aufdrängen:
- `detection-engineer` – Fixture-Analyse, Threshold-Tuning, Regression
- `qt-ui-developer` – PySide6-Komponenten, QSS, Signal/Slot
- `release-engineer` – End-to-End-Release-Lauf
- `creative-director` – kombiniert Brand, Voice, Lore/Spectrum

### Qt MCPs roadmap

1. **Qt Documentation MCP** (offiziell, Qt Company) – sobald Qt-Migration
   startet. Token-sparsame, strukturierte API-Referenz. Über Claude
   Marketplace Plugin "qt-development" installierbar.
2. **qt-mcp** (0xCarbon) – sobald erste PySide6-Widgets stehen. Ermöglicht
   Widget-Introspektion, Screenshots und Event-Injection im laufenden App.
   **Wichtig:** Probe nur in Dev-Builds aktivieren – öffnet TCP-Port
   `localhost:9142`. Niemals in Release-Builds via PyInstaller. Aktivierung
   über `QT_MCP_PROBE=1` Environment-Variable, nicht hardcoded.
3. **qt-pilot** (neatobandit0) – später, für headless CI-Tests in GHA.
   Vorerst nicht nötig, qt-mcp deckt die Dev-Loop ab.
4. **Qt Creator MCP** – nicht relevant (kein Qt Creator im Stack).

### Next steps for Claude Code

1. `.claude/skills/` Verzeichnisstruktur anlegen
2. `pill-detection/SKILL.md` schreiben – existierenden Detection-Code als
   Quelle nutzen (geometry-based pill detection, fuzzy match,
   multi-threshold scan), Performance-Erkenntnisse aus v1.x einbauen
3. `vargo-brand-style/SKILL.md` schreiben – `generate_assets.py` als Quelle
   für Farben/Typografie, Erkenntnisse aus bisheriger Asset-Generation
4. `CONTRIBUTING.md` aktualisieren: Hinweis auf `.claude/skills/` und
   wie Skills bei Beiträgen genutzt werden
5. Commit-Strategie: ein Commit pro Skill, klare Messages
   (`docs(skills): add pill-detection skill`)

### Open questions (für Claude Code zu klären)

- Migrationsstrategie tkinter → PySide6: Big Bang vs. inkrementell?
  Aktuell: AppState, OverlayWindow, ControlPanel, SetupWizard in tkinter.
  Frage: alle gleichzeitig portieren oder erst Overlay, dann ControlPanel,
  dann Wizard? Eigene Planungssitzung wert.
- `.claude/` ins Repo committen oder gitignoren? Empfehlung: committen,
  damit auf neuen Maschinen via `setup_dev.py` direkt verfügbar.
