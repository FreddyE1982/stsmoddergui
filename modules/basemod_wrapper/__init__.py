"""Python wrapper that mirrors the BaseMod API via JPype."""

from __future__ import annotations

import sys
from typing import Any, Mapping, Optional

from stsmoddergui import GLOBAL_PLUGIN_REGISTRY, PluginContext

from .config import BaseModConfig
from .exceptions import BaseModError, ConfigurationError
from .gateway import JVMGateway
from .proxies import ProxyFactory
from .reflection import BaseModFacade, JavaPackageProxy

__all__ = [
    "BaseModConfig",
    "BaseModFacade",
    "BaseModError",
    "ConfigurationError",
    "JavaPackageProxy",
    "ProxyFactory",
    "activate_plugin",
    "configure",
    "ensure_basemod",
    "get_facade",
    "get_gateway",
    "get_package",
    "get_proxy_factory",
    "shutdown",
]

_config: Optional[BaseModConfig] = None
_gateway: Optional[JVMGateway] = None
_facade: Optional[BaseModFacade] = None
_proxy_factory: Optional[ProxyFactory] = None


def configure(config: BaseModConfig | Mapping[str, Any] | None = None, **overrides: Any) -> None:
    """Configure the BaseMod wrapper.

    Parameters
    ----------
    config:
        Either a :class:`BaseModConfig` instance or a mapping that can be
        coerced into one.
    **overrides:
        Keyword overrides that will be applied on top of ``config``.  The
        supported keys mirror the dataclass fields of
        :class:`BaseModConfig`.
    """

    global _config, _gateway, _facade, _proxy_factory

    if config is None:
        config = BaseModConfig.from_env()
    elif isinstance(config, Mapping):
        data = dict(config)
        data.update(overrides)
        config = BaseModConfig.from_mapping(data)
    elif overrides:
        data = config.to_mapping()
        data.update(overrides)
        config = BaseModConfig.from_mapping(data)

    if not isinstance(config, BaseModConfig):
        raise TypeError("config must be a BaseModConfig or mapping")

    _config = config
    _gateway = JVMGateway(config)
    _facade = None
    _proxy_factory = None
    GLOBAL_PLUGIN_REGISTRY.refresh()


def ensure_basemod() -> BaseModFacade:
    """Ensure the JVM is running and return the BaseMod facade."""

    global _facade
    gateway = get_gateway()
    gateway.ensure_started()
    if _facade is None:
        _facade = BaseModFacade(gateway)
    return _facade


def get_gateway() -> JVMGateway:
    """Return the configured :class:`JVMGateway`."""

    if _gateway is None:
        if _config is None:
            raise ConfigurationError("BaseMod wrapper has not been configured. Call configure() first.")
        configure(_config)
        if _gateway is None:
            raise ConfigurationError("Failed to initialise BaseMod gateway.")
    return _gateway


def get_facade() -> BaseModFacade:
    return ensure_basemod()


def get_package(name: str = "basemod") -> JavaPackageProxy:
    gateway = get_gateway()
    gateway.ensure_started()
    return JavaPackageProxy(gateway, name)


def get_proxy_factory() -> ProxyFactory:
    global _proxy_factory
    gateway = get_gateway()
    gateway.ensure_started()
    if _proxy_factory is None:
        _proxy_factory = ProxyFactory(gateway)
    return _proxy_factory


def shutdown() -> None:
    gateway = get_gateway()
    gateway.shutdown()


def activate_plugin(context: PluginContext) -> None:
    """Plugin hook so the wrapper can enrich the global API."""

    context.api.setdefault("variables", {})["modules.basemod_wrapper.config"] = _config
    context.api.setdefault("variables", {})["modules.basemod_wrapper.gateway"] = _gateway
    context.api.setdefault("variables", {})["modules.basemod_wrapper.facade"] = _facade
    context.api.setdefault("variables", {})["modules.basemod_wrapper.proxy_factory"] = _proxy_factory


# Initialise with default configuration placeholder so plugin registry works
if _config is None:
    try:  # pragma: no cover - best effort default configuration from env
        configure()
    except Exception:
        pass

try:  # pragma: no cover - plugin auto registration
    GLOBAL_PLUGIN_REGISTRY.register_from_module(sys.modules[__name__])
except Exception:
    pass
