from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from modules.basemod_wrapper.keywords import (
    CARD_PERSISTENCE_MANAGER,
    CardEditor,
    Keyword,
    KeywordContext,
    KEYWORD_REGISTRY,
    RuntimeHandles,
    apply_persistent_card_changes,
    keyword_scheduler,
)


@pytest.fixture(autouse=True)
def reset_scheduler() -> None:
    keyword_scheduler.reset()
    yield
    keyword_scheduler.reset()


class StubCreature:
    def __init__(self, hp: int = 50) -> None:
        self.maxHealth = hp
        self.currentHealth = hp
        self.temp_hp = 0
        self.currentBlock = 0
        self.hand = SimpleNamespace(group=[])
        self.drawPile = SimpleNamespace(group=[])
        self.discardPile = SimpleNamespace(group=[])
        self.masterDeck = SimpleNamespace(group=[])
        self._powers: Dict[str, int] = {}

    def getPower(self, name: str) -> Optional[SimpleNamespace]:
        if name not in self._powers:
            return None
        return SimpleNamespace(amount=self._powers[name])

    def setPower(self, name: str, amount: int) -> None:
        if amount <= 0:
            self._powers.pop(name, None)
            return
        self._powers[name] = amount


def _linear_power(name: str):
    class _Power:
        def __init__(self, owner: StubCreature, *args: Any) -> None:
            amount = int(args[-1]) if args else 0
            existing = owner.getPower(name)
            current = int(getattr(existing, "amount", 0))
            owner.setPower(name, current + amount)
            self.amount = owner.getPower(name).amount

    _Power.__name__ = name
    return _Power


def _poison_power(owner: StubCreature, _source: Any, amount: int) -> Any:
    existing = owner.getPower("PoisonPower")
    current = int(getattr(existing, "amount", 0))
    owner.setPower("PoisonPower", current + amount)
    return SimpleNamespace(amount=owner.getPower("PoisonPower").amount)


