"""
audio_manager.py  –  SC Signature Reader / Vargo Dynamics
All audio output via WAV files (winsound.PlaySound) with beep fallback.
All playback runs in a single-worker ThreadPoolExecutor so sounds
play in sequence and never block the UI or scan loop.
"""

import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base directory – works both as plain Python and PyInstaller frozen exe
# ---------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Optional winsound import – graceful no-op on non-Windows
# ---------------------------------------------------------------------------

try:
    import winsound as _winsound
    _HAS_WINSOUND = True
except ImportError:
    _HAS_WINSOUND = False


# ---------------------------------------------------------------------------
# AudioManager
# ---------------------------------------------------------------------------

class AudioManager:
    """
    Manages all audio output for SC Signature Reader.

    Sounds are loaded from WAV files in the sounds/ directory next to the
    executable (or inside the PyInstaller bundle). If a file is missing the
    method falls back to a single winsound.Beep so the app always works even
    on a fresh clone without WAV files.

    Config keys (read from the config dict passed to __init__):
        audio_enabled           bool   master switch
        audio_volume            float  0.0–1.0  (stored for reference;
                                       winsound respects the Windows system
                                       volume – use the volume mixer to
                                       adjust playback level)
        audio_voice_init        bool   startup sound (init.wav)
        audio_sound_activate    bool   scanner-activated sound (activate.wav)
        audio_sound_deactivate  bool   scanner-deactivated sound (deactivate.wav)
        audio_sound_signal      bool   signal-detected sound (signal.wav)

    WAV file location:
        <app_dir>/sounds/init.wav
        <app_dir>/sounds/activate.wav
        <app_dir>/sounds/deactivate.wav
        <app_dir>/sounds/signal.wav
    """

    def __init__(self, config: dict):
        self._config   = config
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audio")

    # ------------------------------------------------------------------
    # Public play methods – all non-blocking
    # ------------------------------------------------------------------

    def play_init(self):
        """Play init.wav on app startup."""
        if not self._enabled() or not self._config.get("audio_voice_init", True):
            return
        self._executor.submit(self._play_wav, "init")

    def play_activate(self):
        """Play activate.wav when the scanner is activated."""
        if not self._enabled() or not self._config.get("audio_sound_activate", True):
            return
        self._executor.submit(self._play_wav, "activate")

    def play_deactivate(self):
        """Play deactivate.wav when the scanner is deactivated."""
        if not self._enabled() or not self._config.get("audio_sound_deactivate", True):
            return
        self._executor.submit(self._play_wav, "deactivate")

    def play_signal(self, mineral_name: str = ""):
        """Play signal.wav when a mineral signature is detected."""
        if not self._enabled() or not self._config.get("audio_sound_signal", False):
            return
        self._executor.submit(self._play_wav, "signal")

    def test_audio(self):
        """Play init → activate → deactivate in sequence (0.5 s gaps). For UI test buttons."""
        self._executor.submit(self._do_test_sequence)

    def set_volume(self, value: float):
        """Clamp value to [0.0, 1.0] and persist in config.

        Note: winsound has no programmatic volume control – use the Windows
        volume mixer to adjust playback level. This value is stored so it can
        be used if the backend changes in future.
        """
        self._config["audio_volume"] = max(0.0, min(1.0, float(value)))
        log.debug(
            "Volume setting stored in config (winsound has no "
            "programmatic volume control – use system volume)"
        )

    # ------------------------------------------------------------------
    # Private helpers – called inside the executor worker thread
    # ------------------------------------------------------------------

    def _enabled(self) -> bool:
        return bool(self._config.get("audio_enabled", True))

    def _get_sound_path(self, name: str) -> "Path | None":
        """Resolve name → sounds/name.wav.

        Search order:
          1. sys._MEIPASS/sounds/name.wav  (PyInstaller bundle)
          2. _BASE_DIR/sounds/name.wav     (normal Python install)
        Returns None if neither exists.
        """
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate = Path(meipass) / "sounds" / f"{name}.wav"
            if candidate.is_file():
                return candidate
        candidate = _BASE_DIR / "sounds" / f"{name}.wav"
        if candidate.is_file():
            return candidate
        return None

    def _play_wav(self, name: str):
        """Play sounds/name.wav via winsound.PlaySound.

        Falls back to winsound.Beep(1000, 100) if the WAV file is not found.
        winsound.SND_ASYNC is essential: without it PlaySound blocks the
        calling thread for the entire duration of the WAV file.
        """
        if not _HAS_WINSOUND:
            print("\a", end="", flush=True)
            return
        path = self._get_sound_path(name)
        if path:
            _winsound.PlaySound(
                str(path),
                _winsound.SND_FILENAME | _winsound.SND_ASYNC,
            )
        else:
            log.warning("Sound file not found: %s - using fallback beep", name)
            _winsound.Beep(1000, 100)

    def _do_test_sequence(self):
        self._play_wav("init")
        time.sleep(0.5)
        self._play_wav("activate")
        time.sleep(0.5)
        self._play_wav("deactivate")
