import types

import pytest

import plugins
from plugins import PluginError, PluginManager


@pytest.fixture()
def isolated_manager():
    """Return a fresh plugin manager for isolated tests."""

    manager = PluginManager()
    yield manager
    manager._plugins.clear()
    manager._exposed.clear()
    manager._export_subscribers.clear()


def test_auto_discover_registers_plugins(isolated_manager):
    discovered = isolated_manager.auto_discover("tests.sample_plugins")
    assert "tests.sample_plugins.plugin_alpha" in discovered
    assert "tests.sample_plugins.nested.cool_plugin" in discovered
    record = discovered["tests.sample_plugins.plugin_alpha"]
    assert record.name == "demo_alpha"
    assert "demo_plugin_alpha" in isolated_manager.exposed


def test_auto_discover_respects_match_callable(isolated_manager):
    discovered = isolated_manager.auto_discover(
        "tests.sample_plugins",
        match=lambda name: name.endswith("plugin_alpha"),
    )
    assert set(discovered) == {"tests.sample_plugins.plugin_alpha"}


def test_subscribe_to_exports_replays_repository_state(monkeypatch):
    manager = PluginManager()
    fake_manifest = types.SimpleNamespace(diff=lambda *a, **k: {"plugins": {"setup_plugin": object()}})
    monkeypatch.setitem(plugins.__dict__, "_REPOSITORY_ATTRIBUTE_MANIFEST", fake_manifest)

    events = []

    def callback(exposure_diff, repository_diff, snapshot):
        events.append((exposure_diff, repository_diff, snapshot))

    manager.subscribe_to_exports(callback)
    assert "plugins" in events[0][1]
    assert "setup_plugin" in events[0][1]["plugins"]


def test_refresh_repository_exports_notifies_subscribers(monkeypatch):
    manager = PluginManager()
    events = []

    def callback(exposure_diff, repository_diff, snapshot):
        events.append((exposure_diff, repository_diff))

    fake_calls = {"count": 0}

    def fake_diff(module_name=None, initial=False):
        fake_calls["count"] += 1
        return {"modules.basemod_wrapper.cards": {"SimpleCardBlueprint": object()}}

    monkeypatch.setitem(
        plugins.__dict__,
        "_REPOSITORY_ATTRIBUTE_MANIFEST",
        types.SimpleNamespace(diff=fake_diff),
    )

    manager.subscribe_to_exports(callback, replay=False)
    diff = manager.refresh_repository_exports()

    assert fake_calls["count"] == 1
    assert diff["modules.basemod_wrapper.cards"]
    assert events[0][1]["modules.basemod_wrapper.cards"]


def test_auto_discover_requires_package_directory(monkeypatch, tmp_path):
    manager = PluginManager()
    path = tmp_path / "plugins"
    path.mkdir()
    with pytest.raises(PluginError):
        manager.auto_discover(path)


def test_expose_notifies_subscribers(monkeypatch):
    manager = PluginManager()
    fake_manifest = types.SimpleNamespace(diff=lambda *a, **k: {})
    monkeypatch.setitem(plugins.__dict__, "_REPOSITORY_ATTRIBUTE_MANIFEST", fake_manifest)

    events = []

    def callback(exposure_diff, repository_diff, snapshot):
        events.append(exposure_diff)

    manager.subscribe_to_exports(callback, replay=False)
    marker = object()
    manager.expose("example", marker)

    assert events[-1] == {"example": marker}


def test_refresh_repository_exports_handles_bootstrap_gap(monkeypatch):
    manager = PluginManager()
    monkeypatch.delitem(plugins.__dict__, "_REPOSITORY_ATTRIBUTE_MANIFEST", raising=False)

    diff = manager.refresh_repository_exports()

    assert diff == {}
