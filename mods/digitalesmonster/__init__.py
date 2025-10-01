"""Digitales Monster mod package entry point."""
from __future__ import annotations

from .project import (
    DigitalesMonsterCharacter,
    DigitalesMonsterDeck,
    DigitalesMonsterProject,
    DigitalesMonsterProjectConfig,
    bootstrap_digitalesmonster_project,
)
from .persistence import (
    LEVEL_STABILITY_PERSIST_KEY,
    LevelStabilityProfile,
    LevelStabilityRecord,
    LevelStabilityStore,
    StabilityPersistFieldAdapter,
)
from plugins import PLUGIN_MANAGER

__all__ = [
    "DigitalesMonsterCharacter",
    "DigitalesMonsterDeck",
    "DigitalesMonsterProject",
    "DigitalesMonsterProjectConfig",
    "bootstrap_digitalesmonster_project",
    "LevelStabilityProfile",
    "LevelStabilityRecord",
    "LevelStabilityStore",
    "StabilityPersistFieldAdapter",
    "LEVEL_STABILITY_PERSIST_KEY",
]

PLUGIN_MANAGER.expose_module("mods.digitalesmonster", alias="digitalesmonster")
