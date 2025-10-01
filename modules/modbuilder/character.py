from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
import json
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Type, Union

from modules.basemod_wrapper.card_assets import ensure_pillow
from modules.basemod_wrapper.cards import SimpleCardBlueprint, build_card_localizations
from modules.basemod_wrapper.loader import BaseModBootstrapError, ensure_dependency_classpath
from modules.basemod_wrapper.project import (
    BundleOptions,
    BundlePackaging,
    CharacterAssets,
    CharacterBlueprint,
    ModProject,
    create_project,
)

from .analytics import build_deck_analytics
from .deck import Deck
from plugins import PLUGIN_MANAGER


ColorTuple = Tuple[float, float, float, float]
RARITY_TARGETS: Mapping[str, float] = {"COMMON": 0.60, "UNCOMMON": 0.37, "RARE": 0.03}
CHARACTER_VALIDATION_HOOK = "modbuilder_character_validate"


@dataclass(slots=True)
class CharacterStartConfig:
    hp: int = 72
    max_hp: Optional[int] = None
    gold: int = 99
    deck: Optional[Union[Type[Deck], Deck]] = None
    relics: List[str] = field(default_factory=list)


@dataclass(slots=True)
class CharacterImageConfig:
    shoulder1: Optional[str] = None
    shoulder2: Optional[str] = None
    corpse: Optional[str] = None
    staticspineanimation: Optional[str] = None
    staticspineatlas: Optional[str] = None
    staticspinejson: Optional[str] = None
    energy_orb: Optional[str] = None
    banner: Optional[str] = None
    select: Optional[str] = None


@dataclass(slots=True)
class CharacterColorConfig:
    identifier: Optional[str] = None
    card_color: Optional[ColorTuple] = None
    trail_color: Optional[ColorTuple] = None
    slash_color: Optional[ColorTuple] = None
    attack_bg: Optional[str] = None
    skill_bg: Optional[str] = None
    power_bg: Optional[str] = None
    orb: Optional[str] = None
    attack_bg_small: Optional[str] = None
    skill_bg_small: Optional[str] = None
    power_bg_small: Optional[str] = None
    orb_small: Optional[str] = None


@dataclass(frozen=True)
class CharacterDeckSnapshot:
    """Immutable view over the decks attached to a character."""

    start_deck: Type[Deck]
    unlockable_deck: Optional[Type[Deck]]
    start_cards: Tuple[SimpleCardBlueprint, ...]
    unlockable_cards: Tuple[SimpleCardBlueprint, ...]
    all_cards: Tuple[SimpleCardBlueprint, ...]
    unique_cards: Mapping[str, SimpleCardBlueprint]

    @property
    def total_cards(self) -> int:
        return len(self.all_cards)


@dataclass
class CharacterValidationReport:
    """Container collecting validation errors and plugin supplied context."""

    errors: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        cleaned = str(message).strip()
        if cleaned:
            self.errors.append(cleaned)

    def extend_errors(self, messages: Iterable[str]) -> None:
        for message in messages:
            self.add_error(message)

    def merge(self, other: "CharacterValidationReport") -> None:
        self.extend_errors(other.errors)
        for key, value in other.context.items():
            existing = self.context.get(key)
            if isinstance(existing, dict) and isinstance(value, dict):
                existing.update(value)
            else:
                self.context[key] = value

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def format_errors(self) -> str:
        return " ".join(self.errors)


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "mod"


