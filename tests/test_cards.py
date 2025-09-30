from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.basemod_wrapper.loader import BaseModBootstrapError
from modules.basemod_wrapper.project import ModProject


class StubActionManager:
    def __init__(self) -> None:
        self.actions = []

    def addToBottom(self, action) -> None:
        self.actions.append(action)

    def pop(self):
        return self.actions.pop(0)

    def clear(self) -> None:
        self.actions.clear()


class StubDamageAction:
    def __init__(self, target, info, effect) -> None:
        self.target = target
        self.info = info
        self.effect = effect


class StubDamageAllEnemiesAction:
    def __init__(self, player, amounts, damage_type, effect) -> None:
        self.player = player
        self.amounts = list(amounts)
        self.damage_type = damage_type
        self.effect = effect


class StubGainBlockAction:
    def __init__(self, target, source, amount) -> None:
        self.target = target
        self.source = source
        self.amount = amount


class StubDrawCardAction:
    def __init__(self, player, amount) -> None:
        self.player = player
        self.amount = amount


class StubGainEnergyAction:
    def __init__(self, amount) -> None:
        self.amount = amount


class StubApplyPowerAction:
    def __init__(self, target, source, power, amount) -> None:
        self.target = target
        self.source = source
        self.power = power
        self.amount = amount


class StubDamageInfo:
    class DamageType:
        NORMAL = "NORMAL"

    def __init__(self, source, amount, damage_type) -> None:
        self.source = source
        self.base = amount
        self.output = amount
        self.type = damage_type


class StubCustomCard:
    def __init__(self, card_id, name, img, cost, description, card_type, color, rarity, target) -> None:
        self.cardID = card_id
        self.name = name
        self.rawDescription = description
        self.cost = cost
        self.type = card_type
        self.color = color
        self.rarity = rarity
        self.target = target
        self.baseDamage = 0
        self.damage = 0
        self.baseBlock = 0
        self.block = 0
        self.baseMagicNumber = 0
        self.magicNumber = 0
        self.multiDamage = []
        self.damageTypeForTurn = StubDamageInfo.DamageType.NORMAL
        self.isMultiDamage = False
        self.upgraded = False

    def initializeDescription(self) -> None:
        self.description = self.rawDescription

    def upgradeName(self) -> None:
        self.upgraded = True

    def upgradeDamage(self, amount: int) -> None:
        self.baseDamage += amount
        self.damage = self.baseDamage

    def upgradeBlock(self, amount: int) -> None:
        self.baseBlock += amount
        self.block = self.baseBlock

    def upgradeMagicNumber(self, amount: int) -> None:
        self.baseMagicNumber += amount
        self.magicNumber = self.baseMagicNumber


class StubStrengthPower:
    def __init__(self, owner, amount) -> None:
        self.owner = owner
        self.amount = amount
        self.name = "Strength"


class StubWeakPower:
    def __init__(self, owner, amount, is_source_monster) -> None:
        self.owner = owner
        self.amount = amount
        self.is_source_monster = is_source_monster
        self.name = "Weak"


class StubPoisonPower:
    def __init__(self, owner, source, amount) -> None:
        self.owner = owner
        self.source = source
        self.amount = amount
        self.name = "Poison"


class StubDexterityPower:
    def __init__(self, owner, amount) -> None:
        self.owner = owner
        self.amount = amount
        self.name = "Dexterity"


class StubArtifactPower:
    def __init__(self, owner, amount) -> None:
        self.owner = owner
        self.amount = amount
        self.name = "Artifact"


class StubFocusPower:
    def __init__(self, owner, amount) -> None:
        self.owner = owner
        self.amount = amount
        self.name = "Focus"


class StubVulnerablePower:
    def __init__(self, owner, amount, is_source_monster) -> None:
        self.owner = owner
        self.amount = amount
        self.is_source_monster = is_source_monster
        self.name = "Vulnerable"


class StubFrailPower:
    def __init__(self, owner, amount, is_source_monster) -> None:
        self.owner = owner
        self.amount = amount
        self.is_source_monster = is_source_monster
        self.name = "Frail"


class StubCardColor:
    RED = "RED"
    GREEN = "GREEN"
    BLUE = "BLUE"
    PURPLE = "PURPLE"

    @staticmethod
    def valueOf(name: str):
        return getattr(StubCardColor, name)


