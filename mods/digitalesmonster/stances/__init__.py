"""Digimon stance framework for the Digitales Monster mod."""
from __future__ import annotations

from importlib import import_module

from .base import (
    DigimonStance,
    DigimonStanceContext,
    DigimonStanceError,
    DigimonStanceManager,
    DigimonStanceRequirementError,
    DigimonStabilityError,
    DigiviceActivationError,
    PowerGrant,
    StanceStatProfile,
    StanceStabilityConfig,
    StanceTransition,
)
from plugins import PLUGIN_MANAGER

__all__ = [
    "DigimonStance",
    "DigimonStanceContext",
    "DigimonStanceError",
    "DigimonStabilityError",
    "DigimonStanceRequirementError",
    "DigiviceActivationError",
    "DigimonStanceManager",
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
]

_DEFERRED_EXPORTS = {
    "NaturalRookieStance": "mods.digitalesmonster.stances.rookie",
    "DigiviceChampionStance": "mods.digitalesmonster.stances.champion",
    "DigiviceUltraStance": "mods.digitalesmonster.stances.ultra",
    "SkullGreymonInstabilityStance": "mods.digitalesmonster.stances.ultra",
    "WarpMegaStance": "mods.digitalesmonster.stances.mega",
    "BurstMegaStance": "mods.digitalesmonster.stances.mega",
    "ArmorDigieggStance": "mods.digitalesmonster.stances.armor",
}


def __getattr__(name: str):  # pragma: no cover - trivial lazy import helper
    if name in _DEFERRED_EXPORTS:
        module = import_module(_DEFERRED_EXPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(name)


PLUGIN_MANAGER.expose_lazy_module("mods.digitalesmonster.stances", alias="digitalesmonster_stances")
