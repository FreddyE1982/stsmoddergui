"""High level JPype wrapper that exposes the BaseMod API for Python users."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Union

from .loader import (
    ensure_basemod_environment,
    ensure_dependency_classpath,
    ensure_desktop_jar,
    ensure_jpype,
)
from .project import (
    BundleOptions,
    BundlePackaging,
    BundleResult,
    ModProject,
    ProjectLayout,
    compileandbundle,
    create_project,
)
from .cards import (
    CardLocalizationEntry,
    ResolvedCardLocalization,
    SimpleCardBlueprint,
    build_card_localizations,
    register_simple_card,
)
from .keywords import (
    KEYWORD_REGISTRY,
    Keyword,
    KeywordRegistry,
    apply_persistent_card_changes,
    keyword_scheduler,
)
from .relics import Relic, RELIC_REGISTRY
from .stances import Stance, STANCE_REGISTRY
from .overlays import (
    OverlayHandle,
    OverlayManager,
    OverlaySnapshot,
    clear_overlays,
    hide_overlay,
    overlay_manager,
    show_overlay,
    update_overlay,
)
from . import experimental

ensure_jpype()
from .proxy import JavaPackageWrapper, create_package_wrapper
from plugins import PLUGIN_MANAGER


class BaseModEnvironment:
    """Lifecycle manager around the BaseMod JVM runtime.

    Instances of this class take care of preparing the JVM, downloading the
    BaseMod release and exposing Java packages in a pythonic way.  The default
    environment is created eagerly at module import so end users can simply do::

        from modules.basemod_wrapper import basemod
        basemod.BaseMod.subscribe(my_python_listener)

    The wrapper automatically handles functional interfaces and iterable
    conversion so Python callables can be passed where Java expects a functional
    interface.
    """

    DEFAULT_PACKAGES: Iterable[str] = (
        "basemod",
        "com.megacrit.cardcrawl",
        "com.badlogic.gdx",
        "com.evacipated.cardcrawl.modthespire",
        "com.evacipated.cardcrawl.mod.stslib",
    )

    def __init__(
        self,
        base_dir: Path | None = None,
        *,
        basemod_version: str | None = None,
        stslib_version: str | None = None,
        modthespire_version: str | None = None,
    ) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parent
        self._versions = {
            "basemod": basemod_version,
            "stslib": stslib_version,
            "modthespire": modthespire_version,
        }
        self._jars = ensure_basemod_environment(
            self.base_dir,
            basemod_version=basemod_version,
            stslib_version=stslib_version,
            modthespire_version=modthespire_version,
        )
        self._packages: dict[str, JavaPackageWrapper] = {}

        for package in self.DEFAULT_PACKAGES:
            self.package(package)

    @property
    def dependency_jars(self) -> Dict[str, Path]:
        """Return the resolved dependency jar mapping."""

        return dict(self._jars)

    @property
    def classpath(self) -> Sequence[Path]:
        """Return the default classpath used for the JVM."""

        return tuple(self._jars.values())

    @property
    def dependency_versions(self) -> Dict[str, Optional[str]]:
        """Return the dependency version hints used to bootstrap the JVM."""

        return dict(self._versions)

    def package(self, name: str) -> JavaPackageWrapper:
        """Return a :class:`JavaPackageWrapper` for ``name``."""

        if name not in self._packages:
            self._packages[name] = create_package_wrapper(name)
        return self._packages[name]

    def resolve(self, dotted_path: str) -> Any:
        """Resolve ``dotted_path`` against known packages and classes."""

        segments = dotted_path.split(".")
        for split in range(len(segments), 0, -1):
            package_name = ".".join(segments[:split])
            try:
                target = self.package(package_name)
            except Exception:
                continue
            value: Any = target
            for attr in segments[split:]:
                value = getattr(value, attr)
            return value
        raise AttributeError(f"Unable to resolve '{dotted_path}'.")

    def default_bundle_options(
        self,
        *,
        python_source: Path,
        assets_source: Path,
        output_directory: Path,
        version: str = "0.1.0",
        sts_version: str = "2020-12-01",
        mts_version: str = "3.30.1",
        dependencies: Optional[Sequence[str]] = None,
        additional_classpath: Optional[Sequence[Path]] = None,
        packaging: Union[str, BundlePackaging] = BundlePackaging.DIRECTORY,
    ) -> BundleOptions:
        """Produce a :class:`BundleOptions` instance with sensible defaults."""

        classpath = list(self.classpath)
        if additional_classpath:
            classpath.extend(additional_classpath)
        resolved_dependencies = tuple(dependencies or ("basemod", "stslib"))
        return BundleOptions(
            java_classpath=tuple(classpath),
            python_source=python_source,
            assets_source=assets_source,
            output_directory=output_directory,
            version=version,
            sts_version=sts_version,
            mts_version=mts_version,
            dependencies=resolved_dependencies,
            packaging=packaging,
        )

    # Convenience attribute access -------------------------------------------------
    def __getattr__(self, item: str) -> JavaPackageWrapper:
        return self.package(item)


class UnifiedSpireAPI:
    """High level façade over BaseMod and StSLib functionality."""

    _ACTION_MAP: Dict[str, str] = {
        "addtemporaryhp": "com.evacipated.cardcrawl.mod.stslib.actions.tempHp.AddTemporaryHPAction",
        "removealltemporaryhp": "com.evacipated.cardcrawl.mod.stslib.actions.tempHp.RemoveAllTemporaryHPAction",
        "autoplaycard": "com.evacipated.cardcrawl.mod.stslib.actions.common.AutoplayCardAction",
        "damagecallback": "com.evacipated.cardcrawl.mod.stslib.actions.common.DamageCallbackAction",
        "fetch": "com.evacipated.cardcrawl.mod.stslib.actions.common.FetchAction",
        "movecards": "com.evacipated.cardcrawl.mod.stslib.actions.common.MoveCardsAction",
        "multigroupmove": "com.evacipated.cardcrawl.mod.stslib.actions.common.MultiGroupMoveAction",
        "multigroupselect": "com.evacipated.cardcrawl.mod.stslib.actions.common.MultiGroupSelectAction",
        "refund": "com.evacipated.cardcrawl.mod.stslib.actions.common.RefundAction",
        "selectcards": "com.evacipated.cardcrawl.mod.stslib.actions.common.SelectCardsAction",
        "selectcardscentered": "com.evacipated.cardcrawl.mod.stslib.actions.common.SelectCardsCenteredAction",
        "selectcardsinhand": "com.evacipated.cardcrawl.mod.stslib.actions.common.SelectCardsInHandAction",
        "stunmonster": "com.evacipated.cardcrawl.mod.stslib.actions.common.StunMonsterAction",
        "evokespecificorb": "com.evacipated.cardcrawl.mod.stslib.actions.defect.EvokeSpecificOrbAction",
        "triggerpassive": "com.evacipated.cardcrawl.mod.stslib.actions.defect.TriggerPassiveAction",
        "gaincustomblock": "com.evacipated.cardcrawl.mod.stslib.actions.common.GainCustomBlockAction",
        "modifyexhaustive": "com.evacipated.cardcrawl.mod.stslib.actions.common.ModifyExhaustiveAction",
        "allenemyapplypower": "com.evacipated.cardcrawl.mod.stslib.actions.common.AllEnemyApplyPowerAction",
    }

    _KEYWORD_ALIASES: Dict[str, str] = {
        "inate": "innate",
        "etheral": "ethereal",
        "exhausts": "exhaust",
        "selfretain": "retain",
        "retainonce": "retain",
        "stslibexhaustive": "exhaustive",
        "stslibpersist": "persist",
        "stslibrefund": "refund",
    }

    _BASE_KEYWORD_ATTRIBUTES: Dict[str, Sequence[str]] = {
        "innate": ("isInnate",),
        "ethereal": ("isEthereal",),
        "exhaust": ("exhaust",),
        "retain": ("selfRetain", "retain"),
    }

    _BOOLEAN_KEYWORDS: Dict[str, str] = {
        "autoplay": "com.evacipated.cardcrawl.mod.stslib.fields.cards.AbstractCard.AutoplayField.autoplay",
        "retain": "com.evacipated.cardcrawl.mod.stslib.fields.cards.AbstractCard.AlwaysRetainField.alwaysRetain",
        "icons": "com.evacipated.cardcrawl.mod.stslib.fields.cards.AbstractCard.CommonKeywordIconsField.useIcons",
        "fleeting": "com.evacipated.cardcrawl.mod.stslib.fields.cards.AbstractCard.FleetingField.fleeting",
        "grave": "com.evacipated.cardcrawl.mod.stslib.fields.cards.AbstractCard.GraveField.grave",
        "purge": "com.evacipated.cardcrawl.mod.stslib.fields.cards.AbstractCard.PurgeField.purge",
        "snecko": "com.evacipated.cardcrawl.mod.stslib.fields.cards.AbstractCard.SneckoField.snecko",
        "soulbound": "com.evacipated.cardcrawl.mod.stslib.fields.cards.AbstractCard.SoulboundField.soulbound",
    }

    _NUMERIC_KEYWORDS: Dict[str, Dict[str, str]] = {
        "exhaustive": {
            "setter": "com.evacipated.cardcrawl.mod.stslib.variables.ExhaustiveVariable.setBaseValue",
            "upgrader": "com.evacipated.cardcrawl.mod.stslib.variables.ExhaustiveVariable.upgrade",
        },
        "persist": {
            "setter": "com.evacipated.cardcrawl.mod.stslib.fields.cards.AbstractCard.PersistFields.setBaseValue",
            "upgrader": "com.evacipated.cardcrawl.mod.stslib.fields.cards.AbstractCard.PersistFields.upgrade",
        },
        "refund": {
            "setter": "com.evacipated.cardcrawl.mod.stslib.variables.RefundVariable.setBaseValue",
            "upgrader": "com.evacipated.cardcrawl.mod.stslib.variables.RefundVariable.upgrade",
        },
    }

    def __init__(self, environment: BaseModEnvironment) -> None:
        self._env = environment
        self.basemod = environment.package("basemod")
        self.stslib = environment.package("com.evacipated.cardcrawl.mod.stslib")
        self.cardcrawl = environment.package("com.megacrit.cardcrawl")
        self.modthespire = environment.package("com.evacipated.cardcrawl.modthespire")
        self.libgdx = environment.package("com.badlogic.gdx")
        self.damage_modifiers = environment.package(
            "com.evacipated.cardcrawl.mod.stslib.damagemods"
        )
        self.block_modifiers = environment.package(
            "com.evacipated.cardcrawl.mod.stslib.blockmods"
        )
        self.icons = environment.package(
            "com.evacipated.cardcrawl.mod.stslib.icons"
        )

    def __getattr__(self, item: str) -> Any:
        for namespace in (self.basemod, self.stslib):
            try:
                return getattr(namespace, item)
            except AttributeError:
                continue
        raise AttributeError(item)

    # ------------------------------------------------------------------
    # Actions and helpers
    # ------------------------------------------------------------------
    def action(self, name: str) -> Any:
        key = name.replace(" ", "").replace("_", "").lower()
        try:
            path = self._ACTION_MAP[key]
        except KeyError as exc:  # pragma: no cover - defensive path
            raise KeyError(f"Unknown StSLib action '{name}'.") from exc
        return self._env.resolve(path)

    # ------------------------------------------------------------------
    # Keyword helpers
    # ------------------------------------------------------------------
    def apply_keyword(
        self,
        card: Any,
        keyword: str,
        *,
        value: Any = True,
        amount: Optional[int] = None,
        upgrade: Optional[int] = None,
    ) -> None:
        raw = keyword.strip()
        cleaned = raw.split(":", 1)[1] if ":" in raw else raw
        key = cleaned.replace(" ", "").replace("-", "").replace("_", "").lower()
        key = self._KEYWORD_ALIASES.get(key, key)
        handled = False
        if key in self._BASE_KEYWORD_ATTRIBUTES:
            flag = bool(value)
            for attr in self._BASE_KEYWORD_ATTRIBUTES[key]:
                setattr(card, attr, flag)
            handled = True
        if key in self._BOOLEAN_KEYWORDS:
            field = self._env.resolve(self._BOOLEAN_KEYWORDS[key])
            field.set(card, bool(value))
            handled = True
        if key in self._NUMERIC_KEYWORDS:
            if amount is None:
                raise ValueError(f"Keyword '{keyword}' requires an 'amount'.")
            mapping = self._NUMERIC_KEYWORDS[key]
            setter = self._env.resolve(mapping["setter"])
            setter(card, int(amount))
            if upgrade:
                upgrader = self._env.resolve(mapping["upgrader"])
                upgrader(card, int(upgrade))
            handled = True
        if not handled:
            metadata = KEYWORD_REGISTRY.resolve(keyword)
            if metadata is not None:
                KEYWORD_REGISTRY.attach_to_card(card, keyword, amount=amount, upgrade=upgrade)
                handled = True
        if not handled:
            raise KeyError(f"Unknown keyword '{keyword}'.")

    def keyword_fields(self) -> Dict[str, str]:
        """Expose the keyword map so callers can introspect support."""

        data: Dict[str, str] = {}
        for key, attrs in self._BASE_KEYWORD_ATTRIBUTES.items():
            data[key] = ", ".join(f"AbstractCard.{attr}" for attr in attrs)
        data.update(self._BOOLEAN_KEYWORDS)
        for key, mapping in self._NUMERIC_KEYWORDS.items():
            data[key] = mapping["setter"]
        return data

    # ------------------------------------------------------------------
    # Modifier helpers
    # ------------------------------------------------------------------
    def add_damage_modifier(self, owner: Any, modifier: Any) -> None:
        manager = self.damage_modifiers.DamageModifierManager
        manager.addModifier(owner, modifier)

    def add_block_modifier(self, owner: Any, modifier: Any) -> None:
        manager = self.block_modifiers.BlockModifierManager
        manager.addModifier(owner, modifier)

    def register_custom_icon(self, icon: Any) -> None:
        helper = self.icons.CustomIconHelper
        helper.addCustomIcon(icon)

    # ------------------------------------------------------------------
    # Keyword registration
    # ------------------------------------------------------------------
    def register_keyword(
        self,
        mod_id: str,
        keyword_id: str,
        names: Sequence[str],
        description: str,
        *,
        proper_name: Optional[str] = None,
        color: Optional[Sequence[float]] = None,
    ) -> Any:
        Keyword = self.stslib.Keyword
        keyword_obj = Keyword()
        keyword_obj.ID = keyword_id
        keyword_obj.NAMES = list(names)
        keyword_obj.DESCRIPTION = description
        if proper_name:
            keyword_obj.PROPER_NAME = proper_name
        if color:
            color_info = None
            for attr in ("KeywordInfo", "KeywordColorInfo"):
                try:
                    color_info = getattr(self.basemod.helpers, attr)
                    break
                except AttributeError:
                    continue
            if color_info:
                keyword_obj.COLOR = color_info(*color)
        base_mod = self.basemod.BaseMod
        try:
            base_mod.addKeyword(mod_id, keyword_obj)
        except TypeError:
            base_mod.addKeyword(mod_id, keyword_obj.PROPER_NAME or keyword_obj.NAMES[0], keyword_obj.NAMES, keyword_obj.DESCRIPTION)
        return keyword_obj

    # ------------------------------------------------------------------
    # Bundling helpers
    # ------------------------------------------------------------------
    def bundle_options(
        self,
        *,
        python_source: Path,
        assets_source: Path,
        output_directory: Path,
        version: str = "0.1.0",
        sts_version: str = "2020-12-01",
        mts_version: str = "3.30.1",
        dependencies: Optional[Sequence[str]] = None,
        additional_classpath: Optional[Sequence[Path]] = None,
    ) -> BundleOptions:
        return self._env.default_bundle_options(
            python_source=python_source,
            assets_source=assets_source,
            output_directory=output_directory,
            version=version,
            sts_version=sts_version,
            mts_version=mts_version,
            dependencies=dependencies,
            additional_classpath=additional_classpath,
        )

# Eagerly create the default environment and expose frequently used packages.
_ENVIRONMENT = BaseModEnvironment()
basemod: JavaPackageWrapper = _ENVIRONMENT.package("basemod")
cardcrawl: JavaPackageWrapper = _ENVIRONMENT.package("com.megacrit.cardcrawl")
modthespire: JavaPackageWrapper = _ENVIRONMENT.package(
    "com.evacipated.cardcrawl.modthespire"
)
libgdx: JavaPackageWrapper = _ENVIRONMENT.package("com.badlogic.gdx")
stslib: JavaPackageWrapper = _ENVIRONMENT.package("com.evacipated.cardcrawl.mod.stslib")
spire: UnifiedSpireAPI = UnifiedSpireAPI(_ENVIRONMENT)

# Share everything with the plugin manager.
PLUGIN_MANAGER.expose("basemod_environment", _ENVIRONMENT)
PLUGIN_MANAGER.expose("basemod", basemod)
PLUGIN_MANAGER.expose("cardcrawl", cardcrawl)
PLUGIN_MANAGER.expose("modthespire", modthespire)
PLUGIN_MANAGER.expose("libgdx", libgdx)
PLUGIN_MANAGER.expose("stslib", stslib)
PLUGIN_MANAGER.expose("spire", spire)
PLUGIN_MANAGER.expose("basemod_dependency_jars", _ENVIRONMENT.dependency_jars)
PLUGIN_MANAGER.expose("basemod_classpath", _ENVIRONMENT.classpath)
PLUGIN_MANAGER.expose("basemod_dependency_versions", _ENVIRONMENT.dependency_versions)
PLUGIN_MANAGER.expose("create_project", create_project)
PLUGIN_MANAGER.expose("compileandbundle", compileandbundle)
PLUGIN_MANAGER.expose("SimpleCardBlueprint", SimpleCardBlueprint)
PLUGIN_MANAGER.expose("register_simple_card", register_simple_card)
PLUGIN_MANAGER.expose("Relic", Relic)
PLUGIN_MANAGER.expose("RelicRegistry", RELIC_REGISTRY)
PLUGIN_MANAGER.expose("ModProject", ModProject)
PLUGIN_MANAGER.expose("ProjectLayout", ProjectLayout)
PLUGIN_MANAGER.expose("BundleOptions", BundleOptions)
PLUGIN_MANAGER.expose("BundlePackaging", BundlePackaging)
PLUGIN_MANAGER.expose("BundleResult", BundleResult)
PLUGIN_MANAGER.expose("default_bundle_options", _ENVIRONMENT.default_bundle_options)
PLUGIN_MANAGER.expose("experimental", experimental)
PLUGIN_MANAGER.expose("ensure_desktop_jar", ensure_desktop_jar)
PLUGIN_MANAGER.expose("ensure_dependency_classpath", ensure_dependency_classpath)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper", alias="basemod_wrapper")

__all__ = [
    "BaseModEnvironment",
    "UnifiedSpireAPI",
    "basemod",
    "cardcrawl",
    "modthespire",
    "libgdx",
    "stslib",
    "spire",
    "experimental",
    "ModProject",
    "ProjectLayout",
    "BundleOptions",
    "BundlePackaging",
    "BundleResult",
    "create_project",
    "compileandbundle",
    "build_card_localizations",
    "CardLocalizationEntry",
    "ResolvedCardLocalization",
    "SimpleCardBlueprint",
    "register_simple_card",
    "Keyword",
    "KeywordRegistry",
    "KEYWORD_REGISTRY",
    "keyword_scheduler",
    "apply_persistent_card_changes",
    "Relic",
    "RELIC_REGISTRY",
    "Stance",
    "STANCE_REGISTRY",
    "OverlayManager",
    "OverlayHandle",
    "OverlaySnapshot",
    "overlay_manager",
    "show_overlay",
    "update_overlay",
    "hide_overlay",
    "clear_overlays",
]
