from __future__ import annotations

from types import SimpleNamespace, ModuleType
from typing import Any, Optional
import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.basemod_wrapper import cards as cards_module
from modules.basemod_wrapper import card_types as card_types_module
from modules.basemod_wrapper import relics as relics_module
from modules.basemod_wrapper import keywords as keywords_module
from modules.basemod_wrapper import project as project_module
from modules.basemod_wrapper import stances as stances_module
from tests.stubs import (
    StubActionManager,
    StubApplyPowerAction,
    StubArtifactPower,
    StubCardColor,
    StubCustomCard,
    StubCustomRelic,
    StubAbstractStance,
    StubColor,
    StubTexture,
    StubDamageAction,
    StubDamageAllEnemiesAction,
    StubDamageInfo,
    StubDexterityPower,
    StubDrawCardAction,
    StubFocusPower,
    StubGainBlockAction,
    StubGainEnergyAction,
    StubLandingSound,
    StubPoisonPower,
    StubRelicTier,
    StubRelicType,
    StubStanceAuraEffect,
    StubStanceHelper,
    StubStanceParticleEffect,
    StubSpire,
    StubStrengthPower,
    StubVulnerablePower,
    StubWeakPower,
    StubFrailPower,
)


def pytest_addoption(parser):
    parser.addoption(
        "--use-real-dependencies",
        action="store_true",
        default=False,
        help="Run tests against the real BaseMod runtime without monkeypatched stubs.",
    )


@pytest.fixture()
def use_real_dependencies(request: pytest.FixtureRequest) -> bool:
    """Return True when the caller requested real runtime dependencies."""

    return bool(request.config.getoption("--use-real-dependencies"))


@pytest.fixture()
def stubbed_runtime(monkeypatch, use_real_dependencies: bool):
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

    stances_namespace = SimpleNamespace(AbstractStance=StubAbstractStance)
    vfx_namespace = SimpleNamespace(
        stance=SimpleNamespace(
            StanceAuraEffect=StubStanceAuraEffect,
            StanceParticleEffect=StubStanceParticleEffect,
        )
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
        stances=stances_namespace,
        dungeons=dungeon_namespace,
        relics=SimpleNamespace(
            AbstractRelic=SimpleNamespace(
                RelicTier=StubRelicTier,
                LandingSound=StubLandingSound,
                RelicType=StubRelicType,
            )
        ),
        helpers=SimpleNamespace(
            CardLibrary=SimpleNamespace(getCard=lambda name: None),
            StanceHelper=StubStanceHelper,
        ),
        vfx=vfx_namespace,
    )
    spire_stub = StubSpire()
    libgdx_stub = SimpleNamespace(graphics=SimpleNamespace(Color=StubColor, Texture=StubTexture))

    if not use_real_dependencies:
        from modules.basemod_wrapper.experimental import graalpy_runtime

        monkeypatch.setitem(os.environ, "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE", "1")
        monkeypatch.setitem(
            os.environ,
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE",
            sys.executable,
        )
        monkeypatch.setattr(graalpy_runtime.platform, "python_implementation", lambda: "GraalPy")

        class _StubSupplier:
            pass

        _java_mapping = {
            "com.megacrit.cardcrawl.stances.AbstractStance": StubAbstractStance,
            "com.megacrit.cardcrawl.helpers.StanceHelper": StubStanceHelper,
            "com.megacrit.cardcrawl.vfx.stance.StanceAuraEffect": StubStanceAuraEffect,
            "com.megacrit.cardcrawl.vfx.stance.StanceParticleEffect": StubStanceParticleEffect,
            "com.badlogic.gdx.graphics.Color": StubColor,
            "com.badlogic.gdx.graphics.Texture": StubTexture,
            "java.util.function.Supplier": _StubSupplier,
        }

        def _java_type(name: str):
            try:
                return _java_mapping[name]
            except KeyError as exc:  # pragma: no cover - debug helper
                raise KeyError(name) from exc

        def _java_add_to_classpath(*_args, **_kwargs):  # pragma: no cover - helper stub
            return None

        def _java_implements(_interface):
            def decorator(obj):
                return obj

            return decorator

        def _java_array(_component, values):
            return list(values)

        java_module = ModuleType("java")
        java_module.type = _java_type  # type: ignore[assignment]
        java_module.add_to_classpath = _java_add_to_classpath  # type: ignore[assignment]
        java_module.implements = _java_implements  # type: ignore[assignment]
        java_module.array = _java_array  # type: ignore[assignment]
        monkeypatch.setitem(sys.modules, "java", java_module)
        stances_module._java_module.cache_clear()
        stances_module._stance_helper.cache_clear()
        stances_module._stance_aura_effect.cache_clear()
        stances_module._stance_particle_effect.cache_clear()

    class StubBaseMod:
        relics_registered: list[tuple[object, object]] = []
        custom_pool_relics: list[tuple[object, object]] = []
        custom_stances: list[tuple[str, object, Optional[object], Optional[object]]] = []

        @staticmethod
        def subscribe(_):
            return None

        @classmethod
        def addRelic(cls, relic, relic_type):
            cls.relics_registered.append((relic, relic_type))

        @classmethod
        def addRelicToCustomPool(cls, relic, color):
            cls.custom_pool_relics.append((relic, color))

        @classmethod
        def addCustomStance(cls, stance_id, factory, aura_supplier=None, particle_supplier=None):
            cls.custom_stances.append((stance_id, factory, aura_supplier, particle_supplier))

    basemod_stub = SimpleNamespace(
        abstracts=SimpleNamespace(CustomCard=StubCustomCard, CustomRelic=StubCustomRelic),
        BaseMod=StubBaseMod,
    )

    monkeypatch.setattr(cards_module, "_cardcrawl", lambda: cardcrawl_stub)
    monkeypatch.setattr(cards_module, "_basemod", lambda: basemod_stub)
    monkeypatch.setattr(cards_module, "_spire", lambda: spire_stub)
    monkeypatch.setattr(card_types_module, "_cardcrawl", lambda: cardcrawl_stub)
    monkeypatch.setattr(relics_module, "_cardcrawl", lambda: cardcrawl_stub)
    monkeypatch.setattr(relics_module, "_basemod", lambda: basemod_stub)
    relics_module._custom_relic_base.cache_clear()
    monkeypatch.setattr(project_module, "_cardcrawl", lambda: cardcrawl_stub)
    monkeypatch.setattr(project_module, "_basemod", lambda: basemod_stub)
    monkeypatch.setattr(stances_module, "_cardcrawl", lambda: cardcrawl_stub)
    monkeypatch.setattr(stances_module, "_basemod", lambda: basemod_stub)
    monkeypatch.setattr(stances_module, "_libgdx", lambda: libgdx_stub)
    stances_module._abstract_stance_base.cache_clear()

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
    StubBaseMod.relics_registered.clear()
    StubBaseMod.custom_pool_relics.clear()
    StubBaseMod.custom_stances.clear()
    StubAbstractStance.stances.clear()
    StubStanceAuraEffect.STANCE_COLORS.clear()
    StubStanceAuraEffect.PARTICLE_COLORS.clear()
    StubStanceAuraEffect.PARTICLE_TEXTURES.clear()
    StubStanceParticleEffect.PARTICLE_COLORS.clear()
    StubStanceHelper.stanceMap.clear()
    StubStanceHelper.nameMap.clear()


@pytest.fixture()
def desktop_jar_path():
    pytest.skip("Desktop jar fixture is not available in the CI environment.")
