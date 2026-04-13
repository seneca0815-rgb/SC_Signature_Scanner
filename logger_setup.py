"""
logger_setup.py  -  SC Signature Reader / Vargo Dynamics
Centralised logging configuration.

Usage
-----
main.py (once, at startup):
    from logger_setup import setup_logger
    log, log_path = setup_logger(config)

Every other module:
    from logger_setup import get_logger
    log = get_logger()
"""

import logging
import os
import platform
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(config: dict) -> tuple:
    """Configure the 'scsigread' logger and return (logger, log_path).

    Log directory:
      Windows : %APPDATA%\\VargoDynamics\\SCSigReader\\logs\\
      Fallback: <project_root>/logs/

    File handler  : RotatingFileHandler, 1 MB max, 2 backups, UTF-8
    Console handler: StreamHandler, WARNING level always
    Root level    : DEBUG (individual handlers apply their own filters)

    Calling setup_logger() a second time replaces the existing handlers
    rather than duplicating them.
    """
    # ------------------------------------------------------------------
    # Log directory
    # ------------------------------------------------------------------
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA", str(Path.home()))
        log_dir = Path(appdata) / "VargoDynamics" / "SCSigReader" / "logs"
    else:
        log_dir = Path(__file__).parent / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "scsigread.log"

    # ------------------------------------------------------------------
    # Level from config
    # ------------------------------------------------------------------
    level_name = str(config.get("log_level", "INFO")).upper()
    file_level = getattr(logging, level_name, logging.INFO)

    # ------------------------------------------------------------------
    # Formatters
    # ------------------------------------------------------------------
    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_fmt = logging.Formatter("[%(levelname)s] %(message)s")

    # ------------------------------------------------------------------
    # File handler
    # ------------------------------------------------------------------
    fh = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=2,
        encoding="utf-8",
    )
    fh.setLevel(file_level)
    fh.setFormatter(file_fmt)

    # ------------------------------------------------------------------
    # Console handler  (always WARNING so the terminal stays quiet)
    # ------------------------------------------------------------------
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(console_fmt)

    # ------------------------------------------------------------------
    # Logger  –  replace handlers to prevent duplicates on re-init
    # ------------------------------------------------------------------
    logger = logging.getLogger("scsigread")
    logger.setLevel(logging.DEBUG)

    for existing in logger.handlers[:]:
        existing.close()
        logger.removeHandler(existing)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger, log_path


def get_logger() -> logging.Logger:
    """Return the pre-configured 'scsigread' logger.

    If setup_logger() has not been called yet the logger still works –
    messages are passed to Python's last-resort handler (stderr, WARNING+).
    """
    return logging.getLogger("scsigread")
