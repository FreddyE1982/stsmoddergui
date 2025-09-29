"""Reflection helpers that provide a Pythonic view of BaseMod."""

from __future__ import annotations

from typing import Any, Callable

from .gateway import JVMGateway

try:  # pragma: no cover - optional dependency guard
    import jpype
except ImportError:  # pragma: no cover
    jpype = None  # type: ignore[assignment]


class JavaPackageProxy:
    """Lazy loader around a Java package tree."""

    def __init__(self, gateway: JVMGateway, package_name: str):
        self._gateway = gateway
        self._package_name = package_name

    def __repr__(self) -> str:  # pragma: no cover - representation helper
        return f"<JavaPackageProxy {self._package_name}>"

    def __getattr__(self, item: str) -> Any:
        fqcn = f"{self._package_name}.{item}" if self._package_name else item
        try:
            return self._gateway.get_class(fqcn)
        except Exception:  # pragma: no cover - fallback to package proxy
            return JavaPackageProxy(self._gateway, fqcn)


class BaseModFacade:
    """High level convenience wrapper around ``basemod.BaseMod``."""

    def __init__(self, gateway: JVMGateway):
        self._gateway = gateway
        self._class = gateway.get_class("basemod.BaseMod")

    def __getattr__(self, item: str) -> Any:
        attr = getattr(self._class, item)
        if callable(attr):
            return _wrap_jpype_callable(attr)
        return attr

    def get_subpackage(self, name: str) -> JavaPackageProxy:
        return JavaPackageProxy(self._gateway, f"basemod.{name}")

    def new_proxy(self, interfaces: list[str], inst: Any) -> Any:
        return self._gateway.create_proxy(interfaces, inst)


def _wrap_jpype_callable(java_callable: Any) -> Callable[..., Any]:
    """Wrap JPype callable to make it friendlier to Python tooling."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return java_callable(*args, **kwargs)

    update = {}
    if hasattr(java_callable, "__name__"):
        update["__name__"] = java_callable.__name__
    if hasattr(java_callable, "__doc__"):
        update["__doc__"] = java_callable.__doc__
    for key, value in update.items():
        setattr(wrapper, key, value)
    return wrapper


__all__ = [
    "BaseModFacade",
    "JavaPackageProxy",
]
