from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.modbuilder import (
    CHARACTER_VALIDATION_HOOK,
    Character,
    CharacterColorConfig,
    CharacterDeckSnapshot,
    CharacterImageConfig,
    CharacterStartConfig,
    CharacterValidationReport,
    Deck,
    DeckAnalytics,
    DeckAnalyticsRow,
    build_deck_analytics,
)
from modules.modbuilder.character import RARITY_TARGETS
from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.basemod_wrapper.loader import BaseModBootstrapError
from modules.basemod_wrapper.card_assets import ensure_pillow
from plugins import PLUGIN_MANAGER, PluginRecord


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


def test_deck_statistics_reports_distribution(use_real_dependencies: bool) -> None:
    class StatsDeck(Deck):
        pass

    common = _make_blueprint("Strike", rarity="common")
    rare = _make_blueprint("Defend", rarity="rare")

    StatsDeck.addCard(common)
    StatsDeck.addCard(common)
    StatsDeck.addCard(rare)

    stats = StatsDeck.statistics()
    assert stats.total_cards == 3
    assert stats.unique_cards == 2
    assert stats.identifier_counts["Strike"] == 2
    assert stats.duplicate_identifiers["Strike"] == 2
    assert pytest.approx(stats.rarity_distribution["COMMON"], rel=1e-5) == (2 / 3) * 100
    assert pytest.approx(stats.rarity_distribution["RARE"], rel=1e-5) == (1 / 3) * 100


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
    assert "We need 55 more cards" in message
    assert "Card Rarity Proportions Incorrect" in message
    assert "Add the given amount of cards of given type" in message
    assert "25 common" in message
    assert "28 uncommon" in message
    assert "2 rare" in message


def test_character_rarity_ratio_reports_removals(tmp_path: Path, use_real_dependencies: bool) -> None:
    class StarterDeck(Deck):
        pass

    for index in range(45):
        StarterDeck.addCard(_make_blueprint(f"Common{index}", rarity="common"))

    class UnlockableDeck(Deck):
        pass

    for index in range(27):
        UnlockableDeck.addCard(_make_blueprint(f"Uncommon{index}", rarity="uncommon"))
    for index in range(3):
        UnlockableDeck.addCard(_make_blueprint(f"Rare{index}", rarity="rare"))

    class DummyCharacter(_BaseTestCharacter):
        def __init__(self) -> None:
            super().__init__()
            self.start.deck = StarterDeck
            self.unlockableDeck = UnlockableDeck

    assets_root = tmp_path / "assets" / "buddy"
    include_cards = {f"Common{index}.png": True for index in range(45)}
    include_cards.update({f"Uncommon{index}.png": True for index in range(27)})
    include_cards.update({f"Rare{index}.png": True for index in range(3)})
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
    assert "Card Rarity Proportions Incorrect" in message
    assert "Remove the given amount of cards of given type" in message
    assert "1 rare" in message


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


def test_character_allows_inner_card_blueprints(tmp_path: Path, use_real_dependencies: bool) -> None:
    class StarterDeck(Deck):
        pass

    Image = ensure_pillow()
    inner_source = tmp_path / "inner" / "common0.png"
    inner_source.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (500, 380), (255, 255, 255, 255)).save(inner_source)

    include_cards: dict[str, bool] = {}

    for index in range(60):
        blueprint = _make_blueprint(f"Common{index}", rarity="common")
        if index == 0:
            blueprint.innerCardImage(str(inner_source))
            include_cards[f"Common{index}.png"] = False
        else:
            include_cards[f"Common{index}.png"] = True
        StarterDeck.addCard(blueprint)

    class UnlockableDeck(Deck):
        pass

    for index in range(37):
        UnlockableDeck.addCard(_make_blueprint(f"Uncommon{index}", rarity="uncommon"))
        include_cards[f"Uncommon{index}.png"] = True
    for index in range(3):
        UnlockableDeck.addCard(_make_blueprint(f"Rare{index}", rarity="rare"))
        include_cards[f"Rare{index}.png"] = True

    class DummyCharacter(_BaseTestCharacter):
        def __init__(self) -> None:
            super().__init__()
            self.start.deck = StarterDeck
            self.unlockableDeck = UnlockableDeck

    assets_root = tmp_path / "assets" / "buddy"
    _prepare_assets(assets_root, include_cards=include_cards)
    python_root = tmp_path / "python"
    _prepare_python_source(python_root)

    result = DummyCharacter.createMod(
        tmp_path / "dist",
        assets_root=assets_root,
        python_source=python_root,
        bundle=False,
        register_cards=False,
    )

    assert result == (tmp_path / "dist" / "Buddy")
    card_image = assets_root / "images" / "cards" / "Common0.png"
    assert not card_image.exists()


