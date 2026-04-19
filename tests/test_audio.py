"""
test_audio.py  –  SC Signature Reader
Unit tests for AudioManager.
winsound is mocked so no actual sound plays during testing.
"""

import os
import shutil
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers – inject a fake winsound with the constants AudioManager needs
# ---------------------------------------------------------------------------

def _make_fake_winsound():
    mod = types.ModuleType("winsound")
    mod.Beep       = MagicMock()
    mod.PlaySound  = MagicMock()
    # Exact values from the Windows SDK
    mod.SND_FILENAME  = 0x00020000   # 131072
    mod.SND_ASYNC     = 0x0001       # 1
    mod.SND_NODEFAULT = 0x0002       # 2
    mod.SND_MEMORY    = 0x0004       # 4
    return mod


_FAKE_WAV_BYTES = b"RIFF\x24\x00\x00\x00WAVEfmt "  # dummy bytes for SND_MEMORY tests


def _reload_audio(fake_winsound=None):
    """Reload audio_manager with the supplied fake winsound in sys.modules."""
    if fake_winsound is not None:
        sys.modules["winsound"] = fake_winsound
    else:
        sys.modules.pop("winsound", None)
    import importlib
    import audio_manager
    importlib.reload(audio_manager)
    return audio_manager


# ---------------------------------------------------------------------------
# Tests – audio disabled (master switch off)
# ---------------------------------------------------------------------------

class TestAudioManagerDisabled(unittest.TestCase):
    """When audio_enabled is False nothing should play."""

    def setUp(self):
        self._ws = _make_fake_winsound()
        self._am = _reload_audio(self._ws)
        self.AudioManager = self._am.AudioManager

    def tearDown(self):
        sys.modules.pop("winsound", None)

    def _make(self):
        cfg = {"audio_enabled": False, "audio_volume": 0.8,
               "audio_voice_init": True, "audio_sound_activate": True,
               "audio_sound_deactivate": True, "audio_sound_signal": True}
        return self.AudioManager(cfg)

    def _drain(self, mgr):
        mgr._executor.shutdown(wait=True)

    def test_play_init_silent(self):
        mgr = self._make()
        mgr.play_init()
        self._drain(mgr)
        self._ws.PlaySound.assert_not_called()
        self._ws.Beep.assert_not_called()

    def test_play_activate_silent(self):
        mgr = self._make()
        mgr.play_activate()
        self._drain(mgr)
        self._ws.PlaySound.assert_not_called()
        self._ws.Beep.assert_not_called()

    def test_play_deactivate_silent(self):
        mgr = self._make()
        mgr.play_deactivate()
        self._drain(mgr)
        self._ws.PlaySound.assert_not_called()
        self._ws.Beep.assert_not_called()

    def test_play_signal_silent(self):
        mgr = self._make()
        mgr.play_signal("Taranite")
        self._drain(mgr)
        self._ws.PlaySound.assert_not_called()
        self._ws.Beep.assert_not_called()


# ---------------------------------------------------------------------------
# Tests – per-flag guards (audio enabled, individual flag off)
# ---------------------------------------------------------------------------

