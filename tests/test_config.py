from __future__ import annotations

import pytest

from audioatlas.config import AnalysisConfig


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"n_fft": 0}, "n_fft"),
        ({"hop_length": 0}, "hop_length"),
        ({"rms_frame_length": 0}, "rms_frame_length"),
        ({"true_peak_oversample": 0}, "true_peak_oversample"),
        ({"welch_nperseg": 0}, "welch_nperseg"),
        ({"max_plot_points": 0}, "max_plot_points"),
        ({"max_findings": 0}, "max_findings"),
        ({"report_max_time_ranges": 0}, "report_max_time_ranges"),
        ({"window": "  "}, "window"),
        ({"db_floor": float("nan")}, "db_floor"),
        ({"db_floor": 0.0}, "db_floor"),
        ({"clipping_threshold": float("inf")}, "clipping_threshold"),
        ({"near_clipping_threshold": float("nan")}, "near_clipping_threshold"),
        ({"correlation_min_rms_dbfs": float("nan")}, "correlation_min_rms_dbfs"),
        ({"onset_density_window_seconds": float("inf")}, "onset_density_window_seconds"),
        ({"short_term_lufs_window_seconds": 0.0}, "short_term_lufs_window_seconds"),
        ({"short_term_lufs_hop_seconds": float("nan")}, "short_term_lufs_hop_seconds"),
        ({"band_finding_min_duration_seconds": float("nan")}, "band_finding_min_duration_seconds"),
        ({"band_finding_min_relative_db": 0.1}, "band_finding_min_relative_db"),
        ({"finding_min_time_range_seconds": float("inf")}, "finding_min_time_range_seconds"),
    ],
)
def test_analysis_config_rejects_invalid_numeric_domains(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        AnalysisConfig(**overrides).validate()  # type: ignore[arg-type]


def test_default_analysis_config_remains_valid() -> None:
    AnalysisConfig().validate()
