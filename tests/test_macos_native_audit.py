from __future__ import annotations

import importlib.util
import os
import plistlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
MACH_O_HEADER = b"\xcf\xfa\xed\xfe" + (b"\x00" * 28)


def _build_script():
    spec = importlib.util.spec_from_file_location(
        "build_macos_app_native_audit",
        ROOT / "scripts" / "build_macos_app.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_mach_o(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MACH_O_HEADER)
    return path


def _app_fixture(tmp_path: Path) -> tuple[Path, Path]:
    app = tmp_path / "AudioAtlas.app"
    contents = app / "Contents"
    executable = _write_mach_o(contents / "MacOS" / "AudioAtlas")
    info = {
        "CFBundleIdentifier": "com.charlesmish.audioatlas",
        "CFBundleVersion": "1",
        "CFBundleExecutable": "AudioAtlas",
        "LSMinimumSystemVersion": "14.0",
    }
    with (contents / "Info.plist").open("wb") as stream:
        plistlib.dump(info, stream)
    return app, executable


class MockNativeTools:
    def __init__(
        self,
        *,
        dependencies: dict[Path, list[str]] | None = None,
        install_ids: dict[Path, str] | None = None,
        rpaths: dict[Path, list[str]] | None = None,
    ) -> None:
        self.dependencies = dependencies or {}
        self.install_ids = install_ids or {}
        self.rpaths = rpaths or {}
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args: str, **kwargs: object) -> SimpleNamespace:
        self.calls.append(args)
        tool = args[0]
        path = Path(args[-1])
        if tool == "lipo":
            return SimpleNamespace(stdout="arm64\n", stderr="")
        if tool == "vtool":
            return SimpleNamespace(stdout="  minos 14.0\n", stderr="")
        if tool != "otool":
            raise AssertionError(f"unexpected native tool: {args!r}")
        if args[1] == "-L":
            linked = self.dependencies.get(path, ["/usr/lib/libSystem.B.dylib"])
            lines = "".join(
                f"\t{name} (compatibility version 1.0.0, current version 1.0.0)\n"
                for name in linked
            )
            return SimpleNamespace(stdout=f"{path}:\n{lines}", stderr="")
        if args[1] == "-D":
            install_id = self.install_ids.get(path)
            suffix = f"\n{install_id}\n" if install_id else "\n"
            return SimpleNamespace(stdout=f"{path}:{suffix}", stderr="")
        if args[1] == "-l":
            commands = "".join(
                "Load command 1\n"
                "          cmd LC_RPATH\n"
                "      cmdsize 40\n"
                f"         path {rpath} (offset 12)\n"
                for rpath in self.rpaths.get(path, [])
            )
            return SimpleNamespace(stdout=commands, stderr="")
        raise AssertionError(f"unexpected otool mode: {args!r}")


def test_valid_frameworks_dependency_records_concrete_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, executable = _app_fixture(tmp_path)
    library = _write_mach_o(app / "Contents" / "Frameworks" / "libfoo.dylib")
    tools = MockNativeTools(
        dependencies={
            executable: ["@rpath/libfoo.dylib", "/usr/lib/libSystem.B.dylib"],
            library: ["@rpath/libfoo.dylib", "/usr/lib/libSystem.B.dylib"],
        },
        install_ids={library: "@rpath/libfoo.dylib"},
        rpaths={executable: ["@executable_path/../Frameworks"]},
    )
    monkeypatch.setattr(build, "_run", tools)

    dependencies = build._audit_bundle(app)

    assert dependencies == (
        build.ResolvedDependency(
            importer=executable.resolve(),
            install_name="@rpath/libfoo.dylib",
            resolved_path=library.resolve(),
        ),
    )
    inspected_rpaths = {
        Path(call[-1]) for call in tools.calls if call[:2] == ("otool", "-l")
    }
    assert inspected_rpaths == {executable, library}
    assert not any(call[0] == "codesign" for call in tools.calls)


