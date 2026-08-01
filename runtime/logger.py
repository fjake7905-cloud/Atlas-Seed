from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any


def _get_log_file() -> Path:
    root = os.getenv("ATLAS_ROOT")
    base = Path(root).resolve() if root else Path.cwd().resolve()
    return base / ".atlas" / "atlas.log"


def setup_logger(name: str = "atlas", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured

    log_level = os.getenv("ATLAS_LOG_LEVEL", "").upper()
    if log_level in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        level = getattr(logging, log_level, level)

    logger.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(console_formatter)

    # Only add console handler if not in pytest (to avoid cluttering test output)
    if not os.getenv("PYTEST_CURRENT_TEST"):
        logger.addHandler(console_handler)

    # File handler
    try:
        log_file = _get_log_file()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # File gets DEBUG always
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s - %(pathname)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception:
        # File logging failure should not break app
        pass

    # Avoid duplicate logs
    logger.propagate = False

    return logger


def get_logger(name: str = "atlas") -> logging.Logger:
    return logging.getLogger(name)


# Default logger instance
default_logger = setup_logger()

# Convenience functions
def info(msg: str, *args: Any, **kwargs: Any) -> None:
    default_logger.info(msg, *args, **kwargs)


def debug(msg: str, *args: Any, **kwargs: Any) -> None:
    default_logger.debug(msg, *args, **kwargs)


def warning(msg: str, *args: Any, **kwargs: Any) -> None:
    default_logger.warning(msg, *args, **kwargs)


def error(msg: str, *args: Any, **kwargs: Any) -> None:
    default_logger.error(msg, *args, **kwargs)
