"""Cinematic boss rivalry tooling powered by the GraalPy experimental runtime.

This module implements the first entry in
``research/graalpy_runtime_modding_examples.md`` – the *Cinematic hand-crafted
boss rivalries*.  Activating the module provisions a battle telemetry engine
that reacts to player actions in real time, funnels the captured data through
trainer pipelines, and continuously rewrites encounter intent scripts without
leaving the GraalPy process.  The design intentionally exposes two API
surfaces:

* :class:`RivalryEngine` – a granular orchestration layer that lets advanced
  tooling feed telemetry events, register custom trainers, and subscribe to
  script updates.
* :class:`CinematicRivalryDirector` – a high-level ergonomic helper that plugs
  straight into :class:`modules.modbuilder.character.Character`, automatically
  keeping the character's runtime metadata in sync with the evolving intents.

When enabled the module guarantees the ``experimental.graalpy_runtime``
submodule is also active so the repository runs on the GraalPy backend.  The
entire API surface is registered with :mod:`plugins` so companion utilities or
gameplay prototypes can orchestrate rivalries without importing the module
directly.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Protocol, Sequence

from plugins import PLUGIN_MANAGER

from . import is_active as experimental_is_active
from . import on as experimental_on

from modules.modbuilder.character import Character

__all__ = [
    "activate",
    "deactivate",
    "AdaptiveDamageTrainer",
    "BossTelemetryEvent",
    "CinematicRivalryDirector",
    "IntentAction",
    "IntentFrame",
    "RivalryEngine",
    "RivalryScript",
    "TelemetryEventType",
    "get_engine",
    "launch_cinematic_rivalry",
    "record_event",
    "register_listener",
    "register_trainer",
]


class TelemetryEventType(str, Enum):
    """Enumeration describing combat telemetry events."""

    TURN_START = "turn_start"
    TURN_END = "turn_end"
    CARD_PLAYED = "card_played"
    DAMAGE_DEALT = "damage_dealt"
    POWER_APPLIED = "power_applied"
    CUSTOM = "custom"


@dataclass(frozen=True)
class BossTelemetryEvent:
    """Snapshot of a combat event emitted by the rivalry runtime."""

    boss_id: str
    turn: int
    event_type: TelemetryEventType
    payload: Mapping[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: time.time())


@dataclass(frozen=True)
class IntentAction:
    """Declarative description of a single boss action for an intent frame."""

    action: str
    value: Optional[float] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IntentFrame:
    """Intent payload orchestrated by the rivalry trainers for a given turn."""

    turn: int
    title: str
    description: str
    actions: Sequence[IntentAction] = field(default_factory=tuple)
    commentary: Optional[str] = None

    def with_action(self, action: IntentAction) -> "IntentFrame":
        """Return a copy of the frame with an additional action registered."""

        actions = tuple(self.actions) + (action,)
        return IntentFrame(
            turn=self.turn,
            title=self.title,
            description=self.description,
            actions=actions,
            commentary=self.commentary,
        )


@dataclass(frozen=True)
class RivalryScript:
    """Immutable representation of the current intent choreography."""

    boss_id: str
    rivalry_name: str
    frames: Sequence[IntentFrame] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def with_frame(self, frame: IntentFrame) -> "RivalryScript":
        """Return a new script where ``frame`` replaces the matching turn."""

        merged: List[IntentFrame] = [existing for existing in self.frames if existing.turn != frame.turn]
        merged.append(frame)
        merged.sort(key=lambda candidate: candidate.turn)
        metadata = dict(self.metadata)
        metadata.setdefault("updated_at", time.time())
        return RivalryScript(
            boss_id=self.boss_id,
            rivalry_name=self.rivalry_name,
            frames=tuple(merged),
            metadata=metadata,
        )


@dataclass
class RivalryProfile:
    """Mutable aggregation of a rivalry session."""

    boss_id: str
    rivalry_name: str
    events: List[BossTelemetryEvent] = field(default_factory=list)
    script: Optional[RivalryScript] = None
    statistics: MutableMapping[str, float] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)


class RivalryTrainer(Protocol):
    """Protocol for trainers capable of generating new intent scripts."""

    def train(self, profile: RivalryProfile, event: BossTelemetryEvent) -> Optional[RivalryScript]:
        """Inspect the telemetry event and optionally return an updated script."""


class RivalryEngine:
    """Core orchestration engine for telemetry ingestion and script synthesis."""

    def __init__(self) -> None:
        self._profiles: Dict[str, RivalryProfile] = {}
        self._trainers: List[RivalryTrainer] = []
        self._global_listeners: List[Callable[[RivalryScript], None]] = []
        self._scoped_listeners: Dict[str, List[Callable[[RivalryScript], None]]] = defaultdict(list)

    # -- profile management -------------------------------------------------
    def _ensure_profile(self, boss_id: str, *, rivalry_name: Optional[str] = None) -> RivalryProfile:
        profile = self._profiles.get(boss_id)
        if profile is None:
            profile = RivalryProfile(boss_id=boss_id, rivalry_name=rivalry_name or _default_rivalry_name(boss_id))
            self._profiles[boss_id] = profile
        elif rivalry_name and rivalry_name != profile.rivalry_name:
            profile.rivalry_name = rivalry_name
        return profile

    def set_initial_script(self, script: RivalryScript) -> None:
        profile = self._ensure_profile(script.boss_id, rivalry_name=script.rivalry_name)
        profile.script = script
        self._notify_listeners(script, profile.boss_id)

    def profile(self, boss_id: str) -> RivalryProfile:
        profile = self._profiles.get(boss_id)
        if profile is None:
            raise KeyError(f"Boss '{boss_id}' has not produced telemetry yet.")
        return profile

    # -- trainer registration ----------------------------------------------
    def register_trainer(self, trainer: RivalryTrainer) -> None:
        if trainer not in self._trainers:
            self._trainers.append(trainer)

    # -- listener registration ---------------------------------------------
    def register_listener(
        self,
        listener: Callable[[RivalryScript], None],
        *,
        boss_id: Optional[str] = None,
    ) -> None:
        if boss_id is None:
            if listener not in self._global_listeners:
                self._global_listeners.append(listener)
            return
        scoped = self._scoped_listeners[boss_id]
        if listener not in scoped:
            scoped.append(listener)

    # -- telemetry ingestion ------------------------------------------------
    def ingest_event(self, event: BossTelemetryEvent) -> RivalryScript:
        profile = self._ensure_profile(event.boss_id)
        profile.events.append(event)

        script = profile.script or RivalryScript(
            boss_id=profile.boss_id,
            rivalry_name=profile.rivalry_name,
            frames=(),
        )

        for trainer in self._trainers:
            updated = trainer.train(profile, event)
            if updated is not None:
                script = updated
                profile.script = updated

        if profile.script is None:
            profile.script = script

        self._notify_listeners(profile.script, profile.boss_id)
        return profile.script

    def scripts(self) -> Mapping[str, RivalryScript]:
        return {
            boss_id: profile.script
            for boss_id, profile in self._profiles.items()
            if profile.script is not None
        }

    def script_for(self, boss_id: str) -> RivalryScript:
        profile = self.profile(boss_id)
        if profile.script is None:
            raise KeyError(f"Boss '{boss_id}' does not have an active intent script yet.")
        return profile.script

    def reset(self, boss_id: Optional[str] = None) -> None:
        if boss_id is None:
            self._profiles.clear()
            return
        self._profiles.pop(boss_id, None)

    # -- notifications ------------------------------------------------------
    def _notify_listeners(self, script: RivalryScript, boss_id: str) -> None:
        for listener in list(self._global_listeners):
            listener(script)
        for listener in list(self._scoped_listeners.get(boss_id, [])):
            listener(script)


class AdaptiveDamageTrainer:
    """Default trainer that adapts boss aggression based on player damage."""

    def __init__(self, *, aggression_multiplier: float = 1.4, defensive_threshold: float = 10.0) -> None:
        self.aggression_multiplier = aggression_multiplier
        self.defensive_threshold = defensive_threshold

    def train(self, profile: RivalryProfile, event: BossTelemetryEvent) -> Optional[RivalryScript]:
        if event.event_type != TelemetryEventType.DAMAGE_DEALT:
            return None

        amount = float(event.payload.get("amount", 0.0))
        stats = profile.statistics
        stats["damage_events"] = stats.get("damage_events", 0.0) + 1.0
        stats["damage_total"] = stats.get("damage_total", 0.0) + amount
        average = stats["damage_total"] / max(stats["damage_events"], 1.0)

        intensity = "relentless" if average >= self.defensive_threshold else "cautious"
        action = "attack" if intensity == "relentless" else "buff"
        planned_value = max(math.ceil(average * self.aggression_multiplier), 4)

        frame = IntentFrame(
            turn=event.turn + 1,
            title=f"{profile.rivalry_name} {'Counterstrike' if intensity == 'relentless' else 'Recalibration'}",
            description=(
                f"{profile.rivalry_name} {('lashes out' if intensity == 'relentless' else 'steadies their stance')} "
                f"after enduring {average:.1f} damage on average."
            ),
            actions=(
                IntentAction(
                    action=action,
                    value=float(planned_value),
                    metadata={
                        "source": "adaptive_damage",
                        "average_damage": average,
                        "events": stats["damage_events"],
                    },
                ),
            ),
            commentary=f"Average player damage across {int(stats['damage_events'])} events: {average:.1f}",
        )

        base_script = profile.script or RivalryScript(
            boss_id=profile.boss_id,
            rivalry_name=profile.rivalry_name,
        )
        return base_script.with_frame(frame)


class CinematicRivalryDirector:
    """High level orchestrator that keeps a character in sync with rivalry scripts."""

    def __init__(
        self,
        engine: RivalryEngine,
        *,
        boss_id: str,
        rivalry_name: str,
        narrative: str,
        initial_script: RivalryScript,
        soundtrack: Optional[str] = None,
    ) -> None:
        self._engine = engine
        self.boss_id = boss_id
        self.rivalry_name = rivalry_name
        self.narrative = narrative
        self.soundtrack = soundtrack
        self._callbacks: List[Callable[[RivalryScript], None]] = []
        self._latest_script: Optional[RivalryScript] = None

        self._engine.set_initial_script(initial_script)
        self._engine.register_listener(self._capture_script, boss_id=boss_id)
        try:
            self._latest_script = self._engine.script_for(boss_id)
        except KeyError:
            self._latest_script = initial_script

    # -- listener bridge ----------------------------------------------------
    def _capture_script(self, script: RivalryScript) -> None:
        self._latest_script = script
        for callback in list(self._callbacks):
            callback(script)

    def add_callback(self, callback: Callable[[RivalryScript], None]) -> None:
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            if self._latest_script is not None:
                callback(self._latest_script)

    # -- telemetry convenience ---------------------------------------------
    def record_event(self, event: BossTelemetryEvent) -> RivalryScript:
        script = self._engine.ingest_event(event)
        self._latest_script = script
        return script

    def record_turn(self, events: Iterable[BossTelemetryEvent]) -> RivalryScript:
        script: Optional[RivalryScript] = None
        for event in events:
            script = self.record_event(event)
        if script is None:
            script = self.current_script()
        return script

    # -- state access -------------------------------------------------------
    def current_script(self) -> RivalryScript:
        if self._latest_script is None:
            self._latest_script = self._engine.script_for(self.boss_id)
        return self._latest_script

    def apply_to_character(self, character: Character) -> RivalryScript:
        script = self.current_script()
        registry = getattr(character, "cinematic_rivalry_scripts", None)
        if registry is None:
            registry = {}
            setattr(character, "cinematic_rivalry_scripts", registry)
        registry[self.boss_id] = {
            "script": script,
            "narrative": self.narrative,
            "soundtrack": self.soundtrack,
        }
        return script


_ENGINE: Optional[RivalryEngine] = None
_DIRECTORS: Dict[str, CinematicRivalryDirector] = {}


def _default_rivalry_name(boss_id: str) -> str:
    cleaned = boss_id.replace("_", " ").strip()
    return cleaned.title() or "Rival"


def activate() -> RivalryEngine:
    """Initialise the rivalry engine and ensure GraalPy is active."""

    if not experimental_is_active("graalpy_runtime"):
        experimental_on("graalpy_runtime")

    global _ENGINE
    if _ENGINE is None:
        engine = RivalryEngine()
        engine.register_trainer(AdaptiveDamageTrainer())
        _ENGINE = engine
    PLUGIN_MANAGER.expose("experimental_graalpy_rivalries_engine", _ENGINE)
    PLUGIN_MANAGER.expose("experimental_graalpy_rivalries_launch", launch_cinematic_rivalry)
    PLUGIN_MANAGER.expose("experimental_graalpy_rivalries_record", record_event)
    PLUGIN_MANAGER.expose_module(
        "modules.basemod_wrapper.experimental.graalpy_cinematic_rivalries"
    )
    return _ENGINE


def deactivate() -> None:
    """Tear down the rivalry engine and unregister plugin exposures."""

    global _ENGINE
    _DIRECTORS.clear()
    _ENGINE = None
    PLUGIN_MANAGER.expose("experimental_graalpy_rivalries_engine", None)
    PLUGIN_MANAGER.expose("experimental_graalpy_rivalries_record", None)


def get_engine() -> RivalryEngine:
    if _ENGINE is None:
        raise RuntimeError("Cinematic rivalries are not active. Call experimental.on('graalpy_cinematic_rivalries').")
    return _ENGINE


def register_trainer(trainer: RivalryTrainer) -> None:
    get_engine().register_trainer(trainer)


def register_listener(listener: Callable[[RivalryScript], None], *, boss_id: Optional[str] = None) -> None:
    get_engine().register_listener(listener, boss_id=boss_id)


def record_event(event: BossTelemetryEvent) -> RivalryScript:
    return get_engine().ingest_event(event)


def launch_cinematic_rivalry(
    boss_id: str,
    *,
    rivalry_name: Optional[str] = None,
    narrative: str,
    initial_script: Optional[RivalryScript] = None,
    soundtrack: Optional[str] = None,
) -> CinematicRivalryDirector:
    engine = activate()
    rivalry_label = rivalry_name or _default_rivalry_name(boss_id)
    script = initial_script or RivalryScript(boss_id=boss_id, rivalry_name=rivalry_label)
    director = CinematicRivalryDirector(
        engine,
        boss_id=boss_id,
        rivalry_name=rivalry_label,
        narrative=narrative,
        initial_script=script,
        soundtrack=soundtrack,
    )
    _DIRECTORS[boss_id] = director
    return director


PLUGIN_MANAGER.expose("experimental_graalpy_rivalries_launch", launch_cinematic_rivalry)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.experimental.graalpy_cinematic_rivalries")
