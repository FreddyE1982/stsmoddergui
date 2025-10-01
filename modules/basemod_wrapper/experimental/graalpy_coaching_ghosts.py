"""Coaching ghost playback for GraalPy powered leaderboard chases.

The :mod:`experimental.graalpy_coaching_ghosts` module lets mods replay
leaderboard ghost runs alongside the current player and surface actionable
coaching prompts.  The implementation mirrors the established experimental
pattern by shipping two complementary APIs:

* :class:`GhostPlaybackEngine` – a granular telemetry pipeline that ingests
  ghost runs, tracks coaching sessions, compares player actions against the
  recorded run and broadcasts progress updates.
* :class:`CoachingGhostDirector` – a high level helper tailored for
  :class:`modules.modbuilder.Deck` / :class:`modules.modbuilder.Character`
  workflows.  It bundles leaderboard import helpers, starts comparison
  sessions, and keeps the character metadata synchronised so UI layers can show
  pace differentials directly in game.

Activating the module automatically ensures ``experimental.graalpy_runtime`` is
enabled so all telemetry processing executes inside the GraalPy backend.  The
engine, director registry and launch helpers are exposed through
:mod:`plugins.PLUGIN_MANAGER` to give tooling and plugins full control without
needing to import the module manually.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from plugins import PLUGIN_MANAGER

from . import is_active as experimental_is_active
from . import on as experimental_on

from modules.modbuilder.deck import Deck
from modules.modbuilder.character import Character

__all__ = [
    "ActionActor",
    "GhostActionType",
    "ActionRecord",
    "GhostRun",
    "CoachingUpdate",
    "SessionSnapshot",
    "GhostPlaybackEngine",
    "CoachingGhostDirector",
    "activate",
    "deactivate",
    "register_ghost_run",
    "load_ghost_runs",
    "launch_coaching_ghosts",
    "get_engine",
    "preview_ghost_actions",
]


class ActionActor(str, Enum):
    """Actors participating in a ghost coaching session."""

    GHOST = "ghost"
    PLAYER = "player"


class GhostActionType(str, Enum):
    """Enumeration of ghost / player action categories."""

    PLAY_CARD = "play_card"
    USE_POTION = "use_potion"
    BUY_CARD = "buy_card"
    GAIN_RELIC = "gain_relic"
    LOSE_HP = "lose_hp"
    GAIN_GOLD = "gain_gold"
    END_TURN = "end_turn"
    CUSTOM = "custom"


def _normalise_mapping(mapping: Mapping[str, Any]) -> Dict[str, Any]:
    return {str(key).lower(): mapping[key] for key in mapping}


def _score_payload(payload: Mapping[str, Any]) -> float:
    score = 0.0
    data = _normalise_mapping(payload)
    if "damage" in data:
        try:
            score += float(data["damage"])
        except (TypeError, ValueError):
            pass
    if "block" in data:
        try:
            score += float(data["block"]) * 0.5
        except (TypeError, ValueError):
            pass
    if "gold" in data:
        try:
            score += float(data["gold"]) * 0.2
        except (TypeError, ValueError):
            pass
    if "hp" in data:
        try:
            score -= abs(float(data["hp"])) * 0.4
        except (TypeError, ValueError):
            pass
    if "cards_drawn" in data:
        try:
            score += float(data["cards_drawn"]) * 0.3
        except (TypeError, ValueError):
            pass
    return score


def _match_identifier(payload_a: Mapping[str, Any], payload_b: Mapping[str, Any], keys: Sequence[str]) -> bool:
    lower_a = _normalise_mapping(payload_a)
    lower_b = _normalise_mapping(payload_b)
    for key in keys:
        if key not in lower_a or key not in lower_b:
            continue
        if str(lower_a[key]).lower() != str(lower_b[key]).lower():
            return False
    return True


@dataclass(frozen=True)
class ActionRecord:
    """Snapshot of a single action performed by a ghost or the player."""

    actor: ActionActor
    floor: int
    turn: int
    action_type: GhostActionType
    description: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: time.time())

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", dict(self.payload))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor": self.actor.value,
            "floor": self.floor,
            "turn": self.turn,
            "action_type": self.action_type.value,
            "description": self.description,
            "payload": dict(self.payload),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, actor: Optional[ActionActor] = None) -> "ActionRecord":
        actor_value = data.get("actor", ActionActor.GHOST.value)
        if isinstance(actor_value, ActionActor):
            actor_obj = actor_value
        else:
            actor_obj = ActionActor(str(actor_value))

        action_value = data.get("action_type", GhostActionType.CUSTOM.value)
        if isinstance(action_value, GhostActionType):
            action_obj = action_value
        else:
            action_obj = GhostActionType(str(action_value))

        return cls(
            actor=actor or actor_obj,
            floor=int(data.get("floor", 0)),
            turn=int(data.get("turn", 0)),
            action_type=action_obj,
            description=str(data.get("description", "")),
            payload=dict(data.get("payload", {})),
            timestamp=float(data.get("timestamp", time.time())),
        )

    def order_token(self) -> Tuple[int, int, float]:
        return (self.floor, self.turn, self.timestamp)

    def score_value(self) -> float:
        return _score_payload(self.payload)

    def matches(self, other: "ActionRecord") -> bool:
        if self.action_type != other.action_type:
            return False
        if self.action_type in {GhostActionType.PLAY_CARD, GhostActionType.BUY_CARD}:
            return _match_identifier(self.payload, other.payload, ("card_id", "card", "identifier"))
        if self.action_type in {GhostActionType.GAIN_RELIC, GhostActionType.USE_POTION}:
            return _match_identifier(self.payload, other.payload, ("relic", "potion"))
        if self.action_type == GhostActionType.LOSE_HP:
            return _score_payload(self.payload) == _score_payload(other.payload)
        return True


@dataclass(frozen=True)
class GhostRun:
    """Immutable representation of a leaderboard ghost run."""

    ghost_id: str
    player_name: str
    score: int
    ascension_level: int
    actions: Tuple[ActionRecord, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "actions", tuple(self.actions))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ghost_id": self.ghost_id,
            "player_name": self.player_name,
            "score": self.score,
            "ascension_level": self.ascension_level,
            "actions": [action.to_dict() for action in self.actions],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GhostRun":
        actions = tuple(
            ActionRecord.from_dict(action, actor=ActionActor.GHOST)
            for action in data.get("actions", [])
        )
        return cls(
            ghost_id=str(data.get("ghost_id", "ghost")),
            player_name=str(data.get("player_name", "Unknown")),
            score=int(data.get("score", 0)),
            ascension_level=int(data.get("ascension_level", 0)),
            actions=actions,
            metadata=dict(data.get("metadata", {})),
        )

    def cumulative_scores(self) -> Tuple[float, ...]:
        scores: List[float] = []
        running = 0.0
        for action in self.actions:
            running += action.score_value()
            scores.append(running)
        return tuple(scores)


@dataclass(frozen=True)
class SessionSnapshot:
    """Immutable view of a coaching session's current progress."""

    session_id: str
    ghost_id: str
    player_name: str
    ghost_progress: int
    player_actions: Tuple[ActionRecord, ...]
    player_score: float
    ghost_score: float
    pace_delta: int
    recommendations: Tuple[str, ...]
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class CoachingUpdate:
    """Update emitted whenever a player action is recorded."""

    session_id: str
    ghost_action: Optional[ActionRecord]
    player_action: ActionRecord
    matched: bool
    pace_delta: int
    score_delta: float
    recommendation: str
    snapshot: SessionSnapshot


