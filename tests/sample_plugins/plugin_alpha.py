"""Minimal plugin used by the auto discovery tests."""

class DemoPlugin:
    """Simple plugin object that records broadcast calls."""

    def __init__(self) -> None:
        self.name = "demo_alpha"
        self.received: list[tuple[str, tuple, dict]] = []

    def ping(self, *args, **kwargs):
        self.received.append(("ping", args, kwargs))
        return {"args": args, "kwargs": kwargs}


def setup_plugin(manager, exposed):
    """Entry point used by :func:`plugins.PluginManager.register_plugin`."""

    plugin = DemoPlugin()
    manager.expose("demo_plugin_alpha", plugin)
    return plugin
