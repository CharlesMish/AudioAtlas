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
from dataclasses import dataclass
from pathlib import Path

DEFAULT_COMMAND_TIMEOUT_SECONDS = 120
PYINSTALLER_TIMEOUT_SECONDS = 900
PACKAGE_ROOT_ENTRIES = {"Contents"}
MACH_O_MAGICS = {
    b"\xfe\xed\xfa\xce",  # 32-bit big-endian
    b"\xce\xfa\xed\xfe",  # 32-bit little-endian
    b"\xfe\xed\xfa\xcf",  # 64-bit big-endian
    b"\xcf\xfa\xed\xfe",  # 64-bit little-endian
    b"\xca\xfe\xba\xbe",  # universal binary
    b"\xbe\xba\xfe\xca",  # byte-swapped universal binary
    b"\xca\xfe\xba\xbf",  # universal binary with 64-bit arch records
    b"\xbf\xba\xfe\xca",  # byte-swapped 64-bit universal binary
}
SYSTEM_LIBRARY_PREFIXES = ("/System/Library/", "/usr/lib/")


@dataclass(frozen=True)
class ResolvedDependency:
    importer: Path
    install_name: str
    resolved_path: Path


@dataclass(frozen=True)
class MachOImage:
    install_id: str | None
    dependencies: tuple[str, ...]
    rpaths: tuple[str, ...]


def _run(
    *args: str,
    context: str,
    timeout: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=True,
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"{context} timed out after {timeout}s: {args}") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"{context} failed with exit code {exc.returncode}:\n"
            f"command: {args}\n"
            f"stdout: {exc.stdout}\n"
            f"stderr: {exc.stderr}"
        ) from exc


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
    build_root = args.work.resolve()
    dist_root = args.dist.resolve()
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--distpath",
        str(dist_root),
        "--workpath",
        str(build_root),
    ]
    if not args.no_clean:
        command.append("--clean")
    command.append(str(spec))
    _run(
        *command,
        context="Run PyInstaller",
        timeout=PYINSTALLER_TIMEOUT_SECONDS,
        cwd=root,
    )
    app = dist_root / "AudioAtlas.app"
    if not app.is_dir():
        raise SystemExit(f"Build completed without expected app bundle: {app}")
    dependencies = _audit_bundle(app)
    _verify_code_signature(app)
    for dependency in dependencies:
        print(
            "Native dependency: "
            f"{dependency.importer.relative_to(app)}: {dependency.install_name} -> "
            f"{dependency.resolved_path.relative_to(app.resolve())}"
        )
    print(f"AudioAtlas app: {app}")
    print(f"Installed size: {_directory_size(app) / 1024 / 1024:.1f} MiB")
    return 0


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _audit_bundle(app: Path) -> tuple[ResolvedDependency, ...]:
    """Fail a build whose metadata or Mach-O closure contradicts its promise."""

    if app.is_symlink() or not app.is_dir():
        raise SystemExit("Bundle audit failed: app must be a real directory")
    app_root = app.resolve(strict=True)
    app = app_root
    info_path = app / "Contents" / "Info.plist"
    with info_path.open("rb") as handle:
        info = plistlib.load(handle)
    expected = {
        "CFBundleIdentifier": "com.charlesmish.audioatlas",
        "LSMinimumSystemVersion": "14.0",
        "LSApplicationCategoryType": "public.app-category.music",
        "NSHumanReadableCopyright": "Copyright © 2026 Charles Mish",
        "CFBundleIconFile": "AudioAtlas.icns",
    }
    for key, value in expected.items():
        if info.get(key) != value:
            raise SystemExit(f"Bundle audit failed: {key}={info.get(key)!r}, expected {value!r}")
    if not re.fullmatch(r"[1-9][0-9]*", str(info.get("CFBundleVersion", ""))):
        raise SystemExit("Bundle audit failed: CFBundleVersion is not a positive integer")
    executable_name = info.get("CFBundleExecutable")
    if not isinstance(executable_name, str) or not executable_name:
        raise SystemExit("Bundle audit failed: CFBundleExecutable is missing")
    executable = app / "Contents" / "MacOS" / executable_name
    icon = app / "Contents" / "Resources" / str(info["CFBundleIconFile"])
    if icon.is_symlink() or not icon.is_file():
        raise SystemExit("Bundle audit failed: CFBundleIconFile is missing")

    root_contents = {entry.name for entry in app.iterdir()}
    if root_contents != PACKAGE_ROOT_ENTRIES:
        raise SystemExit(
            "Bundle audit failed: app root unexpected entries: "
            f"{sorted(root_contents)!r}"
        )

    entries = sorted(app.rglob("*"))
    for path in entries:
        if path.is_symlink():
            _validate_bundle_symlink(path, app_root)
    files = [path for path in entries if path.is_file() and not path.is_symlink()]
    mach_o = [path for path in files if _is_mach_o(path)]

    if not mach_o:
        raise SystemExit("Bundle audit failed: no Mach-O files found")
    if executable.is_symlink() or not executable.is_file() or not _is_mach_o(executable):
        raise SystemExit("Bundle audit failed: CFBundleExecutable is not a Mach-O file")

    images: dict[Path, MachOImage] = {}
    for path in mach_o:
        architecture_lines = _run(
            "lipo",
            "-archs",
            str(path),
            context=f"Check Mach-O architectures for {path.relative_to(app)}",
        ).stdout.split()
        if "arm64" not in architecture_lines or "x86_64" in architecture_lines:
            raise SystemExit(
                f"Bundle audit failed: {path.relative_to(app)} architectures={architecture_lines!r}"
            )
        build_output = _run(
            "vtool",
            "-show-build",
            str(path),
            context=f"Read Mach-O minimum system version for {path.relative_to(app)}",
        ).stdout
        minimum_versions = re.findall(r"^\s*minos\s+(\d+(?:\.\d+)+)", build_output, re.MULTILINE)
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

        linked = tuple(
            line.strip().split(" (", 1)[0]
            for line in _run(
            "otool",
            "-L",
            str(path),
            context=f"Inspect Mach-O linked libraries for {path.relative_to(app)}",
            ).stdout.splitlines()[1:]
            if line.strip().split(" (", 1)[0]
        )
        dylib_ids = [
            line.strip()
            for line in _run(
                "otool",
                "-D",
                str(path),
                context=f"Inspect Mach-O install name for {path.relative_to(app)}",
            ).stdout.splitlines()[1:]
            if line.strip()
        ]
        if len(dylib_ids) > 1:
            raise SystemExit(
                f"Bundle audit failed: {path.relative_to(app)} has multiple install names"
            )
        images[path] = MachOImage(
            install_id=dylib_ids[0] if dylib_ids else None,
            dependencies=linked,
            rpaths=_read_rpaths(path, app),
        )

    return _resolve_bundle_dependencies(
        images,
        executable=executable,
        app_root=app_root,
    )


