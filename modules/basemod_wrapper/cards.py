"""High level helpers for declaring simple Slay the Spire cards."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from importlib import import_module
from pathlib import Path
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from plugins import PLUGIN_MANAGER

from .loader import BaseModBootstrapError
from .card_assets import InnerCardImageResult, prepare_inner_card_image, validate_inner_card_image

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from .project import ModProject


@lru_cache(maxsize=1)
def _wrapper_module():
    return import_module("modules.basemod_wrapper")


def _cardcrawl():
    return getattr(_wrapper_module(), "cardcrawl")


def _basemod():
    return getattr(_wrapper_module(), "basemod")


def _spire():
    return getattr(_wrapper_module(), "spire")


@lru_cache(maxsize=1)
def _keywords_module():
    return import_module("modules.basemod_wrapper.keywords")


def _keyword_registry():
    return getattr(_keywords_module(), "KEYWORD_REGISTRY")


_TYPE_ALIASES: Mapping[str, str] = {
    "attack": "ATTACK",
    "atk": "ATTACK",
    "skill": "SKILL",
    "power": "POWER",
}

_TARGET_ALIASES: Mapping[str, str] = {
    "enemy": "ENEMY",
    "single": "ENEMY",
    "enemies": "ALL_ENEMY",
    "all_enemies": "ALL_ENEMY",
    "aoe": "ALL_ENEMY",
    "self": "SELF",
    "self_only": "SELF",
    "none": "NONE",
    "self_and_enemy": "SELF_AND_ENEMY",
    "selfenemy": "SELF_AND_ENEMY",
    "ally": "SELF",
    "all": "ALL",
}

_RARITY_ALIASES: Mapping[str, str] = {
    "basic": "BASIC",
    "starter": "BASIC",
    "common": "COMMON",
    "uncommon": "UNCOMMON",
    "rare": "RARE",
    "special": "SPECIAL",
    "curse": "CURSE",
}

_SELF_EFFECTS = {
    "block",
    "draw",
    "energy",
    "strength",
    "dexterity",
    "artifact",
    "focus",
}

_ENEMY_EFFECTS = {
    "weak",
    "vulnerable",
    "frail",
    "poison",
}

_EFFECT_VALUE_FIELD: Mapping[str, str] = {
    "block": "block",
    "draw": "magic",
    "energy": "magic",
    "strength": "magic",
    "dexterity": "magic",
    "artifact": "magic",
    "focus": "magic",
    "weak": "magic",
    "vulnerable": "magic",
    "frail": "magic",
    "poison": "magic",
}

_POWER_CLASS: Mapping[str, str] = {
    "strength": "StrengthPower",
    "dexterity": "DexterityPower",
    "artifact": "ArtifactPower",
    "focus": "FocusPower",
    "weak": "WeakPower",
    "vulnerable": "VulnerablePower",
    "frail": "FrailPower",
    "poison": "PoisonPower",
}

_ATTACK_EFFECT_ALIASES: Mapping[str, str] = {
    "slash_diagonal": "SLASH_DIAGONAL",
    "slash_horizontal": "SLASH_HORIZONTAL",
    "slash_heavy": "SLASH_HEAVY",
    "vertical": "SLASH_VERTICAL",
    "smash": "SMASH",
    "blunt_light": "BLUNT_LIGHT",
    "blunt_heavy": "BLUNT_HEAVY",
    "none": "NONE",
}


_KEYWORD_ALIASES: Mapping[str, str] = {
    "inate": "innate",
    "etheral": "ethereal",
    "exhausts": "exhaust",
    "selfretain": "retain",
    "retainonce": "retain",
}


KEYWORD_PLACEHOLDERS: Dict[str, str] = {
    "exhaustive": "!stslib:ex!",
    "persist": "!stslib:ps!",
    "refund": "!stslib:rf!",
}

_CARD_ATTRIBUTE_NAMES: Mapping[str, str] = {
    "damage": "damage",
    "block": "block",
    "magic": "magicNumber",
    "secondary": "secondMagicNumber",
}


@dataclass(frozen=True)
class ActionSpec:
    action: Optional[str] = None
    args: Tuple[Any, ...] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)
    callback: Optional[Callable[[object, object, Optional[object], Any], None]] = None


@dataclass(frozen=True)
class EffectSpec:
    effect: Optional[str]
    target: Optional[str]
    amount: Optional[int]
    amount_key: Optional[str]
    follow_up: Tuple[ActionSpec, ...] = field(default_factory=tuple)
    callback: Optional[Callable[[object, object, Optional[object], int], None]] = None


@dataclass(frozen=True)
class CardLocalizationEntry:
    """Container describing per-language localisation overrides."""

    title: Optional[str] = None
    description: Optional[str] = None
    upgrade_description: Optional[str] = None
    extended_description: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResolvedCardLocalization:
    """Localisation payload ready to be written to cards.json."""

    title: str
    description: str
    upgrade_description: str
    extended_description: Tuple[str, ...] = field(default_factory=tuple)


def register_keyword_placeholder(keyword: str, token: str) -> None:
    """Register ``token`` as the placeholder for ``keyword`` descriptions."""

    KEYWORD_PLACEHOLDERS[_canonical_keyword(keyword)] = token


def _normalise(value: str) -> str:
    return value.replace(" ", "").replace("-", "").lower()


def _coerce_mapping(value: str, mapping: Mapping[str, str], label: str) -> str:
    key = _normalise(value)
    if key in mapping:
        return mapping[key]
    candidate = value.strip().upper()
    if candidate in mapping.values():
        return candidate
    raise BaseModBootstrapError(f"Unknown {label} '{value}'.")


def _resolve_enum(container: object, name: str, label: str) -> object:
    try:
        return getattr(container, name)
    except AttributeError as exc:  # pragma: no cover - depends on JVM enums
        raise BaseModBootstrapError(f"Unknown {label} '{name}'.") from exc


def _format_description(
    description: str,
    value: int,
    *,
    field: str,
    placeholders: Mapping[str, str],
) -> str:
    if "{" not in description:
        return description
    values = {
        "value": value,
        "damage": value if field == "damage" else 0,
        "block": value if field == "block" else 0,
        "magic": value if field == "magic" else 0,
        "amount": value,
    }
    values.update(placeholders)
    try:
        return description.format(**values)
    except Exception:
        return description


def _enqueue_action(action: object) -> None:
    manager = _cardcrawl().dungeons.AbstractDungeon.actionManager
    manager.addToBottom(action)


def _require_monster(monster: object, target_name: str, effect: str) -> object:
    if monster is None:
        raise BaseModBootstrapError(
            f"Effect '{effect}' requires an enemy target but none was provided for card target '{target_name}'."
        )
    return monster


def _canonical_keyword(value: str) -> str:
    stripped = value.strip()
    if ":" in stripped:
        stripped = stripped.split(":", 1)[1]
    cleaned = stripped.replace("_", "")
    return _KEYWORD_ALIASES.get(_normalise(cleaned), _normalise(cleaned))


def _compute_placeholders(keywords: Sequence[str]) -> Dict[str, str]:
    placeholders: Dict[str, str] = {}
    for keyword in keywords:
        token = KEYWORD_PLACEHOLDERS.get(keyword)
        if token:
            placeholders[keyword] = token
    return placeholders


def _normalise_language_code(language: Optional[str]) -> str:
    if language is None:
        return ""
    if not isinstance(language, str):
        raise BaseModBootstrapError("Language codes must be strings.")
    cleaned = language.strip().lower().replace("-", "_")
    if not cleaned:
        raise BaseModBootstrapError("Language codes must be non-empty strings.")
    return cleaned


def _clean_optional_string(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    return str(value).strip()


def _normalise_extended_description(value: Any) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),)
    if isinstance(value, Sequence):
        return tuple(str(item).strip() for item in value if item is not None)
    raise BaseModBootstrapError(
        "Extended descriptions must be strings or iterables of strings."
    )


def _coerce_localization_entry(value: Any) -> CardLocalizationEntry:
    if isinstance(value, CardLocalizationEntry):
        entry = value
    elif isinstance(value, Mapping):
        entry = CardLocalizationEntry(
            title=_clean_optional_string(
                value.get("title")
                or value.get("name")
                or value.get("TITLE")
                or value.get("NAME")
            ),
            description=_clean_optional_string(
                value.get("description")
                or value.get("text")
                or value.get("DESCRIPTION")
            ),
            upgrade_description=_clean_optional_string(
                value.get("upgrade_description")
                or value.get("UPGRADE_DESCRIPTION")
            ),
            extended_description=_normalise_extended_description(
                value.get("extended_description")
                or value.get("EXTENDED_DESCRIPTION")
            ),
        )
    elif isinstance(value, str):
        entry = CardLocalizationEntry(description=value.strip())
    else:
        raise BaseModBootstrapError(
            "Localisation entries must be mappings, strings or CardLocalizationEntry instances."
        )
    return CardLocalizationEntry(
        title=_clean_optional_string(entry.title),
        description=_clean_optional_string(entry.description),
        upgrade_description=_clean_optional_string(entry.upgrade_description),
        extended_description=tuple(
            item for item in _normalise_extended_description(entry.extended_description)
        ),
    )


def _normalise_localisations(
    entries: Mapping[str, Any]
) -> Mapping[str, CardLocalizationEntry]:
    if not isinstance(entries, Mapping):
        raise BaseModBootstrapError("'localizations' must be supplied as a mapping of language to entries.")
    normalised: Dict[str, CardLocalizationEntry] = {}
    for language, entry in entries.items():
        code = _normalise_language_code(language)
        normalised[code] = _coerce_localization_entry(entry)
    return normalised


def _merge_localization_entries(
    base: CardLocalizationEntry, override: Optional[CardLocalizationEntry]
) -> CardLocalizationEntry:
    if override is None:
        return base
    extended = override.extended_description or base.extended_description
    return CardLocalizationEntry(
        title=override.title or base.title,
        description=override.description or base.description,
        upgrade_description=override.upgrade_description
        or base.upgrade_description
        or override.description
        or base.description,
        extended_description=tuple(extended),
    )


_PLACEHOLDER_PATTERN = re.compile(r"\{([^{}]+)\}")


def _localisation_placeholder_mapping(
    blueprint: "SimpleCardBlueprint",
) -> Mapping[str, str]:
    value_token = {
        "damage": "!D!",
        "block": "!B!",
        "magic": "!M!",
    }.get(blueprint.value_field, "!M!")
    mapping: Dict[str, str] = {
        "value": value_token,
        "amount": value_token,
        "damage": "!D!",
        "block": "!B!",
        "magic": "!M!",
        "secondary": "!M2!",
    }
    for key, token in blueprint._placeholders.items():
        mapping[_normalise(key)] = token
    mapping.setdefault("uses", blueprint._placeholders.get("uses", "{uses}"))
    return mapping


def _convert_description_for_localization(
    blueprint: "SimpleCardBlueprint", template: Optional[str]
) -> str:
    if not template:
        return ""
    if "{" not in template:
        return template
    mapping = _localisation_placeholder_mapping(blueprint)

    def repl(match: re.Match[str]) -> str:
        key = _normalise(match.group(1))
        token = mapping.get(key)
        if token is None:
            token = mapping.get("value", match.group(0))
        return token

    return _PLACEHOLDER_PATTERN.sub(repl, template)


def _resolve_localization_entry(
    blueprint: "SimpleCardBlueprint", entry: CardLocalizationEntry
) -> ResolvedCardLocalization:
    description = entry.description or blueprint.description
    upgrade = entry.upgrade_description or entry.description or description
    resolved = ResolvedCardLocalization(
        title=(entry.title or blueprint.title or "").strip(),
        description=_convert_description_for_localization(blueprint, description),
        upgrade_description=_convert_description_for_localization(blueprint, upgrade),
        extended_description=tuple(
            _convert_description_for_localization(blueprint, text)
            for text in entry.extended_description
        ),
    )
    return resolved


def _ensure_tuple(value: Sequence[Any] | Any) -> Tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def _normalise_effect_sequence(
    blueprint: "SimpleCardBlueprint",
    descriptors: Sequence[Any],
    *,
    default_target: str,
    default_field: str,
) -> Tuple[EffectSpec, ...]:
    resolved: List[EffectSpec] = []
    for descriptor in _ensure_tuple(descriptors):
        if descriptor is None:
            continue
        resolved.append(
            _normalise_effect_descriptor(
                blueprint,
                descriptor,
                default_target=default_target,
                default_field=default_field,
            )
        )
    return tuple(resolved)


def _normalise_effect_descriptor(
    blueprint: "SimpleCardBlueprint",
    descriptor: Any,
    *,
    default_target: str,
    default_field: str,
) -> EffectSpec:
    if isinstance(descriptor, EffectSpec):
        return descriptor
    if callable(descriptor):
        return EffectSpec(effect=None, target=None, amount=None, amount_key=None, follow_up=tuple(), callback=descriptor)
    if isinstance(descriptor, str):
        effect_name = _normalise(descriptor)
        return EffectSpec(
            effect=effect_name,
            target=None,
            amount=None,
            amount_key=_resolve_amount_attribute(default_field),
            follow_up=tuple(),
            callback=None,
        )
    if isinstance(descriptor, Mapping):
        effect_name = descriptor.get("effect") or descriptor.get("name")
        target_value = descriptor.get("target")
        amount_literal = descriptor.get("amount")
        amount_key = descriptor.get("amount_key") or descriptor.get("amount_field")
        follow_up_raw = descriptor.get("follow_up_actions") or descriptor.get("follow_up") or ()
        callback = descriptor.get("callable")
        literal, attribute = _normalise_amount_descriptor(amount_literal, amount_key, default_field)
        target = _normalise_effect_target(target_value, default_target)
        follow_up = tuple(_normalise_action_descriptor(item) for item in _ensure_tuple(follow_up_raw))
        name = _normalise(effect_name) if effect_name else None
        return EffectSpec(
            effect=name,
            target=target,
            amount=literal,
            amount_key=attribute,
            follow_up=follow_up,
            callback=callback,
        )
    raise BaseModBootstrapError("Unsupported effect descriptor provided to SimpleCardBlueprint.")


def _normalise_effect_target(target: Any, default_target: str) -> Optional[str]:
    if target is None:
        return default_target
    if isinstance(target, str):
        return _coerce_mapping(target, _TARGET_ALIASES, "effect target")
    raise BaseModBootstrapError(f"Invalid effect target '{target}'.")


def _normalise_amount_descriptor(
    amount: Any,
    amount_key: Optional[str],
    default_field: str,
) -> Tuple[Optional[int], Optional[str]]:
    if amount is not None:
        if isinstance(amount, str):
            normalised = _normalise(amount)
            if normalised in {"value", "default"}:
                return None, _resolve_amount_attribute(default_field)
            return None, _resolve_amount_attribute(amount)
        try:
            return int(amount), None
        except (TypeError, ValueError) as exc:
            raise BaseModBootstrapError("Effect amounts must be integers or named card fields.") from exc
    if amount_key:
        normalised_key = _normalise(amount_key)
        if normalised_key in {"value", "default"}:
            return None, _resolve_amount_attribute(default_field)
        return None, _resolve_amount_attribute(amount_key)
    return None, _resolve_amount_attribute(default_field)


def _resolve_amount_attribute(field: str) -> str:
    normalised = _normalise(str(field))
    mapped = _CARD_ATTRIBUTE_NAMES.get(normalised)
    if mapped:
        return mapped
    if normalised in {"secondary", "second", "secondmagic", "secondarymagic", "magic2"}:
        return _CARD_ATTRIBUTE_NAMES["secondary"]
    if normalised in {"magic", "block", "damage"}:
        return _CARD_ATTRIBUTE_NAMES[normalised]
    raise BaseModBootstrapError(f"Unknown amount reference '{field}'.")


def _normalise_action_descriptor(descriptor: Any) -> ActionSpec:
    if isinstance(descriptor, ActionSpec):
        return descriptor
    if callable(descriptor):
        return ActionSpec(callback=descriptor)
    if isinstance(descriptor, str):
        return ActionSpec(action=descriptor)
    if isinstance(descriptor, Mapping):
        action_name = descriptor.get("action") or descriptor.get("name")
        args = tuple(descriptor.get("args", ()))
        kwargs = dict(descriptor.get("kwargs", {}))
        callback = descriptor.get("callable")
        return ActionSpec(action=action_name, args=args, kwargs=kwargs, callback=callback)
    raise BaseModBootstrapError("Invalid follow-up action descriptor provided to SimpleCardBlueprint.")


@dataclass(slots=True)
class SimpleCardBlueprint:
    """Describe the high level properties of a straightforward card."""

    identifier: str
    title: str
    description: str
    cost: int
    card_type: str
    target: str
    rarity: str
    value: int
    upgrade_value: int = 0
    effect: Optional[str] = None
    image: Optional[str] = None
    inner_image_source: Optional[str] = None
    color_id: Optional[str] = None
    starter: bool = False
    keywords: Sequence[str] = field(default_factory=tuple)
    keyword_values: Mapping[str, int] = field(default_factory=dict)
    keyword_upgrades: Mapping[str, int] = field(default_factory=dict)
    card_uses: Optional[int] = None
    card_uses_upgrade: int = 0
    attack_effect: str = "SLASH_DIAGONAL"
    secondary_value: Optional[int] = None
    secondary_upgrade: int = 0
    effects: Sequence[Any] = field(default_factory=tuple)
    on_draw: Sequence[Any] = field(default_factory=tuple)
    on_discard: Sequence[Any] = field(default_factory=tuple)
    localizations: Mapping[str, CardLocalizationEntry] = field(default_factory=dict)
    _inner_image_result: Optional[InnerCardImageResult] = field(default=None, init=False, repr=False)
    _resolved_effects: Tuple[EffectSpec, ...] = field(default_factory=tuple, init=False, repr=False)
    _on_draw_effects: Tuple[EffectSpec, ...] = field(default_factory=tuple, init=False, repr=False)
    _on_discard_effects: Tuple[EffectSpec, ...] = field(default_factory=tuple, init=False, repr=False)
    _placeholders: Mapping[str, str] = field(default_factory=dict, init=False, repr=False)
    _normalised_localizations: Mapping[str, CardLocalizationEntry] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "identifier", self.identifier)
        object.__setattr__(self, "card_type", _coerce_mapping(self.card_type, _TYPE_ALIASES, "card type"))
        object.__setattr__(self, "target", _coerce_mapping(self.target, _TARGET_ALIASES, "card target"))
        object.__setattr__(self, "rarity", _coerce_mapping(self.rarity, _RARITY_ALIASES, "card rarity"))
        if self.card_type != "ATTACK":
            if not self.effect:
                raise BaseModBootstrapError("Skill and power cards must declare an effect keyword.")
            normalised = _normalise(self.effect)
            if normalised not in _EFFECT_VALUE_FIELD:
                raise BaseModBootstrapError(f"Unsupported effect keyword '{self.effect}'.")
            object.__setattr__(self, "effect", normalised)
        else:
            object.__setattr__(self, "effect", None)
        if isinstance(self.keywords, str):
            raw_keywords = (self.keywords,)
        else:
            raw_keywords = tuple(self.keywords)
        canonical_keywords = []
        seen_keywords = set()
        for keyword in raw_keywords:
            canonical = _canonical_keyword(keyword)
            if canonical in seen_keywords:
                continue
            canonical_keywords.append(canonical)
            seen_keywords.add(canonical)
        object.__setattr__(self, "keywords", tuple(canonical_keywords))

        if isinstance(self.effects, str):
            extra_effects = (self.effects,)
        else:
            extra_effects = tuple(self.effects or ())
        if isinstance(self.on_draw, str):
            draw_effects = (self.on_draw,)
        else:
            draw_effects = tuple(self.on_draw or ())
        if isinstance(self.on_discard, str):
            discard_effects = (self.on_discard,)
        else:
            discard_effects = tuple(self.on_discard or ())
        object.__setattr__(self, "effects", extra_effects)
        object.__setattr__(self, "on_draw", draw_effects)
        object.__setattr__(self, "on_discard", discard_effects)

        value_mapping = {
            _canonical_keyword(key): int(value)
            for key, value in (self.keyword_values or {}).items()
        }
        upgrade_mapping = {
            _canonical_keyword(key): int(value)
            for key, value in (self.keyword_upgrades or {}).items()
        }

        uses_value: Optional[int]
        if self.card_uses is None:
            uses_value = None
        else:
            try:
                uses_value = int(self.card_uses)
            except (TypeError, ValueError) as exc:
                raise BaseModBootstrapError("'card_uses' must be an integer.") from exc
            if uses_value <= 0:
                raise BaseModBootstrapError("'card_uses' must be a positive integer.")
        object.__setattr__(self, "card_uses", uses_value)

        try:
            uses_upgrade_value = int(self.card_uses_upgrade)
        except (TypeError, ValueError) as exc:
            raise BaseModBootstrapError("'card_uses_upgrade' must be an integer.") from exc
        if uses_upgrade_value < 0:
            raise BaseModBootstrapError("'card_uses_upgrade' cannot be negative.")
        object.__setattr__(self, "card_uses_upgrade", uses_upgrade_value)

        has_exhaustive_keyword = "exhaustive" in canonical_keywords
        if "{uses}" in self.description and not has_exhaustive_keyword:
            raise BaseModBootstrapError("Description references '{uses}' but the blueprint is not Exhaustive.")
        if has_exhaustive_keyword:
            if uses_value is None:
                raise BaseModBootstrapError(
                    "Exhaustive cards must define 'card_uses' so the remaining uses can be displayed."
                )
            existing_amount = value_mapping.get("exhaustive")
            if existing_amount is not None and existing_amount != uses_value:
                raise BaseModBootstrapError(
                    "'card_uses' must match the 'exhaustive' value supplied in 'keyword_values'."
                )
            value_mapping.setdefault("exhaustive", uses_value)
            if uses_upgrade_value:
                existing_upgrade = upgrade_mapping.get("exhaustive")
                if existing_upgrade is not None and existing_upgrade != uses_upgrade_value:
                    raise BaseModBootstrapError(
                        "'card_uses_upgrade' must match the 'exhaustive' upgrade supplied in 'keyword_upgrades'."
                    )
                upgrade_mapping.setdefault("exhaustive", uses_upgrade_value)
        else:
            if uses_value is not None:
                raise BaseModBootstrapError("'card_uses' is only valid when the card is Exhaustive.")
            if uses_upgrade_value:
                raise BaseModBootstrapError(
                    "'card_uses_upgrade' is only valid when the card is Exhaustive."
                )

        if self.secondary_value is not None:
            try:
                secondary_value = int(self.secondary_value)
            except (TypeError, ValueError) as exc:
                raise BaseModBootstrapError("'secondary_value' must be an integer.") from exc
            object.__setattr__(self, "secondary_value", secondary_value)
        try:
            secondary_upgrade_value = int(self.secondary_upgrade)
        except (TypeError, ValueError) as exc:
            raise BaseModBootstrapError("'secondary_upgrade' must be an integer.") from exc
        if secondary_upgrade_value < 0:
            raise BaseModBootstrapError("'secondary_upgrade' cannot be negative.")
        if self.secondary_value is None and secondary_upgrade_value:
            raise BaseModBootstrapError("'secondary_upgrade' requires 'secondary_value'.")
        object.__setattr__(self, "secondary_upgrade", secondary_upgrade_value)

        object.__setattr__(self, "keyword_values", value_mapping)
        object.__setattr__(self, "keyword_upgrades", upgrade_mapping)
        attack_effect = _coerce_mapping(self.attack_effect, _ATTACK_EFFECT_ALIASES, "attack effect")
        object.__setattr__(self, "attack_effect", attack_effect)

        placeholders = _compute_placeholders(tuple(canonical_keywords))
        if has_exhaustive_keyword:
            placeholders.setdefault("uses", KEYWORD_PLACEHOLDERS.get("exhaustive", "!stslib:ex!"))
        object.__setattr__(self, "_placeholders", placeholders)

        object.__setattr__(
            self,
            "_normalised_localizations",
            _normalise_localisations(self.localizations or {}),
        )
        object.__setattr__(
            self,
            "localizations",
            MappingProxyType(dict(self._normalised_localizations)),
        )

        resolved_effects: List[EffectSpec] = []
        if self.card_type != "ATTACK" and self.effect:
            primary_field = _EFFECT_VALUE_FIELD[self.effect]
            resolved_effects.append(
                _normalise_effect_descriptor(
                    self,
                    self.effect,
                    default_target=self.target,
                    default_field=primary_field,
                )
            )
        additional_effects = _normalise_effect_sequence(
            self,
            self.effects,
            default_target=self.target,
            default_field=self.value_field,
        )
        if additional_effects:
            resolved_effects.extend(additional_effects)
        object.__setattr__(self, "_resolved_effects", tuple(resolved_effects))

        object.__setattr__(
            self,
            "_on_draw_effects",
            _normalise_effect_sequence(
                self,
                self.on_draw,
                default_target=self.target,
                default_field=self.value_field,
            ),
        )
        object.__setattr__(
            self,
            "_on_discard_effects",
            _normalise_effect_sequence(
                self,
                self.on_discard,
                default_target=self.target,
                default_field=self.value_field,
            ),
        )

    @property
    def value_field(self) -> str:
        if self.card_type == "ATTACK":
            return "damage"
        if not self.effect:
            return "magic"
        return _EFFECT_VALUE_FIELD[self.effect]

    def innerCardImage(self, path: str) -> "SimpleCardBlueprint":
        resolved = validate_inner_card_image(Path(path))
        object.__setattr__(self, "inner_image_source", str(resolved))
        object.__setattr__(self, "_inner_image_result", None)
        object.__setattr__(self, "image", None)
        return self

    def inner_card_image(self, path: str) -> "SimpleCardBlueprint":
        return self.innerCardImage(path)

    def _ensure_inner_card_image(self, project: "ModProject") -> Optional[InnerCardImageResult]:
        if not self.inner_image_source:
            return None
        if self._inner_image_result is None:
            result = prepare_inner_card_image(project, self)
            object.__setattr__(self, "_inner_image_result", result)
            object.__setattr__(self, "image", result.resource_path)
        return self._inner_image_result

    # ------------------------------------------------------------------
    # localisation helpers
    # ------------------------------------------------------------------
    def localization_languages(self, default_language: Optional[str] = "eng") -> Tuple[str, ...]:
        """Return the languages that should be emitted for this blueprint."""

        languages = set(self._normalised_localizations)
        if default_language:
            languages.add(_normalise_language_code(default_language))
        return tuple(sorted(languages))

    def resolve_localization(
        self,
        language: str,
        *,
        default_language: Optional[str] = "eng",
    ) -> Optional[ResolvedCardLocalization]:
        """Return the resolved localisation payload for ``language``."""

        code = _normalise_language_code(language)
        default_code = _normalise_language_code(default_language) if default_language else None
        override = self._normalised_localizations.get(code)
        if override is None and code != default_code:
            return None
        base = CardLocalizationEntry(title=self.title, description=self.description)
        entry = _merge_localization_entries(base, override) if override else base
        return _resolve_localization_entry(self, entry)


class SimpleCardFactory:
    """Construct :class:`CustomCard` subclasses from blueprints."""

    def __init__(self, blueprint: SimpleCardBlueprint, project: "ModProject") -> None:
        self.blueprint = blueprint
        self.project = project

    def build_factory(self) -> Callable[[], object]:
        card_class = self._build_card_class()

        def factory() -> object:
            color = self._resolve_color()
            return card_class(color)

        return factory

    # ------------------------------------------------------------------
    def _resolve_color(self) -> object:
        if self.blueprint.color_id:
            CardColor = _cardcrawl().cards.AbstractCard.CardColor
            return _resolve_enum(CardColor, self.blueprint.color_id, "card color")
        color_enum = getattr(self.project, "_color_enum", None)
        if color_enum is not None:
            return color_enum
        if hasattr(self.project, "runtime_color_enum"):
            return self.project.runtime_color_enum()
        raise BaseModBootstrapError(
            "No card colour available. Define a colour or set 'color_id' on the blueprint."
        )

    def _build_card_class(self) -> type:
        blueprint = self.blueprint
        cardcrawl = _cardcrawl()
        basemod = _basemod()

        CardType = cardcrawl.cards.AbstractCard.CardType
        CardTarget = cardcrawl.cards.AbstractCard.CardTarget
        CardRarity = cardcrawl.cards.AbstractCard.CardRarity

        card_type = _resolve_enum(CardType, blueprint.card_type, "card type")
        card_target = _resolve_enum(CardTarget, blueprint.target, "card target")
        card_rarity = _resolve_enum(CardRarity, blueprint.rarity, "card rarity")

        if blueprint.card_type == "ATTACK" and blueprint.target not in {"ENEMY", "ALL_ENEMY"}:
            raise BaseModBootstrapError("Attack cards must target ENEMY or ALL_ENEMY when using the simple factory.")
        if blueprint.effect in _SELF_EFFECTS and blueprint.target not in {"SELF", "SELF_AND_ENEMY", "ALL"}:
            raise BaseModBootstrapError(
                f"Effect '{blueprint.effect}' requires a self-facing target (SELF or SELF_AND_ENEMY)."
            )
        if blueprint.effect in _ENEMY_EFFECTS and blueprint.target not in {"ENEMY", "SELF_AND_ENEMY"}:
            raise BaseModBootstrapError(
                f"Effect '{blueprint.effect}' requires an enemy-facing target (ENEMY or SELF_AND_ENEMY)."
            )

        blueprint._ensure_inner_card_image(self.project)
        image_path = blueprint.image or self.project.resource_path(f"images/cards/{blueprint.identifier}.png")
        value_field = blueprint.value_field
        attack_effect = _resolve_enum(
            cardcrawl.actions.AbstractGameAction.AttackEffect, blueprint.attack_effect, "attack effect"
        )

        keyword_amounts: Dict[str, int] = {k: int(v) for k, v in blueprint.keyword_values.items()}
        keyword_upgrades: Dict[str, int] = {k: int(v) for k, v in blueprint.keyword_upgrades.items()}

        class GeneratedCard(basemod.abstracts.CustomCard):  # type: ignore[misc]
            ID = blueprint.identifier
            IMG = image_path
            COST = blueprint.cost

            def __init__(self, color: object) -> None:
                description = _format_description(
                    blueprint.description,
                    blueprint.value,
                    field=value_field,
                    placeholders=blueprint._placeholders,
                )
                super().__init__(
                    self.ID,
                    blueprint.title,
                    self.IMG,
                    blueprint.cost,
                    description,
                    card_type,
                    color,
                    card_rarity,
                    card_target,
                )
                self._simple_blueprint = blueprint
                self.simple_color = color
                if value_field == "damage":
                    self.baseDamage = blueprint.value
                    self.damage = blueprint.value
                    if blueprint.target == "ALL_ENEMY":
                        self.isMultiDamage = True
                elif value_field == "block":
                    self.baseBlock = blueprint.value
                    self.block = blueprint.value
                else:
                    self.baseMagicNumber = blueprint.value
                    self.magicNumber = blueprint.value
                if blueprint.secondary_value is not None:
                    self.baseSecondMagicNumber = blueprint.secondary_value
                    self.secondMagicNumber = blueprint.secondary_value
                    self.isSecondMagicNumberModified = False
                if blueprint.target == "ALL_ENEMY":
                    self.damageTypeForTurn = cardcrawl.cards.DamageInfo.DamageType.NORMAL
                if blueprint.keywords:
                    spire_api = _spire()
                    registry = _keyword_registry()
                    for keyword in blueprint.keywords:
                        amount = keyword_amounts.get(keyword)
                        upgrade = keyword_upgrades.get(keyword)
                        metadata = registry.resolve(keyword)
                        if metadata is not None:
                            registry.attach_to_card(
                                self,
                                keyword,
                                amount=amount,
                                upgrade=upgrade,
                            )
                            continue
                        spire_api.apply_keyword(
                            self,
                            keyword,
                            amount=amount,
                            upgrade=upgrade,
                        )
                self.initializeDescription()

            def use(self, player: object, monster: Optional[object]) -> None:
                if blueprint.card_type == "ATTACK":
                    _play_attack(self, player, monster, blueprint, attack_effect)
                    if blueprint._resolved_effects:
                        _execute_effect_sequence(
                            self, player, monster, blueprint, blueprint._resolved_effects
                        )
                else:
                    _execute_effect_sequence(
                        self, player, monster, blueprint, blueprint._resolved_effects
                    )
                _keyword_registry().trigger(self, player, monster)

            def upgrade(self) -> None:
                if not self.upgraded:
                    self.upgradeName()
                    if blueprint.upgrade_value:
                        if value_field == "damage":
                            self.upgradeDamage(blueprint.upgrade_value)
                        elif value_field == "block":
                            self.upgradeBlock(blueprint.upgrade_value)
                        else:
                            self.upgradeMagicNumber(blueprint.upgrade_value)
                    if blueprint.secondary_value is not None and blueprint.secondary_upgrade:
                        if hasattr(self, "upgradeSecondMagicNumber"):
                            self.upgradeSecondMagicNumber(blueprint.secondary_upgrade)
                        else:
                            self.baseSecondMagicNumber += blueprint.secondary_upgrade
                            self.secondMagicNumber += blueprint.secondary_upgrade
                    self.initializeDescription()

            def triggerWhenDrawn(self) -> None:
                try:
                    super().triggerWhenDrawn()
                except AttributeError:
                    pass
                if blueprint._on_draw_effects:
                    player = _current_player()
                    if player is not None:
                        _execute_effect_sequence(
                            self, player, None, blueprint, blueprint._on_draw_effects
                        )

            def triggerOnDiscard(self) -> None:
                try:
                    super().triggerOnDiscard()
                except AttributeError:
                    pass
                if blueprint._on_discard_effects:
                    player = _current_player()
                    if player is not None:
                        _execute_effect_sequence(
                            self, player, None, blueprint, blueprint._on_discard_effects
                        )

            def makeCopy(self):
                return type(self)(self.simple_color)

        GeneratedCard.__name__ = f"{blueprint.identifier}Card"
        return GeneratedCard


def _play_attack(card: object, player: object, monster: Optional[object], blueprint: SimpleCardBlueprint, attack_effect: object) -> None:
    cardcrawl = _cardcrawl()
    actions = cardcrawl.actions.common
    DamageInfo = cardcrawl.cards.DamageInfo
    if blueprint.target == "ALL_ENEMY":
        amounts = getattr(card, "multiDamage", None)
        if not amounts:
            amounts = [card.damage]
        action = actions.DamageAllEnemiesAction(
            player,
            amounts,
            card.damageTypeForTurn,
            attack_effect,
        )
    else:
        monster = _require_monster(monster, blueprint.target, "attack")
        info = DamageInfo(player, card.damage, card.damageTypeForTurn)
        action = actions.DamageAction(monster, info, attack_effect)
    _enqueue_action(action)


def _execute_effect_sequence(
    card: object,
    player: object,
    monster: Optional[object],
    blueprint: SimpleCardBlueprint,
    effects: Sequence[EffectSpec],
) -> None:
    for spec in effects:
        _execute_effect_spec(card, player, monster, blueprint, spec)


def _execute_effect_spec(
    card: object,
    player: object,
    monster: Optional[object],
    blueprint: SimpleCardBlueprint,
    spec: EffectSpec,
) -> None:
    amount = _resolve_effect_amount(card, blueprint, spec)
    if spec.callback is not None:
        spec.callback(card, player, monster, amount)
        _run_follow_up_actions(card, player, monster, blueprint, amount, spec.follow_up)
        return

    effect = spec.effect
    if effect is None:
        _run_follow_up_actions(card, player, monster, blueprint, amount, spec.follow_up)
        return

    effect = _normalise(effect)
    cardcrawl = _cardcrawl()
    actions = cardcrawl.actions.common
    powers = cardcrawl.powers
    target_label = spec.target or blueprint.target

    if effect == "block":
        if player is not None:
            action = actions.GainBlockAction(player, player, amount)
            _enqueue_action(action)
        _run_follow_up_actions(card, player, monster, blueprint, amount, spec.follow_up)
        return
    if effect == "draw":
        if player is not None:
            action = actions.DrawCardAction(player, amount)
            _enqueue_action(action)
        _run_follow_up_actions(card, player, monster, blueprint, amount, spec.follow_up)
        return
    if effect == "energy":
        action = actions.GainEnergyAction(amount)
        _enqueue_action(action)
        _run_follow_up_actions(card, player, monster, blueprint, amount, spec.follow_up)
        return
    if effect in {"strength", "dexterity", "artifact", "focus"}:
        if player is not None:
            power_cls = getattr(powers, _POWER_CLASS[effect])
            power = power_cls(player, amount)
            action = actions.ApplyPowerAction(player, player, power, amount)
            _enqueue_action(action)
        _run_follow_up_actions(card, player, monster, blueprint, amount, spec.follow_up)
        return

    if effect == "poison":
        for target in _resolve_monster_targets(monster, target_label, effect):
            power_cls = getattr(powers, _POWER_CLASS[effect])
            power = power_cls(target, player, amount)
            action = actions.ApplyPowerAction(target, player, power, amount)
            _enqueue_action(action)
        _run_follow_up_actions(card, player, monster, blueprint, amount, spec.follow_up)
        return
    if effect in {"weak", "vulnerable", "frail"}:
        for target in _resolve_monster_targets(monster, target_label, effect):
            power_cls = getattr(powers, _POWER_CLASS[effect])
            power = power_cls(target, amount, False)
            action = actions.ApplyPowerAction(target, player, power, amount)
            _enqueue_action(action)
        _run_follow_up_actions(card, player, monster, blueprint, amount, spec.follow_up)
        return

    raise BaseModBootstrapError(f"Unhandled effect '{effect}'.")


def _resolve_monster_targets(
    monster: Optional[object], target_label: str, effect: str
) -> Sequence[object]:
    if target_label == "ALL_ENEMY":
        return [enemy for enemy in _iter_monsters() if enemy is not None]
    resolved = _require_monster(monster, target_label, effect)
    return [resolved]


def _resolve_effect_amount(card: object, blueprint: SimpleCardBlueprint, spec: EffectSpec) -> int:
    if spec.amount is not None:
        return int(spec.amount)
    if spec.amount_key:
        value = getattr(card, spec.amount_key, 0)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return int(blueprint.value)


def _run_follow_up_actions(
    card: object,
    player: object,
    monster: Optional[object],
    blueprint: SimpleCardBlueprint,
    amount: int,
    actions: Sequence[ActionSpec],
) -> None:
    if not actions:
        return
    spire_api = _spire()
    for action_spec in actions:
        if action_spec.callback is not None:
            action_spec.callback(card, player, monster, amount)
            continue
        if not action_spec.action:
            continue
        action_cls = spire_api.action(action_spec.action)
        args = [
            _resolve_action_arg(
                arg, card, player, monster, blueprint, amount, action_spec.action
            )
            for arg in action_spec.args
        ]
        kwargs = {
            key: _resolve_action_arg(
                value, card, player, monster, blueprint, amount, action_spec.action
            )
            for key, value in action_spec.kwargs.items()
        }
        action = action_cls(*args, **kwargs)
        _enqueue_action(action)


def _resolve_action_arg(
    value: Any,
    card: object,
    player: object,
    monster: Optional[object],
    blueprint: SimpleCardBlueprint,
    amount: int,
    label: str,
) -> Any:
    if isinstance(value, str):
        key = _normalise(value)
        if key == "player":
            return player
        if key == "card":
            return card
        if key == "monster":
            return _require_monster(monster, blueprint.target, label)
        if key == "amount":
            return amount
        if key == "magic":
            return getattr(card, "magicNumber", 0)
        if key in {"secondary", "second"}:
            return getattr(card, "secondMagicNumber", 0)
        if key == "damage":
            return getattr(card, "damage", 0)
        if key == "block":
            return getattr(card, "block", 0)
    if isinstance(value, list):
        return [
            _resolve_action_arg(item, card, player, monster, blueprint, amount, label)
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _resolve_action_arg(item, card, player, monster, blueprint, amount, label)
            for item in value
        )
    if isinstance(value, dict):
        return {
            key: _resolve_action_arg(item, card, player, monster, blueprint, amount, label)
            for key, item in value.items()
        }
    return value


def _iter_monsters() -> Sequence[object]:
    dungeon = _cardcrawl().dungeons.AbstractDungeon
    monsters = getattr(dungeon, "getMonsters", lambda: None)()
    if monsters is None:
        room = getattr(dungeon, "getCurrRoom", lambda: None)()
        monsters = getattr(room, "monsters", None) if room else None
    if monsters is None:
        monsters = getattr(dungeon, "monsters", None)
    collection = getattr(monsters, "monsters", None) if monsters is not None else None
    if collection is None:
        return []
    return [enemy for enemy in collection if enemy is not None]


def _current_player() -> Optional[object]:
    return getattr(_cardcrawl().dungeons.AbstractDungeon, "player", None)


def register_simple_card(project: "ModProject", blueprint: SimpleCardBlueprint) -> None:
    """Register ``blueprint`` against ``project`` using the simple factory."""

    factory = SimpleCardFactory(blueprint, project).build_factory()
    project.add_card(blueprint.identifier, factory, basic=blueprint.starter)


def build_card_localizations(
    blueprints: Iterable[SimpleCardBlueprint],
    *,
    default_language: str = "eng",
) -> Dict[str, Dict[str, Any]]:
    """Return cards.json payloads grouped by language for ``blueprints``."""

    aggregated: Dict[str, Dict[str, Any]] = {}
    default_code = _normalise_language_code(default_language) if default_language else ""
    for blueprint in blueprints:
        for language in blueprint.localization_languages(default_code or None):
            resolved = blueprint.resolve_localization(language, default_language=default_code or None)
            if resolved is None:
                continue
            card_entry: Dict[str, Any] = {
                "NAME": resolved.title,
                "DESCRIPTION": resolved.description,
                "UPGRADE_DESCRIPTION": resolved.upgrade_description,
            }
            if resolved.extended_description:
                card_entry["EXTENDED_DESCRIPTION"] = list(resolved.extended_description)
            aggregated.setdefault(language, {})[blueprint.identifier] = card_entry
    return aggregated


PLUGIN_MANAGER.expose("SimpleCardBlueprint", SimpleCardBlueprint)
PLUGIN_MANAGER.expose("register_simple_card", register_simple_card)
PLUGIN_MANAGER.expose("register_keyword_placeholder", register_keyword_placeholder)
PLUGIN_MANAGER.expose("keyword_placeholders", KEYWORD_PLACEHOLDERS)
PLUGIN_MANAGER.expose("build_card_localizations", build_card_localizations)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.cards", alias="basemod_cards")

__all__ = [
    "ActionSpec",
    "EffectSpec",
    "CardLocalizationEntry",
    "ResolvedCardLocalization",
    "SimpleCardBlueprint",
    "SimpleCardFactory",
    "register_simple_card",
    "register_keyword_placeholder",
    "build_card_localizations",
]
