# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).resolve().parents[1]
metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
version = metadata["project"]["version"]
bundle_build_version = os.environ.get("AUDIOATLAS_BUNDLE_BUILD_NUMBER", "1")
if not bundle_build_version.isdigit() or int(bundle_build_version) <= 0:
    raise ValueError("AUDIOATLAS_BUNDLE_BUILD_NUMBER must be a positive integer")
codesign_identity = os.environ.get("AUDIOATLAS_CODESIGN_IDENTITY") or None
entitlements = root / "packaging" / "macos" / "AudioAtlas.entitlements"
source_root = root / "src"
datas = collect_data_files("audioatlas")
for distribution in ("numpy", "scipy", "soundfile", "librosa", "numba", "pyloudnorm"):
    datas += copy_metadata(distribution)
# Provenance intentionally fingerprints measurement source bytes. Preserve the
# package-relative Python sources as data so frozen reports retain the same
# comparability identity as the wheel instead of hashing an empty file set.
datas += [
    (str(path), str(path.parent.relative_to(source_root)))
    for path in sorted((source_root / "audioatlas").rglob("*.py"))
]

analysis = Analysis(
    [str(root / "src" / "audioatlas" / "macos_app.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(root / "packaging" / "macos" / "audioatlas_runtime_hook.py")],
    excludes=["sklearn", "pandas", "bokeh", "numba.np.ufunc.omppool"],
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
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=codesign_identity,
    entitlements_file=str(entitlements),
)
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="AudioAtlas",
)
app = BUNDLE(
    collection,
    name="AudioAtlas.app",
    bundle_identifier="com.charlesmish.audioatlas",
    version=version,
    info_plist={
        "CFBundleDisplayName": "AudioAtlas",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": bundle_build_version,
        "LSMinimumSystemVersion": "14.0",
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Audio file",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "CFBundleTypeExtensions": [
                    "wav", "wave", "flac", "ogg", "aif", "aiff", "mp3"
                ],
            }
        ],
    },
)
