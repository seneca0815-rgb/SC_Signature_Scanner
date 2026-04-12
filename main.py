"""
main.py  –  SC Signature Reader / Vargo Dynamics
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
from control_panel import ControlPanel
from tray_icon import TrayIcon


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_base_dir() -> Path:
    import sys
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

def _build_scan_loop(state: AppState):
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

                img    = ov.capture_roi()
                img    = ov.preprocess(img)
                text   = ov.ocr_text(img)

                if text:
                    result = ov.lookup_text(text)
                    if result != last_key:
                        last_key = result
                        state.set_signal(result or "")
                else:
                    if last_key is not None:
                        last_key = None
                        state.set_signal("")

            except Exception as exc:
                print(f"[scan_loop] {exc}")

            time.sleep(state.interval)

    return scan_loop


# ---------------------------------------------------------------------------
# Hotkey listener
# ---------------------------------------------------------------------------

def _start_hotkey_listener(state: AppState, config: dict):
    try:
        import keyboard
    except ImportError:
        print("[hotkey] 'keyboard' not installed – hotkey disabled")
        return

    hotkey = config.get("hotkey", "F9")

    def on_hotkey():
        state.toggle_pause()
        print(f"[hotkey] Scanner {'paused' if state.paused else 'active'}")

    try:
        keyboard.add_hotkey(hotkey, on_hotkey)
        print(f"[hotkey] {hotkey} registered")
    except Exception as e:
        print(f"[hotkey] Failed to register {hotkey}: {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # --- Setup wizard ---
    if "--setup" in sys.argv:
        from setup_wizard import SetupWizard
        SetupWizard().run()

    # --- Load config and lookup ---
    try:
        config = load_json(CONFIG_PATH)
    except FileNotFoundError:
        print(f"[main] config.json not found at {CONFIG_PATH}")
        print("[main] Run with --setup to configure, or copy config.example.json")
        sys.exit(1)

    try:
        lookup = load_json(LOOKUP_PATH)
    except FileNotFoundError:
        print(f"[main] lookup.json not found at {LOOKUP_PATH}")
        sys.exit(1)

    # Initialise overlay module (loads config+lookup, applies theme, sets globals)
    import overlay as ov
    ov.init(CONFIG_PATH, LOOKUP_PATH)

    # --- Shared state ---
    state = AppState(config)

    # --- Tkinter root (hidden – ControlPanel and Overlay are Toplevels) ---
    root = tk.Tk()
    root.withdraw()
    root.title("SC Signature Reader")

    # --- Overlay window ---
    from overlay_window import OverlayWindow
    overlay = OverlayWindow(root, config, state)

    # --- Control panel ---
    panel = ControlPanel(root, config, state, overlay, BASE_DIR)

    # --- Tray icon ---
    tray = TrayIcon(state, panel, BASE_DIR)
    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()

    # --- Scan loop thread ---
    scan_fn = _build_scan_loop(state)
    scan_thread = threading.Thread(target=scan_fn, daemon=True)
    scan_thread.start()

    # --- Hotkey ---
    _start_hotkey_listener(state, config)

    # --- Mainloop ---
    print("SC Signature Reader started.")
    try:
        root.mainloop()
    finally:
        state.running = False
        tray.stop()


if __name__ == "__main__":
    main()
