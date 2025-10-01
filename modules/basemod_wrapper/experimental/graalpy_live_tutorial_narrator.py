"""Narrated tutorial engine powered by the GraalPy experimental backend.

The :mod:`experimental.graalpy_live_tutorial_narrator` module introduces a
voice-over queue that reacts to gameplay telemetry emitted by Slay the Spire.
Two complementary APIs are provided so tooling can choose the level of control
that best matches their workflow:

* :class:`TutorialNarrationEngine` – a granular event-driven pipeline.  It lets
  callers register :class:`VoiceLine` descriptors, ingest
  :class:`NarrationEvent` payloads, and receive :class:`NarrationCue` objects
  whenever a line is scheduled for playback.  Hooks are exposed for plugin
  authors who want to observe the narration queue in real time.
* :class:`TutorialNarrationDirector` – an ergonomic façade that plugs straight
  into :class:`modules.modbuilder.character.Character` instances.  It inspects
  the character's starting deck, generates onboarding voice lines, and provides
  helpers such as :meth:`TutorialNarrationDirector.record_card_draw` or
  :meth:`TutorialNarrationDirector.queue_run_start` so gameplay scripts can
  trigger narration without touching the lower-level engine.

Activating the module automatically enables
``experimental.graalpy_runtime`` when necessary so the narration pipeline runs
entirely inside the GraalVM process.  The engine, director registry, and launch
helper are exposed via :mod:`plugins` to keep companion tooling in sync.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import re
import time
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Any, Callable, Deque, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from plugins import PLUGIN_MANAGER

from . import is_active as experimental_is_active
from . import on as experimental_on

from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.modbuilder.character import Character
from modules.modbuilder.deck import Deck, DeckStatistics

__all__ = [
    "NarrationCue",
    "NarrationEvent",
    "NarrationEventType",
    "TutorialNarrationDirector",
    "TutorialNarrationEngine",
    "VoiceLine",
    "activate",
    "active_directors",
    "deactivate",
    "get_director",
    "get_engine",
    "launch_tutorial_narrator",
    "record_event",
]


class NarrationEventType(str, Enum):
    """Enumeration describing the narration triggers supported by the engine."""

    RUN_START = "run_start"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    CARD_DRAWN = "card_drawn"
    CARD_PLAYED = "card_played"
    CARD_DISCARDED = "card_discarded"
    DAMAGE_TAKEN = "damage_taken"
    POWER_APPLIED = "power_applied"
    KEYWORD_TRIGGERED = "keyword_triggered"
    CUSTOM = "custom"


@dataclass(frozen=True)
class NarrationEvent:
    """Snapshot describing a gameplay moment that could trigger narration."""

    event_type: NarrationEventType
    player: str
    turn: Optional[int] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    deck_statistics: Optional[DeckStatistics] = None
    timestamp: float = field(default_factory=lambda: time.time())

    def __post_init__(self) -> None:
        cleaned_metadata = {
            str(key): value for key, value in (self.metadata or {}).items()
        }
        object.__setattr__(self, "metadata", MappingProxyType(cleaned_metadata))


@dataclass(frozen=True)
class VoiceLine:
    """Declarative description of a voice line emitted by the narration engine."""

    identifier: str
    event_type: NarrationEventType
    script: str
    audio_path: Optional[Path] = None
    priority: int = 0
    tags: Sequence[str] = field(default_factory=tuple)
    condition: Optional[Callable[[NarrationEvent], bool]] = None
    cooldown_events: int = 0
    once: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        identifier = str(self.identifier).strip()
        if not identifier:
            raise ValueError("VoiceLine.identifier must be a non-empty string.")
        object.__setattr__(self, "identifier", identifier)
        script = str(self.script).strip()
        if not script:
            raise ValueError("VoiceLine.script must be a non-empty string.")
        object.__setattr__(self, "script", script)
        if self.audio_path is not None:
            object.__setattr__(self, "audio_path", Path(self.audio_path))
        cleaned_tags = tuple(sorted({str(tag) for tag in self.tags or ()}))
        object.__setattr__(self, "tags", cleaned_tags)
        meta = {str(key): value for key, value in (self.metadata or {}).items()}
        object.__setattr__(self, "metadata", MappingProxyType(meta))
        cooldown = int(self.cooldown_events or 0)
        if cooldown < 0:
            raise ValueError("VoiceLine.cooldown_events cannot be negative.")
        object.__setattr__(self, "cooldown_events", cooldown)


@dataclass(frozen=True)
class NarrationCue:
    """Concrete narration entry queued for playback."""

    line_id: str
    text: str
    audio_path: Optional[Path]
    event: NarrationEvent
    tags: Tuple[str, ...]
    metadata: Mapping[str, Any]
    voice_profile: Optional[str] = None
    timestamp: float = field(default_factory=lambda: time.time())


@dataclass
class _RegisteredLine:
    line: VoiceLine
    order: int


class _SafeFormatDict(dict):
    """Dictionary that returns ``{key}`` for missing entries during formatting."""

    def __missing__(self, key: str) -> str:
        return "{" + str(key) + "}"


def _normalise_keywords(keywords: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted({str(keyword).lower() for keyword in keywords if keyword}))


def _summarise_description(description: str) -> str:
    """Return a human readable summary of a card description."""

    def _replacement(match: re.Match[str]) -> str:
        token = match.group(1)
        return token.replace("_", " ")

    cleaned = re.sub(r"\s+", " ", description or "").strip()
    cleaned = re.sub(r"{([^}]+)}", _replacement, cleaned)
    if cleaned and not cleaned.endswith("."):
        cleaned += "."
    return cleaned


class TutorialNarrationEngine:
    """Granular pipeline that converts events into narration cues."""

    def __init__(self, *, queue_limit: int = 32) -> None:
        if queue_limit <= 0:
            raise ValueError("queue_limit must be a positive integer.")
        self._queue: Deque[NarrationCue] = deque(maxlen=queue_limit)
        self._queue_limit = queue_limit
        self._lines: Dict[NarrationEventType, List[_RegisteredLine]] = defaultdict(list)
        self._line_lookup: Dict[str, _RegisteredLine] = {}
        self._listeners: List[Callable[[NarrationCue], None]] = []
        self._scoped_listeners: Dict[NarrationEventType, List[Callable[[NarrationCue], None]]] = defaultdict(list)
        self._event_counter = 0
        self._line_usage: Dict[str, int] = defaultdict(int)
        self._cooldowns: Dict[str, int] = {}
        self._order_counter = 0
        self._lock = RLock()

    # ------------------------------------------------------------------
    # queue management helpers
    # ------------------------------------------------------------------
    @property
    def queue_limit(self) -> int:
        return self._queue_limit

    def set_queue_limit(self, value: int) -> None:
        if value <= 0:
            raise ValueError("queue_limit must be a positive integer.")
        with self._lock:
            if value == self._queue_limit:
                return
            snapshot = list(self._queue)
            self._queue = deque(snapshot, maxlen=value)
            self._queue_limit = value

    def pending_cues(self) -> Tuple[NarrationCue, ...]:
        with self._lock:
            return tuple(self._queue)

    def pop_next_cue(self) -> Optional[NarrationCue]:
        with self._lock:
            if not self._queue:
                return None
            return self._queue.popleft()

    def clear_queue(self) -> None:
        with self._lock:
            self._queue.clear()

    # ------------------------------------------------------------------
    # voice line registration
    # ------------------------------------------------------------------
    def register_voice_line(self, line: VoiceLine, *, replace: bool = False) -> VoiceLine:
        with self._lock:
            existing = self._line_lookup.get(line.identifier)
            if existing is not None:
                if not replace:
                    raise ValueError(
                        f"Voice line '{line.identifier}' is already registered."
                    )
                self._lines[existing.line.event_type].remove(existing)
            registered = _RegisteredLine(line=line, order=self._order_counter)
            self._order_counter += 1
            self._line_lookup[line.identifier] = registered
            self._lines[line.event_type].append(registered)
            return line

    def clear_voice_lines(self) -> None:
        with self._lock:
            self._lines.clear()
            self._line_lookup.clear()
            self._line_usage.clear()
            self._cooldowns.clear()

    def voice_lines(self) -> Mapping[str, VoiceLine]:
        with self._lock:
            return {identifier: reg.line for identifier, reg in self._line_lookup.items()}

    # ------------------------------------------------------------------
    # listener registration
    # ------------------------------------------------------------------
    def subscribe(
        self,
        listener: Callable[[NarrationCue], None],
        *,
        event_type: Optional[NarrationEventType] = None,
    ) -> None:
        if listener in self._listeners or any(
            listener in listeners for listeners in self._scoped_listeners.values()
        ):
            return
        if event_type is None:
            self._listeners.append(listener)
        else:
            self._scoped_listeners[event_type].append(listener)

    def unsubscribe(self, listener: Callable[[NarrationCue], None]) -> None:
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass
        for listeners in self._scoped_listeners.values():
            try:
                listeners.remove(listener)
            except ValueError:
                continue

    # ------------------------------------------------------------------
    # event ingestion
    # ------------------------------------------------------------------
    def ingest_event(self, event: NarrationEvent, *, voice_profile: Optional[str] = None) -> Optional[NarrationCue]:
        with self._lock:
            self._event_counter += 1
            candidates = list(self._lines.get(event.event_type, ()))
            if event.event_type is not NarrationEventType.CUSTOM:
                candidates.extend(self._lines.get(NarrationEventType.CUSTOM, ()))
            best: Optional[_RegisteredLine] = None
            best_score: Tuple[int, int] | None = None
            for registered in candidates:
                line = registered.line
                if line.once and self._line_usage.get(line.identifier, 0) > 0:
                    continue
                if line.cooldown_events:
                    last_event = self._cooldowns.get(line.identifier)
                    if last_event is not None and (self._event_counter - last_event) <= line.cooldown_events:
                        continue
                if line.condition is not None and not line.condition(event):
                    continue
                score = (line.priority, -registered.order)
                if best is None or score > best_score:
                    best = registered
                    best_score = score
            if best is None:
                return None
            cue = self._create_cue(best.line, event, voice_profile=voice_profile)
            self._queue.append(cue)
            self._line_usage[best.line.identifier] += 1
            if best.line.cooldown_events:
                self._cooldowns[best.line.identifier] = self._event_counter
        self._notify_listeners(cue)
        return cue

    def _create_cue(
        self,
        line: VoiceLine,
        event: NarrationEvent,
        *,
        voice_profile: Optional[str] = None,
    ) -> NarrationCue:
        context = self._build_context(event, line)
        try:
            text = line.script.format_map(_SafeFormatDict(context))
        except Exception as exc:  # pragma: no cover - defensive guard
            raise ValueError(
                f"Failed to render narration script '{line.identifier}': {exc}"
            ) from exc
        metadata = dict(line.metadata)
        metadata.setdefault("event_type", event.event_type.value)
        metadata.setdefault("line_identifier", line.identifier)
        metadata.setdefault("player", event.player)
        metadata.setdefault("turn", event.turn)
        metadata.setdefault("voice_profile", voice_profile)
        metadata.update(event.metadata)
        cue = NarrationCue(
            line_id=line.identifier,
            text=text,
            audio_path=line.audio_path,
            event=event,
            tags=line.tags,
            metadata=MappingProxyType(metadata),
            voice_profile=voice_profile,
        )
        return cue

    def _build_context(self, event: NarrationEvent, line: VoiceLine) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "player": event.player,
            "turn": event.turn or 0,
            "event_type": event.event_type.value,
        }
        context.update(event.metadata)
        if event.deck_statistics is not None:
            stats = event.deck_statistics
            context.setdefault("deck_total_cards", stats.total_cards)
            context.setdefault("deck_unique_cards", stats.unique_cards)
            commons = stats.rarity_counts.get("COMMON", 0)
            uncommons = stats.rarity_counts.get("UNCOMMON", 0)
            rares = stats.rarity_counts.get("RARE", 0)
            context.setdefault("deck_common_count", commons)
            context.setdefault("deck_uncommon_count", uncommons)
            context.setdefault("deck_rare_count", rares)
            distribution = stats.rarity_distribution
            context.setdefault("deck_common_percent", distribution.get("COMMON", 0.0))
            context.setdefault("deck_uncommon_percent", distribution.get("UNCOMMON", 0.0))
            context.setdefault("deck_rare_percent", distribution.get("RARE", 0.0))
        context.setdefault("line_identifier", line.identifier)
        context.setdefault("voice_tags", ", ".join(line.tags))
        return context

    def _notify_listeners(self, cue: NarrationCue) -> None:
        listeners = list(self._listeners)
        listeners.extend(self._scoped_listeners.get(cue.event.event_type, ()))
        for listener in listeners:
            listener(cue)


class TutorialNarrationDirector:
    """High-level helper that scripts narration for a character."""

    def __init__(
        self,
        character: Character,
        deck: type[Deck],
        *,
        engine: TutorialNarrationEngine,
        voice_profile: str = "mentor",
        queue_limit: int = 32,
    ) -> None:
        self._character = character
        self._deck = deck
        self._engine = engine
        self._voice_profile = str(voice_profile or "mentor")
        self._engine.set_queue_limit(max(self._engine.queue_limit, queue_limit))
        self._script_manifest: Dict[str, Dict[str, Any]] = {}
        self._registered_keywords: Dict[str, VoiceLine] = {}
        self._registered_cards: Dict[str, VoiceLine] = {}
        self._intro_lines: List[VoiceLine] = []
        self._line_index = 0
        self._highlighted_keywords: set[str] = set()

    # ------------------------------------------------------------------
    # public properties
    # ------------------------------------------------------------------
    @property
    def character(self) -> Character:
        return self._character

    @property
    def deck(self) -> type[Deck]:
        return self._deck

    @property
    def engine(self) -> TutorialNarrationEngine:
        return self._engine

    @property
    def voice_profile(self) -> str:
        return self._voice_profile

    # ------------------------------------------------------------------
    # script generation
    # ------------------------------------------------------------------
    def register_intro_line(
        self,
        script: str,
        *,
        priority: int = 50,
        audio_path: Optional[Path] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> VoiceLine:
        identifier = self._unique_identifier("intro")
        line = VoiceLine(
            identifier=identifier,
            event_type=NarrationEventType.RUN_START,
            script=script,
            audio_path=audio_path,
            priority=priority,
            tags=("intro", "run"),
            metadata=metadata or {},
        )
        self._engine.register_voice_line(line, replace=True)
        self._intro_lines.append(line)
        self._script_manifest[identifier] = self._manifest_entry(line)
        return line

    def register_keyword_hint(
        self,
        keyword: str,
        script: str,
        *,
        priority: int = 30,
        audio_path: Optional[Path] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> VoiceLine:
        keyword_key = str(keyword).lower()
        identifier = self._unique_identifier(f"keyword:{keyword_key}")

        def _condition(event: NarrationEvent) -> bool:
            event_keyword = str(event.metadata.get("keyword", "")).lower()
            return event_keyword == keyword_key

        line = VoiceLine(
            identifier=identifier,
            event_type=NarrationEventType.KEYWORD_TRIGGERED,
            script=script,
            audio_path=audio_path,
            priority=priority,
            tags=("keyword", keyword_key),
            condition=_condition,
            metadata=metadata or {},
        )
        self._engine.register_voice_line(line, replace=True)
        self._registered_keywords[keyword_key] = line
        self._script_manifest[identifier] = self._manifest_entry(line)
        return line

    def register_card_hint(
        self,
        card_id: str,
        script: str,
        *,
        priority: int = 20,
        audio_path: Optional[Path] = None,
        event_type: NarrationEventType = NarrationEventType.CARD_DRAWN,
        metadata: Optional[Mapping[str, Any]] = None,
        cooldown_events: int = 1,
    ) -> VoiceLine:
        resolved_id = str(card_id)
        identifier = self._unique_identifier(f"card:{resolved_id}:{event_type.value}")

        def _condition(event: NarrationEvent) -> bool:
            return str(event.metadata.get("card_id")) == resolved_id

        tags = ("card", resolved_id.lower())
        line = VoiceLine(
            identifier=identifier,
            event_type=event_type,
            script=script,
            audio_path=audio_path,
            priority=priority,
            tags=tags,
            condition=_condition,
            cooldown_events=cooldown_events,
            metadata=metadata or {},
        )
        self._engine.register_voice_line(line, replace=True)
        self._registered_cards[resolved_id] = line
        self._script_manifest[identifier] = self._manifest_entry(line)
        return line

    def script_from_deck(
        self,
        *,
        highlight_keywords: Sequence[str] = (),
        trigger: NarrationEventType = NarrationEventType.CARD_DRAWN,
        base_priority: int = 25,
    ) -> None:
        stats = self._deck.statistics()
        highlighted = {keyword.lower() for keyword in highlight_keywords}
        self._highlighted_keywords.update(highlighted)
        for blueprint in self._deck.cards():
            keywords = _normalise_keywords(blueprint.keywords)
            highlighted_keyword = next((kw for kw in keywords if kw in highlighted), None)
            summary = _summarise_description(blueprint.description)
            metadata = {
                "card_id": blueprint.identifier,
                "card_title": blueprint.title,
                "card_summary": summary,
                "card_keywords": keywords,
                "card_rarity": blueprint.rarity,
                "card_is_starter": bool(blueprint.starter),
                "deck_total_cards": stats.total_cards,
            }
            if highlighted_keyword:
                metadata["highlighted_keyword"] = highlighted_keyword
                script = (
                    "{player}, lean on {card_title} when you need {highlighted_keyword} – {card_summary}"
                )
                priority = base_priority + 5
            else:
                script = "{player}, remember {card_title}: {card_summary}"
                priority = base_priority
                if blueprint.starter:
                    priority += 2
            self.register_card_hint(
                blueprint.identifier,
                script,
                priority=priority,
                metadata=metadata,
                event_type=trigger,
            )

    # ------------------------------------------------------------------
    # event convenience wrappers
    # ------------------------------------------------------------------
    def queue_run_start(
        self,
        *,
        player_name: Optional[str] = None,
        run_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Tuple[Optional[NarrationCue], ...]:
        event = self._make_event(
            NarrationEventType.RUN_START,
            player_name=player_name,
            metadata={"run_id": run_id, **(metadata or {})},
        )
        cue = self._engine.ingest_event(event, voice_profile=self._voice_profile)
        return (cue,) if cue else tuple()

    def record_card_draw(
        self,
        card_id: str,
        *,
        player_name: Optional[str] = None,
        turn: Optional[int] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[NarrationCue]:
        blueprint = self._resolve_card(card_id)
        context = {
            "card_id": blueprint.identifier,
            "card_title": blueprint.title,
            "card_summary": _summarise_description(blueprint.description),
            "card_keywords": _normalise_keywords(blueprint.keywords),
            "card_rarity": blueprint.rarity,
        }
        context.update(metadata or {})
        return self._engine.ingest_event(
            self._make_event(
                NarrationEventType.CARD_DRAWN,
                player_name=player_name,
                turn=turn,
                metadata=context,
            ),
            voice_profile=self._voice_profile,
        )

    def record_keyword_trigger(
        self,
        keyword: str,
        *,
        player_name: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[NarrationCue]:
        key = str(keyword).lower()
        context = {"keyword": key}
        context.update(metadata or {})
        return self._engine.ingest_event(
            self._make_event(
                NarrationEventType.KEYWORD_TRIGGERED,
                player_name=player_name,
                metadata=context,
            ),
            voice_profile=self._voice_profile,
        )

    def apply_to_character(self, character: Optional[Character] = None) -> Mapping[str, Any]:
        target = character or self._character
        payload = {
            "voice_profile": self._voice_profile,
            "deck": self._deck.__name__,
            "script_summary": self.script_manifest(),
            "highlighted_keywords": tuple(sorted(self._highlighted_keywords)),
        }
        setattr(target, "tutorial_narration", payload)
        return MappingProxyType(payload)

    def script_manifest(self) -> Mapping[str, Mapping[str, Any]]:
        return MappingProxyType(
            {
                identifier: MappingProxyType(dict(entry))
                for identifier, entry in self._script_manifest.items()
            }
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _unique_identifier(self, suffix: str) -> str:
        self._line_index += 1
        base = self._character.mod_id or self._character.name
        return f"{base}:{suffix}:{self._line_index:03d}"

    def _manifest_entry(self, line: VoiceLine) -> Dict[str, Any]:
        entry = {
            "event_type": line.event_type.value,
            "script": line.script,
            "tags": tuple(line.tags),
            "priority": line.priority,
            "cooldown_events": line.cooldown_events,
            "metadata": dict(line.metadata),
        }
        if line.audio_path is not None:
            entry["audio_path"] = str(line.audio_path)
        return entry

    def _make_event(
        self,
        event_type: NarrationEventType,
        *,
        player_name: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        turn: Optional[int] = None,
    ) -> NarrationEvent:
        name = player_name or self._character.name
        decks = self._deck.statistics()
        return NarrationEvent(
            event_type=event_type,
            player=name,
            turn=turn,
            metadata=metadata or {},
            deck_statistics=decks,
        )

    def _resolve_card(self, card_id: str) -> SimpleCardBlueprint:
        identifier = str(card_id)
        for blueprint in self._deck.cards():
            if blueprint.identifier == identifier:
                return blueprint
        raise KeyError(f"Deck '{self._deck.__name__}' does not include card '{identifier}'.")


_ENGINE: Optional[TutorialNarrationEngine] = None
_DIRECTORS: Dict[str, TutorialNarrationDirector] = {}
_ENGINE_LOCK = RLock()


def get_engine() -> TutorialNarrationEngine:
    with _ENGINE_LOCK:
        global _ENGINE
        if _ENGINE is None:
            _ENGINE = TutorialNarrationEngine()
        return _ENGINE


def record_event(event: NarrationEvent, *, voice_profile: Optional[str] = None) -> Optional[NarrationCue]:
    return get_engine().ingest_event(event, voice_profile=voice_profile)


def active_directors() -> Mapping[str, TutorialNarrationDirector]:
    return MappingProxyType(dict(_DIRECTORS))


def get_director(mod_id: str) -> TutorialNarrationDirector:
    try:
        return _DIRECTORS[mod_id]
    except KeyError as exc:
        raise KeyError(f"No tutorial narrator registered for '{mod_id}'.") from exc


def launch_tutorial_narrator(
    character: Character,
    *,
    deck: Optional[type[Deck] | Deck] = None,
    default_voice: str = "mentor",
    queue_limit: int = 32,
    auto_script: bool = True,
    highlight_keywords: Sequence[str] = (),
) -> TutorialNarrationDirector:
    engine = get_engine()
    resolved_deck: Optional[type[Deck]]
    if deck is None:
        configured = character.start.deck
        if configured is None:
            raise ValueError(
                "launch_tutorial_narrator requires a deck argument when the character has no starting deck configured."
            )
        resolved_deck = configured if isinstance(configured, type) else configured.__class__
    elif isinstance(deck, Deck):
        resolved_deck = deck.__class__
    else:
        resolved_deck = deck
    if resolved_deck is None:
        raise ValueError("Unable to resolve the deck associated with the narrator.")
    director = TutorialNarrationDirector(
        character,
        resolved_deck,
        engine=engine,
        voice_profile=default_voice,
        queue_limit=queue_limit,
    )
    if auto_script:
        director.register_intro_line(
            "{player}, we begin with {deck_total_cards} cards – keep an eye on those {deck_common_percent:.0f}% commons.",
            priority=60,
        )
        director.script_from_deck(highlight_keywords=highlight_keywords)
    _DIRECTORS[character.mod_id] = director
    _refresh_plugin_exports()
    return director


def activate() -> None:
    if not experimental_is_active("graalpy_runtime"):
        experimental_on("graalpy_runtime")
    engine = get_engine()
    _refresh_plugin_exports(engine)
    PLUGIN_MANAGER.expose_module(
        "modules.basemod_wrapper.experimental.graalpy_live_tutorial_narrator"
    )


def deactivate() -> None:
    _DIRECTORS.clear()
    global _ENGINE
    _ENGINE = None
    PLUGIN_MANAGER.expose("experimental_graalpy_narration_engine", None)
    PLUGIN_MANAGER.expose("experimental_graalpy_narration_directors", {})
    PLUGIN_MANAGER.expose("experimental_graalpy_narration_launch", launch_tutorial_narrator)


def _refresh_plugin_exports(engine: Optional[TutorialNarrationEngine] = None) -> None:
    if engine is None:
        engine = _ENGINE
    PLUGIN_MANAGER.expose("experimental_graalpy_narration_engine", engine)
    PLUGIN_MANAGER.expose("experimental_graalpy_narration_directors", dict(_DIRECTORS))
    PLUGIN_MANAGER.expose("experimental_graalpy_narration_launch", launch_tutorial_narrator)


# Ensure the launch helper is visible even before activation so plugins can discover it.
PLUGIN_MANAGER.expose("experimental_graalpy_narration_launch", launch_tutorial_narrator)
PLUGIN_MANAGER.expose_module(
    "modules.basemod_wrapper.experimental.graalpy_live_tutorial_narrator"
)