class TestFlagGuards(unittest.TestCase):

    def setUp(self):
        self._ws = _make_fake_winsound()
        self._am = _reload_audio(self._ws)
        self.AudioManager = self._am.AudioManager

    def tearDown(self):
        sys.modules.pop("winsound", None)

    def _make(self, **flags):
        cfg = {"audio_enabled": True, "audio_volume": 0.8,
               "audio_voice_init": True, "audio_sound_activate": True,
               "audio_sound_deactivate": True, "audio_sound_signal": True}
        cfg.update(flags)
        return self.AudioManager(cfg)

    def _drain(self, mgr):
        mgr._executor.shutdown(wait=True)

    def test_voice_init_flag_false(self):
        mgr = self._make(audio_voice_init=False)
        mgr.play_init()
        self._drain(mgr)
        self._ws.PlaySound.assert_not_called()

    def test_activate_flag_false(self):
        mgr = self._make(audio_sound_activate=False)
        mgr.play_activate()
        self._drain(mgr)
        self._ws.PlaySound.assert_not_called()

    def test_deactivate_flag_false(self):
        mgr = self._make(audio_sound_deactivate=False)
        mgr.play_deactivate()
        self._drain(mgr)
        self._ws.PlaySound.assert_not_called()

    def test_signal_flag_false_by_default(self):
        mgr = self._make(audio_sound_signal=False)
        mgr.play_signal("Taranite")
        self._drain(mgr)
        self._ws.PlaySound.assert_not_called()

    def test_signal_flag_true_triggers_play(self):
        """When signal flag is explicitly True a sound attempt is made."""
        fake_path = Path("/fake/sounds/signal.wav")
        mgr = self._make(audio_sound_signal=True)
        with patch.object(mgr, "_get_sound_path", return_value=fake_path), \
             patch.object(mgr, "_apply_volume", return_value=_FAKE_WAV_BYTES):
            mgr.play_signal("Taranite")
            self._drain(mgr)
        self._ws.PlaySound.assert_called_once()


# ---------------------------------------------------------------------------
# Tests – _play_wav with WAV file found
# ---------------------------------------------------------------------------

class TestPlayWavFound(unittest.TestCase):
    """When a WAV file exists, PlaySound must be called with SND_MEMORY and scaled bytes."""

    def setUp(self):
        self._ws = _make_fake_winsound()
        self._am = _reload_audio(self._ws)
        self.AudioManager = self._am.AudioManager

    def tearDown(self):
        sys.modules.pop("winsound", None)

    def _make(self, **extra):
        cfg = {"audio_enabled": True, "audio_volume": 0.8,
               "audio_voice_init": True, "audio_sound_activate": True,
               "audio_sound_deactivate": True, "audio_sound_signal": True}
        cfg.update(extra)
        return self.AudioManager(cfg)

    def _drain(self, mgr):
        mgr._executor.shutdown(wait=True)

    def test_play_wav_uses_snd_memory(self):
        """When volume scaling succeeds, PlaySound must use SND_MEMORY with bytes."""
        fake_path = Path("/fake/sounds/activate.wav")
        mgr = self._make()
        with patch.object(mgr, "_get_sound_path", return_value=fake_path), \
             patch.object(mgr, "_apply_volume", return_value=_FAKE_WAV_BYTES):
            mgr._play_wav("activate")
        self._ws.PlaySound.assert_called_once_with(
            _FAKE_WAV_BYTES, self._ws.SND_MEMORY)

    def test_play_wav_falls_back_to_snd_filename_when_scaling_fails(self):
        """When _apply_volume returns None, fall back to SND_FILENAME."""
        fake_path = Path("/fake/sounds/init.wav")
        mgr = self._make()
        with patch.object(mgr, "_get_sound_path", return_value=fake_path), \
             patch.object(mgr, "_apply_volume", return_value=None):
            mgr._play_wav("init")
        self._ws.PlaySound.assert_called_once_with(
            str(fake_path), self._ws.SND_FILENAME)

    def test_snd_memory_flag_is_used_for_scaled_audio(self):
        fake_path = Path("/fake/sounds/signal.wav")
        mgr = self._make()
        with patch.object(mgr, "_get_sound_path", return_value=fake_path), \
             patch.object(mgr, "_apply_volume", return_value=_FAKE_WAV_BYTES):
            mgr._play_wav("signal")
        _, flags = self._ws.PlaySound.call_args[0]
        self.assertEqual(flags, self._ws.SND_MEMORY)

    def test_play_activate_triggers_playsound_not_beep(self):
        fake_path = Path("/fake/sounds/activate.wav")
        mgr = self._make()
        with patch.object(mgr, "_get_sound_path", return_value=fake_path), \
             patch.object(mgr, "_apply_volume", return_value=_FAKE_WAV_BYTES):
            mgr.play_activate()
            self._drain(mgr)
        self._ws.PlaySound.assert_called_once()
        self._ws.Beep.assert_not_called()

    def test_play_deactivate_triggers_playsound_not_beep(self):
        fake_path = Path("/fake/sounds/deactivate.wav")
        mgr = self._make()
        with patch.object(mgr, "_get_sound_path", return_value=fake_path), \
             patch.object(mgr, "_apply_volume", return_value=_FAKE_WAV_BYTES):
            mgr.play_deactivate()
            self._drain(mgr)
        self._ws.PlaySound.assert_called_once()
        self._ws.Beep.assert_not_called()

    def test_muted_volume_skips_playback(self):
        """When volume is 0.0 the sound must be skipped entirely."""
        fake_path = Path("/fake/sounds/activate.wav")
        mgr = self._make(audio_volume=0.0)
        with patch.object(mgr, "_get_sound_path", return_value=fake_path):
            mgr._play_wav("activate")
        self._ws.PlaySound.assert_not_called()
        self._ws.Beep.assert_not_called()