def _build_runtime(player: StubCreature, monsters: List[StubCreature]):
    action_log: List[Dict[str, Any]] = []

    def record(name: str, **payload: Any) -> None:
        entry = {"name": name, **payload}
        action_log.append(entry)

    def gain_block_action(target: StubCreature, _source: StubCreature, amount: int):
        def runner() -> None:
            target.currentBlock += amount
            record("gain_block", amount=amount)

        return runner

    def lose_block_action(target: StubCreature, _source: StubCreature, amount: int):
        def runner() -> None:
            target.currentBlock = max(0, target.currentBlock - amount)
            record("lose_block", amount=amount)

        return runner

    def draw_action(_player: StubCreature, amount: int):
        def runner() -> None:
            record("draw", amount=amount)

        return runner

    def discard_action(_player: StubCreature, _source: StubCreature, amount: int, _random: bool):
        def runner() -> None:
            record("discard", amount=amount)

        return runner

    def apply_power_action(owner: StubCreature, _source: StubCreature, power: Any, amount: int):
        def runner() -> None:
            record("apply_power", power=type(power).__name__, amount=amount)

        return runner

    def remove_power_action(owner: StubCreature, _source: StubCreature, name: str):
        def runner() -> None:
            owner.setPower(name, 0)
            record("remove_power", power=name)

        return runner

    def lose_hp_action(target: StubCreature, _source: StubCreature, amount: int):
        def runner() -> None:
            target.currentHealth = max(0, target.currentHealth - amount)
            record("lose_hp", amount=amount)

        return runner

    def heal_action(target: StubCreature, _source: StubCreature, amount: int):
        def runner() -> None:
            target.currentHealth = min(target.maxHealth, target.currentHealth + amount)
            record("heal", amount=amount)

        return runner

    def add_card_action(card: Any, amount: int):
        def runner() -> None:
            for _ in range(amount):
                player.hand.group.append(card.makeCopy())
            record("add_card", amount=amount)

        return runner

    class ActionManager:
        def addToBottom(self, action: Any) -> None:
            action()

    class Dungeon:
        def __init__(self) -> None:
            self.actionManager = ActionManager()
            self.player = player
            self._room = SimpleNamespace(monsters=SimpleNamespace(monsters=monsters))

        def getCurrRoom(self) -> Any:
            return self._room

    card_library: Dict[str, Any] = {}

    def get_card(name: str) -> Any:
        return card_library.get(name)

    def register_card(name: str, card: Any) -> None:
        card_library[name] = card

    class StubCard:
        def __init__(self, card_id: str) -> None:
            self.cardID = card_id
            self.name = card_id
            self.rawDescription = ""
            self.cost = 1

        def makeCopy(self) -> "StubCard":
            return StubCard(self.cardID)

    register_card("Strike", StubCard("Strike"))

    cardcrawl = SimpleNamespace(
        actions=SimpleNamespace(
            common=SimpleNamespace(
                GainBlockAction=gain_block_action,
                LoseBlockAction=lose_block_action,
                DrawCardAction=draw_action,
                DiscardAction=discard_action,
                ApplyPowerAction=apply_power_action,
                RemoveSpecificPowerAction=remove_power_action,
                LoseHPAction=lose_hp_action,
                HealAction=heal_action,
                MakeTempCardInHandAction=add_card_action,
            )
        ),
        powers=SimpleNamespace(
            StrengthPower=_linear_power("StrengthPower"),
            DexterityPower=_linear_power("DexterityPower"),
            FocusPower=_linear_power("FocusPower"),
            ArtifactPower=_linear_power("ArtifactPower"),
            IntangiblePlayerPower=_linear_power("IntangiblePlayerPower"),
            IntangiblePower=_linear_power("IntangiblePower"),
            WeakPower=_linear_power("WeakPower"),
            VulnerablePower=_linear_power("VulnerablePower"),
            FrailPower=_linear_power("FrailPower"),
            ConstrictedPower=_linear_power("ConstrictedPower"),
            ShackledPower=_linear_power("ShackledPower"),
            LockOnPower=_linear_power("LockOnPower"),
            SlowPower=_linear_power("SlowPower"),
            ThornsPower=_linear_power("ThornsPower"),
            PlatedArmorPower=_linear_power("PlatedArmorPower"),
            MetallicizePower=_linear_power("MetallicizePower"),
        ),
        dungeons=SimpleNamespace(AbstractDungeon=Dungeon()),
        helpers=SimpleNamespace(CardLibrary=SimpleNamespace(getCard=get_card)),
    )
    setattr(cardcrawl.powers, "PoisonPower", _poison_power)

    temp_hp_field = SimpleNamespace(tempHp=SimpleNamespace(get=lambda owner: owner.temp_hp))

    def spire_action(name: str):
        if name == "AddTemporaryHPAction":
            def ctor(target: StubCreature, _source: StubCreature, amount: int):
                def runner() -> None:
                    target.temp_hp += amount
                    record("add_temp_hp", amount=amount)

                return runner

            return ctor
        if name == "RemoveAllTemporaryHPAction":
            def ctor(target: StubCreature, _source: StubCreature):
                def runner() -> None:
                    target.temp_hp = 0
                    record("remove_temp_hp")

                return runner

            return ctor
        raise KeyError(name)

    spire = SimpleNamespace(
        action=spire_action,
        stslib=SimpleNamespace(patches=SimpleNamespace(tempHp=SimpleNamespace(TempHPField=temp_hp_field))),
        register_keyword=lambda *args, **kwargs: None,
    )

    basemod = SimpleNamespace(BaseMod=SimpleNamespace(subscribe=lambda _: None))

    return RuntimeHandles(cardcrawl=cardcrawl, basemod=basemod, spire=spire), action_log


def test_keyword_auto_registers_in_registry(use_real_dependencies: bool) -> None:
    class RegistryKeyword(Keyword):
        def apply(self, context: KeywordContext) -> None:
            pass

    metadata = KEYWORD_REGISTRY.resolve("RegistryKeyword")
    assert metadata is not None
    assert metadata.keyword is not None


