import json
import os
import sys
from pathlib import Path

import pytest

from modules.basemod_wrapper import experimental
from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.basemod_wrapper.project import ModProject
from plugins import PLUGIN_MANAGER

from tests.test_graalpy_rule_weaver import _write_fake_graalpy


def _restore_environment(snapshot):
    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_mechanics_only_project_runtime(tmp_path: Path, use_real_dependencies: bool) -> None:
    project = ModProject("buddy_mechanics", "Buddy Mechanics", "Buddy", "Runtime tweaks")

    blueprint = SimpleCardBlueprint(
        identifier="BuddyMechanic",
        title="Buddy Mechanic",
        description="Gain {block} Block.",
        cost=1,
        card_type="skill",
        target="self",
        rarity="common",
        effect="block",
        value=5,
        upgrade_value=2,
        keywords=("artifact",),
        keyword_values={"artifact": 1},
    )

    project.register_mechanic_blueprint_provider(lambda: (blueprint,))

    path_script = tmp_path / "buddy_rules.json"
    path_script.write_text(
        json.dumps(
            {
                "mutations": [
                    {
                        "id": "buddy_cost_rework",
                        "operations": [
                            {
                                "type": "adjust_card",
                                "card_id": "BuddyMechanic",
                                "cost": 0,
                                "secondary_value": 3,
                            },
                            {
                                "type": "set_description",
                                "card_id": "BuddyMechanic",
                                "description": "Gain {block} Block and refund energy.",
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf8",
    )

    project.register_mechanic_script_path(lambda path=path_script: path)

    package_root = tmp_path / "buddy_runtime_pkg"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf8")
    resource_script = package_root / "resource_rules.json"
    resource_script.write_text(
        json.dumps(
            {
                "mutations": [
                    {
                        "id": "buddy_keyword_attachments",
                        "operations": [
                            {
                                "type": "add_keyword",
                                "card_id": "BuddyMechanic",
                                "keyword": "exhaustive",
                                "amount": 2,
                                "card_uses": 2,
                                "card_uses_upgrade": 1,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf8",
    )

    original_sys_path = list(sys.path)
    sys.path.insert(0, str(tmp_path))
    project.register_mechanic_script_resource("buddy_runtime_pkg", "resource_rules.json")

    from modules.basemod_wrapper.experimental import graalpy_rule_weaver as rule_weaver

    def _apply(context: rule_weaver.RuleWeaverContext) -> rule_weaver.MechanicActivation:
        revert = context.adjust_card_values("BuddyMechanic", value=9)
        return rule_weaver.MechanicActivation(
            identifier="buddy_value_increase",
            revert_callbacks=(revert,),
        )

    mutation = rule_weaver.MechanicMutation(
        identifier="buddy_value_increase",
        description="Raise Buddy Mechanic block while testing mechanics-only builds.",
        apply=_apply,
        priority=50,
    )

    project.register_mechanic_mutation(mutation, activate=True)

    env_keys = (
        "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE",
        "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE",
        "GRAALPY_HOME",
    )
    env_snapshot = {key: os.environ.get(key) for key in env_keys}

    try:
        if use_real_dependencies:
            graalpy_home = tmp_path / "graalpy_home"
            (graalpy_home / "bin").mkdir(parents=True)
            fake_exe = graalpy_home / "bin" / "graalpy"
            _write_fake_graalpy(fake_exe)
            os.environ["GRAALPY_HOME"] = str(graalpy_home)
            os.environ.pop("STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE", None)
            os.environ.pop("STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE", None)
        else:
            simulator = tmp_path / "simulator"
            simulator.write_text("#!/usr/bin/env python3\nimport sys; sys.exit(0)\n", encoding="utf8")
            simulator.chmod(0o755)
            os.environ["STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE"] = "1"
            os.environ["STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE"] = str(simulator)
            os.environ.pop("GRAALPY_HOME", None)

        engine = project.enable_mechanics_runtime()
        assert experimental.is_active("graalpy_rule_weaver")
        assert engine is rule_weaver.get_engine()

        assert blueprint.cost == 0
        assert blueprint.value == 9
        assert "exhaustive" in blueprint.keywords
        assert blueprint.card_uses == 2
        assert blueprint.card_uses_upgrade == 1
        assert "refund" not in blueprint.keywords

        exposed_key = f"mod_project:{project.mod_id}:mechanics_runtime"
        exposed_payload = PLUGIN_MANAGER.exposed[exposed_key]
        resolved_script = str(path_script.resolve())
        assert resolved_script in exposed_payload["scripts"]
        assert mutation.identifier in exposed_payload["mutations"]

        project.enable_mechanics_runtime()
        assert blueprint.cost == 0
        assert blueprint.value == 9
        assert blueprint.card_uses == 2
        assert blueprint.keywords.count("exhaustive") == 1

    finally:
        _restore_environment(env_snapshot)
        sys.path[:] = original_sys_path
        sys.modules.pop("buddy_runtime_pkg", None)
        for module_name in ("graalpy_rule_weaver", "graalpy_runtime"):
            try:
                experimental.off(module_name)
            except Exception:
                pass