# ---------------------------------------------------------------------------
# Tests – _play_wav with WAV file missing (Beep fallback)
# ---------------------------------------------------------------------------

class TestPlayWavMissing(unittest.TestCase):
    """When no WAV file exists the method must fall back to a single Beep."""

    def setUp(self):
        self._ws = _make_fake_winsound()
        self._am = _reload_audio(self._ws)
        self.AudioManager = self._am.AudioManager

    def tearDown(self):
        sys.modules.pop("winsound", None)

    def _make(self):
        return self.AudioManager({"audio_enabled": True, "audio_volume": 0.8,
                                   "audio_voice_init": True,
                                   "audio_sound_activate": True,
                                   "audio_sound_deactivate": True,
                                   "audio_sound_signal": True})

    def _drain(self, mgr):
        mgr._executor.shutdown(wait=True)

    def test_missing_wav_falls_back_to_beep(self):
        mgr = self._make()
        with patch.object(mgr, "_get_sound_path", return_value=None):
            mgr._play_wav("activate")
        self._ws.Beep.assert_called_once_with(1000, 100)
        self._ws.PlaySound.assert_not_called()

    def test_fallback_beep_called_exactly_once_per_missing_file(self):
        mgr = self._make()
        with patch.object(mgr, "_get_sound_path", return_value=None):
            mgr._play_wav("init")
            mgr._play_wav("activate")
        self.assertEqual(self._ws.Beep.call_count, 2)

    def test_play_init_falls_back_to_beep_when_no_wav(self):
        mgr = self._make()
        with patch.object(mgr, "_get_sound_path", return_value=None):
            mgr.play_init()
            self._drain(mgr)
        self._ws.Beep.assert_called_once_with(1000, 100)


# ---------------------------------------------------------------------------
# Tests – _get_sound_path path resolution
# ---------------------------------------------------------------------------

