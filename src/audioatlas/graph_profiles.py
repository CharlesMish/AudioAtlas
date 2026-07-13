"""Lightweight graph-profile names shared by the CLI and selection logic."""

from __future__ import annotations

VALID_PROFILES = ("compact", "minimal", "standard", "full")
PROFILE_ALIASES = {"compact": "minimal"}


def selection_profile(profile: str) -> str:
    """Return the underlying graph-membership profile for a public profile name."""

    return PROFILE_ALIASES.get(profile, profile)