class StubSpire:
    def __init__(self) -> None:
        self.calls = []

    def apply_keyword(self, card, keyword, *, amount=None) -> None:
        self.calls.append((card, keyword, amount))


@pytest.fixture()
def stubbed_runtime(monkeypatch):
    action_manager = StubActionManager()
    attack_effects = SimpleNamespace(
        SLASH_DIAGONAL="SLASH_DIAGONAL",
        SLASH_HORIZONTAL="SLASH_HORIZONTAL",
        NONE="NONE",
    )
    abstract_card = SimpleNamespace(
        CardType=SimpleNamespace(ATTACK="ATTACK", SKILL="SKILL", POWER="POWER"),
        CardTarget=SimpleNamespace(
            ENEMY="ENEMY",
            ALL_ENEMY="ALL_ENEMY",
            SELF="SELF",
            SELF_AND_ENEMY="SELF_AND_ENEMY",
            NONE="NONE",
            ALL="ALL",
        ),
        CardRarity=SimpleNamespace(
            BASIC="BASIC",
            COMMON="COMMON",
            UNCOMMON="UNCOMMON",
            RARE="RARE",
            SPECIAL="SPECIAL",
            CURSE="CURSE",
        ),
        CardColor=StubCardColor,
    )
    cards_namespace = SimpleNamespace(AbstractCard=abstract_card, DamageInfo=StubDamageInfo)
    common_actions = SimpleNamespace(
        DamageAction=StubDamageAction,
        DamageAllEnemiesAction=StubDamageAllEnemiesAction,
        GainBlockAction=StubGainBlockAction,
        DrawCardAction=StubDrawCardAction,
        GainEnergyAction=StubGainEnergyAction,
        ApplyPowerAction=StubApplyPowerAction,
    )
    actions_namespace = SimpleNamespace(AbstractGameAction=SimpleNamespace(AttackEffect=attack_effects), common=common_actions)
    powers_namespace = SimpleNamespace(
        StrengthPower=StubStrengthPower,
        WeakPower=StubWeakPower,
        PoisonPower=StubPoisonPower,
        DexterityPower=StubDexterityPower,
        ArtifactPower=StubArtifactPower,
        FocusPower=StubFocusPower,
        VulnerablePower=StubVulnerablePower,
        FrailPower=StubFrailPower,
    )
    dungeon_namespace = SimpleNamespace(AbstractDungeon=SimpleNamespace(actionManager=action_manager))
    cardcrawl_stub = SimpleNamespace(
        cards=cards_namespace,
        actions=actions_namespace,
        powers=powers_namespace,
        dungeons=dungeon_namespace,
    )
    spire_stub = StubSpire()
    basemod_stub = SimpleNamespace(abstracts=SimpleNamespace(CustomCard=StubCustomCard))

    from modules.basemod_wrapper import cards as cards_module

    monkeypatch.setattr(cards_module, "_cardcrawl", lambda: cardcrawl_stub)
    monkeypatch.setattr(cards_module, "_basemod", lambda: basemod_stub)
    monkeypatch.setattr(cards_module, "_spire", lambda: spire_stub)

    yield cardcrawl_stub, action_manager, spire_stub

    action_manager.clear()
    spire_stub.calls.clear()


def test_attack_blueprint_registers_basic_card(stubbed_runtime):
    _, action_manager, _ = stubbed_runtime
    project = ModProject("buddy", "Buddy Mod", "Buddy", "Testing")
    project._color_enum = "BUDDY_COLOR"

    blueprint = SimpleCardBlueprint(
        identifier="BuddyStrike",
        title="Buddy Strike",
        description="Deal {damage} damage.",
        cost=1,
        card_type="attack",
        target="enemy",
        rarity="common",
        value=9,
        upgrade_value=4,
        starter=True,
        image="buddy/images/cards/strike.png",
    )
    project.add_simple_card(blueprint)

    registration = project.cards["BuddyStrike"]
    assert registration.make_basic is True

    card = registration.factory()
    player = object()
    monster = object()
    card.use(player, monster)
    action = action_manager.pop()
    assert isinstance(action, StubDamageAction)
    assert action.target is monster
    assert action.info.base == 9

    card.upgrade()
    assert card.damage == 13


