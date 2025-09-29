"""Utility functions to bootstrap JPype and the BaseMod Java environment."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

import urllib.request


BASEMOD_RELEASE_URL = "https://github.com/daviscook477/BaseMod/releases/latest/download/BaseMod.jar"
BASEMOD_JAR_NAME = "BaseMod.jar"


class BaseModBootstrapError(RuntimeError):
    """Raised when the BaseMod wrapper cannot be initialised."""


def ensure_jpype() -> None:
    """Ensure that JPype is available, installing it on demand."""

    try:
        import jpype  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover - installation path
        subprocess.check_call([sys.executable, "-m", "pip", "install", "JPype1"])
        import jpype  # type: ignore  # noqa: F401


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, destination.open("wb") as target:
        shutil.copyfileobj(response, target)


def ensure_basemod_jar(base_dir: Path) -> Path:
    """Download the BaseMod jar if it is missing."""

    jar_path = base_dir / "lib" / BASEMOD_JAR_NAME
    if not jar_path.exists():
        _download(BASEMOD_RELEASE_URL, jar_path)
    return jar_path


def start_jvm(classpath_entries: Iterable[Path]) -> None:
    """Start the JVM with the given classpath if it is not already running."""

    import jpype

    if jpype.isJVMStarted():
        return

    classpath = os.pathsep.join(str(entry) for entry in classpath_entries)
    jpype.startJVM(classpath=[classpath])

    # Enable import hooks once the JVM is up.
    import jpype.imports  # noqa: F401


def ensure_basemod_environment(base_dir: Optional[Path] = None) -> Path:
    """Ensure that the BaseMod environment is ready for use."""

    base_dir = base_dir or Path(__file__).resolve().parent
    ensure_jpype()
    jar_path = ensure_basemod_jar(base_dir)
    start_jvm([jar_path])
    return jar_path


__all__ = [
    "BaseModBootstrapError",
    "ensure_jpype",
    "ensure_basemod_jar",
    "ensure_basemod_environment",
    "start_jvm",
]
