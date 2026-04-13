# SC Signature Reader — User Manual

**Vargo Dynamics** · Version 1.1

---

## What does it do?

When you scan a rock or salvageable object in Star Citizen, the HUD displays
an orange signature number. SC Signature Reader reads that number automatically
and shows you the corresponding mineral name, multiplier and rarity in a small
overlay — without you having to memorise or look up anything manually.

```
HUD shows:  9510
Overlay shows:  ℹ  Quantainium (3x)  ·  Legendary
```

The tool uses screen capture only. It does **not** read game memory or inject
anything — it is fully ToS-compliant.

---

## Installation

### Option A — Installer (recommended)

1. Download `SCSigReader_Setup_1.1.exe` from the [Releases page](../../releases).
2. Run the installer — it will also install **Tesseract OCR** automatically.
3. The **Setup Wizard** opens at the end of installation. Complete it once.

### Option B — From source

See [README.md](README.md) for the developer setup instructions.

---

## Setup Wizard

The wizard runs once after installation (or any time via `SCSigReader.exe --setup`).
It has five steps:

| Step | What to do |
|---|---|
| **Welcome** | Read the intro, click Next. |
| **Resolution** | Select the resolution you play Star Citizen at. If unsure, check Windows → Display Settings → Resolution. |
| **Theme** | Choose how the overlay looks. A live preview is shown on the right. |
| **Hotkey** | Choose a key to pause/resume the scanner while in-game. **Scroll Lock** is recommended — it is not used by Star Citizen. |
| **Audio** | Configure audio feedback: startup announcement, scanner sounds and signal detection sound. |
| **Finish** | Review your choices and click **Finish** to save and launch. |

All settings are stored in `config.json` next to the executable and can be
changed at any time — either by re-running the wizard (`--setup`) or by editing
the file directly.

---

## The Control Panel

The control panel opens when SC Signature Reader starts.

```
┌─────────────────────────────────────┐
│ VARGO  DYNAMICS   SC Signature Reader│
├─────────────────────────────────────┤
│ SCANNER                             │
│  ● ACTIVE                   [PAUSE] │
│  Hotkey: Scroll Lock                │
├─────────────────────────────────────┤
│ LAST SIGNAL                         │
│  ℹ  Quantainium (3x)  ·  Legendary  │
├─────────────────────────────────────┤
│ THEME                               │
│  [vargo ▾]              [preview]   │
├─────────────────────────────────────┤
│ AUDIO                               │
│  [ON]   Volume ████░░   Signal [OFF]│
├─────────────────────────────────────┤
│ RECENT SIGNALS                      │
│  Quantainium (3x)  ·  Legendary     │
│  Quartz (4x)  ·  Common             │
│  Laranite (2x)  ·  Uncommon         │
├─────────────────────────────────────┤
│ [MINIMISE TO TRAY]  [LOG]  [EXIT]   │
└─────────────────────────────────────┘
```

| Element | Description |
|---|---|
| **● ACTIVE / PAUSED** | Current scanner state. Green = scanning, red = paused. |
| **PAUSE / RESUME** | Toggle the scanner on/off. Same as pressing the hotkey. |
| **Hotkey** | The keyboard shortcut configured in the wizard. |
| **LAST SIGNAL** | The most recent recognised signature and its lookup result. |
| **THEME** | Change the overlay appearance live. The change is saved automatically. |
| **AUDIO** | Master on/off, volume slider and signal sound toggle. |
| **RECENT SIGNALS** | The last five distinct signatures detected this session. |
| **MINIMISE TO TRAY** | Hides the control panel. The scanner keeps running. Right-click the tray icon to restore it. |
| **LOG** | Opens the logs folder in Explorer — attach `scsigread.log` when reporting issues. |
| **EXIT** | Stops the scanner completely and closes all windows. |

---

## The Overlay

The overlay is a small translucent pill that appears on screen whenever a
known signature number is detected.

- It appears automatically — you do not need to press anything.
- It disappears when no signature is in the scan area.
- It is always on top of other windows, including Star Citizen in borderless
  windowed mode.
- It pauses (hides) when the scanner is paused.

**Overlay position** — the default position is top-left (x 30, y 30). To move
it, edit `overlay_x` and `overlay_y` in `config.json`.

---

## System Tray

When the control panel is minimised, SC Signature Reader runs in the system
tray (bottom-right corner of the taskbar).

Right-click the tray icon for the context menu:

| Menu item | Action |
|---|---|
| **Show / Hide Panel** | Restore or hide the control panel. |
| **Scanner → Pause** | Pause the scanner. |
| **Scanner → Resume** | Resume the scanner. |
| **Exit** | Stop and close everything. |

Double-clicking the tray icon also shows/hides the control panel.

---

## Understanding the Results

The lookup result follows this format:

```
Mineral name  (multiplier)  ·  Rarity
```

**Examples**

| Result | Meaning |
|---|---|
| `Quantainium (3x)  ·  Legendary` | Quantainium with a 3× yield multiplier, legendary rarity |
| `Quartz (4x)  ·  Common` | Quartz with 4× multiplier, common rarity |
| `Laranite (2x)  ·  Uncommon` | Laranite with 2× multiplier |
| `Aslarite (5x)  ·  Uncommon  /  Savrilium (6x)  ·  Legendary` | Two minerals share the same signature number — both are shown |
| `~  Quartz (4x)  ·  Common  (Fuzzy Δ=1)` | Fuzzy match — OCR read the number with a 1-character error; result is likely correct |

---

## Hotkey

The hotkey (default: **Scroll Lock**) pauses and resumes the scanner without
switching away from the game.

