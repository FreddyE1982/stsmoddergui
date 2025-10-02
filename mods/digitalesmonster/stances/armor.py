"""Armor digitation stance implementation."""
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

__all__ = ["ArmorDigieggStance"]


class ArmorDigieggStance(DigimonStance):
    """Armor-Digitation, die Digi-Eier als alternative Pipeline nutzt."""

    identifier = "digitalesmonster:armor_digiegg"
    display_name = "Armor-Digitation"
    level = "Armor"
    stats = StanceStatProfile(hp=82, max_hp=82, block=17, strength=2, dexterity=3)
    stability = StanceStabilityConfig(
        level=level,
        start=85,
        maximum=120,
        entry_cost=25,
        per_turn_drain=6,
        recovery_on_exit=18,
        lower_bound=0,
    )
    entry_powers = (
        PowerGrant("Dexterity", 2, remove_on_exit=True),
        PowerGrant("digitalesmonster:armor-aegis", 1, remove_on_exit=True),
        PowerGrant("Metallicize", 3, remove_on_exit=True),
    )
    fallback_identifier = "digitalesmonster:natural_rookie"
    description_text = (
        "Armor-Digitation verschiebt die Stabilitätskurve und nutzt Digi-Eier als Verstärker."
        " Bei Überlastung zerbricht das Ei und Agumon fällt auf das Rookie-Level zurück."
    )

    def verify_entry_requirements(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
    ) -> None:
        egg_name = self._resolve_digiegg(context)
        if egg_name is None:
            raise DigimonStanceRequirementError(
                "Armor-Digitation erfordert ein aktives Digi-Ei in Relikten oder Metadaten."
            )
        if context.digisoul < 2:
            raise DigimonStanceRequirementError(
                "Armor-Level benötigt mindestens 2 Punkte DigiSoul."
            )
        pipeline = context.metadata.setdefault("armor_pipeline", {})
        pipeline.setdefault("egg", egg_name)
        pipeline["pending"] = False

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
        pipeline = context.metadata.setdefault("armor_pipeline", {})
        pipeline.update(
            {
                "active": True,
                "entry_reason": reason,
                "previous_stance": getattr(previous, "identifier", None),
                "turns": pipeline.get("turns", 0),
                "egg": pipeline.get("egg", self._resolve_digiegg(context)),
            }
        )
        context.digisoul = max(0, context.digisoul - 1)
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
        pipeline = context.metadata.setdefault("armor_pipeline", {})
        pipeline.setdefault("turns", 0)
        pipeline["turns"] += 1
        pipeline["last_record"] = record.current
        if context.digisoul > 0:
            context.digisoul -= 1
            pipeline["digisoul_spent"] = pipeline.get("digisoul_spent", 0) + 1
        if context.digisoul >= 3 and record.current < self.stability.maximum:
            manager.adjust_stability(3, reason="armor-digisoul-recovery")
            pipeline["reinforced"] = True
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
        pipeline = context.metadata.setdefault("armor_pipeline", {})
        pipeline["active"] = False
        pipeline["last_exit_reason"] = reason
        pipeline["stability_snapshot"] = record_before.current
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
        pipeline = context.metadata.setdefault("armor_pipeline", {})
        pipeline["egg_shattered"] = True
        pipeline["instability_reason"] = reason
        pipeline["active"] = False
        context.digisoul = 0
        return super().on_instability(
            manager=manager,
            context=context,
            record=record,
            reason=reason,
        ) or self.fallback_identifier

    @staticmethod
    def _resolve_digiegg(context: DigimonStanceContext) -> Optional[str]:
        egg = context.metadata.get("armor_egg")
        if egg:
            return str(egg).lower()
        for relic in context.relics:
            normalized = relic.strip().lower()
            if "digi-ei" in normalized or "digiei" in normalized or "digi egg" in normalized:
                return normalized
        return None


PLUGIN_MANAGER.expose("ArmorDigieggStance", ArmorDigieggStance)
PLUGIN_MANAGER.expose_module(
    "mods.digitalesmonster.stances.armor", alias="digitalesmonster_stance_armor"
)
