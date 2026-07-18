"""PyInstaller runtime adjustments shared by frozen desktop applications."""

from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from typing import Any

from platformdirs import user_cache_path

# Frozen applications ship neither TBB nor OpenMP. Workqueue is Numba's
# supported dependency-free backend and behaves consistently on macOS/Windows.
os.environ.setdefault("NUMBA_THREADING_LAYER", "workqueue")

import numba


def _without_disk_cache(decorator: Any) -> Any:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        kwargs["cache"] = False
        return decorator(*args, **kwargs)

    return wrapped


# Frozen modules lack normal source locators, so librosa's import-time cached
# decorators cannot use Numba's source-keyed disk cache. JIT remains enabled.
numba.jit = _without_disk_cache(numba.jit)
numba.njit = _without_disk_cache(numba.njit)
numba.vectorize = _without_disk_cache(numba.vectorize)
numba.guvectorize = _without_disk_cache(numba.guvectorize)

cache_root = user_cache_path("AudioAtlas", appauthor=False)
os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
os.environ.setdefault("NUMBA_CACHE_DIR", str(cache_root / "numba"))
for variable in ("MPLCONFIGDIR", "NUMBA_CACHE_DIR"):
    with suppress(OSError):
        Path(os.environ[variable]).mkdir(parents=True, exist_ok=True)
