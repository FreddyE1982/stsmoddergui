"""Global plugin infrastructure for the stsmoddergui repository.

This module exposes a single :class:`PluginManager` instance that can be used
by any part of the code base to offer structured extension points.  The design
follows a simple registry model that keeps the exposed API in a dedicated
namespace for clarity while still allowing plugins to mutate and extend the
behaviour of the application.

The plugin interface is intentionally high level and pythonic – plugin authors
only need to provide callables or objects with methods that will be invoked by
the core application.  Every repository module can explicitly expose any
function, class or variable via :func:`PLUGIN_MANAGER.expose` which makes the
entire repository accessible to plugins as required by the contributing
guidelines.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, MutableMapping, Optional


class PluginError(RuntimeError):
    """Raised whenever a plugin cannot be registered or executed."""


@dataclass
class PluginRecord:
    """Simple data container describing a registered plugin."""

    name: str
    module: str
    obj: Any
    exposed: MappingProxyType


class PluginManager:
    """Co-ordinates plugin registration and access to repository internals.

    The manager keeps a registry of plugin objects and provides a typed context
    dictionary that mirrors everything the repository decides to expose.  The
    context is made available to plugins during registration so they can pull
    whichever components they need without any extra ceremony.
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, PluginRecord] = {}
        self._exposed: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    @property
    def exposed(self) -> MappingProxyType:
        """Immutable view of the currently exposed repository objects."""

        return MappingProxyType(self._exposed)

    @property
    def plugins(self) -> MappingProxyType:
        """Immutable view of the registered plugins."""

        return MappingProxyType(self._plugins)

    def expose(self, name: str, obj: Any) -> None:
        """Expose an object to the plugin context under ``name``.

        The manager will overwrite existing entries – this allows modules to
        update the exposed object when their own state changes.  Consumers get a
        live object reference so they can interact with the real implementation.
        """

        if not name:
            raise PluginError("Exposed names must be non-empty strings.")
        self._exposed[name] = obj

    def expose_module(self, module_name: str, alias: Optional[str] = None) -> None:
        """Expose all public attributes of ``module_name`` under ``alias``.

        ``alias`` defaults to the module name.  Private attributes (prefixed
        with an underscore) are ignored.  This keeps the plugin API pleasant to
        use and mirrors the typical behaviour of ``from module import *``.
        """

        module = import_module(module_name)
        export_name = alias or module_name
        export: Dict[str, Any] = {
            key: getattr(module, key)
            for key in dir(module)
            if not key.startswith("_")
        }
        self.expose(export_name, MappingProxyType(export))

    def register_plugin(self, module_name: str, attr: str = "setup_plugin") -> PluginRecord:
        """Import ``module_name`` and run its setup function.

        ``attr`` defaults to ``setup_plugin`` which mirrors common Python plugin
        conventions.  The callable is expected to accept two positional
        arguments: the :class:`PluginManager` instance and a mapping of exposed
        objects.
        """

        if module_name in self._plugins:
            raise PluginError(f"Plugin '{module_name}' is already registered.")

        module = import_module(module_name)
        try:
            factory = getattr(module, attr)
        except AttributeError as exc:  # pragma: no cover - explicit error path
            raise PluginError(
                f"Plugin '{module_name}' does not provide a '{attr}' callable."
            ) from exc

        if not callable(factory):
            raise PluginError(
                f"Plugin '{module_name}.{attr}' must be callable, got {type(factory)!r}."
            )

        instance = factory(self, self.exposed)
        record = PluginRecord(
            name=getattr(instance, "name", module_name),
            module=module_name,
            obj=instance,
            exposed=self.exposed,
        )
        self._plugins[module_name] = record
        return record

    def broadcast(self, hook: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Invoke ``hook`` on all registered plugins and collect responses."""

        responses: Dict[str, Any] = {}
        for name, record in self._plugins.items():
            target = getattr(record.obj, hook, None)
            if target is None:
                continue
            if not callable(target):
                raise PluginError(
                    f"Hook '{hook}' on plugin '{name}' is not callable (got {type(target)!r})."
                )
            responses[name] = target(*args, **kwargs)
        return responses

    def ensure(self, required: Iterable[str]) -> None:
        """Validate that all ``required`` plugins have been registered."""

        missing = [name for name in required if name not in self._plugins]
        if missing:
            raise PluginError(
                "Missing required plugin(s): " + ", ".join(sorted(missing))
            )


# Expose the global plugin manager instance immediately for general use.
PLUGIN_MANAGER = PluginManager()

# Make sure plugin authors can introspect the plugin infrastructure itself.
PLUGIN_MANAGER.expose_module("plugins")

__all__ = ["PLUGIN_MANAGER", "PluginManager", "PluginError", "PluginRecord"]
