from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

import audioatlas.app_core as app_core
from audioatlas.app_core import (
    AppInputError,
    AppInputInfo,
    LargeFileDecision,
    default_report_directory,
    friendly_error_message,
    inspect_app_input,
    prepare_and_analyze_for_app,
    safe_report_directory,
    validate_app_input,
)
from audioatlas.errors import AnalysisCancelled, AudioLoadError
from audioatlas.output import OUTPUT_MARKER_FILENAME, write_output_manifest
from audioatlas.pipeline import CancellationToken


def test_default_report_directory_is_visible_beside_source(tmp_path: Path):
    source = tmp_path / "Mix v3.wav"

    assert default_report_directory(source) == tmp_path / "AudioAtlas Report – Mix v3"


@pytest.mark.parametrize("suffix", [".wav", ".WAVE", ".flac", ".ogg", ".aif", ".aiff", ".mp3"])
def test_validate_app_input_accepts_documented_audio_extensions(tmp_path: Path, suffix: str):
    source = tmp_path / f"track{suffix}"
    source.touch()

    assert validate_app_input(source) == source


def test_validate_app_input_rejects_multiple_non_audio_shapes(tmp_path: Path):
    unsupported = tmp_path / "notes.txt"
    unsupported.touch()

    with pytest.raises(AppInputError, match="not supported"):
        validate_app_input(unsupported)
    with pytest.raises(AppInputError, match="one audio file"):
        validate_app_input(tmp_path)


