"""High level JPype wrapper that exposes the BaseMod API for Python users."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .loader import ensure_basemod_environment, ensure_jpype
from .project import BundleOptions, ModProject, compileandbundle, create_project

ensure_jpype()
from .proxy import JavaPackageWrapper, create_package_wrapper
from plugins import PLUGIN_MANAGER


class BaseModEnvironment:
    """Lifecycle manager around the BaseMod JVM runtime.

    Instances of this class take care of preparing the JVM, downloading the
    BaseMod release and exposing Java packages in a pythonic way.  The default
    environment is created eagerly at module import so end users can simply do::

        from modules.basemod_wrapper import basemod
        basemod.BaseMod.subscribe(my_python_listener)

    The wrapper automatically handles functional interfaces and iterable
    conversion so Python callables can be passed where Java expects a functional
    interface.
    """

    DEFAULT_PACKAGES: Iterable[str] = (
        "basemod",
        "com.megacrit.cardcrawl",
        "com.badlogic.gdx",
        "com.evacipated.cardcrawl.modthespire",
    )

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parent
        ensure_basemod_environment(self.base_dir)
        self._packages: dict[str, JavaPackageWrapper] = {}

        for package in self.DEFAULT_PACKAGES:
            self.package(package)

    def package(self, name: str) -> JavaPackageWrapper:
        """Return a :class:`JavaPackageWrapper` for ``name``."""

        if name not in self._packages:
            self._packages[name] = create_package_wrapper(name)
        return self._packages[name]

    # Convenience attribute access -------------------------------------------------
    def __getattr__(self, item: str) -> JavaPackageWrapper:
        return self.package(item)


# Eagerly create the default environment and expose frequently used packages.
_ENVIRONMENT = BaseModEnvironment()
basemod: JavaPackageWrapper = _ENVIRONMENT.package("basemod")
cardcrawl: JavaPackageWrapper = _ENVIRONMENT.package("com.megacrit.cardcrawl")
modthespire: JavaPackageWrapper = _ENVIRONMENT.package(
    "com.evacipated.cardcrawl.modthespire"
)
libgdx: JavaPackageWrapper = _ENVIRONMENT.package("com.badlogic.gdx")

# Share everything with the plugin manager.
PLUGIN_MANAGER.expose("basemod_environment", _ENVIRONMENT)
PLUGIN_MANAGER.expose("basemod", basemod)
PLUGIN_MANAGER.expose("cardcrawl", cardcrawl)
PLUGIN_MANAGER.expose("modthespire", modthespire)
PLUGIN_MANAGER.expose("libgdx", libgdx)
PLUGIN_MANAGER.expose("create_project", create_project)
PLUGIN_MANAGER.expose("compileandbundle", compileandbundle)
PLUGIN_MANAGER.expose("ModProject", ModProject)
PLUGIN_MANAGER.expose("BundleOptions", BundleOptions)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper", alias="basemod_wrapper")

__all__ = [
    "BaseModEnvironment",
    "basemod",
    "cardcrawl",
    "modthespire",
    "libgdx",
    "ModProject",
    "BundleOptions",
    "create_project",
    "compileandbundle",
]
