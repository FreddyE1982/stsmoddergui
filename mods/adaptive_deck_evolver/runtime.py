"""Runtime integration helpers for the adaptive deck evolver."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.basemod_wrapper.experimental.graalpy_rule_weaver import (
    MechanicActivation,
    MechanicMutation,
)
from modules.modbuilder import Deck

from .analysis import FightingStyleHeuristic
from .evolution import DeckEvolutionEngine
from .models import (
    CardProfile,
    CombatCardEvent,
    CombatSessionRecord,
    DeckMutationPlan,
    KeywordAdjustment,
)
from .persistence import PlayerProfile, ProfilePersistence

DEFAULT_STORAGE = Path(__file__).resolve().parent / "data" / "profile.json"


def _normalise_status_effects(
    status_effects: Optional[Mapping[str, Mapping[str, float]]]
) -> Mapping[str, Mapping[str, float]]:
    if not status_effects:
        return {}
    normalised: Dict[str, Dict[str, float]] = {}
    for scope, effects in status_effects.items():
        target = scope.lower()
        target_map: Dict[str, float] = {}
        for name, amount in effects.items():
            target_map[str(name).lower()] = float(amount)
        normalised[target] = target_map
    return normalised


class CombatRecorder:
    """Collects telemetry for a single combat encounter."""

    def __init__(
        self,
        *,
        combat_id: str,
        enemy: str,
        floor: int,
        player_hp_start: float,
        relics: Sequence[str] = (),
        notes: Sequence[str] = (),
    ) -> None:
        self.combat_id = combat_id
        self.enemy = enemy
        self.floor = floor
        self.player_hp_start = float(player_hp_start)
        self._events: list[CombatCardEvent] = []
        self.relics = tuple(str(relic) for relic in relics)
        self.notes = [str(entry) for entry in notes]

    def record_card_play(
        self,
        *,
        card_id: str,
        turn: int,
        energy_before: float,
        energy_spent: float,
        energy_remaining: float,
        damage_dealt: float = 0.0,
        block_gained: float = 0.0,
        player_hp_change: float = 0.0,
        enemy_hp_change: float = 0.0,
        status_effects: Optional[Mapping[str, Mapping[str, float]]] = None,
        cards_drawn: int = 0,
        cards_discarded: int = 0,
        exhausted: bool = False,
        retained: bool = False,
        energy_generated: float = 0.0,
        tags: Sequence[str] = (),
    ) -> CombatCardEvent:
        event = CombatCardEvent(
            card_id=str(card_id),
            turn=int(turn),
            energy_before=float(energy_before),
            energy_spent=float(energy_spent),
            energy_remaining=float(energy_remaining),
            damage_dealt=float(damage_dealt),
            block_gained=float(block_gained),
            player_hp_change=float(player_hp_change),
            enemy_hp_change=float(enemy_hp_change),
            status_effects=_normalise_status_effects(status_effects),
            cards_drawn=int(cards_drawn),
            cards_discarded=int(cards_discarded),
            exhausted=bool(exhausted),
            retained=bool(retained),
            energy_generated=float(energy_generated),
            tags=tuple(str(tag) for tag in tags),
        )
        self._events.append(event)
        return event

    def add_note(self, note: str) -> None:
        self.notes.append(str(note))

    def finalize(
        self,
        *,
        victory: bool,
        player_hp_end: float,
        reward_cards: Sequence[str] = (),
        notes: Sequence[str] = (),
    ) -> CombatSessionRecord:
        turn_count = max((event.turn for event in self._events), default=0)
        combined_notes = tuple(self.notes + [str(entry) for entry in notes])
        return CombatSessionRecord(
            combat_id=self.combat_id,
            enemy=self.enemy,
            floor=self.floor,
            victory=bool(victory),
            turn_count=turn_count,
            player_hp_start=self.player_hp_start,
            player_hp_end=float(player_hp_end),
            card_events=tuple(self._events),
            relics=self.relics,
            reward_cards=tuple(str(card) for card in reward_cards),
            notes=combined_notes,
        )


class AdaptiveMechanicMod:
    """High level façade that orchestrates adaptive deck evolution."""

    def __init__(
        self,
        *,
        mod_id: str = "adaptive_evolver",
        storage_path: Optional[Path] = None,
        deck: Optional[type[Deck]] = None,
        autosave: bool = True,
    ) -> None:
        self.mod_id = mod_id
        self.storage_path = storage_path or DEFAULT_STORAGE
        self.persistence = ProfilePersistence(self.storage_path)
        self.profile = self.persistence.load(mod_id=mod_id)
        self.heuristic = FightingStyleHeuristic(self.profile)
        self.engine = DeckEvolutionEngine(self.profile, self.heuristic)
        self.deck = deck
        self.autosave = autosave
        self._recorders: Dict[str, CombatRecorder] = {}
        self._base_deck_ids: set[str] = set(self.profile.deck.keys())
        self._project = None
        self.latest_plan: Optional[DeckMutationPlan] = None

    # ------------------------------------------------------------------
    def attach_deck(self, deck: type[Deck]) -> None:
        self.deck = deck
        self._base_deck_ids = set(deck.card_identifiers())

    def register_base_deck(self, blueprints: Iterable[SimpleCardBlueprint]) -> None:
        identifiers = set()
        for blueprint in blueprints:
            identifiers.add(blueprint.identifier)
            if blueprint.identifier not in self.profile.deck:
                profile = CardProfile.from_blueprint(blueprint)
                self.profile.register_card_profile(profile)
        if identifiers:
            self._base_deck_ids = identifiers
            if self.autosave:
                self.persistence.save(self.profile)

    def register_unlockables(self, blueprints: Iterable[SimpleCardBlueprint]) -> None:
        for blueprint in blueprints:
            profile = CardProfile.from_blueprint(blueprint)
            self.profile.register_unlockable(profile)
        if self.autosave:
            self.persistence.save(self.profile)

    # ------------------------------------------------------------------
    def begin_combat(
        self,
        combat_id: str,
        *,
        enemy: str,
        floor: int,
        player_hp_start: float,
        relics: Sequence[str] = (),
        notes: Sequence[str] = (),
    ) -> CombatRecorder:
        recorder = CombatRecorder(
            combat_id=str(combat_id),
            enemy=str(enemy),
            floor=int(floor),
            player_hp_start=float(player_hp_start),
            relics=relics,
            notes=notes,
        )
        self._recorders[recorder.combat_id] = recorder
        return recorder

    def complete_combat(
        self,
        combat_id: str,
        *,
        victory: bool,
        player_hp_end: float,
        reward_cards: Sequence[str] = (),
        notes: Sequence[str] = (),
    ) -> DeckMutationPlan:
        if combat_id not in self._recorders:
            raise KeyError(f"Unknown combat identifier '{combat_id}'.")
        recorder = self._recorders.pop(combat_id)
        session = recorder.finalize(
            victory=bool(victory),
            player_hp_end=player_hp_end,
            reward_cards=reward_cards,
            notes=notes,
        )
        style_vector = self.heuristic.ingest_combat(session)
        plan = self.engine.plan_evolution(style_vector=style_vector)
        self.engine.apply(plan)
        self.latest_plan = plan
        if self.deck is not None:
            self.apply_plan_to_deck(plan)
        if self.autosave:
            self.persistence.save(self.profile)
        return plan

    # ------------------------------------------------------------------
    def apply_plan_to_deck(self, plan: DeckMutationPlan) -> None:
        if not self.deck or plan.is_empty():
            return
        deck_cards = self.deck.unique_cards()
        for mutation in plan.mutations:
            blueprint = deck_cards.get(mutation.card_id)
            if not blueprint:
                continue
            if mutation.new_value is not None:
                object.__setattr__(blueprint, "value", int(mutation.new_value))
            if mutation.new_upgrade_value is not None:
                object.__setattr__(blueprint, "upgrade_value", int(mutation.new_upgrade_value))
            if mutation.new_cost is not None:
                object.__setattr__(blueprint, "cost", int(mutation.new_cost))
            if mutation.new_secondary_value is not None:
                object.__setattr__(blueprint, "secondary_value", int(mutation.new_secondary_value))
            if mutation.new_secondary_upgrade is not None:
                object.__setattr__(blueprint, "secondary_upgrade", int(mutation.new_secondary_upgrade))
            self._apply_keyword_adjustments(blueprint, mutation.keyword_adjustments)
        for card in plan.new_cards:
            blueprint = card.to_blueprint()
            self.deck.addCard(blueprint)
        # Unlockables are intentionally not added directly; downstream systems can query profile.

    def _apply_keyword_adjustments(
        self,
        blueprint: SimpleCardBlueprint,
        adjustments: Sequence[KeywordAdjustment],
    ) -> None:
        if not adjustments:
            return
        keywords = set(blueprint.keywords)
        values = dict(blueprint.keyword_values)
        upgrades = dict(blueprint.keyword_upgrades)
        for adjustment in adjustments:
            keywords.add(adjustment.keyword)
            if adjustment.amount is not None:
                values[adjustment.keyword] = int(adjustment.amount)
            if adjustment.upgrade is not None:
                upgrades[adjustment.keyword] = int(adjustment.upgrade)
            if adjustment.card_uses is not None:
                object.__setattr__(blueprint, "card_uses", int(adjustment.card_uses))
            if adjustment.card_uses_upgrade is not None:
                object.__setattr__(blueprint, "card_uses_upgrade", int(adjustment.card_uses_upgrade))
        object.__setattr__(blueprint, "keywords", tuple(sorted(keywords)))
        object.__setattr__(blueprint, "keyword_values", values)
        object.__setattr__(blueprint, "keyword_upgrades", upgrades)

    # ------------------------------------------------------------------
    def iter_dynamic_blueprints(self) -> Iterable[SimpleCardBlueprint]:
        for identifier, profile in self.profile.deck.items():
            if identifier not in self._base_deck_ids or profile.generated_by:
                yield profile.to_blueprint()
        for profile in self.profile.unlockables.values():
            yield profile.to_blueprint()

    def register_with_project(self, project: object) -> None:
        self._project = project
        if hasattr(project, "register_mechanic_blueprint_provider"):
            project.register_mechanic_blueprint_provider(self.iter_dynamic_blueprints)
        mutation = self._build_runtime_mutation()
        if hasattr(project, "register_mechanic_mutation"):
            project.register_mechanic_mutation(mutation, activate=False)

    # ------------------------------------------------------------------
    def _build_runtime_mutation(self) -> MechanicMutation:
        identifier = f"{self.mod_id}:adaptive-sync"

        def apply(context) -> MechanicActivation:
            reverts = []
            for profile in self.profile.deck.values():
                reverts.append(
                    context.adjust_card_values(
                        profile.identifier,
                        value=profile.value,
                        upgrade_value=profile.upgrade_value,
                        cost=profile.cost,
                        secondary_value=profile.secondary_value,
                        secondary_upgrade=profile.secondary_upgrade,
                    )
                )
                if profile.description or profile.upgrade_description:
                    reverts.append(
                        context.set_card_description(
                            profile.identifier,
                            description=profile.description,
                            upgrade_description=profile.upgrade_description,
                        )
                    )
                for keyword in profile.keywords:
                    reverts.append(
                        context.add_keyword_to_card(
                            profile.identifier,
                            keyword,
                            amount=profile.keyword_values.get(keyword),
                            upgrade=profile.keyword_upgrades.get(keyword),
                            card_uses=profile.card_uses if keyword == "exhaustive" else None,
                            card_uses_upgrade=profile.card_uses_upgrade if keyword == "exhaustive" else None,
                        )
                    )
            metadata = {
                "deck_cards": len(self.profile.deck),
                "unlockables": len(self.profile.unlockables),
            }
            return MechanicActivation(
                identifier=identifier,
                revert_callbacks=tuple(reverts),
                metadata=metadata,
            )

        return MechanicMutation(
            identifier=identifier,
            description="Synchronise adaptive deck state with persistent profile.",
            apply=apply,
            priority=50,
            tags=("adaptive", "evolution", self.mod_id),
            metadata={"mod_id": self.mod_id},
        )

    # ------------------------------------------------------------------
    def save(self) -> None:
        self.persistence.save(self.profile)

    def reset_profile(self) -> PlayerProfile:
        self.profile = self.persistence.reset(mod_id=self.mod_id)
        self.heuristic = FightingStyleHeuristic(self.profile)
        self.engine = DeckEvolutionEngine(self.profile, self.heuristic)
        self._base_deck_ids = set()
        return self.profile
