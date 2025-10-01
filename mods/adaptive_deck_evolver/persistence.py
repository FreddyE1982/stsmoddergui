"""Persistent profile storage for the adaptive deck evolver."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional, Sequence

from .models import (
    CardProfile,
    CardUsageStats,
    ComboStats,
    CombatSessionRecord,
    DeckMutationPlan,
    StyleVector,
)

SCHEMA_VERSION = 1


@dataclass(slots=True)
class PlayerProfile:
    """Stores aggregated analytics and deck state across runs."""

    mod_id: str
    schema_version: int = SCHEMA_VERSION
    fights_recorded: int = 0
    wins: int = 0
    losses: int = 0
    card_stats: MutableMapping[str, CardUsageStats] = field(default_factory=dict)
    combo_stats: MutableMapping[str, ComboStats] = field(default_factory=dict)
    deck: MutableMapping[str, CardProfile] = field(default_factory=dict)
    unlockables: MutableMapping[str, CardProfile] = field(default_factory=dict)
    style_history: Sequence[StyleVector] = field(default_factory=tuple)
    energy_spent_total: float = 0.0
    energy_wasted_total: float = 0.0
    damage_dealt_total: float = 0.0
    block_gained_total: float = 0.0
    status_value_total: float = 0.0
    generated_cards: int = 0
    mutation_history: Sequence[Dict[str, Any]] = field(default_factory=tuple)

    def card_usage(self, card_id: str) -> CardUsageStats:
        card_id = str(card_id)
        stats = self.card_stats.get(card_id)
        if stats is None:
            stats = CardUsageStats(card_id=card_id)
            self.card_stats[card_id] = stats
        return stats

    def combo_usage(self, key: Sequence[str]) -> ComboStats:
        identifier = tuple(key)
        stats = self.combo_stats.get("::".join(identifier))
        if stats is None:
            stats = ComboStats(identifier)
            self.combo_stats["::".join(identifier)] = stats
        return stats

    def register_card_profile(self, profile: CardProfile) -> None:
        self.deck[profile.identifier] = profile

    def register_unlockable(self, profile: CardProfile) -> None:
        self.unlockables[profile.identifier] = profile

    def update_from_combat(self, combat: CombatSessionRecord, *, style_vector: StyleVector) -> None:
        self.fights_recorded += 1
        if combat.victory:
            self.wins += 1
        else:
            self.losses += 1
        self.energy_spent_total += sum(event.energy_spent for event in combat.card_events)
        self.energy_wasted_total += sum(max(event.energy_remaining, 0.0) for event in combat.card_events)
        self.damage_dealt_total += sum(event.damage_dealt for event in combat.card_events)
        self.block_gained_total += sum(event.block_gained for event in combat.card_events)
        self.status_value_total += sum(
            sum(eff.values())
            for event in combat.card_events
            for eff in (event.status_effects.get("enemy", {}),)
        )
        history = list(self.style_history)
        history.append(style_vector)
        self.style_history = tuple(history[-20:])  # keep last 20 entries for smoothing

    def allocate_card_identifier(self, *, prefix: str = "adaptive") -> str:
        self.generated_cards += 1
        suffix = f"{self.generated_cards:03d}"
        return f"{self.mod_id}_{prefix}_{suffix}"

    def record_mutation_plan(self, plan: DeckMutationPlan) -> None:
        history = list(self.mutation_history)
        history.append(plan.to_dict())
        self.mutation_history = tuple(history[-50:])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mod_id": self.mod_id,
            "schema_version": self.schema_version,
            "fights_recorded": self.fights_recorded,
            "wins": self.wins,
            "losses": self.losses,
            "card_stats": {card_id: stats.to_dict() for card_id, stats in self.card_stats.items()},
            "combo_stats": {key: stats.to_dict() for key, stats in self.combo_stats.items()},
            "deck": {card_id: profile.to_dict() for card_id, profile in self.deck.items()},
            "unlockables": {card_id: profile.to_dict() for card_id, profile in self.unlockables.items()},
            "style_history": [vector.to_dict() for vector in self.style_history],
            "energy_spent_total": self.energy_spent_total,
            "energy_wasted_total": self.energy_wasted_total,
            "damage_dealt_total": self.damage_dealt_total,
            "block_gained_total": self.block_gained_total,
            "status_value_total": self.status_value_total,
            "generated_cards": self.generated_cards,
            "mutation_history": list(self.mutation_history),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PlayerProfile":
        profile = cls(mod_id=str(payload.get("mod_id", "adaptive")))
        profile.schema_version = int(payload.get("schema_version", SCHEMA_VERSION))
        profile.fights_recorded = int(payload.get("fights_recorded", 0))
        profile.wins = int(payload.get("wins", 0))
        profile.losses = int(payload.get("losses", 0))
        profile.card_stats = {
            card_id: CardUsageStats.from_dict(data)
            for card_id, data in (payload.get("card_stats", {}) or {}).items()
        }
        profile.combo_stats = {
            key: ComboStats.from_dict(data)
            for key, data in (payload.get("combo_stats", {}) or {}).items()
        }
        profile.deck = {
            card_id: CardProfile.from_dict(data)
            for card_id, data in (payload.get("deck", {}) or {}).items()
        }
        profile.unlockables = {
            card_id: CardProfile.from_dict(data)
            for card_id, data in (payload.get("unlockables", {}) or {}).items()
        }
        profile.style_history = tuple(
            StyleVector.from_dict(entry) for entry in payload.get("style_history", [])
        )
        profile.energy_spent_total = float(payload.get("energy_spent_total", 0.0))
        profile.energy_wasted_total = float(payload.get("energy_wasted_total", 0.0))
        profile.damage_dealt_total = float(payload.get("damage_dealt_total", 0.0))
        profile.block_gained_total = float(payload.get("block_gained_total", 0.0))
        profile.status_value_total = float(payload.get("status_value_total", 0.0))
        profile.generated_cards = int(payload.get("generated_cards", 0))
        profile.mutation_history = tuple(payload.get("mutation_history", []) or [])
        return profile


class ProfilePersistence:
    """Read/write helper for :class:`PlayerProfile`."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self, *, mod_id: str = "adaptive") -> PlayerProfile:
        if not self.path.exists():
            return PlayerProfile(mod_id=mod_id)
        payload = json.loads(self.path.read_text(encoding="utf8"))
        profile = PlayerProfile.from_dict(payload)
        if profile.schema_version != SCHEMA_VERSION:
            profile.schema_version = SCHEMA_VERSION
            self.save(profile)
        return profile

    def save(self, profile: PlayerProfile) -> None:
        payload = profile.to_dict()
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf8")

    def reset(self, *, mod_id: str = "adaptive") -> PlayerProfile:
        profile = PlayerProfile(mod_id=mod_id)
        self.save(profile)
        return profile
