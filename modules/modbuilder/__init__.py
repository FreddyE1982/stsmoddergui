from __future__ import annotations

from .deck import Deck, DeckStatistics
from .character import (
    CHARACTER_VALIDATION_HOOK,
    Character,
    CharacterColorConfig,
    CharacterDeckSnapshot,
    CharacterImageConfig,
    CharacterStartConfig,
    CharacterValidationReport,
)
from plugins import PLUGIN_MANAGER

PLUGIN_MANAGER.expose("Deck", Deck)
PLUGIN_MANAGER.expose("DeckStatistics", DeckStatistics)
PLUGIN_MANAGER.expose("Character", Character)
PLUGIN_MANAGER.expose("CharacterStartConfig", CharacterStartConfig)
PLUGIN_MANAGER.expose("CharacterImageConfig", CharacterImageConfig)
PLUGIN_MANAGER.expose("CharacterColorConfig", CharacterColorConfig)
PLUGIN_MANAGER.expose("CharacterDeckSnapshot", CharacterDeckSnapshot)
PLUGIN_MANAGER.expose("CharacterValidationReport", CharacterValidationReport)
PLUGIN_MANAGER.expose("CHARACTER_VALIDATION_HOOK", CHARACTER_VALIDATION_HOOK)
PLUGIN_MANAGER.expose_module("modules.modbuilder")

__all__ = [
    "Deck",
    "DeckStatistics",
    "Character",
    "CharacterStartConfig",
    "CharacterImageConfig",
    "CharacterColorConfig",
    "CharacterDeckSnapshot",
    "CharacterValidationReport",
    "CHARACTER_VALIDATION_HOOK",
]