def test_hp_proxy_and_arithmetic_controls_temp_hp(use_real_dependencies: bool) -> None:
    player = StubCreature()
    runtime, log = _build_runtime(player, [])

    class HPKeyword(Keyword):
        def apply(self, context: KeywordContext) -> None:
            context.hp_proxy += 7

    keyword = HPKeyword()
    context = KeywordContext(keyword=keyword, player=player, monster=None, card=object(), amount=None, upgrade=None, runtime=runtime)
    keyword.run(context)
    keyword_scheduler.flush()

    assert player.temp_hp == 7
    assert log[-1]["name"] == "add_temp_hp"


def test_power_proxy_applies_exact_delta(use_real_dependencies: bool) -> None:
    player = StubCreature()
    runtime, log = _build_runtime(player, [])

    class PowerKeyword(Keyword):
        def apply(self, context: KeywordContext) -> None:
            context.player_proxy.powers.strength = 4
            context.player_proxy.powers.strength = 6
            context.player_proxy.powers.weak = 2

    keyword = PowerKeyword()
    context = KeywordContext(keyword=keyword, player=player, monster=None, card=object(), amount=None, upgrade=None, runtime=runtime)
    keyword.run(context)
    keyword_scheduler.flush()

    assert player.getPower("StrengthPower").amount == 6
    assert player.getPower("WeakPower").amount == 2
    assert log[-1]["power"] == "WeakPower"


def test_enemy_proxy_controls_target_and_hp(use_real_dependencies: bool) -> None:
    player = StubCreature()
    monster = StubCreature()
    runtime, log = _build_runtime(player, [monster])

    class EnemyKeyword(Keyword):
        def apply(self, context: KeywordContext) -> None:
            target = self.enemies.target
            target -= 5
            target.powers.vulnerable = 3

    keyword = EnemyKeyword()
    context = KeywordContext(keyword=keyword, player=player, monster=monster, card=object(), amount=None, upgrade=None, runtime=runtime)
    keyword.run(context)
    keyword_scheduler.flush()

    assert monster.currentHealth == monster.maxHealth - 5
    assert monster.getPower("VulnerablePower").amount == 3
    assert any(entry["name"] == "lose_hp" for entry in log)


def test_card_editor_snapshot_and_persistence(use_real_dependencies: bool, tmp_path) -> None:
    player = StubCreature()
    card = SimpleNamespace(
        cardID="StubCard",
        name="Original",
        rawDescription="Deal damage.",
        cost=2,
        baseDamage=6,
        initializeDescription=lambda: None,
    )
    player.masterDeck.group.append(SimpleNamespace(cardID="StubCard", baseDamage=6))
    player.hand.group.append(card)
    runtime, _ = _build_runtime(player, [])

    context = KeywordContext(keyword=SimpleNamespace(), player=player, monster=None, card=card, amount=None, upgrade=None, runtime=runtime)
    editor = context.hand[0]

    snapshot = editor.snapshot("title", "cost")
    assert snapshot == {"title": "Original", "cost": 2}

    editor.persist_for_combat(title="Altered", cost=1)
    assert card.name == "Altered"
    assert card.cost == 1

    editor.persist_for_run(player, baseDamage=9)
    master_card = player.masterDeck.group[0]
    assert master_card.baseDamage == 9

    storage_path = tmp_path / "persistent_cards.json"
    CARD_PERSISTENCE_MANAGER.configure_storage(storage_path)
    try:
        editor.persist_forever(player, baseMagicNumber=3)
        assert storage_path.exists()
        stored = json.loads(storage_path.read_text(encoding="utf8"))
        assert stored["StubCard"]["baseMagicNumber"] == 3

        fresh_player = StubCreature()
        fresh_player.masterDeck.group.append(SimpleNamespace(cardID="StubCard", baseMagicNumber=0))
        apply_persistent_card_changes(fresh_player)
        assert fresh_player.masterDeck.group[0].baseMagicNumber == 3
    finally:
        CARD_PERSISTENCE_MANAGER.reset_storage()


