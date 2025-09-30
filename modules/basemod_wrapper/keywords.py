"""Extensible keyword infrastructure for the Slay the Spire wrapper.

The module exposes :class:`Keyword` which mod authors can subclass to implement
custom gameplay behaviour without touching the underlying JVM plumbing.  All
keywords register themselves automatically and can be combined with canonical
ones declared on :class:`modules.basemod_wrapper.cards.SimpleCardBlueprint`.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
import json
import random
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
import weakref

from plugins import PLUGIN_MANAGER


_RANDOM = random.Random()


@lru_cache(maxsize=1)
def _wrapper_module():
    return import_module("modules.basemod_wrapper")


def _spire():
    return getattr(_wrapper_module(), "spire")


def _basemod():
    return getattr(_wrapper_module(), "basemod")


def _cardcrawl():
    return getattr(_wrapper_module(), "cardcrawl")


def _normalize_keyword(name: str) -> str:
    cleaned = name.strip()
    if ":" in cleaned:
        cleaned = cleaned.split(":", 1)[1]
    return cleaned.replace(" ", "").replace("-", "").replace("_", "").lower()


class KeywordError(RuntimeError):
    """Raised when keyword registration or execution fails."""


@dataclass
class _KeywordMetadata:
    keyword: "Keyword"
    names: Tuple[str, ...]
    description: str
    color: Optional[Sequence[float]] = None
    mod_id: Optional[str] = None

    def register_with_basemod(self) -> None:
        if not self.mod_id:
            return
        names = self.names or (self.keyword.name,)
        description = self.description or self.keyword.description
        if not names:
            return
        _spire().register_keyword(
            self.mod_id,
            self.keyword.keyword_id,
            names,
            description,
            proper_name=self.keyword.proper_name,
            color=self.color,
        )


class KeywordScheduler:
    """Schedule keyword callbacks across turns and combat events."""

    def __init__(self) -> None:
        self._pending_now: List[Callable[[], None]] = []
        self._start_of_turn: Dict[int, List[Callable[[], None]]] = {}
        self._end_of_turn: Dict[int, List[Callable[[], None]]] = {}
        self._turn: int = 0
        self._registered = False
        self._try_register_with_basemod()

    def _try_register_with_basemod(self) -> None:
        if self._registered:
            return
        try:
            _basemod().BaseMod.subscribe(self)
        except Exception:
            return
        self._registered = True

    def receiveOnBattleStart(self, _room: Any) -> None:  # pragma: no cover - requires JVM
        self.reset()

    def receiveOnStartOfTurnPostDraw(self) -> None:  # pragma: no cover - requires JVM
        self.advance_turn()

    def receivePostPlayerTurn(self) -> None:  # pragma: no cover - requires JVM
        self.execute_end_of_turn()

    @property
    def turn(self) -> int:
        return self._turn

    def reset(self) -> None:
        self._pending_now.clear()
        self._start_of_turn.clear()
        self._end_of_turn.clear()
        self._turn = 0

    def enqueue_immediate(self, func: Callable[[], None]) -> None:
        self._pending_now.append(func)

    def enqueue_start_of_turn(self, turn_offset: int, func: Callable[[], None]) -> None:
        target_turn = self._turn + max(1, turn_offset)
        self._start_of_turn.setdefault(target_turn, []).append(func)

    def enqueue_end_of_turn(self, turn_offset: int, func: Callable[[], None]) -> None:
        target_turn = self._turn + max(1, turn_offset)
        self._end_of_turn.setdefault(target_turn, []).append(func)

    def enqueue_random_turn(self, *, end_of_turn: bool, max_offset: int = 3, func: Callable[[], None]) -> None:
        offset = _RANDOM.randint(1, max_offset)
        if end_of_turn:
            self.enqueue_end_of_turn(offset, func)
        else:
            self.enqueue_start_of_turn(offset, func)

    def flush(self) -> None:
        tasks = list(self._pending_now)
        self._pending_now.clear()
        for task in tasks:
            task()

    def advance_turn(self) -> None:
        self._turn += 1
        tasks = self._start_of_turn.pop(self._turn, [])
        for task in tasks:
            task()

    def execute_end_of_turn(self) -> None:
        tasks = self._end_of_turn.pop(self._turn, [])
        for task in tasks:
            task()

    def debug_advance_turn(self) -> None:
        self.advance_turn()
        self.execute_end_of_turn()


_SCHEDULER = KeywordScheduler()
keyword_scheduler = _SCHEDULER


class CardPersistenceManager:
    """Persist card modifications across runs."""

    def __init__(self) -> None:
        self._path = Path(__file__).with_name("persistent_cards.json")
        self._data: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf8"))
            except json.JSONDecodeError:
                self._data = {}
        self._loaded = True

    def record(self, card_id: str, payload: Dict[str, Any]) -> None:
        self._ensure_loaded()
        existing = self._data.setdefault(card_id, {})
        existing.update(payload)
        self._path.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf8")

    def payload_for(self, card_id: str) -> Dict[str, Any]:
        self._ensure_loaded()
        return dict(self._data.get(card_id, {}))

    def apply_to_deck(self, deck: Iterable[Any]) -> None:
        self._ensure_loaded()
        for card in deck:
            payload = self._data.get(getattr(card, "cardID", ""))
            if not payload:
                continue
            CardEditor(card).apply(**payload)


_CARD_PERSISTENCE = CardPersistenceManager()


class CardEditor:
    """High level helper that mirrors ``SimpleCardBlueprint`` fields."""

    _SUPPORTED_FIELDS = {
        "title": "name",
        "description": "rawDescription",
        "cost": "cost",
        "value": "baseDamage",
        "block": "baseBlock",
        "magic": "baseMagicNumber",
        "rarity": "rarity",
        "target": "target",
        "card_type": "type",
    }

    def __init__(self, card: Any) -> None:
        self._card = card

    def apply(self, **fields: Any) -> None:
        for key, value in fields.items():
            attr = self._SUPPORTED_FIELDS.get(key)
            if attr:
                setattr(self._card, attr, value)
                continue
            if hasattr(self._card, key):
                setattr(self._card, key, value)

    def persist_for_combat(self, **fields: Any) -> None:
        self.apply(**fields)
        if hasattr(self._card, "initializeDescription"):
            try:
                self._card.initializeDescription()
            except Exception:
                pass

    def persist_for_run(self, player: Any, **fields: Any) -> None:
        self.persist_for_combat(**fields)
        master_deck = getattr(player, "masterDeck", None)
        if master_deck is None:
            return
        card_id = getattr(self._card, "cardID", None)
        if card_id is None:
            return
        for candidate in getattr(master_deck, "group", []):
            if getattr(candidate, "cardID", None) == card_id:
                CardEditor(candidate).apply(**fields)

    def persist_forever(self, player: Any, **fields: Any) -> None:
        self.persist_for_run(player, **fields)
        card_id = getattr(self._card, "cardID", None)
        if card_id is not None:
            _CARD_PERSISTENCE.record(card_id, fields)


class CardZoneProxy:
    """Expose card piles with editing helpers."""

    def __init__(self, owner: Any, accessor: Callable[[], Iterable[Any]]) -> None:
        self._owner = owner
        self._accessor = accessor

    def __len__(self) -> int:
        collection = self._accessor()
        if hasattr(collection, "size"):
            return int(collection.size())  # pragma: no cover - requires JVM
        return len(getattr(collection, "group", collection))

    def get(self, index: int) -> CardEditor:
        collection = self._accessor()
        if hasattr(collection, "group"):
            group = list(collection.group)
        else:
            group = list(collection)
        card = group[index]
        return CardEditor(card)

    def add_by_name(self, name: str) -> None:
        cardcrawl = _cardcrawl()
        library = cardcrawl.helpers.CardLibrary
        card = library.getCard(name)
        if card is None:
            raise KeywordError(f"Unknown card '{name}'.")
        player = getattr(cardcrawl.dungeons.AbstractDungeon, "player", None)
        if player is None:
            raise KeywordError("Player is not available – cannot add card to hand.")
        action = cardcrawl.actions.common.MakeTempCardInHandAction(card.makeCopy(), 1)
        cardcrawl.dungeons.AbstractDungeon.actionManager.addToBottom(action)


class HPProxy:
    """Expose HP related operations for the active player."""

    def __init__(self, context: "KeywordContext") -> None:
        self._context = context

    @property
    def value(self) -> int:
        temp_field = _spire().stslib.patches.tempHp.TempHPField.tempHp
        return int(temp_field.get(self._context.player))

    def _set_temp_hp(self, value: int) -> None:
        player = self._context.player
        current = self.value
        delta = int(value) - current
        if delta == 0:
            return
        if delta > 0:
            action_cls = _spire().action("AddTemporaryHPAction")
            action = action_cls(player, player, delta)
        else:
            action_cls = _spire().action("RemoveAllTemporaryHPAction")
            action = action_cls(player, player)
        self._context.enqueue_action(action)

    def __int__(self) -> int:
        return self.value

    def __iadd__(self, other: int) -> "HPProxy":
        self._set_temp_hp(self.value + int(other))
        return self

    def __isub__(self, other: int) -> "HPProxy":
        self._set_temp_hp(self.value - int(other))
        return self

    @property
    def permanent(self) -> int:
        return int(self._context.player.maxHealth)

    @permanent.setter
    def permanent(self, value: int) -> None:
        player = self._context.player
        current = int(player.maxHealth)
        delta = int(value) - current
        cardcrawl = _cardcrawl()
        if delta == 0:
            return
        if delta > 0:
            action = cardcrawl.actions.common.IncreaseMaxHpAction(player, delta, True)
        else:
            action = cardcrawl.actions.common.LoseMaxHpAction(player, player, abs(delta))
        self._context.enqueue_action(action)

    @property
    def current(self) -> int:
        return int(self._context.player.currentHealth)


class PlayerProxy:
    """Provide access to player centric attributes."""

    def __init__(self, context: "KeywordContext") -> None:
        self._context = context

    def _get_power(self, power_name: str) -> int:
        player = self._context.player
        power = player.getPower(power_name)
        if power is None:
            return 0
        return int(getattr(power, "amount", 0))

    def _set_power(self, power_name: str, amount: int) -> None:
        player = self._context.player
        current = self._get_power(power_name)
        delta = int(amount) - current
        if delta == 0:
            return
        powers = _cardcrawl().powers
        power_cls = getattr(powers, power_name)
        power = power_cls(player, delta)
        action = _cardcrawl().actions.common.ApplyPowerAction(player, player, power, delta)
        self._context.enqueue_action(action)

    @property
    def strength(self) -> int:
        return self._get_power("StrengthPower")

    @strength.setter
    def strength(self, value: int) -> None:
        self._set_power("StrengthPower", value)

    @property
    def dexterity(self) -> int:
        return self._get_power("DexterityPower")

    @dexterity.setter
    def dexterity(self, value: int) -> None:
        self._set_power("DexterityPower", value)

    @property
    def artifact(self) -> int:
        return self._get_power("ArtifactPower")

    @artifact.setter
    def artifact(self, value: int) -> None:
        self._set_power("ArtifactPower", value)


class EnemyProxy:
    """Expose enemy interactions."""

    def __init__(self, context: "KeywordContext") -> None:
        self._context = context

    @property
    def target(self) -> Any:
        if self._context.monster is not None:
            return self._context.monster
        return self.random

    @property
    def random(self) -> Any:
        dungeon = _cardcrawl().dungeons.AbstractDungeon
        current_room = getattr(dungeon, "getCurrRoom", lambda: None)()
        monsters = getattr(current_room, "monsters", None)
        if monsters is None:
            return None
        chooser = getattr(monsters, "getRandomMonster", None)
        if chooser:
            return chooser(True)
        group = getattr(monsters, "monsters", None)
        if group:
            return _RANDOM.choice(list(group))
        return None

    def all(self) -> Iterable[Any]:
        dungeon = _cardcrawl().dungeons.AbstractDungeon
        current_room = getattr(dungeon, "getCurrRoom", lambda: None)()
        monsters = getattr(current_room, "monsters", None)
        if monsters is None:
            return ()
        group = getattr(monsters, "monsters", None)
        if group is None:
            return ()
        return tuple(group)


@dataclass
class KeywordContext:
    keyword: "Keyword"
    player: Any
    monster: Optional[Any]
    card: Any
    amount: Optional[int]
    upgrade: Optional[int]

    def __post_init__(self) -> None:
        self.scheduler = _SCHEDULER
        self.hp_proxy = HPProxy(self)
        self.player_proxy = PlayerProxy(self)
        self.enemy_proxy = EnemyProxy(self)
        self.hand = CardZoneProxy(self.player, lambda: getattr(self.player, "hand", []))
        self.draw_pile = CardZoneProxy(self.player, lambda: getattr(self.player, "drawPile", []))
        self.discard_pile = CardZoneProxy(self.player, lambda: getattr(self.player, "discardPile", []))

    def enqueue_action(self, action: Any) -> None:
        def _runner() -> None:
            manager = _cardcrawl().dungeons.AbstractDungeon.actionManager
            manager.addToBottom(action)

        self.scheduler.enqueue_immediate(_runner)


class KeywordMeta(type):
    """Automatically register keyword subclasses on definition."""

    def __new__(mcls, name: str, bases: Tuple[type, ...], namespace: Dict[str, Any]):
        cls = super().__new__(mcls, name, bases, namespace)
        if namespace.get("_abstract", False):
            return cls
        if any(isinstance(base, KeywordMeta) for base in bases) or any(base is Keyword for base in bases):
            instance = cls()
            KEYWORD_REGISTRY.register(instance)
        return cls


class Keyword(metaclass=KeywordMeta):
    """Base class for all custom keywords."""

    _abstract = True

    def __init__(self, *, name: Optional[str] = None, description: str = "", proper_name: Optional[str] = None) -> None:
        self.name = name or self.__class__.__name__
        self.description = description
        self.proper_name = proper_name
        self.when: str = "now"
        self.keyword_id = _normalize_keyword(self.name)
        self._context: Optional[KeywordContext] = None

    @property
    def hp(self) -> HPProxy:
        if not self._context:
            raise KeywordError("Keyword context is not active.")
        return self._context.hp_proxy

    @hp.setter
    def hp(self, value: int) -> None:
        if not self._context:
            raise KeywordError("Keyword context is not active.")
        self._context.hp_proxy._set_temp_hp(int(value))

    @property
    def player(self) -> PlayerProxy:
        if not self._context:
            raise KeywordError("Keyword context is not active.")
        return self._context.player_proxy

    @property
    def enemies(self) -> EnemyProxy:
        if not self._context:
            raise KeywordError("Keyword context is not active.")
        return self._context.enemy_proxy

    @property
    def cards(self) -> KeywordContext:
        if not self._context:
            raise KeywordError("Keyword context is not active.")
        return self._context

    def apply(self, context: KeywordContext) -> None:  # pragma: no cover - to be overridden
        raise NotImplementedError

    def _bind_context(self, context: KeywordContext) -> None:
        self._context = context

    def _release_context(self) -> None:
        self._context = None

    def run(self, context: KeywordContext) -> None:
        self._bind_context(context)
        try:
            self.apply(context)
        finally:
            self._release_context()

    def register(
        self,
        *,
        names: Optional[Sequence[str]] = None,
        description: Optional[str] = None,
        mod_id: Optional[str] = None,
        color: Optional[Sequence[float]] = None,
    ) -> None:
        KEYWORD_REGISTRY.register(self, names=names, description=description, mod_id=mod_id, color=color)


class KeywordRegistry:
    """Keep track of available keyword implementations."""

    def __init__(self) -> None:
        self._keywords: Dict[str, _KeywordMetadata] = {}
        self._card_keywords: "weakref.WeakKeyDictionary[Any, List[Tuple[Keyword, Dict[str, Any]]]]" = weakref.WeakKeyDictionary()

    def register(
        self,
        keyword: Keyword,
        *,
        names: Optional[Sequence[str]] = None,
        description: Optional[str] = None,
        mod_id: Optional[str] = None,
        color: Optional[Sequence[float]] = None,
    ) -> None:
        aliases = list(names or (keyword.name,))
        normalized = {keyword.keyword_id}
        for alias in aliases:
            normalized.add(_normalize_keyword(alias))
        metadata = _KeywordMetadata(
            keyword=keyword,
            names=tuple(aliases),
            description=description or keyword.description,
            color=color,
            mod_id=mod_id,
        )
        for key in normalized:
            self._keywords[key] = metadata
        metadata.register_with_basemod()

    def resolve(self, name: str) -> Optional[_KeywordMetadata]:
        return self._keywords.get(_normalize_keyword(name))

    def attach_to_card(self, card: Any, keyword_name: str, *, amount: Optional[int], upgrade: Optional[int]) -> None:
        metadata = self.resolve(keyword_name)
        if metadata is None:
            raise KeywordError(f"Unknown keyword '{keyword_name}'.")
        bucket = self._card_keywords.setdefault(card, [])
        bucket.append((metadata.keyword, {"amount": amount, "upgrade": upgrade}))

    def trigger(self, card: Any, player: Any, monster: Optional[Any]) -> None:
        entries = self._card_keywords.get(card)
        if not entries:
            return
        for keyword, payload in entries:
            context = KeywordContext(
                keyword=keyword,
                player=player,
                monster=monster,
                card=card,
                amount=payload.get("amount"),
                upgrade=payload.get("upgrade"),
            )
            when = getattr(keyword, "when", "now").lower()
            if when == "now":
                _SCHEDULER.enqueue_immediate(lambda ctx=context, kw=keyword: kw.run(ctx))
            elif when == "next":
                _SCHEDULER.enqueue_start_of_turn(1, lambda ctx=context, kw=keyword: kw.run(ctx))
            elif when == "random":
                _SCHEDULER.enqueue_random_turn(end_of_turn=False, func=lambda ctx=context, kw=keyword: kw.run(ctx))
            elif when == "nextend":
                _SCHEDULER.enqueue_end_of_turn(1, lambda ctx=context, kw=keyword: kw.run(ctx))
            elif when == "randomend":
                _SCHEDULER.enqueue_random_turn(end_of_turn=True, func=lambda ctx=context, kw=keyword: kw.run(ctx))
            else:
                raise KeywordError(f"Unknown scheduling hint '{keyword.when}'.")
        _SCHEDULER.flush()


KEYWORD_REGISTRY = KeywordRegistry()


def apply_persistent_card_changes(player: Any) -> None:
    master_deck = getattr(player, "masterDeck", None)
    if master_deck is None:
        return
    cards = getattr(master_deck, "group", [])
    _CARD_PERSISTENCE.apply_to_deck(cards)


PLUGIN_MANAGER.expose("Keyword", Keyword)
PLUGIN_MANAGER.expose("KeywordRegistry", KeywordRegistry)
PLUGIN_MANAGER.expose("KEYWORD_REGISTRY", KEYWORD_REGISTRY)
PLUGIN_MANAGER.expose("keyword_scheduler", _SCHEDULER)
PLUGIN_MANAGER.expose("apply_persistent_card_changes", apply_persistent_card_changes)

__all__ = [
    "Keyword",
    "KeywordRegistry",
    "KeywordScheduler",
    "KEYWORD_REGISTRY",
    "keyword_scheduler",
    "apply_persistent_card_changes",
]

