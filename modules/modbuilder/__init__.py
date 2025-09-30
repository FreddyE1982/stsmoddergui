from __future__ import annotations

from .deck import Deck, DeckStatistics, build_statistics_from_cards
from .analytics import DeckAnalytics, DeckAnalyticsRow, build_deck_analytics, tabulate_blueprints
from .character import (
    CHARACTER_VALIDATION_HOOK,
    Character,
    CharacterColorConfig,
    CharacterDeckSnapshot,
    CharacterImageConfig,
    CharacterStartConfig,
    CharacterValidationReport,
)
from .runtime_env import (
    PlatformBootstrap,
    PythonRuntimeBootstrapPlan,
    PythonRuntimeDescriptor,
    bootstrap_python_runtime,
    discover_python_runtime,
    execute_bootstrap_plan,
    write_runtime_bootstrapper,
)
from plugins import PLUGIN_MANAGER

PLUGIN_MANAGER.expose("Deck", Deck)
PLUGIN_MANAGER.expose("DeckStatistics", DeckStatistics)
PLUGIN_MANAGER.expose("build_statistics_from_cards", build_statistics_from_cards)
PLUGIN_MANAGER.expose("DeckAnalytics", DeckAnalytics)
PLUGIN_MANAGER.expose("DeckAnalyticsRow", DeckAnalyticsRow)
PLUGIN_MANAGER.expose("build_deck_analytics", build_deck_analytics)
PLUGIN_MANAGER.expose("tabulate_blueprints", tabulate_blueprints)
PLUGIN_MANAGER.expose("Character", Character)
PLUGIN_MANAGER.expose("CharacterStartConfig", CharacterStartConfig)
PLUGIN_MANAGER.expose("CharacterImageConfig", CharacterImageConfig)
PLUGIN_MANAGER.expose("CharacterColorConfig", CharacterColorConfig)
PLUGIN_MANAGER.expose("CharacterDeckSnapshot", CharacterDeckSnapshot)
PLUGIN_MANAGER.expose("CharacterValidationReport", CharacterValidationReport)
PLUGIN_MANAGER.expose("CHARACTER_VALIDATION_HOOK", CHARACTER_VALIDATION_HOOK)
PLUGIN_MANAGER.expose("discover_python_runtime", discover_python_runtime)
PLUGIN_MANAGER.expose("bootstrap_python_runtime", bootstrap_python_runtime)
PLUGIN_MANAGER.expose("execute_bootstrap_plan", execute_bootstrap_plan)
PLUGIN_MANAGER.expose("PythonRuntimeDescriptor", PythonRuntimeDescriptor)
PLUGIN_MANAGER.expose("PythonRuntimeBootstrapPlan", PythonRuntimeBootstrapPlan)
PLUGIN_MANAGER.expose("PlatformBootstrap", PlatformBootstrap)
PLUGIN_MANAGER.expose("write_runtime_bootstrapper", write_runtime_bootstrapper)
PLUGIN_MANAGER.expose_module("modules.modbuilder")

__all__ = [
    "Deck",
    "DeckStatistics",
    "build_statistics_from_cards",
    "DeckAnalytics",
    "DeckAnalyticsRow",
    "build_deck_analytics",
    "tabulate_blueprints",
    "Character",
    "CharacterStartConfig",
    "CharacterImageConfig",
    "CharacterColorConfig",
    "CharacterDeckSnapshot",
    "CharacterValidationReport",
    "CHARACTER_VALIDATION_HOOK",
    "discover_python_runtime",
    "bootstrap_python_runtime",
    "execute_bootstrap_plan",
    "PythonRuntimeDescriptor",
    "PythonRuntimeBootstrapPlan",
    "PlatformBootstrap",
    "write_runtime_bootstrapper",
]
