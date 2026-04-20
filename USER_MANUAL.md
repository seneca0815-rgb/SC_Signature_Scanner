# SC Signature Reader — User Manual

**Vargo Dynamics** · Version 1.3

---

## What does it do?

When you scan a rock or salvageable object in Star Citizen, the HUD displays
a signature number inside a small rounded pill next to a Location-Pin icon.
SC Signature Reader reads that number automatically and shows you the
corresponding mineral name, multiplier and rarity in a small overlay —
without you having to memorise or look up anything manually.

```
HUD shows:  9510
Overlay shows:  ℹ  Quantainium (3x)  ·  Legendary
```

The tool uses screen capture only. It does **not** read game memory or inject
anything — it is fully ToS-compliant.

**Works on all ships** — Aegis, Anvil, Krueger, RSI, Argo and more.
Detection is manufacturer-independent: it works regardless of HUD colour
(cyan, orange, purple, green) or background (dark space, nebula, planet surface).

---

## Installation

### Option A — Installer (recommended)

1. Download `SCSigReader_Setup_1.3.exe` from the [Releases page](../../releases).
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
- The **text colour changes automatically** based on rarity:

| Rarity | Colour |
|---|---|
| Common | White |
| Uncommon | Blue |
| Rare | Yellow |
| Epic | Gold |
| Legendary | Purple |

**Overlay position** — select a named preset in the control panel, or set
`overlay_position` to `custom` in `config.json` and adjust `overlay_x` / `overlay_y`.

Available presets: `top_left`, `top_center`, `top_right`, `upper_left`,
`upper_center`, `upper_right`, `center_left`, `center_right`,
`bottom_left`, `bottom_center`, `bottom_right`.

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

The scan region covers the full game viewport above the cockpit dashboard.
Rock labels float anywhere on screen depending on camera angle, so a
full-width region is required.

| Resolution | Notes |
|---|---|
| 1920 × 1080 | Full HD |
| 2560 × 1440 | WQHD (default in wizard) |
| 3440 × 1440 | Ultrawide |

For other resolutions, select **Custom** in the wizard and adjust
`scan_region` manually in `config.json`:

```json
"scan_region": { "top": 130, "left": 200, "width": 2160, "height": 900 }
```

Use `find_roi.py` to help identify the correct region for your setup.

---

## Themes

Six built-in themes are available. The overlay text colour changes
automatically to match the detected mineral's rarity regardless of theme.

| Theme | Background | Default text | Style |
|---|---|---|---|
| **vargo** | `#1a1a2a` | Cyan | Default Vargo Dynamics style |
| **dark-gold** | `#111827` | Gold | Warm, classic |
| **dark-blue** | `#0d1b2a` | Blue | Cool, subtle |
| **cockpit** | `#071a07` | Neon green | Retro terminal / HUD look |
| **minimal** | `#0d0d1a` | White | Compact, unobtrusive |
| **ghost** | Transparent | White | Floating text, no background box |

Themes can be switched live in the control panel without restarting.

---

## Audio

SC Signature Reader plays voice announcements and sound effects
via WAV files from the `sounds\` folder.

| Sound | Default | When it plays |
|---|---|---|
| **Startup** | On | App launches — *"Vargo Dynamics Scanner online."* |
| **Activated** | On | Scanner resumed via hotkey or control panel |
| **Deactivated** | On | Scanner paused via hotkey or control panel |
| **Signal detected** | **Off** | Every time a signature is recognised |

The signal sound is off by default — when actively scouting asteroids
the overlay triggers frequently, and a sound on every detection
becomes distracting quickly. Enable it in the control panel or
`config.json` if you prefer audio feedback for each find.

**Volume** is controlled via the Windows volume mixer
(right-click the speaker icon in the taskbar → *SC Signature Reader*).

**Audio settings in config.json:**

```json
"audio_enabled":          true,
"audio_volume":           0.5,
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
- Enable `"log_level": "DEBUG"` in `config.json` and check `pills=N` in the timing lines.
- Run `python test_icon_detection.py` on a HUD screenshot to see which pills were detected.

**Wrong mineral shown / flickering**
- Increase `vote_frames` (default `3`) to `5` for more stable results.
- Tighten `scan_region` to exclude large bright UI panels.

**Pill not found (pills=0 every cycle)**
- Check `median_V` in DEBUG log — if > 100, try lowering `pill_v_adaptive_offset`.
- The scan region may be outside the game viewport — use `find_roi.py` to re-calibrate.

**Too many false pill candidates**
- Reduce `pill_aspect_max` (e.g. `5.0`) to filter elongated false positives.
- Tighten `scan_region` to exclude bright cockpit panel areas.

**Slow scan cycles (> 1000 ms)**
- Enable DEBUG logging — the PERFORMANCE panel in the control panel shows avg/last cycle time.
- Reduce `max_pills` (e.g. `2`) to limit Tesseract calls per cycle.

**The hotkey does not work**
- Some keys require the application to be run as administrator. Right-click `SCSigReader.exe → Run as administrator`.
- Try a different key in the Setup Wizard.

**No audio / sounds not playing**
- Verify that the `sounds\` folder exists next to `SCSigReader.exe` and contains the WAV files.
- Check `audio_enabled: true` in `config.json`.
- Check the Windows volume mixer — SC Signature Reader may be muted independently.
- If WAV files are missing the app falls back to a simple beep tone.

**"~" prefix in the result**
- A tilde (`~`) means a fuzzy match was used. The result is still likely correct.
- If you see frequent fuzzy matches, check the DEBUG log for raw OCR values.

**Different resolution or FOV**
- Adjust `scan_region` (see reference table above).
- Pill detection is resolution- and HUD-colour-independent.

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

---

## Legal note

We contacted CIG Player Support regarding this tool. Their response confirmed
that tools providing unfair advantages, reading game memory, or automating
gameplay are prohibited by the ToS. SC Signature Reader does none of these
things — it uses screen capture only, provides no information unavailable to
any player, and requires full manual control of all gameplay decisions.

We are confident it complies with the Star Citizen Terms of Service.
This assessment is ours, not CIG's. Use at your own risk.

*SC Signature Reader is a fan-made community tool.
Not affiliated with or endorsed by Cloud Imperium Games.
See [DISCLAIMER.md](DISCLAIMER.md) for the full disclaimer.*
