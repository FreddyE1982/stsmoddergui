"""Top-level package for the stsmoddergui toolkit.

This package exposes the global plugin registry which allows
extensions to hook into every portion of the repository.
"""

from __future__ import annotations

from .plugin_manager import GLOBAL_PLUGIN_REGISTRY, PluginContext, PluginDescriptor

__all__ = [
    "GLOBAL_PLUGIN_REGISTRY",
    "PluginContext",
    "PluginDescriptor",
]
