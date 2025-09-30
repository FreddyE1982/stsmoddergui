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
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import (
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
)

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

    def python_executable(self, platform: Optional[str] = None) -> Path:
        """Return the Python launcher inside the managed virtual environment."""

        target = _normalise_platform(platform)
        if target == "windows":
            return self.venv_directory / "Scripts" / "python.exe"
        return self.venv_directory / "bin" / "python"

    def pip_executable(self, platform: Optional[str] = None) -> Path:
        """Return the pip launcher inside the managed virtual environment."""

        target = _normalise_platform(platform)
        if target == "windows":
            return self.venv_directory / "Scripts" / "pip.exe"
        return self.venv_directory / "bin" / "pip"

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


def _normalise_platform(platform: Optional[str]) -> str:
    if platform is None:
        return "windows" if os.name == "nt" else "posix"
    candidate = platform.lower()
    if candidate not in {"windows", "posix"}:
        raise PythonRuntimeError(f"Unsupported platform '{platform}'.")
    return candidate


def _ensure_virtualenv(venv_directory: Path, *, logger: Callable[[str], None]) -> None:
    marker = venv_directory / "pyvenv.cfg"
    if marker.exists():
        logger(f"Virtual environment already present at {venv_directory}.")
        return
    logger(f"Creating virtual environment at {venv_directory}.")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_directory)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise PythonRuntimeError(
            "Failed to create virtual environment:\n" f"{result.stderr.strip()}"
        )


def _run_pip(
    pip_executable: Path,
    arguments: Sequence[str],
    *,
    env: Mapping[str, str],
    logger: Callable[[str], None],
) -> None:
    command = [str(pip_executable), *arguments]
    logger("Executing: " + " ".join(shlex.quote(part) for part in command))
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(env),
    )
    if result.returncode != 0:
        raise PythonRuntimeError(
            "pip command failed:\n"
            + result.stdout.strip()
            + ("\n" if result.stdout.strip() else "")
            + result.stderr.strip()
        )


def _prepare_environment(
    base: Optional[MutableMapping[str, str]],
    python_root: Path,
    *,
    extra_env: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    environment: Dict[str, str] = dict(base or os.environ)
    pythonpath = environment.get("PYTHONPATH", "")
    python_root_text = str(python_root)
    if pythonpath:
        if python_root_text not in pythonpath.split(os.pathsep):
            environment["PYTHONPATH"] = os.pathsep.join([pythonpath, python_root_text])
    else:
        environment["PYTHONPATH"] = python_root_text
    if extra_env:
        environment.update({str(key): str(value) for key, value in extra_env.items()})
    return environment


def _invoke_entrypoint(
    plan: PythonRuntimeBootstrapPlan,
    *,
    platform: str,
    environment: Mapping[str, str],
    logger: Callable[[str], None],
) -> None:
    python_executable = plan.python_executable(platform)
    command = [str(python_executable), "-m", f"{plan.descriptor.package_name}.entrypoint"]
    logger("Executing: " + " ".join(shlex.quote(part) for part in command))
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(environment),
    )
    if result.returncode != 0:
        raise PythonRuntimeError(
            "Entrypoint execution failed:\n"
            + result.stdout.strip()
            + ("\n" if result.stdout.strip() else "")
            + result.stderr.strip()
        )


def execute_bootstrap_plan(
    plan: PythonRuntimeBootstrapPlan,
    *,
    platform: Optional[str] = None,
    extra_env: Optional[Mapping[str, str]] = None,
    logger: Optional[Callable[[str], None]] = None,
    skip_entrypoint: bool = False,
) -> None:
    """Execute ``plan`` by creating the venv, installing deps and running the entrypoint."""

    logger = logger or print
    target_platform = _normalise_platform(platform)
    _ensure_virtualenv(plan.venv_directory, logger=logger)

    pip_executable = plan.pip_executable(target_platform)
    environment = os.environ.copy()
    for requirements in plan.descriptor.requirement_files:
        _run_pip(
            pip_executable,
            ["install", "--no-input", "-r", str(requirements)],
            env=environment,
            logger=logger,
        )
    for editable in plan.descriptor.editable_targets:
        _run_pip(
            pip_executable,
            ["install", "--no-input", "-e", str(editable)],
            env=environment,
            logger=logger,
        )
    if not plan.descriptor.requirement_files and not plan.descriptor.editable_targets:
        _run_pip(
            pip_executable,
            ["install", "--no-input", "JPype1"],
            env=environment,
            logger=logger,
        )

    runtime_env = _prepare_environment(environment, plan.descriptor.python_root, extra_env=extra_env)

    if skip_entrypoint:
        return

    _invoke_entrypoint(
        plan,
        platform=target_platform,
        environment=runtime_env,
        logger=logger,
    )


