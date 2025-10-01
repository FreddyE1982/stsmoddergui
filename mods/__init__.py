"""Repository packaged mods and mechanic engines.

The :mod:`mods` namespace collects gameplay systems that can be shipped as
mechanics-only experiences.  Modules located here are designed to be entirely
plugin-friendly: they expose their public API through the global
:mod:`plugins` manager so downstream tooling can discover runtime objects,
register extensions and inspect persistent state.

The :class:`AdaptiveMechanicMod` defined in
:mod:`mods.adaptive_deck_evolver.runtime` is exposed immediately for
convenience.
"""
from __future__ import annotations

from plugins import PLUGIN_MANAGER

from .adaptive_deck_evolver import AdaptiveTelemetryCore
from .adaptive_deck_evolver.runtime import AdaptiveMechanicMod
from .digitalesmonster import (
    DigitalesMonsterProject,
    DigitalesMonsterProjectConfig,
    DigitalesMonsterCharacter,
    DigitalesMonsterDeck,
    bootstrap_digitalesmonster_project,
)

__all__ = ["AdaptiveMechanicMod", "AdaptiveTelemetryCore", "DigitalesMonsterProject", "DigitalesMonsterProjectConfig", "DigitalesMonsterCharacter", "DigitalesMonsterDeck", "bootstrap_digitalesmonster_project"]

# Provide friendly aliases for plugin consumers while keeping the automatic
# lazy exposure active.  The plugin manager already exports every repository
# module lazily, however exposing the high level factory under a predictable key
# makes extension authoring substantially easier.
PLUGIN_MANAGER.expose("adaptive_mechanic_mod_factory", AdaptiveMechanicMod)
PLUGIN_MANAGER.expose("adaptive_telemetry_core_relic", AdaptiveTelemetryCore)
PLUGIN_MANAGER.expose_module("mods.adaptive_deck_evolver", alias="adaptive_deck_evolver")
PLUGIN_MANAGER.expose("digitalesmonster_bootstrap_project", bootstrap_digitalesmonster_project)
PLUGIN_MANAGER.expose("digitalesmonster_project_class", DigitalesMonsterProject)
PLUGIN_MANAGER.expose_module("mods.digitalesmonster", alias="digitalesmonster")
