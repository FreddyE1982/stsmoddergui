"""High level facilities for building fully fledged BaseMod projects."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Type

from importlib import import_module
from functools import lru_cache

from .loader import BaseModBootstrapError
from plugins import PLUGIN_MANAGER

ColorTuple = Tuple[float, float, float, float]


@lru_cache(maxsize=1)
def _wrapper_module():
    """Return the lazily imported :mod:`modules.basemod_wrapper` package."""

    return import_module("modules.basemod_wrapper")


def _basemod():
    return getattr(_wrapper_module(), "basemod")


def _cardcrawl():
    return getattr(_wrapper_module(), "cardcrawl")


def _libgdx():
    return getattr(_wrapper_module(), "libgdx")


def _coerce_color(value: ColorTuple) -> object:
    """Convert a RGBA tuple into a libGDX ``Color`` instance."""

    try:
        return _libgdx().graphics.Color(*value)
    except Exception as exc:  # pragma: no cover - dependent on JVM deps
        raise BaseModBootstrapError(
            "libGDX colour initialisation failed. Ensure the Slay the Spire jars"
            " are on the classpath before calling runtime hooks."
        ) from exc


@dataclass(slots=True)
class ColorDefinition:
    """Describes a new BaseMod colour and its associated textures."""

    identifier: str
    attack_bg: str
    skill_bg: str
    power_bg: str
    orb: str
    attack_bg_small: str
    skill_bg_small: str
    power_bg_small: str
    orb_small: str
    color: ColorTuple
    trail_color: ColorTuple
    slash_color: ColorTuple

    def register(self) -> object:
        _basemod().BaseMod.addColor(
            self.identifier,
            _coerce_color(self.color),
            _coerce_color(self.trail_color),
            _coerce_color(self.slash_color),
            self.attack_bg,
            self.skill_bg,
            self.power_bg,
            self.orb,
            self.attack_bg_small,
            self.skill_bg_small,
            self.power_bg_small,
            self.orb_small,
        )
        return _cardcrawl().cards.AbstractCard.CardColor.valueOf(self.identifier)


@dataclass(slots=True)
class CharacterAssets:
    shoulder_image: str
    shoulder2_image: str
    corpse_image: str
    energy_orb_small: Optional[str] = None


@dataclass(slots=True)
class CharacterBlueprint:
    identifier: str
    character_name: str
    description: str
    assets: CharacterAssets
    starting_deck: List[str]
    starting_relics: List[str]
    loadout_description: str
    energy_per_turn: int = 3
    card_draw: int = 5
    max_hp: int = 72
    starting_hp: int = 72
    starting_gold: int = 99
    orb_slots: int = 0
    campfire_x: float = 0.0
    campfire_y: float = 0.0
    loadout_x: float = 220.0
    loadout_y: float = 300.0
    color: Optional[ColorDefinition] = None
    banner_texture: Optional[str] = None
    select_button_texture: Optional[str] = None
    energy_image: Optional[str] = None

    def build_player_class(self, color_enum: object, player_enum: object, color_definition: ColorDefinition) -> Type:
        import jpype

        CustomPlayer = _basemod().abstracts.CustomPlayer
        EnergyManager = _cardcrawl().characters.EnergyManager

        class GeneratedCharacter(CustomPlayer):  # type: ignore[misc]
            ENERGY_PER_TURN = self.energy_per_turn
            START_HP = self.starting_hp
            MAX_HP = self.max_hp
            START_GOLD = self.starting_gold
            CARD_DRAW = self.card_draw
            ORB_SLOTS = self.orb_slots

            def __init__(self):
                super().__init__(self.blueprint.character_name, player_enum, None, None, None, None)
                self.initializeClass(
                    self.blueprint.assets.shoulder_image,
                    self.blueprint.assets.shoulder2_image,
                    self.blueprint.assets.corpse_image,
                    self.getLoadout(),
                    self.blueprint.campfire_x,
                    self.blueprint.campfire_y,
                    self.blueprint.loadout_x,
                    self.blueprint.loadout_y,
                    EnergyManager(self.blueprint.energy_per_turn),
                    self.blueprint.energy_image,
                )

            def getLoadout(self):
                Loadout = CustomPlayer.Loadout
                return Loadout(
                    self.blueprint.character_name,
                    self.blueprint.loadout_description,
                    self.getStartingRelics(),
                    self.getStartingDeck(),
                    False,
                )

            def getStartingDeck(self):
                return jpype.JArray(str)(self.blueprint.starting_deck)

            def getStartingRelics(self):
                return jpype.JArray(str)(self.blueprint.starting_relics)

            def getCardColor(self):
                return color_enum

            def getCardTrailColor(self):
                return _coerce_color(color_definition.trail_color)

            def getSlashAttackColor(self):
                return _coerce_color(color_definition.slash_color)

            def getEnergyNumFont(self):
                return _cardcrawl().helpers.FontHelper.energyNumFontRed

        GeneratedCharacter.blueprint = self  # type: ignore[attr-defined]
        GeneratedCharacter.__name__ = f"{self.identifier}Character"
        return GeneratedCharacter


@dataclass(slots=True)
class CardRegistration:
    factory: Callable[[], object]
    make_basic: bool = False


@dataclass
class BundleOptions:
    java_classpath: Sequence[Path]
    python_source: Path
    assets_source: Path
    output_directory: Path
    version: str = "0.1.0"
    sts_version: str = "2020-12-01"
    mts_version: str = "3.30.1"
    dependencies: Sequence[str] = ("basemod", "stslib")


class ModProject:
    """Container capturing all high level configuration for a BaseMod mod."""

    def __init__(
        self,
        mod_id: str,
        name: str,
        author: str,
        description: str,
        version: str = "0.1.0",
    ) -> None:
        self.mod_id = mod_id
        self.name = name
        self.author = author
        self.description = description
        self.version = version
        self.cards: Dict[str, CardRegistration] = {}
        self.basic_cards: set[str] = set()
        self.color_definition: Optional[ColorDefinition] = None
        self.character_blueprints: List[CharacterBlueprint] = []
        self._subscriber = None
        self._color_enum = None
        self._player_enum = None

    # ------------------------------------------------------------------
    # configuration API
    # ------------------------------------------------------------------
    def define_color(
        self,
        identifier: str,
        *,
        card_color: ColorTuple,
        trail_color: ColorTuple,
        slash_color: ColorTuple,
        attack_bg: str,
        skill_bg: str,
        power_bg: str,
        orb: str,
        attack_bg_small: str,
        skill_bg_small: str,
        power_bg_small: str,
        orb_small: str,
    ) -> ColorDefinition:
        color = ColorDefinition(
            identifier=identifier,
            attack_bg=attack_bg,
            skill_bg=skill_bg,
            power_bg=power_bg,
            orb=orb,
            attack_bg_small=attack_bg_small,
            skill_bg_small=skill_bg_small,
            power_bg_small=power_bg_small,
            orb_small=orb_small,
            color=card_color,
            trail_color=trail_color,
            slash_color=slash_color,
        )
        self.color_definition = color
        return color

    def add_card(self, identifier: str, factory: Callable[[], object], *, basic: bool = False) -> None:
        self.cards[identifier] = CardRegistration(factory=factory, make_basic=basic)
        if basic:
            self.basic_cards.add(identifier)

    def card(self, identifier: str, *, basic: bool = False) -> Callable[[Callable[[], object]], Callable[[], object]]:
        def decorator(factory: Callable[[], object]) -> Callable[[], object]:
            self.add_card(identifier, factory, basic=basic)
            return factory

        return decorator

    def add_character(self, blueprint: CharacterBlueprint) -> None:
        if not self.color_definition:
            raise BaseModBootstrapError("define_color must be called before adding characters.")
        blueprint.color = self.color_definition
        self.character_blueprints.append(blueprint)

    # ------------------------------------------------------------------
    # runtime integration
    # ------------------------------------------------------------------
    def enable_runtime(self) -> None:
        if self._subscriber is not None:
            return
        if not self.color_definition:
            raise BaseModBootstrapError("A colour must be defined before runtime registration.")

        color_enum = self.color_definition.register()
        try:
            player_enum = _cardcrawl().characters.AbstractPlayer.PlayerClass.valueOf(self.mod_id.upper())
        except Exception as exc:  # pragma: no cover - depends on patch availability
            raise BaseModBootstrapError(
                f"Player class {self.mod_id.upper()} is not available. Run compileandbundle() "
                "to generate the enum patch jar first."
            ) from exc
        self._color_enum = color_enum
        self._player_enum = player_enum

        project = self

        class _Subscriber:
            def receiveEditCards(self):
                project._register_cards()

            def receiveEditCharacters(self):
                project._register_characters()

            def receivePostInitialize(self):
                _basemod().BaseMod.registerModBadge(
                    project.color_definition.attack_bg,
                    project.name,
                    project.description,
                    project.author,
                    lambda: None,
                )

        subscriber = _Subscriber()
        _basemod().BaseMod.subscribe(subscriber)
        self._subscriber = subscriber

    def _register_cards(self) -> None:
        for identifier, registration in self.cards.items():
            card = registration.factory()
            _basemod().BaseMod.addCard(card)
            if registration.make_basic:
                _basemod().BaseMod.addBasicCard(card)

    def _register_characters(self) -> None:
        if not self.color_definition:
            raise BaseModBootstrapError("Cannot register characters without a colour definition.")
        try:
            color_enum = _cardcrawl().cards.AbstractCard.CardColor.valueOf(self.color_definition.identifier)
        except Exception as exc:  # pragma: no cover - depends on patch availability
            raise BaseModBootstrapError(
                f"Card color {self.color_definition.identifier} is not available. "
                "Ensure your enum patch has been compiled and is on the classpath."
            ) from exc
        try:
            player_enum = _cardcrawl().characters.AbstractPlayer.PlayerClass.valueOf(self.mod_id.upper())
        except Exception as exc:  # pragma: no cover - depends on patch availability
            raise BaseModBootstrapError(
                f"Player class {self.mod_id.upper()} is not available. Run compileandbundle() "
                "to generate the enum patch jar first."
            ) from exc
        for blueprint in self.character_blueprints:
            character_cls = blueprint.build_player_class(color_enum, player_enum, self.color_definition)
            _basemod().BaseMod.addCharacter(
                character_cls(),
                blueprint.assets.shoulder_image,
                blueprint.assets.shoulder2_image,
                blueprint.assets.corpse_image,
                player_enum,
            )

    # bundling
    # ------------------------------------------------------------------
    def compile_and_bundle(self, options: BundleOptions) -> Path:
        output_dir = options.output_directory
        output_dir.mkdir(parents=True, exist_ok=True)
        mod_root = output_dir / self.name.replace(" ", "")
        resources_root = mod_root / "resources" / self.mod_id
        python_root = mod_root / "python"
        patches_root = mod_root / "patches"
        classes_root = mod_root / "classes"

        if mod_root.exists():
            shutil.rmtree(mod_root)
        mod_root.mkdir(parents=True)
        resources_root.mkdir(parents=True)
        python_root.mkdir()
        patches_root.mkdir()
        classes_root.mkdir()

        shutil.copytree(options.assets_source, resources_root, dirs_exist_ok=True)
        shutil.copytree(options.python_source, python_root / options.python_source.name)

        patch_java = patches_root / f"{self.mod_id.title().replace('_', '')}Enums.java"
        patch_java.write_text(self._render_enum_patch())

        javac_cmd = [
            "javac",
            "-cp",
            self._build_classpath(options.java_classpath),
            "-d",
            str(classes_root),
            str(patch_java),
        ]
        subprocess.run(javac_cmd, check=True)
        jar_path = mod_root / f"{self.mod_id}_patches.jar"
        subprocess.run(["jar", "cf", str(jar_path), "-C", str(classes_root), "."], check=True)

        (mod_root / "ModTheSpire.json").write_text(self._render_modthespire_manifest(options))
        (mod_root / "README.txt").write_text(self._render_bundle_readme())
        return mod_root

    def _render_enum_patch(self) -> str:
        class_name = f"{self.mod_id.title().replace('_', '')}Enums"
        identifier = self.color_definition.identifier if self.color_definition else self.mod_id.upper()
        player_enum = self.mod_id.upper()
        return textwrap.dedent(
            f"""
            package {self.mod_id}.patches;

            import com.evacipated.cardcrawl.modthespire.lib.SpireEnum;
            import com.megacrit.cardcrawl.cards.AbstractCard;
            import com.megacrit.cardcrawl.characters.AbstractPlayer;

            public class {class_name} {{
                public static class CardColor {{
                    @SpireEnum
                    public static AbstractCard.CardColor {identifier};
                    @SpireEnum(name = "{identifier}")
                    public static AbstractCard.CardColor LIBRARY_COLOR;
                }}

                public static class PlayerClass {{
                    @SpireEnum
                    public static AbstractPlayer.PlayerClass {player_enum};
                }}
            }}
            """
        ).strip()

    def _render_modthespire_manifest(self, options: BundleOptions) -> str:
        manifest = {
            "modid": self.mod_id,
            "name": self.name,
            "author_list": [self.author],
            "description": self.description,
            "version": options.version,
            "sts_version": options.sts_version,
            "mts_version": options.mts_version,
            "dependencies": list(dict.fromkeys(options.dependencies)),
        }
        return json.dumps(manifest, indent=2)

    def _render_bundle_readme(self) -> str:
        return textwrap.dedent(
            f"""
            {self.name}
            ==================

            This directory was generated by the stsmoddergui BaseMod project wrapper.
            Drop the folder into ModTheSpire's mods directory and enable it from the
            launcher. The Python sources live under ./python/ and can be tweaked
            without rebuilding the jar as long as classpaths remain consistent.
            """
        ).strip() + "\n"

    @staticmethod
    def _build_classpath(entries: Sequence[Path]) -> str:
        ordered = list(dict.fromkeys(entries))
        return os.pathsep.join(str(entry) for entry in ordered)


def create_project(mod_id: str, name: str, author: str, description: str, version: str = "0.1.0") -> ModProject:
    project = ModProject(mod_id, name, author, description, version)
    return project


def compileandbundle(project: ModProject, options: BundleOptions) -> Path:
    return project.compile_and_bundle(options)


PLUGIN_MANAGER.expose("create_project", create_project)
PLUGIN_MANAGER.expose("compileandbundle", compileandbundle)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.project", alias="basemod_project")

__all__ = [
    "ColorDefinition",
    "CharacterAssets",
    "CharacterBlueprint",
    "CardRegistration",
    "BundleOptions",
    "ModProject",
    "create_project",
    "compileandbundle",
]
