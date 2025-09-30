"""Adaptive card illustration swaps powered by GraalPy.

The :mod:`experimental.graalpy_adaptive_illustrations` module applies dynamic
image transformations to card artwork whenever the deck composition or runtime
state changes.  It ships two complementary APIs:

* :class:`AdaptiveIllustrationEngine` – a granular rule-based pipeline that
  loads Pillow images, executes custom transformations, and materialises the
  resulting textures on disk.  Authoring tools can register their own
  :class:`IllustrationSwapRule` instances to orchestrate bespoke workflows.
* :class:`AdaptiveIllustrationDirector` – a high level helper that plugs
  straight into :class:`modules.modbuilder.Deck` subclasses.  It synthesises
  swap rules from rarity palettes or card specific overrides, then updates the
  deck's :class:`~modules.basemod_wrapper.cards.SimpleCardBlueprint`
  registrations with the generated art.

Activating the module automatically toggles ``experimental.graalpy_runtime`` so
that all transformations execute under the GraalPy backend.  The engine and its
launch helpers are registered with :mod:`plugins` to keep third-party tooling in
sync.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from PIL import Image, ImageEnhance, ImageFilter

from plugins import PLUGIN_MANAGER

from . import is_active as experimental_is_active
from . import on as experimental_on

from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.modbuilder.deck import Deck, DeckStatistics

ColorTuple = Tuple[int, int, int]

__all__ = [
    "IllustrationSwapContext",
    "IllustrationSwapRule",
    "AdaptiveIllustrationEngine",
    "AdaptiveIllustrationDirector",
    "activate",
    "deactivate",
    "create_tint_transform",
    "create_keyword_glow_transform",
    "build_context_from_deck",
    "launch_adaptive_illustrations",
    "get_engine",
    "get_director",
]


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-")
    return cleaned.lower() or "adaptive"


def _serialise(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _serialise(inner)
            for key, inner in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple, set)):
        return tuple(_serialise(item) for item in value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf8", errors="ignore")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass(frozen=True)
class IllustrationSwapContext:
    """Immutable snapshot describing the factors that drive illustration swaps."""

    deck_statistics: DeckStatistics
    relics: Sequence[str] = field(default_factory=tuple)
    keyword_counts: Mapping[str, int] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalised_relics = tuple(str(relic) for relic in self.relics)
        normalised_keywords: Dict[str, int] = {}
        for key, value in (self.keyword_counts or {}).items():
            try:
                amount = int(value)
            except (TypeError, ValueError):
                continue
            if amount <= 0:
                continue
            normalised_keywords[str(key).lower()] = amount
        object.__setattr__(self, "relics", normalised_relics)
        object.__setattr__(self, "keyword_counts", MappingProxyType(normalised_keywords))
        object.__setattr__(self, "metadata", MappingProxyType(_serialise(self.metadata)))

    @property
    def dominant_rarity(self) -> Optional[str]:
        counts = self.deck_statistics.rarity_counts
        if not counts:
            return None
        rarity, _ = max(counts.items(), key=lambda item: item[1])
        return rarity

    def keyword_total(self, keyword: str) -> int:
        return int(self.keyword_counts.get(keyword.lower(), 0))

    def hash_token(self) -> str:
        payload = {
            "deck": {
                "identifier_counts": dict(self.deck_statistics.identifier_counts),
                "rarity_counts": dict(self.deck_statistics.rarity_counts),
            },
            "relics": sorted(self.relics),
            "keywords": {key: value for key, value in sorted(self.keyword_counts.items())},
            "metadata": dict(self.metadata),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf8")
        return hashlib.sha256(encoded).hexdigest()[:12]


@dataclass
class IllustrationSwapRule:
    """Declarative rule describing how to generate an adaptive illustration."""

    card_id: str | Sequence[str]
    transform: Callable[[Image.Image, IllustrationSwapContext], Image.Image]
    name: Optional[str] = None
    condition: Optional[Callable[[IllustrationSwapContext], bool]] = None
    source_image: Optional[Path] = None
    priority: int = 0
    output_subdirectory: Optional[str] = None

    def targets(self) -> Tuple[str, ...]:
        if isinstance(self.card_id, str):
            return (self.card_id.lower(),)
        return tuple(sorted({str(target).lower() for target in self.card_id}))

    def matches(self, card_id: str, context: IllustrationSwapContext) -> bool:
        lower = card_id.lower()
        target_match = any(target == "*" or target == lower for target in self.targets())
        if not target_match:
            return False
        if self.condition is not None and not self.condition(context):
            return False
        return True

    def slug(self) -> str:
        if self.name:
            return _slugify(self.name)
        targets = "-".join(self.targets())
        return _slugify(targets or "swap")


class AdaptiveIllustrationEngine:
    """Rule driven pipeline that generates adaptive card art variants."""

    def __init__(
        self,
        *,
        output_directory: Optional[Path] = None,
        image_format: str = "PNG",
    ) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        default_dir = output_directory or base_dir / "lib" / "graalpy" / "adaptive_illustrations"
        self._output_directory = Path(default_dir)
        self._output_directory.mkdir(parents=True, exist_ok=True)
        self._image_format = image_format.upper()
        self._records: list[Tuple[int, int, IllustrationSwapRule]] = []
        self._order_counter = 0
        self._rule_index: Dict[Tuple[Tuple[str, ...], str], IllustrationSwapRule] = {}
        self._cache: Dict[Tuple[str, str, str], Path] = {}

    @property
    def output_directory(self) -> Path:
        return self._output_directory

    def clear_rules(self) -> None:
        self._records.clear()
        self._rule_index.clear()

    def rules(self) -> Tuple[IllustrationSwapRule, ...]:
        return tuple(record[2] for record in self._records)

    def clear_cache(self) -> None:
        self._cache.clear()

    def _rule_key(self, rule: IllustrationSwapRule) -> Tuple[Tuple[str, ...], str]:
        return rule.targets(), rule.slug()

    def register_rule(self, rule: IllustrationSwapRule, *, replace: bool = False) -> None:
        key = self._rule_key(rule)
        existing = self._rule_index.get(key)
        if existing is not None:
            if not replace:
                return
            self._records = [record for record in self._records if record[2] is not existing]
            self._rule_index.pop(key, None)
        self._order_counter += 1
        self._records.append((rule.priority, self._order_counter, rule))
        self._rule_index[key] = rule
        self._records.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)

    def set_rules(self, rules: Iterable[IllustrationSwapRule]) -> None:
        self.clear_rules()
        for rule in rules:
            self.register_rule(rule)

    def _coerce_path(self, path: Path | str | None) -> Optional[Path]:
        if path is None:
            return None
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return (self._output_directory / candidate).resolve()

    def _rule_directory(self, rule: IllustrationSwapRule) -> Path:
        if rule.output_subdirectory:
            directory = self._output_directory / _slugify(rule.output_subdirectory)
        else:
            directory = self._output_directory
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _select_rule(self, card_id: str, context: IllustrationSwapContext) -> Optional[IllustrationSwapRule]:
        for _, _, rule in self._records:
            if rule.matches(card_id, context):
                return rule
        return None

    def _source_for(self, rule: IllustrationSwapRule, blueprint: SimpleCardBlueprint) -> Path:
        if rule.source_image is not None:
            resolved = self._coerce_path(rule.source_image)
            if resolved is None:
                raise FileNotFoundError("Rule declared a source_image that could not be resolved.")
            return resolved
        if blueprint.inner_image_source:
            resolved = self._coerce_path(blueprint.inner_image_source)
            if resolved:
                return resolved
        if blueprint.image:
            resolved = self._coerce_path(blueprint.image)
            if resolved:
                return resolved
        raise FileNotFoundError(
            f"Card '{blueprint.identifier}' does not declare an inner image source; adaptive swap cannot proceed."
        )

    def _write_transformed_image(
        self,
        card_id: str,
        rule: IllustrationSwapRule,
        image: Image.Image,
        context: IllustrationSwapContext,
    ) -> Path:
        directory = self._rule_directory(rule)
        token = context.hash_token()
        filename = f"{_slugify(card_id)}-{rule.slug()}-{token}.{self._image_format.lower()}"
        destination = directory / filename
        image.save(destination, format=self._image_format)
        return destination

    def generate(
        self,
        card_id: str,
        blueprint: SimpleCardBlueprint,
        context: IllustrationSwapContext,
    ) -> Optional[Path]:
        rule = self._select_rule(card_id, context)
        if rule is None:
            return None
        cache_key = (card_id.lower(), rule.slug(), context.hash_token())
        cached = self._cache.get(cache_key)
        if cached is not None and cached.exists():
            return cached
        source = self._source_for(rule, blueprint)
        if not source.exists():
            raise FileNotFoundError(f"Card '{card_id}' source image '{source}' does not exist.")
        with Image.open(source) as handle:
            handle = handle.convert("RGBA")
            transformed = rule.transform(handle, context)
        if not isinstance(transformed, Image.Image):
            raise TypeError("Illustration transforms must return a PIL.Image instance.")
        result = self._write_transformed_image(card_id, rule, transformed.convert("RGBA"), context)
        self._cache[cache_key] = result
        return result

    def apply_to_blueprint(
        self,
        blueprint: SimpleCardBlueprint,
        context: IllustrationSwapContext,
        *,
        persist: bool = True,
    ) -> Optional[Path]:
        path = self.generate(blueprint.identifier, blueprint, context)
        if path and persist:
            blueprint.innerCardImage(str(path))
        return path


@dataclass
class _PaletteConfig:
    color: ColorTuple
    intensity: float = 0.45
    name: Optional[str] = None
    condition: Optional[Callable[[IllustrationSwapContext], bool]] = None
    priority: int = 0


@dataclass
class _OverrideConfig:
    transform: Callable[[Image.Image, IllustrationSwapContext], Image.Image]
    source_image: Optional[Path] = None
    name: Optional[str] = None
    condition: Optional[Callable[[IllustrationSwapContext], bool]] = None
    priority: int = 10


class AdaptiveIllustrationDirector:
    """High level helper that wires adaptive illustrations into a deck."""

    def __init__(
        self,
        deck: type[Deck],
        *,
        asset_root: Path,
        output_directory: Path,
        engine: AdaptiveIllustrationEngine,
        default_transform: Optional[Callable[[Image.Image, IllustrationSwapContext], Image.Image]] = None,
    ) -> None:
        self.deck = deck
        self.asset_root = Path(asset_root)
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.engine = engine
        self.default_transform = default_transform or create_tint_transform((160, 160, 160), intensity=0.35)
        self._palette_rules: Dict[str, _PaletteConfig] = {}
        self._overrides: Dict[str, _OverrideConfig] = {}
        self._baseline_sources: Dict[str, Path] = {}

    def register_rarity_palette(
        self,
        rarity: str,
        *,
        color: ColorTuple,
        intensity: float = 0.45,
        name: Optional[str] = None,
        condition: Optional[Callable[[IllustrationSwapContext], bool]] = None,
        priority: int = 0,
    ) -> None:
        self._palette_rules[rarity.upper()] = _PaletteConfig(
            color=color,
            intensity=intensity,
            name=name,
            condition=condition,
            priority=priority,
        )

    def register_card_override(
        self,
        card_id: str,
        transform: Callable[[Image.Image, IllustrationSwapContext], Image.Image],
        *,
        source_image: Optional[Path] = None,
        name: Optional[str] = None,
        condition: Optional[Callable[[IllustrationSwapContext], bool]] = None,
        priority: int = 10,
    ) -> None:
        self._overrides[card_id.lower()] = _OverrideConfig(
            transform=transform,
            source_image=source_image,
            name=name,
            condition=condition,
            priority=priority,
        )

    def build_context(
        self,
        *,
        relics: Sequence[str] = (),
        keyword_counts: Mapping[str, int] = (),
        metadata: Mapping[str, Any] = (),
    ) -> IllustrationSwapContext:
        return IllustrationSwapContext(
            deck_statistics=self.deck.statistics(),
            relics=relics,
            keyword_counts=dict(keyword_counts),
            metadata=dict(metadata),
        )

    def _rule_for_blueprint(self, blueprint: SimpleCardBlueprint) -> IllustrationSwapRule:
        card_key = blueprint.identifier.lower()
        override = self._overrides.get(card_key)
        rarity_config = self._palette_rules.get(blueprint.rarity.upper())
        baseline = self._baseline_sources.get(card_key)
        if baseline is None:
            source = blueprint.inner_image_source or blueprint.image
            if not source:
                raise FileNotFoundError(
                    f"Card '{blueprint.identifier}' has no inner image registered for adaptive swaps."
                )
            baseline = Path(source)
            self._baseline_sources[card_key] = baseline
        if override is not None:
            transform = override.transform
            name = override.name or f"{blueprint.identifier}-override"
            condition = override.condition
            priority = override.priority
            source = override.source_image or baseline
        else:
            palette = rarity_config
            if palette is None:
                transform = self.default_transform
                name = f"{blueprint.rarity.lower()}-default"
                condition = None
                priority = 0
            else:
                transform = create_tint_transform(palette.color, intensity=palette.intensity)
                name = palette.name or f"{blueprint.rarity.lower()}-palette"
                condition = palette.condition
                priority = palette.priority
            source = baseline
        rule = IllustrationSwapRule(
            card_id=blueprint.identifier,
            transform=transform,
            name=name,
            condition=condition,
            source_image=source,
            priority=priority,
            output_subdirectory=self.deck.display_name,
        )
        return rule

    def ensure_rules(self) -> None:
        for blueprint in self.deck.cards():
            rule = self._rule_for_blueprint(blueprint)
            self.engine.register_rule(rule, replace=True)

    def apply(
        self,
        context: Optional[IllustrationSwapContext] = None,
        *,
        persist: bool = True,
    ) -> Dict[str, Path]:
        self.ensure_rules()
        actual_context = context or self.build_context()
        results: Dict[str, Path] = {}
        for blueprint in self.deck.cards():
            path = self.engine.apply_to_blueprint(blueprint, actual_context, persist=persist)
            if path:
                results[blueprint.identifier] = path
        return results


def create_tint_transform(color: ColorTuple, *, intensity: float = 0.5) -> Callable[[Image.Image, IllustrationSwapContext], Image.Image]:
    """Return a transformation that blends the image with ``color``."""

    intensity = max(0.0, min(1.0, float(intensity)))

    def transform(image: Image.Image, context: IllustrationSwapContext) -> Image.Image:
        base = image.convert("RGBA")
        overlay = Image.new("RGBA", base.size, (*color, int(255 * intensity)))
        blended = Image.blend(base, overlay, intensity)
        enhancer = ImageEnhance.Color(blended)
        adjusted = enhancer.enhance(1.0 + (intensity * 0.25))
        return adjusted

    return transform


def create_keyword_glow_transform(
    keyword: str,
    *,
    color: ColorTuple,
    radius: int = 6,
    intensity: float = 0.6,
) -> Callable[[Image.Image, IllustrationSwapContext], Image.Image]:
    """Return a transformation that emits a glow when ``keyword`` is present."""

    keyword = keyword.lower()
    radius = max(1, int(radius))
    intensity = max(0.1, min(1.0, float(intensity)))

    def transform(image: Image.Image, context: IllustrationSwapContext) -> Image.Image:
        base = image.convert("RGBA")
        amount = max(1, context.keyword_total(keyword))
        alpha = base.split()[-1]
        blur = alpha.filter(ImageFilter.GaussianBlur(radius=radius * amount))
        overlay_strength = min(1.0, intensity * amount)
        overlay = Image.new("RGBA", base.size, (*color, int(255 * overlay_strength)))
        glow_layer = Image.new("RGBA", base.size)
        glow_layer.paste(overlay, mask=blur)
        return Image.alpha_composite(glow_layer, base)

    return transform


def build_context_from_deck(
    deck: type[Deck],
    *,
    relics: Sequence[str] = (),
    keyword_counts: Mapping[str, int] = (),
    metadata: Mapping[str, Any] = (),
) -> IllustrationSwapContext:
    return IllustrationSwapContext(
        deck_statistics=deck.statistics(),
        relics=relics,
        keyword_counts=dict(keyword_counts),
        metadata=dict(metadata),
    )


_ENGINE: Optional[AdaptiveIllustrationEngine] = None
_DIRECTORS: Dict[str, AdaptiveIllustrationDirector] = {}


def activate() -> AdaptiveIllustrationEngine:
    """Ensure GraalPy runtime is active and return the adaptive engine."""

    if not experimental_is_active("graalpy_runtime"):
        experimental_on("graalpy_runtime")
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = AdaptiveIllustrationEngine()
    PLUGIN_MANAGER.expose("experimental_graalpy_illustrations_engine", _ENGINE)
    PLUGIN_MANAGER.expose("experimental_graalpy_illustrations_directors", _DIRECTORS)
    PLUGIN_MANAGER.expose("experimental_graalpy_illustrations_launch", launch_adaptive_illustrations)
    PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.experimental.graalpy_adaptive_illustrations")
    return _ENGINE


def deactivate() -> None:
    """Tear down registered directors and reset plugin exposures."""

    global _ENGINE
    _DIRECTORS.clear()
    if _ENGINE is not None:
        _ENGINE.clear_cache()
    _ENGINE = None
    PLUGIN_MANAGER.expose("experimental_graalpy_illustrations_directors", None)
    PLUGIN_MANAGER.expose("experimental_graalpy_illustrations_engine", None)


def get_engine() -> AdaptiveIllustrationEngine:
    engine = activate()
    if engine is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Adaptive illustration engine is unavailable.")
    return engine


def launch_adaptive_illustrations(
    deck: type[Deck],
    *,
    asset_root: Path,
    output_directory: Optional[Path] = None,
    default_transform: Optional[Callable[[Image.Image, IllustrationSwapContext], Image.Image]] = None,
) -> AdaptiveIllustrationDirector:
    engine = activate()
    root = Path(asset_root)
    directory = Path(output_directory) if output_directory is not None else engine.output_directory / _slugify(deck.display_name)
    director = AdaptiveIllustrationDirector(
        deck,
        asset_root=root,
        output_directory=directory,
        engine=engine,
        default_transform=default_transform,
    )
    key_candidates = {
        deck.__name__.lower(),
        getattr(deck, "display_name", deck.__name__).lower(),
    }
    for key in key_candidates:
        _DIRECTORS[key] = director
    return director


def get_director(name: str) -> AdaptiveIllustrationDirector:
    if not _DIRECTORS:
        raise RuntimeError("No adaptive illustration directors are active. Call launch_adaptive_illustrations first.")
    cleaned = name.lower().strip()
    director = _DIRECTORS.get(cleaned)
    if director is None:
        raise KeyError(f"No adaptive illustration director registered under '{name}'.")
    return director


PLUGIN_MANAGER.expose("experimental_graalpy_illustrations_launch", launch_adaptive_illustrations)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.experimental.graalpy_adaptive_illustrations")