@dataclass
class _CoachingSession:
    """Mutable state container for an active coaching session."""

    session_id: str
    ghost_run: GhostRun
    player_name: str
    metadata: MutableMapping[str, Any]
    ghost_index: int = 0
    player_actions: List[ActionRecord] = field(default_factory=list)
    player_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    history: List[CoachingUpdate] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.metadata = dict(self.metadata)
        self._ghost_curve = self.ghost_run.cumulative_scores()

    def next_ghost_action(self) -> Optional[ActionRecord]:
        if self.ghost_index >= len(self.ghost_run.actions):
            return None
        return self.ghost_run.actions[self.ghost_index]

    def ghost_score(self) -> float:
        if not self._ghost_curve:
            return 0.0
        index = min(self.ghost_index, len(self._ghost_curve) - 1)
        return self._ghost_curve[index]

    def pace_delta(self) -> int:
        return len(self.player_actions) - self.ghost_index

    def snapshot(self) -> SessionSnapshot:
        return SessionSnapshot(
            session_id=self.session_id,
            ghost_id=self.ghost_run.ghost_id,
            player_name=self.player_name,
            ghost_progress=self.ghost_index,
            player_actions=tuple(self.player_actions),
            player_score=self.player_score,
            ghost_score=self.ghost_score(),
            pace_delta=self.pace_delta(),
            recommendations=tuple(self.recommendations[-6:]),
            metadata=dict(self.metadata),
        )

    def record_player_action(self, action: ActionRecord) -> CoachingUpdate:
        self.player_actions.append(action)
        self.player_score += action.score_value()
        expected = self.next_ghost_action()
        matched = False
        recommendation: str
        if expected is None:
            recommendation = "Ghost run finished – push for personal best!"
        else:
            matched = action.matches(expected)
            if matched:
                self.ghost_index += 1
                recommendation = (
                    f"Matched ghost action '{expected.description}'."
                )
            else:
                recommendation = (
                    f"Ghost played '{expected.description}' on floor {expected.floor} turn {expected.turn}."
                )
        pace = self.pace_delta()
        ghost_score = self.ghost_score()
        score_delta = self.player_score - ghost_score
        if matched and action.score_value() < (expected.score_value() if expected else 0.0):
            recommendation += " Consider squeezing more value out of this turn to stay ahead."
        if not matched and expected is not None:
            if pace < 0:
                recommendation += " You are trailing the ghost's pace. Focus on high-impact plays."
            elif pace > 0:
                recommendation += " You are ahead of schedule – capitalise on the tempo advantage."
            else:
                recommendation += " Try mirroring the ghost's route to compare outcomes."
        self.recommendations.append(recommendation)
        snapshot = self.snapshot()
        update = CoachingUpdate(
            session_id=self.session_id,
            ghost_action=expected,
            player_action=action,
            matched=matched,
            pace_delta=pace,
            score_delta=score_delta,
            recommendation=recommendation,
            snapshot=snapshot,
        )
        self.history.append(update)
        return update