def bootstrap_python_runtime(
    bundle_root: Path,
    *,
    package_name: Optional[str] = None,
    venv_directory: Optional[Path] = None,
    platform: Optional[str] = None,
    extra_env: Optional[Mapping[str, str]] = None,
    logger: Optional[Callable[[str], None]] = None,
    skip_entrypoint: bool = False,
) -> PythonRuntimeDescriptor:
    """Discover and bootstrap the Python runtime for ``bundle_root`` immediately."""

    descriptor = discover_python_runtime(bundle_root, package_name)
    plan = descriptor.bootstrap_plan(venv_directory=venv_directory)
    execute_bootstrap_plan(
        plan,
        platform=platform,
        extra_env=extra_env,
        logger=logger,
        skip_entrypoint=skip_entrypoint,
    )
    return descriptor


def write_runtime_bootstrapper(
    target_directory: Path,
    *,
    script_name: str = "bootstrap_mod.py",
) -> Path:
    """Write a convenience launcher script into ``target_directory``."""

    path = target_directory / script_name
    path.write_text(BOOTSTRAPPER_TEMPLATE, encoding="utf8")
    return path


def _cli_plan(descriptor: PythonRuntimeDescriptor, *, output_json: bool) -> None:
    plan = descriptor.bootstrap_plan()
    if output_json:
        print(json.dumps(plan.as_dict(), indent=2))
        return
    print(f"Bundle: {descriptor.bundle_root}")
    print(f"Python package: {descriptor.package_name}")
    print(f"Virtualenv: {plan.venv_directory}")
    print("POSIX bootstrap commands:")
    for command in plan.posix.commands():
        print(f"  {command}")
    print("Windows bootstrap commands:")
    for command in plan.windows.commands():
        print(f"  {command}")


def _cli_launch(args: "argparse.Namespace") -> None:
    descriptor = bootstrap_python_runtime(
        Path(args.bundle),
        package_name=args.package,
        venv_directory=Path(args.venv) if args.venv else None,
        platform=args.platform,
        skip_entrypoint=args.skip_entrypoint,
    )
    print(
        f"Python runtime for '{descriptor.package_name}' ready at "
        f"{descriptor.bundle_root / '.venv'}"
    )


