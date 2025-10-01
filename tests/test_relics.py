from types import SimpleNamespace

import pytest

from modules.basemod_wrapper import create_project
from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.basemod_wrapper.relics import RELIC_REGISTRY, Relic
from modules.basemod_wrapper import relics as relics_module
from mods.adaptive_deck_evolver import AdaptiveMechanicMod, AdaptiveTelemetryCore
from modules.modbuilder import Deck


class _RelicTestDeck(Deck):
    pass


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_relic_subclass_registration_and_project_integration(
    use_real_dependencies: bool, stubbed_runtime
) -> None:
    class BuddyDataCore(Relic):
        mod_id = "unit_test_mod"
        identifier = "unit_test_mod:buddy_core"
        display_name = "Buddy Core"
        description_text = "Test relic wiring."
        tier = "COMMON"
        landing_sound = "CLINK"
        relic_pool = "SHARED"
        image = "unit_test_mod/images/relics/buddy_core.png"

        def on_plan_finalised(self, mod: object, plan: object) -> None:
            notes = list(getattr(plan, "notes", ()))
            notes.append("buddy-core-note")
            plan.notes = tuple(dict.fromkeys(notes))

    try:
        record = RELIC_REGISTRY.record("unit_test_mod:buddy_core")
        assert record is not None
        plan = SimpleNamespace(notes=tuple(), mutations=tuple(), style_vector=None, source_combat=None)
        relic_instance = record.spawn_instance()
        relic_instance.on_plan_finalised(SimpleNamespace(), plan)
        assert "buddy-core-note" in plan.notes

        project = create_project("unit_test_mod", "Unit Test", "Buddy", "Relic test")
        project.register_relic_record(record)
        assert "unit_test_mod:buddy_core" in project._relic_records

        if not use_real_dependencies:
            basemod_stub = relics_module._basemod()
            basemod_stub.BaseMod.relics_registered.clear()
            project._register_relics()
            assert any(
                entry[0].relicId == record.identifier for entry in basemod_stub.BaseMod.relics_registered
            )
        else:
            clone = record.spawn_instance()
            assert clone.relicId == record.identifier
    finally:
        RELIC_REGISTRY.unregister("unit_test_mod:buddy_core")


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_adaptive_mod_telemetry_core_effect(use_real_dependencies: bool, tmp_path) -> None:
    _RelicTestDeck.clear()
    strike = SimpleCardBlueprint(
        identifier="telemetry_strike",
        title="Telemetry Strike",
        description="Deal 6 damage.",
        cost=1,
        card_type="ATTACK",
        target="ENEMY",
        rarity="COMMON",
        value=6,
        upgrade_value=3,
    )
    block = SimpleCardBlueprint(
        identifier="telemetry_guard",
        title="Telemetry Guard",
        description="Gain 5 Block.",
        cost=1,
        card_type="SKILL",
        target="SELF",
        rarity="COMMON",
        value=5,
        upgrade_value=3,
        effect="block",
    )
    _RelicTestDeck.addCard(strike)
    _RelicTestDeck.addCard(block)

    mod = AdaptiveMechanicMod(
        mod_id="adaptive_evolver",
        storage_path=tmp_path / "profile.json",
        deck=_RelicTestDeck,
        autosave=False,
    )
    mod.register_base_deck(_RelicTestDeck.cards())

    recorder = mod.begin_combat(
        "telemetry-combat",
        enemy="Lagavulin",
        floor=2,
        player_hp_start=70,
        relics=(AdaptiveTelemetryCore.identifier,),
    )
    assert any("Telemetry Core" in note for note in recorder.notes)

    for turn in range(1, 4):
        recorder.record_card_play(
            card_id="telemetry_strike",
            turn=turn,
            energy_before=3,
            energy_spent=1,
            energy_remaining=2,
            damage_dealt=9,
            enemy_hp_change=-9,
            status_effects={"enemy": {"vulnerable": 1}},
            cards_drawn=1,
        )
        recorder.record_card_play(
            card_id="telemetry_guard",
            turn=turn,
            energy_before=2,
            energy_spent=1,
            energy_remaining=1,
            block_gained=4,
            player_hp_change=-2,
            status_effects={"enemy": {"weak": 1}},
        )

    plan = mod.complete_combat(
        "telemetry-combat",
        victory=True,
        player_hp_end=64,
        reward_cards=("adaptive-option",),
    )

    assert "Telemetry Core" in " ".join(plan.notes)
    if plan.mutations:
        for mutation in plan.mutations:
            assert mutation.metadata.get("telemetry_core_boost") is True
            assert any("Telemetry Core" in note for note in mutation.notes)
    if plan.style_vector is not None:
        assert "Telemetry Core" in plan.style_vector.summary
        assert plan.style_vector.combo >= 0
    assert plan.source_combat is not None and plan.source_combat.startswith("telemetry_core")
