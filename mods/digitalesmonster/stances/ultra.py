"""Ultra level stance implementations with SkullGreymon fallback."""
from __future__ import annotations

from typing import Optional

from mods.digitalesmonster.stances.base import (
    DigimonStance,
    DigimonStanceContext,
    DigimonStanceManager,
    DigimonStanceRequirementError,
    PowerGrant,
    StanceStatProfile,
    StanceStabilityConfig,
)
from plugins import PLUGIN_MANAGER

__all__ = [
    "DigiviceUltraStance",
    "SkullGreymonInstabilityStance",
]


class DigiviceUltraStance(DigimonStance):
    """Stance representing MetalGreymons reguläre Ultra-Digitation."""

    identifier = "digitalesmonster:digivice_ultra"
    display_name = "Digivice-gestütztes Ultra-Level"
    level = "Ultra"
    stats = StanceStatProfile(hp=84, max_hp=84, block=16, strength=4, dexterity=2)
    stability = StanceStabilityConfig(
        level=level,
        start=70,
        maximum=110,
        entry_cost=35,
        per_turn_drain=12,
        recovery_on_exit=18,
        lower_bound=0,
    )
    entry_powers = (
        PowerGrant("Strength", 2, remove_on_exit=True),
        PowerGrant("digitalesmonster:rocket-evolution", 1, remove_on_exit=True),
        PowerGrant("PlatedArmor", 3, remove_on_exit=True),
    )
    fallback_identifier = "digitalesmonster:skullgreymon_instability"
    description_text = (
        "MetalGreymon kanalisiert verstärkte DigiSoul-Ströme. Stabilität sinkt bei"
        " Überlastung und öffnet den Pfad zu SkullGreymon."
    )

    def verify_entry_requirements(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
    ) -> None:
        try:
            context.require_digivice()
        except DigimonStanceRequirementError as exc:
            raise DigimonStanceRequirementError(
                "Ultra-Level benötigt ein aktives Digivice oder ein resonantes Relikt."
            ) from exc
        if context.digisoul < 4:
            raise DigimonStanceRequirementError(
                "Ultra-Level benötigt mindestens 4 Punkte DigiSoul."  # noqa: ERA001 - intentional German text
            )
        try:
            champion = manager.profile.get("Champion")
        except KeyError:
            return
        if champion.current < 30:
            raise DigimonStanceRequirementError(
                "Die Champion-Stabilität muss bei mindestens 30 Punkten liegen, um"
                " das Ultra-Level sicher zu halten."
            )

    def on_enter(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
        previous: Optional[DigimonStance],
        previous_record,
        new_record,
        reason: str,
    ) -> None:
        ultra_meta = context.metadata.setdefault("ultra_mode", {})
        ultra_meta.update(
            {
                "variant": "MetalGreymon",
                "active": True,
                "entry_reason": reason,
                "previous_stance": getattr(previous, "identifier", None),
                "skull_branch": False,
                "digisoul_spent": ultra_meta.get("digisoul_spent", 0) + min(context.digisoul, 2),
            }
        )
        if context.digisoul > 0:
            context.digisoul = max(0, context.digisoul - 2)
        super().on_enter(
            manager=manager,
            context=context,
            previous=previous,
            previous_record=previous_record,
            new_record=new_record,
            reason=reason,
        )

    def on_turn_start(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
        record,
        reason: str,
    ) -> None:
        ultra_meta = context.metadata.setdefault("ultra_mode", {})
        if context.digisoul > 0:
            context.digisoul = max(0, context.digisoul - 1)
            ultra_meta["digisoul_spent"] = ultra_meta.get("digisoul_spent", 0) + 1
        ultra_meta["last_turn_record"] = record.current
        super().on_turn_start(manager=manager, context=context, record=record, reason=reason)

    def on_exit(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
        new_stance,
        record_before,
        reason: str,
    ) -> None:
        context.metadata.setdefault("ultra_mode", {})["active"] = False
        super().on_exit(
            manager=manager,
            context=context,
            new_stance=new_stance,
            record_before=record_before,
            reason=reason,
        )

    def on_instability(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
        record,
        reason: str,
    ) -> str:
        ultra_meta = context.metadata.setdefault("ultra_mode", {})
        ultra_meta["skull_branch"] = True
        ultra_meta["instability_reason"] = reason
        skull_meta = context.metadata.setdefault("skullgreymon", {})
        skull_meta.update(
            {
                "pending": True,
                "trigger_record": record.current,
                "trigger_reason": reason,
            }
        )
        context.grant_power("Vulnerable", 2)
        context.grant_power("digitalesmonster:corrupted-aura", 1)
        return super().on_instability(
            manager=manager,
            context=context,
            record=record,
            reason=reason,
        ) or self.fallback_identifier


