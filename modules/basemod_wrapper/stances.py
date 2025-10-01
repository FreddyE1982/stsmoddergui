"""GraalPy-backed base class and registry for custom Slay the Spire stances.

The repository historically provided high level helpers for cards, relics and
characters.  Custom stances remained a manual exercise even though the
experimental GraalPy runtime makes implementing Java subclasses from Python
straightforward.  This module introduces a :class:`Stance` base class that
piggybacks on the GraalPy backend to inherit from
``com.megacrit.cardcrawl.stances.AbstractStance`` and wires new instances into
the game registries automatically.

Subclasses only need to define identifiers, localisation metadata and optional
visual hooks.  Instantiating the class ensures the GraalPy runtime is active,
builds libGDX colour handles, and registers the prototype with all stance
lookups.  The global registry exposes plugin friendly state and integrates with
``modules.basemod_wrapper.project.ModProject`` so bundled mods do not have to
manually call BaseMod or touch ``AbstractStance`` internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple, Type

from plugins import PLUGIN_MANAGER

from .experimental import is_active as experimental_is_active, on as experimental_on
from .java_backend import active_backend
from .loader import BaseModBootstrapError

ColorTuple = Tuple[float, float, float, float]

__all__ = [
    "Stance",
    "STANCE_REGISTRY",
    "StanceRecord",
    "StanceRegistry",
    "register_stance_runtime",
]


def _wrapper_module():
    return import_module("modules.basemod_wrapper")


def _basemod():
    try:
        return getattr(_wrapper_module(), "basemod")
    except Exception:
        return None


def _cardcrawl():
    try:
        return getattr(_wrapper_module(), "cardcrawl")
    except Exception:
        return None


def _libgdx():
    try:
        return getattr(_wrapper_module(), "libgdx")
    except Exception:
        return None


@lru_cache(maxsize=1)
def _java_module():
    try:
        import java  # type: ignore

        return java
    except ImportError as exc:  # pragma: no cover - depends on GraalPy runtime
        raise BaseModBootstrapError(
            "GraalPy java module is unavailable. Ensure the runtime was launched via the graalpy executable."
        ) from exc


def _ensure_graalpy_backend() -> None:
    """Activate the GraalPy runtime if necessary and validate the backend."""

    if not experimental_is_active("graalpy_runtime"):
        experimental_on("graalpy_runtime")
    backend = active_backend()
    if backend.name != "graalpy":
        raise BaseModBootstrapError(
            "Custom stances require the GraalPy backend. Launch the runtime via graalpy or enable the experimental module."
        )


def _coerce_color(value: Optional[ColorTuple]) -> Optional[object]:
    if value is None:
        return None
    libgdx = _libgdx()
    if libgdx is None:
        return value
    try:
        return libgdx.graphics.Color(*value)
    except Exception as exc:  # pragma: no cover - requires libGDX classes
        raise BaseModBootstrapError(
            "libGDX colour initialisation failed. Ensure the Slay the Spire jars are on the classpath before registering stances."
        ) from exc


def _load_texture(path: Optional[str]) -> Optional[object]:
    if not path:
        return None
    libgdx = _libgdx()
    if libgdx is None:
        return Path(path)
    try:
        return libgdx.graphics.Texture(path)
    except Exception as exc:  # pragma: no cover - requires libGDX classes
        raise BaseModBootstrapError(
            f"Failed to load stance texture '{path}'. Ensure the asset exists and the JVM runtime is active."
        ) from exc


def _maybe_put(mapping: object, key: str, value: object) -> None:
    if mapping is None:
        return
    put = getattr(mapping, "put", None)
    if callable(put):
        put(key, value)
        return
    if isinstance(mapping, dict):
        mapping[key] = value


@lru_cache(maxsize=1)
def _abstract_stance_base():
    _ensure_graalpy_backend()
    java = _java_module()
    try:
        return java.type("com.megacrit.cardcrawl.stances.AbstractStance")
    except Exception as exc:  # pragma: no cover - depends on GraalPy runtime
        raise BaseModBootstrapError(
            "Unable to resolve com.megacrit.cardcrawl.stances.AbstractStance via GraalPy."
        ) from exc


@lru_cache(maxsize=1)
def _stance_helper():
    java = _java_module()
    try:
        return java.type("com.megacrit.cardcrawl.helpers.StanceHelper")
    except Exception:  # pragma: no cover - optional helper in some builds
        return None


@lru_cache(maxsize=1)
def _stance_aura_effect():
    java = _java_module()
    try:
        return java.type("com.megacrit.cardcrawl.vfx.stance.StanceAuraEffect")
    except Exception:  # pragma: no cover - optional helper in some builds
        return None


@lru_cache(maxsize=1)
def _stance_particle_effect():
    java = _java_module()
    try:
        return java.type("com.megacrit.cardcrawl.vfx.stance.StanceParticleEffect")
    except Exception:  # pragma: no cover - optional helper in some builds
        return None


def _create_supplier(method):
    backend = active_backend()
    return backend.create_proxy("java.util.function.Supplier", {"get": method})


@dataclass(frozen=True)
class StanceRecord:
    identifier: str
    mod_id: str
    cls: Type["Stance"]
    instance: "Stance"
    display_name: str
    description: str
    primary_color: Optional[ColorTuple]
    aura_color: Optional[ColorTuple]
    particle_color: Optional[ColorTuple]
    aura_texture: Optional[str]
    particle_texture: Optional[str]

    def spawn_instance(self) -> "Stance":
        stance = self.cls.__new__(self.cls)
        self.cls.__init__(stance)
        return stance


class StanceRegistry:
    """Track registered stances and expose plugin friendly lookups."""

    def __init__(self) -> None:
        self._records: Dict[str, StanceRecord] = {}
        self._by_mod: Dict[str, Dict[str, StanceRecord]] = {}

    def register(self, cls: Type["Stance"], instance: "Stance") -> StanceRecord:
        identifier = instance.identifier
        if identifier in self._records:
            existing = self._records[identifier]
            raise BaseModBootstrapError(
                f"Stance '{identifier}' already registered by {existing.cls.__module__}.{existing.cls.__name__}."
            )
        record = StanceRecord(
            identifier=identifier,
            mod_id=instance.mod_id,
            cls=cls,
            instance=instance,
            display_name=instance.display_name or identifier,
            description=instance.description_text,
            primary_color=cls.primary_color,
            aura_color=cls.aura_color,
            particle_color=cls.particle_color,
            aura_texture=cls.aura_texture,
            particle_texture=cls.particle_texture,
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

    def record(self, identifier: str) -> Optional[StanceRecord]:
        return self._records.get(identifier)

    def for_mod(self, mod_id: str) -> Tuple[StanceRecord, ...]:
        return tuple(self._by_mod.get(mod_id, {}).values())

    def install_on_project(self, project: object) -> None:
        mod_id = getattr(project, "mod_id", None)
        if not mod_id:
            return
        for record in self.for_mod(str(mod_id)):
            if hasattr(project, "register_stance_record"):
                project.register_stance_record(record)

    def items(self) -> Iterable[Tuple[str, StanceRecord]]:  # pragma: no cover - helper
        return self._records.items()


STANCE_REGISTRY = StanceRegistry()


def register_stance_runtime(record: StanceRecord) -> None:
    _ensure_graalpy_backend()
    basemod = _basemod()
    stance = record.instance
    stance_id = record.identifier

    aura_texture = _load_texture(record.aura_texture)
    particle_texture = _load_texture(record.particle_texture)

    basemod_module = getattr(basemod, "BaseMod", None) if basemod is not None else None
    supplier = _create_supplier(lambda: record.cls())
    aura_supplier = _create_supplier(lambda: aura_texture) if aura_texture is not None else None
    particle_supplier = _create_supplier(lambda: particle_texture) if particle_texture is not None else None

    registered = False
    if basemod_module is not None:
        add_custom = getattr(basemod_module, "addCustomStance", None)
        if callable(add_custom):
            if aura_supplier is not None and particle_supplier is not None:
                add_custom(stance_id, supplier, aura_supplier, particle_supplier)
            else:
                add_custom(stance_id, supplier)
            registered = True

    abstract_stance = _abstract_stance_base()
    stances_map = getattr(abstract_stance, "stances", None)
    helper = _stance_helper()
    aura_effect = _stance_aura_effect()
    particle_effect = _stance_particle_effect()

    _maybe_put(stances_map, stance_id, stance)
    if helper is not None:
        helper_map = getattr(helper, "stanceMap", None) or getattr(helper, "STANCES", None)
        if helper_map is not None:
            _maybe_put(helper_map, stance_id, supplier)
        name_map = getattr(helper, "nameMap", None) or getattr(helper, "STANCE_NAMES", None)
        if name_map is not None:
            _maybe_put(name_map, stance.display_name or stance_id, stance_id)

    aura_color = _coerce_color(record.aura_color) or _coerce_color(record.primary_color)
    particle_color = _coerce_color(record.particle_color) or aura_color
    if aura_effect is not None:
        _maybe_put(getattr(aura_effect, "STANCE_COLORS", None), stance_id, aura_color)
        _maybe_put(getattr(aura_effect, "PARTICLE_COLORS", None), stance_id, particle_color)
        if aura_texture is not None:
            _maybe_put(getattr(aura_effect, "PARTICLE_TEXTURES", None), stance_id, particle_texture)
    if particle_effect is not None:
        _maybe_put(getattr(particle_effect, "PARTICLE_COLORS", None), stance_id, particle_color)

    if not registered and basemod_module is not None:
        # BaseMod interface missing – expose minimal supplier so mods can still instantiate.
        PLUGIN_MANAGER.broadcast(
            "log_warning",
            "stance-registration",
            f"BaseMod.addCustomStance unavailable; registered '{stance_id}' via runtime maps only.",
        )


class StanceMeta(type):
    def __new__(mcls, name: str, bases: Tuple[type, ...], namespace: Mapping[str, object]):
        abstract = namespace.get("_abstract", False)
        resolved_bases = bases
        if not abstract:
            java_base = _abstract_stance_base()
            if java_base not in bases:
                resolved_bases = (java_base, *bases)
        cls = super().__new__(mcls, name, resolved_bases, dict(namespace))
        if abstract:
            return cls
        if not getattr(cls, "identifier", None):
            raise BaseModBootstrapError(f"Stance subclass '{cls.__name__}' must define an identifier.")
        if not getattr(cls, "mod_id", None):
            raise BaseModBootstrapError(f"Stance subclass '{cls.__name__}' must define mod_id.")
        instance = cls()
        record = STANCE_REGISTRY.register(cls, instance)
        register_stance_runtime(record)
        return cls


class Stance(metaclass=StanceMeta):
    """Base class for GraalPy powered custom stances."""

    _abstract = True
    mod_id: str = ""
    identifier: str = ""
    display_name: Optional[str] = None
    description_text: str = ""
    primary_color: Optional[ColorTuple] = None
    aura_color: Optional[ColorTuple] = None
    particle_color: Optional[ColorTuple] = None
    aura_texture: Optional[str] = None
    particle_texture: Optional[str] = None

    def __init__(self) -> None:
        if type(self) is Stance:
            return
        _ensure_graalpy_backend()
        super().__init__()  # type: ignore[misc]
        self.ID = self.identifier
        self.mod_id = self.mod_id
        self.display_name = self.display_name or self._derive_display_name()
        self.name = self.display_name
        self.description = self.description_text
        primary = _coerce_color(self.primary_color)
        if primary is not None:
            self.c = primary
        aura = _coerce_color(self.aura_color) or primary
        particle = _coerce_color(self.particle_color) or aura or primary
        if aura is not None:
            setattr(self, "auraColor", aura)
        if particle is not None:
            setattr(self, "particleColor", particle)

    def _derive_display_name(self) -> str:
        local_id = self.identifier.split(":")[-1]
        return local_id.replace("_", " ").title()

    def register_localization(self, description: str) -> None:
        self.description_text = description


Stance._abstract = False  # type: ignore[attr-defined]

PLUGIN_MANAGER.expose("Stance", Stance)
PLUGIN_MANAGER.expose("StanceRegistry", STANCE_REGISTRY)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.stances", alias="basemod_stances")

