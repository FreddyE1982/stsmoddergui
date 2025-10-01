"""High level facilities for building fully fledged BaseMod projects."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Type

from importlib import import_module
import importlib.resources as import_resources
from functools import lru_cache

from .loader import BaseModBootstrapError, ensure_dependency_classpath
from .java_backend import active_backend
from plugins import PLUGIN_MANAGER

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from .cards import SimpleCardBlueprint

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
    skeleton_atlas: Optional[str] = None
    skeleton_json: Optional[str] = None
    skeleton_scale: float = 1.0

    def build_player_class(self, color_enum: object, player_enum: object, color_definition: ColorDefinition) -> Type:
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
                atlas = self.blueprint.skeleton_atlas
                json = self.blueprint.skeleton_json
                scale = float(self.blueprint.skeleton_scale)
                if atlas and json:
                    self.loadAnimation(atlas, json, scale)
                elif atlas or json:
                    raise BaseModBootstrapError(
                        "Character blueprints require both skeleton atlas and json paths when supplying animation assets."
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
                return active_backend().create_array("java.lang.String", self.blueprint.starting_deck)

            def getStartingRelics(self):
                return active_backend().create_array("java.lang.String", self.blueprint.starting_relics)

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


@dataclass(slots=True)
class _MechanicsRuntimePlan:
    blueprint_providers: List[Callable[[], Iterable["SimpleCardBlueprint"]]] = field(
        default_factory=list
    )
    mutations: List[Tuple[object, bool]] = field(default_factory=list)
    script_loaders: List[Tuple[Callable[[], Path], bool]] = field(default_factory=list)
    resource_scripts: List[Tuple[str, str, bool]] = field(default_factory=list)
    hooks: List[Callable[[object], None]] = field(default_factory=list)
    loaded_scripts: set[str] = field(default_factory=set)

    def register_blueprint_provider(
        self, provider: Callable[[], Iterable["SimpleCardBlueprint"]]
    ) -> None:
        if not callable(provider):
            raise TypeError("Blueprint provider must be callable.")
        if provider not in self.blueprint_providers:
            self.blueprint_providers.append(provider)

    def register_mutation(self, mutation: object, *, activate: bool = False) -> None:
        for index, (existing, existing_activate) in enumerate(self.mutations):
            if existing is mutation:
                if activate and not existing_activate:
                    self.mutations[index] = (existing, True)
                return
        self.mutations.append((mutation, activate))

    def register_script_loader(
        self, loader: Path | str | Callable[[], Path], *, activate: bool = True
    ) -> None:
        if callable(loader):
            resolver: Callable[[], Path] = loader  # type: ignore[assignment]
        else:
            path = Path(loader)

            def resolver(path: Path = path) -> Path:
                return path

        self.script_loaders.append((resolver, activate))

    def register_script_resource(
        self, package: str, resource: str, activate: bool = True
    ) -> None:
        if not package or not resource:
            raise ValueError("Package and resource names must be provided for mechanic scripts.")
        self.resource_scripts.append((package, resource, activate))

    def register_hook(self, hook: Callable[[object], None]) -> None:
        if not callable(hook):
            raise TypeError("Mechanic hooks must be callable.")
        self.hooks.append(hook)

    def resolve_script_loader(self, loader: Callable[[], Path]) -> Path:
        path = Path(loader())
        if not path.exists():
            raise BaseModBootstrapError(f"Mechanic rule script '{path}' does not exist.")
        return path

    def record_loaded_script(self, path: Path, *, key: Optional[str] = None) -> Optional[str]:
        resolved = Path(path)
        if not resolved.exists():
            raise BaseModBootstrapError(f"Mechanic rule script '{resolved}' does not exist.")
        if key is None:
            try:
                key = str(resolved.resolve())
            except OSError:
                key = str(resolved)
        if key in self.loaded_scripts:
            return None
        self.loaded_scripts.add(key)
        return key

    def open_resource(self, package: str, resource: str):
        try:
            ref = import_resources.files(package).joinpath(resource)
        except ModuleNotFoundError as exc:
            raise BaseModBootstrapError(
                f"Unable to locate package '{package}' for mechanic rule script '{resource}'."
            ) from exc
        if not ref.exists():
            raise BaseModBootstrapError(
                f"Mechanic rule script '{resource}' is not bundled with package '{package}'."
            )
        return import_resources.as_file(ref)


@dataclass(frozen=True)
class ProjectLayout:
    """Represents the auto generated on-disk structure of a mod project."""

    mod_id: str
    root: Path
    package_name: str
    python_root: Path
    python_package: Path
    cards_package: Path
    resource_root: Path
    images_root: Path
    cards_image_root: Path
    character_image_root: Path
    orbs_image_root: Path
    localization_root: Path
    entrypoint: Path
    project_module: Path

    def resource_path(self, *parts: str) -> str:
        """Return a resource path relative to the game resources folder."""

        cleaned = "/".join(str(part).strip("/\\") for part in parts if part)
        if not cleaned:
            return self.mod_id
        return f"{self.mod_id}/{cleaned}"


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
        self.layout: Optional[ProjectLayout] = None
        self._mechanics_plan = _MechanicsRuntimePlan()

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

    def add_simple_card(self, blueprint: "SimpleCardBlueprint") -> None:
        """Create and register a simple card blueprint against the project."""

        from .cards import register_simple_card

        register_simple_card(self, blueprint)

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
    # mechanics runtime configuration
    # ------------------------------------------------------------------
    def register_mechanic_blueprint_provider(
        self, provider: Callable[[], Iterable["SimpleCardBlueprint"]]
    ) -> None:
        """Expose card blueprints to the mechanics runtime.

        Mechanics-only mods frequently adjust card data without registering new
        cards.  Providers added here are forwarded to the
        :mod:`experimental.graalpy_rule_weaver` engine whenever
        :meth:`enable_mechanics_runtime` is invoked.  Providers are de-duplicated
        so calling this multiple times with the same callable is safe.
        """

        self._mechanics_plan.register_blueprint_provider(provider)

    def register_mechanic_mutation(self, mutation: object, *, activate: bool = False) -> None:
        """Register a :class:`MechanicMutation` for automatic installation.

        ``mutation`` should be an instance of
        :class:`experimental.graalpy_rule_weaver.MechanicMutation`.  Activation
        happens during :meth:`enable_mechanics_runtime`.  Passing
        ``activate=True`` ensures the mutation is immediately applied once the
        runtime spins up, while ``False`` merely registers it for manual
        activation later.
        """

        self._mechanics_plan.register_mutation(mutation, activate=activate)

    def register_mechanic_script_path(
        self, path: Path | str | Callable[[], Path], *, activate: bool = True
    ) -> None:
        """Schedule a rule script located on disk.

        ``path`` can be a :class:`pathlib.Path`, a string resolved relative to
        the current working directory, or a callable that returns the absolute
        path to the script when invoked.  Scripts are loaded at most once per
        project even if :meth:`enable_mechanics_runtime` is called multiple
        times.
        """

        self._mechanics_plan.register_script_loader(path, activate=activate)

    def register_mechanic_script_resource(
        self, package: str, resource: str, *, activate: bool = True
    ) -> None:
        """Schedule a rule script bundled as a package resource.

        This helper resolves ``resource`` using :mod:`importlib.resources`
        relative to ``package`` at runtime.  It keeps mechanics-only mods
        self-contained even when deployed as zipped Python packages.
        """

        self._mechanics_plan.register_script_resource(package, resource, activate=activate)

    def register_mechanic_hook(self, hook: Callable[[object], None]) -> None:
        """Register a callback invoked with the rule weaver engine.

        Hooks are executed during :meth:`enable_mechanics_runtime` after the
        engine has been activated and blueprint providers have been registered.
        They provide an escape hatch for advanced configuration such as dynamic
        mutation factories.
        """

        self._mechanics_plan.register_hook(hook)

    def enable_mechanics_runtime(self) -> object:
        """Activate mechanics-only runtime helpers without registering cards.

        The method switches on the :mod:`experimental.graalpy_rule_weaver`
        experiment, forwards all registered blueprint providers, loads rule
        scripts and applies eager mutations.  The underlying engine instance is
        returned so callers can perform additional configuration.
        """

        from modules.basemod_wrapper import experimental

        module = experimental.on("graalpy_rule_weaver")
        engine = module.get_engine()
        plan = self._mechanics_plan

        for provider in plan.blueprint_providers:
            engine.register_blueprint_provider(provider)

        for mutation, activate in plan.mutations:
            if not isinstance(mutation, module.MechanicMutation):
                raise BaseModBootstrapError(
                    "register_mechanic_mutation expects MechanicMutation instances from experimental.graalpy_rule_weaver."
                )
            engine.register_mutation(mutation, activate=activate)

        for loader, activate in plan.script_loaders:
            script_path = plan.resolve_script_loader(loader)
            key = plan.record_loaded_script(script_path)
            if key is None:
                continue
            engine.load_script(script_path, activate=activate)

        for package, resource, activate in plan.resource_scripts:
            with plan.open_resource(package, resource) as script_path:
                key = plan.record_loaded_script(
                    script_path, key=f"resource:{package}:{resource}"
                )
                if key is None:
                    continue
                engine.load_script(script_path, activate=activate)

        for hook in plan.hooks:
            hook(engine)

        PLUGIN_MANAGER.expose(
            f"mod_project:{self.mod_id}:mechanics_runtime",
            {
                "scripts": tuple(sorted(plan.loaded_scripts)),
                "mutations": tuple(
                    getattr(mutation, "identifier", repr(mutation))
                    for mutation, _ in plan.mutations
                ),
            },
        )

        return engine

    def resource_path(self, *segments: str) -> str:
        """Return a resources-relative path for the current mod."""

        cleaned = "/".join(str(part).strip("/\\") for part in segments if part)
        if not cleaned:
            return self.mod_id
        return f"{self.mod_id}/{cleaned}"

    # ------------------------------------------------------------------
    # runtime integration
    # ------------------------------------------------------------------
    def runtime_color_enum(self) -> object:
        """Return the registered card colour for runtime factories."""

        if self._color_enum is None:
            raise BaseModBootstrapError(
                "Colour not initialised. Call enable_runtime() before creating cards."
            )
        return self._color_enum

    def scaffold(
        self,
        base_directory: Path,
        *,
        package_name: Optional[str] = None,
        language: str = "eng",
    ) -> ProjectLayout:
        """Create a ready-to-fill project structure on disk.

        The scaffold includes a Python package, entrypoint and placeholder
        resource directories.  Existing files are preserved which allows the
        method to be rerun safely during iteration.
        """

        package = (package_name or self.mod_id).replace("-", "_")
        root = Path(base_directory).resolve()
        project_root = root / self.mod_id
        python_root = project_root / "python"
        python_package = python_root / package
        cards_package = python_package / "cards"
        resource_root = project_root / "assets" / self.mod_id
        images_root = resource_root / "images"
        cards_image_root = images_root / "cards"
        character_image_root = images_root / "character"
        orbs_image_root = images_root / "orbs"
        localization_root = resource_root / "localizations" / language
        entrypoint = python_package / "entrypoint.py"
        project_module = python_package / "project.py"

        for directory in (
            project_root,
            python_root,
            python_package,
            cards_package,
            resource_root,
            images_root,
            cards_image_root,
            character_image_root,
            orbs_image_root,
            localization_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        init_files = [python_package / "__init__.py", cards_package / "__init__.py"]
        for init_file in init_files:
            if not init_file.exists():
                init_file.write_text("\n", encoding="utf8")

        if not project_module.exists():
            template = textwrap.dedent(
                """
                \"\"\"Project definition for {name}.\"\"\"

                from modules.basemod_wrapper import create_project


                PROJECT = create_project(
                    "{mod_id}",
                    "{name}",
                    "{author}",
                    "{description}",
                    version="{version}",
                )


                def configure() -> None:
                    \"\"\"Configure colours, cards and characters.\"\"\"

                    # Example colour definition:
                    # PROJECT.define_color(
                    #     "{mod_id_upper}_COLOR",
                    #     card_color=(0.5, 0.2, 0.7, 1.0),
                    #     trail_color=(0.4, 0.1, 0.6, 1.0),
                    #     slash_color=(0.7, 0.3, 0.9, 1.0),
                    #     attack_bg=PROJECT.resource_path("images/cards/attack.png"),
                    #     skill_bg=PROJECT.resource_path("images/cards/skill.png"),
                    #     power_bg=PROJECT.resource_path("images/cards/power.png"),
                    #     orb=PROJECT.resource_path("images/cards/orb.png"),
                    #     attack_bg_small=PROJECT.resource_path("images/cards/attack_small.png"),
                    #     skill_bg_small=PROJECT.resource_path("images/cards/skill_small.png"),
                    #     power_bg_small=PROJECT.resource_path("images/cards/power_small.png"),
                    #     orb_small=PROJECT.resource_path("images/cards/orb_small.png"),
                    # )

                    # Register cards:
                    # @PROJECT.card("MyCard", basic=True)
                    # def make_my_card():
                    #     from .cards.example import ExampleCard
                    #     return ExampleCard()

                    # Register characters:
                    # from modules.basemod_wrapper.project import CharacterAssets, CharacterBlueprint
                    # PROJECT.add_character(
                    #     CharacterBlueprint(
                    #         identifier="{mod_id}_character",
                    #         character_name="Example",
                    #         description="An example hero.",
                    #         assets=CharacterAssets(
                    #             shoulder_image=PROJECT.resource_path("images/character/shoulder.png"),
                    #             shoulder2_image=PROJECT.resource_path("images/character/shoulder2.png"),
                    #             corpse_image=PROJECT.resource_path("images/character/corpse.png"),
                    #         ),
                    #         starting_deck=[],
                    #         starting_relics=[],
                    #         loadout_description="Describe your hero here.",
                    #     )
                    # )

                    # Mechanics-only rule weaving (optional):
                    # from pathlib import Path
                    # PROJECT.register_mechanic_script_path(
                    #     lambda: Path(__file__).with_name("mechanics") / "rules.json"
                    # )
                    # PROJECT.register_mechanic_script_resource(
                    #     "{package}.mechanics",
                    #     "buddy_rules.json",
                    # )
                    #
                    # from modules.basemod_wrapper.experimental import graalpy_rule_weaver
                    # mutation = graalpy_rule_weaver.MechanicMutation(...)
                    # PROJECT.register_mechanic_mutation(mutation, activate=True)


                def enable_runtime() -> None:
                    \"\"\"Apply configuration and register BaseMod hooks.\"\"\"

                    configure()
                    PROJECT.enable_runtime()


                def enable_mechanics_runtime() -> None:
                    \"\"\"Activate mechanics-only tweaks without registering cards.\"\"\"

                    configure()
                    PROJECT.enable_mechanics_runtime()
                """
            )
            template = template.format(
                name=self.name,
                mod_id=self.mod_id,
                author=self.author,
                description=self.description,
                version=self.version,
                mod_id_upper=self.mod_id.upper(),
                package=package,
            )
            project_module.write_text(template.strip() + "\n", encoding="utf8")

        if not entrypoint.exists():
            entrypoint.write_text(
                textwrap.dedent(
                    """
                    \"\"\"Runtime entrypoint used by ModTheSpire.\"\"\"

                    from .project import enable_mechanics_runtime, enable_runtime

                    MECHANICS_ONLY = False


                    def initialize():
                        \"\"\"Entry hook that ModTheSpire should invoke.\"\"\"

                        if MECHANICS_ONLY:
                            enable_mechanics_runtime()
                        else:
                            enable_runtime()


                    initialize()
                    """
                ).strip()
                + "\n",
                encoding="utf8",
            )

        readme = project_root / "README.txt"
        if not readme.exists():
            readme.write_text(
                textwrap.dedent(
                    f"""
                    {self.name} scaffolding
                    ==========================

                    python/        Python package containing all mod logic.
                    assets/        Game-ready resources (copied into resources/{self.mod_id}).

                    Update python/{package}/project.py to declare colours, cards and
                    characters.  Assets should be placed inside assets/{self.mod_id}/.
                    """
                ).strip()
                + "\n",
                encoding="utf8",
            )

        localization_stub = localization_root / "cards.json"
        if not localization_stub.exists():
            localization_stub.write_text("{}\n", encoding="utf8")

        layout = ProjectLayout(
            mod_id=self.mod_id,
            root=project_root,
            package_name=package,
            python_root=python_root,
            python_package=python_package,
            cards_package=cards_package,
            resource_root=resource_root,
            images_root=images_root,
            cards_image_root=cards_image_root,
            character_image_root=character_image_root,
            orbs_image_root=orbs_image_root,
            localization_root=localization_root,
            entrypoint=entrypoint,
            project_module=project_module,
        )
        self.layout = layout
        return layout

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
    def bundle_options_from_layout(
        self,
        layout: ProjectLayout,
        *,
        output_directory: Optional[Path] = None,
        version: Optional[str] = None,
        sts_version: Optional[str] = None,
        mts_version: Optional[str] = None,
        dependencies: Optional[Sequence[str]] = None,
        additional_classpath: Optional[Sequence[Path]] = None,
    ) -> BundleOptions:
        """Produce :class:`BundleOptions` using a :class:`ProjectLayout`."""

        jars = ensure_dependency_classpath(layout.root)
        classpath: List[Path] = [jars["basemod"], jars["modthespire"]]
        stslib_dependency = dependencies is None or "stslib" in dependencies
        if stslib_dependency and "stslib" in jars:
            classpath.append(jars["stslib"])
        elif "stslib" in jars and jars["stslib"] not in classpath:
            classpath.append(jars["stslib"])
        if additional_classpath:
            classpath.extend(additional_classpath)

        opts = BundleOptions(
            java_classpath=tuple(dict.fromkeys(classpath)),
            python_source=layout.python_package,
            assets_source=layout.resource_root,
            output_directory=output_directory or (layout.root / "dist"),
            version=version or self.version,
            sts_version=sts_version or "2020-12-01",
            mts_version=mts_version or "3.30.1",
            dependencies=dependencies or ("basemod", "stslib"),
        )
        return opts

    def compile_and_bundle(
        self,
        options: BundleOptions,
        *,
        layout: Optional[ProjectLayout] = None,
    ) -> Path:
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
        from modules.modbuilder.runtime_env import write_runtime_bootstrapper

        write_runtime_bootstrapper(mod_root)
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


def compileandbundle(
    project: ModProject,
    options: Optional[BundleOptions] = None,
    *,
    layout: Optional[ProjectLayout] = None,
    output_directory: Optional[Path] = None,
    version: Optional[str] = None,
    sts_version: Optional[str] = None,
    mts_version: Optional[str] = None,
    dependencies: Optional[Sequence[str]] = None,
    additional_classpath: Optional[Sequence[Path]] = None,
) -> Path:
    """Bundle ``project`` either from explicit ``options`` or a ``layout``."""

    if options is None:
        if layout is None:
            raise BaseModBootstrapError(
                "compileandbundle requires either BundleOptions or a ProjectLayout."
            )
        options = project.bundle_options_from_layout(
            layout,
            output_directory=output_directory,
            version=version,
            sts_version=sts_version,
            mts_version=mts_version,
            dependencies=dependencies,
            additional_classpath=additional_classpath,
        )
    return project.compile_and_bundle(options)


PLUGIN_MANAGER.expose("create_project", create_project)
PLUGIN_MANAGER.expose("compileandbundle", compileandbundle)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.project", alias="basemod_project")

__all__ = [
    "ColorDefinition",
    "CharacterAssets",
    "CharacterBlueprint",
    "CardRegistration",
    "ProjectLayout",
    "BundleOptions",
    "ModProject",
    "create_project",
    "compileandbundle",
]
