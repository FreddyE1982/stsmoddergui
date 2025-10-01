import os
from pathlib import Path

import pytest

from modules.basemod_wrapper import experimental
from modules.basemod_wrapper.experimental.graalpy_runtime import GraalPyProvisioningState
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
