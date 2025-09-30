"""Helpers for preparing card art via the StSModdingToolCardImagesCreator."""
from __future__ import annotations

import shutil
import subprocess
import sys
import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from .loader import BaseModBootstrapError
from plugins import PLUGIN_MANAGER


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "tools"
CARD_IMAGE_TOOL_DIR = TOOLS_ROOT / "StSModdingToolCardImagesCreator"
CARD_IMAGE_TOOL_REPO = "https://github.com/JohnnyBazooka89/StSModdingToolCardImagesCreator.git"
CARD_IMAGE_TOOL_JAR = CARD_IMAGE_TOOL_DIR / "target" / "StSCardImagesCreator" / "StSCardImagesCreator-0.0.5-jar-with-dependencies.jar"
INNER_CARD_MANIFEST_NAME = ".inner_card_manifest.json"

_CARD_TYPE_TO_FOLDER = {
    "ATTACK": "Attacks",
    "SKILL": "Skills",
    "POWER": "Powers",
}


ImageModule = Any


def ensure_pillow() -> ImageModule:
    """Return :mod:`PIL.Image`, installing Pillow on demand."""

    try:
        from PIL import Image  # type: ignore import
    except ImportError:  # pragma: no cover - dependency bootstrap
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "Pillow"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        from PIL import Image  # type: ignore import
    return Image


def ensure_card_image_tool() -> Path:
    """Clone the card image tool repository if necessary and return its path."""

    if CARD_IMAGE_TOOL_DIR.exists():
        return CARD_IMAGE_TOOL_DIR
    TOOLS_ROOT.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", CARD_IMAGE_TOOL_REPO, str(CARD_IMAGE_TOOL_DIR)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return CARD_IMAGE_TOOL_DIR


def ensure_card_image_tool_built() -> Path:
    """Ensure the image tool has been compiled and return the jar path."""

    ensure_card_image_tool()
    if CARD_IMAGE_TOOL_JAR.exists():
        return CARD_IMAGE_TOOL_JAR
    subprocess.run(
        ["mvn", "-q", "package"],
        check=True,
        cwd=str(CARD_IMAGE_TOOL_DIR),
    )
    if not CARD_IMAGE_TOOL_JAR.exists():  # pragma: no cover - defensive path
        raise BaseModBootstrapError("Failed to build card image processing tool jar.")
    return CARD_IMAGE_TOOL_JAR


def validate_inner_card_image(path: Path) -> Path:
    """Validate that ``path`` points to a 500x380 PNG image."""

    image_module = ensure_pillow()
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise BaseModBootstrapError(f"inner card image '{path}' does not exist.")
    with image_module.open(resolved) as handle:  # type: ignore[attr-defined]
        width, height = handle.size
    if width != 500 or height != 380:
        raise BaseModBootstrapError("innerCardImage MUST be 500x380")
    return resolved


def _resolve_cards_asset_directory(project: "ModProject") -> Path:
    if getattr(project, "layout", None):
        return Path(project.layout.cards_image_root)  # type: ignore[attr-defined]
    fallback = REPO_ROOT / "assets" / project.mod_id / "images" / "cards"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


@dataclass(slots=True)
class InnerCardImageResult:
    """Holds the processed image paths for a blueprint."""

    resource_path: str
    small_asset_path: Path
    portrait_asset_path: Path