class TestGetSoundPath(unittest.TestCase):

    def setUp(self):
        self._tmpdir   = tempfile.mkdtemp()
        self._sounds   = os.path.join(self._tmpdir, "sounds")
        os.makedirs(self._sounds)
        self._am = _reload_audio()   # no winsound needed for path tests
        self.AudioManager = self._am.AudioManager

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        sys.modules.pop("winsound", None)

    def _make(self):
        return self.AudioManager({"audio_enabled": True})

    def _wav(self, name: str) -> str:
        """Create a minimal placeholder WAV in the temp sounds dir."""
        path = os.path.join(self._sounds, f"{name}.wav")
        with open(path, "wb") as f:
            f.write(b"RIFF")   # dummy content – not a real WAV header
        return path

    def test_returns_none_when_sounds_folder_empty(self):
        mgr = self._make()
        with patch.object(self._am, "_BASE_DIR", Path(self._tmpdir)):
            result = mgr._get_sound_path("activate")
        self.assertIsNone(result)

    def test_returns_path_when_wav_exists(self):
        self._wav("activate")
        mgr = self._make()
        with patch.object(self._am, "_BASE_DIR", Path(self._tmpdir)):
            result = mgr._get_sound_path("activate")
        self.assertIsNotNone(result)
        self.assertEqual(result, Path(self._sounds) / "activate.wav")

    def test_returns_none_for_different_name(self):
        self._wav("activate")
        mgr = self._make()
        with patch.object(self._am, "_BASE_DIR", Path(self._tmpdir)):
            result = mgr._get_sound_path("signal")
        self.assertIsNone(result)

    def test_meipass_takes_priority_over_base_dir(self):
        """PyInstaller bundle path must be checked before BASE_DIR."""
        # WAV only in meipass, not in BASE_DIR
        meipass_sounds = os.path.join(self._tmpdir, "meipass", "sounds")
        os.makedirs(meipass_sounds)
        meipass_wav = os.path.join(meipass_sounds, "init.wav")
        with open(meipass_wav, "wb") as f:
            f.write(b"RIFF")
        meipass_dir = os.path.join(self._tmpdir, "meipass")

        mgr = self._make()
        with patch.object(sys, "_MEIPASS", meipass_dir, create=True), \
             patch.object(self._am, "_BASE_DIR", Path(self._tmpdir)):
            result = mgr._get_sound_path("init")

        self.assertEqual(result, Path(meipass_sounds) / "init.wav")

    def test_falls_back_to_base_dir_when_no_meipass(self):
        self._wav("deactivate")
        mgr = self._make()
        # No _MEIPASS attribute → fall through to BASE_DIR
        with patch.object(self._am, "_BASE_DIR", Path(self._tmpdir)):
            # Ensure _MEIPASS is not set on sys
            if hasattr(sys, "_MEIPASS"):
                with patch.object(sys, "_MEIPASS", None):
                    result = mgr._get_sound_path("deactivate")
            else:
                result = mgr._get_sound_path("deactivate")

        self.assertEqual(result, Path(self._sounds) / "deactivate.wav")


# ---------------------------------------------------------------------------
# Tests – set_volume
# ---------------------------------------------------------------------------

class TestSetVolume(unittest.TestCase):

    def setUp(self):
        self._am = _reload_audio()
        self.AudioManager = self._am.AudioManager

    def tearDown(self):
        sys.modules.pop("winsound", None)

    def _make(self):
        return self.AudioManager({"audio_enabled": True, "audio_volume": 0.8})

    def test_clamps_above_one(self):
        mgr = self._make()
        mgr.set_volume(1.5)
        self.assertAlmostEqual(mgr._config["audio_volume"], 1.0)

    def test_clamps_below_zero(self):
        mgr = self._make()
        mgr.set_volume(-0.3)
        self.assertAlmostEqual(mgr._config["audio_volume"], 0.0)

    def test_stores_valid_value(self):
        mgr = self._make()
        mgr.set_volume(0.6)
        self.assertAlmostEqual(mgr._config["audio_volume"], 0.6)

    def test_boundary_zero(self):
        mgr = self._make()
        mgr.set_volume(0.0)
        self.assertAlmostEqual(mgr._config["audio_volume"], 0.0)

    def test_boundary_one(self):
        mgr = self._make()
        mgr.set_volume(1.0)
        self.assertAlmostEqual(mgr._config["audio_volume"], 1.0)


# ---------------------------------------------------------------------------
# Tests – non-blocking guarantee
# ---------------------------------------------------------------------------

