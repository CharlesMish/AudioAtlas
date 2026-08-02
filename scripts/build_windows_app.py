#!/usr/bin/env python3
"""Build and audit the internal x64 AudioAtlas Windows application."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

DEFAULT_COMMAND_TIMEOUT_SECONDS = 120
PYINSTALLER_TIMEOUT_SECONDS = 900
MAX_UNPACKED_BYTES = 350 * 1024 * 1024
AMD64_MACHINE = 0x8664
EXPECTED_EXECUTABLES = {"audioatlas.exe"}
PE_IMAGE_SUFFIXES = {".exe", ".dll", ".pyd", ".scr", ".cpl"}
IMAGE_FILE_DLL = 0x2000
API_SET_DLL_PATTERN = re.compile(
    r"^(?:api|ext)-ms-win-[a-z0-9-]+-l\d+-\d+-\d+\.dll$",
    re.IGNORECASE,
)
SYSTEM_DLLS = {
    "advapi32.dll",
    "avrt.dll",
    "bcrypt.dll",
    "bcryptprimitives.dll",
    "cfgmgr32.dll",
    "comctl32.dll",
    "comdlg32.dll",
    "crypt32.dll",
    "cryptbase.dll",
    "dbghelp.dll",
    "dnsapi.dll",
    "dwmapi.dll",
    "gdi32.dll",
    "imm32.dll",
    "iphlpapi.dll",
    "kernel32.dll",
    "kernelbase.dll",
    "msvcrt.dll",
    "netapi32.dll",
    "ncrypt.dll",
    "ntdll.dll",
    "ole32.dll",
    "oleaut32.dll",
    "oleacc.dll",
    "powrprof.dll",
    "profapi.dll",
    "psapi.dll",
    "rpcrt4.dll",
    "rasapi32.dll",
    "secur32.dll",
    "setupapi.dll",
    "shell32.dll",
    "shcore.dll",
    "shlwapi.dll",
    "ucrtbase.dll",
    "user32.dll",
    "userenv.dll",
    "uxtheme.dll",
    "version.dll",
    "winhttp.dll",
    "wininet.dll",
    "winmm.dll",
    "wintrust.dll",
    "wtsapi32.dll",
    "ws2_32.dll",
}


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
            f"command: {args}\nstdout: {exc.stdout}\nstderr: {exc.stderr}"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist/windows"))
    parser.add_argument("--work", type=Path, default=Path("build/pyinstaller-windows"))
    parser.add_argument("--audit", type=Path, default=Path("dist/windows/windows-pe-audit.json"))
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args(argv)

    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise SystemExit("The AudioAtlas Windows app must be built on x64 Windows.")
    if sys.version_info[:2] != (3, 11):
        raise SystemExit("The AudioAtlas Windows app must be frozen with Python 3.11.")

    build_number = os.environ.get("AUDIOATLAS_BUNDLE_BUILD_NUMBER", "1")
    if not re.fullmatch(r"[1-9][0-9]*", build_number):
        raise SystemExit("AUDIOATLAS_BUNDLE_BUILD_NUMBER must be a positive integer.")

    root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = metadata["project"]["version"]
    version_file = args.work.resolve() / "AudioAtlas-version-info.txt"
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(_windows_version_info(version), encoding="utf-8")

    environment = os.environ.copy()
    environment["AUDIOATLAS_WINDOWS_VERSION_FILE"] = str(version_file)
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
    command.append(str(root / "packaging" / "windows" / "AudioAtlas.spec"))
    _run_with_environment(
        command,
        environment=environment,
        context="Run PyInstaller",
        timeout=PYINSTALLER_TIMEOUT_SECONDS,
        cwd=root,
    )

    app = args.dist.resolve() / "AudioAtlas"
    executable = app / "AudioAtlas.exe"
    if not executable.is_file():
        raise SystemExit(f"Build completed without expected executable: {executable}")
    audit = audit_windows_bundle(app)
    installed_bytes = sum(path.stat().st_size for path in app.rglob("*") if path.is_file())
    if installed_bytes > MAX_UNPACKED_BYTES:
        raise SystemExit(
            f"Windows app exceeds {MAX_UNPACKED_BYTES} byte budget: {installed_bytes}"
        )
    audit["installed_bytes"] = installed_bytes
    audit["version"] = version
    audit["bundle_build"] = int(build_number)
    args.audit.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.audit.resolve().write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"AudioAtlas Windows app: {app}")
    print(f"Installed size: {installed_bytes / 1024 / 1024:.1f} MiB")
    return 0


def _run_with_environment(
    command: list[str],
    *,
    environment: dict[str, str],
    context: str,
    timeout: int,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"{context} timed out after {timeout}s: {command}") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"{context} failed with exit code {exc.returncode}:\n"
            f"command: {command}\nstdout: {exc.stdout}\nstderr: {exc.stderr}"
        ) from exc


def _windows_version_info(version: str) -> str:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)a(\d+)", version)
    if match is None:
        raise SystemExit(f"Unsupported Windows version format: {version!r}")
    numeric = tuple(int(part) for part in match.groups())
    dotted = ".".join(str(part) for part in numeric)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeric!r}, prodvers={numeric!r}, mask=0x3f, flags=0x0,
    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'Charles Mish'),
    StringStruct('FileDescription', 'AudioAtlas local audio analysis'),
    StringStruct('FileVersion', '{dotted}'),
    StringStruct('InternalName', 'AudioAtlas'),
    StringStruct('LegalCopyright', 'Copyright (c) 2026 Charles Mish'),
    StringStruct('OriginalFilename', 'AudioAtlas.exe'),
    StringStruct('ProductName', 'AudioAtlas'),
    StringStruct('ProductVersion', '{version}')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)\n"""


