"""
generate_sounds.py  –  SC Signature Reader / Vargo Dynamics
Generates sci-fi WAV audio files via numpy FM synthesis.

Run once to (re)create all files in sounds/:
    python generate_sounds.py

Requires: numpy  (already a runtime dependency)
"""

import wave
import struct
import math
from pathlib import Path

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    print("numpy not found – falling back to pure-Python math")

SOUNDS_DIR  = Path(__file__).parent / "sounds"
SAMPLE_RATE = 44100
DTYPE_MAX   = 32767  # 16-bit signed PCM peak


# ---------------------------------------------------------------------------
# Synthesis helpers
# ---------------------------------------------------------------------------

def _envelope(n: int, attack: float, decay: float, sustain: float,
               release: float, sustain_level: float = 0.8) -> "np.ndarray":
    """ADSR amplitude envelope, all times in seconds."""
    a = int(attack   * SAMPLE_RATE)
    d = int(decay    * SAMPLE_RATE)
    s = int(sustain  * SAMPLE_RATE)
    r = int(release  * SAMPLE_RATE)
    total = a + d + s + r

    env = np.zeros(total)
    env[:a]            = np.linspace(0, 1, a)
    env[a:a+d]         = np.linspace(1, sustain_level, d)
    env[a+d:a+d+s]     = sustain_level
    env[a+d+s:]        = np.linspace(sustain_level, 0, r)
    # Pad or trim to exactly n samples
    if len(env) < n:
        env = np.pad(env, (0, n - len(env)))
    return env[:n]


def _sine(freq_arr: "np.ndarray") -> "np.ndarray":
    """Sine wave from an instantaneous-frequency array (Hz)."""
    phase = np.cumsum(freq_arr / SAMPLE_RATE) * 2 * math.pi
    return np.sin(phase)


def _freq_sweep(f_start: float, f_end: float, n: int,
                curve: str = "linear") -> "np.ndarray":
    """Return an instantaneous-frequency array sweeping from f_start to f_end."""
    t = np.linspace(0, 1, n)
    if curve == "exp":
        return f_start * (f_end / f_start) ** t
    elif curve == "log":
        return f_start + (f_end - f_start) * np.log1p(t * (math.e - 1))
    else:
        return np.linspace(f_start, f_end, n)


def _to_pcm16(signal: "np.ndarray", peak: float = 0.85) -> bytes:
    """Normalise and convert float64 → signed int16 PCM bytes."""
    mx = np.max(np.abs(signal))
    if mx > 0:
        signal = signal / mx * peak
    return (signal * DTYPE_MAX).astype(np.int16).tobytes()


def _write_wav(path: Path, pcm: bytes, channels: int = 1):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    print(f"  wrote {path.name}  ({len(pcm)//2} samples)")


# ---------------------------------------------------------------------------
# Sound definitions
# ---------------------------------------------------------------------------

def make_init(path: Path):
    """
    Power-up sequence (~1.4 s):
    • Low hum sweeps 90 Hz → 1 100 Hz  (0.6 s, exp curve)
    • Brief silence gap
    • Two confirm pings: 1 600 Hz + 2 200 Hz  (80 ms each)
    • Harmonic tail 1 100 Hz fade out  (0.3 s)
    """
    sr = SAMPLE_RATE

    # --- sweep phase ---
    n_sweep = int(0.6 * sr)
    f_sweep = _freq_sweep(90, 1100, n_sweep, curve="exp")
    # FM modulation: mod depth grows from 0 to 30 Hz
    mod_depth = np.linspace(0, 30, n_sweep)
    mod_freq  = np.full(n_sweep, 8.0)   # 8 Hz warble
    fm_phase  = np.cumsum(mod_freq / sr) * 2 * math.pi
    f_sweep   = f_sweep + mod_depth * np.sin(fm_phase)
    sweep     = _sine(f_sweep)
    env_sweep = np.linspace(0.2, 1.0, n_sweep) ** 1.5
    sweep    *= env_sweep

    # --- gap ---
    gap = np.zeros(int(0.04 * sr))

    # --- confirm pings ---
    def _ping(freq, dur):
        n = int(dur * sr)
        s = np.sin(2 * math.pi * freq / sr * np.arange(n))
        env = _envelope(n, 0.005, 0.02, 0.0, dur - 0.025)
        return s * env

    ping1 = _ping(1600, 0.08)
    ping2 = _ping(2200, 0.10)
    ping_gap = np.zeros(int(0.03 * sr))

    # --- harmonic tail ---
    n_tail = int(0.3 * sr)
    tail   = np.sin(2 * math.pi * 1100 / sr * np.arange(n_tail))
    tail  *= np.linspace(0.5, 0.0, n_tail)

    signal = np.concatenate([sweep, gap, ping1, ping_gap, ping2, tail])
    _write_wav(path, _to_pcm16(signal))