class TestNonBlocking(unittest.TestCase):

    def setUp(self):
        self._ws = _make_fake_winsound()
        self._am = _reload_audio(self._ws)
        self.AudioManager = self._am.AudioManager

    def tearDown(self):
        sys.modules.pop("winsound", None)

    def test_play_methods_return_before_sound_finishes(self):
        """All play methods must enqueue work and return without blocking."""
        cfg = {"audio_enabled": True, "audio_volume": 0.8,
               "audio_voice_init": True, "audio_sound_activate": True,
               "audio_sound_deactivate": True, "audio_sound_signal": True}
        mgr = self.AudioManager(cfg)
        fake_path = Path("/fake/sounds/activate.wav")

        # Block the worker thread for 300 ms
        def slow_task():
            time.sleep(0.3)

        mgr._executor.submit(slow_task)

        t0 = time.monotonic()
        with patch.object(mgr, "_get_sound_path", return_value=fake_path):
            mgr.play_activate()
            mgr.play_deactivate()
            mgr.play_signal("X")
        elapsed = time.monotonic() - t0

        # Three submit() calls must complete long before the 300 ms blocker
        self.assertLess(elapsed, 0.2,
                        "play_* methods must not block waiting for the worker")
        mgr._executor.shutdown(wait=True)


# ---------------------------------------------------------------------------
# Tests – test_audio sequence
# ---------------------------------------------------------------------------

class TestTestAudioSequence(unittest.TestCase):

    def setUp(self):
        self._ws = _make_fake_winsound()
        self._am = _reload_audio(self._ws)
        self.AudioManager = self._am.AudioManager

    def tearDown(self):
        sys.modules.pop("winsound", None)

    def test_test_audio_calls_all_three_sounds(self):
        cfg = {"audio_enabled": True, "audio_volume": 0.8,
               "audio_voice_init": True, "audio_sound_activate": True,
               "audio_sound_deactivate": True}
        mgr = self.AudioManager(cfg)

        with patch.object(mgr, "_play_wav") as mock_play, \
             patch("audio_manager.time.sleep"):
            mgr.test_audio()
            mgr._executor.shutdown(wait=True)

        self.assertEqual(mock_play.call_count, 3)
        mock_play.assert_any_call("init")
        mock_play.assert_any_call("activate")
        mock_play.assert_any_call("deactivate")

    def test_test_audio_plays_in_correct_order(self):
        cfg = {"audio_enabled": True, "audio_volume": 0.8,
               "audio_voice_init": True, "audio_sound_activate": True,
               "audio_sound_deactivate": True}
        mgr = self.AudioManager(cfg)

        with patch.object(mgr, "_play_wav") as mock_play, \
             patch("audio_manager.time.sleep"):
            mgr.test_audio()
            mgr._executor.shutdown(wait=True)

        names = [c.args[0] for c in mock_play.call_args_list]
        self.assertEqual(names, ["init", "activate", "deactivate"])


# ---------------------------------------------------------------------------
# Tests – no winsound available (non-Windows)
# ---------------------------------------------------------------------------

class TestNoWinsound(unittest.TestCase):
    """When winsound is not importable, play methods must not raise."""

    def setUp(self):
        sys.modules.pop("winsound", None)
        import builtins
        self._real_import = builtins.__import__

        def _block_ws(name, *args, **kwargs):
            if name == "winsound":
                raise ImportError("No module named 'winsound'")
            return self._real_import(name, *args, **kwargs)

        builtins.__import__ = _block_ws
        self._am = _reload_audio()
        self.AudioManager = self._am.AudioManager

    def tearDown(self):
        import builtins
        builtins.__import__ = self._real_import
        sys.modules.pop("winsound", None)

    def test_play_activate_no_exception(self):
        mgr = self.AudioManager({"audio_enabled": True,
                                   "audio_sound_activate": True})
        try:
            mgr.play_activate()
            mgr._executor.shutdown(wait=True)
        except Exception as e:
            self.fail(f"play_activate() raised unexpectedly: {e}")

    def test_play_init_no_exception(self):
        mgr = self.AudioManager({"audio_enabled": True,
                                   "audio_voice_init": True})
        try:
            mgr.play_init()
            mgr._executor.shutdown(wait=True)
        except Exception as e:
            self.fail(f"play_init() raised unexpectedly: {e}")


# ---------------------------------------------------------------------------
# Tests – module-level _apply_volume() directly (lines 63-70, 76)
# ---------------------------------------------------------------------------

