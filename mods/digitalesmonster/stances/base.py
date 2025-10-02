"""Foundation for the Digitales Monster stance system."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Sequence, Tuple, Type, Union

from modules.basemod_wrapper.stances import STANCE_REGISTRY, Stance
from mods.digitalesmonster.persistence import LevelStabilityProfile, LevelStabilityRecord
from plugins import PLUGIN_MANAGER

__all__ = [
    "DigimonStance",
    "DigimonStanceContext",
    "DigimonStanceError",
    "DigimonStabilityError",
    "DigimonStanceManager",
    "DigimonStanceRequirementError",
    "DigiviceActivationError",
    "PowerGrant",
    "StanceStatProfile",
    "StanceStabilityConfig",
    "StanceTransition",
]


class DigimonStanceError(RuntimeError):
    """Base class for stance related errors."""


class DigimonStabilityError(DigimonStanceError):
    """Raised when stability operations cannot be executed."""


class DigimonStanceRequirementError(DigimonStanceError):
    """Raised when a stance requirement (digivice, relic, etc.) is not satisfied."""


class DigiviceActivationError(DigimonStanceRequirementError):
    """Raised when a stance needs an active Digivice but none is available."""


@dataclass(frozen=True)
class StanceStabilityConfig:
    """Static stability configuration for a stance."""

    level: str
    start: int
    maximum: int
    entry_cost: int = 0
    per_turn_drain: int = 0
    recovery_on_exit: int = 0
    lower_bound: int = 0

    def clamp(self, value: int) -> int:
        if value < self.lower_bound:
            return self.lower_bound
        if value > self.maximum:
            return self.maximum
        return value


@dataclass(frozen=True)
class StanceStatProfile:
    """HP and core stat defaults applied when a stance is entered."""

    hp: int
    max_hp: int
    block: int = 0
    strength: int = 0
    dexterity: int = 0


@dataclass(frozen=True)
class PowerGrant:
    """Power application descriptor used when a stance is entered."""

    power_id: str
    amount: int
    remove_on_exit: bool = True


@dataclass
class DigimonStanceContext:
    """Mutable combat context updated by the stance manager."""

    profile: LevelStabilityProfile
    player_hp: int
    player_max_hp: int
    block: int = 0
    strength: int = 0
    dexterity: int = 0
    powers: MutableMapping[str, int] = field(default_factory=dict)
    relics: Tuple[str, ...] = ()
    digisoul: int = 0
    digivice_active: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def apply_stats(self, stats: StanceStatProfile) -> None:
        self.player_max_hp = stats.max_hp
        self.player_hp = min(stats.hp, stats.max_hp)
        self.block = stats.block
        self.strength = stats.strength
        self.dexterity = stats.dexterity

    def grant_power(self, power_id: str, amount: int) -> None:
        self.powers[power_id] = self.powers.get(power_id, 0) + int(amount)

    def remove_power(self, power_id: str, amount: Optional[int] = None) -> None:
        if power_id not in self.powers:
            return
        if amount is None:
            self.powers.pop(power_id, None)
            return
        new_value = self.powers[power_id] - int(amount)
        if new_value <= 0:
            self.powers.pop(power_id, None)
        else:
            self.powers[power_id] = new_value

    def require_digivice(self) -> None:
        if self.digivice_active:
            return
        normalized = {relic.lower() for relic in self.relics}
        if "digivice" in normalized or "digi-vice" in normalized:
            return
        raise DigiviceActivationError(
            "Champion- und höhere Level benötigen ein aktiviertes Digivice."
        )


@dataclass(frozen=True)
class StanceTransition:
    """Return value describing a stance change."""

    previous_identifier: Optional[str]
    new_identifier: Optional[str]
    reason: str
    stability_before: Optional[LevelStabilityRecord]
    stability_after: Optional[LevelStabilityRecord]
    forced_fallback: bool = False


class DigimonStance(Stance):
    """Base class for all Digitales Monster stances."""

    _abstract = True
    mod_id = "digitalesmonster"
    level: str = ""
    stats = StanceStatProfile(hp=70, max_hp=70)
    stability = StanceStabilityConfig(level="", start=0, maximum=0)
    entry_powers: Tuple[PowerGrant, ...] = ()
    fallback_identifier: Optional[str] = None

    def __init__(self) -> None:
        super().__init__()
        self._active_record: Optional[LevelStabilityRecord] = None

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------
    def verify_entry_requirements(
        self,
        *,
        manager: "DigimonStanceManager",
        context: DigimonStanceContext,
    ) -> None:
        """Validate stance entry requirements."""

    def on_enter(
        self,
        *,
        manager: "DigimonStanceManager",
        context: DigimonStanceContext,
        previous: Optional["DigimonStance"],
        previous_record: Optional[LevelStabilityRecord],
        new_record: LevelStabilityRecord,
        reason: str,
    ) -> None:
        self._active_record = new_record
        context.apply_stats(self.stats)
        for grant in self.entry_powers:
            context.grant_power(grant.power_id, grant.amount)
        self.updateDescription()
        manager.broadcast_event(
            "stance_entered",
            stance=self,
            context=context,
            previous=previous,
            previous_record=previous_record,
            new_record=new_record,
            reason=reason,
        )

    def on_exit(
        self,
        *,
        manager: "DigimonStanceManager",
        context: DigimonStanceContext,
        new_stance: Optional["DigimonStance"],
        record_before: LevelStabilityRecord,
        reason: str,
    ) -> None:
        for grant in self.entry_powers:
            if grant.remove_on_exit:
                context.remove_power(grant.power_id, grant.amount)
        manager.broadcast_event(
            "stance_exited",
            stance=self,
            context=context,
            new_stance=new_stance,
            record_before=record_before,
            reason=reason,
        )

    def on_stability_changed(
        self,
        *,
        manager: "DigimonStanceManager",
        context: DigimonStanceContext,
        record_before: LevelStabilityRecord,
        record_after: LevelStabilityRecord,
        reason: str,
    ) -> None:
        self._active_record = record_after
        self.updateDescription()
        manager.broadcast_event(
            "stability_changed",
            stance=self,
            context=context,
            record_before=record_before,
            record_after=record_after,
            reason=reason,
        )

    def on_turn_start(
        self,
        *,
        manager: "DigimonStanceManager",
        context: DigimonStanceContext,
        record: LevelStabilityRecord,
        reason: str,
    ) -> None:
        manager.broadcast_event(
            "turn_start",
            stance=self,
            context=context,
            record=record,
            reason=reason,
        )

    def on_instability(
        self,
        *,
        manager: "DigimonStanceManager",
        context: DigimonStanceContext,
        record: LevelStabilityRecord,
        reason: str,
    ) -> Optional[str]:
        manager.broadcast_event(
            "instability_triggered",
            stance=self,
            context=context,
            record=record,
            reason=reason,
        )
        return self.fallback_identifier

    # ------------------------------------------------------------------
    # Description helpers
    # ------------------------------------------------------------------
    def build_description(self, record: Optional[LevelStabilityRecord]) -> str:
        if record is None:
            return self.description_text
        return (
            f"Stabilität {record.current}/{record.maximum}. "
            f"Einstiegskosten {self.stability.entry_cost}, Verlust pro Runde {self.stability.per_turn_drain}."
        )

    def updateDescription(self) -> None:  # noqa: N802 - BaseMod uses camelCase
        description = self.build_description(self._active_record)
        if description:
            self.description = description
            self.description_text = description


class DigimonStanceManager:
    """Coordinator that keeps track of stance transitions and stability."""

    def __init__(
        self,
        profile: Optional[LevelStabilityProfile] = None,
        *,
        fallback_identifier: Optional[str] = None,
    ) -> None:
        self.profile = profile or LevelStabilityProfile()
        self.fallback_identifier = fallback_identifier
        self.current_stance: Optional[DigimonStance] = None
        self.current_record: Optional[LevelStabilityRecord] = None
        self._active_context: Optional[DigimonStanceContext] = None
        self._handling_instability = False

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------
    def create_context(
        self,
        *,
        player_hp: int,
        player_max_hp: int,
        block: int = 0,
        strength: int = 0,
        dexterity: int = 0,
        powers: Optional[MutableMapping[str, int]] = None,
        relics: Sequence[str] = (),
        digisoul: int = 0,
        digivice_active: bool = False,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> DigimonStanceContext:
        context = DigimonStanceContext(
            profile=self.profile,
            player_hp=int(player_hp),
            player_max_hp=int(player_max_hp),
            block=int(block),
            strength=int(strength),
            dexterity=int(dexterity),
            powers=powers or {},
            relics=tuple(relics),
            digisoul=int(digisoul),
            digivice_active=bool(digivice_active),
            metadata=dict(metadata or {}),
        )
        return context

    def prepare_stance(
        self,
        stance: Union[str, Type[DigimonStance], DigimonStance],
    ) -> LevelStabilityRecord:
        stance_obj = self._instantiate_stance(stance)
        return self._ensure_record(stance_obj)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def enter(
        self,
        stance: Union[str, Type[DigimonStance], DigimonStance],
        context: DigimonStanceContext,
        *,
        reason: str = "manual",
        enforce_requirements: bool = True,
    ) -> StanceTransition:
        new_stance = self._instantiate_stance(stance)
        record_before = self._ensure_record(new_stance)
        if enforce_requirements:
            new_stance.verify_entry_requirements(manager=self, context=context)

        previous_stance = self.current_stance
        previous_record = self.current_record

        if previous_stance is not None and previous_record is not None:
            previous_stance.on_exit(
                manager=self,
                context=context,
                new_stance=new_stance,
                record_before=previous_record,
                reason=reason,
            )

        updated_record = self._apply_entry_cost(new_stance, record_before)
        self.current_stance = new_stance
        self.current_record = updated_record
        self._active_context = context
        new_stance.on_enter(
            manager=self,
            context=context,
            previous=previous_stance,
            previous_record=previous_record,
            new_record=updated_record,
            reason=reason,
        )

        self.broadcast_event(
            "stance_changed",
            previous=previous_stance,
            new=new_stance,
            context=context,
            record_before=record_before,
            record_after=updated_record,
            reason=reason,
        )
        return StanceTransition(
            previous_identifier=previous_stance.identifier if previous_stance else None,
            new_identifier=new_stance.identifier,
            reason=reason,
            stability_before=record_before,
            stability_after=updated_record,
            forced_fallback=False,
        )

    def exit(self, *, reason: str = "manual") -> StanceTransition:
        if self.current_stance is None or self.current_record is None or self._active_context is None:
            raise DigimonStabilityError("No active stance to exit.")
        previous = self.current_stance
        record_before = self.current_record
        context = self._active_context
        previous.on_exit(
            manager=self,
            context=context,
            new_stance=None,
            record_before=record_before,
            reason=reason,
        )
        self.broadcast_event(
            "stance_changed",
            previous=previous,
            new=None,
            context=context,
            record_before=record_before,
            record_after=record_before,
            reason=reason,
        )
        self.current_stance = None
        self.current_record = None
        self._active_context = context
        return StanceTransition(
            previous_identifier=previous.identifier,
            new_identifier=None,
            reason=reason,
            stability_before=record_before,
            stability_after=record_before,
            forced_fallback=False,
        )

    def adjust_stability(self, delta: int, *, reason: str = "manual") -> LevelStabilityRecord:
        if self.current_stance is None or self.current_record is None or self._active_context is None:
            raise DigimonStabilityError("No active stance for stability adjustment.")
        config = self.current_stance.stability
        record_before = self.current_record
        new_value = config.clamp(record_before.current + int(delta))
        updated = self.profile.update_level(config.level, current=new_value)
        self.current_record = updated
        self.current_stance.on_stability_changed(
            manager=self,
            context=self._active_context,
            record_before=record_before,
            record_after=updated,
            reason=reason,
        )
        if updated.current <= config.lower_bound and delta < 0:
            self._trigger_instability(reason=reason)
        return updated

    def tick_turn(self, *, reason: str = "turn_start") -> LevelStabilityRecord:
        if self.current_stance is None or self.current_record is None:
            raise DigimonStabilityError("Cannot tick turn without an active stance.")
        config = self.current_stance.stability
        if config.per_turn_drain <= 0:
            self.current_stance.on_turn_start(
                manager=self,
                context=self._active_context,
                record=self.current_record,
                reason=reason,
            )
            return self.current_record
        updated = self.adjust_stability(-config.per_turn_drain, reason=reason)
        self.current_stance.on_turn_start(
            manager=self,
            context=self._active_context,
            record=updated,
            reason=reason,
        )
        return updated

    def broadcast_event(self, event: str, **payload: Any) -> None:
        PLUGIN_MANAGER.broadcast("digitalesmonster_stance_event", event=event, payload=payload)
        PLUGIN_MANAGER.broadcast(f"digitalesmonster_{event}", **payload)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _instantiate_stance(
        self,
        stance: Union[str, Type[DigimonStance], DigimonStance],
    ) -> DigimonStance:
        if isinstance(stance, DigimonStance):
            return stance
        if isinstance(stance, str):
            record = STANCE_REGISTRY.record(stance)
            if record is None:
                raise DigimonStabilityError(f"Unknown stance identifier '{stance}'.")
            return record.cls()
        if isinstance(stance, type) and issubclass(stance, DigimonStance):
            return stance()
        raise TypeError(f"Unsupported stance reference: {stance!r}")

    def _ensure_record(self, stance: DigimonStance) -> LevelStabilityRecord:
        config = stance.stability
        if not config.level:
            raise DigimonStabilityError(
                f"Stance '{stance.identifier}' does not define a stability level identifier."
            )
        try:
            record = self.profile.get(config.level)
        except KeyError:
            record = self.profile.register_level(
                config.level,
                start=config.start,
                maximum=config.maximum,
                current=config.start,
            )
        else:
            record = self.profile.update_level(
                config.level,
                start=config.start,
                maximum=config.maximum,
            )
            if record.current < config.lower_bound:
                record = self.profile.update_level(config.level, current=config.lower_bound)
        return record

    def _apply_entry_cost(
        self,
        stance: DigimonStance,
        record: LevelStabilityRecord,
    ) -> LevelStabilityRecord:
        cost = max(0, int(stance.stability.entry_cost))
        if cost == 0:
            return record
        new_value = stance.stability.clamp(record.current - cost)
        updated = self.profile.update_level(stance.stability.level, current=new_value)
        return updated

    def _trigger_instability(self, *, reason: str) -> None:
        if self._handling_instability:
            return
        if self.current_stance is None or self.current_record is None or self._active_context is None:
            return
        self._handling_instability = True
        try:
            fallback = self.current_stance.on_instability(
                manager=self,
                context=self._active_context,
                record=self.current_record,
                reason=reason,
            )
            fallback_identifier = fallback or self.fallback_identifier
            if fallback_identifier and fallback_identifier != self.current_stance.identifier:
                context = self._active_context
                self.enter(
                    fallback_identifier,
                    context,
                    reason="fallback",
                    enforce_requirements=False,
                )
        finally:
            self._handling_instability = False


PLUGIN_MANAGER.expose("DigimonStance", DigimonStance)
PLUGIN_MANAGER.expose("DigimonStanceContext", DigimonStanceContext)
PLUGIN_MANAGER.expose("DigimonStanceManager", DigimonStanceManager)
PLUGIN_MANAGER.expose("DigimonStabilityConfig", StanceStabilityConfig)
PLUGIN_MANAGER.expose("DigimonStanceStats", StanceStatProfile)
PLUGIN_MANAGER.expose("DigimonPowerGrant", PowerGrant)
PLUGIN_MANAGER.expose("DigimonStanceTransition", StanceTransition)
PLUGIN_MANAGER.expose_module("mods.digitalesmonster.stances.base", alias="digitalesmonster_stances_base")
