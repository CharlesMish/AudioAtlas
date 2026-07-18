# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).resolve().parents[1]
metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
version = metadata["project"]["version"]
build_number = os.environ.get("AUDIOATLAS_BUNDLE_BUILD_NUMBER", "1")
if not build_number.isdigit() or int(build_number) <= 0:
    raise ValueError("AUDIOATLAS_BUNDLE_BUILD_NUMBER must be a positive integer")
version_file = os.environ.get("AUDIOATLAS_WINDOWS_VERSION_FILE")
if not version_file or not Path(version_file).is_file():
    raise ValueError("AUDIOATLAS_WINDOWS_VERSION_FILE must name generated version metadata")

PACKAGING_CONTRACT = {
    "architectures": ["x86_64"],
    "windows_targets": ["Windows 10 22H2 x64", "Windows 11 x64"],
    "python": "3.11",
    "layout": "onedir",
    "signing_status": "unsigned-internal",
}

source_root = root / "src"
datas = collect_data_files("audioatlas")
for distribution in ("numpy", "scipy", "soundfile", "librosa", "numba", "pyloudnorm"):
    datas += copy_metadata(distribution)
datas += [
    (str(path), str(path.parent.relative_to(source_root)))
    for path in sorted((source_root / "audioatlas").rglob("*.py"))
]

analysis = Analysis(
    [str(root / "src" / "audioatlas" / "windows_app.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(root / "packaging" / "common" / "audioatlas_runtime_hook.py")],
    excludes=["AppKit", "objc", "PyObjCTools", "sklearn", "pandas", "bokeh", "numba.np.ufunc.omppool"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="AudioAtlas",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    version=version_file,
)
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="AudioAtlas",
)
