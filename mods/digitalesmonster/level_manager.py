"""Level-Übergangsmanager für Digitales Monster."""
from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Callable, Dict, List, Optional, Tuple, Union

from mods.digitalesmonster.persistence import LevelStabilityProfile, LevelStabilityRecord, StabilityPersistenceController
from mods.digitalesmonster.stances import (
    DigimonStanceContext,
    DigimonStanceManager,
    DigimonStanceRequirementError,
    StanceTransition,
)
from plugins import PLUGIN_MANAGER

__all__ = [
    "CardTriggerEvent",
    "RelicTriggerEvent",
    "CombatTriggerEvent",
    "TransitionDecision",
    "LevelTransitionManager",
]


@dataclass(slots=True)
class CardTriggerEvent:
    card_id: str
    context: DigimonStanceContext
    manager: DigimonStanceManager
    times_played: int = 1
    reason: str = "card_played"


@dataclass(slots=True)
class RelicTriggerEvent:
    relic_id: str
    context: DigimonStanceContext
    manager: DigimonStanceManager
    acquired: bool = True
    reason: str = "relic_event"


@dataclass(slots=True)
class CombatTriggerEvent:
    result: str
    context: DigimonStanceContext
    manager: DigimonStanceManager
    floor: Optional[int] = None
    encounter: Optional[str] = None
    reason: str = "combat_result"


@dataclass(slots=True)
class TransitionDecision:
    """Resultat eines Trigger-Handlers."""

    stance: Optional[Union[str, object]] = None
    stability_delta: int = 0
    reason: str = "trigger"
    enforce_requirements: bool = True
    metadata_updates: Dict[str, Dict[str, object]] = field(default_factory=dict)
    chance: float = 1.0
    fallback_identifier: Optional[str] = None


TransitionHandler = Callable[[Union[CardTriggerEvent, RelicTriggerEvent, CombatTriggerEvent]], Optional[TransitionDecision]]


