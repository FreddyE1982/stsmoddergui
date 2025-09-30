"""Extensible keyword infrastructure for the Slay the Spire wrapper.

The module exposes :class:`Keyword` which mod authors can subclass to implement
custom gameplay behaviour without touching the underlying JVM plumbing.  All
keywords register themselves automatically and can be combined with canonical
ones declared on :class:`modules.basemod_wrapper.cards.SimpleCardBlueprint`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from importlib import import_module
import json
import random
from pathlib import Path
import re
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple
import weakref


def _normalize_identifier(value: str) -> str:
    cleaned = value.strip()
    return "".join(ch for ch in cleaned.lower() if ch.isalnum())


def _camelize(value: str) -> str:
    parts = [part for part in re.split(r"[^0-9a-zA-Z]+", value) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts)


from plugins import PLUGIN_MANAGER


_RANDOM = random.Random()


@dataclass(frozen=True)
class RuntimeHandles:
    """Bundle live handles to the BaseMod runtime."""

    cardcrawl: Any
    basemod: Any
    spire: Any

    @classmethod
    def current(cls) -> "RuntimeHandles":
        """Return handles backed by the active runtime modules."""

        return cls(cardcrawl=_cardcrawl(), basemod=_basemod(), spire=_spire())


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

    def enqueue_random_turn(
        self,
        *,
        end_of_turn: bool,
        min_offset: int = 1,
        max_offset: int = 3,
        func: Callable[[], None],
    ) -> None:
        if min_offset > max_offset:
            min_offset, max_offset = max_offset, min_offset
        offset = _RANDOM.randint(max(1, min_offset), max(1, max_offset))
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
        if tasks:
            self.flush()

    def execute_end_of_turn(self) -> None:
        tasks = self._end_of_turn.pop(self._turn, [])
        for task in tasks:
            task()
        if tasks:
            self.flush()

    def debug_advance_turn(self) -> None:
        self.advance_turn()
        self.execute_end_of_turn()

    def apply_persistent_changes(self, runtime: Optional[RuntimeHandles] = None) -> None:
        runtime = runtime or RuntimeHandles.current()
        dungeon = getattr(runtime.cardcrawl.dungeons, "AbstractDungeon", None)
        player = getattr(dungeon, "player", None) if dungeon else None
        if player is not None:
            apply_persistent_card_changes(player)

    def receivePostDungeonInitialize(self, _dungeon: Any) -> None:  # pragma: no cover - requires JVM
        self.apply_persistent_changes()


_SCHEDULER = KeywordScheduler()
keyword_scheduler = _SCHEDULER


class CardPersistenceManager:
    """Persist card modifications across runs."""

    def __init__(self) -> None:
        self._default_path = Path(__file__).with_name("persistent_cards.json")
        self._path = self._default_path
        self._data: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    @property
    def path(self) -> Path:
        return self._path

    def configure_storage(self, path: Path) -> None:
        """Change the persistence target to ``path``.

        The method clears the in-memory cache so callers can point the manager at
        temporary directories during tests or mod previews without leaking
        changes into the default storage location.
        """

        self._path = Path(path)
        self._data = {}
        self._loaded = False

    def reset_storage(self) -> None:
        """Restore the default persistence location."""

        self.configure_storage(self._default_path)

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
        self._path.parent.mkdir(parents=True, exist_ok=True)
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
CARD_PERSISTENCE_MANAGER = _CARD_PERSISTENCE


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
        "secondary_value": "baseSecondMagicNumber",
        "image": "textureImg",
    }

    def __init__(self, card: Any) -> None:
        self._card = card

    @property
    def card(self) -> Any:
        return self._card

    def apply(self, **fields: Any) -> None:
        for key, value in fields.items():
            attr = self._SUPPORTED_FIELDS.get(key)
            if attr:
                setattr(self._card, attr, value)
                continue
            if hasattr(self._card, key):
                setattr(self._card, key, value)

    def snapshot(self, *fields: str) -> Dict[str, Any]:
        if not fields:
            fields = tuple(self._SUPPORTED_FIELDS)
        result: Dict[str, Any] = {}
        for field in fields:
            attr = self._SUPPORTED_FIELDS.get(field, field)
            if hasattr(self._card, attr):
                result[field] = getattr(self._card, attr)
        return result

    def __getattr__(self, item: str) -> Any:
        attr = self._SUPPORTED_FIELDS.get(item, item)
        if hasattr(self._card, attr):
            return getattr(self._card, attr)
        raise AttributeError(item)

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

    def __init__(self, context: "KeywordContext", accessor: Callable[[], Iterable[Any]], *, label: str) -> None:
        self._context = context
        self._accessor = accessor
        self._label = label

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

    def __getitem__(self, index: int) -> CardEditor:
        return self.get(index)

    def add_by_name(self, name: str) -> None:
        if self._label != "hand":
            raise KeywordError("Cards can only be added directly to the hand from keywords.")
        cardcrawl = self._context.runtime.cardcrawl
        library = cardcrawl.helpers.CardLibrary
        getter = getattr(library, "getCard", None)
        card = getter(name) if callable(getter) else None
        if card is None:
            card = self._locate_card_in_library(library, name)
        if card is None:
            card = self._locate_card_in_player_collections(name)
        if card is None:
            raise KeywordError(f"Unknown card '{name}'.")
        player = getattr(cardcrawl.dungeons.AbstractDungeon, "player", None)
        if player is None:
            raise KeywordError("Player is not available – cannot add card to hand.")
        action = cardcrawl.actions.common.MakeTempCardInHandAction(card.makeCopy(), 1)
        cardcrawl.dungeons.AbstractDungeon.actionManager.addToBottom(action)

    def _locate_card_in_library(self, library: Any, name: str) -> Optional[Any]:
        normalized = _normalize_identifier(name)
        containers = []
        for attr in ("cardsByID", "cards", "cardsByName"):
            candidate = getattr(library, attr, None)
            if candidate is not None:
                containers.append(candidate)
        for container in containers:
            if isinstance(container, dict):
                items = container.values()
            elif hasattr(container, "values"):
                items = container.values()
            elif hasattr(container, "items"):
                items = (value for _, value in container.items())
            else:
                items = []
            for card in items:
                match = self._match_card_identifier(card, normalized)
                if match is not None:
                    return match
        return None

    def _locate_card_in_player_collections(self, name: str) -> Optional[Any]:
        normalized = _normalize_identifier(name)
        player = self._context.player
        piles = []
        for attr in ("hand", "drawPile", "discardPile", "exhaustPile", "masterDeck"):
            pile = getattr(player, attr, None)
            if pile is None:
                continue
            group = getattr(pile, "group", None)
            if group is None:
                group = getattr(pile, "cards", None)
            if group is None:
                group = getattr(pile, "cardGroup", None)
            if group is None:
                group = pile
            piles.append(group)
        for pile in piles:
            try:
                iterator = list(pile)
            except TypeError:
                continue
            for card in iterator:
                match = self._match_card_identifier(card, normalized)
                if match is not None:
                    return card
        return None

    @staticmethod
    def _match_card_identifier(card: Any, normalized: str) -> Optional[Any]:
        for attr in ("cardID", "name", "card_id"):
            value = getattr(card, attr, None)
            if value and _normalize_identifier(str(value)) == normalized:
                return card
        return None


class ComparableInt:
    """Mixin that provides arithmetic and comparison helpers."""

    def _value(self) -> int:
        raise NotImplementedError

    def __int__(self) -> int:
        return self._value()

    def __float__(self) -> float:
        return float(self._value())

    def _coerce_other(self, other: Any) -> int:
        if isinstance(other, ComparableInt):
            return int(other)
        try:
            return int(other)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"Cannot interpret {other!r} as an integer") from exc

    def __add__(self, other: Any) -> int:
        return self._value() + self._coerce_other(other)

    def __radd__(self, other: Any) -> int:
        return self._coerce_other(other) + self._value()

    def __sub__(self, other: Any) -> int:
        return self._value() - self._coerce_other(other)

    def __rsub__(self, other: Any) -> int:
        return self._coerce_other(other) - self._value()

    def __eq__(self, other: Any) -> bool:  # type: ignore[override]
        try:
            other_value = self._coerce_other(other)
        except TypeError:
            return False
        return self._value() == other_value

    def __lt__(self, other: Any) -> bool:
        return self._value() < self._coerce_other(other)

    def __le__(self, other: Any) -> bool:
        return self._value() <= self._coerce_other(other)

    def __gt__(self, other: Any) -> bool:
        return self._value() > self._coerce_other(other)

    def __ge__(self, other: Any) -> bool:
        return self._value() >= self._coerce_other(other)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._value()})"


class HPProxy(ComparableInt):
    """Expose HP related operations for the active player."""

    def __init__(self, context: "KeywordContext") -> None:
        self._context = context

    @property
    def value(self) -> int:
        temp_field = self._context.runtime.spire.stslib.patches.tempHp.TempHPField.tempHp
        return int(temp_field.get(self._context.player))

    def _set_temp_hp(self, value: int) -> None:
        player = self._context.player
        current = self.value
        delta = int(value) - current
        if delta == 0:
            return
        if delta > 0:
            action_cls = self._context.runtime.spire.action("AddTemporaryHPAction")
            action = action_cls(player, player, delta)
        else:
            action_cls = self._context.runtime.spire.action("RemoveAllTemporaryHPAction")
            action = action_cls(player, player)
        self._context.enqueue_action(action)

    def _value(self) -> int:
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
        cardcrawl = self._context.runtime.cardcrawl
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
        object.__setattr__(self, "_context", context)
        object.__setattr__(self, "_powers", PowerProxy(self._context, self._context.player, owner_label="player"))

    @property
    def powers(self) -> "PowerProxy":
        return self._powers

    @property
    def strength(self) -> int:
        return self.powers.StrengthPower

    @strength.setter
    def strength(self, value: int) -> None:
        self.powers.StrengthPower = value

    @property
    def dexterity(self) -> int:
        return self.powers.DexterityPower

    @dexterity.setter
    def dexterity(self, value: int) -> None:
        self.powers.DexterityPower = value

    @property
    def artifact(self) -> int:
        return self.powers.ArtifactPower

    @artifact.setter
    def artifact(self, value: int) -> None:
        self.powers.ArtifactPower = value

    @property
    def focus(self) -> int:
        return self.powers.FocusPower

    @focus.setter
    def focus(self, value: int) -> None:
        self.powers.FocusPower = value

    @property
    def block(self) -> int:
        return int(getattr(self._context.player, "currentBlock", 0))

    @block.setter
    def block(self, value: int) -> None:
        player = self._context.player
        current = int(getattr(player, "currentBlock", 0))
        delta = int(value) - current
        if delta == 0:
            return
        cardcrawl = self._context.runtime.cardcrawl
        if delta > 0:
            action = cardcrawl.actions.common.GainBlockAction(player, player, delta)
        else:
            action = cardcrawl.actions.common.LoseBlockAction(player, player, abs(delta))
        self._context.enqueue_action(action)

    @property
    def energy(self) -> int:
        manager = getattr(self._context.player, "energy", None)
        if manager is None:
            return 0
        return int(getattr(manager, "energy", 0))

    @energy.setter
    def energy(self, value: int) -> None:
        manager = getattr(self._context.player, "energy", None)
        if manager is None:
            raise KeywordError("Player energy manager is unavailable.")
        manager.energy = int(value)

    def draw_cards(self, amount: int) -> None:
        action = self._context.runtime.cardcrawl.actions.common.DrawCardAction(self._context.player, int(amount))
        self._context.enqueue_action(action)

    def discard(self, amount: int) -> None:
        action_cls = self._context.runtime.cardcrawl.actions.common.DiscardAction
        action = action_cls(self._context.player, self._context.player, int(amount), False)
        self._context.enqueue_action(action)

    def __getattr__(self, item: str) -> int:
        if item.startswith("_"):
            raise AttributeError(item)
        return getattr(self._powers, item)

    def __setattr__(self, key: str, value: Any) -> None:
        if key in {"_context", "_powers"}:
            object.__setattr__(self, key, value)
            return
        if hasattr(type(self), key):
            object.__setattr__(self, key, value)
            return
        setattr(self._powers, key, value)


class EnemyProxy:
    """Expose enemy interactions."""

    def __init__(self, context: "KeywordContext") -> None:
        self._context = context

    def _wrap(self, monster: Optional[Any]) -> "MonsterHandle":
        if monster is None:
            raise KeywordError("No monster available for keyword interaction.")
        return MonsterHandle(self._context, monster)

    @property
    def target(self) -> "MonsterHandle":
        if self._context.monster is not None:
            return self._wrap(self._context.monster)
        return self.random

    @property
    def random(self) -> "MonsterHandle":
        dungeon = self._context.runtime.cardcrawl.dungeons.AbstractDungeon
        current_room = getattr(dungeon, "getCurrRoom", lambda: None)()
        monsters = getattr(current_room, "monsters", None)
        if monsters is None:
            raise KeywordError("No monsters available in the current room.")
        chooser = getattr(monsters, "getRandomMonster", None)
        if chooser:
            return self._wrap(chooser(True))
        group = getattr(monsters, "monsters", None)
        if group:
            return self._wrap(_RANDOM.choice(list(group)))
        raise KeywordError("No monsters available in the current room.")

    def all(self) -> Iterable["MonsterHandle"]:
        dungeon = self._context.runtime.cardcrawl.dungeons.AbstractDungeon
        current_room = getattr(dungeon, "getCurrRoom", lambda: None)()
        monsters = getattr(current_room, "monsters", None)
        if monsters is None:
            return ()
        group = getattr(monsters, "monsters", None)
        if group is None:
            return ()
        return tuple(self._wrap(monster) for monster in group)


@dataclass
class MonsterHandle(ComparableInt):
    context: "KeywordContext"
    monster: Any
    powers: "PowerProxy" = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "powers", PowerProxy(self.context, self.monster, owner_label="enemy"))

    def _value(self) -> int:
        return int(getattr(self.monster, "currentHealth", 0))

    @property
    def max(self) -> int:
        return int(getattr(self.monster, "maxHealth", 0))

    @property
    def hp(self) -> int:
        return self._value()

    @hp.setter
    def hp(self, value: int) -> None:
        current = self._value()
        delta = int(value) - current
        if delta == 0:
            return
        runtime = self.context.runtime.cardcrawl
        if delta > 0:
            action = runtime.actions.common.HealAction(self.monster, self.context.player, delta)
        else:
            action = runtime.actions.common.LoseHPAction(self.monster, self.context.player, abs(delta))
        self.context.enqueue_action(action)

    def __iadd__(self, other: int) -> "MonsterHandle":
        self.hp = self._value() + int(other)
        return self

    def __isub__(self, other: int) -> "MonsterHandle":
        self.hp = self._value() - int(other)
        return self

    @property
    def block(self) -> int:
        return int(getattr(self.monster, "currentBlock", 0))

    @block.setter
    def block(self, value: int) -> None:
        current = int(getattr(self.monster, "currentBlock", 0))
        delta = int(value) - current
        if delta == 0:
            return
        runtime = self.context.runtime.cardcrawl
        if delta > 0:
            action = runtime.actions.common.GainBlockAction(self.monster, self.context.player, delta)
        else:
            action = runtime.actions.common.LoseBlockAction(self.monster, self.context.player, abs(delta))
        self.context.enqueue_action(action)

    def __getattr__(self, item: str) -> Any:
        if item.startswith("_"):
            raise AttributeError(item)
        return getattr(self.powers, item)

    def __setattr__(self, key: str, value: Any) -> None:
        if key in {"context", "monster", "powers"}:
            object.__setattr__(self, key, value)
            return
        if hasattr(type(self), key):
            object.__setattr__(self, key, value)
            return
        setattr(self.powers, key, value)


@dataclass
class KeywordContext:
    keyword: "Keyword"
    player: Any
    monster: Optional[Any]
    card: Any
    amount: Optional[int]
    upgrade: Optional[int]
    runtime: Optional[RuntimeHandles] = None

    def __post_init__(self) -> None:
        self.runtime = self.runtime or RuntimeHandles.current()
        self.scheduler = _SCHEDULER
        self.hp_proxy = HPProxy(self)
        self.player_proxy = PlayerProxy(self)
        self.enemy_proxy = EnemyProxy(self)
        self.hand = CardZoneProxy(self, lambda: getattr(self.player, "hand", []), label="hand")
        self.draw_pile = CardZoneProxy(self, lambda: getattr(self.player, "drawPile", []), label="draw")
        self.discard_pile = CardZoneProxy(
            self, lambda: getattr(self.player, "discardPile", []), label="discard"
        )

    def enqueue_action(self, action: Any) -> None:
        def _runner() -> None:
            manager = self.runtime.cardcrawl.dungeons.AbstractDungeon.actionManager
            manager.addToBottom(action)

        self.scheduler.enqueue_immediate(_runner)

    def apply_power(self, owner: Any, power_name: str, amount: int, *, source: Optional[Any] = None) -> None:
        if amount == 0:
            return
        powers = self.runtime.cardcrawl.powers
        try:
            power_cls = getattr(powers, power_name)
        except AttributeError as exc:
            raise KeywordError(f"Unknown power '{power_name}'.") from exc
        source = source or self.player
        amount = int(amount)
        if amount == 0:
            return
        power = _instantiate_power(power_cls, owner, source, amount)
        action = self.runtime.cardcrawl.actions.common.ApplyPowerAction(owner, source, power, amount)
        self.enqueue_action(action)

    def remove_power(self, owner: Any, power_name: str) -> None:
        action_cls = self.runtime.cardcrawl.actions.common.RemoveSpecificPowerAction
        action = action_cls(owner, self.player, power_name)
        self.enqueue_action(action)


def _instantiate_power(power_cls: Any, owner: Any, source: Any, amount: int) -> Any:
    attempts: List[Tuple[Any, ...]] = [
        (owner, amount),
        (owner, amount, False),
        (owner, amount, True),
        (owner, source, amount),
        (owner, source, amount, False),
        (owner, source, amount, True),
        (owner,),
    ]
    for args in attempts:
        try:
            return power_cls(*args)
        except TypeError:
            continue
    tried = [len(args) for args in attempts]
    raise KeywordError(f"Could not instantiate power '{power_cls.__name__}'. Tried constructor arity {tried}.")


class PowerProxy:
    """Expose powers on creatures with pythonic accessors."""

    _PLAYER_ALIASES: Dict[str, str] = {
        "strength": "StrengthPower",
        "dexterity": "DexterityPower",
        "focus": "FocusPower",
        "artifact": "ArtifactPower",
        "intangible": "IntangiblePlayerPower",
        "buffer": "BufferPower",
        "metallicize": "MetallicizePower",
        "platedarmor": "PlatedArmorPower",
        "thorns": "ThornsPower",
        "vigor": "VigorPower",
        "combust": "CombustPower",
        "barricade": "BarricadePower",
        "flamebarrier": "FlameBarrierPower",
        "echoform": "EchoPower",
        "electrodynamics": "ElectrodynamicsPower",
        "creativeai": "CreativeAIPower",
        "staticdischarge": "StaticDischargePower",
        "blur": "BlurPower",
    }

    _ENEMY_ALIASES: Dict[str, str] = {
        "weak": "WeakPower",
        "vulnerable": "VulnerablePower",
        "frail": "FrailPower",
        "poison": "PoisonPower",
        "artifact": "ArtifactPower",
        "strength": "StrengthPower",
        "dexterity": "DexterityPower",
        "focus": "FocusPower",
        "intangible": "IntangiblePower",
        "constricted": "ConstrictedPower",
        "shackled": "ShackledPower",
        "lockon": "LockOnPower",
        "slow": "SlowPower",
        "thorns": "ThornsPower",
    }

    def __init__(self, context: KeywordContext, owner: Any, *, owner_label: str) -> None:
        self._context = context
        self._owner = owner
        self._owner_label = owner_label

    def _alias_mapping(self) -> Dict[str, str]:
        if self._owner_label == "player":
            return self._PLAYER_ALIASES
        return self._ENEMY_ALIASES

    def _resolve_name(self, name: str) -> str:
        if name.endswith("Power"):
            return name
        normalized = _normalize_identifier(name)
        aliases = self._alias_mapping()
        if normalized in aliases:
            return aliases[normalized]
        if normalized.endswith("power"):
            base_key = normalized[:-5]
            if base_key in aliases:
                return aliases[base_key]
            camel_base = _camelize(base_key)
            if camel_base:
                return f"{camel_base}Power"
        camel = _camelize(name)
        if camel:
            if camel.endswith("Power"):
                return camel
            return f"{camel}Power"
        return name

    def __getattr__(self, item: str) -> int:
        power_name = self._resolve_name(item)
        owner = self._owner
        power = getattr(owner, "getPower", lambda _: None)(power_name)
        if power is None:
            return 0
        return int(getattr(power, "amount", 0))

    def __setattr__(self, key: str, value: int) -> None:
        if key.startswith("_"):
            object.__setattr__(self, key, value)
            return
        power_name = self._resolve_name(key)
        amount = int(value)
        owner = self._owner
        current_power = getattr(owner, "getPower", lambda _: None)(power_name)
        current_amount = int(getattr(current_power, "amount", 0)) if current_power is not None else 0
        if amount <= 0:
            self._context.remove_power(self._owner, power_name)
            return
        delta = amount - current_amount
        if delta == 0:
            return
        source = self._context.player if self._owner_label == "enemy" else owner
        self._context.apply_power(owner, power_name, delta, source=source)

    def __dir__(self) -> Iterator[str]:  # pragma: no cover - trivial helper
        base = set(super().__dir__())  # type: ignore[arg-type]
        base.update(self._alias_mapping().keys())
        return sorted(base)


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
        self.turn_offset: int = 1
        self.random_turn_range: Tuple[int, int] = (1, 3)
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

    def trigger(
        self,
        card: Any,
        player: Any,
        monster: Optional[Any],
        *,
        runtime: Optional[RuntimeHandles] = None,
    ) -> None:
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
                runtime=runtime,
            )
            when = getattr(keyword, "when", "now").lower()
            offset = max(1, int(getattr(keyword, "turn_offset", 1) or 1))
            random_range = getattr(keyword, "random_turn_range", (1, 3))
            if isinstance(random_range, int):
                random_min, random_max = 1, int(random_range)
            else:
                try:
                    random_min, random_max = random_range
                except (TypeError, ValueError):
                    random_min, random_max = 1, 3
            if when == "now":
                _SCHEDULER.enqueue_immediate(lambda ctx=context, kw=keyword: kw.run(ctx))
            elif when == "next":
                _SCHEDULER.enqueue_start_of_turn(offset, lambda ctx=context, kw=keyword: kw.run(ctx))
            elif when == "random":
                _SCHEDULER.enqueue_random_turn(
                    end_of_turn=False,
                    min_offset=random_min,
                    max_offset=random_max,
                    func=lambda ctx=context, kw=keyword: kw.run(ctx),
                )
            elif when == "nextend":
                _SCHEDULER.enqueue_end_of_turn(offset, lambda ctx=context, kw=keyword: kw.run(ctx))
            elif when == "randomend":
                _SCHEDULER.enqueue_random_turn(
                    end_of_turn=True,
                    min_offset=random_min,
                    max_offset=random_max,
                    func=lambda ctx=context, kw=keyword: kw.run(ctx),
                )
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
PLUGIN_MANAGER.expose("KeywordContext", KeywordContext)
PLUGIN_MANAGER.expose("RuntimeHandles", RuntimeHandles)
PLUGIN_MANAGER.expose("CardEditor", CardEditor)
PLUGIN_MANAGER.expose("CardZoneProxy", CardZoneProxy)
PLUGIN_MANAGER.expose("CardPersistenceManager", CardPersistenceManager)
PLUGIN_MANAGER.expose("CARD_PERSISTENCE_MANAGER", _CARD_PERSISTENCE)
PLUGIN_MANAGER.expose("HPProxy", HPProxy)
PLUGIN_MANAGER.expose("PlayerProxy", PlayerProxy)
PLUGIN_MANAGER.expose("EnemyProxy", EnemyProxy)
PLUGIN_MANAGER.expose("MonsterHandle", MonsterHandle)
PLUGIN_MANAGER.expose("PowerProxy", PowerProxy)

__all__ = [
    "Keyword",
    "KeywordRegistry",
    "KeywordScheduler",
    "KeywordContext",
    "RuntimeHandles",
    "CardEditor",
    "CardZoneProxy",
    "CardPersistenceManager",
    "CARD_PERSISTENCE_MANAGER",
    "HPProxy",
    "PlayerProxy",
    "EnemyProxy",
    "MonsterHandle",
    "PowerProxy",
    "KEYWORD_REGISTRY",
    "keyword_scheduler",
    "apply_persistent_card_changes",
]

