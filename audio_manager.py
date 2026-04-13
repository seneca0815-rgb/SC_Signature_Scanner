"""
audio_manager.py  -  SC Signature Reader / Vargo Dynamics
All audio output via WAV files with real volume control.

Volume is applied by scaling PCM samples with numpy before playback.
Sounds are played synchronously inside the single-worker executor thread
(PlaySound with SND_MEMORY), so they queue naturally and never overlap.
"""

import io
import logging
import sys
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

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
# WAV volume scaling
# ---------------------------------------------------------------------------

def _apply_volume(path: Path, volume: float) -> "bytes | None":
    """Read a WAV file, scale PCM samples by *volume* (0.0–1.0) and return
    the result as a WAV byte string suitable for winsound.SND_MEMORY.

    Supports 8-bit (unsigned) and 16-bit (signed) PCM WAVs.
    Returns None on any read/decode error so the caller can fall back.
    """
    try:
        with wave.open(str(path), "rb") as wf:
            params     = wf.getparams()
            raw_frames = wf.readframes(params.nframes)

        sampwidth = params.sampwidth

        if sampwidth == 2:                        # 16-bit signed PCM
            samples = np.frombuffer(raw_frames, dtype=np.int16)
            scaled  = np.clip(samples * volume, -32768, 32767).astype(np.int16)
        elif sampwidth == 1:                      # 8-bit unsigned PCM (centre=128)
            samples = np.frombuffer(raw_frames, dtype=np.uint8).astype(np.float32) - 128.0
            scaled  = np.clip(samples * volume, -128, 127).astype(np.int8)
            scaled  = (scaled.astype(np.int16) + 128).astype(np.uint8)
        else:
            # 32-bit float or other format: skip scaling, return None so
            # caller falls back to plain file playback
            return None

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf_out:
            wf_out.setparams(params)
            wf_out.writeframes(scaled.tobytes())
        return buf.getvalue()

    except Exception as exc:
        log.warning("Volume scaling failed for %s: %s", path.name, exc)
        return None


# ---------------------------------------------------------------------------
# AudioManager
# ---------------------------------------------------------------------------

class AudioManager:
    """
    Manages all audio output for SC Signature Reader.

    Sounds are loaded from WAV files in the sounds/ directory next to the
    executable (or inside the PyInstaller bundle). Volume is applied by
    scaling PCM samples before playback – the slider in the UI has real effect.
    If a WAV file is missing the method falls back to winsound.Beep.

    Config keys:
        audio_enabled           bool   master switch
        audio_volume            float  0.0–1.0  (default 0.5)
        audio_voice_init        bool   startup sound (init.wav)
        audio_sound_activate    bool   scanner-activated sound (activate.wav)
        audio_sound_deactivate  bool   scanner-deactivated sound (deactivate.wav)
        audio_sound_signal      bool   signal-detected sound (signal.wav)
    """

    def __init__(self, config: dict):
        self._config   = config
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audio")

    # ------------------------------------------------------------------
    # Public play methods – all non-blocking (submit to executor)
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
        """Play init -> activate -> deactivate in sequence (0.5 s gaps)."""
        self._executor.submit(self._do_test_sequence)

    def set_volume(self, value: float):
        """Clamp value to [0.0, 1.0] and persist in config.
        Volume takes effect immediately on the next sound played.
        """
        self._config["audio_volume"] = max(0.0, min(1.0, float(value)))

    # ------------------------------------------------------------------
    # Private helpers – run inside the executor worker thread
    # ------------------------------------------------------------------

    def _enabled(self) -> bool:
        return bool(self._config.get("audio_enabled", True))

    def _volume(self) -> float:
        return float(self._config.get("audio_volume", 0.5))

    def _get_sound_path(self, name: str) -> "Path | None":
        """Resolve name -> sounds/name.wav (PyInstaller bundle first)."""
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate = Path(meipass) / "sounds" / f"{name}.wav"
            if candidate.is_file():
                return candidate
        candidate = _BASE_DIR / "sounds" / f"{name}.wav"
        if candidate.is_file():
            return candidate
        return None

    def _apply_volume(self, path: Path) -> "bytes | None":
        """Delegate to module-level _apply_volume with current volume setting."""
        return _apply_volume(path, self._volume())

    def _play_wav(self, name: str):
        """Play sounds/name.wav with volume scaling.

        Uses winsound.PlaySound(data, SND_MEMORY) – synchronous inside the
        dedicated worker thread, so sounds queue naturally without overlapping.
        Falls back to Beep(1000, 100) when the WAV file is not found.
        """
        if not _HAS_WINSOUND:
            print("\a", end="", flush=True)
            return

        path = self._get_sound_path(name)
        if path:
            volume = self._volume()
            if volume == 0.0:
                return                          # muted – skip playback entirely
            data = self._apply_volume(path)
            if data is not None:
                _winsound.PlaySound(data, _winsound.SND_MEMORY)
            else:
                # Scaling failed – play file directly at system volume
                _winsound.PlaySound(str(path), _winsound.SND_FILENAME)
        else:
            log.warning("Sound file not found: %s - using fallback beep", name)
            _winsound.Beep(1000, 100)

    def _do_test_sequence(self):
        self._play_wav("init")
        time.sleep(0.5)
        self._play_wav("activate")
        time.sleep(0.5)
        self._play_wav("deactivate")