def test_loader_and_executable_paths_use_the_importing_image_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, executable = _app_fixture(tmp_path)
    plugin = _write_mach_o(app / "Contents" / "Frameworks" / "Plugins" / "plugin.so")
    local = _write_mach_o(plugin.parent / "liblocal.dylib")
    global_library = _write_mach_o(app / "Contents" / "Frameworks" / "libglobal.dylib")
    tools = MockNativeTools(
        dependencies={
            plugin: [
                "@loader_path/liblocal.dylib",
                "@executable_path/../Frameworks/libglobal.dylib",
            ],
            local: ["@loader_path/liblocal.dylib"],
            global_library: ["@loader_path/libglobal.dylib"],
        },
        install_ids={
            local: "@loader_path/liblocal.dylib",
            global_library: "@loader_path/libglobal.dylib",
        },
    )
    monkeypatch.setattr(build, "_run", tools)

    dependencies = build._audit_bundle(app)

    assert {(item.install_name, item.resolved_path) for item in dependencies} == {
        ("@loader_path/liblocal.dylib", local.resolve()),
        (
            "@executable_path/../Frameworks/libglobal.dylib",
            global_library.resolve(),
        ),
    }


def test_dependent_library_inherits_the_executable_run_path_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, executable = _app_fixture(tmp_path)
    plugin = _write_mach_o(app / "Contents" / "Frameworks" / "plugin.dylib")
    helper = _write_mach_o(app / "Contents" / "Frameworks" / "helper.dylib")
    tools = MockNativeTools(
        dependencies={
            executable: ["@rpath/plugin.dylib"],
            plugin: ["@rpath/helper.dylib"],
            helper: ["@rpath/helper.dylib"],
        },
        install_ids={
            plugin: "@rpath/plugin.dylib",
            helper: "@rpath/helper.dylib",
        },
        rpaths={executable: ["@executable_path/../Frameworks"]},
    )
    monkeypatch.setattr(build, "_run", tools)

    dependencies = build._audit_bundle(app)

    assert {(item.importer, item.resolved_path) for item in dependencies} == {
        (executable.resolve(), plugin.resolve()),
        (plugin.resolve(), helper.resolve()),
    }


def test_run_path_context_propagates_through_a_non_executable_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, executable = _app_fixture(tmp_path)
    plugin = _write_mach_o(app / "Contents" / "Frameworks" / "plugin.dylib")
    child = _write_mach_o(app / "Contents" / "Frameworks" / "nested" / "child.dylib")
    helper = _write_mach_o(child.parent / "helper.dylib")
    tools = MockNativeTools(
        dependencies={
            executable: ["@loader_path/../Frameworks/plugin.dylib"],
            plugin: ["@rpath/child.dylib"],
            child: ["@rpath/helper.dylib"],
            helper: ["@rpath/helper.dylib"],
        },
        install_ids={
            plugin: "@loader_path/../Frameworks/plugin.dylib",
            child: "@rpath/child.dylib",
            helper: "@rpath/helper.dylib",
        },
        rpaths={plugin: ["@loader_path/nested"]},
    )
    monkeypatch.setattr(build, "_run", tools)

    dependencies = build._audit_bundle(app)

    assert {(item.importer, item.resolved_path) for item in dependencies} == {
        (executable.resolve(), plugin.resolve()),
        (plugin.resolve(), child.resolve()),
        (child.resolve(), helper.resolve()),
    }


