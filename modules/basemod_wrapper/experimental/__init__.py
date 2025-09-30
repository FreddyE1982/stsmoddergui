"""Runtime toggle infrastructure for optional BaseMod experimental features.

The :mod:`modules.basemod_wrapper.experimental` package acts as a curated home
for features that are not part of the stable BaseMod façade yet.  Each feature
lives in its own submodule and can be activated or deactivated on demand::

    from modules.basemod_wrapper import experimental

    # Enable the ``sample_feature`` module.
    experimental.on("sample_feature")

    # Disable it again once the experiment is over.
    experimental.off("sample_feature")

Every submodule is expected to expose :func:`activate` and :func:`deactivate`
callables.  They are invoked automatically whenever :func:`on` / :func:`off` are
called so experiments can flip runtime hooks without leaking side effects.  The
module loader keeps track of active experiments, lazily imports packages only
when required, and exposes the state through helper functions that integrate
with the repository-wide :mod:`plugins` system.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from importlib.util import find_spec
import pkgutil
from threading import RLock
from types import ModuleType
from typing import Dict, Iterable, Mapping

from plugins import PLUGIN_MANAGER

__all__ = [
    "ExperimentalFeatureError",
    "available_modules",
    "active_modules",
    "load",
    "on",
    "off",
    "is_active",
    "refresh",
]


class ExperimentalFeatureError(RuntimeError):
    """Raised when an experimental module cannot be resolved."""


@dataclass
class _ExperimentalFeature:
    """Bookkeeping structure for lazily loaded experimental modules."""

    canonical_name: str
    module_name: str
    module: ModuleType | None = None
    active: bool = False

    def load(self) -> ModuleType:
        """Import and return the underlying Python module."""

        if self.module is None:
            if find_spec(self.module_name) is None:
                raise ExperimentalFeatureError(
                    f"Experimental module '{self.module_name}' cannot be located."
                )
            self.module = import_module(self.module_name)
        return self.module

    def activate(self) -> ModuleType:
        """Trigger the module's :func:`activate` hook if required."""

        module = self.load()
        if not self.active:
            hook = getattr(module, "activate", None) or getattr(module, "on_activate", None)
            if hook is not None:
                hook()
            self.active = True
        return module

    def deactivate(self) -> ModuleType:
        """Trigger the module's :func:`deactivate` hook if required."""

        module = self.load()
        if self.active:
            hook = getattr(module, "deactivate", None) or getattr(
                module, "on_deactivate", None
            )
            if hook is not None:
                hook()
            self.active = False
        return module


_FEATURES: Dict[str, _ExperimentalFeature] = {}
_AMBIGUOUS = object()
_ALIAS_MAP: Dict[str, str | object] = {}
_DISCOVERY_LOCK = RLock()


def _register_alias(feature: _ExperimentalFeature) -> None:
    """Expose canonical and shorthand aliases for a feature."""

    _ALIAS_MAP.setdefault(feature.canonical_name, feature.canonical_name)
    short_alias = feature.canonical_name.rsplit(".", 1)[-1]
    if short_alias not in _ALIAS_MAP:
        _ALIAS_MAP[short_alias] = feature.canonical_name
    elif _ALIAS_MAP[short_alias] not in (feature.canonical_name, _AMBIGUOUS):
        # Alias collision – require callers to use the fully qualified name.
        _ALIAS_MAP[short_alias] = _AMBIGUOUS


def _register_feature(module_name: str) -> None:
    canonical = module_name[len(__name__) + 1 :]
    if not canonical or canonical.startswith("_"):
        return
    feature = _FEATURES.get(canonical)
    if feature is None:
        feature = _ExperimentalFeature(canonical, module_name)
        _FEATURES[canonical] = feature
    _register_alias(feature)


def refresh() -> Mapping[str, _ExperimentalFeature]:
    """Re-scan the package and return the known feature mapping."""

    with _DISCOVERY_LOCK:
        for module_info in pkgutil.walk_packages(__path__, prefix=f"{__name__}."):
            if module_info.name.endswith(".__init__"):
                continue
            _register_feature(module_info.name)
        return dict(_FEATURES)


def _resolve(name: str) -> _ExperimentalFeature:
    cleaned = name.strip()
    if not cleaned:
        raise ExperimentalFeatureError("Experimental module name cannot be empty.")
    refresh()
    candidates = (
        cleaned,
        cleaned.lstrip("."),
        cleaned.rsplit(".", 1)[-1],
    )
    for candidate in candidates:
        if candidate in _FEATURES:
            return _FEATURES[candidate]
        alias = _ALIAS_MAP.get(candidate)
        if isinstance(alias, str) and alias in _FEATURES:
            return _FEATURES[alias]
        if alias is _AMBIGUOUS:
            raise ExperimentalFeatureError(
                f"Experimental module alias '{cleaned}' is ambiguous. Use the fully qualified name."
            )
    qualified = cleaned
    if not qualified.startswith(__name__):
        qualified = f"{__name__}.{qualified.lstrip('.')}"
    if find_spec(qualified) is None:
        raise ExperimentalFeatureError(f"Unknown experimental module '{cleaned}'.")
    _register_feature(qualified)
    return _FEATURES[qualified[len(__name__) + 1 :]]


def on(name: str) -> ModuleType:
    """Activate the given experimental module and return it."""

    feature = _resolve(name)
    module = feature.activate()
    PLUGIN_MANAGER.expose(f"experimental:{feature.canonical_name}:active", True)
    return module


def off(name: str) -> ModuleType:
    """Deactivate the given experimental module and return it."""

    feature = _resolve(name)
    module = feature.deactivate()
    PLUGIN_MANAGER.expose(f"experimental:{feature.canonical_name}:active", feature.active)
    return module


def load(name: str) -> ModuleType:
    """Return the module instance without toggling activation."""

    feature = _resolve(name)
    return feature.load()


def is_active(name: str) -> bool:
    """Return ``True`` when the experimental module is active."""

    feature = _resolve(name)
    return feature.active


def available_modules() -> Iterable[str]:
    """Return all known experimental module names."""

    refresh()
    return tuple(sorted(_FEATURES))


def active_modules() -> Mapping[str, ModuleType]:
    """Return a mapping of active module names to module objects."""

    refresh()
    active: Dict[str, ModuleType] = {}
    for name, feature in _FEATURES.items():
        if feature.active and feature.module is not None:
            active[name] = feature.module
    return active


# Ensure initial discovery so plugin exposures have metadata to work with.
refresh()

# Surface the toggle interface through the repository-wide plugin manager.
PLUGIN_MANAGER.expose("experimental_on", on)
PLUGIN_MANAGER.expose("experimental_off", off)
PLUGIN_MANAGER.expose("experimental_load", load)
PLUGIN_MANAGER.expose("experimental_is_active", is_active)
PLUGIN_MANAGER.expose("experimental_available", lambda: tuple(available_modules()))
PLUGIN_MANAGER.expose("experimental_active", active_modules)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.experimental", alias="basemod_experimental")
