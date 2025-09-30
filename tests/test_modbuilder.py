from __future__ import annotations

from pathlib import Path

import pytest

from modules.modbuilder import Character, CharacterColorConfig, CharacterImageConfig, CharacterStartConfig, Deck
from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.basemod_wrapper.loader import BaseModBootstrapError
from modules.basemod_wrapper.card_assets import ensure_pillow


def _make_blueprint(identifier: str, rarity: str = "common", image_stub: str | None = None) -> SimpleCardBlueprint:
    image_path = image_stub or f"buddy/images/cards/{identifier}.png"
    return SimpleCardBlueprint(
        identifier=identifier,
        title=identifier,
        description="Deal {damage} damage.",
        cost=1,
        card_type="attack",
        target="enemy",
        rarity=rarity,
        value=7,
        image=image_path,
    )


def _write_placeholder(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("asset", encoding="utf8")


class _BaseTestCharacter(Character):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Buddy"
        self.mod_id = "buddy"
        self.description = "Testing"
        self.color = CharacterColorConfig(
            identifier="BUDDY_BLUE",
            card_color=(0.2, 0.4, 0.8, 1.0),
            trail_color=(0.2, 0.3, 0.7, 1.0),
            slash_color=(0.3, 0.5, 0.9, 1.0),
            attack_bg="buddy/images/cards/attack.png",
            skill_bg="buddy/images/cards/skill.png",
            power_bg="buddy/images/cards/power.png",
            orb="buddy/images/cards/orb.png",
            attack_bg_small="buddy/images/cards/attack_small.png",
            skill_bg_small="buddy/images/cards/skill_small.png",
            power_bg_small="buddy/images/cards/power_small.png",
            orb_small="buddy/images/cards/orb_small.png",
        )
        self.image = CharacterImageConfig(
            shoulder1="buddy/images/character/shoulder1.png",
            shoulder2="buddy/images/character/shoulder2.png",
            corpse="buddy/images/character/corpse.png",
        )
        self.start = CharacterStartConfig()


def _prepare_assets(root: Path, *, include_cards: dict[str, bool], include_static: bool = False) -> None:
    for name, present in include_cards.items():
        target = root / "images" / "cards" / name
        if present:
            _write_placeholder(target)
    for name in [
        "attack.png",
        "skill.png",
        "power.png",
        "orb.png",
        "attack_small.png",
        "skill_small.png",
        "power_small.png",
        "orb_small.png",
    ]:
        _write_placeholder(root / "images" / "cards" / name)
    for name in ["shoulder1.png", "shoulder2.png", "corpse.png"]:
        _write_placeholder(root / "images" / "character" / name)
    if include_static:
        Image = ensure_pillow()
        pose = root / "images" / "character" / "pose.png"
        pose.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (64, 64), (255, 255, 255, 255)).save(pose)


def _prepare_python_source(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "__init__.py").write_text("\n", encoding="utf8")


def test_deck_collects_cards(use_real_dependencies: bool) -> None:
    class StarterDeck(Deck):
        pass

    first = _make_blueprint("Strike")
    second = _make_blueprint("Defend", rarity="uncommon")

    StarterDeck.addCard(first)
    StarterDeck.addCard(second)
    StarterDeck.addCard(first)

    cards = StarterDeck.cards()
    assert len(cards) == 3
    assert cards[0] is first
    assert cards[1] is second
    assert cards[2] is first


def test_character_reports_missing_assets(tmp_path: Path, use_real_dependencies: bool) -> None:
    class StarterDeck(Deck):
        pass

    StarterDeck.addCard(_make_blueprint("Strike"))

    class DummyCharacter(_BaseTestCharacter):
        def __init__(self) -> None:
            super().__init__()
            self.start.deck = StarterDeck

    assets_root = tmp_path / "assets" / "buddy"
    _prepare_assets(assets_root, include_cards={"Strike.png": False})
    python_root = tmp_path / "python"
    _prepare_python_source(python_root)

    with pytest.raises(BaseModBootstrapError) as excinfo:
        DummyCharacter.createMod(
            tmp_path / "dist",
            assets_root=assets_root,
            python_source=python_root,
            bundle=False,
        )
    message = str(excinfo.value)
    assert "Missing assets for cards" in message
    assert "Strike" in message


def test_character_enforces_card_counts_and_ratio(tmp_path: Path, use_real_dependencies: bool) -> None:
    class StarterDeck(Deck):
        pass

    for index in range(10):
        StarterDeck.addCard(_make_blueprint(f"Strike{index}"))

    class UnlockableDeck(Deck):
        pass

    for index in range(10, 20):
        UnlockableDeck.addCard(_make_blueprint(f"Strike{index}"))

    class DummyCharacter(_BaseTestCharacter):
        def __init__(self) -> None:
            super().__init__()
            self.start.deck = StarterDeck
            self.unlockableDeck = UnlockableDeck

    assets_root = tmp_path / "assets" / "buddy"
    include_cards = {f"Strike{index}.png": True for index in range(20)}
    _prepare_assets(assets_root, include_cards=include_cards)
    python_root = tmp_path / "python"
    _prepare_python_source(python_root)

    with pytest.raises(BaseModBootstrapError) as excinfo:
        DummyCharacter.createMod(
            tmp_path / "dist",
            assets_root=assets_root,
            python_source=python_root,
            bundle=False,
        )
    message = str(excinfo.value)
    assert "This deck has 20 cards." in message
    assert "Card Rarity Proportions Incorrect" in message


def test_static_spine_assets_are_generated(tmp_path: Path, use_real_dependencies: bool) -> None:
    class StarterDeck(Deck):
        pass

    for index in range(60):
        StarterDeck.addCard(_make_blueprint(f"Common{index}", rarity="common"))

    class UnlockableDeck(Deck):
        pass

    for index in range(37):
        UnlockableDeck.addCard(_make_blueprint(f"Uncommon{index}", rarity="uncommon"))
    for index in range(3):
        UnlockableDeck.addCard(_make_blueprint(f"Rare{index}", rarity="rare"))

    class DummyCharacter(_BaseTestCharacter):
        def __init__(self) -> None:
            super().__init__()
            self.start.deck = StarterDeck
            self.unlockableDeck = UnlockableDeck
            self.image.staticspineanimation = "buddy/images/character/pose.png"

    assets_root = tmp_path / "assets" / "buddy"
    include_cards = {f"Common{index}.png": True for index in range(60)}
    include_cards.update({f"Uncommon{index}.png": True for index in range(37)})
    include_cards.update({f"Rare{index}.png": True for index in range(3)})
    _prepare_assets(assets_root, include_cards=include_cards, include_static=True)
    python_root = tmp_path / "python"
    _prepare_python_source(python_root)

    expected_atlas = assets_root / "images" / "character" / "pose.atlas"
    expected_json = assets_root / "images" / "character" / "pose.json"

    result = DummyCharacter.createMod(
        tmp_path / "dist",
        assets_root=assets_root,
        python_source=python_root,
        bundle=False,
        register_cards=False,
    )

    assert result == (tmp_path / "dist" / "Buddy")
    assert expected_atlas.exists()
    assert expected_json.exists()
    character = DummyCharacter()
    character.image.staticspineanimation = "buddy/images/character/pose.png"
    Character._prepare_static_spine(character, assets_root)
    assert character.image.staticspineatlas.endswith("pose.atlas")
    assert character.image.staticspinejson.endswith("pose.json")