class Character:
    """High level helper that wires decks and assets into a mod project."""

    def __init__(self) -> None:
        name = self.__class__.__name__
        self.name: str = name
        self.mod_id: str = _slugify(name)
        self.author: str = "Unknown"
        self.description: str = ""
        self.version: str = "0.1.0"
        self.handSize: int = 5
        self.energyPerTurn: int = 3
        self.orbSlots: int = 0
        self.maxhp: int = 72
        self.loadout_description: str = ""
        self.banner_image: Optional[str] = None
        self.select_button_image: Optional[str] = None
        self.energy_image: Optional[str] = None
        self.campfire_x: float = 0.0
        self.campfire_y: float = 0.0
        self.loadout_x: float = 220.0
        self.loadout_y: float = 300.0

        self.start = CharacterStartConfig()
        self.image = CharacterImageConfig()
        self.color = CharacterColorConfig(identifier=f"{self.mod_id.upper()}_COLOR")

        self.unlockableDeck: Optional[Union[Type[Deck], Deck]] = None
        self.assets_root: Optional[Path] = None
        self.python_root: Optional[Path] = None
        self.bundle_dependencies: Sequence[str] = ("basemod", "stslib")
        self.additional_classpath: Sequence[Path] = ()
        self.desktop_jar: Optional[Path] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @classmethod
    def createMod(
        cls,
        destination: Union[str, Path],
        *,
        assets_root: Optional[Union[str, Path]] = None,
        python_source: Optional[Union[str, Path]] = None,
        bundle: bool = True,
        dependencies: Optional[Sequence[str]] = None,
        additional_classpath: Optional[Sequence[Path]] = None,
        java_classpath: Optional[Sequence[Path]] = None,
        register_cards: bool = True,
        packaging: Union[str, BundlePackaging] = BundlePackaging.DIRECTORY,
    ) -> Path:
        character = cls()
        assets_root_path = cls._resolve_assets_root(character, assets_root)
        python_source_path = cls._resolve_python_source(cls, character, python_source)

        decks = cls.collect_cards(character)
        report = cls.validate(character, decks=decks, assets_root=assets_root_path)
        if not report.is_valid:
            raise BaseModBootstrapError(report.format_errors())

        start_cards = list(decks.start_cards)
        unlockable_cards = list(decks.unlockable_cards)
        unique_cards = decks.unique_cards

        cls._prepare_static_spine(character, assets_root_path)
        cls._write_card_localizations(character, assets_root_path, unique_cards)

        if bundle and not register_cards:
            raise BaseModBootstrapError("Cards must be registered when bundling the mod.")

        project: Optional[ModProject]
        project = None
        if register_cards or bundle:
            project = cls._build_project(character)
            cls._apply_color(character, project)
            for blueprint in unique_cards.values():
                project.add_simple_card(blueprint)

            blueprint = cls._build_character_blueprint(character, start_cards)
            project.add_character(blueprint)

        output_root = Path(destination).resolve()
        output_root.mkdir(parents=True, exist_ok=True)

        bundle_dependencies = dependencies or character.bundle_dependencies
        extra_classpath = list(character.additional_classpath)
        if additional_classpath:
            extra_classpath.extend(additional_classpath)

        if not bundle:
            mod_name = character.name.replace(" ", "")
            return output_root / mod_name

        if project is None:
            raise BaseModBootstrapError("Project setup was skipped; unable to bundle.")
        options = cls._build_bundle_options(
            character,
            assets_root_path,
            python_source_path,
            output_root,
            bundle_dependencies,
            java_classpath,
            extra_classpath,
            packaging,
        )
        return project.compile_and_bundle(options)

    # ------------------------------------------------------------------
    # Helper construction
    # ------------------------------------------------------------------
    @classmethod
    def collect_cards(cls, character: "Character") -> CharacterDeckSnapshot:
        """Return the current deck configuration for ``character``."""

        start_deck_cls = cls._coerce_deck(character.start.deck, "start")
        unlockable_deck_cls = cls._coerce_deck(character.unlockableDeck, "unlockable")

        if start_deck_cls is None:
            raise BaseModBootstrapError("Characters must declare a start deck before bundling.")

        start_cards = tuple(start_deck_cls.cards())
        unlockable_cards = (
            tuple(unlockable_deck_cls.cards()) if unlockable_deck_cls is not None else tuple()
        )
        all_cards = start_cards + unlockable_cards
        unique_cards = MappingProxyType(
            cls._compute_unique_cards(start_cards, unlockable_cards)
        )
        return CharacterDeckSnapshot(
            start_deck=start_deck_cls,
            unlockable_deck=unlockable_deck_cls,
            start_cards=start_cards,
            unlockable_cards=unlockable_cards,
            all_cards=all_cards,
            unique_cards=unique_cards,
        )

    @classmethod
    def validate(
        cls,
        character: "Character",
        *,
        decks: Optional[CharacterDeckSnapshot] = None,
        assets_root: Optional[Union[str, Path]] = None,
    ) -> CharacterValidationReport:
        """Validate deck configuration, rarities and required assets."""

        decks = decks or cls.collect_cards(character)
        report = CharacterValidationReport()

        analytics = build_deck_analytics(
            character,
            decks,
            rarity_targets=RARITY_TARGETS,
        )
        report.context.setdefault("analytics", analytics)
        report.context.setdefault("analytics_table", analytics.as_table())

        count_error = cls._validate_card_totals(decks.all_cards)
        if count_error:
            report.add_error(count_error)
        ratio_error = cls._validate_rarity_ratio(decks.all_cards)
        if ratio_error:
            report.add_error(ratio_error)

        assets_root_path: Optional[Path] = None
        if assets_root is not None:
            assets_root_path = Path(assets_root).resolve()
            asset_error = cls._validate_assets(character, assets_root_path, decks.unique_cards)
            if asset_error:
                report.add_error(asset_error)

        cls._run_validation_hooks(character, decks, report, assets_root_path)
        return report

    @staticmethod
    def _coerce_deck(deck: Optional[Union[Type[Deck], Deck]], label: str) -> Optional[Type[Deck]]:
        if deck is None:
            return None
        if isinstance(deck, Deck):
            return type(deck)
        if isinstance(deck, type) and issubclass(deck, Deck):
            return deck
        raise BaseModBootstrapError(f"{label.capitalize()} deck must inherit from Deck.")

    @staticmethod
    def _compute_unique_cards(
        start_cards: Sequence[SimpleCardBlueprint],
        unlockable_cards: Sequence[SimpleCardBlueprint],
    ) -> Dict[str, SimpleCardBlueprint]:
        mapping: Dict[str, SimpleCardBlueprint] = {}
        for blueprint in list(start_cards) + list(unlockable_cards):
            mapping.setdefault(blueprint.identifier, blueprint)
        return mapping

    @staticmethod
    def _validate_card_totals(cards: Sequence[SimpleCardBlueprint]) -> Optional[str]:
        total = len(cards)
        if total >= 75:
            return None
        missing = 75 - total
        return (
            f"This deck has {total} cards. We need {missing} more cards to be able to compile the mod."
        )

    @classmethod
    def _validate_rarity_ratio(cls, cards: Sequence[SimpleCardBlueprint]) -> Optional[str]:
        actual_counts: Dict[str, int] = {key: 0 for key in RARITY_TARGETS}
        for blueprint in cards:
            rarity = blueprint.rarity.upper()
            if rarity == "BASIC":
                rarity = "COMMON"
            if rarity in actual_counts:
                actual_counts[rarity] += 1
        target_total = max(len(cards), 75)
        targets = cls._compute_target_counts(target_total)
        additions: List[str] = []
        removals: List[str] = []
        for rarity, required in targets.items():
            current = actual_counts.get(rarity, 0)
            diff = required - current
            if diff > 0:
                additions.append(f"{diff} {rarity.lower()}")
            elif diff < 0:
                removals.append(f"{abs(diff)} {rarity.lower()}")
        if not additions and not removals:
            return None
        parts: List[str] = ["Card Rarity Proportions Incorrect."]
        if additions:
            joined = ", ".join(additions)
            parts.append(f"Add the given amount of cards of given type: {joined}.")
        if removals:
            joined = ", ".join(removals)
            parts.append(f"Remove the given amount of cards of given type: {joined}.")
        return " ".join(parts)

    @staticmethod
    def _compute_target_counts(total: int) -> Dict[str, int]:
        raw = {rarity: total * ratio for rarity, ratio in RARITY_TARGETS.items()}
        floors = {rarity: int(math.floor(value)) for rarity, value in raw.items()}
        allocated = sum(floors.values())
        remainder = total - allocated
        ordered = sorted(RARITY_TARGETS, key=lambda key: (raw[key] - floors[key]), reverse=True)
        for rarity in ordered:
            if remainder <= 0:
                break
            floors[rarity] += 1
            remainder -= 1
        return floors

    @classmethod
    def _run_validation_hooks(
        cls,
        character: "Character",
        decks: CharacterDeckSnapshot,
        report: CharacterValidationReport,
        assets_root: Optional[Path],
    ) -> None:
        responses = PLUGIN_MANAGER.broadcast(
            CHARACTER_VALIDATION_HOOK,
            character=character,
            decks=decks,
            report=report,
            assets_root=assets_root,
            character_cls=cls,
        )
        for plugin_name, result in responses.items():
            cls._ingest_validation_response(plugin_name, result, report)

    @staticmethod
    def _ingest_validation_response(
        plugin_name: str, result: Any, report: CharacterValidationReport
    ) -> None:
        if result is None:
            return
        if isinstance(result, CharacterValidationReport):
            report.merge(result)
            return
        if isinstance(result, str):
            report.add_error(result)
            return
        if isinstance(result, Mapping):
            errors = result.get("errors")
            if errors:
                if isinstance(errors, str):
                    report.add_error(errors)
                else:
                    report.extend_errors(errors)
            context_payload = {key: value for key, value in result.items() if key != "errors"}
            if context_payload:
                report.context.setdefault(plugin_name, {}).update(context_payload)
            return
        if isinstance(result, Iterable) and not isinstance(result, (bytes, str)):
            for entry in result:
                if entry is None:
                    continue
                if isinstance(entry, CharacterValidationReport):
                    report.merge(entry)
                elif isinstance(entry, str):
                    report.add_error(entry)
                else:
                    raise BaseModBootstrapError(
                        f"Plugin '{plugin_name}' returned unsupported validation entry: {entry!r}"
                    )
            return
        raise BaseModBootstrapError(
            f"Plugin '{plugin_name}' returned unsupported validation response: {result!r}"
        )

    @classmethod
    def _validate_assets(
        cls,
        character: "Character",
        assets_root: Path,
        cards: Mapping[str, SimpleCardBlueprint],
    ) -> Optional[str]:
        mod_id = character.mod_id
        missing_cards: Dict[str, List[str]] = {}
        for identifier, blueprint in cards.items():
            issues: List[str] = []
            if blueprint.inner_image_source:
                inner_path = Path(blueprint.inner_image_source)
                if not inner_path.exists():
                    issues.append(f"inner image '{inner_path}' is missing")
            image_resource = blueprint.image or f"{mod_id}/images/cards/{blueprint.identifier}.png"
            resolved = cls._resource_path(image_resource, assets_root, mod_id)
            if not resolved.exists():
                if not (blueprint.inner_image_source and blueprint.image is None):
                    issues.append(f"card image '{resolved}' is missing")
            if issues:
                missing_cards[identifier] = issues
        asset_issues: List[str] = []
        if character.image.shoulder1:
            asset_issues.extend(
                cls._missing_asset_messages(
                    "shoulder image",
                    character.image.shoulder1,
                    assets_root,
                    mod_id,
                )
            )
        if character.image.shoulder2:
            asset_issues.extend(
                cls._missing_asset_messages(
                    "shoulder2 image",
                    character.image.shoulder2,
                    assets_root,
                    mod_id,
                )
            )
        if character.image.corpse:
            asset_issues.extend(
                cls._missing_asset_messages(
                    "corpse image",
                    character.image.corpse,
                    assets_root,
                    mod_id,
                )
            )
        if character.image.energy_orb:
            asset_issues.extend(
                cls._missing_asset_messages(
                    "energy orb",
                    character.image.energy_orb,
                    assets_root,
                    mod_id,
                )
            )
        if character.banner_image:
            asset_issues.extend(
                cls._missing_asset_messages(
                    "banner",
                    character.banner_image,
                    assets_root,
                    mod_id,
                )
            )
        if character.select_button_image:
            asset_issues.extend(
                cls._missing_asset_messages(
                    "select button",
                    character.select_button_image,
                    assets_root,
                    mod_id,
                )
            )
        if character.energy_image:
            asset_issues.extend(
                cls._missing_asset_messages(
                    "energy image",
                    character.energy_image,
                    assets_root,
                    mod_id,
                )
            )
        for attr in (
            "attack_bg",
            "skill_bg",
            "power_bg",
            "orb",
            "attack_bg_small",
            "skill_bg_small",
            "power_bg_small",
            "orb_small",
        ):
            value = getattr(character.color, attr)
            if value:
                asset_issues.extend(
                    cls._missing_asset_messages(f"color {attr}", value, assets_root, mod_id)
                )
        if character.image.staticspineanimation:
            static_path = cls._resource_path(
                character.image.staticspineanimation,
                assets_root,
                mod_id,
            )
            if not static_path.exists():
                asset_issues.append(f"static spine image '{static_path}' is missing")
        if not missing_cards and not asset_issues:
            return None
        message_parts: List[str] = []
        if missing_cards:
            details = []
            for identifier, issues in sorted(missing_cards.items()):
                blueprint = cards[identifier]
                issues_str = "; ".join(issues)
                details.append(f"- {identifier}: {issues_str} | blueprint={blueprint!r}")
            message_parts.append("Missing assets for cards:\n" + "\n".join(details))
        if asset_issues:
            message_parts.append("Missing character assets: " + "; ".join(sorted(asset_issues)))
        return " ".join(message_parts)

    @staticmethod
    def _missing_asset_messages(label: str, resource: str, assets_root: Path, mod_id: str) -> List[str]:
        resolved = Character._resource_path(resource, assets_root, mod_id)
        if resolved.exists():
            return []
        return [f"{label} '{resolved}' is missing"]

    @staticmethod
    def _resource_path(resource: str, assets_root: Path, mod_id: str) -> Path:
        candidate = Path(resource)
        if candidate.is_absolute():
            return candidate
        cleaned = resource.replace("\\", "/").strip("/")
        prefix = f"{mod_id}/"
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
        resolved = (assets_root / cleaned).resolve()
        try:
            assets_root_resolved = assets_root.resolve()
            resolved.relative_to(assets_root_resolved)
        except Exception:
            pass
        return resolved

    @classmethod
    def _prepare_static_spine(cls, character: "Character", assets_root: Path) -> None:
        if not character.image.staticspineanimation:
            return
        mod_id = character.mod_id
        image_path = cls._resource_path(
            character.image.staticspineanimation,
            assets_root,
            mod_id,
        )
        if not image_path.exists():
            return
        Image = ensure_pillow()
        with Image.open(image_path) as handle:  # type: ignore[attr-defined]
            width, height = handle.size
        atlas_path = image_path.with_suffix(".atlas")
        json_path = image_path.with_suffix(".json")
        region_name = image_path.stem
        atlas_content = (
            f"{image_path.name}\n"
            f"size: {width}, {height}\n"
            "format: RGBA8888\n"
            "filter: Linear,Linear\n"
            "repeat: none\n"
            f"{region_name}\n"
            "  rotate: false\n"
            "  xy: 0, 0\n"
            f"  size: {width}, {height}\n"
            f"  orig: {width}, {height}\n"
            "  offset: 0, 0\n"
            "  index: -1\n"
        )
        atlas_path.write_text(atlas_content, encoding="utf8")
        skeleton = {
            "skeleton": {
                "hash": "",
                "spine": "3.7.94",
                "width": width,
                "height": height,
                "images": "",
            },
            "bones": [{"name": "root"}],
            "slots": [
                {"name": "main", "bone": "root", "attachment": region_name},
            ],
            "skins": {
                "default": {
                    "main": {
                        region_name: {
                            "name": region_name,
                            "path": image_path.name,
                            "x": 0,
                            "y": 0,
                            "width": width,
                            "height": height,
                        }
                    }
                }
            },
            "animations": {"idle": {}},
        }
        json_path.write_text(json.dumps(skeleton, indent=2), encoding="utf8")
        relative_base = character.image.staticspineanimation.replace("\\", "/").strip("/")
        prefix = f"{mod_id}/"
        if relative_base.startswith(prefix):
            relative_base = relative_base[len(prefix) :]
        base_no_ext = Path(relative_base).with_suffix("")
        atlas_resource = f"{mod_id}/{base_no_ext.with_suffix('.atlas')}".replace("\\", "/")
        json_resource = f"{mod_id}/{base_no_ext.with_suffix('.json')}".replace("\\", "/")
        character.image.staticspineatlas = atlas_resource
        character.image.staticspinejson = json_resource

    @classmethod
    def _build_project(cls, character: "Character") -> ModProject:
        project = create_project(
            character.mod_id,
            character.name,
            character.author,
            character.description,
            version=character.version,
        )
        return project

    @classmethod
    def _apply_color(cls, character: "Character", project: ModProject) -> None:
        color = character.color
        required = (
            color.identifier,
            color.card_color,
            color.trail_color,
            color.slash_color,
            color.attack_bg,
            color.skill_bg,
            color.power_bg,
            color.orb,
            color.attack_bg_small,
            color.skill_bg_small,
            color.power_bg_small,
            color.orb_small,
        )
        if any(value is None for value in required):
            raise BaseModBootstrapError("Character colour configuration is incomplete.")
        project.define_color(
            color.identifier,  # type: ignore[arg-type]
            card_color=color.card_color,  # type: ignore[arg-type]
            trail_color=color.trail_color,  # type: ignore[arg-type]
            slash_color=color.slash_color,  # type: ignore[arg-type]
            attack_bg=color.attack_bg,  # type: ignore[arg-type]
            skill_bg=color.skill_bg,  # type: ignore[arg-type]
            power_bg=color.power_bg,  # type: ignore[arg-type]
            orb=color.orb,  # type: ignore[arg-type]
            attack_bg_small=color.attack_bg_small,  # type: ignore[arg-type]
            skill_bg_small=color.skill_bg_small,  # type: ignore[arg-type]
            power_bg_small=color.power_bg_small,  # type: ignore[arg-type]
            orb_small=color.orb_small,  # type: ignore[arg-type]
        )

    @classmethod
    def _build_character_blueprint(
        cls,
        character: "Character",
        start_cards: Sequence[SimpleCardBlueprint],
    ) -> CharacterBlueprint:
        assets = CharacterAssets(
            shoulder_image=character.image.shoulder1 or "",
            shoulder2_image=character.image.shoulder2 or "",
            corpse_image=character.image.corpse or "",
            energy_orb_small=character.image.energy_orb,
        )
        blueprint = CharacterBlueprint(
            identifier=f"{character.mod_id}_character",
            character_name=character.name,
            description=character.description or character.name,
            assets=assets,
            starting_deck=[card.identifier for card in start_cards],
            starting_relics=list(character.start.relics),
            loadout_description=character.loadout_description or character.description,
            energy_per_turn=character.energyPerTurn,
            card_draw=character.handSize,
            max_hp=character.start.max_hp if character.start.max_hp is not None else character.maxhp,
            starting_hp=character.start.hp,
            starting_gold=character.start.gold,
            orb_slots=character.orbSlots,
            campfire_x=character.campfire_x,
            campfire_y=character.campfire_y,
            loadout_x=character.loadout_x,
            loadout_y=character.loadout_y,
            banner_texture=character.banner_image,
            select_button_texture=character.select_button_image,
            energy_image=character.energy_image,
            skeleton_atlas=character.image.staticspineatlas,
            skeleton_json=character.image.staticspinejson,
            skeleton_scale=1.0,
        )
        return blueprint

    @classmethod
    def _build_bundle_options(
        cls,
        character: "Character",
        assets_root: Path,
        python_root: Path,
        output_root: Path,
        dependencies: Sequence[str],
        java_classpath: Optional[Sequence[Path]],
        extra_classpath: Sequence[Path],
        packaging: Union[str, BundlePackaging],
    ) -> BundleOptions:
        if java_classpath is not None:
            classpath = list(java_classpath)
        else:
            jars = ensure_dependency_classpath()
            classpath = [jars["basemod"], jars["modthespire"]]
            if "stslib" in dependencies and "stslib" in jars:
                classpath.append(jars["stslib"])
        if character.desktop_jar is not None:
            classpath.append(Path(character.desktop_jar))
        classpath.extend(extra_classpath)
        unique_classpath = list(dict.fromkeys(Path(entry) for entry in classpath))
        options = BundleOptions(
            java_classpath=tuple(unique_classpath),
            python_source=python_root,
            assets_source=assets_root,
            output_directory=output_root,
            version=character.version,
            sts_version="2020-12-01",
            mts_version="3.30.1",
            dependencies=dependencies,
            packaging=packaging,
        )
        return options

    # ------------------------------------------------------------------
    # Path resolution helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_assets_root(
        character: "Character",
        assets_root: Optional[Union[str, Path]],
    ) -> Path:
        path = Path(assets_root) if assets_root is not None else character.assets_root
        if path is None:
            raise BaseModBootstrapError("Assets root directory is required for createMod().")
        resolved = Path(path).resolve()
        if not resolved.exists():
            raise BaseModBootstrapError(f"Assets directory '{resolved}' does not exist.")
        return resolved

    @classmethod
    def _write_card_localizations(
        cls,
        character: "Character",
        assets_root: Path,
        cards: Mapping[str, SimpleCardBlueprint],
    ) -> None:
        payloads = build_card_localizations(cards.values())
        if not payloads:
            return
        base_dir = assets_root / "localizations"
        for language, entries in payloads.items():
            target_dir = base_dir / language
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / "cards.json"
            existing: Dict[str, Any]
            if target_file.exists():
                try:
                    existing = json.loads(target_file.read_text(encoding="utf8"))
                except json.JSONDecodeError:
                    existing = {}
            else:
                existing = {}
            existing.update(entries)
            target_file.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
                encoding="utf8",
            )

    @staticmethod
    def _resolve_python_source(
        cls: Type["Character"],
        character: "Character",
        python_source: Optional[Union[str, Path]],
    ) -> Path:
        if python_source is not None:
            resolved = Path(python_source).resolve()
            if not resolved.exists():
                raise BaseModBootstrapError(f"Python source directory '{resolved}' does not exist.")
            return resolved
        if character.python_root is not None:
            resolved = Path(character.python_root).resolve()
            if not resolved.exists():
                raise BaseModBootstrapError(f"Python source directory '{resolved}' does not exist.")
            return resolved
        module = sys.modules.get(cls.__module__)
        if module is None or not hasattr(module, "__file__"):
            raise BaseModBootstrapError("Unable to resolve python source automatically.")
        module_file_attr = getattr(module, "__file__", None)
        if module_file_attr is None:
            raise BaseModBootstrapError("Unable to resolve python source automatically.")
        module_file = Path(module_file_attr).resolve()
        package = getattr(module, "__package__", "") or module.__name__
        depth = len(package.split(".")) - 1
        directory = module_file.parent
        for _ in range(depth):
            directory = directory.parent
        if not directory.exists():
            raise BaseModBootstrapError("Derived python source directory does not exist.")
        return directory


__all__ = [
    "Character",
    "CharacterStartConfig",
    "CharacterImageConfig",
    "CharacterColorConfig",
    "CharacterDeckSnapshot",
    "CharacterValidationReport",
    "CHARACTER_VALIDATION_HOOK",
]