| State | Overlay | Control Panel |
|---|---|---|
| **Active** | Shows results normally | Green ● ACTIVE |
| **Paused** | Hidden | Red ● PAUSED, RESUME button |

You can change the hotkey in the Setup Wizard (`--setup`) or by editing
`"hotkey"` in `config.json`. The value must be a key name recognised by the
`keyboard` library (e.g. `"scroll lock"`, `"f9"`, `"pause"`, `"insert"`).

---

## Supported Resolutions

The scan region is pre-configured for the three most common resolutions:

| Resolution | Notes |
|---|---|
| 1920 × 1080 | Full HD |
| 2560 × 1440 | WQHD (default in wizard) |
| 3440 × 1440 | Ultrawide |

For other resolutions or custom FOV settings, select **Custom** in the wizard
and adjust `scan_region` manually in `config.json`:

```json
"scan_region": { "top": 130, "left": 200, "width": 2160, "height": 900 }
```

Use `find_roi.py` (developer tool) to help identify the correct region for
your setup.

---

## Themes

Five built-in themes are available:

| Theme | Background | Text | Style |
|---|---|---|---|
| **vargo** | Dark navy | Cyan | Default Vargo Dynamics style |
| **dark-gold** | Near-black | Gold | Classic dark overlay |
| **dark-blue** | Deep navy | Light blue | Cool tone |
| **light** | Off-white | Dark | High contrast |
| **minimal** | Black | White | Smallest visual footprint |

Themes can be switched live in the control panel without restarting.

---

## Audio

SC Signature Reader plays voice announcements and sound effects
via WAV files from the `sounds\` folder.

| Sound | Default | When it plays |
|---|---|---|
| **Startup** | On | App launches – *"Vargo Dynamics Scanner online."* |
| **Activated** | On | Scanner resumed via hotkey or control panel |
| **Deactivated** | On | Scanner paused via hotkey or control panel |
| **Signal detected** | **Off** | Every time a signature is recognised |

The signal sound is off by default — when actively scouting asteroids
the overlay triggers frequently, and a sound on every detection
becomes distracting quickly. Enable it in the control panel or
`config.json` if you prefer audio feedback for each find.

**Volume** is controlled via the Windows volume mixer
(right-click the speaker icon in the taskbar → *SC Signature Reader*).
The volume slider in the control panel and wizard stores your preference
but the actual output level follows the system mixer.

**Audio settings in the control panel:**

| Control | Description |
|---|---|
| **ON / OFF toggle** | Master switch for all audio |
| **Volume slider** | Stores preference (see note above) |
| **Signal sound toggle** | Enable/disable the per-detection sound |

**Audio settings in config.json:**

```json
"audio_enabled":          true,
"audio_volume":           0.8,
"audio_voice_init":       true,
"audio_sound_activate":   true,
"audio_sound_deactivate": true,
"audio_sound_signal":     false
```

---

## Troubleshooting

**The overlay never appears**
- Make sure Star Citizen is in **borderless windowed** mode (not exclusive fullscreen).
- Check that the scanner is **Active** (green dot in the control panel).
- Confirm the scan region matches your resolution — run the Setup Wizard again (`--setup`).

**Wrong mineral shown / flickering**
- The HUD number may not be fully in the scan region. Try increasing `width` and `height` slightly in `config.json`.
- Increase `vote_frames` (default `3`) to `5` for more stable results.

**OCR detects nothing at all**
- Verify Tesseract is installed: open a terminal and run `tesseract --version`.
- Check `tesseract_cmd` in `config.json` points to the correct path (usually `C:\Program Files\Tesseract-OCR\tesseract.exe`).

**The overlay is in the wrong position**
- Edit `overlay_x` and `overlay_y` in `config.json`. Values are screen pixels from the top-left corner.

**The hotkey does not work**
- Some keys require the application to be run as administrator. Right-click `SCSigReader.exe → Run as administrator`.
- Try a different key in the Setup Wizard.

**"~" prefix in the result**
- A tilde (`~`) means a fuzzy match was used (OCR read the number with a small error). The result is still likely correct. If you see frequent fuzzy matches, tighten the scan region.

**No audio / sounds not playing**
- Verify that the `sounds\` folder exists next to `SCSigReader.exe` and contains the WAV files.
- Check `audio_enabled: true` in `config.json`.
- Check the Windows volume mixer — SC Signature Reader may be muted independently from system volume.
- If WAV files are missing the app falls back to a simple beep tone.

**Reporting a problem**
The fastest way to get help is to share your log file:

1. Open the control panel.
2. Click **LOG** in the footer — this opens the logs folder directly.
3. Attach `scsigread.log` to your Spectrum reply or GitHub issue.

The log contains your Tesseract version, scan region, theme and any errors
that occurred — usually enough to diagnose the problem without back-and-forth.

---

## Files

| File | Purpose |
|---|---|
| `SCSigReader.exe` | Main application |
| `config.json` | All settings — edit to fine-tune behaviour |
| `lookup.json` | Signature → mineral name table (163 entries) |
| `themes.py` | Theme colour definitions |
| `sounds\` | WAV audio files (init, activate, deactivate, signal) |
| `logs\scsigread.log` | Application log — share this when reporting issues |

---

## Re-running the Setup Wizard

```
SCSigReader.exe --setup
```

This re-runs the full wizard and overwrites `scan_region`, `theme`, `hotkey`
and audio settings in `config.json`. All other settings are preserved.

---

*SC Signature Reader is a fan-made community tool.
Not affiliated with or endorsed by Cloud Imperium Games.
See [DISCLAIMER.md](DISCLAIMER.md).*