def test_character_collect_cards_and_validate(tmp_path: Path, use_real_dependencies: bool) -> None:
    class StarterDeck(Deck):
        pass

    include_cards: dict[str, bool] = {}

    for index in range(60):
        blueprint = _make_blueprint(f"Common{index}", rarity="common")
        StarterDeck.addCard(blueprint)
        include_cards[f"Common{index}.png"] = True

    class UnlockableDeck(Deck):
        pass

    for index in range(37):
        UnlockableDeck.addCard(_make_blueprint(f"Uncommon{index}", rarity="uncommon"))
        include_cards[f"Uncommon{index}.png"] = True
    for index in range(3):
        UnlockableDeck.addCard(_make_blueprint(f"Rare{index}", rarity="rare"))
        include_cards[f"Rare{index}.png"] = True

    class DummyCharacter(_BaseTestCharacter):
        def __init__(self) -> None:
            super().__init__()
            self.start.deck = StarterDeck
            self.unlockableDeck = UnlockableDeck

    assets_root = tmp_path / "assets" / "buddy"
    _prepare_assets(assets_root, include_cards=include_cards)

    character = DummyCharacter()
    decks = DummyCharacter.collect_cards(character)
    assert isinstance(decks, CharacterDeckSnapshot)
    assert decks.start_deck is StarterDeck
    assert decks.unlockable_deck is UnlockableDeck
    assert decks.total_cards == 100
    assert decks.unique_cards["Common0"].identifier == "Common0"

    report = DummyCharacter.validate(character, decks=decks, assets_root=assets_root)
    assert isinstance(report, CharacterValidationReport)
    assert report.is_valid
    assert report.format_errors() == ""
    assert isinstance(report.context["analytics"], DeckAnalytics)
    assert isinstance(report.context["analytics_table"], tuple)
    assert report.context["analytics"].combined.total_cards == decks.total_cards


def test_build_deck_analytics_generates_rows(tmp_path: Path, use_real_dependencies: bool) -> None:
    class StarterDeck(Deck):
        display_name = "Buddy Starter"

    StarterDeck.addCard(_make_blueprint("Common0", rarity="common"))
    StarterDeck.addCard(_make_blueprint("Common0", rarity="common"))
    StarterDeck.addCard(_make_blueprint("Uncommon0", rarity="uncommon"))

    class Unlockables(Deck):
        display_name = "Buddy Unlocks"

    Unlockables.addCard(_make_blueprint("Rare0", rarity="rare"))
    Unlockables.addCard(_make_blueprint("Rare1", rarity="rare"))

    class DummyCharacter(_BaseTestCharacter):
        def __init__(self) -> None:
            super().__init__()
            self.start.deck = StarterDeck
            self.unlockableDeck = Unlockables

    character = DummyCharacter()
    decks = DummyCharacter.collect_cards(character)

    analytics = build_deck_analytics(character, decks, rarity_targets=RARITY_TARGETS)

    assert isinstance(analytics, DeckAnalytics)
    assert all(isinstance(row, DeckAnalyticsRow) for row in analytics.rows)
    assert analytics.rows[0].label.startswith("Buddy starter")
    assert analytics.rows[-1].total_cards == len(decks.all_cards)

    table = analytics.as_table()
    assert isinstance(table, tuple)
    assert table[0]["duplicates"]["Common0"] == 2

    mapping = analytics.by_label()
    assert analytics.rows[1].label in mapping

    output_path = analytics.write_json(tmp_path / "analytics" / "summary.json")
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["rows"][-1]["total_cards"] == analytics.combined.total_cards
    assert data["rarity_targets"] == dict(RARITY_TARGETS)


def test_character_validation_hook_integration(tmp_path: Path, use_real_dependencies: bool) -> None:
    class StarterDeck(Deck):
        pass

    include_cards: dict[str, bool] = {}

    for index in range(60):
        StarterDeck.addCard(_make_blueprint(f"Common{index}", rarity="common"))
        include_cards[f"Common{index}.png"] = True

    class UnlockableDeck(Deck):
        pass

    for index in range(37):
        UnlockableDeck.addCard(_make_blueprint(f"Uncommon{index}", rarity="uncommon"))
        include_cards[f"Uncommon{index}.png"] = True
    for index in range(3):
        UnlockableDeck.addCard(_make_blueprint(f"Rare{index}", rarity="rare"))
        include_cards[f"Rare{index}.png"] = True

    class DummyCharacter(_BaseTestCharacter):
        def __init__(self) -> None:
            super().__init__()
            self.start.deck = StarterDeck
            self.unlockableDeck = UnlockableDeck

    assets_root = tmp_path / "assets" / "buddy"
    _prepare_assets(assets_root, include_cards=include_cards)
    python_root = tmp_path / "python"
    _prepare_python_source(python_root)

    plugin_name = "tests.validation_plugin"

    class _ValidationPlugin:
        name = "validation-plugin"

        def modbuilder_character_validate(self, **kwargs):  # type: ignore[no-untyped-def]
            report: CharacterValidationReport = kwargs["report"]
            report.add_error("Injected plugin error")
            return {"errors": ["Additional hook error"], "hook": CHARACTER_VALIDATION_HOOK}

    plugin = _ValidationPlugin()
    record = PluginRecord(
        name=plugin_name,
        module=plugin_name,
        obj=plugin,
        exposed=PLUGIN_MANAGER.exposed,
    )
    original_plugins = dict(PLUGIN_MANAGER._plugins)
    PLUGIN_MANAGER._plugins[plugin_name] = record
    try:
        character = DummyCharacter()
        decks = DummyCharacter.collect_cards(character)
        report = DummyCharacter.validate(character, decks=decks, assets_root=assets_root)
        assert not report.is_valid
        assert "Injected plugin error" in report.errors
        assert "Additional hook error" in report.errors
        assert plugin_name in report.context
        assert report.context[plugin_name]["hook"] == CHARACTER_VALIDATION_HOOK

        with pytest.raises(BaseModBootstrapError) as excinfo:
            DummyCharacter.createMod(
                tmp_path / "dist",
                assets_root=assets_root,
                python_source=python_root,
                bundle=False,
                register_cards=False,
            )
        message = str(excinfo.value)
        assert "Injected plugin error" in message
        assert "Additional hook error" in message
    finally:
        PLUGIN_MANAGER._plugins = original_plugins