class GhostPlaybackEngine:
    """Core engine that tracks ghost runs and player coaching sessions."""

    def __init__(self) -> None:
        self._runs: Dict[str, GhostRun] = {}
        self._sessions: Dict[str, _CoachingSession] = {}
        self._listeners: List[Callable[[CoachingUpdate], None]] = []
        self._session_listeners: Dict[str, List[Callable[[CoachingUpdate], None]]] = {}
        self._lock = RLock()

    # -- ghost run management ---------------------------------------------
    def register_run(self, run: GhostRun, *, replace: bool = False) -> None:
        with self._lock:
            if not replace and run.ghost_id in self._runs:
                raise ValueError(f"Ghost run '{run.ghost_id}' is already registered.")
            self._runs[run.ghost_id] = run

    def load_runs(self, path: Path, *, replace: bool = False) -> Tuple[GhostRun, ...]:
        payload = json.loads(Path(path).read_text(encoding="utf8"))
        runs: List[GhostRun] = []
        if isinstance(payload, Mapping):
            payload = [payload]
        if not isinstance(payload, Iterable):
            raise TypeError("Ghost run manifest must be a mapping or sequence.")
        for entry in payload:
            run = GhostRun.from_dict(entry)
            self.register_run(run, replace=replace)
            runs.append(run)
        return tuple(runs)

    def runs(self) -> Mapping[str, GhostRun]:
        with self._lock:
            return dict(self._runs)

    def get_run(self, ghost_id: str) -> GhostRun:
        with self._lock:
            try:
                return self._runs[ghost_id]
            except KeyError as exc:
                raise KeyError(f"Ghost run '{ghost_id}' is not registered.") from exc

    # -- listener registration --------------------------------------------
    def register_listener(self, listener: Callable[[CoachingUpdate], None], *, session_id: Optional[str] = None) -> None:
        with self._lock:
            if session_id is None:
                if listener not in self._listeners:
                    self._listeners.append(listener)
            else:
                listeners = self._session_listeners.setdefault(session_id, [])
                if listener not in listeners:
                    listeners.append(listener)

    def _notify(self, update: CoachingUpdate) -> None:
        listeners = list(self._listeners)
        listeners.extend(self._session_listeners.get(update.session_id, ()))
        for listener in listeners:
            listener(update)

    # -- session lifecycle ------------------------------------------------
    def start_session(
        self,
        ghost_id: str,
        *,
        player_name: str,
        session_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> SessionSnapshot:
        with self._lock:
            if session_id is None:
                base_id = f"{ghost_id}:{int(time.time() * 1000)}"
                session_id = base_id
                counter = 1
                while session_id in self._sessions:
                    session_id = f"{base_id}:{counter}"
                    counter += 1
            elif session_id in self._sessions:
                raise ValueError(f"Session '{session_id}' already exists.")
            run = self.get_run(ghost_id)
            session = _CoachingSession(
                session_id=session_id,
                ghost_run=run,
                player_name=player_name,
                metadata=dict(metadata or {}),
            )
            self._sessions[session_id] = session
            snapshot = session.snapshot()
            return snapshot

    def end_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
            self._session_listeners.pop(session_id, None)

    def sessions(self) -> Mapping[str, SessionSnapshot]:
        with self._lock:
            return {session_id: session.snapshot() for session_id, session in self._sessions.items()}

    def record_player_action(self, session_id: str, action: ActionRecord) -> CoachingUpdate:
        with self._lock:
            try:
                session = self._sessions[session_id]
            except KeyError as exc:
                raise KeyError(f"Session '{session_id}' is not active.") from exc
            update = session.record_player_action(action)
        self._notify(update)
        return update

    def session_history(self, session_id: str) -> Tuple[CoachingUpdate, ...]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session '{session_id}' is not active.")
            return tuple(session.history)

    def snapshot(self, session_id: str) -> SessionSnapshot:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session '{session_id}' is not active.")
            return session.snapshot()

    def preview_actions(self, session_id: str, count: int = 3) -> Tuple[ActionRecord, ...]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session '{session_id}' is not active.")
            start = session.ghost_index
            run = session.ghost_run.actions
            return run[start : start + max(0, int(count))]


@dataclass
class CoachingGhostDirector:
    """High level helper that orchestrates coaching ghosts for a deck."""

    deck: type[Deck]
    engine: GhostPlaybackEngine
    default_player_name: str
    leaderboard: Dict[str, GhostRun] = field(default_factory=dict)
    active_sessions: Dict[str, SessionSnapshot] = field(default_factory=dict)

    def register_run(self, run: GhostRun, *, replace: bool = False) -> None:
        self.engine.register_run(run, replace=replace)
        self.leaderboard[run.ghost_id] = run

    def load_leaderboard(self, path: Path, *, replace: bool = False) -> Tuple[GhostRun, ...]:
        runs = self.engine.load_runs(path, replace=replace)
        for run in runs:
            self.leaderboard[run.ghost_id] = run
        return runs

    def available_ghosts(self) -> Tuple[str, ...]:
        return tuple(sorted(self.leaderboard))

    def start_session(
        self,
        ghost_id: str,
        *,
        player_name: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> SessionSnapshot:
        snapshot = self.engine.start_session(
            ghost_id,
            player_name=player_name or self.default_player_name,
            session_id=session_id,
            metadata={"deck": self.deck.display_name, **(metadata or {})},
        )
        self.active_sessions[snapshot.session_id] = snapshot
        return snapshot

    def record_turn(
        self,
        session_id: str,
        actions: Iterable[Mapping[str, Any] | ActionRecord],
    ) -> Tuple[CoachingUpdate, ...]:
        updates: List[CoachingUpdate] = []
        for item in actions:
            if isinstance(item, ActionRecord):
                record = item
            else:
                record = ActionRecord.from_dict(
                    {"action_type": item.get("action_type", GhostActionType.CUSTOM.value), **item},
                    actor=ActionActor.PLAYER,
                )
            if record.actor != ActionActor.PLAYER:
                record = ActionRecord(
                    actor=ActionActor.PLAYER,
                    floor=record.floor,
                    turn=record.turn,
                    action_type=record.action_type,
                    description=record.description,
                    payload=record.payload,
                    timestamp=record.timestamp,
                )
            update = self.engine.record_player_action(session_id, record)
            self.active_sessions[session_id] = update.snapshot
            updates.append(update)
        return tuple(updates)

    def apply_to_character(self, character: Character) -> Mapping[str, Any]:
        registry = getattr(character, "coaching_ghost_sessions", None)
        if registry is None:
            registry = {}
            setattr(character, "coaching_ghost_sessions", registry)
        for session_id, snapshot in self.active_sessions.items():
            registry[session_id] = {
                "ghost_id": snapshot.ghost_id,
                "player": snapshot.player_name,
                "pace_delta": snapshot.pace_delta,
                "player_score": snapshot.player_score,
                "ghost_score": snapshot.ghost_score,
                "recommendations": list(snapshot.recommendations),
                "metadata": dict(snapshot.metadata),
            }
        return registry


_ENGINE: Optional[GhostPlaybackEngine] = None
_DIRECTORS: Dict[str, CoachingGhostDirector] = {}


def activate() -> GhostPlaybackEngine:
    """Ensure the GraalPy runtime is active and return the playback engine."""

    if not experimental_is_active("graalpy_runtime"):
        experimental_on("graalpy_runtime")

    global _ENGINE
    if _ENGINE is None:
        _ENGINE = GhostPlaybackEngine()
    PLUGIN_MANAGER.expose("experimental_graalpy_ghosts_engine", _ENGINE)
    PLUGIN_MANAGER.expose("experimental_graalpy_ghosts_launch", launch_coaching_ghosts)
    PLUGIN_MANAGER.expose("experimental_graalpy_ghosts_sessions", _ENGINE.sessions)
    PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.experimental.graalpy_coaching_ghosts")
    return _ENGINE


def deactivate() -> None:
    """Tear down the playback engine and clear plugin exposures."""

    global _ENGINE
    _DIRECTORS.clear()
    _ENGINE = None
    PLUGIN_MANAGER.expose("experimental_graalpy_ghosts_engine", None)
    PLUGIN_MANAGER.expose("experimental_graalpy_ghosts_sessions", None)


def get_engine() -> GhostPlaybackEngine:
    if _ENGINE is None:
        raise RuntimeError("Coaching ghosts are not active. Call experimental.on('graalpy_coaching_ghosts').")
    return _ENGINE


def register_ghost_run(run: GhostRun, *, replace: bool = False) -> None:
    activate().register_run(run, replace=replace)


def load_ghost_runs(path: Path, *, replace: bool = False) -> Tuple[GhostRun, ...]:
    return activate().load_runs(path, replace=replace)


def launch_coaching_ghosts(
    deck: type[Deck],
    *,
    default_player_name: str = "Player",
    leaderboard: Optional[Path] = None,
) -> CoachingGhostDirector:
    engine = activate()
    director = CoachingGhostDirector(deck=deck, engine=engine, default_player_name=default_player_name)
    if leaderboard is not None:
        director.load_leaderboard(leaderboard)
    _DIRECTORS[deck.display_name] = director
    return director


def preview_ghost_actions(session_id: str, count: int = 3) -> Tuple[ActionRecord, ...]:
    return get_engine().preview_actions(session_id, count=count)


PLUGIN_MANAGER.expose("experimental_graalpy_ghosts_launch", launch_coaching_ghosts)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.experimental.graalpy_coaching_ghosts")
