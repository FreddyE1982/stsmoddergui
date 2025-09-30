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
from importlib.util import find_spec
from pathlib import Path
import pkgutil
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


_MISSING = object()


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
            try:
                _REPOSITORY_ATTRIBUTE_MANIFEST.mark_dirty(self._module_name)
            except NameError:  # pragma: no cover - executed during bootstrap
                pass
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
        self._dirty: set[str] = set()
        self._snapshots: Dict[str, set[str]] = {}

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
            self._dirty.add(module_name)
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

    def mark_dirty(self, module_name: str) -> None:
        if module_name in self._modules:
            if module_name in self._cache:
                self._dirty.add(module_name)

    def invalidate(self, module_name: Optional[str] = None) -> None:
        """Invalidate cached attributes so future lookups rescan modules."""

        if module_name is None:
            self._cache.clear()
            self._dirty = set(self._modules)
            self._snapshots.clear()
            return
        if module_name in self._cache:
            self._cache.pop(module_name, None)
            self._dirty.add(module_name)
            self._snapshots.pop(module_name, None)

    def diff(
        self,
        module_name: Optional[str] = None,
        *,
        initial: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """Return newly discovered attributes for dirty modules."""

        if module_name is not None:
            modules = [module_name]
            if module_name not in self._cache and module_name in self._modules:
                self._materialise(module_name)
        elif initial:
            modules = list(self._cache.keys())
        else:
            modules = list(self._dirty)
        changes: Dict[str, Dict[str, Any]] = {}
        for name in modules:
            if name not in self._modules:
                continue
            exports = self._materialise(name)
            keys = set(exports.keys())
            previous = self._snapshots.get(name, set())
            if initial or name not in self._snapshots:
                changes[name] = {key: exports[key] for key in keys}
            else:
                new_keys = keys - previous
                if new_keys:
                    changes[name] = {key: exports[key] for key in new_keys}
            self._snapshots[name] = keys
        if module_name is None:
            if initial:
                self._dirty.clear()
            else:
                self._dirty.difference_update(modules)
        return changes


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
        self._export_subscribers: List[
            Callable[[Dict[str, Any], Dict[str, Dict[str, Any]], MappingProxyType], None]
        ] = []

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
        previous = self._exposed.get(name, _MISSING)
        self._exposed[name] = obj
        diff: Dict[str, Any] = {}
        if previous is _MISSING or previous is not obj:
            diff[name] = obj
        self._notify_export_subscribers(diff)

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
        self._notify_export_subscribers({})
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

    def subscribe_to_exports(
        self,
        callback: Callable[[Dict[str, Any], Dict[str, Dict[str, Any]], MappingProxyType], None],
        *,
        replay: bool = True,
    ) -> None:
        """Register ``callback`` to receive export and repository diffs."""

        if callback in self._export_subscribers:
            return
        self._export_subscribers.append(callback)
        if replay:
            try:
                repository_diff = _REPOSITORY_ATTRIBUTE_MANIFEST.diff(initial=True)
            except NameError:  # pragma: no cover - occurs during bootstrap
                repository_diff = {}
            callback({}, repository_diff, self.exposed)

    def refresh_repository_exports(
        self, module_name: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Force a diff computation for cached repository attributes."""

        try:
            repository_diff = _REPOSITORY_ATTRIBUTE_MANIFEST.diff(
                module_name, initial=False
            )
        except NameError:  # pragma: no cover - occurs during bootstrap
            repository_diff = {}
        if repository_diff and self._export_subscribers:
            snapshot = self.exposed
            for callback in list(self._export_subscribers):
                callback({}, repository_diff, snapshot)
        return repository_diff

    def auto_discover(
        self,
        location: str | Path,
        *,
        attr: str = "setup_plugin",
        recursive: bool = True,
        match: Optional[Callable[[str], bool]] = None,
    ) -> Dict[str, PluginRecord]:
        """Automatically register plugins located under ``location``."""

        package_name, search_paths = self._resolve_auto_discover_location(location)
        matcher = match or self._default_auto_discover_match
        discovered: Dict[str, PluginRecord] = {}
        failures: List[Tuple[str, Exception]] = []
        for module_name in self._walk_auto_discover_modules(
            search_paths, package_name, recursive
        ):
            if not matcher(module_name):
                continue
            try:
                discovered[module_name] = self.register_plugin(module_name, attr=attr)
            except PluginError as exc:
                failures.append((module_name, exc))
        if failures:
            reasons = "\n".join(f"- {name}: {error}" for name, error in failures)
            raise PluginError(
                "Failed to auto discover plugin modules:\n" + reasons
            )
        return discovered

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _notify_export_subscribers(self, exposure_diff: Dict[str, Any]) -> None:
        if not self._export_subscribers:
            return
        try:
            repository_diff = _REPOSITORY_ATTRIBUTE_MANIFEST.diff()
        except NameError:  # pragma: no cover - occurs during bootstrap
            repository_diff = {}
        if not exposure_diff and not repository_diff:
            return
        snapshot = self.exposed
        for callback in list(self._export_subscribers):
            callback(dict(exposure_diff), repository_diff, snapshot)

    @staticmethod
    def _default_auto_discover_match(module_name: str) -> bool:
        base = module_name.rsplit(".", 1)[-1].lower()
        return (
            base.startswith("plugin_")
            or base.endswith("_plugin")
            or base.endswith("plugin")
        )

    def _resolve_auto_discover_location(
        self, location: str | Path
    ) -> Tuple[str, Sequence[str]]:
        if isinstance(location, Path):
            path = location
        else:
            spec = find_spec(str(location))
            if spec and spec.submodule_search_locations:
                return str(location), list(spec.submodule_search_locations)
            path = Path(str(location))
        if not path.is_absolute():
            candidate = path.resolve()
        else:
            candidate = path
        if not candidate.exists():
            raise PluginError(f"Plugin location '{location}' does not exist.")
        if (candidate / "__init__.py").exists():
            try:
                relative = candidate.relative_to(_REPO_ROOT)
                package_name = ".".join(relative.parts)
            except Exception as exc:  # pragma: no cover - defensive path
                raise PluginError(
                    "Unable to derive package name for plugin discovery."
                ) from exc
        else:
            raise PluginError(
                "Auto discovery requires package-style directories with an __init__.py."
            )
        return package_name, [str(candidate)]

    @staticmethod
    def _walk_auto_discover_modules(
        search_paths: Sequence[str],
        package_name: str,
        recursive: bool,
    ) -> Iterator[str]:
        for module_info in pkgutil.walk_packages(search_paths, package_name + "."):
            if module_info.ispkg and not recursive:
                continue
            yield module_info.name


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


# Determine repository structure before initialising the plugin manager so
# helpers can report accurate diffs immediately after bootstrap.
_REPO_ROOT = Path(__file__).resolve().parent
_MODULE_PROXIES = _discover_repository_modules(_REPO_ROOT)
_REPOSITORY_NAMESPACE = _RepositoryNamespace(_MODULE_PROXIES)
_REPOSITORY_ATTRIBUTE_MANIFEST = _RepositoryAttributeManifest(_MODULE_PROXIES)

# Expose the global plugin manager instance immediately for general use.
PLUGIN_MANAGER = PluginManager()

# Make sure plugin authors can introspect the plugin infrastructure itself.
PLUGIN_MANAGER.expose_module("plugins")

for module_name in _MODULE_PROXIES:
    if module_name in PLUGIN_MANAGER.exposed:
        continue
    PLUGIN_MANAGER.expose_lazy_module(module_name)

PLUGIN_MANAGER.expose("repository", _REPOSITORY_NAMESPACE)
PLUGIN_MANAGER.expose("repository_attributes", _REPOSITORY_ATTRIBUTE_MANIFEST)
PLUGIN_MANAGER.expose("auto_discover_plugins", PLUGIN_MANAGER.auto_discover)
PLUGIN_MANAGER.expose(
    "subscribe_to_repository_exports", PLUGIN_MANAGER.subscribe_to_exports
)
PLUGIN_MANAGER.expose(
    "refresh_repository_exports", PLUGIN_MANAGER.refresh_repository_exports
)

# Seed the repository diff cache so later subscribers only receive incremental
# updates.
PLUGIN_MANAGER.refresh_repository_exports()

__all__ = ["PLUGIN_MANAGER", "PluginManager", "PluginError", "PluginRecord"]
