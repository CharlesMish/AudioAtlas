from __future__ import annotations

import pytest

from audioatlas.desktop_smoke import run_frozen_smoke


@pytest.mark.parametrize("depth", [None, "overview", "standard", "detailed"])
def test_smoke_uses_validated_depth_and_standard_default(tmp_path, monkeypatch, depth):
    import audioatlas.app_core as app_core

    report = tmp_path / "report.html"
    report.touch()
    calls = []

    def analyze(path, **kwargs):
        from types import SimpleNamespace
        calls.append(kwargs)
        return SimpleNamespace(html_report_path=report)

    monkeypatch.setattr(app_core, "analyze_for_app", analyze)
    args = ["--smoke-analyze", "track.wav", "--output-parent", str(tmp_path)]
    if depth is not None:
        args.extend(["--report-depth", depth])
    run_frozen_smoke(args)
    assert calls[0]["report_depth"] == (depth or "standard")


def test_smoke_rejects_invalid_depth_before_analysis(tmp_path, monkeypatch):
    import audioatlas.app_core as app_core

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid depth must not start analysis")

    monkeypatch.setattr(app_core, "analyze_for_app", forbidden)
    with pytest.raises(SystemExit) as error:
        run_frozen_smoke(["--smoke-analyze", "track.wav", "--output-parent", str(tmp_path),
                          "--report-depth", "custom"])
    assert error.value.code == 2
