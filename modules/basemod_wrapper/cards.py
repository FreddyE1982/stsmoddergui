"""High level helpers for declaring simple Slay the Spire cards."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from importlib import import_module
from typing import Callable, Dict, Mapping, Optional, Sequence

from plugins import PLUGIN_MANAGER

from .loader import BaseModBootstrapError


@lru_cache(maxsize=1)
def _wrapper_module():
    return import_module("modules.basemod_wrapper")


def _cardcrawl():
    return getattr(_wrapper_module(), "cardcrawl")


def _basemod():
    return getattr(_wrapper_module(), "basemod")


def _spire():
    return getattr(_wrapper_module(), "spire")


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


def _format_description(description: str, value: int, *, field: str) -> str:
    if "{" not in description:
        return description
    values = {
        "value": value,
        "damage": value if field == "damage" else 0,
        "block": value if field == "block" else 0,
        "magic": value if field == "magic" else 0,
        "amount": value,
    }
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
    color_id: Optional[str] = None
    starter: bool = False
    keywords: Sequence[str] = field(default_factory=tuple)
    keyword_values: Mapping[str, int] = field(default_factory=dict)
    attack_effect: str = "SLASH_DIAGONAL"

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
            object.__setattr__(self, "keywords", (self.keywords,))
        else:
            object.__setattr__(self, "keywords", tuple(self.keywords))
        attack_effect = _coerce_mapping(self.attack_effect, _ATTACK_EFFECT_ALIASES, "attack effect")
        object.__setattr__(self, "attack_effect", attack_effect)

    @property
    def value_field(self) -> str:
        if self.card_type == "ATTACK":
            return "damage"
        if not self.effect:
            return "magic"
        return _EFFECT_VALUE_FIELD[self.effect]


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

        image_path = blueprint.image or self.project.resource_path(f"images/cards/{blueprint.identifier}.png")
        value_field = blueprint.value_field
        attack_effect = _resolve_enum(
            cardcrawl.actions.AbstractGameAction.AttackEffect, blueprint.attack_effect, "attack effect"
        )

        keyword_settings: Dict[str, int] = {k: int(v) for k, v in blueprint.keyword_values.items()}

        class GeneratedCard(basemod.abstracts.CustomCard):  # type: ignore[misc]
            ID = blueprint.identifier
            IMG = image_path
            COST = blueprint.cost

            def __init__(self, color: object) -> None:
                description = _format_description(blueprint.description, blueprint.value, field=value_field)
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
                if blueprint.target == "ALL_ENEMY":
                    self.damageTypeForTurn = cardcrawl.cards.DamageInfo.DamageType.NORMAL
                if blueprint.keywords:
                    spire_api = _spire()
                    for keyword in blueprint.keywords:
                        settings = {}
                        if keyword in keyword_settings:
                            settings["amount"] = keyword_settings[keyword]
                        spire_api.apply_keyword(self, keyword, amount=settings.get("amount"))
                self.initializeDescription()

            def use(self, player: object, monster: Optional[object]) -> None:
                if blueprint.card_type == "ATTACK":
                    _play_attack(self, player, monster, blueprint, attack_effect)
                else:
                    _play_effect(self, player, monster, blueprint)

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
                    self.initializeDescription()

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


def _play_effect(card: object, player: object, monster: Optional[object], blueprint: SimpleCardBlueprint) -> None:
    effect = blueprint.effect
    if effect is None:
        return
    cardcrawl = _cardcrawl()
    actions = cardcrawl.actions.common
    powers = cardcrawl.powers
    if effect == "block":
        action = actions.GainBlockAction(player, player, card.block)
        _enqueue_action(action)
        return
    if effect == "draw":
        action = actions.DrawCardAction(player, card.magicNumber)
        _enqueue_action(action)
        return
    if effect == "energy":
        action = actions.GainEnergyAction(card.magicNumber)
        _enqueue_action(action)
        return
    if effect in {"strength", "dexterity", "artifact", "focus"}:
        owner = player
        power_cls = getattr(powers, _POWER_CLASS[effect])
        power = power_cls(owner, card.magicNumber)
        action = actions.ApplyPowerAction(owner, player, power, card.magicNumber)
        _enqueue_action(action)
        return
    monster = _require_monster(monster, blueprint.target, effect)
    if effect == "poison":
        power_cls = getattr(powers, _POWER_CLASS[effect])
        power = power_cls(monster, player, card.magicNumber)
        action = actions.ApplyPowerAction(monster, player, power, card.magicNumber)
        _enqueue_action(action)
        return
    if effect in {"weak", "vulnerable", "frail"}:
        power_cls = getattr(powers, _POWER_CLASS[effect])
        power = power_cls(monster, card.magicNumber, False)
        action = actions.ApplyPowerAction(monster, player, power, card.magicNumber)
        _enqueue_action(action)
        return
    raise BaseModBootstrapError(f"Unhandled effect '{effect}'.")


def register_simple_card(project: "ModProject", blueprint: SimpleCardBlueprint) -> None:
    """Register ``blueprint`` against ``project`` using the simple factory."""

    factory = SimpleCardFactory(blueprint, project).build_factory()
    project.add_card(blueprint.identifier, factory, basic=blueprint.starter)


PLUGIN_MANAGER.expose("SimpleCardBlueprint", SimpleCardBlueprint)
PLUGIN_MANAGER.expose("register_simple_card", register_simple_card)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.cards", alias="basemod_cards")

__all__ = ["SimpleCardBlueprint", "SimpleCardFactory", "register_simple_card"]
