"""Analysis provenance and comparability fingerprints.

The public report remains path-safe. Provenance records implementation and
configuration identities that affect reproducibility without recording the
input's local directory or a human-readable track identifier.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from audioatlas import __version__
from audioatlas.config import AnalysisConfig
from audioatlas.release import FINDING_RULESET_VERSION, SUMMARY_SCHEMA_VERSION

PROVENANCE_FORMAT_VERSION = 1

# These files define measurements or the data fed into them. Report rendering
# and CLI presentation are intentionally excluded from the measurement code
# fingerprint so cosmetic changes do not invalidate numerical comparability.
_MEASUREMENT_CODE_PATHS = (
    "analysis/__init__.py",
    "analysis/bundle.py",
    "analysis/dynamics.py",
    "analysis/levels.py",
    "analysis/loudness.py",
    "analysis/spectral.py",
    "analysis/stereo.py",
    "analysis/tonal.py",
    "config.py",
    "io.py",
    "utils.py",
)
_RULE_CODE_PATHS = ("analysis/findings.py",)
_DEPENDENCY_DISTRIBUTIONS = (
    "numpy",
    "scipy",
    "soundfile",
    "librosa",
    "numba",
    "pyloudnorm",
)


def canonical_json_sha256(value: object) -> str:
    """Return SHA-256 for a stable JSON representation."""

    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def track_identity_block(track_id: str | None) -> dict[str, object]:
    """Return a non-plaintext identity block for revision workflows.

    The supplied token is never written to the report. Only its SHA-256 digest
    is retained, allowing independently named exports of the same track to be
    matched without publishing the token itself. Hashing does not make a short
    or reused token secret.
    """

    if track_id is None:
        return {"kind": "none", "track_id_sha256": None}
    normalized = track_id.strip()
    if not normalized:
        raise ValueError("track_id cannot be blank")
    if len(normalized) > 512:
        raise ValueError("track_id must be 512 characters or fewer")
    if any(char in normalized for char in ("\n", "\r", "\x00")):
        raise ValueError("track_id cannot contain line breaks or null characters")
    return {
        "kind": "user-supplied-sha256",
        "track_id_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    }


def build_analysis_provenance(config: AnalysisConfig) -> dict[str, object]:
    """Build a path-safe provenance block for one analysis run."""

    config_payload = asdict(config)
    config_hash = canonical_json_sha256(config_payload)
    measurement_code_hash = measurement_code_sha256()
    rule_code_hash = finding_rule_code_sha256()
    dependencies = _dependency_versions()
    decoder = _decoder_versions(dependencies)
    measurement_method = {
        "approximate_true_peak": {
            "method": (
                "sample_peak"
                if config.true_peak_oversample == 1
                else "scipy.signal.resample_poly"
            ),
            "oversample_factor": config.true_peak_oversample,
            "standards_grade_meter": False,
        },
        "integrated_loudness": {
            "method": "pyloudnorm.Meter.integrated_loudness",
        },
    }

    compatible_payload = {
        "analysis_config_sha256": config_hash,
        "measurement_code_sha256": measurement_code_hash,
        "dependencies": dependencies,
        "decoder": decoder,
        "measurement_methods": measurement_method,
    }
    compatible_signature = canonical_json_sha256(compatible_payload)

    environment = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform_system": platform.system() or "unknown",
        "platform_machine": platform.machine() or "unknown",
        "byteorder": sys.byteorder,
    }
    exact_signature = canonical_json_sha256(
        {
            "compatible_analysis_sha256": compatible_signature,
            "environment": environment,
        }
    )

    return {
        "format_version": PROVENANCE_FORMAT_VERSION,
        "audioatlas_version": __version__,
        "summary_schema_version": SUMMARY_SCHEMA_VERSION,
        "finding_ruleset_version": FINDING_RULESET_VERSION,
        "analysis_config_sha256": config_hash,
        "measurement_code_sha256": measurement_code_hash,
        "finding_rule_code_sha256": rule_code_hash,
        "dependencies": dependencies,
        "decoder": decoder,
        "measurement_methods": measurement_method,
        "environment": environment,
        "compatible_analysis_sha256": compatible_signature,
        "exact_environment_sha256": exact_signature,
    }


def _dependency_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for distribution in _DEPENDENCY_DISTRIBUTIONS:
        try:
            out[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            out[distribution] = None
    return out


def _decoder_versions(dependencies: dict[str, str | None]) -> dict[str, str | None]:
    libsndfile_version: str | None = None
    try:
        import soundfile as sf

        value = getattr(sf, "__libsndfile_version__", None)
        if value is not None:
            libsndfile_version = str(value)
    except Exception:  # pragma: no cover - only reached in unusual broken installs
        pass
    return {
        "python_binding": "soundfile",
        "soundfile_version": dependencies.get("soundfile"),
        "libsndfile_version": libsndfile_version,
    }


def _code_fingerprint(relative_paths: tuple[str, ...]) -> str:
    package_root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    files: list[Path] = []
    for relative in relative_paths:
        path = package_root / relative
        if path.is_dir():
            files.extend(sorted(path.rglob("*.py")))
        elif path.is_file():
            files.append(path)
    for path in sorted(set(files), key=lambda item: item.relative_to(package_root).as_posix()):
        relative = path.relative_to(package_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@lru_cache(maxsize=1)
def measurement_code_sha256() -> str:
    """Return the current installed measurement-code fingerprint."""

    return _code_fingerprint(_MEASUREMENT_CODE_PATHS)


@lru_cache(maxsize=1)
def finding_rule_code_sha256() -> str:
    """Return the current installed finding-rule implementation fingerprint."""

    return _code_fingerprint(_RULE_CODE_PATHS)


def provenance_signature(summary: dict[str, Any], key: str) -> str | None:
    """Return a validated provenance signature from a summary."""

    block = summary.get("analysis_provenance")
    if not isinstance(block, dict):
        return None
    value = block.get(key)
    if isinstance(value, str) and len(value) == 64:
        return value
    return None
