"""Data structures for the adaptive deck evolver mechanics."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from modules.basemod_wrapper.cards import SimpleCardBlueprint

TURN_BUCKETS: Tuple[Tuple[int, int], ...] = ((1, 2), (3, 5), (6, 9), (10, 99))
TURN_BUCKET_NAMES: Tuple[str, ...] = ("early", "mid", "late", "endurance")


@dataclass(slots=True)
class CombatCardEvent:
    """Represents a single card play recorded during combat."""

    card_id: str
    turn: int
    energy_before: float
    energy_spent: float
    energy_remaining: float
    damage_dealt: float
    block_gained: float
    player_hp_change: float
    enemy_hp_change: float
    status_effects: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    cards_drawn: int = 0
    cards_discarded: int = 0
    exhausted: bool = False
    retained: bool = False
    energy_generated: float = 0.0
    tags: Tuple[str, ...] = field(default_factory=tuple)
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())

    def effectiveness(self, status_weights: Mapping[str, float]) -> float:
        """Return a heuristic score describing how successful the play was."""

        enemy_effects = self.status_effects.get("enemy", {})
        player_effects = self.status_effects.get("player", {})
        neutral_effects = self.status_effects.get("environment", {})
        status_score = 0.0
        for status, amount in enemy_effects.items():
            weight = status_weights.get(status.lower(), 1.0)
            status_score += weight * float(amount)
        for status, amount in player_effects.items():
            weight = status_weights.get(status.lower(), 1.0)
            status_score -= abs(weight) * abs(float(amount))
        for status, amount in neutral_effects.items():
            weight = status_weights.get(status.lower(), 0.5)
            status_score += weight * float(amount)

        damage_score = float(self.damage_dealt)
        block_score = float(self.block_gained) * 0.65
        card_flow = (self.cards_drawn - self.cards_discarded) * 0.4
        energy_delta = (self.energy_generated - self.energy_spent) * 0.35
        energy_waste_penalty = max(self.energy_remaining, 0.0) * 0.15
        hp_penalty = 0.0
        if self.player_hp_change < 0:
            hp_penalty += abs(self.player_hp_change) * 1.4
        if self.enemy_hp_change > 0:
            hp_penalty += abs(self.enemy_hp_change) * 0.6
        combo_bonus = 0.35 if self.retained else 0.0
        exhaust_bonus = 0.55 if self.exhausted else 0.0

        score = (
            damage_score
            + block_score
            + status_score
            + card_flow
            + energy_delta
            + combo_bonus
            + exhaust_bonus
            - energy_waste_penalty
            - hp_penalty
        )
        return score

    def turn_bucket(self) -> str:
        for (start, end), name in zip(TURN_BUCKETS, TURN_BUCKET_NAMES):
            if start <= self.turn <= end:
                return name
        return TURN_BUCKET_NAMES[-1]


@dataclass(slots=True)
class CardUsageStats:
    """Aggregated card usage metrics across all recorded combats."""

    card_id: str
    plays: int = 0
    victories: int = 0
    defeats: int = 0
    total_score: float = 0.0
    positive_score: float = 0.0
    negative_score: float = 0.0
    damage_total: float = 0.0
    block_total: float = 0.0
    status_total: float = 0.0
    energy_spent: float = 0.0
    energy_generated: float = 0.0
    energy_wasted: float = 0.0
    average_energy_before: float = 0.0
    turn_buckets: MutableMapping[str, int] = field(default_factory=lambda: {bucket: 0 for bucket in TURN_BUCKET_NAMES})
    combo_followers: MutableMapping[str, int] = field(default_factory=dict)
    combo_predecessors: MutableMapping[str, int] = field(default_factory=dict)
    draw_triggers: int = 0
    exhaust_triggers: int = 0
    retention_triggers: int = 0
    last_played: float = 0.0

    def record_event(
        self,
        event: CombatCardEvent,
        *,
        score: float,
        victory: bool,
        follower: Optional[str] = None,
        predecessor: Optional[str] = None,
    ) -> None:
        self.plays += 1
        self.total_score += score
        if score >= 0:
            self.positive_score += score
        else:
            self.negative_score += score
        if victory:
            self.victories += 1
        else:
            self.defeats += 1
        self.damage_total += float(event.damage_dealt)
        self.block_total += float(event.block_gained)
        enemy_effects = event.status_effects.get("enemy", {})
        player_effects = event.status_effects.get("player", {})
        self.status_total += sum(float(amount) for amount in enemy_effects.values())
        self.status_total -= sum(abs(float(amount)) for amount in player_effects.values())
        self.energy_spent += float(event.energy_spent)
        self.energy_generated += float(event.energy_generated)
        self.energy_wasted += max(event.energy_remaining, 0.0)
        self.average_energy_before += float(event.energy_before)
        self.turn_buckets[event.turn_bucket()] = self.turn_buckets.get(event.turn_bucket(), 0) + 1
        self.draw_triggers += int(max(event.cards_drawn, 0))
        self.exhaust_triggers += 1 if event.exhausted else 0
        self.retention_triggers += 1 if event.retained else 0
        self.last_played = max(self.last_played, event.timestamp)
        if follower:
            self.combo_followers[follower] = self.combo_followers.get(follower, 0) + 1
        if predecessor:
            self.combo_predecessors[predecessor] = self.combo_predecessors.get(predecessor, 0) + 1

    def average_score(self) -> float:
        if not self.plays:
            return 0.0
        return self.total_score / self.plays

    def energy_efficiency(self) -> float:
        spent = self.energy_spent or 1.0
        return max(min((self.energy_generated + (self.energy_spent - self.energy_wasted)) / spent, 2.0), -2.0)

    def preferred_turn_bucket(self) -> str:
        if not self.plays:
            return "unknown"
        bucket, _ = max(self.turn_buckets.items(), key=lambda item: item[1])
        return bucket

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id,
            "plays": self.plays,
            "victories": self.victories,
            "defeats": self.defeats,
            "total_score": self.total_score,
            "positive_score": self.positive_score,
            "negative_score": self.negative_score,
            "damage_total": self.damage_total,
            "block_total": self.block_total,
            "status_total": self.status_total,
            "energy_spent": self.energy_spent,
            "energy_generated": self.energy_generated,
            "energy_wasted": self.energy_wasted,
            "average_energy_before": self.average_energy_before,
            "turn_buckets": dict(self.turn_buckets),
            "combo_followers": dict(self.combo_followers),
            "combo_predecessors": dict(self.combo_predecessors),
            "draw_triggers": self.draw_triggers,
            "exhaust_triggers": self.exhaust_triggers,
            "retention_triggers": self.retention_triggers,
            "last_played": self.last_played,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CardUsageStats":
        instance = cls(card_id=str(payload["card_id"]))
        instance.plays = int(payload.get("plays", 0))
        instance.victories = int(payload.get("victories", 0))
        instance.defeats = int(payload.get("defeats", 0))
        instance.total_score = float(payload.get("total_score", 0.0))
        instance.positive_score = float(payload.get("positive_score", 0.0))
        instance.negative_score = float(payload.get("negative_score", 0.0))
        instance.damage_total = float(payload.get("damage_total", 0.0))
        instance.block_total = float(payload.get("block_total", 0.0))
        instance.status_total = float(payload.get("status_total", 0.0))
        instance.energy_spent = float(payload.get("energy_spent", 0.0))
        instance.energy_generated = float(payload.get("energy_generated", 0.0))
        instance.energy_wasted = float(payload.get("energy_wasted", 0.0))
        instance.average_energy_before = float(payload.get("average_energy_before", 0.0))
        buckets = payload.get("turn_buckets", {})
        instance.turn_buckets = {bucket: int(buckets.get(bucket, 0)) for bucket in TURN_BUCKET_NAMES}
        instance.combo_followers = {str(key): int(value) for key, value in (payload.get("combo_followers", {}) or {}).items()}
        instance.combo_predecessors = {str(key): int(value) for key, value in (payload.get("combo_predecessors", {}) or {}).items()}
        instance.draw_triggers = int(payload.get("draw_triggers", 0))
        instance.exhaust_triggers = int(payload.get("exhaust_triggers", 0))
        instance.retention_triggers = int(payload.get("retention_triggers", 0))
        instance.last_played = float(payload.get("last_played", 0.0))
        return instance


@dataclass(slots=True)
class ComboStats:
    """Aggregated statistics for observed card combinations."""

    key: Tuple[str, ...]
    plays: int = 0
    victories: int = 0
    defeats: int = 0
    total_score: float = 0.0
    damage_total: float = 0.0
    block_total: float = 0.0
    energy_total: float = 0.0
    average_turn: float = 0.0

    def record(self, events: Sequence[CombatCardEvent], *, victory: bool, status_weights: Mapping[str, float]) -> None:
        if not events:
            return
        self.plays += 1
        if victory:
            self.victories += 1
        else:
            self.defeats += 1
        score = sum(event.effectiveness(status_weights) for event in events)
        self.total_score += score
        self.damage_total += sum(event.damage_dealt for event in events)
        self.block_total += sum(event.block_gained for event in events)
        self.energy_total += sum(event.energy_spent for event in events)
        turn_average = sum(event.turn for event in events) / len(events)
        self.average_turn = ((self.average_turn * (self.plays - 1)) + turn_average) / self.plays

    def average_score(self) -> float:
        if not self.plays:
            return 0.0
        return self.total_score / self.plays

    def energy_cost(self) -> float:
        if not self.plays:
            return 0.0
        return self.energy_total / self.plays

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": list(self.key),
            "plays": self.plays,
            "victories": self.victories,
            "defeats": self.defeats,
            "total_score": self.total_score,
            "damage_total": self.damage_total,
            "block_total": self.block_total,
            "energy_total": self.energy_total,
            "average_turn": self.average_turn,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ComboStats":
        instance = cls(tuple(str(part) for part in payload.get("key", ()) or ()))
        instance.plays = int(payload.get("plays", 0))
        instance.victories = int(payload.get("victories", 0))
        instance.defeats = int(payload.get("defeats", 0))
        instance.total_score = float(payload.get("total_score", 0.0))
        instance.damage_total = float(payload.get("damage_total", 0.0))
        instance.block_total = float(payload.get("block_total", 0.0))
        instance.energy_total = float(payload.get("energy_total", 0.0))
        instance.average_turn = float(payload.get("average_turn", 0.0))
        return instance


@dataclass(slots=True)
class CombatSessionRecord:
    """Snapshot describing a completed combat encounter."""

    combat_id: str
    enemy: str
    floor: int
    victory: bool
    turn_count: int
    player_hp_start: float
    player_hp_end: float
    card_events: Tuple[CombatCardEvent, ...]
    relics: Tuple[str, ...] = ()
    reward_cards: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())

    @property
    def damage_taken(self) -> float:
        return max(self.player_hp_start - self.player_hp_end, 0.0)

    @property
    def style_signature(self) -> Mapping[str, Any]:
        return {
            "enemy": self.enemy,
            "floor": self.floor,
            "turn_count": self.turn_count,
            "relics": self.relics,
            "reward_cards": self.reward_cards,
        }


@dataclass(slots=True)
class StyleVector:
    """Represents the aggregate fighting style detected for a profile."""

    aggression: float
    defense: float
    control: float
    combo: float
    energy_efficiency: float
    draw_bias: float
    preferred_turn_window: str
    dominant_combo: Tuple[str, ...]
    summary: str

    def dominant_archetype(self) -> str:
        scores = {
            "aggressive": self.aggression,
            "defensive": self.defense,
            "control": self.control,
            "combo": self.combo,
        }
        archetype, _ = max(scores.items(), key=lambda item: item[1])
        return archetype

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aggression": self.aggression,
            "defense": self.defense,
            "control": self.control,
            "combo": self.combo,
            "energy_efficiency": self.energy_efficiency,
            "draw_bias": self.draw_bias,
            "preferred_turn_window": self.preferred_turn_window,
            "dominant_combo": list(self.dominant_combo),
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StyleVector":
        return cls(
            aggression=float(payload.get("aggression", 0.0)),
            defense=float(payload.get("defense", 0.0)),
            control=float(payload.get("control", 0.0)),
            combo=float(payload.get("combo", 0.0)),
            energy_efficiency=float(payload.get("energy_efficiency", 0.0)),
            draw_bias=float(payload.get("draw_bias", 0.0)),
            preferred_turn_window=str(payload.get("preferred_turn_window", "unknown")),
            dominant_combo=tuple(str(part) for part in payload.get("dominant_combo", ()) or ()),
            summary=str(payload.get("summary", "")),
        )


@dataclass(slots=True)
class CardProfile:
    """Serializable mirror of :class:`SimpleCardBlueprint` with metadata."""

    identifier: str
    title: str
    description: str
    upgrade_description: Optional[str]
    card_type: str
    target: str
    rarity: str
    cost: int
    value: int
    upgrade_value: int
    effect: Optional[str]
    secondary_value: Optional[int]
    secondary_upgrade: int
    keywords: Tuple[str, ...] = field(default_factory=tuple)
    keyword_values: Mapping[str, int] = field(default_factory=dict)
    keyword_upgrades: Mapping[str, int] = field(default_factory=dict)
    attack_effect: str = "SLASH_DIAGONAL"
    card_uses: Optional[int] = None
    card_uses_upgrade: int = 0
    role: str = "generalist"
    generated_by: Optional[str] = None
    notes: Tuple[str, ...] = ()

    def to_blueprint(self) -> SimpleCardBlueprint:
        return SimpleCardBlueprint(
            identifier=self.identifier,
            title=self.title,
            description=self.description,
            cost=self.cost,
            card_type=self.card_type,
            target=self.target,
            rarity=self.rarity,
            value=self.value,
            upgrade_value=self.upgrade_value,
            effect=self.effect,
            secondary_value=self.secondary_value,
            secondary_upgrade=self.secondary_upgrade,
            keywords=self.keywords,
            keyword_values=dict(self.keyword_values),
            keyword_upgrades=dict(self.keyword_upgrades),
            attack_effect=self.attack_effect,
            card_uses=self.card_uses,
            card_uses_upgrade=self.card_uses_upgrade,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identifier": self.identifier,
            "title": self.title,
            "description": self.description,
            "upgrade_description": self.upgrade_description,
            "card_type": self.card_type,
            "target": self.target,
            "rarity": self.rarity,
            "cost": self.cost,
            "value": self.value,
            "upgrade_value": self.upgrade_value,
            "effect": self.effect,
            "secondary_value": self.secondary_value,
            "secondary_upgrade": self.secondary_upgrade,
            "keywords": list(self.keywords),
            "keyword_values": dict(self.keyword_values),
            "keyword_upgrades": dict(self.keyword_upgrades),
            "attack_effect": self.attack_effect,
            "card_uses": self.card_uses,
            "card_uses_upgrade": self.card_uses_upgrade,
            "role": self.role,
            "generated_by": self.generated_by,
            "notes": list(self.notes),
        }

    @classmethod
    def from_blueprint(
        cls,
        blueprint: SimpleCardBlueprint,
        *,
        role: str = "generalist",
        generated_by: Optional[str] = None,
        notes: Sequence[str] = (),
    ) -> "CardProfile":
        upgrade_description = None
        localisation = blueprint.localizations.get("eng") if blueprint.localizations else None
        if localisation is not None:
            upgrade_description = localisation.upgrade_description
        return cls(
            identifier=blueprint.identifier,
            title=blueprint.title,
            description=blueprint.description,
            upgrade_description=upgrade_description,
            card_type=blueprint.card_type,
            target=blueprint.target,
            rarity=blueprint.rarity,
            cost=blueprint.cost,
            value=blueprint.value,
            upgrade_value=blueprint.upgrade_value,
            effect=blueprint.effect,
            secondary_value=blueprint.secondary_value,
            secondary_upgrade=blueprint.secondary_upgrade,
            keywords=tuple(blueprint.keywords),
            keyword_values=dict(blueprint.keyword_values),
            keyword_upgrades=dict(blueprint.keyword_upgrades),
            attack_effect=blueprint.attack_effect,
            card_uses=blueprint.card_uses,
            card_uses_upgrade=blueprint.card_uses_upgrade,
            role=role,
            generated_by=generated_by,
            notes=tuple(notes),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CardProfile":
        return cls(
            identifier=str(payload["identifier"]),
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            upgrade_description=payload.get("upgrade_description"),
            card_type=str(payload.get("card_type", "ATTACK")),
            target=str(payload.get("target", "ENEMY")),
            rarity=str(payload.get("rarity", "COMMON")),
            cost=int(payload.get("cost", 1)),
            value=int(payload.get("value", 6)),
            upgrade_value=int(payload.get("upgrade_value", 3)),
            effect=payload.get("effect"),
            secondary_value=payload.get("secondary_value"),
            secondary_upgrade=int(payload.get("secondary_upgrade", 0)),
            keywords=tuple(str(keyword) for keyword in payload.get("keywords", ()) or ()),
            keyword_values={str(k): int(v) for k, v in (payload.get("keyword_values", {}) or {}).items()},
            keyword_upgrades={str(k): int(v) for k, v in (payload.get("keyword_upgrades", {}) or {}).items()},
            attack_effect=str(payload.get("attack_effect", "SLASH_DIAGONAL")),
            card_uses=payload.get("card_uses"),
            card_uses_upgrade=int(payload.get("card_uses_upgrade", 0)),
            role=str(payload.get("role", "generalist")),
            generated_by=payload.get("generated_by"),
            notes=tuple(str(entry) for entry in payload.get("notes", ()) or ()),
        )

    def apply_mutation(self, mutation: "DeckMutation") -> None:
        if mutation.new_value is not None:
            self.value = int(mutation.new_value)
        if mutation.new_upgrade_value is not None:
            self.upgrade_value = int(mutation.new_upgrade_value)
        if mutation.new_cost is not None:
            self.cost = int(mutation.new_cost)
        if mutation.new_secondary_value is not None:
            self.secondary_value = int(mutation.new_secondary_value)
        if mutation.new_secondary_upgrade is not None:
            self.secondary_upgrade = int(mutation.new_secondary_upgrade)
        if mutation.description is not None:
            self.description = mutation.description
        if mutation.upgrade_description is not None:
            self.upgrade_description = mutation.upgrade_description
        if mutation.role:
            self.role = mutation.role
        if mutation.keyword_adjustments:
            keywords = set(self.keywords)
            values = dict(self.keyword_values)
            upgrades = dict(self.keyword_upgrades)
            for adjustment in mutation.keyword_adjustments:
                keywords.add(adjustment.keyword)
                if adjustment.amount is not None:
                    values[adjustment.keyword] = int(adjustment.amount)
                if adjustment.upgrade is not None:
                    upgrades[adjustment.keyword] = int(adjustment.upgrade)
                if adjustment.card_uses is not None:
                    self.card_uses = int(adjustment.card_uses)
                if adjustment.card_uses_upgrade is not None:
                    self.card_uses_upgrade = int(adjustment.card_uses_upgrade)
            self.keywords = tuple(sorted(keywords))
            self.keyword_values = values
            self.keyword_upgrades = upgrades
        if mutation.notes:
            self.notes = tuple(sorted(set(self.notes) | set(mutation.notes)))


@dataclass(slots=True)
class KeywordAdjustment:
    """Describes a keyword change to apply to a card."""

    keyword: str
    amount: Optional[int] = None
    upgrade: Optional[int] = None
    card_uses: Optional[int] = None
    card_uses_upgrade: Optional[int] = None


@dataclass(slots=True)
class DeckMutation:
    """Represents a targeted modification to an existing card."""

    card_id: str
    new_value: Optional[int] = None
    new_upgrade_value: Optional[int] = None
    new_cost: Optional[int] = None
    new_secondary_value: Optional[int] = None
    new_secondary_upgrade: Optional[int] = None
    description: Optional[str] = None
    upgrade_description: Optional[str] = None
    keyword_adjustments: Tuple[KeywordAdjustment, ...] = ()
    role: str = "generalist"
    notes: Tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id,
            "new_value": self.new_value,
            "new_upgrade_value": self.new_upgrade_value,
            "new_cost": self.new_cost,
            "new_secondary_value": self.new_secondary_value,
            "new_secondary_upgrade": self.new_secondary_upgrade,
            "description": self.description,
            "upgrade_description": self.upgrade_description,
            "keyword_adjustments": [
                {
                    "keyword": adjustment.keyword,
                    "amount": adjustment.amount,
                    "upgrade": adjustment.upgrade,
                    "card_uses": adjustment.card_uses,
                    "card_uses_upgrade": adjustment.card_uses_upgrade,
                }
                for adjustment in self.keyword_adjustments
            ],
            "role": self.role,
            "notes": list(self.notes),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DeckMutation":
        adjustments = []
        for entry in payload.get("keyword_adjustments", ()) or ():
            adjustments.append(
                KeywordAdjustment(
                    keyword=str(entry.get("keyword", "")),
                    amount=entry.get("amount"),
                    upgrade=entry.get("upgrade"),
                    card_uses=entry.get("card_uses"),
                    card_uses_upgrade=entry.get("card_uses_upgrade"),
                )
            )
        return cls(
            card_id=str(payload["card_id"]),
            new_value=payload.get("new_value"),
            new_upgrade_value=payload.get("new_upgrade_value"),
            new_cost=payload.get("new_cost"),
            new_secondary_value=payload.get("new_secondary_value"),
            new_secondary_upgrade=payload.get("new_secondary_upgrade"),
            description=payload.get("description"),
            upgrade_description=payload.get("upgrade_description"),
            keyword_adjustments=tuple(adjustments),
            role=str(payload.get("role", "generalist")),
            notes=tuple(str(entry) for entry in payload.get("notes", ()) or ()),
            metadata=payload.get("metadata", {}),
        )


@dataclass(slots=True)
class DeckMutationPlan:
    """Aggregates deck mutations and generated cards for a combat cycle."""

    mutations: Tuple[DeckMutation, ...] = ()
    new_cards: Tuple[CardProfile, ...] = ()
    unlockables: Tuple[CardProfile, ...] = ()
    style_vector: Optional[StyleVector] = None
    notes: Tuple[str, ...] = ()
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    source_combat: Optional[str] = None

    def is_empty(self) -> bool:
        return not self.mutations and not self.new_cards and not self.unlockables

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutations": [mutation.to_dict() for mutation in self.mutations],
            "new_cards": [card.to_dict() for card in self.new_cards],
            "unlockables": [card.to_dict() for card in self.unlockables],
            "style_vector": self.style_vector.to_dict() if self.style_vector else None,
            "notes": list(self.notes),
            "timestamp": self.timestamp,
            "source_combat": self.source_combat,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DeckMutationPlan":
        mutations = [DeckMutation.from_dict(entry) for entry in payload.get("mutations", ()) or ()]
        new_cards = [CardProfile.from_dict(entry) for entry in payload.get("new_cards", ()) or ()]
        unlockables = [CardProfile.from_dict(entry) for entry in payload.get("unlockables", ()) or ()]
        style_vector_payload = payload.get("style_vector")
        style_vector = StyleVector.from_dict(style_vector_payload) if style_vector_payload else None
        return cls(
            mutations=tuple(mutations),
            new_cards=tuple(new_cards),
            unlockables=tuple(unlockables),
            style_vector=style_vector,
            notes=tuple(str(entry) for entry in payload.get("notes", ()) or ()),
            timestamp=float(payload.get("timestamp", datetime.utcnow().timestamp())),
            source_combat=payload.get("source_combat"),
        )
