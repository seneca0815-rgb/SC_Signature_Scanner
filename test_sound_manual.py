"""
test_sound_manual.py  –  quick standalone audio test
Plays each AudioManager sound in sequence so you can verify
beep fallbacks (and WAV files once you drop them into sounds/).
Run from the project root:  python test_sound_manual.py
"""

import time
from pathlib import Path
from audio_manager import AudioManager

BASE    = Path(__file__).parent
SOUNDS  = BASE / "sounds"
WAVS    = list(SOUNDS.glob("*.wav"))

cfg = {
    "audio_enabled":          True,
    "audio_volume":           0.8,
    "audio_voice_init":       True,
    "audio_sound_activate":   True,
    "audio_sound_deactivate": True,
    "audio_sound_signal":     True,
}

am = AudioManager(cfg)

if WAVS:
    print(f"WAV files found in sounds/: {[w.name for w in WAVS]}")
else:
    print("No WAV files in sounds/ - will use beep fallback for each sound.")
    print("Drop init.wav / activate.wav / deactivate.wav / signal.wav into sounds/ to test WAVs.\n")

print("--- play_init        (init.wav / beep fallback)")
am.play_init()
time.sleep(1.2)

print("--- play_activate    (activate.wav / beep fallback)")
am.play_activate()
time.sleep(1.2)

print("--- play_deactivate  (deactivate.wav / beep fallback)")
am.play_deactivate()
time.sleep(1.2)

print("--- play_signal      (signal.wav / beep fallback)")
am.play_signal("Taranite")
time.sleep(1.2)

print("\n--- test_audio() sequence (init -> activate -> deactivate, 0.5 s gaps)")
am.test_audio()
time.sleep(3.5)

am._executor.shutdown(wait=True)
print("\nDone.")
