from __future__ import annotations

import json
from pathlib import Path

import pytest

from mods.adaptive_deck_evolver import AdaptiveMechanicMod, DeckMutationPlan
from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.modbuilder import Deck


class _TestDeck(Deck):
    pass


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_adaptive_mechanic_mod_generates_evolution_plan(
    tmp_path: Path, use_real_dependencies: bool
) -> None:
    storage_path = tmp_path / "profile.json"
    _TestDeck.clear()
    strike = SimpleCardBlueprint(
        identifier="strike_buddy",
        title="Buddy Strike",
        description="Deal 6 damage.",
        cost=1,
        card_type="ATTACK",
        target="ENEMY",
        rarity="COMMON",
        value=6,
        upgrade_value=3,
    )
    guard = SimpleCardBlueprint(
        identifier="guard_pal",
        title="Buddy Guard",
        description="Gain 5 Block.",
        cost=1,
        card_type="SKILL",
        target="SELF",
        rarity="COMMON",
        value=5,
        upgrade_value=3,
        effect="block",
    )
    _TestDeck.addCard(strike)
    _TestDeck.addCard(guard)

    mod = AdaptiveMechanicMod(
        mod_id="buddy_mod",
        storage_path=storage_path,
        deck=_TestDeck,
        autosave=True,
    )
    mod.register_base_deck(_TestDeck.cards())
    if use_real_dependencies:
        mod.save()
        assert storage_path.exists()

    recorder = mod.begin_combat(
        "combat-1",
        enemy="Lagavulin",
        floor=1,
        player_hp_start=70,
        relics=("Lantern",),
    )

    for turn in range(1, 4):
        recorder.record_card_play(
            card_id="strike_buddy",
            turn=turn,
            energy_before=3,
            energy_spent=1,
            energy_remaining=2,
            damage_dealt=12,
            enemy_hp_change=-12,
            status_effects={"enemy": {"vulnerable": 2}},
            cards_drawn=1,
            exhausted=False,
            retained=False,
        )
        recorder.record_card_play(
            card_id="guard_pal",
            turn=turn,
            energy_before=2,
            energy_spent=1,
            energy_remaining=1,
            block_gained=2,
            player_hp_change=-3,
            status_effects={"enemy": {"weak": 1}},
            cards_drawn=0,
            exhausted=False,
            retained=True,
        )

    recorder.record_card_play(
        card_id="guard_pal",
        turn=4,
        energy_before=3,
        energy_spent=2,
        energy_remaining=1,
        block_gained=1,
        player_hp_change=-6,
        status_effects={"player": {"frail": 1}},
        cards_drawn=0,
        exhausted=True,
        retained=False,
    )

    plan = mod.complete_combat(
        "combat-1",
        victory=True,
        player_hp_end=62,
        reward_cards=("flex-option",),
    )

    assert isinstance(plan, DeckMutationPlan)
    assert not plan.is_empty()
    assert plan.style_vector is not None
    assert plan is mod.latest_plan
    assert storage_path.exists()

    payload = json.loads(storage_path.read_text(encoding="utf8"))
    assert payload["fights_recorded"] >= 1
    assert payload["wins"] == 1

    if plan.mutations:
        mutated_ids = {mutation.card_id for mutation in plan.mutations}
        assert "guard_pal" in mutated_ids
    if plan.new_cards:
        assert any(card.generated_by for card in plan.new_cards)

    deck_cards = _TestDeck.unique_cards()
    guard_blueprint = deck_cards.get("guard_pal")
    if guard_blueprint is not None:
        assert guard_blueprint.value >= 5 or guard_blueprint.cost <= 1

    dynamic_ids = {bp.identifier for bp in mod.iter_dynamic_blueprints()}
    for card in plan.new_cards:
        assert card.identifier in dynamic_ids
