"""
audio_manager.py  –  SC Signature Reader / Vargo Dynamics
All audio output: TTS announcements via pyttsx3, tones via winsound.
All playback runs in a single-worker ThreadPoolExecutor so sounds
play in sequence and never block the UI or scan loop.
"""

import platform
import time
from concurrent.futures import ThreadPoolExecutor

# ---------------------------------------------------------------------------
# Optional imports – graceful no-ops on missing libs or non-Windows
# ---------------------------------------------------------------------------

_WINDOWS = platform.system() == "Windows"

try:
    import winsound as _winsound
    _HAS_WINSOUND = True
except ImportError:
    _HAS_WINSOUND = False

_pyttsx3 = None          # lazy-loaded on first TTS use
_TTS_WARNED = False      # print import warning only once


def _get_tts():
    """Lazily import and return the pyttsx3 module (not an engine instance)."""
    global _pyttsx3, _TTS_WARNED
    if _pyttsx3 is not None:
        return _pyttsx3
    try:
        import pyttsx3 as _mod
        _pyttsx3 = _mod
        return _pyttsx3
    except ImportError:
        if not _TTS_WARNED:
            print("[audio] pyttsx3 not installed – TTS will fall back to a beep. "
                  "Install with:  pip install pyttsx3")
            _TTS_WARNED = True
        return None


# ---------------------------------------------------------------------------
# AudioManager
# ---------------------------------------------------------------------------

class AudioManager:
    """
    Manages all audio output for SC Signature Reader.

    Config keys (read from the config dict passed to __init__):
        audio_enabled           bool   master switch
        audio_volume            float  0.0–1.0
        audio_voice_init        bool   startup TTS announcement
        audio_sound_activate    bool   scanner-activated beep
        audio_sound_deactivate  bool   scanner-deactivated beep
        audio_sound_signal      bool   signal-detected beep
    """

    def __init__(self, config: dict):
        self._config   = config
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audio")
        # pyttsx3 engine – created lazily on first TTS call inside the worker thread
        self._tts_engine = None

    # ------------------------------------------------------------------
    # Public play methods – all non-blocking
    # ------------------------------------------------------------------

    def play_init(self):
        """TTS: 'Vargo Dynamics Scanner online.' – if audio_voice_init enabled."""
        if not self._enabled() or not self._config.get("audio_voice_init", True):
            return
        self._executor.submit(self._do_tts, "Vargo Dynamics Scanner online.")

    def play_activate(self):
        """Ascending two-tone beep: 800 Hz → 1200 Hz, 80 ms each."""
        if not self._enabled() or not self._config.get("audio_sound_activate", True):
            return
        self._executor.submit(self._do_beep_sequence,
                               [(800, 80), (1200, 80)])

    def play_deactivate(self):
        """Descending two-tone beep: 1200 Hz → 800 Hz, 80 ms each."""
        if not self._enabled() or not self._config.get("audio_sound_deactivate", True):
            return
        self._executor.submit(self._do_beep_sequence,
                               [(1200, 80), (800, 80)])

    def play_signal(self, mineral_name: str = ""):
        """Single short beep (1000 Hz, 100 ms) when a signal is detected."""
        if not self._enabled() or not self._config.get("audio_sound_signal", False):
            return
        self._executor.submit(self._do_beep, 1000, 100)

    def test_audio(self):
        """Play init + activate + deactivate in sequence (0.5 s gaps). For UI test buttons."""
        self._executor.submit(self._do_test_sequence)

    def set_volume(self, value: float):
        """Clamp value to [0.0, 1.0], store in config."""
        self._config["audio_volume"] = max(0.0, min(1.0, float(value)))

    # ------------------------------------------------------------------
    # Private helpers – run inside the executor worker thread
    # ------------------------------------------------------------------

    def _enabled(self) -> bool:
        return bool(self._config.get("audio_enabled", True))

    def _volume(self) -> float:
        return float(self._config.get("audio_volume", 0.8))

    def _do_beep(self, freq: int, duration_ms: int):
        if _HAS_WINSOUND:
            _winsound.Beep(freq, duration_ms)
        else:
            # Non-Windows fallback: terminal bell
            print("\a", end="", flush=True)

    def _do_beep_sequence(self, tones: list):
        for freq, duration_ms in tones:
            self._do_beep(freq, duration_ms)

    def _do_tts(self, text: str):
        mod = _get_tts()
        if mod is None:
            # TTS unavailable – play a single beep as substitute
            self._do_beep(1000, 120)
            return
        try:
            engine = mod.init()
            vol    = self._volume()
            engine.setProperty("volume", vol)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as exc:
            print(f"[audio] TTS error: {exc}")

    def _do_test_sequence(self):
        self._do_tts("Vargo Dynamics Scanner online.")
        time.sleep(0.5)
        self._do_beep_sequence([(800, 80), (1200, 80)])
        time.sleep(0.5)
        self._do_beep_sequence([(1200, 80), (800, 80)])