@pytest.mark.parametrize(
    ("placement", "contents", "message"),
    [
        ("Resources", b"plain text", "resolved dependency is not Mach-O"),
        ("Resources", MACH_O_HEADER, "exactly one existing in-bundle resolution"),
    ],
)
def test_dependency_is_not_accepted_by_basename_or_wrong_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    placement: str,
    contents: bytes,
    message: str,
) -> None:
    build = _build_script()
    app, executable = _app_fixture(tmp_path)
    misplaced = app / "Contents" / placement / "libfoo.dylib"
    misplaced.parent.mkdir(parents=True)
    misplaced.write_bytes(contents)
    tools = MockNativeTools(
        dependencies={executable: ["@rpath/libfoo.dylib"]},
        rpaths={
            executable: [
                "@executable_path/../Resources"
                if contents == b"plain text"
                else "@executable_path/../Frameworks"
            ]
        },
    )
    monkeypatch.setattr(build, "_run", tools)

    with pytest.raises(SystemExit, match=message):
        build._audit_bundle(app)


def test_duplicate_rpath_targets_are_rejected_as_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, executable = _app_fixture(tmp_path)
    _write_mach_o(app / "Contents" / "Frameworks" / "libfoo.dylib")
    _write_mach_o(app / "Contents" / "Resources" / "libfoo.dylib")
    tools = MockNativeTools(
        dependencies={executable: ["@rpath/libfoo.dylib"]},
        rpaths={
            executable: [
                "@executable_path/../Frameworks",
                "@executable_path/../Resources",
            ]
        },
    )
    monkeypatch.setattr(build, "_run", tools)

    with pytest.raises(SystemExit, match="exactly one existing in-bundle resolution"):
        build._audit_bundle(app)


def test_rpath_dependency_without_lc_rpath_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, executable = _app_fixture(tmp_path)
    tools = MockNativeTools(dependencies={executable: ["@rpath/libfoo.dylib"]})
    monkeypatch.setattr(build, "_run", tools)

    with pytest.raises(SystemExit, match="has no LC_RPATH"):
        build._audit_bundle(app)


def test_absolute_external_dependency_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, executable = _app_fixture(tmp_path)
    outside = _write_mach_o(tmp_path / "outside" / "libfoo.dylib")
    tools = MockNativeTools(dependencies={executable: [str(outside)]})
    monkeypatch.setattr(build, "_run", tools)

    with pytest.raises(SystemExit, match="absolute non-system dependency"):
        build._audit_bundle(app)


@pytest.mark.parametrize(
    ("target_kind", "message"),
    [
        ("broken", "broken symlink"),
        ("relative-external", "escaping symlink"),
        ("absolute-external", "absolute external symlink"),
    ],
)
def test_unsafe_bundle_symlinks_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target_kind: str,
    message: str,
) -> None:
    build = _build_script()
    app, _ = _app_fixture(tmp_path)
    link = app / "Contents" / "Frameworks" / "libfoo.dylib"
    link.parent.mkdir(parents=True)
    outside = _write_mach_o(tmp_path / "outside" / "libfoo.dylib")
    if target_kind == "broken":
        link.symlink_to("missing.dylib")
    elif target_kind == "relative-external":
        link.symlink_to(Path(os.path.relpath(outside, link.parent)))
    else:
        link.symlink_to(outside)
    monkeypatch.setattr(build, "_run", MockNativeTools())

    with pytest.raises(SystemExit, match=message):
        build._audit_bundle(app)


def test_strict_code_signature_verification_is_a_separate_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    app, _ = _app_fixture(tmp_path)
    calls = []
    monkeypatch.setattr(
        build,
        "_run",
        lambda *args, **kwargs: calls.append(args) or SimpleNamespace(stdout="", stderr=""),
    )

    build._verify_code_signature(app)

    assert calls == [("codesign", "--verify", "--deep", "--strict", str(app))]


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS tools")
def test_real_built_app_native_dependency_closure() -> None:
    app_value = os.environ.get("AUDIOATLAS_TEST_APP")
    if not app_value:
        pytest.skip("AUDIOATLAS_TEST_APP is set only after the workflow builds the app")
    app = Path(app_value).resolve()
    build = _build_script()

    dependencies = build._audit_bundle(app)

    assert dependencies
    assert all(item.resolved_path.is_relative_to(app) for item in dependencies)
    assert all(build._is_mach_o(item.resolved_path) for item in dependencies)
