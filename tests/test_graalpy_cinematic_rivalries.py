"""End-to-end tests for the GraalPy cinematic rivalry experimental module."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import pytest

from modules.basemod_wrapper import experimental
from plugins import PLUGIN_MANAGER


def _write_fake_graalpy(executable: Path) -> None:
    executable.write_text(
        """#!/usr/bin/env python3
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("GraalPy 23.0.0")
    sys.exit(0)

if len(args) >= 3 and args[0:2] == ["-m", "pip"]:
    command = args[2]
    if command == "install":
        # Simulate a successful pip install invocation.
        print("Simulated install", " ".join(args[3:]))
        sys.exit(0)
    if command == "show" and len(args) >= 4:
        package = args[3]
        print(f"Name: {package}")
        if package.lower() == "pillow":
            print("Version: 10.1.0")
        else:
            print("Version: 1.0.0")
        sys.exit(0)

print("Unhandled GraalPy invocation", args, file=sys.stderr)
sys.exit(0)
""",
        encoding="utf8",
    )
    executable.chmod(0o755)


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_cinematic_rivalry_pipeline(tmp_path: Path, use_real_dependencies: bool) -> None:
    # Ensure a clean slate before configuring the environment.
    for name in ("graalpy_cinematic_rivalries", "graalpy_runtime"):
        try:
            experimental.off(name)
        except Exception:
            pass

    env_backup = {key: os.environ.get(key) for key in (
        "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE",
        "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE",
        "GRAALPY_HOME",
    )}

    try:
        if use_real_dependencies:
            graalpy_home = tmp_path / "graalpy_home"
            (graalpy_home / "bin").mkdir(parents=True)
            executable = graalpy_home / "bin" / "graalpy"
            _write_fake_graalpy(executable)
            os.environ["GRAALPY_HOME"] = str(graalpy_home)
        else:
            simulator = tmp_path / "simulated_graalpy"
            simulator.write_text("#!/usr/bin/env python3\nimport sys; sys.exit(0)\n", encoding="utf8")
            simulator.chmod(0o755)
            os.environ["STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE"] = "1"
            os.environ["STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE"] = str(simulator)

        module = experimental.on("graalpy_cinematic_rivalries")
        assert experimental.is_active("graalpy_runtime"), "Activating rivalries must enable GraalPy runtime."

        engine = module.get_engine()
        assert isinstance(engine, module.RivalryEngine)

        initial_frame = module.IntentFrame(
            turn=1,
            title="Opening Gambit",
            description="Guardian sizes up the intruder.",
            actions=(
                module.IntentAction(
                    action="buff",
                    value=3.0,
                    metadata={"source": "test"},
                ),
            ),
        )
        initial_script = module.RivalryScript(
            boss_id="guardian",
            rivalry_name="Guardian Rivalry",
            frames=(initial_frame,),
            metadata={"origin": "unit-test"},
        )

        director = module.launch_cinematic_rivalry(
            "guardian",
            rivalry_name="Guardian Rivalry",
            narrative="Guardian versus the fearless Buddy.",
            initial_script=initial_script,
            soundtrack="audio/guardian.ogg",
        )

        # Register a granular listener to ensure both API tiers stay in sync.
        captured: List[module.RivalryScript] = []
        module.register_listener(captured.append, boss_id="guardian")

        event = module.BossTelemetryEvent(
            boss_id="guardian",
            turn=1,
            event_type=module.TelemetryEventType.DAMAGE_DEALT,
            payload={"amount": 14},
        )
        updated_script = director.record_event(event)

        assert updated_script.frames[-1].turn == 2
        adaptive_action = updated_script.frames[-1].actions[0]
        assert adaptive_action.metadata["source"] == "adaptive_damage"
        assert adaptive_action.value >= 4.0
        assert captured, "Listeners registered on the granular API must receive updates."

        from modules.modbuilder.character import Character

        character = Character()
        applied = director.apply_to_character(character)
        registry = getattr(character, "cinematic_rivalry_scripts")
        assert registry["guardian"]["script"] == applied
        assert registry["guardian"]["narrative"].startswith("Guardian versus")

        # The plugin manager should expose the engine and record helper globally.
        assert PLUGIN_MANAGER.exposed["experimental_graalpy_rivalries_engine"] is engine
        assert PLUGIN_MANAGER.exposed["experimental_graalpy_rivalries_record"] is module.record_event

        follow_up = module.BossTelemetryEvent(
            boss_id="guardian",
            turn=2,
            event_type=module.TelemetryEventType.DAMAGE_DEALT,
            payload={"amount": 6},
        )
        module.record_event(follow_up)
        assert len(engine.scripts()["guardian"].frames) >= 1
    finally:
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for name in ("graalpy_cinematic_rivalries", "graalpy_runtime"):
            try:
                experimental.off(name)
            except Exception:
                pass
