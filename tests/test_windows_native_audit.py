from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
IMAGE_FILE_DLL = 0x2000


def _build_script():
    spec = importlib.util.spec_from_file_location(
        "build_windows_app_native_audit",
        ROOT / "scripts" / "build_windows_app.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_pe(path: Path, marker: bytes = b"") -> Path:
    payload = bytearray(512)
    payload[:2] = b"MZ"
    payload[60:64] = (128).to_bytes(4, "little")
    payload[128:132] = b"PE\x00\x00"
    payload[256 : 256 + len(marker)] = marker
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


class FakePEFormatError(Exception):
    pass


class FakePE:
    def __init__(self, config: dict[str, object]) -> None:
        self.FILE_HEADER = SimpleNamespace(
            Machine=config["machine"],
            Characteristics=config["characteristics"],
        )
        self.DIRECTORY_ENTRY_IMPORT = [
            SimpleNamespace(dll=name.encode("ascii"))
            for name in config.get("imports", [])
        ]
        self.DIRECTORY_ENTRY_DELAY_IMPORT = [
            SimpleNamespace(dll=name.encode("ascii"))
            for name in config.get("delay_imports", [])
        ]

    def parse_data_directories(self, *, directories: list[int]) -> None:
        assert directories == [1, 2]

    def close(self) -> None:
        return None


class FakePefile:
    PEFormatError = FakePEFormatError
    DIRECTORY_ENTRY = {
        "IMAGE_DIRECTORY_ENTRY_IMPORT": 1,
        "IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT": 2,
    }

    def __init__(self, configs: dict[Path, dict[str, object]]) -> None:
        self.configs = configs

    def PE(self, path: str, *, fast_load: bool) -> FakePE:
        assert fast_load
        try:
            config = self.configs[Path(path)]
        except KeyError as exc:
            raise FakePEFormatError(path) from exc
        return FakePE(config)


def _image(
    *,
    dll: bool,
    imports: list[str] | None = None,
    machine: int = 0x8664,
) -> dict[str, object]:
    return {
        "machine": machine,
        "characteristics": IMAGE_FILE_DLL if dll else 0x0002,
        "imports": imports or [],
    }


def _base_bundle(tmp_path: Path) -> tuple[Path, dict[Path, dict[str, object]]]:
    app = tmp_path / "AudioAtlas"
    executable = _write_pe(app / "AudioAtlas.exe", b"executable")
    runtime = _write_pe(app / "_internal" / "VCRUNTIME140.dll", b"runtime")
    configs = {
        executable: _image(
            dll=False,
            imports=["KERNEL32.dll", "vcruntime140.DLL"],
        ),
        runtime: _image(dll=True, imports=["kernel32.dll"]),
    }
    return app, configs


def _audit(
    build: object,
    app: Path,
    configs: dict[Path, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    monkeypatch.setitem(sys.modules, "pefile", FakePefile(configs))
    return build.audit_windows_bundle(app)


def test_known_good_pyinstaller_root_internal_layout_records_canonical_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, configs = _base_bundle(tmp_path)
    extension = _write_pe(app / "_internal" / "package" / "module.pyd", b"extension")
    helper = _write_pe(app / "_internal" / "helper.dll", b"helper")
    configs[extension] = _image(
        dll=True,
        imports=["helper.DLL", "api-ms-win-core-file-l1-1-0.dll"],
    )
    configs[helper] = _image(dll=True, imports=["kernel32.dll"])

    audit = _audit(build, app, configs, monkeypatch)

    assert audit["schema_version"] == 2
    assert audit["regular_file_count"] == 4
    assert audit["pe_file_count"] == 4
    records = audit["pe_files"]
    assert isinstance(records, list)
    by_path = {record["path"]: record for record in records}
    assert by_path["AudioAtlas.exe"]["pe_classification"] == "executable"
    assert by_path["_internal/package/module.pyd"]["pe_classification"] == (
        "python-extension"
    )
    assert by_path["_internal/helper.dll"]["pe_classification"] == "dll"
    assert by_path["_internal/helper.dll"]["size"] == helper.stat().st_size
    assert by_path["_internal/helper.dll"]["sha256"] == hashlib.sha256(
        helper.read_bytes()
    ).hexdigest()
    extension_imports = by_path["_internal/package/module.pyd"]["resolved_imports"]
    assert extension_imports == [
        {
            "name": "api-ms-win-core-file-l1-1-0.dll",
            "resolution": "windows-system",
            "path": None,
        },
        {
            "name": "helper.dll",
            "resolution": "bundled",
            "path": "_internal/helper.dll",
        },
    ]
    canonical = json.dumps(
        records, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    assert audit["inventory_root_sha256"] == hashlib.sha256(canonical).hexdigest()


@pytest.mark.parametrize(
    ("name", "dll_flag", "form"),
    [
        ("screensaver.scr", False, ".scr"),
        ("control.cpl", True, ".cpl"),
        ("extensionless", False, "<extensionless>"),
    ],
)
def test_unexpected_standalone_runnable_pe_forms_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    dll_flag: bool,
    form: str,
) -> None:
    build = _build_script()
    app, configs = _base_bundle(tmp_path)
    rogue = _write_pe(app / "_internal" / name, b"rogue")
    configs[rogue] = _image(dll=dll_flag)

    with pytest.raises(SystemExit, match=f"form={re.escape(form)}"):
        _audit(build, app, configs, monkeypatch)


def test_required_dll_in_unreachable_data_directory_does_not_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, configs = _base_bundle(tmp_path)
    extension = _write_pe(app / "_internal" / "package" / "module.pyd")
    unreachable = _write_pe(app / "_internal" / "data" / "required.dll")
    configs[extension] = _image(dll=True, imports=["required.dll"])
    configs[unreachable] = _image(dll=True)

    with pytest.raises(SystemExit, match="Missing native dependency 'required.dll'"):
        _audit(build, app, configs, monkeypatch)


def test_duplicate_case_insensitive_reachable_dll_basenames_are_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, configs = _base_bundle(tmp_path)
    extension = _write_pe(app / "_internal" / "package" / "module.pyd")
    sibling = _write_pe(extension.parent / "Foo.DLL", b"sibling")
    internal = _write_pe(app / "_internal" / "foo.dll", b"internal")
    configs[extension] = _image(dll=True, imports=["FOO.dll"])
    configs[sibling] = _image(dll=True)
    configs[internal] = _image(dll=True)

    with pytest.raises(SystemExit, match="Ambiguous reachable DLL import"):
        _audit(build, app, configs, monkeypatch)


def test_malformed_pe_is_rejected_before_parser_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, configs = _base_bundle(tmp_path)
    malformed = app / "_internal" / "malformed.dll"
    malformed.parent.mkdir(parents=True, exist_ok=True)
    malformed.write_bytes(b"MZ" + (b"\x00" * 10))

    with pytest.raises(SystemExit, match="Malformed DOS header"):
        _audit(build, app, configs, monkeypatch)


def test_missing_arbitrary_dll_is_not_treated_as_a_system_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, configs = _base_bundle(tmp_path)
    configs[app / "AudioAtlas.exe"] = _image(
        dll=False,
        imports=["kernel32.dll", "not-a-windows-component.dll", "vcruntime140.dll"],
    )

    with pytest.raises(SystemExit, match="not-a-windows-component.dll"):
        _audit(build, app, configs, monkeypatch)


def test_reachable_plain_text_dll_cannot_satisfy_an_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, configs = _base_bundle(tmp_path)
    extension = _write_pe(app / "_internal" / "package" / "module.pyd")
    (app / "_internal" / "required.dll").write_text("not PE", encoding="utf-8")
    configs[extension] = _image(dll=True, imports=["required.dll"])

    with pytest.raises(SystemExit, match="malformed headers"):
        _audit(build, app, configs, monkeypatch)


def test_inventory_root_is_stable_across_repeated_audits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, configs = _base_bundle(tmp_path)

    first = _audit(build, app, configs, monkeypatch)
    second = _audit(build, app, configs, monkeypatch)

    assert first == second
