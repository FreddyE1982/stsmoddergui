"""Pluggable bridge between Python and the Slay the Spire JVM runtime.

The historical implementation of :mod:`modules.basemod_wrapper` has relied on
JPype to marshal objects between Python and Java.  Migrating to GraalPy requires
that we keep the public façade stable while swapping out the underlying bridge
mechanics at runtime.  This module centralises all JVM integration concerns in a
single backend manager so alternative implementations (JPype, GraalPy, or future
bridges) can be activated without touching call sites across the repository.

Backends are small objects implementing :class:`JavaIntegrationBackend`.  They
provide the primitive operations the wrapper needs (resolving classes, exposing
packages, creating functional interface proxies, manufacturing Java arrays, and
expanding bootstrap instructions).  The :class:`JavaBackendManager` keeps track
of the available implementations, exposes plugin-friendly helpers for switching
between them, and surfaces backend specific bootstrap guidance to
``modules.modbuilder.runtime_env``.

The default backend is JPype so the stable experience remains unchanged.  The
experimental GraalPy module registers an additional backend that leverages the
``java`` polyglot module when activated.  All repository components interact
with the current backend exclusively through this manager to guarantee the
“expose everything to plugins” rule mandated by the contributing guidelines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from importlib.util import find_spec
from pathlib import Path
import subprocess
import sys
from threading import RLock
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

from plugins import PLUGIN_MANAGER

__all__ = [
    "JavaIntegrationBackend",
    "JavaBackendManager",
    "JAVA_BACKENDS",
    "register_backend",
    "use_backend",
    "active_backend",
    "available_backends",
    "with_backend",
]


class JavaIntegrationBackend(ABC):
    """Abstract base class for JVM bridge implementations."""

    name: str

    @abstractmethod
    def ensure_bridge(self) -> None:
        """Ensure the Python bridge package is available."""

    @abstractmethod
    def is_bridge_available(self) -> bool:
        """Return ``True`` when the bridge runtime can be imported."""

    @abstractmethod
    def start_vm(self, classpath_entries: Sequence[Path]) -> None:
        """Start or attach to the JVM."""

    @abstractmethod
    def is_vm_running(self) -> bool:
        """Return ``True`` if the underlying JVM is active."""

    @abstractmethod
    def shutdown_vm(self) -> None:
        """Attempt to stop the underlying JVM if supported."""

    @abstractmethod
    def jclass(self, name: str) -> Any:
        """Return the Java class handle for ``name``."""

    @abstractmethod
    def jpackage(self, name: str) -> Any:
        """Return a handle representing the Java package ``name``."""

    @abstractmethod
    def package_getattr(self, package: Any, item: str) -> Any:
        """Return the attribute ``item`` from ``package``."""

    @abstractmethod
    def is_package(self, value: Any) -> bool:
        """Return ``True`` when ``value`` represents a Java package."""

    @abstractmethod
    def is_class(self, value: Any) -> bool:
        """Return ``True`` when ``value`` represents a Java class."""

    @abstractmethod
    def create_proxy(self, interface_name: str, methods: Mapping[str, Callable[..., Any]]) -> Any:
        """Return a proxy instance implementing ``interface_name``."""

    @abstractmethod
    def create_array(self, component_name: str, values: Sequence[Any]) -> Any:
        """Return a Java array for the given component class and ``values``."""

    @abstractmethod
    def extend_bootstrap_commands(
        self,
        *,
        posix: List[str],
        windows: List[str],
        pip_posix: Path,
        pip_windows: Path,
        requirement_files_present: bool,
        editable_targets_present: bool,
    ) -> None:
        """Augment bootstrap instructions with backend specific guidance."""

    @abstractmethod
    def install_default_dependencies(
        self,
        pip_executable: Path,
        *,
        environment: MutableMapping[str, str],
        logger: Callable[[str], None],
        requirement_files_present: bool,
        editable_targets_present: bool,
    ) -> None:
        """Install bridge specific dependencies in managed environments."""


class JavaBackendManager:
    """Thread-safe registry for JVM integration backends."""

    def __init__(self) -> None:
        self._backends: Dict[str, JavaIntegrationBackend] = {}
        self._active_name: Optional[str] = None
        self._lock = RLock()

    def register(self, backend: JavaIntegrationBackend, *, activate: bool = False) -> None:
        with self._lock:
            self._backends[backend.name] = backend
            if activate or self._active_name is None:
                self._active_name = backend.name

    def available(self) -> Iterable[str]:
        with self._lock:
            return tuple(sorted(self._backends))

    def get(self, name: Optional[str] = None) -> JavaIntegrationBackend:
        with self._lock:
            target = name or self._active_name
            if target is None or target not in self._backends:
                raise RuntimeError("No JVM integration backend has been registered.")
            return self._backends[target]

    def activate(self, name: str) -> JavaIntegrationBackend:
        with self._lock:
            if name not in self._backends:
                raise KeyError(name)
            self._active_name = name
            backend = self._backends[name]
            backend.ensure_bridge()
            return backend

    def active_name(self) -> str:
        with self._lock:
            backend = self.get()
            return backend.name

    def with_backend(self, name: str) -> JavaIntegrationBackend:
        return self.activate(name)


JAVA_BACKENDS = JavaBackendManager()


def register_backend(backend: JavaIntegrationBackend, *, activate: bool = False) -> None:
    """Register ``backend`` with the global manager."""

    JAVA_BACKENDS.register(backend, activate=activate)


def use_backend(name: str) -> JavaIntegrationBackend:
    """Activate and return the backend identified by ``name``."""

    backend = JAVA_BACKENDS.activate(name)
    PLUGIN_MANAGER.expose("java_backend_active", backend.name)
    return backend


def active_backend() -> JavaIntegrationBackend:
    """Return the currently active backend."""

    backend = JAVA_BACKENDS.get()
    PLUGIN_MANAGER.expose("java_backend_active", backend.name)
    return backend


def available_backends() -> Iterable[str]:
    """Expose the registered backend names."""

    return JAVA_BACKENDS.available()


def with_backend(name: str) -> JavaIntegrationBackend:
    """Convenience wrapper around :func:`use_backend` for plugins."""

    return use_backend(name)


# -- JPype backend -----------------------------------------------------------


class _JPypeBackend(JavaIntegrationBackend):
    name = "jpype"

    def ensure_bridge(self) -> None:
        if not self.is_bridge_available():
            subprocess.check_call([sys.executable, "-m", "pip", "install", "JPype1"])

    def is_bridge_available(self) -> bool:
        return find_spec("jpype") is not None

    def start_vm(self, classpath_entries: Sequence[Path]) -> None:
        import jpype

        if jpype.isJVMStarted():
            return
        classpath = [str(path) for path in classpath_entries]
        jpype.startJVM(classpath=[os.pathsep.join(classpath)])  # type: ignore[attr-defined]
        import jpype.imports  # noqa: F401

    def is_vm_running(self) -> bool:
        import jpype

        return jpype.isJVMStarted()

    def shutdown_vm(self) -> None:
        import jpype

        if jpype.isJVMStarted():
            try:
                jpype.shutdownJVM()
            except RuntimeError:  # pragma: no cover - jpype quirk during interpreter shutdown
                pass

    def jclass(self, name: str) -> Any:
        import jpype

        return jpype.JClass(name)

    def jpackage(self, name: str) -> Any:
        import jpype

        return jpype.JPackage(name)

    def package_getattr(self, package: Any, item: str) -> Any:
        return getattr(package, item)

    def is_package(self, value: Any) -> bool:
        import jpype

        return isinstance(value, jpype._jpackage.JPackage)

    def is_class(self, value: Any) -> bool:
        import jpype

        return isinstance(value, jpype.JClass)

    def create_proxy(self, interface_name: str, methods: Mapping[str, Callable[..., Any]]) -> Any:
        import jpype

        return jpype.JProxy(interface_name, dict(methods))

    def create_array(self, component_name: str, values: Sequence[Any]) -> Any:
        import jpype

        array_type = jpype.JArray(jpype.JClass(component_name))
        return array_type(values)

    def extend_bootstrap_commands(
        self,
        *,
        posix: List[str],
        windows: List[str],
        pip_posix: Path,
        pip_windows: Path,
        requirement_files_present: bool,
        editable_targets_present: bool,
    ) -> None:
        if not posix:
            posix.append(f"{shlex.quote(str(pip_posix))} install JPype1")
        if not windows:
            windows.append(f"{_windows_quote(str(pip_windows))} install JPype1")

    def install_default_dependencies(
        self,
        pip_executable: Path,
        *,
        environment: MutableMapping[str, str],
        logger: Callable[[str], None],
        requirement_files_present: bool,
        editable_targets_present: bool,
    ) -> None:
        if requirement_files_present or editable_targets_present:
            return
        _run_pip_with_logger(pip_executable, ["install", "--no-input", "JPype1"], environment, logger)


# Helper imports for JPype backend
import os
import shlex


def _windows_quote(path: str) -> str:
    if not path:
        return '""'
    if path.startswith('"') and path.endswith('"'):
        return path
    return f'"{path}"'


def _run_pip_with_logger(
    pip_executable: Path,
    arguments: Sequence[str],
    environment: Mapping[str, str],
    logger: Callable[[str], None],
) -> None:
    command = [str(pip_executable), *arguments]
    logger("Executing: " + " ".join(shlex.quote(part) for part in command))
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(environment),
    )
    if result.returncode != 0:
        raise RuntimeError(
            "pip command failed:\n"
            + result.stdout.strip()
            + ("\n" if result.stdout.strip() else "")
            + result.stderr.strip()
        )


register_backend(_JPypeBackend(), activate=True)


PLUGIN_MANAGER.expose("java_backends", JAVA_BACKENDS)
PLUGIN_MANAGER.expose("java_backend_use", use_backend)
PLUGIN_MANAGER.expose("java_backend_active", lambda: active_backend().name)
PLUGIN_MANAGER.expose("java_backend_available", lambda: tuple(available_backends()))
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.java_backend")

