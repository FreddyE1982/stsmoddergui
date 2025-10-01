from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, List

import pytest

from modules.basemod_wrapper import experimental
from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.modbuilder.deck import Deck
from plugins import PLUGIN_MANAGER


def _write_fake_graalpy(executable: Path) -> None:
    executable.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("GraalPy 23.1.0")
    sys.exit(0)

if len(args) >= 3 and args[0:2] == ["-m", "pip"]:
    command = args[2]
    if command == "install":
        print("Simulated install", " ".join(args[3:]))
        sys.exit(0)
    if command == "show" and len(args) >= 4:
        package = args[3]
        print(f"Name: {package}")
        print("Version: 10.2.0")
        sys.exit(0)

print(json.dumps({"invocation": args}))
sys.exit(0)
""",
        encoding="utf8",
    )
    executable.chmod(0o755)


class BuddyDeck(Deck):
    display_name = "Buddy Rule Deck"


def _prepare_deck() -> None:
    BuddyDeck.clear()
    BuddyDeck.addCard(
        SimpleCardBlueprint(
            identifier="BuddyStrike",
            title="Buddy Strike",
            description="Deal {damage} damage.",
            cost=1,
            card_type="attack",
            target="enemy",
            rarity="basic",
            value=8,
            upgrade_value=3,
            starter=True,
        )
    )
    BuddyDeck.addCard(
        SimpleCardBlueprint(
            identifier="BuddyBrew",
            title="Buddy Brew",
            description="Gain {block} Block.",
            cost=1,
            card_type="skill",
            target="self",
            rarity="basic",
            effect="block",
            value=6,
            upgrade_value=3,
            keywords=("artifact",),
            keyword_values={"artifact": 1},
            starter=True,
        )
    )


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_rule_weaver_engine_activation(tmp_path: Path, use_real_dependencies: bool) -> None:
    for name in ("graalpy_rule_weaver", "graalpy_runtime"):
        try:
            experimental.off(name)
        except Exception:
            pass

    env_backup = {key: os.environ.get(key) for key in ("STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE", "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE", "GRAALPY_HOME")}

    try:
        _prepare_deck()

        if use_real_dependencies:
            graalpy_home = tmp_path / "graalpy_home"
            (graalpy_home / "bin").mkdir(parents=True)
            executable = graalpy_home / "bin" / "graalpy"
            _write_fake_graalpy(executable)
            os.environ["GRAALPY_HOME"] = str(graalpy_home)
        else:
            simulator = tmp_path / "simulator"
            simulator.write_text("#!/usr/bin/env python3\nimport sys; sys.exit(0)\n", encoding="utf8")
            simulator.chmod(0o755)
            os.environ["STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE"] = "1"
            os.environ["STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE"] = str(simulator)

        module = experimental.on("graalpy_rule_weaver")
        assert experimental.is_active("graalpy_runtime"), "Activating rule weaver must enable the GraalPy runtime."

        engine = module.get_engine()
        engine.register_blueprint_provider(BuddyDeck.cards)

        def _apply_damage_buff(context: module.RuleWeaverContext) -> module.MechanicActivation:
            reverts: List[Callable[[module.RuleWeaverContext], None]] = []
            reverts.append(context.adjust_card_values("BuddyStrike", value=11, upgrade_value=5))
            reverts.append(context.add_keyword_to_card("BuddyStrike", "refund", amount=1))
            return module.MechanicActivation(
                identifier="buddy_strike_buff",
                revert_callbacks=tuple(reverts),
                metadata={"source": "test"},
            )

        mutation = module.MechanicMutation(
            identifier="buddy_strike_buff",
            description="Boost Buddy Strike while testing keyword attachments.",
            apply=_apply_damage_buff,
            priority=25,
            tags=("cards", "combat"),
            metadata={"suite": "primary"},
        )

        engine.register_mutation(mutation, activate=True)

        strike = BuddyDeck.unique_cards()["BuddyStrike"]
        assert strike.value == 11
        assert strike.upgrade_value == 5
        assert "refund" in strike.keywords
        assert strike.keyword_values["refund"] == 1

        exposed = PLUGIN_MANAGER.exposed
        assert "experimental_graalpy_rule_weaver_engine" in exposed
        assert mutation.identifier in exposed["experimental_graalpy_rule_weaver_mutations"]
        assert mutation.identifier in exposed["experimental_graalpy_rule_weaver_active"]

        engine.deactivate_mutation(mutation.identifier)
        strike_after = BuddyDeck.unique_cards()["BuddyStrike"]
        assert strike_after.value == 8
        assert strike_after.upgrade_value == 3
        assert "refund" not in strike_after.keywords

        script_data = {
            "mutations": [
                {
                    "id": "buddy_brew_rework",
                    "description": "Tweak Buddy Brew to demonstrate script parsing.",
                    "operations": [
                        {
                            "type": "adjust_card",
                            "card_id": "BuddyBrew",
                            "cost": 0,
                            "value": 8,
                            "upgrade_value": 4,
                        },
                        {
                            "type": "add_keyword",
                            "card_id": "BuddyBrew",
                            "keyword": "exhaustive",
                            "amount": 2,
                            "card_uses": 2,
                            "card_uses_upgrade": 1,
                        },
                        {
                            "type": "set_description",
                            "card_id": "BuddyBrew",
                            "description": "Gain {block} Block and exhaust after {uses} uses.",
                        },
                    ],
                }
            ]
        }

        script_path = tmp_path / "buddy_rules.json"
        script_path.write_text(json.dumps(script_data, indent=2), encoding="utf8")

        module.load_script(script_path, activate=True)

        brew = BuddyDeck.unique_cards()["BuddyBrew"]
        assert brew.cost == 0
        assert brew.value == 8
        assert "exhaustive" in brew.keywords
        assert brew.card_uses == 2
        assert "uses" in brew._placeholders
        assert "exhaust" in brew.description.lower()

        module.deactivate()
        brew_after = BuddyDeck.unique_cards()["BuddyBrew"]
        assert brew_after.cost == 1
        assert brew_after.card_uses is None
        assert "exhaustive" not in brew_after.keywords

    finally:
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

