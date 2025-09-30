"""Nested plugin used to ensure recursive discovery works."""

from dataclasses import dataclass, field


@dataclass
class CoolPlugin:
    name: str = "cool_nested"
    calls: list = field(default_factory=list)

    def ping(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return "cool"


def setup_plugin(manager, exposed):
    plugin = CoolPlugin()
    manager.expose("cool_plugin", plugin)
    return plugin
