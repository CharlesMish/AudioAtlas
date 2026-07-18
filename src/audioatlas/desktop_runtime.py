"""Per-user runtime paths and logging shared by desktop front ends."""

from __future__ import annotations

import logging
import os
from contextlib import suppress
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_cache_path, user_log_path


def cache_directory() -> Path:
    return user_cache_path("AudioAtlas", appauthor=False)


def log_directory() -> Path:
    return user_log_path("AudioAtlas", appauthor=False)


def log_path() -> Path:
    return log_directory() / "app.log"


def configure_scientific_cache_environment() -> Path:
    """Select persistent user-writable caches without importing the engine."""

    root = cache_directory()
    os.environ.setdefault("MPLCONFIGDIR", str(root / "matplotlib"))
    os.environ.setdefault("NUMBA_CACHE_DIR", str(root / "numba"))
    for name in ("MPLCONFIGDIR", "NUMBA_CACHE_DIR"):
        with suppress(OSError):
            Path(os.environ[name]).mkdir(parents=True, exist_ok=True)
    return root


def configure_desktop_logger(name: str = "audioatlas.desktop") -> logging.Logger:
    """Return one rotating, local-only diagnostic logger."""

    logger = logging.getLogger(name)
    if getattr(logger, "_audioatlas_configured", False):
        return logger
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = RotatingFileHandler(
            path, maxBytes=1_048_576, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
    except OSError:
        handler = logging.NullHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger._audioatlas_configured = True  # type: ignore[attr-defined]
    return logger
