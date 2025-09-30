"""Activate a GraalPy-powered JVM bridge for the BaseMod wrapper.

The GraalPy runtime removes the JPype dependency entirely – both Python and
Java execute inside the same GraalVM process.  Activating this experimental
module installs the GraalPy distribution when missing, rebuilds required Python
packages (Pillow in particular) for the current operating system, records build
metadata for reproducibility, and swaps the repository-wide JVM backend to a
polyglot-powered implementation.  Once enabled, all Python ↔ Java interactions
performed through :mod:`modules.basemod_wrapper` flow through the GraalPy
bridge and no JPype API is exercised.

Deactivating the module restores the previously active backend.  The module
exposes provisioning helpers through :mod:`plugins` so tooling and tests can
trigger the migration workflow programmatically.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, MutableMapping, Optional, Sequence

from plugins import PLUGIN_MANAGER

from ..java_backend import (
    JavaIntegrationBackend,
    available_backends,
    register_backend,
    use_backend,
    active_backend,
    _run_pip_with_logger,
    _windows_quote,
)

import shlex

__all__ = ["activate", "deactivate", "GraalPyProvisioningState"]


@dataclass(frozen=True)
class GraalPyProvisioningState:
    """Introspection structure describing the GraalPy provisioning process."""

    executable: Path
    platform: str
    architecture: str
    graalpy_version: str
    pillow_version: str
    manifest_path: Path


_PREVIOUS_BACKEND: Optional[str] = None
_PROVISIONING_STATE: Optional[GraalPyProvisioningState] = None


def _posix_quote(value: Path | str) -> str:
    return shlex.quote(str(value))


def _detect_graalpy_executable() -> Optional[Path]:
    candidates: Iterable[Path] = []
    env_home = os.environ.get("GRAALPY_HOME")
    if env_home:
        root = Path(env_home)
        candidates = (
            root / "bin" / "graalpy",
            root / "bin" / "graalpy.exe",
            root / "Scripts" / "graalpy.exe",
        )
    else:
        candidates = ()
    names = ("graalpy", "graalpy.exe", "graalpy.bat")
    resolved: list[Path] = []
    for name in names:
        path = shutil.which(name)
        if path:
            resolved.append(Path(path))
    for candidate in list(candidates) + resolved:
        if candidate and candidate.exists():
            return candidate
    return None


def _ensure_graalpy_installed() -> Path:
    executable = _detect_graalpy_executable()
    if executable is not None:
        return executable
    subprocess.check_call([sys.executable, "-m", "pip", "install", "graalpy"])
    executable = _detect_graalpy_executable()
    if executable is None:
        raise RuntimeError(
            "GraalPy installation completed but no interpreter executable could be located."
        )
    return executable


def _run_graalpy(executable: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(executable), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed: "
            + " ".join(_posix_quote(part) for part in [executable, *arguments])
            + "\n"
            + result.stdout.strip()
            + ("\n" if result.stdout.strip() else "")
            + result.stderr.strip()
        )
    return result


def _graalpy_version(executable: Path) -> str:
    result = _run_graalpy(executable, ["--version"])
    return result.stdout.strip() or result.stderr.strip()


def _pip_show_version(executable: Path, package: str) -> str:
    result = _run_graalpy(executable, ["-m", "pip", "show", package])
    for line in result.stdout.splitlines():
        if line.lower().startswith("version:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


class GraalPyPackagePreparer:
    """Ensure GraalPy specific Python packages are built for the host system."""

    def __init__(self, executable: Path, *, base_dir: Optional[Path] = None) -> None:
        self.executable = executable
        self.base_dir = base_dir or Path(__file__).resolve().parents[2]
        self.manifest_directory = self.base_dir / "lib" / "graalpy"
        self.manifest_directory.mkdir(parents=True, exist_ok=True)

    def prepare(self) -> GraalPyProvisioningState:
        pillow_command = ["-m", "pip", "install", "--no-binary", ":all:", "Pillow"]
        _run_graalpy(self.executable, pillow_command)
        pillow_version = _pip_show_version(self.executable, "Pillow")
        graal_version = _graalpy_version(self.executable)
        manifest = {
            "platform": platform.system(),
            "architecture": platform.machine(),
            "graalpy_version": graal_version,
            "pillow_version": pillow_version,
            "executable": str(self.executable),
        }
        manifest_path = self.manifest_directory / "pillow_build.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf8")
        return GraalPyProvisioningState(
            executable=self.executable,
            platform=manifest["platform"],
            architecture=manifest["architecture"],
            graalpy_version=graal_version,
            pillow_version=pillow_version,
            manifest_path=manifest_path,
        )


class _GraalPyPackageHandle:
    """Lazy package descriptor used by :class:`GraalPyBackend`."""

    def __init__(self, backend: "GraalPyBackend", name: str) -> None:
        self._backend = backend
        self._name = name

    def resolve(self, attribute: str) -> Any:
        full = f"{self._name}.{attribute}"
        try:
            return self._backend.jclass(full)
        except RuntimeError:
            return _GraalPyPackageHandle(self._backend, full)


class GraalPyBackend(JavaIntegrationBackend):
    name = "graalpy"

    def __init__(self) -> None:
        self._java_module: Any | None = None

    # -- lifecycle ---------------------------------------------------------
    def ensure_bridge(self) -> None:
        if not self.is_bridge_available():
            raise RuntimeError(
                "GraalPy backend requires running under the GraalPy interpreter. "
                "Use the graalpy executable provisioned by the experimental module."
            )

    def is_bridge_available(self) -> bool:
        return platform.python_implementation().lower() == "graalpy"

    def _java(self) -> Any:
        if self._java_module is not None:
            return self._java_module
        try:
            import java  # type: ignore
        except ImportError as exc:  # pragma: no cover - executed under GraalPy
            raise RuntimeError(
                "GraalPy java module is unavailable. Ensure the interpreter was launched via graalpy."
            ) from exc
        self._java_module = java
        return java

    def start_vm(self, classpath_entries: Sequence[Path]) -> None:
        java = self._java()
        add_to_classpath = getattr(java, "add_to_classpath", None)
        if add_to_classpath is None:
            raise RuntimeError("graalpy java.add_to_classpath helper not found.")
        for entry in classpath_entries:
            add_to_classpath(str(entry))

    def is_vm_running(self) -> bool:
        try:
            self._java()
            return True
        except RuntimeError:
            return False

    def shutdown_vm(self) -> None:  # pragma: no cover - GraalPy keeps JVM embedded
        pass

    # -- accessors ---------------------------------------------------------
    def jclass(self, name: str) -> Any:
        java = self._java()
        try:
            return java.type(name)
        except Exception as exc:  # pragma: no cover - real execution under GraalPy
            raise RuntimeError(f"Unable to resolve Java class '{name}' via GraalPy.") from exc

    def jpackage(self, name: str) -> Any:
        return _GraalPyPackageHandle(self, name)

    def package_getattr(self, package: Any, item: str) -> Any:
        if isinstance(package, _GraalPyPackageHandle):
            return package.resolve(item)
        return getattr(package, item)

    def is_package(self, value: Any) -> bool:
        return isinstance(value, _GraalPyPackageHandle)

    def is_class(self, value: Any) -> bool:
        return hasattr(value, "class_")

    def create_proxy(self, interface_name: str, methods: Mapping[str, Callable[..., Any]]) -> Any:
        java = self._java()
        interface = java.type(interface_name)
        implements = getattr(java, "implements", None)
        if implements is None:
            raise RuntimeError("graalpy java.implements helper is unavailable.")

        namespace: Dict[str, Callable[..., Any]] = {}

        def _wrap(callback: Callable[..., Any]) -> Callable[..., Any]:
            def _method(self, *args: Any) -> Any:
                return callback(*args)

            return _method

        for method_name, callback in methods.items():
            namespace[method_name] = _wrap(callback)

        proxy_name = f"GraalPyProxy_{abs(hash((interface_name, tuple(sorted(methods)))))}"
        proxy_class = type(proxy_name, (object,), namespace)
        proxy_class = implements(interface)(proxy_class)
        return proxy_class()

    def create_array(self, component_name: str, values: Sequence[Any]) -> Any:
        java = self._java()
        array_helper = getattr(java, "array", None)
        if array_helper is None:
            raise RuntimeError("graalpy java.array helper is unavailable.")
        component = java.type(component_name)
        return array_helper(component, list(values))

    # -- bootstrap ---------------------------------------------------------
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
        command = f"{_posix_quote(pip_posix)} install --no-binary :all: Pillow"
        if command not in posix:
            posix.append(command)
        windows_command = (
            f"{_windows_quote(str(pip_windows))} install --no-binary :all: Pillow"
        )
        if windows_command not in windows:
            windows.append(windows_command)

    def install_default_dependencies(
        self,
        pip_executable: Path,
        *,
        environment: MutableMapping[str, str],
        logger: Callable[[str], None],
        requirement_files_present: bool,
        editable_targets_present: bool,
    ) -> None:
        _run_pip_with_logger(
            pip_executable,
            ["install", "--no-input", "--no-binary", ":all:", "Pillow"],
            environment,
            logger,
        )


def activate() -> GraalPyProvisioningState:
    """Install GraalPy, rebuild dependencies and switch the JVM backend."""

    global _PREVIOUS_BACKEND, _PROVISIONING_STATE

    executable = _ensure_graalpy_installed()
    preparer = GraalPyPackagePreparer(executable)
    provisioning_state = preparer.prepare()

    if "graalpy" not in available_backends():
        register_backend(GraalPyBackend())

    _PREVIOUS_BACKEND = active_backend().name
    use_backend("graalpy")
    _PROVISIONING_STATE = provisioning_state

    PLUGIN_MANAGER.expose("experimental_graalpy_state", provisioning_state)
    return provisioning_state


def deactivate() -> None:
    """Restore the previously active JVM backend."""

    global _PREVIOUS_BACKEND
    if _PREVIOUS_BACKEND is not None:
        use_backend(_PREVIOUS_BACKEND)
        _PREVIOUS_BACKEND = None
    PLUGIN_MANAGER.expose("experimental_graalpy_state", _PROVISIONING_STATE)


PLUGIN_MANAGER.expose("experimental_graalpy_activate", activate)
PLUGIN_MANAGER.expose("experimental_graalpy_deactivate", deactivate)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.experimental.graalpy_runtime")

