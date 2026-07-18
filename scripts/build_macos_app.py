#!/usr/bin/env python3
"""Build the reproducible Apple Silicon AudioAtlas application bundle."""

from __future__ import annotations

import argparse
import os
import platform
import plistlib
import re
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist/macos"))
    parser.add_argument("--work", type=Path, default=Path("build/pyinstaller"))
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args(argv)

    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise SystemExit("AudioAtlas.app must be built on an Apple Silicon Mac.")

    build_number = os.environ.get("AUDIOATLAS_BUNDLE_BUILD_NUMBER", "1")
    if not re.fullmatch(r"[1-9][0-9]*", build_number):
        raise SystemExit("AUDIOATLAS_BUNDLE_BUILD_NUMBER must be a positive integer.")

    root = Path(__file__).resolve().parents[1]
    spec = root / "packaging" / "macos" / "AudioAtlas.spec"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--distpath",
        str(args.dist.resolve()),
        "--workpath",
        str(args.work.resolve()),
    ]
    if not args.no_clean:
        command.append("--clean")
    command.append(str(spec))
    subprocess.run(command, cwd=root, check=True)

    app = args.dist.resolve() / "AudioAtlas.app"
    if not app.is_dir():
        raise SystemExit(f"Build completed without expected app bundle: {app}")
    _audit_bundle(app)
    print(f"AudioAtlas app: {app}")
    print(f"Installed size: {_directory_size(app) / 1024 / 1024:.1f} MiB")
    return 0


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _audit_bundle(app: Path) -> None:
    """Fail a build whose metadata or Mach-O closure contradicts its promise."""

    info_path = app / "Contents" / "Info.plist"
    with info_path.open("rb") as handle:
        info = plistlib.load(handle)
    expected = {
        "CFBundleIdentifier": "com.charlesmish.audioatlas",
        "LSMinimumSystemVersion": "14.0",
    }
    for key, value in expected.items():
        if info.get(key) != value:
            raise SystemExit(f"Bundle audit failed: {key}={info.get(key)!r}, expected {value!r}")
    if not re.fullmatch(r"[1-9][0-9]*", str(info.get("CFBundleVersion", ""))):
        raise SystemExit("Bundle audit failed: CFBundleVersion is not a positive integer")

    files = [path for path in app.rglob("*") if path.is_file() and not path.is_symlink()]
    bundle_basenames = {path.name for path in files}
    mach_o: list[Path] = []
    for path in files:
        identified = subprocess.run(
            ["file", "-b", str(path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if "Mach-O" in identified:
            mach_o.append(path)

    if not mach_o:
        raise SystemExit("Bundle audit failed: no Mach-O files found")
    for path in mach_o:
        architectures = subprocess.run(
            ["lipo", "-archs", str(path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split()
        if "arm64" not in architectures or "x86_64" in architectures:
            raise SystemExit(
                f"Bundle audit failed: {path.relative_to(app)} architectures={architectures!r}"
            )
        build = subprocess.run(
            ["vtool", "-show-build", str(path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        minimum_versions = re.findall(
            r"^\s*minos\s+(\d+(?:\.\d+)+)", build, re.MULTILINE
        )
        if not minimum_versions:
            raise SystemExit(
                f"Bundle audit failed: {path.relative_to(app)} has no macOS build target"
            )
        for minimum_version in minimum_versions:
            if _version_tuple(minimum_version) > (14, 0):
                raise SystemExit(
                    "Bundle audit failed: "
                    f"{path.relative_to(app)} requires macOS {minimum_version}"
                )
        linked = subprocess.run(
            ["otool", "-L", str(path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()[1:]
        dylib_ids = subprocess.run(
            ["otool", "-D", str(path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()[1:]
        install_id = dylib_ids[0].strip() if dylib_ids else None
        for line in linked:
            dependency = line.strip().split(" (", 1)[0]
            if dependency == install_id:
                continue
            if dependency.startswith(("/System/", "/usr/lib/")):
                continue
            if dependency.startswith(
                ("@rpath/", "@loader_path/", "@executable_path/")
            ) and Path(dependency).name in bundle_basenames:
                continue
            raise SystemExit(
                "Bundle audit failed: unresolved or non-system dependency "
                f"{dependency!r} in {path.relative_to(app)}"
            )

    subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", str(app)],
        check=True,
    )


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


if __name__ == "__main__":
    raise SystemExit(main())