def _resolve_bundle_dependencies(
    images: dict[Path, MachOImage],
    *,
    executable: Path,
    app_root: Path,
) -> tuple[ResolvedDependency, ...]:
    """Resolve imports with the run-path stack for each concrete loader chain."""

    resolved: dict[tuple[Path, str], Path] = {}
    visited_states: set[tuple[Path, tuple[tuple[Path, str], ...]]] = set()
    visited_images: set[Path] = set()

    def extended(
        inherited: tuple[tuple[Path, str], ...], path: Path
    ) -> tuple[tuple[Path, str], ...]:
        context = list(inherited)
        for value in images[path].rpaths:
            entry = (path, value)
            if entry not in context:
                context.append(entry)
        return tuple(context)

    def walk(root: Path, inherited: tuple[tuple[Path, str], ...]) -> None:
        pending = [(root, extended(inherited, root))]
        while pending:
            importer, rpaths = pending.pop()
            state = (importer, rpaths)
            if state in visited_states:
                continue
            visited_states.add(state)
            visited_images.add(importer)
            image = images[importer]
            for dependency in image.dependencies:
                if dependency == image.install_id:
                    continue
                if dependency.startswith(SYSTEM_LIBRARY_PREFIXES):
                    continue
                target = _resolve_dependency(
                    dependency,
                    importer=importer,
                    executable=executable,
                    rpaths=rpaths,
                    app_root=app_root,
                )
                key = (importer, dependency)
                previous = resolved.setdefault(key, target)
                if previous != target:
                    raise SystemExit(
                        "Bundle audit failed: loader contexts resolve one dependency "
                        f"to different files: {dependency!r} in "
                        f"{importer.relative_to(app_root)}"
                    )
                if target not in images:
                    raise SystemExit(
                        "Bundle audit failed: resolved dependency was omitted from the "
                        f"Mach-O inventory: {target.relative_to(app_root)}"
                    )
                pending.append((target, extended(rpaths, target)))

    walk(executable, ())
    executable_context = extended((), executable)
    # Python extensions and other dlopen targets may not be statically reachable
    # from the main executable. Audit each such image as a root, with only the
    # executable's process-wide context plus that image's own run paths.
    for path in sorted(images):
        if path not in visited_images:
            walk(path, executable_context)

    return tuple(
        ResolvedDependency(
            importer=importer.resolve(strict=True),
            install_name=install_name,
            resolved_path=target,
        )
        for (importer, install_name), target in sorted(
            resolved.items(),
            key=lambda item: (
                str(item[0][0]).casefold(),
                item[0][1],
            ),
        )
    )