def prepare_inner_card_image(project: "ModProject", blueprint: "SimpleCardBlueprint") -> InnerCardImageResult:
    """Run the Java tool for ``blueprint`` and place the outputs in assets."""

    if not blueprint.inner_image_source:
        raise BaseModBootstrapError("No inner card image registered on blueprint.")

    jar_path = ensure_card_image_tool_built()
    source_path = Path(blueprint.inner_image_source)
    if blueprint.card_type not in _CARD_TYPE_TO_FOLDER:
        raise BaseModBootstrapError(f"Unsupported card type '{blueprint.card_type}' for inner card images.")

    assets_dir = _resolve_cards_asset_directory(project)
    assets_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_inner_card_manifest(assets_dir)

    digest = _hash_file(source_path)
    dest_small = assets_dir / f"{blueprint.identifier}.png"
    dest_portrait = assets_dir / f"{blueprint.identifier}_p.png"
    resource_path = project.resource_path(f"images/cards/{blueprint.identifier}.png")

    if not _reuse_cached_inner_art(manifest, digest, dest_small, dest_portrait):
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            cards_dir = work_dir / "cards"
            cards_dir.mkdir(parents=True, exist_ok=True)
            copied_name = source_path.name
            shutil.copy2(source_path, cards_dir / copied_name)

            subprocess.run(["java", "-jar", str(jar_path)], cwd=str(work_dir), check=True)

            folder_name = _CARD_TYPE_TO_FOLDER[blueprint.card_type]
            output_dir = work_dir / "images" / folder_name
            small_image = output_dir / copied_name
            portrait_image = output_dir / f"{source_path.stem}_p{source_path.suffix}"
            if not small_image.exists() or not portrait_image.exists():
                raise BaseModBootstrapError("Processed card images were not generated as expected.")

            shutil.copy2(small_image, dest_small)
            shutil.copy2(portrait_image, dest_portrait)

    _update_inner_card_manifest(
        manifest,
        digest,
        blueprint.identifier,
        source_path,
        dest_small,
        dest_portrait,
        resource_path,
    )
    _save_inner_card_manifest(assets_dir, manifest)

    return InnerCardImageResult(resource_path=resource_path, small_asset_path=dest_small, portrait_asset_path=dest_portrait)


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _manifest_path(directory: Path) -> Path:
    return directory / INNER_CARD_MANIFEST_NAME


def _load_inner_card_manifest(directory: Path) -> Dict[str, Any]:
    path = _manifest_path(directory)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf8"))
        except json.JSONDecodeError:
            pass
    return {"hashes": {}, "cards": {}}


def _save_inner_card_manifest(directory: Path, manifest: Dict[str, Any]) -> None:
    path = _manifest_path(directory)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf8")


def _reuse_cached_inner_art(
    manifest: Dict[str, Any], digest: str, dest_small: Path, dest_portrait: Path
) -> bool:
    entry = manifest.get("hashes", {}).get(digest)
    if not entry:
        return False
    small_path = Path(entry.get("small", ""))
    portrait_path = Path(entry.get("portrait", ""))
    if not small_path.exists() or not portrait_path.exists():
        return False
    shutil.copy2(small_path, dest_small)
    shutil.copy2(portrait_path, dest_portrait)
    return True


def _update_inner_card_manifest(
    manifest: Dict[str, Any],
    digest: str,
    identifier: str,
    source_path: Path,
    dest_small: Path,
    dest_portrait: Path,
    resource_path: str,
) -> None:
    hashes = manifest.setdefault("hashes", {})
    cards = manifest.setdefault("cards", {})
    hashes[digest] = {
        "source": str(source_path),
        "small": str(dest_small),
        "portrait": str(dest_portrait),
        "resource": resource_path,
    }
    cards[identifier] = {
        "hash": digest,
        "small": str(dest_small),
        "portrait": str(dest_portrait),
        "resource": resource_path,
    }


def load_inner_card_manifest(project: "ModProject") -> Dict[str, Any]:
    """Return the manifest describing processed inner card art."""

    directory = _resolve_cards_asset_directory(project)
    directory.mkdir(parents=True, exist_ok=True)
    return _load_inner_card_manifest(directory)


PLUGIN_MANAGER.expose("ensure_card_image_tool", ensure_card_image_tool)
PLUGIN_MANAGER.expose("ensure_card_image_tool_built", ensure_card_image_tool_built)
PLUGIN_MANAGER.expose("prepare_inner_card_image", prepare_inner_card_image)
PLUGIN_MANAGER.expose("validate_inner_card_image", validate_inner_card_image)
PLUGIN_MANAGER.expose("ensure_pillow", ensure_pillow)
PLUGIN_MANAGER.expose("load_inner_card_manifest", load_inner_card_manifest)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.card_assets", alias="basemod_card_assets")

__all__ = [
    "InnerCardImageResult",
    "ensure_card_image_tool",
    "ensure_card_image_tool_built",
    "ensure_pillow",
    "prepare_inner_card_image",
    "validate_inner_card_image",
    "load_inner_card_manifest",
]

