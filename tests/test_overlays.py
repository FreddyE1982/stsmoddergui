import pytest

from modules.basemod_wrapper.overlays import OverlayManager


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