def _verify_code_signature(app: Path) -> None:
    """Run the strict code-signature gate independently of dependency resolution."""

    _run(
        "codesign",
        "--verify",
        "--deep",
        "--strict",
        str(app),
        context="Verify app signing status",
    )


def _is_mach_o(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            return stream.read(4) in MACH_O_MAGICS
    except OSError as exc:
        raise SystemExit(f"Bundle audit failed: could not inspect {path}") from exc


def _validate_bundle_symlink(link: Path, app_root: Path) -> None:
    try:
        declared_target = Path(os.readlink(link))
        resolved = link.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SystemExit(f"Bundle audit failed: broken symlink {link.relative_to(app_root)}") from exc
    if not resolved.is_relative_to(app_root):
        kind = "absolute external" if declared_target.is_absolute() else "escaping"
        raise SystemExit(
            f"Bundle audit failed: {kind} symlink {link.relative_to(app_root)} -> "
            f"{declared_target}"
        )


def _read_rpaths(path: Path, app: Path) -> tuple[str, ...]:
    output = _run(
        "otool",
        "-l",
        str(path),
        context=f"Inspect Mach-O run paths for {path.relative_to(app)}",
    ).stdout
    return tuple(
        match.group(1)
        for match in re.finditer(
            r"^\s*cmd LC_RPATH\s*$\n^\s*cmdsize \d+\s*$\n^\s*path (.+?) \(offset \d+\)\s*$",
            output,
            re.MULTILINE,
        )
    )


def _resolve_dependency(
    install_name: str,
    *,
    importer: Path,
    executable: Path,
    rpaths: tuple[tuple[Path, str], ...],
    app_root: Path,
) -> Path:
    if install_name.startswith("/"):
        raise SystemExit(
            "Bundle audit failed: absolute non-system dependency "
            f"{install_name!r} in {importer.relative_to(app_root)}"
        )

    if install_name == "@loader_path" or install_name.startswith("@loader_path/"):
        candidates = [_expand_origin(install_name, "@loader_path", importer.parent)]
    elif install_name == "@executable_path" or install_name.startswith(
        "@executable_path/"
    ):
        candidates = [
            _expand_origin(install_name, "@executable_path", executable.parent)
        ]
    elif install_name == "@rpath" or install_name.startswith("@rpath/"):
        if not rpaths:
            raise SystemExit(
                "Bundle audit failed: @rpath dependency has no LC_RPATH in "
                f"{importer.relative_to(app_root)}: {install_name!r}"
            )
        suffix = install_name.removeprefix("@rpath").removeprefix("/")
        candidates = [
            _expand_rpath(rpath, loader=loader, executable=executable) / suffix
            for loader, rpath in rpaths
        ]
    else:
        raise SystemExit(
            "Bundle audit failed: unsupported relative dependency "
            f"{install_name!r} in {importer.relative_to(app_root)}"
        )

    existing: list[Path] = []
    for candidate in candidates:
        lexical = candidate.resolve(strict=False)
        if not lexical.is_relative_to(app_root):
            raise SystemExit(
                "Bundle audit failed: dependency escapes the app bundle: "
                f"{install_name!r} in {importer.relative_to(app_root)}"
            )
        if not candidate.exists():
            continue
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise SystemExit(
                f"Bundle audit failed: broken dependency path {candidate}"
            ) from exc
        if not resolved.is_relative_to(app_root):
            raise SystemExit(
                "Bundle audit failed: dependency resolves outside the app bundle: "
                f"{install_name!r} in {importer.relative_to(app_root)}"
            )
        if not resolved.is_file() or not _is_mach_o(resolved):
            raise SystemExit(
                "Bundle audit failed: resolved dependency is not Mach-O: "
                f"{candidate.relative_to(app_root)}"
            )
        if resolved not in existing:
            existing.append(resolved)

    if len(existing) != 1:
        rendered = [str(path.relative_to(app_root)) for path in existing]
        raise SystemExit(
            "Bundle audit failed: dependency must have exactly one existing in-bundle "
            f"resolution: {install_name!r} in {importer.relative_to(app_root)} -> "
            f"{rendered!r}"
        )
    return existing[0]


def _expand_origin(value: str, token: str, origin: Path) -> Path:
    suffix = value.removeprefix(token).removeprefix("/")
    return origin / suffix


def _expand_rpath(value: str, *, loader: Path, executable: Path) -> Path:
    if value == "@loader_path" or value.startswith("@loader_path/"):
        return _expand_origin(value, "@loader_path", loader.parent)
    if value == "@executable_path" or value.startswith("@executable_path/"):
        return _expand_origin(value, "@executable_path", executable.parent)
    if value.startswith("/"):
        return Path(value)
    raise SystemExit(
        f"Bundle audit failed: unsupported LC_RPATH {value!r} in {loader}"
    )


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


if __name__ == "__main__":
    raise SystemExit(main())