def _cli(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Bootstrap bundled Python runtimes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Print the bootstrap commands for a bundle")
    plan_parser.add_argument("bundle", type=str, help="Path to the bundled mod directory")
    plan_parser.add_argument("--package", type=str, default=None, help="Override the Python package name")
    plan_parser.add_argument("--json", action="store_true", help="Emit the plan as JSON")

    launch_parser = subparsers.add_parser(
        "launch", help="Automatically create the venv, install dependencies and run the entrypoint"
    )
    launch_parser.add_argument("bundle", type=str, help="Path to the bundled mod directory")
    launch_parser.add_argument("--package", type=str, default=None, help="Override the Python package name")
    launch_parser.add_argument(
        "--venv", type=str, default=None, help="Custom location for the virtual environment"
    )
    launch_parser.add_argument(
        "--platform",
        type=str,
        default=None,
        choices=("posix", "windows"),
        help="Force platform specific behaviour (defaults to host)",
    )
    launch_parser.add_argument(
        "--skip-entrypoint",
        action="store_true",
        help="Prepare the runtime without executing the entrypoint",
    )

    args = parser.parse_args(argv)
    if args.command == "plan":
        descriptor = discover_python_runtime(Path(args.bundle), args.package)
        _cli_plan(descriptor, output_json=args.json)
        return 0
    if args.command == "launch":
        _cli_launch(args)
        return 0
    return 1


def main() -> None:
    """Entry-point for ``python -m modules.modbuilder.runtime_env``."""

    raise SystemExit(_cli())


PLUGIN_MANAGER.expose("discover_python_runtime", discover_python_runtime)
PLUGIN_MANAGER.expose("PythonRuntimeDescriptor", PythonRuntimeDescriptor)
PLUGIN_MANAGER.expose("PythonRuntimeBootstrapPlan", PythonRuntimeBootstrapPlan)
PLUGIN_MANAGER.expose("PlatformBootstrap", PlatformBootstrap)
PLUGIN_MANAGER.expose("bootstrap_python_runtime", bootstrap_python_runtime)
PLUGIN_MANAGER.expose("execute_bootstrap_plan", execute_bootstrap_plan)
PLUGIN_MANAGER.expose("write_runtime_bootstrapper", write_runtime_bootstrapper)
PLUGIN_MANAGER.expose_module("modules.modbuilder.runtime_env")


__all__ = [
    "PythonRuntimeError",
    "PlatformBootstrap",
    "PythonRuntimeBootstrapPlan",
    "PythonRuntimeDescriptor",
    "bootstrap_python_runtime",
    "execute_bootstrap_plan",
    "write_runtime_bootstrapper",
    "discover_python_runtime",
    "main",
]

BOOTSTRAPPER_TEMPLATE = """#!/usr/bin/env python3
\"\"\"One-click bootstrapper for bundled Slay the Spire mods.\"\"\"
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path


def _iter_requirement_files(python_root: Path, package_root: Path) -> list[Path]:
    searched: set[Path] = set()
    result: list[Path] = []
    directories = (python_root, package_root, package_root.parent)
    names = (
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-dev.in",
        "requirements.in",
    )
    for directory in directories:
        for name in names:
            candidate = directory / name
            if candidate.exists() and candidate not in searched:
                searched.add(candidate)
                result.append(candidate)
    return result


def _iter_editable_targets(package_root: Path) -> list[Path]:
    markers = ("pyproject.toml", "setup.cfg", "setup.py")
    for marker in markers:
        if (package_root / marker).exists():
            return [package_root]
    return []


def _run_pip(pip_executable: Path, arguments: list[str]) -> None:
    command = [str(pip_executable), "install", "--no-input", *arguments]
    print("$ " + " ".join(shlex.quote(part) for part in command))
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            "pip command failed (status {status})\n{stdout}{stderr}".format(
                status=result.returncode,
                stdout=(result.stdout or "").strip(),
                stderr=("\n" + (result.stderr or "").strip()) if result.stderr else "",
            )
        )


def _ensure_virtualenv(venv_directory: Path) -> None:
    marker = venv_directory / "pyvenv.cfg"
    if marker.exists():
        print(f"Reusing virtual environment at {venv_directory}")
        return
    print(f"Creating virtual environment at {venv_directory}")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_directory)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            "Virtual environment creation failed (status {status})\n{stderr}".format(
                status=result.returncode,
                stderr=(result.stderr or "").strip(),
            )
        )


def _python_executable(venv_directory: Path) -> Path:
    if os.name == "nt":
        return venv_directory / "Scripts" / "python.exe"
    return venv_directory / "bin" / "python"


def _pip_executable(venv_directory: Path) -> Path:
    if os.name == "nt":
        return venv_directory / "Scripts" / "pip.exe"
    return venv_directory / "bin" / "pip"


def _bootstrap(bundle_root: Path) -> str:
    bundle_root = bundle_root.resolve()
    python_root = bundle_root / "python"
    if not python_root.exists():
        raise SystemExit(f"Bundle directory '{bundle_root}' does not contain a python/ folder.")

    packages = [
        child
        for child in python_root.iterdir()
        if child.is_dir()
        and (child / "entrypoint.py").exists()
        and (child / "__init__.py").exists()
    ]
    if not packages:
        raise SystemExit("No Python package with an entrypoint.py was found under 'python/'.")
    if len(packages) > 1:
        names = ", ".join(sorted(package.name for package in packages))
        raise SystemExit(
            "Multiple Python packages were found. Specify package_name explicitly. Available packages: "
            + names
        )

    package_root = packages[0]
    package_name = package_root.name
    venv_directory = bundle_root / ".venv"
    _ensure_virtualenv(venv_directory)

    pip_executable = _pip_executable(venv_directory)
    requirement_files = _iter_requirement_files(python_root, package_root)
    editable_targets = _iter_editable_targets(package_root)

    for requirement in requirement_files:
        _run_pip(pip_executable, ["-r", str(requirement)])
    for editable in editable_targets:
        _run_pip(pip_executable, ["-e", str(editable)])
    if not requirement_files and not editable_targets:
        _run_pip(pip_executable, ["JPype1"])

    python_executable = _python_executable(venv_directory)
    environment = os.environ.copy()
    python_root_text = str(python_root)
    pythonpath = environment.get("PYTHONPATH")
    if pythonpath:
        environment["PYTHONPATH"] = pythonpath + os.pathsep + python_root_text
    else:
        environment["PYTHONPATH"] = python_root_text

    print(f"Executing entrypoint for {package_name}")
    result = subprocess.run(
        [str(python_executable), "-m", f"{package_name}.entrypoint"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    if result.returncode != 0:
        raise SystemExit(
            "Entrypoint execution failed (status {status})\n{stdout}{stderr}".format(
                status=result.returncode,
                stdout=(result.stdout or "").strip(),
                stderr=("\n" + (result.stderr or "").strip()) if result.stderr else "",
            )
        )
    return package_name


def main() -> None:
    bundle_root = Path.cwd()
    try:
        from modules.modbuilder.runtime_env import bootstrap_python_runtime  # type: ignore
    except Exception:
        package_name = _bootstrap(bundle_root)
    else:
        descriptor = bootstrap_python_runtime(bundle_root)
        package_name = descriptor.package_name
    print(f"Python runtime initialised for '{package_name}' at {bundle_root / '.venv'}")


if __name__ == "__main__":
    main()
"""


