"""Plugin used by tests to capture card type registration broadcasts."""

from __future__ import annotations

from typing import List, Tuple


class CardTypeListenerPlugin:
    """Collects registry events emitted by the card type system."""

    def __init__(self) -> None:
        self.name = "card_type_listener"
        self.events: List[Tuple[str, object, object]] = []

    def on_card_type_registered(self, *, record, registry):
        self.events.append(("registered", record, registry))
        return {"event": "registered", "identifier": record.identifier}

    def on_card_type_unregistered(self, *, record, registry):
        self.events.append(("unregistered", record, registry))
        return {"event": "unregistered", "identifier": record.identifier}


def setup_plugin(manager, exposed):
    """Register the listener plugin with the global plugin manager."""

    plugin = CardTypeListenerPlugin()
    manager.expose("card_type_listener", plugin)
    return plugin
