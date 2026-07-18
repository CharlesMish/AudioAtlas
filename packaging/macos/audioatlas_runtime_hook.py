"""PyInstaller runtime adjustments for librosa/Numba in a frozen app."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# The frozen app intentionally ships no TBB or OpenMP runtime. Workqueue is the
# supported Numba backend exercised by the report engine and avoids unresolved
# optional libomp references on clean Macs.
os.environ.setdefault("NUMBA_THREADING_LAYER", "workqueue")

import numba


def _without_disk_cache(decorator: Any) -> Any:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        kwargs["cache"] = False
        return decorator(*args, **kwargs)

    return wrapped


# Librosa declares cached Numba decorators at import time. Frozen modules do not
# have a normal source-file locator, so Numba's disk cache raises before analysis
# begins. Keep JIT enabled, but disable only those unavailable disk caches.
numba.jit = _without_disk_cache(numba.jit)
numba.njit = _without_disk_cache(numba.njit)
numba.vectorize = _without_disk_cache(numba.vectorize)
numba.guvectorize = _without_disk_cache(numba.guvectorize)

cache_root = Path.home() / "Library" / "Caches" / "AudioAtlas"
os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
os.environ.setdefault("NUMBA_CACHE_DIR", str(cache_root / "numba"))
try:
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["NUMBA_CACHE_DIR"]).mkdir(parents=True, exist_ok=True)
except OSError:
    pass
