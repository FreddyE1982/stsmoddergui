"""Helpers for inspecting and bootstrapping bundled Python runtimes.

This module makes it easier for documentation and tooling to instruct
teammates on how to activate the Python half of a bundled mod.  Bundles
produced by :func:`modules.modbuilder.Character.createMod` ship the Python
package next to the compiled patch jar.  Testers still need to provision a
Python interpreter with JPype installed and make sure the generated
``entrypoint`` module is reachable at game launch.

The helpers below keep that workflow declarative:

* :func:`discover_python_runtime` inspects a bundle directory and returns a
  :class:`PythonRuntimeDescriptor` describing the Python package, entrypoint
  module and any dependency manifests (``requirements.txt`` / ``pyproject``).
* :class:`PythonRuntimeDescriptor.bootstrap_plan` manufactures
  copy-paste-ready command sequences for POSIX and Windows shells so teams can
  set up virtual environments, install JPype and point ``PYTHONPATH`` at the
  bundled sources without guesswork.

The functions are exported through the global plugin manager so downstream
tooling and documentation renderers can surface the same guidance.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
from typing import Dict, Iterator, List, Optional, Tuple

from plugins import PLUGIN_MANAGER


class PythonRuntimeError(RuntimeError):
    """Raised when a bundled Python runtime cannot be resolved."""


def _posix_quote(path: Path | str) -> str:
    """Return a shell-escaped representation suitable for POSIX shells."""

    return shlex.quote(str(path))


def _windows_quote(path: Path | str) -> str:
    """Return a quoted representation suitable for ``cmd.exe``."""

    text = str(path)
    if not text:
        return '""'
    if text.startswith('"') and text.endswith('"'):
        return text
    return f'"{text}"'


def _iter_requirement_files(python_root: Path, package_root: Path) -> Iterator[Path]:
    """Yield requirement manifests shipped with the bundle."""

    searched: set[Path] = set()
    candidate_dirs: Tuple[Path, ...] = (
        python_root,
        package_root,
        package_root.parent,
    )
    names: Tuple[str, ...] = (
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-dev.in",
        "requirements.in",
    )
    for directory in candidate_dirs:
        for name in names:
            candidate = directory / name
            if candidate.exists() and candidate not in searched:
                searched.add(candidate)
                yield candidate


def _iter_editable_targets(package_root: Path) -> Iterator[Path]:
    """Yield package directories that should be installed in editable mode."""

    markers = ("pyproject.toml", "setup.cfg", "setup.py")
    for marker in markers:
        if (package_root / marker).exists():
            yield package_root
            break


@dataclass(frozen=True)
class PlatformBootstrap:
    """Command set tailored for a particular operating system."""

    create_virtualenv: str
    install_dependencies: Tuple[str, ...]
    configure_pythonpath: str
    verify_runtime: str

    def commands(self) -> Tuple[str, ...]:
        """Return the commands in execution order."""

        return (
            self.create_virtualenv,
            *self.install_dependencies,
            self.configure_pythonpath,
            self.verify_runtime,
        )


@dataclass(frozen=True)
class PythonRuntimeBootstrapPlan:
    """Concrete instructions for getting the Python runtime ready."""

    descriptor: "PythonRuntimeDescriptor"
    venv_directory: Path
    posix: PlatformBootstrap
    windows: PlatformBootstrap

    def environment_variables(self) -> Dict[str, str]:
        """Return environment variables required for launching the mod."""

        return {"PYTHONPATH": str(self.descriptor.python_root)}

    def as_dict(self) -> Dict[str, object]:
        """Serialise the plan for docs, logging or JSON output."""

        return {
            "package": self.descriptor.package_name,
            "entrypoint": str(self.descriptor.entrypoint),
            "python_root": str(self.descriptor.python_root),
            "venv_directory": str(self.venv_directory),
            "posix": {
                "create_virtualenv": self.posix.create_virtualenv,
                "install_dependencies": list(self.posix.install_dependencies),
                "configure_pythonpath": self.posix.configure_pythonpath,
                "verify_runtime": self.posix.verify_runtime,
            },
            "windows": {
                "create_virtualenv": self.windows.create_virtualenv,
                "install_dependencies": list(self.windows.install_dependencies),
                "configure_pythonpath": self.windows.configure_pythonpath,
                "verify_runtime": self.windows.verify_runtime,
            },
            "environment": self.environment_variables(),
        }


@dataclass(frozen=True)
class PythonRuntimeDescriptor:
    """High level description of the Python runtime shipped with a bundle."""

    bundle_root: Path
    python_root: Path
    package_name: str
    package_root: Path
    entrypoint: Path
    requirement_files: Tuple[Path, ...]
    editable_targets: Tuple[Path, ...]

    def bootstrap_plan(
        self,
        *,
        venv_directory: Optional[Path] = None,
        python_launcher_posix: str = "python3",
        python_launcher_windows: str = "py -3",
    ) -> PythonRuntimeBootstrapPlan:
        """Return command sequences for activating the runtime.

        ``python_launcher_posix`` and ``python_launcher_windows`` allow callers to
        tailor the bootstrap commands to their team's conventions (for example
        substituting ``python`` for ``python3`` on macOS).
        """

        venv_directory = venv_directory or (self.bundle_root / ".venv")

        posix_install: List[str] = []
        windows_install: List[str] = []

        pip_posix = venv_directory / "bin" / "pip"
        pip_windows = venv_directory / "Scripts" / "pip.exe"

        requirement_args_posix: List[str] = []
        requirement_args_windows: List[str] = []
        for requirement in self.requirement_files:
            requirement_args_posix.append(f"-r {_posix_quote(requirement)}")
            requirement_args_windows.append(f"-r {_windows_quote(requirement)}")

        if requirement_args_posix:
            posix_install.append(
                f"{_posix_quote(pip_posix)} install {' '.join(requirement_args_posix)}"
            )
            windows_install.append(
                f"{_windows_quote(pip_windows)} install {' '.join(requirement_args_windows)}"
            )

        for editable in self.editable_targets:
            posix_install.append(
                f"{_posix_quote(pip_posix)} install -e {_posix_quote(editable)}"
            )
            windows_install.append(
                f"{_windows_quote(pip_windows)} install -e {_windows_quote(editable)}"
            )

        if not posix_install:
            posix_install.append(f"{_posix_quote(pip_posix)} install JPype1")
        if not windows_install:
            windows_install.append(f"{_windows_quote(pip_windows)} install JPype1")

        python_posix = venv_directory / "bin" / "python"
        python_windows = venv_directory / "Scripts" / "python.exe"

        posix = PlatformBootstrap(
            create_virtualenv=f"{python_launcher_posix} -m venv {_posix_quote(venv_directory)}",
            install_dependencies=tuple(posix_install),
            configure_pythonpath=(
                "export PYTHONPATH=\"${PYTHONPATH:+$PYTHONPATH:}" f"{_posix_quote(self.python_root)}\""
            ),
            verify_runtime=f"{_posix_quote(python_posix)} -m {self.package_name}.entrypoint",
        )

        windows = PlatformBootstrap(
            create_virtualenv=f"{python_launcher_windows} -m venv {_windows_quote(venv_directory)}",
            install_dependencies=tuple(windows_install),
            configure_pythonpath=(
                f"set PYTHONPATH=%PYTHONPATH%;{_windows_quote(self.python_root)}"
            ),
            verify_runtime=f"{_windows_quote(python_windows)} -m {self.package_name}.entrypoint",
        )

        return PythonRuntimeBootstrapPlan(self, venv_directory, posix, windows)


def discover_python_runtime(bundle_root: Path, package_name: Optional[str] = None) -> PythonRuntimeDescriptor:
    """Inspect ``bundle_root`` and describe the shipped Python runtime.

    ``bundle_root`` should point to the directory produced by
    :func:`modules.modbuilder.Character.createMod` (the folder that also houses
    ``ModTheSpire.json`` and the compiled patch jar).
    """

    bundle_root = bundle_root.resolve()
    if not bundle_root.exists():
        raise PythonRuntimeError(f"Bundle directory '{bundle_root}' does not exist.")

    python_root = bundle_root / "python"
    if not python_root.exists():
        raise PythonRuntimeError(
            f"Bundle directory '{bundle_root}' does not contain a python/ folder."
        )

    candidates: Dict[str, Path] = {}
    for child in python_root.iterdir():
        if not child.is_dir():
            continue
        entrypoint = child / "entrypoint.py"
        init_py = child / "__init__.py"
        if entrypoint.exists() and init_py.exists():
            candidates[child.name] = child

    if not candidates:
        raise PythonRuntimeError(
            f"No Python package with an entrypoint.py was found under '{python_root}'."
        )

    target_name: Optional[str] = package_name
    if target_name is None:
        if len(candidates) > 1:
            available = ", ".join(sorted(candidates))
            raise PythonRuntimeError(
                "Multiple Python packages were found. Specify package_name explicitly. "
                f"Available packages: {available}."
            )
        target_name = next(iter(candidates))
    if target_name not in candidates:
        available = ", ".join(sorted(candidates))
        raise PythonRuntimeError(
            f"Package '{target_name}' not found in bundle. Available packages: {available}."
        )

    package_root = candidates[target_name]
    entrypoint = package_root / "entrypoint.py"

    requirement_files = tuple(_iter_requirement_files(python_root, package_root))
    editable_targets = tuple(_iter_editable_targets(package_root))

    descriptor = PythonRuntimeDescriptor(
        bundle_root=bundle_root,
        python_root=python_root,
        package_name=target_name,
        package_root=package_root,
        entrypoint=entrypoint,
        requirement_files=requirement_files,
        editable_targets=editable_targets,
    )
    return descriptor


PLUGIN_MANAGER.expose("discover_python_runtime", discover_python_runtime)
PLUGIN_MANAGER.expose("PythonRuntimeDescriptor", PythonRuntimeDescriptor)
PLUGIN_MANAGER.expose("PythonRuntimeBootstrapPlan", PythonRuntimeBootstrapPlan)
PLUGIN_MANAGER.expose("PlatformBootstrap", PlatformBootstrap)
PLUGIN_MANAGER.expose_module("modules.modbuilder.runtime_env")


__all__ = [
    "PythonRuntimeError",
    "PlatformBootstrap",
    "PythonRuntimeBootstrapPlan",
    "PythonRuntimeDescriptor",
    "discover_python_runtime",
]

