"""
generate_sounds.py  –  SC Signature Reader / Vargo Dynamics
Layers sci-fi sound effects on top of the existing voice/speech WAV samples.

Run once to (re)create all files in sounds/:
    python generate_sounds.py

The script reads each original WAV, generates an appropriate effect via
numpy FM synthesis, and mixes both together. The voice always stays at
full level; the effect level is tunable per sound via EFFECT_LEVEL.

Requires: numpy  (already a runtime dependency)
"""

import wave
import io
from pathlib import Path

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

SOUNDS_DIR   = Path(__file__).parent / "sounds"
SAMPLE_RATE  = 44100
EFFECT_LEVEL = 0.55   # how loud the effect is relative to the voice (0.0–1.0)


# ---------------------------------------------------------------------------
# WAV I/O helpers
# ---------------------------------------------------------------------------

def _read_wav(path: Path) -> tuple[np.ndarray, int, int]:
    """Return (float64 signal [-1,1], sample_rate, n_channels)."""
    with wave.open(str(path), "rb") as wf:
        sr      = wf.getframerate()
        sw      = wf.getsampwidth()
        ch      = wf.getnchannels()
        frames  = wf.readframes(wf.getnframes())
    dtype = np.int16 if sw == 2 else np.int8
    pcm   = np.frombuffer(frames, dtype=dtype).astype(np.float64)
    if sw == 2:
        pcm /= 32767.0
    else:
        pcm = (pcm - 128) / 127.0
    return pcm, sr, ch


def _write_wav(path: Path, signal: np.ndarray, sample_rate: int = SAMPLE_RATE,
               channels: int = 1):
    """Write a float64 [-1,1] array as 16-bit mono/stereo WAV."""
    # Normalise – leave headroom so clipping never happens
    mx = np.max(np.abs(signal))
    if mx > 0:
        signal = signal / mx * 0.92
    pcm = (signal * 32767).astype(np.int16).tobytes()
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    print(f"  wrote {path.name}  ({len(pcm) // 2} samples @ {sample_rate} Hz)")