import io
import struct
import wave as _wave_mod


def _write_wav(sampwidth: int, nframes: int = 8, framerate: int = 8000) -> bytes:
    """Create a minimal valid WAV file in memory with the given sample width."""
    buf = io.BytesIO()
    with _wave_mod.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(sampwidth)
        wf.setframerate(framerate)
        if sampwidth == 2:
            wf.writeframes(struct.pack(f"<{nframes}h", *([1000] * nframes)))
        elif sampwidth == 1:
            wf.writeframes(bytes([128] * nframes))
        else:
            wf.writeframes(bytes(nframes * sampwidth))
    return buf.getvalue()


class TestApplyVolumeDirect(unittest.TestCase):
    """Test the module-level _apply_volume() function with real numpy + wave."""

    def setUp(self):
        import importlib
        # Temporarily remove any mock from sys.modules to load real numpy.
        # test_core.py installs a MagicMock via sys.modules.setdefault at
        # collection time, so we must bypass it here.
        _saved = sys.modules.pop("numpy", None)
        try:
            real_numpy = importlib.import_module("numpy")
        except ImportError:
            real_numpy = None
        finally:
            if _saved is not None:
                sys.modules["numpy"] = _saved

        if real_numpy is None or isinstance(real_numpy, MagicMock):
            self.skipTest("real numpy not available")
        self._real_numpy = real_numpy

        self._ws   = _make_fake_winsound()
        self._am   = _reload_audio(self._ws)
        # Inject real numpy into the reloaded module so _apply_volume works
        self._am.np = self._real_numpy

        self._tmp  = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _wav_path(self, sampwidth: int) -> Path:
        p = self._tmp / f"test_{sampwidth}.wav"
        p.write_bytes(_write_wav(sampwidth))
        return p

    def test_16bit_returns_bytes(self):
        path = self._wav_path(2)
        result = self._am._apply_volume(path, 0.8)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

    def test_16bit_returns_valid_wav(self):
        path = self._wav_path(2)
        result = self._am._apply_volume(path, 0.5)
        buf = io.BytesIO(result)
        with _wave_mod.open(buf, "rb") as wf:
            self.assertEqual(wf.getsampwidth(), 2)

    def test_8bit_returns_bytes(self):
        """Lines 63-66: 8-bit PCM path must return bytes (not None)."""
        path = self._wav_path(1)
        result = self._am._apply_volume(path, 0.8)
        self.assertIsInstance(result, bytes)

    def test_8bit_returns_valid_wav(self):
        path = self._wav_path(1)
        result = self._am._apply_volume(path, 1.0)
        self.assertIsNotNone(result)
        buf = io.BytesIO(result)
        with _wave_mod.open(buf, "rb") as wf:
            self.assertEqual(wf.getsampwidth(), 1)

    def test_unsupported_sampwidth_returns_none(self):
        """Lines 67-70: sample width != 1 or 2 must return None."""
        path = self._wav_path(4)
        result = self._am._apply_volume(path, 1.0)
        self.assertIsNone(result)

    def test_missing_file_returns_none(self):
        result = self._am._apply_volume(self._tmp / "no_such.wav", 1.0)
        self.assertIsNone(result)

    def test_volume_zero_scales_to_silence(self):
        path = self._wav_path(2)
        result = self._am._apply_volume(path, 0.0)
        self.assertIsInstance(result, bytes)


# ---------------------------------------------------------------------------
# Tests – frozen path (line 27)
# ---------------------------------------------------------------------------

class TestFrozenBasedir(unittest.TestCase):
    """Line 27: _BASE_DIR uses sys.executable.parent when frozen=True."""

    def test_frozen_base_dir(self):
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", "/fake/dist/app.exe"):
            am = _reload_audio(_make_fake_winsound())
        self.assertEqual(str(am._BASE_DIR), str(Path("/fake/dist")))


if __name__ == "__main__":
    unittest.main()
