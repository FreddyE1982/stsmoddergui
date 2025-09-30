"""Demonstration experimental feature used for integration tests.

The :mod:`sample_feature` module keeps track of an in-memory flag that can be
flipped on and off via :func:`modules.basemod_wrapper.experimental.on` and
:func:`modules.basemod_wrapper.experimental.off`.  Real experimental features
should follow the same API contract: all runtime state must be established in
:func:`activate` and torn down in :func:`deactivate` so they can be toggled
safely at runtime.
"""
from __future__ import annotations

from typing import List

_ENABLED: bool = False
_HISTORY: List[str] = []


def activate() -> None:
    """Mark the experimental feature as enabled."""

    global _ENABLED
    _ENABLED = True
    _HISTORY.append("on")


def deactivate() -> None:
    """Mark the experimental feature as disabled."""

    global _ENABLED
    _ENABLED = False
    _HISTORY.append("off")


def is_enabled() -> bool:
    """Return ``True`` when the feature is currently enabled."""

    return _ENABLED


def history() -> List[str]:
    """Return a copy of the activation history for inspection."""

    return list(_HISTORY)


def reset() -> None:
    """Reset the feature to its initial state for testing purposes."""

    global _ENABLED
    _ENABLED = False
    _HISTORY.clear()
