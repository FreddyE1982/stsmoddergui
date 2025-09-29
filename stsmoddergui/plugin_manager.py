"""Centralised plugin management for :mod:`stsmoddergui`.

The plugin architecture is designed to be repository-wide.  Every
function, class, and module level variable that lives inside the
project is introspected and exposed through the plugin context.  The
registry makes it possible for third party code to interact with any
part of the code base without modifying the core implementation.

The system is intentionally designed to be forward compatible: new
packages and modules are discovered dynamically at runtime.  Whenever a
new module is added it will become available to existing plugins after a
reload cycle without requiring manual changes.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, Iterable, Iterator, Mapping, MutableMapping, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(slots=True)
class PluginContext:
    """Context injected into plugins during activation.

    Attributes
    ----------
    api:
        A mutable mapping that contains all exported repository objects
        grouped by type.  The dictionary contains the keys
        ``modules``, ``classes``, ``functions``, ``variables`` and
        ``packages``.  Each key maps to another dictionary where the key
        is the fully qualified name of the object and the value is the
        actual Python object.
    registry:
        Reference back to the :class:`PluginRegistry` that activated the
        plugin.  This allows plugins to request further introspection or
        to register hooks of their own.
    metadata:
        Arbitrary metadata supplied during plugin registration.  This can
        be used to configure plugins without relying on global state.
    """

    api: MutableMapping[str, Dict[str, Any]]
    registry: "PluginRegistry"
    metadata: MutableMapping[str, Any] = field(default_factory=dict)

    def require(self, name: str) -> Any:
        """Return a previously exposed object by name.

        The ``name`` parameter is matched against all namespaces in the
        API map.  The first match is returned.  A ``KeyError`` is raised
        if the object cannot be found.
        """

        for namespace in ("packages", "modules", "classes", "functions", "variables"):
            bucket = self.api.get(namespace, {})
            if name in bucket:
                return bucket[name]
        raise KeyError(f"No exposed object named '{name}'.")


@dataclass(slots=True)
class PluginDescriptor:
    """Lightweight descriptor for a plugin module."""

    name: str
    module: ModuleType
    activate: Callable[[PluginContext], None]
    metadata: Dict[str, Any] = field(default_factory=dict)


class PluginRegistry:
    """Registry that keeps track of loaded plugins and API exposure."""

    def __init__(self) -> None:
        self._descriptors: Dict[str, PluginDescriptor] = {}
        self._exposed_api: Dict[str, Dict[str, Any]] = {}
        self._scanned_packages: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def api(self) -> Mapping[str, Dict[str, Any]]:
        """Return the full repository API mapping."""

        if not self._exposed_api:
            self.refresh()
        return self._exposed_api

    def refresh(self) -> None:
        """Rescan the repository to expose all modules and objects."""

        packages = self._discover_packages()
        exposed_modules: Dict[str, Any] = {}
        exposed_classes: Dict[str, Any] = {}
        exposed_functions: Dict[str, Any] = {}
        exposed_variables: Dict[str, Any] = {}

        for package_name in packages:
            package = importlib.import_module(package_name)
            self._scanned_packages.add(package_name)
            exposed_modules[package_name] = package
            for finder, name, is_pkg in pkgutil.walk_packages(package.__path__, prefix=f"{package_name}."):
                try:
                    module = importlib.import_module(name)
                except Exception as exc:  # pragma: no cover - best effort introspection
                    # Keep a note in the variables namespace for debugging purposes.
                    exposed_variables[f"{name}.__load_error__"] = exc
                    continue
                exposed_modules[name] = module
                self._introspect_module(name, module, exposed_classes, exposed_functions, exposed_variables)

        self._exposed_api = {
            "packages": {pkg: importlib.import_module(pkg) for pkg in packages},
            "modules": exposed_modules,
            "classes": exposed_classes,
            "functions": exposed_functions,
            "variables": exposed_variables,
        }

    def register(self, module_name: str, *, metadata: Optional[Mapping[str, Any]] = None) -> PluginDescriptor:
        """Register and activate a plugin by module name."""

        if module_name in self._descriptors:
            return self._descriptors[module_name]

        module = importlib.import_module(module_name)
        activate = getattr(module, "activate_plugin", None)
        if not callable(activate):
            raise AttributeError(
                f"Plugin module '{module_name}' must define an 'activate_plugin(context)' callable."
            )

        descriptor = PluginDescriptor(
            name=module_name,
            module=module,
            activate=activate,
            metadata=dict(metadata or {}),
        )
        self._descriptors[module_name] = descriptor
        self._activate(descriptor)
        return descriptor

    def register_from_module(self, module: ModuleType, *, metadata: Optional[Mapping[str, Any]] = None) -> PluginDescriptor:
        """Register a plugin from an already imported module."""

        module_name = module.__name__
        if module_name in self._descriptors:
            return self._descriptors[module_name]
        activate = getattr(module, "activate_plugin", None)
        if not callable(activate):
            raise AttributeError(
                f"Plugin module '{module_name}' must define an 'activate_plugin(context)' callable."
            )
        descriptor = PluginDescriptor(
            name=module_name,
            module=module,
            activate=activate,
            metadata=dict(metadata or {}),
        )
        self._descriptors[module_name] = descriptor
        self._activate(descriptor)
        return descriptor

    def iter_plugins(self) -> Iterator[PluginDescriptor]:
        """Iterate over all registered plugin descriptors."""

        return iter(self._descriptors.values())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _activate(self, descriptor: PluginDescriptor) -> None:
        context = PluginContext(api=self.api.copy(), registry=self, metadata=descriptor.metadata)
        descriptor.activate(context)

    def _discover_packages(self) -> Iterable[str]:
        """Find top-level packages that belong to the project."""

        packages = set()
        for package_dir in ("stsmoddergui", "modules"):
            path = _PROJECT_ROOT / package_dir
            if not path.exists():
                continue
            if (path / "__init__.py").exists():
                packages.add(package_dir.replace("/", "."))
            else:
                # treat namespace packages by creating a virtual package on the fly
                init_file = path / "__init__.py"
                if not init_file.exists():
                    init_file.write_text("""\n# Namespace package generated for plugin discovery.\n""")
                packages.add(package_dir.replace("/", "."))
        return sorted(packages)

    def _introspect_module(
        self,
        module_name: str,
        module: ModuleType,
        exposed_classes: Dict[str, Any],
        exposed_functions: Dict[str, Any],
        exposed_variables: Dict[str, Any],
    ) -> None:
        """Populate the API dictionaries with members from ``module``."""

        for attr_name, attr_value in inspect.getmembers(module):
            fq_name = f"{module_name}.{attr_name}"
            if inspect.isclass(attr_value):
                exposed_classes[fq_name] = attr_value
            elif inspect.isfunction(attr_value):
                exposed_functions[fq_name] = attr_value
            elif not attr_name.startswith("__"):
                exposed_variables[fq_name] = attr_value


GLOBAL_PLUGIN_REGISTRY = PluginRegistry()

__all__ = [
    "PluginContext",
    "PluginDescriptor",
    "PluginRegistry",
    "GLOBAL_PLUGIN_REGISTRY",
]
