from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.basemod_wrapper.project import ModProject
from modules.basemod_wrapper.keywords import Keyword, keyword_scheduler


class StubPlayer:
    def __init__(self) -> None:
        self.maxHealth = 80
        self.currentHealth = 70
        self.temp_hp = 0
        self.hand = []
        self.drawPile = []
        self.discardPile = []
        self.masterDeck = SimpleNamespace(group=[])
        self._powers: dict[str, SimpleNamespace] = {}

    def getPower(self, name: str):
        return self._powers.get(name)

    def setPower(self, name: str, amount: int) -> None:
        self._powers[name] = SimpleNamespace(amount=amount)


class StubCard:
    def __init__(self) -> None:
        self.cardID = "StubCard"
        self.name = "Stub"
        self.rawDescription = ""
        self.cost = 1


@pytest.fixture(autouse=True)
def reset_scheduler():
    keyword_scheduler.reset()
    yield
    keyword_scheduler.reset()


def test_custom_keyword_runs_during_card_use(stubbed_runtime):
    triggered = {}

    class BuddyKeyword(Keyword):
        def __init__(self) -> None:
            super().__init__()
            self.when = "now"

        def apply(self, context) -> None:
            triggered["flag"] = True
            context.card.marker = "buddy"

    project = ModProject("buddy", "Buddy", "Buddy", "Test")
    project._color_enum = "BUDDY_COLOR"
    blueprint = SimpleCardBlueprint(
        identifier="BuddyCard",
        title="Buddy Card",
        description="Do the thing.",
        cost=1,
        card_type="skill",
        target="self",
        effect="block",
        rarity="common",
        value=2,
        keywords=("BuddyKeyword",),
    )
    project.add_simple_card(blueprint)
    card = project.cards["BuddyCard"].factory()

    cardcrawl_stub, action_manager, _ = stubbed_runtime
    player = StubPlayer()
    cardcrawl_stub.dungeons.AbstractDungeon.player = player

    card.use(player, None)

    assert triggered["flag"] is True
    assert getattr(card, "marker") == "buddy"


def test_keyword_scheduler_next_turn_execution(stubbed_runtime):
    calls = {"count": 0}

    class DelayedKeyword(Keyword):
        def __init__(self) -> None:
            super().__init__()
            self.when = "next"

        def apply(self, context) -> None:
            calls["count"] += 1

    project = ModProject("delay", "Delay", "Delay", "Test")
    project._color_enum = "BUDDY_COLOR"
    blueprint = SimpleCardBlueprint(
        identifier="DelayedCard",
        title="Delayed",
        description="Wait a turn.",
        cost=1,
        card_type="skill",
        target="self",
        effect="block",
        rarity="common",
        value=1,
        keywords=("DelayedKeyword",),
    )
    project.add_simple_card(blueprint)
    card = project.cards["DelayedCard"].factory()

    cardcrawl_stub, _, _ = stubbed_runtime
    player = StubPlayer()
    cardcrawl_stub.dungeons.AbstractDungeon.player = player

    card.use(player, None)

    assert calls["count"] == 0
    keyword_scheduler.debug_advance_turn()
    assert calls["count"] == 1


def test_card_editor_helpers(tmp_path, monkeypatch, stubbed_runtime):
    recorded: list[tuple[str, dict[str, int]]] = []

    class RecordingPersistence:
        def record(self, card_id: str, payload: dict[str, int]) -> None:
            recorded.append((card_id, payload))

        def apply_to_deck(self, deck):
            return None

    from modules.basemod_wrapper import keywords as keywords_module

    monkeypatch.setattr(keywords_module, "_CARD_PERSISTENCE", RecordingPersistence())

    class EditKeyword(Keyword):
        def __init__(self) -> None:
            super().__init__()
            self.when = "now"

        def apply(self, context) -> None:
            editor = self.cards.hand.get(0)
            editor.persist_for_combat(title="Altered")
            editor.persist_forever(self.cards.player, cost=0)

    project = ModProject("edit", "Edit", "Edit", "Test")
    project._color_enum = "BUDDY_COLOR"
    blueprint = SimpleCardBlueprint(
        identifier="Editor",
        title="Editor",
        description="Change cards.",
        cost=1,
        card_type="skill",
        target="self",
        effect="block",
        rarity="common",
        value=1,
        keywords=("EditKeyword",),
    )
    project.add_simple_card(blueprint)
    card = project.cards["Editor"].factory()

    cardcrawl_stub, _, _ = stubbed_runtime
    player = StubPlayer()
    hand_card = StubCard()
    player.hand = SimpleNamespace(group=[hand_card])
    player.masterDeck.group.append(StubCard())
    cardcrawl_stub.dungeons.AbstractDungeon.player = player

    card.use(player, None)

    assert hand_card.name == "Altered"
    assert recorded[0][0] == "StubCard"
    assert recorded[0][1]["cost"] == 0
