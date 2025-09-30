"""Utility functions to bootstrap JPype and the BaseMod Java environment."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .java_backend import active_backend


BASEMOD_RELEASE_URL = "https://github.com/daviscook477/BaseMod/releases/latest/download/BaseMod.jar"
BASEMOD_JAR_NAME = "BaseMod.jar"
STSLIB_RELEASE_URL = "https://github.com/kiooeht/StSLib/releases/latest/download/StSLib.jar"
STSLIB_JAR_NAME = "StSLib.jar"
MODTHESPIRE_RELEASE_URL = "https://github.com/kiooeht/ModTheSpire/releases/latest/download/ModTheSpire.zip"
MODTHESPIRE_JAR_NAME = "ModTheSpire.jar"
DESKTOP_JAR_NAME = "desktop-1.0.jar"
DEPENDENCY_MANIFEST_NAME = "dependency_manifest.json"


class BaseModBootstrapError(RuntimeError):
    """Raised when the BaseMod wrapper cannot be initialised."""


def ensure_jpype() -> None:
    """Ensure that the active JVM bridge is ready for use."""

    ensure_java_bridge()


def ensure_java_bridge() -> None:
    """Ensure the configured JVM bridge dependencies are installed."""

    backend = active_backend()
    backend.ensure_bridge()


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, destination.open("wb") as target:
        shutil.copyfileobj(response, target)


def _manifest_path(base_dir: Path) -> Path:
    return base_dir / "lib" / DEPENDENCY_MANIFEST_NAME


def _load_manifest(base_dir: Path) -> Dict[str, Dict[str, Dict[str, str]]]:
    manifest_path = _manifest_path(base_dir)
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf8"))
        except json.JSONDecodeError:
            pass
    return {}


def _save_manifest(base_dir: Path, manifest: Dict[str, Dict[str, Dict[str, str]]]) -> None:
    manifest_path = _manifest_path(base_dir)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf8")


def _jar_filename(default_name: str, version: Optional[str]) -> str:
    if not version:
        return default_name
    stem = Path(default_name).stem
    suffix = Path(default_name).suffix
    clean_version = version.replace("/", "-")
    return f"{stem}-{clean_version}{suffix}"


def _manifest_lookup(
    manifest: Dict[str, Dict[str, Dict[str, str]]],
    dependency: str,
    version_key: str,
) -> Optional[Path]:
    entry = manifest.get(dependency, {}).get(version_key)
    if not entry:
        return None
    path = Path(entry.get("path", ""))
    if path.exists():
        return path
    return None


def _manifest_store(
    manifest: Dict[str, Dict[str, Dict[str, str]]],
    dependency: str,
    version_key: str,
    *,
    path: Path,
    url: str,
    version_label: str,
) -> None:
    manifest.setdefault(dependency, {})[version_key] = {
        "path": str(path),
        "url": url,
        "version": version_label,
    }


def ensure_basemod_jar(base_dir: Path, version: Optional[str] = None) -> Path:
    """Download the BaseMod jar for ``version`` if it is missing."""

    version_key = version or "latest"
    manifest = _load_manifest(base_dir)
    cached = _manifest_lookup(manifest, "basemod", version_key)
    if cached:
        return cached
    jar_name = _jar_filename(BASEMOD_JAR_NAME, version)
    jar_path = base_dir / "lib" / jar_name
    if not jar_path.exists():
        _download(BASEMOD_RELEASE_URL, jar_path)
    _manifest_store(
        manifest,
        "basemod",
        version_key,
        path=jar_path,
        url=BASEMOD_RELEASE_URL,
        version_label=version or "latest",
    )
    _save_manifest(base_dir, manifest)
    return jar_path


def ensure_stslib_jar(base_dir: Path, version: Optional[str] = None) -> Path:
    """Download the StSLib jar for ``version`` if it is missing."""

    version_key = version or "latest"
    manifest = _load_manifest(base_dir)
    cached = _manifest_lookup(manifest, "stslib", version_key)
    if cached:
        return cached
    jar_name = _jar_filename(STSLIB_JAR_NAME, version)
    jar_path = base_dir / "lib" / jar_name
    if not jar_path.exists():
        _download(STSLIB_RELEASE_URL, jar_path)
    _manifest_store(
        manifest,
        "stslib",
        version_key,
        path=jar_path,
        url=STSLIB_RELEASE_URL,
        version_label=version or "latest",
    )
    _save_manifest(base_dir, manifest)
    return jar_path


def ensure_modthespire_jar(base_dir: Path, version: Optional[str] = None) -> Path:
    """Download and extract the ModTheSpire jar for ``version`` if needed."""

    version_key = version or "latest"
    manifest = _load_manifest(base_dir)
    cached = _manifest_lookup(manifest, "modthespire", version_key)
    if cached:
        return cached

    jar_name = _jar_filename(MODTHESPIRE_JAR_NAME, version)
    jar_path = base_dir / "lib" / jar_name
    if jar_path.exists():
        manifest.setdefault("modthespire", {})[version_key] = {
            "path": str(jar_path),
            "url": MODTHESPIRE_RELEASE_URL,
            "version": version or "latest",
        }
        _save_manifest(base_dir, manifest)
        return jar_path

    archive_fd, archive_name = tempfile.mkstemp(prefix="modthespire", suffix=".zip")
    archive_path = Path(archive_name)
    os.close(archive_fd)
    try:
        _download(MODTHESPIRE_RELEASE_URL, archive_path)
        with zipfile.ZipFile(archive_path) as archive:
            with archive.open(MODTHESPIRE_JAR_NAME) as source, jar_path.open("wb") as target:
                shutil.copyfileobj(source, target)
    finally:
        try:
            archive_path.unlink()
        except FileNotFoundError:
            pass
    _manifest_store(
        manifest,
        "modthespire",
        version_key,
        path=jar_path,
        url=MODTHESPIRE_RELEASE_URL,
        version_label=version or "latest",
    )
    _save_manifest(base_dir, manifest)
    return jar_path


def start_jvm(classpath_entries: Sequence[Path]) -> None:
    """Start the JVM with the given classpath if it is not already running."""

    backend = active_backend()
    backend.ensure_bridge()
    backend.start_vm(tuple(classpath_entries))


def ensure_basemod_environment(
    base_dir: Optional[Path] = None,
    *,
    extra_classpath: Optional[Sequence[Path]] = None,
    basemod_version: Optional[str] = None,
    stslib_version: Optional[str] = None,
    modthespire_version: Optional[str] = None,
) -> Dict[str, Path]:
    """Ensure that the BaseMod + StSLib environment is ready for use."""

    base_dir = base_dir or Path(__file__).resolve().parent
    ensure_java_bridge()
    basemod_jar = ensure_basemod_jar(base_dir, version=basemod_version)
    stslib_jar = ensure_stslib_jar(base_dir, version=stslib_version)
    modthespire_jar = ensure_modthespire_jar(base_dir, version=modthespire_version)
    classpath = [basemod_jar, stslib_jar, modthespire_jar]
    if extra_classpath:
        classpath.extend(extra_classpath)
    start_jvm(classpath)
    return {"basemod": basemod_jar, "stslib": stslib_jar, "modthespire": modthespire_jar}


def ensure_dependency_classpath(
    base_dir: Optional[Path] = None,
    *,
    basemod_version: Optional[str] = None,
    stslib_version: Optional[str] = None,
    modthespire_version: Optional[str] = None,
) -> Dict[str, Path]:
    """Return a mapping of core dependency jars without starting the JVM."""

    base_dir = base_dir or Path(__file__).resolve().parent
    return {
        "basemod": ensure_basemod_jar(base_dir, version=basemod_version),
        "stslib": ensure_stslib_jar(base_dir, version=stslib_version),
        "modthespire": ensure_modthespire_jar(base_dir, version=modthespire_version),
    }


def ensure_desktop_jar(
    *, search_paths: Optional[Sequence[Path]] = None, env: Optional[Dict[str, str]] = None
) -> Path:
    """Locate ``desktop-1.0.jar`` across common install paths."""

    env = env or os.environ  # type: ignore[assignment]
    candidates: List[Path] = []
    manual = env.get("STS_DESKTOP_JAR") or env.get("SLAYTHESPIRE_DESKTOP")
    if manual:
        candidates.append(Path(manual))
    home = Path(env.get("SLAYTHESPIRE_HOME", ""))
    if home:
        candidates.append(Path(home) / DESKTOP_JAR_NAME)
    if search_paths:
        candidates.extend(Path(path) for path in search_paths)
    user_home = Path.home()
    default_locations: Iterable[Path] = (
        user_home / ".local/share/Steam/steamapps/common/SlayTheSpire" / DESKTOP_JAR_NAME,
        user_home
        / "Library/Application Support/Steam/steamapps/common/SlayTheSpire"
        / DESKTOP_JAR_NAME,
        Path("C:/Program Files (x86)/Steam/steamapps/common/SlayTheSpire")
        / DESKTOP_JAR_NAME,
        Path("C:/Program Files/Steam/steamapps/common/SlayTheSpire")
        / DESKTOP_JAR_NAME,
        Path("/Applications/SlayTheSpire.app/Contents/Resources") / DESKTOP_JAR_NAME,
    )
    candidates.extend(default_locations)
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise BaseModBootstrapError(
        "Unable to locate desktop-1.0.jar. Set STS_DESKTOP_JAR or install via Steam/GOG."
    )


__all__ = [
    "BaseModBootstrapError",
    "ensure_jpype",
    "ensure_java_bridge",
    "ensure_basemod_jar",
    "ensure_basemod_environment",
    "ensure_dependency_classpath",
    "start_jvm",
    "ensure_stslib_jar",
    "ensure_modthespire_jar",
    "ensure_desktop_jar",
]
