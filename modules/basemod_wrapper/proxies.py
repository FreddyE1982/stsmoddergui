"""Factories that turn Python callables into Java interface proxies."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

from .gateway import JVMGateway


class ProxyFactory:
    """Factory class that simplifies creation of Java proxies."""

    def __init__(self, gateway: JVMGateway):
        self._gateway = gateway

    def callable(self, interface: str, func: Callable[..., Any]) -> Any:
        return self._gateway.create_proxy([interface], _CallableAdapter(func))

    def mapping(self, interfaces: Iterable[str], mapping: Mapping[str, Callable[..., Any]]) -> Any:
        return self._gateway.create_proxy(list(interfaces), mapping)


class _CallableAdapter:
    """Adapter that maps any method call to a single Python callable."""

    def __init__(self, func: Callable[..., Any]):
        self._func = func

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._func(*args, **kwargs)

    def __getattr__(self, item: str) -> Callable[..., Any]:  # pragma: no cover - delegation helper
        def method(*args: Any, **kwargs: Any) -> Any:
            return self._func(item, *args, **kwargs)

        return method


__all__ = ["ProxyFactory"]
