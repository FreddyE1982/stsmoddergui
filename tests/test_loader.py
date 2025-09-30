import json
from pathlib import Path

import pytest

from modules.basemod_wrapper import loader


def test_ensure_basemod_jar_reuses_manifest_cache(monkeypatch, tmp_path):
    calls = {"count": 0}

    def fake_download(url: str, destination: Path) -> None:
        calls["count"] += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("jar", encoding="utf8")

    monkeypatch.setattr(loader, "_download", fake_download)

    first = loader.ensure_basemod_jar(tmp_path)
    assert first.exists()
    assert calls["count"] == 1

    calls["count"] = 0
    second = loader.ensure_basemod_jar(tmp_path)
    assert second == first
    assert calls["count"] == 0

    manifest_path = tmp_path / "lib" / loader.DEPENDENCY_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    assert manifest["basemod"]["latest"]["path"] == str(first)


def test_ensure_modthespire_jar_skips_download_when_present(monkeypatch, tmp_path):
    jar_path = tmp_path / "lib" / loader.MODTHESPIRE_JAR_NAME
    jar_path.parent.mkdir(parents=True, exist_ok=True)
    jar_path.write_text("modthespire", encoding="utf8")

    def fail_download(url: str, destination: Path) -> None:  # pragma: no cover - defensive
        raise AssertionError("Download should not occur when jar already exists")

    monkeypatch.setattr(loader, "_download", fail_download)

    resolved = loader.ensure_modthespire_jar(tmp_path)
    assert resolved == jar_path

    manifest_path = tmp_path / "lib" / loader.DEPENDENCY_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    assert manifest["modthespire"]["latest"]["path"] == str(jar_path)


def test_ensure_desktop_jar_prefers_env_and_search_paths(tmp_path):
    explicit = tmp_path / "explicit" / loader.DESKTOP_JAR_NAME
    explicit.parent.mkdir(parents=True)
    explicit.write_text("desktop", encoding="utf8")

    via_env = tmp_path / "env" / loader.DESKTOP_JAR_NAME
    via_env.parent.mkdir(parents=True)
    via_env.write_text("desktop", encoding="utf8")

    resolved = loader.ensure_desktop_jar(search_paths=[explicit], env={"STS_DESKTOP_JAR": str(via_env)})
    assert resolved == via_env

    resolved_fallback = loader.ensure_desktop_jar(search_paths=[explicit], env={})
    assert resolved_fallback == explicit


def test_ensure_desktop_jar_raises_when_missing(tmp_path):
    with pytest.raises(loader.BaseModBootstrapError):
        loader.ensure_desktop_jar(search_paths=[], env={})