def audit_windows_bundle(app: Path) -> dict[str, Any]:
    """Audit every bundled file and resolve the exact PE import closure."""

    import pefile

    if app.is_symlink() or not app.is_dir():
        raise SystemExit("Windows bundle audit requires a real application directory")
    app = app.resolve(strict=True)
    entries = sorted(app.rglob("*"))
    symlinks = [path.relative_to(app).as_posix() for path in entries if path.is_symlink()]
    if symlinks:
        raise SystemExit(f"Windows bundle contains unsupported symlinks: {symlinks!r}")
    _reject_case_insensitive_path_collisions(entries, app)
    files = [path for path in entries if path.is_file()]

    pe_images: dict[Path, dict[str, Any]] = {}
    for path in files:
        is_pe = _has_pe_headers(path)
        if not is_pe:
            if path.suffix.casefold() in PE_IMAGE_SUFFIXES:
                raise SystemExit(
                    f"Packaged PE-named file has malformed headers: {path.relative_to(app)}"
                )
            continue
        try:
            pe = pefile.PE(str(path), fast_load=True)
        except pefile.PEFormatError as exc:
            raise SystemExit(f"Packaged PE could not be parsed: {path}") from exc
        try:
            pe.parse_data_directories(
                directories=[
                    pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                    pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
                ]
            )
            machine = pe.FILE_HEADER.Machine
            if machine != AMD64_MACHINE:
                raise SystemExit(
                    f"Packaged PE is not AMD64: {path.relative_to(app)} "
                    f"machine={machine:#x}"
                )
            classification = _classify_pe(path, pe.FILE_HEADER.Characteristics, app)
            if classification == "other-runnable":
                form = path.suffix.casefold() or "<extensionless>"
                raise SystemExit(
                    "Unexpected standalone runnable PE image: "
                    f"{path.relative_to(app).as_posix()} form={form}"
                )
            imports = sorted(_pe_imports(pe))
        except pefile.PEFormatError as exc:
            raise SystemExit(f"Packaged PE could not be parsed: {path}") from exc
        finally:
            pe.close()
        pe_images[path] = {
            "path": path.relative_to(app).as_posix(),
            "size": path.stat().st_size,
            "sha256": _sha256(path),
            "pe_classification": classification,
            "architecture": "x86_64",
            "imports": imports,
        }

    if not pe_images:
        raise SystemExit("Windows bundle audit found no PE files")

    executables = {
        record["path"].casefold()
        for record in pe_images.values()
        if record["pe_classification"] == "executable"
    }
    if executables != EXPECTED_EXECUTABLES:
        raise SystemExit(f"Unexpected packaged executables: {sorted(executables)!r}")

    directory_entries = _directory_entry_index(files)
    for path, record in pe_images.items():
        record["resolved_imports"] = [
            _resolve_pe_import(
                name,
                importer=path,
                app=app,
                files_by_directory=directory_entries,
                pe_images=pe_images,
            )
            for name in record["imports"]
        ]

    pe_records = sorted(
        pe_images.values(), key=lambda record: (record["path"].casefold(), record["path"])
    )
    runtimes = sorted(
        Path(record["path"]).name.casefold()
        for record in pe_records
        if record["pe_classification"] == "dll"
        and Path(record["path"]).name.casefold().startswith("vcruntime")
        and Path(record["path"]).name.casefold().endswith(".dll")
    )
    if not runtimes:
        raise SystemExit("Windows bundle does not include the Visual C++ runtime")
    canonical_inventory = json.dumps(
        pe_records,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {
        "schema_version": 2,
        "architecture": "x86_64",
        "windows_targets": ["Windows 10 22H2 x64", "Windows 11 x64"],
        "signing_status": "unsigned-internal",
        "regular_file_count": len(files),
        "pe_file_count": len(pe_records),
        "visual_cpp_runtimes": sorted(set(runtimes)),
        "pe_files": pe_records,
        "inventory_root_sha256": hashlib.sha256(canonical_inventory).hexdigest(),
        "unresolved_imports": {},
    }


def _pe_imports(pe: Any) -> set[str]:
    imports: set[str] = set()
    for attribute in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT"):
        for entry in getattr(pe, attribute, []):
            try:
                name = entry.dll.decode("ascii").casefold()
            except UnicodeDecodeError as exc:
                raise SystemExit("Packaged PE contains a non-ASCII DLL import name") from exc
            if (
                not name
                or name in {".", ".."}
                or Path(name).name != name
                or "/" in name
                or "\\" in name
                or ":" in name
            ):
                raise SystemExit(f"Packaged PE contains an unsafe DLL import name: {name!r}")
            imports.add(name)
    return imports


def _has_pe_headers(path: Path) -> bool:
    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            dos_header = stream.read(64)
            if not dos_header.startswith(b"MZ"):
                return False
            if len(dos_header) < 64:
                raise SystemExit(f"Malformed DOS header in bundled file: {path}")
            pe_offset = int.from_bytes(dos_header[60:64], "little")
            if pe_offset < 64 or pe_offset > size - 24:
                raise SystemExit(f"Malformed PE header offset in bundled file: {path}")
            stream.seek(pe_offset)
            if stream.read(4) != b"PE\x00\x00":
                raise SystemExit(f"Malformed PE signature in bundled file: {path}")
    except OSError as exc:
        raise SystemExit(f"Could not inspect bundled file: {path}") from exc
    return True


def _classify_pe(path: Path, characteristics: int, app: Path) -> str:
    relative = path.relative_to(app).as_posix()
    suffix = path.suffix.casefold()
    is_dll = bool(characteristics & IMAGE_FILE_DLL)
    if not is_dll and suffix == ".exe" and relative.casefold() in EXPECTED_EXECUTABLES:
        return "executable"
    if is_dll and suffix == ".dll" and path.is_relative_to(app / "_internal"):
        return "dll"
    if is_dll and suffix == ".pyd" and path.is_relative_to(app / "_internal"):
        return "python-extension"
    return "other-runnable"


def _reject_case_insensitive_path_collisions(paths: list[Path], app: Path) -> None:
    observed: dict[str, str] = {}
    for path in paths:
        relative = path.relative_to(app).as_posix()
        folded = relative.casefold()
        previous = observed.setdefault(folded, relative)
        if previous != relative:
            raise SystemExit(
                "Windows bundle contains case-insensitive path ambiguity: "
                f"{previous!r}, {relative!r}"
            )


def _directory_entry_index(files: list[Path]) -> dict[Path, dict[str, list[Path]]]:
    index: dict[Path, dict[str, list[Path]]] = {}
    for path in files:
        index.setdefault(path.parent, {}).setdefault(path.name.casefold(), []).append(path)
    return index


def _resolve_pe_import(
    name: str,
    *,
    importer: Path,
    app: Path,
    files_by_directory: dict[Path, dict[str, list[Path]]],
    pe_images: dict[Path, dict[str, Any]],
) -> dict[str, Any]:
    internal = app / "_internal"
    roots: list[Path] = []
    for root in (importer.parent, app, internal):
        if root.is_dir() and root not in roots:
            roots.append(root)
    candidates = [
        candidate
        for root in roots
        for candidate in files_by_directory.get(root, {}).get(name.casefold(), [])
    ]
    if len(candidates) > 1:
        relative = [path.relative_to(app).as_posix() for path in candidates]
        raise SystemExit(
            f"Ambiguous reachable DLL import {name!r} in "
            f"{importer.relative_to(app).as_posix()}: {relative!r}"
        )
    if candidates:
        target = candidates[0]
        target_record = pe_images.get(target)
        if target_record is None or target_record["pe_classification"] not in {
            "dll",
            "python-extension",
        }:
            raise SystemExit(
                f"DLL import {name!r} in {importer.relative_to(app).as_posix()} "
                f"resolves to a non-library image: {target.relative_to(app).as_posix()}"
            )
        if _is_windows_system_import(name):
            raise SystemExit(
                f"Bundled image shadows Windows system dependency {name!r}: "
                f"{target.relative_to(app).as_posix()}"
            )
        return {
            "name": name,
            "resolution": "bundled",
            "path": target.relative_to(app).as_posix(),
        }
    if _is_windows_system_import(name):
        return {"name": name, "resolution": "windows-system", "path": None}
    raise SystemExit(
        f"Missing native dependency {name!r} imported by "
        f"{importer.relative_to(app).as_posix()}"
    )


def _is_windows_system_import(name: str) -> bool:
    return name in SYSTEM_DLLS or API_SET_DLL_PATTERN.fullmatch(name) is not None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