class LevelTransitionManager:
    """Koordiniert Stance-Wechsel auf Basis von Karten-, Relikt- und Kampftriggern."""

    def __init__(
        self,
        stance_manager: DigimonStanceManager,
        profile: Optional[LevelStabilityProfile] = None,
        *,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.stance_manager = stance_manager
        self.profile = profile or stance_manager.profile
        self._rng = rng or random.Random(0xD1A1)
        self._card_triggers: Dict[str, List[Tuple[int, TransitionHandler]]] = {}
        self._relic_triggers: Dict[str, List[Tuple[int, TransitionHandler]]] = {}
        self._combat_triggers: List[Tuple[int, TransitionHandler]] = []
        self._persistence: Optional[StabilityPersistenceController] = None
        PLUGIN_MANAGER.expose("digitalesmonster_level_transition_manager", self)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register_card_trigger(
        self,
        card_id: str,
        handler: TransitionHandler,
        *,
        priority: int = 0,
    ) -> None:
        self._card_triggers.setdefault(card_id, []).append((priority, handler))
        self._card_triggers[card_id].sort(key=lambda item: item[0], reverse=True)

    def register_relic_trigger(
        self,
        relic_id: str,
        handler: TransitionHandler,
        *,
        priority: int = 0,
    ) -> None:
        self._relic_triggers.setdefault(relic_id, []).append((priority, handler))
        self._relic_triggers[relic_id].sort(key=lambda item: item[0], reverse=True)

    def register_combat_trigger(self, handler: TransitionHandler, *, priority: int = 0) -> None:
        self._combat_triggers.append((priority, handler))
        self._combat_triggers.sort(key=lambda item: item[0], reverse=True)

    def bind_persistence(self, controller: StabilityPersistenceController) -> None:
        self._persistence = controller

    def seed_random(self, seed: int) -> None:
        self._rng.seed(seed)

    # ------------------------------------------------------------------
    # Dispatch helpers
    # ------------------------------------------------------------------
    def handle_card_play(
        self,
        card_id: str,
        context: DigimonStanceContext,
        *,
        times_played: int = 1,
        reason: str = "card_played",
    ) -> Optional[StanceTransition]:
        event = CardTriggerEvent(card_id, context, self.stance_manager, times_played, reason)
        handlers = self._card_triggers.get(card_id, [])
        return self._dispatch(event, handlers)

    def handle_relic_event(
        self,
        relic_id: str,
        context: DigimonStanceContext,
        *,
        acquired: bool = True,
        reason: str = "relic_event",
    ) -> Optional[StanceTransition]:
        event = RelicTriggerEvent(relic_id, context, self.stance_manager, acquired, reason)
        handlers = self._relic_triggers.get(relic_id, [])
        return self._dispatch(event, handlers)

    def handle_combat_result(
        self,
        result: str,
        context: DigimonStanceContext,
        *,
        floor: Optional[int] = None,
        encounter: Optional[str] = None,
        reason: str = "combat_result",
    ) -> Optional[StanceTransition]:
        event = CombatTriggerEvent(result, context, self.stance_manager, floor, encounter, reason)
        transition = self._dispatch(event, self._combat_triggers)
        if self._persistence:
            self._persistence.record_result(result, context=context, stance_manager=self.stance_manager)
        return transition

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _dispatch(
        self,
        event: Union[CardTriggerEvent, RelicTriggerEvent, CombatTriggerEvent],
        handlers: List[Tuple[int, TransitionHandler]],
    ) -> Optional[StanceTransition]:
        transition: Optional[StanceTransition] = None
        for _, handler in handlers:
            decision = handler(event)
            if decision is None:
                continue
            transition = self._apply_decision(event.context, decision)
        return transition

    def _apply_decision(
        self,
        context: DigimonStanceContext,
        decision: TransitionDecision,
    ) -> Optional[StanceTransition]:
        for key, updates in decision.metadata_updates.items():
            target = context.metadata.setdefault(key, {})
            target.update(updates)
        if decision.stability_delta:
            self.stance_manager.adjust_stability(decision.stability_delta, reason=decision.reason)
        if decision.stance is None:
            return None
        if decision.chance < 1.0:
            if self._rng.random() > max(0.0, min(1.0, decision.chance)):
                return None
        try:
            transition = self.stance_manager.enter(
                decision.stance,
                context,
                reason=decision.reason,
                enforce_requirements=decision.enforce_requirements,
            )
        except DigimonStanceRequirementError:
            if decision.fallback_identifier:
                return self.stance_manager.enter(
                    decision.fallback_identifier,
                    context,
                    reason=f"fallback:{decision.reason}",
                    enforce_requirements=False,
                )
            raise
        return transition

    # ------------------------------------------------------------------
    # Built-in triggers
    # ------------------------------------------------------------------
    def register_default_triggers(self, *, fusion_identifier: Optional[str] = None) -> None:
        """Registriert Standardtrigger für Jogress, Stabilität und Persistenz."""

        if fusion_identifier is None:
            fusion_identifier = "digitalesmonster:omnimon_fusion"

        def _dna_digitation_handler(event: CardTriggerEvent) -> Optional[TransitionDecision]:
            context = event.context
            pipeline = context.metadata.setdefault("fusion_pipeline", {})
            partners = pipeline.setdefault("partners", {})
            partners.setdefault("war_greymon", True)
            partners.setdefault("metal_garurumon", pipeline.get("metal_garurumon", False))
            base_chance = 0.45 + 0.05 * max(0, min(5, event.context.digisoul - 6))
            threshold = min(0.9, base_chance)
            roll = self._rng.random()
            pipeline.update(
                {
                    "trigger": f"card:{event.card_id}",
                    "last_roll": roll,
                    "threshold": threshold,
                    "ready": pipeline.get("ready", False) or roll <= threshold,
                    "random_ready": roll <= threshold,
                    "last_times_played": event.times_played,
                }
            )
            if not pipeline["ready"]:
                return TransitionDecision(
                    stance=None,
                    metadata_updates={"fusion_pipeline": pipeline},
                    reason="fusion-prep",
                )
            return TransitionDecision(
                stance=fusion_identifier,
                stability_delta=-event.times_played * 5,
                reason="dna-digitation",
                metadata_updates={"fusion_pipeline": pipeline},
                enforce_requirements=True,
            )

        def _fusion_partner_relic(event: RelicTriggerEvent) -> Optional[TransitionDecision]:
            pipeline = event.context.metadata.setdefault("fusion_pipeline", {})
            partners = pipeline.setdefault("partners", {})
            partners[event.relic_id.lower()] = event.acquired
            return TransitionDecision(
                stance=None,
                reason="fusion-partner-sync",
                metadata_updates={"fusion_pipeline": pipeline},
            )

        def _victory_heal(event: CombatTriggerEvent) -> Optional[TransitionDecision]:
            if event.result.lower() != "victory":
                return None
            record = self._ensure_level_record(event.manager)
            heal = max(5, record.maximum // 10)
            return TransitionDecision(
                stance=None,
                stability_delta=heal,
                reason="victory-stability",
            )

        self.register_card_trigger("digitalesmonster:dna-digitation", _dna_digitation_handler, priority=100)
        self.register_relic_trigger("omnimon", _fusion_partner_relic, priority=10)
        self.register_relic_trigger("metal_garurumon", _fusion_partner_relic, priority=10)
        self.register_relic_trigger("war_greymon", _fusion_partner_relic, priority=10)
        self.register_combat_trigger(_victory_heal, priority=-10)

    def _ensure_level_record(self, manager: DigimonStanceManager) -> LevelStabilityRecord:
        if manager.current_record is not None:
            return manager.current_record
        if manager.current_stance is not None:
            return manager.prepare_stance(manager.current_stance)
        return self.profile.register_level("Fallback", start=40, maximum=80)


PLUGIN_MANAGER.expose("CardTriggerEvent", CardTriggerEvent)
PLUGIN_MANAGER.expose("RelicTriggerEvent", RelicTriggerEvent)
PLUGIN_MANAGER.expose("CombatTriggerEvent", CombatTriggerEvent)
PLUGIN_MANAGER.expose("LevelTransitionManager", LevelTransitionManager)
PLUGIN_MANAGER.expose_module("mods.digitalesmonster.level_manager", alias="digitalesmonster_level_manager")
