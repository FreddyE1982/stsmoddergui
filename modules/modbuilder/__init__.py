from __future__ import annotations

from .deck import Deck
from .character import Character, CharacterColorConfig, CharacterImageConfig, CharacterStartConfig
from plugins import PLUGIN_MANAGER

PLUGIN_MANAGER.expose("Deck", Deck)
PLUGIN_MANAGER.expose("Character", Character)
PLUGIN_MANAGER.expose("CharacterStartConfig", CharacterStartConfig)
PLUGIN_MANAGER.expose("CharacterImageConfig", CharacterImageConfig)
PLUGIN_MANAGER.expose("CharacterColorConfig", CharacterColorConfig)
PLUGIN_MANAGER.expose_module("modules.modbuilder")

__all__ = [
    "Deck",
    "Character",
    "CharacterStartConfig",
    "CharacterImageConfig",
    "CharacterColorConfig",
]