def test_analyze_for_app_uses_fixed_friend_facing_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "song.wav"
    source.touch()
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    sentinel = object()

    def fake_analyze(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return sentinel

    monkeypatch.setattr(app_core, "_analyze_file", fake_analyze)

    result = app_core.analyze_for_app(source)

    assert result is sentinel
    args, kwargs = calls[0]
    assert args == (source, default_report_directory(source))
    assert kwargs["theme_name"] == "default"
    assert kwargs["presentation_mode"] == "studio"
    assert kwargs["include_local_paths"] is False
    assert kwargs["selection"].profile == "standard"


def test_analyze_for_app_can_retry_under_selected_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "song.wav"
    source.touch()
    destination = tmp_path / "reports"
    calls: list[tuple[object, ...]] = []

    def fake_analyze(*args: object, **kwargs: object) -> object:
        calls.append(args)
        return object()

    monkeypatch.setattr(app_core, "_analyze_file", fake_analyze)

    app_core.analyze_for_app(source, output_parent=destination)

    assert calls[0][1] == destination / "AudioAtlas Report – song"


def test_safe_report_directory_reuses_only_a_report_for_the_same_filename(tmp_path: Path):
    wav = tmp_path / "song.wav"
    flac = tmp_path / "song.flac"
    wav.touch()
    flac.touch()
    report = default_report_directory(wav)
    report.mkdir()
    (report / "summary.json").write_text(
        json.dumps({"metadata": {"filename": wav.name}}), encoding="utf-8"
    )
    write_output_manifest(
        report,
        kind="single-track-report",
        generated_files=["summary.json", OUTPUT_MARKER_FILENAME],
    )

    assert safe_report_directory(wav) == report
    assert safe_report_directory(flac) == tmp_path / "AudioAtlas Report – song.flac"


def test_safe_report_directory_skips_unowned_and_numbered_collisions(tmp_path: Path):
    source = tmp_path / "song.wav"
    source.touch()
    base = default_report_directory(source)
    base.mkdir()
    (base / "notes.txt").write_text("human", encoding="utf-8")
    full = tmp_path / "AudioAtlas Report – song.wav"
    full.mkdir()
    (full / "notes.txt").write_text("human", encoding="utf-8")

    assert safe_report_directory(source) == tmp_path / "AudioAtlas Report – song.wav (2)"


def test_safe_report_directory_truncates_unicode_component_deterministically(tmp_path: Path):
    source = tmp_path / (("音" * 80) + ".wav")

    first = safe_report_directory(source)
    second = safe_report_directory(source)

    assert first == second
    assert len(first.name.encode("utf-8")) <= 240
    assert first.name.startswith("AudioAtlas Report – ")


def test_inspect_app_input_flags_large_decoded_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "long.wav"
    source.touch()
    monkeypatch.setattr(
        "soundfile.info",
        lambda path: SimpleNamespace(frames=48_000 * 60 * 31, samplerate=48_000, channels=2),
    )

    info = inspect_app_input(source)

    assert info.duration_seconds == 31 * 60
    assert info.needs_large_file_confirmation


def _input_info(source: Path, *, large: bool = False) -> AppInputInfo:
    duration = 31 * 60 if large else 10
    frames = 48_000 * duration
    return AppInputInfo(
        source=source,
        duration_seconds=duration,
        samplerate=48_000,
        channels=2,
        frames=frames,
        estimated_decoded_bytes=frames * 2 * 4,
    )


def test_prepare_and_analyze_inspects_initializes_and_runs_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "song.wav"
    source.touch()
    updates = []
    analyses = []
    inspected = _input_info(source)
    monkeypatch.setattr(app_core, "inspect_app_input", lambda path: inspected)
    monkeypatch.setattr(
        app_core,
        "analyze_for_app",
        lambda *args, **kwargs: analyses.append((args, kwargs)) or "result",
    )

    result = prepare_and_analyze_for_app(
        source,
        preparation_callback=updates.append,
        cancellation_token=CancellationToken(),
    )

    assert result == "result"
    assert [update.stage for update in updates] == ["inspecting", "initializing"]
    assert len(analyses) == 1


def test_prepare_and_analyze_waits_for_large_file_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "large.wav"
    source.touch()
    updates = []
    monkeypatch.setattr(app_core, "inspect_app_input", lambda path: _input_info(source, large=True))
    monkeypatch.setattr(app_core, "analyze_for_app", lambda *args, **kwargs: "result")

    result = prepare_and_analyze_for_app(
        source,
        preparation_callback=updates.append,
        confirmation_callback=lambda info, decision: decision.resolve(True),
        cancellation_token=CancellationToken(),
    )

    assert result == "result"
    assert [update.stage for update in updates] == [
        "inspecting",
        "confirming",
        "initializing",
    ]


def test_prepare_and_analyze_rejects_large_file_without_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "large.wav"
    source.touch()
    monkeypatch.setattr(app_core, "inspect_app_input", lambda path: _input_info(source, large=True))
    monkeypatch.setattr(
        app_core,
        "analyze_for_app",
        lambda *args, **kwargs: pytest.fail("analysis should not start"),
    )

    with pytest.raises(AnalysisCancelled, match="before loading"):
        prepare_and_analyze_for_app(
            source,
            confirmation_callback=lambda info, decision: decision.resolve(False),
            cancellation_token=CancellationToken(),
        )


def test_prepare_and_analyze_honors_cancel_after_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "song.wav"
    source.touch()
    token = CancellationToken()

    def inspect(path: Path) -> AppInputInfo:
        token.cancel()
        return _input_info(source)

    monkeypatch.setattr(app_core, "inspect_app_input", inspect)

    with pytest.raises(AnalysisCancelled):
        prepare_and_analyze_for_app(source, cancellation_token=token)


def test_prepare_and_analyze_honors_cancel_while_waiting_for_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "large.wav"
    source.touch()
    token = CancellationToken()
    monkeypatch.setattr(app_core, "inspect_app_input", lambda path: _input_info(source, large=True))

    with pytest.raises(AnalysisCancelled):
        prepare_and_analyze_for_app(
            source,
            confirmation_callback=lambda info, decision: token.cancel(),
            cancellation_token=token,
        )


def test_prepare_and_analyze_propagates_inspection_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "bad.wav"
    source.touch()
    monkeypatch.setattr(
        app_core,
        "inspect_app_input",
        lambda path: (_ for _ in ()).throw(AudioLoadError(source, "bad metadata")),
    )

    with pytest.raises(AudioLoadError, match="bad metadata"):
        prepare_and_analyze_for_app(source, cancellation_token=CancellationToken())


def test_failed_preparation_leaves_previous_report_byte_for_byte_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "bad.wav"
    source.touch()
    report = tmp_path / "AudioAtlas Report – bad"
    report.mkdir()
    previous = report / "report.html"
    previous.write_bytes(b"previous successful report\x00")
    before = previous.read_bytes()
    monkeypatch.setattr(
        app_core,
        "inspect_app_input",
        lambda path: (_ for _ in ()).throw(AudioLoadError(source, "bad metadata")),
    )

    with pytest.raises(AudioLoadError):
        prepare_and_analyze_for_app(source, cancellation_token=CancellationToken())

    assert previous.read_bytes() == before


def test_prepare_and_analyze_honors_cancel_during_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "song.wav"
    source.touch()
    token = CancellationToken()
    monkeypatch.setattr(app_core, "inspect_app_input", lambda path: _input_info(source))

    def initialize(*args: object, **kwargs: object) -> object:
        token.cancel()
        token.raise_if_cancelled()
        return object()

    monkeypatch.setattr(app_core, "analyze_for_app", initialize)

    with pytest.raises(AnalysisCancelled):
        prepare_and_analyze_for_app(source, cancellation_token=token)


def test_prepare_and_analyze_reuses_inspection_and_confirmation_on_location_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "large.wav"
    source.touch()
    inspected = _input_info(source, large=True)
    monkeypatch.setattr(
        app_core,
        "inspect_app_input",
        lambda path: pytest.fail("metadata should not be inspected twice"),
    )
    monkeypatch.setattr(app_core, "analyze_for_app", lambda *args, **kwargs: "result")

    assert (
        prepare_and_analyze_for_app(
            source,
            input_info=inspected,
            large_file_confirmed=True,
            cancellation_token=CancellationToken(),
        )
        == "result"
    )


def test_preparation_can_block_on_worker_without_blocking_caller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "slow.wav"
    source.touch()
    entered = threading.Event()
    release = threading.Event()

    def inspect(path: Path) -> AppInputInfo:
        entered.set()
        release.wait(timeout=2)
        return _input_info(source)

    monkeypatch.setattr(app_core, "inspect_app_input", inspect)
    monkeypatch.setattr(app_core, "analyze_for_app", lambda *args, **kwargs: "result")
    worker = threading.Thread(
        target=prepare_and_analyze_for_app,
        kwargs={"input_path": source, "cancellation_token": CancellationToken()},
    )

    worker.start()
    assert entered.wait(timeout=1)
    assert worker.is_alive()
    release.set()
    worker.join(timeout=2)
    assert not worker.is_alive()


def test_large_file_decision_is_one_shot():
    decision = LargeFileDecision()

    assert decision.resolve(True)
    assert not decision.resolve(False)
    assert decision.wait(CancellationToken())


def test_friendly_error_does_not_surface_unexpected_internal_paths():
    message = friendly_error_message(RuntimeError("failed at /Users/private/secret.wav"))

    assert "/Users/private" not in message
    assert "previous report" in message
