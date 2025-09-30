from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.basemod_wrapper.loader import BaseModBootstrapError
from modules.basemod_wrapper.project import ModProject
from modules.basemod_wrapper.card_assets import InnerCardImageResult, ensure_pillow
from tests.stubs import (
    StubActionManager,
    StubApplyPowerAction,
    StubArtifactPower,
    StubCardColor,
    StubCustomCard,
    StubDamageAction,
    StubDamageAllEnemiesAction,
    StubDamageInfo,
    StubDexterityPower,
    StubDrawCardAction,
    StubFocusPower,
    StubGainBlockAction,
    StubGainEnergyAction,
    StubPoisonPower,
    StubSpire,
    StubStrengthPower,
    StubVulnerablePower,
    StubWeakPower,
    StubFrailPower,
)


def test_inner_card_image_requires_exact_dimensions(tmp_path, use_real_dependencies):
    Image = ensure_pillow()
    image_path = tmp_path / "bad.png"
    Image.new("RGBA", (250, 190), (255, 0, 0, 255)).save(image_path)

    blueprint = SimpleCardBlueprint(
        identifier="BuddyBlock",
        title="Buddy Block",
        description="Gain {block} block.",
        cost=1,
        card_type="skill",
        target="self",
        rarity="common",
        value=5,
        effect="block",
    )

    with pytest.raises(BaseModBootstrapError) as excinfo:
        blueprint.innerCardImage(str(image_path))
    assert str(excinfo.value) == "innerCardImage MUST be 500x380"


def test_inner_card_image_resets_blueprint_image(tmp_path, use_real_dependencies):
    Image = ensure_pillow()
    image_path = tmp_path / "good.png"
    Image.new("RGBA", (500, 380), (255, 255, 255, 255)).save(image_path)

    blueprint = SimpleCardBlueprint(
        identifier="BuddyPortrait",
        title="Buddy Portrait",
        description="Gain {block} Block.",
        cost=1,
        card_type="skill",
        target="self",
        rarity="common",
        effect="block",
        value=8,
        image="buddy/images/cards/portrait.png",
    )

    returned = blueprint.innerCardImage(str(image_path))

    assert returned is blueprint
    assert blueprint.inner_image_source == str(image_path.resolve())
    assert blueprint.image is None
    assert blueprint._inner_image_result is None


def test_factory_uses_prepared_inner_card_image(monkeypatch, stubbed_runtime, tmp_path):
    Image = ensure_pillow()
    source = tmp_path / "source.png"
    Image.new("RGBA", (500, 380), (0, 0, 255, 255)).save(source)

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
    ).innerCardImage(str(source))

    expected = InnerCardImageResult(
        resource_path="buddy/images/cards/BuddyStrike.png",
        small_asset_path=tmp_path / "dest.png",
        portrait_asset_path=tmp_path / "dest_p.png",
    )
    calls = {"count": 0}

    def fake_prepare(proj, bp):
        calls["count"] += 1
        assert proj is project
        assert bp is blueprint
        return expected

    monkeypatch.setattr("modules.basemod_wrapper.cards.prepare_inner_card_image", fake_prepare)

    project.add_simple_card(blueprint)
    registration = project.cards["BuddyStrike"]
    card = registration.factory()

    assert blueprint.image == expected.resource_path
    assert card.IMG == expected.resource_path
    assert calls["count"] == 1


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
    assert spire_stub.calls[0]["keyword"] == "retain"

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


def test_keyword_normalisation_and_settings(stubbed_runtime):
    _, _, spire_stub = stubbed_runtime
    project = ModProject("buddy", "Buddy Mod", "Buddy", "Testing")
    project._color_enum = "BUDDY_COLOR"

    blueprint = SimpleCardBlueprint(
        identifier="BuddyKeywords",
        title="Buddy Keywords",
        description="Do keyword things.",
        cost=0,
        card_type="skill",
        target="self",
        effect="block",
        rarity="common",
        value=0,
        keywords=("Inate", "stslib:Exhaustive", "Exhaust", "retain", "retain"),
        keyword_values={"stslib:exhaustive": "2"},
        keyword_upgrades={"exhaustive": 1},
        card_uses=2,
    )

    assert blueprint.keywords == ("innate", "exhaustive", "exhaust", "retain")
    assert blueprint.keyword_values == {"exhaustive": 2}
    assert blueprint.keyword_upgrades == {"exhaustive": 1}

    project.add_simple_card(blueprint)
    card = project.cards["BuddyKeywords"].factory()

    exhaustive_call = next(call for call in spire_stub.calls if call["keyword"] == "exhaustive")
    assert exhaustive_call["amount"] == 2
    assert exhaustive_call["upgrade"] == 1

    assert card.exhaust is False  # base keywords handled by real API, stub untouched


def test_exhaustive_requires_card_uses():
    with pytest.raises(BaseModBootstrapError) as excinfo:
        SimpleCardBlueprint(
            identifier="BuddyNoUses",
            title="Buddy No Uses",
            description="Gain {block} Block.",
            cost=1,
            card_type="skill",
            target="self",
            effect="block",
            rarity="common",
            value=5,
            keywords=("stslib:Exhaustive",),
        )

    assert "Exhaustive cards must define 'card_uses'" in str(excinfo.value)


