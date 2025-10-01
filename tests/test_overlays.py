import gc

import pytest

from modules.basemod_wrapper.keywords import KEYWORD_REGISTRY, Keyword, RuntimeHandles
from modules.basemod_wrapper.overlays import OverlayManager, overlay_manager


class DummyTexture:
    def __init__(self, width: int, height: int, *, name: str = "texture") -> None:
        self._width = width
        self._height = height
        self.name = name

    def getWidth(self) -> int:  # pragma: no cover - trivial
        return self._width

    def getHeight(self) -> int:  # pragma: no cover - trivial
        return self._height

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"DummyTexture({self.name}, {self._width}x{self._height})"


class FakeSpriteBatch:
    def __init__(self) -> None:
        self.draw_calls = []
        self._color = (1.0, 1.0, 1.0, 1.0)

    def draw(self, *args):
        self.draw_calls.append(args)

    def setColor(self, r, g, b, a):  # pragma: no cover - trivial
        self._color = (float(r), float(g), float(b), float(a))

    def getColor(self):  # pragma: no cover - trivial
        return self._color


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_overlay_manager_handles_delay_and_expiry(use_real_dependencies):
    assert isinstance(use_real_dependencies, bool)
    manager = OverlayManager(auto_register=False)
    texture = DummyTexture(120, 80, name="warning")

    handle = manager.show_overlay(
        texture,
        x=300,
        y=500,
        duration=2.0,
        delay=1.0,
        metadata={"kind": "warning"},
    )

    batch = FakeSpriteBatch()
    manager.render_to(batch)
    assert batch.draw_calls == []

    manager.debug_tick(1.1)
    batch = FakeSpriteBatch()
    manager.render_to(batch)
    assert len(batch.draw_calls) == 1
    texture_arg, x_arg, y_arg, width_arg, height_arg = batch.draw_calls[0]
    assert texture_arg is texture
    assert pytest.approx(x_arg) == 300.0
    assert pytest.approx(y_arg) == 500.0
    assert pytest.approx(width_arg) == 120.0
    assert pytest.approx(height_arg) == 80.0

    snapshot = handle.snapshot()
    assert snapshot.visible
    assert snapshot.metadata["kind"] == "warning"

    manager.debug_tick(2.5)
    batch = FakeSpriteBatch()
    manager.render_to(batch)
    assert batch.draw_calls == []
    assert manager.active_overlay_ids == ()


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_overlay_manager_z_order_and_updates(use_real_dependencies):
    assert isinstance(use_real_dependencies, bool)
    manager = OverlayManager(auto_register=False)
    base = DummyTexture(100, 60, name="base")
    prompt = DummyTexture(240, 140, name="prompt")

    primary = manager.show_overlay(
        base,
        x=640,
        y=360,
        z_index=5,
        metadata={"id": "primary"},
    )
    secondary = manager.show_overlay(
        prompt,
        x=640,
        y=360,
        z_index=-4,
        anchor="center",
        metadata={"id": "secondary"},
    )
    assert primary.snapshot().metadata["id"] == "primary"

    manager.debug_tick(0.2)
    batch = FakeSpriteBatch()
    manager.render_to(batch)
    assert [call[0] for call in batch.draw_calls] == [prompt, base]
    # Center anchor shifts the overlay left/up by half the size
    first_call = batch.draw_calls[0]
    assert pytest.approx(first_call[1]) == 640 - 240 / 2
    assert pytest.approx(first_call[2]) == 360 - 140 / 2

    secondary.update(z_index=12)
    manager.debug_tick(0.1)
    batch = FakeSpriteBatch()
    manager.render_to(batch)
    assert [call[0] for call in batch.draw_calls] == [base, prompt]

    secondary.update(rotation=45, scale_x=1.2, scale_y=0.8)
    batch = FakeSpriteBatch()
    manager.render_to(batch)
    # Rotation and scaling trigger the extended draw overload with origin params
    assert len(batch.draw_calls[-1]) == 10

    manager.clear()
    assert manager.active_overlay_ids == ()


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_overlay_trigger_card_event(use_real_dependencies):
    assert isinstance(use_real_dependencies, bool)
    manager = OverlayManager(auto_register=False)
    texture = DummyTexture(64, 64, name="card_ping")

    handle = manager.register_trigger(
        "card_used",
        match={"card_id": "Strike_R"},
        source=texture,
        overlay_kwargs={
            "x": 120,
            "y": 340,
            "metadata": {"kind": "card"},
            "z_index": 7,
        },
        overlay_identifier="card_used_overlay",
    )

    class DummyCard:
        def __init__(self, card_id: str) -> None:
            self.cardID = card_id
            self.name = card_id

    manager.handle_event("card_used", card=DummyCard("Defend_R"), card_id="Defend_R")
    assert manager.active_overlay_ids == ()

    manager.handle_event("card_used", card=DummyCard("Strike_R"), card_id="Strike_R")
    assert manager.active_overlay_ids == ("card_used_overlay",)
    snapshot = manager.overlay_snapshot("card_used_overlay")
    assert snapshot.metadata["kind"] == "card"
    assert pytest.approx(snapshot.x) == 120.0
    assert pytest.approx(snapshot.y) == 340.0

    manager.debug_tick(0.5)
    manager.handle_event("card_used", card=DummyCard("Strike_R"), card_id="Strike_R")
    assert manager.active_overlay_ids == ("card_used_overlay",)

    handle.unregister()
    manager.clear()


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_keyword_trigger_overlays(use_real_dependencies):
    assert isinstance(use_real_dependencies, bool)
    manager = overlay_manager()
    manager.clear()
    manager.clear_triggers()

    texture = DummyTexture(48, 48, name="keyword_flash")
    captured_ids = []

    def builder(payload):
        captured_ids.append(payload.get("card_id"))
        return {
            "source": texture,
            "x": 42,
            "y": 128,
            "metadata": {
                "keyword": payload.get("keyword_id"),
                "amount": payload.get("amount"),
            },
            "identifier": "keyword_overlay",
        }

    trigger_handle = manager.register_trigger(
        "keyword_triggered",
        predicate=lambda payload: payload.get("keyword_id") == "flash",
        builder=builder,
        once=True,
    )

    class FlashKeyword(Keyword):
        def __init__(self) -> None:
            super().__init__(name="Flash")

        def apply(self, context):
            self.context = context

    keyword = FlashKeyword()
    KEYWORD_REGISTRY.register(keyword)

    class DummyCard:
        def __init__(self) -> None:
            self.cardID = "TestCard"

    card = DummyCard()
    KEYWORD_REGISTRY.attach_to_card(card, "Flash", amount=3, upgrade=None)

    class DummyEnergy:
        def __init__(self) -> None:
            self.energy = 3

    class DummyPlayer:
        def __init__(self) -> None:
            self.hand = []
            self.drawPile = []
            self.discardPile = []
            self.energy = DummyEnergy()
            self.currentBlock = 0

    class DummyDungeon:
        actionManager = type("Mgr", (), {"addToBottom": staticmethod(lambda action: None)})()
        player = None

        @staticmethod
        def getCurrRoom():
            return type("Room", (), {"monsters": None})()

    class DummyCardCrawl:
        actions = type("Actions", (), {"common": type("Common", (), {})()})()
        powers = type("Powers", (), {})()
        helpers = type("Helpers", (), {"CardLibrary": type("Library", (), {})()})()
        dungeons = type("Dungeons", (), {"AbstractDungeon": DummyDungeon})()

    runtime = RuntimeHandles(cardcrawl=DummyCardCrawl(), basemod=None, spire=None)

    player = DummyPlayer()
    KEYWORD_REGISTRY.trigger(card, player, None, runtime=runtime)

    assert manager.active_overlay_ids == ("keyword_overlay",)
    assert trigger_handle.identifier not in manager.active_trigger_ids
    assert captured_ids == ["TestCard"]
    snapshot = manager.overlay_snapshot("keyword_overlay")
    assert snapshot.metadata["keyword"] == "flash"
    assert snapshot.metadata["amount"] == 3

    manager.hide_overlay("keyword_overlay")
    manager.clear_triggers()
    manager.clear()

    # Cleanup registry entries created for the test
    KEYWORD_REGISTRY._card_keywords.pop(card, None)
    for key in list(KEYWORD_REGISTRY._keywords):
        if KEYWORD_REGISTRY._keywords[key].keyword is keyword:
            del KEYWORD_REGISTRY._keywords[key]
    gc.collect()
