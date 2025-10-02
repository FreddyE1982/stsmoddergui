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
from importlib import import_module

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
    "DigimonStance",
    "DigimonStanceContext",
    "DigimonStanceManager",
    "DigimonStanceError",
    "DigimonStabilityError",
    "DigimonStanceRequirementError",
    "DigiviceActivationError",
    "PowerGrant",
    "StanceStatProfile",
    "StanceStabilityConfig",
    "StanceTransition",
    "NaturalRookieStance",
    "DigiviceChampionStance",
    "DigiviceUltraStance",
    "SkullGreymonInstabilityStance",
    "WarpMegaStance",
    "BurstMegaStance",
    "ArmorDigieggStance",
    "JogressFusionStance",
    "OmnimonFusionStance",
    "ImperialdramonPaladinModeStance",
]

_STANCE_EXPORTS = {
    "DigimonStance": "mods.digitalesmonster.stances",
    "DigimonStanceContext": "mods.digitalesmonster.stances",
    "DigimonStanceManager": "mods.digitalesmonster.stances",
    "DigimonStanceError": "mods.digitalesmonster.stances",
    "DigimonStabilityError": "mods.digitalesmonster.stances",
    "DigimonStanceRequirementError": "mods.digitalesmonster.stances",
    "DigiviceActivationError": "mods.digitalesmonster.stances",
    "PowerGrant": "mods.digitalesmonster.stances",
    "StanceStatProfile": "mods.digitalesmonster.stances",
    "StanceStabilityConfig": "mods.digitalesmonster.stances",
    "StanceTransition": "mods.digitalesmonster.stances",
    "NaturalRookieStance": "mods.digitalesmonster.stances",
    "DigiviceChampionStance": "mods.digitalesmonster.stances",
    "DigiviceUltraStance": "mods.digitalesmonster.stances",
    "SkullGreymonInstabilityStance": "mods.digitalesmonster.stances",
    "WarpMegaStance": "mods.digitalesmonster.stances",
    "BurstMegaStance": "mods.digitalesmonster.stances",
    "ArmorDigieggStance": "mods.digitalesmonster.stances",
    "JogressFusionStance": "mods.digitalesmonster.stances",
    "OmnimonFusionStance": "mods.digitalesmonster.stances",
    "ImperialdramonPaladinModeStance": "mods.digitalesmonster.stances",
}


def __getattr__(name: str):  # pragma: no cover - simple lazy import helper
    if name in _STANCE_EXPORTS:
        module = import_module(_STANCE_EXPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(name)


PLUGIN_MANAGER.expose_module("mods.digitalesmonster", alias="digitalesmonster")
PLUGIN_MANAGER.expose_lazy_module("mods.digitalesmonster.stances", alias="digitalesmonster_stances")