def test_card_zone_adds_card_by_title(use_real_dependencies: bool) -> None:
    player = StubCreature()
    runtime, _ = _build_runtime(player, [])
    library = runtime.cardcrawl.helpers.CardLibrary

    class LibraryCard:
        def __init__(self, card_id: str, name: str) -> None:
            self.cardID = card_id
            self.name = name

        def makeCopy(self) -> "LibraryCard":
            return LibraryCard(self.cardID, self.name)

    template = LibraryCard("Strike_R", "Strike")
    library.getCard = lambda _: None
    library.cardsByName = {"Strike": template}
    library.cardsByID = {"Strike_R": template}
    player.masterDeck.group.append(template)

    context = KeywordContext(
        keyword=SimpleNamespace(),
        player=player,
        monster=None,
        card=SimpleNamespace(),
        amount=None,
        upgrade=None,
        runtime=runtime,
    )

    context.hand.add_by_name("Strike")
    keyword_scheduler.flush()
    assert player.hand.group[-1].cardID == "Strike_R"

    player.hand.group.clear()
    library.cardsByName = {}
    library.cardsByID = {}

    context.hand.add_by_name("Strike")
    keyword_scheduler.flush()
    assert player.hand.group[-1].cardID == "Strike_R"


def test_keyword_scheduler_applies_persistent_changes(use_real_dependencies: bool, tmp_path) -> None:
    player = StubCreature()
    runtime, _ = _build_runtime(player, [])
    card = SimpleNamespace(cardID="PersistMe", baseMagicNumber=1, initializeDescription=lambda: None)
    player.masterDeck.group.append(card)

    storage_path = tmp_path / "cards.json"
    CARD_PERSISTENCE_MANAGER.configure_storage(storage_path)
    try:
        editor = CardEditor(card)
        editor.persist_forever(player, baseMagicNumber=7)
        player.masterDeck.group[0].baseMagicNumber = 1
        runtime.cardcrawl.dungeons.AbstractDungeon.player = player
        keyword_scheduler.apply_persistent_changes(runtime)
        assert player.masterDeck.group[0].baseMagicNumber == 7
    finally:
        CARD_PERSISTENCE_MANAGER.reset_storage()


def test_keyword_when_respects_turn_offsets(use_real_dependencies: bool) -> None:
    player = StubCreature()
    runtime, log = _build_runtime(player, [])

    class OffsetKeyword(Keyword):
        def __init__(self) -> None:
            super().__init__()
            self.when = "next"
            self.turn_offset = 2

        def apply(self, context: KeywordContext) -> None:
            context.player_proxy.block += 3

    keyword = OffsetKeyword()
    class DummyCard:
        pass

    card = DummyCard()
    KEYWORD_REGISTRY.attach_to_card(card, keyword.__class__.__name__, amount=None, upgrade=None)

    KEYWORD_REGISTRY.trigger(card, player, None, runtime=runtime)
    assert player.currentBlock == 0
    keyword_scheduler.debug_advance_turn()
    assert player.currentBlock == 0
    keyword_scheduler.debug_advance_turn()
    assert any(entry["name"] == "gain_block" for entry in log)
    assert player.currentBlock == 3


def test_keyword_random_range_is_respected(use_real_dependencies: bool) -> None:
    player = StubCreature()
    runtime, log = _build_runtime(player, [])

    class RandomKeyword(Keyword):
        def __init__(self) -> None:
            super().__init__()
            self.when = "random"
            self.random_turn_range = (2, 2)

        def apply(self, context: KeywordContext) -> None:
            context.player_proxy.draw_cards(1)

    keyword = RandomKeyword()
    class DummyCard:
        pass

    card = DummyCard()
    KEYWORD_REGISTRY.attach_to_card(card, keyword.__class__.__name__, amount=None, upgrade=None)

    KEYWORD_REGISTRY.trigger(card, player, None, runtime=runtime)
    assert not any(entry["name"] == "draw" for entry in log)
    keyword_scheduler.debug_advance_turn()
    assert not any(entry["name"] == "draw" for entry in log)
    keyword_scheduler.debug_advance_turn()
    assert any(entry["name"] == "draw" for entry in log)