def test_attack_all_enemies_uses_multidamage(stubbed_runtime):
    cardcrawl_stub, action_manager, _ = stubbed_runtime
    project = ModProject("buddy", "Buddy Mod", "Buddy", "Testing")
    project._color_enum = "BUDDY_COLOR"

    blueprint = SimpleCardBlueprint(
        identifier="BuddyWhirl",
        title="Buddy Whirl",
        description="Deal {damage} damage to ALL enemies.",
        cost=2,
        card_type="attack",
        target="all_enemies",
        rarity="uncommon",
        value=6,
        image="buddy/images/cards/whirl.png",
        attack_effect="slash_horizontal",
    )
    project.add_simple_card(blueprint)
    card = project.cards["BuddyWhirl"].factory()

    player = object()
    card.use(player, None)
    action = action_manager.pop()
    assert isinstance(action, StubDamageAllEnemiesAction)
    assert action.player is player
    assert action.amounts == [6]
    assert action.effect == cardcrawl_stub.actions.AbstractGameAction.AttackEffect.SLASH_HORIZONTAL


def test_skill_and_power_effects(stubbed_runtime):
    _, action_manager, spire_stub = stubbed_runtime
    project = ModProject("buddy", "Buddy Mod", "Buddy", "Testing")
    project._color_enum = "BUDDY_COLOR"

    block_blueprint = SimpleCardBlueprint(
        identifier="BuddyGuard",
        title="Buddy Guard",
        description="Gain {block} Block.",
        cost=1,
        card_type="skill",
        target="self",
        effect="block",
        rarity="common",
        value=12,
        upgrade_value=4,
        keywords=("retain",),
        keyword_values={"retain": 1},
        image="buddy/images/cards/guard.png",
    )
    project.add_simple_card(block_blueprint)
    block_card = project.cards["BuddyGuard"].factory()
    player = object()
    block_card.use(player, None)
    block_action = action_manager.pop()
    assert isinstance(block_action, StubGainBlockAction)
    assert block_action.amount == 12
    assert spire_stub.calls[0][1] == "retain"

    weak_blueprint = SimpleCardBlueprint(
        identifier="BuddyGlare",
        title="Buddy Glare",
        description="Apply {magic} Weak.",
        cost=1,
        card_type="skill",
        target="enemy",
        effect="weak",
        rarity="uncommon",
        value=2,
        image="buddy/images/cards/glare.png",
    )
    project.add_simple_card(weak_blueprint)
    weak_card = project.cards["BuddyGlare"].factory()
    monster = object()
    weak_card.use(player, monster)
    weak_action = action_manager.pop()
    assert isinstance(weak_action, StubApplyPowerAction)
    assert weak_action.amount == 2
    assert weak_action.power.name == "Weak"

    power_blueprint = SimpleCardBlueprint(
        identifier="BuddyFortify",
        title="Buddy Fortify",
        description="Gain {magic} Strength each turn.",
        cost=2,
        card_type="power",
        target="self",
        effect="strength",
        rarity="rare",
        value=2,
        image="buddy/images/cards/fortify.png",
    )
    project.add_simple_card(power_blueprint)
    power_card = project.cards["BuddyFortify"].factory()
    power_card.use(player, None)
    power_action = action_manager.pop()
    assert power_action.power.name == "Strength"
    assert power_action.amount == 2


def test_color_override_uses_card_enum(stubbed_runtime):
    _, _, _ = stubbed_runtime
    project = ModProject("buddy", "Buddy Mod", "Buddy", "Testing")

    blueprint = SimpleCardBlueprint(
        identifier="BuddyBolt",
        title="Buddy Bolt",
        description="Deal {damage} damage.",
        cost=1,
        card_type="attack",
        target="enemy",
        rarity="common",
        value=7,
        color_id="RED",
        image="buddy/images/cards/bolt.png",
    )
    project.add_simple_card(blueprint)
    card = project.cards["BuddyBolt"].factory()
    assert card.color == StubCardColor.RED


def test_invalid_skill_without_effect_raises(stubbed_runtime):
    with pytest.raises(BaseModBootstrapError):
        SimpleCardBlueprint(
            identifier="InvalidSkill",
            title="Invalid",
            description="No effect",
            cost=1,
            card_type="skill",
            target="self",
            rarity="common",
            value=1,
            image="invalid.png",
        )
