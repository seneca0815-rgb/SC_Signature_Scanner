"""
app_state.py  –  SC Signature Reader / Vargo Dynamics
Shared application state passed to all components.
Thread-safe via threading primitives.
"""

import threading
from collections import deque
from pathlib import Path
import json

from logger_setup import get_logger

log = get_logger()


MAX_RECENT = 5


class AppState:
    """
    Single source of truth shared between scan_loop, ControlPanel,
    OverlayWindow and TrayIcon.

    All writes are protected by _lock.
    UI components poll via tkinter after() or register a callback.
    """

    def __init__(self, config: dict):
        self._lock          = threading.Lock()
        self._callbacks     = []           # called on every signal change

        # Runtime flags
        self.running        = True         # False → all threads exit
        self._paused        = False        # True → scan_loop idles

        # Signal state
        self._last_signal   = ""           # last recognised text
        self._recent        = deque(maxlen=MAX_RECENT)

        # Performance tracking
        self._cycle_times   = deque(maxlen=10)
        self._last_cycle_ms = 0.0

        # Config
        self.interval       = config.get("interval_ms", 500) / 1000
        self._active_theme  = config.get("theme", "vargo")
        self._config        = config
        self._config_path   = None         # set by main after load

    # ------------------------------------------------------------------
    # Pause / resume
    # ------------------------------------------------------------------

    @property
    def paused(self) -> bool:
        return self._paused

    def toggle_pause(self):
        with self._lock:
            self._paused = not self._paused
        log.info("Scanner %s", "paused" if self._paused else "resumed")
        self._notify()

    def set_paused(self, value: bool):
        with self._lock:
            self._paused = value
        self._notify()

    # ------------------------------------------------------------------
    # Signal
    # ------------------------------------------------------------------

    @property
    def last_signal(self) -> str:
        return self._last_signal

    @property
    def recent_signals(self) -> list[str]:
        with self._lock:
            return list(reversed(self._recent))

    def set_signal(self, text: str):
        with self._lock:
            self._last_signal = text
            if text:
                self._recent.append(text)
        log.debug("Signal set: '%s'", text)
        self._notify()

    # ------------------------------------------------------------------
    # Performance
    # ------------------------------------------------------------------

    @property
    def last_cycle_ms(self) -> float:
        return self._last_cycle_ms

    @property
    def avg_cycle_ms(self) -> float:
        with self._lock:
            if not self._cycle_times:
                return 0.0
            return sum(self._cycle_times) / len(self._cycle_times)

    def record_cycle_time(self, ms: float):
        with self._lock:
            self._last_cycle_ms = ms
            self._cycle_times.append(ms)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    @property
    def active_theme(self) -> str:
        return self._active_theme

    def set_theme(self, name: str):
        with self._lock:
            self._active_theme = name
            self._config["theme"] = name
        log.info("Theme changed to: %s", name)
        self._save_config()
        self._notify()

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def set_config_path(self, path: Path):
        self._config_path = path

    def _save_config(self):
        if self._config_path and self._config_path.exists():
            try:
                with open(self._config_path, "w", encoding="utf-8") as f:
                    json.dump(self._config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                log.warning("Config save failed: %s", e)

    # ------------------------------------------------------------------
    # Change notification
    # ------------------------------------------------------------------

    def register_callback(self, fn):
        """Register a callable that is invoked on every state change."""
        self._callbacks.append(fn)

    def _notify(self):
        for fn in self._callbacks:
            try:
                fn()
            except Exception as e:
                log.warning("AppState callback error: %s", e)