def test_card_uses_must_be_positive_integer(use_real_dependencies):
    with pytest.raises(BaseModBootstrapError) as excinfo:
        SimpleCardBlueprint(
            identifier="BuddyZeroUses",
            title="Buddy Zero Uses",
            description="Gain {block} Block.",
            cost=1,
            card_type="skill",
            target="self",
            effect="block",
            rarity="common",
            value=5,
            keywords=("stslib:Exhaustive",),
            card_uses=0,
        )

    assert "positive integer" in str(excinfo.value)


def test_card_uses_upgrade_requires_exhaustive_keyword(use_real_dependencies):
    with pytest.raises(BaseModBootstrapError) as excinfo:
        SimpleCardBlueprint(
            identifier="BuddyUpgradeUses",
            title="Buddy Upgrade Uses",
            description="Gain {block} Block.",
            cost=1,
            card_type="skill",
            target="self",
            effect="block",
            rarity="common",
            value=5,
            card_uses_upgrade=1,
        )

    assert "only valid when the card is Exhaustive" in str(excinfo.value)


def test_exhaustive_description_uses_dynamic_token(stubbed_runtime):
    project = ModProject("buddy", "Buddy Mod", "Buddy", "Testing")
    project._color_enum = "BUDDY_COLOR"

    blueprint = SimpleCardBlueprint(
        identifier="BuddyUses",
        title="Buddy Uses",
        description="Gain {block} Block. Exhaustive {uses}.",
        cost=1,
        card_type="skill",
        target="self",
        effect="block",
        rarity="common",
        value=12,
        keywords=("stslib:Exhaustive",),
        card_uses=2,
    )

    project.add_simple_card(blueprint)
    card = project.cards["BuddyUses"].factory()

    assert card.rawDescription == "Gain 12 Block. Exhaustive !stslib:ex!."


def test_uses_placeholder_requires_exhaustive_keyword():
    with pytest.raises(BaseModBootstrapError) as excinfo:
        SimpleCardBlueprint(
            identifier="BuddyInvalidUses",
            title="Buddy Invalid Uses",
            description="Deal {damage} damage. Track {uses} anyway.",
            cost=1,
            card_type="attack",
            target="enemy",
            rarity="common",
            value=7,
        )

    assert "not Exhaustive" in str(excinfo.value)


def test_secondary_values_follow_ups_and_hooks(stubbed_runtime):
    cardcrawl_stub, action_manager, spire_stub = stubbed_runtime

    class TempHPAction:
        def __init__(self, target, source, amount) -> None:
            self.target = target
            self.source = source
            self.amount = amount
            self.label = "temp_hp"

    class RemoveTempHPAction:
        def __init__(self, target, source) -> None:
            self.target = target
            self.source = source
            self.label = "remove_temp_hp"

    spire_stub.register_action("AddTemporaryHPAction", TempHPAction)
    spire_stub.register_action("RemoveAllTemporaryHPAction", RemoveTempHPAction)

    project = ModProject("combo", "Combo", "Buddy", "Testing")
    project._color_enum = "BUDDY_COLOR"

    callbacks: list[tuple[str, int]] = []

    def effect_callback(card, player, monster, amount):
        callbacks.append(("effect", amount))

    def follow_up_callback(card, player, monster, amount):
        callbacks.append(("follow", amount))

    blueprint = SimpleCardBlueprint(
        identifier="BuddyCombo",
        title="Buddy Combo",
        description="Gain {block} Block. Apply {secondary} Weak and add temp HP.",
        cost=1,
        card_type="skill",
        target="self_and_enemy",
        rarity="rare",
        effect="block",
        value=9,
        secondary_value=2,
        secondary_upgrade=1,
        effects=[
            {
                "effect": "weak",
                "target": "enemy",
                "amount": "secondary",
                "follow_up": [
                    {"action": "AddTemporaryHPAction", "args": ["monster", "player", "amount"]},
                    {"action": "RemoveAllTemporaryHPAction", "kwargs": {"target": "player", "source": "monster"}},
                    {"callable": follow_up_callback},
                ],
            },
            {"callable": effect_callback},
        ],
        on_draw=[{"effect": "draw", "amount": 1}],
        on_discard=[{"effect": "energy", "amount": 1}],
    )

    project.add_simple_card(blueprint)
    card = project.cards["BuddyCombo"].factory()

    assert getattr(card, "secondMagicNumber") == 2

    player = object()
    monster = object()
    cardcrawl_stub.dungeons.AbstractDungeon.player = player

    card.use(player, monster)

    assert isinstance(action_manager.actions[0], StubGainBlockAction)
    assert isinstance(action_manager.actions[1], StubApplyPowerAction)
    assert isinstance(action_manager.actions[2], TempHPAction)
    assert isinstance(action_manager.actions[3], RemoveTempHPAction)
    assert action_manager.actions[2].amount == 2

    assert callbacks == [("follow", 2), ("effect", 9)]

    action_manager.clear()

    card.triggerWhenDrawn()
    assert isinstance(action_manager.actions[0], StubDrawCardAction)
    action_manager.clear()

    card.triggerOnDiscard()
    assert isinstance(action_manager.actions[0], StubGainEnergyAction)

    card.upgrade()
    assert getattr(card, "secondMagicNumber") == 3


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
