"""Jogress- und Fusions-Stances für das Digitales Monster Mod."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

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

__all__ = ["JogressFusionStance", "OmnimonFusionStance", "ImperialdramonPaladinModeStance"]


class JogressFusionStance(DigimonStance):
    """Basisklasse für Jogress-/Fusion-Stances."""

    _abstract = True
    fusion_metadata_key = "fusion_pipeline"
    required_partners: Tuple[str, ...] = ()
    required_digisoul: int = 8
    digisoul_drain_per_turn: int = 3
    random_activation_threshold: float = 1.0
    fallback_identifier = "digitalesmonster:warp_mega"

    def _get_pipeline(self, context: DigimonStanceContext) -> Dict[str, object]:
        return context.metadata.setdefault(self.fusion_metadata_key, {})

    def verify_entry_requirements(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
    ) -> None:
        pipeline = self._get_pipeline(context)
        partners = pipeline.get("partners", {})
        if self.required_partners:
            missing = [partner for partner in self.required_partners if not partners or not partners.get(partner)]
            if missing:
                raise DigimonStanceRequirementError(
                    "Jogress benötigt synchronisierte Partnerdaten: " + ", ".join(sorted(missing))
                )
        if context.digisoul < self.required_digisoul:
            raise DigimonStanceRequirementError(
                f"Jogress benötigt mindestens {self.required_digisoul} Punkte DigiSoul."
            )
        try:
            context.require_digivice()
        except DigimonStanceRequirementError as exc:
            raise DigimonStanceRequirementError("Jogress erfordert aktive Digivices oder entsprechende Relikte.") from exc

        ready = bool(pipeline.get("ready"))
        if not ready:
            roll = float(pipeline.get("last_roll", 1.0))
            threshold = float(pipeline.get("threshold", self.random_activation_threshold))
            if roll > threshold:
                raise DigimonStanceRequirementError(
                    "Der Jogress-Impuls hat nicht synchronisiert. Weitere Trigger erforderlich."
                )
            pipeline["ready"] = True
            pipeline["random_ready"] = True

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
        pipeline = self._get_pipeline(context)
        pipeline.update(
            {
                "active": True,
                "form": getattr(self, "display_name", self.identifier),
                "entry_reason": reason,
                "previous_stance": getattr(previous, "identifier", None),
                "digisoul_spent": pipeline.get("digisoul_spent", 0) + min(context.digisoul, self.required_digisoul),
            }
        )
        if context.digisoul > 0:
            context.digisoul = max(0, context.digisoul - self.required_digisoul)
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
        pipeline = self._get_pipeline(context)
        drain = max(0, int(self.digisoul_drain_per_turn))
        if drain and context.digisoul > 0:
            spent = min(drain, context.digisoul)
            context.digisoul -= spent
            pipeline["digisoul_spent"] = pipeline.get("digisoul_spent", 0) + spent
        pipeline["last_record"] = record.current
        if context.digisoul <= 0:
            pipeline["digisoul_empty"] = True
            manager.adjust_stability(-record.current, reason="fusion-digisoul-empty")
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
        pipeline = self._get_pipeline(context)
        pipeline["active"] = False
        pipeline["last_exit_reason"] = reason
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
        pipeline = self._get_pipeline(context)
        pipeline["instability_reason"] = reason
        pipeline["active"] = False
        fallback = super().on_instability(manager=manager, context=context, record=record, reason=reason)
        return fallback or self.fallback_identifier


class OmnimonFusionStance(JogressFusionStance):
    """Jogress-Fusion von WarGreymon und MetalGarurumon."""

    identifier = "digitalesmonster:omnimon_fusion"
    display_name = "Omnimon Jogress"
    level = "Jogress-Mega"
    stats = StanceStatProfile(hp=110, max_hp=110, block=26, strength=7, dexterity=4)
    stability = StanceStabilityConfig(
        level=level,
        start=45,
        maximum=85,
        entry_cost=60,
        per_turn_drain=22,
        recovery_on_exit=12,
        lower_bound=5,
    )
    entry_powers = (
        PowerGrant("Artifact", 2, remove_on_exit=True),
        PowerGrant("digitalesmonster:gigantisches-schwert", 2, remove_on_exit=True),
        PowerGrant("digitalesmonster:giga-kanone", 2, remove_on_exit=True),
    )
    required_partners = ("war_greymon", "metal_garurumon")
    required_digisoul = 10
    digisoul_drain_per_turn = 3
    random_activation_threshold = 0.75
    fallback_identifier = "digitalesmonster:warp_mega"
    description_text = (
        "Omnimon vereint WarGreymon und MetalGarurumon. Der Jogress zündet nur bei"
        " synchronisierten Partnerdaten und verbrennt DigiSoul im Rekordtempo."
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
        pipeline = self._get_pipeline(context)
        partners = pipeline.setdefault("partners", {})
        partners.setdefault("war_greymon", True)
        partners.setdefault("metal_garurumon", True)
        pipeline["omnimon_ready"] = True
        context.grant_power("Strength", 3)
        context.grant_power("digitalesmonster:omnimon-focus", 1)
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
        pipeline = self._get_pipeline(context)
        pipeline.setdefault("combo_counter", 0)
        pipeline["combo_counter"] += 1
        context.grant_power("Buffer", 1)
        super().on_turn_start(manager=manager, context=context, record=record, reason=reason)


class ImperialdramonPaladinModeStance(JogressFusionStance):
    """Seltene Jogress-Fusion mit Omnimon-Unterstützung."""

    identifier = "digitalesmonster:imperialdramon_paladin"
    display_name = "Imperialdramon Paladin Mode"
    level = "Jogress-Transzendent"
    stats = StanceStatProfile(hp=120, max_hp=120, block=18, strength=8, dexterity=5)
    stability = StanceStabilityConfig(
        level=level,
        start=35,
        maximum=70,
        entry_cost=70,
        per_turn_drain=28,
        recovery_on_exit=18,
        lower_bound=8,
    )
    entry_powers = (
        PowerGrant("Strength", 4, remove_on_exit=True),
        PowerGrant("Artifact", 2, remove_on_exit=True),
        PowerGrant("digitalesmonster:omega-schwert", 3, remove_on_exit=True),
    )
    required_partners = ("imperialdramon_fighter", "omnimon")
    required_digisoul = 12
    digisoul_drain_per_turn = 4
    random_activation_threshold = 0.6
    fallback_identifier = "digitalesmonster:omnimon_fusion"
    description_text = (
        "Imperialdramon Paladin Mode verschmilzt Imperialdramon Fighter Mode mit Omnimon."
        " Nur DNA-Digivices höchster Stufe halten diese Form stabil."
    )

    def verify_entry_requirements(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
    ) -> None:
        pipeline = self._get_pipeline(context)
        partners = pipeline.get("partners", {})
        if not partners.get("omnimon"):
            raise DigimonStanceRequirementError(
                "Paladin Mode erfordert eine aktive Omnimon-Fusion als Energiequelle."
            )
        super().verify_entry_requirements(manager=manager, context=context)

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
        pipeline = self._get_pipeline(context)
        pipeline["paladin_active"] = True
        context.grant_power("digitalesmonster:paladin-barriere", 2)
        super().on_enter(
            manager=manager,
            context=context,
            previous=previous,
            previous_record=previous_record,
            new_record=new_record,
            reason=reason,
        )

    def on_exit(
        self,
        *,
        manager: DigimonStanceManager,
        context: DigimonStanceContext,
        new_stance,
        record_before,
        reason: str,
    ) -> None:
        pipeline = self._get_pipeline(context)
        pipeline["paladin_active"] = False
        pipeline.setdefault("partners", {})["omnimon"] = True
        super().on_exit(
            manager=manager,
            context=context,
            new_stance=new_stance,
            record_before=record_before,
            reason=reason,
        )


PLUGIN_MANAGER.expose("JogressFusionStance", JogressFusionStance)
PLUGIN_MANAGER.expose("OmnimonFusionStance", OmnimonFusionStance)
PLUGIN_MANAGER.expose("ImperialdramonPaladinModeStance", ImperialdramonPaladinModeStance)
PLUGIN_MANAGER.expose_module("mods.digitalesmonster.stances.fusion", alias="digitalesmonster_stance_fusion")