class SkullGreymonInstabilityStance(DigimonStance):
    """Instabile Abzweigung, die bei Ultra-Überlastung ausgelöst wird."""

    identifier = "digitalesmonster:skullgreymon_instability"
    display_name = "SkullGreymon – Instabil"
    level = "Ultra-Instabil"
    stats = StanceStatProfile(hp=82, max_hp=82, block=6, strength=5, dexterity=0)
    stability = StanceStabilityConfig(
        level=level,
        start=45,
        maximum=70,
        entry_cost=0,
        per_turn_drain=14,
        recovery_on_exit=8,
        lower_bound=0,
    )
    entry_powers = (
        PowerGrant("Vulnerable", 2, remove_on_exit=True),
        PowerGrant("Frail", 2, remove_on_exit=True),
        PowerGrant("digitalesmonster:skull-rage", 2, remove_on_exit=True),
    )
    fallback_identifier = "digitalesmonster:natural_rookie"
    description_text = (
        "SkullGreymon verkörpert unkontrollierte DigiSoul und zerreißt die Stabilität."
        " Rückfall zum Rookie-Level ist wahrscheinlich."
    )

    def verify_entry_requirements(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
    ) -> None:
        skull_meta = context.metadata.setdefault("skullgreymon", {})
        ultra_meta = context.metadata.get("ultra_mode", {})
        if not skull_meta.get("pending") and not ultra_meta.get("skull_branch"):
            raise DigimonStanceRequirementError(
                "SkullGreymon kann nur aus einer instabilen Ultra-Digitation hervorgehen."
            )

    def on_enter(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
        previous: Optional[DigimonStance],
        previous_record,
        new_record,
        reason: str,
    ) -> None:
        skull_meta = context.metadata.setdefault("skullgreymon", {})
        skull_meta.update(
            {
                "active": True,
                "pending": False,
                "entry_reason": reason,
                "previous_stance": getattr(previous, "identifier", None),
            }
        )
        context.strength = max(0, context.strength + 1)
        context.dexterity = max(0, context.dexterity - 1)
        super().on_enter(
            manager=manager,
            context=context,
            previous=previous,
            previous_record=previous_record,
            new_record=new_record,
            reason=reason,
        )

    def on_turn_start(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
        record,
        reason: str,
    ) -> None:
        skull_meta = context.metadata.setdefault("skullgreymon", {})
        skull_meta.setdefault("turns", 0)
        skull_meta["turns"] += 1
        skull_meta["last_record"] = record.current
        hp_drain = 4
        context.player_hp = max(1, context.player_hp - hp_drain)
        super().on_turn_start(manager=manager, context=context, record=record, reason=reason)

    def on_exit(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
        new_stance,
        record_before,
        reason: str,
    ) -> None:
        skull_meta = context.metadata.setdefault("skullgreymon", {})
        skull_meta["active"] = False
        skull_meta["last_exit_reason"] = reason
        super().on_exit(
            manager=manager,
            context=context,
            new_stance=new_stance,
            record_before=record_before,
            reason=reason,
        )

    def on_instability(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
        record,
        reason: str,
    ) -> str:
        skull_meta = context.metadata.setdefault("skullgreymon", {})
        skull_meta["last_instability_reason"] = reason
        return super().on_instability(
            manager=manager,
            context=context,
            record=record,
            reason=reason,
        ) or self.fallback_identifier


PLUGIN_MANAGER.expose("DigiviceUltraStance", DigiviceUltraStance)
PLUGIN_MANAGER.expose("SkullGreymonInstabilityStance", SkullGreymonInstabilityStance)
PLUGIN_MANAGER.expose_module(
    "mods.digitalesmonster.stances.ultra", alias="digitalesmonster_stance_ultra"
)
