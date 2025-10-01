"""GraalPy-powered rule weaving engine for dynamic game mechanics.

The :mod:`experimental.graalpy_rule_weaver` module introduces an orchestration
layer that allows mods and tooling to rewrite gameplay rules at runtime.
Activating the module ensures :mod:`experimental.graalpy_runtime` is enabled so
every rule script executes inside the GraalPy VM alongside the Slay the Spire
runtime.  Callers can register bespoke mechanic mutations via
:class:`RuleWeaverEngine`, load declarative rule scripts from JSON/YAML files
and expose their helpers to the global plugin surface.

Key concepts
============

``RuleWeaverEngine``
    Central registry that manages mechanic mutations.  It keeps track of card
    blueprints, keyword registries and plugin broadcasts so rules can be
    applied and reverted safely.  Mutations can be registered programmatically
    or loaded from :class:`RuleWeaverScript` definitions.

``MechanicMutation``
    Metadata wrapper around the callable that mutates gameplay state.  The
    mutation records revert callbacks so deactivating the experiment restores
    the original mechanics without lingering side effects.

``RuleWeaverContext``
    Runtime context handed to mutations.  It exposes accessors for BaseMod,
    CardCrawl, StSLib and helper methods that adjust card blueprints, register
    keywords or execute GraalPy rule snippets.

The engine adheres to the repository-wide plugin requirements by exposing its
state, registration helpers and script loaders through
``plugins.PLUGIN_MANAGER``.  Tooling can introspect registered mutations, watch
activation events and publish additional rule packs without touching internal
module state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from importlib import import_module
from pathlib import Path
import threading
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from plugins import PLUGIN_MANAGER

from . import is_active as experimental_is_active
from . import on as experimental_on

from modules.basemod_wrapper import basemod, cardcrawl, spire, stslib
from modules.basemod_wrapper.cards import SimpleCardBlueprint, KEYWORD_PLACEHOLDERS
from modules.basemod_wrapper.keywords import KEYWORD_REGISTRY, Keyword, KeywordRegistry


__all__ = [
    "MechanicActivation",
    "MechanicMutation",
    "RuleWeaverContext",
    "RuleWeaverEngine",
    "RuleWeaverScript",
    "activate",
    "deactivate",
    "get_engine",
    "load_script",
]


def _canonical_keyword(value: str) -> str:
    cleaned = str(value or "").strip()
    if ":" in cleaned:
        cleaned = cleaned.split(":", 1)[1]
    return cleaned.replace("_", "").replace("-", "").replace(" ", "").lower()


def _compute_placeholders(keywords: Sequence[str]) -> Dict[str, str]:
    placeholders: Dict[str, str] = {}
    for keyword in keywords:
        token = KEYWORD_PLACEHOLDERS.get(keyword)
        if token:
            placeholders[keyword] = token
    if "exhaustive" in keywords:
        placeholders.setdefault("uses", KEYWORD_PLACEHOLDERS.get("exhaustive", "!stslib:ex!"))
    return placeholders


def _normalise_tags(tags: Iterable[str]) -> Tuple[str, ...]:
    normalised = []
    seen = set()
    for tag in tags:
        cleaned = str(tag).strip()
        if not cleaned:
            continue
        lower = cleaned.lower()
        if lower in seen:
            continue
        seen.add(lower)
        normalised.append(lower)
    return tuple(normalised)


@dataclass(slots=True)
class MechanicActivation:
    """Represents an applied mechanic mutation."""

    identifier: str
    revert_callbacks: Tuple[Callable[["RuleWeaverContext"], None], ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def revert(self, context: "RuleWeaverContext") -> None:
        for callback in reversed(self.revert_callbacks):
            callback(context)


@dataclass(slots=True)
class MechanicMutation:
    """Metadata container describing a rule weaving mutation."""

    identifier: str
    description: str
    apply: Callable[["RuleWeaverContext"], Optional[MechanicActivation]]
    priority: int = 100
    tags: Tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.identifier or not str(self.identifier).strip():
            raise ValueError("MechanicMutation.identifier must be a non-empty string.")
        self.identifier = str(self.identifier).strip()
        self.description = str(self.description or "").strip()
        if not callable(self.apply):
            raise TypeError("MechanicMutation.apply must be callable.")
        try:
            self.priority = int(self.priority)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError("MechanicMutation.priority must be an integer.") from exc
        self.tags = _normalise_tags(self.tags)
        if not isinstance(self.metadata, Mapping):
            raise TypeError("MechanicMutation.metadata must be a mapping.")
        self.metadata = MappingProxyType(dict(self.metadata))


class RuleWeaverContext:
    """Execution environment handed to mechanic mutations."""

    def __init__(
        self,
        *,
        engine: "RuleWeaverEngine",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.engine = engine
        self.metadata = MappingProxyType(dict(metadata or {}))
        self.basemod = basemod
        self.cardcrawl = cardcrawl
        self.spire = spire
        self.stslib = stslib
        self.keyword_registry: KeywordRegistry = KEYWORD_REGISTRY
        self._blueprints = self._collect_blueprints()

    # ------------------------------------------------------------------
    def _collect_blueprints(self) -> Mapping[str, SimpleCardBlueprint]:
        blueprints: Dict[str, SimpleCardBlueprint] = {}
        for provider in self.engine.blueprint_providers:
            try:
                iterable = provider()
            except Exception as exc:
                raise RuntimeError(f"Blueprint provider {provider!r} raised an exception.") from exc
            for blueprint in iterable:
                if not isinstance(blueprint, SimpleCardBlueprint):
                    continue
                blueprints.setdefault(blueprint.identifier, blueprint)
        return MappingProxyType(blueprints)

    def blueprint(self, identifier: str) -> SimpleCardBlueprint:
        try:
            return self._blueprints[identifier]
        except KeyError as exc:
            raise KeyError(f"Unknown card blueprint '{identifier}'.") from exc

    # ------------------------------------------------------------------
    def adjust_card_values(
        self,
        identifier: str,
        *,
        value: Optional[int] = None,
        upgrade_value: Optional[int] = None,
        cost: Optional[int] = None,
        secondary_value: Optional[int] = None,
        secondary_upgrade: Optional[int] = None,
    ) -> Callable[["RuleWeaverContext"], None]:
        blueprint = self.blueprint(identifier)
        previous: Dict[str, Any] = {}

        def _assign(field: str, new_value: Optional[int]) -> None:
            if new_value is None:
                return
            previous.setdefault(field, getattr(blueprint, field))
            object.__setattr__(blueprint, field, int(new_value))

        _assign("value", value)
        _assign("upgrade_value", upgrade_value)
        _assign("cost", cost)
        _assign("secondary_value", secondary_value)
        _assign("secondary_upgrade", secondary_upgrade)

        def revert(context: "RuleWeaverContext") -> None:
            target = context.blueprint(identifier)
            for field, old_value in previous.items():
                object.__setattr__(target, field, old_value)

        return revert

    def set_card_description(
        self,
        identifier: str,
        *,
        description: Optional[str] = None,
        upgrade_description: Optional[str] = None,
    ) -> Callable[["RuleWeaverContext"], None]:
        blueprint = self.blueprint(identifier)
        previous_description = blueprint.description
        previous_localisations = blueprint.localizations
        new_description = description if description is not None else blueprint.description

        object.__setattr__(blueprint, "description", str(new_description))

        if upgrade_description is not None:
            localisations = {key: value for key, value in previous_localisations.items()}
            entry = localisations.get("eng")
            if entry is not None:
                entry = entry._replace(upgrade_description=upgrade_description)
            else:
                from modules.basemod_wrapper.cards import CardLocalizationEntry

                entry = CardLocalizationEntry(
                    title=blueprint.title,
                    description=blueprint.description,
                    upgrade_description=upgrade_description,
                )
            localisations["eng"] = entry
            object.__setattr__(blueprint, "localizations", MappingProxyType(localisations))

        def revert(context: "RuleWeaverContext") -> None:
            target = context.blueprint(identifier)
            object.__setattr__(target, "description", previous_description)
            object.__setattr__(target, "localizations", previous_localisations)

        return revert

    def add_keyword_to_card(
        self,
        identifier: str,
        keyword: str,
        *,
        amount: Optional[int] = None,
        upgrade: Optional[int] = None,
        card_uses: Optional[int] = None,
        card_uses_upgrade: Optional[int] = None,
    ) -> Callable[["RuleWeaverContext"], None]:
        canonical = _canonical_keyword(keyword)
        if not canonical:
            raise ValueError("Keyword identifier must be a non-empty string.")
        blueprint = self.blueprint(identifier)

        previous_keywords = blueprint.keywords
        previous_values = blueprint.keyword_values
        previous_upgrades = blueprint.keyword_upgrades
        previous_card_uses = blueprint.card_uses
        previous_card_uses_upgrade = blueprint.card_uses_upgrade
        previous_placeholders = blueprint._placeholders

        keywords = list(previous_keywords)
        if canonical not in keywords:
            keywords.append(canonical)
        object.__setattr__(blueprint, "keywords", tuple(keywords))

        values = dict(previous_values)
        upgrades = dict(previous_upgrades)
        if amount is not None:
            values[canonical] = int(amount)
        if upgrade is not None:
            upgrades[canonical] = int(upgrade)

        if canonical == "exhaustive":
            resolved_uses = amount if amount is not None else card_uses or previous_card_uses
            if resolved_uses is None:
                raise ValueError("Exhaustive keyword requires an explicit amount or card_uses value.")
            object.__setattr__(blueprint, "card_uses", int(resolved_uses))
            if card_uses_upgrade is not None:
                object.__setattr__(blueprint, "card_uses_upgrade", int(card_uses_upgrade))
            elif upgrade is not None:
                object.__setattr__(blueprint, "card_uses_upgrade", int(upgrade))
            else:
                object.__setattr__(blueprint, "card_uses_upgrade", previous_card_uses_upgrade)
            values.setdefault("exhaustive", int(resolved_uses))
            if blueprint.card_uses_upgrade:
                upgrades.setdefault("exhaustive", int(blueprint.card_uses_upgrade))

        object.__setattr__(blueprint, "keyword_values", MappingProxyType(values))
        object.__setattr__(blueprint, "keyword_upgrades", MappingProxyType(upgrades))
        object.__setattr__(blueprint, "_placeholders", _compute_placeholders(blueprint.keywords))

        def revert(context: "RuleWeaverContext") -> None:
            target = context.blueprint(identifier)
            object.__setattr__(target, "keywords", previous_keywords)
            object.__setattr__(target, "keyword_values", previous_values)
            object.__setattr__(target, "keyword_upgrades", previous_upgrades)
            object.__setattr__(target, "_placeholders", previous_placeholders)
            object.__setattr__(target, "card_uses", previous_card_uses)
            object.__setattr__(target, "card_uses_upgrade", previous_card_uses_upgrade)

        return revert

    def register_keyword(
        self,
        keyword_cls: type[Keyword] | str,
        *,
        names: Optional[Sequence[str]] = None,
        description: Optional[str] = None,
        mod_id: Optional[str] = None,
        color: Optional[Sequence[float]] = None,
    ) -> Callable[["RuleWeaverContext"], None]:
        if isinstance(keyword_cls, str):
            module_name, _, attr = keyword_cls.rpartition(".")
            if not module_name:
                raise ValueError("Keyword class path must include a module name.")
            module = import_module(module_name)
            keyword_cls = getattr(module, attr)
        if not issubclass(keyword_cls, Keyword):
            raise TypeError("register_keyword expects a Keyword subclass.")
        keyword = keyword_cls()
        registry = self.keyword_registry
        registry.register(keyword, names=names, description=description, mod_id=mod_id, color=color)

        aliases = {keyword.keyword_id}
        for name in names or ():
            aliases.add(_canonical_keyword(name))

        def revert(context: "RuleWeaverContext") -> None:
            registry = context.keyword_registry
            for alias in aliases:
                existing = registry._keywords.get(alias)
                if existing and existing.keyword is keyword:
                    registry._keywords.pop(alias, None)

        return revert

    def execute_python(self, source: str, *, filename: str = "<rule>") -> MutableMapping[str, Any]:
        namespace: Dict[str, Any] = {
            "context": self,
            "basemod": self.basemod,
            "cardcrawl": self.cardcrawl,
            "stslib": self.stslib,
            "spire": self.spire,
        }
        compiled = compile(source, filename, "exec")
        exec(compiled, namespace)
        return namespace


class RuleWeaverScript:
    """Declarative rule script that materialises mutations."""

    def __init__(self, *, source_path: Path, payload: Mapping[str, Any]) -> None:
        self.source_path = source_path
        self.payload = payload
        if "mutations" not in payload or not isinstance(payload["mutations"], Sequence):
            raise ValueError("Rule scripts must define a 'mutations' array.")

    @classmethod
    def load(cls, path: Path | str) -> "RuleWeaverScript":
        resolved = Path(path)
        if not resolved.exists():
            raise FileNotFoundError(resolved)
        text = resolved.read_text(encoding="utf8")
        if resolved.suffix.lower() in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore
            except Exception as exc:  # pragma: no cover - optional dependency
                raise RuntimeError("PyYAML is required to load YAML rule scripts.") from exc
            payload = yaml.safe_load(text)
        else:
            payload = json.loads(text)
        if not isinstance(payload, Mapping):
            raise ValueError("Rule script root must be a mapping.")
        return cls(source_path=resolved, payload=payload)

    def build_mutations(self) -> Tuple[MechanicMutation, ...]:
        mutations: List[MechanicMutation] = []
        for entry in self.payload.get("mutations", []):
            if not isinstance(entry, Mapping):
                raise ValueError("Each mutation entry must be a mapping.")
            identifier = entry.get("id") or entry.get("identifier")
            description = entry.get("description", "")
            priority = entry.get("priority", 100)
            tags = entry.get("tags", ())
            operations = entry.get("operations", [])
            metadata = entry.get("metadata", {})
            if not isinstance(operations, Sequence):
                raise ValueError(f"Mutation '{identifier}' must define an operations sequence.")

            def _build_apply(ops: Sequence[Mapping[str, Any]], mutation_id: str, meta: Mapping[str, Any]) -> Callable[[RuleWeaverContext], MechanicActivation]:
                def apply(context: RuleWeaverContext) -> MechanicActivation:
                    reverts: List[Callable[[RuleWeaverContext], None]] = []
                    for raw_operation in ops:
                        if not isinstance(raw_operation, Mapping):
                            raise ValueError(f"Invalid operation payload in mutation '{mutation_id}'.")
                        op_type = str(raw_operation.get("type") or raw_operation.get("operation") or "").strip().lower()
                        if op_type == "adjust_card":
                            reverts.append(
                                context.adjust_card_values(
                                    str(raw_operation["card_id"]),
                                    value=raw_operation.get("value"),
                                    upgrade_value=raw_operation.get("upgrade_value"),
                                    cost=raw_operation.get("cost"),
                                    secondary_value=raw_operation.get("secondary_value"),
                                    secondary_upgrade=raw_operation.get("secondary_upgrade"),
                                )
                            )
                        elif op_type == "set_description":
                            reverts.append(
                                context.set_card_description(
                                    str(raw_operation["card_id"]),
                                    description=raw_operation.get("description"),
                                    upgrade_description=raw_operation.get("upgrade_description"),
                                )
                            )
                        elif op_type in {"add_keyword", "attach_keyword"}:
                            reverts.append(
                                context.add_keyword_to_card(
                                    str(raw_operation["card_id"]),
                                    raw_operation.get("keyword") or raw_operation.get("name"),
                                    amount=raw_operation.get("amount"),
                                    upgrade=raw_operation.get("upgrade"),
                                    card_uses=raw_operation.get("card_uses"),
                                    card_uses_upgrade=raw_operation.get("card_uses_upgrade"),
                                )
                            )
                        elif op_type == "register_keyword":
                            reverts.append(
                                context.register_keyword(
                                    raw_operation.get("class") or raw_operation.get("keyword"),
                                    names=raw_operation.get("names"),
                                    description=raw_operation.get("description"),
                                    mod_id=raw_operation.get("mod_id"),
                                    color=raw_operation.get("color"),
                                )
                            )
                        elif op_type == "python":
                            context.execute_python(str(raw_operation.get("source", "")), filename=f"{self.source_path}:{mutation_id}")
                        else:
                            raise ValueError(f"Unsupported operation type '{op_type}' in mutation '{mutation_id}'.")
                    return MechanicActivation(identifier=mutation_id, revert_callbacks=tuple(reverts), metadata=MappingProxyType(dict(meta)))

                return apply

            apply = _build_apply(tuple(operations), str(identifier), metadata)
            mutation = MechanicMutation(
                identifier=str(identifier),
                description=str(description),
                apply=apply,
                priority=priority,
                tags=tuple(tags or ()),
                metadata=metadata,
            )
            mutations.append(mutation)
        return tuple(mutations)


class RuleWeaverEngine:
    """Manage mechanic mutations and expose plugin-friendly helpers."""

    def __init__(self) -> None:
        self._mutations: Dict[str, MechanicMutation] = {}
        self._activations: Dict[str, MechanicActivation] = {}
        self._lock = threading.RLock()
        self.blueprint_providers: List[Callable[[], Iterable[SimpleCardBlueprint]]] = []

    # ------------------------------------------------------------------
    def register_blueprint_provider(
        self,
        provider: Callable[[], Iterable[SimpleCardBlueprint]],
    ) -> None:
        if not callable(provider):
            raise TypeError("Blueprint provider must be callable.")
        with self._lock:
            if provider not in self.blueprint_providers:
                self.blueprint_providers.append(provider)

    # ------------------------------------------------------------------
    def register_mutation(self, mutation: MechanicMutation, *, activate: bool = False) -> None:
        with self._lock:
            self._mutations[mutation.identifier] = mutation
        if activate:
            self.activate_mutation(mutation.identifier)
        _refresh_plugin_exports()

    def activate_mutation(self, identifier: str) -> MechanicActivation:
        with self._lock:
            if identifier in self._activations:
                return self._activations[identifier]
            if identifier not in self._mutations:
                raise KeyError(identifier)
            mutation = self._mutations[identifier]
            context = RuleWeaverContext(engine=self, metadata={"mutation": identifier})
            activation = mutation.apply(context) or MechanicActivation(identifier=identifier)
            self._activations[identifier] = activation
        _refresh_plugin_exports()
        return activation

    def deactivate_mutation(self, identifier: str) -> None:
        with self._lock:
            activation = self._activations.pop(identifier, None)
        if activation is None:
            return
        context = RuleWeaverContext(engine=self, metadata={"mutation": identifier, "phase": "deactivate"})
        activation.revert(context)
        _refresh_plugin_exports()

    def deactivate_all(self) -> None:
        for identifier in list(self._activations):
            self.deactivate_mutation(identifier)

    # ------------------------------------------------------------------
    @property
    def registered_mutations(self) -> Mapping[str, MechanicMutation]:
        with self._lock:
            return MappingProxyType(dict(self._mutations))

    @property
    def active_mutations(self) -> Mapping[str, MechanicActivation]:
        with self._lock:
            return MappingProxyType(dict(self._activations))

    # ------------------------------------------------------------------
    def load_script(self, path: Path | str, *, activate: bool = False) -> Tuple[MechanicMutation, ...]:
        script = RuleWeaverScript.load(path)
        mutations = script.build_mutations()
        for mutation in mutations:
            self.register_mutation(mutation, activate=activate)
        return mutations


_ENGINE = RuleWeaverEngine()


def get_engine() -> RuleWeaverEngine:
    return _ENGINE


def load_script(path: Path | str, *, activate: bool = False) -> Tuple[MechanicMutation, ...]:
    return _ENGINE.load_script(path, activate=activate)


def activate() -> RuleWeaverEngine:
    if not experimental_is_active("graalpy_runtime"):
        experimental_on("graalpy_runtime")
    _refresh_plugin_exports()
    return _ENGINE


def deactivate() -> None:
    _ENGINE.deactivate_all()
    _refresh_plugin_exports()


def _refresh_plugin_exports() -> None:
    PLUGIN_MANAGER.expose("experimental_graalpy_rule_weaver_engine", _ENGINE)
    PLUGIN_MANAGER.expose(
        "experimental_graalpy_rule_weaver_mutations",
        {key: mutation.description for key, mutation in _ENGINE.registered_mutations.items()},
    )
    PLUGIN_MANAGER.expose(
        "experimental_graalpy_rule_weaver_active",
        {key: activation.metadata for key, activation in _ENGINE.active_mutations.items()},
    )
    PLUGIN_MANAGER.expose("experimental_graalpy_rule_weaver_load", load_script)


_refresh_plugin_exports()

