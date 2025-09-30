"""Helpers for preparing card art via the StSModdingToolCardImagesCreator."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .loader import BaseModBootstrapError
from plugins import PLUGIN_MANAGER


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "tools"
CARD_IMAGE_TOOL_DIR = TOOLS_ROOT / "StSModdingToolCardImagesCreator"
CARD_IMAGE_TOOL_REPO = "https://github.com/JohnnyBazooka89/StSModdingToolCardImagesCreator.git"
CARD_IMAGE_TOOL_JAR = CARD_IMAGE_TOOL_DIR / "target" / "StSCardImagesCreator" / "StSCardImagesCreator-0.0.5-jar-with-dependencies.jar"

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

        assets_dir = _resolve_cards_asset_directory(project)
        assets_dir.mkdir(parents=True, exist_ok=True)
        dest_small = assets_dir / f"{blueprint.identifier}.png"
        dest_portrait = assets_dir / f"{blueprint.identifier}_p.png"
        shutil.copy2(small_image, dest_small)
        shutil.copy2(portrait_image, dest_portrait)

    resource_path = project.resource_path(f"images/cards/{blueprint.identifier}.png")
    return InnerCardImageResult(resource_path=resource_path, small_asset_path=dest_small, portrait_asset_path=dest_portrait)


PLUGIN_MANAGER.expose("ensure_card_image_tool", ensure_card_image_tool)
PLUGIN_MANAGER.expose("ensure_card_image_tool_built", ensure_card_image_tool_built)
PLUGIN_MANAGER.expose("prepare_inner_card_image", prepare_inner_card_image)
PLUGIN_MANAGER.expose("validate_inner_card_image", validate_inner_card_image)
PLUGIN_MANAGER.expose("ensure_pillow", ensure_pillow)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.card_assets", alias="basemod_card_assets")

__all__ = [
    "InnerCardImageResult",
    "ensure_card_image_tool",
    "ensure_card_image_tool_built",
    "ensure_pillow",
    "prepare_inner_card_image",
    "validate_inner_card_image",
]

