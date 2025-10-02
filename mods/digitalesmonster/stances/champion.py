"""Champion level stance implementation with Digivice requirements."""
from __future__ import annotations

from mods.digitalesmonster.stances.base import (
    DigimonStance,
    DigimonStanceManager,
    DigimonStanceRequirementError,
    DigimonStanceContext,
    PowerGrant,
    StanceStatProfile,
    StanceStabilityConfig,
)
from plugins import PLUGIN_MANAGER


class DigiviceChampionStance(DigimonStance):
    """Champion-Stance die eine aktive Digivice-Resonanz erfordert."""

    identifier = "digitalesmonster:digivice_champion"
    display_name = "Digivice-gestütztes Champion-Level"
    level = "Champion"
    stats = StanceStatProfile(hp=78, max_hp=78, block=12, strength=3, dexterity=1)
    stability = StanceStabilityConfig(
        level=level,
        start=90,
        maximum=130,
        entry_cost=20,
        per_turn_drain=8,
        recovery_on_exit=15,
        lower_bound=0,
    )
    entry_powers = (
        PowerGrant("Strength", 2, remove_on_exit=True),
        PowerGrant("digitalesmonster:digivice-resonanz", 1, remove_on_exit=True),
    )
    fallback_identifier = "digitalesmonster:natural_rookie"
    description_text = (
        "Das Digivice überlädt Agumon mit DigiSoul. Stabilität sinkt schnell ohne Resonanzpflege."
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
                "Champion-Level benötigt ein aktives Digivice oder ein entsprechendes Relikt."
            ) from exc
        if context.digisoul <= 0:
            raise DigimonStanceRequirementError(
                "Die DigiSoul-Ladung muss positiv sein, um das Champion-Level zu halten."
            )

    def on_enter(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
        previous,
        previous_record,
        new_record,
        reason: str,
    ) -> None:
        context.metadata.setdefault("digivice_resonanz", {})["level"] = "Champion"
        context.metadata["digivice_resonanz"]["last_reason"] = reason
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
        if context.digisoul > 0:
            context.digisoul = max(0, context.digisoul - 1)
        context.metadata.setdefault("digivice_resonanz", {})["turn_drain"] = self.stability.per_turn_drain
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
        recovery = self.stability.recovery_on_exit
        if recovery > 0:
            recovered = min(
                self.stability.maximum,
                record_before.current + recovery,
            )
            manager.profile.update_level(self.stability.level, current=recovered)
        context.metadata.setdefault("digivice_resonanz", {})["last_exit_reason"] = reason
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
        context.metadata.setdefault("digivice_resonanz", {})["instability_reason"] = reason
        context.metadata["digivice_resonanz"]["instability_value"] = record.current
        return super().on_instability(manager=manager, context=context, record=record, reason=reason) or self.fallback_identifier


PLUGIN_MANAGER.expose("DigiviceChampionStance", DigiviceChampionStance)
PLUGIN_MANAGER.expose_module(
    "mods.digitalesmonster.stances.champion", alias="digitalesmonster_stance_champion"
)
