"""Natürliches Rookie-Level stance implementation."""
from __future__ import annotations

from mods.digitalesmonster.stances.base import (
    DigimonStance,
    StanceStatProfile,
    StanceStabilityConfig,
    PowerGrant,
)
from plugins import PLUGIN_MANAGER


class NaturalRookieStance(DigimonStance):
    """Baseline stance that represents Agumons natürliche Rookie-Form."""

    identifier = "digitalesmonster:natural_rookie"
    display_name = "Natürliches Rookie-Level"
    level = "Rookie"
    stats = StanceStatProfile(hp=70, max_hp=70, block=4, strength=1, dexterity=1)
    stability = StanceStabilityConfig(
        level=level,
        start=120,
        maximum=160,
        entry_cost=0,
        per_turn_drain=0,
        recovery_on_exit=10,
        lower_bound=0,
    )
    entry_powers = (
        PowerGrant("Strength", 1, remove_on_exit=True),
        PowerGrant("Dexterity", 1, remove_on_exit=True),
        PowerGrant("digitalesmonster:rookie-instinct", 1, remove_on_exit=True),
    )
    description_text = (
        "Agumons natürliche Rookie-Form stabilisiert DigiSoul-Impulse und hält die "
        "Stabilität aufrecht."
    )

    def build_description(self, record):
        if record is None:
            return self.description_text
        return (
            "Natürliches Rookie-Level. Stabilität {current}/{maximum}. "
            "Verleiht +1 Stärke, +1 Geschick und einen Rookie-Instinkt-Schild.".format(
                current=record.current,
                maximum=record.maximum,
            )
        )


PLUGIN_MANAGER.expose("NaturalRookieStance", NaturalRookieStance)
PLUGIN_MANAGER.expose_module(
    "mods.digitalesmonster.stances.rookie", alias="digitalesmonster_stance_rookie"
)
