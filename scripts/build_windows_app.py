#!/usr/bin/env python3
"""Build and audit the internal x64 AudioAtlas Windows application."""

from __future__ import annotations

import argparse
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
    """Audit packaged PE architecture and import closure."""

    import pefile

    files = [path for path in app.rglob("*") if path.is_file()]
    bundled_names = {path.name.casefold() for path in files}
    executables = {
        path.relative_to(app).as_posix().casefold()
        for path in files
        if path.suffix.casefold() == ".exe"
    }
    if executables != EXPECTED_EXECUTABLES:
        raise SystemExit(f"Unexpected packaged executables: {sorted(executables)!r}")

    pe_records: list[dict[str, Any]] = []
    unresolved: dict[str, list[str]] = {}
    for path in files:
        if path.suffix.casefold() not in {".exe", ".dll", ".pyd"}:
            continue
        try:
            pe = pefile.PE(str(path), fast_load=True)
            pe.parse_data_directories(
                directories=[
                    pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                    pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
                ]
            )
        except pefile.PEFormatError as exc:
            raise SystemExit(f"Packaged PE could not be parsed: {path}") from exc
        if pe.FILE_HEADER.Machine != AMD64_MACHINE:
            raise SystemExit(
                f"Packaged PE is not AMD64: {path.relative_to(app)} "
                f"machine={pe.FILE_HEADER.Machine:#x}"
            )
        imports = sorted(_pe_imports(pe))
        missing = [name for name in imports if not _is_resolved_import(name, bundled_names)]
        relative = path.relative_to(app).as_posix()
        if missing:
            unresolved[relative] = missing
        pe_records.append({"path": relative, "imports": imports})
        pe.close()

    if not pe_records:
        raise SystemExit("Windows bundle audit found no PE files")
    if unresolved:
        raise SystemExit(f"Windows bundle has unresolved DLL imports: {unresolved!r}")
    runtimes = sorted(
        name for name in bundled_names if name.startswith("vcruntime") and name.endswith(".dll")
    )
    if not runtimes:
        raise SystemExit("Windows bundle does not include the Visual C++ runtime")
    return {
        "schema_version": 1,
        "architecture": "x86_64",
        "windows_targets": ["Windows 10 22H2 x64", "Windows 11 x64"],
        "signing_status": "unsigned-internal",
        "visual_cpp_runtimes": runtimes,
        "pe_files": pe_records,
        "unresolved_imports": {},
    }


def _pe_imports(pe: Any) -> set[str]:
    imports: set[str] = set()
    for attribute in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT"):
        for entry in getattr(pe, attribute, []):
            imports.add(entry.dll.decode("ascii").casefold())
    return imports


def _is_resolved_import(name: str, bundled_names: set[str]) -> bool:
    return (
        name in bundled_names
        or name in SYSTEM_DLLS
        or name.startswith("api-ms-win-")
        or name.startswith("ext-ms-win-")
    )


if __name__ == "__main__":
    raise SystemExit(main())
