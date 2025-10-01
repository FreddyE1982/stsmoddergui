"""Deck evolution engine that converts heuristic signals into mutations."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .analysis import FightingStyleHeuristic
from .models import (
    CardProfile,
    CardUsageStats,
    ComboStats,
    DeckMutation,
    DeckMutationPlan,
    KeywordAdjustment,
    StyleVector,
)
from .persistence import PlayerProfile


class DeckEvolutionEngine:
    """Generate and apply deck evolution plans using combat heuristics."""

    def __init__(self, profile: PlayerProfile, heuristic: FightingStyleHeuristic) -> None:
        self.profile = profile
        self.heuristic = heuristic

    # ------------------------------------------------------------------
    def plan_evolution(
        self,
        *,
        style_vector: Optional[StyleVector] = None,
    ) -> DeckMutationPlan:
        style = style_vector or self.heuristic.style_vector
        if style is None:
            style = StyleVector(
                aggression=0.0,
                defense=0.0,
                control=0.0,
                combo=0.0,
                energy_efficiency=0.0,
                draw_bias=0.0,
                preferred_turn_window="unknown",
                dominant_combo=(),
                summary="No data yet",
            )
        mutations = self._identify_card_mutations(style)
        new_cards, unlockables = self._generate_new_cards(style)
        notes = [
            f"Dominant archetype: {style.dominant_archetype()}",
            f"Energy efficiency: {style.energy_efficiency:.2f}",
            f"Combo focus: {style.combo:.2f}",
        ]
        plan = DeckMutationPlan(
            mutations=tuple(mutations),
            new_cards=tuple(new_cards),
            unlockables=tuple(unlockables),
            style_vector=style,
            notes=tuple(notes),
        )
        return plan

    def apply(self, plan: DeckMutationPlan) -> None:
        if plan.is_empty():
            return
        for mutation in plan.mutations:
            card = self.profile.deck.get(mutation.card_id)
            if not card:
                continue
            card.apply_mutation(mutation)
            self.profile.deck[card.identifier] = card
        for card in plan.new_cards:
            self.profile.register_card_profile(card)
        for card in plan.unlockables:
            self.profile.register_unlockable(card)
        self.profile.record_mutation_plan(plan)

    # ------------------------------------------------------------------
    def _identify_card_mutations(self, style: StyleVector) -> List[DeckMutation]:
        archetype = style.dominant_archetype()
        mutations: List[DeckMutation] = []
        mutated_ids: set[str] = set()
        energy_pressure = style.energy_efficiency < 0.3
        card_stats = sorted(
            (stats for stats in self.profile.card_stats.values() if stats.plays >= 3),
            key=lambda item: item.plays,
            reverse=True,
        )
        for stats in card_stats:
            card = self.profile.deck.get(stats.card_id)
            if not card:
                continue
            avg_score = stats.average_score()
            notes: List[str] = []
            new_value: Optional[int] = None
            new_upgrade: Optional[int] = None
            new_cost: Optional[int] = None
            new_secondary: Optional[int] = None
            new_secondary_upgrade: Optional[int] = None
            keyword_adjustments: List[KeywordAdjustment] = []
            if avg_score < -0.45:
                if archetype == "aggressive":
                    delta = max(2, int(abs(avg_score) * 1.8))
                    new_value = card.value + delta
                    new_upgrade = card.upgrade_value + max(1, delta // 2)
                    notes.append(f"Aggressive boost: +{delta} base damage")
                elif archetype == "defensive":
                    delta = max(3, int(abs(avg_score) * 2.5))
                    new_secondary = (card.secondary_value or card.value) + delta
                    new_secondary_upgrade = card.secondary_upgrade + max(1, delta // 2)
                    notes.append(f"Defensive reinforcement: +{delta} block/secondary value")
                elif archetype == "control":
                    keyword_adjustments.append(KeywordAdjustment(keyword="weak", amount=1, upgrade=1))
                    new_upgrade = card.upgrade_value + 1
                    notes.append("Control focus: added Weak keyword")
                else:
                    delta = max(2, int(abs(avg_score) * 1.5))
                    new_value = card.value + delta
                    new_upgrade = card.upgrade_value + max(1, delta // 2)
                    notes.append(f"General boost: +{delta} value")
            if energy_pressure and card.cost > 1:
                new_cost = max(card.cost - 1, 0)
                notes.append("Reduced cost to relieve energy pressure")
            if not notes:
                continue
            mutation = DeckMutation(
                card_id=card.identifier,
                new_value=new_value,
                new_upgrade_value=new_upgrade,
                new_cost=new_cost,
                new_secondary_value=new_secondary,
                new_secondary_upgrade=new_secondary_upgrade,
                keyword_adjustments=tuple(keyword_adjustments),
                role=archetype,
                notes=tuple(notes),
                metadata={
                    "average_score": avg_score,
                    "plays": stats.plays,
                    "reason": "underperforming_card",
                },
            )
            mutations.append(mutation)
            mutated_ids.add(card.identifier)
        # Enhance standout cards for mastery
        top_cards = self.heuristic.rank_cards(limit=5)
        for card_id, score in top_cards:
            if score <= 1.0:
                continue
            if card_id in mutated_ids:
                continue
            card = self.profile.deck.get(card_id)
            if not card:
                continue
            upgrade_boost = max(1, int(score // 1.5))
            mutation = DeckMutation(
                card_id=card_id,
                new_upgrade_value=card.upgrade_value + upgrade_boost,
                notes=(f"Rewarding mastery: +{upgrade_boost} upgrade value",),
                role=archetype,
                metadata={"reason": "top_performer", "score": score},
            )
            mutations.append(mutation)
        return mutations

    def _generate_new_cards(self, style: StyleVector) -> Tuple[List[CardProfile], List[CardProfile]]:
        combos = self.heuristic.top_combos(limit=4, minimum_plays=3)
        if not combos:
            return ([], [])
        archetype = style.dominant_archetype()
        existing_tokens = {
            card.generated_by
            for card in list(self.profile.deck.values()) + list(self.profile.unlockables.values())
            if card.generated_by
        }
        deck_cards: List[CardProfile] = []
        unlockables: List[CardProfile] = []
        for combo, score in combos:
            token = f"combo:{'->'.join(combo)}"
            if token in existing_tokens:
                continue
            stats = self.profile.combo_stats.get("::".join(combo))
            if not stats:
                continue
            card_profile = self._build_card_from_combo(combo, stats, style, archetype, token)
            if not card_profile:
                continue
            if score > 4.5:
                deck_cards.append(card_profile)
            else:
                unlockables.append(card_profile)
            existing_tokens.add(token)
            if len(deck_cards) + len(unlockables) >= 3:
                break
        return (deck_cards, unlockables)

    def _build_card_from_combo(
        self,
        combo: Tuple[str, ...],
        stats: ComboStats,
        style: StyleVector,
        archetype: str,
        token: str,
    ) -> Optional[CardProfile]:
        energy_cost = max(0, round(stats.energy_cost()))
        damage = int(max(stats.damage_total / max(stats.plays, 1), 0))
        block = int(max(stats.block_total / max(stats.plays, 1), 0))
        if damage == 0 and block == 0:
            damage = 6
        if archetype == "defensive" and block < damage:
            block = max(block, damage // 2)
        if archetype == "control" and damage < 4:
            damage = 4
        rarity = "UNCOMMON"
        if stats.average_score() > 7:
            rarity = "RARE"
        elif stats.average_score() < 3:
            rarity = "COMMON"
        description = self._compose_description(archetype, damage, block, stats, combo)
        keywords: List[str] = []
        keyword_values: Dict[str, int] = {}
        keyword_upgrades: Dict[str, int] = {}
        if archetype == "control":
            keywords.append("weak")
            keyword_values["weak"] = 1
            keyword_upgrades["weak"] = 1
        if archetype == "defensive" and block > 0:
            keywords.append("retain")
        prefix = "combo"
        identifier = self.profile.allocate_card_identifier(prefix=prefix)
        card_type = "ATTACK" if damage >= block else "SKILL"
        effect = None if card_type == "ATTACK" else "block"
        secondary_value = block if card_type == "SKILL" else None
        secondary_upgrade = max(1, block // 3) if secondary_value else 0
        upgrade_value = max(1, damage // 3)
        card = CardProfile(
            identifier=identifier,
            title=f"{combo[0].title()} Synergy",
            description=description,
            upgrade_description=f"Improved synergy from {' and '.join(combo)}",
            card_type=card_type,
            target="ENEMY" if card_type == "ATTACK" else "SELF",
            rarity=rarity,
            cost=energy_cost,
            value=max(damage, 4),
            upgrade_value=max(upgrade_value, 2),
            effect=effect,
            secondary_value=secondary_value,
            secondary_upgrade=secondary_upgrade,
            keywords=tuple(keywords),
            keyword_values=keyword_values,
            keyword_upgrades=keyword_upgrades,
            role=archetype,
            generated_by=token,
            notes=(f"Generated from combo {' -> '.join(combo)}",),
        )
        return card

    def _compose_description(
        self,
        archetype: str,
        damage: int,
        block: int,
        stats: ComboStats,
        combo: Tuple[str, ...],
    ) -> str:
        parts = [f"Inspired by {' -> '.join(combo)}."]
        if archetype == "aggressive":
            parts.append(f"Deal {max(damage, 6)} damage twice.")
        elif archetype == "defensive":
            parts.append(f"Gain {max(block, 6)} Block and Retain this turn.")
        elif archetype == "control":
            parts.append(f"Apply 1 Weak and deal {max(damage, 4)} damage.")
        else:
            parts.append(f"Deal {max(damage, 6)} damage and gain {max(block, 4)} Block.")
        if stats.average_turn:
            parts.append(f"Optimised for turn {stats.average_turn:.1f}.")
        return " ".join(parts)
