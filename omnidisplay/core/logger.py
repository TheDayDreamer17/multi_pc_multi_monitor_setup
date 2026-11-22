"""
Unified Logging system for OmniDisplay.
Writes timestamped logs to ~/.omnidisplay.log and standard output if available.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = os.path.expanduser("~/.omnidisplay.log")

def get_logger(name: str = "omnidisplay") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Rotating File Handler
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        sys.stderr.write(f"Failed to create file log handler: {e}\n")

    # 2. Console Handler (only if stdout is available and valid)
    if sys.stdout is not None:
        try:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        except Exception:
            pass

    return logger

def get_recent_logs(lines: int = 100) -> list:
    """Reads the last N lines from the log file."""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            return [line.rstrip() for line in all_lines[-lines:]]
    except Exception:
        return []