def make_activate(path: Path):
    """
    Scanner ON  (~0.28 s):
    Rising exponential sweep 500 Hz → 2 400 Hz, short crisp attack.
    """
    sr    = SAMPLE_RATE
    n     = int(0.28 * sr)
    freqs = _freq_sweep(500, 2400, n, curve="exp")
    sig   = _sine(freqs)
    # AM: quick rise then hold
    env   = np.concatenate([
        np.linspace(0, 1, int(0.04 * sr)),
        np.ones(n - int(0.04 * sr) - int(0.06 * sr)),
        np.linspace(1, 0, int(0.06 * sr)),
    ])
    _write_wav(path, _to_pcm16(sig * env[:n]))


def make_deactivate(path: Path):
    """
    Scanner OFF  (~0.28 s):
    Falling exponential sweep 2 400 Hz → 500 Hz, mirror of activate.
    """
    sr    = SAMPLE_RATE
    n     = int(0.28 * sr)
    freqs = _freq_sweep(2400, 500, n, curve="exp")
    sig   = _sine(freqs)
    env   = np.concatenate([
        np.linspace(0, 1, int(0.02 * sr)),
        np.ones(n - int(0.02 * sr) - int(0.10 * sr)),
        np.linspace(1, 0, int(0.10 * sr)),
    ])
    _write_wav(path, _to_pcm16(sig * env[:n]))


def make_signal(path: Path):
    """
    Target locked  (~0.45 s):
    Two pings – a short pre-ping (1 200 Hz, 70 ms) followed by the main
    ping (1 800 Hz, 120 ms) with a faint harmonic overtone at 3 600 Hz.
    """
    sr = SAMPLE_RATE

    def _ping(freq, dur, overtone_ratio=0.0):
        n   = int(dur * sr)
        t   = np.arange(n)
        s   = np.sin(2 * math.pi * freq / sr * t)
        if overtone_ratio:
            s += overtone_ratio * np.sin(2 * math.pi * (freq * 2) / sr * t)
        env = _envelope(n, 0.006, 0.03, 0.0, dur - 0.036)
        return s * env[:n]

    pre  = _ping(1200, 0.07)
    gap  = np.zeros(int(0.04 * sr))
    main = _ping(1800, 0.12, overtone_ratio=0.25)
    tail = np.zeros(int(0.22 * sr))

    signal = np.concatenate([pre, gap, main, tail])
    _write_wav(path, _to_pcm16(signal))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not _HAS_NUMPY:
        print("ERROR: numpy is required. Install with: pip install numpy")
        return

    SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating sounds in {SOUNDS_DIR}/")

    make_init(      SOUNDS_DIR / "init.wav")
    make_activate(  SOUNDS_DIR / "activate.wav")
    make_deactivate(SOUNDS_DIR / "deactivate.wav")
    make_signal(    SOUNDS_DIR / "signal.wav")

    print("Done.")


if __name__ == "__main__":
    main()
