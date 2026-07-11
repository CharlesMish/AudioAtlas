"""AudioAtlas: factual single-track audio maps."""

from audioatlas.release import (
    CATALOG_SCHEMA_VERSION,
    FINDING_RULESET_VERSION,
    FINDINGS_SCHEMA_VERSION,
    RELEASE_LABEL,
    SUMMARY_SCHEMA_VERSION,
)

__all__ = [
    "CATALOG_SCHEMA_VERSION",
    "FINDING_RULESET_VERSION",
    "FINDINGS_SCHEMA_VERSION",
    "RELEASE_LABEL",
    "SUMMARY_SCHEMA_VERSION",
    "__version__",
]

__version__ = "0.2.0a2"
