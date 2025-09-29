"""Gateway utilities that manage the JVM lifecycle."""

from __future__ import annotations

import os
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Iterable

from .config import BaseModConfig
from .exceptions import BaseModError, ConfigurationError, JVMNotStartedError

try:  # pragma: no cover - import guard for optional dependency
    import jpype
    import jpype.imports  # noqa: F401
except ImportError as exc:  # pragma: no cover - helpful error messaging
    jpype = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


@dataclass
class JVMGateway(AbstractContextManager["JVMGateway"]):
    """Context manager that guarantees the JVM is started."""

    config: BaseModConfig
    started_here: bool = False

    def __post_init__(self) -> None:
        if jpype is None:
            raise BaseModError(
                "JPype is required to interact with BaseMod. Install the 'jpype1' package first."
            ) from _IMPORT_ERROR
        for path in self.config.compute_classpath():
            if not os.path.exists(path):
                raise ConfigurationError(f"Classpath entry does not exist: {path}")

    # ------------------------------------------------------------------
    # Context manager API
    # ------------------------------------------------------------------
    def __enter__(self) -> "JVMGateway":
        self.ensure_started()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool | None:  # pragma: no cover - trivial
        return None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def ensure_started(self) -> None:
        if not jpype.isJVMStarted():
            classpath = os.pathsep.join(self.config.compute_classpath())
            jpype.startJVM(classpath=classpath, *self.config.jvm_args)
            self.started_here = True

    def shutdown(self) -> None:
        if jpype.isJVMStarted():
            jpype.shutdownJVM()
            self.started_here = False

    def get_class(self, fqcn: str):
        if not jpype.isJVMStarted():
            raise JVMNotStartedError("Attempted to access a Java class before the JVM was started.")
        return jpype.JClass(fqcn)

    def create_proxy(self, interfaces: Iterable[str], inst):
        if not jpype.isJVMStarted():
            raise JVMNotStartedError("Attempted to create a proxy before the JVM was started.")
        return jpype.JProxy(list(interfaces), inst=inst)

    def attach_classpath(self, paths: Iterable[str | os.PathLike[str]]) -> None:
        for path in paths:
            jpype.addClassPath(str(path))


__all__ = ["JVMGateway"]
