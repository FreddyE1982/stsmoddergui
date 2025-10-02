"""Runtime registry and base class for custom Slay the Spire card types."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple, Type

from plugins import PLUGIN_MANAGER

from .loader import BaseModBootstrapError

__all__ = [
    "CardType",
    "CardTypeMeta",
    "CardTypeRecord",
    "CardTypeRegistry",
    "CARD_TYPE_REGISTRY",
]


def _wrapper_module():
    return import_module("modules.basemod_wrapper")


def _cardcrawl():
    try:
        return getattr(_wrapper_module(), "cardcrawl")
    except Exception:
        return None


_BASE_TYPES = {"ATTACK", "SKILL", "POWER"}


def _normalise(value: str) -> str:
    return value.replace(" ", "").replace("-", "").lower()


@dataclass(frozen=True)
class CardTypeRecord:
    """Metadata describing a registered :class:`CardType`."""

    identifier: str
    mod_id: str
    cls: Type["CardType"]
    instance: "CardType"
    display_name: str
    description: Optional[str]
    base_type: str
    aliases: Tuple[str, ...]

    def descriptor(self) -> str:
        """Return the descriptor string used on card banners."""

        return self.display_name

    def enum_value(self) -> Optional[object]:
        """Return the runtime enum value if available."""

        cardcrawl = _cardcrawl()
        if cardcrawl is None:
            return None
        try:
            enum_container = cardcrawl.cards.AbstractCard.CardType
        except Exception:
            return None
        try:
            return getattr(enum_container, self.identifier)
        except AttributeError:
            return None


class CardTypeRegistry:
    """Registry tracking custom card types defined by mods."""

    def __init__(self) -> None:
        self._records: Dict[str, CardTypeRecord] = {}
        self._by_mod: Dict[str, Dict[str, CardTypeRecord]] = {}
        self._aliases: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _notify_plugins(self, hook: str, record: CardTypeRecord) -> None:
        """Broadcast ``hook`` to plugins with the given ``record``."""

        PLUGIN_MANAGER.broadcast(hook, record=record, registry=self)

    @staticmethod
    def _canonical_identifier(identifier: str) -> str:
        if not identifier:
            raise BaseModBootstrapError("Card type identifiers must be non-empty strings.")
        cleaned = identifier.strip().upper()
        if not cleaned:
            raise BaseModBootstrapError("Card type identifiers must contain characters.")
        return cleaned

    def _register_aliases(self, identifier: str, record: CardTypeRecord) -> None:
        keys = {_normalise(identifier), _normalise(record.display_name)}
        for alias in record.aliases:
            keys.add(_normalise(str(alias)))
        for key in keys:
            existing = self._aliases.get(key)
            if existing and existing != identifier:
                raise BaseModBootstrapError(
                    f"Card type alias '{key}' already maps to '{existing}' and cannot point to '{identifier}'."
                )
            self._aliases[key] = identifier

    def register(self, cls: Type["CardType"], instance: "CardType") -> CardTypeRecord:
        identifier = self._canonical_identifier(getattr(instance, "identifier", ""))
        if identifier in self._records:
            existing = self._records[identifier]
            raise BaseModBootstrapError(
                f"Card type '{identifier}' already registered by "
                f"{existing.cls.__module__}.{existing.cls.__name__}."
            )
        mod_id = getattr(instance, "mod_id", "").strip()
        if not mod_id:
            raise BaseModBootstrapError(f"Card type '{identifier}' must declare a mod_id.")
        base_type = self._canonical_identifier(getattr(instance, "base_type", ""))
        if base_type not in _BASE_TYPES:
            raise BaseModBootstrapError(
                f"Card type '{identifier}' declares unsupported base_type '{base_type}'. Valid values: {sorted(_BASE_TYPES)}."
            )
        display_name = str(getattr(instance, "display_name", "") or identifier.replace("_", " ").title())
        description = getattr(instance, "description", None)
        aliases = tuple(str(alias) for alias in getattr(instance, "aliases", ()) if alias)
        record = CardTypeRecord(
            identifier=identifier,
            mod_id=mod_id,
            cls=cls,
            instance=instance,
            display_name=display_name,
            description=description,
            base_type=base_type,
            aliases=aliases,
        )
        self._records[identifier] = record
        self._by_mod.setdefault(mod_id, {})[identifier] = record
        self._register_aliases(identifier, record)
        self._ensure_stub_enum(identifier)
        setattr(instance, "_registry_record", record)
        self._notify_plugins("on_card_type_registered", record)
        return record

    def unregister(self, identifier: str) -> None:
        canonical = self._canonical_identifier(identifier)
        record = self._records.pop(canonical, None)
        if record is None:
            return
        mod_records = self._by_mod.get(record.mod_id)
        if mod_records and canonical in mod_records:
            del mod_records[canonical]
            if not mod_records:
                self._by_mod.pop(record.mod_id, None)
        for key, value in list(self._aliases.items()):
            if value == canonical:
                del self._aliases[key]
        self._remove_stub_enum(canonical)
        if record is not None:
            self._notify_plugins("on_card_type_unregistered", record)

    def record(self, identifier: str) -> Optional[CardTypeRecord]:
        if not identifier:
            return None
        return self._records.get(self._canonical_identifier(identifier))

    def resolve(self, value: object) -> Optional[CardTypeRecord]:
        if value is None:
            return None
        if isinstance(value, CardType):
            record = getattr(value, "_registry_record", None)
            if record is not None:
                return record
            return self.record(getattr(value, "identifier", ""))
        if isinstance(value, CardTypeRecord):
            return value
        text = str(value)
        canonical = self._canonical_identifier(text)
        if canonical in self._records:
            return self._records[canonical]
        alias = self._aliases.get(_normalise(text))
        if alias:
            return self._records.get(alias)
        return None

    def for_mod(self, mod_id: str) -> Tuple[CardTypeRecord, ...]:
        records = self._by_mod.get(str(mod_id), {})
        return tuple(records.values())

    def descriptor_for(self, identifier: str) -> Optional[str]:
        record = self.record(identifier)
        if record is None:
            return None
        return record.descriptor()

    def base_type_for(self, identifier: str) -> Optional[str]:
        record = self.record(identifier)
        if record is None:
            return None
        return record.base_type

    def install_on_project(self, project: object) -> None:
        mod_id = getattr(project, "mod_id", None)
        if not mod_id:
            return
        for record in self.for_mod(str(mod_id)):
            if hasattr(project, "register_card_type_record"):
                project.register_card_type_record(record)

    def items(self) -> Iterable[Tuple[str, CardTypeRecord]]:
        return tuple(self._records.items())

    def _ensure_stub_enum(self, identifier: str) -> None:
        cardcrawl = _cardcrawl()
        if cardcrawl is None:
            return
        try:
            container = cardcrawl.cards.AbstractCard.CardType
        except Exception:
            return
        if hasattr(container, identifier):
            return
        try:
            setattr(container, identifier, identifier)
        except Exception:
            pass

    def _remove_stub_enum(self, identifier: str) -> None:
        cardcrawl = _cardcrawl()
        if cardcrawl is None:
            return
        try:
            container = cardcrawl.cards.AbstractCard.CardType
        except Exception:
            return
        current = getattr(container, identifier, None)
        if isinstance(current, str) and current == identifier:
            try:
                delattr(container, identifier)
            except Exception:
                pass


CARD_TYPE_REGISTRY = CardTypeRegistry()


class CardTypeMeta(type):
    """Metaclass ensuring concrete card type subclasses auto-register."""

    def __new__(
        mcls,
        name: str,
        bases: Tuple[type, ...],
        namespace: Mapping[str, object],
    ):
        cls = super().__new__(mcls, name, bases, dict(namespace))
        if namespace.get("_abstract", False):
            return cls
        identifier = getattr(cls, "identifier", "")
        if not identifier:
            raise BaseModBootstrapError(f"CardType subclass '{cls.__name__}' must define an identifier.")
        mod_id = getattr(cls, "mod_id", "")
        if not mod_id:
            raise BaseModBootstrapError(f"CardType subclass '{cls.__name__}' must define a mod_id.")
        instance = cls.__new__(cls)  # type: ignore[misc]
        cls.__init__(instance)  # type: ignore[misc]
        record = CARD_TYPE_REGISTRY.register(cls, instance)
        setattr(cls, "_registry_record", record)
        return cls


class CardType(metaclass=CardTypeMeta):
    """Base class for declaring custom card types."""

    _abstract = True
    mod_id: str = ""
    identifier: str = ""
    display_name: Optional[str] = None
    description: Optional[str] = None
    base_type: str = "SKILL"
    aliases: Sequence[str] = ()

    def __init__(self) -> None:
        if type(self) is CardType:
            return
        if not self.identifier:
            raise BaseModBootstrapError("CardType subclasses must define an identifier.")
        if not self.mod_id:
            raise BaseModBootstrapError("CardType subclasses must define mod_id.")

    @property
    def registry_record(self) -> CardTypeRecord:
        record = getattr(self, "_registry_record", None)
        if record is None:
            raise BaseModBootstrapError(
                f"CardType '{self.identifier}' has not been registered correctly."
            )
        return record

    @property
    def enum_value(self) -> Optional[object]:
        return self.registry_record.enum_value()


PLUGIN_MANAGER.expose("CardType", CardType)
PLUGIN_MANAGER.expose("CardTypeRegistry", CardTypeRegistry)
PLUGIN_MANAGER.expose("CARD_TYPE_REGISTRY", CARD_TYPE_REGISTRY)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.card_types", alias="card_types")
