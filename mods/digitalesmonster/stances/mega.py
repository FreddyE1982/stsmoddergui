"""Mega and Burst level stance implementations."""
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
    "WarpMegaStance",
    "BurstMegaStance",
]


class WarpMegaStance(DigimonStance):
    """Warp-Digitation direkt von Rookie/Champion zum Mega-Level."""

    identifier = "digitalesmonster:warp_mega"
    display_name = "Warp-Digitation: Mega-Level"
    level = "Mega"
    stats = StanceStatProfile(hp=90, max_hp=90, block=18, strength=5, dexterity=2)
    stability = StanceStabilityConfig(
        level=level,
        start=55,
        maximum=95,
        entry_cost=45,
        per_turn_drain=12,
        recovery_on_exit=12,
        lower_bound=0,
    )
    entry_powers = (
        PowerGrant("Strength", 3, remove_on_exit=True),
        PowerGrant("digitalesmonster:crest-of-courage", 1, remove_on_exit=False),
        PowerGrant("Buffer", 1, remove_on_exit=True),
    )
    fallback_identifier = "digitalesmonster:digivice_ultra"
    description_text = (
        "WarGreymon springt dank Warp-Digitation direkt ins Mega-Level. Hoher DigiSoul-Verbrauch"
        " stabilisiert die Form nur kurzfristig."
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
                "Warp-Digitation benötigt eine aktive Digivice-Resonanz."
            ) from exc
        if context.digisoul < 6:
            raise DigimonStanceRequirementError(
                "Mega-Level benötigt mindestens 6 Punkte DigiSoul."
            )
        # Warp-Digitation darf direkt erfolgen, setzt aber voraus, dass
        # Stabilität nicht bereits im freien Fall ist. Wenn der aktuelle
        # Stance existiert und auf dem Ultra-Level instabil ist, blockieren
        # wir den Sprung.
        if manager.current_record and manager.current_record.current <= 0:
            raise DigimonStanceRequirementError(
                "Warp-Digitation ist nicht möglich, während eine andere Form kollabiert."
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
        warp_meta = context.metadata.setdefault("warp_digitation", {})
        warp_meta.update(
            {
                "active": True,
                "entry_reason": reason,
                "previous_stance": getattr(previous, "identifier", None),
                "digisoul_spent": warp_meta.get("digisoul_spent", 0) + min(context.digisoul, 3),
            }
        )
        if context.digisoul > 0:
            spent = min(3, context.digisoul)
            context.digisoul -= spent
            warp_meta["digisoul_spent"] = warp_meta.get("digisoul_spent", 0) + spent
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
        warp_meta = context.metadata.setdefault("warp_digitation", {})
        if context.digisoul > 0:
            drain = min(2, context.digisoul)
            context.digisoul -= drain
            warp_meta["digisoul_spent"] = warp_meta.get("digisoul_spent", 0) + drain
            context.grant_power("digitalesmonster:mega-overdrive", drain)
        warp_meta["last_record"] = record.current
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
        warp_meta = context.metadata.setdefault("warp_digitation", {})
        warp_meta["active"] = False
        warp_meta["last_exit_reason"] = reason
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
        warp_meta = context.metadata.setdefault("warp_digitation", {})
        warp_meta["instability_reason"] = reason
        return super().on_instability(
            manager=manager,
            context=context,
            record=record,
            reason=reason,
        ) or self.fallback_identifier


class BurstMegaStance(DigimonStance):
    """Burst Mode Mega-Level mit HP-Modifikationen."""

    identifier = "digitalesmonster:burst_mega"
    display_name = "Burst Mode Mega-Level"
    level = "Mega-Burst"
    stats = StanceStatProfile(hp=95, max_hp=95, block=12, strength=7, dexterity=3)
    stability = StanceStabilityConfig(
        level=level,
        start=40,
        maximum=75,
        entry_cost=50,
        per_turn_drain=20,
        recovery_on_exit=6,
        lower_bound=0,
    )
    entry_powers = (
        PowerGrant("Strength", 4, remove_on_exit=True),
        PowerGrant("digitalesmonster:burst-aura", 3, remove_on_exit=True),
        PowerGrant("Artifact", 1, remove_on_exit=True),
    )
    fallback_identifier = "digitalesmonster:warp_mega"
    description_text = (
        "ShineGreymon Burst Mode opfert Lebensenergie für massive Kraft."
        " Hoher DigiSoul-Abfluss reduziert die Einsatzdauer drastisch."
    )

    def verify_entry_requirements(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
    ) -> None:
        if context.digisoul < 8:
            raise DigimonStanceRequirementError(
                "Burst Mode benötigt mindestens 8 Punkte DigiSoul."
            )
        warp_meta = context.metadata.get("warp_digitation", {})
        if not warp_meta.get("active"):
            raise DigimonStanceRequirementError(
                "Burst Mode erfordert eine aktive Warp-Digitation."
            )
        try:
            context.require_digivice()
        except DigimonStanceRequirementError as exc:
            raise DigimonStanceRequirementError(
                "Burst Mode ohne Digivice-Resonanz ist instabil."
            ) from exc

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
        pre_hp = context.player_hp
        pre_max_hp = context.player_max_hp
        super().on_enter(
            manager=manager,
            context=context,
            previous=previous,
            previous_record=previous_record,
            new_record=new_record,
            reason=reason,
        )
        burst_meta = context.metadata.setdefault("burst_mode", {})
        bonus = max(10, context.metadata.get("warp_digitation", {}).get("digisoul_spent", 0))
        burst_meta.update(
            {
                "active": True,
                "entry_reason": reason,
                "previous_stance": getattr(previous, "identifier", None),
                "hp_bonus": bonus,
                "pre_hp": pre_hp,
                "pre_max_hp": pre_max_hp,
            }
        )
        context.player_max_hp += bonus
        context.player_hp = min(context.player_max_hp, context.player_hp + bonus)
        context.digisoul = max(0, context.digisoul - 3)

    def on_turn_start(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
        record,
        reason: str,
    ) -> None:
        burst_meta = context.metadata.setdefault("burst_mode", {})
        burst_meta.setdefault("turns", 0)
        burst_meta["turns"] += 1
        burst_meta["last_record"] = record.current
        drain = max(3, burst_meta.get("hp_bonus", 0) // 4)
        context.player_hp = max(1, context.player_hp - drain)
        if context.digisoul > 0:
            context.digisoul = max(0, context.digisoul - 2)
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
        burst_meta = context.metadata.setdefault("burst_mode", {})
        pre_max = burst_meta.get("pre_max_hp", context.player_max_hp)
        pre_hp = burst_meta.get("pre_hp", context.player_hp)
        burst_meta["active"] = False
        burst_meta["last_exit_reason"] = reason
        context.player_max_hp = max(1, pre_max)
        context.player_hp = max(1, min(context.player_max_hp, pre_hp))
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
        burst_meta = context.metadata.setdefault("burst_mode", {})
        burst_meta["instability_reason"] = reason
        burst_meta["active"] = False
        return super().on_instability(
            manager=manager,
            context=context,
            record=record,
            reason=reason,
        ) or self.fallback_identifier


PLUGIN_MANAGER.expose("WarpMegaStance", WarpMegaStance)
PLUGIN_MANAGER.expose("BurstMegaStance", BurstMegaStance)
PLUGIN_MANAGER.expose_module(
    "mods.digitalesmonster.stances.mega", alias="digitalesmonster_stance_mega"
)
