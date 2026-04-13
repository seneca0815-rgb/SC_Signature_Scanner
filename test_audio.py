"""
test_audio.py  –  SC Signature Reader
Unit tests for AudioManager.
All winsound.Beep and pyttsx3 calls are mocked so no actual sound plays.
"""

import sys
import time
import types
import unittest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers to inject/remove fake winsound / pyttsx3 in sys.modules
# ---------------------------------------------------------------------------

def _make_fake_winsound():
    mod = types.ModuleType("winsound")
    mod.Beep = MagicMock()
    return mod


def _make_fake_pyttsx3():
    engine_mock = MagicMock()
    mod = types.ModuleType("pyttsx3")
    mod.init = MagicMock(return_value=engine_mock)
    return mod, engine_mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAudioManagerDisabled(unittest.TestCase):
    """When audio_enabled is False, no beeps or TTS should fire."""

    def setUp(self):
        self._fake_ws = _make_fake_winsound()
        self._fake_pyttsx3, self._tts_engine = _make_fake_pyttsx3()
        sys.modules["winsound"] = self._fake_ws
        sys.modules["pyttsx3"] = self._fake_pyttsx3
        # Reload to pick up mocked modules
        import importlib
        import audio_manager
        importlib.reload(audio_manager)
        from audio_manager import AudioManager
        self.AudioManager = AudioManager

    def tearDown(self):
        sys.modules.pop("winsound", None)
        sys.modules.pop("pyttsx3", None)

    def _make(self, extra=None):
        cfg = {"audio_enabled": False, "audio_volume": 0.8,
               "audio_voice_init": True, "audio_sound_activate": True,
               "audio_sound_deactivate": True, "audio_sound_signal": True}
        if extra:
            cfg.update(extra)
        return self.AudioManager(cfg)

    def _drain(self, mgr):
        """Wait for the executor queue to drain."""
        mgr._executor.shutdown(wait=True)

    def test_play_init_no_sound_when_disabled(self):
        mgr = self._make()
        mgr.play_init()
        self._drain(mgr)
        self._fake_pyttsx3.init.assert_not_called()
        self._fake_ws.Beep.assert_not_called()

    def test_play_activate_no_sound_when_disabled(self):
        mgr = self._make()
        mgr.play_activate()
        self._drain(mgr)
        self._fake_ws.Beep.assert_not_called()

    def test_play_deactivate_no_sound_when_disabled(self):
        mgr = self._make()
        mgr.play_deactivate()
        self._drain(mgr)
        self._fake_ws.Beep.assert_not_called()

    def test_play_signal_no_sound_when_disabled(self):
        mgr = self._make()
        mgr.play_signal("Taranite")
        self._drain(mgr)
        self._fake_ws.Beep.assert_not_called()


class TestAudioManagerEnabled(unittest.TestCase):
    """Core behaviour when audio_enabled is True."""

    def setUp(self):
        self._fake_ws = _make_fake_winsound()
        self._fake_pyttsx3, self._tts_engine = _make_fake_pyttsx3()
        sys.modules["winsound"] = self._fake_ws
        sys.modules["pyttsx3"] = self._fake_pyttsx3
        import importlib
        import audio_manager
        importlib.reload(audio_manager)
        from audio_manager import AudioManager
        self.AudioManager = AudioManager

    def tearDown(self):
        sys.modules.pop("winsound", None)
        sys.modules.pop("pyttsx3", None)

    def _make(self, extra=None):
        cfg = {"audio_enabled": True, "audio_volume": 0.8,
               "audio_voice_init": True, "audio_sound_activate": True,
               "audio_sound_deactivate": True, "audio_sound_signal": False}
        if extra:
            cfg.update(extra)
        return self.AudioManager(cfg)

    def _drain(self, mgr):
        mgr._executor.shutdown(wait=True)

    # --- play_init ---

    def test_play_init_calls_tts_when_enabled(self):
        mgr = self._make()
        mgr.play_init()
        self._drain(mgr)
        self._fake_pyttsx3.init.assert_called_once()
        self._tts_engine.say.assert_called_once_with(
            "Vargo Dynamics Scanner online.")
        self._tts_engine.runAndWait.assert_called_once()

    def test_play_init_skipped_when_voice_init_false(self):
        mgr = self._make({"audio_voice_init": False})
        mgr.play_init()
        self._drain(mgr)
        self._fake_pyttsx3.init.assert_not_called()

    # --- play_activate ---

    def test_play_activate_ascending_tones(self):
        mgr = self._make()
        mgr.play_activate()
        self._drain(mgr)
        calls = self._fake_ws.Beep.call_args_list
        self.assertEqual(calls[0], call(800,  80))
        self.assertEqual(calls[1], call(1200, 80))

    def test_play_activate_skipped_when_flag_false(self):
        mgr = self._make({"audio_sound_activate": False})
        mgr.play_activate()
        self._drain(mgr)
        self._fake_ws.Beep.assert_not_called()

    # --- play_deactivate ---

    def test_play_deactivate_descending_tones(self):
        mgr = self._make()
        mgr.play_deactivate()
        self._drain(mgr)
        calls = self._fake_ws.Beep.call_args_list
        self.assertEqual(calls[0], call(1200, 80))
        self.assertEqual(calls[1], call(800,  80))

    def test_play_deactivate_skipped_when_flag_false(self):
        mgr = self._make({"audio_sound_deactivate": False})
        mgr.play_deactivate()
        self._drain(mgr)
        self._fake_ws.Beep.assert_not_called()

    # --- play_signal ---

    def test_play_signal_no_beep_when_flag_false(self):
        mgr = self._make({"audio_sound_signal": False})
        mgr.play_signal("Taranite")
        self._drain(mgr)
        self._fake_ws.Beep.assert_not_called()

    def test_play_signal_beeps_when_flag_true(self):
        mgr = self._make({"audio_sound_signal": True})
        mgr.play_signal("Taranite")
        self._drain(mgr)
        self._fake_ws.Beep.assert_called_once_with(1000, 100)

    # --- set_volume ---

    def test_set_volume_clamps_above_one(self):
        mgr = self._make()
        mgr.set_volume(1.5)
        self._drain(mgr)
        self.assertAlmostEqual(mgr._config["audio_volume"], 1.0)

    def test_set_volume_clamps_below_zero(self):
        mgr = self._make()
        mgr.set_volume(-0.3)
        self._drain(mgr)
        self.assertAlmostEqual(mgr._config["audio_volume"], 0.0)

    def test_set_volume_stores_valid_value(self):
        mgr = self._make()
        mgr.set_volume(0.6)
        self._drain(mgr)
        self.assertAlmostEqual(mgr._config["audio_volume"], 0.6)

    # --- non-blocking ---

    def test_play_methods_return_immediately(self):
        """All play methods must submit to executor and return without waiting."""
        mgr = self._make({"audio_sound_signal": True, "audio_voice_init": False})
        # Temporarily block the executor so work queues but doesn't run
        barrier_done = False

        def slow_task():
            nonlocal barrier_done
            time.sleep(0.3)
            barrier_done = True

        mgr._executor.submit(slow_task)

        t0 = time.monotonic()
        mgr.play_activate()
        mgr.play_deactivate()
        mgr.play_signal("X")
        elapsed = time.monotonic() - t0
        # All three submissions must complete far faster than the 0.3 s blocker
        self.assertLess(elapsed, 0.2)
        self._drain(mgr)

    # --- test_audio sequence ---

    def test_test_audio_calls_all_sounds(self):
        mgr = self._make({"audio_voice_init": True,
                          "audio_sound_activate": True,
                          "audio_sound_deactivate": True})
        with patch("time.sleep"):   # skip the 0.5 s gaps
            mgr.test_audio()
            self._drain(mgr)

        self._fake_pyttsx3.init.assert_called()
        beep_calls = self._fake_ws.Beep.call_args_list
        # activate: 800, 1200  |  deactivate: 1200, 800
        self.assertIn(call(800,  80), beep_calls)
        self.assertIn(call(1200, 80), beep_calls)


