"""Relic base classes and registration helpers."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from typing import Callable, Dict, Iterable, Iterator, Mapping, Optional, Tuple, Type

from .loader import BaseModBootstrapError
from plugins import PLUGIN_MANAGER


def _wrapper_module():
    return import_module("modules.basemod_wrapper")


def _cardcrawl():
    try:
        return getattr(_wrapper_module(), "cardcrawl")
    except Exception:
        return None


def _basemod():
    try:
        return getattr(_wrapper_module(), "basemod")
    except Exception:
        return None


@lru_cache(maxsize=1)
def _custom_relic_base():
    basemod = _basemod()
    if basemod is not None:
        try:
            return basemod.abstracts.CustomRelic
        except Exception:
            pass

    class _FallbackCustomRelic:
        def __init__(self, relic_id: str, image_path: str, tier: object, landing_sound: object) -> None:
            self.relicId = relic_id
            self.imgUrl = image_path
            self.tier = tier
            self.landing_sound = landing_sound
            self.counter = 0
            self.grayscale = False
            self.name = relic_id
            self.description = ""
            self.flavorText = ""

        def makeCopy(self):  # pragma: no cover - trivial fallback behaviour
            return self.__class__()

    return _FallbackCustomRelic


@dataclass(frozen=True)
class RelicRecord:
    identifier: str
    mod_id: str
    cls: Type["Relic"]
    instance: "Relic"
    pool: str
    color_id: Optional[str]
    image: str

    def spawn_instance(self) -> "Relic":
        relic = self.cls.__new__(self.cls)
        self.cls.__init__(relic)
        return relic


class RelicRegistry:
    """Registry tracking relic subclasses and their prototypes."""

    def __init__(self) -> None:
        self._records: Dict[str, RelicRecord] = {}
        self._by_mod: Dict[str, Dict[str, RelicRecord]] = {}

    def register(self, cls: Type["Relic"], instance: "Relic") -> RelicRecord:
        identifier = instance.identifier
        if identifier in self._records:
            existing = self._records[identifier]
            raise BaseModBootstrapError(
                f"Relic '{identifier}' already registered by {existing.cls.__module__}.{existing.cls.__name__}."
            )
        record = RelicRecord(
            identifier=identifier,
            mod_id=instance.mod_id,
            cls=cls,
            instance=instance,
            pool=cls.relic_pool,
            color_id=cls.color_id,
            image=instance.image_path,
        )
        self._records[identifier] = record
        self._by_mod.setdefault(instance.mod_id, {})[identifier] = record
        return record

    def unregister(self, identifier: str) -> None:
        record = self._records.pop(identifier, None)
        if record is None:
            return
        mod_records = self._by_mod.get(record.mod_id)
        if mod_records and identifier in mod_records:
            del mod_records[identifier]
            if not mod_records:
                self._by_mod.pop(record.mod_id, None)

    def record(self, identifier: str) -> Optional[RelicRecord]:
        return self._records.get(identifier)

    def for_mod(self, mod_id: str) -> Tuple[RelicRecord, ...]:
        records = self._by_mod.get(mod_id, {})
        return tuple(records.values())

    def install_on_project(self, project: object) -> None:
        mod_id = getattr(project, "mod_id", None)
        if not mod_id:
            return
        for record in self.for_mod(str(mod_id)):
            if hasattr(project, "register_relic_record"):
                project.register_relic_record(record)

    def items(self) -> Iterable[Tuple[str, RelicRecord]]:  # pragma: no cover - trivial helper
        return self._records.items()


RELIC_REGISTRY = RelicRegistry()


def _resolve_enum(container: object, name: str, label: str) -> object:
    if container is None:
        return name
    if hasattr(container, "valueOf"):
        try:
            return container.valueOf(name)
        except Exception as exc:
            raise BaseModBootstrapError(f"Unknown {label} '{name}'.") from exc
    try:
        return getattr(container, name)
    except AttributeError as exc:
        raise BaseModBootstrapError(f"Unknown {label} '{name}'.") from exc


class RelicMeta(type):
    def __new__(mcls, name: str, bases: Tuple[type, ...], namespace: Mapping[str, object]):
        cls = super().__new__(mcls, name, bases, dict(namespace))
        if getattr(cls, "_abstract", False):
            return cls
        if not getattr(cls, "identifier", None):
            raise BaseModBootstrapError(f"Relic subclass '{cls.__name__}' must define an identifier.")
        if not getattr(cls, "mod_id", None):
            raise BaseModBootstrapError(f"Relic subclass '{cls.__name__}' must define mod_id.")
        instance = cls()
        RELIC_REGISTRY.register(cls, instance)
        return cls


class Relic(_custom_relic_base(), metaclass=RelicMeta):  # type: ignore[misc]
    _abstract = True
    mod_id: str = ""
    identifier: str = ""
    relic_pool: str = "SHARED"
    color_id: Optional[str] = None
    tier: str = "COMMON"
    landing_sound: str = "FLAT"
    display_name: Optional[str] = None
    description_text: str = ""
    flavor_text: str = ""
    image: Optional[str] = None

    def __init__(self) -> None:
        if type(self) is Relic:
            return
        if not self.identifier:
            raise BaseModBootstrapError("Relic subclasses must define an identifier.")
        tier_enum = _resolve_enum(
            getattr(getattr(getattr(_cardcrawl(), "relics", None), "AbstractRelic", None), "RelicTier", None),
            self.tier,
            "relic tier",
        )
        landing_enum = _resolve_enum(
            getattr(getattr(getattr(_cardcrawl(), "relics", None), "AbstractRelic", None), "LandingSound", None),
            self.landing_sound,
            "relic landing sound",
        )
        image_path = self.image or self.default_image_path()
        super().__init__(self.identifier, image_path, tier_enum, landing_enum)
        self.mod_id = self.mod_id
        self.image_path = image_path
        if self.display_name:
            self.name = self.display_name
        if self.description_text:
            self.description = self.description_text
        if self.flavor_text:
            self.flavorText = self.flavor_text

    def default_image_path(self) -> str:
        local_id = self.identifier.split(":")[-1]
        return f"{self.mod_id}/images/relics/{local_id}.png"

    def spawn_copy(self) -> "Relic":
        return type(self)()

    def on_combat_begin(self, mod: object, recorder: object) -> None:
        return None

    def on_plan_finalised(self, mod: object, plan: object) -> None:
        return None


Relic._abstract = False  # type: ignore[attr-defined]

PLUGIN_MANAGER.expose("Relic", Relic)
PLUGIN_MANAGER.expose("RelicRegistry", RELIC_REGISTRY)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.relics", alias="basemod_relics")
