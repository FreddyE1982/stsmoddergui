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
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, Optional


class PluginError(RuntimeError):
    """Raised whenever a plugin cannot be registered or executed."""


@dataclass
class PluginRecord:
    """Simple data container describing a registered plugin."""

    name: str
    module: str
    obj: Any
    exposed: MappingProxyType


class _LazyModuleProxy:
    """Proxy that imports a module on first attribute access."""

    def __init__(self, module_name: str) -> None:
        self._module_name = module_name
        self._module: Optional[Any] = None

    def _load(self) -> Any:
        if self._module is None:
            self._module = import_module(self._module_name)
        return self._module

    def load(self) -> Any:
        """Return the underlying module, importing it on demand."""

        return self._load()

    def __getattr__(self, item: str) -> Any:
        return getattr(self._load(), item)

    def __dir__(self) -> Iterable[str]:  # pragma: no cover - simple passthrough
        return dir(self._load())


class _RepositoryNamespace:
    """Collects lazily imported modules under friendly aliases."""

    def __init__(self, modules: Dict[str, _LazyModuleProxy]) -> None:
        self._modules = modules
        self._aliases: Dict[str, _LazyModuleProxy] = {}
        for name, proxy in modules.items():
            alias = name.split(".")[-1]
            self._aliases.setdefault(alias, proxy)

    def module(self, name: str) -> _LazyModuleProxy:
        return self._modules[name]

    def __getattr__(self, item: str) -> Any:
        if item in self._aliases:
            return self._aliases[item]
        if item in self._modules:
            return self._modules[item]
        raise AttributeError(item)

    def __dir__(self) -> Iterable[str]:  # pragma: no cover - trivial glue
        return sorted(set(self._modules) | set(self._aliases))

    def items(self):
        return self._modules.items()


class _RepositoryAttributeManifest:
    """Materialises public attributes for each repository module on demand."""

    def __init__(self, modules: Dict[str, _LazyModuleProxy]) -> None:
        self._modules = modules
        self._cache: Dict[str, MappingProxyType] = {}

    def _materialise(self, module_name: str) -> MappingProxyType:
        if module_name not in self._modules:
            raise KeyError(module_name)
        if module_name not in self._cache:
            module = self._modules[module_name].load()
            export: Dict[str, Any] = {
                key: getattr(module, key)
                for key in dir(module)
                if key != "__builtins__"
            }
            self._cache[module_name] = MappingProxyType(export)
        return self._cache[module_name]

    def __contains__(self, module_name: str) -> bool:  # pragma: no cover - trivial
        return module_name in self._modules

    def __getitem__(self, module_name: str) -> MappingProxyType:
        return self._materialise(module_name)

    def get(self, module_name: str, default: Optional[Any] = None) -> MappingProxyType:
        try:
            return self._materialise(module_name)
        except KeyError:
            if default is not None:
                return default
            raise

    def modules(self) -> Iterable[str]:
        return self._modules.keys()

    def items(self):  # pragma: no cover - simple delegation
        for module_name in sorted(self._modules):
            yield module_name, self._materialise(module_name)

    def snapshot(self) -> MappingProxyType:
        """Return an immutable mapping of module names to public attributes."""

        manifest = {name: self._materialise(name) for name in self._modules}
        return MappingProxyType(manifest)


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

    def expose_lazy_module(self, module_name: str, alias: Optional[str] = None) -> None:
        """Expose ``module_name`` lazily under ``alias`` for plugin access."""

        proxy = _LazyModuleProxy(module_name)
        export_name = alias or module_name
        self.expose(export_name, proxy)

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


# ---------------------------------------------------------------------------
# repository exposure helpers
# ---------------------------------------------------------------------------
def _module_name_from_path(root: Path, path: Path) -> Optional[str]:
    rel = path.relative_to(root)
    if rel.name == "__init__.py":
        parts = rel.parts[:-1]
    else:
        parts = rel.with_suffix("").parts
    if not parts:
        return None
    return ".".join(parts)


def _discover_repository_modules(root: Path) -> Dict[str, _LazyModuleProxy]:
    modules: Dict[str, _LazyModuleProxy] = {}
    for path in root.rglob("*.py"):
        if path.name.startswith("_"):
            continue
        module_name = _module_name_from_path(root, path)
        if not module_name:
            continue
        modules[module_name] = _LazyModuleProxy(module_name)
    return modules


# Expose the global plugin manager instance immediately for general use.
PLUGIN_MANAGER = PluginManager()

# Make sure plugin authors can introspect the plugin infrastructure itself.
PLUGIN_MANAGER.expose_module("plugins")

_REPO_ROOT = Path(__file__).resolve().parent
_MODULE_PROXIES = _discover_repository_modules(_REPO_ROOT)
_REPOSITORY_NAMESPACE = _RepositoryNamespace(_MODULE_PROXIES)
_REPOSITORY_ATTRIBUTE_MANIFEST = _RepositoryAttributeManifest(_MODULE_PROXIES)

for module_name in _MODULE_PROXIES:
    if module_name in PLUGIN_MANAGER.exposed:
        continue
    PLUGIN_MANAGER.expose_lazy_module(module_name)

PLUGIN_MANAGER.expose("repository", _REPOSITORY_NAMESPACE)
PLUGIN_MANAGER.expose("repository_attributes", _REPOSITORY_ATTRIBUTE_MANIFEST)

__all__ = ["PLUGIN_MANAGER", "PluginManager", "PluginError", "PluginRecord"]
