"""Adaptive deck evolution mechanics package.

This package implements a mechanics-only mod that observes every combat,
constructs a richly detailed profile of the player's fighting style and evolves
the registered deck after each victorious encounter.  The modules are split
into clear layers so plugin authors can hook into any part of the pipeline:

``models``
    Data structures describing card profiles, combat events and evolution plans.
``analysis``
    Heuristic engine that interprets combat telemetry and builds play style
    vectors.  The heuristic tracks card usage down to turn windows, energy
    efficiency and synergy chains.
``evolution``
    Deck evolution engine that converts the heuristic output into concrete
    blueprint adjustments and newly generated cards.
``persistence``
    Durable profile storage with schema upgrades and JSON round-tripping.
``runtime``
    High level façade that repositories and runtime hooks can use to record
    fights and synchronise the resulting plan with :class:`ModProject`.

The top-level package exposes the :class:`AdaptiveMechanicMod` runtime helper.
"""
from __future__ import annotations

from .analysis import FightingStyleHeuristic
from .evolution import DeckEvolutionEngine
from .models import (
    CardProfile,
    CardUsageStats,
    ComboStats,
    CombatCardEvent,
    CombatSessionRecord,
    DeckMutation,
    DeckMutationPlan,
    StyleVector,
)
from .persistence import PlayerProfile, ProfilePersistence
from .runtime import AdaptiveMechanicMod, CombatRecorder

__all__ = [
    "AdaptiveMechanicMod",
    "CardProfile",
    "CardUsageStats",
    "ComboStats",
    "CombatCardEvent",
    "CombatRecorder",
    "CombatSessionRecord",
    "DeckEvolutionEngine",
    "DeckMutation",
    "DeckMutationPlan",
    "FightingStyleHeuristic",
    "PlayerProfile",
    "ProfilePersistence",
    "StyleVector",
]