def _resample_to(signal: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """Crude linear-interpolation resampling (good enough for short fx)."""
    if src_sr == dst_sr:
        return signal
    ratio   = dst_sr / src_sr
    new_len = int(len(signal) * ratio)
    old_idx = np.linspace(0, len(signal) - 1, new_len)
    return np.interp(old_idx, np.arange(len(signal)), signal)


def _to_mono(signal: np.ndarray, channels: int) -> np.ndarray:
    """Convert interleaved multi-channel signal to mono."""
    if channels == 1:
        return signal
    return signal.reshape(-1, channels).mean(axis=1)


def _mix(voice: np.ndarray, effect: np.ndarray,
         effect_level: float = EFFECT_LEVEL) -> np.ndarray:
    """Mix voice (full level) + effect (scaled) to the same length."""
    n = max(len(voice), len(effect))
    out = np.zeros(n)
    out[:len(voice)]  += voice
    out[:len(effect)] += effect * effect_level
    return out


# ---------------------------------------------------------------------------
# Effect synthesis helpers
# ---------------------------------------------------------------------------

def _sine(freq_arr: np.ndarray) -> np.ndarray:
    phase = np.cumsum(freq_arr / SAMPLE_RATE) * 2 * np.pi
    return np.sin(phase)


def _freq_sweep(f0: float, f1: float, n: int,
                curve: str = "exp") -> np.ndarray:
    t = np.linspace(0, 1, n)
    if curve == "exp" and f0 > 0 and f1 > 0:
        return f0 * (f1 / f0) ** t
    return np.linspace(f0, f1, n)


def _noise_burst(n: int, color: str = "white") -> np.ndarray:
    """Generate a noise burst. color = 'white' | 'pink'."""
    noise = np.random.default_rng(42).standard_normal(n)
    if color == "pink":
        # Approximate pink noise: low-pass-ish roll-off via cumsum + correct
        noise = np.cumsum(noise)
        noise -= noise.mean()
        noise /= (np.max(np.abs(noise)) + 1e-9)
    return noise


def _env_adsr(n: int, attack: float, decay: float,
              sustain_level: float, release: float) -> np.ndarray:
    """ADSR amplitude envelope (times in seconds)."""
    a = int(attack  * SAMPLE_RATE)
    d = int(decay   * SAMPLE_RATE)
    r = int(release * SAMPLE_RATE)
    s = max(0, n - a - d - r)
    env = np.concatenate([
        np.linspace(0, 1,             a) if a else [],
        np.linspace(1, sustain_level, d) if d else [],
        np.full(s, sustain_level)        if s else [],
        np.linspace(sustain_level, 0, r) if r else [],
    ])
    # Pad / trim to exactly n
    if len(env) < n:
        env = np.pad(env, (0, n - len(env)))
    return env[:n]


# ---------------------------------------------------------------------------
# Per-sound effect generators
# ---------------------------------------------------------------------------

def _fx_init(n_voice: int) -> np.ndarray:
    """
    Power-up effect for init.wav:
    Layered noise burst + rising frequency sweep, timed to feel like the
    scanner is booting while the voice speaks.
    """
    sr   = SAMPLE_RATE
    n    = max(n_voice, int(1.4 * sr))

    # 1) Pink noise sweep filtered with a rising amplitude envelope
    noise  = _noise_burst(n, color="pink")
    env_n  = _env_adsr(n, 0.05, 0.6, 0.0, 0.4)
    noise *= env_n

    # 2) Rising sweep 80 Hz → 1 200 Hz with FM warble
    n_sweep   = int(0.7 * sr)
    f_sweep   = _freq_sweep(80, 1200, n_sweep, curve="exp")
    warble_t  = np.linspace(0, n_sweep / sr, n_sweep)
    f_sweep  += 20 * np.sin(2 * np.pi * 6 * warble_t)  # 6 Hz warble ±20 Hz
    sweep     = _sine(f_sweep)
    env_s     = _env_adsr(n_sweep, 0.01, 0.3, 0.5, 0.3)
    sweep    *= env_s * 0.6

    # 3) Confirm ping at the end
    n_ping  = int(0.12 * sr)
    ping    = np.sin(2 * np.pi * 1600 / sr * np.arange(n_ping))
    ping   *= _env_adsr(n_ping, 0.005, 0.02, 0.0, 0.09)
    ping_start = max(0, n - n_ping - int(0.05 * sr))

    fx = np.zeros(n)
    fx         += noise * 0.4
    fx[:n_sweep] += sweep
    fx[ping_start:ping_start + n_ping] += ping

    return fx


def _fx_activate(n_voice: int) -> np.ndarray:
    """
    Rising sweep 400 Hz → 2 200 Hz for activate.wav.
    Short and crisp, punches in at the start of the voice.
    """
    sr = SAMPLE_RATE
    n  = max(n_voice, int(0.30 * sr))

    n_sweep = int(0.22 * sr)
    f_sweep = _freq_sweep(400, 2200, n_sweep, curve="exp")
    sweep   = _sine(f_sweep)
    env     = _env_adsr(n_sweep, 0.008, 0.05, 0.6, 0.16)
    sweep  *= env

    fx = np.zeros(n)
    fx[:n_sweep] += sweep
    return fx


def _fx_deactivate(n_voice: int) -> np.ndarray:
    """
    Falling sweep 2 200 Hz → 300 Hz for deactivate.wav.
    Mirror image of activate – brief power-down whine.
    """
    sr = SAMPLE_RATE
    n  = max(n_voice, int(0.30 * sr))

    n_sweep = int(0.22 * sr)
    f_sweep = _freq_sweep(2200, 300, n_sweep, curve="exp")
    sweep   = _sine(f_sweep)
    env     = _env_adsr(n_sweep, 0.005, 0.03, 0.7, 0.18)
    sweep  *= env

    fx = np.zeros(n)
    fx[:n_sweep] += sweep
    return fx


def _fx_signal(n_voice: int) -> np.ndarray:
    """
    Lock-on double-ping for signal.wav:
    Short pre-ping at 1 200 Hz, main ping at 1 800 Hz with subtle overtone.
    Plays before / alongside the voice.
    """
    sr = SAMPLE_RATE
    n  = max(n_voice, int(0.50 * sr))

    def _ping(freq: float, dur: float, overtone: float = 0.0) -> np.ndarray:
        ns = int(dur * sr)
        t  = np.arange(ns)
        s  = np.sin(2 * np.pi * freq / sr * t)
        if overtone:
            s += overtone * np.sin(2 * np.pi * freq * 2 / sr * t)
        return s * _env_adsr(ns, 0.005, 0.025, 0.0, dur - 0.03)

    pre  = _ping(1200, 0.07)
    main = _ping(1800, 0.13, overtone=0.20)

    gap_pre  = int(0.0  * sr)
    gap_mid  = int(0.04 * sr)

    fx = np.zeros(n)
    p  = gap_pre
    fx[p:p + len(pre)]  += pre;  p += len(pre) + gap_mid
    fx[p:p + len(main)] += main

    return fx


# ---------------------------------------------------------------------------
# Per-file processing
# ---------------------------------------------------------------------------

_RECIPES = {
    "init.wav":       _fx_init,
    "activate.wav":   _fx_activate,
    "deactivate.wav": _fx_deactivate,
    "signal.wav":     _fx_signal,
}


def process(name: str):
    path = SOUNDS_DIR / name
    if not path.exists():
        print(f"  SKIP {name} – file not found")
        return

    voice_raw, src_sr, ch = _read_wav(path)
    voice = _to_mono(voice_raw, ch)

    # Resample voice to SAMPLE_RATE if needed
    if src_sr != SAMPLE_RATE:
        voice = _resample_to(voice, src_sr, SAMPLE_RATE)

    fx_fn  = _RECIPES[name]
    effect = fx_fn(len(voice))

    mixed = _mix(voice, effect)
    _write_wav(path, mixed)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not _HAS_NUMPY:
        print("ERROR: numpy is required. Install with: pip install numpy")
        return

    print(f"Layering sci-fi effects onto voice samples in {SOUNDS_DIR}/")
    for name in _RECIPES:
        process(name)
    print("Done.")


if __name__ == "__main__":
    main()
