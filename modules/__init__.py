"""Module namespace initialisation for repository provided libraries."""
from __future__ import annotations

from plugins import PLUGIN_MANAGER  # pragma: no cover

PLUGIN_MANAGER.expose("modules", __name__)

__all__ = ["PLUGIN_MANAGER"]
