from __future__ import annotations

import pytest
from click import BadParameter

from audioatlas.cli import _make_selection
from audioatlas.graphs import all_graphs
from audioatlas.graphs.selection import GraphSelection, GraphSelectionError

ALL_KEYS = [graph.key for graph in all_graphs()]
MINIMAL_KEYS = ["waveform_rms", "rms_timeline", "log_spectrogram", "sample_histogram"]
STANDARD_KEYS = [
    "waveform_rms",
    "rms_timeline",
    "crest_factor_timeline",
    "log_spectrogram",
    "average_spectrum",
    "sample_histogram",
    "stereo_correlation",
    "mid_side_energy",
    "spectral_shape",
    "band_energy_timeline",
    "onset_density",
    "chroma_cqt",
    "short_term_lufs",
    "peak_timeline",
]


def _keys(selection: GraphSelection) -> list[str]:
    return [graph.key for graph in selection.resolve(all_graphs())]


def test_profiles_resolve_expected_graphs():
    assert _keys(GraphSelection()) == STANDARD_KEYS
    assert _keys(GraphSelection(profile="standard")) == STANDARD_KEYS
    assert _keys(GraphSelection(profile="full")) == ALL_KEYS
    assert _keys(GraphSelection(profile="minimal")) == MINIMAL_KEYS
    assert _keys(GraphSelection(profile="compact")) == MINIMAL_KEYS
    assert len(_keys(GraphSelection(profile="minimal"))) == 4
    assert len(_keys(GraphSelection(profile="compact"))) == 4
    assert len(_keys(GraphSelection(profile="standard"))) == 14
    assert len(_keys(GraphSelection(profile="full"))) == 17


def test_enable_disable_resolve_in_graph_order():
    selection = GraphSelection(
        profile="minimal",
        enable=("chroma_cqt", "chroma_cqt"),
        disable=("rms_timeline", "rms_timeline"),
    )

    assert _keys(selection) == [
        "waveform_rms",
        "log_spectrogram",
        "sample_histogram",
        "chroma_cqt",
    ]


def test_unknown_graph_key_error_lists_valid_keys():
    with pytest.raises(GraphSelectionError) as excinfo:
        GraphSelection(enable=("missing_graph",)).resolve(all_graphs())

    message = str(excinfo.value)
    assert "missing_graph" in message
    assert "waveform_rms" in message


def test_unknown_profile_error_lists_valid_profiles():
    with pytest.raises(GraphSelectionError) as excinfo:
        GraphSelection(profile="tiny").resolve(all_graphs())

    message = str(excinfo.value)
    assert "tiny" in message
    assert "compact" in message
    assert "minimal" in message
    assert "standard" in message
    assert "full" in message


def test_enable_disable_conflict_error():
    with pytest.raises(GraphSelectionError) as excinfo:
        GraphSelection(enable=("chroma_cqt",), disable=("chroma_cqt",)).resolve(all_graphs())

    assert "chroma_cqt" in str(excinfo.value)


def test_empty_selection_error():
    with pytest.raises(GraphSelectionError) as excinfo:
        GraphSelection(profile="minimal", disable=tuple(MINIMAL_KEYS)).resolve(all_graphs())

    assert "empty" in str(excinfo.value)


def test_graphs_yaml_config_and_cli_merge(tmp_path):
    config_path = tmp_path / "graphs.yaml"
    config_path.write_text(
        """\
sections:
  - name: ignored
    start: 0
graphs:
  profile: minimal
  enable: [chroma_cqt]
  disable: [rms_timeline]
""",
        encoding="utf-8",
    )

    selection = _make_selection(None, ("short_term_lufs",), ("sample_histogram",), config_path)

    assert selection.profile == "minimal"
    assert selection.enable == ("chroma_cqt", "short_term_lufs")
    assert selection.disable == ("rms_timeline", "sample_histogram")
    assert _keys(selection) == ["waveform_rms", "log_spectrogram", "chroma_cqt", "short_term_lufs"]


def test_cli_profile_overrides_graphs_yaml_profile(tmp_path):
    config_path = tmp_path / "graphs.yaml"
    config_path.write_text(
        """\
graphs:
  profile: minimal
  disable: [chroma_cqt]
""",
        encoding="utf-8",
    )

    selection = _make_selection("full", (), (), config_path)

    assert selection.profile == "full"
    assert "chroma_cqt" not in _keys(selection)


def test_graphs_yaml_rejects_malformed_yaml(tmp_path):
    config_path = tmp_path / "bad.yaml"
    config_path.write_text("graphs: [profile: standard\n", encoding="utf-8")

    with pytest.raises(BadParameter):
        _make_selection(None, (), (), config_path)


def test_graphs_yaml_rejects_bad_types(tmp_path):
    config_path = tmp_path / "bad_types.yaml"
    config_path.write_text(
        """\
graphs:
  profile: [standard]
  enable: chroma_cqt
""",
        encoding="utf-8",
    )

    with pytest.raises(BadParameter):
        _make_selection(None, (), (), config_path)
