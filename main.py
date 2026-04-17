"""
main.py  -  SC Signature Reader / Vargo Dynamics
Central entry point. Creates shared AppState, starts all threads,
opens the control panel and runs the tkinter mainloop.

Usage:
    python main.py           # normal start
    python main.py --setup   # run setup wizard first
"""

import sys
import threading
import time
import json
from pathlib import Path

import tkinter as tk

from app_state import AppState
from audio_manager import AudioManager
from control_panel import ControlPanel
from logger_setup import get_logger, setup_logger
from tray_icon import TrayIcon

VERSION = "1.0"

# Module-level logger – handlers are added by setup_logger() in main()
log = get_logger()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


BASE_DIR    = get_base_dir()
CONFIG_PATH = BASE_DIR / "config.json"
LOOKUP_PATH = BASE_DIR / "lookup.json"


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Scan loop (imported logic, runs in background thread)
# ---------------------------------------------------------------------------

def _build_scan_loop(state: AppState, audio: "AudioManager"):
    """
    Returns a scan_loop function that uses the given AppState.
    Imports overlay internals here to avoid circular imports.
    """
    import overlay as ov

    def scan_loop():
        last_key = None
        while state.running:
            try:
                if state.paused:
                    time.sleep(0.2)
                    continue

                hits   = ov.scan_once(state=state)
                result = hits[0][1] if hits else ""

                if result != last_key:
                    last_key = result
                    state.set_signal(result)
                    if result:
                        audio.play_signal(result)

            except Exception as exc:
                log.error("Scan loop error: %s", exc)

            time.sleep(state.interval)

    return scan_loop


# ---------------------------------------------------------------------------
# Hotkey listener
# ---------------------------------------------------------------------------

def _start_hotkey_listener(state: AppState, config: dict, audio: "AudioManager"):
    try:
        import keyboard
    except ImportError:
        log.warning("'keyboard' package not installed - hotkey disabled")
        return

    hotkey = config.get("hotkey", "F9")

    def on_hotkey():
        state.toggle_pause()
        log.debug("Hotkey pressed - scanner %s", "paused" if state.paused else "active")
        if state.paused:
            audio.play_deactivate()
        else:
            audio.play_activate()

    try:
        keyboard.add_hotkey(hotkey, on_hotkey)
        log.info("Hotkey registered: %s", hotkey)
    except Exception as e:
        log.warning("Failed to register hotkey '%s': %s", hotkey, e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    try:
        _run()
    except Exception:
        log.exception("Unhandled exception in main - application will exit")
        raise


def _run():
    # --- Setup wizard ---
    if "--setup" in sys.argv:
        from setup_wizard import SetupWizard
        SetupWizard(audio_manager=None).run()  # audio not yet loaded here

    # --- Load config ---
    try:
        config = load_json(CONFIG_PATH)
    except FileNotFoundError:
        # Logger not yet configured – use print as last resort
        print(f"[main] config.json not found at {CONFIG_PATH}")
        print("[main] Run with --setup to configure, or copy config.example.json")
        sys.exit(1)

    # --- Logging ---
    _log, log_path = setup_logger(config)
    log_dir = log_path.parent

    log.info("SC Signature Reader v%s starting", VERSION)
    log.info("Base directory: %s", BASE_DIR)
    log.info("Config loaded: %s", CONFIG_PATH)
    log.info("Log file: %s", log_path)

    # --- Tesseract validation ---
    try:
        import os
        import pytesseract
        tesseract_cmd = config.get("tesseract_cmd", "tesseract")
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        # Derive TESSDATA_PREFIX from tesseract_cmd when not already set.
        # Tesseract 5.x requires TESSDATA_PREFIX to point at the tessdata/
        # subdirectory (not the Tesseract-OCR install root).
        if tesseract_cmd and tesseract_cmd != "tesseract":
            tessdata_dir = Path(tesseract_cmd).parent / "tessdata"
            if tessdata_dir.is_dir():
                os.environ.setdefault("TESSDATA_PREFIX", str(tessdata_dir))
                log.debug("TESSDATA_PREFIX set to: %s", os.environ["TESSDATA_PREFIX"])
        tess_ver = pytesseract.get_tesseract_version()
        log.info("Tesseract version: %s", tess_ver)
    except FileNotFoundError:
        log.error(
            "Tesseract not found at '%s'. "
            "OCR will not work. "
            "Download from https://github.com/UB-Mannheim/tesseract/wiki",
            config.get("tesseract_cmd"),
        )
    except Exception as e:
        log.warning("Tesseract check failed: %s", e)

    # --- Load lookup table ---
    try:
        lookup = load_json(LOOKUP_PATH)
    except FileNotFoundError:
        log.error("lookup.json not found at %s", LOOKUP_PATH)
        sys.exit(1)

    log.info("Lookup table loaded: %d entries", len(lookup))

    # Initialise overlay module (loads config+lookup, applies theme, sets globals)
    import overlay as ov
    ov.init(CONFIG_PATH, LOOKUP_PATH)
    # Use the theme-merged config so UI components receive the correct colours.
    # overlay.init() does {**config, **theme} — without this, OverlayWindow would
    # always read the raw bg_color/fg_color from disk (vargo defaults).
    config = ov.config

    # --- Shared state ---
    state = AppState(config)
    state.set_config_path(CONFIG_PATH)

    # --- Audio ---
    audio = AudioManager(config)

    # --- Tkinter root (hidden – ControlPanel and Overlay are Toplevels) ---
    root = tk.Tk()
    root.withdraw()
    root.title("SC Signature Reader")

    # --- Overlay window ---
    from overlay_window import OverlayWindow
    overlay = OverlayWindow(root, config, state)

    # --- Control panel ---
    panel = ControlPanel(root, config, state, overlay, BASE_DIR,
                         audio=audio, log_dir=log_dir)

    log.info("Theme: %s", config.get("theme"))
    log.info("Scan region: %s", config.get("scan_region") or config.get("roi"))
    log.info("Audio enabled: %s", config.get("audio_enabled", False))
    log.info("Hotkey: %s", config.get("hotkey", "Scroll Lock"))
    log.info("Control panel ready")

    # --- Tray icon ---
    tray = TrayIcon(state, panel, BASE_DIR)
    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()

    # --- Scan loop thread ---
    scan_fn = _build_scan_loop(state, audio)
    scan_thread = threading.Thread(target=scan_fn, daemon=True)
    scan_thread.start()

    # --- Hotkey ---
    _start_hotkey_listener(state, config, audio)

    # --- Startup sound ---
    audio.play_init()

    # --- Mainloop ---
    log.info("SC Signature Reader started")
    try:
        root.mainloop()
    finally:
        state.running = False
        tray.stop()
        log.info("SC Signature Reader shutdown cleanly")


if __name__ == "__main__":
    main()
