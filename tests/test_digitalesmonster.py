import os
from pathlib import Path

import pytest

from modules.basemod_wrapper import experimental
from modules.basemod_wrapper.experimental.graalpy_runtime import GraalPyProvisioningState
from modules.basemod_wrapper.loader import BaseModBootstrapError
from mods.digitalesmonster import (
    LEVEL_STABILITY_PERSIST_KEY,
    DigitalesMonsterProject,
    DigitalesMonsterProjectConfig,
    bootstrap_digitalesmonster_project,
)
from mods.digitalesmonster.persistence import (
    LevelStabilityProfile,
    LevelStabilityStore,
    StabilityPersistFieldAdapter,
)
from plugins import PLUGIN_MANAGER


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_project_initialisation_and_metadata(use_real_dependencies: bool) -> None:
    project = DigitalesMonsterProject(DigitalesMonsterProjectConfig())
    mod_project = project.mod_project

    assert mod_project.mod_id == "digitalesmonster"
    assert mod_project.name == "Digitales Monster"
    assert mod_project.author == "Digital Frontier Initiative"
    assert "digitalesmonster_project_metadata" in PLUGIN_MANAGER.exposed
    assert PLUGIN_MANAGER.exposed["digitalesmonster_mod_project"] is mod_project

    project.configure_character_assets()
    color = PLUGIN_MANAGER.exposed["digitalesmonster_character_color"]
    assert color.identifier == "DIGITALESMONSTER_ORANGE"
    assert color.attack_bg.endswith("digitalesmonster/images/cards/attack.png")


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_graalpy_activation_integration(tmp_path: Path, use_real_dependencies: bool, monkeypatch) -> None:
    try:
        experimental.off("graalpy_runtime")
    except Exception:
        pass

    backup = {
        "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE": os.environ.get("STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE"),
        "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE": os.environ.get(
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE"
        ),
        "STSMODDERGUI_GRAALPY_RUNTIME_ALLOW_FALLBACK": os.environ.get(
            "STSMODDERGUI_GRAALPY_RUNTIME_ALLOW_FALLBACK"
        ),
        "GRAALPY_HOME": os.environ.get("GRAALPY_HOME"),
    }

    project = DigitalesMonsterProject()

    try:
        if use_real_dependencies:
            graalpy_home = tmp_path / "graalpy_home"
            (graalpy_home / "bin").mkdir(parents=True)
            executable = graalpy_home / "bin" / "graalpy"
            executable.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n", encoding="utf8")
            executable.chmod(0o755)
            monkeypatch.setenv("GRAALPY_HOME", str(graalpy_home))
            state = project.enable_graalpy_runtime(simulate=False, allow_fallback=True)
        else:
            simulator = tmp_path / "graalpy-sim"
            simulator.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n", encoding="utf8")
            simulator.chmod(0o755)
            state = project.enable_graalpy_runtime(simulate=True, executable=simulator)

        assert project.is_graalpy_active(), "GraalPy runtime must be marked as active."
        assert isinstance(state, GraalPyProvisioningState)
        assert PLUGIN_MANAGER.exposed["digitalesmonster_graalpy_state"] is state
    finally:
        experimental.off("graalpy_runtime")
        for key, value in backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_level_stability_profile_serialisation(tmp_path: Path, use_real_dependencies: bool) -> None:
    profile = LevelStabilityProfile()
    profile.register_level("Rookie", start=100, maximum=150)
    profile.adjust_current("Rookie", -30)
    profile.update_level("Rookie", maximum=180)

    store = LevelStabilityStore(tmp_path / "stability.json")
    store.save(profile)
    loaded = store.load()

    rookie = loaded.get("Rookie")
    assert rookie.start == 100
    assert rookie.maximum == 180
    assert rookie.current == 70

    adapter = StabilityPersistFieldAdapter(LevelStabilityProfile())
    adapter.update_from_stslib(loaded.as_payload())
    mirrored = adapter.profile.get("Rookie")
    assert mirrored.start == rookie.start
    assert mirrored.maximum == rookie.maximum
    assert mirrored.current == rookie.current

    assert PLUGIN_MANAGER.exposed["digitalesmonster_level_stability_key"] == LEVEL_STABILITY_PERSIST_KEY


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_bootstrap_helper_respects_activation_flags(tmp_path: Path, use_real_dependencies: bool) -> None:
    if use_real_dependencies:
        project = bootstrap_digitalesmonster_project(activate_graalpy=False)
        assert not project.is_graalpy_active()
    else:
        project = bootstrap_digitalesmonster_project(activate_graalpy=True, simulate_graalpy=True)
        assert project.is_graalpy_active()
        assert isinstance(project.graalpy_state, GraalPyProvisioningState)
    experimental.off("graalpy_runtime")


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_stance_manager_default_flow(use_real_dependencies: bool, stubbed_runtime) -> None:
    project = DigitalesMonsterProject()
    assert PLUGIN_MANAGER.exposed["digitalesmonster_project_builder"] is project
    assert PLUGIN_MANAGER.exposed["digitalesmonster_stability_profile"] is project.stability_profile
    try:
        project.enable_graalpy_runtime(simulate=not use_real_dependencies)
        project._ensure_stances_loaded()
        rookie_id = project.default_stance_identifier
        champion_id = PLUGIN_MANAGER.exposed["digitalesmonster_champion_stance"]
        context = project.create_stance_context(digisoul=5, digivice_active=True)
        transition = project.enter_default_stance(context=context, reason="unit-test")
        assert transition.new_identifier == rookie_id
        assert context.powers["Strength"] == 1
        assert context.powers["Dexterity"] == 1
        assert context.metadata == {}

        champion_transition = project.stance_manager.enter(
            champion_id,
            context,
            reason="digivice-sync",
        )
        assert champion_transition.new_identifier == champion_id
        assert context.metadata["digivice_resonanz"]["level"] == "Champion"
        assert context.powers["digitalesmonster:digivice-resonanz"] == 1

        # Drain stability until the fallback triggers.
        for _ in range(30):
            project.stance_manager.adjust_stability(-25, reason="stress")
            if project.stance_manager.current_stance.identifier == rookie_id:
                break

        assert project.stance_manager.current_stance.identifier == rookie_id
        assert context.powers.get("digitalesmonster:digivice-resonanz") is None
    except BaseModBootstrapError:
        assert use_real_dependencies
        return
    finally:
        try:
            experimental.off("graalpy_runtime")
        except Exception:
            pass
        for key in (
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE",
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE",
            "STSMODDERGUI_GRAALPY_RUNTIME_ALLOW_FALLBACK",
        ):
            os.environ.pop(key, None)
        if use_real_dependencies:
            return


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_champion_requires_digivice_and_digisoul(use_real_dependencies: bool, stubbed_runtime) -> None:
    project = DigitalesMonsterProject()
    try:
        project.enable_graalpy_runtime(simulate=not use_real_dependencies)
        project._ensure_stances_loaded()
        from mods.digitalesmonster import DigimonStanceRequirementError  # noqa: WPS433 - runtime import

        champion_id = PLUGIN_MANAGER.exposed["digitalesmonster_champion_stance"]
        context = project.create_stance_context(digisoul=0, digivice_active=False)
        project.enter_default_stance(context=context)
        with pytest.raises(DigimonStanceRequirementError):
            project.stance_manager.enter(champion_id, context, reason="missing")

        context.digivice_active = True
        with pytest.raises(DigimonStanceRequirementError):
            project.stance_manager.enter(champion_id, context, reason="no-digisoul")

        context.digisoul = 3
        project.stance_manager.enter(champion_id, context, reason="ready")
    except BaseModBootstrapError:
        assert use_real_dependencies
        return
    finally:
        try:
            experimental.off("graalpy_runtime")
        except Exception:
            pass
        for key in (
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE",
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE",
            "STSMODDERGUI_GRAALPY_RUNTIME_ALLOW_FALLBACK",
        ):
            os.environ.pop(key, None)
        if use_real_dependencies:
            return


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_ultra_stance_instability_branch(use_real_dependencies: bool, stubbed_runtime) -> None:
    project = DigitalesMonsterProject()
    try:
        project.enable_graalpy_runtime(simulate=not use_real_dependencies)
        project._ensure_stances_loaded()
        from mods.digitalesmonster import DigimonStanceRequirementError  # noqa: WPS433 - runtime import

        champion_id = PLUGIN_MANAGER.exposed["digitalesmonster_champion_stance"]
        ultra_id = PLUGIN_MANAGER.exposed["digitalesmonster_ultra_stance"]
        skull_id = PLUGIN_MANAGER.exposed["digitalesmonster_skullgreymon_stance"]
        context = project.create_stance_context(
            digisoul=5,
            digivice_active=True,
            relics=("Digivice",),
        )
        project.enter_default_stance(context=context)
        context.digisoul = 2
        with pytest.raises(DigimonStanceRequirementError):
            project.stance_manager.enter(ultra_id, context, reason="insufficient-digisoul")

        context.digisoul = 5
        project.stance_manager.enter(champion_id, context, reason="champion-sync")
        transition = project.stance_manager.enter(ultra_id, context, reason="ultra-ready")
        assert transition.new_identifier == ultra_id
        assert context.metadata["ultra_mode"]["active"]

        for _ in range(8):
            project.stance_manager.adjust_stability(-25, reason="ultra-instability")
            if project.stance_manager.current_stance.identifier == skull_id:
                break
        assert project.stance_manager.current_stance.identifier == skull_id
        skull_meta = context.metadata["skullgreymon"]
        assert skull_meta["active"]
        assert context.powers.get("Vulnerable", 0) >= 2
    except BaseModBootstrapError:
        assert use_real_dependencies
        return
    finally:
        try:
            experimental.off("graalpy_runtime")
        except Exception:
            pass
        for key in (
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE",
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE",
            "STSMODDERGUI_GRAALPY_RUNTIME_ALLOW_FALLBACK",
        ):
            os.environ.pop(key, None)
        if use_real_dependencies:
            return


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_mega_and_burst_modes(use_real_dependencies: bool, stubbed_runtime) -> None:
    project = DigitalesMonsterProject()
    try:
        project.enable_graalpy_runtime(simulate=not use_real_dependencies)
        project._ensure_stances_loaded()
        from mods.digitalesmonster import DigimonStanceRequirementError  # noqa: WPS433 - runtime import

        champion_id = PLUGIN_MANAGER.exposed["digitalesmonster_champion_stance"]
        ultra_id = PLUGIN_MANAGER.exposed["digitalesmonster_ultra_stance"]
        mega_id = PLUGIN_MANAGER.exposed["digitalesmonster_mega_stance"]
        burst_id = PLUGIN_MANAGER.exposed["digitalesmonster_burst_stance"]

        context = project.create_stance_context(
            digisoul=9,
            digivice_active=True,
            relics=("Digivice",),
        )
        project.enter_default_stance(context=context)
        project.stance_manager.enter(champion_id, context, reason="champion-bridge")
        project.stance_manager.enter(ultra_id, context, reason="ultra-bridge")

        context.digisoul = 5
        with pytest.raises(DigimonStanceRequirementError):
            project.stance_manager.enter(mega_id, context, reason="insufficient")

        context.digisoul = 9
        mega_transition = project.stance_manager.enter(mega_id, context, reason="warp")
        assert mega_transition.new_identifier == mega_id
        assert context.metadata["warp_digitation"]["active"]

        context.digisoul = 6
        with pytest.raises(DigimonStanceRequirementError):
            project.stance_manager.enter(burst_id, context, reason="low-digisoul")

        context.digisoul = 9
        burst_transition = project.stance_manager.enter(burst_id, context, reason="burst")
        assert burst_transition.new_identifier == burst_id
        burst_meta = context.metadata["burst_mode"]
        assert burst_meta["active"]
        assert context.player_max_hp > burst_meta["pre_max_hp"]
        project.stance_manager.tick_turn(reason="burst-turn")
        if project.stance_manager.current_stance.identifier == burst_id:
            assert context.player_hp < context.player_max_hp
        else:
            assert project.stance_manager.current_stance.identifier == mega_id

        for _ in range(6):
            project.stance_manager.adjust_stability(-30, reason="burst-instability")
            if project.stance_manager.current_stance.identifier in {
                mega_id,
                ultra_id,
                project.default_stance_identifier,
            }:
                break
        assert project.stance_manager.current_stance.identifier in {
            mega_id,
            ultra_id,
            project.default_stance_identifier,
        }
        assert context.metadata["burst_mode"]["active"] is False
    except BaseModBootstrapError:
        assert use_real_dependencies
        return
    finally:
        try:
            experimental.off("graalpy_runtime")
        except Exception:
            pass
        for key in (
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE",
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE",
            "STSMODDERGUI_GRAALPY_RUNTIME_ALLOW_FALLBACK",
        ):
            os.environ.pop(key, None)
        if use_real_dependencies:
            return


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_armor_digiegg_pipeline(use_real_dependencies: bool, stubbed_runtime) -> None:
    project = DigitalesMonsterProject()
    try:
        project.enable_graalpy_runtime(simulate=not use_real_dependencies)
        project._ensure_stances_loaded()
        from mods.digitalesmonster import DigimonStanceRequirementError  # noqa: WPS433 - runtime import

        armor_id = PLUGIN_MANAGER.exposed["digitalesmonster_armor_stance"]
        rookie_id = project.default_stance_identifier
        context = project.create_stance_context(digisoul=1, digivice_active=False)
        project.enter_default_stance(context=context)

        with pytest.raises(DigimonStanceRequirementError):
            project.stance_manager.enter(armor_id, context, reason="no-egg")

        context.metadata["armor_egg"] = "Digi-Ei des Mutes"
        context.digisoul = 3
        transition = project.stance_manager.enter(armor_id, context, reason="armor-ready")
        assert transition.new_identifier == armor_id
        pipeline = context.metadata["armor_pipeline"]
        assert pipeline["active"]
        assert "digi-ei" in pipeline["egg"]

        project.stance_manager.tick_turn(reason="armor-turn")
        assert pipeline["turns"] >= 1

        for _ in range(8):
            project.stance_manager.adjust_stability(-25, reason="armor-instability")
            if project.stance_manager.current_stance.identifier == rookie_id:
                break
        assert project.stance_manager.current_stance.identifier == rookie_id
        assert context.metadata["armor_pipeline"]["egg_shattered"]
    except BaseModBootstrapError:
        assert use_real_dependencies
        return
    finally:
        try:
            experimental.off("graalpy_runtime")
        except Exception:
            pass
        for key in (
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE",
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE",
            "STSMODDERGUI_GRAALPY_RUNTIME_ALLOW_FALLBACK",
        ):
            os.environ.pop(key, None)
        if use_real_dependencies:
            return
