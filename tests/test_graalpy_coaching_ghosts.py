from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import pytest

from modules.basemod_wrapper import experimental
from modules.modbuilder.deck import Deck
from plugins import PLUGIN_MANAGER


def _write_fake_graalpy(executable: Path) -> None:
    executable.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("GraalPy 23.0.0")
    sys.exit(0)

if len(args) >= 3 and args[0:2] == ["-m", "pip"]:
    command = args[2]
    if command == "install":
        print("Simulated install", " ".join(args[3:]))
        sys.exit(0)
    if command == "show" and len(args) >= 4:
        package = args[3]
        print(json.dumps({"name": package, "version": "1.0.0"}))
        sys.exit(0)

print("Unhandled GraalPy invocation", args, file=sys.stderr)
sys.exit(0)
""",
        encoding="utf8",
    )
    executable.chmod(0o755)


def _toggle_modules(off: Iterable[str]) -> None:
    for name in off:
        try:
            experimental.off(name)
        except Exception:
            pass


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_coaching_ghost_workflow(tmp_path: Path, use_real_dependencies: bool) -> None:
    _toggle_modules(("graalpy_coaching_ghosts", "graalpy_runtime"))

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

        module = experimental.on("graalpy_coaching_ghosts")
        assert experimental.is_active("graalpy_runtime"), "Activating coaching ghosts must enable the GraalPy runtime."

        engine = module.get_engine()
        assert isinstance(engine, module.GhostPlaybackEngine)

        ghost_run = module.GhostRun(
            ghost_id="buddy_top_run",
            player_name="Buddy",
            score=890,
            ascension_level=15,
            actions=(
                module.ActionRecord(
                    actor=module.ActionActor.GHOST,
                    floor=1,
                    turn=1,
                    action_type=module.GhostActionType.PLAY_CARD,
                    description="Buddy Strike on Jaw Worm",
                    payload={"card_id": "BuddyStrike", "damage": 9},
                ),
                module.ActionRecord(
                    actor=module.ActionActor.GHOST,
                    floor=1,
                    turn=1,
                    action_type=module.GhostActionType.END_TURN,
                    description="End turn",
                ),
            ),
            metadata={"notes": "High tempo"},
        )

        module.register_ghost_run(ghost_run, replace=True)

        session = engine.start_session("buddy_top_run", player_name="Buddy")
        assert session.ghost_id == "buddy_top_run"

        preview = module.preview_ghost_actions(session.session_id, count=2)
        assert len(preview) == 2 and preview[0].description.startswith("Buddy Strike")

        update = engine.record_player_action(
            session.session_id,
            module.ActionRecord(
                actor=module.ActionActor.PLAYER,
                floor=1,
                turn=1,
                action_type=module.GhostActionType.PLAY_CARD,
                description="Buddy Strike on Jaw Worm",
                payload={"card_id": "BuddyStrike", "damage": 9},
            ),
        )

        assert update.matched is True
        assert abs(update.score_delta) < 1e-6
        assert "Matched ghost action" in update.recommendation

        history = engine.session_history(session.session_id)
        assert history[-1].recommendation == update.recommendation

        # High level director integration
        class BuddyDeck(Deck):
            display_name = "Buddy"

        director = module.launch_coaching_ghosts(BuddyDeck, default_player_name="Buddy")
        director.register_run(ghost_run, replace=True)

        director_session = director.start_session("buddy_top_run")
        updates = director.record_turn(
            director_session.session_id,
            [
                {
                    "floor": 1,
                    "turn": 1,
                    "action_type": module.GhostActionType.PLAY_CARD,
                    "description": "Buddy Strike",
                    "payload": {"card_id": "BuddyStrike", "damage": 9},
                },
                {
                    "floor": 1,
                    "turn": 1,
                    "action_type": module.GhostActionType.END_TURN,
                    "description": "End turn",
                },
            ],
        )

        assert updates[0].matched is True
        assert updates[-1].pace_delta >= 0

        from modules.modbuilder.character import Character

        character = Character()
        registry = director.apply_to_character(character)
        assert director_session.session_id in registry
        assert registry[director_session.session_id]["ghost_id"] == "buddy_top_run"

        assert PLUGIN_MANAGER.exposed["experimental_graalpy_ghosts_engine"] is engine
        assert callable(PLUGIN_MANAGER.exposed["experimental_graalpy_ghosts_launch"])
    finally:
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _toggle_modules(("graalpy_coaching_ghosts", "graalpy_runtime"))