class TestAudioManagerNoPyttsx3(unittest.TestCase):
    """When pyttsx3 is not installed, TTS falls back to a beep and warns once."""

    def setUp(self):
        self._fake_ws = _make_fake_winsound()
        sys.modules["winsound"] = self._fake_ws
        # Ensure pyttsx3 is NOT available
        sys.modules.pop("pyttsx3", None)
        # Make importing pyttsx3 raise ImportError
        blocker = types.ModuleType("pyttsx3")
        blocker.__spec__ = None

        import builtins
        self._real_import = builtins.__import__

        def _block_pyttsx3(name, *args, **kwargs):
            if name == "pyttsx3":
                raise ImportError("No module named 'pyttsx3'")
            return self._real_import(name, *args, **kwargs)

        builtins.__import__ = _block_pyttsx3
        self._patched_import = _block_pyttsx3

        import importlib
        import audio_manager
        importlib.reload(audio_manager)
        from audio_manager import AudioManager
        self.AudioManager = AudioManager

    def tearDown(self):
        import builtins
        builtins.__import__ = self._real_import
        sys.modules.pop("winsound", None)
        sys.modules.pop("pyttsx3", None)

    def test_tts_falls_back_to_beep(self):
        cfg = {"audio_enabled": True, "audio_volume": 0.8,
               "audio_voice_init": True}
        mgr = self.AudioManager(cfg)
        mgr.play_init()
        mgr._executor.shutdown(wait=True)
        self._fake_ws.Beep.assert_called_once_with(1000, 120)


class TestAudioManagerNoWinsound(unittest.TestCase):
    """On non-Windows (no winsound), beep methods must not raise."""

    def setUp(self):
        sys.modules.pop("winsound", None)
        # Block winsound import
        import builtins
        self._real_import = builtins.__import__

        def _block_ws(name, *args, **kwargs):
            if name == "winsound":
                raise ImportError("No module named 'winsound'")
            return self._real_import(name, *args, **kwargs)

        builtins.__import__ = _block_ws
        self._patched_import = _block_ws

        import importlib
        import audio_manager
        importlib.reload(audio_manager)
        from audio_manager import AudioManager
        self.AudioManager = AudioManager

    def tearDown(self):
        import builtins
        builtins.__import__ = self._real_import
        sys.modules.pop("winsound", None)

    def test_play_activate_no_exception_without_winsound(self):
        cfg = {"audio_enabled": True, "audio_volume": 0.8,
               "audio_sound_activate": True}
        mgr = self.AudioManager(cfg)
        try:
            mgr.play_activate()
            mgr._executor.shutdown(wait=True)
        except Exception as e:
            self.fail(f"play_activate() raised unexpectedly: {e}")


if __name__ == "__main__":
    unittest.main()
