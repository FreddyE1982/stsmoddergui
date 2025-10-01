"""Heuristic that analyses combat telemetry and derives play style vectors."""
from __future__ import annotations

from collections import Counter
from typing import List, Mapping, MutableMapping, Optional, Sequence, Tuple

from .models import CardUsageStats, CombatCardEvent, CombatSessionRecord, StyleVector
from .persistence import PlayerProfile


STATUS_WEIGHTS: Mapping[str, float] = {
    "vulnerable": 3.5,
    "weak": 2.75,
    "frail": 2.2,
    "poison": 1.9,
    "burn": 1.4,
    "bleed": 2.1,
    "strength": -3.0,
    "dexterity": -2.8,
    "artifact": -1.5,
    "focus": -2.5,
    "draw": 1.25,
    "energy": 1.8,
    "retain": 0.9,
    "platedarmor": 1.7,
    "metallicize": 1.4,
    "clarity": 1.1,
    "slow": 1.6,
    "lockon": 1.8,
    "mark": 1.5,
}


class FightingStyleHeuristic:
    """Interpret combat logs and produce detailed fighting style analytics."""

    def __init__(self, profile: PlayerProfile) -> None:
        self.profile = profile
        self._latest_style: Optional[StyleVector] = None
        if profile.style_history:
            self._latest_style = profile.style_history[-1]

    # ------------------------------------------------------------------
    def ingest_combat(self, combat: CombatSessionRecord) -> StyleVector:
        """Update the profile using ``combat`` and return the new style vector."""

        events = combat.card_events
        for index, event in enumerate(events):
            follower = events[index + 1].card_id if index + 1 < len(events) else None
            predecessor = events[index - 1].card_id if index > 0 else None
            score = event.effectiveness(STATUS_WEIGHTS)
            stats = self.profile.card_usage(event.card_id)
            stats.record_event(
                event,
                score=score,
                victory=combat.victory,
                follower=follower,
                predecessor=predecessor,
            )
        self._record_combos(events, combat.victory)
        style_vector = self._compute_style_vector()
        self.profile.update_from_combat(combat, style_vector=style_vector)
        self._latest_style = style_vector
        return style_vector

    # ------------------------------------------------------------------
    def score_card(self, card_id: str) -> float:
        stats = self.profile.card_stats.get(card_id)
        if not stats or not stats.plays:
            return 0.0
        base_score = stats.average_score()
        synergy_bonus = 0.0
        for follower, count in stats.combo_followers.items():
            follower_stats = self.profile.card_stats.get(follower)
            if not follower_stats or not follower_stats.plays:
                continue
            synergy_bonus += follower_stats.average_score() * (count / max(stats.plays, 1)) * 0.2
        return base_score + synergy_bonus

    def rank_cards(self, *, limit: int = 10) -> List[Tuple[str, float]]:
        scored = [(card_id, self.score_card(card_id)) for card_id in self.profile.card_stats]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def top_combos(self, *, limit: int = 5, minimum_plays: int = 2) -> List[Tuple[Tuple[str, ...], float]]:
        combos: List[Tuple[Tuple[str, ...], float]] = []
        for key, stats in self.profile.combo_stats.items():
            if stats.plays < minimum_plays:
                continue
            combos.append((stats.key, stats.average_score()))
        combos.sort(key=lambda item: item[1], reverse=True)
        return combos[:limit]

    @property
    def style_vector(self) -> Optional[StyleVector]:
        return self._latest_style

    # ------------------------------------------------------------------
    def _record_combos(self, events: Sequence[CombatCardEvent], victory: bool) -> None:
        if len(events) < 2:
            return
        for length in (2, 3):
            if len(events) < length:
                continue
            for index in range(len(events) - length + 1):
                window = events[index : index + length]
                key = tuple(event.card_id for event in window)
                stats = self.profile.combo_usage(key)
                stats.record(window, victory=victory, status_weights=STATUS_WEIGHTS)

    def _compute_style_vector(self) -> StyleVector:
        fights = max(self.profile.fights_recorded, 1)
        damage_rate = self.profile.damage_dealt_total / fights
        block_rate = self.profile.block_gained_total / fights
        control_rate = self.profile.status_value_total / fights
        energy_spent = max(self.profile.energy_spent_total, 1.0)
        energy_efficiency = 1.0 - (self.profile.energy_wasted_total / energy_spent)
        energy_efficiency = max(min(energy_efficiency, 1.0), -1.0)

        combo_candidates = [(stats.key, stats.average_score(), stats.plays) for stats in self.profile.combo_stats.values() if stats.plays]
        dominant_combo: Tuple[str, ...] = ()
        combo_score = 0.0
        if combo_candidates:
            combo_candidates.sort(key=lambda item: (item[1], item[2]), reverse=True)
            dominant_combo, combo_score, _ = combo_candidates[0]

        draw_bias = self._compute_draw_bias()
        preferred_turn_window = self._resolve_turn_window()

        aggression = damage_rate + (combo_score * 0.2)
        defense = block_rate + (draw_bias * 0.15)
        control = control_rate + (combo_score * 0.1)
        combo = combo_score + draw_bias * 0.05

        summary_parts = [
            f"Aggression {aggression:.2f}",
            f"Defense {defense:.2f}",
            f"Control {control:.2f}",
            f"Combo {combo:.2f}",
            f"Energy {energy_efficiency:.2f}",
            f"Draw {draw_bias:.2f}",
            f"Turns {preferred_turn_window}",
        ]
        summary = " | ".join(summary_parts)
        return StyleVector(
            aggression=aggression,
            defense=defense,
            control=control,
            combo=combo,
            energy_efficiency=energy_efficiency,
            draw_bias=draw_bias,
            preferred_turn_window=preferred_turn_window,
            dominant_combo=dominant_combo,
            summary=summary,
        )

    def _compute_draw_bias(self) -> float:
        draw_events = 0
        total_plays = 0
        for stats in self.profile.card_stats.values():
            draw_events += stats.draw_triggers
            total_plays += stats.plays
        if not total_plays:
            return 0.0
        return draw_events / total_plays

    def _resolve_turn_window(self) -> str:
        bucket_counter: MutableMapping[str, int] = Counter()
        for stats in self.profile.card_stats.values():
            for bucket, count in stats.turn_buckets.items():
                bucket_counter[bucket] += count
        if not bucket_counter:
            return "unknown"
        bucket, _ = bucket_counter.most_common(1)[0]
        return bucket
