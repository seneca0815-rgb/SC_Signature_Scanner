"""
test_logger.py  -  SC Signature Reader
Unit tests for logger_setup.setup_logger() and get_logger().
"""

import importlib
import logging
import os
import shutil
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import patch


def _reload():
    """Reload logger_setup so module-level state is fresh."""
    import logger_setup
    importlib.reload(logger_setup)
    return logger_setup


def _reset_logger():
    """Remove all handlers from the 'scsigread' logger."""
    logger = logging.getLogger("scsigread")
    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)


class TestSetupLoggerDirectory(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        _reset_logger()

    def tearDown(self):
        _reset_logger()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _fake_appdata(self):
        return str(self._tmpdir)

    def test_creates_log_directory_if_not_exists(self):
        ls = _reload()
        with patch.dict(os.environ, {"APPDATA": self._fake_appdata()}):
            _, log_path = ls.setup_logger({})
        self.assertTrue(log_path.parent.is_dir())

    def test_returns_logger_and_path(self):
        ls = _reload()
        with patch.dict(os.environ, {"APPDATA": self._fake_appdata()}):
            result = ls.setup_logger({})
        self.assertEqual(len(result), 2)
        logger, log_path = result
        self.assertIsInstance(logger, logging.Logger)
        self.assertIsInstance(log_path, Path)

    def test_log_path_ends_with_scsigread_log(self):
        ls = _reload()
        with patch.dict(os.environ, {"APPDATA": self._fake_appdata()}):
            _, log_path = ls.setup_logger({})
        self.assertEqual(log_path.name, "scsigread.log")

    def test_log_directory_contains_vargo_dynamics_path(self):
        ls = _reload()
        with patch.dict(os.environ, {"APPDATA": self._fake_appdata()}):
            _, log_path = ls.setup_logger({})
        parts = log_path.parts
        self.assertIn("VargoDynamics", parts)
        self.assertIn("SCSigReader", parts)
        self.assertIn("logs", parts)


class TestSetupLoggerHandlers(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        _reset_logger()

    def tearDown(self):
        _reset_logger()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _setup(self, config=None):
        ls = _reload()
        with patch.dict(os.environ, {"APPDATA": self._tmpdir}):
            return ls.setup_logger(config or {})

    def test_logger_has_exactly_two_handlers(self):
        logger, _ = self._setup()
        self.assertEqual(len(logger.handlers), 2)

    def test_file_handler_is_rotating(self):
        logger, _ = self._setup()
        fh = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))
        self.assertEqual(fh.maxBytes, 1_000_000)
        self.assertEqual(fh.backupCount, 2)

    def test_file_handler_is_utf8(self):
        logger, _ = self._setup()
        fh = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))
        self.assertEqual(fh.encoding, "utf-8")

    def test_console_handler_level_is_always_warning(self):
        # Even when log_level is DEBUG, console stays at WARNING
        logger, _ = self._setup({"log_level": "DEBUG"})
        ch = next(
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, RotatingFileHandler)
        )
        self.assertEqual(ch.level, logging.WARNING)

    def test_root_logger_level_is_debug(self):
        logger, _ = self._setup()
        self.assertEqual(logger.level, logging.DEBUG)

    def test_no_duplicate_handlers_on_second_call(self):
        ls = _reload()
        with patch.dict(os.environ, {"APPDATA": self._tmpdir}):
            ls.setup_logger({})
            logger, _ = ls.setup_logger({})
        self.assertEqual(len(logger.handlers), 2)


class TestLogLevel(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        _reset_logger()

    def tearDown(self):
        _reset_logger()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _setup(self, config):
        ls = _reload()
        with patch.dict(os.environ, {"APPDATA": self._tmpdir}):
            return ls.setup_logger(config)

    def _file_handler(self, logger):
        return next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))

    def test_debug_level_enables_debug_messages(self):
        logger, _ = self._setup({"log_level": "DEBUG"})
        fh = self._file_handler(logger)
        self.assertEqual(fh.level, logging.DEBUG)

    def test_warning_level_suppresses_info(self):
        logger, _ = self._setup({"log_level": "WARNING"})
        fh = self._file_handler(logger)
        self.assertGreater(fh.level, logging.INFO)

    def test_default_level_is_info(self):
        logger, _ = self._setup({})
        fh = self._file_handler(logger)
        self.assertEqual(fh.level, logging.INFO)

    def test_invalid_level_falls_back_to_info(self):
        logger, _ = self._setup({"log_level": "NONSENSE"})
        fh = self._file_handler(logger)
        self.assertEqual(fh.level, logging.INFO)


class TestLogFileContent(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        _reset_logger()

    def tearDown(self):
        _reset_logger()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _setup(self, config=None):
        ls = _reload()
        with patch.dict(os.environ, {"APPDATA": self._tmpdir}):
            return ls.setup_logger(config or {"log_level": "DEBUG"})

    def test_log_file_created_and_written(self):
        """The log file exists after setup and contains content after a log call."""
        logger, log_path = self._setup()
        logger.info("hello logger test")
        for h in logger.handlers:
            h.flush()
        self.assertTrue(log_path.exists())
        self.assertGreater(log_path.stat().st_size, 0)

    def test_log_file_is_utf8(self):
        logger, log_path = self._setup()
        logger.info("UTF-8 test: Vargo Dynamics")
        for h in logger.handlers:
            h.flush()
        content = log_path.read_bytes()
        # Should decode cleanly as UTF-8
        self.assertIn(b"UTF-8 test", content)

    def test_log_format_contains_timestamp_level_message(self):
        logger, log_path = self._setup()
        logger.warning("format-check-marker")
        for h in logger.handlers:
            h.flush()
        text = log_path.read_text(encoding="utf-8")
        self.assertIn("format-check-marker", text)
        # Timestamp pattern: YYYY-MM-DD
        import re
        self.assertRegex(text, r"\d{4}-\d{2}-\d{2}")
        # Level indicator
        self.assertIn("WARNING", text)

    def test_log_format_contains_logger_name(self):
        logger, log_path = self._setup()
        logger.info("name-check")
        for h in logger.handlers:
            h.flush()
        text = log_path.read_text(encoding="utf-8")
        self.assertIn("scsigread", text)


class TestGetLogger(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        _reset_logger()

    def tearDown(self):
        _reset_logger()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_get_logger_returns_same_instance_as_setup_logger(self):
        ls = _reload()
        with patch.dict(os.environ, {"APPDATA": self._tmpdir}):
            logger_from_setup, _ = ls.setup_logger({})
        logger_from_get = ls.get_logger()
        self.assertIs(logger_from_setup, logger_from_get)

    def test_get_logger_name_is_scsigread(self):
        ls = _reload()
        self.assertEqual(ls.get_logger().name, "scsigread")


if __name__ == "__main__":
    unittest.main()
