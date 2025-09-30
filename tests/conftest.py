from __future__ import annotations

from types import SimpleNamespace
from typing import Any
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.basemod_wrapper import cards as cards_module
from modules.basemod_wrapper import keywords as keywords_module
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

    class StubMonsterGroup:
        def __init__(self) -> None:
            self.monsters: list[Any] = []

        def getRandomMonster(self, _use_alive: bool):
            return self.monsters[0] if self.monsters else None

    class StubRoom:
        def __init__(self) -> None:
            self.monsters = StubMonsterGroup()

    class StubDungeon:
        def __init__(self) -> None:
            self.actionManager = action_manager
            self.player = None
            self._room = StubRoom()

        def getCurrRoom(self):
            return self._room

    dungeon_namespace = SimpleNamespace(AbstractDungeon=StubDungeon())
    cardcrawl_stub = SimpleNamespace(
        cards=cards_namespace,
        actions=actions_namespace,
        powers=powers_namespace,
        dungeons=dungeon_namespace,
        helpers=SimpleNamespace(CardLibrary=SimpleNamespace(getCard=lambda name: None)),
    )
    spire_stub = StubSpire()

    class StubBaseMod:
        @staticmethod
        def subscribe(_):
            return None

    basemod_stub = SimpleNamespace(
        abstracts=SimpleNamespace(CustomCard=StubCustomCard),
        BaseMod=StubBaseMod,
    )

    monkeypatch.setattr(cards_module, "_cardcrawl", lambda: cardcrawl_stub)
    monkeypatch.setattr(cards_module, "_basemod", lambda: basemod_stub)
    monkeypatch.setattr(cards_module, "_spire", lambda: spire_stub)

    class StubTempHPField:
        @staticmethod
        def get(player):
            return getattr(player, "temp_hp", 0)

    class StubAddTempHPAction:
        def __init__(self, target, source, amount) -> None:
            self.target = target
            self.source = source
            self.amount = amount
            self.name = "add_temp_hp"

    class StubRemoveTempHPAction:
        def __init__(self, target, source) -> None:
            self.target = target
            self.source = source
            self.name = "remove_temp_hp"

    keyword_spire_stub = SimpleNamespace(
        action=lambda name: {
            "AddTemporaryHPAction": StubAddTempHPAction,
            "RemoveAllTemporaryHPAction": StubRemoveTempHPAction,
        }[name],
        stslib=SimpleNamespace(
            patches=SimpleNamespace(tempHp=SimpleNamespace(TempHPField=SimpleNamespace(tempHp=StubTempHPField))),
            Keyword=lambda: SimpleNamespace(),
        ),
        register_keyword=lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(keywords_module, "_cardcrawl", lambda: cardcrawl_stub)
    monkeypatch.setattr(keywords_module, "_basemod", lambda: basemod_stub)
    monkeypatch.setattr(keywords_module, "_spire", lambda: keyword_spire_stub)

    yield cardcrawl_stub, action_manager, spire_stub

    action_manager.clear()
    spire_stub.reset()


@pytest.fixture()
def desktop_jar_path():
    pytest.skip("Desktop jar fixture is not available in the CI environment.")
