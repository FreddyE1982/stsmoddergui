import sys

import pytest

from modules.basemod_wrapper.card_types import CardType, CARD_TYPE_REGISTRY
from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.basemod_wrapper.project import ModProject
from plugins import PLUGIN_MANAGER


def test_card_type_registration_populates_registry(stubbed_runtime, use_real_dependencies):
    class Technique(CardType):
        mod_id = "buddy"
        identifier = "TECHNIQUE"
        display_name = "Technique"
        base_type = "SKILL"

    try:
        record = CARD_TYPE_REGISTRY.record("TECHNIQUE")
        assert record is not None
        assert record.mod_id == "buddy"
        assert record.display_name == "Technique"
        assert record.base_type == "SKILL"

        cardcrawl = stubbed_runtime[0]
        enum_container = cardcrawl.cards.AbstractCard.CardType
        assert getattr(enum_container, "TECHNIQUE") == "TECHNIQUE"
        assert Technique._registry_record is record
    finally:
        CARD_TYPE_REGISTRY.unregister("TECHNIQUE")


def test_simple_card_blueprint_accepts_custom_type(stubbed_runtime, use_real_dependencies):
    class Technique(CardType):
        mod_id = "buddy"
        identifier = "TECHNIQUE"
        display_name = "Technique"
        base_type = "SKILL"

    try:
        project = ModProject("buddy", "Buddy Mod", "Buddy", "Testing")
        project._color_enum = "BUDDY_COLOR"
        CARD_TYPE_REGISTRY.install_on_project(project)

        blueprint = SimpleCardBlueprint(
            identifier="BuddyTechnique",
            title="Technique Drill",
            description="Gain {block} Block.",
            cost=1,
            card_type="Technique",
            target="self",
            rarity="common",
            value=6,
            effect="block",
        )

        assert blueprint.card_type == "TECHNIQUE"
        assert blueprint.base_card_type == "SKILL"
        assert blueprint.card_type_descriptor == "Technique"

        project.add_simple_card(blueprint)
        registration = project.cards["BuddyTechnique"]
        card = registration.factory()

        assert getattr(card, "type", None) == "TECHNIQUE"
        assert "Technique" in card.getCardDescriptors()

        enum_patch = project._render_enum_patch()
        assert "public static AbstractCard.CardType TECHNIQUE;" in enum_patch
    finally:
        CARD_TYPE_REGISTRY.unregister("TECHNIQUE")


def test_card_type_registry_broadcasts_and_project_view(stubbed_runtime, use_real_dependencies):
    plugin_module = "tests.sample_plugins.card_type_listener"
    previous_plugins = dict(PLUGIN_MANAGER._plugins)
    previous_exposed = dict(PLUGIN_MANAGER._exposed)
    PLUGIN_MANAGER._plugins.pop(plugin_module, None)
    PLUGIN_MANAGER._exposed.pop("card_type_listener", None)
    CARD_TYPE_REGISTRY.unregister("DIGI_TECH")

    try:
        PLUGIN_MANAGER.register_plugin(plugin_module)
        listener = PLUGIN_MANAGER.exposed["card_type_listener"]
        listener.events.clear()

        class DigiTech(CardType):
            mod_id = "buddy"
            identifier = "DIGI_TECH"
            display_name = "Digi-Technik"
            base_type = "SKILL"

        try:
            assert listener.events, "Listener did not capture registration event"
            event_type, record, registry = listener.events[0]
            assert event_type == "registered"
            assert registry is CARD_TYPE_REGISTRY
            assert record.identifier == "DIGI_TECH"

            project = ModProject("buddy", "Buddy Mod", "Buddy", "Testing")
            project._color_enum = "BUDDY_COLOR"
            CARD_TYPE_REGISTRY.install_on_project(project)
            mapping = project.card_type_records
            assert mapping["DIGI_TECH"] is record

            with pytest.raises(TypeError):
                mapping["DIGI_TECH"] = record  # type: ignore[index]
        finally:
            CARD_TYPE_REGISTRY.unregister("DIGI_TECH")
            assert listener.events[-1][0] == "unregistered"
    finally:
        PLUGIN_MANAGER._plugins.clear()
        PLUGIN_MANAGER._plugins.update(previous_plugins)
        PLUGIN_MANAGER._exposed.clear()
        PLUGIN_MANAGER._exposed.update(previous_exposed)
        sys.modules.pop(plugin_module, None)
